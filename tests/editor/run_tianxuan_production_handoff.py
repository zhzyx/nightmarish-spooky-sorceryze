"""Verify native specification handoff in a private editor, with no model provider."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from editor_test_isolation import copy_editor
from run_unified_settings_native import sanitized_environment

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", action="store_true", help="Exercise source scripts before rebuilding")
    args = parser.parse_args()
    binary = args.godot.resolve(strict=True)
    sources = [
        ROOT / "editor/plugins/ainative_editor_plugin.cpp",
        ROOT / "editor/plugins/ainative_editor_plugin.h",
        ROOT / "editor/docks/tianxuan/TianxuanWorkbench.cpp",
        ROOT / "editor/docks/tianxuan/workspace_controller.gd",
        ROOT / "samples/ainative-workbench/addons/ainative/workbench.gd",
        ROOT / "samples/ainative-workbench/addons/ainative/spec_handoff.gd",
        Path(__file__).with_name("tianxuan_production_handoff.gd"),
        Path(__file__),
    ]
    report = {
        "ok": False,
        "source_mode": args.source,
        "editor_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "input_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources
        },
        "scope": "Private synthetic account/specification; no business authentication or model provider",
    }
    with tempfile.TemporaryDirectory(prefix="tianxuan-production-handoff-") as temporary:
        private = Path(temporary).resolve()
        with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
            editor = copy_editor(binary, private / "engine")
        project = private / "project"
        project.mkdir()
        (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Private handoff probe"\n')
        shutil.copy2(Path(__file__).with_name("tianxuan_production_handoff.gd"), project / "probe.gd")
        if args.source:
            shutil.copytree(ROOT / "samples/ainative-workbench/addons", project / "addons")
        output = private / "result.json"
        environment = sanitized_environment(private)
        environment.update(
            GONGGONG_WORKSPACE="",
            TIANXUAN_API="http://127.0.0.1:1",
            TX_HANDOFF_SOURCE="yes" if args.source else "no",
            TX_REPORT=str(output),
        )
        try:
            result = subprocess.run(
                [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                cwd=project,
                env=environment,
                capture_output=True,
                timeout=60,
            )
            report["exit_code"] = result.returncode
            stdout, stderr = result.stdout, result.stderr
        except subprocess.TimeoutExpired as failure:
            report["exit_code"] = -1
            report["error"] = "Private handoff probe exceeded 60 seconds"
            stdout, stderr = failure.stdout or b"", failure.stderr or b""
        report["native"] = json.loads(output.read_text()) if output.is_file() else {}
        report["script_error_seen"] = b"SCRIPT ERROR:" in stderr
        report["stale_sources"] = [
            str(path.relative_to(ROOT))
            for path in sources
            if hashlib.sha256(path.read_bytes()).hexdigest() != report["input_sha256"][str(path.relative_to(ROOT))]
        ]
        report["binary_changed"] = hashlib.sha256(binary.read_bytes()).hexdigest() != report["editor_sha256"]
        report["ok"] = (
            report["exit_code"] == 0
            and report["native"].get("ok", False)
            and not report["script_error_seen"]
            and not report["stale_sources"]
            and not report["binary_changed"]
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.with_suffix(".stdout.log").write_bytes(stdout)
        args.out.with_suffix(".stderr.log").write_bytes(stderr)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
