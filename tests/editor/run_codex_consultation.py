"""Native Codex consultation through the real bridge and an offline JSONL model fixture."""

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

from editor_test_isolation import macos_editor

ROOT = Path(__file__).resolve().parents[2]
MOCK = r"""
const fs = require('fs');
let wire = '';
process.stdin.on('data', data => wire += data);
process.stdin.on('end', () => {
  const input = JSON.parse(wire.slice(wire.indexOf('\n') + 1));
  const args = process.argv;
  if (args[args.indexOf('--sandbox') + 1] !== 'read-only' || !args.includes('approval_policy="never"')
      || !args.includes('features.shell_tool=false') || !args.includes('features.apply_patch_freeform=false')) process.exit(4);
  const names = input.available_tools.map(t => t.function.name).sort();
  const expected = ['read_file','read_script','read_logs','list_scripts','list_directory','get_editor_state'].sort();
  if (JSON.stringify(names) !== JSON.stringify(expected) || input.tool_context.consultation_only !== true
      || input.tool_context.writes_allowed !== false || input.tool_context.execution_allowed !== false) process.exit(5);
  const latest = input.messages.findLastIndex(m => m.role === 'user');
  const prompt = input.messages[latest].content;
  const results = input.messages.slice(latest).filter(m => m.role === 'tool');
  fs.appendFileSync(process.env.CONSULT_WIRE, JSON.stringify({prompt, results: results.length, names}) + '\n');
  if (prompt === 'CANCEL') { setInterval(() => {}, 1000); return; }
  let answer;
  if (prompt === 'ATTACK') answer = {content:'',actions:[{name:'write_file',arguments:JSON.stringify({path:process.env.CONSULT_TARGET,content:'BAD'})}]};
  else if (prompt === 'READ' && results.length < 2) answer = {content:'',actions:[{name:'read_file',arguments:JSON.stringify({path:process.env.CONSULT_TARGET})}]};
  else if (prompt === 'READ' && results.length === 2 && results.every(m => m.content.includes('CONSULT_SENTINEL'))) answer = {content:'CODEX_CONSULTATION_READ_OK',actions:[]};
  else process.exit(6);
  console.log(JSON.stringify({type:'item.completed',item:{type:'agent_message',text:JSON.stringify(answer)}}));
  console.log(JSON.stringify({type:'turn.completed'}));
});
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="codex-consult-") as tmp:
        root = Path(tmp)
        isolated_editor = macos_editor(args.godot, root / "isolated-editor")
        project = root / "project"
        project.mkdir()
        (project / "project.godot").write_text('[application]\nconfig/name="Consultation"\n')
        shutil.copyfile(ROOT / "tests/editor/codex_consultation.gd", project / "gate.gd")
        entry = root / "entry.js"
        entry.write_text(MOCK, encoding="utf-8")
        node = shutil.which("node")
        if not node:
            parser.error("Node is required for the offline Codex fixture")
        # Match the native executable entry contract without contacting a provider.
        codex_entry = entry
        if os.name != "nt":
            codex_entry = root / "offline-codex"
            codex_entry.write_text("#!/bin/sh\nexec " + shlex.quote(node) + " " + shlex.quote(str(entry)) + ' "$@"\n')
            codex_entry.chmod(0o755)
        target = project / "sentinel.txt"
        target.write_text("CONSULT_SENTINEL", encoding="utf-8")
        wire = root / "wire.jsonl"
        env = dict(
            os.environ,
            CONSULT_NODE=node,
            CONSULT_ENTRY=str(codex_entry),
            CONSULT_BRIDGE=str(ROOT / "tools/codebuddy_cli/godot_bridge.js"),
            CONSULT_TARGET=str(target),
            CONSULT_WIRE=str(wire),
            CONSULT_ABSENT=str(root / "absent"),
        )
        for key in ["APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME"]:
            env[key] = str(root / key)
            (root / key).mkdir()
        result = subprocess.run(
            [str(isolated_editor), "--headless", "--editor", "--path", str(project), "--script", "res://gate.gd"],
            env=env,
            capture_output=True,
            timeout=120,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.with_suffix(".stdout.log").write_bytes(result.stdout)
        args.out.with_suffix(".stderr.log").write_bytes(result.stderr)
        assert result.returncode == 0 and b"CODEX_CONSULTATION_NATIVE_OK" in result.stdout, result.stdout[-4000:]
        requests = [json.loads(line) for line in wire.read_text().splitlines()]
        assert [(r["prompt"], r["results"]) for r in requests] == [
            ("ATTACK", 0),
            ("CANCEL", 0),
            ("READ", 0),
            ("READ", 1),
            ("READ", 2),
        ], requests
        assert target.read_text() == "CONSULT_SENTINEL"
        assert not (root / "absent").exists()
        assert not list(root.rglob("ai_chat_resume.json"))
        args.out.write_text(
            json.dumps(
                {
                    "ok": True,
                    "issue_number": 46,
                    "request_id": "requirement-8275346195acf05e0605ca999b44d868",
                    "editor_sha256": hashlib.sha256(args.godot.read_bytes()).hexdigest(),
                    "requests": requests,
                    "provider": "offline fixture only",
                    "issue_binding": "empty; absent workspace unchanged",
                    "sentinel_unchanged": True,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
