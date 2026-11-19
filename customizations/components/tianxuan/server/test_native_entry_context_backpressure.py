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


# Public test-only certificate/key; no production identity or credentials.
# SAN localhost, valid 2020-2040; tests trust it only through their local factory.
_TLS_CERT = "-----BEGIN CERTIFICATE-----\nMIIC1DCCAbygAwIBAgIJAMtmgolAKcshMA0GCSqGSIb3DQEBCwUAMBQxEjAQBgNV\nBAMTCWxvY2FsaG9zdDAeFw0xOTEyMzExNjAwMDBaFw0zOTEyMzExNjAwMDBaMBQx\nEjAQBgNVBAMTCWxvY2FsaG9zdDCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoC\nggEBAMZ4yut91VJdXN3ZVPM5jnFEmpaA1Q1Dys6N+NWjS8TEsHv/TyKqnmYDkNch\noOmR2/fkAn5vt7xsSZ9ODYQy1mGUYu2cE03C2CRDZDUTo5UtmDfzhX2UhUOoQJuS\nwmEvwudwulUekJ3pAnP+9TNjZAboBdEU4quNU2X7plerDvWIHb8avS9GBsW2VoYa\nrFZ7Xh2SKRO9lsbPaiQEnp2dGUMuBxA3IrPVmcnb603vi/J3ID1B7nUFDdYs959D\nIxTk6Kv3OgxkldGkF54H0DczjBimLK4Fh0qApzSMTS/Fo/iwGJmhUqzcDJOWzWbm\n2mLDqSgELb1+MMENdQSmJpluLzECAwEAAaMpMCcwFAYDVR0RBA0wC4IJbG9jYWxo\nb3N0MA8GA1UdEwEB/wQFMAMBAf8wDQYJKoZIhvcNAQELBQADggEBAGX8eJoQoq7i\n4KRxw3x92wdPoQDoGipOzlxLs8WQfk4q4PvYDQ882PPfD5TgTwIn03iVPOTe+cZZ\nR2Zwk1848PiTrZOI+23/X3DPy3KLy0cb4DkCxs5pSAilpFUuQXFBEFGr2ayXX5Jc\nulMQDJ/6BVvb3+euRqFq+OLk34XWvkIcg+gMplhEC/yns/0zDQgxEyGfEHko50C1\nP/FxhuGVCGpIrqaxD9f80BEUjUH2+Ky7ChNlY8DGfN676aC81xyfR/QP6FRS/Vt3\nT3up2lhpdoJXzKOyOrM5RcuX7kJljVtXc05en+5+HrI7WAA5ka940i7TaizCNTs/\nH5mM+B2LPa8=\n-----END CERTIFICATE-----"  # codespell:ignore fo
_TLS_KEY = "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDGeMrrfdVSXVzd\n2VTzOY5xRJqWgNUNQ8rOjfjVo0vExLB7/08iqp5mA5DXIaDpkdv35AJ+b7e8bEmf\nTg2EMtZhlGLtnBNNwtgkQ2Q1E6OVLZg384V9lIVDqECbksJhL8LncLpVHpCd6QJz\n/vUzY2QG6AXRFOKrjVNl+6ZXqw71iB2/Gr0vRgbFtlaGGqxWe14dkikTvZbGz2ok\nBJ6dnRlDLgcQNyKz1ZnJ2+tN74vydyA9Qe51BQ3WLPefQyMU5Oir9zoMZJXRpBee\nB9A3M4wYpiyuBYdKgKc0jE0vxaP4sBiZoVKs3AyTls1m5tpiw6koBC29fjDBDXUE\npiaZbi8xAgMBAAECggEAC8ALA3YnswCkBt5fESdPL5WIMXDfLDHfR+tP2BYa3kNm\nz3CGFt9TEWcUpCfxhuKDy2FMZH/ouNcQZMYSNslrt8s5MCgVXH00nrD+tcW74ZEZ\nefaI6K5qVV8YtB00NNzHBTy/S1rL5Q1uf7+QdMJloaMK9R3vbYiob1k+t+IAuLiD\nmRxXo3uZL14EEfSrnjn2UO7gSg1+dxiaG+yZgrYl/FFZEWoewrIHCX3F9JrsUTRr\nXGSatZ2kujCK8PmYY99ER2RCk2JxAXDAPh1BN7B5xBOZHWUkIyRUwvV/9Vb+p3CE\nkm/7OYu5NVvEyjFvOjFVbBTiK4dqQl3MikPtjxtLoQKBgQDemEQftxpELGMJVGp8\n/PL5Gfp2zL6gDCOcGJISgNQM37sF+RwexZgrC7O9me6MdrJzrMrlzuLKblBGxKE7\nylJMxQNhSljls1NDcbu1lEqf+FA6q3oSZ9R/TFymVqQN2rGJBF0Aj3wlvcpYAKsO\nhCKmBdotPlcRJb3PnirqyiEd3wKBgQDkQcMJKMg4HEf9fizqAyCjoqf6h4nADy+v\nIbOj6RR7mVUXE7po9QzB6Jgdtg6pLItd3QDbovGMQgm/AWSVpNrplRo/tZMNSgKZ\nIWC70+MFKXubYSRteiFXdX8pkFvpnlAcUe5wGb/JNHsHvn/LGjy/vbkpHN70vAh1\n5BNC/8407wKBgQC1H7M3F1fBJ1kCy3TG9VCED3Z1Wo62TopfRsL9WWSygQ5+gsA1\n7dSvGhuMaQfptd/pLi3/JwP1ciPSIceMjkm/fAQPE18YsX1MAOybiOncF0K5KrTu\n6xvG5YzyMMfXGh+h/THr9dUwJKnUR97ote43p8VrUTGpm0tC+FG1sPmXgwKBgBcu\nlqBXg/4u4SDdr7IUnzv/SRAos9TNtgoTYitDgNEMwZeWaVg/iwwmk0xxMQv9eioO\nSAgGhIG6M0My4QRRuen/Oqs9xbGT0q+6tBhfbK8Zh3RAaXK09K3tQPz3rF4NthUq\nPQ0lkFTe/5/JuTDneUQAAM4sIHi6oCFZCJvFXywBAoGAKnnU7T297NPziZD4QH2l\nku78+mq6D1Tf/bmShMKkyithPICtxdSqwMABqdniBdOPLyS1WiZkFSlQFEaI23d3\n4Z5HKOv/6YHm0/nL5b4D6hiqniEpIm409crNdSqsfhBp+AQTA6rulPz8CTTvy4qe\n709HID7DLefjYAKc3v187J0=\n-----END PRIVATE KEY-----"


@pytest.mark.parametrize(
    "scheme, proxy, outcome",
    [
        ("http", False, "ok"),
        ("http", True, "ok"),
        ("https", False, "ok"),
        ("https", True, "ok"),
        ("https", False, "untrusted"),
        ("https", False, "hostname"),
        ("https", True, "hostname"),
        ("https", False, "redirect"),
        ("https", False, "capacity"),
        ("https", True, "capacity"),
    ],
)
def test_lazy_tls_real_transport(tmp_path, monkeypatch, scheme, proxy, outcome):
    import http.client
    import ssl
    from http.server import BaseHTTPRequestHandler, HTTPServer

    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert.write_text(_TLS_CERT)
    key.write_text(_TLS_KEY)
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(cert, key)
    contexts, requests, tunnels, closed, bodies = [], [], [], [], []
    original = ssl._create_default_https_context

    def context(*args, **kwargs):
        result = original(*args, **kwargs)
        assert result.verify_mode == ssl.CERT_REQUIRED and result.check_hostname
        if outcome != "untrusted":
            result.load_verify_locations(cafile=cert)
        contexts.append(result)
        return result

    monkeypatch.setattr(ssl, "_create_default_https_context", context)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def do_CONNECT(self):
            tunnels.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.flush()
            self.connection = server_context.wrap_socket(self.connection, server_side=True)
            self.rfile = self.connection.makefile("rb", self.rbufsize)
            self.wfile = self.connection.makefile("wb", 0)
            self.handle_one_request()
            self.close_connection = True

        def do_POST(self):
            assert isinstance(self.connection, ssl.SSLSocket) == (scheme == "https")
            requests.append((self.path, self.headers["Authorization"], self.headers["Connection"]))
            # Refuse before reading the delayed body, as the admission server does.
            capacity = outcome == "capacity" and len(requests) <= 2
            code = 503 if capacity else 302 if outcome == "redirect" else 200
            body = b'{"detail":{"status":"not_started","reason":"context_capacity"}}' if capacity else b'{"ok":true}'
            if not capacity:
                bodies.append(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(code)
            self.send_header("Content-Length", str(len(body)))
            if code == 302:
                self.send_header("Location", "https://localhost:1/forbidden")
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()
            if capacity:
                bodies.append(self.rfile.read(int(self.headers["Content-Length"])))
            self.connection.settimeout(3)
            try:
                closed.append(self.rfile.read(1) == b"")
            except (ConnectionResetError, BrokenPipeError):
                # Rejecting a redirect closes the unread response immediately.
                # TLS peers may observe a reset instead of an orderly EOF.
                closed.append(True)
            self.close_connection = True

    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.timeout = 3
    if scheme == "https" and not proxy:
        server.socket = server_context.wrap_socket(server.socket, server_side=True)
    port = server.server_port
    monkeypatch.setattr(
        transport.urllib.request, "getproxies", lambda: {scheme: f"http://127.0.0.1:{port}"} if proxy else {}
    )
    monkeypatch.setattr(transport.urllib.request, "proxy_bypass", lambda host: False)
    c = EntryContextClient.__new__(EntryContextClient)
    host = "127.0.0.1" if outcome == "hostname" or scheme == "http" else "localhost"
    c.url, c.token, c.execution = f"{scheme}://{host}:{port}", "test", "execution"
    if outcome == "capacity":
        original_send = http.client.HTTPConnection.send

        def send(self, data):
            if isinstance(data, bytes) and data.startswith(b"{"):
                time.sleep(0.05)
            return original_send(self, data)

        monkeypatch.setattr(http.client.HTTPConnection, "send", send)
    count = 3 if outcome == "capacity" else 2 if outcome == "ok" else 1

    def serve():
        for _ in range(count):
            server.handle_request()

    thread = threading.Thread(target=serve)
    thread.start()
    try:
        if outcome in {"untrusted", "hostname"}:
            with pytest.raises(urllib.error.URLError) as error:
                c.check()
            assert isinstance(error.value.reason, ssl.SSLCertVerificationError)
        elif outcome == "redirect":
            with pytest.raises(urllib.error.HTTPError) as error:
                c.check()
            assert error.value.code == 302
        else:
            assert c.check() == {"ok": True}
            if outcome == "ok":
                assert c.check() == {"ok": True}
    finally:
        thread.join(10)
        server.server_close()
    assert not thread.is_alive()
    assert len(contexts) == (count if scheme == "https" else 0)
    assert len(tunnels) == (count if scheme == "https" and proxy else 0)
    if outcome in {"untrusted", "hostname"}:
        assert not requests
    else:
        assert len(requests) == count and closed == [True] * count
        assert len(bodies) == count and len(set(bodies)) == 1
        assert all(auth == "Bearer test" and connection == "keep-alive" for _, auth, connection in requests)
        expected = c.url + "/native-context/execution" if proxy and scheme == "http" else "/native-context/execution"
        assert all(path == expected for path, _, _ in requests)
