"""Native per-session reasoning and Codex wire regression; controlled CLI only."""

import argparse
import contextlib
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from editor_test_isolation import copy_editor
from run_model_autofetch import fixture_program
from run_unified_settings_native import sanitized_environment

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

FIXTURE = r"""import json, os, sys
from pathlib import Path
args=sys.argv[1:]
if args[:2]==['login','status']:sys.exit(0)
if args and args[0]=='exec':
 body=sys.stdin.read();data=json.loads(body.rsplit('\n',1)[-1]);efforts=[x for x in args if x.startswith('model_reasoning_effort=')];model=args[args.index('--model')+1] if '--model' in args else ''
 effort=json.loads(efforts[0].split('=',1)[1]) if efforts else ''
 row={'model':model,'effort':effort,'effort_args':efforts,'packet_effort':data.get('reasoning_effort'),'tools':len(data.get('available_tools',[])),'consultation':data.get('tool_context',{}).get('consultation_only')}
 with Path(os.environ['WIRE_CAPTURE']).open('a') as f:f.write(json.dumps(row)+'\n')
 print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps({'content':'wire-'+model+'-'+(effort or 'default'),'actions':[]})}}),flush=True)
 print(json.dumps({'type':'turn.completed'}),flush=True);sys.exit(0)
for line in sys.stdin:
 packet=json.loads(line)
 if 'id' not in packet:continue
 result={}
 if packet.get('method')=='model/list':
  mode=Path(os.environ['WIRE_MODE']);efforts=['medium'] if mode.exists() else ['medium','high','xhigh','max','ultra']
  result={'data':[{'id':'fixture-full','model':'fixture-full','isDefault':True,'supportedReasoningEfforts':[{'reasoningEffort':e} for e in efforts]},{'id':'fixture-none','model':'fixture-none','supportedReasoningEfforts':[]}],'nextCursor':None}
 print(json.dumps({'id':packet['id'],'result':result}),flush=True)
"""


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    from ainative.owned_process import run_owned

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    godot = args.godot.resolve(strict=True)
    node = args.node.resolve(strict=True)
    report_path = args.report.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).with_name("reasoning_sessions.gd")
    result = {
        "ok": False,
        "scope": "Actual native editor with synthetic local Codex; no real provider inference",
        "editor_sha256": digest(godot),
        "fixture_sha256": {script.name: digest(script), Path(__file__).name: digest(Path(__file__))},
        "runs": [],
    }
    base = None
    original_cwd = Path.cwd()
    try:
        with tempfile.TemporaryDirectory(prefix="reasoning-sessions-") as temporary:
            base = Path(temporary).resolve()
            executable = copy_editor(godot, base / "editor")
            (base / "SConstruct").touch()
            if os.name == "nt":
                subprocess.run(
                    ["cmd.exe", "/c", "mklink", "/J", str(base / "tools"), str(ROOT / "tools")],
                    check=True,
                    capture_output=True,
                )
            else:
                (base / "tools").symlink_to(ROOT / "tools", target_is_directory=True)
            project = base / "project"
            project.mkdir()
            (project / "project.godot").write_text(
                '[application]\nconfig/name="Reasoning session fixture"\n'
                '[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
                encoding="utf-8",
            )
            fixture = fixture_program(base / "codex-fixture", FIXTURE)
            config = executable.parent / "editor_data/gonggong/config.json"
            config.parent.mkdir(parents=True)
            config.write_text(
                json.dumps({
                    "schema_version": 1,
                    "runtimes": {"codex": str(fixture), "node": str(node), "workflow_python": sys.executable},
                }),
                encoding="utf-8",
            )
            output = base / "result.json"
            capture = base / "capture.jsonl"
            env = dict(
                sanitized_environment(base),
                CODEX_HOME=str(base / "private-codex"),
                GONGGONG_NODE=str(node),
                WIRE_RESULT=str(output),
                WIRE_CAPTURE=str(capture),
                WIRE_MODE=str(base / "mode"),
            )
            with contextlib.chdir(base):
                history = project / ".godot/editor/ai_chat_history.json"
                saved_history = None
                for phase in ("full", "reopen", "legacy"):
                    if phase == "legacy":
                        # Simulate a version-1 history predating per-session preferences.
                        legacy = json.loads(saved_history)
                        for agent in legacy["agents"]:
                            agent.pop("reasoning_preferences", None)
                        history.write_text(json.dumps(legacy), encoding="utf-8")
                        history.with_suffix(".json.bak").unlink(missing_ok=True)
                    output.unlink(missing_ok=True)
                    env["WIRE_PHASE"] = phase
                    failures = []
                    log_path = report_path.with_name(report_path.stem + "-" + phase + ".log")
                    with log_path.open("wb") as log:
                        code = run_owned(
                            [
                                str(executable),
                                "--headless",
                                "--editor",
                                "--path",
                                str(project),
                                "--script",
                                str(script),
                            ],
                            stdout=log,
                            env=env,
                            limit=4 * 1024 * 1024,
                            timeout=180,
                            active=lambda: True,
                            fail=failures.append,
                        )
                    native = (
                        json.loads(output.read_text(encoding="utf-8"))
                        if output.exists()
                        else {"ok": False, "error": "missing result"}
                    )
                    run = {
                        "phase": phase,
                        "exit_code": code,
                        "process_failures": failures,
                        "native": native,
                        "log_sha256": digest(log_path),
                    }
                    result["runs"].append(run)
                    if code != 0 or failures or native.get("ok") is not True:
                        raise RuntimeError("Native phase failed: " + phase)
                    if phase == "full":
                        saved_history = history.read_text(encoding="utf-8")
                        agents = json.loads(saved_history)["agents"]
                        preferences = [a.get("reasoning_preferences", {}).get("2:fixture-full") for a in agents]
                        run["persisted_preferences"] = preferences
                        if preferences != ["medium", ""]:
                            raise RuntimeError("History did not persist distinct session preferences")
                rows = [json.loads(line) for line in capture.read_text(encoding="utf-8").splitlines()]
                result["actual_cli_invocations"] = rows
                expected = [("fixture-full", e) for e in ("medium", "high", "xhigh", "max", "ultra")]
                expected += [("fixture-none", ""), ("fixture-full", "")]
                result["exact_wire_verified"] = (
                    [(x["model"], x["effort"]) for x in rows] == expected
                    and all(
                        x["effort"] == x["packet_effort"] and x["tools"] == 0 and x["consultation"] is True
                        for x in rows
                    )
                    and all(not x["effort_args"] for x in rows[-2:])
                )
                result["ok"] = result["exact_wire_verified"]
    except Exception as error:
        result["ok"] = False
        result["error"] = type(error).__name__ + ": " + str(error)
    finally:
        os.chdir(original_cwd)
        result["private_directory_removed"] = base is not None and not base.exists()
        result["ok"] = result["ok"] and result["private_directory_removed"]
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
