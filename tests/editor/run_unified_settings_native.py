"""Exercise the real native settings controls in a private, addon-free editor.

No provider service, real credentials, user settings, or managed runtime is used.
The loopback responder supplies model lists and one delayed synthetic chat only.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from editor_test_isolation import copy_editor


def sanitized_environment(base):
    """Make both startup discovery and subprocess credentials fixture-owned."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if not re.search(r"KEY|TOKEN|SECRET|CREDENTIAL|PASSWORD", key, re.IGNORECASE)
        and not key.upper().startswith((
            "GONGGONG_",
            "GODOT_AI_",
            "AINATIVE_",
            "OPENAI_",
            "ANTHROPIC_",
            "CODEX_",
            "CODEBUDDY_",
            "GOOGLE_",
            "GEMINI_",
        ))
        and not key.upper().endswith(("_API_KEY", "_API_TOKEN", "_ACCESS_TOKEN"))
    }
    for key in (
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_CACHE_HOME",
        "TMP",
        "TEMP",
    ):
        directory = base / "private-home" / key.lower()
        directory.mkdir(parents=True, exist_ok=True)
        environment[key] = str(directory)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["GODOT_AI_API_KEY"] = ""
    environment["OPENAI_API_KEY"] = ""
    return environment


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--diagnostic-skip-lifetime",
        action="store_true",
        help="Diagnostic comparison only; never replaces the full lifecycle acceptance run",
    )
    args = parser.parse_args()
    binary = args.godot.resolve(strict=True)
    script = Path(__file__).with_name("unified_settings_native.gd")
    result = {
        "state": "failed",
        "editor_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "fixture_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
        "scope": "Actual native settings, lifetime, session credentials, save/reopen, old scope cleanup; loopback synthetic model response only",
        "runs": [],
        "diagnostic_only": args.diagnostic_skip_lifetime,
    }
    with tempfile.TemporaryDirectory(
        prefix="godot-unified-settings-", ignore_cleanup_errors=os.name == "nt"
    ) as temporary:
        base = Path(temporary).resolve()
        # Check cwd and project as well as the executable: neither may discover
        # a real workspace from an ancestor. The repo fixture is copied locally.
        for ancestor in (base, *base.parents):
            if (ancestor / "gonggong-workspace.json").exists():
                raise RuntimeError("System temporary directory inherits a real GongGong workspace")
        saved_workspace = os.environ.pop("GONGGONG_WORKSPACE", None)
        try:
            executable = copy_editor(binary, base / "engine")
        finally:
            if saved_workspace is not None:
                os.environ["GONGGONG_WORKSPACE"] = saved_workspace
        project = base / "project"
        project.mkdir()
        definition = 'config_version=5\n[application]\nconfig/name="Unified Native Settings Fixture"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
        (project / "project.godot").write_text(definition, encoding="utf-8", newline="\n")
        shutil.copy2(script, project / "accept.gd")
        old_workspace = base / "old-workspace"
        new_workspace = base / "new-workspace"
        old_workspace.mkdir()
        new_workspace.mkdir()
        model_capture = base / "model-helper-input.json"
        entry = old_workspace / "customizations/components/godot-host/daqian/models_cli.py"
        entry.parent.mkdir(parents=True)
        entry.write_text(
            "import json, sys\nfrom pathlib import Path\n"
            + "value=json.loads(sys.stdin.readline())\n"
            + f"Path({str(model_capture)!r}).write_text(json.dumps(value), encoding='utf-8')\n"
            + "print(json.dumps({'result':[]}))\n",
            encoding="utf-8",
            newline="\n",
        )
        events = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def respond(self, payload):
                body = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                events.append({"kind": "synthetic-model-list", "path": self.path})
                self.respond({"data": [{"id": "fixture-model"}]})

            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                events.append({"kind": "synthetic-chat", "model": request.get("model")})
                time.sleep(1.2)
                self.respond({
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": "UNIFIED_SYNTHETIC_CHAT_DONE"},
                            "finish_reason": "stop",
                        }
                    ]
                })

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
        endpoint = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
        node = shutil.which("node") or "fixture-node"
        fixtures = {}
        for name in ("build-python", "art-python", "chat-cli", "image-cli", "buddy-cli"):
            value = base / (name + (".exe" if os.name == "nt" else ""))
            value.touch()
            fixtures[name] = str(value).replace("\\", "/")
        settings_file = base / "engine/editor_data/editor_settings-4.8.tres"
        values = {
            "ai_chat/backend": 0,
            "ai_chat/model": "fixture-model",
            "ai_chat/endpoint": endpoint,
            "ai_chat/cli_node": node,
            "ai_chat/cli_entry": fixtures["buddy-cli"],
            "ai_chat/codex_entry": fixtures["chat-cli"],
            "ai_chat/build_python": fixtures["build-python"],
            "ai_chat/editor_control_bridge_enabled": False,
            "gonggong/workspace": str(old_workspace).replace("\\", "/"),
            "gonggong/python": sys.executable.replace("\\", "/"),
            "gonggong/tenant": "fixture-original-tenant",
        }
        settings_file.write_text(
            '[gd_resource type="EditorSettings" format=3]\n\n[resource]\n'
            + "\n".join(key + " = " + json.dumps(value, ensure_ascii=False) for key, value in values.items())
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        project_key = hashlib.sha256(str(project).replace("\\", "/").encode()).hexdigest()
        state = base / "engine/editor_data/ainative/projects" / project_key
        state.mkdir(parents=True)
        (state / "local.cfg").write_text(
            "[host]\npython="
            + json.dumps(fixtures["art-python"])
            + '\nfactory="editor_demo:factory"\nuse_bundled_script=true\n[service]\nmode="offline"\ncli_path='
            + json.dumps(fixtures["image-cli"])
            + "\n[managed_comfy]\nautostart=false\n",
            encoding="utf-8",
            newline="\n",
        )
        environment = sanitized_environment(base)
        environment.update({
            "UNIFIED_ENDPOINT": endpoint,
            "UNIFIED_BUILD_PYTHON": fixtures["build-python"],
            "UNIFIED_ART_PYTHON": fixtures["art-python"],
            "UNIFIED_CHAT_CLI": fixtures["chat-cli"],
            "UNIFIED_ART_CLI": fixtures["image-cli"],
            "UNIFIED_FRAMEWORK_PYTHON": sys.executable.replace("\\", "/"),
            "UNIFIED_NODE": node,
            "UNIFIED_BUDDY": fixtures["buddy-cli"],
            "UNIFIED_SECOND_WORKSPACE": str(new_workspace).replace("\\", "/"),
            "UNIFIED_MESH_RUNTIME": str(base / "synthetic-mesh-runtime").replace("\\", "/"),
            "UNIFIED_MODEL_CAPTURE": str(model_capture),
        })
        try:
            modes = ("full",) if args.diagnostic_skip_lifetime else ("full", "reopen")
            for mode in modes:
                receipt = base / (mode + ".json")
                env = dict(environment, UNIFIED_SETTINGS_MODE=mode, UNIFIED_SETTINGS_RECEIPT=str(receipt))
                env["UNIFIED_SETTINGS_DIAGNOSTIC_SKIP_LIFETIME"] = "1" if args.diagnostic_skip_lifetime else "0"
                command = [
                    str(executable),
                    "--headless",
                    "--editor",
                    "--path",
                    str(project),
                    "--script",
                    "res://accept.gd",
                ]
                try:
                    process = subprocess.run(
                        command,
                        cwd=project,
                        env=env,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=100,
                    )
                    log = process.stdout + process.stderr
                    value = json.loads(receipt.read_text(encoding="utf-8")) if receipt.is_file() else {}
                    behavior_passed = (
                        process.returncode == 0
                        and value.get("ok") is True
                        and "UNIFIED_SETTINGS_NATIVE_OK" in log
                        and "SCRIPT ERROR:" not in log
                    )
                    passed = behavior_passed and "ERROR:" not in log
                    entry = {
                        "name": mode,
                        "passed": passed,
                        "behavior_passed": behavior_passed,
                        "strict_errors": [line for line in log.splitlines() if "ERROR:" in line],
                        "returncode": process.returncode,
                        "receipt": value,
                    }
                    if not passed:
                        entry["log_tail"] = log[-18000:]
                    print(log)
                    result["runs"].append(entry)
                    if not behavior_passed:
                        break
                except subprocess.TimeoutExpired as error:
                    log = "".join(
                        piece.decode(errors="replace") if isinstance(piece, bytes) else piece
                        for piece in [error.stdout or "", error.stderr or ""]
                    )
                    result["runs"].append({"name": mode, "passed": False, "error": "timeout", "log_tail": log[-18000:]})
                    print(log)
                    break
            result["private_settings_contain_no_session_key"] = (
                "synthetic-session-only-key" not in settings_file.read_text(encoding="utf-8")
            )
            result["project_sources_unchanged"] = (project / "project.godot").read_text(
                encoding="utf-8"
            ) == definition and not (project / "addons").exists()
            result["synthetic_events"] = events
            result["behavior_passed"] = len(result["runs"]) == len(modes) and all(
                run.get("behavior_passed", False) for run in result["runs"]
            )
            result["state"] = (
                "passed"
                if len(result["runs"]) == 2
                and all(run["passed"] for run in result["runs"])
                and result["private_settings_contain_no_session_key"]
                and result["project_sources_unchanged"]
                and sum(event["kind"] == "synthetic-chat" for event in events) == 1
                else "failed"
            )
            if args.diagnostic_skip_lifetime:
                result["state"] = "diagnostic-complete" if result["behavior_passed"] else "diagnostic-failed"
        finally:
            server.shutdown()
            server.server_close()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"state": result["state"], "report": str(args.report)}, ensure_ascii=False))
    return 0 if result["state"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
