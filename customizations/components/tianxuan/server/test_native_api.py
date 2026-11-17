"""Real ASGI boundary regression for the native candidate adapter."""

import asyncio
import base64
import importlib
import json
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest
from api import create_app
from fastapi.testclient import TestClient
from native_store import NativeStore
from tianxuan_core import Tianxuan

P = "/api/v1/native"


def account(client, number):
    data = {"tenant_name": f"Org{number}", "email": f"o{number}@example.invalid", "password": "password123"}
    registered = client.post("/api/v1/auth/register", json=data)
    assert registered.status_code == 200, registered.text
    session = client.post("/api/v1/auth/session", json={k: data[k] for k in ("email", "password")})
    assert session.status_code == 200
    return registered.json(), {"Authorization": "Bearer " + session.json()["token"]}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.delenv("TIANXUAN_REQUIRE_KEYS", raising=False)
    store = Tianxuan(str(tmp_path / "auth.db"))
    native = NativeStore(tmp_path / "native.db")
    app = create_app(store, native_store=native, native_only=True)
    with TestClient(app) as client:
        owner, headers = account(client, 1)
        other, other_headers = account(client, 2)
        yield store, native, app, client, owner, headers, other, other_headers
    store.db.close()


def batch(key="first", module="m", base=None, value=b"hello"):
    return {
        "request_key": key,
        "changes": [
            {"module": module, "base": base, "reads": None, "edits": {"a.txt": base64.b64encode(value).decode()}}
        ],
    }


def test_candidate_lifecycle_and_isolation(setup):
    store, native, _, client, _, h, _, other = setup
    payload = batch()
    result = client.post(P + "/batches", headers=h, json=payload)
    assert result.status_code == 200, result.text
    revision = result.json()["revisions"]["m"]
    assert client.post(P + "/batches", headers=h, json=payload).json() == result.json()
    assert client.post(P + "/batches", headers=h, json=batch(value=b"changed")).status_code == 409
    path = P + f"/modules/m/revisions/{revision}"
    assert client.get(path + "/objects/a.txt", headers=h).content == b"hello"
    assert client.get(path, headers=other).status_code == 422
    assert client.get(path + "/objects/a.txt", headers=other).status_code == 422
    candidate = client.post(P + "/compositions", headers=h, json={"selected": {"m": revision}}).json()
    assert candidate["state"] == "candidate"
    assert client.get(P + "/compositions/" + candidate["id"], headers=other).status_code == 422
    with TestClient(create_app(store, native_store=NativeStore(native.database), native_only=True)) as restarted:
        assert restarted.get(P + "/compositions/" + candidate["id"], headers=h).json() == candidate
    with native._connection(write=True) as db:
        db.execute("UPDATE native_blobs SET content=?", (b"corrupt",))
    assert client.get(path + "/objects/a.txt", headers=h).status_code == 422
    assert client.get(P + "/compositions/" + candidate["id"], headers=h).status_code == 422


def test_identity_and_parameters(setup):
    store, _, _, client, owner, h, _, _ = setup
    path = P + "/modules/m/head"
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"X-Actor": owner["user_id"]}).status_code == 401
    assert client.get(path + "?tenant=forged", headers=h).status_code == 422
    assert client.post(P + "/batches", headers=h, json={**batch(), "actor": owner["user_id"]}).status_code == 422
    for reads in ([], ["a.txt"]):
        payload = batch()
        payload["changes"][0]["reads"] = reads
        assert client.post(P + "/batches", headers=h, json=payload).status_code == 422
    token = h["Authorization"].split()[1]
    store.revoke_session(token)
    assert client.get(path, headers=h).status_code == 401


def test_atomic_conflict_unknown_reads_and_concurrency(setup):
    _, native, _, client, owner, h, _, _ = setup
    first = client.post(P + "/batches", headers=h, json=batch()).json()["revisions"]["m"]
    # Unrelated module drift does not invalidate m.
    assert client.post(P + "/batches", headers=h, json=batch("other", "other")).status_code == 200
    payload = batch("advance", base=first)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: client.post(P + "/batches", headers=h, json=payload), range(2)))
    assert all(r.status_code == 200 for r in results)
    assert results[0].json() == results[1].json()
    stale = batch("stale", base=first)
    stale["changes"][0]["edits"] = {"unrelated": "Yg=="}
    stale["changes"].append(batch("unused", "atomic")["changes"][0])
    assert client.post(P + "/batches", headers=h, json=stale).status_code == 409
    assert native.head(owner["tenant_id"], "atomic") is None


def test_limits_and_storage_errors(setup, monkeypatch):
    import native_api

    _, native, _, client, _, h, _, _ = setup
    payload = batch()
    payload["changes"][0]["edits"] = {"a": "%%%"}
    assert client.post(P + "/batches", headers=h, json=payload).status_code == 422
    monkeypatch.setattr(native_api, "MAX_OBJECT", 2)
    assert client.post(P + "/batches", headers=h, json=batch(value=b"abc")).status_code == 413
    monkeypatch.setattr(native_api, "MAX_OBJECT", 100)
    monkeypatch.setattr(native_api, "MAX_DECODED", 2)
    assert client.post(P + "/batches", headers=h, json=batch(value=b"abc")).status_code == 413
    monkeypatch.setattr(native_api, "MAX_DECODED", 100)

    def busy(*args):
        error = sqlite3.OperationalError("secret/local/path")
        error.sqlite_errorcode = sqlite3.SQLITE_BUSY
        raise error

    monkeypatch.setattr(native, "submit", busy)
    response = client.post(P + "/batches", headers=h, json=batch())
    assert response.status_code == 503 and response.headers["retry-after"] == "1"
    assert "secret" not in response.text


@pytest.mark.parametrize("name", ["\ud800", "path/\udfff", "\ud800x\udfff"])
def test_invalid_unicode_object_name_is_rejected_before_storage(setup, name):
    _, native, _, client, owner, headers, _, _ = setup
    payload = batch()
    payload["changes"][0]["edits"] = {name: "YQ=="}
    response = client.post(P + "/batches", headers=headers, content=json.dumps(payload))
    assert response.status_code == 422
    assert native.head(owner["tenant_id"], "m") is None


def test_valid_unicode_object_name_roundtrips(setup):
    _, native, _, client, owner, headers, _, _ = setup
    payload = batch()
    name = "场景/\U0001f30d.txt"
    payload["changes"][0]["edits"] = {name: "YQ=="}
    response = client.post(P + "/batches", headers=headers, content=json.dumps(payload))
    assert response.status_code == 200
    revision = response.json()["revisions"]["m"]
    assert native.read(owner["tenant_id"], "m", revision, name) == b"a"


def test_stream_limit_stops_receiving(setup, monkeypatch):
    import native_api

    _, _, app, _, _, h, _, _ = setup
    monkeypatch.setattr(native_api, "MAX_BODY", 10)
    received = []
    sent = []

    async def receive():
        received.append(1)
        assert len(received) <= 2, "read beyond rejected chunk"
        return {"type": "http.request", "body": b"x" * 6, "more_body": True}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": P + "/batches",
        "raw_path": (P + "/batches").encode(),
        "query_string": b"",
        "headers": [(b"authorization", h["Authorization"].encode())],
        "server": ("test", 80),
        "client": ("test", 1),
        "root_path": "",
    }
    asyncio.run(app(scope, receive, send))
    assert received == [1, 1]
    assert sent[0]["status"] == 413


def test_strict_production_access(setup, monkeypatch):
    store, native, _, _, owner, session, other, _ = setup
    key = store.issue_access_key(owner["user_id"], owner["user_id"], "test")["key"]
    other_key = store.issue_access_key(other["user_id"], other["user_id"], "test")["key"]
    monkeypatch.setenv("TIANXUAN_REQUIRE_KEYS", "1")
    monkeypatch.setenv("TIANXUAN_TENANT_ID", owner["tenant_id"])
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://testserver")
    with TestClient(create_app(store, native_store=native, native_only=True)) as client:
        assert client.get(P + "/modules/m/head", headers=session).status_code == 401
        assert client.get(P + "/modules/m/head", headers={"Authorization": "Bearer " + other_key}).status_code == 403
        h = {"Authorization": "Bearer " + key, "X-Actor": other["user_id"]}
        assert client.post(P + "/batches", headers=h, json=batch()).status_code == 200
        assert native.head(owner["tenant_id"], "m") is not None
        assert native.head(other["tenant_id"], "m") is None
        assert client.post("/api/v1/auth/register", headers=h, json={}).status_code == 403


def test_real_native_startup_forbids_git_and_processes(tmp_path, monkeypatch):
    import subprocess

    import duobao_bridge
    import merge_queue

    def forbidden(*args, **kwargs):
        raise AssertionError("Git/process construction forbidden")

    monkeypatch.setattr(duobao_bridge, "GitService", forbidden)
    monkeypatch.setattr(merge_queue, "MergeQueue", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setenv("TIANXUAN_DB", str(tmp_path / "auth.db"))
    monkeypatch.setenv("TIANXUAN_NATIVE_DB", str(tmp_path / "native.db"))
    monkeypatch.setenv("TIANXUAN_STORAGE_MODE", "native")
    monkeypatch.delenv("TIANXUAN_REQUIRE_KEYS", raising=False)
    sys.modules.pop("main", None)
    main = importlib.import_module("main")
    try:
        assert main._MERGE_QUEUE is None
        with TestClient(main.app) as client:
            _, h = account(client, 99)
            assert client.post(P + "/batches", headers=h, json=batch()).status_code == 200
            assert client.get("/api/v1/repos", headers=h).status_code == 404
    finally:
        main._STORE.db.close()
        sys.modules.pop("main", None)


def test_blocked_identity_does_not_block_event_loop(setup, monkeypatch):
    import threading

    import httpx

    store, _, app, _, _, h, _, _ = setup
    entered = threading.Event()
    release = threading.Event()
    original = store.user_for_token

    def blocked(token):
        entered.set()
        assert release.wait(5)
        return original(token)

    monkeypatch.setattr(store, "user_for_token", blocked)

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            pending = asyncio.create_task(client.get(P + "/modules/m/head", headers=h))
            try:
                assert await asyncio.to_thread(entered.wait, 3)
                response = await asyncio.wait_for(client.get("/api/v1/health"), 2)
                assert response.status_code == 200
            finally:
                release.set()
            assert (await pending).status_code == 200

    asyncio.run(exercise())


def test_git_mode_fallback_starts(tmp_path, monkeypatch):
    monkeypatch.setenv("TIANXUAN_DB", str(tmp_path / "fallback.db"))
    monkeypatch.setenv("TIANXUAN_STORAGE_MODE", "git")
    monkeypatch.setenv("TIANXUAN_MERGE_WORKER", "0")
    monkeypatch.delenv("TIANXUAN_REQUIRE_KEYS", raising=False)
    sys.modules.pop("main", None)
    main = importlib.import_module("main")
    try:
        assert main._MERGE_QUEUE is not None
        with TestClient(main.app) as client:
            assert client.get("/api/v1/health").status_code == 200
    finally:
        main._STORE.db.close()
        sys.modules.pop("main", None)


def test_expired_sessions_and_viewer_write_denial(setup):
    store, _, _, client, owner, _, _, _ = setup
    viewer = store.add_member(owner["user_id"], "viewer@example.invalid", "password123", role="viewer")
    token = store.issue_session(viewer["user_id"])
    h = {"Authorization": "Bearer " + token}
    assert client.get(P + "/modules/m/head", headers=h).status_code == 200
    assert client.post(P + "/batches", headers=h, json=batch()).status_code == 403
    store.db.execute("UPDATE sessions SET expires_at='2000-01-01T00:00:00+00:00'")
    store.db.commit()
    assert client.get(P + "/modules/m/head", headers=h).status_code == 401


def test_atomic_batch_dependency_composition(setup):
    _, _, _, client, _, h, _, _ = setup
    payload = batch()
    dependent = batch("ignored", "dependent")["changes"][0]
    dependent["dependencies"] = {"m": "@batch"}
    payload["changes"].append(dependent)
    response = client.post(P + "/batches", headers=h, json=payload)
    assert response.status_code == 200, response.text
    revisions = response.json()["revisions"]
    composition = client.post(P + "/compositions", headers=h, json={"selected": {"dependent": revisions["dependent"]}})
    assert composition.status_code == 200
    assert composition.json()["modules"] == revisions
    assert client.get(P + "/compositions/" + composition.json()["id"], headers=h).json() == composition.json()


def test_real_sqlite_lock_maps_to_retryable_response(setup, monkeypatch):
    _, native, _, client, _, h, _, _ = setup
    original = sqlite3.connect

    def short_timeout(*args, **kwargs):
        kwargs["timeout"] = 0.01
        return original(*args, **kwargs)

    with original(native.database, isolation_level=None) as lock:
        lock.execute("BEGIN IMMEDIATE")
        monkeypatch.setattr(sqlite3, "connect", short_timeout)
        response = client.post(P + "/batches", headers=h, json=batch())
        assert response.status_code == 503
        assert response.headers["retry-after"] == "1"
        lock.rollback()
    assert client.post(P + "/batches", headers=h, json=batch()).status_code == 200


def test_early_length_entry_and_batch_limits(setup, monkeypatch):
    import native_api

    _, _, _, client, _, h, _, _ = setup
    assert (
        client.post(
            P + "/batches", headers={**h, "content-length": str(native_api.MAX_BODY + 1)}, content=b"{}"
        ).status_code
        == 413
    )
    payload = batch()
    payload["changes"] *= 129
    assert client.post(P + "/batches", headers=h, json=payload).status_code == 422
    monkeypatch.setattr(native_api, "MAX_ENTRIES", 1)
    payload = batch()
    payload["changes"][0]["edits"]["b"] = "Yg=="
    assert client.post(P + "/batches", headers=h, json=payload).status_code == 413
