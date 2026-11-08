"""Isolated native debugger action pulses. Confirmations here are test signals, not humans."""

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from editor_test_isolation import copy_editor

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("client", ROOT / "tools/editor_control_client.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Editor client module loader is unavailable")
client_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client_module)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--godot", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    report = {"ok": False, "editor_sha256": hashlib.sha256(args.godot.read_bytes()).hexdigest(), "checks": []}
    with tempfile.TemporaryDirectory(prefix="runtime-command-fixture-") as tmp:
        base = Path(tmp)
        editor = copy_editor(args.godot, base / "editor")
        project = base / "project"
        project.mkdir()
        (editor.parent / "editor_data/editor_settings-4.8.tres").write_text(
            '[gd_resource type="EditorSettings" format=3]\n[resource]\nai_chat/editor_control_bridge_enabled = true\nrun/window_placement/game_embed_mode = 0\n'
        )
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Runtime command fixture"\nrun/main_scene="res://game.tscn"\n[editor]\nrun/main_run_args="--headless"\n[input]\nfixture_move={"deadzone":0.5,"events":[]}\n'
        )
        (project / "game.tscn").write_text(
            '[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://game.gd" id="1"]\n[node name="Game" type="Node"]\nscript=ExtResource("1")\n'
        )
        (project / "game.gd").write_text(
            'extends Node\nvar observed := false\nfunc _process(_delta):\n\tobserved = observed or Input.is_action_pressed("fixture_move")\n\tvar f = FileAccess.open("res://game-state.json.pending", FileAccess.WRITE)\n\tf.store_string(JSON.stringify({"observed":observed,"pressed":Input.is_action_pressed("fixture_move")}))\n\tf.close()\n\tDirAccess.rename_absolute("res://game-state.json.pending", "res://game-state.json")\n'
        )
        shutil.copyfile(ROOT / "tests/editor/runtime_command_gaps.gd", project / "test.gd")
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith("GONGGONG_") and k not in {"GODOT_AI_API_KEY", "OPENAI_API_KEY"}
        }
        for key in ["APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "TEMP", "TMP"]:
            (base / key).mkdir()
            env[key] = str(base / key)
        with (base / "log.txt").open("wb") as log:
            proc = subprocess.Popen(
                [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://test.gd"],
                stdout=log,
                stderr=subprocess.STDOUT,
                env=env,
            )
            serial = 0
            counter = 0

            def until(fn, seconds=40):
                deadline = time.monotonic() + seconds
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        raise AssertionError((base / "log.txt").read_text()[-6000:])
                    val = fn()
                    if val:
                        return val
                    time.sleep(0.03)
                raise AssertionError("Timeout: " + (base / "log.txt").read_text()[-6000:])

            def command(action, **kw):
                nonlocal serial
                serial += 1
                f = project / "command.pending"
                f.write_text(json.dumps({"serial": serial, "action": action, **kw}))
                f.replace(project / "command.json")
                ack = project / f"ack-{serial}.json"
                return until(lambda: json.loads(ack.read_text()) if ack.exists() else None)

            def route(action, **kw):
                nonlocal counter
                counter += 1
                ident = f"runtime-{counter}"
                return ident, client.route({
                    "intent": "engine_operation",
                    "source": "runtime-fixture",
                    "request_id": ident,
                    "operation": {"action": action, **kw},
                })

            def apply(action, **kw):
                ident, r = route(action, **kw)
                assert r.get("confirmation_required") and r.get("manual_confirmation_required"), r
                assert command("approve")["visible"]
                r = client.status(ident, "runtime-fixture")
                assert r.get("ok"), r
                return r

            try:
                until(lambda: (project / "ready.json").exists())
                client = client_module.EditorClient(project, proc.pid)
                until(lambda: route("game_input_state", index=31)[1].get("error") != "editor_busy")
                assert route("capture_editor")[1].get("error") == "capture_renderer_unavailable"
                assert route("game_input_state", index=31)[1].get("error") == "game_session_unavailable"
                report["checks"].append("headless capture explicit rejection; missing debugger session rejected")
                apply("run_project")
                until(lambda: (project / "game-state.json").exists())
                until(lambda: route("game_input_state")[1].get("ok"))
                assert route("game_input_query")[1].get("requested")

                def observation():
                    state = route("game_input_state")[1].get("state", {})
                    return state if state.get("receipt", {}).get("status") == "observed" else None

                state = until(observation)
                token = state["receipt"]["runtime_token"]
                value = {
                    "name": "fixture_move",
                    "duration": 0.2,
                    "strength": 0.75,
                    "request_id": "one-pulse",
                    "runtime_token": token,
                }
                r = apply("game_action_pulse", value=value)
                assert r["requested"] and not r["business_completed"]

                def released():
                    r = route("game_input_state")[1].get("state", {}).get("last_action_receipt", {})
                    return r if r.get("request_id") == "one-pulse" and r.get("status") == "released" else None

                receipt = until(released)
                assert receipt["ok"] and receipt["strength"] == 0, receipt
                game = json.loads((project / "game-state.json").read_text())
                assert game["observed"] and not game["pressed"], game
                report["checks"].append(
                    "real debugger peer query, observed InputMap action pulse, timed release and runtime receipt"
                )
                bad = {**value, "duration": 3}
                assert route("game_action_pulse", value=bad)[1].get("error") == "invalid_game_action"
                assert (
                    route("game_action_pulse", value={**value, "runtime_token": "wrong"})[1].get("error")
                    == "observed_game_runtime_required"
                )
                command("tools", value=False)
                assert route("game_input_query")[1].get("error") == "permission_denied"
                command("tools", value=True)
                report["checks"].append("duration/token/permission rejection")
                apply("stop_project")
                assert route("game_input_state")[1].get("error") == "game_session_unavailable"
                report["ok"] = True
            finally:
                if proc.poll() is None:
                    try:
                        command("exit")
                    except Exception:
                        proc.terminate()
                proc.wait(timeout=15)
                report["editor_log_tail"] = (base / "log.txt").read_text(errors="replace")[-2500:]
                args.report.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
