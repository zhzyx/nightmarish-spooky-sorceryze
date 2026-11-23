"""多宝合入队列 HTTP 接口测试。"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from api import create_app
from duobao_bridge import GitService
from fastapi.testclient import TestClient
from merge_queue import MergeQueue
from starlette.websockets import WebSocketDisconnect
from tianxuan_core import Tianxuan


def _git() -> str:
    executable = os.environ.get("GIT_EXECUTABLE") or shutil.which("git") or ""
    if not executable:
        pytest.skip("git executable not available")
    return executable


def _setup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[TestClient, dict[str, str], MergeQueue]:
    monkeypatch.setenv("TIANXUAN_REPO_ROOT", str(tmp_path))
    service = GitService(_git())
    repo = Path(service.create_repo(tmp_path, "docs"))
    service.commit(repo, "main", "init", {"a.md": "# one\n"}, "T", "t@example.invalid")
    base = service.log(repo, "main", 1)[0]["sha"]
    service.branch(repo, "feature", base)
    service.commit(repo, "feature", "feat", {"b.md": "# two\n"}, "T", "t@example.invalid")

    store = Tianxuan(":memory:")
    actor = store.register("队列租户", "queue@example.com", "secret-pass")["user_id"]
    queue = MergeQueue(str(tmp_path / "queue.db"), service)
    app = create_app(store, merge_queue=queue)
    client = TestClient(app)
    return client, {"X-Actor": str(actor)}, queue


def test_enqueue_and_process_through_api(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, headers, _ = _setup(monkeypatch, tmp_path)
    created = client.post(
        "/api/v1/merge-queue",
        headers=headers,
        json={"repo": "docs.git", "source": "feature", "target": "main", "title": "API 合入"},
    )
    assert created.status_code == 200, created.text
    item = created.json()
    assert item["status"] == "queued"

    listed = client.get("/api/v1/merge-queue", headers=headers).json()["items"]
    assert [entry["id"] for entry in listed] == [item["id"]]

    processed = client.post("/api/v1/merge-queue/process", headers=headers).json()["processed"]
    assert len(processed) == 1
    assert processed[0]["status"] == "merged"
    assert processed[0]["evidence"]["merge_sha"]


def test_cancel_and_viewer_rejection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, headers, _ = _setup(monkeypatch, tmp_path)
    item = client.post(
        "/api/v1/merge-queue",
        headers=headers,
        json={"repo": "docs.git", "source": "feature", "target": "main"},
    ).json()

    cancelled = client.post(f"/api/v1/merge-queue/{item['id']}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    viewer = client.post(
        "/api/v1/users",
        headers=headers,
        json={"email": "viewer@example.com", "password": "secret-pass", "role": "viewer"},
    )
    assert viewer.status_code == 200, viewer.text
    payload = viewer.json()
    viewer_id = payload.get("id") or payload["user_id"]
    denied = client.post(
        "/api/v1/merge-queue",
        headers={"X-Actor": viewer_id},
        json={"repo": "docs.git", "source": "feature", "target": "main"},
    )
    assert denied.status_code == 403


def test_websocket_streams_merge_queue_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, headers, _ = _setup(monkeypatch, tmp_path)
    actor = headers["X-Actor"]
    with client.websocket_connect(f"/api/v1/ws/merge-queue?actor={actor}") as websocket:
        message = websocket.receive_json()
    assert message["type"] == "snapshot"
    assert message["items"] == []


def test_websocket_rejects_unknown_actor(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, _, _ = _setup(monkeypatch, tmp_path)
    with pytest.raises(WebSocketDisconnect) as failure:
        with client.websocket_connect("/api/v1/ws/merge-queue?actor=usr_missing") as websocket:
            websocket.receive_json()
    assert failure.value.code == 4401


def test_merge_queue_api_filters_and_paginates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, headers, _ = _setup(monkeypatch, tmp_path)
    for title in ("一", "二", "三"):
        client.post(
            "/api/v1/merge-queue",
            headers=headers,
            json={"repo": "docs.git", "source": "feature", "target": "main", "title": title},
        )
    page = client.get("/api/v1/merge-queue", headers=headers, params={"limit": 1, "offset": 1}).json()
    assert page["total"] == 3
    assert len(page["items"]) == 1

    client.post("/api/v1/merge-queue/process", headers=headers)
    merged = client.get("/api/v1/merge-queue", headers=headers, params={"status": "merged"}).json()
    assert merged["total"] == 1
    assert merged["items"][0]["status"] == "merged"


def test_retry_cancelled_candidate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, headers, _ = _setup(monkeypatch, tmp_path)
    item = client.post(
        "/api/v1/merge-queue",
        headers=headers,
        json={"repo": "docs.git", "source": "feature", "target": "main", "title": "重试"},
    ).json()
    client.post(f"/api/v1/merge-queue/{item['id']}/cancel", headers=headers)
    retried = client.post(f"/api/v1/merge-queue/{item['id']}/retry", headers=headers)
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "queued"
    assert retried.json()["attempts"] == 0
    assert retried.json()["evidence"]["retried_from"] == "cancelled"

    merged = client.post("/api/v1/merge-queue/process", headers=headers).json()["processed"]
    assert merged[0]["status"] == "merged"
    denied = client.post(f"/api/v1/merge-queue/{item['id']}/retry", headers=headers)
    assert denied.status_code == 400


def test_merge_queue_status_reports_worker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, headers, queue = _setup(monkeypatch, tmp_path)
    initial = client.get("/api/v1/merge-queue/status", headers=headers).json()
    assert initial == {"worker": False, "queued": 0, "total": 0}

    client.post(
        "/api/v1/merge-queue",
        headers=headers,
        json={"repo": "docs.git", "source": "feature", "target": "main", "title": "状态"},
    )
    queued = client.get("/api/v1/merge-queue/status", headers=headers).json()
    assert queued["queued"] == 1
    assert queued["total"] == 1

    queue.start_worker(interval=0.1)
    try:
        running = client.get("/api/v1/merge-queue/status", headers=headers).json()
        assert running["worker"] is True
    finally:
        queue.stop_worker()


def _add_editor(client: TestClient, headers: dict[str, str], email: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/users",
        headers=headers,
        json={"email": email, "password": "secret-pass", "role": "editor"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    return {"X-Actor": str(payload.get("id") or payload["user_id"])}


def test_queue_binding_and_creator_permissions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, headers, _ = _setup(monkeypatch, tmp_path)
    first_editor = _add_editor(client, headers, "first@example.com")
    second_editor = _add_editor(client, headers, "second@example.com")

    created = client.post(
        "/api/v1/merge-queue",
        headers=first_editor,
        json={
            "repo": "docs.git",
            "source": "feature",
            "target": "main",
            "pr_number": 7,
            "issue_ref": "#1188",
        },
    )
    assert created.status_code == 200, created.text
    item = created.json()
    assert item["evidence"]["binding"] == {"pr_number": 7, "issue_ref": "#1188"}

    assert client.post(f"/api/v1/merge-queue/{item['id']}/cancel", headers=second_editor).status_code == 403
    assert client.post(f"/api/v1/merge-queue/{item['id']}/retry", headers=second_editor).status_code == 403
    assert client.post(f"/api/v1/merge-queue/{item['id']}/cancel", headers=first_editor).status_code == 200

    second = client.post(
        "/api/v1/merge-queue",
        headers=first_editor,
        json={"repo": "docs.git", "source": "feature", "target": "main"},
    ).json()
    assert client.post(f"/api/v1/merge-queue/{second['id']}/cancel", headers=headers).status_code == 200
    assert client.post(f"/api/v1/merge-queue/{second['id']}/retry", headers=headers).status_code == 200


def test_exact_request_requires_session_and_is_readable_by_tenant_reviewer(monkeypatch, tmp_path):
    client, legacy, queue = _setup(monkeypatch, tmp_path)
    store = client.app.state.store
    admin = {"Authorization": "Bearer " + store.issue_session(legacy["X-Actor"])}
    reviewer = _add_editor(client, legacy, "reviewer@example.invalid")
    reader = {"Authorization": "Bearer " + store.issue_session(reviewer["X-Actor"])}
    repo = tmp_path / "docs.git"
    source = GitService().branch_tip(repo, "feature")
    body = {"source": "feature", "target": "main", "candidate": source}
    path = "/api/v1/git/repos/docs.git/merge-requests"
    assert client.post(path, headers=legacy, json=body).status_code == 401
    assert client.post(path, headers=admin, json={**body, "candidate": source[:12]}).status_code == 422
    created = client.post(path, headers=admin, json=body)
    assert created.status_code == 200
    item = created.json()
    assert item["check_state"] == "queued"
    assert client.get(path + "/" + item["id"], headers=reader).json() == item
    assert client.get(path.replace("docs.git", "wrong.git") + "/" + item["id"], headers=reader).status_code == 404
    other = store.register("其他租户", "other@example.invalid", "secret-pass")
    outsider = {"Authorization": "Bearer " + store.issue_session(other["user_id"])}
    assert client.get(path + "/" + item["id"], headers=outsider).status_code == 404
    assert queue.count_items() == 1


@pytest.mark.parametrize("required_approvals", [0, 1, 2])
def test_requester_can_deliver_under_project_approval_policy(monkeypatch, tmp_path, required_approvals):
    client, legacy, queue = _setup(monkeypatch, tmp_path)
    store = client.app.state.store
    actor = legacy["X-Actor"]
    owner = {"Authorization": "Bearer " + store.issue_session(actor)}
    client.app.state.required_approvals = required_approvals
    issue = store.create_issue(actor, "Requester delivery")["id"]
    repo = tmp_path / "docs.git"
    candidate = queue.git.branch_tip(repo, "feature")
    root = "/api/v1/git/repos/docs.git/merge-requests"
    created = client.post(
        root, headers=owner, json={"source": "feature", "target": "main", "candidate": candidate, "issue_id": issue}
    )
    assert created.status_code == 200
    route = root + "/" + created.json()["id"]
    assert client.post(route + "/deliver", headers=owner).status_code == 409
    assert queue.process_next()["status"] == "checked"
    approval = {"decision": "APPROVED"}
    if required_approvals:
        assert client.post(route + "/deliver", headers=owner).status_code == 403
        assert client.post(route + "/review", headers=owner, json=approval).json()["reviews"] == {actor: "APPROVED"}
    if required_approvals == 2:
        assert client.post(route + "/review", headers=owner, json=approval).status_code == 200
        assert client.post(route + "/deliver", headers=owner).status_code == 403
        peer_id = _add_editor(client, legacy, "policy-reviewer@example.invalid")["X-Actor"]
        peer = {"Authorization": "Bearer " + store.issue_session(peer_id)}
        assert client.post(route + "/review", headers=peer, json=approval).status_code == 200
        assert client.post(route + "/deliver", headers=peer).status_code == 403
    result = client.post(route + "/deliver", headers=owner)
    assert result.status_code == 200
    assert result.json()["target_tip"] == queue.git.branch_tip(repo, "main") == candidate
    assert client.post(route + "/deliver", headers=owner).json()["comment_id"] == result.json()["comment_id"]
    assert len(store.list_issue_comments(actor, issue)) == 1


def test_delivery_recovers_lost_work_order_write_and_refuses_retracted_target(monkeypatch, tmp_path):
    from exact_integration import git

    client, legacy, queue = _setup(monkeypatch, tmp_path)
    store = client.app.state.store
    author = legacy["X-Actor"]
    owner = {"Authorization": "Bearer " + store.issue_session(author)}
    reviewer = _add_editor(client, legacy, "peer@example.invalid")["X-Actor"]
    peer = {"Authorization": "Bearer " + store.issue_session(reviewer)}
    issue = store.create_issue(author, "Read back the checked target")["id"]
    repo = tmp_path / "docs.git"
    service = queue.git
    base, candidate = (service.branch_tip(repo, name) for name in ("main", "feature"))
    root = "/api/v1/git/repos/docs.git/merge-requests"
    create = client.post(
        root, headers=owner, json={"source": "feature", "target": "main", "candidate": candidate, "issue_id": issue}
    )
    assert create.status_code == 200
    ident = create.json()["id"]
    route = root + "/" + ident
    assert queue.process_next()["status"] == "checked"
    assert client.post(route + "/review", headers=peer, json={"decision": "APPROVED"}).status_code == 200
    # Exact Git apply completed, then the service stopped before writing to Tianxuan.
    applied = queue.reviewed_delivery(ident, author)["evidence"]["merge_sha"]
    assert applied == candidate and store.list_issue_comments(author, issue) == []
    client.app.state.required_approvals = 2
    client.app.state.required_checks = ("new-project-check",)
    git(service.git_executable, repo, "update-ref", "refs/heads/main", base, applied)
    assert client.post(route + "/deliver", headers=owner).status_code == 409
    assert store.list_issue_comments(author, issue) == []
    git(service.git_executable, repo, "update-ref", "refs/heads/main", applied, base)
    accepted = client.post(route + "/deliver", headers=owner)
    assert accepted.status_code == 200 and accepted.json()["target_tip"] == candidate
    assert client.post(route + "/deliver", headers=owner).json()["comment_id"] == accepted.json()["comment_id"]
    assert len(store.list_issue_comments(author, issue)) == 1
