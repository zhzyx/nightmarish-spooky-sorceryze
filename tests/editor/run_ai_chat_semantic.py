"""Mock HTTP scene acceptance. No real model service is contacted."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys
from run_requirements_intake import GH_FIXTURE
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CASES = {
    "interface_2d": ("editor_action", {"action": "main_screen", "target": "2D"}),
    "highlight_tabs": ("editor_action", {"action": "highlight", "target": "main_screen_tabs"}),
    "open_scene": ("editor_action", {"action": "open_scene", "target": "res://fixture.tscn"}),
    "open_script": ("editor_action", {"action": "open_script", "target": "res://fixture.gd", "line": 3, "column": 1}),
    "select_node": ("editor_action", {"action": "select_node", "target": "Child"}),
    "project_settings": ("editor_action", {"action": "project_settings", "target": "Display/Window"}),
    "highlight_project": ("editor_action", {"action": "highlight", "target": "project_settings"}),
    "editor_settings": ("editor_action", {"action": "editor_settings", "target": "interface/editor"}),
    "highlight_editor": ("editor_action", {"action": "highlight", "target": "editor_settings"}),
    "highlight_inspector": ("editor_action", {"action": "highlight", "target": "inspector"}),
    "highlight_filesystem": ("editor_action", {"action": "highlight", "target": "filesystem"}),
    "state": ("get_editor_state", {}),
    "write": ("editor_action", {"action": "set_project_setting", "target": "display/window/size/viewport_width", "value": 777}),
    "reject": ("editor_action", {"action": "set_project_setting", "target": "display/window/size/viewport_width", "value": 888}),
    "invalid": ("editor_action", {"action": "open_scene", "target": "res://../outside.tscn"}),
    "save_failure": ("editor_action", {"action": "clear_project_setting", "target": "display/window/size/viewport_width"}),
    "switch_2d": ("editor_action", {"action": "main_screen", "target": "2D"}),
    "highlight_scene": ("editor_action", {"action": "highlight", "target": "scene_tree"}),
    "clear_highlight": ("editor_action", {"action": "clear_highlight"}),
    "clear": ("editor_action", {"action": "clear_project_setting", "target": "display/window/size/viewport_width"}),
    "consultation": ("editor_action", {"action": "main_screen", "target": "3D"}),
    "permission_off": ("editor_action", {"action": "main_screen", "target": "3D"}),
}

BOUND_CASES = {"state_empty", "state_long_ascii", "state_long_cjk", "state_long_unicode", "state_count", "state_budget", "state_case_a", "state_case_b", "state_case_c"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--interfaces", action="store_true")
    parser.add_argument("--bounds", action="store_true")
    parser.add_argument("--codex", action="store_true", help="Offline native Codex subprocess, requires --bounds")
    parser.add_argument("--manual-stop", action="store_true", help="Visible 100-second delayed highlight response; click Stop")
    parser.add_argument("--signal-stop", action="store_true", help="Headless Stop signal callback; not a native click")
    args = parser.parse_args()
    assert not (args.manual_stop and args.signal_stop)
    stop_case = args.manual_stop or args.signal_stop
    assert not args.codex or args.bounds
    assert not stop_case or not (args.bounds or args.codex or args.interfaces)
    results, errors, seen = {}, [], set()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            try:
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                messages = request["messages"]
                if "Requirements intake only" in messages[0]["content"]:
                    value = json.loads(messages[-1]["content"])
                    response = json.dumps({"choices": [{"message": {"role": "assistant", "content": json.dumps({"decision": "continue", "title": "Semantic fixture", "category": "development", "goal": value["request"], "scope": ["isolated semantic test"], "acceptance": ["expected test behavior"], "questions": []})}, "finish_reason": "stop"}]}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(response)))
                    self.end_headers()
                    self.wfile.write(response)
                    return
                latest = max(i for i, msg in enumerate(messages) if msg["role"] == "user")
                case = messages[latest]["content"]
                seen.add(case)
                tool_results = [m["content"] for m in messages[latest:] if m["role"] == "tool"]
                if tool_results:
                    results[case] = tool_results[-1]
                    if stop_case and case == "highlight_tabs":
                        (project / "server-waiting").write_text("waiting")
                        time.sleep(100)
                        (project / "server-released").write_text("released")
                    message = {"role": "assistant", "content": "Checked " + case}
                elif stop_case and case == "recovery":
                    message = {"role": "assistant", "content": "RECOVERY_OK"}
                else:
                    name, arguments = ("get_editor_state", {}) if case in BOUND_CASES else CASES[case]
                    message = {"role": "assistant", "content": "", "tool_calls": [{"id": case, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}]}
                payload = json.dumps({"choices": [{"message": message, "finish_reason": "tool_calls" if "tool_calls" in message else "stop"}]}).encode()
                outcome = "sent"
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    outcome = "disconnected"
                    raise
                finally:
                    if stop_case and case == "highlight_tabs" and tool_results:
                        (project / "server-response-finished").write_text(outcome)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                if not stop_case:
                    errors.append("Unexpected disconnected HTTP client")
            except Exception as exc:
                errors.append(str(exc))
                self.send_error(500)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with tempfile.TemporaryDirectory(prefix="godot-semantic-") as temp:
            workspace = Path(temp)
            source = Path(__file__).resolve().parents[2]
            for folder in ["framework", "customizations", ".github"]:
                shutil.copytree(source / folder, workspace / folder, ignore=shutil.ignore_patterns("__pycache__"))
            (workspace / "tools").mkdir()
            shutil.copyfile(source / "tools/gonggong_bridge.py", workspace / "tools/gonggong_bridge.py")
            if args.codex:
                for name in ["codex_cli/godot_bridge.js", "codebuddy_cli/godot_bridge.js", "codebuddy_cli/node_modules/@tencent-ai/codebuddy-code/bin/native/win32-x64/job-object.node"]:
                    target = workspace / "tools" / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source / "tools" / name, target)
                shutil.copyfile(Path(__file__).with_name("mock_codex_semantic.js"), workspace / "mock_codex_semantic.js")
                (workspace / "wire").mkdir()
            shutil.copyfile(source / "CURRENT_FRAMEWORK.json", workspace / "CURRENT_FRAMEWORK.json")
            # Isolated transport fixture: never import these receipts into production evidence.
            (workspace / "framework/tools/agent-context.mjs").write_text('process.stdout.write("ISOLATED_FRAMEWORK_CONTEXT_FIXTURE");', encoding="utf-8")
            (workspace / ".gonggong-local.json").write_text("{}")
            (workspace / "work-items.json").write_text(json.dumps({"repository": "test/repo", "tenant_id": "gonggong-workspace"}))
            (workspace / "fake-issues.json").write_text(json.dumps([{"number": 6, "state": "open", "html_url": "https://github.com/test/repo/issues/6", "body": "<!-- gonggong-request:isolated-gate -->", "labels": [{"name": n} for n in ["type:development", "status:in-progress", "workspace:gonggong"]], "updated_at": "2026-01-01T00:00:00Z"}]))
            for command in [["init", "--quiet"], ["remote", "add", "origin", "https://github.com/test/repo.git"], ["add", "framework"], ["-c", "user.name=Isolated Test", "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "Isolated fixture"]]:
                subprocess.run(["git", "-C", temp, *command], check=True, capture_output=True)
            subprocess.run([sys.executable, str(workspace / "framework/extensions/diting-files/diting_files.py"), "init", "--repo", temp], check=True)
            project = workspace / "project"
            project.mkdir()
            for base in [workspace, project]:
                for name in ["auth", "api", "issue"]:
                    (base / name).write_text(GH_FIXTURE, encoding="utf-8")
            (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Semantic test"\n[display]\nwindow/size/viewport_width=640\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n', encoding="utf-8")
            (project / "fixture.tscn").write_text('[gd_scene format=3]\n[node name="Root" type="Node"]\n[node name="Child" type="Node" parent="."]\n')
            (project / "fixture.gd").write_text('extends Node\n\nfunc demo():\n\tpass\n')
            shutil.copyfile(Path(__file__).with_name("ai_chat_semantic.gd"), project / "test.gd")
            env = {**os.environ, "APPDATA": str(project / "appdata"), "LOCALAPPDATA": str(project / "localappdata"), "GODOT_AI_API_KEY": "", "AI_CHAT_TEST_URL": f"http://127.0.0.1:{server.server_port}/v1/chat/completions"}
            env["SEMANTIC_INTERFACES"] = "1" if args.interfaces else ""
            env["SEMANTIC_BOUNDS"] = "1" if args.bounds else ""
            env["SEMANTIC_CODEX_ENTRY"] = str(workspace / "mock_codex_semantic.js") if args.codex else ""
            env["SEMANTIC_WIRE_DIR"] = str(workspace / "wire")
            env["SEMANTIC_MANUAL_STOP"] = "1" if stop_case else ""
            env["SEMANTIC_STOP_SIGNAL"] = "1" if args.signal_stop else ""
            env.update(GONGGONG_TEST_WORKSPACE=temp, GONGGONG_WORKSPACE=temp, GONGGONG_PYTHON=sys.executable, GONGGONG_GH=sys.executable, GONGGONG_NODE=shutil.which("node"))
            display = [] if args.manual_stop else ["--headless"]
            print("SEMANTIC_PROJECT", project, flush=True)
            run = subprocess.run([str(args.godot.resolve()), *display, "--editor", "--path", str(project), "--script", "res://test.gd"], env=env, cwd=project, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240 if args.manual_stop else 180)
            print(run.stdout)
            print(run.stderr)
            if args.codex:
                wire = {path.stem: json.loads(path.read_text(encoding="utf-8"))["content"] for path in (workspace / "wire").glob("*.json")}
                assert set(wire) == BOUND_CASES | {"open_scene"}, ("Incomplete native Codex wire", sorted(wire))
                assert not seen and not results, ("Unexpected HTTP business fallback", seen)
                results = wire
                print("NATIVE_CODEX_WIRE_CASES", sorted(wire), "HTTP_BUSINESS_CASES", sorted(seen))
            print("MOCK_RESULTS", json.dumps(results, ensure_ascii=False))
            print("MOCK_ERRORS", errors)
            assert run.returncode == 0 and "AI_CHAT_SEMANTIC_OK" in run.stdout, "scene driver failed"
            assert not errors, errors
            if stop_case:
                report = json.loads((project / "stop-report.json").read_text(encoding="utf-8"))
                print("SEMANTIC_STOP_REPORT", json.dumps(report))
                assert report["overlay_before"] and report["stop_was_enabled"]
                assert report["stop_seconds"] < 1 and report["frame_gap_seconds"] < 1
                assert not report["overlay_after"] and report["stop_disabled_after"]
                assert not report["server_released_at_stop"] and not report["server_released_at_recovery"]
                assert report["recovery_received"] and report["observed_server_release"] and report["stale_response_absent"]
                assert report["late_response_outcome"] in {"sent", "disconnected"}
                print("SEMANTIC_SIGNAL_STOP_OK" if args.signal_stop else "SEMANTIC_MANUAL_STOP_OK")
                return
            if args.bounds:
                assert set(results) == BOUND_CASES | {"open_scene"}, results.keys()
                states = {key: json.loads(results[key]) for key in BOUND_CASES}
                for key, value in states.items():
                    size = len(results[key].encode("utf-8"))
                    assert size <= 16 * 1024, (key, size)
                    assert value["ok"]
                    assert len(value["selected_nodes"]) <= 100
                    assert len(value["unsaved_scenes"]) <= 100
                    print("BOUND_STATE_BYTES", key, size)
                empty = states["state_empty"]
                assert empty["scene"] is None and empty["script"] is None and not empty["truncated"]
                for key in ["state_long_ascii", "state_long_cjk", "state_long_unicode"]:
                    assert states[key]["selected_nodes"] == [] and states[key]["truncated"]
                    assert "selected_nodes" in states[key]["truncated_fields"]
                    assert states[key]["scene"] == "res://fixture.tscn"
                assert len(states["state_count"]["selected_nodes"]) == 100
                assert states["state_count"]["truncated"]
                budget = states["state_budget"]
                assert 0 < len(budget["selected_nodes"]) < 100 and budget["truncated"]
                assert all(len(path) >= 1000 for path in budget["selected_nodes"]), "Paths must be retained whole"
                for case in ["state_case_a", "state_case_b", "state_case_c"]:
                    value = states[case]
                    assert value["script"] is None and value["running"] is False
                    assert value["selected_nodes"] == [], value
                    assert "selected_nodes" in value["redacted_fields"] and value["truncated"]
                print("SEMANTIC_MOCK_BOUNDS_OK")
                return
            interface_cases = {"highlight_tabs", "interface_2d", "open_scene", "open_script", "select_node", "project_settings", "highlight_project", "editor_settings", "highlight_editor", "highlight_inspector", "highlight_filesystem"}
            if args.interfaces:
                assert set(results) == interface_cases, results
                assert all(json.loads(value)["ok"] for value in results.values()), results
                print("SEMANTIC_MOCK_INTERFACES_OK")
                return
            assert set(results) == set(CASES) - interface_cases - {"permission_off"}, results
            assert "permission_off" in seen, seen
            state = json.loads(results["state"])
            assert state["ok"] and state["scene"] is None and state["script"] is None
            written = json.loads(results["write"])
            assert written["ok"] and written["saved"] and written["old_value"] == 640 and written["new_value"] == 777
            assert "reject" in results["reject"].lower() or "declin" in results["reject"].lower()
            assert json.loads(results["invalid"])["error"] == "invalid_project_path"
            assert not json.loads(results["save_failure"])["saved"]
            assert json.loads(results["highlight_scene"])["visible"]
            assert json.loads(results["clear"])["saved"]
            assert "Consultation" in results["consultation"]
            assert "PERMISSION_OFF_REJECTED" in run.stdout
            assert "viewport_width" not in (project / "project.godot").read_text(encoding="utf-8")
            print("SEMANTIC_MOCK_HTTP_ACCEPTANCE_OK")
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


if __name__ == "__main__":
    main()
