"""Exercise the ordinary native workbench sidebar against a private loopback model."""

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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    # The private editor must never discover the operator's production workspace.
    os.environ.pop("GONGGONG_WORKSPACE", None)
    messages = []

    class Model(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, data):
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self.reply({"data": [{"id": "fixture"}]})

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            messages.extend(m["content"] for m in payload["messages"] if m["role"] == "user")
            self.reply({
                "choices": [{"message": {"role": "assistant", "content": "received"}, "finish_reason": "stop"}]
            })

    with tempfile.TemporaryDirectory(prefix="u09-resource-selection-") as directory:
        private = Path(directory)
        editor = copy_editor(args.godot.resolve(), private / "editor")
        project = private / "project"
        project.mkdir()
        (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="U09"\n')
        for name, offset in (("north", 0.25), ("south", 0.75)):
            (project / name).mkdir()
            (project / name / "SameGradient.tres").write_text(
                f'[gd_resource type="Gradient" format=3]\n\n[resource]\noffsets = PackedFloat32Array(0, {offset})\n'
            )
        script = Path(__file__).with_name("workbench_resource_selection.gd")
        shutil.copyfile(script, project / "probe.gd")
        env = {k: v for k, v in os.environ.items() if not k.startswith("GONGGONG_")}
        with ThreadingHTTPServer(("127.0.0.1", 0), Model) as server:
            threading.Thread(target=server.serve_forever, daemon=True).start()
            env["U09_ENDPOINT"] = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
            try:
                result = subprocess.run(
                    [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                    capture_output=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=100,
                    env=env,
                )
            finally:
                server.shutdown()
        receipt = next(
            (
                json.loads(line.removeprefix("U09_RECEIPT "))
                for line in result.stdout.splitlines()
                if line.startswith("U09_RECEIPT ")
            ),
            None,
        )
        frozen = []
        if len(messages) == 1 and "编辑器引用：" in messages[0]:
            frozen = json.loads(messages[0].partition("编辑器引用：")[2])
        passed = bool(
            result.returncode == 0 and receipt and "SCRIPT ERROR:" not in result.stderr and frozen == receipt["history"]
        )
        report = {
            "passed": passed,
            "engine_sha256": hashlib.sha256(
                editor.with_name(editor.name.replace(".console.exe", ".exe")).read_bytes()
            ).hexdigest(),
            "exit": result.returncode,
            "model_requests": len(messages),
            "received_references": frozen,
            "controls_and_history": receipt,
            "stderr": result.stderr,
        }
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
