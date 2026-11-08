"""Exercise the native command approval path with isolated Issue and model transports."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from editor_test_isolation import copy_editor

ROOT = Path(__file__).resolve().parents[2]
STORAGE = ROOT / "customizations/platforms/data-collection/git-files/storage/diting_files.py"


def prepare_candidate_fixture(project, workspace, row):
    def git(root, *args):
        subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True)

    remote = project / ".remote.git"
    git(project, "init", "--bare", str(remote))
    git(workspace, "init", "-b", "main")
    git(workspace, "config", "user.name", "Approval fixture")
    git(workspace, "config", "user.email", "fixture@example.invalid")
    origin = "https://github.com/fixture/board.git"
    git(workspace, "remote", "add", "origin", origin)
    git(workspace, "config", "url." + remote.as_uri() + ".insteadOf", origin)
    (workspace / "SConstruct").touch()
    (workspace / "tools/editor_self_build.py").touch()
    (workspace / "work-items.json").write_text(json.dumps({"repository": "fixture/board", "tenant_id": "fixture"}))
    (workspace / "design-docs").mkdir()
    (workspace / "design-docs" / (row["request"] + ".md")).write_text("Approval fixture")
    dataset = workspace / "gonggong-diting-data"
    dataset.mkdir()
    (dataset / ".gitattributes").write_text("* text eol=lf\n")
    (dataset / "dataset.json").write_text(
        json.dumps({
            "schema_version": 1,
            "dataset_id": "00000000-0000-4000-8000-000000000210",
            "name": "gonggong-diting-data",
            "origin_framework": "gonggong",
        })
    )
    git(workspace, "add", ".")
    git(workspace, "commit", "-m", "Offline approval fixture")
    git(workspace, "push", "origin", "main")
    # Offline Issue transport, real candidate creation and command provenance guard.
    (project / "SConstruct").touch()
    scripts = project / "tools"
    scripts.mkdir()
    prefix = f"import sys\nsys.path.insert(0, {str(ROOT / 'tools')!r})\n"
    (scripts / "editor_engine_candidate.py").write_text(
        prefix
        + "import editor_engine_candidate as candidate\n"
        + "def verify(workspace, issue, request):\n"
        + f"    assert issue == {row['number']!r} and request == {row['request']!r}\n"
        + "candidate.verify_work_order = verify\nraise SystemExit(candidate.main())\n",
        encoding="utf-8",
    )
    (scripts / "editor_provenance_guard.py").write_text(
        prefix
        + "import runpy\n"
        + f"runpy.run_path({str(ROOT / 'tools/editor_provenance_guard.py')!r}, run_name='__main__')\n",
        encoding="utf-8",
    )


class Model(BaseHTTPRequestHandler):
    def do_GET(self):
        assert self.path == "/v1/models"
        response = json.dumps({"data": [{"id": "fixture"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert request["model"] == "fixture"
        messages = request["messages"]
        last_user = next(turn for turn in reversed(messages) if turn["role"] == "user")
        if last_user["content"] == "Wait for steering":
            self.server.workspace.joinpath("awaiting-steering").touch()
            time.sleep(1.0)
        if last_user["content"] == "Fail this turn":
            self.send_error(401)
            return
        if "canvas fixture rejected" in str(last_user["content"]):
            time.sleep(0.4)
            self.send_error(401)
            return
        followup = any(
            "Check the receipt again" in str(turn.get("content")) for turn in messages if turn["role"] == "user"
        )
        message = {"role": "assistant", "content": "Receipt rechecked" if followup else "Verified"}
        if last_user["content"] == "执行":
            message["content"] = "Continued original Issue"
        if any(turn.get("content") == "Fail this turn" for turn in messages) and "核对已绑定工单" in str(
            last_user["content"]
        ):
            message["content"] = "Retry reached original conversation"
        if last_user["content"] == "Retain the amended icon scope":
            message["content"] = "Amendment resumed on original Issue"
        filtered = "canvas fixture filtered" in str(last_user["content"])
        if filtered:
            time.sleep(0.4)
            message["content"] = json.dumps({"route": "answer", "text": "Unexpected filtered answer"})
        elif any("canvas fixture question" in str(turn.get("content")) for turn in messages if turn["role"] == "user"):
            time.sleep(0.4)  # Allow the real workspace to switch before the receipt arrives.
            message["content"] = json.dumps({"route": "answer", "text": "Canvas fixture answer"})
        elif not followup and not any(turn["role"] == "tool" for turn in messages):
            message.update(
                content="",
                tool_calls=[
                    {
                        "id": "fixture-command",
                        "type": "function",
                        "function": {
                            "name": "run_command",
                            "arguments": json.dumps({
                                "command": "Add-Content -Encoding ascii executions once"
                                if os.name == "nt"
                                else "echo once >> executions",
                            }),
                        },
                    }
                ],
            )
        finish = "tool_calls" if "tool_calls" in message else "stop"
        response = json.dumps({
            "choices": [{"message": message, "finish_reason": "content_filter" if filtered else finish}]
        }).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


def run(binary):
    os.environ.pop("GONGGONG_WORKSPACE", None)
    with (
        tempfile.TemporaryDirectory(prefix="daqian-approval-", ignore_cleanup_errors=os.name == "nt") as tmp,
        ThreadingHTTPServer(("127.0.0.1", 0), Model) as server,
    ):
        project = Path(tmp).resolve()
        isolated_editor = copy_editor(binary, project / "isolated-editor")
        configuration = isolated_editor.parent / "editor_data/gonggong/config.json"
        configuration.parent.mkdir(parents=True, exist_ok=True)
        configuration.write_text(
            json.dumps({"schema_version": 1, "runtimes": {"workflow_python": sys.executable}}), encoding="utf-8"
        )
        # The editor enumerates models at startup, before the test can configure the inline form.
        (isolated_editor.parent / "editor_data/editor_settings-4.8.tres").write_text(
            '[gd_resource type="EditorSettings" format=3]\n\n[resource]\n'
            'ai_chat/backend = 0\nai_chat/endpoint = ""\nai_chat/model = ""\n',
            encoding="utf-8",
        )
        workspace = project / ".fixture"
        server.workspace = workspace
        threading.Thread(target=server.serve_forever, daemon=True).start()
        project.joinpath("project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Approval test"\n', encoding="utf-8"
        )
        shutil.copyfile(Path(__file__).with_name("daqian_node_approval.gd"), project / "test.gd")
        bridge = workspace / "tools/gonggong_bridge.py"
        board = workspace / "customizations/components/godot-host/daqian/board.py"
        board.parent.mkdir(parents=True)
        bridge.parent.mkdir()
        actor = dict(login="tester", user_id="42", repo="fixture/board", repo_id="1")
        row = dict(
            number=210,
            title="Approval test",
            status="planned",
            closed=False,
            request="daqian-direct-" + "a" * 20,
            url="https://github.com/fixture/board/issues/210",
            updated="current",
            source_sha256="b" * 64,
            dependencies=[],
            owners=[],
            decision=False,
            design_document=dict(
                path="design-docs/test.md",
                source="fixture",
                markdown=(
                    "Unrelated paragraph\n\n" * 100
                    + "<!-- daqian-node:run_command -->\n## Bound section\n\nDetails\n"
                    + "Evidence\n\n" * 50
                ),
            ),
        )
        reporting = dict(
            tenant_id="fixture",
            request_ref=row["request"],
            source_ref=row["url"],
            source_sha256=row["source_sha256"],
            actor=actor["user_id"],
            agent=dict(id="sinan", version="1", definition_sha256="0" * 64, origin="offline-fixture"),
        )
        bridge.write_text(
            """import json,runpy,sys
from pathlib import Path
row = {!r}
action = sys.argv[1]
if action == "flush":
    root = Path(sys.argv[sys.argv.index("--workspace")+1])
    store = runpy.run_path({!r})
    for path in (root / ".gonggong-outbox/chat").glob("*.json"):
        store["record"](root, path)
        path.unlink()
    Path(sys.argv[sys.argv.index("--out")+1]).write_text(json.dumps({{"ok": True}}), encoding="utf-8")
    sys.exit()
req = json.loads(Path(sys.argv[sys.argv.index("--request")+1]).read_text(encoding="utf-8"))
if action == 'issue-agent':
    marker = Path(__file__).parent.parent / 'amendment-attempted'
    assert 'Retain the amended icon scope' in str(req)
    if marker.exists():
        result = dict(ok=True, ready=True, issue_number=row['number'], request_id=row['request'], url=row['url'])
    else:
        marker.touch()
        result = dict(ok=False, error='fixture requirements recheck failed')
    Path(sys.argv[sys.argv.index('--out')+1]).write_text(json.dumps(result), encoding='utf-8')
    sys.exit()
assert req['issue_number'] == row['number'] and req['request_id'] == row['request']
if action == 'issue-route':
    assert req['model'] == 'fixture'
    result = dict(ok=True, url=row['url'], number=row['number'], request_id=row['request'], revision=row['updated'],
                  route='sinan', reason='fixture route', ready=True, scope=['Inspect'], acceptance=['Verified'], questions=[])
elif action == 'issue-start':
    assert req["expected_user"] == "42" and req["expected_revision"] == row["updated"]
    Path(__file__).parent.parent.joinpath('started').touch()
    result = dict(ok=True, status='status:in-progress')
else:
    assert action == 'chat'
    result = {!r}
Path(sys.argv[sys.argv.index('--out')+1]).write_text(json.dumps(result), encoding="utf-8")
""".format(row, str(STORAGE), dict(ok=True, context="Fixture", reporting=reporting)),
            encoding="utf-8",
        )
        board.write_text(
            "import json,sys\nfrom pathlib import Path\n"
            + f"actor={actor!r}\nrow={row!r}\n"
            + 'if "--end-session" in sys.argv: sys.exit()\n'
            + 'root=Path(sys.argv[sys.argv.index("--repo")+1])\n'
            + 'if (root/"started").exists(): row["status"]="in-progress"\n'
            + 'if (root/"changed").exists(): row["updated"]="changed"\n'
            + 'result={"access":actor} if "--access-only" in sys.argv else {"board":dict(actor,issues=[row], verified_at="now")}\n'
            + 'Path(sys.argv[sys.argv.index("--result")+1]).write_text(json.dumps(result), encoding="utf-8")\n',
            encoding="utf-8",
        )
        prepare_candidate_fixture(project, workspace, row)
        env = dict(
            {key: value for key, value in os.environ.items() if not key.startswith("GONGGONG_")},
            GONGGONG_RUNTIME_CONFIG=str(configuration),
            DAQIAN_TEST_REPO=str(workspace),
            DAQIAN_TEST_PYTHON=sys.executable,
            GODOT_AI_API_KEY="fixture-key",
            DAQIAN_TEST_ENDPOINT=f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
        )
        try:
            result = subprocess.run(
                [
                    str(isolated_editor),
                    "--headless",
                    "--editor",
                    "--log-file",
                    str(project / "editor.log"),
                    "--path",
                    str(project),
                    "--script",
                    "res://test.gd",
                ],
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
        except subprocess.TimeoutExpired as exc:
            raise SystemExit(((exc.stdout or b"") + (exc.stderr or b"")).decode(errors="replace")) from exc
        server.shutdown()
        log = result.stdout + result.stderr
        if result.returncode or "DAQIAN_INLINE_APPROVAL_OK" not in log or "SCRIPT ERROR" in log:
            raise SystemExit(log)
        print("DAQIAN_INLINE_APPROVAL_OK")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    run(parser.parse_args().godot)
