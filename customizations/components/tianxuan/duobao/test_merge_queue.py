"""多宝合入队列：串行合入、冲突隔离、合入检验与优先级。"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest
from git_service import GitService
from merge_queue import MergeQueue


def _git() -> str:
    executable = os.environ.get("GIT_EXECUTABLE") or shutil.which("git") or ""
    if not executable:
        pytest.skip("git executable not available")
    return executable


def _repo(tmp_path: Path) -> tuple[GitService, Path]:
    service = GitService(_git())
    repo = Path(service.create_repo(tmp_path, "docs"))
    service.commit(repo, "main", "init", {"a.md": "# one\n"}, "T", "t@example.invalid")
    return service, repo


def _branch(service: GitService, repo: Path, name: str, files: dict[str, str]) -> None:
    base = service.log(repo, "main", 1)[0]["sha"]
    service.branch(repo, name, base)
    service.commit(repo, name, f"feat {name}", files, "T", "t@example.invalid")


def test_queue_merges_candidate_and_records_evidence(tmp_path: Path) -> None:
    service, repo = _repo(tmp_path)
    _branch(service, repo, "feature", {"b.md": "# two\n"})
    queue = MergeQueue(str(tmp_path / "queue.db"), service)

    item = queue.enqueue("usr_1", str(repo), "feature", "main", "合入 feature")
    assert item["status"] == "queued"
    done = queue.process_next()

    assert done is not None
    assert done["status"] == "merged"
    assert done["evidence"]["merge_sha"]
    assert done["attempts"] == 1
    head = service.log(repo, "main", 1)[0]
    assert head["sha"] == done["evidence"]["merge_sha"]


def test_conflict_is_isolated_without_touching_target(tmp_path: Path) -> None:
    service, repo = _repo(tmp_path)
    _branch(service, repo, "feature", {"a.md": "# feature\n"})
    service.commit(repo, "main", "main change", {"a.md": "# main\n"}, "T", "t@example.invalid")
    before = service.log(repo, "main", 1)[0]["sha"]
    queue = MergeQueue(str(tmp_path / "queue.db"), service)

    queue.enqueue("usr_1", str(repo), "feature", "main", "冲突候选")
    done = queue.process_next()

    assert done is not None
    assert done["status"] == "conflict"
    assert "a.md" in done["evidence"]["conflicts"]
    assert service.log(repo, "main", 1)[0]["sha"] == before


def test_failed_check_rejects_candidate(tmp_path: Path) -> None:
    service, repo = _repo(tmp_path)
    _branch(service, repo, "feature", {"b.md": "# two\n"})
    before = service.log(repo, "main", 1)[0]["sha"]
    checks = [[sys.executable, "-c", "raise SystemExit(3)"]]
    queue = MergeQueue(str(tmp_path / "queue.db"), service, checks=checks)

    queue.enqueue("usr_1", str(repo), "feature", "main", "检验失败")
    done = queue.process_next()

    assert done is not None
    assert done["status"] == "rejected"
    assert done["evidence"]["checks"][0]["exit_code"] == 3
    assert service.log(repo, "main", 1)[0]["sha"] == before


def test_priority_and_latest_target_are_honored(tmp_path: Path) -> None:
    service, repo = _repo(tmp_path)
    _branch(service, repo, "feature-low", {"low.md": "# low\n"})
    _branch(service, repo, "feature-high", {"high.md": "# high\n"})
    queue = MergeQueue(str(tmp_path / "queue.db"), service)

    low = queue.enqueue("usr_1", str(repo), "feature-low", "main", "low", priority=0)
    high = queue.enqueue("usr_1", str(repo), "feature-high", "main", "high", priority=10)
    service.commit(repo, "main", "advance", {"c.md": "# c\n"}, "T", "t@example.invalid")

    first = queue.process_next()
    assert first is not None and first["id"] == high["id"] and first["status"] == "merged"
    second = queue.process_next()
    assert second is not None and second["id"] == low["id"] and second["status"] == "merged"
    assert [item for item in queue.list_items() if item["status"] == "queued"] == []

    sha = service.log(repo, "main", 1)[0]["sha"]
    assert sha == second["evidence"]["merge_sha"]


def test_worker_processes_queued_candidate(tmp_path: Path) -> None:
    import time

    service, repo = _repo(tmp_path)
    _branch(service, repo, "feature", {"b.md": "# two\n"})
    queue = MergeQueue(str(tmp_path / "queue.db"), service)
    queue.start_worker(interval=0.05)
    try:
        item = queue.enqueue("usr_1", str(repo), "feature", "main", "自动合入")
        deadline = time.time() + 10
        current = item
        while time.time() < deadline:
            current = queue.get(item["id"])
            if current["status"] in {"merged", "conflict", "rejected"}:
                break
            time.sleep(0.05)
        assert current["status"] == "merged", current
    finally:
        queue.stop_worker()
        queue.close()


def test_recover_stale_validating_candidate(tmp_path: Path) -> None:
    service, repo = _repo(tmp_path)
    _branch(service, repo, "feature", {"b.md": "# two\n"})
    queue = MergeQueue(str(tmp_path / "queue.db"), service)
    item = queue.enqueue("usr_1", str(repo), "feature", "main", "恢复")
    with queue._lock, queue.db:
        queue.db.execute(
            "UPDATE merge_queue SET status = 'validating', updated_at = ? WHERE id = ?",
            ("2000-01-01T00:00:00+00:00", item["id"]),
        )
    assert queue.recover_stale(older_than_seconds=1) == 1
    assert queue.get(item["id"])["status"] == "queued"


def test_process_next_is_serialized(tmp_path: Path) -> None:
    import threading
    import time

    service, repo = _repo(tmp_path)
    _branch(service, repo, "feature-a", {"a.md": "# a\n"})
    _branch(service, repo, "feature-b", {"b.md": "# b\n"})
    queue = MergeQueue(str(tmp_path / "queue.db"), service)
    queue.enqueue("usr_1", str(repo), "feature-a", "main", "A")
    queue.enqueue("usr_1", str(repo), "feature-b", "main", "B")

    active = 0
    peak = 0
    original = queue._execute

    def slow(item: dict[str, Any]) -> dict[str, Any]:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        time.sleep(0.2)
        try:
            return original(item)  # type: ignore[no-any-return]
        finally:
            active -= 1

    queue._execute = slow  # type: ignore[method-assign]
    workers = [threading.Thread(target=queue.process_next) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=20)
    statuses = [entry["status"] for entry in queue.list_items()]
    assert statuses and all(status == "merged" for status in statuses)
    assert peak == 1
