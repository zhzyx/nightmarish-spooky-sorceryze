"""Exercise both GDScript Controllers in a private real editor with native AICore."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from editor_test_isolation import copy_editor
from run_unified_settings_native import sanitized_environment

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    os.environ.pop("GONGGONG_WORKSPACE", None)
    reports = []
    for workflow in ("tianshu", "maliang"):
        with tempfile.TemporaryDirectory(prefix=f"{workflow}-runtime-") as folder:
            project = Path(folder)
            binary = copy_editor(args.godot, project / "private-editor")
            environment = sanitized_environment(project)
            environment["DAQIAN_TEST_PYTHON"] = sys.executable
            source = (
                ROOT / "tests/editor/tianshu_controller_acceptance.gd"
                if workflow == "tianshu"
                else ROOT / "tests/editor/maliang_runtime_contract.gd"
            )
            script = source.read_text(encoding="utf-8")
            if workflow == "tianshu":
                script = (
                    script
                    .replace("extends SceneTree", "@tool\nextends Node", 1)
                    .replace("func _initialize()", "func _ready()")
                    .replace("root.add_child(controller)", "get_tree().root.add_child(controller)")
                    .replace("\tquit(", "\tget_tree().quit(")
                    .replace("await process_frame", "await get_tree().process_frame")
                )
                relative = "editor/docks/daqian/workflow_controller.gd"
            else:
                relative = "addons/ainative/workflow_controller.gd"
            controller = ROOT / relative if workflow == "tianshu" else ROOT / "samples/ainative-workbench" / relative
            target = project / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(controller, target)
            (project / "acceptance.gd").write_text(script, encoding="utf-8")
            plugin = project / "addons/acceptance"
            plugin.mkdir(parents=True)
            (plugin / "plugin.cfg").write_text(
                '[plugin]\nname="Native runtime acceptance"\ndescription="Isolated fixture"\n'
                'author="test"\nversion="1"\nscript="plugin.gd"\n',
                encoding="utf-8",
            )
            (plugin / "plugin.gd").write_text(
                '@tool\nextends EditorPlugin\nfunc _enter_tree():\n\tadd_child(load("res://acceptance.gd").new())\n',
                encoding="utf-8",
            )
            (project / "project.godot").write_text(
                '[application]\nconfig/name="Native runtime acceptance"\n[editor_plugins]\n'
                'enabled=PackedStringArray("res://addons/acceptance/plugin.cfg")\n'
                '[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
                encoding="utf-8",
            )
            command = [str(binary), "--headless", "--editor", "--path", str(project)]
            with (args.out / f"{workflow}.log").open("w", encoding="utf-8") as log:
                result = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=60)
            output = (args.out / f"{workflow}.log").read_text(encoding="utf-8")
            records = [json.loads(line) for line in output.splitlines() if line.startswith('{"checks":')]
            passed = (
                result.returncode == 0
                and len(records) == 1
                and records[0]["native_runtime"] is True
                and records[0]["checks"] > 0
                and not records[0]["failures"]
                and "ERROR:" not in output
            )
            reports.append({
                "workflow": workflow,
                "passed": passed,
                "exit_code": result.returncode,
                "result": records,
                "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "controller_sha256": hashlib.sha256(controller.read_bytes()).hexdigest(),
            })
    (args.out / "report.json").write_text(json.dumps(reports, indent=2) + "\n", encoding="utf-8")
    return 0 if all(report["passed"] for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
