"""本地 Git 仓库浏览 API 测试：仓库列表、分支、提交日志与 diff。"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

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
        json={"tenant_name": "Git 工坊", "email": "git@example.com", "password": "secret-pass"},
    ).json()
    return client, {"X-Actor": registered["user_id"]}


def _repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[GitService, str, str, str]:
    git = os.environ.get("GIT_EXECUTABLE") or shutil.which("git") or ""
    if not git:
        pytest.skip("git executable not available")
    monkeypatch.setenv("GIT_EXECUTABLE", git)
    monkeypatch.setenv("TIANXUAN_REPO_ROOT", str(tmp_path))
    service = GitService(git)
    repo = service.create_repo(tmp_path, "docs")
    first = service.commit(repo, "main", "one", {"a.md": "# one\n"}, "T", "t@example.invalid")
    second = service.commit(repo, "main", "two", {"a.md": "# two\n"}, "T", "t@example.invalid")
    return service, Path(repo).name, first, second


def test_git_repo_browser(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _, name, first, second = _repo(monkeypatch, tmp_path)
    client, headers = _client()

    repos = client.get("/api/v1/git/repos", headers=headers).json()["repos"]
    assert repos == [name]

    branches = client.get(f"/api/v1/git/repos/{name}/branches", headers=headers).json()["branches"]
    assert branches == ["main"]

    log = client.get(f"/api/v1/git/repos/{name}/log", headers=headers).json()["commits"]
    assert log[0]["sha"] == second

    diff = client.get(f"/api/v1/git/repos/{name}/diff", headers=headers, params={"a": first, "b": second}).json()[
        "diff"
    ]
    assert "-# one" in diff
    assert "+# two" in diff


def test_git_repo_requires_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TIANXUAN_REPO_ROOT", raising=False)
    client, headers = _client()
    assert client.get("/api/v1/git/repos", headers=headers).status_code == 400
    assert client.get("/api/v1/git/repos/missing.git/branches", headers=headers).status_code == 400


def test_git_repo_unknown_name(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _repo(monkeypatch, tmp_path)
    client, headers = _client()
    assert client.get("/api/v1/git/repos/missing.git/branches", headers=headers).status_code == 400
