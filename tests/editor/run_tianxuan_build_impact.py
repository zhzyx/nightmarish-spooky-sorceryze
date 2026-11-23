"""Measure native and embedded SCons invalidation in an idle isolated worktree.

Temporarily changes two candidate files, builds and probes private editor copies,
then restores their exact original bytes and rebuilds even when a probe fails.
Do not run alongside another writer, build or test of this worktree.
"""

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from editor_test_isolation import copy_editor
from run_unified_settings_native import sanitized_environment

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "editor/docks/tianxuan"
CPP = MODULE / "TianxuanWorkbench.cpp"
SCRIPT = MODULE / "workspace_controller.gd"
HEADER = MODULE / "TianxuanScripts.gen.h"
PROBE = """extends SceneTree

func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	await process_frame
	await process_frame
	var view = EditorInterface.get_base_control().find_child("TianxuanWorkspaceView", true, false)
	if view == null:
		quit(1)
		return
	var controller = view.get_meta("controller")
	var native = str(controller.get_meta("tianxuan_build_probe", ""))
	var embedded = str(controller.tianxuan_build_probe()) if controller.has_method("tianxuan_build_probe") else ""
	var passed = native == OS.get_environment("TX_EXPECT_NATIVE") and embedded == OS.get_environment("TX_EXPECT_EMBEDDED")
	print(JSON.stringify({"passed": passed, "native": native, "embedded": embedded}))
	quit(0 if passed else 1)
"""


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build(command, log):
    with log.open("w", encoding="utf-8") as output:
        result = subprocess.run(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT)
    content = log.read_text(encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError("Candidate build failed:\n" + content[-6000:])
    return {
        "log_sha256": digest(log),
        "recompiled_bridge": "Compiling editor/docks/tianxuan/TianxuanWorkbench.cpp" in content,
        "regenerated_scripts": "Generating editor/docks/tianxuan/TianxuanScripts.gen.h" in content,
        "diagnostics": [line for line in content.splitlines() if "warning:" in line.lower()],
    }


def probe(binary, native="", embedded=""):
    with tempfile.TemporaryDirectory(prefix="tianxuan-build-probe-") as temporary:
        directory = Path(temporary).resolve()
        project = directory / "project"
        project.mkdir()
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Build invalidation probe"\n', encoding="utf-8"
        )
        (project / "probe.gd").write_text(PROBE, encoding="utf-8")
        with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
            editor = copy_editor(binary, directory / "engine")
        environment = {
            key: value
            for key, value in sanitized_environment(directory).items()
            if not key.startswith(("TIANXUAN_", "TX_"))
        }
        environment.update(TIANXUAN_API="http://127.0.0.1:9", TX_EXPECT_NATIVE=native, TX_EXPECT_EMBEDDED=embedded)
        result = subprocess.run(
            [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
            cwd=directory,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        output = result.stdout + result.stderr
        reports = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
        report = next((value for value in reports if value.get("passed") is True), None)
        if result.returncode or "SCRIPT ERROR" in output or report is None:
            raise AssertionError(output[-6000:])
        report["binary_sha256"] = digest(editor)
        report["process_diagnostics"] = [
            line for line in result.stderr.splitlines() if line.startswith(("ERROR:", "WARNING:"))
        ]
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("scons_flags", nargs=argparse.REMAINDER, help="SCons flags following --")
    args = parser.parse_args()
    flags = args.scons_flags[1:] if args.scons_flags[:1] == ["--"] else args.scons_flags
    if not flags:
        parser.error("Provide the exact candidate SCons flags after --")
    binary = args.godot.resolve(strict=True)
    command = [sys.executable, "-m", "SCons", *flags]
    originals = {path: path.read_bytes() for path in (CPP, SCRIPT)}
    marker = "invalidation-" + secrets.token_hex(8)
    anchor = b'\tpController->set_meta("session_controller", pSession);'
    if originals[CPP].count(anchor) != 1:
        raise AssertionError("Expected one native controller construction anchor")
    records = {}
    with tempfile.TemporaryDirectory(prefix="tianxuan-build-invalidation-") as temporary:
        logs = Path(temporary)
        build(command, logs / "baseline.log")
        before = probe(binary)
        header_before = digest(HEADER)
        try:
            CPP.write_bytes(
                originals[CPP].replace(
                    anchor, anchor + f'\n\tpController->set_meta("tianxuan_build_probe", "{marker}");'.encode()
                )
            )
            print("Building native input mutation", flush=True)
            native_build = build(command, logs / "native.log")
            native_probe = probe(binary, native=marker)
            if (
                not native_build["recompiled_bridge"]
                or digest(HEADER) != header_before
                or native_probe["binary_sha256"] == before["binary_sha256"]
            ):
                raise AssertionError("Native input did not invalidate its target independently of embedded scripts")
            records["native_invalidation"] = dict(passed=True, build=native_build, before=before, after=native_probe)

            CPP.write_bytes(originals[CPP])
            SCRIPT.write_bytes(
                originals[SCRIPT] + f'\n\nfunc tianxuan_build_probe() -> String:\n\treturn "{marker}"\n'.encode()
            )
            print("Building embedded input mutation", flush=True)
            embedded_build = build(command, logs / "embedded.log")
            embedded_probe = probe(binary, embedded=marker)
            if (
                not embedded_build["recompiled_bridge"]
                or not embedded_build["regenerated_scripts"]
                or digest(HEADER) == header_before
            ):
                raise AssertionError("Embedded input did not regenerate the header and rebuild its native consumer")
            records["generated_input_invalidation"] = dict(
                passed=True,
                build=embedded_build,
                before=before,
                after=embedded_probe,
                header_before=header_before,
                header_after=digest(HEADER),
            )
        finally:
            for path, content in originals.items():
                path.write_bytes(content)
            print("Restoring and rebuilding the original candidate", flush=True)
            restored_build = build(command, logs / "restored.log")
        restored = probe(binary)
        if digest(HEADER) != header_before or any(path.read_bytes() != content for path, content in originals.items()):
            raise AssertionError("Restored candidate differs from its original inputs")
    files = [
        path
        for path in MODULE.iterdir()
        if path.is_file() and not path.name.endswith(".gen.h") and path.name != "build-impact.json"
    ]
    files += [
        ROOT / path
        for path in (
            "editor/SCsub",
            "editor/docks/SCsub",
            "editor/editor_node.cpp",
            "editor/editor_builders.py",
            "editor/docks/workbench/AIWorkbenchSidebar.cpp",
            "editor/docks/workbench/business_session.gd",
            "tests/editor/run_tianxuan_build_impact.py",
            "tests/editor/editor_test_isolation.py",
            "tests/editor/run_unified_settings_native.py",
        )
    ]
    invocation = " ".join([
        "python tests/editor/run_tianxuan_build_impact.py --godot",
        args.godot.as_posix(),
        "--report",
        args.report.as_posix(),
        "--",
        *flags,
    ])
    records["native_invalidation"].update(
        command=invocation,
        observed="Changing only C++ rebuilt the native bridge and linked a changed executable; its isolated editor controller exposed the new marker while the generated header stayed identical.",
    )
    records["generated_input_invalidation"].update(
        command=invocation,
        observed="Changing the embedded controller regenerated its header, rebuilt the native bridge and exposed the new script method in the compiled editor. Restoration removed both markers and restored the original generated header.",
    )
    report = dict(
        passed=True,
        evidence_level="actual_scons_rebuild_and_private_headless_editor",
        checks=records,
        input_blobs={
            path.relative_to(ROOT).as_posix(): subprocess.check_output(
                ["git", "hash-object", str(path)], cwd=ROOT, text=True
            ).strip()
            for path in sorted(files)
        },
        restored=dict(build=restored_build, probe=restored),
        platform=sys.platform,
        display_boundary="No actual display, IME or Windows acceptance; temporary mutations were restored before writing this receipt.",
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(passed=True, checks=list(records), binary_sha256=restored["binary_sha256"])))


if __name__ == "__main__":
    main()
