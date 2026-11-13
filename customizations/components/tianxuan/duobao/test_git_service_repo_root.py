"""Exact-root regressions using local, synthetic Git repositories only."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from git_service import GitService, GitServiceError

GIT_EXECUTABLE = os.environ.get("GIT_EXECUTABLE", "git")


class GitServiceRepoRootTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="duobao-root-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        config = self.root / "isolated.gitconfig"
        config.write_text(
            "[user]\nname = Root Test\nemail = root-test@example.invalid\n"
            "[commit]\ngpgsign = false\n[core]\nautocrlf = false\n",
            encoding="utf-8",
        )
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        environment.update(
            GIT_CONFIG_GLOBAL=str(config),
            GIT_CONFIG_SYSTEM=os.devnull,
            GIT_CONFIG_NOSYSTEM="1",
            GIT_ALLOW_PROTOCOL="file",
            GIT_TERMINAL_PROMPT="0",
            GIT_CONFIG_COUNT="1",
            GIT_CONFIG_KEY_0="core.hooksPath",
            GIT_CONFIG_VALUE_0=os.devnull,
        )
        # No discovery ceiling: Git must discover the synthetic parent of each
        # rejected child, so a test-only ceiling cannot hide the product bug.
        patcher = mock.patch.dict(os.environ, environment, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.service = GitService(GIT_EXECUTABLE)
        self.worktree = self.root / ("工作 tree" if os.name == "nt" else "工作 tree ")
        self._git("init", "--quiet", "--initial-branch=main", str(self.worktree))
        (self.worktree / "tracked.txt").write_text("initial\n", encoding="utf-8")
        self._git("-C", str(self.worktree), "add", "tracked.txt")
        self._git("-C", str(self.worktree), "commit", "--quiet", "-m", "initial")
        self.bare = self.root / "bare repository.git"
        self._git("clone", "--quiet", "--bare", str(self.worktree), str(self.bare))
        self.linked = self.root / "linked worktree"
        self._git("-C", str(self.worktree), "worktree", "add", "--quiet", "-b", "linked", str(self.linked))

    def _git(self, *arguments: str) -> str:
        return subprocess.check_output([GIT_EXECUTABLE, *arguments], text=True, encoding="utf-8")

    def _snapshot(self, repository: Path) -> tuple[str, str, str]:
        refs = self._git("-C", str(repository), "for-each-ref", "--format=%(refname) %(objectname)")
        head = self._git("-C", str(repository), "symbolic-ref", "HEAD")
        status = ""
        if self._git("-C", str(repository), "rev-parse", "--is-bare-repository").strip() == "false":
            status = self._git("-C", str(repository), "status", "--porcelain", "--untracked-files=all")
        return refs, head, status

    def _assert_child_rejected(self, repository: Path, child: Path, *, bare: bool) -> None:
        flag = "--absolute-git-dir" if bare else "--show-toplevel"
        actual = self._git("-C", str(child), "rev-parse", flag).removesuffix("\n")
        self.assertEqual(Path(actual).resolve(), repository.resolve())
        before = self._snapshot(repository)
        operations = {
            "status": lambda: self.service.status(child),
            "list_branches": lambda: self.service.list_branches(child),
            "log": lambda: self.service.log(child),
            "diff": lambda: self.service.diff(child, "HEAD", "HEAD"),
            "branch": lambda: self.service.branch(child, "must-not-be-created"),
            "commit": lambda: self.service.commit(
                child, "main", "must not commit", {"changed.txt": "x"}, "Test", "test@example.invalid"
            ),
            "merge": lambda: self.service.merge(child, "main", "main"),
        }
        for name, operation in operations.items():
            with self.subTest(operation=name):
                try:
                    with self.assertRaises(GitServiceError):
                        operation()
                finally:
                    self.assertEqual(self._snapshot(repository), before)

    def test_plain_child_rejected_without_parent_mutation(self) -> None:
        child = self.worktree / "plain" / "nested"
        child.mkdir(parents=True)
        (self.worktree / "tracked.txt").write_text("dirty\n", encoding="utf-8")
        self._assert_child_rejected(self.worktree, child, bare=False)

    def test_bare_internal_directory_rejected_without_parent_mutation(self) -> None:
        self._assert_child_rejected(self.bare, self.bare / "objects", bare=True)

    def test_linked_child_rejected_without_parent_mutation(self) -> None:
        child = self.linked / "plain"
        child.mkdir()
        self._assert_child_rejected(self.linked, child, bare=False)

    def test_worktree_metadata_directory_rejected(self) -> None:
        before = self._snapshot(self.worktree)
        with self.assertRaises(GitServiceError):
            self.service.status(self.worktree / ".git")
        self.assertEqual(self._snapshot(self.worktree), before)

    def test_non_repository_directory_rejected(self) -> None:
        outside = self.root / "no-repository"
        outside.mkdir()
        # The test runner itself may live under a checkout. Isolate only this
        # fixture, and verify that native Git also sees no repository here.
        with mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": str(self.root)}):
            probe = subprocess.run(
                [GIT_EXECUTABLE, "-C", str(outside), "rev-parse", "--is-bare-repository"], capture_output=True
            )
            self.assertNotEqual(probe.returncode, 0)
            with self.assertRaises(GitServiceError):
                self.service.status(outside)

    def test_exact_roots_and_normalized_paths_remain_usable(self) -> None:
        for repository, bare in ((self.worktree, False), (self.bare, True), (self.linked, False)):
            with self.subTest(repository=repository.name):
                status = self.service.status(repository / ".")
                self.assertEqual(status["path"], str(repository.resolve()))
                self.assertIs(status["bare"], bare)
                self.assertEqual(self.service.status(os.path.relpath(repository))["path"], str(repository.resolve()))
                self.assertFalse(status["empty"])
                self.assertEqual(self.service.branch(repository, "accepted-root"), status["head_sha"])
                self.assertIn("accepted-root", self.service.list_branches(repository))
                self.assertEqual(len(self.service.log(repository)), 1)
                self.assertEqual(self.service.diff(repository, "HEAD", "HEAD"), "")
        empty_bare = self.service.create_repo(self.root, "empty")
        self.assertTrue(self.service.status(empty_bare)["empty"])
        empty_worktree = self.root / "empty-worktree"
        self._git("init", "--quiet", "--initial-branch=main", str(empty_worktree))
        self.assertTrue(self.service.status(empty_worktree)["empty"])

    def test_symlink_roots_accepted_and_symlink_children_rejected(self) -> None:
        for index, (repository, bare) in enumerate(((self.worktree, False), (self.bare, True), (self.linked, False))):
            link = self.root / f"alias-{index}"
            try:
                link.symlink_to(repository, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"directory symlinks unavailable: {error}")
            with self.subTest(repository=repository.name):
                status = self.service.status(link)
                self.assertEqual(status["path"], str(repository.resolve()))
                self.assertIs(status["bare"], bare)
                child = repository / "ordinary-child"
                child.mkdir()
                self._assert_child_rejected(repository, link / child.name, bare=bare)

    @unittest.skipIf(os.name == "nt", "Windows forbids CR/LF in path components")
    def test_root_paths_preserve_carriage_returns_and_newlines(self) -> None:
        for index, name in enumerate(("cr\rname", "crlf\r\nname", "lf\nname", "end\r", "end\n")):
            for bare in (False, True):
                with self.subTest(name=name, bare=bare):
                    repository = self.root / f"{index}-{bare}-{name}"
                    arguments = ["init", "--quiet", "--initial-branch=main"]
                    if bare:
                        arguments.append("--bare")
                    self._git(*arguments, str(repository))
                    resolved, actual_bare = self.service._repo_path(repository)
                    self.assertEqual(resolved, repository.resolve())
                    self.assertEqual(actual_bare, bare)
                    child = repository / "child"
                    child.mkdir()
                    with self.assertRaises(GitServiceError):
                        self.service._repo_path(child)


if __name__ == "__main__":
    unittest.main()
