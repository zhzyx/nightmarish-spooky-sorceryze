"""Fixed installed producer broker; sign only the exact authorized native task."""

import argparse
import hashlib
import os
import time
from pathlib import Path

from native_entry_runtime import load_config, runner, runtime_state
from native_model_producer import launch, prepare_context_inputs, prepare_inputs, register, snapshot


def produce(config, template, registry):
    work = Path(os.environ["NATIVE_WORKSPACE"])
    execution = work.parent.name
    runner.require(len(execution) == 64 and all(c in "0123456789abcdef" for c in execution), "Exact execution required")
    registry = Path(registry)
    runner.require(registry.is_absolute(), "Absolute host registry required")
    contract = runner.read(registry / (execution + ".contract.json"))
    runner.require(runner.digest(contract) == execution, "Authorized task changed")
    runner.require(runner.read(os.environ["NATIVE_CONTEXT"]) == contract["source"]["definition"], "Source changed")
    resolver = None
    if "context_transport" in config:
        from native_entry_context_client import EntryContextClient

        resolver = EntryContextClient(config["context_transport"], execution)
    files = snapshot(work, large=True) if resolver else snapshot(work)
    outputs = [module + "/" + path for module, paths in contract["writes"].items() for path in paths]
    runner.require(
        all(isinstance(paths, list) for paths in contract["writes"].values()), "Finite producer outputs required"
    )
    acceptance = contract["source"]["definition"]["acceptance"]
    contextual = (
        resolver is not None and sum(p.stat().st_size for p in work.rglob("*") if p.is_file()) > resolver.full_bytes
    )
    small_files = None
    if not contextual:
        try:
            small_files = snapshot(work)
        except (ValueError, UnicodeError):
            if resolver is None:
                raise
            contextual = True
        if resolver is not None and small_files is not None:
            contextual = len(runner.canonical(small_files).encode()) > resolver.full_bytes
    if contextual:
        manifest = {
            "selection_digest": runner.digest(resolver.binding["selected"]),
            "module_count": len(resolver.binding["selected"]),
        }
        inputs = prepare_context_inputs(
            contract,
            execution,
            work,
            manifest,
            outputs,
            acceptance,
            runner.digest(resolver.binding),
            materialized_files=files,
        )
    else:
        inputs = prepare_inputs(contract, execution, work, small_files, outputs, acceptance)
    plan = runner.read(config["template"])
    runner.require(plan == template, "Installed template changed")
    bindings = config.get("catalog_bindings")
    if bindings is not None:
        profile_id = bindings.get(contract["profile"])
        selected = [profile for profile in plan["profiles"] if profile["id"] == profile_id]
        runner.require(len(selected) == 1, "Selected catalog model has no admitted producer profile")
        # A signed grant runs only the selected profile, including on a provider failure.
        plan["profiles"] = selected
    else:
        runner.require(len(plan["profiles"]) == 1, "Multiple producer profiles require explicit catalog bindings")
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

    def context_factory(binding, execution, workspace):
        runner.require(
            runner.digest(resolver.binding) == binding["installed_context"]
            and resolver.binding["installation_digest"] == contract["installation"]
            and resolver.binding["actor"] == contract["actor"]
            and resolver.binding["producer"] == contract["producer"],
            "Installed context identity changed",
        )
        return resolver

    launch(registry, context_factory=context_factory if contextual else None)
    if resolver:
        resolver.check("producer_completed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--registry", required=True)
    args = parser.parse_args()
    config, template = load_config(args.config, args.sha256)
    produce(config, template, args.registry)
