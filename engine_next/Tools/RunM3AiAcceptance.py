"""Run real Executor workflows through next_asset without a Godot process."""

import argparse
import base64
import hashlib
import json
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path


def process_exists(pid):
    if os.name == "nt":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            return (
                bool(ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)))
                and exit_code.value == 259
            )
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def wait_for_process_exit(pid):
    for _ in range(500):
        if not process_exists(pid):
            return True
        time.sleep(0.01)
    return not process_exists(pid)


def request(factory, fixture):
    data = Path(fixture).read_bytes()
    source = {"id": "input", "revision": "input-r1"}
    graph = [
        {
            "id": "copy",
            "provider": "local-copy" if factory == "editor_demo:factory" else "synthetic",
            "request": {
                "node": "copy" if factory == "editor_demo:factory" else "echo",
                "version": "1",
                "inputs": {"source": source},
                "parameters": {"delay": 0, "fail": False} if factory == "editor_demo:factory" else {},
                "context": [],
            },
            "links": {},
        }
    ]
    artifact = {
        "id": "input",
        "revision": "input-r1",
        "type": "mesh",
        "payload": {
            "content_base64": base64.b64encode(data).decode("ascii"),
            "content_sha256": hashlib.sha256(data).hexdigest(),
            "extension": ".glb",
            "extension_future": {"opaque": [7, "preserve-me"]},
        },
    }
    entity = {
        "entity_id": 7,
        "name": "mesh",
        "node_type": "MeshInstance3D",
        "parent_entity_id": 0,
        "transform": {"translation": [0, 0, 0], "rotation_xyzw": [0, 0, 0, 1], "scale": [1, 1, 1]},
        "gameplay": {"kind": "static"},
        "assets": [{"role": "mesh", "asset_id": "mesh", "revision": "pending", "content_sha256": "0" * 64}],
    }
    return {
        "schema_version": 1,
        "request_id": "ai-" + factory.split(":")[0],
        "model": {
            "provider": "local-copy" if factory == "editor_demo:factory" else "synthetic-m3",
            "provider_version": "1",
            "model": "LOCAL IMPORT / COPY - NOT AI" if factory == "editor_demo:factory" else "no-generation-fixture",
            "model_version": "1",
        },
        "graph": graph,
        "manifest": {"schema_version": 1, "artifacts": [artifact]},
        "scene_template": {
            "schema_version": 1,
            "scene_id": "m3.ai",
            "scene_revision": "r1",
            "simulation": {"fixed_step_ms": 16, "max_speed": 8},
            "entities": [entity],
        },
        "asset_bindings": [{"asset_id": "mesh", "role": "mesh", "output": {"node": "copy", "port": "result"}}],
    }


def invoke(args, root, factory, *, resume=False, max_steps=None, timeout_ms=None, output_limit=None, python=None):
    request_path = root / "request.json"
    request_path.write_text(json.dumps(request(factory, args.fixture)), encoding="utf-8")
    (root / "out").mkdir(exist_ok=True)
    state = root / "state/controller.json"
    host = os.environ.get("M3_INNER_PYTHON", str(python or args.python))
    command = [
        str(args.next_asset),
        "ai-run",
        "--request",
        request_path,
        "--python",
        host,
        "--executor-script",
        str(args.executor),
        "--factory",
        factory,
        "--database",
        root / "executor.sqlite",
        "--state",
        state,
        "--output",
        root / "out/scene.enpak",
    ]
    if resume:
        command.append("--resume")
    if max_steps is not None:
        command += ["--max-steps", str(max_steps)]
    if timeout_ms is not None:
        command += ["--timeout-ms", str(timeout_ms)]
    if output_limit is not None:
        command += ["--output-limit", str(output_limit)]
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(root / "home"),
        "PYTHONPATH": str(args.repo / "engine_next/Tests/AI"),
        "ENGINE_NEXT_M3_TEST_STATE": str(root / "provider"),
    }
    return subprocess.run([str(value) for value in command], capture_output=True, text=True, env=env, timeout=60)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--next-asset", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--executor", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for name in ("next_asset", "repo", "fixture", "executor", "python", "report"):
        setattr(args, name, getattr(args, name).resolve())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.report.parent) as temporary:
        root = Path(temporary)
        offline_root = root / "offline"
        offline_root.mkdir()
        result = invoke(args, offline_root, "editor_demo:factory")
        assert result.returncode == 0, result.stdout + result.stderr
        offline = json.loads(result.stdout)
        assert offline["valid"] and offline["snapshot"]["state"] == "succeeded"
        assert offline["snapshot"]["artifacts"][0]["artifact"]["payload"]["extension_future"]["opaque"] == [
            7,
            "preserve-me",
        ]

        synthetic_root = root / "synthetic"
        synthetic_root.mkdir()
        (synthetic_root / "provider").mkdir()
        (synthetic_root / "provider/lost.once").write_text("1", encoding="utf-8")
        interrupted = invoke(args, synthetic_root, "SyntheticProvider:factory", max_steps=1)
        assert interrupted.returncode != 0 and "step_limit" in interrupted.stdout, interrupted.stdout
        resumed = invoke(args, synthetic_root, "SyntheticProvider:factory", resume=True)
        assert resumed.returncode == 0, resumed.stdout + resumed.stderr
        submit_count = json.loads((synthetic_root / "provider/submit-count.json").read_text())
        assert submit_count == 1
        synthetic = json.loads(resumed.stdout)
        assert synthetic["snapshot"]["artifacts"][0]["artifact"]["payload"]["extension_future"]["opaque"] == [
            7,
            "preserve-me",
        ]

        missing_root = root / "missing"
        missing_root.mkdir()
        missing = invoke(args, missing_root, "editor_demo:factory", python=missing_root / "missing-python")
        assert missing.returncode != 0 and "python_unavailable" in missing.stdout

        tree_root = root / "tree"
        tree_root.mkdir()
        (tree_root / "provider").mkdir()
        (tree_root / "provider/tree").write_text("1", encoding="utf-8")
        tree = invoke(args, tree_root, "SyntheticProvider:factory", timeout_ms=100)
        assert tree.returncode != 0 and "process_timeout" in tree.stdout, tree.stdout
        assert not (tree_root / "out/scene.enpak").exists()

        flood_root = root / "flood"
        flood_root.mkdir()
        (flood_root / "provider").mkdir()
        (flood_root / "provider/flood").write_text("1", encoding="utf-8")
        flood = invoke(args, flood_root, "SyntheticProvider:factory", timeout_ms=5000, output_limit=16384)
        assert flood.returncode != 0 and "process_output_limit" in flood.stdout, flood.stdout
        assert not (flood_root / "out/scene.enpak").exists()
        zero_limit = invoke(args, flood_root, "SyntheticProvider:factory", output_limit=0)
        overflow_limit = invoke(args, flood_root, "SyntheticProvider:factory", output_limit="9" * 100)
        excessive_limit = invoke(args, flood_root, "SyntheticProvider:factory", output_limit=384 * 1024 * 1024 + 1)
        assert zero_limit.returncode == 2 and overflow_limit.returncode == 2 and excessive_limit.returncode == 2

        detached_root = root / "detached"
        detached_root.mkdir()
        (detached_root / "provider").mkdir()
        (detached_root / "provider/detached").write_text("1", encoding="utf-8")
        detached = invoke(args, detached_root, "SyntheticProvider:factory")
        assert detached.returncode == 0, detached.stdout + detached.stderr
        detached_pid = json.loads((detached_root / "provider/detached-pid.json").read_text())
        detached_stopped = wait_for_process_exit(detached_pid)
        if not detached_stopped:
            try:
                os.kill(detached_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            wait_for_process_exit(detached_pid)
        assert detached_stopped, f"detached process {detached_pid} survived transport cleanup"
        assert (detached_root / "out/scene.enpak").is_dir()

        artifact_state_root = root / "artifact-state"
        artifact_state_root.mkdir()
        (artifact_state_root / "out/scene.enpak").mkdir(parents=True)
        blocked = invoke(args, artifact_state_root, "SyntheticProvider:factory")
        assert blocked.returncode != 0 and "package_publish" in blocked.stdout, blocked.stdout
        persisted = json.loads((artifact_state_root / "state/controller.json").read_text())
        assert len(persisted["published_artifacts"]) == 1 and not persisted["published"]
        (artifact_state_root / "out/scene.enpak").rmdir()
        artifact_resumed = invoke(args, artifact_state_root, "SyntheticProvider:factory", resume=True)
        assert artifact_resumed.returncode == 0, artifact_resumed.stdout + artifact_resumed.stderr
        assert json.loads(artifact_resumed.stdout)["snapshot"]["artifacts"] == []
        artifact_submits = json.loads((artifact_state_root / "provider/submit-count.json").read_text())
        assert artifact_submits == 1
        report = {
            "passed": True,
            "offline": "succeeded",
            "synthetic_resume": "succeeded",
            "provider_submits": submit_count,
            "python_missing_rejected": True,
            "artifact_extension_preserved": True,
            "artifact_identity_persisted_before_package": True,
            "artifact_resume_provider_submits": artifact_submits,
            "process_tree_timeout": True,
            "process_output_limit": True,
            "invalid_output_limits_rejected": True,
            "detached_process_reaped": True,
        }
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            "ENGINE_NEXT_M3_AI offline=1 synthetic_resume=1 provider_submits=1 artifact_state=1 output_limit=1 detached_reaped=1 status=ok"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
