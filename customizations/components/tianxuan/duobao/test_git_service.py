"""多宝 Git 服务适配器测试。

显式传入仓库自带的 Git 可执行文件，避免依赖 PATH 或宿主全局 Git 配置。
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from git_service import (
    DEFAULT_GIT_EXECUTABLE,
    GIT_EXECUTABLE_ENV,
    GitService,
    GitServiceError,
    MergeConflict,
    ValidationError,
)

GIT_EXECUTABLE = os.environ.get("GIT_EXECUTABLE", r"D:\GongGong\project\runtime\git\cmd\git.exe")
AUTHOR_NAME = "Sail-Li"
AUTHOR_EMAIL = "ruilimerlin@gmail.com"
SHA_PATTERN = r"^[0-9a-f]{40}$"


class GitServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory(prefix="duobao-git-test-", ignore_cleanup_errors=True)
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name) / "repos"
        self.service = GitService(GIT_EXECUTABLE)
        self.repo = self.service.create_repo(self.root, "demo")

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _git(self, *arguments: str) -> str:
        completed = subprocess.run(
            [GIT_EXECUTABLE, *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            shell=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            f"git {' '.join(arguments)} failed: {completed.stderr}",
        )
        return completed.stdout

    def _commit(
        self,
        branch: str = "main",
        message: str = "commit",
        files: dict[str, str] | None = None,
    ) -> str:
        if files is None:
            files = {"file.txt": "one\n"}
        return self.service.commit(  # type: ignore[no-any-return]
            self.repo, branch, message, files, AUTHOR_NAME, AUTHOR_EMAIL
        )

    # ------------------------------------------------------------------
    # repository / commit
    # ------------------------------------------------------------------
    def test_create_repo_and_first_commit(self) -> None:
        self.assertTrue(Path(self.repo).is_dir())
        self.assertEqual(self.service.list_branches(self.repo), [])
        self.assertEqual(self.service.log(self.repo), [])

        initial = self.service.status(self.repo)
        self.assertTrue(initial["bare"])
        self.assertEqual(initial["head"], "main")
        self.assertIsNone(initial["head_sha"])
        self.assertTrue(initial["empty"])

        sha = self._commit(
            message="initial commit",
            files={"README.md": "# 多宝\n", "docs/design.md": "设计\n"},
        )
        self.assertRegex(sha, SHA_PATTERN)
        self.assertEqual(self._git("-C", self.repo, "rev-parse", "main").strip(), sha)
        self.assertEqual(
            self._git("-C", self.repo, "show", "-s", "--format=%an <%ae>", "main").strip(),
            f"{AUTHOR_NAME} <{AUTHOR_EMAIL}>",
        )
        self.assertEqual(
            self._git("-C", self.repo, "show", "main:README.md").replace("\r\n", "\n"),
            "# 多宝\n",
        )
        self.assertEqual(
            self._git("-C", self.repo, "show", "main:docs/design.md").replace("\r\n", "\n"),
            "设计\n",
        )

        self.assertEqual(self.service.list_branches(self.repo), ["main"])
        current = self.service.status(self.repo)
        self.assertEqual(current["head"], "main")
        self.assertEqual(current["head_sha"], sha)
        self.assertEqual(current["branches"], ["main"])
        self.assertFalse(current["empty"])

        # 非裸工作区：读取状态时沿用仓库自身的换行配置，不误报修改。
        worktree = Path(self._temporary.name) / "worktree"
        self._git("clone", "--quiet", self.repo, str(worktree))
        worktree_status = self.service.status(str(worktree))
        self.assertFalse(worktree_status["bare"])
        self.assertTrue(worktree_status["clean"])
        self.assertEqual(worktree_status["head_sha"], sha)

        # 已存在同名仓库时拒绝覆盖。
        named = self.service.create_repo(self.root, "plain.git")
        self.assertEqual(Path(named).name, "plain.git")
        with self.assertRaises(GitServiceError):
            self.service.create_repo(self.root, "plain.git")

    # ------------------------------------------------------------------
    # branches
    # ------------------------------------------------------------------
    def test_branch_and_list(self) -> None:
        first = self._commit()
        self.assertEqual(self.service.branch(self.repo, "feature/login"), first)
        # 同一目标重复创建是幂等的。
        self.assertEqual(self.service.branch(self.repo, "feature/login"), first)
        self.assertEqual(self.service.branch(self.repo, "release", start="main"), first)
        self.assertEqual(
            self.service.list_branches(self.repo),
            ["feature/login", "main", "release"],
        )

        second = self._commit(message="second", files={"file.txt": "two\n"})
        with self.assertRaises(GitServiceError):
            self.service.branch(self.repo, "feature/login", start="main")
        self.assertEqual(
            self._git("-C", self.repo, "rev-parse", "refs/heads/feature/login").strip(),
            first,
        )
        self.assertEqual(self._git("-C", self.repo, "rev-parse", "main").strip(), second)

    # ------------------------------------------------------------------
    # history / diff
    # ------------------------------------------------------------------
    def test_log(self) -> None:
        first = self._commit(message="first")
        second = self._commit(message="second", files={"file.txt": "two\n"})

        entries = self.service.log(self.repo)
        self.assertEqual([entry["message"] for entry in entries], ["second", "first"])
        self.assertEqual(entries[0]["sha"], second)
        self.assertEqual(entries[1]["sha"], first)
        self.assertEqual(entries[0]["author"], AUTHOR_NAME)
        self.assertEqual(entries[0]["email"], AUTHOR_EMAIL)
        self.assertTrue(entries[0]["date"])

        self.assertEqual(len(self.service.log(self.repo, limit=1)), 1)
        self.assertEqual(self.service.log(self.repo, limit=1)[0]["sha"], second)
        self.assertEqual(self.service.log(self.repo, ref="main", limit=1)[0]["sha"], second)

        with self.assertRaises(ValidationError):
            self.service.log(self.repo, limit=0)
        with self.assertRaises(ValidationError):
            self.service.log(self.repo, ref="HEAD~1")
        with self.assertRaises(ValidationError):
            self.service.log(self.repo, ref="-n")
        with self.assertRaises(GitServiceError):
            self.service.log(self.repo, ref="missing")

    def test_diff(self) -> None:
        first = self._commit(files={"app.py": "print('one')\n"})
        second = self._commit(message="add two", files={"app.py": "print('one')\nprint('two')\n"})

        diff = self.service.diff(self.repo, first, second)
        self.assertIn("--- a/app.py", diff)
        self.assertIn("+++ b/app.py", diff)
        self.assertIn("+print('two')", diff)

        reverse = self.service.diff(self.repo, second, first)
        self.assertIn("-print('two')", reverse)
        self.assertEqual(self.service.diff(self.repo, first, first), "")

        with self.assertRaises(ValidationError):
            self.service.diff(self.repo, "HEAD~1", second)
        with self.assertRaises(ValidationError):
            self.service.diff(self.repo, "main;rm", second)
        with self.assertRaises(GitServiceError):
            self.service.diff(self.repo, "missing", second)

    # ------------------------------------------------------------------
    # merges
    # ------------------------------------------------------------------
    def test_fast_forward_merge(self) -> None:
        self._commit(files={"base.txt": "base\n"})
        self.service.branch(self.repo, "feature")
        feature_sha = self._commit(
            branch="feature",
            message="feature work",
            files={"feature.txt": "feature\n"},
        )

        merged = self.service.merge(self.repo, "feature", "main", strategy="--ff-only")
        self.assertEqual(merged, feature_sha)
        self.assertEqual(self._git("-C", self.repo, "rev-parse", "main").strip(), feature_sha)
        self.assertEqual(len(self.service.log(self.repo, ref="main")), 2)
        self.assertEqual(
            self.service.log(self.repo, ref="main", limit=1)[0]["message"],
            "feature work",
        )

        # 默认 --no-ff：生成双亲合并提交。
        self.service.branch(self.repo, "topic")
        topic_sha = self._commit(branch="topic", message="topic work", files={"topic.txt": "topic\n"})
        merge_sha = self.service.merge(self.repo, "topic", "main")
        self.assertNotIn(merge_sha, (feature_sha, topic_sha))
        parents = self._git("-C", self.repo, "rev-list", "--parents", "-n", "1", merge_sha).split()
        self.assertEqual(parents, [merge_sha, feature_sha, topic_sha])
        self.assertEqual(
            self.service.log(self.repo, ref="main", limit=1)[0]["message"],
            "Merge branch 'topic' into main",
        )

    def test_conflicting_merge_raises_and_leaves_clean_state(self) -> None:
        self._commit(files={"greeting.txt": "hello\n"})
        self.service.branch(self.repo, "left")
        self._commit(branch="left", message="left change", files={"greeting.txt": "left\n"})
        main_sha = self._commit(message="main change", files={"greeting.txt": "right\n"})
        branches_before = self.service.list_branches(self.repo)

        with self.assertRaises(MergeConflict) as raised:
            self.service.merge(self.repo, "left", "main")

        self.assertIn("greeting.txt", raised.exception.paths)
        self.assertEqual(raised.exception.conflicts, raised.exception.paths)
        self.assertIn("greeting.txt", str(raised.exception))

        # 裸仓库未被改动，也没有遗留的合并状态。
        self.assertEqual(self._git("-C", self.repo, "rev-parse", "main").strip(), main_sha)
        self.assertEqual(self.service.list_branches(self.repo), branches_before)
        self.assertEqual(self.service.status(self.repo)["head_sha"], main_sha)
        self.assertFalse((Path(self.repo) / "MERGE_HEAD").exists())

        # 再次合并仍得到冲突（而不是“merge 已在进行中”等残留错误）。
        with self.assertRaises(MergeConflict):
            self.service.merge(self.repo, "left", "main")
        self.assertEqual(self._git("-C", self.repo, "rev-parse", "main").strip(), main_sha)

    # ------------------------------------------------------------------
    # validation
    # ------------------------------------------------------------------
    def test_invalid_refs_and_paths_rejected(self) -> None:
        self._commit()

        bad_paths = [
            "",
            ".",
            "..",
            "../escape.txt",
            "sub/../../escape.txt",
            "/etc/passwd",
            r"C:\Windows\evil.txt",
            "C:evil.txt",
            "dir/",
            "a;b.txt",
            "a|b.txt",
            "a>b.txt",
            "a\nb.txt",
        ]
        for bad_path in bad_paths:
            with self.subTest(path=bad_path):
                with self.assertRaises(ValidationError):
                    self.service.commit(
                        self.repo,
                        "main",
                        "bad path",
                        {bad_path: "x"},
                        AUTHOR_NAME,
                        AUTHOR_EMAIL,
                    )

        bad_branches = [
            "",
            "../main",
            "-evil",
            "bad name",
            "refs/heads/main",
            "a..b",
            "x.lock",
            "a;b",
            "/abs",
            "feature//x",
            "@",
            "HEAD",
        ]
        for bad_branch in bad_branches:
            with self.subTest(branch=bad_branch):
                with self.assertRaises(ValidationError):
                    self.service.branch(self.repo, bad_branch)

        with self.assertRaises(ValidationError):
            self.service.log(self.repo, ref="main^")
        with self.assertRaises(ValidationError):
            self.service.diff(self.repo, "../main", "main")
        with self.assertRaises(ValidationError):
            self.service.merge(self.repo, "main", "main", strategy="--evil")
        with self.assertRaises(ValidationError):
            self.service.create_repo(self.root, "../escaped")
        with self.assertRaises(ValidationError):
            self.service.create_repo(self.root, "demo/evil")

        with self.assertRaises(ValidationError):
            self.service.commit(self.repo, "main", "bad author", {"x.txt": "x"}, "", AUTHOR_EMAIL)
        with self.assertRaises(ValidationError):
            self.service.commit(self.repo, "main", "bad email", {"x.txt": "x"}, AUTHOR_NAME, "nope")
        with self.assertRaises(ValidationError):
            self.service.commit(self.repo, "main", "", {"x.txt": "x"}, AUTHOR_NAME, AUTHOR_EMAIL)
        with self.assertRaises(ValidationError):
            self.service.commit(self.repo, "main", "empty files", {}, AUTHOR_NAME, AUTHOR_EMAIL)
        with self.assertRaises(ValidationError):
            self.service.commit(
                self.repo,
                "main",
                "bad content",
                {"x.txt": 42},  # type: ignore[dict-item]
                AUTHOR_NAME,
                AUTHOR_EMAIL,
            )

        self.assertFalse((self.root.parent / "escaped.git").exists())
        self.assertFalse((self.root / "demo" / "evil.git").exists())
        self.assertFalse((Path(self.repo).parent / "escape.txt").exists())

        with self.assertRaises(GitServiceError):
            self.service.status(self.root)

    # ------------------------------------------------------------------
    # executable resolution
    # ------------------------------------------------------------------
    def test_git_executable_resolution(self) -> None:
        self.assertEqual(self.service.git_executable, GIT_EXECUTABLE)
        with mock.patch.dict(os.environ, {GIT_EXECUTABLE_ENV: r"C:\custom\git.exe"}):
            self.assertEqual(GitService().git_executable, r"C:\custom\git.exe")
            self.assertEqual(GitService(GIT_EXECUTABLE).git_executable, GIT_EXECUTABLE)
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(GitService().git_executable, DEFAULT_GIT_EXECUTABLE)
        with self.assertRaises(ValidationError):
            GitService("")


if __name__ == "__main__":
    unittest.main()
