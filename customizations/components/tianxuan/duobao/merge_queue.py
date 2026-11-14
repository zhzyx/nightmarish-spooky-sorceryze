"""多宝合入队列：持久化候选、冲突预检、合入检验与串行合入。

Git 只是底层对象存储与传输；合入的排队、检验、重试和证据由多宝自己承担。
"""

from __future__ import annotations

import json
import os
import shlex
import signal
import sqlite3
import subprocess
import tempfile
import threading
import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from git_service import GitService, MergeConflict

SCHEMA = """
CREATE TABLE IF NOT EXISTS merge_queue (
  id TEXT PRIMARY KEY,
  repo TEXT NOT NULL,
  source TEXT NOT NULL,
  target TEXT NOT NULL,
  title TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  evidence TEXT NOT NULL DEFAULT '{}',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_merge_queue_status
  ON merge_queue(status, priority DESC, created_at);
"""

STATUSES = {"queued", "validating", "merged", "conflict", "rejected", "cancelled"}
CHECK_OUTPUT_LIMIT = 2000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return f"mq_{uuid.uuid4().hex}"


def _is_retryable(error: BaseException) -> bool:
    if isinstance(error, sqlite3.OperationalError):
        return True
    text = str(error).lower()
    return any(
        marker in text for marker in ("database is locked", "another git process", "index.lock", "could not lock")
    )


def _is_sensitive_environment(key: str) -> bool:
    upper = key.upper()
    if upper.startswith("TIANXUAN_"):
        return True
    return any(
        marker in upper
        for marker in (
            "TOKEN",
            "SECRET",
            "PASSWORD",
            "API_KEY",
            "PRIVATE_KEY",
            "CREDENTIAL",
            "COOKIE",
        )
    )


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                check=False,
                capture_output=True,
            )
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)  # type: ignore[attr-defined]
    except (OSError, ProcessLookupError):
        pass
    try:
        process.communicate(timeout=2.0)
    except (subprocess.TimeoutExpired, OSError):
        process.kill()


class MergeQueue:
    """串行合入梯队；每次只领取一个候选，验证后在最新目标上合入。"""

    def __init__(
        self,
        db_path: str,
        git_service: GitService,
        *,
        checks: Sequence[Sequence[str]] | None = None,
        check_timeout: float = 600.0,
    ) -> None:
        self.db = sqlite3.connect(db_path, check_same_thread=False, timeout=30.0)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()
        self.git = git_service
        self.checks = [list(check) for check in (checks or [])]
        self.check_timeout = check_timeout
        self._lock = threading.Lock()
        self._process_lock = threading.Lock()
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()

    def start_worker(self, interval: float = 2.0) -> None:
        """启动常驻合入 worker；每次领取一个候选，失败继续等待下一次。"""
        if self._worker is not None:
            return
        self.recover_stale()
        self._stop.clear()

        def loop() -> None:
            while not self._stop.wait(max(0.2, float(interval))):
                try:
                    self.process_next()
                except Exception:
                    continue

        self._worker = threading.Thread(target=loop, name="duobao-merge-queue", daemon=True)
        self._worker.start()

    def stop_worker(self) -> None:
        self._stop.set()
        worker = self._worker
        if worker is not None:
            worker.join(timeout=5.0)
        self._worker = None

    def close(self) -> None:
        self.stop_worker()
        with self._lock:
            self.db.close()

    # ---------- 队列 ----------
    def enqueue(
        self,
        actor: str,
        repo: str,
        source: str,
        target: str,
        title: str = "",
        priority: int = 0,
    ) -> dict[str, Any]:
        repo_path = self._repo_path(repo)
        branches = set(self.git.list_branches(repo_path))
        if source not in branches:
            raise ValueError(f"unknown source branch: {source}")
        if target not in branches:
            raise ValueError(f"unknown target branch: {target}")
        if source == target:
            raise ValueError("source and target must differ")
        item_id = _new_id()
        now = _now()
        with self._lock, self.db:
            self.db.execute(
                "INSERT INTO merge_queue (id, repo, source, target, title, priority, status, "
                "attempts, evidence, created_by, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'queued', 0, '{}', ?, ?, ?)",
                (item_id, str(repo_path), source, target, title or source, priority, actor, now, now),
            )
        return self.get(item_id)

    def list_items(self, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if status is not None and status not in STATUSES:
            raise ValueError(f"unknown status: {status}")
        sql = "SELECT * FROM merge_queue"
        args: list[Any] = []
        if status is not None:
            sql += " WHERE status = ?"
            args.append(status)
        sql += " ORDER BY priority DESC, created_at, id LIMIT ?"
        args.append(max(1, min(int(limit), 200)))
        with self._lock:
            rows = self.db.execute(sql, args).fetchall()
        return [self._decode(row) for row in rows]

    def get(self, item_id: str) -> dict[str, Any]:
        with self._lock:
            row = self.db.execute("SELECT * FROM merge_queue WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            raise KeyError(item_id)
        return self._decode(row)

    def cancel(self, item_id: str) -> dict[str, Any]:
        now = _now()
        with self._lock, self.db:
            changed = self.db.execute(
                "UPDATE merge_queue SET status = 'cancelled', updated_at = ? WHERE id = ? AND status = 'queued'",
                (now, item_id),
            ).rowcount
        if changed != 1:
            raise ValueError("only queued candidates can be cancelled")
        return self.get(item_id)

    def process_next(self) -> dict[str, Any] | None:
        # 合入梯队必须串行：worker 与手动 /process 同时存在时也不能并行执行候选。
        with self._process_lock:
            item = self._claim()
            if item is None:
                return None
            try:
                outcome = self._execute(item)
            except Exception as error:  # 队列必须留下证据而不是丢失候选
                attempt = int(item["attempts"]) + 1
                if _is_retryable(error) and attempt < 3:
                    outcome = {
                        "status": "queued",
                        "evidence": {
                            "retry_error": f"{type(error).__name__}: {error}",
                            "attempt": attempt,
                        },
                    }
                else:
                    outcome = {
                        "status": "rejected",
                        "evidence": {"error": f"{type(error).__name__}: {error}", "attempt": attempt},
                    }
            with self._lock, self.db:
                self.db.execute(
                    "UPDATE merge_queue SET status = ?, evidence = ?, updated_at = ? WHERE id = ?",
                    (
                        outcome["status"],
                        json.dumps(outcome["evidence"], ensure_ascii=False),
                        _now(),
                        item["id"],
                    ),
                )
            return self.get(item["id"])

    def recover_stale(self, older_than_seconds: float = 300.0) -> int:
        """把进程中断后卡在 validating 的候选重新放回队列。"""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=max(0.0, older_than_seconds))
        recovered = 0
        with self._lock, self.db:
            rows = self.db.execute(
                "SELECT id, evidence, updated_at FROM merge_queue WHERE status = 'validating'"
            ).fetchall()
            for row in rows:
                try:
                    updated = datetime.fromisoformat(str(row["updated_at"]))
                except ValueError:
                    updated = cutoff - timedelta(seconds=1)
                if updated >= cutoff:
                    continue
                evidence = json.loads(row["evidence"] or "{}")
                evidence["recovered_from"] = "validating"
                evidence["recovered_at"] = _now()
                self.db.execute(
                    "UPDATE merge_queue SET status = 'queued', evidence = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(evidence, ensure_ascii=False), _now(), row["id"]),
                )
                recovered += 1
        return recovered

    def process_batch(self, limit: int = 5) -> list[dict[str, Any]]:
        results = []
        for _ in range(max(1, min(int(limit), 50))):
            result = self.process_next()
            if result is None:
                break
            results.append(result)
        return results

    # ---------- 内部 ----------
    def _claim(self) -> dict[str, Any] | None:
        with self._lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                row = self.db.execute(
                    "SELECT * FROM merge_queue WHERE status = 'queued' ORDER BY priority DESC, created_at, id LIMIT 1"
                ).fetchone()
                if row is None:
                    self.db.commit()
                    return None
                self.db.execute(
                    "UPDATE merge_queue SET status = 'validating', attempts = attempts + 1, "
                    "updated_at = ? WHERE id = ? AND status = 'queued'",
                    (_now(), row["id"]),
                )
                self.db.commit()
            except BaseException:
                self.db.rollback()
                raise
        return self._decode(row)

    def _execute(self, item: dict[str, Any]) -> dict[str, Any]:
        repo = self._repo_path(item["repo"])
        branches = set(self.git.list_branches(repo))
        if item["source"] not in branches or item["target"] not in branches:
            return {
                "status": "rejected",
                "evidence": {"error": "source or target branch no longer exists"},
            }

        preview = self._preview(repo, item["source"], item["target"])
        evidence: dict[str, Any] = {
            "validated_at": _now(),
            "checks": preview["checks"],
            "conflicts": preview["conflicts"],
        }
        if preview["conflicts"]:
            evidence["error"] = "merge conflict"
            return {"status": "conflict", "evidence": evidence}
        if any(check["exit_code"] != 0 for check in preview["checks"]):
            evidence["error"] = "validation checks failed"
            return {"status": "rejected", "evidence": evidence}

        try:
            sha = self.git.merge(repo, item["source"], item["target"])
        except MergeConflict as error:
            evidence["conflicts"] = list(error.conflicts)
            evidence["error"] = "merge conflict on final merge"
            return {"status": "conflict", "evidence": evidence}
        evidence["merge_sha"] = sha
        evidence["merged_at"] = _now()
        return {"status": "merged", "evidence": evidence}

    def _preview(self, repo: Path, source: str, target: str) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        conflicts: list[str] = []
        with tempfile.TemporaryDirectory(prefix="duobao-queue-") as temporary:
            worktree = Path(temporary) / "worktree"
            environment = self._check_environment()
            environment["GIT_TERMINAL_PROMPT"] = "0"
            subprocess.run(
                [self.git.git_executable, "clone", "--quiet", str(repo), str(worktree)],
                check=True,
                capture_output=True,
                env=environment,
            )
            subprocess.run(
                [self.git.git_executable, "-C", str(worktree), "checkout", "--quiet", target],
                check=True,
                capture_output=True,
                env=environment,
            )
            merged = subprocess.run(
                [
                    self.git.git_executable,
                    "-C",
                    str(worktree),
                    "-c",
                    "user.name=Duobao Queue",
                    "-c",
                    "user.email=duobao@gonggong.local",
                    "merge",
                    "--no-verify",
                    "--no-commit",
                    "--no-ff",
                    f"origin/{source}",
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
            )
            conflicted = subprocess.run(
                [self.git.git_executable, "-C", str(worktree), "diff", "--name-only", "--diff-filter=U"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
            )
            conflicts = [line.strip() for line in conflicted.stdout.splitlines() if line.strip()]
            if merged.returncode == 0 and not conflicts:
                for check in self.checks:
                    checks.append(self._run_check(worktree, check))
            subprocess.run(
                [self.git.git_executable, "-C", str(worktree), "merge", "--abort"],
                check=False,
                capture_output=True,
                env=environment,
            )
        return {"conflicts": conflicts, "checks": checks}

    def _check_environment(self) -> dict[str, str]:
        """合并检查默认不继承部署凭据；管理员可用白名单显式放行。"""
        allowlist = [item.strip() for item in os.environ.get("TIANXUAN_MERGE_CHECK_ENV", "").split(",") if item.strip()]
        if allowlist:
            environment = {key: os.environ[key] for key in allowlist if key in os.environ}
        else:
            environment = {key: value for key, value in os.environ.items() if not _is_sensitive_environment(key)}
        environment["GIT_TERMINAL_PROMPT"] = "0"
        environment["CI"] = "1"
        return environment

    def _run_check(self, worktree: Path, check: Sequence[str]) -> dict[str, Any]:
        started = datetime.now(timezone.utc)
        popen_kwargs: dict[str, Any] = {}
        if os.name == "nt":
            popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            popen_kwargs["start_new_session"] = True
        process: subprocess.Popen[str] | None = None
        try:
            process = subprocess.Popen(
                list(check),
                cwd=worktree,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=self._check_environment(),
                **popen_kwargs,
            )
            stdout, stderr = process.communicate(timeout=self.check_timeout)
            exit_code = process.returncode
            output = f"{stdout}\n{stderr}".strip()
        except subprocess.TimeoutExpired:
            if process is not None:
                _terminate_process_tree(process)
            exit_code = 124
            output = f"check timed out after {self.check_timeout}s"
        except OSError as error:
            exit_code = 127
            output = str(error)
        duration = (datetime.now(timezone.utc) - started).total_seconds()
        return {
            "command": shlex.join(check),
            "exit_code": exit_code,
            "duration_seconds": round(duration, 3),
            "output": output[-CHECK_OUTPUT_LIMIT:],
        }

    def _repo_path(self, repo: str) -> Path:
        path = Path(repo)
        if not path.is_dir():
            raise ValueError(f"repository not found: {repo}")
        if not (path / "HEAD").is_file() and not (path / ".git").exists():
            raise ValueError(f"not a Git repository: {repo}")
        return path.resolve()

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["evidence"] = json.loads(item["evidence"] or "{}")
        return item
