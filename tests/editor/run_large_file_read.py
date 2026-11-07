"""Exercise bounded read_file/read_script ranges through the real editor tool loop.

The model endpoint is an offline fixture; settings are self-contained beside a
cloned candidate executable, including on macOS. No production Issue is created.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = """@tool
extends SceneTree
func _initialize():
    run.call_deferred()
func run():
    await create_timer(0.5).timeout
    var dock = root.find_child("AI Chat", true, false)
    var backend = dock.find_child("AIBackend", true, false)
    backend.select(0)
    backend.item_selected.emit(0)
    dock.find_child("APIEndpoint", true, false).text = OS.get_environment("RANGE_ENDPOINT")
    dock.find_child("APIModel", true, false).text = "offline-range-fixture"
    dock.find_child("APIKey", true, false).text = "offline-fixture"
    dock.find_child("AllowTools", true, false).button_pressed = true
    dock.find_child("ConsultationOnly", true, false).button_pressed = true
    dock.find_child("ChatInput", true, false).text = "Read the fixture excerpts."
    dock.find_child("Send", true, false).pressed.emit()
    for i in range(1200):
        await create_timer(0.05).timeout
        if FileAccess.file_exists("res://test-error.txt"):
            push_error(FileAccess.get_file_as_string("res://test-error.txt"))
            quit(2)
            return
        for label in dock.find_children("*", "RichTextLabel", true, false):
            if "LARGE_FILE_RANGE_OK" in label.get_parsed_text() and dock.find_child("Stop", true, false).disabled:
                print("LARGE_FILE_RANGE_OK")
                quit(0)
                return
    quit(2)
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    cases, verified, errors = [], [], []
    with tempfile.TemporaryDirectory(prefix="large-file-read-") as folder:
        root = Path(folder)
        executable = root / "editor" / args.godot.name
        executable.parent.mkdir()
        clone = (
            subprocess.run(["cp", "-c", str(args.godot.resolve()), str(executable)], capture_output=True)
            if sys.platform == "darwin"
            else None
        )
        if clone is None or clone.returncode:
            shutil.copy2(args.godot, executable)
        (executable.parent / "_sc_").touch()
        project = root / "project"
        project.mkdir()
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Bounded range fixture"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
        )
        (project / "test.gd").write_text(SCRIPT)

        def fixture(name, data):
            path = project / name
            path.write_bytes(data)
            return str(path)

        source = (ROOT / "editor/docks/ai_chat_dock.cpp").read_bytes()
        assert len(source) > 256 * 1024
        source_path = fixture("editor.cpp", source)
        unicode_text = ("prefix\n" * 50000) + "汉字😀\r\nlast\n"
        unicode_path = fixture("unicode.cpp", unicode_text.encode())
        boundary = fixture("boundary.txt", ("a" * 16383 + "汉😀\nsecond").encode())
        giant = fixture("giant.txt", b"x" * (256 * 1024 + 1))
        escaped = fixture("escaped.txt", b"\x01" * 50000)
        sparse = project / "overscan.txt"
        with sparse.open("wb") as file:
            file.truncate(16 * 1024 * 1024 + 1)
        scan_exact = fixture("scan-exact.txt", b"x" * (16 * 1024 * 1024 - 2) + b"\nz")

        def success(label, path, offset, limit, content, returned, total, truncated, tool="read_file"):
            cases.append((
                label,
                tool,
                dict(path=path, offset=offset, limit=limit),
                dict(content=content, offset=offset, returned_lines=returned, total_lines=total, truncated=truncated),
            ))

        def failure(label, path, expected, **arguments):
            cases.append((label, "read_file", dict(path=path, **arguments), expected))

        lines = source.decode().split("\n")
        success("actual engine source", source_path, 3690, 180, "\n".join(lines[3689:3869]), 180, len(lines), True)
        success(
            "read_script large source",
            source_path,
            5400,
            3,
            "\n".join(lines[5399:5402]),
            3,
            len(lines),
            True,
            "read_script",
        )
        success("unicode and CRLF", unicode_path, 50001, 2, "汉字😀\r\nlast", 2, 50003, True)
        success("UTF-8 crosses scan chunk", boundary, 1, 1, "a" * 16383 + "汉😀", 1, 2, True)
        success("EOF empty line", unicode_path, 50003, 1, "", 1, 50003, True)
        success("offset beyond EOF", unicode_path, 2147483647, 500, "", 0, 50003, True)
        success("empty file", fixture("empty.txt", b""), 1, 1, "", 1, 1, False)
        success("BOM preserved", fixture("bom.txt", b"\xef\xbb\xbfhello\n"), 1, 1, "\ufeffhello", 1, 2, True)
        success("maximum scan budget", scan_exact, 2, 1, "z", 1, 2, True)
        failure("whole read stays bounded", source_path, "256 KiB")
        failure("single oversized line", giant, "256 KiB", offset=1, limit=1)
        failure("encoded output budget", escaped, "Encoded excerpt", offset=1, limit=1)
        failure("scan budget", str(sparse), "16 MiB", offset=1, limit=1)
        failure("invalid offset", unicode_path, "positive integer", offset=0, limit=1)
        failure("invalid limit", unicode_path, "1-500", offset=1, limit=501)
        for label, data in [
            ("NUL", b"ok\n\x00"),
            ("overlong", b"ok\n\xc0\xaf"),
            ("surrogate", b"ok\n\xed\xa0\x80"),
            ("above Unicode range", b"ok\n\xf4\x90\x80\x80"),
            ("truncated UTF-8", b"ok\n\xe4\xb8"),
            ("bad continuation", b"ok\n\xe4a\x80"),
        ]:
            failure(label, fixture("invalid-" + label.replace(" ", "-") + ".txt", data), "UTF-8", offset=1, limit=1)

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                try:
                    body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                    results = [m for m in body["messages"] if m["role"] == "tool"]
                    index = len(verified)
                    if results:
                        label, _, _, expected = cases[index]
                        actual = results[-1]["content"]
                        if isinstance(expected, str):
                            assert actual.startswith("Error: ") and expected in actual, (label, actual)
                        else:
                            actual = json.loads(actual)
                            assert {k: actual[k] for k in expected} == expected, label
                        verified.append(label)
                        index += 1
                    if index == len(cases):
                        message = dict(role="assistant", content="LARGE_FILE_RANGE_OK")
                        finish = "stop"
                    else:
                        _, tool, arguments, _ = cases[index]
                        message = dict(
                            role="assistant",
                            content="",
                            tool_calls=[
                                dict(
                                    id=f"range-{index}",
                                    type="function",
                                    function=dict(name=tool, arguments=json.dumps(arguments)),
                                )
                            ],
                        )
                        finish = "tool_calls"
                    data = json.dumps(dict(choices=[dict(message=message, finish_reason=finish)])).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except Exception as error:
                    errors.append(str(error))
                    (project / "test-error.txt").write_text(str(error))
                    self.send_error(500)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            result = subprocess.run(
                [str(executable), "--headless", "--editor", "--path", str(project), "--script", "res://test.gd"],
                env={**os.environ, "RANGE_ENDPOINT": f"http://127.0.0.1:{server.server_port}/v1/chat/completions"},
                capture_output=True,
                timeout=90,
            )
        finally:
            server.shutdown()
            server.server_close()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.with_suffix(".stdout.log").write_bytes(result.stdout)
        args.out.with_suffix(".stderr.log").write_bytes(result.stderr)
        assert not errors and result.returncode == 0 and len(verified) == len(cases), (
            errors,
            verified,
            result.stdout[-3000:],
            result.stderr[-2000:],
        )
        args.out.write_text(
            json.dumps(
                dict(
                    ok=True,
                    cases=verified,
                    provider="offline HTTP fixture; real editor tools",
                    settings="self-contained cloned executable",
                ),
                indent=2,
            )
            + "\n"
        )


if __name__ == "__main__":
    main()
