"""Gitea 仓库接入 API 测试：状态、未配置、创建与读取仓库（假客户端）。"""

from __future__ import annotations

from typing import Any

import api as api_module
from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


class _FakeGitea:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url
        self.token = token

    def __enter__(self) -> _FakeGitea:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def create_repo(self, name: str, private: bool = True, default_branch: str = "main") -> dict[str, Any]:
        return {"name": name, "private": private, "default_branch": default_branch}

    def get_repo(self, owner: str, name: str) -> dict[str, Any]:
        return {"full_name": f"{owner}/{name}", "owner": owner, "name": name}

    def list_repos(self, owner: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return [{"full_name": f"{owner or 'me'}/demo", "limit": limit}]

    def list_branches(self, owner: str, repo: str) -> list[dict[str, Any]]:
        return [{"name": "main", "protected": False, "commit_sha": "abc123"}]

    def list_pull_requests(self, owner: str, repo: str, state: str = "open") -> list[dict[str, Any]]:
        return [{"number": 1, "title": "demo", "state": state}]

    def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: str = "",
    ) -> dict[str, Any]:
        return {"number": 2, "title": title, "head": head, "base": base, "body": body}

    def merge_pull_request(self, owner: str, repo: str, number: int, method: str = "merge") -> dict[str, Any]:
        return {"number": number, "merged": True, "method": method}


def _setup() -> tuple[TestClient, dict[str, str]]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    registered = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "仓库工坊", "email": "repo@example.com", "password": "secret-pass"},
    ).json()
    return client, {"X-Actor": registered["user_id"]}


def test_status_unconfigured_and_repo_rejected(monkeypatch) -> None:
    monkeypatch.delenv("TIANXUAN_GITEA_URL", raising=False)
    monkeypatch.delenv("TIANXUAN_GITEA_TOKEN", raising=False)
    client, headers = _setup()

    status = client.get("/api/v1/gitea/status").json()
    assert status["configured"] is False
    assert client.post("/api/v1/repos", headers=headers, json={"name": "demo"}).status_code == 400


def test_create_and_get_repo_with_fake_client(monkeypatch) -> None:
    monkeypatch.setenv("TIANXUAN_GITEA_URL", "http://gitea.example")
    monkeypatch.setenv("TIANXUAN_GITEA_TOKEN", "secret")
    monkeypatch.setattr(api_module, "GiteaClient", _FakeGitea)
    client, headers = _setup()

    assert client.get("/api/v1/gitea/status").json()["configured"] is True

    created = client.post("/api/v1/repos", headers=headers, json={"name": "demo", "private": True}).json()
    assert created == {"name": "demo", "private": True, "default_branch": "main"}

    fetched = client.get("/api/v1/repos/owner/demo", headers=headers).json()
    assert fetched["full_name"] == "owner/demo"

    listed = client.get("/api/v1/repos?owner=owner&limit=10", headers=headers).json()["repos"]
    assert listed[0]["full_name"] == "owner/demo"
    assert listed[0]["limit"] == 10


def test_repo_branches_and_pull_requests_with_fake_client(monkeypatch) -> None:
    monkeypatch.setenv("TIANXUAN_GITEA_URL", "http://gitea.example")
    monkeypatch.setenv("TIANXUAN_GITEA_TOKEN", "secret")
    monkeypatch.setattr(api_module, "GiteaClient", _FakeGitea)
    client, headers = _setup()

    branches = client.get("/api/v1/repos/owner/demo/branches", headers=headers).json()["branches"]
    assert branches == [{"name": "main", "protected": False, "commit_sha": "abc123"}]

    pulls = client.get("/api/v1/repos/owner/demo/pulls", headers=headers, params={"state": "all"}).json()["pulls"]
    assert pulls[0]["state"] == "all"

    created = client.post(
        "/api/v1/repos/owner/demo/pulls",
        headers=headers,
        json={"title": "feat", "head": "feature", "base": "main", "body": "demo"},
    ).json()
    assert created["number"] == 2
    assert created["head"] == "feature"

    merged = client.post(
        "/api/v1/repos/owner/demo/pulls/2/merge",
        headers=headers,
        json={"method": "squash"},
    ).json()
    assert merged == {"number": 2, "merged": True, "method": "squash"}
