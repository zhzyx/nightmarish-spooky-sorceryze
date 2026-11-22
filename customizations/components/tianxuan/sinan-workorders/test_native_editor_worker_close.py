"""Exercise the editor-scoped local producer with real HTTP disconnects and process trees."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest
import test_native_project_reopen as reopen
from native_checkpoint import recover_project
from native_store import NativeStoreError
from native_worker import editor_connection_closed

fixture = reopen.fixture
host = reopen.host


@pytest.mark.parametrize("restartable, revoke", [(True, False), (True, True), (False, False)])
def test_editor_disconnect_only_replays_a_signed_checkpoint(tmp_path, monkeypatch, restartable, revoke):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4] / "tests/editor"))
    from run_macos_registered_worker_close import exercise

    result = exercise(tmp_path, restartable=restartable, revoke=revoke)
    assert result["control_alive"] and result["answered_before_close"] and not result["answered_after_close"]


def test_fast_reopen_waits_for_prelaunch_close_on_original_contract(host, monkeypatch):
    h = host
    issue = reopen.install(h)
    key = reopen.stage.signed(h, issue)
    before = reopen.snapshot(h, key)
    entered, release, closed, joining = (Event() for _ in range(4))
    worker = h.workflow.worker
    materialize = worker.workspace.materialize
    await_terminal = h.workflow.await_terminal

    def materialize_once(*args):
        if not entered.is_set():
            entered.set()
            assert release.wait(10)
        return materialize(*args)

    async def join(*args):
        joining.set()
        return await await_terminal(*args)

    def opening():
        def session():
            if closed.is_set():
                raise NativeStoreError("Original editor closed")

        token = editor_connection_closed.set(closed)
        try:
            return asyncio.run(recover_project(h.workflow, h.actor, "studio", session))
        finally:
            editor_connection_closed.reset(token)

    monkeypatch.setattr(worker.workspace, "materialize", materialize_once)
    monkeypatch.setattr(h.workflow, "await_terminal", join)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(opening)
        try:
            assert entered.wait(10)
            closed.set()
            second = pool.submit(reopen.reopen, h)
            assert joining.wait(10)
        finally:
            release.set()
        first.result(timeout=10)
        assert second.result(timeout=10).raise_for_status().json()["continued"] == 1
    events = h.api("status", key=key).raise_for_status().json()["progress"]["events"]
    (stopped,) = [event for event in events if event["step"] == "process.interrupted"]
    assert stopped["details"]["checkpoint"] == "before-launch"
    reopen.verify_received(h, key, before)
