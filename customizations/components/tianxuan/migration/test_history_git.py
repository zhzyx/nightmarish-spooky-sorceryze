import hashlib
import json
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from history_git import MAX_FILE_SIZE, _heading, list_commits, read_file, requirement_titles
from history_records import export_binary
from importer import import_inventory
from migration_status import publish_import


class PublishedGitHistory(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        repo = root / "work"
        subprocess.run(["git", "init", "-q", str(repo)], check=True)

        def git(*args):
            return (
                subprocess
                .check_output([
                    "git",
                    "-C",
                    str(repo),
                    "-c",
                    "core.autocrlf=false",
                    "-c",
                    "user.name=test",
                    "-c",
                    "user.email=test@example.invalid",
                    *args,
                ])
                .decode()
                .strip()
            )

        path = repo / "design-docs" / "plan.md"
        path.parent.mkdir()
        path.write_bytes("# 需求\n".encode())
        (repo / "large").write_bytes(b"1" * (MAX_FILE_SIZE + 1))
        (repo / "binary").write_bytes(b"\x00\xff")
        git("add", ".")
        self.blob = git("rev-parse", ":design-docs/plan.md")
        git("update-index", "--add", "--cacheinfo", f"120000,{self.blob},link")
        git("commit", "-qm", "requirement")
        self.first = git("rev-parse", "HEAD")
        git("commit", "--allow-empty", "-qm", "second")
        self.second = git("rev-parse", "HEAD")
        bundle = root / "archive.bundle"
        git("bundle", "create", str(bundle), "--all")
        (root / "records.jsonl").write_bytes(b"")
        manifest = root / "report.json"
        manifest.write_text(
            json.dumps(
                dict(
                    source="org/project",
                    revision=self.second,
                    counts={},
                    records_sha256=hashlib.sha256(b"").hexdigest(),
                    historical_policy="record_only",
                )
            )
        )
        db = root / "native.db"
        receipt = import_inventory(
            manifest,
            db,
            "tenant",
            "actor",
            artifacts={"github:org/project/history.bundle": (bundle, hashlib.sha256(bundle.read_bytes()).hexdigest())},
        )
        publish_import(db, "tenant", "demo", "actor", receipt["module"], receipt["revision"])
        self.args = (db, "tenant", "demo", receipt["revision"])

    def test_paged_history_and_requirement(self):
        first = list_commits(*self.args, limit=1)
        self.assertEqual(first["items"][0]["oid"], self.second)
        self.assertEqual(first["items"][0]["parents"], [self.first])
        second = list_commits(*self.args, offset=first["next_offset"], limit=1)
        self.assertEqual(second["items"][0]["oid"], self.first)
        self.assertIsNone(second["next_offset"])
        history = list_commits(*self.args, commit=self.second, path="design-docs/plan.md")
        self.assertEqual([item["oid"] for item in history["items"]], [self.first])
        file = read_file(*self.args, self.second, "design-docs/plan.md")
        self.assertEqual((file["blob"], file["text"], file["size"]), (self.blob, "# 需求\n", 9))

    def test_concurrent_initialization_reuses_verified_cache_and_reauthorizes(self):
        with patch("history_records.export_binary", wraps=export_binary) as export:
            with ThreadPoolExecutor(max_workers=3) as pool:
                pages = list(pool.map(lambda _: list_commits(*self.args), range(3)))
            self.assertEqual(export.call_count, 1)
            self.assertEqual(pages[0], pages[-1])
        db, tenant, project, revision = self.args
        for scope in (
            (db, "other", project, revision),
            (db, tenant, "other", revision),
            (db, tenant, project, "other"),
        ):
            with self.assertRaises(LookupError):
                list_commits(*scope)

    def test_path_type_limits_and_literal_names(self):
        for path in ("../bad", "/escape", "folder\\outside", "a//b", "a\x00b", "C:/etc", "."):
            with self.subTest(path=path), self.assertRaises(ValueError):
                read_file(*self.args, self.second, path)
        for path in ("binary", "large", "link", "design-docs"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                read_file(*self.args, self.second, path)
        for path in ("missing", "design-docs/*.md", "design-docs/PLAN.md"):
            with self.subTest(path=path), self.assertRaises(LookupError):
                read_file(*self.args, self.second, path)
        for commit in ("HEAD", "--all", self.blob):
            with self.assertRaises(ValueError):
                list_commits(*self.args, commit=commit)
        for pagination in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
            with self.assertRaises(ValueError):
                list_commits(*self.args, **pagination)

    def test_batch_titles_verify_tree_and_ignore_code(self):
        path = "design-docs/plan.md"
        self.assertEqual(requirement_titles(*self.args, self.first, {path: self.blob}), {path: "需求"})
        with self.assertRaises(ValueError):
            requirement_titles(*self.args, self.first, {path: self.first})
        with self.assertRaises(LookupError):
            requirement_titles(*self.args, self.first, {"missing.md": self.blob})
        self.assertEqual(_heading(b"---\ntitle: metadata\n---\n~~~md\n# hidden\n~~~\nTitle\n===\n"), "Title")
        self.assertIsNone(_heading(b"    # code\n"))

    def test_failed_restore_is_retriable(self):
        with patch("history_records.export_binary", side_effect=ValueError("Damaged block")):
            with self.assertRaisesRegex(ValueError, "Damaged block"):
                list_commits(*self.args)
        self.assertEqual(list_commits(*self.args, limit=1)["items"][0]["oid"], self.second)


if __name__ == "__main__":
    unittest.main()
