"""Run the built-in Terrain3D scene editor from an empty project, then reopen its saved scene."""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def verify(executable, root, yugong=False):
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text(
        'config_version=5\n[application]\nconfig/name="Terrain3D Module Editor Test"\n', encoding="utf8"
    )
    script = Path(__file__).with_name("yugong_smoke.gd") if yugong else Path(__file__).with_suffix(".gd")
    (project / "editor_smoke.gd").write_bytes(script.read_bytes())
    (project / "editable_terrain_data").mkdir()
    (project / "editable_terrain_data" / "sentinel").write_text("preserve", encoding="utf8")
    (project / "main.tscn").write_text(
        '[gd_scene format=3]\n[ext_resource type="Script" path="res://editor_smoke.gd" id="1"]\n'
        '[node name="TerrainTestScene" type="Node3D"]\nscript = ExtResource("1")\n',
        encoding="utf8",
    )
    env = os.environ.copy()
    for name in ("APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        env[name] = str(root / name)
        Path(env[name]).mkdir(exist_ok=True)
    for stage in (("create", "reopen", "runtime") if yugong else ("create", "reopen")):
        env["TERRAIN3D_YUGONG_STAGE" if yugong else "TERRAIN3D_EDITOR_GUI_STAGE"] = stage
        log = root / (stage + ".log")
        args = [
            str(executable),
            "--editor",
            "--path",
            str(project),
            "--log-file",
            str(log),
            "--quit-after",
            "24000" if yugong and env.get("YUGONG_LIVE_AI") else "1800",
            "res://main.tscn",
        ]
        if stage == "runtime":
            args.remove("--editor")
        if not (yugong and env.get("YUGONG_SCREENSHOT") and stage == "create"):
            args.insert(1, "--headless")
        else:
            args[1:1] = ["--resolution", "1400x880", "--single-window", "--no-focus"]
        result = subprocess.run(args, env=env, timeout=240, capture_output=True)
        output = log.read_text("utf8", errors="replace") if log.exists() else ""
        print(stage, result.returncode, log, flush=True)
        prefix = "Yugong " if yugong else "Terrain3D editor "
        if result.returncode or (prefix + stage + ": 0 failures") not in output or "ERROR:" in output:
            print(output[-4500:], flush=True)
            return 1
    assert (project / "editable_terrain_data" / "sentinel").read_text() == "preserve"
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("directory", nargs="?", type=Path)
    parser.add_argument("--yugong", action="store_true")
    options = parser.parse_args()
    exe = options.executable.resolve()
    if options.directory:
        work = options.directory.resolve()
        work.mkdir(exist_ok=True, parents=True)
        sys.exit(verify(exe, work, options.yugong))
    with tempfile.TemporaryDirectory(prefix="terrain3d_editor_") as tmp:
        sys.exit(verify(exe, Path(tmp), options.yugong))
