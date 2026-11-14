"""事件保留/清理接口测试。"""

from __future__ import annotations

from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


def _client() -> tuple[TestClient, Tianxuan, dict[str, str]]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    admin = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "保留租户", "email": "retention@example.com", "password": "secret-pass"},
    ).json()
    return client, store, {"X-Actor": admin["user_id"]}


def _age_all_events(store: Tianxuan) -> None:
    with store.db:
        store.db.execute("UPDATE events SET created_at = '2000-01-01T00:00:00+00:00'")


def test_prune_identity_events_only() -> None:
    client, store, headers = _client()
    actor = headers["X-Actor"]
    user = client.get("/api/v1/users", headers=headers).json()["users"][0]
    client.post(
        "/api/v1/identity/links",
        headers=headers,
        json={"provider": "tianshu", "subject": "gh_retention", "user_id": user["id"]},
    )
    _age_all_events(store)

    pruned = client.post(
        "/api/v1/events/prune",
        headers=headers,
        params={"older_than_days": 30, "type_prefix": "identity."},
    )
    assert pruned.status_code == 200, pruned.text
    assert pruned.json()["deleted"] == 1
    remaining = client.get("/api/v1/events", headers=headers).json()["events"]
    assert all(not event["type"].startswith("identity.") for event in remaining)
    assert remaining
    assert actor


def test_prune_requires_admin() -> None:
    client, _, headers = _client()
    viewer = client.post(
        "/api/v1/users",
        headers=headers,
        json={"email": "viewer-retention@example.com", "password": "secret-pass", "role": "viewer"},
    ).json()
    denied = client.post(
        "/api/v1/events/prune",
        headers={"X-Actor": viewer.get("id") or viewer["user_id"]},
        params={"older_than_days": 30},
    )
    assert denied.status_code == 403
