"""Native Yanshi intake acceptance with isolated GitHub/model fixtures; no real services."""

import argparse
import hashlib
import http.server
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

from editor_test_isolation import copy_editor
from run_runtime_setup_simulation import make_package
from runtime_policy_fixture import copy_runtime_policy
from runtime_selector_fixture import native_selector

ROOT = Path(__file__).resolve().parents[2]
GH_FIXTURE = """import json,sys,re,os
from pathlib import Path
r=Path(os.environ['GONGGONG_TEST_WORKSPACE'])
op=Path(__file__).name
args=sys.argv[1:]
with (r/'fake-gh-calls.log').open('a',encoding='utf-8') as log: log.write(json.dumps([op,args])+chr(10))
repo=json.loads((r/'work-items.json').read_text())['repository']
db=r/'fake-issues.json'
issues=json.loads(db.read_text()) if db.exists() else []
if op=='auth': raise SystemExit(1 if (r/'gh_disabled').exists() else 0)
if op=='api':
 path=args[0]
 if path=='user': value={'login':'fixture-worker','id':123}
 elif path=='repos/'+repo: value={'full_name':repo,'permissions':{'push':True}}
 elif '/issues?' in path: value=[issues] if '--slurp' in args else issues
 elif '/comments' in path: value=[[]]
 else: value=next(x for x in issues if x['number']==int(path.split('/')[-1]))
 print(json.dumps(value));raise SystemExit(0)
if args[0]=='create':
 body=Path(args[args.index('--body-file')+1]).read_text(encoding='utf-8')
 labels=[{'name':args[i+1]} for i in range(len(args)) if args[i]=='--label']
 number=8001+len(issues)
 issue={'number':number,'state':'open','body':body,'labels':labels,'title':args[args.index('--title')+1],
        'html_url':'https://github.com/'+repo+'/issues/'+str(number),'updated_at':'2026-11-03T00:00:00Z'}
 issues.append(issue);db.write_text(json.dumps(issues),encoding='utf-8');print(issue['html_url'])
elif args[0]=='edit':
 issue=next(x for x in issues if x['number']==int(args[1]))
 issue['labels']=[x for x in issue['labels'] if not x['name'].startswith('status:')]+[{'name':'status:in-progress'}]
 db.write_text(json.dumps(issues),encoding='utf-8')
elif args[0]=='comment': pass
else: raise SystemExit('unsupported fixture command')
"""


def run_editor(command, root, env):
    if os.name != "nt":
        return subprocess.run(command, cwd=root, env=env, capture_output=True, timeout=240)
    # Reuse the existing suspended-before-assignment Job boundary. Cleanup is
    # restricted to this invocation, including children left after editor exit.
    spec = importlib.util.spec_from_file_location(
        "requirements_owned_process", ROOT / "tools/editor_provenance_process.py"
    )
    processes = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(processes)
    with processes.WindowsJob(uuid.uuid4().hex) as job:
        child = job.spawn(command, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = child.communicate(timeout=240)
        finally:
            job.quiesce()
            child.wait(timeout=5)
        return subprocess.CompletedProcess(command, child.returncode, stdout, stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--portable-chat", action="store_true", help="Pair an unregistered editor with the workspace launcher"
    )
    parser.add_argument("--runtime-source", type=Path)
    parser.add_argument("--runtime-python", type=Path)
    parser.add_argument("--runtime-node", type=Path)
    parser.add_argument("--runtime-git", type=Path)
    args = parser.parse_args()
    direct_runtime = all((args.runtime_python, args.runtime_node, args.runtime_git))
    if any((args.runtime_python, args.runtime_node, args.runtime_git)) and not direct_runtime:
        parser.error("--runtime-python, --runtime-node and --runtime-git must be supplied together")
    if os.name != "nt" and (args.runtime_source or direct_runtime):
        parser.error("Runtime deployment/selector acceptance requires Windows")
    requests = []
    normal = 0
    tool_roundtrips = 0
    catalog_requests = []
    with tempfile.TemporaryDirectory(prefix="requirements-native-") as folder:
        root = Path(folder).resolve()
        shutil.copytree(ROOT / "framework", root / "framework", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(ROOT / "CURRENT_FRAMEWORK.json", root / "CURRENT_FRAMEWORK.json")
        shutil.copytree(ROOT / "customizations", root / "customizations", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / ".github", root / ".github")
        (root / "tools").mkdir()
        for relative in ("tools/check_gonggong_distribution.py", "integrations/gonggong/frozen-distribution.json"):
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, root / relative)
        shutil.copyfile(ROOT / "tools/gonggong_bridge.py", root / "tools/gonggong_bridge.py")
        shutil.copyfile(ROOT / "tools/gonggong_runtime_config.py", root / "tools/gonggong_runtime_config.py")
        shutil.copyfile(ROOT / "tools/configure_gonggong_runtime.ps1", root / "tools/configure_gonggong_runtime.ps1")
        shutil.copyfile(ROOT / "tools/run_gonggong_config_agent.ps1", root / "tools/run_gonggong_config_agent.ps1")
        shutil.copyfile(ROOT / "tools/check_gonggong_github.ps1", root / "tools/check_gonggong_github.ps1")
        shutil.copyfile(ROOT / "tools/install_gonggong_github_cli.ps1", root / "tools/install_gonggong_github_cli.ps1")
        shutil.copyfile(ROOT / "work-items.json", root / "work-items.json")
        for name in ["auth", "api", "issue"]:
            (root / name).write_text(GH_FIXTURE, encoding="utf-8")

        def run(cmd):
            return subprocess.run(cmd, cwd=root, check=True, capture_output=True)

        run(["git", "init", "--quiet"])
        run(["git", "config", "core.autocrlf", "false"])
        run(["git", "remote", "add", "origin", "https://github.com/zhzyx/nightmarish-spooky-sorceryze.git"])
        run(["git", "add", "."])
        run([
            "git",
            "-c",
            "user.name=Native Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "-m",
            "Isolated original framework",
        ])
        run([
            sys.executable,
            "-I",
            str(root / "customizations/platforms/data-collection/git-files/storage/diting_files.py"),
            "init",
            "--repo",
            str(root),
        ])
        isolated_editor = copy_editor(args.godot, root / "isolated-editor")
        # Current hosts resolve receipt code from the running installation.
        # Model that installation separately from this non-engine workspace:
        # putting SConstruct in the workspace would request an engine checkout.
        installation = isolated_editor.parent
        shutil.copyfile(ROOT / "SConstruct", installation / "SConstruct")
        for directory in ("customizations", "tools", "integrations"):
            shutil.copytree(root / directory, installation / directory)
        if args.portable_chat:
            (installation / "customizations/components/godot-host/bridge.py").unlink()
            (installation / "integrations/gonggong/frozen-distribution.json").unlink()
        else:
            # The selected data checkout predates the installed chat protocol. Other
            # workspace operations still use their normal launcher.
            launcher = root / "tools/gonggong_bridge.py"
            launcher.write_text(
                "import sys\nif sys.argv[1] in ('chat', 'flush'):\n"
                "    raise SystemExit('stale workspace chat adapter executed')\n"
                + launcher.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        copy_runtime_policy(ROOT, installation)
        project = root / "project"
        project.mkdir()
        # The editor changes cwd to the opened project before invoking Python.
        for name in ["auth", "api", "issue"]:
            (project / name).write_text(GH_FIXTURE, encoding="utf-8")
        (project / "project.godot").write_text(
            '[application]\nconfig/name="Requirements intake fixture"\n', encoding="utf-8"
        )
        shutil.copyfile(ROOT / "tests/editor/requirements_intake.gd", project / "gate.gd")
        (project / "workflow_probe.txt").write_text("NATIVE_WORKFLOW_READ_OK", encoding="utf-8")

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                catalog_requests.append(self.path)
                if self.path != "/v1/models":
                    self.send_error(404)
                    return
                body = json.dumps({"data": [{"id": "fixture", "object": "model"}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                nonlocal normal, tool_roundtrips
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requirements = "Requirements intake only" in data["messages"][0]["content"]
                # Framework context is appended as a system message on every
                # request, including tool continuations. Classify the latest
                # conversation message rather than the last wire message.
                latest = next(message for message in reversed(data["messages"]) if message["role"] != "system")
                tool_continuation = latest["role"] == "tool"
                requests.append({
                    "requirements": requirements,
                    "roles": [message["role"] for message in data["messages"]],
                    "has_native_read_marker": "NATIVE_WORKFLOW_READ_OK" in json.dumps(data["messages"]),
                    "tool_continuation": tool_continuation,
                })
                if requirements:
                    value = json.loads(data["messages"][-1]["content"])
                    text = value["request"]
                    existing = value["existing_issue"]
                    assert "clarify-feature" in data["messages"][0]["content"]
                    assert "ISOLATED_FRAMEWORK_CONTEXT_FIXTURE" not in data["messages"][0]["content"]
                    if "Create first feature" in text:
                        (root / "first_intake_waiting").touch()
                        time.sleep(2)
                    if "Cancel pending" in text:
                        (root / "model_waiting").touch()
                        time.sleep(1.5)
                    if "API failure" in text and not (root / "api_fixed").exists():
                        self.send_response(503)
                        self.end_headers()
                        return
                    decision = (
                        "continue"
                        if existing and ("Refine" in text or ("second feature" in text and existing["number"] == 8002))
                        else "new"
                    )
                    requests[-1].update(
                        outcome=text, existing_issue=existing["number"] if existing else None, decision=decision
                    )
                    incomplete = "Clarify pending" in text and "用户补充" not in text
                    body = json.dumps({
                        "decision": decision,
                        "title": text.splitlines()[0],
                        "category": "development",
                        "goal": "" if incomplete else text,
                        "scope": [] if incomplete else ["One requested change"],
                        "acceptance": [] if incomplete else ["Observable requested result"],
                        "questions": ["INTAKE_CLARIFICATION_REQUIRED"] if incomplete else [],
                    })
                elif tool_continuation:
                    assert latest["tool_call_id"] == "intake-workflow-read"
                    assert "NATIVE_WORKFLOW_READ_OK" in latest["content"]
                    tool_roundtrips += 1
                    body = "INTAKE_WORK_REPLY_" + str(normal)
                else:
                    normal += 1
                    users = [message["content"] for message in data["messages"] if message["role"] == "user"]
                    requests[-1]["users"] = users
                    if normal == 1:
                        assert any("Create first feature" in text for text in users)
                        assert any("Refine first feature during requirements phase" in text for text in users), (
                            "Development started before applying the intake supplement"
                        )
                    body = "INTAKE_WORK_REPLY_" + str(normal)
                message = {"role": "assistant", "content": body}
                if not requirements and normal == 1 and not tool_continuation:
                    assert any(tool["function"]["name"] == "read_file" for tool in data["tools"])
                    message["content"] = ""
                    message["tool_calls"] = [
                        {
                            "id": "intake-workflow-read",
                            "type": "function",
                            "function": {
                                "name": "read_file",
                                "arguments": json.dumps({"path": "res://workflow_probe.txt"}),
                            },
                        }
                    ]
                result = json.dumps({
                    "choices": [
                        {"message": message, "finish_reason": "tool_calls" if "tool_calls" in message else "stop"}
                    ]
                }).encode()
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(result)))
                    self.end_headers()
                    self.wfile.write(result)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, *unused):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        env = dict(
            os.environ,
            GONGGONG_WORKSPACE=str(root),
            GONGGONG_TEST_WORKSPACE=str(root),
            GONGGONG_TEST_PYTHON=sys.executable,
            GONGGONG_GH=sys.executable,
            GONGGONG_TEST_ENDPOINT=f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
            GONGGONG_FRAMEWORK_SOURCE=str(root / "absent-upstream"),
        )
        for name in ("GONGGONG_PYTHON", "GONGGONG_NODE", "GONGGONG_CODEX"):
            env.pop(name, None)
        bootstrap_runtimes = {"workflow_python": sys.executable, "node": shutil.which("node"), "codex": ""}
        selector_marker = None
        expected_runtime_paths = None
        assert bootstrap_runtimes["node"], "Native fixture needs the existing host Node"
        env["GONGGONG_GIT"] = shutil.which("git")
        assert env["GONGGONG_GIT"], "Native fixture needs the existing host Git"
        if args.runtime_source or direct_runtime:
            if direct_runtime:
                # Keep workflow_python mutable so the scene can trigger missing Python.
                # The explicit source package exposes a launcher for the requested Python
                # to deterministic discovery without a persistent environment override.
                runtime_source = root / "direct-runtime-source"
                direct_paths = {
                    "python": args.runtime_python.resolve(strict=True),
                    "node": args.runtime_node.resolve(strict=True),
                    "git": args.runtime_git.resolve(strict=True),
                }
                make_package(runtime_source, direct_paths)
                bootstrap_runtimes["node"] = str(direct_paths["node"])
                env["GONGGONG_GIT"] = str(direct_paths["git"])
            else:
                runtime_source = args.runtime_source.resolve()
            env["GONGGONG_RUNTIME_SOURCE"] = str(runtime_source)
            expected_runtime_paths = {
                "python": str(runtime_source / "python/python.exe"),
                "node": bootstrap_runtimes["node"],
                "git": env["GONGGONG_GIT"],
                "gh": env["GONGGONG_GH"],
            }
            env["GONGGONG_TEST_RUNTIME_PYTHON"] = (
                str(args.runtime_python.resolve()) if direct_runtime else str(runtime_source / "python/python.exe")
            )
            env["GONGGONG_TEST_RUNTIME_NODE"] = (
                str(args.runtime_node.resolve()) if direct_runtime else str(runtime_source / "node/node.exe")
            )
            env["GONGGONG_TEST_RUNTIME_GIT"] = (
                str(args.runtime_git.resolve()) if direct_runtime else str(runtime_source / "git/cmd/git.exe")
            )
            fake_codex, selector_marker = native_selector(
                root / "native-selector",
                {
                    "python": env["GONGGONG_TEST_RUNTIME_PYTHON"],
                    "node": env["GONGGONG_TEST_RUNTIME_NODE"],
                    "git": env["GONGGONG_TEST_RUNTIME_GIT"],
                    "gh": env["GONGGONG_GH"],
                },
            )
            # A discoverable trap proves generic setup never invokes a provider.
            # It is not configured as an editor runtime or used to enable the scenario.
            env["CODEX_EXE"] = str(fake_codex)
            env["GONGGONG_TEST_RUNTIME_SETUP"] = "1"

        # The panel checks runtime readiness in its constructor's deferred work.
        # Establish the valid bootstrap before the editor starts, then let the
        # scene driver deliberately remove Python after catalog readiness. A
        # startup environment override would freeze the field and prevent that.
        bootstrap_config = installation / "editor_data/gonggong/config.json"
        bootstrap_config.parent.mkdir(parents=True, exist_ok=True)
        bootstrap_config.write_text(
            json.dumps({"schema_version": 1, "runtimes": bootstrap_runtimes}) + "\n", encoding="utf-8"
        )

        for name in ["OPENAI_API_KEY", "GODOT_AI_API_KEY"]:
            env.pop(name, None)
        for name in ["APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME"]:
            env[name] = str(root / name)
            (root / name).mkdir()
        try:
            result = run_editor(
                [
                    str(isolated_editor),
                    "--headless",
                    "--editor",
                    "--path",
                    str(project),
                    "--script",
                    "res://gate.gd",
                ],
                root,
                env,
            )
        finally:
            server.shutdown()
            server.server_close()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.with_suffix(".stdout.log").write_bytes(result.stdout)
        args.out.with_suffix(".stderr.log").write_bytes(result.stderr)
        args.out.with_suffix(".debug.json").write_text(
            json.dumps(
                {
                    "requests": requests,
                    "catalog_requests": catalog_requests,
                    "setup_reports": [
                        {"name": p.name, "result": json.loads(p.read_text(encoding="utf-8-sig"))}
                        for p in (installation / "editor_data").rglob("gonggong-setup-*.json")
                    ],
                    "journals": [
                        json.loads(p.read_text(encoding="utf-8"))
                        for p in (root / ".gonggong-outbox/requirements").glob("*.json")
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        assert result.returncode == 0 and b"REQUIREMENTS_AGENT_NATIVE_OK" in result.stdout, result.stdout[-3500:]
        if selector_marker is not None:
            assert not selector_marker.exists(), "Generic setup invoked the Codex trap"
            setup_results = [
                json.loads(path.read_text(encoding="utf-8-sig"))
                for path in (installation / "editor_data").rglob("gonggong-setup-*.json")
                if not path.name.endswith(".progress.json")
            ]
            configured = [value for value in setup_results if value.get("state") == "configured"]
            assert configured, "Missing actual successful runtime deployment receipt"
            assert all(value["agent"]["provider_started"] is False for value in configured)
            for value in configured:
                for component, expected in expected_runtime_paths.items():
                    assert Path(value[component]).resolve() == Path(expected).resolve(), (
                        "Runtime selection did not use the explicit fixture path",
                        component,
                        value[component],
                        expected,
                    )
        issues = json.loads((root / "fake-issues.json").read_text())
        assert len(issues) == 5, issues
        documents = list((root / "design-docs").glob("*.md"))
        assert len(documents) == 5, documents
        supplements = [
            request
            for request in requests
            if request.get("existing_issue") == 8001
            and "Refine first feature during requirements phase" in request.get("outcome", "")
        ]
        assert len(supplements) == 1 and supplements[0]["decision"] == "continue", requests
        assert not any(x["title"] == "Refine first feature during requirements phase" for x in issues), issues
        assert normal == 7 and sum(x["requirements"] for x in requests) == 11, requests
        assert tool_roundtrips == 1, requests
        events = [
            json.loads(p.read_text(encoding="utf-8")) for p in (root / "gonggong-diting-data/events").rglob("*.json")
        ]
        for p in (root / ".gonggong-outbox").rglob("*.json"):
            assert "intake-unit-session-secret" not in p.read_text(encoding="utf-8")
        assert not list((root / ".gonggong-outbox/chat").glob("*.json"))
        run(["git", "add", "."])
        run([
            "git",
            "-c",
            "user.name=Native Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "-m",
            "Isolated actual fixture receipts",
        ])
        receipt = json.loads(
            run([
                sys.executable,
                "-I",
                str(root / "customizations/platforms/data-collection/git-files/storage/diting_files.py"),
                "git-check",
                "--repo",
                str(root),
                "--require-committed",
            ]).stdout
        )
        report = {
            "ok": True,
            "native_page": True,
            "runtime_setup_and_resume": bool(args.runtime_source or direct_runtime),
            "runtime_setup_provider_invoked": False if selector_marker is not None else None,
            "runtime_setup_explicit_paths_verified": expected_runtime_paths is not None,
            "runtime_setup_source_kind": "compiled launchers to explicit binaries"
            if direct_runtime
            else "supplied package",
            "catalog_requests": catalog_requests,
            "bootstrap_runtime_configuration": "private installation JSON; mutable fields, no Python/Node/Codex override",
            "windows_owned_process_cleanup": "verified Job empty" if os.name == "nt" else "not applicable",
            "actual_native_read_tool_roundtrips": tool_roundtrips,
            "actual_yanshi_admission": True,
            "model_and_github": "isolated loopback/CLI fixtures only",
            "requirements_calls": 11,
            "development_calls": normal,
            "issues_created": len(issues),
            "events": len(events),
            "git_check": receipt,
            "cases": [
                "new requirement",
                "supplement during intake amends the same Issue before the first development request",
                "followup reuses Issue",
                "portable workspace launcher"
                if args.portable_chat
                else "installed chat and flush with stale workspace launcher",
                "new requirement while bound",
                "same text new turn still classified",
                "cancel before publication",
                "model API repair then explicit retry",
                "GitHub auth repair before model call",
                "clarification pauses and resumes the same requirement",
            ],
            "editor_sha256": hashlib.sha256(args.godot.read_bytes()).hexdigest(),
            "fixture_events_imported": False,
        }
        if args.runtime_source or direct_runtime:
            report["cases"].insert(0, "missing runtime runs deterministic host setup and resumes the original request")
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
