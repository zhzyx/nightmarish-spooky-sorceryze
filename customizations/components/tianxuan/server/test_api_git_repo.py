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


def _client(protected_branches: tuple[str, ...] = ()) -> tuple[TestClient, dict[str, str]]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store, protected_branches=protected_branches))
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


def test_git_tree_and_branch_crud(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _, name, first, _ = _repo(monkeypatch, tmp_path)
    client, headers = _client()

    tree = client.get(f"/api/v1/git/repos/{name}/tree", headers=headers).json()["entries"]
    assert [(entry["name"], entry["type"]) for entry in tree] == [("a.md", "blob")]

    created = client.post(
        f"/api/v1/git/repos/{name}/branches",
        headers=headers,
        json={"name": "feature", "start": first},
    )
    assert created.json() == {"branch": "feature", "sha": first}
    branches = client.get(f"/api/v1/git/repos/{name}/branches", headers=headers).json()["branches"]
    assert "feature" in branches

    deleted = client.delete(f"/api/v1/git/repos/{name}/branches/feature", headers=headers)
    assert deleted.json() == {"branch": "feature", "deleted": True}


def test_protected_branch_mutation_requires_admin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _, name, first, _ = _repo(monkeypatch, tmp_path)
    client, headers = _client(protected_branches=("release/*",))
    store = client.app.state.store  # type: ignore[attr-defined]
    editor = store.add_member(headers["X-Actor"], "editor@example.com", "secret-pass", role="editor")
    editor_headers = {"X-Actor": editor["user_id"]}

    denied = client.post(
        f"/api/v1/git/repos/{name}/branches",
        headers=editor_headers,
        json={"name": "release/1.0", "start": first},
    )
    assert denied.status_code == 403
    assert "protected" in denied.json()["detail"]

    allowed = client.post(
        f"/api/v1/git/repos/{name}/branches",
        headers=headers,
        json={"name": "release/1.0", "start": first},
    )
    assert allowed.status_code == 200

    assert client.delete(f"/api/v1/git/repos/{name}/branches/release/1.0", headers=editor_headers).status_code == 403
    assert client.delete(f"/api/v1/git/repos/{name}/branches/release/1.0", headers=headers).status_code == 200


def test_import_and_tags_endpoints(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _, name, _, _ = _repo(monkeypatch, tmp_path)
    monkeypatch.setenv("TIANXUAN_IMPORT_ALLOW_LOCAL", "1")
    client, headers = _client()
    source = str(tmp_path / name)

    response = client.post(
        "/api/v1/git/import",
        headers=headers,
        json={"name": "mirror", "source": source},
    )
    assert response.status_code == 200, response.text
    imported = response.json()
    assert imported["mirror"] is True
    assert imported["default_branch"] == "main"
    assert "main" in imported["branches"]

    repos = client.get("/api/v1/git/repos", headers=headers).json()["repos"]
    assert "mirror.git" in repos
    tags = client.get("/api/v1/git/repos/mirror.git/tags", headers=headers).json()["tags"]
    assert tags == []


def test_import_requires_admin_and_local_opt_in(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _, name, _, _ = _repo(monkeypatch, tmp_path)
    client, headers = _client()
    store = client.app.state.store  # type: ignore[attr-defined]
    editor = store.add_member(headers["X-Actor"], "editor@example.com", "secret-pass", role="editor")
    editor_headers = {"X-Actor": editor["user_id"]}
    source = str(tmp_path / name)

    monkeypatch.setenv("TIANXUAN_IMPORT_ALLOW_LOCAL", "1")
    denied = client.post(
        "/api/v1/git/import",
        headers=editor_headers,
        json={"name": "mirror", "source": source},
    )
    assert denied.status_code == 403

    monkeypatch.delenv("TIANXUAN_IMPORT_ALLOW_LOCAL", raising=False)
    blocked = client.post(
        "/api/v1/git/import",
        headers=headers,
        json={"name": "mirror", "source": source},
    )
    assert blocked.status_code == 400
