#!/usr/bin/env python3
"""Compile and execute C and C++ extensions in an isolated headless project."""

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
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    executable = args.godot.resolve(strict=True)
    compiler = args.compiler.resolve(strict=True)
    folder = Path(__file__).resolve().parent
    header = folder.parents[1] / "core/extension/gdextension_interface.gen.h"
    with tempfile.TemporaryDirectory(prefix="godot native compile ") as temporary:
        project = Path(temporary)
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Native compile test"\n[physics]\n2d/physics_engine="Dummy"\n'
        )
        (project / ".godot").mkdir()
        (project / ".godot/global_script_class_cache.cfg").write_text("list=[]\n")
        shutil.copyfile(folder / "native_compile.gd", project / "native_compile.gd")
        source = project / "native fixture.c"
        shutil.copyfile(folder / "native_fixture.c", source)
        include = project / "native includes"
        include.mkdir()
        shutil.copyfile(header, include / header.name)
        env = dict(
            os.environ,
            HOME=str(project),
            XDG_DATA_HOME=str(project / "data"),
            XDG_CONFIG_HOME=str(project / "config"),
            RUNTIME_NATIVE_COMPILER=str(compiler),
            RUNTIME_NATIVE_SOURCE=str(source),
            RUNTIME_NATIVE_INCLUDE=str(include),
        )
        run = subprocess.run(
            [
                str(executable),
                "--headless",
                "--quit-after",
                "2",
                "--path",
                str(project),
                "--script",
                "native_compile.gd",
            ],
            env=env,
            text=True,
            capture_output=True,
            timeout=120,
        )
        report = {
            "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
            "header_sha256": hashlib.sha256(header.read_bytes()).hexdigest(),
            "fixture_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "compiler": subprocess.run([str(compiler), "--version"], capture_output=True, text=True, timeout=15).stdout,
            "exit_code": run.returncode,
            "stdout": run.stdout,
            "stderr": run.stderr,
            "passed": run.returncode == 0 and "RUNTIME_NATIVE_COMPILE_OK" in run.stdout and "ERROR:" not in run.stderr,
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
