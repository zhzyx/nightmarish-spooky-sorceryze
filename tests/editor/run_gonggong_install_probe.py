"""Verify installed editor location discovery with no workspace environment override."""

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

from editor_test_isolation import macos_editor
from run_requirements_intake import run_editor

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="gonggong-install-") as temporary:
        base = Path(temporary)
        folder = base / "unrelated-project"
        folder.mkdir()
        isolated_editor = macos_editor(args.godot, base / "isolated-editor")
        expected_workspace = ROOT
        if sys.platform == "darwin":
            # The macOS probe runs a private executable. Install the real discovery
            # markers beside that copy, separately from the opened project.
            expected_workspace = isolated_editor.parent
            for name in ("gonggong-workspace.json", "SConstruct", "tools/codebuddy_cli/godot_bridge.js"):
                target = expected_workspace / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
        (folder / "project.godot").write_text('[application]\nconfig/name="Installation probe"\n', encoding="utf-8")
        shutil.copyfile(ROOT / "tests/editor/gonggong_install_probe.gd", folder / "probe.gd")
        env = dict(os.environ, GONGGONG_EXPECTED_WORKSPACE=str(expected_workspace))
        env.pop("GONGGONG_WORKSPACE", None)
        env.pop("GONGGONG_PYTHON", None)
        env.pop("GONGGONG_NODE", None)
        for name in ("APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
            directory = folder / name
            directory.mkdir()
            env[name] = str(directory)
        result = run_editor(
            [str(isolated_editor), "--headless", "--editor", "--path", str(folder), "--script", "res://probe.gd"],
            folder,
            env,
            timeout=60,
        )
        if result.returncode or b"GONGGONG_INSTALLED_WORKSPACE_DISCOVERY_OK" not in result.stdout:
            print(result.stdout[-5000:].decode("utf-8", errors="replace"))
            print(result.stderr[-5000:].decode("utf-8", errors="replace"))
            return 1
        print(
            "Installed editor found workspace from executable ancestors; isolated settings, unrelated cwd, no workspace override."
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
