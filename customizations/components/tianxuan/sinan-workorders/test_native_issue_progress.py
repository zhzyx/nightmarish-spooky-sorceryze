"""Verify issue-scoped progress against signed local work and persistent worker receipts."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
import test_native_entry_context
import test_native_stage_admission
from api import create_app
from fastapi.testclient import TestClient
from native_store import NativeStoreError
from native_workflow import NativeWorkflow
from test_native_stage_stop import CRITERION, install_preview
from tianxuan_core import Tianxuan

fixture = test_native_stage_admission.fixture
host = test_native_stage_admission.host
live_context = test_native_entry_context.live_context


def test_installed_context_tool_reports_only_receipt_references(live_context):
    entry, client, _, issue = live_context
    response = client.resolve({"op": "manifest", "cursor": None})
    progress = entry.workflow.issue_detail(client.binding["actor"], issue["project"], issue["number"])[
        "execution_progress"
    ]
    step = progress["events"][-1]
    assert progress["id"] == client.execution and step["step"] == "context.manifest"
    assert step["details"] == {name: response[name] for name in ("result_id", "response_sha256")}


def start(host, *, preview=False):
    issue = host.issues[0]
    if preview:
        install_preview(host)
    host.target(issue, criteria=CRITERION if preview else "preview visible")
    host.confirm(issue).raise_for_status()
    key = host.api("authorize", issue=issue["id"]).raise_for_status().json()
    assert host.reserve(key).raise_for_status().json()
    return issue, key


def test_stage_progress_survives_reopen_and_exact_late_receipt(host, record_property):
    issue, key = start(host, preview=True)
    host.api("execute", key=key).raise_for_status()
    reached = host.api("verify-stage", key=key).raise_for_status().json()
    progress = host.detail(issue)["execution_progress"]
    assert progress["stage"] == "preview" and reached["state"] == progress["state"] == "stage-reached"
    assert reached["candidate"] == progress["candidate"]
    assert progress["worker_ref"] == "native-worker:" + key
    assert progress["events"][-1]["details"]["modules"] == reached["modules"]
    assert [e["sequence"] for e in progress["events"]] == list(range(1, len(progress["events"]) + 1))
    assert host.detail(host.issues[1])["execution_progress"] is None
    original = host.workflow
    domain = Tianxuan(str(host.calls.parent / "domain.sqlite"))
    try:
        restored = NativeWorkflow(domain, original.worker, original.runner, original.release, original.authorize)
        with TestClient(
            create_app(domain, native_store=original.worker.store, native_workflow=restored),
            headers=host.client.headers,
        ) as client:
            host.client = client
            assert host.api("status", key=key).json()["progress"] == progress
            step = next(e for e in progress["events"] if e["step"] == "workspace.materialize")
            restored._record_step(key, step["step"], step["details"])
            with pytest.raises(NativeStoreError, match="rebound"):
                restored._record_step(key, step["step"], {})
            assert (
                host.api("reconcile", key=key).json()["progress"]
                == host.detail(issue)["execution_progress"]
                == progress
            )
            domain.set_visibility(host.actor, host.doc, "private")
            member = domain.add_member(host.actor, "progress@example.invalid", "fixture-pass")["user_id"]
            client.headers["Authorization"] = "Bearer " + domain.issue_session(member)
            assert host.detail(issue)["execution_progress"] is None
            assert host.api("status", key=key).status_code == 403
            record_property(
                "reopened",
                json.dumps({
                    "execution": key,
                    "candidate": reached["candidate"],
                    "stage": progress["stage"],
                    "events": len(progress["events"]),
                    "state": progress["state"],
                    "replayed": step,
                    "same_history_after_replay": True,
                    "private_progress": None,
                    "private_status": 403,
                }),
            )
    finally:
        domain.db.close()


def test_late_worker_completion_preserves_verified_stage(host):
    issue, key = start(host, preview=True)
    w = host.workflow
    worker_run = w.worker.run
    closed, release = threading.Event(), threading.Event()

    def delay_reply(task, execution):
        terminal = worker_run(task, execution)
        closed.set()
        assert release.wait(15)
        return terminal

    w.worker.run = delay_reply
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(w.execute, host.actor, key)
        try:
            assert closed.wait(15)
            assert w.reconcile(host.actor, key)["state"] == "produced"
            assert w.verify_stage(host.actor, key)["state"] == "stage-reached"
            settled = host.detail(issue)["execution_progress"]
        finally:
            release.set()
        assert future.result(timeout=15)["state"] == "stage-reached"
    assert host.detail(issue)["execution_progress"] == settled


def test_failed_process_has_no_artifact(host):
    host.workflow.worker.profiles["local"]["argv"][1:] = ["-c", "raise SystemExit(7)"]
    issue, key = start(host)
    failed = host.api("execute", key=key).raise_for_status().json()
    progress = host.detail(issue)["execution_progress"]
    assert failed["state"] == progress["state"] == "failed" and progress["candidate"] is None
    closed = next(e for e in progress["events"] if e["step"] == "process.closed")
    assert closed["details"] == {"exit_code": 7, "transcript": failed["transcript"]}
    assert all(e["step"] != "candidate.compose" for e in progress["events"])


def test_legacy_execution_starts_with_observed_snapshot(host):
    issue, key = start(host)
    terminal = host.api("execute", key=key).raise_for_status().json()
    original = host.workflow
    with original._transaction() as db:
        db.execute("DROP TRIGGER native_progress_created")
        db.execute("DROP TRIGGER native_progress_changed")
        db.execute("DROP TABLE native_task_progress")
    for _ in range(2):
        restored = NativeWorkflow(
            original.domain, original.worker, original.runner, original.release, original.authorize
        )
        history = restored.issue_detail(host.actor, "studio", issue["number"])["execution_progress"]
        assert history["candidate"] == terminal["candidate"] and history["state"] == "produced"
        (event,) = history["events"]
        assert (event["sequence"], event["step"], event["state"]) == (1, "snapshot", "produced")
