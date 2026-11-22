"""Drive the Q03 Godot editor probe in a private project and export its sampled frames."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from run_unified_settings_native import sanitized_environment

HERE = Path(__file__).resolve().parent


def digest(content):
    return hashlib.sha256(content).hexdigest()


def probe(editor, scratch, phase, scene=None, action=None):
    with tempfile.TemporaryDirectory(prefix=phase + "-", dir=scratch) as project_dir:
        project = Path(project_dir)
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Q03"\n[internationalization]\nlocale/test="en"\n',
            encoding="utf-8",
        )
        if scene is not None:
            (project / "motion.tscn").write_bytes(scene)
        shutil.copyfile(HERE / "workbench_approach_replay.gd", project / "approach.gd")
        shutil.copyfile(HERE / "workbench_q03_animation.gd", project / "probe.gd")
        env = {k: v for k, v in sanitized_environment(project).items() if not k.startswith("TIANXUAN_")}
        proc = subprocess.run(
            [editor, "--headless", "--editor", "--language", "en", "--path", project, "--script", "res://probe.gd"],
            env=env | {"Q03_PHASE": phase, "Q03_ACTION": json.dumps(action)},
            cwd=project,
            capture_output=True,
            timeout=45,
        )
        log = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
        assert proc.returncode == 0 and "SCRIPT ERROR" not in log, log[-5000:]
        rows = [json.loads(line[4:]) for line in log.splitlines() if line.startswith("Q03=")]
        assert len(rows) == 1, log[-5000:]
        scene = (project / "motion.tscn").read_bytes()
        assert digest(scene) == rows[0]["sha256"]
        return scene, rows[0]


def export_comparison(frames, directory):
    """Draw both actor outlines at coordinates sampled from the actual editor viewport."""
    from PIL import Image, ImageDraw, ImageFont

    images = []
    for frame, (source, candidate) in enumerate(zip(frames["Walk"], frames["Landing"], strict=True)):
        canvas = Image.new("RGB", (604, 170), "#182330")
        draw = ImageDraw.Draw(canvas)
        font = ImageFont.load_default()
        for offset, name, point in ((0, "MANUAL", source), (302, "AI PREVIEW", candidate)):
            draw.text((offset + 15, 8), name, fill="#ffffff", font=font)
            x, y = point[0] + offset, point[1] + 16
            draw.line((offset + 15, 128, offset + 280, 128), fill="#cad3df", width=2)
            draw.polygon([(x, y - 15), (x + 12, y), (x, y + 15), (x - 12, y)], fill="#efa03a")
        draw.line((301, 5, 301, 139), fill="#54667a")
        draw.text((15, 148), f"Frame {frame:02d} / 24", fill="#ffffff", font=font)
        if frame >= 12:
            draw.text((318, 148), "Protected interval", fill="#ffffff", font=font)
        images.append(canvas)
    images[0].save(
        directory / "comparison.gif", save_all=True, append_images=images[1:], duration=[85] * 24 + [650], loop=0
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["produce", "check"])
    parser.add_argument("editor", type=Path)
    parser.add_argument("scratch", type=Path)
    parser.add_argument("source_sha256")
    args = parser.parse_args()
    if args.phase == "produce":
        grant = json.loads(Path(os.environ["NATIVE_CONTEXT"]).read_text(encoding="utf-8"))["stage_authorization"]
        assert grant["stage"] == "preview"
        target = Path(os.environ["NATIVE_WORKSPACE"]) / "a/motion.tscn"
        action = json.loads(Path(os.environ["Q03_DECISION_FILE"]).read_text(encoding="utf-8"))
        assert action["execution"] == Path(os.environ["NATIVE_CONTEXT"]).parent.name
        assert action["issue"] == grant["issue_id"] and action["criteria"] == grant["criteria"]
        assert digest(target.read_bytes()) == args.source_sha256 == action["source_sha256"]
        candidate, observation = probe(args.editor, args.scratch, "produce", target.read_bytes(), action)
        target.write_bytes(candidate)
        print(json.dumps(observation))
    else:
        source = (Path(os.environ["DUOBAO_INPUT"]) / "a/motion.tscn").read_bytes()
        _, replay = probe(args.editor, args.scratch, "replay", source)
        assert digest(source) == replay["sha256"] and replay["sha256"] != args.source_sha256
        print(json.dumps({"sha256": replay["sha256"], "replay": replay["replay"], "landing": replay["landing"]}))
