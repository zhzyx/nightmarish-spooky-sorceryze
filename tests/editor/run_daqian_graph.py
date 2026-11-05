"""Run the native Daqian tab and graph interaction test in an isolated Godot project."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("--godot", type=Path, required=True)
parser.add_argument("--report", type=Path, required=True)
parser.add_argument("--scenario", choices=["graph","parallel","entry"],default="graph")
args = parser.parse_args()
scenarios = {"graph":("daqian_graph.gd","DAQIAN_GRAPH_TEST passed"),
             "parallel":("daqian_editor_parallel.gd","DAQIAN_NATIVE_PARALLEL_OK"),
             "entry":("daqian_ai_entry.gd","DAQIAN_AI_ENTRY_OK")}
script, marker = scenarios[args.scenario]
env = os.environ.copy()
if args.scenario == "parallel":
    node = env.get("DAQIAN_TEST_NODE") or shutil.which("node")
    if not node:
        raise SystemExit("Node required for Daqian native parallel acceptance")
    env.update(DAQIAN_TEST_REPO=str(Path(__file__).resolve().parents[2]),DAQIAN_TEST_NODE=node,DAQIAN_TEST_PYTHON=sys.executable)
binary = args.godot.resolve()
with tempfile.TemporaryDirectory(prefix="daqian-editor-", ignore_cleanup_errors=os.name == "nt") as directory:
    project = Path(directory)
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Daqian graph tests"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n')
    shutil.copyfile(Path(__file__).with_name(script), project / "test.gd")
    result = subprocess.run([str(binary),"--headless","--editor","--path",str(project),"--script","res://test.gd"],
                            env=env,capture_output=True, encoding="utf-8", errors="replace",timeout=120)
    log = result.stdout + result.stderr
    passed = result.returncode == 0 and marker in log and "SCRIPT ERROR" not in log
    report = {"state":"passed" if passed else "failed","editor_sha256":hashlib.sha256(binary.read_bytes()).hexdigest(),
              "scenario":args.scenario,"scope":"native editor; fixture graph source, execution state, model catalog and 55-issue board"}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+"\n")
    if not passed:
        raise SystemExit(log)
    print(report)
