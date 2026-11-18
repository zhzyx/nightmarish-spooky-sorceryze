"""Actual loopback RPC and ordinary main wiring; no provider calls."""

import json
import socket
import threading
import time
import urllib.error
from contextvars import ContextVar
from pathlib import Path
from types import SimpleNamespace

import pytest
import uvicorn
from fastapi import FastAPI
from native_entry_context import EntryContexts, RuntimeInstallation, mount_entry_runtime
from native_entry_context_client import EntryContextClient
from native_store import _digest
from test_native_workflow import fixture, reserve, task  # noqa: F401

# pytest fixture registration
# ruff: noqa: F811


def policy(root, digest="installed", remote=None):
    value = dict(
        version=1,
        installation=digest,
        remote=remote,
        context=dict(
            local_token_sha256=_digest(b"local-secret"),
            full_bytes=1024,
            limits=dict(response_bytes=4096, chunk_bytes=1024, total_bytes=8192, max_reads=20),
        ),
    )
    path = root / "runtime.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return RuntimeInstallation(path, _digest(path.read_bytes()))


@pytest.fixture(params=[False, True])
def live_context(fixture, request):
    w, actor, tenant, req, initial, root = fixture
    remote_spec = None
    remote = None
    if request.param:
        from native_remote_worker import RemoteNativeWorker

        local = w.worker
        installation = local.installation("local")
        remote_spec = dict(
            profiles={"local": dict(timeout=5, installation=installation)},
            nodes={
                "node-a": dict(
                    tenant=tenant,
                    token_sha256=_digest(b"local-secret"),
                    profiles={"local": installation},
                    capacity=1,
                    enabled=True,
                    package=_digest(Path(__import__("native_node").__file__).read_bytes()),
                )
            },
        )
        remote = RemoteNativeWorker(
            local.store,
            root / "remote",
            remote_spec["profiles"],
            authorize=local.intake.authorize,
            nodes=remote_spec["nodes"],
            single_coordinator=True,
        )
        w.worker = remote
        remote.bind(w)
    key, issue = task(fixture, "a")
    reserve(fixture, key)
    installed = policy(root, remote=remote_spec)
    active = {"allow": True}

    def authority(mandate):
        if not active["allow"]:
            raise ValueError("Revoked entry")
        return True

    entry = SimpleNamespace(
        root=root,
        native=w.worker.store,
        domain=w.domain,
        workflow=w,
        installation=SimpleNamespace(sha256="installed", verify=lambda: True),
        runtime_installation=installed,
        current_entry=ContextVar("test-entry", default=None),
        entry_authority=authority,
        module_authority=lambda *args: active["allow"],
    )
    entry.contexts = EntryContexts(entry, installed)
    app = mount_entry_runtime(FastAPI(), entry)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", timeout_graceful_shutdown=3))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started
    token = root / "context-token"
    token.write_text("local-secret")
    client = EntryContextClient(
        dict(server="http://127.0.0.1:" + str(sock.getsockname()[1]), token_file=str(token)), key
    )
    try:
        yield entry, client, active, issue
    finally:
        server.should_exit = True
        thread.join(10)
        sock.close()
        assert not thread.is_alive()
        if remote is not None:
            remote.close()


def test_http_context_authority_and_restart(live_context):
    e, client, active, issue = live_context
    first = client.resolve(dict(op="manifest", cursor=None))
    assert first["dependency_kind"] == "namespace"
    assert client.binding["selected"]
    assert client.binding["source_digest"]
    before = e.contexts.context(client.execution).receipt()
    e.contexts = EntryContexts(e, e.runtime_installation)
    assert e.contexts.context(client.execution).receipt() == before
    active["allow"] = False
    with pytest.raises(urllib.error.HTTPError):
        client.check("completion")
    active["allow"] = True
    client.token = "wrong"
    with pytest.raises(urllib.error.HTTPError):
        client.resolve(dict(op="manifest", cursor=None))
    client.token = "local-secret"
    with pytest.raises(urllib.error.HTTPError):
        client.call("emit", "process_closed", {"exit_code": 0, "physical": True})
    e.domain.db.execute("UPDATE issues SET status='cancelled' WHERE id=?", (issue["id"],))
    e.domain.db.commit()
    with pytest.raises(urllib.error.HTTPError):
        client.check("completion")


def test_unknown_read_not_replayed(live_context):
    e, client, active, issue = live_context
    c = e.contexts.context(client.execution)
    c.emit("started", {"request_id": "unknown"})
    e.contexts = EntryContexts(e, e.runtime_installation)
    with pytest.raises(urllib.error.HTTPError):
        client.resolve(dict(op="manifest", cursor=None))
    assert e.contexts.context(client.execution).receipt()["terminal"] == "incomplete"


def test_main_installed_context(monkeypatch):
    import native_entry_factory
    from test_native_entry_normal import NormalEntryTests

    original = native_entry_factory.OrdinaryEntry.__init__

    def installed(self, domain, native, manifest, digest, root, **kwargs):
        root = Path(root)
        root.mkdir(exist_ok=True)
        kwargs["runtime_installation"] = policy(root, digest)
        return original(self, domain, native, manifest, digest, root, **kwargs)

    monkeypatch.setattr(native_entry_factory.OrdinaryEntry, "__init__", installed)
    test = NormalEntryTests("test_main_two_users")
    result = test.defaultTestResult()
    test.run(result)
    assert not result.errors and not result.failures, (result.errors, result.failures)


def test_node_assignment_and_policy_revocation(live_context):
    entry, client, active, issue = live_context
    if entry.runtime_installation.verify()["remote"] is not None:
        worker = entry.workflow.worker
        node = worker.nodes["node-a"]
        for field, value in (("enabled", False), ("tenant", "other"), ("package", "changed")):
            previous = node[field]
            node[field] = value
            with pytest.raises(urllib.error.HTTPError):
                client.check("completion")
            node[field] = previous
        worker.cancel(client.execution)
        with pytest.raises(urllib.error.HTTPError):
            client.check("completion")
    else:
        entry.runtime_installation.path.write_text("{}")
        with pytest.raises(urllib.error.HTTPError):
            client.check("completion")


def test_context_transport_rejects_authority_confusion(tmp_path):
    for url in ("http://127.0.0.1:80@evil.invalid", "https://host.invalid/path", "https://user@host.invalid"):
        with pytest.raises(ValueError):
            EntryContextClient(dict(server=url, token_file=str(tmp_path / "missing")), "a" * 64)
