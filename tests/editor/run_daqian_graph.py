"""Run the native Daqian tab and graph interaction test in an isolated Godot project."""
import argparse
import hashlib
import json
import os
import sys
import shlex
from pathlib import Path
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("--godot", type=Path, required=True)
parser.add_argument("--report", type=Path, required=True)
parser.add_argument("--scenario", choices=["graph","parallel","entry","inputs","multi_issue","publish","direct"],default="graph")
args = parser.parse_args()
scenarios = {"direct":("daqian_direct.gd","DAQIAN_DIRECT_OK"),
             "graph":("daqian_graph.gd","DAQIAN_GRAPH_TEST passed"),
             "publish":("daqian_publish.gd","DAQIAN_PUBLISH_OK"),
             "parallel":("daqian_editor_parallel.gd","DAQIAN_NATIVE_PARALLEL_OK"),
             "entry":("daqian_ai_entry.gd","DAQIAN_AI_ENTRY_OK"),
             "inputs":("daqian_inputs.gd","DAQIAN_NATIVE_INPUTS_OK"),
             "multi_issue":("daqian_multi_issue.gd","DAQIAN_MULTI_ISSUE_OK")}
script, marker = scenarios[args.scenario]
env = os.environ.copy()
if args.scenario in {"parallel","inputs","multi_issue"}:
    node = env.get("DAQIAN_TEST_NODE") or shutil.which("node")
    if not node:
        raise SystemExit("Node required for Daqian native parallel acceptance")
    env.update(DAQIAN_TEST_REPO=str(Path(__file__).resolve().parents[2]),DAQIAN_TEST_NODE=node,DAQIAN_TEST_PYTHON=sys.executable)
binary = args.godot.resolve()
with tempfile.TemporaryDirectory(prefix="daqian-editor-", ignore_cleanup_errors=os.name == "nt") as directory:
    project = Path(directory)
    if args.scenario in {"graph","parallel","inputs","multi_issue"}:
        # The repository gate is exercised using the ordinary gh transport; no product bypass.
        fixture=project/"fixture_gh.py"
        fixture.write_text("""import json,sys,os
from pathlib import Path
mode_path=Path(os.environ["DAQIAN_TEST_ACCESS_FILE"])
mode=mode_path.read_text() if mode_path.is_file() else "member"
uid=84 if mode=="switch" else 42
login="next" if mode=="switch" else "fixture"
a=sys.argv[1:]
if a[:2]==["api","user"]: print(str(uid) if "--jq" in a else json.dumps({"id":uid,"login":login}))
elif a[0]=="api" and a[1].startswith("user/repos?"): print("" if mode=="denied" else "123")
elif a[0]=="api" and "issues?" in a[1]: print("[[]]")
elif a[:3]==["config","get","user"]: print("fixture")
else: sys.exit(1)
""",encoding="utf-8")
        if os.name == "nt":
            # A native console-script launcher keeps REST query '&' and jq pipes out of cmd.exe.
            from pip._vendor.distlib.scripts import ScriptMaker
            source_dir=project/"fixture-source"
            source_dir.mkdir()
            (source_dir/"fixture-gh").write_text("#!python\n"+fixture.read_text(encoding="utf-8"),encoding="utf-8")
            maker=ScriptMaker(str(source_dir),str(project))
            maker.executable=sys.executable
            maker.make("fixture-gh")
            wrapper=project/"fixture-gh.exe"
        else:
            wrapper=project/"fixture-gh"
            wrapper.write_text('#!/bin/sh\nexec '+shlex.quote(sys.executable)+' '+shlex.quote(str(fixture))+' "$@"\n')
            wrapper.chmod(0o755)
        env.update(DAQIAN_TEST_ACCESS_FILE=str(project/"membership-fixture"),GONGGONG_GH=str(wrapper),DAQIAN_TEST_REPO=str(Path(__file__).resolve().parents[2]),DAQIAN_TEST_PYTHON=sys.executable)
    if args.scenario in {"publish", "direct"}:
        # Exercise the actual UI, chat session and subprocess boundary without creating a real Issue.
        workspace = project / ".fixture"
        labels = workspace / ".github/labels.json"
        labels.parent.mkdir(parents=True)
        shutil.copyfile(Path(__file__).resolve().parents[2] / ".github/labels.json", labels)
        board = workspace / "customizations/components/godot-host/daqian/board.py"
        board.parent.mkdir(parents=True)
        board.write_text("""import json, sys
from pathlib import Path
actor = dict(login='tester', user_id='42', repo='fixture/board', repo_id='1')
result = {'access': actor} if '--access-only' in sys.argv else {'board': dict(actor, issues=[], verified_at='fixture')}
Path(sys.argv[sys.argv.index('--result')+1]).write_text(json.dumps(result))
""", encoding="utf-8")
        bridge = workspace / "tools/gonggong_bridge.py"
        bridge.parent.mkdir(parents=True)
        bridge.write_text("""import json, sys
from pathlib import Path
assert sys.argv[1] == 'issue-agent'
request = json.loads(Path(sys.argv[sys.argv.index('--request')+1]).read_text())
with Path(__file__).with_name('calls').open('a') as out:
    print(json.dumps([request['outcome'], request['backend'], request['model']]), file=out)
reply = dict(ok=True, ready=True, issue_number=123, request_id='fixture', url='https://github.com/fixture/board/issues/123',
             scope=['Implement'], acceptance=['Verify'], questions=[])
if not request['retry_authorized']:
    reply = dict(ok=False, error='fixture model unavailable')
Path(sys.argv[sys.argv.index('--out')+1]).write_text(json.dumps(reply))
""", encoding="utf-8")
        if args.scenario == "direct":
            bridge.write_text("""import json, sys
from pathlib import Path
action = sys.argv[1]
request = json.loads(Path(sys.argv[sys.argv.index('--request')+1]).read_text())
calls = Path(__file__).with_name('calls')
first = not calls.exists()
with calls.open('a') as out:
    print(json.dumps([action, request]), file=out)
if action == 'issue-direct':
    reply = dict(ok=True, number=124, url='https://github.com/fixture/board/issues/124',
                 status='planned', revision='fixture-revision', request_id='daqian-direct-'+request['draft_id'][6:])
    if first:
        reply = dict(ok=False, reconcile_required=True, error='先核对发布结果')
elif action == 'issue-start':
    reply = dict(ok=True, status='status:in-progress')
else:
    assert action == 'chat'
    reply = dict(ok=False, error='fixture stops at the execution admission boundary')
Path(sys.argv[sys.argv.index('--out')+1]).write_text(json.dumps(reply))
""", encoding="utf-8")
        env.update(DAQIAN_TEST_REPO=str(workspace), DAQIAN_TEST_PYTHON=sys.executable)
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Daqian graph tests"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n')
    shutil.copyfile(Path(__file__).with_name(script), project / "test.gd")
    result = subprocess.run([str(binary),"--headless","--editor","--path",str(project),"--script","res://test.gd"],
                            env=env,capture_output=True, encoding="utf-8", errors="replace",timeout=120)
    log = result.stdout + result.stderr
    passed = result.returncode == 0 and marker in log and "SCRIPT ERROR" not in log
    report = {"state":"passed" if passed else "failed","editor_sha256":hashlib.sha256(binary.read_bytes()).hexdigest(),
              "scenario":args.scenario,"scope":"native editor to Yanshi subprocess with fixture receipt" if args.scenario == "publish" else "native editor to direct issue and Sinan admission subprocesses" if args.scenario == "direct" else "native editor; fixture graph source, execution state, model catalog and 55-issue board"}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+"\n")
    if not passed:
        raise SystemExit(log)
    print(report)

# The existing native parallel acceptance also covers user input waking a single
# branch. Keep both subprocess results so the CI artifact identifies each run.
if args.scenario == "parallel":
    for related in ("inputs","multi_issue"):
        extra_report=args.report.with_name(args.report.stem+"-"+related+".json")
        subprocess.run([sys.executable,str(Path(__file__).resolve()),"--scenario",related,
                        "--godot",str(binary),"--report",str(extra_report)],check=True,env=env)
