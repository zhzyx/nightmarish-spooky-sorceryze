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


RS256_JWK = {
    "kty": "RSA",
    "n": "n0aM4klM0cdstf2qOgNrUuowfOLe4EEUeVQfBk83eYBCTlsxhorlX5obppRaHawJsl7ugjZ6TgoSbzLUyu7XhP3UsP0kp63257EBCuPRfJAxKdOP11GhBbxrVOr5BBCDhq2ewbxKtIGbbC99Sf63e9QmQhAT8qxB6d7ckn6qzP7-_s0yLpzt0otf9Sd1r_r1r4PRcm9dNSBRR0Uset4tA_YkzehGEap9NELHF-Aj8P4nudEd-5UFsgUWk7tBCWXEu3jOOdGV_R-u610q2HzEeA28vqrKeI8peE0h7P5b1Ll6zIDrmNz4T0urI5MbmbGwK8GgGMJLtDg-q1yjrVZtLw",
    "e": "AQAB",
    "kid": "test-key-1",
}
RS256_TOKEN = (
    "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6InRlc3Qta2V5LTEifQ."
    "eyJzdWIiOiJvaWRjLXJzIiwiYXVkIjoidGlhbnh1YW4iLCJpc3MiOiJodHRwczovL2lzc3Vlci5leGFtcGxlIiwiZXhwIjo0MTAyNDQ0ODAwfQ."
    "gjIgGFrrwmS5kkmbke-wx0lnR_cijGQsrfLh3lmKlG24I0WGAIs-fArR_9p1gtHGdI2nku8HrXH_sMLL8F7hjIy19ueNxYrQBtpWdXlEwIT17bIr354wrQnZ5GdoYhEfgXOvT38NI5UstV3X1OYS1JhqSOh3SSDmDQMD39ol5S27q4eU4A8L6AlrZC-We8tGwUFGU-6Qlt6I2XHl3c4i07b4fKrCLr2ixJzuzpgZnggtW18kygWcuIaoB1OliBYIOJlcVcUpUX9iGxRIP0gQh5PvnvpTq5uWpsRinXa-8BpvijcPgmDjoP4XF3Ju5yJ1h1lR_w34SHAaNTJWiaw0Vg"
)


def test_oidc_rs256_jwks(monkeypatch) -> None:
    import json

    monkeypatch.setenv("TIANXUAN_OIDC_JWKS", json.dumps({"keys": [RS256_JWK]}))
    monkeypatch.setenv("TIANXUAN_OIDC_AUDIENCE", "tianxuan")
    monkeypatch.setenv("TIANXUAN_OIDC_ISSUER", "https://issuer.example")
    client, headers, user_id = _client()
    client.post(
        "/api/v1/identity/links",
        headers=headers,
        json={"provider": "oidc", "subject": "oidc-rs", "user_id": user_id},
    )
    ok = client.post(
        "/api/v1/identity/resolve",
        json={"provider": "oidc", "subject": "oidc-rs", "secret": RS256_TOKEN},
    )
    assert ok.status_code == 200, ok.text

    header, payload, signature = RS256_TOKEN.split(".")
    tampered_claims = identity._b64url_encode(  # noqa: SLF001
        json.dumps({"sub": "oidc-rs", "aud": "tianxuan", "exp": 4102444800}).encode()
    )
    tampered = f"{header}.{tampered_claims}.{signature}"
    assert (
        client.post(
            "/api/v1/identity/resolve",
            json={"provider": "oidc", "subject": "oidc-rs", "secret": tampered},
        ).status_code
        == 403
    )

    none_header = identity._b64url_encode(  # noqa: SLF001
        json.dumps({"alg": "none", "typ": "JWT"}).encode()
    )
    none_token = f"{none_header}.{payload}.{signature}"
    assert (
        client.post(
            "/api/v1/identity/resolve",
            json={"provider": "oidc", "subject": "oidc-rs", "secret": none_token},
        ).status_code
        == 403
    )


def test_admin_can_rebind_identity(monkeypatch) -> None:
    monkeypatch.setenv("TIANXUAN_IDENTITY_SECRET", "shared-secret")
    client, headers, user_id = _client()
    member = client.post(
        "/api/v1/users",
        headers=headers,
        json={"email": "second@example.com", "password": "secret-pass", "role": "editor"},
    ).json()
    second_id = member.get("id") or member["user_id"]
    link = client.post(
        "/api/v1/identity/links",
        headers=headers,
        json={"provider": "tianshu", "subject": "gh_rebind", "user_id": user_id},
    ).json()

    rebound = client.patch(
        f"/api/v1/identity/links/{link['id']}",
        headers=headers,
        json={"user_id": second_id},
    )
    assert rebound.status_code == 200, rebound.text
    assert rebound.json()["user_id"] == second_id

    resolved = client.post(
        "/api/v1/identity/resolve",
        json={"provider": "tianshu", "subject": "gh_rebind", "secret": "shared-secret"},
    ).json()
    assert resolved["user_id"] == second_id

    other = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "外部租户", "email": "outside@example.com", "password": "secret-pass"},
    ).json()
    denied = client.patch(
        f"/api/v1/identity/links/{link['id']}",
        headers=headers,
        json={"user_id": other["user_id"]},
    )
    assert denied.status_code == 404

    viewer = client.post(
        "/api/v1/users",
        headers=headers,
        json={"email": "viewer2@example.com", "password": "secret-pass", "role": "viewer"},
    ).json()
    viewer_id = viewer.get("id") or viewer["user_id"]
    forbidden = client.patch(
        f"/api/v1/identity/links/{link['id']}",
        headers={"X-Actor": viewer_id},
        json={"user_id": second_id},
    )
    assert forbidden.status_code == 403
