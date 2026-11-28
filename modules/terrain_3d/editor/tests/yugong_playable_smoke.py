"""Exercise the built-in playable layout page in an isolated project, then walk both routes."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


def run(executable, project, root, stage, args, env, expected):
    log = root / (stage + ".log")
    result = subprocess.run(
        [str(executable), "--path", str(project), "--log-file", str(log), *args],
        env=env, capture_output=True, timeout=300,
    )
    output = log.read_text("utf8", errors="replace") if log.exists() else ""
    if result.returncode or expected not in output or "ERROR:" in output:
        raise RuntimeError(f"{stage} failed: {log}\n{output[-5000:]}")
    print(stage, expected, log, flush=True)


def verify(executable, root, live=False, gpu=False, offline=False):
    project = root / "project"
    project.mkdir(parents=True)
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="愚公可玩地形验收"\n', encoding="utf8")
    (project / "Input.tscn").write_text(
        '[gd_scene format=3]\n[ext_resource type="Script" path="res://editor_probe.gd" id="1"]\n'
        '[node name="Input" type="Node3D"]\nscript = ExtResource("1")\n', encoding="utf8",
    )
    for src, dest in [("yugong_playable_editor.gd", "editor_probe.gd"), ("yugong_playable_runtime.gd", "runtime_probe.gd")]:
        shutil.copyfile(Path(__file__).with_name(src), project / dest)
    env = os.environ.copy()
    for key in ("APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        folder = root / key
        folder.mkdir()
        env[key] = str(folder)
    # A clean Windows editor profile also checks the workbench's host Python at startup.
    if os.name == "nt":
        env.setdefault("GONGGONG_PYTHON", sys.executable)
    env["YUGONG_PLAYABLE_TEST"] = "astra" if live else ("offline" if offline else "fixture")
    graphics = ["--single-window", "--no-focus", "--resolution", "1280x800"]
    if gpu:
        (root / "proof").mkdir()
        env["YUGONG_PROOF"] = str(root / "proof")
        env["YUGONG_TEST_PLAY_BUTTON"] = "1"
    run(executable, project, root, "editor", ["--editor", *(graphics if gpu else ["--headless"]), "res://Input.tscn"],
        env, "Yugong playable editor: 0 failures")
    env.pop("YUGONG_PLAYABLE_TEST")
    env.pop("YUGONG_TEST_PLAY_BUTTON", None)
    if gpu:
        run(executable, project, root, "gpu", [*graphics, "--script", "res://runtime_probe.gd"], env,
            "Yugong playable runtime: 0 failures")
        env.pop("YUGONG_PROOF")
    for stage in (["walk", "walk-edited", "walk-alternate"] if offline else ["walk", "walk-edited"]):
        if stage == "walk-edited":
            env["YUGONG_TEST_EDITED"] = "1"
        elif stage == "walk-alternate":
            env.pop("YUGONG_TEST_EDITED", None)
            env["YUGONG_TEST_ALTERNATE"] = "1"
        run(executable, project, root, stage, ["--headless", "--fixed-fps", "60", "--script", "res://runtime_probe.gd"],
            env, "Yugong playable runtime: 0 failures")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("directory", type=Path)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--live-ai", action="store_true")
    source.add_argument("--offline", action="store_true")
    parser.add_argument("--gpu", action="store_true")
    args = parser.parse_args()
    verify(args.executable.resolve(), args.directory.resolve(), args.live_ai, args.gpu, args.offline)
