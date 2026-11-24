"""Independent same-account device grants preserve role and parent revocation."""

import pytest
from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


@pytest.fixture
def setup(monkeypatch):
    domain = Tianxuan()
    owner = domain.register("devices", "owner@example.invalid", "password")
    key = domain.issue_access_key(owner["user_id"], owner["user_id"], "source")
    monkeypatch.setenv("TIANXUAN_REQUIRE_KEYS", "1")
    monkeypatch.setenv("TIANXUAN_AUTH_MODE", "keys")
    monkeypatch.setenv("TIANXUAN_TENANT_ID", owner["tenant_id"])
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://testserver")
    app = create_app(domain)
    with TestClient(app, base_url="https://testserver") as a, TestClient(app, base_url="https://testserver") as b:
        yield domain, owner, key, a, b
    domain.db.close()


def login(client, key):
    response = client.post("/api/v1/auth/key-login", headers={"Origin": "https://testserver"}, json={"key": key})
    assert response.status_code == 200, response.text
    return response.json()


def test_shared_key_creates_independent_device_grants(setup):
    domain, owner, key, a, b = setup
    one, two = login(a, key["key"]), login(b, key["key"])
    assert one["device_id"] != two["device_id"]
    assert one["credential_id"] != two["credential_id"]
    for client, grant in ((a, one), (b, two)):
        me = client.get("/api/v1/auth/me", headers={"X-Device-ID": "forged", "X-Actor": "forged"}).json()
        assert me["id"] == owner["user_id"] and me["device_id"] == grant["device_id"]
        assert (
            client.post(
                "/api/v1/docs", headers={"Origin": "https://testserver"}, json={"title": grant["device_id"]}
            ).status_code
            == 200
        )
    assert a.post("/api/v1/auth/key-logout", headers={"Origin": "https://testserver"}).status_code == 200
    assert a.get("/api/v1/auth/me").status_code == 401
    assert b.get("/api/v1/auth/me").status_code == 200
    assert domain.user_for_access_key(key["key"]) == owner["user_id"]
    domain.revoke_access_key(owner["user_id"], key["id"])
    assert b.get("/api/v1/auth/me").status_code == 401


def test_native_enrollment_revoke_and_no_delegation(setup):
    domain, owner, key, a, _ = setup
    h = {"Authorization": "Bearer " + key["key"]}
    first = a.post("/api/v1/auth/device-session", headers=h).json()
    second = a.post("/api/v1/auth/device-session", headers=h).json()
    child = {"Authorization": "Bearer " + first["token"]}
    assert a.post("/api/v1/auth/device-session", headers=child).status_code == 403
    assert a.delete("/api/v1/auth/devices/" + first["device_id"], headers=h).status_code == 200
    assert a.get("/api/v1/auth/me", headers=child).status_code == 401
    assert a.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + second["token"]}).status_code == 200
    member = domain.add_member(owner["user_id"], "view@example.invalid", "password", role="viewer")
    other = domain.issue_access_key(owner["user_id"], member["user_id"], "view")
    other_h = {"Authorization": "Bearer " + other["key"]}
    assert a.delete("/api/v1/auth/devices/" + second["device_id"], headers=other_h).status_code == 404
    device = a.post("/api/v1/auth/device-session", headers=other_h).json()
    assert (
        a.post("/api/v1/docs", headers={"Authorization": "Bearer " + device["token"]}, json={"title": "no"}).status_code
        == 403
    )
    serialized = a.get("/api/v1/auth/devices", headers=h).text
    assert key["key"] not in serialized and first["token"] not in serialized


def test_password_sessions_coexist_and_keep_device_identity(monkeypatch):
    monkeypatch.delenv("TIANXUAN_AUTH_MODE", raising=False)
    monkeypatch.delenv("TIANXUAN_REQUIRE_KEYS", raising=False)
    domain = Tianxuan()
    domain.register("devices", "password@example.invalid", "password")
    with TestClient(create_app(domain)) as client:
        payload = {"email": "password@example.invalid", "password": "password"}
        first = client.post("/api/v1/auth/session", json=payload).json()
        second = client.post("/api/v1/auth/session", json=payload).json()
        assert first["device_id"] != second["device_id"]
        assert domain.device_context(first["token"])["device_id"] == first["device_id"]
        assert domain.user_for_token(second["token"]) == domain.user_for_token(first["token"])
    domain.db.close()


def test_stale_account_cookie_cannot_replace_key_identity(setup):
    from access_control import COOKIE, SESSION_COOKIE

    domain, owner, key, a, _ = setup
    other = domain.register("other", "other@example.invalid", "password")
    stale = domain.issue_session(other["user_id"])
    a.cookies.set(SESSION_COOKIE, stale)
    a.cookies.set(COOKIE, key["key"])
    me = a.get("/api/v1/auth/me").json()
    assert me["id"] == owner["user_id"]
    assert me["device_id"] == domain.device_context(key["key"])["device_id"]
    enrolled = a.post("/api/v1/auth/device-session", headers={"Origin": "https://testserver"}).json()
    assert enrolled["user_id"] == owner["user_id"]
    assert a.post("/api/v1/auth/key-logout", headers={"Origin": "https://testserver"}).status_code == 200
    assert domain.user_for_token(stale) == other["user_id"]


def test_revocation_between_resolve_and_device_binding_rejects(setup, monkeypatch):
    domain, _, key, a, _ = setup
    monkeypatch.setattr(domain, "device_context", lambda token: None)
    response = a.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + key["key"]})
    assert response.status_code == 401


def test_device_registration_survives_restart_and_source_expiry(tmp_path):
    from tianxuan_core import _token_hash

    database = str(tmp_path / "identity.sqlite")
    domain = Tianxuan(database)
    owner = domain.register("persistent", "owner@example.invalid", "password")["user_id"]
    key = domain.issue_access_key(owner, owner, "source")["key"]
    grants = [domain.issue_device_session(key) for _ in range(2)]
    domain.db.close()
    domain = Tianxuan(database)
    try:
        for grant in grants:
            assert domain.user_for_access_key(grant["token"]) == owner
            assert domain.device_context(grant["token"]) == {
                name: grant[name] for name in ("device_id", "credential_id")
            }
        domain.db.execute(
            "UPDATE sessions SET expires_at=? WHERE token_hash=?",
            ("2000-01-01T00:00:00+00:00", _token_hash(key)),
        )
        domain.db.commit()
        for grant in grants:
            assert domain.user_for_access_key(grant["token"]) is None
            assert domain.device_context(grant["token"]) is None
    finally:
        domain.db.close()


def test_expiry_during_enrollment_rolls_back_child(setup, monkeypatch):
    from tianxuan_core import PermissionDenied

    domain, _, key, _, _ = setup
    before = domain.db.execute("SELECT count(*) FROM sessions").fetchone()[0]
    monkeypatch.setattr(domain, "device_context", lambda token: None)
    with pytest.raises(PermissionDenied, match="expired during device enrollment"):
        domain.issue_device_session(key["key"])
    assert domain.db.execute("SELECT count(*) FROM sessions").fetchone()[0] == before


def test_legacy_sessions_migrate_once_and_identity_reads_need_no_write_lock(tmp_path):
    import sqlite3

    database = str(tmp_path / "legacy.sqlite")
    domain = Tianxuan(database)
    owner = domain.register("legacy", "owner@example.invalid", "password")["user_id"]
    tokens = [domain.issue_session(owner) for _ in range(2)]
    domain.db.execute("DROP TABLE session_devices")
    domain.db.commit()
    domain.db.close()
    domain = Tianxuan(database)
    contexts = [domain.device_context(token) for token in tokens]
    assert contexts[0] != contexts[1]
    domain.db.close()
    domain = Tianxuan(database)
    blocker = sqlite3.connect(database)
    try:
        before = list(domain.db.iterdump())
        blocker.execute("BEGIN IMMEDIATE")
        domain.db.execute("PRAGMA busy_timeout=5")
        assert [domain.device_context(token) for token in tokens] == contexts
        assert list(domain.db.iterdump()) == before
    finally:
        blocker.close()
        domain.db.close()


@pytest.mark.parametrize("mode", ["accounts", "keys"])
def test_persistent_devices_keep_distinct_audit_identity_and_revoke_independently(tmp_path, monkeypatch, mode):
    from tianxuan_core import UNTIL_REVOKED, _token_hash

    monkeypatch.setenv("TIANXUAN_AUTH_MODE", mode)
    monkeypatch.setenv("TIANXUAN_REQUIRE_KEYS", "1" if mode == "keys" else "0")
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://testserver")
    path = str(tmp_path / "persistent.sqlite")
    domain = Tianxuan(path)
    owner = domain.register("persistent", "owner@example.invalid", "password")
    monkeypatch.setenv("TIANXUAN_TENANT_ID", owner["tenant_id"])
    key = domain.issue_access_key(owner["user_id"], owner["user_id"], "source", until_revoked=True)
    with TestClient(create_app(domain), base_url="https://testserver") as client:
        grants = []
        for _ in range(2):
            if mode == "accounts":
                response = client.post(
                    "/api/v1/auth/editor-session", json={"email": "owner@example.invalid", "password": "password"}
                )
            else:
                response = client.post("/api/v1/auth/device-session", headers={"Authorization": "Bearer " + key["key"]})
            assert response.status_code == 200, response.text
            grants.append(response.json())
        assert grants[0]["device_id"] != grants[1]["device_id"]
        assert grants[0]["credential_id"] != grants[1]["credential_id"]
    domain.db.close()
    domain = Tianxuan(path)
    try:
        with TestClient(create_app(domain), base_url="https://testserver") as client:
            headers = [{"Authorization": "Bearer " + g["token"]} for g in grants]
            for grant, header in zip(grants, headers):
                me = client.get("/api/v1/auth/me", headers=header).json()
                assert me["id"] == owner["user_id"]
                assert all(me[k] == grant[k] for k in ("device_id", "credential_id"))
                assert (
                    domain.db.execute(
                        "SELECT expires_at FROM sessions WHERE token_hash=?", (_token_hash(grant["token"]),)
                    ).fetchone()[0]
                    == UNTIL_REVOKED
                )
            assert (
                client.delete("/api/v1/auth/devices/" + grants[0]["device_id"], headers=headers[1]).status_code == 200
            )
            assert client.get("/api/v1/auth/me", headers=headers[0]).status_code == 401
            assert client.get("/api/v1/auth/me", headers=headers[1]).status_code == 200
            if mode == "accounts":
                devices = client.get("/api/v1/auth/editor-devices", headers=headers[1]).json()["devices"]
                assert [d["id"] for d in devices] == [grants[1]["credential_id"]]
                assert (
                    client.delete(
                        "/api/v1/auth/editor-devices/" + grants[1]["credential_id"], headers=headers[1]
                    ).status_code
                    == 200
                )
            else:
                domain.revoke_access_key(owner["user_id"], key["id"])
            assert client.get("/api/v1/auth/me", headers=headers[1]).status_code == 401
    finally:
        domain.db.close()


def test_existing_editor_device_keeps_credential_label_during_migration(tmp_path):
    path = str(tmp_path / "editor-migration.sqlite")
    domain = Tianxuan(path)
    domain.register("editor", "owner@example.invalid", "password")
    grant = domain.login_editor_device("owner@example.invalid", "password")
    domain.db.execute("DROP TABLE session_devices")
    domain.db.commit()
    domain.db.close()
    domain = Tianxuan(path)
    try:
        context = domain.device_context(grant["token"])
        assert context["credential_id"] == grant["credential_id"]
        assert context["device_id"] != context["credential_id"]
        assert domain.revoke_editor_device(grant["user_id"], context["credential_id"])
        assert domain.user_for_token(grant["token"]) is None
    finally:
        domain.db.close()


def test_source_revoked_by_another_connection_during_enrollment_is_rejected(tmp_path, monkeypatch):
    from tianxuan_core import PermissionDenied

    path = str(tmp_path / "revocation-race.sqlite")
    domain = Tianxuan(path)
    owner = domain.register("race", "owner@example.invalid", "password")["user_id"]
    key = domain.issue_access_key(owner, owner, "source")
    other = Tianxuan(path)
    original = domain.issue_session
    before = domain.db.execute("SELECT count(*) FROM session_devices").fetchone()[0]

    def revoke_before_child(actor):
        other.revoke_access_key(owner, key["id"])
        return original(actor)

    monkeypatch.setattr(domain, "issue_session", revoke_before_child)
    try:
        with pytest.raises(PermissionDenied, match="expired during device enrollment"):
            domain.issue_device_session(key["key"])
        assert domain.user_for_access_key(key["key"]) is None
        assert domain.db.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0
        assert domain.db.execute("SELECT count(*) FROM session_devices").fetchone()[0] == before
    finally:
        other.db.close()
        domain.db.close()


def test_legacy_bearer_cannot_write_after_device_binding_is_lost(monkeypatch):
    monkeypatch.setenv("TIANXUAN_AUTH_MODE", "legacy")
    monkeypatch.setenv("TIANXUAN_REQUIRE_KEYS", "0")
    domain = Tianxuan()
    owner = domain.register("legacy", "owner@example.invalid", "password")["user_id"]
    token = domain.issue_session(owner)
    monkeypatch.setattr(domain, "device_context", lambda credential: None)
    try:
        with TestClient(create_app(domain)) as client:
            response = client.post(
                "/api/v1/docs", headers={"Authorization": "Bearer " + token}, json={"title": "rejected"}
            )
            assert response.status_code == 401
            assert domain.list_docs(owner) == []
    finally:
        domain.db.close()
