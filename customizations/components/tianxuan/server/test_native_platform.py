"""Native platform HTTP integration
model upstream is deterministic MockTransport only."""

import importlib
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import api
import httpx
import merge_queue
import pytest
from api import create_app
from fastapi.testclient import TestClient
from gateway import ModelGateway
from native_store import NativeStore
from starlette.websockets import WebSocketDisconnect
from test_native_api import account
from tianxuan_core import Tianxuan


@pytest.mark.parametrize("base", ["\ud800", {"bad": "\ud800"}, ["\ud800"], 7, False])
def test_snapshot_invalid_base_has_no_native_write(tmp_path, base):
    domain = Tianxuan(str(tmp_path / "domain.db"))
    native = NativeStore(tmp_path / "native.db")
    try:
        with TestClient(
            create_app(domain, native_store=native, native_only=True), raise_server_exceptions=False
        ) as client:
            owner, headers = account(client, 81)
            doc = domain.create_requirement(owner["user_id"], "invalid-base", "Title", "Outcome", "Scope", "Accept")
            path = f"/api/v1/native/requirements/{doc['id']}"
            source = client.get(path + "/source", headers=headers).json()["source_version"]
            response = client.post(
                path + "/snapshots",
                headers=headers,
                content=json.dumps({"request_key": "bad-base", "source_version": source, "base": base}),
            )
            assert response.status_code == 422
            with native._connection() as db:
                assert db.execute("SELECT count(*) FROM native_receipts").fetchone()[0] == 0
    finally:
        domain.db.close()


def test_native_requirement_keeps_current_source_acl(tmp_path):
    domain = Tianxuan(str(tmp_path / "domain.db"))
    native = NativeStore(tmp_path / "native.db")
    try:
        with TestClient(create_app(domain, native_store=native, native_only=True)) as client:
            owner, headers = account(client, 82)
            viewer = domain.add_member(owner["user_id"], "viewer82@example.invalid", "password123", role="viewer")
            viewer_headers = {"Authorization": "Bearer " + domain.issue_session(viewer["user_id"])}
            editor = domain.add_member(owner["user_id"], "editor82@example.invalid", "password123")
            editor_headers = {"Authorization": "Bearer " + domain.issue_session(editor["user_id"])}
            doc = domain.create_requirement(
                owner["user_id"], "private-source", "Private", "PRIVATE SECRET", "Scope", "Accept"
            )
            domain.set_visibility(owner["user_id"], doc["id"], "private")
            path = f"/api/v1/native/requirements/{doc['id']}"
            source = client.get(path + "/source", headers=headers).json()["source_version"]
            saved = client.post(
                path + "/snapshots",
                headers=headers,
                json={"request_key": "private", "source_version": source, "base": None},
            ).json()
            module, revision = saved["module"], saved["revision"]
            public = client.post(
                "/api/v1/native/batches",
                headers=headers,
                json={
                    "request_key": "public-dependency",
                    "changes": [
                        {
                            "module": "public",
                            "base": None,
                            "reads": None,
                            "edits": {"readme": "cHVibGlj"},
                            "dependencies": {module: revision},
                        }
                    ],
                },
            ).json()["revisions"]["public"]
            selections = [{module: revision}, {"public": public}]
            candidates = [
                client.post("/api/v1/native/compositions", headers=headers, json={"selected": selected}).json()["id"]
                for selected in selections
            ]
            paths = [
                f"/api/v1/native/modules/{module}/head",
                f"/api/v1/native/modules/{module}/revisions/{revision}",
                f"/api/v1/native/modules/{module}/revisions/{revision}/objects/snapshot.json",
                *[f"/api/v1/native/compositions/{candidate}" for candidate in candidates],
            ]
            assert client.get(f"/api/v1/docs/{doc['id']}", headers=viewer_headers).status_code == 403
            for target in paths:
                response = client.get(target, headers=viewer_headers)
                assert response.status_code == 403, (target, response.status_code)
                assert "PRIVATE SECRET" not in response.text
            for selected in selections:
                assert (
                    client.post(
                        "/api/v1/native/compositions", headers=viewer_headers, json={"selected": selected}
                    ).status_code
                    == 403
                )
                assert (
                    client.post(
                        "/api/v1/native/compositions", headers=editor_headers, json={"selected": selected}
                    ).status_code
                    == 403
                )
            unknown = "requirement-" + "f" * 64
            legacy = native.submit(
                owner["tenant_id"],
                owner["user_id"],
                "legacy-unbound",
                [
                    {
                        "module": unknown,
                        "base": None,
                        "reads": None,
                        "edits": {"snapshot.json": json.dumps({"binding": {"doc_id": doc["id"]}}).encode()},
                    }
                ],
            )["revisions"][unknown]
            legacy_composition = native.compose(owner["tenant_id"], {unknown: legacy})["id"]
            assert client.get(f"/api/v1/native/modules/{unknown}/head", headers=headers).status_code == 403
            assert client.get(f"/api/v1/native/compositions/{legacy_composition}", headers=headers).status_code == 403
            for reserved in (module, "requirement-" + "f" * 64):
                assert (
                    client.post(
                        "/api/v1/native/batches",
                        headers=headers,
                        json={
                            "request_key": "forge",
                            "changes": [
                                {"module": reserved, "base": None, "reads": None, "edits": {"snapshot.json": "e30="}}
                            ],
                        },
                    ).status_code
                    == 422
                )
            domain.share_doc(owner["user_id"], doc["id"], viewer["user_id"], "read")
            assert all(client.get(target, headers=viewer_headers).status_code == 200 for target in paths)
            domain.unshare_doc(owner["user_id"], doc["id"], viewer["user_id"])
            assert all(client.get(target, headers=viewer_headers).status_code == 403 for target in paths)
            domain.db.close()
            domain = Tianxuan(str(tmp_path / "domain.db"))
            with TestClient(create_app(domain, native_store=native, native_only=True)) as restarted:
                assert all(restarted.get(target, headers=viewer_headers).status_code == 403 for target in paths)
                assert all(restarted.get(target, headers=headers).status_code == 200 for target in paths)
    finally:
        domain.db.close()


def test_native_platform(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Git constructor called")

    monkeypatch.setattr(api, "GitService", forbidden)
    monkeypatch.setattr(api, "GiteaClient", forbidden)
    monkeypatch.setattr(merge_queue, "MergeQueue", forbidden)
    monkeypatch.setenv("TIANXUAN_STORAGE_MODE", "native")
    monkeypatch.setenv("TIANXUAN_DB", str(tmp_path / "domain.db"))
    monkeypatch.setenv("TIANXUAN_NATIVE_DB", str(tmp_path / "native.db"))
    monkeypatch.setenv("TIANXUAN_REQUIRED_APPROVALS", "invalid-git-setting")
    monkeypatch.setenv("TIANXUAN_MERGE_CHECKS", "'invalid")
    monkeypatch.setenv("TIANXUAN_REPO_ROOT", "Z:/nonexistent")
    import main

    module = importlib.reload(main)
    client = TestClient(module.app)
    owner, h = account(client, 31)
    _, other = account(client, 32)
    assert client.get("/api/v1/ready").status_code == 200
    assert client.get("/api/v1/capabilities").json()["mode"] == "native"
    for path in ("git/repos", "repos", "gitea/status", "merge-queue", "repo-links"):
        assert client.get("/api/v1/" + path, headers=h).status_code == 404
    r = client.post(
        "/api/v1/requirements",
        headers=h,
        json=dict(request_id="req", title="Title", outcome="Outcome", scope="Scope", acceptance="Acceptance"),
    )
    assert r.status_code == 200, r.text
    doc = r.json()
    did = doc["id"]
    tickets = client.post(
        f"/api/v1/requirements/{did}/tickets", headers=h, json={"tickets": [{"title": "Implement"}]}
    ).json()["issues"]
    assert tickets
    path = f"/api/v1/docs/{did}"
    assert client.get(path, headers={"X-Actor": owner["user_id"]}).status_code == 401
    with pytest.raises(WebSocketDisconnect) as denied:
        with client.websocket_connect(f"/api/v1/ws/docs/{did}?actor={owner['user_id']}"):
            pass
    assert denied.value.code == 4401
    token = h["Authorization"].split()[1]
    with client.websocket_connect(f"/api/v1/ws/docs/{did}?token={token}") as websocket:
        assert websocket.receive_json()["type"] == "snapshot"
    assert client.patch(path, headers=h, json={"body_md": "# Updated", "expected_version": 1}).status_code == 200
    assert client.post(path + "/comments", headers=h, json={"body": "Review"}).status_code == 200
    for suffix in ("", "/comments", "/versions", "/ai-view", "/issues"):
        assert client.get(path + suffix, headers=h).status_code == 200
    assert client.get(path, headers=other).status_code in (403, 404)
    source_path = f"/api/v1/native/requirements/{did}/source"
    target = f"/api/v1/native/requirements/{did}/snapshots"
    source = client.get(source_path, headers=h).json()
    payload = {"request_key": "snapshot1", "source_version": source["source_version"], "base": None}
    response = client.post(target, headers=h, json=payload)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["state"] == "candidate"
    issue = tickets[0]["id"]
    assert client.patch(f"/api/v1/issues/{issue}", headers=h, json={"to_status": "planned"}).status_code == 200
    assert client.get(source_path, headers=h).json()["source_version"] != source["source_version"]
    assert client.post(target, headers=h, json=payload).json() == saved
    assert client.post(target, headers=h, json={**payload, "request_key": "stale"}).status_code == 409
    assert client.post(target, headers=h, json={**payload, "base": saved["revision"]}).status_code == 409
    assert client.post(target, headers=other, json=payload).status_code in (403, 404)
    assert client.post(target, headers=h, json={**payload, "reads": []}).status_code == 422
    assert client.post(target, headers=h, content=json.dumps({**payload, "request_key": "\ud800"})).status_code == 422
    current = client.get(source_path, headers=h).json()["source_version"]
    next_payload = {"request_key": "snapshot2", "source_version": current, "base": None}
    assert client.post(target, headers=h, json=next_payload).status_code == 409
    next_payload["base"] = saved["revision"]
    assert client.post(target, headers=h, json=next_payload).status_code == 200
    assert client.post(target, headers=h, json=payload).json() == saved
    module._STORE.db.close()
    restarted = Tianxuan(str(tmp_path / "domain.db"))
    native = NativeStore(tmp_path / "native.db")
    with TestClient(create_app(restarted, native_store=native, native_only=True)) as c:
        assert c.post(target, headers=h, json=payload).json() == saved
        obj = f"/api/v1/native/modules/{saved['module']}/revisions/{saved['revision']}/objects/snapshot.json"
        snapshot = c.get(obj, headers=h).json()
        assert snapshot["snapshot"] == source["snapshot"]
        assert c.get("/api/v1/issues", headers=h).json()["issues"][0]["status"] == "planned"
        assert c.get(path, headers=h).json()["status"] != "done"
        c.post("/api/v1/auth/logout", headers=h)
        assert c.post(target, headers=h, json=payload).status_code == 401
    restarted.db.close()


def test_model_verified_identity(tmp_path):
    calls = []

    def upstream(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "local simulation"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            },
        )

    gateway = ModelGateway(":memory:", transport=httpx.MockTransport(upstream))
    store = Tianxuan(":memory:")
    client = TestClient(
        create_app(store, gateway=gateway, native_store=NativeStore(tmp_path / "n.db"), native_only=True)
    )
    owner, h = account(client, 41)
    other, oh = account(client, 42)
    body = {
        "model": "deepseek-v4-pro",
        "messages": [{"role": "user", "content": "ping"}],
        "base_url": "https://mock.invalid/v1",
    }
    headers = {**h, "X-Model-Key": "local-test"}
    for spoof in ({"X-Tenant": other["tenant_id"]}, {"X-Actor": other["user_id"]}):
        assert client.post("/api/v1/models/chat", headers={**headers, **spoof}, json=body).status_code == 403
    assert not calls
    assert client.post("/api/v1/models/chat", headers=headers, json=body).status_code == 200
    assert len(calls) == 1
    usage = client.get("/api/v1/models/usage", headers=h).json()
    assert usage["usage"][0]["actor"] == owner["user_id"]
    assert usage["totals"]["calls"] == 1
    assert client.get("/api/v1/models/usage", headers=oh).json()["totals"]["calls"] == 0
    assert client.get("/api/v1/models/usage", headers=h, params={"tenant_id": other["tenant_id"]}).status_code == 403
    assert client.get("/api/v1/models/usage", headers={"X-Actor": owner["user_id"]}).status_code == 401
    store.revoke_session(h["Authorization"].split()[1])
    assert client.post("/api/v1/models/chat", headers=headers, json=body).status_code == 401
    store.db.close()
    gateway.close()


def test_source_is_consistent_across_connections(tmp_path, monkeypatch):
    path = str(tmp_path / "source.db")
    store = Tianxuan(path)
    store.db.execute("PRAGMA journal_mode=WAL")
    writer = Tianxuan(path)
    actor = store.register("org", "atomic@example.invalid", "password123")["user_id"]
    doc = store.create_requirement(actor, "req", "Title", "O", "S", "A")
    before = store.requirement_snapshot(actor, doc["id"])
    read = Event()
    written = Event()
    original = store.get_doc_shared

    def paused(*args, **kwargs):
        result = original(*args, **kwargs)
        read.set()
        assert written.wait(5)
        return result

    monkeypatch.setattr(store, "get_doc_shared", paused)

    def update():
        assert read.wait(5)
        writer.plan_tickets(actor, doc["id"], [{"title": "New"}])
        written.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(update)
        during = store.requirement_snapshot(actor, doc["id"])
        future.result()
    assert during == before
    assert writer.requirement_snapshot(actor, doc["id"]) != before
    store.db.close()
    writer.db.close()


def test_actor_context_holds_shared_connection(tmp_path):
    store = Tianxuan(str(tmp_path / "locked.db"))
    actor = store.register("lock", "lock@example.invalid", "password123")["user_id"]
    started = Event()

    def lookup():
        started.set()
        return store.actor_context(actor)

    with ThreadPoolExecutor(max_workers=1) as pool:
        with store._connection_lock:
            result = pool.submit(lookup)
            assert started.wait(5)
            assert not result.done()
        assert result.result(timeout=5)["actor"] == actor
    store.db.close()


def test_native_production_gateway_and_roles(tmp_path, monkeypatch):
    store = Tianxuan(":memory:")
    owner = store.register("strict", "strict@example.invalid", "password123")
    actor = owner["user_id"]
    member = store.add_member(actor, "reader@example.invalid", "password123", role="viewer")["user_id"]
    key = store.issue_access_key(actor, actor, "admin")["key"]
    reader_key = store.issue_access_key(actor, member, "reader")["key"]
    monkeypatch.setenv("TIANXUAN_REQUIRE_KEYS", "1")
    monkeypatch.setenv("TIANXUAN_TENANT_ID", owner["tenant_id"])
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://testserver")
    gateway = ModelGateway(
        ":memory:",
        transport=httpx.MockTransport(lambda r: (_ for _ in ()).throw(AssertionError("no upstream expected"))),
    )
    client = TestClient(
        create_app(store, gateway=gateway, native_store=NativeStore(tmp_path / "strict.db"), native_only=True)
    )
    assert (
        client.get(
            "/api/v1/models/usage", headers={"Authorization": "Bearer " + store.issue_session(actor)}
        ).status_code
        == 401
    )
    assert client.get("/api/v1/models/usage", headers={"Authorization": "Bearer " + reader_key}).status_code == 403
    h = {"Authorization": "Bearer " + key}
    assert client.get("/api/v1/models/usage", headers=h).status_code == 200
    assert client.post("/api/v1/auth/register", headers=h, json={}).status_code == 403
    store.set_role(actor, member, "editor")
    assert client.get("/api/v1/models/usage", headers={"Authorization": "Bearer " + reader_key}).status_code == 403
    key_id = next(row["id"] for row in store.list_access_keys(actor) if row["name"] == "admin")
    store.revoke_access_key(actor, key_id)
    assert client.get("/api/v1/models/usage", headers=h).status_code == 401
    store.db.close()
    gateway.close()


def test_native_status_uses_capabilities_without_gitea(monkeypatch):
    import argparse

    import tianshu_bridge

    seen = []

    def request(api_url, method, path, **kwargs):
        seen.append(path)
        return {"mode": "native", "git": False} if path.endswith("capabilities") else {"status": "ok"}

    monkeypatch.setattr(tianshu_bridge, "_request", request)
    result = tianshu_bridge.status(argparse.Namespace(api="http://local", actor="", token="session"))
    assert result["capabilities"]["mode"] == "native"
    assert seen == ["/api/v1/health", "/api/v1/capabilities"]
