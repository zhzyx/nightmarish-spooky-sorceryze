"""Native Yanshi intake acceptance with isolated GitHub/model fixtures; no real services."""

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
from pathlib import Path

from editor_test_isolation import copy_editor

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--runtime-source", type=Path)
    args = parser.parse_args()
    requests = []
    normal = 0
    with tempfile.TemporaryDirectory(prefix="requirements-native-") as folder:
        root = Path(folder)
        shutil.copytree(ROOT / "framework", root / "framework", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(ROOT / "CURRENT_FRAMEWORK.json", root / "CURRENT_FRAMEWORK.json")
        shutil.copytree(ROOT / "customizations", root / "customizations", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / ".github", root / ".github")
        (root / "tools").mkdir()
        for relative in ("tools/check_gonggong_distribution.py", "integrations/gonggong/frozen-distribution.json"):
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, root / relative)
        shutil.copyfile(ROOT / "tools/gonggong_bridge.py", root / "tools/gonggong_bridge.py")
        shutil.copyfile(ROOT / "tools/configure_gonggong_runtime.ps1", root / "tools/configure_gonggong_runtime.ps1")
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
        project = root / "project"
        project.mkdir()
        # The editor changes cwd to the opened project before invoking Python.
        for name in ["auth", "api", "issue"]:
            (project / name).write_text(GH_FIXTURE, encoding="utf-8")
        (project / "project.godot").write_text(
            '[application]\nconfig/name="Requirements intake fixture"\n', encoding="utf-8"
        )
        shutil.copyfile(ROOT / "tests/editor/requirements_intake.gd", project / "gate.gd")

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                nonlocal normal
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requirements = "Requirements intake only" in data["messages"][0]["content"]
                requests.append({"requirements": requirements})
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
                        if existing
                        and (
                            "Refine" in text
                            or ("Clarify pending" in text and "用户补充" in text)
                            or ("second feature" in text and existing["number"] == 8002)
                        )
                        else "new"
                    )
                    requests[-1].update(
                        outcome=text, existing_issue=existing["number"] if existing else None, decision=decision
                    )
                    body = json.dumps({
                        "decision": decision,
                        "title": text.splitlines()[0],
                        "category": "development",
                        "goal": text,
                        "scope": ["One requested change"],
                        "acceptance": ["Observable requested result"],
                        "questions": ["INTAKE_CLARIFICATION_REQUIRED"]
                        if "Clarify pending" in text and "用户补充" not in text
                        else [],
                    })
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
                result = json.dumps({
                    "choices": [{"message": {"role": "assistant", "content": body}, "finish_reason": "stop"}]
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
            GONGGONG_PYTHON=sys.executable,
            GONGGONG_GH=sys.executable,
            GONGGONG_TEST_ENDPOINT=f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
            GONGGONG_FRAMEWORK_SOURCE=str(root / "absent-upstream"),
        )
        if args.runtime_source:
            env["GONGGONG_TEST_RUNTIME_SOURCE"] = str(args.runtime_source.resolve())
        for name in ["OPENAI_API_KEY", "GODOT_AI_API_KEY"]:
            env.pop(name, None)
        for name in ["APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME"]:
            env[name] = str(root / name)
            (root / name).mkdir()
        try:
            result = subprocess.run(
                [
                    str(isolated_editor),
                    "--headless",
                    "--editor",
                    "--path",
                    str(project),
                    "--script",
                    "res://gate.gd",
                ],
                cwd=root,
                env=env,
                capture_output=True,
                timeout=240,
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
            "runtime_setup_and_resume": bool(args.runtime_source),
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
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
