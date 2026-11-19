"""Issue planning projections and revision-bound art decisions in the domain transaction."""

import hashlib
import json
from typing import Any

from tianxuan_core import PermissionDenied, TianxuanError, VersionConflict, _connection_call, _now


def module_read(store, actor, module):
    if module.startswith("requirement-"):
        store.require_native_module_read(actor, module)


def authorize(store, actor, payload):
    store._require_tenant_issue(actor, payload["issue_id"], write=True)
    if "module" in payload:
        module_read(store, actor, payload["module"])


def empty_plan():
    return dict(iteration="", milestone="", roadmap="", status="", estimated_minutes=0, custom_fields={})


@_connection_call
def roadmap(store, actor):
    if not store.db.in_transaction:
        store.db.execute("BEGIN")
    items = []
    for issue in store.list_issues(actor):
        plan = empty_plan()
        logged = 0
        for row in store.db.execute(
            "SELECT action, data FROM issue_work_events WHERE issue_id=? AND action IN ('work.plan','work.log') "
            "ORDER BY version",
            (issue["id"],),
        ):
            data = json.loads(row["data"])
            if row["action"] == "work.plan":
                plan.update(data["plan"])
            else:
                logged += data["minutes"]
        items.append(dict(id=issue["id"], title=issue["title"], plan=plan, logged_minutes=logged))
    items.sort(key=lambda item: tuple(item["plan"][k] for k in ("roadmap", "milestone", "iteration")))
    return {"items": items}


def snapshot(store, actor, issue_id, through_version=2**63 - 1):
    state = dict(
        id=issue_id,
        version=0,
        plan=empty_plan(),
        logs=[],
        logged_minutes=0,
        assets={},
        history=[],
    )
    checked_modules = set()
    for row in store.db.execute(
        "SELECT * FROM issue_work_events WHERE issue_id=? AND version<=? ORDER BY version", (issue_id, through_version)
    ):
        data = json.loads(row["data"])
        if "module" in data and data["module"] not in checked_modules:
            module_read(store, actor, data["module"])
            checked_modules.add(data["module"])
        event = dict(
            **data, action=row["action"], version=row["version"], actor=row["actor"], created_at=row["created_at"]
        )
        state["history"].append(event)
        state["version"] = event["version"]
        if event["action"] == "work.plan":
            state["plan"].update(data["plan"])
        elif event["action"] == "work.log":
            state["logs"].append(event)
            state["logged_minutes"] += data["minutes"]
        else:
            state["assets"][data["kind"]] = event
    return state


def bounded_text(value, limit=512, *, empty=False):
    return isinstance(value, str) and len(value) <= limit and (empty or bool(value.strip()))


def minutes(value, minimum):
    return type(value) is int and minimum <= value <= 100_000_000


def validate_plan(plan):
    if (
        not isinstance(plan, dict)
        or not plan
        or plan.keys() - {"iteration", "milestone", "roadmap", "status", "estimated_minutes", "custom_fields"}
    ):
        raise TianxuanError("invalid plan fields")
    for key, value in plan.items():
        if key == "custom_fields":
            valid = (
                isinstance(value, dict)
                and len(value) <= 100
                and all(
                    bounded_text(k, 100) and (bounded_text(v, 2000, empty=True) or type(v) in (int, float, bool))
                    for k, v in value.items()
                )
            )
        elif key == "estimated_minutes":
            valid = minutes(value, 0)
        else:
            valid = bounded_text(value, empty=True)
        if not valid:
            raise TianxuanError(f"invalid plan field {key}")


_KEYS = {
    "work.plan": {"plan"},
    "work.log": {"minutes", "note"},
    "work.submit_asset": {"kind", "module", "revision", "path"},
    "work.decide": {"kind", "module", "revision", "path", "decision", "note"},
}


@_connection_call
def execute(store, actor: str, name: str, payload: dict[str, Any], *, call_id=None, human=False):
    payload = dict(payload)
    if "call_id" in payload:
        embedded = payload.pop("call_id")
        if call_id is not None and call_id != embedded:
            raise TianxuanError("conflicting call_id")
        call_id = embedded
    issue_id = payload.get("issue_id")
    if not bounded_text(issue_id):
        raise TianxuanError("issue_id required")
    if name == "work.read":
        if payload.keys() != {"issue_id"} or call_id is not None:
            raise TianxuanError("invalid read arguments")
        if not store.db.in_transaction:
            store.db.execute("BEGIN")
        store._require_tenant_issue(actor, issue_id)
        return snapshot(store, actor, issue_id)
    if name == "work.decide" and not human:
        raise PermissionDenied("asset decision requires human confirmation")
    if name not in _KEYS or call_id is None:
        raise TianxuanError("unknown action or missing call_id")
    if name in ("work.log", "work.decide"):
        payload.setdefault("note", "")
    if payload.keys() != _KEYS[name] | {"issue_id", "expected_version"}:
        raise TianxuanError("invalid work arguments")
    payload = store._tool_payload(name, payload)
    expected = payload["expected_version"]
    if type(expected) is not int or expected < 0:
        raise TianxuanError("invalid expected_version")
    data = {key: payload[key] for key in _KEYS[name]}
    if name == "work.plan":
        validate_plan(data["plan"])
    if "note" in data and not bounded_text(data["note"], 4000, empty=True):
        raise TianxuanError("invalid note")
    if name == "work.log" and not minutes(data["minutes"], 1):
        raise TianxuanError("invalid minutes")
    if "kind" in data and (
        data["kind"] not in ("concept", "model")
        or not all(bounded_text(data[k]) for k in ("module", "revision", "path"))
    ):
        raise TianxuanError("invalid asset binding")
    if name == "work.decide" and data["decision"] not in ("approved", "changes_requested"):
        raise TianxuanError("invalid asset decision")

    def apply():
        current = store.db.execute(
            "SELECT COALESCE(MAX(version), 0) FROM issue_work_events WHERE issue_id=?", (issue_id,)
        ).fetchone()[0]
        if expected != current:
            raise VersionConflict("work version changed")
        if name == "work.submit_asset":
            native = getattr(store, "work_native_store", None)
            if native is None:
                raise TianxuanError("native asset store unavailable")
            try:
                content = native.read(store._tenant_of(actor), data["module"], data["revision"], data["path"])
            except ValueError as exc:
                raise TianxuanError("native asset unavailable") from exc
            data.update(digest=hashlib.sha256(content).hexdigest(), decision="pending")
        elif name == "work.decide":
            row = store.db.execute(
                "SELECT data FROM issue_work_events WHERE issue_id=? AND action IN ('work.submit_asset','work.decide') "
                "AND json_extract(data, '$.kind')=? ORDER BY version DESC LIMIT 1",
                (issue_id, data["kind"]),
            ).fetchone()
            asset = json.loads(row["data"]) if row else None
            if (
                not asset
                or asset["decision"] != "pending"
                or any(data[k] != asset[k] for k in ("module", "revision", "path"))
            ):
                raise VersionConflict("pending asset binding changed")
            data["digest"] = asset["digest"]
        store.db.execute(
            "INSERT INTO issue_work_events VALUES(?,?,?,?,?,?)",
            (issue_id, expected + 1, name, json.dumps(data, ensure_ascii=False), actor, _now()),
        )
        return {"id": issue_id, "version": expected + 1}

    # Reconstruct the exact acknowledged projection without copying its entire
    # history into every receipt. Reads always check current module access.
    receipt = store._run_tool_once(actor, name, payload, call_id, apply)
    return snapshot(store, actor, issue_id, receipt["version"])
