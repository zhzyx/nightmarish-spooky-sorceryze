#!/usr/bin/env python3
"""Exercise runtime compilation in a private, headless project."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    executable = args.godot.resolve(strict=True)
    script = Path(__file__).with_name("gdscript_compile.gd")
    with tempfile.TemporaryDirectory(prefix="godot-runtime-compile-") as folder:
        project = Path(folder)
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Runtime compile test"\n'
            '[physics]\n2d/physics_engine="Dummy"\n'
        )
        (project / ".godot").mkdir()
        (project / ".godot/global_script_class_cache.cfg").write_text("list=[]\n")
        shutil.copyfile(script, project / script.name)
        env = dict(
            os.environ, HOME=str(project), XDG_DATA_HOME=str(project / "data"), XDG_CONFIG_HOME=str(project / "config")
        )
        run = subprocess.run(
            [str(executable), "--headless", "--path", str(project), "--script", script.name],
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
        )
        report = {
            "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
            "test_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
            "exit_code": run.returncode,
            "stdout": run.stdout,
            "stderr": run.stderr,
            "passed": run.returncode == 0
            and "RUNTIME_GDSCRIPT_COMPILE_OK" in run.stdout
            and "ERROR:" not in run.stderr,
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
