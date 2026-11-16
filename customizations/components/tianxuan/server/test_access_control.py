import pytest
from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


@pytest.fixture
def setup(monkeypatch):
    store = Tianxuan(":memory:")
    owner = store.register("Secure", "owner@example.invalid", "password")
    viewer = store.add_member(owner["user_id"], "view@example.invalid", "password", role="viewer")
    admin_key = store.issue_access_key(owner["user_id"], owner["user_id"], "admin")["key"]
    view_key = store.issue_access_key(owner["user_id"], viewer["user_id"], "viewer")["key"]
    monkeypatch.delenv("TIANXUAN_ALLOW_ACTOR_HEADER", raising=False)
    monkeypatch.setenv("TIANXUAN_REQUIRE_KEYS", "1")
    monkeypatch.setenv("TIANXUAN_TENANT_ID", owner["tenant_id"])
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://testserver")
    with TestClient(create_app(store), base_url="https://testserver") as client:
        yield store, client, owner, viewer, admin_key, view_key
    store.db.close()


def test_no_actor_or_ordinary_session_bypass(setup):
    store, client, owner, _, _, _ = setup
    assert client.get("/api/v1/docs", headers={"X-Actor": owner["user_id"]}).status_code == 401
    token = store.issue_session(owner["user_id"])
    assert client.get("/api/v1/docs", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert client.post("/api/v1/auth/register", json={}).status_code == 401


def test_viewer_spoof_and_all_writes_rejected(setup):
    _, client, owner, viewer, _, key = setup
    h = {"Authorization": f"Bearer {key}", "X-Actor": owner["user_id"]}
    assert client.get("/api/v1/auth/me", headers=h).json()["id"] == viewer["user_id"]
    for path in ["/api/v1/users", "/api/v1/repos/a/b/pulls/1/merge", "/api/v1/merge-queue/a/retry", "/api/v1/docs"]:
        assert client.post(path, headers=h, json={}).status_code == 403


def test_cookie_csrf_and_revocation(setup):
    store, client, owner, _, admin_key, _ = setup
    assert client.post("/api/v1/auth/key-login", json={"key": admin_key}).status_code == 403
    login = client.post("/api/v1/auth/key-login", headers={"Origin": "https://testserver"}, json={"key": admin_key})
    assert login.status_code == 200
    assert "HttpOnly" in login.headers["set-cookie"] and "Secure" in login.headers["set-cookie"]
    assert client.get("/api/v1/docs").status_code == 200
    assert client.post("/api/v1/docs", json={"title": "CSRF"}).status_code == 403
    assert (
        client.post("/api/v1/docs", headers={"Origin": "https://testserver"}, json={"title": "allowed"}).status_code
        == 200
    )
    key_id = store.list_access_keys(owner["user_id"])[0]["id"]
    # Identify the admin key without depending on UUID or timestamp ordering.
    key_id = next(k["id"] for k in store.list_access_keys(owner["user_id"]) if k["name"] == "admin")
    store.revoke_access_key(owner["user_id"], key_id)
    assert client.get("/api/v1/docs").status_code == 401


def test_keys_are_hashed_and_tenant_bound(setup):
    store, client, owner, viewer, key, _ = setup
    h = {"Authorization": f"Bearer {key}"}
    created = client.post(
        "/api/v1/auth/keys", headers=h, json={"user_id": viewer["user_id"], "name": "second", "days": 1}
    )
    assert created.status_code == 200
    raw = created.json()["key"]
    assert raw not in str([tuple(r) for r in store.db.execute("SELECT * FROM access_keys")])
    assert raw not in client.get("/api/v1/auth/keys", headers=h).text
    other = store.register("Other", "other@example.invalid", "password")
    other_key = store.issue_access_key(other["user_id"], other["user_id"], "other")["key"]
    assert client.get("/api/v1/docs", headers={"Authorization": f"Bearer {other_key}"}).status_code == 403
    assert (
        client.post("/api/v1/auth/keys", headers=h, json={"user_id": other["user_id"], "name": "no"}).status_code == 403
    )


def test_websocket_does_not_accept_actor_alone(setup):
    from starlette.websockets import WebSocketDisconnect

    _, client, owner, _, _, _ = setup
    with pytest.raises(WebSocketDisconnect) as failure:
        with client.websocket_connect(f"/api/v1/ws/docs/missing?actor={owner['user_id']}"):
            pass
    assert failure.value.code == 4401


def test_admin_revoke_and_role_change_take_effect(setup):
    store, client, owner, viewer, admin, key = setup
    ah = {"Authorization": f"Bearer {admin}"}
    vh = {"Authorization": f"Bearer {key}"}
    store.set_role(owner["user_id"], viewer["user_id"], "editor")
    assert client.post("/api/v1/docs", headers=vh, json={"title": "editor"}).status_code == 200
    store.set_role(owner["user_id"], viewer["user_id"], "viewer")
    assert client.post("/api/v1/docs", headers=vh, json={"title": "readonly"}).status_code == 403
    key_id = next(k["id"] for k in store.list_access_keys(owner["user_id"]) if k["name"] == "viewer")
    assert client.delete(f"/api/v1/auth/keys/{key_id}", headers=ah).status_code == 200
    assert client.get("/api/v1/docs", headers=vh).status_code == 401


@pytest.mark.parametrize("revoke", ["key", "share"])
def test_websocket_revocation_preserves_other_writers(setup, revoke):
    from starlette.websockets import WebSocketDisconnect

    store, client, owner, viewer, admin, key = setup
    ah = {"Authorization": f"Bearer {admin}"}
    vh = {"Authorization": f"Bearer {key}"}
    doc = client.post("/api/v1/docs", headers=ah, json={"title": "private", "body_md": "original"}).json()
    store.set_visibility(owner["user_id"], doc["id"], "private")
    store.share_doc(owner["user_id"], doc["id"], viewer["user_id"], "read")
    path = f"/api/v1/ws/docs/{doc['id']}"
    with client.websocket_connect(path, headers=vh) as reader:
        assert reader.receive_json()["type"] == "snapshot"
        assert reader.receive_json()["type"] == "presence"
        with client.websocket_connect(path, headers=ah) as writer:
            assert writer.receive_json()["type"] == "snapshot"
            assert writer.receive_json()["type"] == "presence"
            assert reader.receive_json()["type"] == "presence"
            if revoke == "share":
                store.unshare_doc(owner["user_id"], doc["id"], viewer["user_id"])
            else:
                key_id = next(k["id"] for k in store.list_access_keys(owner["user_id"]) if k["name"] == "viewer")
                store.revoke_access_key(owner["user_id"], key_id)
            writer.send_json({"type": "update", "expected_version": 1, "body_md": "new private data"})
            assert writer.receive_json()["type"] == "updated"
            with pytest.raises(WebSocketDisconnect) as closed:
                reader.receive_json()
            assert closed.value.code == (4401 if revoke == "key" else 4403)


def test_repository_read_write_and_stale_file(setup, tmp_path, monkeypatch):
    from duobao_bridge import GitService

    store, client, owner, _, admin, viewer = setup
    monkeypatch.setenv("TIANXUAN_REPO_ROOT", str(tmp_path))
    service = GitService()
    repo = service.create_repo(tmp_path, "code")
    service.commit(repo, "main", "initial", {"hello.txt": "original"}, "Audit", "audit@example.invalid")
    ah = {"Authorization": f"Bearer {admin}"}
    vh = {"Authorization": f"Bearer {viewer}"}
    base = "/api/v1/git/repos/code.git"
    content = client.get(base + "/file", params={"path": "hello.txt"}, headers=vh).json()
    payload = {
        "path": "hello.txt",
        "branch": "main",
        "content": "edited",
        "message": "edit",
        "expected_blob": content["sha"],
    }
    assert client.post(base + "/file", headers=vh, json=payload).status_code == 403
    created = client.post(base + "/file", headers=ah, json=payload)
    assert created.status_code == 200, created.text
    assert created.json()["branch"].startswith("web/" + owner["user_id"] + "/")
    assert service.read_file(repo, "main", "hello.txt") == "original"
    assert service.read_file(repo, created.json()["branch"], "hello.txt") == "edited"
    payload["expected_blob"] = "0" * 40
    assert client.post(base + "/file", headers=ah, json=payload).status_code == 409
    assert client.get(base + "/file", headers=ah, params={"path": "../secret"}).status_code in {400, 404}
    service.commit(repo, "main", "directory", {"nested/readme.txt": "nested"}, "Audit", "audit@example.invalid")
    assert client.get(base + "/file", headers=ah, params={"path": "nested"}).status_code == 413
    editor = store.add_member(owner["user_id"], "editor@example.invalid", "password", role="editor")
    editor_key = store.issue_access_key(owner["user_id"], editor["user_id"], "editor")["key"]
    client.app.state.protected_branches = ("web/*",)
    payload["expected_blob"] = content["sha"]
    assert (
        client.post(base + "/file", headers={"Authorization": f"Bearer {editor_key}"}, json=payload).status_code == 403
    )
