"""Run the native Daqian tab and graph interaction test in an isolated Godot project."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("--godot", type=Path, required=True)
parser.add_argument("--report", type=Path, required=True)
args = parser.parse_args()
binary = args.godot.resolve()
with tempfile.TemporaryDirectory(prefix="daqian-editor-") as directory:
    project = Path(directory)
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Daqian graph tests"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n')
    shutil.copyfile(Path(__file__).with_name("daqian_graph.gd"), project / "test.gd")
    result = subprocess.run([str(binary),"--headless","--editor","--path",str(project),"--script","res://test.gd","--quit-after","900"],
                            capture_output=True, encoding="utf-8", errors="replace",timeout=60)
    log = result.stdout + result.stderr
    passed = result.returncode == 0 and "DAQIAN_GRAPH_TEST passed" in log and "SCRIPT ERROR" not in log
    report = {"state":"passed" if passed else "failed","editor_sha256":hashlib.sha256(binary.read_bytes()).hexdigest(),
              "scope":"native editor; fixture graph source, execution state, model catalog and 55-issue board"}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+"\n")
    if not passed:
        raise SystemExit(log)
    print(report)
