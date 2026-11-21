"""Evidence and durable close/reopen history for ordinary Tianxuan issues."""

import hashlib
import json

from issue_flow import definition, move, transition
from tianxuan_core import TianxuanError, TransitionRejected, VersionConflict, _connection_call, _now


def _asset_version(store, issue_id):
    return store.db.execute(
        "SELECT COALESCE(MAX(version),0) FROM issue_work_events WHERE issue_id=? "
        "AND action IN ('work.submit_asset','work.decide')",
        (issue_id,),
    ).fetchone()[0]


def _verify_submissions(store, actor, issue_id):
    from work_management import read_approved_asset

    rows = store.db.execute(
        "SELECT data FROM issue_work_events WHERE issue_id=? AND action='work.submit_asset' AND version IN "
        "(SELECT MAX(version) FROM issue_work_events WHERE issue_id=? AND action='work.submit_asset' "
        "GROUP BY json_extract(data,'$.kind'))",
        (issue_id, issue_id),
    )
    for row in rows:
        submission = json.loads(row[0])
        read_approved_asset(store, actor, issue_id, *(submission[k] for k in ("kind", "module", "revision", "path")))


def _record(store, issue, version, kind, actor, previous, target, revision, evidence):
    store.db.execute(
        "INSERT INTO issue_lifecycle(issue_id,version,kind,actor,previous,target,revision,evidence,asset_version,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            issue["id"],
            version,
            kind,
            actor,
            previous,
            target,
            revision,
            evidence,
            _asset_version(store, issue["id"]),
            _now(),
        ),
    )


def _accepted(store, issue, version, revision):
    row = store.db.execute(
        "SELECT evidence FROM issue_lifecycle WHERE issue_id=? AND kind='accepted' AND version=? AND revision=? AND asset_version=?",
        (issue["id"], version, revision, _asset_version(store, issue["id"])),
    ).fetchone()
    return row[0] if row else None


def _require_managed_children_accepted(store, issue):
    if issue["type"] != "requirement":
        return
    pending = store.db.execute(
        "SELECT 1 FROM issues i JOIN native_managed_issues n ON n.issue_id=i.id "
        "WHERE i.parent_id=? AND (i.status!='done' OR COALESCE(n.acceptance,'')='') LIMIT 1",
        (issue["id"],),
    ).fetchone()
    if pending:
        raise TransitionRejected("child awaits native workflow acceptance")
    if (
        issue["requirement_id"]
        and store.db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='native_entry_intents'"
        ).fetchone()
    ):
        if store.db.execute(
            "SELECT 1 FROM native_entry_intents WHERE tenant=? AND requirement=? AND receipt IS NULL LIMIT 1",
            (issue["tenant_id"], issue["requirement_id"]),
        ).fetchone():
            raise TransitionRejected("requirement entry awaits native planning")


def record_close(store, actor, issue, version):
    _require_managed_children_accepted(store, issue)
    _verify_submissions(store, actor, issue["id"])
    revision = store.issue_snapshot(actor, issue["id"])["revision"]
    evidence = _accepted(store, issue, version, revision)
    if not evidence:
        raise TransitionRejected("current acceptance evidence required")
    _record(store, issue, version + 1, "closed", actor, issue["status"], "done", revision, evidence)


@_connection_call
def close_native_aggregate(store, actor, issue_id, mapped_children):
    """The installed native entry supplies its complete, accepted task mapping."""
    if not store.db.in_transaction:
        store.db.execute("BEGIN IMMEDIATE")
    store._require_editor(actor)
    issue = store._require_tenant_issue(actor, issue_id, write=True)
    rows = store.db.execute(
        "SELECT i.id,i.status,n.acceptance FROM issues i LEFT JOIN native_managed_issues n ON n.issue_id=i.id "
        "WHERE i.parent_id=? AND i.tenant_id=? ORDER BY i.id",
        (issue_id, issue["tenant_id"]),
    ).fetchall()
    if (
        issue["type"] != "requirement"
        or not rows
        or {r["id"] for r in rows} != mapped_children
        or not all(r["status"] == "done" and r["acceptance"] for r in rows)
    ):
        raise TransitionRejected("all mapped children require native acceptance")
    revision = store.issue_snapshot(actor, issue_id)["revision"]
    version = definition(store, issue_id)[0]
    if not _accepted(store, issue, version, revision):
        evidence = "native-children:" + hashlib.sha256(json.dumps([tuple(r) for r in rows]).encode()).hexdigest()
        _record(store, issue, version, "accepted", actor, issue["status"], issue["status"], revision, evidence)
    return store.transition_issue(actor, issue_id, "done")


def _history(store, issue):
    issue_id = issue["id"]
    history = [
        dict(row)
        for row in store.db.execute(
            "SELECT version,kind,actor,previous,target,revision,evidence,asset_version,created_at FROM issue_lifecycle "
            "WHERE issue_id=? ORDER BY rowid",
            (issue_id,),
        )
    ]

    for row in store.db.execute(
        "SELECT actor,payload,created_at FROM events WHERE tenant_id=? AND target=? AND type='issue.transitioned' "
        "AND (json_extract(payload,'$.to') IN ('done','cancelled') OR json_extract(payload,'$.from') IN ('done','cancelled')) "
        "AND json_extract(payload,'$.lifecycle') IS NULL",
        (issue["tenant_id"], issue_id),
    ):
        change = json.loads(row["payload"])
        history.append(
            dict(
                kind="historical",
                actor=row["actor"],
                previous=change["from"],
                target=change["to"],
                created_at=row["created_at"],
                evidence=None,
                revision=None,
                version=None,
            )
        )
    return sorted(history, key=lambda event: event["created_at"])


def _previous(issue, history, stages, edges):
    if issue["status"] not in ("done", "cancelled"):
        return ""
    prior = next(
        (
            event["previous"]
            for event in reversed(history)
            if event["kind"] in ("historical", "closed") and event["target"] == issue["status"]
        ),
        "",
    )
    available = [s["id"] for s in stages if s["id"] not in ("done", "cancelled")]
    if prior in available:
        return prior
    # Event retention may have expired on an older ticket. Return to a stage
    # permitted to reach that terminal in its current definition.
    return next((e["from"] for e in edges if e["to"] == issue["status"] and e["from"] in available), "")


@_connection_call
def read(store, actor, issue_id, project):
    if not store.db.in_transaction:
        store.db.execute("BEGIN")
    issue = store._project_issue(actor, issue_id, project)
    version, _, stages, edges = definition(store, issue_id)
    revision = store.issue_snapshot(actor, issue_id)["revision"]
    history = _history(store, issue)
    managed = bool(store.db.execute("SELECT 1 FROM native_managed_issues WHERE issue_id=?", (issue_id,)).fetchone())
    return dict(
        id=issue_id,
        number=issue["number"],
        status=issue["status"],
        revision=revision,
        version=version,
        asset_version=_asset_version(store, issue_id),
        managed=managed,
        can_close=not managed and {"from": issue["status"], "to": "done"} in edges,
        reopen_to="" if managed else _previous(issue, history, stages, edges),
        accepted=_accepted(store, issue, version, revision),
        history=history,
    )


@_connection_call
def mutate(store, actor, issue_id, project, operation, expected_version, revision, comment, call_id, asset_version):
    if type(expected_version) is not int or expected_version < 0 or not isinstance(call_id, str) or not call_id.strip():
        raise TianxuanError("invalid lifecycle version or call_id")
    if operation not in ("accept", "close", "reopen") or (operation != "accept" and comment is not None):
        raise TianxuanError("invalid lifecycle operation")
    payload = dict(
        issue_id=issue_id,
        project=project,
        expected_version=expected_version,
        revision=revision,
        comment=comment,
        asset_version=asset_version,
    )

    def apply():
        issue = store._project_issue(actor, issue_id, project, write=True)
        state = read(store, actor, issue_id, project)
        if state["managed"]:
            raise TransitionRejected("native workflow owns this issue")
        if (
            state["version"] != expected_version
            or state["revision"] != revision
            or state["asset_version"] != asset_version
        ):
            raise VersionConflict("flow or content revision changed")
        previous = issue["status"]
        if operation == "accept":
            if not state["can_close"]:
                raise TransitionRejected("current stage does not allow closure")
            evidence = store.db.execute(
                "SELECT 1 FROM issue_comments WHERE id=? AND issue_id=? AND tenant_id=? AND trim(body)!=''",
                (comment, issue_id, issue["tenant_id"]),
            ).fetchone()
            if not evidence:
                raise TransitionRejected("select an existing evidence comment from this issue")
            if state["accepted"] and state["accepted"] != comment:
                raise VersionConflict("another acceptance was already recorded")
            if not state["accepted"]:
                _verify_submissions(store, actor, issue_id)
                _record(store, issue, expected_version, "accepted", actor, previous, previous, revision, comment)
        elif operation == "close":
            _, _, stages, _ = definition(store, issue_id)
            # This authenticated explicit decision is also the human signoff on a human review stage.
            human = any(s["id"] == previous and s["human"] for s in stages)
            transition(store, actor, issue, "done", human=human)
        else:
            target = state["reopen_to"]
            if not target:
                raise TransitionRejected("no reopen stage for this issue")
            move(store, actor, issue, target)
            _record(store, issue, expected_version + 1, "reopened", actor, previous, target, revision, None)
        return {"id": issue_id, "version": definition(store, issue_id)[0]}

    return store._run_tool_once(actor, "lifecycle." + operation, payload, call_id, apply)
