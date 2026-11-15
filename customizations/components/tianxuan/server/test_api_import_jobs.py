"""仓库异步导入任务：成功、失败、列表与租户隔离。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import api as api_module
import pytest
from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


def _client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[TestClient, Tianxuan, dict[str, str]]:
    monkeypatch.setenv("TIANXUAN_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("TIANXUAN_IMPORT_JOBS_INLINE", "1")
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    admin = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "导入工坊", "email": "import@example.com", "password": "secret-pass"},
    ).json()
    return client, store, {"X-Actor": admin["user_id"]}


def test_import_job_succeeds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, _, headers = _client(monkeypatch, tmp_path)

    def fake_import(self: Any, root: Any, name: str, source: str, **kwargs: Any) -> Path:
        return Path(root) / name

    monkeypatch.setattr(api_module.GitService, "import_repo", fake_import)
    created = client.post(
        "/api/v1/git/import-jobs",
        headers=headers,
        json={"name": "demo.git", "source": "https://example.com/demo.git"},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["status"] == "succeeded"
    assert body["phase"] == "done"
    assert body["path"].endswith("demo.git")

    fetched = client.get(f"/api/v1/git/import-jobs/{body['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]

    listed = client.get("/api/v1/git/import-jobs", headers=headers).json()["jobs"]
    assert [job["id"] for job in listed] == [body["id"]]


def test_import_job_records_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, _, headers = _client(monkeypatch, tmp_path)

    def failing_import(self: Any, root: Any, name: str, source: str, **kwargs: Any) -> Path:
        raise api_module.GitServiceError("clone failed")

    monkeypatch.setattr(api_module.GitService, "import_repo", failing_import)
    created = client.post(
        "/api/v1/git/import-jobs",
        headers=headers,
        json={"name": "broken.git", "source": "https://example.com/broken.git"},
    )
    assert created.status_code == 200
    body = created.json()
    assert body["status"] == "failed"
    assert body["phase"] == "failed"
    assert "clone failed" in body["error"]


def test_import_job_requires_admin_and_tenant(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, store, headers = _client(monkeypatch, tmp_path)
    viewer = store.add_member(headers["X-Actor"], "viewer@example.com", "secret-pass", role="viewer")
    denied = client.post(
        "/api/v1/git/import-jobs",
        headers={"X-Actor": viewer["user_id"]},
        json={"name": "x.git", "source": "https://example.com/x.git"},
    )
    assert denied.status_code == 403

    other = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "另一个租户", "email": "other@example.com", "password": "secret-pass"},
    ).json()
    job_id = store.create_import_job(headers["X-Actor"], "y.git", "https://example.com/y.git")["id"]
    cross = client.get(f"/api/v1/git/import-jobs/{job_id}", headers={"X-Actor": other["user_id"]})
    assert cross.status_code == 404
