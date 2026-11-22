"""Exact local operation replay, authorization and side-effect checks at a paused run."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

import pytest
from native_store import NativeStoreError
from native_workflow import NativeWorkflow
from test_native_stage_admission import host  # noqa: F401
from test_native_stage_stop import drive, install_preview, signed
from test_native_workflow import fixture, reserve, task  # noqa: F401
from tianxuan_core import Tianxuan

# ruff: noqa: F811


def command(workflow, actor, issue, key, action, expected=None):
    progress = workflow.status(actor, key)["progress"]
    revision = progress["control"]["revision"] if expected is None else expected
    return workflow.control_run(actor, action, issue["id"], key, revision), revision


@pytest.mark.parametrize("reserved", [False, True])
def test_pause_before_process_or_reservation_and_restart(fixture, reserved):
    w, actor, *_, folder = fixture
    key, issue = task(fixture, "a")
    if reserved:
        reserve(fixture, key)
    paused, revision = command(w, actor, issue, key, "pause")
    assert paused["control"]["state"] == "paused" and w.execute(actor, key)["state"] == "paused"
    assert command(w, actor, issue, key, "pause", revision)[0] == paused
    assert not (w.worker.root / key).exists()
    domain = Tianxuan(str(folder / "domain.sqlite"))
    with closing(domain.db):
        other = NativeWorkflow(domain, w.worker, w.runner, w.release, w.authorize, catalog=w.catalog)
        assert other.status(actor, key)["progress"] == paused
        (w.worker.root / key).mkdir()
        with pytest.raises(NativeStoreError, match="Unresolved worker"):
            command(other, actor, issue, key, "resume")
        assert other.status(actor, key)["state"] == "paused"
        (w.worker.root / key).rmdir()
        resumed, generation = command(other, actor, issue, key, "resume")
        assert resumed["state"] == "ready"
        assert command(w, actor, issue, key, "resume", generation)[0] == resumed
        # A delayed retry of the first pause never changes this newer decision.
        assert command(w, actor, issue, key, "pause", revision)[0] == resumed
        reserve(fixture, key)
        terminal = other.execute(actor, key)
        assert terminal["state"] == "produced" and terminal["exit_code"] == 0


def test_signed_pause_rejects_revoked_confirmation_and_wrong_project(host):
    h = host
    issue = h.issues[0]
    h.target(issue)
    h.confirm(issue).raise_for_status()
    key = h.api("authorize", issue=issue["id"]).raise_for_status().json()
    control = h.detail(issue)["execution_progress"]["control"]
    payload = dict(issue=issue["id"], key=key, expected=control["revision"])
    assert h.client.post("/api/v1/native/workflow/pause?project=other", json=payload).status_code == 409
    paused = h.api("pause", **payload).raise_for_status().json()
    h.confirm(issue, "revoked").raise_for_status()
    assert h.api("resume", **dict(payload, expected=paused["control"]["revision"])).status_code == 409
    assert h.api("execute", key=key).json()["state"] == "paused"
    assert h.observations() == []


def test_resume_rejects_changed_worker_terminal(fixture):
    w, actor, *_ = fixture
    key, issue = task(fixture, "a")
    reserve(fixture, key)
    original = w.worker.run

    def finish(contract, execution):
        result = original(contract, execution)
        command(w, actor, issue, key, "pause")
        return result

    w.worker.run = finish
    assert w.execute(actor, key)["state"] == "paused"
    row = w.status(actor, key)
    altered = dict(json.loads(row["terminal"]), candidate="0" * 64)
    with w._transaction() as db:
        db.execute("UPDATE native_tasks SET terminal=? WHERE id=?", (json.dumps(altered), key))
    with pytest.raises(NativeStoreError, match="side effects differ"):
        command(w, actor, issue, key, "resume")
    assert w.status(actor, key)["state"] == "paused"


@pytest.mark.parametrize("operation", ["pause", "cancel"])
def test_sinan_observes_requested_stop_and_continues_review_without_relaunch(host, operation):
    h = host
    issue = install_preview(h)
    profile = h.workflow.worker.profiles["local"]
    profile["timeout"] = 20
    probe = Path(profile["argv"][1])
    started, release = probe.with_suffix(".started"), probe.with_suffix(".release")
    probe.write_text(
        "import pathlib, time\n"
        f"pathlib.Path({str(started)!r}).touch(exist_ok=False)\n"
        f"while not pathlib.Path({str(release)!r}).exists(): time.sleep(.01)\n" + probe.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    key = signed(h, issue)
    with ThreadPoolExecutor(1) as pool:
        owner = pool.submit(drive, h)
        try:
            deadline = time.monotonic() + 10
            while not started.exists():
                assert time.monotonic() < deadline and not owner.done()
                time.sleep(0.02)
            decision, _ = command(h.workflow, h.actor, issue, key, operation)
            assert decision["control"]["state"] in {"pausing", "canceling"}
            if operation == "pause":
                release.touch()
            result = owner.result(timeout=20)["result"]
        finally:
            release.touch(exist_ok=True)
    (item,) = result["results"]
    assert not result["errors"] and not result["deliveries"] and not result.get("stages")
    assert item["state"] == item["receipt"]["controlState"] == ("paused" if operation == "pause" else "cancelled")
    if operation == "pause":
        command(h.workflow, h.actor, issue, key, "resume")
    next_run = drive(h)
    assert next_run["calls"].count("execute") == 0
    assert next_run["calls"].count("verify-stage") == (1 if operation == "pause" else 0)
