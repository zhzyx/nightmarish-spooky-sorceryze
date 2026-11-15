"""文档共享过期：未来有效期可读、过期后失效、非法时间拒绝。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


def _setup() -> tuple[TestClient, Tianxuan, dict[str, str], dict[str, str], dict[str, Any]]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    admin = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "共享工坊", "email": "admin@example.com", "password": "secret-pass"},
    ).json()
    viewer = store.add_member(admin["user_id"], "viewer@example.com", "secret-pass", role="viewer")
    headers = {"X-Actor": admin["user_id"]}
    viewer_headers = {"X-Actor": viewer["user_id"]}
    document = client.post(
        "/api/v1/docs",
        headers=headers,
        json={"title": "私密文档", "body_md": "# 共享\n"},
    ).json()
    store.set_visibility(admin["user_id"], document["id"], "private")
    return client, store, headers, viewer_headers, document


def _future(days: int = 1) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def test_future_share_expiry_grants_read_and_is_listed() -> None:
    client, _, headers, viewer_headers, document = _setup()
    expires_at = _future()
    created = client.post(
        f"/api/v1/docs/{document['id']}/shares",
        headers=headers,
        json={"user_id": viewer_headers["X-Actor"], "permission": "read", "expires_at": expires_at},
    )
    assert created.status_code == 200, created.text
    assert created.json()["expires_at"] is not None

    readable = client.get(f"/api/v1/docs/{document['id']}", headers=viewer_headers)
    assert readable.status_code == 200

    shares = client.get(f"/api/v1/docs/{document['id']}/shares", headers=headers).json()["shares"]
    assert [entry["user_id"] for entry in shares] == [viewer_headers["X-Actor"]]
    assert shares[0]["expires_at"] is not None


def test_expired_share_is_denied_and_hidden() -> None:
    client, store, headers, viewer_headers, document = _setup()
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    store.db.execute(
        "INSERT INTO doc_shares (doc_id, user_id, permission, created_by, created_at, expires_at) "
        "VALUES (?, ?, 'read', ?, ?, ?)",
        (document["id"], viewer_headers["X-Actor"], headers["X-Actor"], past, past),
    )
    store.db.commit()

    denied = client.get(f"/api/v1/docs/{document['id']}", headers=viewer_headers)
    assert denied.status_code in {403, 404}
    shares = client.get(f"/api/v1/docs/{document['id']}/shares", headers=headers).json()["shares"]
    assert shares == []


def test_share_rejects_invalid_or_past_expiry() -> None:
    client, _, headers, viewer_headers, document = _setup()
    payload = {"user_id": viewer_headers["X-Actor"], "permission": "read"}
    past = client.post(
        f"/api/v1/docs/{document['id']}/shares",
        headers=headers,
        json={**payload, "expires_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()},
    )
    assert past.status_code == 400
    invalid = client.post(
        f"/api/v1/docs/{document['id']}/shares",
        headers=headers,
        json={**payload, "expires_at": "not-a-date"},
    )
    assert invalid.status_code == 400
