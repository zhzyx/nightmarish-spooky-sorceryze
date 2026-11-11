"""Real private debugger, controlled local model transport, no external service."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from editor_test_isolation import copy_editor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expect-missing", action="store_true")
    parser.add_argument("--extended", action="store_true")
    parser.add_argument("--instances", type=int, choices=(1, 2), default=1)
    parser.add_argument("--secret", default="runtime-fixture-secret")
    args = parser.parse_args()
    observations, failures, seen = {}, [], []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def reply(self, value):
            raw = json.dumps(value).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            self.reply({"data": [{"id": "runtime-diagnostics-fixture"}]})

        def do_POST(self):
            try:
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                messages = request["messages"]
                start = max(i for i, row in enumerate(messages) if row["role"] == "user")
                label = messages[start]["content"]
                seen.append(label)
                results = [row["content"] for row in messages[start + 1 :] if row["role"] == "tool"]
                if results:
                    observations[label] = results[-1]
                    message = {"role": "assistant", "content": "Diagnostic snapshot received."}
                else:
                    message = {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "logs-" + label,
                                "type": "function",
                                "function": {
                                    "name": "read_logs",
                                    "arguments": "{}",
                                },
                            }
                        ],
                    }
                self.reply({"choices": [{"message": message}]})
            except Exception as exc:
                failures.append(str(exc))
                self.send_error(500)

    # Retain this owned private directory for failures and exact native receipts.
    work = Path(tempfile.mkdtemp(prefix="owned-runtime-diagnostics-"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        editor = copy_editor(args.godot, work / "editor")
        (editor.parent / "editor_data/editor_settings-4.8.tres").write_text(
            '[gd_resource type="EditorSettings" format=3]\n[resource]\nrun/window_placement/game_embed_mode = 0\n'
            'ai_chat/backend = 0\nai_chat/model = "runtime-diagnostics-fixture"\n'
            f'ai_chat/endpoint = "http://127.0.0.1:{server.server_port}/v1/chat/completions"\n',
            encoding="utf-8",
        )
        project = work / "project"
        project.mkdir()
        if args.instances == 2:
            metadata = project / ".godot/editor/project_metadata.cfg"
            metadata.parent.mkdir(parents=True)
            metadata.write_text(
                "[debug_options]\nmultiple_instances_enabled=true\nrun_instance_count=2\n", encoding="utf-8"
            )
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Runtime diagnostics"\nrun/main_scene="res://game.tscn"\n'
            '[editor]\nrun/main_run_args="--headless --audio-driver Dummy"\n'
            '[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
            encoding="utf-8",
        )
        (project / "game.tscn").write_text(
            '[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://game.gd" id="1"]\n'
            '[node name="Game" type="Node"]\nscript=ExtResource("1")\n',
            encoding="utf-8",
        )
        (project / "game.gd").write_text(
            "extends Node\nfunc _ready():\n\tpush_error("
            + json.dumps("RUNTIME_DIAGNOSTIC_ERROR " + args.secret)
            + ")\n"
            '\tpush_warning("RUNTIME_DIAGNOSTIC_WARNING")\n\tprint("RUNTIME_ORIGINAL_OUTPUT")\n',
            encoding="utf-8",
        )
        if args.extended:
            (project / "flood.tscn").write_text(
                (project / "game.tscn").read_text(encoding="utf-8").replace("game.gd", "flood.gd"), encoding="utf-8"
            )
            (project / "flood.gd").write_text(
                'extends Node\nfunc _ready():\n\tfor i in range(205):\n\t\tpush_error("BOUND_" + str(i) + "界".repeat(400))\n\tpush_error("runtime-fixture-secret".repeat(2000))\n',
                encoding="utf-8",
            )
            with (project / "project.godot").open("a", encoding="utf-8") as stream:
                stream.write("[network]\nlimits/debugger/max_errors_per_second=1024\n")
        shutil.copyfile(Path(__file__).with_name("runtime_diagnostics.gd"), project / "driver.gd")
        env = {
            **os.environ,
            "GODOT_AI_API_KEY": args.secret,
            "OPENAI_API_KEY": "",
            "AI_CHAT_TEST_URL": f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
            "APPDATA": str(work / "appdata"),
            "LOCALAPPDATA": str(work / "localappdata"),
            "RUNTIME_DIAGNOSTICS_EXTENDED": "1" if args.extended else "0",
            "RUNTIME_DIAGNOSTICS_INSTANCES": str(args.instances),
        }
        result = subprocess.run(
            [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://driver.gd"],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=100,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "RUNTIME_DEBUGGER_ERROR_OBSERVED=true" in result.stdout, result.stdout
        expected = {"empty", "bad", "stopped", "fixed"} | ({"cleared", "bounded"} if args.extended else set())
        assert set(observations) == expected, observations.keys()
        bad = json.loads(observations["bad"])
        assert bad["ok"] and bad["source"] == "editor_output"
        assert "RUNTIME_DIAGNOSTIC_ERROR " + args.secret not in observations["bad"]
        present = "RUNTIME_DIAGNOSTIC_ERROR" in observations["bad"]
        assert present != args.expect_missing, observations["bad"]
        assert "RUNTIME_ORIGINAL_OUTPUT" in bad["logs"]
        if not args.expect_missing:
            assert "RUNTIME_DIAGNOSTIC_WARNING" in observations["bad"]
            assert "res://game.gd" in observations["bad"]
            live = [s for s in bad["debugger"]["sessions"] if s["active"]]
            assert len(live) == args.instances and all(s["error_count"] >= 1 for s in live)
            assert len({s["pid"] for s in live}) == args.instances
            assert len({s["session_id"] for s in live}) == args.instances
            stopped = json.loads(observations["stopped"])["debugger"]["sessions"]
            assert not any(s["active"] for s in stopped)
            fixed = json.loads(observations["fixed"])["debugger"]["sessions"]
            current = [s for s in fixed if s["active"]]
            assert len(current) == args.instances and all(s["error_count"] == 0 for s in current)
            old = {s["session_id"]: s["generation"] for s in live}
            assert all(s["generation"] != old[s["session_id"]] for s in current)
            assert "RUNTIME_DIAGNOSTIC_ERROR" not in json.dumps(current)
            if args.extended:
                cleared = json.loads(observations["cleared"])["debugger"]["sessions"]
                assert all(not s["entries"] and s["error_count"] == 0 and s["warning_count"] == 0 for s in cleared)
                bounded = json.loads(observations["bounded"])["debugger"]
                assert (
                    bounded["truncated"] and sum(s["error_count"] for s in bounded["sessions"]) >= 205 * args.instances
                )
                assert sum(len(s["entries"]) for s in bounded["sessions"]) <= 200
                assert sum(s["characters_before_result_budget"] for s in bounded["sessions"]) <= 32000
                assert len(observations["bounded"]) <= 30000
                assert "context_excerpted" not in json.loads(observations["bounded"])
                assert "runtime-fixture-secret" not in observations["bounded"]
        assert "permission_off" in seen and "permission_off" not in observations
        chat = (project / "chat.txt").read_text(encoding="utf-8")
        assert "工具" in chat and ("关闭" in chat or "启用" in chat or "disabled" in chat), chat[-2000:]
        if not args.expect_missing:
            assert "JSON::parse_string" not in result.stderr, result.stderr
            snapshots = list((project / ".godot/editor/ai_chat_snapshots").glob("*.json"))
            assert len(snapshots) >= len(expected), snapshots
            stored_consultations = 0
            for snapshot in snapshots:
                envelope = json.loads(snapshot.read_text(encoding="utf-8"))
                assert hashlib.sha256(envelope["payload"].encode()).hexdigest() == envelope["sha256"], snapshot
                before = json.loads(envelope["payload"])["messages_before"]
                assert isinstance(before, list), snapshot
                for message in before:
                    if message.get("role") == "user":
                        assert message.get("consultation_only") is True, message
                        stored_consultations += 1
            assert stored_consultations >= len(expected) - 1, stored_consultations
        assert not failures, failures
        passed = True
    except Exception as exc:
        failures.append(str(exc))
        passed = False
    finally:
        server.shutdown()
    report = {
        "ok": passed,
        "expect_missing": args.expect_missing,
        "private_root": str(work),
        "binary_sha256": hashlib.sha256(args.godot.read_bytes()).hexdigest(),
        "observations": observations,
        "seen": seen,
        "failures": failures,
        "scope": "Real debugger and native read_logs; controlled HTTP model; driver edits fixture between runs, not an AI repair claim.",
    }
    if "result" in locals():
        report.update(exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": passed, "report": str(args.out), "private_root": str(work)}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
