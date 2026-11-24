"""Run UI probes in a private, headless editor; retain logs, clean test settings."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REPORTS = ROOT / "data-collection/receipts/apple-gray"
parser = argparse.ArgumentParser()
parser.add_argument("--scale", type=float, choices=(1.0, 1.5, 2.0), default=1.0)
args = parser.parse_args()
REPORTS = REPORTS / ("scale-" + str(args.scale))
REPORTS.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "tests/editor"))
from editor_test_isolation import copy_editor

source = ROOT / "bin/godot.windows.editor.x86_64.exe"
env = dict(os.environ)
env.pop("GONGGONG_WORKSPACE", None)
env["APPLE_GRAY_SCALE"] = str(args.scale)
os.environ.pop("GONGGONG_WORKSPACE", None)
results = []
with tempfile.TemporaryDirectory(prefix="apple-gray-probes-") as temporary:
    parent = Path(temporary)
    editor = copy_editor(source, parent / "editor")
    (editor.parent / "_sc_").write_text('[presets]\ninterface/editor/appearance/display_scale=7\ninterface/editor/appearance/custom_display_scale=' + str(args.scale) + '\n', encoding="utf-8")
    for dependency in (ROOT / "bin").glob("*.dll"):
        shutil.copy2(dependency, editor.parent / dependency.name)
    for name in ("folding_probe", "theme_probe", "layout_probe", "material_inspector_probe", "interaction_probe"):
        project = parent / name
        project.mkdir()
        (project / "project.godot").write_text('[application]\nconfig/name="Apple Gray Probe"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n', encoding="utf-8")
        shutil.copy2(HERE / ("apple_gray_" + name + ".gd"), project / "probe.gd")
        command = [str(editor), "--headless", "--path", str(project), "--log-file", str(REPORTS / (name + "-engine.log"))]
        if name != "folding_probe":
            command.append("--editor")
        command += ["--script", "res://probe.gd"]
        try:
            result = subprocess.run(command, env=env, cwd=project, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        except subprocess.TimeoutExpired as error:
            def as_bytes(value):
                return value.encode("utf-8") if isinstance(value, str) else (value or b"")
            output = as_bytes(error.stdout) + as_bytes(error.stderr)
            (REPORTS / (name + ".log")).write_bytes(output)
            results.append({"probe": name, "exit_code": 124})
            continue
        (REPORTS / (name + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
        results.append({"probe": name, "exit_code": result.returncode})
    # Native unit-test startup does not register the full editor resource set.
    # Do not load the settings/shortcuts serialized by the full editor probes.
    native_editor = copy_editor(source, parent / "native-editor")
    native = subprocess.run([str(native_editor), "--headless", "--test", "--test-case=*[EditorVisual]*"], env=env, cwd=ROOT, capture_output=True, timeout=60)
    (REPORTS / "inspector-native.log").write_bytes(native.stdout + native.stderr)
    results.append({"probe": "inspector-native", "exit_code": native.returncode})
report = {"binary_sha256": hashlib.sha256(source.with_name(source.name.replace(".console.exe", ".exe")).read_bytes()).hexdigest(), "results": results, "temporary_settings_removed": True}
(REPORTS / "probe-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report))
sys.exit(any(row["exit_code"] for row in results))
