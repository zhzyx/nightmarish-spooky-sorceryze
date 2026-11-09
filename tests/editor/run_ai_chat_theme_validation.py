"""Probe a supplied editor's actual theme switching in a private headless project.

The report identifies the observed binary; it does not attest source/build provenance.
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from editor_test_isolation import copy_editor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    source = args.godot.resolve(strict=True)
    report_path = args.report.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).with_name("ai_chat_theme_validation.gd")
    report = {
        "state": "running",
        "mode": "headless",
        "platform": platform.system(),
        "architecture": platform.machine(),
        "binary_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "probe_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
        "source_provenance": None,
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.respond({"data": [{"id": "theme-fixture"}]})

        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            self.respond({
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "THEME_REPLY\nBody text and 中文.\n```python\nprint(42)\n```",
                        },
                        "finish_reason": "stop",
                    }
                ]
            })

        def respond(self, value):
            body = json.dumps(value).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix="ai-chat-theme-") as temporary:
            base = Path(temporary)
            binary = copy_editor(source, base / "engine")
            project = base / "project"
            project.mkdir()
            (project / "project.godot").write_text(
                'config_version=5\n[application]\nconfig/name="Private theme probe"\n', encoding="utf-8"
            )
            shutil.copyfile(script, project / "probe.gd")
            env = os.environ.copy()
            env["AI_THEME_REPORT"] = str(base / "probe.json")
            env["AI_THEME_ENDPOINT"] = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
            for name in ["APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME"]:
                env[name] = str(base / name.lower())
            version = subprocess.run(
                [str(binary), "--headless", "--version"], capture_output=True, text=True, timeout=10, check=True
            )
            report["binary_version"] = version.stdout.strip()
            result = subprocess.run(
                [str(binary), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                cwd=project,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            report["exit_code"] = result.returncode
            if (base / "probe.json").exists():
                report["probe"] = json.loads((base / "probe.json").read_text(encoding="utf-8"))
            report["state"] = (
                "passed"
                if result.returncode == 0
                and "SCRIPT ERROR" not in result.stderr
                and "probe" in report
                and not report["probe"]["failures"]
                else "failed"
            )
            if report["state"] == "failed":
                report["stdout"] = result.stdout
                report["stderr"] = result.stderr
    except Exception as error:
        report.update(state="failed", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        server.shutdown()
        server.server_close()
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["state"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
