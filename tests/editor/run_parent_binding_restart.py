"""Crash/cold-start a real parent requirement binding using offline transports only."""

import argparse
import hashlib
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from contextlib import nullcontext
from pathlib import Path

from editor_test_isolation import copy_editor
from run_requirements_intake import GH_FIXTURE, run_editor
from runtime_policy_fixture import copy_runtime_policy

ROOT = Path(__file__).resolve().parents[2]


def main():
    from editor_provenance_process import WindowsJob

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--checkpoint-failure", action="store_true", help="Fail history writes, then retry the saved binding"
    )
    args = parser.parse_args()
    if args.godot.name.endswith(".console.exe"):
        parser.error("Use the engine .exe directly; the console wrapper owns a kill-on-close Job")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    calls = []
    with tempfile.TemporaryDirectory(prefix="parent-binding-") as folder:
        root = Path(folder).resolve()
        project = root / "project"
        project.mkdir()
        for name in ("framework", "customizations", "integrations", ".github"):
            shutil.copytree(ROOT / name, root / name, ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("CURRENT_FRAMEWORK.json", "work-items.json"):
            shutil.copyfile(ROOT / name, root / name)
        (root / "tools").mkdir()
        for name in ("gonggong_bridge.py", "gonggong_runtime_config.py", "check_gonggong_distribution.py"):
            shutil.copyfile(ROOT / "tools" / name, root / "tools" / name)
        for name in ("auth", "api", "issue"):
            (project / name).write_text(GH_FIXTURE, encoding="utf-8", newline="\n")
        for command in (
            ["git", "init", "--quiet"],
            ["git", "config", "core.autocrlf", "false"],
            ["git", "remote", "add", "origin", "https://github.com/zhzyx/nightmarish-spooky-sorceryze.git"],
            ["git", "add", "."],
            [
                "git",
                "-c",
                "user.name=Native fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "--quiet",
                "-m",
                "Offline binding fixture",
            ],
            [
                sys.executable,
                "-I",
                str(root / "customizations/platforms/data-collection/git-files/storage/diting_files.py"),
                "init",
                "--repo",
                str(root),
            ],
        ):
            subprocess.run(command, cwd=root, check=True, capture_output=True)
        editor = copy_editor(args.godot, root / "isolated-editor")
        installation = editor.parent
        shutil.copyfile(ROOT / "SConstruct", installation / "SConstruct")
        shutil.copyfile(ROOT / "CURRENT_FRAMEWORK.json", installation / "CURRENT_FRAMEWORK.json")
        for name in ("framework", "customizations", "integrations", "tools"):
            shutil.copytree(root / name, installation / name)
        copy_runtime_policy(ROOT, installation)
        (project / "project.godot").write_text(
            '[application]\nconfig/name="Parent binding restart fixture"\n', encoding="utf-8"
        )
        shutil.copyfile(ROOT / "tests/editor/parent_binding_restart.gd", project / "gate.gd")

        class Model(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.reply({"data": [{"id": "fixture", "object": "model"}]})

            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                assert "Requirements intake only" in request["messages"][0]["content"], "Unexpected production request"
                value = json.loads(request["messages"][-1]["content"])
                calls.append({"existing_issue": value["existing_issue"], "request": value["request"]})
                proposal = {
                    "decision": "new",
                    "title": "Parent binding fixture",
                    "category": "development",
                    "goal": "Persist the parent feature binding",
                    "scope": ["One parent feature"],
                    "acceptance": ["The requested feature is observable"],
                    "questions": [],
                }
                self.reply({
                    "choices": [
                        {"message": {"role": "assistant", "content": json.dumps(proposal)}, "finish_reason": "stop"}
                    ]
                })

            def reply(self, value):
                body = json.dumps(value).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *unused):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Model)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        env = dict(
            os.environ,
            GONGGONG_WORKSPACE=str(root),
            GONGGONG_TEST_WORKSPACE=str(root),
            GONGGONG_TEST_PYTHON=sys.executable,
            GONGGONG_GH=sys.executable,
            GONGGONG_GIT=shutil.which("git"),
            GONGGONG_TEST_ENDPOINT=f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
            GONGGONG_TEST_CHECKPOINT_FAILURE="1" if args.checkpoint_failure else "0",
            GONGGONG_FRAMEWORK_SOURCE=str(root / "absent-upstream"),
        )
        for name in ("GONGGONG_PYTHON", "GONGGONG_NODE", "GONGGONG_CODEX", "OPENAI_API_KEY", "GODOT_AI_API_KEY"):
            env.pop(name, None)
        for name in ("HOME", "APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
            path = root / "private" / name
            path.mkdir(parents=True)
            env[name] = str(path)
        (Path(env["HOME"]) / "Library/Caches").mkdir(parents=True)
        config = installation / "editor_data/gonggong/config.json"
        config.parent.mkdir(parents=True)
        config.write_text(
            json.dumps({
                "schema_version": 1,
                "runtimes": {"workflow_python": sys.executable, "node": shutil.which("node"), "codex": ""},
            }),
            encoding="utf-8",
        )
        command = [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://gate.gd"]
        try:
            with (
                args.out.with_suffix(".warm.log").open("wb") as log,
                WindowsJob(uuid.uuid4().hex) if os.name == "nt" else nullcontext() as job,
            ):
                spawn = job.spawn if job else subprocess.Popen
                child = spawn(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
                try:
                    deadline = time.monotonic() + 120
                    while (
                        not (root / "binding-before.json").exists()
                        and child.poll() is None
                        and time.monotonic() < deadline
                    ):
                        time.sleep(0.02)
                    assert (root / "binding-before.json").exists(), (
                        "Native requirement never produced a parent binding; inspect warm log"
                    )
                    before = json.loads((root / "binding-before.json").read_text(encoding="utf-8"))
                    assert len(calls) == 1 and calls[0]["existing_issue"] is None, calls
                    assert before["binding"]["request_id"].startswith("requirement-"), before
                    if args.checkpoint_failure:
                        assert before.get("checkpoint_failure_verified"), before
                        gh_calls = [json.loads(line) for line in (root / "fake-gh-calls.log").read_text().splitlines()]
                        assert sum(op == "issue" and args[0] == "create" for op, args in gh_calls) == 1, gh_calls
                finally:
                    if child.poll() is None:
                        child.kill()
                    child.wait(timeout=10)
                    if job:
                        job.quiesce()
            result = run_editor(command, root, dict(env, GONGGONG_TEST_BINDING_PHASE="cold"))
            args.out.with_suffix(".cold.stdout.log").write_bytes(result.stdout)
            args.out.with_suffix(".cold.stderr.log").write_bytes(result.stderr)
            cold = json.loads((root / "binding-cold.json").read_text(encoding="utf-8"))
            report = {
                "ok": before["durable_before_crash"] and cold["ok"] and result.returncode == 0,
                "editor_sha256": hashlib.sha256(args.godot.read_bytes()).hexdigest(),
                "public_parent_requirement": True,
                "model_and_github": "isolated loopback/CLI fixtures only",
                "ordinary_requirements_calls": len(calls),
                "checkpoint_failure_tested": args.checkpoint_failure,
                "warm": before,
                "cold": cold,
                "cold_exit_code": result.returncode,
                "termination": "kill real editor before graceful shutdown; cold reopen same isolated project",
            }
            args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            assert report["ok"], report
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
