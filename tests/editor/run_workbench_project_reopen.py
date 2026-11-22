"""Close and reopen the same editor project against the signed, durable workflow checkpoint."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import httpx
from run_workbench_design_tasks import Tianxuan, copy_editor, create_app, sanitized_environment
from run_workbench_offline_document import serve

COMPONENT = Path(__file__).resolve().parents[2] / "customizations/components/tianxuan"
sys.path[:0] = [str(COMPONENT / name) for name in ("server", "sinan-workorders", "duobao")]

# isort: split
import test_native_project_reopen as checks  # noqa: E402
from native_workflow import NativeWorkflow  # noqa: E402

# This observer only reads the already mounted native session and waits for the
# service's response. The application itself must initiate every recovery request.
OBSERVER = """extends SceneTree

func _initialize() -> void:
    observe.call_deferred()

func observe() -> void:
    var marker := OS.get_environment("R07_OBSERVED")
    var deadline := Time.get_ticks_msec() + 30000
    while Time.get_ticks_msec() < deadline:
        var session := root.find_child("WorkbenchBusinessSession", true, false)
        if session and not session.get_identity().is_empty() and FileAccess.file_exists(marker):
            print("R07_NATIVE=" + JSON.stringify({"pid": OS.get_process_id(), "identity": session.get_identity()}))
            root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
            return
        await create_timer(0.05).timeout
    printerr("No authenticated project recovery response on native startup")
    quit(1)
"""


def editor(engine, project, origin, token, extra, result_prefixes=("A02_NATIVE=", "R07_NATIVE=")):
    env = {k: v for k, v in sanitized_environment(project).items() if not k.startswith("TIANXUAN_")}
    env.update(TIANXUAN_TOKEN=token, TIANXUAN_API=origin, TIANXUAN_PROJECT="studio", **extra)
    with subprocess.Popen(
        [
            engine,
            "--headless",
            "--single-window",
            "--resolution",
            "1440x960",
            "--editor",
            "--path",
            project,
            "--script",
            "res://probe.gd",
        ],
        cwd=project,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ) as proc:
        try:
            output = proc.communicate(timeout=90)[0].decode("utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise
    assert token not in output
    lines = [line.split("=", 1)[1] for line in output.splitlines() if line.startswith(result_prefixes)]
    if proc.returncode or len(lines) != 1 or "SCRIPT ERROR" in output:
        raise RuntimeError(output[-6500:])
    return {"pid": proc.pid, "exit": proc.returncode, "result": json.loads(lines[0])}


@contextmanager
def receiver(h, token, marker):
    app = create_app(h.workflow.domain, native_workflow=h.workflow, native_store=h.workflow.worker.store)
    requests = []

    @app.middleware("http")
    async def observe(request, call_next):
        response = await call_next(request)
        path = request.url.path
        requests.append({"method": request.method, "path": path, "status": response.status_code})
        if path.endswith("/recover-project") and response.status_code == 200:
            assert request.query_params["project"] == "studio"
            marker.touch()
        return response

    with (
        serve(app, 0) as port,
        httpx.Client(
            base_url=f"http://127.0.0.1:{port}", headers={"Authorization": "Bearer " + token}, trust_env=False
        ) as client,
    ):
        h.client = client
        yield str(client.base_url), requests


def exercise(root, executable):
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="R07"\n')
    probe = project / "probe.gd"
    marker = root / "response"
    engine = copy_editor(executable, root / "engine")
    with contextmanager(checks.fixture.__wrapped__)(root) as fixture:
        workflow, actor, tenant, _, _, _ = fixture
        domain = workflow.domain
        token = domain.issue_session(actor)
        with contextmanager(checks.host.__wrapped__)(fixture) as h:
            issue = checks.install(h)
            with patch.dict(
                os.environ,
                TIANXUAN_AUTH_MODE="accounts",
                TIANXUAN_TENANT_ID=tenant,
                TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
            ):
                with receiver(h, token, marker) as (url, first_http):
                    for row in h.issues:
                        h.target(row, criteria=checks.stage.CRITERION)
                    shutil.copyfile(Path(__file__).with_name("workbench_task_confirmations.gd"), probe)
                    first = editor(
                        engine,
                        project,
                        url,
                        token,
                        {"A02_TASK": json.dumps(dict(number=issue["number"], action="confirm", focus_only=True))},
                    )
                    assert marker.exists()
                    original_confirmation = h.detail(issue)["task_confirmation"]
                    assert original_confirmation["status"] == "confirmed"
                    key = h.api("authorize", issue=issue["id"]).raise_for_status().json()
                    assert h.reserve(key).raise_for_status().json()
                    assert h.api("execute", key=key).raise_for_status().json()["state"] == "produced"
                    before = checks.snapshot(h, key)
                    starts = checks.count_processes(h)
                    assert len(starts["workers"]) == 1 and starts["checkers"] == []
                domain.db.close()
                fresh = Tianxuan(str(root / "domain.sqlite"))
                try:
                    h.workflow = NativeWorkflow(
                        fresh,
                        workflow.worker,
                        workflow.runner,
                        workflow.release,
                        workflow.authorize,
                        catalog=workflow.catalog,
                    )
                    probe.write_text(OBSERVER, encoding="utf-8")
                    with receiver(h, token, marker) as (url, reopened_http):
                        runs = []
                        for iteration in range(2):
                            marker.unlink()
                            start = len(reopened_http)
                            run = editor(engine, project, url, token, {"R07_OBSERVED": str(marker)})
                            requests = reopened_http[start:]
                            effects = [r for r in requests if r["method"] in {"POST", "PUT", "PATCH", "DELETE"}]
                            assert [r for r in effects if r["path"].startswith("/api/v1/native/workflow/")] == [
                                dict(path="/api/v1/native/workflow/recover-occupancy", method="POST", status=200),
                                dict(path="/api/v1/native/workflow/recover-project", method="POST", status=200),
                            ]
                            assert not any("confirmation" in r["path"] for r in effects)
                            assert run["result"]["identity"]["id"] == actor and run["result"]["pid"] == run["pid"]
                            received = checks.verify_received(h, key, before)
                            assert received["processes"]["workers"] == starts["workers"]
                            assert received["after"]["candidate"] == before["candidate"]
                            assert h.detail(issue)["task_confirmation"] == original_confirmation
                            assert h.detail(h.issues[1])["task_confirmation"]["status"] == "pending"
                            if iteration == 0:
                                outcome = received
                            else:
                                assert received == outcome
                            runs.append({**run, "startup_writes": effects})
                finally:
                    fresh.db.close()
    with executable.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return dict(
        passed=True,
        mode="compiled headless editor / authenticated loopback / installed deterministic processes",
        editor_sha256=digest,
        initial_editor=first,
        reopened_editors=runs,
        original_confirmation=original_confirmation,
        initial_confirmation_requests=sum(
            r["path"].endswith("/task-confirmation") and r["method"] == "PUT" for r in first_http
        ),
        before_processes=starts,
        **outcome,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with (
        tempfile.TemporaryDirectory(prefix="r07-project-reopen-") as folder,
        patch.dict(os.environ, GONGGONG_WORKSPACE=""),
    ):
        report = exercise(Path(folder), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
