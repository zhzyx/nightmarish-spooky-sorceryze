"""Project an authorized task's immutable check receipts onto its editable object."""

import json

from fastapi import APIRouter, Request
from native_api import PREFIX, _call, _identity
from native_store import NativeStoreError


def current_inputs(store, db, tenant, inputs):
    """Compare the registered read set with a single snapshot of the saved heads."""
    for module, bound in inputs.items():
        head = db.execute("SELECT revision FROM native_heads WHERE tenant=? AND module=?", (tenant, module)).fetchone()
        if head is None or ("revision" in bound and bound["revision"] != head["revision"]):
            return False
        state = store._revision(db, tenant, module, head["revision"])
        if any(state["objects"].get(path) != digest for path, digest in bound["objects"].items()):
            return False
        if state["dependencies"] != bound["dependencies"]:
            return False
        for dependency, pin in bound["dependencies"].items():
            if (
                db.execute(
                    "SELECT 1 FROM native_heads WHERE tenant=? AND module=? AND revision=?", (tenant, dependency, pin)
                ).fetchone()
                is None
            ):
                return False
    return True


def validation_for_object(workflow, actor, key, module, path):
    # edit_baseline enforces historical task visibility and writable object scope.
    latest = workflow.edit_baseline(actor, key, module, path)["latest"]
    row = workflow.status(actor, key)
    task = json.loads(row["task"])
    terminal = json.loads(row["terminal"] or "{}")
    candidate = terminal.get("candidate")
    revision = terminal.get("modules", {}).get(module)
    receipts = []
    outcomes = {}
    runner = workflow.runner
    for tool in task["checks"]:
        outcomes[tool] = "pending"
        if not candidate or not revision:
            continue
        with runner.store._connection() as db:
            db.execute("BEGIN")
            saved = db.execute(
                "SELECT payload FROM native_check_runs WHERE tenant=? AND run_key=?",
                (row["tenant"], key + "-" + tool),
            ).fetchone()
            if saved is None:
                continue
            run = json.loads(saved["payload"])
            if run["candidate"] != candidate or run["check"] != tool:
                raise NativeStoreError("Check run does not match this task")
            if run["state"] not in {"cached", "complete"}:
                continue
            evidence = runner.cache._evidence(db, row["tenant"], run["evidence"])
            if evidence["binding"] != run["binding"]["binding"] or evidence["binding"]["check"] != tool:
                raise NativeStoreError("Check evidence does not match the executed inputs")
            objects = evidence["binding"]["inputs"].get(module, {}).get("objects", {})
            if path not in objects:
                # A completed check on another input is not a required object check.
                del outcomes[tool]
                continue
            inputs_match = current_inputs(runner.store, db, row["tenant"], evidence["binding"]["inputs"])
            revoked = (
                db.execute(
                    "SELECT 1 FROM native_check_revocations WHERE tenant=? AND evidence_id=?",
                    (row["tenant"], evidence["id"]),
                ).fetchone()
                is not None
            )
        receipt = {
            "revision": revision,
            "sha256": objects[path],
            "candidate": candidate,
            "tool": tool,
            "outcome": evidence["outcome"],
            "result_location": {"evidence": evidence["id"], "log_sha256": evidence["log_sha256"]},
            "revoked": revoked,
        }
        receipts.append(receipt)
        if inputs_match and latest["sha256"] == objects[path] and not revoked:
            if evidence["outcome"] == "passed":
                hit = runner.cache.lookup(row["tenant"], candidate, tool, **run["context"])
                if hit is None or hit["evidence"]["id"] != evidence["id"]:
                    continue
            outcomes[tool] = evidence["outcome"]
    states = set(outcomes.values())
    current = "pending"
    if "failed" in states:
        current = "failed"
    elif states == {"passed"}:
        current = "passed"
    return {
        "task": key,
        "module": module,
        "path": path,
        "current": {**latest, "state": current, "checks": outcomes},
        "receipts": receipts,
    }


def create_validation_router(workflow):
    router = APIRouter(prefix=PREFIX + "/workflow")

    @router.get("/tasks/{key}/validation/{module}/{path:path}")
    async def validation(key: str, module: str, path: str, request: Request):
        _, actor = _identity(request)
        return await _call(validation_for_object, workflow, actor, key, module, path)

    return router
