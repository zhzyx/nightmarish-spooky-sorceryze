"""Gitea 仓库接入 API 测试：状态、未配置、创建与读取仓库（假客户端）。"""

from __future__ import annotations

from typing import Any

import api as api_module
from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


class _FakeGitea:
    reviews: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    sudos: list[str] = []

    def __init__(self, base_url: str, token: str, sudo: str = "") -> None:
        self.base_url = base_url
        self.token = token
        self.sudo = sudo
        type(self).sudos.append(sudo)

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

    def list_pull_requests(
        self, owner: str, repo: str, state: str = "open", page: int = 1, limit: int = 30
    ) -> list[dict[str, Any]]:
        return [{"number": 1, "title": "demo", "state": state, "page": page, "limit": limit}]

    def list_releases(self, owner: str, repo: str) -> list[dict[str, Any]]:
        return [{"id": 1, "tag_name": "v1.0.0", "name": "First release", "draft": False, "prerelease": False}]

    def create_release(
        self,
        owner: str,
        repo: str,
        tag_name: str,
        name: str = "",
        body: str = "",
        draft: bool = False,
        prerelease: bool = False,
    ) -> dict[str, Any]:
        return {
            "id": 2,
            "tag_name": tag_name,
            "name": name,
            "body": body,
            "draft": draft,
            "prerelease": prerelease,
        }

    def update_release(
        self,
        owner: str,
        repo: str,
        release_id: int,
        *,
        name: str | None = None,
        body: str | None = None,
        draft: bool | None = None,
        prerelease: bool | None = None,
    ) -> dict[str, Any]:
        return {
            "id": release_id,
            "tag_name": "v1.0.0",
            "name": name or "First release",
            "body": body or "",
            "draft": bool(draft),
            "prerelease": bool(prerelease),
        }

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

    def get_pull_request(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        return {
            "number": number,
            "title": "demo",
            "head": "feature",
            "base": "main",
            "head_sha": "a" * 40,
            "base_sha": "b" * 40,
            "state": "open",
        }

    def merge_pull_request(self, owner: str, repo: str, number: int, method: str = "merge") -> dict[str, Any]:
        return {"number": number, "merged": True, "method": method}

    def list_reviews(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        return list(type(self).reviews)

    def create_review(self, owner: str, repo: str, number: int, *, event: str, body: str = "") -> dict[str, Any]:
        review = {
            "id": len(type(self).reviews) + 1,
            "state": event,
            "body": body,
            "user": "reviewer",
            "submitted_at": "",
        }
        type(self).reviews.append(review)
        return review

    def list_commit_statuses(self, owner: str, repo: str, sha: str) -> list[dict[str, Any]]:
        return list(type(self).statuses)

    def create_commit_status(
        self,
        owner: str,
        repo: str,
        sha: str,
        *,
        state: str,
        context: str = "duobao",
        description: str = "",
        target_url: str = "",
    ) -> dict[str, Any]:
        status = {
            "state": state,
            "context": context,
            "description": description,
            "target_url": target_url,
            "created_at": "",
        }
        type(self).statuses.append(status)
        return status


def _setup(
    protected_branches: tuple[str, ...] = (),
    required_approvals: int = 0,
    required_checks: tuple[str, ...] = (),
) -> tuple[TestClient, dict[str, str]]:
    _FakeGitea.reviews = []
    _FakeGitea.statuses = []
    _FakeGitea.sudos = []
    store = Tianxuan(":memory:")
    client = TestClient(
        create_app(
            store,
            protected_branches=protected_branches,
            required_approvals=required_approvals,
            required_checks=required_checks,
        )
    )
    registered = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "仓库工坊", "email": "repo@example.com", "password": "secret-pass"},
    ).json()
    store.link_identity(registered["user_id"], "gitea", "tester", registered["user_id"])
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


def test_update_release_with_fake_client(monkeypatch) -> None:
    monkeypatch.setenv("TIANXUAN_GITEA_URL", "http://gitea.example")
    monkeypatch.setenv("TIANXUAN_GITEA_TOKEN", "secret")
    monkeypatch.setattr(api_module, "GiteaClient", _FakeGitea)
    client, headers = _setup()

    updated = client.patch(
        "/api/v1/repos/owner/demo/releases/7",
        headers=headers,
        json={"name": "Renamed", "draft": True},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Renamed"
    assert updated.json()["draft"] is True


def test_create_release_with_fake_client(monkeypatch) -> None:
    monkeypatch.setenv("TIANXUAN_GITEA_URL", "http://gitea.example")
    monkeypatch.setenv("TIANXUAN_GITEA_TOKEN", "secret")
    monkeypatch.setattr(api_module, "GiteaClient", _FakeGitea)
    client, headers = _setup()

    created = client.post(
        "/api/v1/repos/owner/demo/releases",
        headers=headers,
        json={"tag_name": "v2.0.0", "name": "Second release", "draft": True},
    )
    assert created.status_code == 200, created.text
    assert created.json()["tag_name"] == "v2.0.0"
    assert created.json()["draft"] is True


def test_repo_releases_with_fake_client(monkeypatch) -> None:
    monkeypatch.setenv("TIANXUAN_GITEA_URL", "http://gitea.example")
    monkeypatch.setenv("TIANXUAN_GITEA_TOKEN", "secret")
    monkeypatch.setattr(api_module, "GiteaClient", _FakeGitea)
    client, headers = _setup()

    releases = client.get("/api/v1/repos/owner/demo/releases", headers=headers).json()["releases"]
    assert releases[0]["tag_name"] == "v1.0.0"
    assert releases[0]["name"] == "First release"


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


def test_protected_branch_rejects_direct_gitea_merge(monkeypatch) -> None:
    monkeypatch.setenv("TIANXUAN_GITEA_URL", "http://gitea.example")
    monkeypatch.setenv("TIANXUAN_GITEA_TOKEN", "secret")
    monkeypatch.setattr(api_module, "GiteaClient", _FakeGitea)
    client, headers = _setup(protected_branches=("main",))

    response = client.post(
        "/api/v1/repos/owner/demo/pulls/2/merge",
        headers=headers,
        json={"method": "merge"},
    )
    assert response.status_code == 403
    assert "protected" in response.json()["detail"]


def test_viewer_cannot_create_repo_or_open_or_merge_pull(monkeypatch) -> None:
    monkeypatch.setenv("TIANXUAN_GITEA_URL", "http://gitea.example")
    monkeypatch.setenv("TIANXUAN_GITEA_TOKEN", "secret")
    monkeypatch.setattr(api_module, "GiteaClient", _FakeGitea)
    client, headers = _setup()
    store = client.app.state.store  # type: ignore[attr-defined]
    viewer = store.add_member(headers["X-Actor"], "viewer@example.com", "secret-pass", role="viewer")
    viewer_headers = {"X-Actor": viewer["user_id"]}

    assert client.post("/api/v1/repos", headers=viewer_headers, json={"name": "demo"}).status_code == 403
    assert (
        client.post(
            "/api/v1/repos/owner/demo/pulls",
            headers=viewer_headers,
            json={"title": "feat", "head": "feature", "base": "main"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/repos/owner/demo/pulls/2/merge",
            headers=viewer_headers,
            json={"method": "merge"},
        ).status_code
        == 403
    )


def test_required_approval_gates_merge(monkeypatch) -> None:
    monkeypatch.setenv("TIANXUAN_GITEA_URL", "http://gitea.example")
    monkeypatch.setenv("TIANXUAN_GITEA_TOKEN", "secret")
    monkeypatch.setattr(api_module, "GiteaClient", _FakeGitea)
    client, headers = _setup(required_approvals=1)

    blocked = client.post(
        "/api/v1/repos/owner/demo/pulls/2/merge",
        headers=headers,
        json={"method": "merge"},
    )
    assert blocked.status_code == 403
    assert "approving review" in blocked.json()["detail"]

    review = client.post(
        "/api/v1/repos/owner/demo/pulls/2/reviews",
        headers=headers,
        json={"event": "APPROVED", "body": "LGTM"},
    )
    assert review.status_code == 200
    assert review.json()["state"] == "APPROVED"

    listed = client.get("/api/v1/repos/owner/demo/pulls/2/reviews", headers=headers).json()["reviews"]
    assert [entry["state"] for entry in listed] == ["APPROVED"]

    merged = client.post(
        "/api/v1/repos/owner/demo/pulls/2/merge",
        headers=headers,
        json={"method": "merge"},
    )
    assert merged.status_code == 200


def test_viewer_cannot_review_pull(monkeypatch) -> None:
    monkeypatch.setenv("TIANXUAN_GITEA_URL", "http://gitea.example")
    monkeypatch.setenv("TIANXUAN_GITEA_TOKEN", "secret")
    monkeypatch.setattr(api_module, "GiteaClient", _FakeGitea)
    client, headers = _setup()
    store = client.app.state.store  # type: ignore[attr-defined]
    viewer = store.add_member(headers["X-Actor"], "viewer@example.com", "secret-pass", role="viewer")
    viewer_headers = {"X-Actor": viewer["user_id"]}

    response = client.post(
        "/api/v1/repos/owner/demo/pulls/2/reviews",
        headers=viewer_headers,
        json={"event": "APPROVED"},
    )
    assert response.status_code == 403


def test_required_checks_gate_merge(monkeypatch) -> None:
    monkeypatch.setenv("TIANXUAN_GITEA_URL", "http://gitea.example")
    monkeypatch.setenv("TIANXUAN_GITEA_TOKEN", "secret")
    monkeypatch.setattr(api_module, "GiteaClient", _FakeGitea)
    client, headers = _setup(required_checks=("ci/build",))
    sha = "a" * 40

    missing = client.post("/api/v1/repos/owner/demo/pulls/2/merge", headers=headers, json={"method": "merge"})
    assert missing.status_code == 403
    assert "missing" in missing.json()["detail"]

    failed = client.post(
        f"/api/v1/repos/owner/demo/statuses/{sha}",
        headers=headers,
        json={"state": "failure", "context": "ci/build", "description": "tests failed"},
    )
    assert failed.status_code == 200
    blocked = client.post("/api/v1/repos/owner/demo/pulls/2/merge", headers=headers, json={"method": "merge"})
    assert blocked.status_code == 403
    assert "failing" in blocked.json()["detail"]

    passed = client.post(
        f"/api/v1/repos/owner/demo/statuses/{sha}",
        headers=headers,
        json={"state": "success", "context": "ci/build", "description": "tests passed"},
    )
    assert passed.status_code == 200
    listed = client.get(f"/api/v1/repos/owner/demo/commits/{sha}/statuses", headers=headers).json()["statuses"]
    assert [entry["state"] for entry in listed] == ["failure", "success"]

    merged = client.post("/api/v1/repos/owner/demo/pulls/2/merge", headers=headers, json={"method": "merge"})
    assert merged.status_code == 200


def test_viewer_cannot_write_commit_status(monkeypatch) -> None:
    monkeypatch.setenv("TIANXUAN_GITEA_URL", "http://gitea.example")
    monkeypatch.setenv("TIANXUAN_GITEA_TOKEN", "secret")
    monkeypatch.setattr(api_module, "GiteaClient", _FakeGitea)
    client, headers = _setup()
    store = client.app.state.store  # type: ignore[attr-defined]
    viewer = store.add_member(headers["X-Actor"], "viewer@example.com", "secret-pass", role="viewer")
    viewer_headers = {"X-Actor": viewer["user_id"]}

    response = client.post(
        f"/api/v1/repos/owner/demo/statuses/{'a' * 40}",
        headers=viewer_headers,
        json={"state": "success", "context": "ci/build"},
    )
    assert response.status_code == 403


def test_gitea_writes_use_linked_identity_as_sudo(monkeypatch) -> None:
    monkeypatch.setenv("TIANXUAN_GITEA_URL", "http://gitea.example")
    monkeypatch.setenv("TIANXUAN_GITEA_TOKEN", "secret")
    monkeypatch.setattr(api_module, "GiteaClient", _FakeGitea)
    client, headers = _setup()

    created = client.post("/api/v1/repos", headers=headers, json={"name": "demo"})
    assert created.status_code == 200
    assert "tester" in _FakeGitea.sudos


def test_gitea_writes_require_linked_identity(monkeypatch) -> None:
    monkeypatch.setenv("TIANXUAN_GITEA_URL", "http://gitea.example")
    monkeypatch.setenv("TIANXUAN_GITEA_TOKEN", "secret")
    monkeypatch.setattr(api_module, "GiteaClient", _FakeGitea)
    client, _ = _setup()
    other = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "无绑定租户", "email": "nolink@example.com", "password": "secret-pass"},
    ).json()
    other_headers = {"X-Actor": other["user_id"]}

    assert client.get("/api/v1/repos", headers=other_headers).status_code == 200
    denied = client.post("/api/v1/repos", headers=other_headers, json={"name": "demo"})
    assert denied.status_code == 403
    assert "Gitea identity" in denied.json()["detail"]
