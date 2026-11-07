"""Headless model picker check in a portable, isolated editor. No inference."""

import argparse
import json
import os
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from editor_test_isolation import copy_editor

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser()
p.add_argument("--godot", type=Path, required=True)
p.add_argument("--node", required=True)
p.add_argument("--codex", required=True)
p.add_argument("--out", type=Path, required=True)
a = p.parse_args()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        body = json.dumps({
            "data": [{"id": "fixture-reasoner", "reasoning_efforts": ["medium", "high"]}, {"id": "unknown-model"}]
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
with tempfile.TemporaryDirectory(prefix="model-picker-") as folder:
    root = Path(folder)
    editor = copy_editor(a.godot, root / "bin")
    (root / "SConstruct").touch()
    (root / "tools").symlink_to(ROOT / "tools", target_is_directory=True)
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text(
        '[application]\nconfig/name="Model picker test"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
    )
    result = root / "result.json"
    env = dict(
        os.environ,
        GONGGONG_NODE=a.node,
        MODEL_TEST_CODEX=a.codex,
        MODEL_TEST_RESULT=str(result),
        MODEL_TEST_ENDPOINT=f"http://127.0.0.1:{server.server_port}/v1",
    )
    run = subprocess.run(
        [
            str(editor),
            "--headless",
            "--editor",
            "--path",
            str(project),
            "--script",
            str(ROOT / "tests/editor/model_picker.gd"),
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=70,
    )
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.with_suffix(".log").write_bytes(run.stdout)
    data = (
        json.loads(result.read_text())
        if result.exists()
        else {"ok": False, "error": "no result", "returncode": run.returncode}
    )
    a.out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(data, ensure_ascii=False))
    raise SystemExit(0 if data["ok"] and run.returncode == 0 else 1)
