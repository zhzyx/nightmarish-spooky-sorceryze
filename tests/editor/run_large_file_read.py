"""Exercise bounded read_file/read_script ranges through the real editor tool loop.

The model endpoint is an offline fixture; settings are self-contained beside a
cloned candidate executable, including on macOS. No production Issue is created.
"""

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
    dock.get_ai_settings_control().find_child("APIEndpoint", true, false).text = OS.get_environment("RANGE_ENDPOINT")
    dock.find_child("APIModel", true, false).text = "offline-range-fixture"
    dock.get_ai_settings_control().find_child("APIKey", true, false).text = "offline-fixture"
    dock.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = true
    dock.find_child("ConsultationOnly", true, false).button_pressed = true
    for i in range(200):
        if not dock.find_child("Send", true, false).disabled:
            break
        await create_timer(0.05).timeout
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
    for label in dock.find_children("*", "RichTextLabel", true, false):
        print(label.get_parsed_text())
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
        executable = copy_editor(args.godot, root / "editor")
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

        def chunk(label, path, text, offset=0, limit=1000, tool="read_file"):
            selected = text[offset : offset + limit]
            cases.append((
                label,
                tool,
                dict(path=path, char_offset=offset, char_limit=limit),
                dict(
                    content=selected,
                    char_offset=offset,
                    returned_characters=len(selected),
                    total_characters=len(text),
                    next_char_offset=min(offset, len(text)) + len(selected),
                    truncated=len(selected) < len(text),
                    has_more=offset + len(selected) < len(text),
                    read_mode="character_range",
                ),
            ))

        long_text = '{"text":"' + "x" * 300000 + "汉😀" + '"}\n'
        long_path = fixture("long.jsonl", long_text.encode())
        for offset in (0, 131072, 299500):
            chunk("long JSONL chunk " + str(offset), long_path, long_text, offset)
        chunk("emoji boundary", long_path, long_text, 300009, 1, "read_script")
        chunk("EOF", long_path, long_text, len(long_text))
        chunk("beyond EOF", long_path, long_text, 2147483647)
        chunk("empty chunk", fixture("empty-chunk.txt", b""), "")
        chunk("escaped chunk", escaped, "\x01" * 50000)
        chunk("scan boundary chunk", boundary, "a" * 16383 + "汉😀\nsecond", 16383, 2)
        chunk("BOM chunk", fixture("bom-chunk.txt", b"\xef\xbb\xbfhello"), "\ufeffhello", 0, 1)
        for kwargs in [
            dict(char_offset=-1),
            dict(char_offset=0.5),
            dict(char_offset=True),
            dict(char_offset="0"),
            dict(char_offset=2147483648),
            dict(char_limit=0),
            dict(char_limit=32769),
            dict(char_limit=1.5),
            dict(char_limit=False),
            dict(char_offset=0, offset=1),
            dict(char_limit=1, limit=1),
        ]:
            failure("invalid chunk " + str(kwargs), long_path, "Character offset", **kwargs)
        failure("chunk scan budget", str(sparse), "16 MiB", char_limit=1)
        for index, data in enumerate([
            b"ok\x00",
            b"ok\xc0\xaf",
            b"ok\xed\xa0\x80",
            b"ok\xf4\x90\x80\x80",
            b"ok\xe4\xb8",
            b"ok\xe4a\x80",
        ]):
            failure(
                "invalid chunk UTF-8 " + str(index), fixture("bad-chunk-" + str(index), data), "UTF-8", char_limit=1
            )

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                data = json.dumps({"data": [{"id": "offline-range-fixture"}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

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
        (executable.parent / "editor_data/editor_settings-4.8.tres").write_text(
            '[gd_resource type="EditorSettings" format=3]\n\n[resource]\n'
            + "ai_chat/backend = 0\n"
            + 'ai_chat/endpoint = "http://127.0.0.1:'
            + str(server.server_port)
            + '/v1/chat/completions"\n'
            + 'ai_chat/model = "offline-range-fixture"\n'
            + "ai_chat/editor_control_bridge_enabled = false\n"
        )
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
