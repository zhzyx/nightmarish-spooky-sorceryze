"""Verify AI Chat's main-screen order across normal editor save/restart."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from editor_test_isolation import copy_editor

ROOT = Path(__file__).resolve().parents[2]
WINDOW_SOURCES = (
    "editor/docks/editor_dock.h",
    "editor/docks/editor_dock.cpp",
    "editor/docks/editor_dock_manager.h",
    "editor/docks/editor_dock_manager.cpp",
    "editor/docks/workbench/AuxiliaryDockLayout.cpp",
    "editor/docks/workbench/AIWorkbenchSidebar.cpp",
    "editor/docks/workbench/AIWorkbenchReference.cpp",
    "editor/docks/ai_chat_dock.h",
    "editor/docks/ai_chat_dock.cpp",
    "editor/docks/AIChatController.h",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--build-evidence", type=Path)
    parser.add_argument(
        "--workbench-command", action="store_true", help="Exercise the global workbench command in each layout"
    )
    parser.add_argument("--workbench-button", action="store_true", help="Click the editor title bar workbench button")
    args = parser.parse_args()
    probes = []
    if args.workbench_command:
        probes.append("--workbench-command")
    if args.workbench_button:
        probes.append("--workbench-button")
    binary = args.godot.resolve()
    report = {
        "state": "running",
        "mode": "headless",
        "binary_sha256": sha(binary),
        "phases": [],
        "test_sha256": {p.name: sha(p) for p in [Path(__file__), Path(__file__).with_name("ai_chat_tab_order.gd")]},
        "input_sha256": {p: sha(ROOT / p) for p in WINDOW_SOURCES},
        "evidence_level": "headless controls, display-capability fallback, and single-window split geometry; native floating windows and IME require separate display validation",
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
        with tempfile.TemporaryDirectory(prefix="issue58-order-", ignore_cleanup_errors=os.name == "nt") as directory:
            base = Path(directory)
            isolated_binary = copy_editor(binary, base / "engine")
            assert sha(isolated_binary) == report["binary_sha256"], "Private editor differs from the candidate"
            engine = isolated_binary.parent
            project = base / "project"
            project.mkdir()
            (project / "project.godot").write_text(
                'config_version=5\n[application]\nconfig/name="Tab Order Regression"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
                encoding="utf-8",
            )
            shutil.copyfile(Path(__file__).with_name("ai_chat_tab_order.gd"), project / "order.gd")
            if args.workbench_command:
                (project / "sidebar_fixture.gd").write_text("extends Node2D\n# Editable draft", encoding="utf-8")
                (project / "sidebar_fixture.tscn").write_text(
                    '[gd_scene format=3]\n[node name="CanvasRoot" type="Node2D"]\n'
                    '[node name="Selection" type="Node2D" parent="."]\nposition = Vector2(12, 24)\n',
                    encoding="utf-8",
                )
            env = os.environ.copy()
            for key in ["HOME", "APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME"]:
                env[key] = str(project / key.lower())
                Path(env[key]).mkdir(exist_ok=True)
            env.pop("GONGGONG_WORKSPACE", None)
            (Path(env["HOME"]) / "Library/Caches").mkdir(parents=True, exist_ok=True)
            phases = [
                "initial",
                "legacy_maliang_last",
                "legacy_maliang_selected",
                "pre_daqian_layout",
                "pre_maliang_layout",
                "restart",
            ]
            if args.workbench_command:
                phases += [
                    "auxiliary_inline_seed",
                    "auxiliary_inline_verify",
                    "auxiliary_window_seed",
                    "auxiliary_window_verify",
                ]
            for phase in phases:
                env.pop("AI_CHAT_ORDER_EXPECT_SELECTED", None)
                if phase.startswith("auxiliary_") and phase.endswith("_verify"):
                    env["AI_CHAT_ORDER_EXPECT_SELECTED"] = "Script"
                if phase.startswith("legacy_") or phase.startswith("pre_"):
                    config = project / ".godot/editor/editor_layout.cfg"
                    text = config.read_text(encoding="utf-8")
                    order = re.search(r'^dock_12="([^"\n]+)"', text, re.M).group(1).split(",")
                    if phase.startswith("legacy_maliang"):
                        order.remove("AINativeMainScreen")
                        order.append("AINativeMainScreen")
                    else:
                        order.remove("DaqianMainScreen" if phase == "pre_daqian_layout" else "AINativeMainScreen")
                    expected = "AINativeMainScreen" if phase == "legacy_maliang_selected" else "2D"
                    env["AI_CHAT_ORDER_EXPECT_SELECTED"] = expected
                    text = re.sub(r'^dock_12="[^"\n]+"', 'dock_12="' + ",".join(order) + '"', text, flags=re.M)
                    text = re.sub(
                        r"^dock_12_selected_tab_idx=\d+",
                        "dock_12_selected_tab_idx=" + str(order.index(expected)),
                        text,
                        flags=re.M,
                    )
                    config.write_text(text, encoding="utf-8")
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
                        *(["--", *probes] if probes else []),
                    ],
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                )
                assert result.returncode == 0, result.stdout + result.stderr
                assert "SCRIPT ERROR" not in result.stderr, result.stderr
                line = next(line for line in result.stdout.splitlines() if line.startswith("AI_CHAT_TAB_ORDER_RESULT="))
                sample = json.loads(line.split("=", 1)[1])
                layout = (project / ".godot/editor/editor_layout.cfg").read_text(encoding="utf-8")
                saved = re.search(r'^dock_12="([^"\n]+)"', layout, re.M)
                assert saved is not None, "Normal editor exit did not save the main-screen layout"
                sample["saved_order"] = saved.group(1).split(",")
                if phase.startswith("auxiliary_"):
                    assert sample["expanded"] is True, sample
                    assert re.search(r"^sidebar_expanded=true$", layout, re.M), "Expanded state was not saved"
                assert sample["saved_order"][:5] == [
                    "AIChatMainScreen",
                    "AINativeMainScreen",
                    "DaqianMainScreen",
                    "WebPlatformMainScreen",
                    "2D",
                ], sample
                if report["phases"]:
                    assert sample["labels"] == report["phases"][0]["labels"], "Restart changed visible peer order"
                    assert sample["saved_order"] == report["phases"][0]["saved_order"], (
                        "Restart changed saved peer order"
                    )
                report["phases"].append(sample)
            report["stale_sources"] = [p for p, digest in report["input_sha256"].items() if sha(ROOT / p) != digest]
            assert not report["stale_sources"], "Candidate sources changed during the regression"
            assert sha(binary) == report["binary_sha256"], "Candidate binary changed during the regression"
            assert all(
                sha(Path(__file__).with_name(name)) == digest for name, digest in report["test_sha256"].items()
            ), "Probe changed during the regression"
            report["state"] = "passed"
    except Exception as error:
        report["state"] = "failed"
        report["error_type"] = type(error).__name__
        raise
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
