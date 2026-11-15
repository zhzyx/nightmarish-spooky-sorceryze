"""就绪检查：数据库、仓库根与降级状态。"""

from __future__ import annotations

import pytest
from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


def _client() -> TestClient:
    return TestClient(create_app(Tianxuan(":memory:")))


def test_ready_without_repo_root() -> None:
    response = _client().get("/api/v1/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] is True
    assert body["checks"]["repo_root"] is None


def test_ready_reports_repo_root_state(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("TIANXUAN_REPO_ROOT", str(tmp_path))
    ready = _client().get("/api/v1/ready")
    assert ready.status_code == 200
    assert ready.json()["checks"]["repo_root"] is True

    monkeypatch.setenv("TIANXUAN_REPO_ROOT", str(tmp_path / "missing"))
    degraded = _client().get("/api/v1/ready")
    assert degraded.status_code == 503
    assert degraded.json()["status"] == "degraded"
    assert degraded.json()["checks"]["repo_root"] is False
