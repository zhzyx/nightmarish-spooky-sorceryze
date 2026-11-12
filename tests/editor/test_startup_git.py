#!/usr/bin/env python3
"""Startup Git tests use local temporary repositories; no external remote."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "customizations/components/godot-host/startup_git_helper.py"
spec = importlib.util.spec_from_file_location("startup_git_helper", HELPER)
assert spec is not None and spec.loader is not None
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


@unittest.skipUnless(shutil.which("git"), "Git required")
class StartupGitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = self.root / "remote.git"
        self.seed = self.root / "seed"
        self.local = self.root / "local"
        self.git(self.root, "init", "--bare", str(self.remote))
        self.git(self.root, "clone", str(self.remote), str(self.seed))
        self.git(self.seed, "checkout", "-b", "main")
        self.configure(self.seed)
        self.commit(self.seed, "initial.txt", "initial")
        self.git(self.seed, "push", "-u", "origin", "main")
        self.git(self.root, "clone", "-b", "main", str(self.remote), str(self.local))
        self.configure(self.local)

    def git(self, cwd, *args):
        result = subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)
        return result.stdout.decode().strip()

    def configure(self, repo):
        self.git(repo, "config", "user.name", "Startup Test")
        self.git(repo, "config", "user.email", "startup@example.invalid")
        self.git(repo, "config", "commit.gpgsign", "false")

    def commit(self, repo, name, data):
        (repo / name).write_text(data)
        self.git(repo, "add", name)
        self.git(repo, "commit", "-m", name)
        return self.git(repo, "rev-parse", "HEAD")

    def advance(self):
        target = self.commit(self.seed, "remote.txt", "remote")
        self.git(self.seed, "push", "origin", "main")
        return target

    def sync(self, status):
        result = helper.synchronize(str(self.local))
        self.assertEqual(result["status"], status, result)
        self.assertLess(len(json.dumps(result)), 2048)
        self.assertNotIn(str(self.remote), result["message"])
        return result

    def test_current_and_fast_forward(self):
        self.sync("current")
        target = self.advance()
        self.sync("updated")
        self.assertEqual(self.git(self.local, "rev-parse", "HEAD"), target)
        self.assertEqual((self.local / "remote.txt").read_text(), "remote")

    def test_dirty_and_untracked_fetch_without_update(self):
        original = self.git(self.local, "rev-parse", "HEAD")
        target = self.advance()
        (self.local / "initial.txt").write_text("unsaved")
        self.sync("dirty")
        self.assertEqual(self.git(self.local, "rev-parse", "HEAD"), original)
        self.assertEqual(self.git(self.local, "rev-parse", "@{u}"), target)
        self.assertEqual((self.local / "initial.txt").read_text(), "unsaved")
        (self.local / "initial.txt").write_text("initial")
        (self.local / "untracked.txt").write_text("precious")
        self.sync("dirty")
        self.assertEqual((self.local / "untracked.txt").read_text(), "precious")
        self.assertFalse((self.local / "remote.txt").exists())

    def test_ignored_local_file_is_not_overwritten(self):
        self.commit(self.seed, ".gitignore", "private.txt\n")
        self.git(self.seed, "push", "origin", "main")
        self.sync("updated")
        local_file = self.local / "private.txt"
        local_file.write_text("precious local content")
        original = self.git(self.local, "rev-parse", "HEAD")
        (self.seed / "private.txt").write_text("upstream content")
        self.git(self.seed, "add", "--force", "private.txt")
        self.git(self.seed, "commit", "-m", "Track formerly ignored path")
        self.git(self.seed, "push", "origin", "main")
        self.sync("update_failed")
        self.assertEqual(local_file.read_text(), "precious local content")
        self.assertEqual(self.git(self.local, "rev-parse", "HEAD"), original)
        self.assertEqual(self.git(self.local, "status", "--porcelain"), "")

    def test_configured_squash_does_not_change_fast_forward_policy(self):
        target = self.advance()
        self.git(self.local, "config", "branch.main.mergeOptions", "--squash")
        self.sync("updated")
        self.assertEqual(self.git(self.local, "rev-parse", "HEAD"), target)
        self.assertEqual(self.git(self.local, "status", "--porcelain"), "")

    def test_ahead_and_diverged(self):
        head = self.commit(self.local, "local.txt", "local")
        self.sync("ahead")
        self.advance()
        self.sync("diverged")
        self.assertEqual(self.git(self.local, "rev-parse", "HEAD"), head)
        self.assertFalse((self.local / ".git/MERGE_HEAD").exists())

    def test_no_upstream_and_detached(self):
        self.git(self.local, "branch", "--unset-upstream")
        self.sync("no_upstream")
        self.git(self.local, "checkout", "--detach")
        self.sync("no_upstream")

    def test_missing_repo_and_git(self):
        self.assertEqual(helper.synchronize(str(self.root))["status"], "no_repository")
        with patch.object(helper.shutil, "which", return_value=None):
            self.sync("no_git")

    def test_offline_message_does_not_include_remote(self):
        self.git(self.local, "remote", "set-url", "origin", str(self.root / "missing-secret-token.git"))
        self.sync("fetch_failed")

    def test_existing_operation_and_lock(self):
        gitdir = self.local / ".git"
        (gitdir / "MERGE_HEAD").write_text(self.git(self.local, "rev-parse", "HEAD"))
        self.sync("busy")
        (gitdir / "MERGE_HEAD").unlink()
        with helper.worktree_lock(gitdir):
            self.sync("busy")
        self.sync("current")

    def test_configuration_change_after_fetch(self):
        self.advance()
        original_run = helper.Runner.run

        def changed(runner, *args):
            result = original_run(runner, *args)
            if args[0] == "fetch":
                self.git(self.local, "config", "branch.main.merge", "refs/heads/other")
            return result

        with patch.object(helper.Runner, "run", changed):
            # Removed/nonexistent upstream must never update the worktree.
            result = helper.synchronize(str(self.local))
        self.assertEqual(result["status"], "changed")
        self.assertFalse((self.local / "remote.txt").exists())

    def test_remote_configuration_change_after_fetch(self):
        self.advance()
        original_head = self.git(self.local, "rev-parse", "HEAD")
        original_run = helper.Runner.run
        for setting, value in (
            ("remote.origin.url", str(self.root / "new-secret-token.git")),
            ("remote.origin.fetch", "+refs/heads/extra:refs/remotes/origin/extra"),
        ):
            with self.subTest(setting=setting):

                def changed(runner, *args):
                    result = original_run(runner, *args)
                    if args[0] == "fetch":
                        # Add a fetch mapping to preserve @{u} resolution while
                        # still changing configured remote behavior.
                        operation = "--add" if setting.endswith(".fetch") else "--replace-all"
                        self.git(self.local, "config", operation, setting, value)
                    return result

                with patch.object(helper.Runner, "run", changed):
                    self.sync("changed")
                self.assertEqual(self.git(self.local, "rev-parse", "HEAD"), original_head)
                self.assertFalse((self.local / "remote.txt").exists())
                self.git(self.local, "remote", "set-url", "origin", str(self.remote))

    def test_dirty_change_after_fetch(self):
        self.advance()
        original_run = helper.Runner.run

        def changed(runner, *args):
            result = original_run(runner, *args)
            if args[0] == "fetch":
                (self.local / "new.txt").write_text("keep")
            return result

        with patch.object(helper.Runner, "run", changed):
            self.sync("dirty")
        self.assertEqual((self.local / "new.txt").read_text(), "keep")
        self.assertFalse((self.local / "remote.txt").exists())

    def test_hooks_not_run(self):
        self.advance()
        marker = self.root / "hook-ran"
        hook = self.local / ".git/hooks/post-merge"
        hook.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\n')
        hook.chmod(0o755)
        self.sync("updated")
        self.assertFalse(marker.exists())

    def test_cancelled_and_timeout(self):
        cancelled = threading.Event()
        cancelled.set()
        self.assertEqual(helper.synchronize(str(self.local), cancelled=cancelled)["status"], "cancelled")
        self.assertEqual(helper.synchronize(str(self.local), timeout=0.05)["status"], "timeout")
        self.sync("current")

    @unittest.skipIf(os.name == "nt", "POSIX process-group cleanup fixture")
    def test_timeout_kills_process_descendants(self):
        fake = self.root / "fake-git"
        marker = self.root / "leaked-child"
        fake.write_text(
            "#!" + sys.executable + "\nimport subprocess, sys, time\n"
            'subprocess.Popen([sys.executable, "-c", '
            + repr(
                "import time; from pathlib import Path; time.sleep(1); Path("
                + repr(str(marker))
                + ').write_text("bad")'
            )
            + "])\ntime.sleep(30)\n"
        )
        fake.chmod(0o755)
        start = time.monotonic()
        with patch.object(helper.shutil, "which", return_value=str(fake)):
            self.assertEqual(helper.synchronize(str(self.local), timeout=0.1)["status"], "timeout")
        self.assertLess(time.monotonic() - start, 3)
        time.sleep(1.1)
        self.assertFalse(marker.exists())

    @unittest.skipIf(os.name == "nt", "POSIX process-group cleanup fixture")
    def test_midflight_cancel_kills_process_descendants(self):
        fake = self.root / "fake-git"
        ready = self.root / "ready"
        marker = self.root / "leaked-child"
        child = (
            "import time; from pathlib import Path; time.sleep(1); Path(" + repr(str(marker)) + ').write_text("bad")'
        )
        fake.write_text(
            "#!"
            + sys.executable
            + "\nimport subprocess, sys, time\n"
            + "from pathlib import Path\n"
            + 'subprocess.Popen([sys.executable, "-c", '
            + repr(child)
            + "])\n"
            + "Path("
            + repr(str(ready))
            + ").touch()\ntime.sleep(30)\n"
        )
        fake.chmod(0o755)
        cancelled = threading.Event()
        results = []
        with patch.object(helper.shutil, "which", return_value=str(fake)):
            worker = threading.Thread(
                target=lambda: results.append(helper.synchronize(str(self.local), cancelled=cancelled))
            )
            worker.start()
            until = time.monotonic() + 3
            while not ready.exists() and time.monotonic() < until:
                time.sleep(0.01)
            cancelled.set()
            worker.join(timeout=3)
        self.assertFalse(worker.is_alive())
        self.assertTrue(ready.exists())
        self.assertEqual(results[0]["status"], "cancelled")
        time.sleep(1.1)
        self.assertFalse(marker.exists())

    def test_cli_cancel_and_parent_eof(self):
        for send in (True, False):
            process = subprocess.Popen(
                [sys.executable, str(HELPER), str(self.local)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if send:
                process.stdin.write(b"cancel\n")
                process.stdin.flush()
            process.stdin.close()
            process.wait(timeout=5)
            result = json.loads(process.stdout.read())
            self.assertEqual(result["status"], "cancelled")
            self.assertEqual(process.stderr.read(), b"")
            process.stdout.close()
            process.stderr.close()

    def test_other_worktree_unchanged(self):
        other = self.root / "other"
        self.git(self.local, "worktree", "add", "-b", "other", str(other))
        original = self.git(other, "rev-parse", "HEAD")
        (other / "keep.txt").write_text("keep")
        self.advance()
        self.sync("updated")
        self.assertEqual(self.git(other, "rev-parse", "HEAD"), original)
        self.assertEqual((other / "keep.txt").read_text(), "keep")
        self.assertFalse((other / "remote.txt").exists())


if __name__ == "__main__":
    unittest.main()
