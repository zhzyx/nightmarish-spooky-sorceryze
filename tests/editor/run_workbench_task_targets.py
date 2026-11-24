"""Save independent execution targets on two signed-design issues through the native workbench."""

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

PROJECT = "a01/bridge"


def run_editor(root, engine, url, token, number, proposals):
    project = root / f"issue-{number}"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="A01"\n', encoding="utf-8")
    shutil.copyfile(Path(__file__).with_name("workbench_task_targets.gd"), project / "probe.gd")
    env = {k: v for k, v in sanitized_environment(project).items() if not k.startswith("TIANXUAN_")}
    env.update(
        TIANXUAN_API=url,
        TIANXUAN_PROJECT=PROJECT,
        TIANXUAN_TOKEN=token,
        A01_TASK=json.dumps(dict(number=number, proposals=proposals)),
    )
    result = subprocess.run(
        [str(engine), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
        cwd=project,
        env=env,
        capture_output=True,
        timeout=80,
    )
    output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
    assert token not in output, "session credential in editor output"
    lines = [s.removeprefix("A01_NATIVE=") for s in output.splitlines() if s.startswith("A01_NATIVE=")]
    if result.returncode or len(lines) != 1 or "SCRIPT ERROR" in output:
        raise RuntimeError(output[-6500:])
    return json.loads(lines[0])


def exercise(root, binary):
    engine = copy_editor(binary, root / "engine")
    database = str(root / "a01.db")
    store = Tianxuan(database)
    account = store.register("Studio", "program@example.invalid", secrets.token_urlsafe(24))
    program = account["user_id"]
    animator = store.add_member(program, "animation@example.invalid", secrets.token_urlsafe(24))["user_id"]
    program_token = store.issue_session(program)
    animation_token = store.issue_session(animator)
    headers = {"Authorization": "Bearer " + program_token}
    animation_headers = {"Authorization": "Bearer " + animation_token}
    doc_id = store.create_doc(program, "桥面机关", "控制拉杆\n\n桥面运动")["id"]
    items = []
    for index, name in enumerate(["程序", "动画"], 1):
        mod = store.create_business_module(program, PROJECT, name, call_id=f"module-{index}")
        items.append(dict(title=name, paragraph=index, module_id=mod["id"], acceptance=name + "模块符合拉杆设计"))
    route = f"/api/v1/docs/{doc_id}/versions/1"
    modes = dict(
        TIANXUAN_AUTH_MODE="accounts",
        TIANXUAN_TENANT_ID=account["tenant_id"],
        TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
    )
    with patch.dict(os.environ, modes):
        try:
            with (
                serve(create_app(store), 0) as port,
                httpx.Client(
                    base_url=f"http://127.0.0.1:{port}", headers=headers, params={"project": PROJECT}, trust_env=False
                ) as client,
            ):
                signoff = (
                    client
                    .post(route + "/signoff", json={"acceptance": "拉杆控制开桥，桥面完成展开"})
                    .raise_for_status()
                    .json()["signoff"]
                )
                split = dict(call_id="split-at-v1", items=items)
                tasks = client.post(route + "/tasks", json=split).raise_for_status().json()["tasks"]
                assert client.post(route + "/tasks", json=split).json()["tasks"] == tasks
                first, second = tasks
                stable_sources = client.get(route + "/tasks").json()["tasks"]
                assert [row["id"] for row in stable_sources] == [first["id"], second["id"]]
                assert (
                    client.patch(f"/api/v1/docs/{doc_id}", json={"body_md": "后续修订", "expected_version": 1}).json()[
                        "version"
                    ]
                    == 2
                )
                issue_root = f"/api/v1/issues/{second['id']}"
                client.put(
                    issue_root + "/assignee", json={"assignee_id": animator, "expected_assignee_id": None}
                ).raise_for_status()
                prototype = dict(stage="可运行原型", criteria="拉动拉杆后只发出一次开桥事件", revision=1)
                missing = dict(stage="动画预览", criteria="　 ", revision=1)
                preview = dict(stage="动画预览", criteria="播放预览时桥面在第 24 帧完全展开", revision=2)
                program_rows = run_editor(
                    root, engine, str(client.base_url), program_token, first["number"], [prototype]
                )
                animation_rows = run_editor(
                    root, engine, str(client.base_url), animation_token, second["number"], [missing, preview]
                )
                created = program_rows[0]["target"]
                returned, corrected = (r["target"] for r in animation_rows)
                for task, target, proposal, owner in (
                    (first, created, prototype, program),
                    (second, returned, missing, animator),
                    (second, corrected, preview, animator),
                ):
                    assert (target["issue_id"], target["document_id"], target["version"], target["revision"]) == (
                        task["id"],
                        doc_id,
                        1,
                        proposal["revision"],
                    )
                    assert (target["responsible_user"], target["stage"], target["criteria"]) == (
                        owner,
                        proposal["stage"],
                        proposal["criteria"].strip(),
                    )
                assert created["status"] == corrected["status"] == "defined" and returned["status"] == "returned"
                assert returned["return_reason"] and animation_rows[0]["feedback"] == returned["return_reason"]
                for row in (program_rows[0], animation_rows[-1]):
                    assert f"来源设计 v1 · 目标修订 {int(row['target']['revision'])}" in row["feedback"]
                for row in program_rows + animation_rows:
                    assert (row["stage"], row["criteria"]) == (row["target"]["stage"], row["target"]["criteria"])
                comments = client.get(issue_root + "/comments").json()["comments"]
                assert len(comments) == 1
                assert (comments[0]["id"], comments[0]["body"], comments[0]["author"]) == (
                    returned["return_comment_id"],
                    returned["return_reason"],
                    animator,
                )
                payload = dict(
                    document_id=doc_id,
                    version=1,
                    stage=preview["stage"],
                    criteria=preview["criteria"],
                    expected_revision=1,
                )
                endpoint = issue_root + "/task-target"
                assert client.put(endpoint, json=payload, headers=animation_headers).json() == corrected
                assert client.put(endpoint, json=payload, headers=headers).status_code == 403
                assert client.put(endpoint, json=payload | {"version": 2}, headers=animation_headers).status_code == 409
                assert (
                    client.put(
                        endpoint, json=payload | {"criteria": "覆盖旧目标"}, headers=animation_headers
                    ).status_code
                    == 409
                )
                assert (
                    client.put(
                        endpoint, json=payload, params={"project": "other"}, headers=animation_headers
                    ).status_code
                    == 404
                )
        finally:
            store.db.close()

        fresh = Tianxuan(database)
        try:
            with (
                serve(create_app(fresh), 0) as port,
                httpx.Client(
                    base_url=f"http://127.0.0.1:{port}", headers=headers, params={"project": PROJECT}, trust_env=False
                ) as client,
            ):
                assert client.get(route + "/signoff").json()["signoff"] == signoff
                assert client.get(route + "/tasks").json()["tasks"] == stable_sources
                for task, target in ((first, created), (second, corrected)):
                    path = f"/api/v1/issues/by-number/{task['number']}/detail"
                    detail = client.get(path).raise_for_status().json()
                    assert detail["task_target"] == target and detail["design_source"] == task["design_source"]
                    assert detail["status"] == "backlog"
                assert client.get(issue_root + "/comments").json()["comments"] == comments
                fresh.set_visibility(program, doc_id, "private")
                hidden = client.get(path, headers=animation_headers).raise_for_status().json()
                assert hidden["design_source"] is None and hidden["task_target"] is None
                assert client.put(endpoint, json=payload, headers=animation_headers).status_code == 404
        finally:
            fresh.db.close()
    return dict(
        state="passed",
        editor_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
        signoff=signoff,
        design_tasks=stable_sources,
        program=program_rows,
        animation=animation_rows,
        return_comment=comments[0],
        service_restart_readback=True,
        source_visibility_enforced=True,
        changed_design_version=2,
        replay_same_record=True,
        wrong_actor=403,
        stale_target=409,
        wrong_version=409,
        wrong_project=404,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="a01-targets-") as temp, patch.dict(os.environ, GONGGONG_WORKSPACE=""):
        report = exercise(Path(temp), args.godot.resolve())
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
