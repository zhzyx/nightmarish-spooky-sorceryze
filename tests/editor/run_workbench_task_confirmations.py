"""Select two tasks in the native workbench and authorize only the first against an authenticated service."""

import argparse
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx
from run_workbench_design_tasks import Tianxuan, copy_editor, create_app, sanitized_environment
from run_workbench_offline_document import serve


def run_editor(root, engine, url, token, project_name, number, action, *, focus_only=False, task_count=2):
    """Read the design's rows and click either the first selected task or the specified issue."""
    if action not in {"read", "confirm", "revoke"}:
        raise ValueError("unsupported native action")
    with tempfile.TemporaryDirectory(prefix="a02-project-", dir=root) as directory:
        project = Path(directory)
        (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="A02"\n', encoding="utf-8")
        shutil.copyfile(Path(__file__).with_name("workbench_task_confirmations.gd"), project / "probe.gd")
        env = {k: v for k, v in sanitized_environment(project).items() if not k.startswith("TIANXUAN_")}
        env.update(
            TIANXUAN_API=url,
            TIANXUAN_PROJECT=project_name,
            TIANXUAN_TOKEN=token,
            A02_TASK=json.dumps(dict(number=number, action=action, focus_only=focus_only, task_count=task_count)),
        )
        result = subprocess.run(
            [
                str(engine),
                "--headless",
                "--single-window",
                "--resolution",
                "1440x960",
                "--editor",
                "--path",
                directory,
                "--script",
                "res://probe.gd",
            ],
            cwd=project,
            env=env,
            capture_output=True,
            timeout=90,
        )
    output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
    assert token not in output, "session credential in editor output"
    lines = [s.removeprefix("A02_NATIVE=") for s in output.splitlines() if s.startswith("A02_NATIVE=")]
    if result.returncode or len(lines) != 1 or "SCRIPT ERROR" in output:
        raise RuntimeError(output[-6500:])
    return json.loads(lines[0])


def exercise(root, binary):
    project = "a02/bridge"
    engine = copy_editor(binary, root / "engine")
    database = str(root / "a02.db")
    store = Tianxuan(database)
    account = store.register("Studio", "program@example.invalid", secrets.token_urlsafe(24))
    user = account["user_id"]
    token = store.issue_session(user)
    doc = store.create_doc(user, "桥面机关", "控制拉杆\n\n桥面运动")["id"]
    store.design_signoff(user, doc, 1, "拉杆控制开桥")
    proposals = [("程序", "原型", "拉动拉杆一次开桥"), ("动画", "预览", "第24帧完全展开")]
    items = [
        dict(title=title, paragraph=i, module_id="default", acceptance=criteria)
        for i, (title, _, criteria) in enumerate(proposals, 1)
    ]
    tasks = store.split_design(user, doc, 1, project, items, "a02-split")
    for task, (_, stage, criteria) in zip(tasks, proposals, strict=True):
        store.set_task_target(user, task["id"], project, doc, 1, 0, stage, criteria)
    store.db.close()
    modes = dict(
        TIANXUAN_AUTH_MODE="accounts",
        TIANXUAN_TENANT_ID=account["tenant_id"],
        TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
    )
    runs = {}
    records = {}
    with patch.dict(os.environ, modes):
        for action in ("confirm", "read", "revoke"):
            fresh = Tianxuan(database)
            try:
                with (
                    serve(create_app(fresh), 0) as port,
                    httpx.Client(
                        base_url=f"http://127.0.0.1:{port}",
                        headers={"Authorization": "Bearer " + token},
                        params={"project": project},
                        trust_env=False,
                    ) as client,
                ):
                    runs[action] = run_editor(
                        root, engine, str(client.base_url), token, project, tasks[0]["number"], action
                    )
                    rows = runs[action]["after"]
                    assert len(runs[action]["selected"]) == (0 if action == "read" else 2)
                    for row, (_, stage, criteria) in zip(rows, proposals, strict=True):
                        assert stage in row["label"] and criteria in row["label"]
                    after = [
                        client.get(f"/api/v1/issues/by-number/{task['number']}/detail").raise_for_status().json()
                        for task in tasks
                    ]
                    first, second = records[action] = [item["task_confirmation"] for item in after]
                    assert first["status"] == ("revoked" if action == "revoke" else "confirmed")
                    assert first["confirmed_by"] == (None if action == "revoke" else user)
                    assert first["issue_revision"] == after[0]["revision"]
                    assert second["status"] == "pending" and second["revision"] == 0 and second["confirmed_by"] is None
                    assert "待确认" in rows[1]["label"] and all(item["status"] == "backlog" for item in after)
                    assert ("已撤销" if action == "revoke" else user) in rows[0]["label"]
                    if action == "read":
                        assert records["read"] == records["confirm"]
                        assert [row["label"] for row in rows] == [row["label"] for row in runs["confirm"]["after"]]
            finally:
                fresh.db.close()
    return dict(
        state="passed", editor_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(), runs=runs, records=records
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with (
        tempfile.TemporaryDirectory(prefix="a02-confirmations-") as temp,
        patch.dict(os.environ, GONGGONG_WORKSPACE=""),
    ):
        report = exercise(Path(temp), args.godot.resolve())
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
