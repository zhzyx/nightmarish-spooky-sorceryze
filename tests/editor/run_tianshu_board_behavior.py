"""Exercise packaged Python behavior through the candidate editor's real helper selection.

The board body is an explicit offline fixture; the native loader, workspace helper
selection and editor_board_entry bootstrap are real. No online Issue/model is called.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from editor_test_isolation import copy_editor
from package_tianshu_board import SOURCE, installed_package, pack

ROOT = Path(__file__).resolve().parents[2]
LEGACY = "26cda2ab35b3ec2f12daa8b3205518d8f7e55c7d"
PROBE = """@tool
extends SceneTree
func _initialize():
    run.call_deferred()
func run():
    for i in 8:
        await process_frame
    var workspace = root.find_child("DaqianWorkspace", true, false)
    if not workspace:
        quit(2)
        return
    var helper := OS.get_environment("BOARD_HELPER")
    var missing := helper + ".missing"
    if workspace._board_entry_args(missing) != PackedStringArray([missing]):
        quit(3)
        return
    var args: PackedStringArray = workspace._board_entry_args(helper)
    if args.size() != 5:
        quit(4)
        return
    var cache: String = args[2]
    DirAccess.remove_absolute(cache)
    var blocked := cache + "." + str(workspace.editor_session) + ".tmp"
    if DirAccess.make_dir_absolute(blocked) != OK:
        quit(5)
        return
    var fallback: PackedStringArray = workspace._board_entry_args(helper)
    DirAccess.remove_absolute(blocked)
    if fallback != PackedStringArray([helper]):
        quit(6)
        return
    args = workspace._board_entry_args(helper)
    if args.size() != 5 or FileAccess.get_sha256(args[2]) != workspace.board_bundle_sha256:
        quit(7)
        return
    var file := FileAccess.open(OS.get_environment("BOARD_ARGS"), FileAccess.WRITE)
    file.store_string(JSON.stringify({"args": args, "missing_fallback": true, "cache_failure_fallback": true}))
    file.close()
    print("BOARD_BEHAVIOR_READY")
    quit()
"""

FIXTURE = """import argparse, json, time
from pathlib import Path
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--result', required=True, type=Path)
    parser.add_argument('--started', type=Path)
    parser.add_argument('--delay', type=float, default=0)
    args = parser.parse_args()
    if args.started:
        args.started.write_text('started')
    time.sleep(args.delay)
    args.result.write_text(json.dumps({'fixture_version': VERSION}), encoding='utf-8')
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "cases": {},
        "scope": "offline fixture CLI/result via real native loader and bootstrap; no online business acceptance",
    }
    with tempfile.TemporaryDirectory(prefix="board-behavior-") as directory:
        root = Path(directory)
        binary = copy_editor(args.godot, root / "editor")
        before = hashlib.sha256(binary.read_bytes()).hexdigest()
        project = root / "project"
        project.mkdir()
        (project / "project.godot").write_text(
            'config_version=5\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
        )
        (project / "probe.gd").write_text(PROBE, encoding="utf-8")
        workspace = root / "workspace"
        helper = workspace / "customizations/components/godot-host/daqian/board.py"
        helper.parent.mkdir(parents=True)
        helper.write_bytes(
            subprocess.check_output(
                ["git", "show", LEGACY + ":customizations/components/godot-host/daqian/board.py"], cwd=ROOT
            )
        )
        source = root / "source"
        source.mkdir()
        shutil.copyfile(SOURCE / "editor_board_entry.py", source / "editor_board_entry.py")
        for name in ("board_delta.py", "progress.py"):
            (source / name).write_text("# Explicit offline fixture\n")
        versions = {}
        for version in ("A", "B"):
            (source / "board.py").write_text("VERSION = " + repr(version) + "\n" + FIXTURE, encoding="utf-8")
            package = root / (version + ".json")
            versions[version] = package
            pack(source, version, package)
        env = {key: value for key, value in os.environ.items() if not key.startswith(("GONGGONG_", "BOARD_"))}
        arguments = root / "args.json"
        env.update(BOARD_HELPER=str(helper), BOARD_ARGS=str(arguments))
        for index, version in enumerate(("A", "B", "A")):
            shutil.copyfile(versions[version], installed_package(binary))
            run = subprocess.run(
                [str(binary), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                cwd=project,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=90,
            )
            if run.returncode or "BOARD_BEHAVIOR_READY" not in run.stdout or "SCRIPT ERROR" in run.stderr:
                raise RuntimeError(run.stdout + run.stderr)
            selected = json.loads(arguments.read_text())
            result = root / f"result-{index}.json"
            command = [sys.executable, *selected["args"], "--repo", str(workspace), "--result", str(result)]
            subprocess.run(command, env=env, check=True, capture_output=True, timeout=20)
            observed = json.loads(result.read_text())
            if observed != {"fixture_version": version}:
                raise RuntimeError("Package behavior did not change with selected package")
            report["cases"][f"{index}-{version}"] = {**selected, "result": observed}
            if index == 1:
                delayed = root / "cancelled-result.json"
                started = root / "started"
                delayed_command = [
                    sys.executable,
                    *selected["args"],
                    "--repo",
                    str(workspace),
                    "--result",
                    str(delayed),
                    "--started",
                    str(started),
                    "--delay",
                    "30",
                ]
                with subprocess.Popen(delayed_command, env=env) as child:
                    try:
                        deadline = time.monotonic() + 10
                        while not started.exists() and child.poll() is None and time.monotonic() < deadline:
                            time.sleep(0.02)
                        if not started.exists():
                            raise RuntimeError("Delayed fixture did not start")
                    finally:
                        if child.poll() is None:
                            child.terminate()
                        child.wait(timeout=10)
                if delayed.exists():
                    raise RuntimeError("Cancelled helper wrote a result")
                report["cases"]["cancelled_cli"] = {"terminal_returncode": child.returncode, "late_result": False}
        if hashlib.sha256(binary.read_bytes()).hexdigest() != before:
            raise RuntimeError("Editor changed")
        report["editor_sha256"] = before
    report["temporary_directory_removed"] = not root.exists()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
