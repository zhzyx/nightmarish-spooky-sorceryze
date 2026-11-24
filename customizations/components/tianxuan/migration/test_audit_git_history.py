import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from audit_git_history import audit_git_history
from git_archive import capture, git
from import_git_history import import_git_history


def publish(root, repo, project):
    folder = root / project
    folder.mkdir()
    mirror = folder / "archive.git"
    git(repo, "clone", "--mirror", "--quiet", "--", str(repo), str(mirror))
    git(mirror, "remote", "set-url", "origin", "https://github.com/sample/repo.git")
    capture("sample/repo", folder)
    return import_git_history(folder, root / "db.sqlite", "owners", "operator", project)["publication"]


def exercise(root):
    repo = root / "work"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main", "--object-format=sha1")
    git(repo, "commit", "-qm", "root", "--allow-empty")
    git(repo, "tag", "-a", "release", "-m", "release")
    git(repo, "branch", "topic")
    original = b"old\x00data\xff"
    changed = b"new\x00data\xff"
    path = repo / "data.bin"
    path.write_bytes(original)
    git(repo, "add", "data.bin")
    git(repo, "commit", "-qm", "binary")
    git(repo, "tag", "light", "refs/heads/topic")
    publications = {"copy": publish(root, repo, "copy")}
    git(repo, "branch", "-d", "topic")
    publications["deleted"] = publish(root, repo, "deleted")
    git(repo, "branch", "topic", "light")
    path.write_bytes(changed)
    git(repo, "add", "data.bin")
    git(repo, "commit", "--amend", "--no-edit", "-q")
    publications["edited"] = publish(root, repo, "edited")

    reports = {}
    for project, publication in publications.items():
        cmd = [
            sys.executable,
            str(Path(__file__).with_name("audit_git_history.py")),
            str(root / "copy/archive.git"),
            str(root / "copy/git-report.json"),
            str(root / "db.sqlite"),
            "--tenant",
            "owners",
            "--project",
            project,
            "--revision",
            publication["revision"],
        ]
        result = subprocess.run(cmd, capture_output=True)
        assert result.returncode == (0 if project == "copy" else 1), result.stderr
        report = json.loads(result.stdout)
        assert report["publication"] == publication
        reports[project] = report

    same, deleted, edited = (reports[k] for k in ("copy", "deleted", "edited"))
    assert same["complete"] and same["ref_status_counts"] == {"matched": 5}
    assert same["object_status_counts"] == {"matched": 6}
    assert {r["source"]["type"] for r in same["objects"]} == {"commit", "tree", "blob", "tag"}
    assert [r["ref"] for r in deleted["refs"] if r["status"] != "matched"] == ["refs/heads/topic"]
    assert deleted["ref_status_counts"]["missing"] == 1 and deleted["object_status_counts"] == {"matched": 6}
    assert {r["ref"] for r in edited["refs"] if r["status"] == "changed"} == {"HEAD", "refs/heads/main"}
    for status, side, data in [("missing", "source", original), ("unexpected", "target", changed)]:
        blobs = [r[side] for r in edited["objects"] if r["status"] == status and r[side]["type"] == "blob"]
        assert blobs == [
            dict(type="blob", size=len(data), sha256=hashlib.sha256(data).hexdigest(), example_name="data.bin")
        ]
    return reports


class HistoryIntegrityTests(unittest.TestCase):
    def test_project_publication_and_two_independent_differences(self):
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
        env.update(
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_AUTHOR_NAME="Source",
            GIT_COMMITTER_NAME="Source",
            GIT_AUTHOR_EMAIL="source@example.invalid",
            GIT_COMMITTER_EMAIL="source@example.invalid",
            GIT_AUTHOR_DATE="2026-11-20T08:00:00Z",
            GIT_COMMITTER_DATE="2026-11-20T08:00:00Z",
        )
        with patch.dict(os.environ, env, clear=True), tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reports = exercise(root)
            args = root / "copy/archive.git", root / "copy/git-report.json", root / "db.sqlite"
            revision = reports["copy"]["publication"]["revision"]
            with self.assertRaises(LookupError):
                audit_git_history(*args, "other", "copy", revision)
            git(args[0], "update-ref", "refs/heads/new", "HEAD")
            with self.assertRaisesRegex(ValueError, "fixed inventory"):
                audit_git_history(*args, "owners", "copy", revision)
