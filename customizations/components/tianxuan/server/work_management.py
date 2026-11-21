"""Issue planning projections and revision-bound art decisions in the domain transaction."""

import hashlib
import io
import json
import re
import zipfile
from typing import Any

from issue_flow import definition
from tianxuan_core import (
    NotFound,
    PermissionDenied,
    TianxuanError,
    VersionConflict,
    _connection_call,
    _now,
    require_native_source_read,
)


def authorize(store, actor, payload):
    store._require_tenant_issue(actor, payload["issue_id"], write=True)
    if "module" in payload:
        require_native_source_read(store, actor, payload["module"])


def empty_plan():
    return dict(iteration="", milestone="", roadmap="", status="", estimated_minutes=0, custom_fields={})


@_connection_call
def project_fields(store, actor, project):
    store._validate_project(project)
    rows = store.db.execute(
        "SELECT key,label FROM project_issue_fields WHERE tenant_id=? AND project=? ORDER BY key",
        (store._tenant_of(actor), project),
    )
    return {"project": project, "fields": [dict(row) for row in rows]}


@_connection_call
def define_text_field(store, actor, project, key, label):
    store._require_editor(actor)
    store._validate_project(project)
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_.-]{0,99}", key) or not bounded_text(label, 100):
        raise TianxuanError("invalid project text field")
    store.db.execute(
        "INSERT INTO project_issue_fields VALUES (?,?,?,?) ON CONFLICT (tenant_id,project,key) "
        "DO UPDATE SET label=excluded.label",
        (store._tenant_of(actor), project, key, label.strip()),
    )
    return project_fields(store, actor, project)


@_connection_call
def roadmap(store, actor, *, project=None) -> dict[str, Any]:
    if not store.db.in_transaction:
        store.db.execute("BEGIN")
    items = []
    for issue in store.list_issues(actor, project=project):
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
        _, _, stages, _ = definition(store, issue["id"])
        progress = next((s["progress"] for s in stages if s["id"] == issue["status"]), 0)
        items.append(
            dict(
                id=issue["id"],
                title=issue["title"],
                status=issue["status"],
                progress=progress,
                plan=plan,
                logged_minutes=logged,
            )
        )
    items.sort(key=lambda item: tuple(item["plan"][k] for k in ("roadmap", "milestone", "iteration")))
    return {"items": items}


@_connection_call
def plan_membership(store, actor, issue_id, project):
    """Read the issue and both group counts from one project-visible snapshot."""
    if not store.db.in_transaction:
        store.db.execute("BEGIN")
    issue = store._require_tenant_issue(actor, issue_id)
    if issue["project"] != project:
        raise NotFound("issue not found in project")
    state = snapshot(store, actor, issue_id)
    fields = {key: state["plan"][key] for key in ("iteration", "milestone")}
    items = roadmap(store, actor, project=project)["items"]
    counts = {key: sum(item["plan"][key] == value for item in items) for key, value in fields.items()}
    return {"id": issue_id, "version": state["version"], "plan": fields, "counts": counts}


def snapshot(store, actor, issue_id, through_version=2**63 - 1) -> dict[str, Any]:
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
            require_native_source_read(store, actor, data["module"])
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


@_connection_call
def list_issue_artifacts(store, actor, project, number):
    issue = store.read_issue_number(actor, project, number)
    rows = store.db.execute(
        "SELECT version, data FROM issue_work_events WHERE issue_id=? AND action='work.submit_asset' "
        "ORDER BY version DESC",
        (issue["id"],),
    )
    references = []
    for row in rows:
        data = json.loads(row["data"])
        try:
            require_native_source_read(store, actor, data["module"])
        except (NotFound, PermissionDenied):
            continue
        references.append({
            "version": row["version"],
            **{k: data[k] for k in ("kind", "module", "revision", "path", "digest")},
        })
    return references


@_connection_call
def read_issue_artifact(store, actor, project, number, version):
    issue = store.read_issue_number(actor, project, number)
    if not 0 < version < 2**63:
        raise NotFound("unknown artifact reference")
    row = store.db.execute(
        "SELECT data FROM issue_work_events WHERE issue_id=? AND version=? AND action='work.submit_asset'",
        (issue["id"], version),
    ).fetchone()
    if not row:
        raise NotFound("unknown artifact reference")
    data = json.loads(row["data"])
    require_native_source_read(store, actor, data["module"])
    native = getattr(store, "work_native_store", None)
    if native is None:
        raise TianxuanError("native asset store unavailable")
    try:
        content = native.read(issue["tenant_id"], data["module"], data["revision"], data["path"])
    except ValueError as exc:
        raise VersionConflict("referenced artifact unavailable") from exc
    if hashlib.sha256(content).hexdigest() != data["digest"]:
        raise VersionConflict("referenced artifact digest changed")
    return content


@_connection_call
def read_approved_asset(store, actor, issue_id, kind, module, revision, path) -> bytes:
    """Resolve a pinned input against one snapshot of the current issue and ACL."""
    if kind not in ("concept", "model") or not all(bounded_text(v) for v in (issue_id, module, revision, path)):
        raise TianxuanError("invalid asset binding")
    if not store.db.in_transaction:
        store.db.execute("BEGIN")
    store._require_tenant_issue(actor, issue_id)
    require_native_source_read(store, actor, module)
    rows = store.db.execute(
        "SELECT action, data FROM issue_work_events WHERE issue_id=? AND action IN ('work.submit_asset','work.decide') "
        "AND json_extract(data, '$.kind')=? ORDER BY version DESC LIMIT 2",
        (issue_id, kind),
    ).fetchall()
    if [row["action"] for row in rows] != ["work.decide", "work.submit_asset"]:
        raise VersionConflict("asset has no current approval")
    decision, submission = (json.loads(row["data"]) for row in rows)
    binding = dict(kind=kind, module=module, revision=revision, path=path)
    if (
        decision.get("decision") != "approved"
        or submission.get("decision") != "pending"
        or any(event.get(key) != value for event in (decision, submission) for key, value in binding.items())
        or decision.get("digest") != submission.get("digest")
    ):
        raise VersionConflict("asset approval does not match current submission")
    native = getattr(store, "work_native_store", None)
    if native is None:
        raise TianxuanError("native asset store unavailable")
    try:
        content: bytes = native.read(store._tenant_of(actor), module, revision, path)
    except ValueError as exc:
        raise TianxuanError("native asset unavailable") from exc
    if hashlib.sha256(content).hexdigest() != decision.get("digest"):
        raise VersionConflict("approved asset digest changed")
    return content


@_connection_call
def godot_inputs(store, actor, issue_id) -> bytes:
    """Build one import project from every current issue asset in one ACL snapshot."""
    if not store.db.in_transaction:
        store.db.execute("BEGIN")
    store._require_tenant_issue(actor, issue_id)
    rows = store.db.execute(
        "SELECT data, version FROM issue_work_events WHERE issue_id=? AND action='work.submit_asset' "
        "AND json_extract(data, '$.kind') IN ('concept','model') "
        "AND version IN (SELECT MAX(version) FROM issue_work_events WHERE issue_id=? AND action='work.submit_asset' "
        "GROUP BY json_extract(data, '$.kind')) ORDER BY version",
        (issue_id, issue_id),
    ).fetchall()
    if not rows:
        raise VersionConflict("issue has no submitted Godot inputs")
    entries = {
        "project.godot": b'config_version=5\n[application]\nconfig/name="Approved issue assets"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
    }
    bindings = []
    for row in rows:
        submission = json.loads(row["data"])
        kind = submission["kind"]
        module, revision, path = (submission[k] for k in ("module", "revision", "path"))
        content = read_approved_asset(store, actor, issue_id, kind, module, revision, path)
        if kind == "concept" and content.startswith(b"\x89PNG\r\n\x1a\n"):
            name = "assets/concept.png"
        elif kind == "model" and content.startswith(b"glTF"):
            name = "assets/model.glb"
        else:
            raise TianxuanError("Godot issue input requires a PNG concept or GLB model")
        if len(content) > 8 * 1024 * 1024:
            raise TianxuanError("Godot input exceeds native file limit")
        entries[name] = content
        bindings.append([kind, module, revision, path, row["version"]])
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w") as archive:
        archive.comment = hashlib.sha256(json.dumps(bindings).encode()).hexdigest().encode("ascii")
        for name, data in entries.items():
            archive.writestr(zipfile.ZipInfo(name), data)
    return result.getvalue()


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
def execute(store, actor: str, name: str, payload: dict[str, Any], *, call_id=None, human=False) -> dict[str, Any]:
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
    field_edit = name == "work.plan" and "field_update" in payload
    keys = {"field_update"} if field_edit else _KEYS[name]
    if payload.keys() != keys | {"issue_id", "expected_version"}:
        raise TianxuanError("invalid work arguments")
    payload = store._tool_payload(name, payload)
    expected = payload["expected_version"]
    if type(expected) is not int or expected < 0:
        raise TianxuanError("invalid expected_version")
    data = {key: payload[key] for key in keys}
    if field_edit:
        field = payload["field_update"]
        if (
            not isinstance(field, dict)
            or field.keys() != {"key", "value"}
            or not bounded_text(field["key"], 100)
            or not bounded_text(field["value"], 2000, empty=True)
        ):
            raise TianxuanError("invalid project text field edit")
    elif name == "work.plan":
        validate_plan(data["plan"])
    if "note" in data and not bounded_text(data["note"], 4000, empty=True):
        raise TianxuanError("invalid note")
    if name == "work.log" and not minutes(data["minutes"], 1):
        raise TianxuanError("invalid minutes")
    kinds = ("concept", "model", "attachment") if name == "work.submit_asset" else ("concept", "model")
    if "kind" in data and (
        data["kind"] not in kinds or not all(bounded_text(data[k]) for k in ("module", "revision", "path"))
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
        if field_edit:
            issue = store._require_tenant_issue(actor, issue_id, write=True)
            definitions = project_fields(store, actor, issue["project"])["fields"]
            if not any(item["key"] == field["key"] for item in definitions):
                raise TianxuanError("unknown project text field")
            # Merge in the authority's transaction. Legacy scalar types and large integers
            # never pass through the native editor's JSON number conversion.
            fields = snapshot(store, actor, issue_id)["plan"]["custom_fields"]
            if field["key"] not in fields and len(fields) >= 100:
                raise TianxuanError("custom field limit reached")
            fields[field["key"]] = field["value"]
            data.clear()
            data["plan"] = {"custom_fields": fields}
        if name == "work.submit_asset":
            native = getattr(store, "work_native_store", None)
            if native is None:
                raise TianxuanError("native asset store unavailable")
            try:
                content = native.read(store._tenant_of(actor), data["module"], data["revision"], data["path"])
            except ValueError as exc:
                raise TianxuanError("native asset unavailable") from exc
            data.update(
                digest=hashlib.sha256(content).hexdigest(),
                decision="attached" if data["kind"] == "attachment" else "pending",
            )
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
