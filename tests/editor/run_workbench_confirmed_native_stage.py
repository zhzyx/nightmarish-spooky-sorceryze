"""Follow one native workbench confirmation through the installed workflow to a real local process."""

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from contextlib import closing, contextmanager
from http.client import HTTPConnection
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


def observe_launches(workflow, folder):
    profile = workflow.worker.profiles["local"]
    probe = Path(profile["argv"][1])
    journal, release = folder / "process-starts.jsonl", folder / "release-worker"
    profile["timeout"] = 30
    profile["env"].update(LAUNCH_JOURNAL=str(journal), RELEASE_WORKER=str(release))
    # The child records its own identity before waiting for both client replays.
    # Append rather than overwrite, so a second physical launch remains visible.
    probe.write_text(
        "import json, os, pathlib, time\n"
        "execution = pathlib.Path(os.environ['NATIVE_CONTEXT']).parent.name\n"
        "with open(os.environ['LAUNCH_JOURNAL'], 'a', encoding='utf-8') as journal:\n"
        "    print(json.dumps(dict(execution=execution, pid=os.getpid())), file=journal)\n"
        "while not pathlib.Path(os.environ['RELEASE_WORKER']).exists():\n"
        "    time.sleep(0.02)\n" + probe.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return journal, release


def replay_launch(host, port, issue, key, journal, release):
    def launches():
        return [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]

    def replay(client):
        def call(operation, **payload):
            return client.post("/api/v1/native/workflow/" + operation, json=payload).raise_for_status().json()

        assert call("authorize", issue=issue["id"]) == key
        current = call("status", key=key)
        assignment = json.loads(current["assignment"])
        assert call("reserve", assignment=assignment, event="replay") is False
        row = call("execute", key=key)
        assert row["id"] == key and row["worker_ref"] == "native-worker:" + key
        return dict(execution=row["id"], worker_ref=row["worker_ref"], state=row["state"], starts=launches())

    headers = {"Authorization": host.client.headers["Authorization"], "Content-Type": "application/json"}
    try:
        with closing(HTTPConnection("127.0.0.1", port, timeout=10)) as first:
            first.request("POST", "/api/v1/native/workflow/execute", json.dumps({"key": key}), headers)
            deadline = time.monotonic() + 10
            while not journal.exists() or not journal.read_bytes().endswith(b"\n"):
                if time.monotonic() >= deadline:
                    raise TimeoutError("Worker did not record its physical start")
                time.sleep(0.02)
            duplicate = replay(host.client)
            # Close the original TCP connection while its response is outstanding.
        with httpx.Client(base_url=host.client.base_url, headers=headers, trust_env=False) as connected:
            reconnected = replay(connected)
            assert reconnected == duplicate and reconnected["state"] == "running"

            def issue_progress():
                detail = (
                    connected
                    .get(f"/api/v1/issues/by-number/{issue['number']}/detail", params={"project": "studio"})
                    .raise_for_status()
                    .json()
                )
                progress = (
                    connected
                    .post("/api/v1/native/workflow/status", json={"key": key})
                    .raise_for_status()
                    .json()["progress"]
                )
                assert detail["execution_progress"] == progress
                return progress

            running = issue_progress()
            assert running["id"] == key and running["state"] == "running"
            assert running["events"][-1]["step"] == "workspace.materialize"
            release.touch()
            settled = connected.post("/api/v1/native/workflow/await-terminal", json={"key": key})
            assert settled.raise_for_status().json()["state"] == "produced"
            terminal = replay(connected)
            produced = issue_progress()
            assert produced["events"][: len(running["events"])] == running["events"]
            assert [event["step"] for event in produced["events"][len(running["events"]) :]] == [
                "process.closed",
                "workspace.collect",
                "candidate.compose",
                "state",
            ]
            assert (
                produced["state"] == "produced"
                and produced["candidate"] == produced["events"][-1]["details"]["candidate"]
            )
            late = (
                connected
                .post(
                    "/api/v1/native/workflow/record",
                    json=dict(
                        assignment={"ticket": key}, event="progress", state="running", receipt=running["events"][-1]
                    ),
                )
                .raise_for_status()
                .json()
            )
            assert late["state"] == "produced" and issue_progress() == produced
    finally:
        release.touch(exist_ok=True)
    (physical,) = launches()
    assert physical["execution"] == key and physical["pid"] > 0
    assert duplicate["starts"] == terminal["starts"] == [physical] and terminal["state"] == "produced"
    return dict(
        duplicate=duplicate,
        reconnected=reconnected,
        after_exit=terminal,
        progress=produced,
        replayed_step=running["events"][-1],
        replay_result=late,
    )


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
        journal, release = observe_launches(workflow, folder)

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
                replay = replay_launch(host, port, first, key, journal, release)
                status = host.api("status", key=key).raise_for_status().json()
                stored = json.loads(status["task"])
                grant = stored["source"]["definition"]["stage_authorization"]
                assert json.loads(status["terminal"])["origin"]["worker_ref"] == replay["after_exit"]["worker_ref"]
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
        replay=replay,
        process_closure=closure,
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
