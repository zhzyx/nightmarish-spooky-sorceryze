"""Check selective draft removal in both the native composer and the received user message."""

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
from run_unified_settings_native import sanitized_environment


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
            messages.append([m["content"] for m in payload["messages"] if m["role"] == "user"][-1])
            (project / "received").touch()
            self.reply({
                "choices": [{"message": {"role": "assistant", "content": "received"}, "finish_reason": "stop"}]
            })

    with tempfile.TemporaryDirectory(prefix="u15-reference-removal-") as directory:
        private = Path(directory)
        editor = copy_editor(args.godot.resolve(), private / "editor")
        project = private / "project"
        project.mkdir()
        (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="U15 project"\n')
        for folder in ("alpha", "beta"):
            target = project / folder
            target.mkdir()
            (target / "same.gd").write_text(
                f'extends Node\nconst MARKER = "{folder} u15-fixture-key u15-next-placeholder"\n',
                encoding="utf-8",
                newline="\n",
            )
        shutil.copyfile(Path(__file__).with_name("workbench_reference_removal.gd"), project / "probe.gd")
        env = sanitized_environment(private)
        with ThreadingHTTPServer(("127.0.0.1", 0), Model) as server:
            threading.Thread(target=server.serve_forever, daemon=True).start()
            env["U15_ENDPOINT"] = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
            try:
                result = subprocess.run(
                    [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                    capture_output=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=100,
                    env=env,
                )
                if result.returncode == 0:
                    # Reopen a paused queue in the shipping history format, using the first native turn's actual metadata.
                    history_path = project / ".godot/editor/ai_chat_history.json"
                    history = json.loads(history_path.read_bytes())
                    active = next(agent for agent in history["agents"] if agent["id"] == history["active_agent"])
                    record = next(
                        row for row in active["transcript"] if row.get("content", "").startswith("retain beta")
                    )
                    refs = record["editor_references"]
                    key = "fixture-restored-placeholder"
                    queued_content = "restore queued" + record["content"].removeprefix("retain beta").replace(
                        "[REDACTED]", key
                    )
                    active["queued_messages"] = [
                        {
                            "role": "user",
                            "content": queued_content,
                            "editor_references": refs,
                            "consultation_only": True,
                        }
                    ]
                    active["draft_editor_references"] = refs
                    active["draft_script_excerpts"] = {refs[0]["object_id"]: "restored selection " + key}
                    history_path.write_text(json.dumps(history, ensure_ascii=False), encoding="utf-8")
                    (project / "received").unlink()
                    shutil.copyfile(
                        Path(__file__).with_name("workbench_reference_queue_restore.gd"), project / "reopen.gd"
                    )
                    reopened = subprocess.run(
                        [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://reopen.gd"],
                        capture_output=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=60,
                        env=env,
                    )
                else:
                    reopened = None
            finally:
                server.shutdown()
        receipt = next(
            (
                json.loads(line.removeprefix("U15_RESULT "))
                for line in result.stdout.splitlines()
                if line.startswith("U15_RESULT ")
            ),
            None,
        )
        passed = False
        if receipt and reopened and len(messages) == 2:
            body = messages[0]
            if isinstance(body, list):
                body = "".join(part["text"] for part in body if part["type"] == "text")
            prefix, _, references = body.partition("编辑器引用：")
            snapshot, _, excerpt = references.partition("\n选段 · ")
            kept = receipt["selected"][1]
            passed = (
                result.returncode == 0
                and "SCRIPT ERROR:" not in result.stderr
                and reopened.returncode == 0
                and "QUEUE_RESTORED" in reopened.stdout
                and messages[1] == body.replace("retain beta", "restore queued", 1)
                and prefix.startswith("retain beta")
                and "关联工单：#1810 · gonggong-ai-workbench-plan1-u15\n" in prefix
                and json.loads(snapshot) == receipt["history"] == [kept]
                and excerpt == kept["object_id"] + ':\nconst MARKER = "beta [REDACTED] [REDACTED]"'
                and "alpha" not in body
                and "u15-fixture-key" not in body
                and "u15-next-placeholder" not in body
            )
        report = {
            "passed": passed,
            "exit": result.returncode,
            "messages": messages,
            "controls": receipt,
            "stderr": result.stderr,
            "restored_queue_exit": reopened.returncode if reopened else None,
            "restored_queue_stderr": reopened.stderr if reopened else None,
            "persisted_draft_and_backup_scrubbed": bool(receipt),
            "engine_sha256": hashlib.file_digest(
                editor.with_name(editor.name.replace(".console.exe", ".exe")).open("rb"), "sha256"
            ).hexdigest(),
        }
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
