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
        retry_text = str(last_user["content"])
        if any(turn.get("content") == "Fail this turn" for turn in messages) and (
            "已绑定" in retry_text and "#210" in retry_text and ("继续" in retry_text or "核对" in retry_text)
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
                                "command": (
                                    "Add-Content -Encoding ascii executions once"
                                    + (
                                        "; while (!(Test-Path release-command)) { Start-Sleep -Milliseconds 100 }"
                                        if self.server.restart
                                        else ""
                                    )
                                )
                                if os.name == "nt"
                                else "echo once >> executions"
                                + (
                                    "; while [ ! -e release-command ]; do sleep 0.1; done"
                                    if self.server.restart
                                    else ""
                                ),
                            }),
                        },
                    }
                ],
            )
        if "tool_calls" in message and (self.server.workspace.parent / "missing-cwd-fixture").exists():
            project = self.server.workspace.parent
            candidate = next(project.glob("godot-candidate-*"))
            cwd = candidate / "temporary-cwd"
            cwd.mkdir(exist_ok=True)
            first = message["tool_calls"][0]["function"]
            first["arguments"] = json.dumps({**json.loads(first["arguments"]), "cwd": str(cwd)})
            message["tool_calls"].append({
                "id": "forbidden-next-step",
                "type": "function",
                "function": {"name": "run_command", "arguments": json.dumps({"command": "echo next > next-step"})},
            })
        finish = "tool_calls" if "tool_calls" in message else "stop"
        response = json.dumps({
            "choices": [{"message": message, "finish_reason": "content_filter" if filtered else finish}]
        }).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


def check_command_restart(command, env, project, changed_actor, stop_watching):
    marker = None
    with (project / "child.log").open("wb") as log:
        process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline and process.poll() is None:
                marker = next(project.glob("godot-candidate-*/executions"), None)
                history = project / ".godot/editor/ai_chat_history.json"
                if (
                    marker
                    and marker.read_text().strip() == "once"
                    and history.exists()
                    and "Preserve original queued work" in history.read_text(encoding="utf-8")
                ):
                    break
                time.sleep(0.1)
            else:
                raise AssertionError(
                    "Command effect missing: " + (project / "child.log").read_text(errors="replace")[-3000:]
                )
        finally:
            process.kill()
            process.wait(timeout=15)
    journal = project / ".godot/editor/ai_chat_resume.json"
    original_journal = journal.read_bytes()
    initial = json.loads(original_journal)
    assert initial["conversation"] == initial["candidate"]["owner"] and initial["reporting"]["source_ref"].endswith(
        "/210"
    )
    assert initial["tool_calls"][initial["tool_index"]]["id"] == "fixture-command"
    shutil.copyfile(Path(__file__).with_name("daqian_command_reopen.gd"), project / "reopen.gd")
    reopened = [*command[:-1], "res://reopen.gd"]

    def observe():
        completed = subprocess.run(reopened, env=env, capture_output=True, timeout=45)
        assert completed.returncode == 0, completed.stderr.decode(errors="replace")
        return json.loads((project / "observed.json").read_text(encoding="utf-8"))

    changed = project / ".fixture" / "changed-authority"
    if changed_actor:
        env["DAQIAN_CHANGED_AUTHORITY"] = "1"
        changed.touch()
    env["DAQIAN_RELEASE_MARKER"] = str(marker.with_name("release-command"))
    if stop_watching:
        env["DAQIAN_STOP_WATCH"] = "1"
    terminal = observe()
    if stop_watching:
        assert terminal["stopped"] and not terminal["journal"] and terminal["watched"], terminal
        assert marker.read_text().splitlines() == ["once"] and list(
            journal.parent.glob(journal.name + ".pending-*.stopped-*")
        )
        assert not any("此步骤已返回结果" in item for item in [terminal["text"]])
        journal.write_bytes(original_journal)  # Interruption after durable stop, before unlink.
        after_stop = observe()
        assert not after_stop["watched"] and not after_stop["journal"] and marker.read_text().splitlines() == ["once"]
        print("DAQIAN_COMMAND_WATCH_STOP_OK")
        return
    assert terminal["watched"], terminal
    if changed_actor:
        assert terminal["journal"] and terminal["rejected"], terminal
        changed.unlink()
        del env["DAQIAN_CHANGED_AUTHORITY"]
        del env["DAQIAN_RELEASE_MARKER"]
        terminal = observe()
    assert not terminal["journal"] and marker.read_text().splitlines() == ["once"], terminal
    assert not list(journal.parent.glob(journal.name + ".pending-*"))
    history = json.loads((journal.parent / "ai_chat_history.json").read_text(encoding="utf-8"))
    worker = next(agent for agent in history["agents"] if agent["conversation_id"] == initial["conversation"])
    results = [turn for turn in worker["messages"] if turn.get("tool_call_id") == "fixture-command"]
    assert len(results) == 1 and json.loads(results[0]["content"])["exit_code"] == 0, results
    assert [turn["content"] for turn in worker["queued_messages"]] == ["Preserve original queued work"]
    assert worker["queue_paused"]
    # Recreate the crash window after durable history replacement but before journal removal.
    journal.write_bytes(original_journal)
    retries = observe()
    assert not retries["journal"] and marker.read_text().splitlines() == ["once"], retries
    after = json.loads((journal.parent / "ai_chat_history.json").read_text(encoding="utf-8"))
    restored = next(agent for agent in after["agents"] if agent["conversation_id"] == initial["conversation"])
    assert sum(turn.get("tool_call_id") == "fixture-command" for turn in restored["messages"]) <= 1
    assert sum("此步骤已返回结果" in str(item) for item in restored["transcript"]) == sum(
        "此步骤已返回结果" in str(item) for item in worker["transcript"]
    )
    print("DAQIAN_COMMAND_RESTART_OK", initial["conversation"], initial["tool_calls"][initial["tool_index"]]["id"])


def run(binary, restart=False, changed_actor=False, stop_watching=False):
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
        server.restart = restart
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
            """import json,os,runpy,sys
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
    if os.environ.get("DAQIAN_DELAY_AUTHORITY"):
        import time
        signal = Path(os.environ["DAQIAN_DELAY_AUTHORITY"])
        signal.touch()
        for _ in range(100):
            if not signal.exists():
                break
            time.sleep(0.1)
    if os.environ.get("DAQIAN_CHANGED_AUTHORITY") == "1":
        result["reporting"]["actor"] = "changed"
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
            command = [
                str(isolated_editor),
                "--headless",
                "--editor",
                "--log-file",
                str(project / "editor.log"),
                "--path",
                str(project),
                "--script",
                "res://test.gd",
            ]
            if restart:
                env["DAQIAN_TEST_COMMAND_RESTART"] = "1"
                try:
                    check_command_restart(command, env, project, changed_actor, stop_watching)
                finally:
                    server.shutdown()
                return
            result = subprocess.run(
                command,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
        except subprocess.TimeoutExpired as exc:

            def decoded(value):
                return value.decode(errors="replace") if isinstance(value, bytes) else (value or "")

            raise SystemExit(decoded(exc.stdout) + decoded(exc.stderr)) from exc
        server.shutdown()
        log = result.stdout + result.stderr
        if result.returncode or "DAQIAN_INLINE_APPROVAL_OK" not in log or "SCRIPT ERROR" in log:
            raise SystemExit(log)
        print("DAQIAN_INLINE_APPROVAL_OK")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--command-restart", action="store_true")
    parser.add_argument("--changed-actor", action="store_true")
    parser.add_argument("--stop-watch", action="store_true")
    args = parser.parse_args()
    run(args.godot, args.command_restart, args.changed_actor, args.stop_watch)
