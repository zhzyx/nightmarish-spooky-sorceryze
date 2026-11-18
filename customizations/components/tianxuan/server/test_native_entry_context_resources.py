"""Measured loopback resource and concurrency regressions; no provider calls."""

import json
import threading
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack

import pytest
from native_context import NativeContext
from native_entry_context import EntryContexts
from native_entry_context_client import EntryContextClient
from native_store import NativeContextStorage
from test_native_entry_context import live_context, policy  # noqa: F401
from test_native_workflow import fixture, reserve, task  # noqa: F401

# ruff: noqa: F811


@pytest.fixture(params=[False, True])
def large_context(fixture, request):
    w, actor, tenant, req, initial, root = fixture
    initial["a"] = w.worker.store.submit(
        tenant, actor, "large-source", [dict(module="a", base=initial["a"], reads=[], edits={"output": b"x" * 131072})]
    )["revisions"]["a"]
    yield from live_context.__wrapped__(fixture, request)


def test_http_read_measurement(large_context, monkeypatch):
    e, client, active, issue = large_context
    e.contexts._contexts.clear()
    instances = []
    original = NativeContextStorage.__init__

    def capture(self, *args, **kwargs):
        original(self, *args, **kwargs)
        instances.append(self)

    monkeypatch.setattr(NativeContextStorage, "__init__", capture)
    manifest = client.resolve(dict(op="manifest", cursor=None))["content"][0]
    args = dict(
        op="read",
        **{k: manifest[k] for k in ("module", "revision", "name", "object_digest")},
        offset=0,
        length=32,
        cursor=None,
        known_receipt=None,
    )
    client.resolve(args)
    cold = sum(s.io["body_bytes"] for s in instances)
    client.resolve(args)
    hot = sum(s.io["body_bytes"] for s in instances) - cold
    print(
        "RESOURCE_MEASUREMENT",
        json.dumps(
            dict(
                instances=len(instances),
                cold=cold,
                hot=hot,
                verifications=sum(s.io["cold_verifications"] for s in instances),
            )
        ),
    )
    assert hot == 8192
    assert sum(s.io["cold_verifications"] for s in instances) == 1
    # Reconstruct the service from its durable ledger, as after a process restart.
    e.contexts = EntryContexts(e, e.runtime_installation)
    client.resolve(args)
    assert len(instances) == 2
    assert instances[-1].io["cold_verifications"] == 1
    assert instances[-1].io["body_bytes"] == 139264


def test_independent_http_contexts(live_context, fixture, monkeypatch):
    e, client, active, issue = live_context
    if e.runtime_installation.verify()["remote"] is not None:
        e.workflow.worker.nodes["node-a"]["capacity"] = 2
    key, _ = task(fixture, "b")
    reserve(fixture, key)
    peer = EntryContextClient(dict(server=client.url, token_file=str(e.root / "context-token")), key)
    entered, release = threading.Event(), threading.Event()
    original = NativeContext.resolve

    def blocked(self, *args):
        if self.binding["execution"] == client.execution:
            entered.set()
            assert release.wait(5)
        return original(self, *args)

    monkeypatch.setattr(NativeContext, "resolve", blocked)
    with ThreadPoolExecutor(2) as pool:
        pending = pool.submit(client.resolve, dict(op="manifest", cursor=None))
        assert entered.wait(5)
        try:
            pool.submit(peer.check, "peer").result(timeout=2)
            print("INDEPENDENT_HTTP_COMPLETED_WHILE_PEER_BLOCKED")
        finally:
            release.set()
        pending.result(timeout=5)


@pytest.mark.parametrize("revoke", [False, True])
def test_saturated_cache_waits_and_rechecks(live_context, revoke):
    e, client, active, issue = live_context
    with ExitStack() as stack, ThreadPoolExecutor(1) as pool:
        for n in range(16):
            stack.enter_context(e.contexts._lease("occupied-" + str(n)))
        pending = pool.submit(client.check, "after-admission")
        deadline = time.monotonic() + 5
        while e.contexts._waiters != 1 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert e.contexts._waiters == 1 and not pending.done()
        assert len(e.contexts._contexts) == 16
        active["allow"] = not revoke
        stack.close()
        if revoke:
            with pytest.raises(urllib.error.HTTPError):
                pending.result(timeout=5)
        else:
            pending.result(timeout=5)
        assert len(e.contexts._contexts) == 16


def test_inflight_revocation_and_serial_unknown(live_context, monkeypatch):
    e, client, active, issue = live_context
    entered, release = threading.Event(), threading.Event()
    original = NativeContext.emit

    def blocked(self, kind, data):
        result = original(self, kind, data)
        if kind == "started":
            entered.set()
            assert release.wait(5)
        return result

    monkeypatch.setattr(NativeContext, "emit", blocked)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(client.resolve, dict(op="manifest", cursor=None))
        assert entered.wait(5)
        second = pool.submit(client.resolve, dict(op="manifest", cursor=None))
        active["allow"] = False
        release.set()
        for pending in (first, second):
            with pytest.raises(urllib.error.HTTPError):
                pending.result(timeout=5)
    active["allow"] = True
    with pytest.raises(urllib.error.HTTPError):
        client.resolve(dict(op="manifest", cursor=None))
    events = e.contexts.context(client.execution).events()
    assert [x["kind"] for x in events] == ["started"]


def test_eviction_preserves_unknown_and_physical_closure(live_context):
    e, client, active, issue = live_context
    c = e.contexts.context(client.execution)
    c.emit("started", {"request_id": "unknown"})
    for n in range(17):
        with e.contexts._lease("evict-" + str(n)):
            pass
    assert client.execution not in e.contexts._contexts
    with pytest.raises(urllib.error.HTTPError):
        client.resolve(dict(op="manifest", cursor=None))
    assert c.receipt()["terminal"] == "incomplete"
    with e.native._connection(write=True) as db:
        db.execute(
            "INSERT INTO native_worker_process_closures VALUES (?,?,?,?)", (client.execution, "{}", "{}", "invalid")
        )
    with pytest.raises(urllib.error.HTTPError):
        client.check("closed")
    with pytest.raises((ValueError, KeyError)):
        e.contexts.receipt({}, client.execution)


def test_capacity_timeout_does_not_start_operation(live_context):
    e, client, active, issue = live_context
    e.contexts.wait_seconds = 0
    before = e.contexts.context(client.execution).events()
    with e.contexts._lease(client.execution):
        with pytest.raises(urllib.error.HTTPError) as error:
            client.resolve(dict(op="manifest", cursor=None))
        assert error.value.code == 503
    assert e.contexts.context(client.execution).events() == before
    e.contexts.wait_seconds = 30
    client.resolve(dict(op="manifest", cursor=None))


def test_events_response_budget(live_context):
    e, client, active, issue = live_context
    c = e.contexts.context(client.execution)
    for _ in range(5):
        c.emit("model_receipt", {"data": "x" * 60000})
    with pytest.raises(urllib.error.HTTPError):
        client.events()
    client.check("small-response-still-works")
