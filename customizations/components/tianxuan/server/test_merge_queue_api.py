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
