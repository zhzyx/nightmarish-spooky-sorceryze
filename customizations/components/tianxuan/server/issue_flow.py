"""Configurable stages and dependencies for ordinary Tianxuan issues."""

import json

from tianxuan_core import (
    ISSUE_TRANSITIONS,
    NotFound,
    PermissionDenied,
    TianxuanError,
    TransitionRejected,
    VersionConflict,
    _connection_call,
    _now,
)

DEFAULT_PROGRESS = {
    "backlog": 0,
    "planned": 10,
    "in-progress": 40,
    "blocked": 20,
    "in-review": 80,
    "done": 100,
    "cancelled": 0,
}
TOOLS = {"flow.read", "flow.configure", "flow.dependencies", "flow.advance"}


def definition(store, issue_id):
    row = store.db.execute("SELECT * FROM issue_flows WHERE issue_id=?", (issue_id,)).fetchone()
    if row and row["definition"]:
        stages, edges = json.loads(row["definition"])
        return row["version"], True, stages, edges
    stages = [dict(id=k, progress=p, human=False) for k, p in DEFAULT_PROGRESS.items()]
    edges = [{"from": k, "to": v} for k, values in ISSUE_TRANSITIONS.items() for v in sorted(values)]
    return row["version"] if row else 0, False, stages, edges


def dependency(store, actor, dep):
    try:
        return store._require_tenant_issue(actor, dep)
    except (PermissionDenied, NotFound) as exc:
        raise PermissionDenied("dependency unavailable") from exc


def dependencies(store, actor, issue_id):
    result = []
    for row in store.db.execute(
        "SELECT d.dependency, n.issue_id IS NULL OR coalesce(n.acceptance,'') != '' AS admitted "
        "FROM issue_dependencies d LEFT JOIN native_managed_issues n ON n.issue_id=d.dependency "
        "WHERE d.issue_id=? ORDER BY d.dependency",
        (issue_id,),
    ):
        issue = dependency(store, actor, row[0])
        result.append(
            {k: issue[k] for k in ("id", "title", "status")}
            | {"accepted": issue["status"] == "done" and bool(row["admitted"])}
        )
    return result


def read(store, actor, issue):
    version, configured, stages, edges = definition(store, issue["id"])
    progress = next((s["progress"] for s in stages if s["id"] == issue["status"]), 0)
    return dict(
        id=issue["id"],
        status=issue["status"],
        version=version,
        configured=configured,
        stages=stages,
        edges=edges,
        dependencies=dependencies(store, actor, issue["id"]),
        progress=progress,
    )


def authorize(store, actor, payload, result):
    issue_id = payload["issue_id"]
    store._require_tenant_issue(actor, issue_id, write=True)
    for dep in payload.get("dependencies", []):
        dependency(store, actor, dep)
    if result:
        for dep in result["dependencies"]:
            dependency(store, actor, dep["id"])


def bump(store, issue_id):
    store.db.execute(
        "INSERT INTO issue_flows(issue_id,version) VALUES (?,1) ON CONFLICT(issue_id) DO UPDATE SET version=version+1",
        (issue_id,),
    )


def transition(store, actor, issue, target, *, human=False):
    issue_id, current = issue["id"], issue["status"]
    _, _, stages, edges = definition(store, issue_id)
    stage = {s["id"]: s for s in stages}
    if {"from": current, "to": target} not in edges:
        raise TransitionRejected(f"{current} -> {target} is not allowed")
    if stage[current]["human"] != human:
        raise TransitionRejected("transition requires the matching human decision or ordinary action")
    deps = dependencies(store, actor, issue_id)
    if (
        target != "cancelled"
        and stage[target]["progress"] >= stage[current]["progress"]
        and any(not d["accepted"] for d in deps)
    ):
        raise TransitionRejected("prerequisite has not been accepted")
    store.db.execute("UPDATE issues SET status=?, updated_at=? WHERE id=?", (target, _now(), issue_id))
    store._event(issue["tenant_id"], "issue.transitioned", actor, issue_id, {"from": current, "to": target})
    bump(store, issue_id)
    if issue["requirement_id"]:
        store.sync_progress(issue["requirement_id"], actor=actor)


def validate_config(stages, edges, current):
    if (
        not isinstance(stages, list)
        or not 2 <= len(stages) <= 64
        or not isinstance(edges, list)
        or not 1 <= len(edges) <= 512
    ):
        raise TianxuanError("invalid flow definition")
    by_id = {}
    for s in stages:
        if (
            not isinstance(s, dict)
            or s.keys() != {"id", "progress", "human"}
            or not isinstance(s["id"], str)
            or not 0 < len(s["id"]) <= 64
            or s["id"].strip() != s["id"]
            or type(s["progress"]) is not int
            or not 0 <= s["progress"] <= 100
            or type(s["human"]) is not bool
            or s["id"] in by_id
        ):
            raise TianxuanError("invalid stage")
        by_id[s["id"]] = s["progress"]
    if (
        current not in by_id
        or by_id.get("done") != 100
        or any(value == 100 for key, value in by_id.items() if key != "done")
    ):
        raise TianxuanError("keep current stage and reserve 100 percent for done")
    seen = set()
    for e in edges:
        if (
            not isinstance(e, dict)
            or e.keys() != {"from", "to"}
            or not all(isinstance(v, str) and v in by_id for v in e.values())
        ):
            raise TianxuanError("invalid flow edge")
        pair = (e["from"], e["to"])
        if pair in seen or pair[0] == pair[1] or pair[0] in ("done", "cancelled"):
            raise TianxuanError("invalid terminal, duplicate or self edge")
        seen.add(pair)
    sources = {source for source, _ in seen}
    if any(s["human"] and s["id"] not in sources for s in stages):
        raise TianxuanError("a human stage requires an outgoing decision")


def set_dependencies(store, issue_id, deps):
    for dep in deps:
        if (
            dep == issue_id
            or store.db.execute(
                "WITH RECURSIVE chain(id) AS (SELECT dependency FROM issue_dependencies WHERE issue_id=? "
                "UNION SELECT d.dependency FROM issue_dependencies d JOIN chain ON d.issue_id=chain.id) "
                "SELECT 1 FROM chain WHERE id=?",
                (dep, issue_id),
            ).fetchone()
        ):
            raise TransitionRejected("cyclic dependency")
    store.db.execute("DELETE FROM issue_dependencies WHERE issue_id=?", (issue_id,))
    store.db.executemany(
        "INSERT INTO issue_dependencies(issue_id,dependency) VALUES (?,?)", [(issue_id, d) for d in deps]
    )


@_connection_call
def execute_flow(store, actor, name, payload, *, call_id=None, human=False):
    payload = dict(payload)
    if "call_id" in payload:
        embedded = payload.pop("call_id")
        if call_id is not None and call_id != embedded:
            raise TianxuanError("conflicting call_id")
        call_id = embedded
    issue_id = payload.get("issue_id")
    if not isinstance(issue_id, str) or not issue_id:
        raise TianxuanError("issue_id required")
    if name == "flow.read":
        if call_id is not None or payload.keys() != {"issue_id"}:
            raise TianxuanError("invalid flow read")
        if not store.db.in_transaction:
            store.db.execute("BEGIN")
        return read(store, actor, store._require_tenant_issue(actor, issue_id))
    keys = {
        "flow.configure": {"stages", "edges"},
        "flow.dependencies": {"dependencies"},
        "flow.advance": {"to_status"},
        "flow.judge": {"to_status"},
    }
    if name not in keys or call_id is None or payload.keys() != keys[name] | {"issue_id", "expected_version"}:
        raise TianxuanError("invalid flow arguments")
    if name == "flow.judge" and not human:
        raise PermissionDenied("human decision required")
    if type(payload["expected_version"]) is not int or payload["expected_version"] < 0:
        raise TianxuanError("invalid expected version")
    if name == "flow.dependencies":
        deps = payload["dependencies"]
        if (
            not isinstance(deps, list)
            or len(deps) > 256
            or not all(isinstance(d, str) and 0 < len(d) <= 256 for d in deps)
            or len(set(deps)) != len(deps)
        ):
            raise TianxuanError("invalid dependencies")
    if "to_status" in payload and not isinstance(payload["to_status"], str):
        raise TianxuanError("invalid target stage")

    def apply():
        issue = store._require_tenant_issue(actor, issue_id, write=True)
        if store.db.execute("SELECT 1 FROM native_managed_issues WHERE issue_id=?", (issue_id,)).fetchone():
            raise TransitionRejected("native workflow owns this issue")
        state = read(store, actor, issue)
        if state["version"] != payload["expected_version"]:
            raise VersionConflict("flow version changed")
        if name == "flow.configure":
            if any(s["human"] and s["id"] == issue["status"] for s in state["stages"]):
                raise TransitionRejected("current stage awaits human judgment")
            validate_config(payload["stages"], payload["edges"], issue["status"])
            bump(store, issue_id)
            store.db.execute(
                "UPDATE issue_flows SET definition=? WHERE issue_id=?",
                (json.dumps([payload["stages"], payload["edges"]]), issue_id),
            )
        elif name == "flow.dependencies":
            if issue["status"] in ("done", "cancelled"):
                raise TransitionRejected("terminal issue cannot change prerequisites")
            set_dependencies(store, issue_id, payload["dependencies"])
            bump(store, issue_id)
        else:
            transition(store, actor, issue, payload["to_status"], human=human)
        return read(store, actor, store.get_issue(issue_id))

    return store._run_tool_once(actor, name, payload, call_id, apply)
