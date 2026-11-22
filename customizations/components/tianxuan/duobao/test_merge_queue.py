"""多宝合入队列：串行合入、冲突隔离、合入检验与优先级。"""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from git_service import GitService
from merge_queue import MergeQueue
from policy import RoleDenied


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


def test_transient_error_requeues_then_rejects(tmp_path: Path) -> None:
    service, repo = _repo(tmp_path)
    _branch(service, repo, "feature", {"b.md": "# two\n"})
    queue = MergeQueue(str(tmp_path / "queue.db"), service)

    def boom(item: dict[str, Any]) -> dict[str, Any]:
        raise sqlite3.OperationalError("database is locked")

    queue._execute = boom  # type: ignore[method-assign]
    item = queue.enqueue("usr_1", str(repo), "feature", "main", "重试")
    first = queue.process_next()
    second = queue.process_next()
    third = queue.process_next()
    assert first is not None and first["status"] == "queued" and first["attempts"] == 1
    assert second is not None and second["status"] == "queued" and second["attempts"] == 2
    assert third is not None and third["status"] == "rejected" and third["attempts"] == 3
    assert queue.get(item["id"])["status"] == "rejected"


def test_check_environment_scrubs_deployment_secrets(tmp_path: Path, monkeypatch) -> None:
    service, _ = _repo(tmp_path)
    queue = MergeQueue(str(tmp_path / "queue.db"), service)
    monkeypatch.setenv("TIANXUAN_SECRET", "should-not-leak")
    monkeypatch.setenv("OPENAI_API_KEY", "should-not-leak")
    monkeypatch.setenv("SAFE_SETTING", "kept")
    environment = queue._check_environment()
    assert "TIANXUAN_SECRET" not in environment
    assert "OPENAI_API_KEY" not in environment
    assert environment["SAFE_SETTING"] == "kept"
    assert environment["CI"] == "1"
    assert environment["GIT_TERMINAL_PROMPT"] == "0"

    home = tmp_path / "check-home"
    isolated = queue._check_environment(home)
    assert isolated["HOME"] == str(home)
    assert isolated["USERPROFILE"] == str(home)
    assert isolated["TEMP"] == str(home)


def test_check_timeout_terminates_process_tree(tmp_path: Path) -> None:
    service, repo = _repo(tmp_path)
    queue = MergeQueue(str(tmp_path / "queue.db"), service, check_timeout=0.3)
    result = queue._run_check(repo, [sys.executable, "-c", "import time; time.sleep(5)"])
    assert result["exit_code"] == 124
    assert result["duration_seconds"] < 3.0


def test_check_runs_with_isolated_home(tmp_path: Path) -> None:
    service, repo = _repo(tmp_path)
    queue = MergeQueue(str(tmp_path / "queue.db"), service)
    result = queue._run_check(repo, [sys.executable, "-c", "import os;print(os.environ.get('TEMP',''))"])
    assert result["exit_code"] == 0
    assert "duobao-check-home" in result["output"]


def test_protected_branch_merges_only_through_queue(tmp_path: Path) -> None:
    service, repo = _repo(tmp_path)
    _branch(service, repo, "feature", {"b.md": "# two\n"})
    queue = MergeQueue(
        str(tmp_path / "queue.db"),
        service,
        protected_branches=("main",),
        role_resolver=lambda actor: "editor",
    )
    item = queue.enqueue("usr_1", str(repo), "feature", "main")
    assert item["evidence"]["policy"] == {"target": "main", "protected": True, "path": "queue", "actor_role": "editor"}

    done = queue.process_next()
    assert done is not None and done["status"] == "merged"
    assert done["evidence"]["policy"]["protected"] is True
    assert done["evidence"]["merge_sha"]


def test_viewer_cannot_enqueue_candidate(tmp_path: Path) -> None:
    service, repo = _repo(tmp_path)
    _branch(service, repo, "feature", {"b.md": "# two\n"})
    queue = MergeQueue(str(tmp_path / "queue.db"), service, role_resolver=lambda actor: "viewer")
    with pytest.raises(RoleDenied):
        queue.enqueue("usr_1", str(repo), "feature", "main")


def test_role_revoked_before_execution_rejects_candidate(tmp_path: Path) -> None:
    service, repo = _repo(tmp_path)
    _branch(service, repo, "feature", {"b.md": "# two\n"})
    roles = {"usr_1": "editor"}
    queue = MergeQueue(
        str(tmp_path / "queue.db"),
        service,
        protected_branches=("main",),
        role_resolver=lambda actor: roles.get(actor, ""),
    )
    before = service.log(repo, "main", 1)[0]["sha"]
    queue.enqueue("usr_1", str(repo), "feature", "main")
    roles["usr_1"] = "viewer"

    done = queue.process_next()
    assert done is not None and done["status"] == "rejected"
    assert "cannot merge" in done["evidence"]["error"]
    assert service.log(repo, "main", 1)[0]["sha"] == before


def test_binding_is_preserved_and_events_are_emitted(tmp_path: Path) -> None:
    service, repo = _repo(tmp_path)
    _branch(service, repo, "feature", {"b.md": "# two\n"})
    events: list[tuple[str, dict[str, Any]]] = []
    queue = MergeQueue(
        str(tmp_path / "queue.db"),
        service,
        event_sink=lambda actor, event_type, target, payload: events.append((event_type, payload)),
    )
    item = queue.enqueue(
        "usr_1",
        str(repo),
        "feature",
        "main",
        pr_number=7,
        issue_ref="#1188",
    )
    assert item["evidence"]["binding"] == {"pr_number": 7, "issue_ref": "#1188"}

    done = queue.process_next()
    assert done is not None and done["status"] == "merged"
    assert done["evidence"]["binding"]["pr_number"] == 7
    assert [name for name, _ in events] == ["repo.merge.enqueued", "repo.merge.merged"]
    assert events[1][1]["status"] == "merged"


def test_invalid_binding_is_rejected(tmp_path: Path) -> None:
    service, repo = _repo(tmp_path)
    _branch(service, repo, "feature", {"b.md": "# two\n"})
    queue = MergeQueue(str(tmp_path / "queue.db"), service)
    for pr_number, issue_ref in ((0, ""), (True, ""), (1, "x" * 501), (1, 42)):
        with pytest.raises(ValueError):
            queue.enqueue(
                "usr_1",
                str(repo),
                "feature",
                "main",
                pr_number=pr_number,
                issue_ref=issue_ref,  # type: ignore[arg-type]
            )


def test_event_sink_failure_does_not_break_queue(tmp_path: Path) -> None:
    service, repo = _repo(tmp_path)
    _branch(service, repo, "feature", {"b.md": "# two\n"})

    def broken(actor: str, event_type: str, target: str, payload: dict[str, Any]) -> None:
        raise RuntimeError("audit unavailable")

    queue = MergeQueue(str(tmp_path / "queue.db"), service, event_sink=broken)
    item = queue.enqueue("usr_1", str(repo), "feature", "main")
    done = queue.process_next()
    assert item["status"] == "queued"
    assert done is not None and done["status"] == "merged"


def test_worker_registry_tracks_heartbeat(tmp_path: Path) -> None:
    service, repo = _repo(tmp_path)
    queue = MergeQueue(str(tmp_path / "queue.db"), service)
    try:
        assert queue.list_workers() == []
        queue.start_worker(0.1)
        time.sleep(0.35)
        workers = queue.list_workers()
        assert [worker["worker_id"] for worker in workers] == [queue.worker_id]
        assert queue.worker_running is True

        queue.stop_worker()
        assert queue.list_workers() == []
        assert queue.worker_running is False
    finally:
        queue.close()


@pytest.mark.parametrize("moving_branch", ["feature", "main"])
def test_exact_request_drift_during_checks(tmp_path: Path, monkeypatch, moving_branch: str) -> None:
    service, repo = _repo(tmp_path)
    _branch(service, repo, "feature", {"candidate.txt": "pinned"})
    base = service.branch_tip(repo, "main")
    candidate = service.branch_tip(repo, "feature")
    queue = MergeQueue(str(tmp_path / "queue.db"), service, checks=[["fixture"]])
    item = queue.enqueue("worker", str(repo), "feature", "main", candidate=candidate)

    def advance(worktree, check):
        assert (worktree / "candidate.txt").read_text() == "pinned"
        assert service.log(worktree, "HEAD", 1)[0]["sha"] == base
        service.commit(repo, moving_branch, "advance", {"later.txt": "later"}, "T", "t@example.invalid")
        return {"command": "fixture", "exit_code": 0}

    monkeypatch.setattr(queue, "_run_check", advance)
    received = queue.process_next()
    assert received["check_state"] == received["status"] == "stale"
    assert received["evidence"]["exact_request"] == {"candidate": candidate, "target_base": base}
    assert queue.get(item["id"])["check_state"] == "stale"
    if moving_branch == "feature":
        assert service.branch_tip(repo, "main") == base
    else:
        replacement = queue.enqueue("worker", str(repo), "feature", "main", candidate=candidate)
        assert replacement["id"] != item["id"] and replacement["check_state"] == "queued"
    queue.close()


def test_concurrent_resolution_replays_and_rechecks_branches(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    from exact_integration import conflict_files, resolved_candidate
    from git_service import GitServiceError

    service, repo = _repo(tmp_path)
    _branch(service, repo, "side", {"a.md": "source\n"})
    service.commit(repo, "main", "target", {"a.md": "target\n"}, "Owner", "owner@example.invalid")
    queue = MergeQueue(str(tmp_path / "queue.db"), service)
    try:
        item = queue.enqueue("author", str(repo), "side", "main", candidate=service.branch_tip(repo, "side"))
        assert queue.process_next()["status"] == "conflict"
        files = conflict_files(service.git_executable, item)
        assert [f["path"] for f in files] == ["a.md"]
        assert files[0]["source"]["text"] == "source\n" and files[0]["target"]["text"] == "target\n"
        choices = {"a.md": {"choice": "text", "text": "result\n"}}

        def resolve(_):
            return resolved_candidate(service.git_executable, item, choices, authorize=lambda _: True)

        with ThreadPoolExecutor(max_workers=3) as workers:
            results = list(workers.map(resolve, range(3)))
        assert results.count(results[0]) == len(results)
        branch, sha = results[0]
        assert service.branch_tip(repo, branch) == sha and service.read_file(repo, sha, "a.md") == "result\n"
        service.commit(repo, "side", "advance", {"a.md": "next\n"}, "Owner", "owner@example.invalid")
        with pytest.raises(GitServiceError):
            resolve(None)
    finally:
        queue.close()
