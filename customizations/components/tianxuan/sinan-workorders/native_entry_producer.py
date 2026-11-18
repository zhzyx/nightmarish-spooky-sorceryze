"""Fixed installed producer broker; sign only the exact authorized native task."""

import argparse
import hashlib
import os
import time
from pathlib import Path

from native_entry_runtime import load_config, runner, runtime_state
from native_model_producer import launch, prepare_inputs, register, snapshot


def produce(config, template, registry):
    work = Path(os.environ["NATIVE_WORKSPACE"])
    execution = work.parent.name
    runner.require(len(execution) == 64 and all(c in "0123456789abcdef" for c in execution), "Exact execution required")
    registry = Path(registry)
    runner.require(registry.is_absolute(), "Absolute host registry required")
    contract = runner.read(registry / (execution + ".contract.json"))
    runner.require(runner.digest(contract) == execution, "Authorized task changed")
    runner.require(runner.read(os.environ["NATIVE_CONTEXT"]) == contract["source"]["definition"], "Source changed")
    files = snapshot(work)
    outputs = [module + "/" + path for module, paths in contract["writes"].items() for path in paths]
    runner.require(
        all(isinstance(paths, list) for paths in contract["writes"].values()), "Finite producer outputs required"
    )
    acceptance = contract["source"]["definition"]["acceptance"]
    inputs = prepare_inputs(contract, execution, work, files, outputs, acceptance)
    plan = runner.read(config["template"])
    runner.require(plan == template, "Installed template changed")
    task = plan["task"]
    task.update(
        id=execution,
        tenant_id=contract["tenant"],
        input=inputs,
        authority_ref=contract["mandate"],
        work_items=[dict(id=contract["issue"], kind="task", relation="implements", certainty="confirmed")],
    )
    key_path = Path(config["key_file"])
    runner.require(key_path.is_file() and not key_path.is_symlink(), "Producer signer key unavailable")
    os.environ["GONGGONG_HOST_KEY"] = key_path.read_text(encoding="utf-8").strip()
    os.environ["PATH"] = str(Path(config["node"]).parent)
    os.environ["GONGGONG_PYTHON"] = config["python"]
    os.chdir(Path(config["node"]).parent)
    framework = Path(config["framework"])
    runner.validate_plan(plan)
    runner.context(framework, task)
    state = runtime_state(config, plan, task)
    payload = {
        **plan,
        "runtime_sha256": runner.runtime_digest(),
        "state_dir": str(state),
        "authority_ref": contract["mandate"],
        "expires_at": time.time() + 3600,
        "framework_sha256": hashlib.sha256((framework / "framework-manifest.json").read_bytes()).hexdigest(),
    }
    grant = {"payload": payload, "signature": runner.signature(payload)}
    register(registry, execution, grant, framework)
    launch(registry)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--registry", required=True)
    args = parser.parse_args()
    config, template = load_config(args.config, args.sha256)
    produce(config, template, args.registry)
