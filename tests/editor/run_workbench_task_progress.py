"""Compare the module and issue progress controls against a physical worker and its SQLite journal."""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from pathlib import Path
from unittest.mock import patch

import httpx
from run_workbench_confirmed_native_stage import (
    StageHost,
    copy_editor,
    create_app,
    fixture,
    install_stage_probe,
    observe_launches,
    serve,
)
from run_workbench_task_confirmations import sanitized_environment


def run_editor(root, engine, url, token, task):
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="S07"\n', encoding="utf-8")
    for script in ("workbench_issue_detail.gd", "workbench_task_progress.gd"):
        shutil.copyfile(Path(__file__).with_name(script), project / script)
    env = {k: v for k, v in sanitized_environment(root).items() if not k.startswith("TIANXUAN_")}
    env.update(TIANXUAN_API=url, TIANXUAN_PROJECT="studio", TIANXUAN_TOKEN=token, S07_TASK=json.dumps(task))
    result = subprocess.run(
        [str(engine), "--headless", "--editor", "--path", str(project), "--script", "res://workbench_task_progress.gd"],
        cwd=project,
        env=env,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=75,
    )
    output = result.stdout + result.stderr
    assert token not in output, "session credential in editor diagnostics"
    records = [line.removeprefix("S07_NATIVE=") for line in output.splitlines() if line.startswith("S07_NATIVE=")]
    if result.returncode or "SCRIPT ERROR" in output or len(records) != 1:
        raise RuntimeError(output[-5000:])
    return json.loads(records[0])


def verify_visible(text, progress):
    assert progress["id"] in text and progress["stage"] in text and progress["state"] in text
    event_lines = [line for line in text.splitlines() if line.startswith("#")]
    assert event_lines == [
        f"#{event['sequence']}　{event['recorded_at']}　{event['step']}　{event['state']}"
        for event in reversed(progress["events"])
    ]
    if progress["candidate"]:
        assert progress["candidate"] in text


def exercise(root, engine, scenario):
    fail = scenario == "failed"
    with contextmanager(fixture.__wrapped__)(root) as (workflow, actor, tenant, _, initial, folder):
        domain = workflow.domain
        host = StageHost()
        host.doc = domain.create_doc(actor, "运行检查", "程序\n\n动画")["id"]
        domain.design_signoff(actor, host.doc, 1, "可运行原型")
        issue, sibling = domain.split_design(
            actor,
            host.doc,
            1,
            "studio",
            [
                dict(paragraph=i, title=title, module_id="default", acceptance="原型")
                for i, title in enumerate(("程序", "动画"), 1)
            ],
            "s07-split",
        )
        host.calls, _ = install_stage_probe(workflow, initial, folder, stage="原型")
        journal, release = observe_launches(workflow, folder)
        profile = workflow.worker.profiles["local"]
        profile["timeout"] = 90
        if fail:
            with Path(profile["argv"][1]).open("a", encoding="utf-8") as child:
                child.write("\nraise SystemExit(7)\n")
        token = domain.issue_session(actor)
        viewer = scenario == "viewer"
        reader = actor
        editor_token = token
        if viewer:
            member = domain.add_member(actor, "viewer@example.invalid", "fixture-pass", role="viewer")["user_id"]
            reader = member
            domain.share_doc(actor, host.doc, member)
            editor_token = domain.issue_session(member)
        settled = root / "settled"
        with patch.dict(
            os.environ,
            TIANXUAN_AUTH_MODE="accounts",
            TIANXUAN_TENANT_ID=tenant,
            TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
        ):
            app = create_app(domain, native_store=workflow.worker.store, native_workflow=workflow)
            with (
                serve(app, 0) as port,
                httpx.Client(
                    base_url=f"http://127.0.0.1:{port}",
                    headers={"Authorization": "Bearer " + token},
                    timeout=100,
                    trust_env=False,
                ) as host.client,
                ThreadPoolExecutor(max_workers=1) as pool,
            ):
                host.target(issue, stage="原型", criteria="原型")
                host.confirm(issue).raise_for_status()
                key = host.api("authorize", issue=issue["id"]).raise_for_status().json()
                scoped_status = host.client.post(
                    "/api/v1/native/workflow/status", params={"project": "studio"}, json={"key": key}
                )
                assert (
                    scoped_status.status_code == 422
                    and scoped_status.json()["detail"] == "query parameters are not supported"
                )
                assert host.reserve(key).raise_for_status().json() is True

                def execute():
                    result = host.api("execute", key=key).raise_for_status().json()
                    settled.touch()
                    return result

                worker = pool.submit(execute)
                try:
                    deadline = time.monotonic() + 15
                    while not journal.exists() or not journal.read_bytes().endswith(b"\n"):
                        if worker.done() or time.monotonic() > deadline:
                            raise RuntimeError("Missing worker start")
                        time.sleep(0.02)
                    running = host.detail(issue)["execution_progress"]
                    assert running["state"] == "running" and running["events"][-1]["step"] == "workspace.materialize"
                    task = dict(
                        issue=issue["id"],
                        sibling=sibling["id"],
                        number=issue["number"],
                        run=key,
                        release=str(release),
                        settled=str(settled),
                    )
                    if viewer:
                        denied = host.client.post(
                            "/api/v1/native/workflow/status",
                            json={"key": key},
                            headers={"Authorization": "Bearer " + editor_token},
                        )
                        assert denied.status_code == 403
                    views = run_editor(root, engine, str(host.client.base_url), editor_token, task)
                finally:
                    release.touch(exist_ok=True)
                final = host.detail(issue)["execution_progress"]
                assert final == host.api("status", key=key).raise_for_status().json()["progress"]
                assert worker.result()["state"] == final["state"] == ("failed" if fail else "produced")
                assert final["events"][: len(running["events"])] == running["events"]
                assert final["id"] == running["id"] == key and len(host.observations()) == 1
                if fail:
                    assert final["candidate"] is None
                else:
                    assert final["candidate"]
                if fail:
                    assert "进程退出码　7" in views["final_issue"]
                for entry in ("module", "issue"):
                    verify_visible(views["running_" + entry], running)
                    verify_visible(views["final_" + entry], final)
                with closing(sqlite3.connect(root / "domain.sqlite")) as stored:
                    rows = stored.execute(
                        "SELECT sequence, recorded_at, step, state, details FROM native_task_progress WHERE task=? ORDER BY sequence",
                        (key,),
                    ).fetchall()
                assert [
                    dict(sequence=n, recorded_at=at, step=step, state=state, details=json.loads(details))
                    for n, at, step, state, details in rows
                ] == final["events"]
                starts = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
                assert len(starts) == 1 and starts[0]["execution"] == key and starts[0]["pid"] > 0
                return dict(
                    issue=issue["id"],
                    reader_role=domain.actor_context(reader)["role"],
                    status_with_project=scoped_status.status_code,
                    number=issue["number"],
                    run=key,
                    running=running["events"][-1],
                    final=final["events"][-1],
                    candidate=final["candidate"],
                    persisted_events=len(rows),
                    physical_starts=len(starts),
                    views=views,
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    binary = args.godot.resolve(strict=True)
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    with (
        tempfile.TemporaryDirectory(prefix="s07-task-progress-") as temp,
        patch.dict(os.environ, GONGGONG_WORKSPACE=""),
    ):
        root = Path(temp)
        engine = copy_editor(binary, root / "engine")
        results = {}
        for scenario in ("produced", "failed", "viewer"):
            folder = root / scenario
            folder.mkdir()
            results[scenario] = exercise(folder, engine, scenario)
    args.report.write_text(
        json.dumps(dict(passed=True, editor_sha256=digest, scenarios=results), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
