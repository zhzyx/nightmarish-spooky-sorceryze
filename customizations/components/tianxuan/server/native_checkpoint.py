"""Read one durable task checkpoint from the coordinator's committed transaction."""

import json


def read_checkpoint(workflow, actor, key):
    # All records are already written by the owning operations in the domain DB.
    # Read one snapshot so an advancing worker cannot mix two stages of a task.
    with workflow._transaction() as db:
        row = workflow._row(db, key)
        workflow._read_allowed(actor, row)
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
