"""Bounded same-turn continuation over real HTTP; synthetic models only."""

# ruff: noqa: F811
import json
import threading
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack

import native_entry_context_client as transport
import pytest
from native_entry_context_client import ContextNotStarted, EntryContextClient
from test_native_entry_broker_context import broker_rpc  # noqa: F401
from test_native_entry_context import live_context  # noqa: F401
from test_native_workflow import fixture  # noqa: F401


def observe(monkeypatch):
    original = EntryContextClient._attempt
    attempts = []
    refused = threading.Event()

    def attempt(request, redirect, timeout):
        attempts.append((request.full_url, request.data, timeout))
        try:
            return original(request, redirect, timeout)
        except ContextNotStarted:
            refused.set()
            raise

    monkeypatch.setattr(EntryContextClient, "_attempt", staticmethod(attempt))
    return attempts, refused


@pytest.mark.parametrize("end", ["release", "revoke", "withdraw"])
def test_saturated_same_request(live_context, monkeypatch, end):
    e, c, active, issue = live_context
    # Keep enough start time for real remote authority checks on Windows.
    e.contexts.wait_seconds = 0.5
    attempts, refused = observe(monkeypatch)
    with ExitStack() as stack, ThreadPoolExecutor(max_workers=1) as pool:
        stack.enter_context(e.contexts._lease(c.execution))
        pending = pool.submit(c.resolve, {"op": "manifest", "cursor": None}, "same-call")
        try:
            assert refused.wait(5)
            if end == "revoke":
                active["allow"] = False
            if end == "withdraw":
                with e.domain._connection_lock:
                    e.domain.db.execute("UPDATE issues SET status='cancelled' WHERE id=?", (issue["id"],))
                    e.domain.db.commit()
            stack.close()
            if end == "release":
                assert pending.result(10)["dependency_kind"] == "namespace"
            else:
                with pytest.raises(urllib.error.HTTPError) as error:
                    pending.result(10)
                assert error.value.code == 409
        finally:
            stack.close()
    assert 2 <= len(attempts) <= 16
    assert len({(url, body) for url, body, _ in attempts}) == 1
    # Read ledger directly: revoked authority must not be bypassed for this check.
    import sqlite3

    with sqlite3.connect(e.contexts.root / (c.execution + ".sqlite")) as db:
        kinds = [row[0] for row in db.execute("SELECT kind FROM context_events")]
    if end == "release":
        assert [x["kind"] for x in e.contexts.context(c.execution).events()] == ["started", "resolved"]
    else:
        assert not kinds


@pytest.mark.parametrize("budget, expected", [(120, 3), (35.01, 1)])
def test_real_http_attempt_exhaustion(live_context, monkeypatch, budget, expected):
    e, c, _, _ = live_context
    e.contexts.wait_seconds = 0.02
    monkeypatch.setattr(c, "MAX_ATTEMPTS", 3)
    monkeypatch.setattr(c, "ADMISSION_SECONDS", budget)
    attempts, _ = observe(monkeypatch)
    with e.contexts._lease(c.execution), pytest.raises(ContextNotStarted):
        c.resolve({"op": "manifest", "cursor": None})
    assert len(attempts) == expected
    assert not e.contexts.context(c.execution).events()


@pytest.mark.parametrize("failure", ["malformed", "extra", "401", "409", "timeout", "disconnect", "reset"])
def test_unknown_never_retried(monkeypatch, failure):
    import io
    from types import SimpleNamespace

    c = EntryContextClient.__new__(EntryContextClient)
    c.url, c.token, c.execution = "http://127.0.0.1:1", "test", "execution"
    attempts = []

    def opened(*args, **kwargs):
        attempts.append(1)
        if failure == "timeout":
            raise TimeoutError("unknown")
        if failure == "disconnect":
            raise urllib.error.URLError("disconnected")
        if failure == "reset":
            raise ConnectionResetError("unknown reset")
        body = (
            b"not json"
            if failure == "malformed"
            else b'{"detail":{"status":"not_started","reason":"context_capacity","extra":true}}'
        )
        raise urllib.error.HTTPError(c.url, int(failure) if failure.isdigit() else 503, "unknown", {}, io.BytesIO(body))

    monkeypatch.setattr(transport.urllib.request, "build_opener", lambda *args: SimpleNamespace(open=opened))
    with pytest.raises((urllib.error.URLError, TimeoutError, ConnectionResetError)) as error:
        c.check()
    assert not isinstance(error.value, ContextNotStarted)
    assert len(attempts) == 1
    with pytest.raises(ValueError):
        c.call("unknown-tool")
    assert len(attempts) == 1


def test_elapsed_reserve_and_cancellation(monkeypatch):
    c = EntryContextClient.__new__(EntryContextClient)
    c.url, c.token, c.execution = "http://127.0.0.1:1", "test", "execution"
    now, attempts = [0.0], []

    def attempt(request, redirect, timeout):
        attempts.append(timeout)
        now[0] += 30
        raise ContextNotStarted(c.url, 503, "not started", {}, None)

    monkeypatch.setattr(c, "_attempt", attempt)
    monkeypatch.setattr(transport.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(transport.time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))
    with pytest.raises(ContextNotStarted):
        c.check()
    assert len(attempts) == 3 and now[0] < 120
    assert attempts == [35, 35, 35]
    attempts.clear()

    def cancelled(seconds):
        raise KeyboardInterrupt()

    monkeypatch.setattr(transport.time, "sleep", cancelled)
    with pytest.raises(KeyboardInterrupt):
        c.check()
    assert len(attempts) == 1


@pytest.mark.parametrize("broker_rpc", [False], indirect=True)
def test_signed_broker_same_model_turn(fixture, monkeypatch, broker_rpc):
    from native_entry_context import ContextAdmissionBusy
    from test_native_entry_broker_context import test_actual_broker_context_http

    e = broker_rpc[1]
    original = e.contexts.call
    resolves = []

    def call(execution, token, method, args, admission=None):
        if method == "resolve":
            resolves.append(json.dumps([execution, args], sort_keys=True))
            if len(resolves) == 1:
                raise ContextAdmissionBusy("controlled unstarted capacity")
        return original(execution, token, method, args, admission)

    monkeypatch.setattr(e.contexts, "call", call)
    start = time.monotonic()
    test_actual_broker_context_http(fixture, monkeypatch, broker_rpc)
    counts = json.loads((fixture[-1] / "counts.json").read_text())
    assert counts == {"turns": 3, "threads": 1}
    assert len(resolves) == 3 and resolves[0] == resolves[1]
    print(
        "BROKER_CAPACITY",
        json.dumps(
            dict(duration=time.monotonic() - start, model_calls=counts["turns"], resolve_attempts=len(resolves))
        ),
    )


@pytest.fixture
def burst_context(fixture, monkeypatch):
    from types import SimpleNamespace

    import test_native_entry_context as fixtures
    from native_store import _digest

    original = fixtures.policy

    def policy(root, **kwargs):
        installed = original(root, **kwargs)
        spec = json.loads(installed.path.read_text())
        spec["context"]["limits"]["max_reads"] = 500
        spec["context"]["limits"]["total_bytes"] = 1048576
        installed.path.write_text(json.dumps(spec))
        installed.sha256 = _digest(installed.path.read_bytes())
        return installed

    monkeypatch.setattr(fixtures, "policy", policy)
    yield from live_context.__wrapped__(fixture, SimpleNamespace(param=False))


@pytest.mark.parametrize("body_delay", [0, 0.05])
def test_250_local_tool_burst(burst_context, monkeypatch, body_delay):
    import http.client

    original_send = http.client.HTTPConnection.send

    def send(self, data):
        # Exercise admission refusal after headers but before the POST body.
        # The ordinary case also retains the original unscheduled 250 burst.
        if body_delay and isinstance(data, bytes) and data.startswith(b"{"):
            time.sleep(body_delay)
        return original_send(self, data)

    monkeypatch.setattr(http.client.HTTPConnection, "send", send)
    e, c, _, _ = burst_context
    attempts, refused = observe(monkeypatch)
    body_reads = []
    from starlette.requests import Request

    original_stream = Request.stream

    async def stream(self):
        body_reads.append(1)
        async for chunk in original_stream(self):
            yield chunk

    monkeypatch.setattr(Request, "stream", stream)
    started = time.monotonic()
    with ExitStack() as stack, ThreadPoolExecutor(max_workers=250) as pool:
        for n in range(16):
            stack.enter_context(e.contexts._lease("occupied-" + str(n)))
        pending = [pool.submit(c.resolve, {"op": "manifest", "cursor": None}, "burst-" + str(n)) for n in range(250)]
        try:
            assert refused.wait(10)
            stack.close()
            results = [p.result(120) for p in pending]
        finally:
            stack.close()
    assert len(results) == 250
    events = e.contexts.context(c.execution).events()
    assert sum(x["kind"] == "started" for x in events) == 250
    assert sum(x["kind"] == "resolved" for x in events) == 250
    assert 250 < len(attempts) <= 4000
    assert len(body_reads) < len(attempts)
    print(
        "LOCAL_250",
        json.dumps(
            dict(
                duration=time.monotonic() - started,
                rpc_attempts=len(attempts),
                body_reads=len(body_reads),
                model_calls=0,
                requests=250,
                body_delay=body_delay,
            )
        ),
    )


@pytest.mark.parametrize("mode", ["malformed", "401", "409", "timeout", "disconnect"])
def test_actual_http_unknown_no_retry(monkeypatch, mode):
    from http.server import BaseHTTPRequestHandler, HTTPServer

    c = EntryContextClient.__new__(EntryContextClient)
    c.token, c.execution = "test", "execution"
    attempts = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            attempts.append(self.rfile.read(int(self.headers["Content-Length"])))
            if mode == "disconnect":
                self.close_connection = True
                return
            if mode == "timeout":
                time.sleep(0.15)
                self.close_connection = True
                return
            self.send_response(int(mode) if mode.isdigit() else 503)
            self.end_headers()
            self.wfile.write(b"not-json")

    server = HTTPServer(("127.0.0.1", 0), Handler)
    c.url = "http://127.0.0.1:" + str(server.server_port)
    monkeypatch.setattr(c, "TRANSPORT_SECONDS", 0.05)
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    try:
        import http.client

        with pytest.raises((urllib.error.URLError, TimeoutError, http.client.RemoteDisconnected)) as error:
            c.resolve({"op": "manifest", "cursor": None}, "unchanged-call")
        assert not isinstance(error.value, ContextNotStarted)
    finally:
        thread.join(3)
        server.server_close()
    assert not thread.is_alive() and len(attempts) == 1
