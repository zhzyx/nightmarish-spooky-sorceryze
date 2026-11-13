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
from run_model_autofetch import fixture_program
from run_unified_settings_native import sanitized_environment

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser()
p.add_argument("--godot", type=Path, required=True)
p.add_argument("--node", required=True)
p.add_argument("--codex", help="Optional executable; default uses an isolated synthetic app-server fixture")
p.add_argument("--out", type=Path, required=True)
a = p.parse_args()
a.node = str(Path(a.node).resolve(strict=True))
a.codex = str(Path(a.codex).resolve(strict=True))


requests: list[str] = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        requests.append(self.path)
        body = json.dumps({
            "data": [
                {"id": "fixture-reasoner", "reasoning_efforts": ["medium", "high"]},
                {"id": "unknown-model"},
                {"id": 123, "reasoning_efforts": ["high"]},
            ]
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
    configuration = root / "bin/editor_data/gonggong/config.json"
    configuration.parent.mkdir(parents=True)
    configuration.write_text(json.dumps({"schema_version": 1, "runtimes": {"codex": a.codex}}), encoding="utf-8")
    (root / "SConstruct").touch()
    if os.name == "nt":
        # Directory junctions do not require the Windows symbolic-link privilege.
        subprocess.run(
            ["cmd.exe", "/c", "mklink", "/J", str(root / "tools"), str(ROOT / "tools")], check=True, capture_output=True
        )
    else:
        (root / "tools").symlink_to(ROOT / "tools", target_is_directory=True)
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text(
        '[application]\nconfig/name="Model picker test"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
    )
    fixture = fixture_program(
        root / "codex-fixture",
        r"""import json, os, sys
from pathlib import Path
if sys.argv[1:3] == ["login", "status"]: sys.exit(0)
for line in sys.stdin:
    packet = json.loads(line)
    if "id" not in packet: continue
    result = {}
    if packet.get("method") == "model/list":
        with Path(os.environ["MODEL_TEST_EVENTS"]).open("a") as stream: stream.write("model/list\n")
        result = {"data": [{"id": "fixture-reasoner", "model": "fixture-reasoner", "isDefault": True, "supportedReasoningEfforts": [{"reasoningEffort": "high"}]}, {"id": "fixture-luna", "model": "fixture-luna", "supportedReasoningEfforts": [{"reasoningEffort": "medium"}]}], "nextCursor": None}
    print(json.dumps({"id": packet["id"], "result": result}), flush=True)
""",
    )
    events = root / "events.txt"
    result = root / "result.json"
    env = dict(
        sanitized_environment(root),
        GONGGONG_NODE=a.node,
        MODEL_TEST_CODEX=a.codex or str(fixture),
        MODEL_TEST_EVENTS=str(events),
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
        json.loads(result.read_text(encoding="utf-8"))
        if result.exists()
        else {"ok": False, "error": "no result", "returncode": run.returncode}
    )
    data["api_catalog_requests"] = requests
    data["codex_catalog_requests"] = len(events.read_text().splitlines()) if events.exists() else None
    data["real_provider"] = bool(a.codex)
    data["ok"] = (
        data.get("ok", False) and len(requests) >= 2 and (bool(a.codex) or bool(data["codex_catalog_requests"]))
    )
    a.out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False))
    raise SystemExit(0 if data["ok"] and run.returncode == 0 else 1)
