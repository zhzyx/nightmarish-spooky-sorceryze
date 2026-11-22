"""Read one durable task checkpoint from the coordinator's committed transaction."""

import asyncio
import json
from contextlib import nullcontext

from native_store import NativeStoreError
from tianxuan_core import NotFound, PermissionDenied, TianxuanError


def read_checkpoint(workflow, actor, key):
    # All records are already written by the owning operations in the domain DB.
    # Read one snapshot so an advancing worker cannot mix two stages of a task.
    with workflow._transaction() as db:
        row = workflow._row(db, key)
        workflow._read_allowed(actor, row)
        return _checkpoint(db, row)


def _checkpoint(db, row):
    key = row["id"]
    stage = db.execute("SELECT receipt FROM native_stage_results WHERE task=?", (key,)).fetchone()
    review = db.execute("SELECT receipt FROM native_workflow_reviews WHERE task=?", (key,)).fetchone()
    origin = db.execute("SELECT project,module_id FROM native_edit_origins WHERE task=?", (key,)).fetchone()
    task = json.loads(row["task"])
    source = task["source"]
    definition = source["definition"]
    grant = definition.get("stage_authorization")
    terminal = json.loads(row["terminal"]) if row["terminal"] else {}
    completed = ["authorized"]
    if row["assignment"]:
        completed.append("reserved")
    if terminal:
        completed.append("worker-terminal")
    if stage:
        completed.append("stage-checked")
    if review and review["receipt"]:
        completed.append("reviewed")
    if row["acceptance"]:
        completed.append("accepted")

    state = row["state"]
    pending = None
    if state in {"running", "held", "closed-unresolved"}:
        pending = "worker-terminal"
    elif state in {"stage-reached", "stage-unmet"}:
        pending = "stage-confirmation"
    elif state == "produced":
        if grant:
            pending = "stage-check"
        elif review and not review["receipt"]:
            pending = "review-outcome"
        elif not review:
            pending = "candidate-review"

    return {
        "task": key,
        "issue": row["issue"],
        "project": origin["project"] if origin else None,
        "business_module": origin["module_id"] if origin else None,
        "target": {"title": definition["title"], "acceptance": definition["acceptance"], "writes": task["writes"]},
        "authorization": {
            "actor": task["actor"],
            "mandate": task["mandate"],
            "source_revision": source["revision"],
            "stage": grant,
        },
        "state": state,
        "completed_steps": completed,
        "input_revisions": task["selected"],
        "artifact_revisions": terminal.get("modules", {}),
        "candidate": terminal.get("candidate"),
        "calls": {"worker": row["worker_ref"], "model_calls": terminal.get("model_calls")},
        "stage_receipt": json.loads(stage["receipt"]) if stage else None,
        "pending_decision": {"kind": pending, "task": key} if pending else None,
    }


def _recovery_class(workflow, actor, row, checkpoint):
    state = row["state"]
    if state == "accepted":
        return "completed", "accepted"
    if state == "stage-reached":
        return "awaiting-confirmation", "authorized-stage-reached"
    if state not in {"ready", "reserved", "produced"}:
        return "needs-attention", state
    pending = checkpoint["pending_decision"]
    if pending and pending["kind"] == "review-outcome":
        return "needs-attention", "review-outcome"
    try:
        task = workflow._valid(actor, row)
    except (PermissionDenied, NativeStoreError, NotFound):
        return "needs-attention", "authorization-unavailable"
    if state == "produced" and checkpoint["authorization"]["stage"] and "stage_criteria" not in task:
        return "needs-attention", "stage-check-unbound"
    return "resumable", state


_OWNED_TASKS = (
    "SELECT t.id FROM native_tasks t JOIN native_active_tasks a ON a.task=t.id AND a.issue=t.issue "
    "JOIN native_edit_origins o ON o.task=t.id JOIN issues i ON i.id=t.issue "
    "WHERE t.tenant=? AND o.project=? AND i.project=o.project AND json_extract(t.task,'$.actor')=? "
)


def recovery_list(workflow, actor, project, after=""):
    # The original project and authorizing principal are pinned at admission.
    # Only the active contract for each issue can be considered for recovery.
    with workflow._transaction() as db:
        workflow.domain._validate_project(project)
        tenant = workflow.domain.actor_context(actor)["tenant"]
        rows = db.execute(
            _OWNED_TASKS + "AND t.id>? ORDER BY t.id",
            (tenant, project, actor, after),
        )
        items = []
        for (key,) in rows:
            row = workflow._row(db, key)
            try:
                workflow._read_allowed(actor, row)
            except (PermissionDenied, NotFound):
                continue
            if len(items) == 100:
                return {"items": items, "next_cursor": items[-1]["checkpoint"]["task"]}
            checkpoint = _checkpoint(db, row)
            category, reason = _recovery_class(workflow, actor, row, checkpoint)
            items.append({"category": category, "reason": reason, "checkpoint": checkpoint})
        return {"items": items, "next_cursor": None}


def _current(workflow, actor, project, key):
    with workflow._transaction(write=False) as db:
        tenant = workflow.domain.actor_context(actor)["tenant"]
        if not db.execute(_OWNED_TASKS + "AND t.id=?", (tenant, project, actor, key)).fetchone():
            raise NotFound("Original project task unavailable")
        row = workflow._row(db, key)
        workflow._read_allowed(actor, row)
        checkpoint = _checkpoint(db, row)
        category, _ = _recovery_class(workflow, actor, row, checkpoint)
        return category, checkpoint, json.loads(row["task"])["profile"]


async def _continue_task(workflow, actor, project, key, session):
    # Re-read between effects. A concurrent reopen, pause or changed confirmation
    # may have moved the boundary since the project list was read.
    for boundary in ("ready", "reserved", "produced"):
        session()
        category, checkpoint, profile = await asyncio.to_thread(_current, workflow, actor, project, key)
        if category != "resumable":
            return "parked"
        if checkpoint["state"] != boundary:
            continue
        context = getattr(workflow, "recovery_context", None)
        with context(actor, checkpoint) if context else nullcontext():
            if boundary == "ready":
                assignment = dict(
                    ticket=key,
                    sourceSnapshot={"source": key, "revision": checkpoint["authorization"]["source_revision"]},
                    model={"id": profile},
                    target="agent",
                )
                if not await asyncio.to_thread(workflow.reserve, actor, assignment):
                    return "deferred"
            elif boundary == "reserved":
                row = await asyncio.to_thread(workflow.execute_receipt, actor, key)
                if row["state"] in {"running", "held", "reserved"}:
                    await workflow.await_terminal(actor, key)
            else:
                settle = workflow.verify_stage if checkpoint["authorization"]["stage"] else workflow.finish
                await asyncio.to_thread(settle, actor, key)
                return "continued"
    return "parked"


async def recover_project(workflow, actor, project, session):
    """One authenticated reopen event. Consider only the caller's original active contracts."""
    keys = []
    cursor = ""
    while True:
        session()
        page = await asyncio.to_thread(recovery_list, workflow, actor, project, cursor)
        keys.extend(item["checkpoint"]["task"] for item in page["items"] if item["category"] == "resumable")
        cursor = page["next_cursor"]
        if not cursor:
            break
    counts = {"continued": 0, "parked": 0, "errors": 0, "deferred": 0}
    while keys:
        deferred = []
        for key in keys:
            try:
                result = await _continue_task(workflow, actor, project, key, session)
            except (NativeStoreError, TianxuanError, OSError):
                # An ambiguous receipt stays with its original ticket. An independent
                # ticket can still advance in the same reopen event.
                counts["errors"] += 1
                continue
            if result == "deferred":
                deferred.append(key)
            else:
                counts[result] += 1
        if len(deferred) == len(keys):
            counts["deferred"] = len(deferred)
            break
        keys = deferred
    return counts
