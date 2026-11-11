"""Isolated, headless acceptance of the native 3D Tianshu workbench."""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from editor_test_isolation import copy_editor

parser = argparse.ArgumentParser()
parser.add_argument("--godot", type=Path, required=True)
parser.add_argument("--report", type=Path, required=True)
parser.add_argument("--source-only", action="store_true")
args = parser.parse_args()
source = Path(__file__).with_name("tianshu_spatial.gd")
with tempfile.TemporaryDirectory(prefix="tianshu-spatial-") as directory:
    root = Path(directory)
    editor = copy_editor(args.godot.resolve(), root / "editor")
    (root / "project.godot").write_text('[application]\nconfig/name="Tianshu 3D acceptance"\n')
    (root / "test.gd").write_bytes(source.read_bytes())
    env = {k: v for k, v in os.environ.items() if not k.startswith("GONGGONG_")}
    env["XDG_CACHE_HOME"] = str(root / "cache")
    env["TIANSHU_SOURCE_ONLY"] = "1" if args.source_only else ""
    env["TIANSHU_SPATIAL_SOURCE"] = str(source.parents[2] / "editor/docks/daqian/spatial_workbench.gd")
    result = subprocess.run(
        [str(editor), "--headless", "--editor", "--path", str(root), "--script", str(root / "test.gd")],
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
    )
    passed = result.returncode == 0 and "TIANSHU_SPATIAL_OK" in result.stdout and "SCRIPT ERROR:" not in result.stderr
    restart = None
    if passed and not args.source_only:
        restart = subprocess.run(
            [str(editor), "--headless", "--editor", "--path", str(root), "--script", str(root / "test.gd")],
            env={**env, "TIANSHU_RESTART": "1"},
            text=True,
            capture_output=True,
            timeout=120,
        )
        passed = (
            restart.returncode == 0
            and "TIANSHU_SPATIAL_OK restart" in restart.stdout
            and "SCRIPT ERROR:" not in restart.stderr
        )
    report = {
        "passed": passed,
        "source_only": args.source_only,
        "binary_sha256": hashlib.sha256(args.godot.read_bytes()).hexdigest(),
        "test_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "restart": None
        if restart is None
        else {"exit_code": restart.returncode, "stdout": restart.stdout, "stderr": restart.stderr},
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(0 if passed else 1)
