"""Regression cases for untrusted commit file mappings (no external services)."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from git_service import GitService, ValidationError


class AdminPathsTests(unittest.TestCase):
    def test_resolved_admin_alias_rejected(self):
        # Model a directory alias not detected as a symlink/junction. This is
        # defense in depth, not a claim that Git clone creates such an alias.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            worktree = root / "worktree"
            admin = worktree / ".git"
            admin.mkdir(parents=True)
            config = admin / "config"
            config.write_text("original")
            alias = worktree / "alias"
            alias.symlink_to(admin, target_is_directory=True)
            original_is_symlink = Path.is_symlink

            def is_symlink(path):
                return False if path == alias else original_is_symlink(path)

            service = GitService()
            with (
                mock.patch.object(service, "_repo_path", return_value=(root, True)),
                mock.patch.object(service, "_clone"),
                mock.patch.object(service, "_checkout_branch"),
                mock.patch("git_service.tempfile.TemporaryDirectory") as temporary,
                mock.patch.object(service, "_run") as run,
                mock.patch.object(Path, "is_symlink", is_symlink),
                mock.patch.object(Path, "is_junction", return_value=False, create=True),
            ):
                temporary.return_value.__enter__.return_value = tmp
                with self.assertRaises(ValidationError):
                    service.commit(
                        root,
                        "main",
                        "test",
                        {"safe.txt": "new", "alias/config": "changed"},
                        "Test",
                        "t@example.invalid",
                    )
                run.assert_not_called()
            self.assertEqual(config.read_text(), "original")
            self.assertFalse((worktree / "safe.txt").exists())

    def test_admin_aliases_rejected_before_any_process(self):
        paths = [
            ".git",
            ".git/config",
            ".GIT/config",
            "dir/.Git/config",
            ".git./config",
            ".git.../config",
            ".git /config",
            "git~1/config",
            ".git:config",
            ".git\\config",
            ".g\u200cit/config",
            ".gi\ufefft/config",
            ".g\u202eit/config",
        ]
        for path in paths:
            with self.subTest(path=path), mock.patch("subprocess.run") as run:
                with self.assertRaises(ValidationError):
                    GitService().commit("nonexistent", "main", "test", {path: "x"}, "Test", "t@example.invalid")
                run.assert_not_called()

    def test_symlinks_rejected_before_any_input_write(self):
        for directory_link in (False, True):
            with self.subTest(directory_link=directory_link), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                worktree = root / "worktree"
                worktree.mkdir()
                admin = worktree / ".git"
                admin.mkdir()
                config = admin / "config"
                config.write_text("original")
                link = worktree / "alias"
                link.symlink_to(admin if directory_link else config, target_is_directory=directory_link)
                path = "alias/config" if directory_link else "alias"
                service = GitService()
                with (
                    mock.patch.object(service, "_repo_path", return_value=(root, True)),
                    mock.patch.object(service, "_clone"),
                    mock.patch.object(service, "_checkout_branch"),
                    mock.patch("git_service.tempfile.TemporaryDirectory") as temporary,
                    mock.patch.object(service, "_run") as run,
                ):
                    temporary.return_value.__enter__.return_value = tmp
                    with self.assertRaises(ValidationError):
                        service.commit(
                            root, "main", "test", {"safe.txt": "new", path: "replaced"}, "Test", "t@example.invalid"
                        )
                    run.assert_not_called()
                self.assertEqual(config.read_text(), "original")
                self.assertFalse((worktree / "safe.txt").exists())

    def test_existing_regular_files_remain_writable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            worktree = root / "worktree"
            worktree.mkdir()
            (worktree / "README.md").write_text("old")
            service = GitService()
            with (
                mock.patch.object(service, "_repo_path", return_value=(root, True)),
                mock.patch.object(service, "_clone"),
                mock.patch.object(service, "_checkout_branch"),
                mock.patch.object(service, "_rev_parse", return_value="a" * 40),
                mock.patch("git_service.tempfile.TemporaryDirectory") as temporary,
                mock.patch.object(service, "_run", return_value=subprocess.CompletedProcess([], 0)),
            ):
                temporary.return_value.__enter__.return_value = tmp
                sha = service.commit(
                    root,
                    "main",
                    "test",
                    {"README.md": "new", ".github/workflows/ci.yml": "ok"},
                    "Test",
                    "t@example.invalid",
                )
            self.assertEqual(sha, "a" * 40)
            self.assertEqual((worktree / "README.md").read_text(), "new")
            self.assertEqual((worktree / ".github/workflows/ci.yml").read_text(), "ok")

    def test_process_disables_hooks_fsmonitor_and_signing(self):
        with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0)) as run:
            GitService()._run(["status"])
        command = run.call_args.args[0]
        self.assertIn(f"core.hooksPath={os.devnull}", command)
        self.assertIn("core.fsmonitor=false", command)
        self.assertIn("commit.gpgsign=false", command)
        self.assertFalse(run.call_args.kwargs["shell"])


if __name__ == "__main__":
    unittest.main()
