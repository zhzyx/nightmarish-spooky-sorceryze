"""Editor device authorization and explicit administrator delegation."""

import pytest
from api import create_app
from fastapi.testclient import TestClient
from identity import reset_identity_attempts
from tianxuan_core import UNTIL_REVOKED, Tianxuan, _token_hash


def bearer(token):
    return {"Authorization": "Bearer " + token}


@pytest.fixture
def domain(tmp_path, monkeypatch):
    reset_identity_attempts()
    monkeypatch.delenv("TIANXUAN_ALLOW_ACTOR_HEADER", raising=False)
    monkeypatch.setenv("TIANXUAN_REQUIRE_KEYS", "0")
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://testserver")
    path = str(tmp_path / "identity.sqlite")
    store = Tianxuan(path)
    owner = store.register("tenant", "admin@example.invalid", "admin-password")
    monkeypatch.setenv("TIANXUAN_TENANT_ID", owner["tenant_id"])
    user = store.add_member(owner["user_id"], "user@example.invalid", "user-password")
    other = store.register("other", "other@example.invalid", "other-password")
    try:
        yield store, owner, user, other, path
    finally:
        store.db.close()
        reset_identity_attempts()


@pytest.mark.parametrize("mode", ["accounts", "legacy"])
def test_persistent_device_restart_permissions_and_revocation(domain, mode, monkeypatch):
    store, owner, user, other, path = domain
    monkeypatch.setenv("TIANXUAN_AUTH_MODE", mode)
    credentials = {"email": "user@example.invalid", "password": "user-password"}
    session_url = "/api/v1/auth/editor-session"
    devices_url = "/api/v1/auth/editor-devices"
    with TestClient(create_app(store), base_url="https://testserver") as client:
        assert client.post(session_url, json={**credentials, "password": "bad"}).status_code == 401
        assert client.post(session_url, headers={"Origin": "https://testserver"}, json=credentials).status_code == 403
        grant = client.post(session_url, json=credentials)
        assert grant.status_code == 200 and grant.headers["cache-control"] == "no-store"
        assert "set-cookie" not in grant.headers
        issued = grant.json()
        actor = user["user_id"]
        assert (issued["user_id"], issued["tenant_id"], issued["role"]) == (actor, owner["tenant_id"], "editor")
        token, device = issued["token"], issued["credential_id"]
        assert store.user_for_access_key(token) is None
        assert (
            store.db.execute("SELECT expires_at FROM sessions WHERE token_hash=?", (_token_hash(token),)).fetchone()[0]
            == UNTIL_REVOKED
        )
        assert token not in str(list(store.db.iterdump()))
        assert "user-password" not in str(list(store.db.iterdump()))
        admin_auth = bearer(store.issue_session(owner["user_id"]))
        other_auth = bearer(store.issue_session(other["user_id"]))
        assert client.get(devices_url, headers=other_auth).json()["devices"] == []
        assert client.delete(devices_url + "/" + device, headers=other_auth).status_code == 404
        other_grant = client.post(
            session_url, json={"email": "other@example.invalid", "password": "other-password"}
        ).json()
        other_device = bearer(other_grant["token"])
        assert client.get(devices_url, headers=other_device).json()["devices"][0]["id"] == other_grant["credential_id"]
        if mode == "accounts":
            assert client.get("/api/v1/merge-queue", headers=other_device).status_code == 403
        assert client.get(devices_url, headers=admin_auth).json()["devices"][0]["id"] == device

    reopened = Tianxuan(path)
    try:
        with TestClient(create_app(reopened), base_url="https://testserver") as client:
            auth = bearer(token)
            assert client.get("/api/v1/auth/me", headers=auth).json()["id"] == actor
            created = client.post("/api/v1/docs", headers=auth, json={"title": "actor record"})
            assert created.json()["created_by"] == actor
            reopened.set_role(owner["user_id"], actor, "viewer")
            assert client.get("/api/v1/auth/me", headers=auth).json()["role"] == "viewer"
            assert client.post("/api/v1/docs", headers=auth, json={"title": "forbidden"}).status_code == 403
            another = client.post(session_url, json=credentials).json()
            assert client.delete(devices_url + "/" + device, headers=admin_auth).json() == {"revoked": True}
            assert client.get("/api/v1/auth/me", headers=auth).status_code == 401
            assert client.post("/api/v1/auth/logout", headers=bearer(another["token"])).json() == {"revoked": True}
            assert client.get("/api/v1/auth/me", headers=bearer(another["token"])).status_code == 401
            events = reopened.identity_events(owner["user_id"])
            assert {(e["type"], e["actor"], e["target"]) for e in events} == {
                ("identity.editor_device.issued", actor, device),
                ("identity.editor_device.issued", actor, another["credential_id"]),
                ("identity.editor_device.revoked", owner["user_id"], device),
                ("identity.editor_device.revoked", actor, another["credential_id"]),
            }
    finally:
        reopened.db.close()


@pytest.mark.parametrize("mode", ["keys", "accounts"])
def test_only_admitted_persistent_admin_can_delegate_long_term_keys(domain, mode, monkeypatch):
    store, owner, user, other, _ = domain
    monkeypatch.setenv("TIANXUAN_AUTH_MODE", mode)
    root = owner["user_id"]
    bootstrap = store.issue_access_key(root, root, "host-authorized", until_revoked=True)
    limited = store.issue_access_key(root, root, "finite", days=1)
    ordinary = store.issue_session(root)
    device = store.login_editor_device("admin@example.invalid", "admin-password")
    recipient = user["user_id"]
    payload = {"user_id": recipient, "name": "editor", "until_revoked": True}
    route = "/api/v1/auth/keys"
    with TestClient(create_app(store), base_url="https://testserver") as client:
        if mode == "keys":
            assert client.get("/api/v1/docs", headers=bearer(device["token"])).status_code == 401
            creds = {"email": "admin@example.invalid", "password": "admin-password"}
            assert client.post("/api/v1/auth/editor-session", json=creds).status_code == 401
            assert (
                client.post("/api/v1/auth/editor-session", headers=bearer(limited["key"]), json=creds).status_code
                == 403
            )
        for token in (ordinary, limited["key"], device["token"]):
            assert client.post(route, headers=bearer(token), json=payload).status_code in (401, 403)
        for token in (limited["key"], ordinary) if mode == "accounts" else (limited["key"],):
            finite = client.post(route, headers=bearer(token), json={**payload, "days": 365, "until_revoked": False})
            assert finite.status_code == 200
            expiry = store.db.execute(
                "SELECT expires_at FROM sessions WHERE token_hash=?", (_token_hash(token),)
            ).fetchone()[0]
            assert finite.json()["expires_at"] == expiry
        admin = bearer(bootstrap["key"])
        assert client.post(route, headers=admin, json={**payload, "user_id": other["user_id"]}).status_code == 403
        assert client.post(route, headers=admin, json={**payload, "days": 5}).status_code == 400
        for days in (0, 366):
            assert (
                client.post(route, headers=admin, json={**payload, "days": days, "until_revoked": False}).status_code
                == 422
            )
        assert client.post(route + "/admin", headers=admin, json=payload).status_code == 409
        created = client.post(route, headers=admin, json=payload)
        assert created.status_code == 200 and created.headers["cache-control"] == "no-store"
        assert created.json()["expires_at"] == UNTIL_REVOKED
        token = created.json()["key"]
        auth = bearer(token)
        assert client.get("/api/v1/auth/me", headers=auth).json()["id"] == recipient
        assert client.post(route, headers=auth, json=payload).status_code == 403
        assert token not in client.get(route, headers=admin).text
        assert client.post("/api/v1/auth/logout", headers=auth).json() == {"revoked": False}
        assert client.get("/api/v1/docs", headers=auth).status_code == 200
        assert client.delete(route + "/" + created.json()["id"], headers=admin).json() == {"revoked": True}
        assert client.get("/api/v1/auth/me", headers=auth).status_code == 401


def test_editor_login_shares_existing_account_login_attempt_limit(domain, monkeypatch):
    store, *_ = domain
    monkeypatch.setenv("TIANXUAN_AUTH_MODE", "accounts")
    with TestClient(create_app(store), base_url="https://testserver") as client:
        for _ in range(30):
            assert (
                client.post("/api/v1/auth/session", json={"email": "missing", "password": "wrong"}).status_code == 401
            )
        assert (
            client.post(
                "/api/v1/auth/editor-session", json={"email": "admin@example.invalid", "password": "admin-password"}
            ).status_code
            == 429
        )


def test_editor_device_commit_uses_verified_account(domain, monkeypatch, tmp_path):
    from duobao_bridge import GitService

    store, owner, user, _, _ = domain
    monkeypatch.setenv("TIANXUAN_AUTH_MODE", "accounts")
    monkeypatch.setenv("TIANXUAN_REPO_ROOT", str(tmp_path))
    service = GitService()
    repo = service.create_repo(tmp_path, "code")
    service.commit(repo, "main", "initial", {"file.txt": "original"}, "Fixture", "fixture@example.invalid")
    with TestClient(create_app(store), base_url="https://testserver") as client:
        grant = client.post(
            "/api/v1/auth/editor-session", json={"email": "user@example.invalid", "password": "user-password"}
        ).json()
        auth = {**bearer(grant["token"]), "X-Actor": owner["user_id"]}
        route = "/api/v1/git/repos/code.git/file"
        before = client.get(route, headers=auth, params={"path": "file.txt"}).json()
        write = {
            "branch": "main",
            "path": "file.txt",
            "content": "new",
            "message": "edit",
            "expected_blob": before["sha"],
        }
        commit = client.post(route, headers=auth, json=write)
        assert commit.status_code == 200
        assert commit.json()["branch"].startswith("web/" + user["user_id"] + "/")
        assert service.log(repo, commit.json()["commit"], 1)[0]["email"] == "user@example.invalid"
        assert client.post("/api/v1/auth/logout", headers=auth).json() == {"revoked": True}
        assert client.post(route, headers=auth, json=write).status_code == 401
