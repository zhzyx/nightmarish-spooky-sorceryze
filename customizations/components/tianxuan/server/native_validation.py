"""Project authorized check receipts onto editable objects and recheck stale inputs."""

import json

from fastapi import APIRouter, Request
from native_api import PREFIX, _body, _call, _fields, _identity
from native_store import Conflict, NativeStoreError, _digest, _json, _revision_id
from tianxuan_core import require_native_source_read


def _head(db, tenant, module):
    row = db.execute("SELECT revision FROM native_heads WHERE tenant=? AND module=?", (tenant, module)).fetchone()
    return row["revision"] if row is not None else None


def current_inputs(store, db, tenant, inputs):
    """Compare the registered read set with a single snapshot of the saved heads."""
    for module, bound in inputs.items():
        head = _head(db, tenant, module)
        if head is None or ("revision" in bound and bound["revision"] != head):
            return False
        state = store._revision(db, tenant, module, head)
        if any(state["objects"].get(path) != digest for path, digest in bound["objects"].items()):
            return False
        if state["dependencies"] != bound["dependencies"]:
            return False
        if any(_head(db, tenant, dependency) != pin for dependency, pin in bound["dependencies"].items()):
            return False
    return True


def _projection(runner, db, row, module, path):
    tenant, key = row["tenant"], row["id"]
    task = json.loads(row["task"])
    terminal = json.loads(row["terminal"] or "{}")
    revision = _head(db, tenant, module)
    digest = runner.store._revision(db, tenant, module, revision)["objects"].get(path)
    receipts = []
    outcomes = dict.fromkeys(task["checks"], "pending")
    stale = {}
    for tool in task["checks"]:
        if not terminal.get("candidate") or module not in terminal["modules"]:
            continue
        runs = [(key + "-" + tool, terminal["candidate"], terminal["modules"])]
        for saved in db.execute(
            "SELECT run_key,candidate,modules FROM native_validation_rechecks "
            "WHERE tenant=? AND task=? AND tool=? ORDER BY rowid",
            (tenant, key, tool),
        ):
            runs.append((saved["run_key"], saved["candidate"], json.loads(saved["modules"])))
        for run_key, candidate, modules in runs:
            saved = db.execute(
                "SELECT payload FROM native_check_runs WHERE tenant=? AND run_key=?", (tenant, run_key)
            ).fetchone()
            if saved is None:
                continue
            run = json.loads(saved["payload"])
            if run["candidate"] != candidate or run["check"] != tool:
                raise NativeStoreError("Check run does not match this task")
            if run["state"] not in {"cached", "complete"}:
                continue
            evidence = runner.cache._evidence(db, tenant, run["evidence"])
            binding = evidence["binding"]
            if binding != run["binding"]["binding"] or binding["check"] != tool:
                raise NativeStoreError("Check evidence does not match the executed inputs")
            objects = binding["inputs"].get(module, {}).get("objects", {})
            if path not in objects:
                outcomes.pop(tool, None)
                continue
            revoked = (
                db.execute(
                    "SELECT 1 FROM native_check_revocations WHERE tenant=? AND evidence_id=?", (tenant, evidence["id"])
                ).fetchone()
                is not None
            )
            receipts.append({
                "revision": modules[module],
                "sha256": objects[path],
                "candidate": candidate,
                "tool": tool,
                "outcome": evidence["outcome"],
                "result_location": {"evidence": evidence["id"], "log_sha256": evidence["log_sha256"]},
                "revoked": revoked,
            })
            stale.pop(tool, None)
            if not current_inputs(runner.store, db, tenant, binding["inputs"]):
                # A private producer candidate can differ from the still-unedited
                # admission base. Only advertise rechecks on a new saved revision.
                if revision != task["selected"][module] and not revoked:
                    stale[tool] = (binding["policy"], evidence["id"])
                continue
            if digest != objects[path] or revoked:
                continue
            if evidence["outcome"] == "passed":
                hit = runner.cache.lookup(tenant, candidate, tool, **run["context"])
                if hit is None or hit["evidence"]["id"] != evidence["id"]:
                    continue
            outcomes[tool] = evidence["outcome"]
    stale = {tool: source for tool, source in stale.items() if outcomes.get(tool) == "pending"}
    states = set(outcomes.values())
    state = "failed" if "failed" in states else "passed" if states == {"passed"} else "pending"
    return {
        "task": key,
        "module": module,
        "path": path,
        "current": {"revision": revision, "sha256": digest, "state": state, "checks": outcomes},
        "receipts": receipts,
        "recheck": {"revision": revision, "checks": list(stale)} if stale else None,
    }, stale


def validation_for_object(workflow, actor, key, module, path):
    workflow.edit_baseline(actor, key, module, path)
    row = workflow.status(actor, key)
    with workflow.runner.store._connection() as db:
        db.execute("BEGIN")
        return _projection(workflow.runner, db, row, module, path)[0]


def _authorized_task(workflow, actor, row):
    workflow._read_allowed(actor, row)
    task = workflow._valid(actor, row)
    if row["state"] not in {"produced", "stage-reached", "stage-unmet", "accepted"}:
        raise Conflict("No verified candidate for this task")
    if workflow._allow(actor, row["issue"], "check") != task["source"]:
        raise Conflict("Check authority changed")
    for acceptance in task["dependencies"].values():
        workflow._accepted_release(task["tenant"], actor, json.loads(acceptance))
    for module in task["selected"]:
        require_native_source_read(workflow.domain, actor, module)
    return task


def recheck_object(workflow, actor, key, module, path, revision):
    _revision_id(revision)
    workflow.edit_baseline(actor, key, module, path)
    row = workflow.status(actor, key)
    task = _authorized_task(workflow, actor, row)
    runner, tenant = workflow.runner, row["tenant"]
    with runner.store._connection() as db:
        db.execute("BEGIN")
        view, stale = _projection(runner, db, row, module, path)
        if view["current"]["revision"] != revision:
            raise Conflict("Saved revision changed")
        if not stale:
            return view
        selected = dict(task["selected"])
        selected.update({name: _head(db, tenant, name) for name in task["writes"]})
        # The original authority covers only the admitted module closure.
        for name, pin in selected.items():
            dependencies = runner.store._revision(db, tenant, name, pin)["dependencies"]
            if any(selected.get(dep) != expected for dep, expected in dependencies.items()):
                raise Conflict("Saved dependency outside authorized composition")
    candidate = runner.store.compose(tenant, selected)["id"]
    for tool, (policy, source_evidence) in stale.items():
        # Each subprocess is bound to the signed check installation, frozen
        # policy and immutable candidate. A second POST shares its stable key.
        _authorized_task(workflow, actor, workflow.status(actor, key))
        context = runner.context(tool, candidate)
        binding = runner.cache.binding(tenant, candidate, tool, **context)
        if context != task["check_contexts"][tool] or binding["binding"]["policy"] != policy:
            raise Conflict("Authorized check installation or read set changed")
        with runner.store._connection() as db:
            db.execute("BEGIN")
            if _head(db, tenant, module) != revision or not current_inputs(
                runner.store, db, tenant, binding["binding"]["inputs"]
            ):
                raise Conflict("Saved inputs changed before check")
        checker = workflow.principals(actor, task["issue"], "checker") if workflow.principals else actor
        run_key = "recheck-" + _digest(_json([key, candidate, tool]).encode())
        fact = runner.execute(tenant, checker, run_key, candidate, tool)
        if fact["state"] not in {"cached", "complete"} or fact["binding"] != binding:
            raise Conflict("Exact check result unavailable")
        with runner.store._connection(write=True) as db, workflow._transaction() as domain_db:
            _authorized_task(workflow, actor, workflow._row(domain_db, key))
            runner._allow(tenant, checker, tool)
            if (
                runner.context(tool, candidate) != context
                or runner.cache.binding(tenant, candidate, tool, **context) != binding
            ):
                raise Conflict("Check installation changed during check")
            if _head(db, tenant, module) != revision or not current_inputs(
                runner.store, db, tenant, binding["binding"]["inputs"]
            ):
                raise Conflict("Saved inputs changed during check")
            revoked = db.execute(
                "SELECT 1 FROM native_check_revocations WHERE tenant=? AND evidence_id IN (?,?)",
                (tenant, source_evidence, fact["evidence"]),
            ).fetchone()
            if revoked:
                raise Conflict("Check evidence revoked")
            if fact.get("outcome") != "failed":
                hit = runner.cache.lookup(tenant, candidate, tool, **context)
                if hit is None or hit["evidence"]["id"] != fact["evidence"]:
                    raise Conflict("Check evidence unavailable")
            db.execute(
                "INSERT OR IGNORE INTO native_validation_rechecks VALUES (?,?,?,?,?,?)",
                (tenant, key, tool, run_key, candidate, _json(selected)),
            )
            # Keep domain authority locked through the native receipt commit.
            db.commit()
    result = validation_for_object(workflow, actor, key, module, path)
    if result["current"]["revision"] != revision:
        raise Conflict("Saved revision changed")
    return result


def create_validation_router(workflow):
    router = APIRouter(prefix=PREFIX + "/workflow")
    if workflow.runner is None:
        return router
    with workflow.runner.store._connection() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS native_validation_rechecks (tenant TEXT NOT NULL, task TEXT NOT NULL, "
            "tool TEXT NOT NULL, run_key TEXT NOT NULL, candidate TEXT NOT NULL, modules TEXT NOT NULL, "
            "PRIMARY KEY(tenant,task,tool,run_key))"
        )

    @router.get("/tasks/{key}/validation/{module}/{path:path}")
    async def validation(key: str, module: str, path: str, request: Request):
        _, actor = _identity(request)
        return await _call(validation_for_object, workflow, actor, key, module, path)

    @router.post("/tasks/{key}/validation/{module}/{path:path}")
    async def recheck(key: str, module: str, path: str, request: Request):
        _, actor = _identity(request)
        payload = _fields(await _body(request, 1024), {"revision"})
        return await _call(recheck_object, workflow, actor, key, module, path, payload["revision"])

    return router
