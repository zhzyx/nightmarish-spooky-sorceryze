"""Verify four concurrent ACP callbacks through the Godot development tool loop."""

import argparse
import functools
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import run_daqian_node_approval as fixture


def check(command, env, project, _changed_actor, _stop_watching, *, modules):
    test_dir = Path(__file__).resolve().parent
    source = test_dir.parents[1] / "tools/codebuddy_cli"
    bridge_dir = project / "tools/codebuddy_cli"
    bridge_dir.mkdir(parents=True)
    for script in ("godot_bridge.js", "godot_acp.js", "godot_terminal.js"):
        shutil.copyfile(source / script, bridge_dir / script)
    node = shutil.which("node")
    if not node or not (modules / "@agentclientprotocol/sdk/dist/acp.js").is_file():
        raise RuntimeError("Install the pinned CodeBuddy dependencies or supply --modules")
    subprocess.run(
        [
            node,
            "-e",
            "require('node:fs').symlinkSync(process.argv[1], process.argv[2], 'junction')",
            str(modules.resolve()),
            str(bridge_dir / "node_modules"),
        ],
        check=True,
    )
    entry = project / "tests/editor/mock_codebuddy_cli.js"
    entry.parent.mkdir(parents=True)
    shutil.copyfile(test_dir / entry.name, entry)
    shutil.copyfile(test_dir / "ai_chat_read_batch.gd", project / "test.gd")
    contents = {
        "first.txt": "FIRST_NATIVE_RESULT",
        "literal.txt": "Error: literal file text",
        "last.txt": "LAST_NATIVE_RESULT",
    }
    names = ["first.txt", "literal.txt", "absent.txt", "last.txt"]
    for name, content in contents.items():
        (project / name).write_text(content, encoding="utf-8")
    wire = project / "native-results.json"
    env.update(
        BATCH_CASE="acp",
        BATCH_NODE=node,
        BATCH_PROJECT=str(project),
        BATCH_WIRE=str(wire),
        GODOT_ACP_LOG_DIRECTORY=str(project / "acp-trace"),
        CLIBridge=str(bridge_dir / "godot_bridge.js"),
        CLIEntry=str(entry),
    )
    run = subprocess.run(command, env=env, capture_output=True, timeout=90)
    log = (run.stdout + run.stderr).decode("utf-8", errors="replace")
    reports = [
        json.loads(line.removeprefix("BATCH_REPORT ")) for line in log.splitlines() if line.startswith("BATCH_REPORT ")
    ]
    assert run.returncode == 0 and reports, log[-5000:]
    report = reports[-1]
    assert report["acp_complete"] and report["idle"] and report["armed"], (report, log[-5000:])
    events = report["events"]
    assert len([phase for phase, state in events if phase.startswith("read-batch-") and state == "running"]) == 1
    assert len([phase for phase, state in events if phase.startswith("tool-") and state == "result_returned"]) == len(
        names
    )
    native = json.loads(wire.read_text(encoding="utf-8"))
    assert len(native) == len(names)
    calls = report["native_calls"]
    assert set(calls) == set(names) and len(set(calls.values())) == len(names), calls
    trace = [
        json.loads(line)
        for path in (project / "acp-trace").glob("*.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    returned = [event for event in trace if event["event"] == "host_file_result"]
    assert len(returned) == len(names), returned
    for name, callback, event in zip(names, native, returned):
        digest = hashlib.sha256(calls[name].encode()).hexdigest()[:16]
        assert event["call_hash"] == digest and event["success"] is (name in contents), (name, event)
        if name in contents:
            assert callback == {"ok": True, "content": contents[name]}, (name, callback)
        else:
            assert callback["ok"] is False and callback["error"], callback
    print("CODEBUDDY_READ_BATCH_OK", json.dumps({"batch": 1, "calls": calls, "successful": 3, "failed": 1}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument(
        "--modules", type=Path, default=Path(__file__).resolve().parents[2] / "tools/codebuddy_cli/node_modules"
    )
    args = parser.parse_args()
    fixture.check_command_restart = functools.partial(check, modules=args.modules)
    fixture.run(args.godot, restart=True)
