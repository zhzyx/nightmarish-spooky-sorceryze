"""Verify generic workbench page references against a real headless editor and loopback receiver."""

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
from urllib.parse import quote

from editor_test_isolation import copy_editor
from run_unified_settings_native import sanitized_environment


class Model(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, value):
        data = json.dumps(value).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.reply({"data": [{"id": "fixture"}]})

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append(payload)
        self.reply({"choices": [{"message": {"role": "assistant", "content": "received"}, "finish_reason": "stop"}]})


def verify(editor, report):
    source = Path(__file__).parent.resolve()
    with (
        tempfile.TemporaryDirectory(prefix="workbench-u12-") as temp,
        ThreadingHTTPServer(("127.0.0.1", 0), Model) as server,
    ):
        root = Path(temp)
        binary = copy_editor(editor, root / "editor")
        server.requests = []
        threading.Thread(target=server.serve_forever, daemon=True).start()
        project = root / "project"
        plugin = project / "addons/notes"
        plugin.mkdir(parents=True)
        (plugin / "plugin.cfg").write_text(
            '[plugin]\nname="R4 Notes"\nauthor="fixture"\nversion="1"\ndescription="Page test"\nscript="plugin.gd"\n'
        )
        (plugin / "plugin.gd").write_text("""@tool
extends EditorPlugin

var page: EditorDock

func _enter_tree():
	page = EditorDock.new()
	page.title = "R4 Notes"
	page.default_slot = EditorDock.DOCK_SLOT_MAIN_SCREEN
	page.available_layouts = EditorDock.DOCK_LAYOUT_MAIN_SCREEN
	var note := TextEdit.new()
	note.name = "PrivateNote"
	page.add_child(note)
	add_dock(page)

func _exit_tree():
	remove_dock(page)
	page.queue_free()
""")
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Page fixture"\n[editor_plugins]\nenabled=PackedStringArray("res://addons/notes/plugin.cfg")\n'
        )
        shutil.copy(source / "workbench_page_reference.gd", project / "test.gd")
        shutil.copy(source / "ai_chat_tab_order.gd", project / "order.gd")
        env = sanitized_environment(root)
        env["PAGE_TEST_ENDPOINT"] = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
        (binary.parent / "editor_data/editor_settings-4.8.tres").write_text(
            '[gd_resource type="EditorSettings" format=3]\n\n[resource]\n'
            + 'ai_chat/endpoint = "'
            + env["PAGE_TEST_ENDPOINT"]
            + '"\n'
            + 'ai_chat/model = "fixture"\nai_chat/backend = 0\n'
        )
        result = subprocess.run(
            [str(binary), "--headless", "--editor", "--path", str(project), "--script", "res://test.gd"],
            env=env,
            cwd=root,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        server.shutdown()
        assert result.returncode == 0 and "SCRIPT ERROR" not in result.stderr, result.stdout + result.stderr
        previews = json.loads(
            next(
                line.removeprefix("PAGE_RESULT=")
                for line in result.stdout.splitlines()
                if line.startswith("PAGE_RESULT=")
            )
        )
        user_turns = [
            [msg["content"] for msg in request["messages"] if msg["role"] == "user"][-1] for request in server.requests
        ]
        assert len(user_turns) == 3 and len(previews) == 2, user_turns
        assert previews[0]["composer"] == previews[1]["composer"]
        assert "UNSENT_EXTENSION_DRAFT_1809" not in json.dumps(server.requests)
        frozen = []
        for row, content in zip(previews, user_turns):
            question, snapshot = content.split("\n[编辑器页面引用]\ncontext_snapshot=")
            expected_id = "editor-page://" + quote(row["module"], safe="") + "#" + quote(row["name"], safe="")
            expected_ref = {
                "kind": "editor",
                "object_id": expected_id,
                "revision": hashlib.sha256(expected_id.encode()).hexdigest(),
            }
            value = json.loads(snapshot)
            assert value == {
                "page_name": row["name"],
                "module_id": row["module"],
                "readable_scope": ["page_name", "module_id"],
                "references": [expected_ref],
            }, value
            assert question == "inspect " + row["name"]
            frozen.append(value)
        assert user_turns[2] == "only the typed question", user_turns[2]
        history = json.loads((project / ".godot/editor/ai_chat_history.json").read_text(encoding="utf-8"))
        records = [record for agent in history["agents"] for record in agent["transcript"] if record["role"] == "user"]
        assert [record["content"] for record in records] == user_turns
        saved_references = [record.get("editor_references", []) for record in records]
        assert saved_references == [frozen[0]["references"], frozen[1]["references"], []], saved_references
        data = {
            "history_matches_receiver": True,
            "editor_exit": result.returncode,
            "previews": previews,
            "received_page_snapshots": frozen,
            "request_count": len(server.requests),
            "last_user_content_after_removal": user_turns[2],
            "source_draft_preserved": True,
            "source_draft_absent_in_full_requests": True,
            "rename_rejected_before_removal": True,
        }
        report.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("Page reference acceptance passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    os.environ.pop("GONGGONG_WORKSPACE", None)
    verify(args.godot.resolve(), args.report.resolve())
