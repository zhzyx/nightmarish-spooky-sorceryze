"""Open two explicitly linked 3D models in the native Godot workbench and return to their preview."""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from run_workbench_issue_consultation import ROOT, exercise


def verify_routes(engine, project, env, store, actor, issues, native):
    fixtures = []
    scene = ["[gd_scene load_steps=3 format=3]"]
    nodes = ['[node name="Preview" type="Node3D"]']
    for index, (issue, record) in enumerate(zip(issues, native["records"], strict=True)):
        side = ("Left", "Right")[index]
        number = 781 + index
        url = f"https://github.com/old/studio/issues/{number}"
        store.link_external(actor, "tianshu", url, "issue", issue["id"])
        assert issue["number"] != number
        mesh = f"{side}/Model.tres"
        (project / side).mkdir()
        (project / mesh).write_text('[gd_resource type="BoxMesh" format=3]\n[resource]\n')
        scene.append(f'[ext_resource type="BoxMesh" path="res://{mesh}" id="{side}"]')
        nodes.extend([
            f'[node name="{side}" type="Node3D" parent="."]',
            f'[node name="Model" type="MeshInstance3D" parent="{side}"]',
            f'mesh = ExtResource("{side}")',
        ])
        fixtures.append(record | {"url": url, "number": number, "title": issue["title"], "side": side})
    # Only the issue in the current Tianxuan project may win the exact external link.
    foreign = store.create_issue(actor, issues[0]["title"], project="u14/other")
    store.link_external(actor, "tianshu", fixtures[0]["url"], "issue", foreign["id"])
    for issue in issues:
        store.link_external(actor, "tianshu", "https://github.com/old/studio/issues/783", "issue", issue["id"])
    (project / "preview.tscn").write_text("\n".join(scene + nodes) + "\n")
    shutil.copyfile(Path(__file__).with_name("workbench_compact_model_route.gd"), project / "compact.gd")
    run = subprocess.run(
        [str(engine), "--headless", "--editor", "--path", str(project), "--script", "res://compact.gd"],
        env=env | {"U14_MODELS": json.dumps(fixtures)},
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        cwd=project.parent,
        timeout=90,
    )
    output = run.stdout + run.stderr
    if env["TIANXUAN_TOKEN"] in output:
        raise AssertionError("Fixture credential appeared in editor diagnostics")
    marks = [line.removeprefix("U14_NATIVE=") for line in output.splitlines() if line.startswith("U14_NATIVE=")]
    assert run.returncode == 0 and len(marks) == 1 and "SCRIPT ERROR" not in output, output[-6500:]
    return {"models": fixtures, "foreign_issue": foreign["id"], **json.loads(marks[0])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    binary = args.godot.resolve(strict=True)
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}), tempfile.TemporaryDirectory(prefix="u14-") as temp:
        result = exercise(Path(temp), binary, verify_routes)
        geometry_report = Path(temp) / "spatial.json"
        subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                "-B",
                str(Path(__file__).with_name("run_tianshu_spatial.py")),
                "--godot",
                str(binary),
                "--report",
                str(geometry_report),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=240,
            env=os.environ | {"PYTHONUTF8": "1"},
        )
        spatial = json.loads(geometry_report.read_text(encoding="utf-8"))
        assert spatial["passed"] and spatial["restart"]["exit_code"] == 0
        geometry = [
            json.loads(line.removeprefix("TIANSHU_COMPOSER_GEOMETRY="))
            for line in spatial["stdout"].splitlines()
            if line.startswith("TIANSHU_COMPOSER_GEOMETRY=")
        ]
        assert [entry["window_width"] for entry in geometry] == [1440, 1100]
        assert all(entry["visible"] and entry["input_bottom"] <= entry["window_height"] for entry in geometry)
    routes = result["routes"]
    assert not any("/turns" in path or "/executions" in path for _, path, _ in routes["http"])
    engine = binary.with_name(binary.name.replace(".console.exe", ".exe"))
    with engine.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    report = {
        "request_id": "gonggong-ai-workbench-plan1-u14",
        "issue_number": 1761,
        "result": "passed",
        "mode": "headless",
        "platform": platform.platform(),
        "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "editor_sha256": digest,
        "source_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "editor/docks/ai_chat_dock.h",
                "editor/docks/daqian/spatial_workbench.gd",
                "editor/docks/workbench/AIWorkbenchDraft.cpp",
                "editor/docks/workbench/AIWorkbenchReference.cpp",
                "editor/docks/workbench/AIWorkbenchSidebar.cpp",
                "editor/docks/workbench/issue_detail.gd",
                "editor/docks/workbench/module_selector.gd",
                "tests/editor/tianshu_spatial.gd",
                "tests/editor/run_workbench_compact_model_route.py",
                "tests/editor/workbench_compact_model_route.gd",
            )
        },
        "inline_composer_geometry": geometry,
        "workbench_project": result["native"]["identity"]["project"],
        "stored_executions": result["stored_executions"],
        **routes,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed compact model routes, draft isolation and 3D preview return")


if __name__ == "__main__":
    main()
