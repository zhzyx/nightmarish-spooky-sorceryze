"""可插拔身份适配 API 测试。"""

from __future__ import annotations

import time

import identity
import pytest
from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


@pytest.fixture(autouse=True)
def _reset_attempts() -> None:
    identity.reset_identity_attempts()


def _client() -> tuple[TestClient, dict[str, str], str]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    admin = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "身份租户", "email": "admin@example.com", "password": "secret-pass"},
    ).json()
    headers = {"X-Actor": admin["user_id"]}
    member = client.post(
        "/api/v1/users",
        headers=headers,
        json={"email": "member@example.com", "password": "secret-pass", "role": "editor"},
    ).json()
    user_id = member.get("id") or member["user_id"]
    return client, headers, str(user_id)


def test_link_and_resolve_external_identity(monkeypatch) -> None:
    monkeypatch.setenv("TIANXUAN_IDENTITY_SECRET", "shared-secret")
    client, headers, user_id = _client()
    linked = client.post(
        "/api/v1/identity/links",
        headers=headers,
        json={"provider": "tianshu", "subject": "gh_123", "user_id": user_id},
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["user_id"] == user_id

    listed = client.get("/api/v1/identity/links", headers=headers, params={"provider": "tianshu"}).json()["links"]
    assert listed[0]["subject"] == "gh_123"

    resolved = client.post(
        "/api/v1/identity/resolve",
        json={"provider": "tianshu", "subject": "gh_123", "secret": "shared-secret"},
    )
    assert resolved.status_code == 200, resolved.text
    body = resolved.json()
    assert body["user_id"] == user_id
    assert body["token"]

    authorized = client.get("/api/v1/docs", headers={"Authorization": f"Bearer {body['token']}"})
    assert authorized.status_code == 200


def test_invalid_secret_and_unlinked_subject(monkeypatch) -> None:
    monkeypatch.setenv("TIANXUAN_IDENTITY_SECRET", "shared-secret")
    client, headers, user_id = _client()
    client.post(
        "/api/v1/identity/links",
        headers=headers,
        json={"provider": "tianshu", "subject": "gh_123", "user_id": user_id},
    )

    denied = client.post(
        "/api/v1/identity/resolve",
        json={"provider": "tianshu", "subject": "gh_123", "secret": "wrong"},
    )
    assert denied.status_code == 403

    unlinked = client.post(
        "/api/v1/identity/resolve",
        json={"provider": "tianshu", "subject": "gh_missing", "secret": "shared-secret"},
    )
    assert unlinked.status_code == 404

    unknown = client.post(
        "/api/v1/identity/resolve",
        json={"provider": "unknown", "subject": "x", "secret": "shared-secret"},
    )
    assert unknown.status_code == 400


def test_other_tenant_cannot_hijack_identity(monkeypatch) -> None:
    monkeypatch.setenv("TIANXUAN_IDENTITY_SECRET", "shared-secret")
    client, headers, user_id = _client()
    client.post(
        "/api/v1/identity/links",
        headers=headers,
        json={"provider": "tianshu", "subject": "gh_shared", "user_id": user_id},
    )
    other = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "另一租户", "email": "other@example.com", "password": "secret-pass"},
    ).json()
    other_headers = {"X-Actor": other["user_id"]}
    denied = client.post(
        "/api/v1/identity/links",
        headers=other_headers,
        json={"provider": "tianshu", "subject": "gh_shared", "user_id": other["user_id"]},
    )
    assert denied.status_code == 403
    resolved = client.post(
        "/api/v1/identity/resolve",
        json={"provider": "tianshu", "subject": "gh_shared", "secret": "shared-secret"},
    ).json()
    assert resolved["user_id"] == user_id


def test_non_admin_cannot_link_identity(monkeypatch) -> None:
    monkeypatch.setenv("TIANXUAN_IDENTITY_SECRET", "shared-secret")
    client, headers, user_id = _client()
    viewer = client.post(
        "/api/v1/users",
        headers=headers,
        json={"email": "viewer@example.com", "password": "secret-pass", "role": "viewer"},
    ).json()
    viewer_id = viewer.get("id") or viewer["user_id"]
    denied = client.post(
        "/api/v1/identity/links",
        headers={"X-Actor": viewer_id},
        json={"provider": "tianshu", "subject": "gh_1", "user_id": user_id},
    )
    assert denied.status_code == 403


def test_identity_resolve_is_rate_limited(monkeypatch) -> None:
    monkeypatch.setenv("TIANXUAN_IDENTITY_SECRET", "shared-secret")
    client, headers, user_id = _client()
    client.post(
        "/api/v1/identity/links",
        headers=headers,
        json={"provider": "tianshu", "subject": "gh_rate", "user_id": user_id},
    )
    for _ in range(30):
        denied = client.post(
            "/api/v1/identity/resolve",
            json={"provider": "tianshu", "subject": "gh_rate", "secret": "wrong"},
        )
        assert denied.status_code == 403
    limited = client.post(
        "/api/v1/identity/resolve",
        json={"provider": "tianshu", "subject": "gh_rate", "secret": "shared-secret"},
    )
    assert limited.status_code == 429


def test_admin_can_unbind_identity(monkeypatch) -> None:
    monkeypatch.setenv("TIANXUAN_IDENTITY_SECRET", "shared-secret")
    client, headers, user_id = _client()
    link = client.post(
        "/api/v1/identity/links",
        headers=headers,
        json={"provider": "tianshu", "subject": "gh_unbind", "user_id": user_id},
    ).json()
    deleted = client.delete(f"/api/v1/identity/links/{link['id']}", headers=headers)
    assert deleted.status_code == 200
    assert client.get("/api/v1/identity/links", headers=headers).json()["links"] == []
    gone = client.post(
        "/api/v1/identity/resolve",
        json={"provider": "tianshu", "subject": "gh_unbind", "secret": "shared-secret"},
    )
    assert gone.status_code == 404


def test_oidc_jwt_signature_and_claims(monkeypatch) -> None:
    monkeypatch.setenv("TIANXUAN_OIDC_SECRET", "oidc-secret")
    monkeypatch.setenv("TIANXUAN_OIDC_AUDIENCE", "tianxuan")
    client, headers, user_id = _client()
    client.post(
        "/api/v1/identity/links",
        headers=headers,
        json={"provider": "oidc", "subject": "oidc-user", "user_id": user_id},
    )
    valid = identity.encode_test_jwt(
        "oidc-secret",
        {"sub": "oidc-user", "aud": "tianxuan", "exp": time.time() + 60},
    )
    ok = client.post(
        "/api/v1/identity/resolve",
        json={"provider": "oidc", "subject": "oidc-user", "secret": valid},
    )
    assert ok.status_code == 200, ok.text

    expired = identity.encode_test_jwt(
        "oidc-secret",
        {"sub": "oidc-user", "aud": "tianxuan", "exp": time.time() - 1},
    )
    assert (
        client.post(
            "/api/v1/identity/resolve",
            json={"provider": "oidc", "subject": "oidc-user", "secret": expired},
        ).status_code
        == 403
    )

    wrong_subject = identity.encode_test_jwt(
        "oidc-secret",
        {"sub": "other", "aud": "tianxuan", "exp": time.time() + 60},
    )
    assert (
        client.post(
            "/api/v1/identity/resolve",
            json={"provider": "oidc", "subject": "oidc-user", "secret": wrong_subject},
        ).status_code
        == 403
    )

    bad_signature = identity.encode_test_jwt(
        "wrong-secret",
        {"sub": "oidc-user", "aud": "tianxuan", "exp": time.time() + 60},
    )
    assert (
        client.post(
            "/api/v1/identity/resolve",
            json={"provider": "oidc", "subject": "oidc-user", "secret": bad_signature},
        ).status_code
        == 403
    )

    wrong_audience = identity.encode_test_jwt(
        "oidc-secret",
        {"sub": "oidc-user", "aud": "other", "exp": time.time() + 60},
    )
    assert (
        client.post(
            "/api/v1/identity/resolve",
            json={"provider": "oidc", "subject": "oidc-user", "secret": wrong_audience},
        ).status_code
        == 403
    )
