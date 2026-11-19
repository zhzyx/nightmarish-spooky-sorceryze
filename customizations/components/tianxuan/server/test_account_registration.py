import pytest
from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


def test_account_registration_cookie_and_isolation(monkeypatch):
    monkeypatch.setenv("TIANXUAN_AUTH_MODE", "accounts")
    monkeypatch.setenv("TIANXUAN_REQUIRE_KEYS", "0")
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://testserver")
    store = Tianxuan(":memory:")
    headers = {"Origin": "https://testserver"}
    with TestClient(create_app(store), base_url="https://testserver") as client:
        assert client.get("/api/v1/auth/config").json()["mode"] == "accounts"
        credentials = {"email": "one@example.com", "password": "long-password"}
        created = client.post("/api/v1/auth/register", headers=headers, json={**credentials, "tenant_name": "One"})
        assert created.status_code == 200
        login = client.post("/api/v1/auth/session", headers=headers, json=credentials)
        assert login.status_code == 200
        assert "token" not in login.json()
        assert "HttpOnly" in login.headers["set-cookie"]
        assert "Secure" in login.headers["set-cookie"]
        assert client.get("/api/v1/auth/me").json()["id"] == created.json()["user_id"]
        assert client.post("/api/v1/docs", json={"title": "Denied"}).status_code == 403
        doc = client.post("/api/v1/docs", headers=headers, json={"title": "Private", "body_md": "# Text"})
        assert doc.status_code == 200
        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
        assert client.get("/api/v1/docs").status_code == 401
        other = {"email": "two@example.com", "password": "long-password"}
        assert client.post("/api/v1/auth/register", headers=headers, json={**other, "tenant_name": "Two"}).status_code == 200
        assert client.post("/api/v1/auth/session", headers=headers, json=other).status_code == 200
        assert client.get(f"/api/v1/docs/{doc.json()['id']}").status_code in {403, 404}
    store.db.close()

def test_account_mode_preserves_admitted_personal_keys(monkeypatch):
    monkeypatch.setenv("TIANXUAN_AUTH_MODE", "accounts")
    monkeypatch.setenv("TIANXUAN_REQUIRE_KEYS", "0")
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://testserver")
    store = Tianxuan(":memory:")
    owner = store.register("Existing", "key@example.com", "long-password")
    key = store.issue_access_key(owner["user_id"], owner["user_id"], "existing")["key"]
    monkeypatch.setenv("TIANXUAN_TENANT_ID", owner["tenant_id"])
    with TestClient(create_app(store), base_url="https://testserver") as client:
        assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {key}"}).json()["id"] == owner["user_id"]
        response = client.post("/api/v1/auth/key-login", headers={"Origin": "https://testserver"}, json={"key": key})
        assert response.status_code == 200
        assert client.get("/api/v1/auth/me").json()["id"] == owner["user_id"]
        other = store.register("Other", "other@example.com", "long-password")
        other_key = store.issue_access_key(other["user_id"], other["user_id"], "other")["key"]
        assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {other_key}"}).status_code == 401
        switched = client.post(
            "/api/v1/auth/session", headers={"Origin": "https://testserver"},
            json={"email": "other@example.com", "password": "long-password"},
        )
        assert switched.status_code == 200
        assert "__Host-tianxuan_key" not in client.cookies
        assert client.get("/api/v1/auth/me").json()["id"] == other["user_id"]
        assert client.post("/api/v1/auth/key-login", headers={"Origin": "https://testserver"}, json={"key": key}).status_code == 200
        assert "__Host-tianxuan_session" not in client.cookies
        assert client.get("/api/v1/auth/me").json()["id"] == owner["user_id"]
    store.db.close()

def test_explicit_keys_mode_requires_production_configuration(monkeypatch):
    monkeypatch.setenv("TIANXUAN_AUTH_MODE", "keys")
    monkeypatch.delenv("TIANXUAN_REQUIRE_KEYS", raising=False)
    monkeypatch.delenv("TIANXUAN_TENANT_ID", raising=False)
    monkeypatch.delenv("TIANXUAN_PUBLIC_ORIGIN", raising=False)
    store = Tianxuan(":memory:")
    with pytest.raises(RuntimeError, match="production key access"):
        create_app(store)
    store.db.close()


def test_new_workspace_cannot_manage_shared_merge_queue(monkeypatch):
    monkeypatch.setenv("TIANXUAN_AUTH_MODE", "accounts")
    monkeypatch.setenv("TIANXUAN_REQUIRE_KEYS", "0")
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://testserver")
    monkeypatch.setenv("TIANXUAN_TENANT_ID", "original-deployment")
    store = Tianxuan(":memory:")
    owner = store.register("New", "new@example.com", "long-password")
    token = store.issue_session(owner["user_id"])
    with TestClient(create_app(store), base_url="https://testserver") as client:
        headers = {"Authorization": f"Bearer {token}"}
        for path in ["/api/v1/merge-queue", "/api/v1/merge-queue/workers", "/api/v1/metrics", "/api/v1/ready"]:
            assert client.get(path, headers=headers).status_code == 403
        assert client.post("/api/v1/merge-queue/process", headers=headers).status_code == 403
        assert client.get("/api/v1/docs", headers=headers).status_code == 200
    store.db.close()
