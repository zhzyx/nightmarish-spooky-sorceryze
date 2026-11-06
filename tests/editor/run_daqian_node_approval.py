"""Exercise the native command approval path with isolated Issue and model transports."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading


class Model(BaseHTTPRequestHandler):
    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        message = {"role": "assistant", "content": "Verified"}
        if not any(turn["role"] == "tool" for turn in request["messages"]):
            message.update(content="", tool_calls=[{
                "id": "fixture-command", "type": "function", "function": {
                    "name": "run_command", "arguments": json.dumps({
                        "command": "echo once >> executions", "cwd": str(self.server.workspace)
                    })
                }
            }])
        response = json.dumps({"choices": [{"message": message, "finish_reason":
                              "tool_calls" if "tool_calls" in message else "stop"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


def run(binary):
    with tempfile.TemporaryDirectory(prefix="daqian-approval-") as tmp, ThreadingHTTPServer(("127.0.0.1", 0), Model) as server:
        project = Path(tmp)
        workspace = project / ".fixture"
        server.workspace = workspace
        threading.Thread(target=server.serve_forever, daemon=True).start()
        project.joinpath("project.godot").write_text('config_version=5\n[application]\nconfig/name="Approval test"\n')
        shutil.copyfile(Path(__file__).with_name("daqian_node_approval.gd"), project / "test.gd")
        bridge = workspace / "tools/gonggong_bridge.py"
        board = workspace / "customizations/components/godot-host/daqian/board.py"
        board.parent.mkdir(parents=True)
        bridge.parent.mkdir()
        actor = dict(login="tester", user_id="42", repo="fixture/board", repo_id="1")
        row = dict(number=210, title="Approval test", status="in-progress", closed=False,
                   request="daqian-direct-" + "a"*20, url="https://github.com/fixture/board/issues/210",
                   updated="current", source_sha256="b"*64, dependencies=[], owners=[], decision=False,
                   design_document=dict(path="design-docs/test.md", source="fixture", markdown=
                                        ("Unrelated paragraph\n\n"*100 + "<!-- daqian-node:run_command -->\n## Bound section\n\nDetails\n" + "Evidence\n\n"*50)))
        reporting = dict(tenant_id="fixture", request_ref=row["request"], source_ref=row["url"],
                         source_sha256=row["source_sha256"], actor=actor["user_id"], agent=dict(id="sinan"))
        bridge.write_text('import json,sys\nfrom pathlib import Path\n' +
                          f'result = {dict(ok=True, context="Fixture", reporting=reporting)!r}\n' +
                          'Path(sys.argv[sys.argv.index("--out")+1]).write_text(json.dumps(result))\n')
        board.write_text('import json,sys\nfrom pathlib import Path\n' +
                         f'actor={actor!r}\nrow={row!r}\n' +
                         'if "--end-session" in sys.argv: sys.exit()\n' +
                         'if (Path(sys.argv[sys.argv.index("--repo")+1])/"changed").exists(): row["updated"]="changed"\n' +
                         'result={"access":actor} if "--access-only" in sys.argv else {"board":dict(actor,issues=[row], verified_at="now")}\n' +
                         'Path(sys.argv[sys.argv.index("--result")+1]).write_text(json.dumps(result))\n')
        env = dict(os.environ, DAQIAN_TEST_REPO=str(workspace), DAQIAN_TEST_PYTHON=sys.executable,
                   GODOT_AI_API_KEY="fixture-key", DAQIAN_TEST_ENDPOINT=f"http://127.0.0.1:{server.server_port}/v1/chat/completions")
        result = subprocess.run([str(binary.resolve()), "--headless", "--editor", "--path", str(project),
                                 "--script", "res://test.gd"], env=env, capture_output=True, text=True, timeout=70)
        server.shutdown()
        log = result.stdout + result.stderr
        if result.returncode or "DAQIAN_INLINE_APPROVAL_OK" not in log or "SCRIPT ERROR" in log:
            raise SystemExit(log)
        print("DAQIAN_INLINE_APPROVAL_OK")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    run(parser.parse_args().godot)
