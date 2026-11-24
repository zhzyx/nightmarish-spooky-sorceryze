"""Offscreen viewport raster probe, with a minimized non-focusable host window."""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from editor_test_isolation import copy_editor

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("--editor", action="store_true")
args = parser.parse_args()
output = ROOT / "data-collection/receipts/apple-gray/render"
output.mkdir(parents=True, exist_ok=True)
os.environ.pop("GONGGONG_WORKSPACE", None)
env = dict(os.environ, APPLE_GRAY_RENDER_OUTPUT=str(output))
with tempfile.TemporaryDirectory(prefix="apple-gray-render-") as temporary:
    parent = Path(temporary)
    editor = copy_editor(ROOT / "bin/godot.windows.editor.x86_64.exe", parent / "editor")
    project = parent / "project"
    project.mkdir()
    if args.editor:
        (project / "sample.tscn").write_text(
            '[gd_scene format=3]\n\n[node name="视觉验收场景" type="Node2D"]\n\n[node name="角色节点" type="Node2D" parent="."]\nposition = Vector2(120, 80)\n',
            encoding="utf-8",
        )
    (project / "project.godot").write_text(
        """[application]
config/name="Background UI Raster Probe"
[display]
window/size/no_focus=true
window/size/mode=1
window/size/viewport_width=320
window/size/viewport_height=200
[rendering]
renderer/rendering_method="gl_compatibility"
""",
        encoding="utf-8",
    )
    script = "apple_gray_editor_render_probe.gd" if args.editor else "apple_gray_render_probe.gd"
    shutil.copy2(ROOT / "tests/editor" / script, project / "probe.gd")
    startup = None
    if sys.platform == "win32":
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
    command = [
        str(editor),
        "--path",
        str(project),
        "--audio-driver",
        "Dummy",
        "--script",
        "res://probe.gd",
        "--log-file",
        str(output / ("editor-engine.log" if args.editor else "engine.log")),
    ]
    if args.editor:
        command.append("--editor")
    result = subprocess.run(command, env=env, cwd=project, capture_output=True, timeout=60, startupinfo=startup)
    (output / "process.log").write_bytes(result.stdout + result.stderr)
    exit_code = result.returncode or int(b"SCRIPT ERROR" in result.stdout + result.stderr)
    print(exit_code)
    report = output / ("editor-render.json" if args.editor else "render.json")
    if report.exists():
        print(report.read_text())
    raise SystemExit(exit_code)
