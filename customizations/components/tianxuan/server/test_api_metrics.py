"""Prometheus 指标端点：管理员可读、普通成员拒绝。"""

from __future__ import annotations

from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


def _setup() -> tuple[TestClient, dict[str, str], dict[str, str]]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    admin = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "指标工坊", "email": "metrics@example.com", "password": "secret-pass"},
    ).json()
    viewer = store.add_member(admin["user_id"], "viewer@example.com", "secret-pass", role="viewer")
    headers = {"X-Actor": admin["user_id"]}
    viewer_headers = {"X-Actor": viewer["user_id"]}
    client.post("/api/v1/docs", headers=headers, json={"title": "指标文档", "body_md": "# 指标\n"})
    return client, headers, viewer_headers


def test_metrics_are_visible_to_admin() -> None:
    client, headers, _ = _setup()
    response = client.get("/api/v1/metrics", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert "tianxuan_docs_total 1" in body
    assert "tianxuan_issues_total 0" in body
    assert "tianxuan_import_jobs_total" in body


def test_metrics_reject_non_admin() -> None:
    client, _, viewer_headers = _setup()
    response = client.get("/api/v1/metrics", headers=viewer_headers)
    assert response.status_code == 403
