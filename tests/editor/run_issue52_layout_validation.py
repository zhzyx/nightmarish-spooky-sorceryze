"""Verify AI Chat layout transitions and saved splits using an isolated editor project."""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from editor_test_isolation import copy_editor

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--build-evidence", type=Path)
    args = parser.parse_args()
    binary = args.godot.resolve()
    report = {
        "state": "running",
        "mode": "headless",
        "platform": platform.system(),
        "architecture": platform.machine(),
        "binary_sha256": sha(binary),
        "phases": [],
        "test_sha256": {
            p.name: sha(p) for p in [Path(__file__), Path(__file__).with_name("issue52_layout_validation.gd")]
        },
    }
    if args.build_evidence:
        report["build_evidence"] = json.loads(args.build_evidence.read_text(encoding="utf-8"))
        expected = report["build_evidence"]
        assert (
            report["binary_sha256"] == expected["binary_sha256" if ".console.exe" in binary.name else "engine_sha256"]
        ), "Binary changed"
        engine = binary.with_name(binary.name.replace(".console.exe", ".exe"))
        assert sha(engine) == expected["engine_sha256"], "Engine binary changed"
        report["engine_sha256"] = sha(engine)
    try:
        with tempfile.TemporaryDirectory(prefix="issue52-layout-", ignore_cleanup_errors=os.name == "nt") as directory:
            base = Path(directory)
            isolated_binary = copy_editor(binary, base / "engine")
            project = base / "project"
            project.mkdir()
            (project / "project.godot").write_text(
                'config_version=5\n[application]\nconfig/name="Tab Order Regression"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
                encoding="utf-8",
            )
            shutil.copyfile(Path(__file__).with_name("issue52_layout_validation.gd"), project / "order.gd")
            env = os.environ.copy()
            for key in ["APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME"]:
                env[key] = str(project / key.lower())
            for phase in ["seed", "initial", "restart"]:
                env["AI_CHAT_ORDER_PHASE"] = phase
                result = subprocess.run(
                    [
                        str(isolated_binary),
                        "--headless",
                        "--editor",
                        "--path",
                        str(project),
                        "--script",
                        "res://order.gd",
                    ],
                    cwd=project,
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                )
                assert result.returncode == 0, result.stdout + result.stderr
                assert "SCRIPT ERROR" not in result.stderr, result.stderr
                line = next(line for line in result.stdout.splitlines() if line.startswith("ISSUE52_LAYOUT_RESULT="))
                sample = json.loads(line.split("=", 1)[1])
                report["phases"].append(sample)
                layout = (project / ".godot/editor/editor_layout.cfg").read_text(encoding="utf-8")
                saved = re.search(r'^dock_12="([^"\n]+)"', layout, re.M)
                assert saved is not None, "Normal editor exit did not save the main-screen layout"
                sample["saved_order"] = saved.group(1).split(",")
                assert sample["saved_order"][0] == "AIChatMainScreen", sample
                assert all(screen in sample["saved_order"] for screen in ["2D", "3D", "Script"]), sample
                sample["saved_splits"] = dict(
                    re.findall(r"^(dock_(?:h?split_\d+|main_split|bottom_split))=(.*)$", layout, re.M)
                )
                assert sample["saved_splits"], "No saved dock split evidence"
                if len(report["phases"]) > 1:
                    # The selected bottom panel legitimately changes center height.
                    def persisted(offsets):
                        return {key: value for key, value in offsets.items() if key != "DockVSplitCenter"}

                    assert persisted(sample["normal_offsets"]) == persisted(report["phases"][0]["normal_offsets"]), (
                        "Restart changed actual restored Dock offsets"
                    )
                    assert sample["normal_size"][0] == report["phases"][0]["normal_size"][0], (
                        "Restart changed restored width"
                    )
                    assert sample["saved_order"] == report["phases"][0]["saved_order"], (
                        "Restart changed saved peer order"
                    )
                    assert sample["saved_splits"] == report["phases"][0]["saved_splits"], (
                        "Saving in AI Chat changed saved split positions"
                    )
            report["state"] = "passed"
    except Exception as error:
        report["state"] = "failed"
        report["error_type"] = type(error).__name__
        for key in ["stdout", "stderr"]:
            value = getattr(error, key, None)
            if value:
                report[key] = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
        raise
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
