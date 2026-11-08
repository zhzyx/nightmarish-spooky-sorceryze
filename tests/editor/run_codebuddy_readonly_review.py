"""Private native mounted-owner submit and CodeBuddy reviewer/parent closure.

The Git repository, Issue service, account scope and ACP model are offline
fixtures. Godot executes its real candidate, mount, typed review and receipt
paths. This never contacts a provider or manipulates a production editor.
"""

import argparse
import hashlib
import importlib.util
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
from run_design_batch import BRIDGE, git, tool_call

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("editor_client", ROOT / "tools/editor_control_client.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Editor client module loader is unavailable")
client_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client_module)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    os.environ.pop("GONGGONG_WORKSPACE", None)
    calls, errors = [], []
    with tempfile.TemporaryDirectory(prefix="native-codebuddy-review-") as tmp:
        folder = Path(tmp).resolve()
        original = folder / "original"
        original.mkdir()
        remote = folder / "remote.git"
        git(folder, "init", "--bare", str(remote))
        git(original, "init", "-b", "main")
        git(original, "config", "user.name", "Offline Fixture")
        git(original, "config", "user.email", "fixture@example.invalid")
        git(original, "remote", "add", "origin", "https://github.com/example/design-batch.git")
        git(original, "config", "url." + str(remote) + ".insteadOf", "https://github.com/example/design-batch.git")
        files = {
            "work-items.json": json.dumps({
                "repository": "example/design-batch",
                "tenant_id": "fixture",
                "category_labels": ".github/labels.json",
            }),
            ".github/labels.json": '[{"name":"type:bug"}]',
            "SConstruct": "# offline fixture engine\n",
            "tools/gonggong_bridge.py": BRIDGE,
            "tools/editor_self_build.py": "# private fixture build entry\n",
            "editor/source.cpp": "OFFLINE_SENTINEL\n",
            "gonggong-diting-data/dataset.json": json.dumps({
                "schema_version": 1,
                "dataset_id": "00000000-0000-4000-8000-000000000441",
                "name": "gonggong-diting-data",
                "origin_framework": "gonggong",
            }),
            "gonggong-diting-data/.gitattributes": "* text eol=lf\n",
        }
        for name, content in files.items():
            target = original / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        git(original, "add", ".")
        git(original, "commit", "-m", "private CodeBuddy reviewer fixture")
        git(original, "push", "origin", "main")
        git(original, "checkout", "-b", "existing-owner")
        project = original / "samples/project"
        project.mkdir(parents=True)
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Private CodeBuddy reviewer"\n'
        )
        shutil.copyfile(ROOT / "tests/editor/codebuddy_readonly_review.gd", project / "gate.gd")
        issue = {
            "number": 441,
            "html_url": "https://github.com/example/design-batch/issues/441",
            "state": "open",
            "updated_at": "2026-11-08T00:00:00Z",
            "body": "<!-- gonggong-request:design-batch-fixture -->",
            "labels": [{"name": name} for name in ["type:bug", "status:in-progress", "workspace:gonggong"]],
        }
        gh = folder / "fake-gh"
        gh.write_text(
            "#!"
            + sys.executable
            + "\nimport json,sys\nassert sys.argv[-1].endswith('/441')\nprint(json.dumps("
            + repr(issue)
            + "))\n"
        )
        gh.chmod(0o700)
        git_wrapper = folder / "git"
        git_wrapper.write_text(
            "#!"
            + sys.executable
            + '\nimport os,sys\na=sys.argv[1:]\nif a[-3:]==["remote","get-url","origin"]: print("https://github.com/example/design-batch.git")\nelse: os.execv("/usr/bin/git",["git",*a])\n'
        )
        git_wrapper.chmod(0o700)
        binary = copy_editor(args.godot, folder / "editor")
        artifact_sha256 = hashlib.sha256(binary.read_bytes()).hexdigest()
        (folder / "SConstruct").touch()
        (folder / "tools").symlink_to(ROOT / "tools", target_is_directory=True)

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                self.reply({"data": [{"id": "private-fixture"}]})

            def reply(self, value):
                body = json.dumps(value).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                try:
                    body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                    prompt = next(row["content"] for row in reversed(body["messages"]) if row["role"] == "user")
                    calls.append(prompt)
                    assert prompt in ["DESIGN_BATCH_WARMUP", "MOUNTED_PRIVATE_INSTRUCTION"], prompt
                    if prompt == "DESIGN_BATCH_WARMUP":
                        bindings = [
                            json.loads(path.read_text())
                            for path in (original / ".git/gonggong-engine-candidates").glob("*.json")
                        ]
                        assert len(bindings) == 1
                        candidate = Path(bindings[0]["source_root"])
                        assert candidate != original and candidate.is_dir()
                        target = candidate / "editor/source.cpp"
                        results = {row["tool_call_id"]: row for row in body["messages"] if row["role"] == "tool"}
                        if "private-history-write" not in results:
                            message = tool_call(
                                "private-history-write",
                                "write_file",
                                {"path": str(target), "content": "OFFLINE_SENTINEL\nPRIVATE_REAL_HISTORY_CHANGE\n"},
                            )
                            self.reply({"choices": [{"message": message, "finish_reason": "tool_calls"}]})
                            return
                        assert target.read_text() == "OFFLINE_SENTINEL\nPRIVATE_REAL_HISTORY_CHANGE\n"
                        assert (original / "editor/source.cpp").read_text() == "OFFLINE_SENTINEL\n"
                    answer = (
                        "PRIVATE_NATIVE_WARMUP_OK"
                        if prompt == "DESIGN_BATCH_WARMUP"
                        else "MOUNTED_PRIVATE_INSTRUCTION_OK"
                    )
                    self.reply({
                        "choices": [{"message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}]
                    })
                except Exception as error:
                    errors.append(str(error))
                    self.send_error(500)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        endpoint = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
        settings = {
            "ai_chat/backend": 0,
            "ai_chat/endpoint": endpoint,
            "ai_chat/model": "private-fixture",
            "ai_chat/editor_control_bridge_enabled": True,
        }
        (binary.parent / "editor_data/editor_settings-4.8.tres").write_text(
            '[gd_resource type="EditorSettings" format=3]\n\n[resource]\n'
            + "\n".join(key + " = " + json.dumps(value) for key, value in settings.items())
            + "\n"
        )
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("GONGGONG_") and key not in {"OPENAI_API_KEY", "GODOT_AI_API_KEY"}
        }
        for key in ["APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "TEMP", "TMP"]:
            (folder / key).mkdir()
            env[key] = str(folder / key)
        env.update(
            DESIGN_BATCH_ROOT=str(original),
            DESIGN_BATCH_PYTHON=sys.executable,
            DESIGN_BATCH_SOURCE=str(ROOT),
            DESIGN_BATCH_NODE=str(args.node.resolve()),
            DESIGN_BATCH_FINALIZED="# Private fixture\n",
            CODEBUDDY_REVIEW_BRIDGE=str(ROOT / "tools/codebuddy_cli/godot_bridge.js"),
            CODEBUDDY_REVIEW_ENTRY=str(ROOT / "tests/editor/mock_codebuddy_cli.js"),
            GODOT_ACP_LOG_DIRECTORY=str(folder / "acp-logs"),
            GONGGONG_GH=str(gh),
            GONGGONG_GIT=str(git_wrapper),
            PATH=str(folder) + os.pathsep + env.get("PATH", ""),
        )
        log = folder / "editor.log"
        with log.open("wb") as output:
            process = subprocess.Popen(
                [str(binary), "--headless", "--editor", "--path", str(project), "--script", "res://gate.gd"],
                env=env,
                stdout=output,
                stderr=subprocess.STDOUT,
            )

            def until(callback, seconds=100):
                deadline = time.monotonic() + seconds
                while time.monotonic() < deadline:
                    value = callback()
                    if value:
                        return value
                    if process.poll() is not None:
                        raise AssertionError(log.read_text(errors="replace")[-8000:])
                    time.sleep(0.03)
                raise AssertionError("Private native fixture timed out: " + log.read_text(errors="replace")[-8000:])

            serial = 0

            def command(action, wait=True):
                nonlocal serial
                serial += 1
                pending = project / "command.pending"
                pending.write_text(json.dumps({"serial": serial, "action": action}))
                pending.replace(project / "fixture-command.json")
                if wait:
                    target = project / f"ack-{serial}.json"
                    until(target.exists)
                    return json.loads(target.read_text())

            try:
                until((project / "ready.json").exists)
                client = client_module.EditorClient(project, process.pid)

                def route(ident, action, **values):
                    return client.route({
                        "intent": "engine_operation",
                        "request_id": ident,
                        "source": "private-review-fixture",
                        "operation": {"action": action, **values},
                    })

                context = route("mounted-context", "chat_host_context")
                assert context["ok"] and context["mounted"] and context["host_instance"] > 0, context
                rejected = route(
                    "wrong-host",
                    "chat_host_send_message",
                    host_instance=context["host_instance"] + 1,
                    value="NEVER_SEND",
                )
                assert rejected.get("error") == "mounted_host_owner_changed_or_unbound", rejected
                accepted = route(
                    "mounted-submit",
                    "chat_host_send_message",
                    host_instance=context["host_instance"],
                    value="MOUNTED_PRIVATE_INSTRUCTION",
                )
                if not accepted.get("confirmation_required"):
                    diagnostic = {
                        "context": context,
                        "response": accepted,
                        "ready": json.loads((project / "ready.json").read_text()),
                        "candidates": [
                            json.loads(path.read_text())
                            for path in (original / ".git/gonggong-engine-candidates").glob("*.json")
                        ],
                        "history": json.loads((project / ".godot/editor/ai_chat_history.json").read_text()),
                    }
                    args.out.with_suffix(".diagnostic.json").write_text(
                        json.dumps(diagnostic, ensure_ascii=False, indent=2)
                    )
                assert accepted.get("manual_confirmation_required") and accepted.get("confirmation_required"), accepted
                assert calls == ["DESIGN_BATCH_WARMUP", "DESIGN_BATCH_WARMUP"]
                assert command("approve")["visible"]
                result = client.status("mounted-submit", "private-review-fixture")
                assert (
                    result.get("ok") and result.get("send_requested") and result.get("business_completed") is False
                ), result
                until(
                    lambda: (
                        value
                        if "MOUNTED_PRIVATE_INSTRUCTION_OK" in (value := command("read"))["text"] and not value["busy"]
                        else None
                    )
                )
                command("unmount")
                history_page = route("actual-native-history", "chat_history")
                assert history_page.get("ok") and history_page.get("rows"), history_page
                changes = None
                for i, snapshot_id in enumerate(history_page["rows"]):
                    request_id = f"actual-native-changes-{i}"
                    preview = route(request_id, "chat_show_changes", value=snapshot_id)
                    if preview.get("confirmation_required"):
                        assert preview.get("manual_confirmation_required"), preview
                        assert command("approve")["visible"]
                        changes = client.status(request_id, "private-review-fixture")
                        assert changes.get("ok") and changes.get("opened"), changes
                        break
                    assert preview.get("error") == "snapshot_not_in_current_conversation", preview
                assert changes is not None, "No real modified snapshot in current native history"
                history_view = command("history_view")
                assert history_view["visible"] and history_view["file_count"] > 0, history_view
                assert "PRIVATE_REAL_HISTORY_CHANGE" in history_view["after"], history_view
                command("review", wait=False)
                until((project / "complete.json").exists, 150)
                completed = json.loads((project / "complete.json").read_text())
                assert completed["ok"] and completed["backend"] == 1
                assert "READONLY_PARENT_RETURN_OK" in completed["text"]
                process.wait(timeout=15)
                assert process.returncode == 0 and not errors
                assert not list(folder.rglob("readonly-forbidden.txt"))
                candidate_bindings = [
                    json.loads(path.read_text())
                    for path in (original / ".git/gonggong-engine-candidates").glob("*.json")
                ]
                assert len(candidate_bindings) == 1
                assert (
                    candidate_bindings[0]["issue"] == 441
                    and candidate_bindings[0]["request_id"] == "design-batch-fixture"
                )
                history = json.loads((project / ".godot/editor/ai_chat_history.json").read_text())
                reviewers = [
                    agent for agent in history["agents"] if agent.get("sub_agent", {}).get("source") == "review"
                ]
                assert len(reviewers) == 1 and reviewers[0]["backend"] == 1, reviewers
                report = {
                    "ok": True,
                    "issue_number": 559,
                    "request_id": "editor-command-gaps-batch-20261108",
                    "editor_sha256": artifact_sha256,
                    "checks": [
                        "mounted native owner bound",
                        "wrong host rejected",
                        "manual confirmation preserved with autoexec",
                        "mounted original send accepted",
                        "actual native write_file changed only the owned private candidate sentinel",
                        "chat_history returned actual snapshot; manually confirmed chat_show_changes opened native nonempty diff with exact changed content",
                        "CodeBuddy parent delegated actual native reviewer",
                        "readonly ACP write/permission/terminal attacks rejected",
                        "typed native child report automatically returned to parent",
                        "single existing candidate retained",
                        "readonly sentinel absent",
                    ],
                    "provider": "offline ACP fixture only",
                    "limitations": [
                        "No production LLM/account/OS or pixel acceptance claimed",
                        "Native confirmation is simulated only inside the private fixture",
                        "ACP provider is simulated; actual vendor model behavior, authentication and OS filesystem isolation are not verified",
                    ],
                }
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=15)
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.with_suffix(".log").write_bytes(log.read_bytes())
                server.shutdown()
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print("CODEBUDDY_READONLY_NATIVE_OK")


if __name__ == "__main__":
    main()
