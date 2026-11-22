"""Follow one native workbench confirmation through the installed workflow to a real local process."""

import argparse
import hashlib
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import httpx
from run_workbench_offline_document import serve
from run_workbench_task_confirmations import copy_editor, create_app, run_editor

COMPONENT = Path(__file__).resolve().parents[2] / "customizations/components/tianxuan"
sys.path[:0] = [str(COMPONENT / name) for name in ("server", "sinan-workorders", "duobao")]

# isort: split
from test_native_stage_admission import StageHost, install_stage_probe  # noqa: E402
from test_native_workflow import fixture  # noqa: E402


def exercise(root, executable):
    engine = copy_editor(executable, root / "editor")
    with contextmanager(fixture.__wrapped__)(root) as (workflow, actor, tenant, _, initial, folder):
        domain = workflow.domain
        host = StageHost()
        host.workflow, host.actor = workflow, actor
        host.doc = domain.create_doc(actor, "桥面设计", "拉杆控制桥面\n\n桥面展开动画")["id"]
        domain.design_signoff(actor, host.doc, 1, "程序与动画分别验证")
        proposals = [("程序", "可运行原型", "拉杆切换一次"), ("动画", "动画预览", "第 24 帧桥面展开")]
        tasks = domain.split_design(
            actor,
            host.doc,
            1,
            "studio",
            [
                dict(title=title, paragraph=index, module_id="default", acceptance=criteria)
                for index, (title, _, criteria) in enumerate(proposals, 1)
            ],
            "confirmed-stage-split",
        )
        first, second = tasks
        stages = {task["id"]: stage for task, (_, stage, _) in zip(tasks, proposals, strict=True)}
        host.calls, plan = install_stage_probe(workflow, initial, folder, stage=stages[first["id"]])

        def installed_plan(operator, issue):
            assert operator == actor and issue in stages
            return dict(plan, stage=stages[issue])

        workflow.installed_plan = installed_plan
        token = domain.issue_session(actor)
        modes = dict(
            TIANXUAN_AUTH_MODE="accounts",
            TIANXUAN_TENANT_ID=tenant,
            TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
        )
        with patch.dict(os.environ, modes):
            app = create_app(domain, native_store=workflow.worker.store, native_workflow=workflow)
            with (
                serve(app, 0) as port,
                httpx.Client(
                    base_url=f"http://127.0.0.1:{port}",
                    headers={"Authorization": "Bearer " + token},
                    trust_env=False,
                ) as host.client,
            ):
                for task, (_, stage, criteria) in zip(tasks, proposals, strict=True):
                    host.target(task, stage, criteria)
                    assert host.api("authorize", issue=task["id"]).status_code == 409
                assert host.observations() == []
                selected = run_editor(
                    root, engine, str(host.client.base_url), token, "studio", first["number"], "confirm"
                )
                assert len(selected["selected"]) == 2
                first_confirmation, sibling = [host.detail(task)["task_confirmation"] for task in tasks]
                assert first_confirmation["status"] == "confirmed" and first_confirmation["confirmed_by"] == actor
                assert sibling["status"] == "pending" and sibling["revision"] == 0
                assert host.api("authorize", issue=second["id"]).status_code == 409
                key = host.api("authorize", issue=first["id"]).raise_for_status().json()
                assert host.api("authorize", issue=first["id"]).raise_for_status().json() == key
                assert host.reserve(key).raise_for_status().json() is True
                for _ in range(2):
                    assert host.api("execute", key=key).raise_for_status().json()["state"] == "produced"
                status = host.api("status", key=key).raise_for_status().json()
                stored = json.loads(status["task"])
                grant = stored["source"]["definition"]["stage_authorization"]
                assert grant["issue_id"] == first["id"] and grant["stage"] == stages[first["id"]]
                assert grant["issue_revision"] == first_confirmation["issue_revision"]
                assert grant["confirmation_revision"] == first_confirmation["revision"]
                assert grant["criteria"] == proposals[0][2] and grant["confirmed_by"] == actor
                assert host.observations() == [dict(execution=key, grant=grant)]
                run_editor(root, engine, str(host.client.base_url), token, "studio", first["number"], "revoke")
                revoked = host.detail(first)["task_confirmation"]
                assert revoked["status"] == "revoked" and revoked["revision"] > first_confirmation["revision"]
                assert host.api("authorize", issue=first["id"]).status_code == 409
                assert host.detail(second)["task_confirmation"] == sibling
                assert len(host.observations()) == 1
        with workflow.worker.store._connection() as db:
            rows = db.execute("SELECT execution,payload FROM native_worker_process_closures").fetchall()
            assert len(rows) == 1 and rows[0]["execution"] == key
            closure = json.loads(rows[0]["payload"])
            assert closure["exit_code"] == 0 and not closure["reasons"]
        assert domain.db.execute("SELECT count(*) FROM native_tasks WHERE issue=?", (second["id"],)).fetchone()[0] == 0
    with executable.open("rb") as binary:
        digest = hashlib.file_digest(binary, "sha256").hexdigest()
    return dict(
        passed=True,
        editor_sha256=digest,
        selected=selected["selected"],
        confirmed=first_confirmation,
        sibling=sibling,
        revoked=revoked,
        execution=key,
        grant=grant,
        candidate=json.loads(status["terminal"])["candidate"],
        profile=stored["profile"],
        process_exit=closure["exit_code"],
        process_count=1,
        sibling_tasks=0,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with (
        tempfile.TemporaryDirectory(prefix="confirmed-native-stage-") as folder,
        patch.dict(os.environ, GONGGONG_WORKSPACE=""),
    ):
        result = exercise(Path(folder), args.godot.resolve(strict=True))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
