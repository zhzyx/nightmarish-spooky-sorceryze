"""Use the installed HTTP dispatcher and real worker to distinguish busy storage from lost replies."""

import asyncio
import json
import os
import shutil
import sqlite3
from pathlib import Path

import pytest
import test_native_stage_stop
from native_execution_host import SharedSinanProcess, WorkflowService
from native_store import NativeStoreError
from starlette.responses import JSONResponse
from test_native_stage_stop import drive, install_preview, signed
from tianxuan_core import StorageBusy

fixture = test_native_stage_stop.fixture
host = test_native_stage_stop.host


def observations(host, key):
    with host.workflow.domain._connection_lock:
        rows = host.workflow.domain.db.execute(
            "SELECT payload FROM events WHERE type='native.execution-recovery' ORDER BY rowid"
        ).fetchall()
    return [item for (raw,) in rows if (item := json.loads(raw))["id"] == key]


def test_busy_storage_retries_only_the_original_reservation(host, monkeypatch, record_property):
    h = host
    issue = install_preview(h)
    key = signed(h, issue)
    w = h.workflow
    original = w.execute
    calls = []

    def busy_once(actor, execution):
        calls.append(execution)
        if len(calls) == 1:
            database = w.domain.db.execute("PRAGMA database_list").fetchone()[2]
            blocker = sqlite3.connect(database)
            previous = w.domain.db.execute("PRAGMA busy_timeout").fetchone()[0]
            try:
                blocker.execute("BEGIN IMMEDIATE")
                w.domain.db.execute("PRAGMA busy_timeout=5")
                return original(actor, execution)
            finally:
                blocker.close()
                w.domain.db.execute(f"PRAGMA busy_timeout={previous}")
        return original(actor, execution)

    monkeypatch.setattr(w, "execute", busy_once)
    run = drive(h)["result"]
    assert run["errors"] == [] and calls == [key, key]
    assert [item["execution"] for item in h.observations()] == [key]
    assert h.api("status", key=key).json()["state"] == "stage-reached"
    (recovery,) = observations(h, key)
    assert (recovery["state"], recovery["reason"], recovery["next_action"]) == (
        "reserved",
        "storage-busy",
        "retry-same-execution",
    )
    assert recovery["known_effects"] == {"reservation_recorded": True, "exit_code": None, "candidate": None}
    record_property("observation", json.dumps({"calls": calls, "starts": h.observations(), "recovery": recovery}))


def test_lost_execute_response_reads_original_before_any_further_effect(host, monkeypatch, record_property):
    h = host
    issue = install_preview(h)
    key = signed(h, issue)
    inner = h.client.app
    operations = []

    async def transport(scope, receive, send):
        if scope["type"] != "http":
            return await inner(scope, receive, send)
        operation = scope["path"].rsplit("/", 1)[-1]
        operations.append(operation)
        if operation != "execute":
            return await inner(scope, receive, send)
        replies = []

        async def withhold(message):
            replies.append(message)

        await inner(scope, receive, withhold)
        assert replies[0]["status"] == 200
        await JSONResponse({"detail": "response unavailable"}, status_code=503)(scope, receive, send)

    monkeypatch.setattr(h.client, "app", transport)
    result = drive(h)["result"]
    assert result["errors"] == [] and operations.count("execute") == 1
    assert operations[operations.index("execute") + 1] == "execution-readback"
    assert [item["execution"] for item in h.observations()] == [key]
    (recovery,) = observations(h, key)
    assert result["recoveries"] == [recovery]
    assert recovery["reason"] == "response-unknown" and recovery["next_action"] == "read-original-receipt"
    assert recovery["known_effects"]["candidate"] == result["stages"][0]["candidate"]
    assert recovery["known_effects"]["exit_code"] == 0
    record_property(
        "observation", json.dumps({"operations": operations, "starts": h.observations(), "recovery": recovery})
    )


@pytest.mark.parametrize("external_reservation", [False, True])
def test_busy_before_launch_stops_after_one_retry(host, monkeypatch, record_property, external_reservation):
    h = host
    issue = install_preview(h)
    key = signed(h, issue)
    w = h.workflow
    offers = []

    def offer(db, task, execution):
        offers.append(execution)
        return True

    if external_reservation:
        monkeypatch.setattr(w.worker, "reserve", offer, raising=False)
    assert w.reserve(
        h.actor,
        {
            "ticket": key,
            "sourceSnapshot": w.inspect(h.actor)["snapshot"]["sourceSnapshots"][0],
            "model": {"id": "local"},
        },
    )
    calls = []

    def busy(actor, execution):
        calls.append(execution)
        raise StorageBusy("storage busy")

    monkeypatch.setattr(w, "execute", busy)
    with pytest.raises(StorageBusy):
        w.execute_receipt(h.actor, key)
    assert offers == ([key] if external_reservation else [])
    assert calls == ([key] if external_reservation else [key, key]) and not h.observations()
    actions = [item["next_action"] for item in observations(h, key)]
    assert actions == ([] if external_reservation else ["retry-same-execution"]) + ["read-original-receipt"]
    record_property("observation", json.dumps({"calls": calls, "offers": offers, "starts": [], "actions": actions}))


def test_installed_pipe_recovers_only_its_own_execution(host, record_property):
    h = host
    key = signed(h, install_preview(h))
    token = h.workflow.domain.issue_session(h.actor)

    def authorize_entry():
        assert h.workflow.domain.user_for_token(token) == h.actor

    port = WorkflowService(h.workflow, h.actor, authorize_entry, [h.issues[0]["id"]])
    outside = WorkflowService(h.workflow, h.actor, authorize_entry, [h.issues[1]["id"]])
    for operation in ("execution-readback", "record-execution-fault"):
        with pytest.raises(NativeStoreError, match="outside this entry"):
            asyncio.run(outside(operation, {"key": key}))
        denied = h.client.post(
            "/api/v1/native/workflow/" + operation, json={"key": key}, headers={"Authorization": "Bearer expired"}
        )
        assert denied.status_code == 401
    assert not observations(h, key)
    calls = []

    async def lost_reply(operation, payload):
        calls.append(operation)
        result = await port(operation, payload)
        if operation == "execute":
            raise ConnectionError("lost reply")
        return result

    async def run():
        driver = SharedSinanProcess(
            [shutil.which("node"), str(Path(__file__).with_name("native_entry_driver.mjs"))],
            {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR"}},
        )
        try:
            result = await asyncio.wait_for(driver.run(lost_reply), 20)
        finally:
            closed = await driver.close()
            assert closed["physical_terminal"] and closed["exit_code"] == 0

        return result, closed

    result, closed = asyncio.run(run())
    assert not result["errors"] and result["stages"][0]["state"] == "stage-reached"
    assert calls.count("execute") == 1 and calls[calls.index("execute") + 1] == "execution-readback"
    assert [item["execution"] for item in h.observations()] == [key]
    assert observations(h, key) == result["recoveries"]
    record_property(
        "observation",
        json.dumps({
            "calls": calls,
            "recovery": result["recoveries"][0],
            "starts": h.observations(),
            "closure": closed,
        }),
    )


def test_readback_while_storage_is_busy(host, record_property):
    h = host
    key = signed(h, install_preview(h))
    assert h.reserve(key).json() is True
    assert h.api("execute", key=key).json()["state"] == "produced"
    w = h.workflow
    db = w.domain.db
    blocker = sqlite3.connect(db.execute("PRAGMA database_list").fetchone()[2])
    previous = db.execute("PRAGMA busy_timeout").fetchone()[0]
    try:
        blocker.execute("BEGIN IMMEDIATE")
        db.execute("PRAGMA busy_timeout=5")
        assert db.execute("SELECT state FROM native_tasks WHERE id=?", (key,)).fetchone()[0] == "produced"
        readback = h.api("execution-readback", key=key).raise_for_status().json()
        assert readback["id"] == key and readback["known_effects"]["exit_code"] == 0
        audit = h.api("record-execution-fault", key=key)
        assert audit.status_code == 503 and audit.headers["retry-after"] == "1"
        terminal = h.api("await-terminal", key=key).raise_for_status().json()
        assert terminal["id"] == key and terminal["state"] == "produced"
        assert json.loads(terminal["terminal"])["candidate"] == readback["known_effects"]["candidate"]
        assert not observations(h, key)
    finally:
        blocker.close()
        db.execute(f"PRAGMA busy_timeout={previous}")
    assert [item["execution"] for item in h.observations()] == [key]
    record_property(
        "observation",
        json.dumps({
            "readback": readback,
            "starts": h.observations(),
            "audit_status": audit.status_code,
            "retry_after": audit.headers["retry-after"],
            "terminal": terminal["state"],
        }),
    )


def test_busy_after_durable_launch_observes_original_worker(host, monkeypatch, record_property):
    h = host
    key = signed(h, install_preview(h))
    original = h.workflow.execute
    calls = []

    def fail_after_execute(actor, execution):
        calls.append(execution)
        assert original(actor, execution)["state"] == "produced"
        raise StorageBusy("receipt store busy")

    monkeypatch.setattr(h.workflow, "execute", fail_after_execute)
    result = drive(h)["result"]
    assert result["errors"] == [] and calls == [key]
    assert [item["execution"] for item in h.observations()] == [key]
    busy, lost = observations(h, key)
    assert busy["state"] == lost["state"] == "produced"
    assert busy["next_action"] == "read-original-receipt" and busy["reason"] == "storage-busy"
    assert result["stages"][0]["candidate"] == busy["known_effects"]["candidate"]
    record_property(
        "observation", json.dumps({"starts": h.observations(), "busy": busy, "stage": result["stages"][0]["state"]})
    )


def test_permanent_storage_failure_does_not_retry(host, monkeypatch):
    h = host
    key = signed(h, install_preview(h))
    assert h.reserve(key).json() is True
    calls = []

    def missing_table(actor, execution):
        calls.append(execution)
        h.workflow.domain.db.execute("SELECT * FROM missing_native_fixture_table")

    monkeypatch.setattr(h.workflow, "execute", missing_table)
    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        h.workflow.execute_receipt(h.actor, key)
    assert calls == [key] and not observations(h, key) and not h.observations()
