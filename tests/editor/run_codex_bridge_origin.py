"""Verify native model discovery never launches a Codex bridge from the opened project."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from editor_test_isolation import copy_editor


def probe(source, node, installed):
    with tempfile.TemporaryDirectory(prefix="codex-bridge-origin-") as temporary:
        root = Path(temporary)
        project = root / "project"
        project.mkdir()
        executable = copy_editor(source, root / "bin")
        if installed:
            (root / "SConstruct").touch()
        for directory in [root, project] if installed else [project]:
            bridge = directory / "tools/codex_cli/godot_bridge.js"
            bridge.parent.mkdir(parents=True)
            bridge.write_text(
                "require('fs').writeFileSync(process.env.ORIGIN_MARKER, __filename);"
                "console.log(JSON.stringify({data:[{id:'fixture'}]}));",
                encoding="utf-8",
            )
        (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Origin probe"\n')
        # Python stands in for the native CLI. Its "login status" invocation opens this script.
        (project / "login").write_text("pass\n")
        (executable.parent / "editor_data/editor_settings-4.8.tres").write_text(
            '[gd_resource type="EditorSettings" format=3]\n\n[resource]\nai_chat/backend = 2\n'
        )
        (project / "probe.gd").write_text(
            """@tool
extends SceneTree
func _initialize():
    probe.call_deferred()
func probe():
    var dock = root.find_child("AI Chat", true, false)
    var status = dock.get_ai_settings_control().find_child("ModelStatus", true, false)
    for i in range(150):
        if FileAccess.file_exists(OS.get_environment("ORIGIN_MARKER")) or "CLI 路径无效" in status.text:
            break
        await create_timer(0.05).timeout
    print("ORIGIN_STATUS=", status.text)
    quit()
""",
            encoding="utf-8",
        )
        marker = root / "observed.txt"
        env = dict(os.environ, ORIGIN_MARKER=str(marker), GONGGONG_NODE=str(node), GONGGONG_CODEX=sys.executable)
        run = subprocess.run(
            [str(executable), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
            cwd=project,
            env=env,
            capture_output=True,
            timeout=45,
            check=True,
        )
        status = next(line for line in run.stdout.decode("utf-8", "replace").splitlines() if "ORIGIN_STATUS=" in line)
        observed = Path(marker.read_text()).relative_to(root).as_posix() if marker.exists() else ""
        print(json.dumps({"installed": installed, "loaded": observed, "status": status}, ensure_ascii=False))
        return observed == "tools/codex_cli/godot_bridge.js" if installed else not observed and "CLI 路径无效" in status


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True)
    args = parser.parse_args()
    os.environ.pop("GONGGONG_WORKSPACE", None)
    sys.exit(0 if all([probe(args.godot, args.node, installed) for installed in (False, True)]) else 1)
