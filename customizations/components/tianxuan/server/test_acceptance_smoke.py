"""天璇平台端到端验收冒烟：文档导出、身份解析、合入队列。"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from api import create_app
from duobao_bridge import GitService
from fastapi.testclient import TestClient
from merge_queue import MergeQueue
from tianxuan_core import Tianxuan

_DATA_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _git() -> str:
    executable = os.environ.get("GIT_EXECUTABLE") or shutil.which("git") or ""
    if not executable:
        pytest.skip("git executable not available")
    return executable


def test_platform_acceptance_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIANXUAN_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("TIANXUAN_IDENTITY_SECRET", "acceptance-secret")

    service = GitService(_git())
    repo = Path(service.create_repo(tmp_path, "docs"))
    service.commit(repo, "main", "init", {"a.md": "# one\n"}, "T", "t@example.invalid")
    base = service.log(repo, "main", 1)[0]["sha"]
    service.branch(repo, "feature", base)
    service.commit(repo, "feature", "feat", {"b.md": "# two\n"}, "T", "t@example.invalid")

    store = Tianxuan(":memory:")
    queue = MergeQueue(str(tmp_path / "queue.db"), service)
    client = TestClient(create_app(store, merge_queue=queue))
    admin = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "验收租户", "email": "acceptance@example.com", "password": "secret-pass"},
    ).json()
    headers = {"X-Actor": admin["user_id"]}

    doc = client.post(
        "/api/v1/docs",
        headers=headers,
        json={
            "title": "验收文档",
            "body_md": f"# 验收\n\n| 名称 | 值 |\n| --- | --- |\n| A | 1 |\n\n![图]({_DATA_PNG})\n",
        },
    ).json()
    for fmt in ("md", "html", "docx", "pdf"):
        exported = client.get(
            f"/api/v1/docs/{doc['id']}/export/file",
            headers=headers,
            params={"format": fmt},
        )
        assert exported.status_code == 200, (fmt, exported.text)
        assert len(exported.content) > 100

    client.post(
        "/api/v1/identity/links",
        headers=headers,
        json={"provider": "tianshu", "subject": "acceptance-user", "user_id": admin["user_id"]},
    )
    resolved = client.post(
        "/api/v1/identity/resolve",
        json={
            "provider": "tianshu",
            "subject": "acceptance-user",
            "secret": "acceptance-secret",
        },
    )
    assert resolved.status_code == 200, resolved.text
    token_headers = {"Authorization": f"Bearer {resolved.json()['token']}"}
    assert client.get("/api/v1/docs", headers=token_headers).status_code == 200

    enqueued = client.post(
        "/api/v1/merge-queue",
        headers=headers,
        json={"repo": "docs.git", "source": "feature", "target": "main", "title": "验收合入"},
    )
    assert enqueued.status_code == 200, enqueued.text
    processed = client.post("/api/v1/merge-queue/process", headers=headers).json()["processed"]
    assert processed and processed[0]["status"] == "merged", processed
    assert processed[0]["evidence"]["merge_sha"]
