"""Coordinator-owned completion events, with durable replay and no idle polling."""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from native_store import NativeStoreError
from test_native_workflow import fixture, reserve, task  # noqa: F401

# ruff: noqa: F811


def test_cancelled_observer_concurrent_execute_and_terminal_replay(fixture):
    w, actor, *_ = fixture
    key, _ = task(fixture, "a")
    reserve(fixture, key)
    entered, release = threading.Event(), threading.Event()
    original = w.worker.run
    launches = []

    def run(contract, identity):
        launches.append(identity)
        entered.set()
        assert release.wait(10)
        return original(contract, identity)

    w.worker.run = run
    with ThreadPoolExecutor(1) as pool:
        producer = pool.submit(w.execute, actor, key)
        assert entered.wait(10)
        assert w.execute(actor, key)["state"] == "running"

        async def observe():
            abandoned = asyncio.create_task(w.await_terminal(actor, key))
            await asyncio.sleep(0)
            abandoned.cancel()
            with pytest.raises(asyncio.CancelledError):
                await abandoned
            assert not w._executions[key][0].cancelled()
            first = asyncio.create_task(w.await_terminal(actor, key))
            second = asyncio.create_task(w.await_terminal(actor, key))
            await asyncio.sleep(0)
            release.set()
            assert all(r["state"] == "produced" for r in await asyncio.gather(first, second))

        asyncio.run(observe())
        assert producer.result(10)["state"] == "produced"
    assert launches == [key]
    assert not w._executions
    # Event arrived before registration; terminal survives an observer restart.
    assert asyncio.run(w.await_terminal(actor, key))["state"] == "produced"


def test_unowned_running_never_waits_or_relaunches(fixture):
    w, actor, *_ = fixture
    key, _ = task(fixture, "a")
    reserve(fixture, key)
    with w._transaction() as db:
        db.execute("UPDATE native_tasks SET state='running' WHERE id=?", (key,))
    with pytest.raises(NativeStoreError, match="ownership unavailable"):
        asyncio.run(w.await_terminal(actor, key))
    assert w.status(actor, key)["state"] == "running"
    assert not (w.worker.root / key).exists()


@pytest.mark.parametrize("change", ["cancelled", "source", "authority"])
def test_current_authority_rechecked_after_event(fixture, change):
    w, actor, *_ = fixture
    key, issue = task(fixture, "a")
    reserve(fixture, key)
    w.execute(actor, key)
    if change == "authority":
        w.authorize = lambda *args: False
    elif change == "cancelled":
        with w._transaction() as db:
            db.execute("UPDATE issues SET status='cancelled' WHERE id=?", (issue["id"],))
    else:
        with w._transaction() as db:
            db.execute("UPDATE native_active_tasks SET task='replaced' WHERE issue=?", (issue["id"],))
    from tianxuan_core import PermissionDenied

    with pytest.raises((NativeStoreError, PermissionDenied)):
        asyncio.run(w.await_terminal(actor, key))


def test_bounded_observer_does_not_cancel_owner(fixture):
    import time
    from concurrent.futures import Future

    w, actor, *_ = fixture
    key, _ = task(fixture, "a")
    reserve(fixture, key)
    event = Future()
    w._executions[key] = (event, time.monotonic() - 1)
    with pytest.raises(NativeStoreError, match="deadline exceeded"):
        asyncio.run(w.await_terminal(actor, key))
    assert not event.cancelled() and not event.done()
    assert w.status(actor, key)["state"] == "reserved"
    w._executions.pop(key)


@pytest.mark.parametrize("credential", ["session", "account-bearer", "account-cookie", "key-bearer", "key-cookie"])
@pytest.mark.parametrize("revoked", [False, True])
def test_http_terminal_refreshes_actual_credential(fixture, monkeypatch, credential, revoked):
    from access_control import COOKIE, SESSION_COOKIE
    from api import create_app
    from fastapi.testclient import TestClient

    w, actor, *_ = fixture
    key, _ = task(fixture, "a")
    reserve(fixture, key)
    assert w.execute(actor, key)["state"] == "produced"
    headers = {}
    cookies = {}
    access = None
    monkeypatch.setenv("TIANXUAN_TENANT_ID", w.domain.actor_context(actor)["tenant"])
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://example.invalid")
    if credential.startswith("key-"):
        monkeypatch.setenv("TIANXUAN_REQUIRE_KEYS", "1")
        monkeypatch.setenv("TIANXUAN_AUTH_MODE", "keys")
        access = w.domain.issue_access_key(actor, actor, "observer-test")
        token = access["key"]
    else:
        monkeypatch.setenv("TIANXUAN_REQUIRE_KEYS", "0")
        monkeypatch.setenv("TIANXUAN_AUTH_MODE", "accounts" if credential.startswith("account-") else "legacy")
        token = w.domain.issue_session(actor)
    if credential.endswith("-cookie"):
        cookies[COOKIE if access else SESSION_COOKIE] = token
        headers["Origin"] = "https://example.invalid"
    else:
        headers["Authorization"] = "Bearer " + token
    entered, release = threading.Event(), threading.Event()
    original = w.await_terminal

    async def waiting(a, k):
        entered.set()
        assert await asyncio.to_thread(release.wait, 10)
        return await original(a, k)

    w.await_terminal = waiting
    app = create_app(w.domain, native_store=w.worker.store, native_only=True, native_workflow=w)
    with TestClient(app, base_url="https://example.invalid", cookies=cookies) as client, ThreadPoolExecutor(1) as pool:
        pending = pool.submit(client.post, "/api/v1/native/workflow/await-terminal", json={"key": key}, headers=headers)
        try:
            assert entered.wait(10)
            if revoked:
                if access:
                    assert w.domain.revoke_access_key(actor, access["id"])
                else:
                    assert w.domain.revoke_session(token)
        finally:
            release.set()
        response = pending.result(15)
    assert response.status_code == (401 if revoked else 200)
    if not revoked:
        assert response.json()["state"] == "produced"
    assert w.status(actor, key)["state"] == "produced"
