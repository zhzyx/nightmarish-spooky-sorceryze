"""Load the pre-U13 Godot layout and follow its issue card to an existing native consultation."""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import tempfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from run_workbench_issue_consultation import ROOT, exercise


def verify_routes(engine, project, env, store, actor, issues, native):
    # U11 has already created two identically titled issues and sent distinct turns from this editor.
    fixtures = []
    for old_number, issue, record in zip((791, 803), issues, native["records"], strict=True):
        url = f"https://github.com/old/studio/issues/{old_number}"
        store.link_external(actor, "tianshu", url, "issue", issue["id"])
        store.link_external(actor, "tianshu", "https://github.com/old/studio/issues/9998", "issue", issue["id"])
        assert old_number != issue["number"]
        fixtures.append(record | {"old_number": old_number, "url": url, "title": issue["title"]})

    # A second connection must observe the links before an editor process uses them.
    with closing(sqlite3.connect(project.parent / "domain.db")) as reader:
        assert reader.execute("SELECT COUNT(*) FROM external_links WHERE system='tianshu'").fetchone() == (4,)
    assert fixtures[0]["title"] == fixtures[1]["title"] and fixtures[0]["chat"] != fixtures[1]["chat"]
    shutil.copyfile(Path(__file__).with_name("workbench_legacy_routes.gd"), project / "legacy.gd")
    layout = project / ".godot/editor/editor_layout.cfg"
    layout.parent.mkdir(exist_ok=True, parents=True)
    baseline = ROOT / "data-collection/gonggong-ai-workbench-plan1-u02.json"
    order = json.loads(baseline.read_text(encoding="utf-8"))["layout_phases"][0]["saved_order"]
    phases = []
    for phase, selection in [
        ("legacy_chat", "AIChatMainScreen"),
        ("legacy_tianshu", "DaqianMainScreen"),
        ("restart", None),
        ("other_project", None),
        ("unchanged", "Script"),
    ]:
        if selection:
            layout.write_text(
                '[docks]\ndock_12="'
                + ",".join(order)
                + '"\ndock_12_selected_tab_idx='
                + str(order.index(selection))
                + "\n",
                encoding="utf-8",
            )
        loaded = layout.read_bytes()
        run = subprocess.run(
            [str(engine), "--headless", "--editor", "--path", str(project), "--script", "res://legacy.gd"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            cwd=project.parent,
            timeout=90,
            env=env
            | {
                "TIANXUAN_PROJECT": "u13/other" if phase == "other_project" else env["TIANXUAN_PROJECT"],
                "U13_PHASE": phase,
                "U13_ISSUES": json.dumps(fixtures),
            },
        )
        output = run.stdout + run.stderr
        if env["TIANXUAN_TOKEN"] in output:
            raise AssertionError("Fixture credential appeared in editor diagnostics")
        lines = [line.removeprefix("U13_NATIVE=") for line in output.splitlines() if line.startswith("U13_NATIVE=")]
        assert run.returncode == 0 and len(lines) == 1 and "SCRIPT ERROR" not in output, output[-6500:]
        saved = layout.read_text(encoding="utf-8")
        phases.append({
            "phase": phase,
            "loaded_layout_sha256": hashlib.sha256(loaded).hexdigest(),
            "saved_order": re.search(r'^dock_12="([^"]+)"', saved, re.M)[1],
            "saved_selection": int(re.search(r"^dock_12_selected_tab_idx=(\d+)", saved, re.M)[1]),
            "saved_sidebar": "sidebar_visible=true" in saved,
            "observed": json.loads(lines[0]),
        })
    return {"legacy_saved_order": order, "fixtures": fixtures, "phases": phases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    binary = args.godot.resolve(strict=True)
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}), tempfile.TemporaryDirectory(prefix="u13-") as directory:
        result = exercise(Path(directory), binary, verify_routes)
    artifact = binary.with_name(binary.name.replace(".console.exe", ".exe"))
    with artifact.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    report = {
        "request_id": "gonggong-ai-workbench-plan1-u13",
        "issue_number": 1791,
        "platform": platform.platform(),
        "mode": "headless",
        "prior_layout_evidence": "data-collection/gonggong-ai-workbench-plan1-u02.json",
        "workbench_identity": result["native"]["identity"],
        "stored_executions": result["stored_executions"],
        "editor_sha256": digest,
        "result": "passed",
        "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        **result["routes"],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed previous layout, saved restart, and linked issue consultation checks")


if __name__ == "__main__":
    main()
