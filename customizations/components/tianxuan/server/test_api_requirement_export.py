"""偃师需求 Markdown 导出与受控 Git 落库测试。"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from api import create_app
from duobao_bridge import GitService
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


def _client() -> tuple[TestClient, dict[str, str]]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": "落库工坊",
            "email": "export@example.com",
            "password": "secret-pass",
            "name": "Owner",
        },
    ).json()
    return client, {"X-Actor": registered["user_id"]}


def _requirement(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    return client.post(  # type: ignore[no-any-return]
        "/api/v1/requirements",
        headers=headers,
        json={
            "request_id": "tx-export-1",
            "title": "导出需求",
            "outcome": "需求可落库为 Git Markdown",
            "scope": "导出与提交",
            "acceptance": "仓库中存在 design/tx-export-1.md",
        },
    ).json()


def test_export_contains_requirement_and_tickets() -> None:
    client, headers = _client()
    requirement = _requirement(client, headers)
    planned = client.post(
        f"/api/v1/requirements/{requirement['id']}/tickets",
        headers=headers,
        json={"tickets": [{"title": "实现导出", "acceptance": "通过"}]},
    )
    assert planned.status_code == 200, planned.text

    body = client.get("/api/v1/requirements/tx-export-1/export", headers=headers).json()
    assert body["filename"] == "tx-export-1.md"
    assert "request_id: tx-export-1" in body["markdown"]
    assert "# 导出需求" in body["markdown"]
    assert "实现导出" in body["markdown"]


def test_export_unknown_requirement() -> None:
    client, headers = _client()
    assert client.get("/api/v1/requirements/missing/export", headers=headers).status_code == 404


def test_commit_requires_configured_root(monkeypatch: pytest.MonkeyPatch) -> None:
    client, headers = _client()
    _requirement(client, headers)
    monkeypatch.delenv("TIANXUAN_REPO_ROOT", raising=False)
    response = client.post(
        "/api/v1/requirements/tx-export-1/commit",
        headers=headers,
        json={"repo": "docs"},
    )
    assert response.status_code == 400
    assert "TIANXUAN_REPO_ROOT" in response.json()["detail"]


def test_commit_rejects_escaping_repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, headers = _client()
    _requirement(client, headers)
    monkeypatch.setenv("TIANXUAN_REPO_ROOT", str(tmp_path))
    response = client.post(
        "/api/v1/requirements/tx-export-1/commit",
        headers=headers,
        json={"repo": "../escape"},
    )
    assert response.status_code == 400
    assert "escapes" in response.json()["detail"]


def test_commit_writes_markdown_to_bare_repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    git = os.environ.get("GIT_EXECUTABLE") or shutil.which("git") or ""
    if not git:
        pytest.skip("git executable not available")
    monkeypatch.setenv("GIT_EXECUTABLE", git)
    monkeypatch.setenv("TIANXUAN_REPO_ROOT", str(tmp_path))
    service = GitService(git)
    repo = service.create_repo(tmp_path, "docs")
    repo_name = Path(repo).name

    client, headers = _client()
    requirement = _requirement(client, headers)
    client.post(
        f"/api/v1/requirements/{requirement['id']}/tickets",
        headers=headers,
        json={"tickets": [{"title": "实现导出", "acceptance": "通过"}]},
    )

    response = client.post(
        "/api/v1/requirements/tx-export-1/commit",
        headers=headers,
        json={"repo": repo_name, "branch": "main", "message": "docs: export requirement"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["path"] == "design/tx-export-1.md"
    assert body["branch"] == "main"
    assert len(body["commit"]) == 40

    log = service.log(repo, "main", 5)
    assert any(item["sha"] == body["commit"] for item in log)

    clone_dir = tmp_path / "clone"
    subprocess.run([git, "clone", "--quiet", repo, str(clone_dir)], check=True, capture_output=True)
    content = (clone_dir / "design" / "tx-export-1.md").read_text(encoding="utf-8")
    assert "# 导出需求" in content
    assert "实现导出" in content

    expected = client.get("/api/v1/requirements/tx-export-1/export", headers=headers).json()["markdown"]
    readback = client.get(
        "/api/v1/requirements/tx-export-1/git-file",
        headers=headers,
        params={"repo": repo_name, "ref": body["commit"]},
    )
    assert readback.status_code == 200, readback.text
    assert readback.json()["markdown"] == expected
    assert readback.json()["path"] == "design/tx-export-1.md"

    missing_ref = client.get(
        "/api/v1/requirements/tx-export-1/git-file",
        headers=headers,
        params={"repo": repo_name, "ref": "deadbeef"},
    )
    assert missing_ref.status_code == 400
