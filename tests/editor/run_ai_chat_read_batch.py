"""Exercise the Codex development read batch with a real editor and isolated model/Issue fixtures."""

import argparse
import functools
import json
import shutil
import subprocess
from pathlib import Path

import run_daqian_node_approval as fixture

MOCK = """
const fs = require('node:fs');
const out = value => process.stdout.write(JSON.stringify(value));
if (process.argv[2] === 'models') {
    out({models: [{id: 'fixture', name: 'fixture'}]});
} else {
    const messages = JSON.parse(fs.readFileSync(process.argv[4], 'utf8')).messages;
    fs.appendFileSync(process.env.BATCH_WIRE, JSON.stringify(messages) + '\\n');
    const corrected = messages.some(m => m.role === 'user' && m.content.includes('USE_CORRECTED_SCOPE'));
    const message = {role:'assistant', content:corrected ? 'CORRECTION_ACCEPTED' : ''};
    if (!corrected && !messages.some(m => m.role === 'tool')) {
        message.tool_calls = [0,1,2,3].map(i => ({id:'read'+i,type:'function',function:{
            name:'read_file',arguments:JSON.stringify({path:process.env.BATCH_PROJECT+'/data'+i+'.txt'})}}));
    }
    out({choices:[{message,finish_reason:message.tool_calls?'tool_calls':'stop'}]});
}
"""

FAIL_FLUSH = """
    events = [json.loads(p.read_bytes()) for p in (root / ".gonggong-outbox/chat").glob("*.json")]
    if os.getenv("BATCH_CASE") == "receipt" and any(
        e["payload"]["phase"].startswith("read-batch-") and e["payload"]["status"] == "result_returned" for e in events
    ):
        Path(sys.argv[sys.argv.index("--out")+1]).write_text(json.dumps({"ok":False,"error":"batch_receipt_test_failure"}))
        sys.exit()
"""


def check(command, env, project, _changed_actor, _stop_watching, *, case):
    repo = Path(env["DAQIAN_TEST_REPO"])
    bridge = repo / "tools/gonggong_bridge.py"
    text = bridge.read_text(encoding="utf-8")
    hook = "    store = runpy.run_path("
    assert hook in text
    text = text.replace(hook, FAIL_FLUSH + hook)
    # The base board deliberately rejects the first amendment. Here we test
    # continuation after an independently accepted change of scope.
    text = text.replace(
        "assert 'Retain the amended icon scope' in str(req)", "assert 'USE_CORRECTED_SCOPE' in str(req); marker.touch()"
    )
    bridge.write_text(text, encoding="utf-8")
    for args in [
        ["add", "tools/gonggong_bridge.py"],
        ["commit", "-m", "Inject isolated receipt refusal"],
        ["push", "origin", "main"],
    ]:
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    mock = project / "tools/codex_cli/godot_bridge.js"
    mock.parent.mkdir()
    mock.write_text(MOCK, encoding="utf-8")
    for index in range(4):
        (project / f"data{index}.txt").write_text(f"READ_BATCH_SENTINEL_{index}", encoding="utf-8")
    shutil.copyfile(Path(__file__).with_name("ai_chat_read_batch.gd"), project / "test.gd")
    wire = project / "wire.jsonl"
    env.update(
        BATCH_CASE=case, BATCH_NODE=shutil.which("node") or "", BATCH_PROJECT=project.as_posix(), BATCH_WIRE=str(wire)
    )
    result = subprocess.run(command, env=env, capture_output=True, timeout=75)
    text = (result.stdout + result.stderr).decode("utf-8", errors="replace")
    lines = [line.removeprefix("BATCH_REPORT ") for line in text.splitlines() if line.startswith("BATCH_REPORT ")]
    assert result.returncode == 0 and lines, text[-6000:]
    report = json.loads(lines[-1])
    assert report["armed"] and report["idle"], (report, text[-4500:])
    calls = [json.loads(line) for line in wire.read_text(encoding="utf-8").splitlines()]
    assert len(calls) == (2 if case == "steer" else 1), (case, len(calls), report, text[-2200:])
    results = [p for p, s in report["events"] if p.startswith("tool-") and s == "result_returned"]
    if case == "steer":
        output = [m for m in calls[1] if m["role"] == "tool"]
        assert report["changed"] and report["corrected"] and len(output) == 4, report
        assert [m["tool_call_id"] for m in output] == [f"read{i}" for i in range(4)]
        assert "READ_BATCH_SENTINEL_0" in output[0]["content"]
        assert all("Skipped unexecuted proposal" in m["content"] for m in output[1:]), output
    elif case == "stop":
        assert report["changed"] and len(results) == 1, report
    else:
        assert report["receipt_error"] and len(results) == 4, report
    print("READ_BATCH_BOUNDARY_OK", json.dumps({"case": case, "model_requests": len(calls), **report}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--case", choices=["stop", "steer", "receipt"], required=True)
    args = parser.parse_args()
    fixture.check_command_restart = functools.partial(check, case=args.case)
    fixture.run(args.godot, restart=True)
