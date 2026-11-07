"""Independent real-dock layout matrix; requires explicit candidate build provenance."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from editor_test_isolation import copy_editor

ROOT = Path(__file__).resolve().parents[2]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument(
        "--build-evidence",
        type=Path,
        required=True,
        help="JSON: commit, binary_sha256, source_sha256 mapping, build_command, build_result=passed",
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--source-root", type=Path, help="Fixed uncommitted candidate root; hashes checked before and after"
    )
    parser.add_argument(
        "--diagnostic-binary-only",
        action="store_true",
        help="Reuse previously verified binary/build receipt for diagnostics; current source is NOT validated",
    )
    parser.add_argument("--widths", type=int, nargs="+", choices=[640, 960, 1440], default=[640, 960, 1440])
    parser.add_argument("--scales", type=float, nargs="+", choices=[1.0, 1.5], default=[1.0, 1.5])
    parser.add_argument("--visible", action="store_true", help="Use native window; headless covers geometry only")
    args = parser.parse_args()
    evidence = json.loads(args.build_evidence.read_text(encoding="utf-8-sig"))
    commit = evidence["commit"]
    subprocess.run(["git", "cat-file", "-e", commit + "^{commit}"], cwd=ROOT, check=True)
    assert evidence["binary_sha256"] == sha256(args.godot), "Binary differs from build evidence"
    paired = args.godot.with_name(args.godot.name.replace(".console.exe", ".exe"))
    assert evidence["engine_sha256"] == sha256(paired), "Engine behind console wrapper differs from build evidence"
    assert evidence["build_result"] == "passed" and evidence["build_command"], "Successful build evidence required"
    assert {"editor/docks/ai_chat_dock.cpp", "editor/docks/ai_chat_dock.h"} <= evidence["source_sha256"].keys()
    for name in evidence["source_sha256"]:
        assert not Path(name).is_absolute() and ".." not in Path(name).parts, (
            "Source path must stay within candidate root"
        )
        if args.diagnostic_binary_only:
            continue
        source = (
            (args.source_root / name).read_bytes()
            if args.source_root
            else subprocess.check_output(["git", "show", f"{commit}:{name}"], cwd=ROOT)
        )
        assert evidence["source_sha256"][name] == hashlib.sha256(source).hexdigest(), name
    # This validates supplied provenance, not a proof that a compiler used it.
    # Coordinator must supply the build receipt from the actual fixed candidate.
    args.out.mkdir(parents=True, exist_ok=True)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            body = json.dumps({"data": [{"id": "layout-model"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if any(m.get("content") == "layout-stop" for m in request["messages"] if m["role"] == "user"):
                time.sleep(2)
            body = json.dumps({
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "LAYOUT_REPLY\n"
                            + ("长消息换行 response " * 100)
                            + "\n"
                            + "long_unbroken_" * 100,
                        },
                        "finish_reason": "stop",
                    }
                ]
            }).encode()
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass  # Expected when the real Stop button cancels a request.

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    results = []
    try:
        for scale, setting, width in [(s, 2 if s == 1.0 else 4, w) for s in args.scales for w in args.widths]:
            with tempfile.TemporaryDirectory(prefix="ai-layout-") as folder:
                temporary = Path(folder)
                isolated_editor = copy_editor(args.godot, temporary / "isolated-editor")
                project = temporary / "project"
                project.mkdir()
                (project / "project.godot").write_text(
                    'config_version=5\n[application]\nconfig/name="Layout regression"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
                    encoding="utf-8",
                )
                shutil.copyfile(Path(__file__).with_name("ai_chat_layout_regression.gd"), project / "layout.gd")
                test_digest = sha256(project / "layout.gd")
                config = isolated_editor.parent / "editor_data"
                config.mkdir(parents=True, exist_ok=True)
                (config / "editor_settings-4.8.tres").write_text(
                    '[gd_resource type="EditorSettings" format=3]\n\n[resource]\n'
                    f"interface/editor/appearance/display_scale = {setting}\n"
                    'interface/editor/editor_language = "en"\n'
                    f'ai_chat/endpoint = "http://127.0.0.1:{server.server_port}/v1/chat/completions"\n'
                    'ai_chat/model = "layout-model"\n'
                    'gonggong/workspace = ""\ngonggong/python = ""\n'
                    "ai_chat/backend = 0\nai_chat/auto_execute_commands = false\n"
                    "ai_chat/auto_apply_file_changes = false\nai_chat/engine_auto_restart = false\n",
                    encoding="utf-8",
                )
                result = (args.out / f"layout-{scale:.1f}-{width}.json").resolve()
                env = {
                    key: value
                    for key, value in os.environ.items()
                    if not re.search(r"KEY|TOKEN|SECRET|CREDENTIAL|PASSWORD", key, re.IGNORECASE)
                    and not key.upper().startswith(("GONGGONG_", "AINATIVE_", "CODEX_"))
                }
                env.update(
                    APPDATA=str(temporary / "appdata"),
                    LOCALAPPDATA=str(temporary / "localappdata"),
                    XDG_CONFIG_HOME=str(temporary / "appdata"),
                    GODOT_AI_API_KEY="",
                    AI_LAYOUT_SCALE=str(scale),
                    AI_LAYOUT_RESULT=str(result),
                    AI_LAYOUT_WIDTH=str(width),
                    AI_LAYOUT_SCREENSHOTS="1" if args.visible else "0",
                    AI_LAYOUT_ENDPOINT=f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
                )
                for name in ("HOME", "USERPROFILE", "XDG_DATA_HOME", "TMP", "TEMP"):
                    private_path = temporary / "private-home" / name.lower()
                    private_path.mkdir(parents=True, exist_ok=True)
                    env[name] = str(private_path)
                command = [
                    str(isolated_editor),
                    *([] if args.visible else ["--headless"]),
                    "--editor",
                    "--path",
                    str(project),
                    "--script",
                    "res://layout.gd",
                ]
                with (args.out / f"layout-{scale:.1f}-{width}.log").open("w", encoding="utf-8") as log:
                    try:
                        run = subprocess.run(
                            command, cwd=project, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=90
                        )
                        exit_code = run.returncode
                    except subprocess.TimeoutExpired:
                        exit_code = 124
                results.append({
                    "scale": scale,
                    "width": width,
                    "exit_code": exit_code,
                    "test_source_sha256": test_digest,
                    "report_present": result.is_file(),
                })
    finally:
        server.shutdown()
        server.server_close()
    summary = {
        "candidate": evidence,
        "mode": "native" if args.visible else "headless_geometry",
        "diagnostic_binary_only": args.diagnostic_binary_only,
        "test_source_sha256": sha256(Path(__file__).with_name("ai_chat_layout_regression.gd")),
        "runs": results,
        "passed": all(r["exit_code"] == 0 and r["report_present"] for r in results),
    }
    if args.source_root and not args.diagnostic_binary_only:
        assert all(sha256(args.source_root / name) == digest for name, digest in evidence["source_sha256"].items()), (
            "Candidate source changed during tests"
        )
    assert sha256(args.godot) == evidence["binary_sha256"], "Candidate binary changed during tests"
    assert sha256(paired) == evidence["engine_sha256"], "Candidate engine changed during tests"
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
