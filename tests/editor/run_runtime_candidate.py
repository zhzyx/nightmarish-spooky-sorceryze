"""Offline native editor acceptance for Issue-bound source candidates and command writes."""

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUEST = "runtime-candidate-fixture"
OTHER_REQUEST = "runtime-candidate-other"
STAGES = [
    "CANDIDATE_BOUNDARY_OK",
    "CANDIDATE_CANCEL_OK",
    "CANDIDATE_SECOND_OK",
    "CANDIDATE_OTHER_OK",
    "CANDIDATE_RESUMED_OK",
    "CANDIDATE_CHILD_OK",
]
BRIDGE = r"""
import importlib.util,json,os,sys
from pathlib import Path
storage_path=Path(os.environ['CANDIDATE_FIXTURE_SOURCE'])/'customizations/platforms/data-collection/git-files/storage/diting_files.py'
spec=importlib.util.spec_from_file_location('fixture_storage',storage_path); storage=importlib.util.module_from_spec(spec); spec.loader.exec_module(storage)
args=sys.argv[1:]; action=args[0]; root=Path(args[args.index('--workspace')+1]); out=Path(args[args.index('--out')+1])
request=json.loads(Path(args[args.index('--request')+1]).read_text()) if '--request' in args else {}
(root/'node-used.txt').write_text(os.environ.get('GONGGONG_NODE',''))
outcome=request.get('outcome','')
other='CANDIDATE_OTHER' in outcome or request.get('request_id')=='runtime-candidate-other'
number=391 if other else 390
request_id='runtime-candidate-other' if other else 'runtime-candidate-fixture'
reporting={'tenant_id':'fixture','request_ref':request_id,'source_ref':'https://github.com/example/test/issues/'+str(number),'agent':{'id':'yanshi','version':'1','definition_sha256':'0'*64,'origin':'offline-fixture'}}
if action=='issue-agent':
 (root/'design-docs').mkdir(exist_ok=True)
 revision='OTHER' if other else 'RESUME' if 'CANDIDATE_RESUME' in outcome else 'SECOND' if 'CANDIDATE_SECOND' in outcome else 'START'
 document='# Fixture requirement\nREVISION_'+revision+'\n'
 previous=root/'design-docs'/ (request_id+'.md')
 if previous.exists() and 'DESIGN_EDIT_ALLOWED' in previous.read_text(): document+='DESIGN_EDIT_ALLOWED\n'
 if revision=='RESUME':
  document+='SECOND_TURN_PRESERVED\n## 设计定版确认\nFixture finalized.\n## 生产工单\n1. CANDIDATE_CHILD validates latest requirement\n'
 (root/'design-docs'/ (request_id+'.md')).write_text(document)
 value={'ok':True,'ready':True,'issue_number':number,'request_id':request_id,'url':reporting['source_ref']}
elif action=='chat': value={'ok':True,'context':'Offline fixture context; no production framework admission claimed.','reporting':reporting}
elif action=='flush':
 for path in (root/'.gonggong-outbox/chat').glob('*.json'):
  storage.record(root,path); path.unlink()
 value={'ok':True}
else: value={'ok':False,'error':'fixture_unknown'}
out.write_text(json.dumps(value))
"""


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.STDOUT).decode().strip()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--godot", type=Path, required=True)
    p.add_argument("--node", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    with tempfile.TemporaryDirectory(prefix="native-candidate-共工 space-") as temp:
        folder = Path(temp).resolve()
        original = folder / "original"
        original.mkdir()
        remote = folder / "remote.git"
        git(folder, "init", "--bare", str(remote))
        git(original, "init", "-b", "main")
        git(original, "config", "user.name", "Fixture")
        git(original, "config", "user.email", "fixture@example.invalid")
        git(original, "remote", "add", "origin", "https://github.com/example/test.git")
        git(original, "config", "url." + str(remote) + ".insteadOf", "https://github.com/example/test.git")
        (original / "work-items.json").write_text(
            json.dumps({"repository": "example/test", "tenant_id": "fixture", "category_labels": ".github/labels.json"})
        )
        (original / ".github").mkdir()
        (original / ".github/labels.json").write_text('[{"name":"type:bug"}]')
        (original / "SConstruct").write_text("# fixture engine\n")
        (original / "tools").mkdir()
        (original / "tools/gonggong_bridge.py").write_text(BRIDGE)
        (original / "tools/editor_self_build.py").write_text("# fixture build entry\n")
        (original / "editor").mkdir()
        protected = original / "editor/source.cpp"
        protected.write_text("ORIGINAL_SOURCE\n")
        dataset = original / "gonggong-diting-data"
        dataset.mkdir()
        (dataset / "dataset.json").write_text(
            json.dumps({
                "schema_version": 1,
                "dataset_id": "00000000-0000-4000-8000-000000000423",
                "name": "gonggong-diting-data",
                "origin_framework": "gonggong",
            })
        )
        (dataset / ".gitattributes").write_text("* text eol=lf\n")
        git(original, "add", ".")
        git(original, "commit", "-m", "fixture")
        git(original, "push", "origin", "main")
        git(original, "checkout", "-b", "existing-owner")
        project = original / "samples/project"
        project.mkdir(parents=True)
        (project / "project.godot").write_text(
            'config_version=5\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
        )
        shutil.copyfile(Path(__file__).with_name("runtime_candidate.gd"), project / "gate.gd")
        gh = folder / "fake-gh"
        issues = {}
        for number, request_id in [(390, REQUEST), (391, OTHER_REQUEST)]:
            issues[str(number)] = {
                "number": number,
                "html_url": "https://github.com/example/test/issues/" + str(number),
                "state": "open",
                "updated_at": "2026-11-07T00:00:00Z",
                "body": "<!-- gonggong-request:" + request_id + " -->",
                "labels": [{"name": name} for name in ["type:bug", "status:in-progress", "workspace:gonggong"]],
            }
        gh.write_text(
            "#!"
            + sys.executable
            + "\nimport json,sys\nissues="
            + repr(issues)
            + '\nprint(json.dumps(issues[sys.argv[-1].rsplit("/",1)[-1]]))\n'
        )
        gh.chmod(0o700)
        git_wrapper = folder / "git"
        git_wrapper.write_text(
            "#!"
            + sys.executable
            + '\nimport os,sys\na=sys.argv[1:]\nif a[-3:]==["remote","get-url","origin"]: print("https://github.com/example/test.git")\nelse: os.execv("/usr/bin/git",["git",*a])\n'
        )
        git_wrapper.chmod(0o700)
        isolated = folder / "isolated-editor"
        isolated.mkdir()
        binary = isolated / args.godot.name
        if subprocess.run(["cp", "-c", str(args.godot.resolve()), str(binary)]).returncode:
            shutil.copy2(args.godot, binary)
        (isolated / "_sc_").touch()
        artifact_sha256 = hashlib.sha256(binary.read_bytes()).hexdigest()
        errors, calls, completed = [], [], []
        targets, owners, stage_calls = {}, {}, {}

        def bindings_for(number):
            return [
                value
                for path in (original / ".git/gonggong-engine-candidates").glob("*.json")
                if (value := json.loads(path.read_text())).get("issue") == number
            ]

        def parent_binding(number):
            matches = bindings_for(number)
            if number in owners:
                matches = [value for value in matches if value["owner"] == owners[number]]
            assert len(matches) == 1, ("unexpected candidate ownership", number, matches)
            value = matches[0]
            owners.setdefault(number, value["owner"])
            targets.setdefault(number, Path(value["source_root"]))
            assert Path(value["source_root"]) == targets[number]
            return value

        def done(marker):
            completed.append(marker)
            return {"role": "assistant", "content": marker}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                try:
                    body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                    calls.append(body)
                    prompt = next(item["content"] for item in reversed(body["messages"]) if item["role"] == "user")
                    stage = next(
                        (
                            name
                            for name in ["CHILD", "RESUME", "OTHER", "SECOND", "CANCEL", "START"]
                            if "CANDIDATE_" + name in prompt
                        ),
                        None,
                    )
                    assert stage is not None, ("unexpected prompt", prompt)
                    stage_calls[stage] = stage_calls.get(stage, 0) + 1
                    if stage == "START" and stage_calls[stage] == 1:
                        parent_binding(390)
                        target = targets[390]
                        assert str(target) in json.dumps(body, ensure_ascii=False), (
                            "candidate root absent from model context"
                        )
                        assert "REVISION_START" in (target / f"design-docs/{REQUEST}.md").read_text()
                        assert (target / f"gonggong-diting-data/events/fixture/{REQUEST}").is_dir()
                        commands = [
                            ("run_command", {"command": "pwd"}),
                            ("read_file", {"path": str(protected)}),
                            ("write_file", {"path": str(protected), "content": "BAD_WRITE"}),
                            ("run_command", {"command": "pwd", "cwd": str(original)}),
                            ("run_command", {"command": "printf BAD_ABSOLUTE > " + shlex.quote(str(protected))}),
                            (
                                "run_command",
                                {"command": "printf PROJECT_OK > " + shlex.quote(str(project / "allowed.txt"))},
                            ),
                            (
                                "run_command",
                                {"command": "git stash push --include-untracked -m isolated-active-provenance"},
                            ),
                        ]
                        message = {
                            "role": "assistant",
                            "content": "Validating candidate boundaries",
                            "tool_calls": [
                                {
                                    "id": "boundary-" + str(i),
                                    "type": "function",
                                    "function": {"name": name, "arguments": json.dumps(value)},
                                }
                                for i, (name, value) in enumerate(commands)
                            ],
                        }
                    elif stage == "START" and stage_calls[stage] == 2:
                        tools = {x["tool_call_id"]: x["content"] for x in body["messages"] if x["role"] == "tool"}
                        assert len(tools) >= 7, tools
                        assert str(targets[390]) in tools["boundary-0"]
                        assert "ORIGINAL_SOURCE" in tools["boundary-1"]
                        assert "workspace_mismatch" in tools["boundary-2"]
                        assert "workspace_mismatch" in tools["boundary-3"]
                        assert json.loads(tools["boundary-4"])["exit_code"] != 0, tools["boundary-4"]
                        assert json.loads(tools["boundary-5"])["exit_code"] == 0
                        assert json.loads(tools["boundary-6"])["exit_code"] != 0
                        event = next((targets[390] / f"gonggong-diting-data/events/fixture/{REQUEST}").glob("*.json"))
                        alias = targets[390] / "evidence-alias.json"
                        alias.symlink_to(event)
                        source_alias = targets[390] / "other-source-alias.cpp"
                        source_alias.symlink_to(protected)
                        commands = [
                            {"command": "printf CANDIDATE_FILE > candidate.txt"},
                            {
                                "command": "printf '\\nDESIGN_EDIT_ALLOWED\\n' >> design-docs/"
                                + REQUEST
                                + ".md && tail -n 1 design-docs/"
                                + REQUEST
                                + ".md"
                            },
                            {
                                "command": "printf SOURCE_PATCH > editor/source.cpp && git stash push -- editor/source.cpp && git stash apply"
                            },
                        ]
                        message = {
                            "role": "assistant",
                            "content": "Checking normal source integration and design edits",
                            "tool_calls": [
                                {
                                    "id": "boundary-" + str(i + 7),
                                    "type": "function",
                                    "function": {"name": "run_command", "arguments": json.dumps(value)},
                                }
                                for i, value in enumerate(commands)
                            ]
                            + [
                                {
                                    "id": "evidence-alias",
                                    "type": "function",
                                    "function": {
                                        "name": "write_file",
                                        "arguments": json.dumps({"path": str(alias), "content": "BAD_EVIDENCE"}),
                                    },
                                },
                                {
                                    "id": "evidence-case",
                                    "type": "function",
                                    "function": {
                                        "name": "write_file",
                                        "arguments": json.dumps({
                                            "path": str(event).replace("gonggong-diting-data", "GONGGONG-DITING-DATA")
                                            if sys.platform == "darwin"
                                            else str(event),
                                            "content": "BAD_EVIDENCE",
                                        }),
                                    },
                                },
                                {
                                    "id": "source-alias",
                                    "type": "function",
                                    "function": {
                                        "name": "write_file",
                                        "arguments": json.dumps({"path": str(source_alias), "content": "BAD_SOURCE"}),
                                    },
                                },
                            ],
                        }
                    elif stage == "START":
                        assert stage_calls[stage] == 3, "boundary tools were unexpectedly retried"
                        tools = {x["tool_call_id"]: x["content"] for x in body["messages"] if x["role"] == "tool"}
                        assert len(tools) >= 10, tools
                        assert "active_provenance_is_host_owned" in tools["evidence-alias"]
                        assert "active_provenance_is_host_owned" in tools["evidence-case"]
                        assert "workspace_mismatch" in tools["source-alias"]
                        for index in [7, 8, 9]:
                            assert json.loads(tools["boundary-" + str(index)])["exit_code"] == 0, tools[
                                "boundary-" + str(index)
                            ]
                        assert "DESIGN_EDIT_ALLOWED" in json.loads(tools["boundary-8"])["stdout"]
                        assert (targets[390] / "editor/source.cpp").read_text() == "SOURCE_PATCH"
                        assert protected.read_text() == "ORIGINAL_SOURCE\n"
                        assert (project / "allowed.txt").read_text() == "PROJECT_OK"
                        assert (targets[390] / "candidate.txt").read_text() == "CANDIDATE_FILE"
                        message = done("CANDIDATE_BOUNDARY_OK")
                    elif stage == "CANCEL":
                        assert stage_calls[stage] == 1, "cancelled command was unexpectedly resumed"
                        code = (
                            "import os,time; from pathlib import Path; Path("
                            + repr(str(project / "cancel-ready"))
                            + ").write_text(str(os.getpid())); time.sleep(30)"
                        )
                        message = {
                            "role": "assistant",
                            "content": "Checking host cancellation",
                            "tool_calls": [
                                {
                                    "id": "cancel-running-command",
                                    "type": "function",
                                    "function": {
                                        "name": "run_command",
                                        "arguments": json.dumps({
                                            "command": shlex.quote(sys.executable) + " -c " + shlex.quote(code)
                                        }),
                                    },
                                }
                            ],
                        }
                    elif stage == "SECOND":
                        parent_binding(390)
                        assert len(bindings_for(390)) == 1, "second turn created another source candidate"
                        assert str(targets[390]) in json.dumps(body, ensure_ascii=False)
                        assert "REVISION_SECOND" in (targets[390] / f"design-docs/{REQUEST}.md").read_text()
                        assert "REVISION_START" in (original / f"design-docs/{REQUEST}.md").read_text(), (
                            "second intake wrote the original workspace"
                        )
                        message = done("CANDIDATE_SECOND_OK")
                    elif stage == "OTHER":
                        parent_binding(391)
                        assert targets[391] != targets[390] and owners[391] != owners[390]
                        assert str(targets[391]) in json.dumps(body, ensure_ascii=False)
                        assert "REVISION_OTHER" in (targets[391] / f"design-docs/{OTHER_REQUEST}.md").read_text()
                        message = done("CANDIDATE_OTHER_OK")
                    elif stage == "RESUME":
                        parent_binding(390)
                        assert len(bindings_for(390)) == 1, "returning to first parent replaced its source ownership"
                        assert str(targets[390]) in json.dumps(body, ensure_ascii=False)
                        assert "REVISION_RESUME" in (targets[390] / f"design-docs/{REQUEST}.md").read_text()
                        assert "REVISION_START" in (original / f"design-docs/{REQUEST}.md").read_text()
                        assert "REVISION_OTHER" in (targets[391] / f"design-docs/{OTHER_REQUEST}.md").read_text()
                        if stage_calls[stage] == 1:
                            message = {
                                "role": "assistant",
                                "content": "Checking newly registered source protection",
                                "tool_calls": [
                                    {
                                        "id": "new-worktree-write",
                                        "type": "function",
                                        "function": {
                                            "name": "run_command",
                                            "arguments": json.dumps({
                                                "command": "printf BAD_NEW_WORKTREE > "
                                                + shlex.quote(str(targets[391] / "editor/source.cpp"))
                                            }),
                                        },
                                    }
                                ],
                            }
                        else:
                            tools = {x["tool_call_id"]: x["content"] for x in body["messages"] if x["role"] == "tool"}
                            assert json.loads(tools["new-worktree-write"])["exit_code"] != 0
                            assert (targets[391] / "editor/source.cpp").read_text() == "ORIGINAL_SOURCE\n"
                            message = done("CANDIDATE_RESUMED_OK")
                    else:
                        children = [value for value in bindings_for(390) if value["owner"] != owners[390]]
                        assert len(children) == 1, ("child did not receive independent source ownership", children)
                        child_root = Path(children[0]["source_root"])
                        assert child_root not in targets.values()
                        assert str(child_root) in json.dumps(body, ensure_ascii=False)
                        assert (child_root / f"design-docs/{REQUEST}.md").read_bytes() == (
                            targets[390] / f"design-docs/{REQUEST}.md"
                        ).read_bytes(), "child inherited stale requirement document"
                        assert not (child_root / "candidate.txt").exists(), (
                            "child adopted uncommitted parent source files"
                        )
                        assert (targets[390] / "candidate.txt").read_text() == "CANDIDATE_FILE"
                        message = done("CANDIDATE_CHILD_OK")
                    data = json.dumps({"choices": [{"message": message}]}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except Exception as error:
                    errors.append(repr(error))
                    traceback.print_exc()
                    print("FIXTURE_ERROR", repr(error), flush=True)
                    self.send_error(500)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        env = dict(
            os.environ,
            CANDIDATE_FIXTURE_ROOT=str(original),
            CANDIDATE_FIXTURE_PYTHON=sys.executable,
            CANDIDATE_FIXTURE_SOURCE=str(ROOT),
            CANDIDATE_FIXTURE_NODE=str(args.node.resolve()),
            CANDIDATE_FIXTURE_ENDPOINT="http://127.0.0.1:" + str(server.server_port) + "/v1/chat/completions",
            GONGGONG_GH=str(gh),
            GONGGONG_GIT=str(git_wrapper),
            PATH=str(folder) + os.pathsep + os.environ.get("PATH", ""),
        )
        env.pop("GONGGONG_NODE", None)
        result = subprocess.run(
            [str(binary), "--headless", "--editor", "--path", str(project), "--script", "res://gate.gd"],
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        server.shutdown()
        report = (
            json.loads((project / "runtime-report.json").read_text())
            if (project / "runtime-report.json").exists()
            else {}
        )
        node = (original / "node-used.txt").read_text() if (original / "node-used.txt").exists() else ""
        cancelled_command_exited = False
        if (project / "cancel-ready").exists():
            try:
                os.kill(int((project / "cancel-ready").read_text()), 0)
            except ProcessLookupError:
                cancelled_command_exited = True
        outcome = {
            "ok": result.returncode == 0
            and report.get("ok")
            and not errors
            and node == str(args.node.resolve())
            and completed == [stage for stage in STAGES if stage != "CANDIDATE_CANCEL_OK"]
            and report.get("stages") == STAGES,
            "cancelled_command_exited": cancelled_command_exited,
            "artifact_sha256": artifact_sha256,
            "errors": errors,
            "requests": len(calls),
            "stages": completed,
            "stage_requests": stage_calls,
            "node_reused": node == str(args.node.resolve()),
            "editor": report,
            "stdout": result.stdout[-8000:],
            "stderr": result.stderr[-8000:],
        }
        outcome["ok"] = outcome["ok"] and cancelled_command_exited
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(outcome, ensure_ascii=False, indent=2))
        print(json.dumps({k: v for k, v in outcome.items() if k not in ["editor", "stdout", "stderr"]}))
        return 0 if outcome["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
