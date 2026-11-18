"""Trusted NativeWorker executable. Registry is host-private, never model-writable.

Host prepares grants after NativeWorkflow.authorize_task, before execute. Existing
NativeWorker owns this executable's complete process tree and candidate intake.
"""

# Installed sibling path bootstrap precedes runtime imports.
# ruff: noqa: E402
import argparse
import hashlib
import os
import sys
from pathlib import Path

# isort: off
ROOT = Path(__file__).resolve().parents[4]
RUNTIME = ROOT / "customizations/platforms/ai-access/host-http/runtime"
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(ROOT / "customizations/components/tianxuan/duobao"))
import runner
from native_workspace import _capture_stage_owner, _verify_stage_owner, absolute, portable, tree_names
# isort: on


def source_digest():
    from native_proposal_adapter import HELPER, HOST

    paths = [
        Path(__file__),
        HOST,
        HELPER,
        Path(__file__).with_name("native_worker.py"),
        ROOT / "customizations/components/tianxuan/duobao/native_workspace.py",
    ]
    return runner.digest({
        "runtime": runner.runtime_digest(),
        "sources": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
    })


def prepare_inputs(contract, execution, workspace, files, write_allowlist, acceptance):
    """Build signed task.input from an authorized worker contract and exact file map.

    files can be obtained with snapshot on a host-owned materialization of the
    same selected revisions. No model or provider call occurs here.
    """
    runner.require(runner.digest(contract) == execution, "Original execution contract mismatch")
    runner.require(isinstance(acceptance, str) and acceptance, "Acceptance required")
    runner.require(
        isinstance(files, dict) and all(isinstance(v, str) for v in files.values()), "UTF-8 file map required"
    )
    runner.require(
        isinstance(write_allowlist, list) and len(set(write_allowlist)) == len(write_allowlist),
        "Finite unique output paths required",
    )
    for name in write_allowlist:
        portable(name)
        module, separator, local = name.partition("/")
        allowed = contract["writes"].get(module, [])
        runner.require(
            separator and (allowed == "*" or local in allowed) and not module.startswith("requirement-"),
            "Write outside worker mandate",
        )
    request = dict(
        request_id=execution,
        task=runner.canonical(contract["source"]["definition"]),
        context=runner.canonical(files),
        write_allowlist=write_allowlist,
        acceptance=acceptance,
    )
    binding = dict(
        execution=execution,
        workspace=str(workspace),
        producer_source=source_digest(),
        definition=contract["source"]["definition"],
        files=files,
        write_allowlist=write_allowlist,
        acceptance=acceptance,
    )
    return {"native_request": request, "native_binding": binding}


def register(registry, execution, grant, framework):
    """Host-only registration; immutable per execution; no model calls."""
    registry = absolute(registry)
    state = Path(grant["payload"]["state_dir"])
    runner.verify_grant(grant, framework, state)
    runner.validate_plan(grant["payload"])
    binding = grant["payload"]["task"]["input"]["native_binding"]
    runner.require(
        binding["execution"] == execution and binding["producer_source"] == source_digest(),
        "Native registration binding mismatch",
    )
    data = {"grant": grant, "framework": str(framework)}
    target = registry / (execution + ".json")
    if target.exists():
        runner.require(runner.read(target) == data, "Execution registry cannot be rebound")
        return
    with target.open("x", encoding="utf-8") as f:
        f.write(runner.canonical(data))
        f.flush()
        os.fsync(f.fileno())


def snapshot(work):
    absolute(work)
    files = {}
    for p in sorted(work.rglob("*")):
        absolute(p)
        if p.is_file() and p.name != ".duobao-source.json":
            data = p.read_bytes()
            runner.require(len(data) <= 131072, "Model input file too large")
            files[p.relative_to(work).as_posix()] = data.decode("utf-8")
    runner.require(len(runner.canonical(files).encode("utf-8")) <= 100000, "Model input exceeds fixed context bound")
    return files


def launch(registry):
    work = absolute(os.environ["NATIVE_WORKSPACE"])
    execution = work.parent.name
    runner.require(
        len(execution) == 64 and all(c in "0123456789abcdef" for c in execution), "Invalid original execution"
    )
    record = runner.read(absolute(registry) / (execution + ".json"))
    grant, framework = record["grant"], Path(record["framework"])
    p = runner.verify_grant(grant, framework, Path(grant["payload"]["state_dir"]))
    runner.validate_plan(p)
    inputs = p["task"]["input"]
    binding = inputs["native_binding"]
    request = {
        k: inputs["native_request"][k] for k in ("request_id", "task", "context", "write_allowlist", "acceptance")
    }
    runner.require(
        binding["execution"] == execution and binding["workspace"] == str(work), "Original workspace mismatch"
    )
    runner.require(binding["producer_source"] == source_digest(), "Installed producer changed")
    runner.require(runner.read(os.environ["NATIVE_CONTEXT"]) == binding["definition"], "Original definition changed")
    files = snapshot(work)
    runner.require(files == binding["files"], "Selected materialized inputs changed")
    runner.require(
        request["task"] == runner.canonical(binding["definition"]) and request["context"] == runner.canonical(files),
        "Model inputs are not fixed original inputs",
    )
    runner.require(
        request["write_allowlist"] == binding["write_allowlist"] and request["acceptance"] == binding["acceptance"],
        "Native mandate changed",
    )
    for name in request["write_allowlist"]:
        portable(name)
        runner.require(
            len(name.split("/")) >= 2
            and not name.split("/")[0].startswith("requirement-")
            and ".duobao-source.json" not in name.split("/"),
            "Reserved or non-module output",
        )
    owner = _capture_stage_owner(work)
    result = runner.run(grant, framework, Path(p["state_dir"]))
    runner.require(result["status"] == "completed", "Model result unknown or incomplete; no proposal application")
    runner.verify_grant(grant, framework, Path(p["state_dir"]))
    runner.require(len(result["result"]["outputs"]) == 1, "One native production step required")
    proposal = next(iter(result["result"]["outputs"].values()))
    from contextlib import closing

    with closing(runner.connect(Path(p["state_dir"]))) as db:
        history = runner.events(db, runner.jid_for(p["task"]))
    evidence = next(
        e["data"]["protocol_evidence"]
        for e in reversed(history)
        if e["kind"] == "call_end" and e["data"]["status"] == "received"
    )
    runner.require(
        evidence["original_request_digest"] == runner.digest(request)
        and proposal["request_id"] == request["request_id"]
        and proposal["input_digest"] == evidence["input_digest"],
        "Original proposal binding mismatch",
    )
    edits = proposal["files"]
    tree_names([*files, *(e["path"] for e in edits)])
    runner.require(len({e["path"] for e in edits}) == len(edits), "Duplicate proposal paths")
    for edit in edits:
        runner.require(
            edit["path"] in request["write_allowlist"]
            and isinstance(edit["content"], str)
            and len(edit["content"].encode("utf-8")) <= 131072,
            "Output outside original mandate",
        )
    runner.require(snapshot(work) == files, "Workspace changed during model execution")
    # Any partial IO failure exits nonzero: NativeWorker closes without collecting
    # or accepting any output. Original files and journal remain for inspection.
    for edit in edits:
        _verify_stage_owner(work, owner)
        path = work / portable(edit["path"])
        absolute(path.parent)
        absolute(path, missing=True)
        path.write_bytes(edit["content"].encode("utf-8"))
    print(
        runner.canonical({
            "execution": execution,
            "proposal_applied": True,
            "runtime_state": p["state_dir"],
            "candidate_accepted": False,
        })
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True)
    args = parser.parse_args()
    launch(args.registry)
