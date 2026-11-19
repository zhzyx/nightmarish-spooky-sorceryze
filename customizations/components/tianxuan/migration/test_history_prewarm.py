"""Exercise offline pack indexing and target adoption against a published native bundle."""

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from history_git import list_commits, read_file
from history_prewarm import adopt
from importer import import_inventory
from migration_status import publish_import
from prewarm_prepare import prepare


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PublishedGitPrewarm(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        cls.offline = Path(temp.name)
        repo = cls.offline / "work"
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        git = [
            "git",
            "-C",
            str(repo),
            "-c",
            "core.autocrlf=false",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@invalid",
        ]
        (repo / "readme.txt").write_bytes(b"archived file\n")
        subprocess.run([*git, "add", "readme.txt"], check=True)
        subprocess.run([*git, "commit", "-qm", "Original text"], check=True)
        cls.first = subprocess.check_output([*git, "rev-parse", "HEAD"], text=True).strip()
        subprocess.run([*git, "tag", "historical", cls.first], check=True)
        subprocess.run([*git, "commit", "--allow-empty", "-qm", "Second commit"], check=True)
        cls.head = subprocess.check_output([*git, "rev-parse", "HEAD"], text=True).strip()
        bundle = cls.offline / "history.bundle"
        subprocess.run([*git, "bundle", "create", str(bundle), "--all"], check=True)
        (cls.offline / "records.jsonl").write_bytes(b"")
        report = cls.offline / "report.json"
        report.write_text(
            json.dumps(
                dict(
                    source="org/project",
                    revision=cls.head,
                    counts={},
                    records_sha256=hashlib.sha256(b"").hexdigest(),
                    historical_policy="record_only",
                )
            ),
            encoding="utf-8",
        )
        cls.database = cls.offline / "native.db"
        cls.scope = ("tenant", "project")
        receipt = import_inventory(
            report,
            cls.database,
            "tenant",
            "actor",
            artifacts={"github:org/project/history.bundle": (bundle, digest(bundle))},
        )
        publish_import(cls.database, *cls.scope, "actor", receipt["module"], receipt["revision"])
        cls.revision = receipt["revision"]
        cls.bundle_digest = digest(bundle)
        cls.kit = cls.offline / "portable"
        cls.expected = prepare(cls.database, *cls.scope, cls.revision, cls.kit)

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.target = Path(temp.name)
        self.db = self.target / "relocated.db"
        shutil.copyfile(self.database, self.db)
        self.received = self.target / "received"
        shutil.copytree(self.kit, self.received)
        self.cache = self.target / "cache"
        self.args = (self.db, *self.scope, self.revision)

    def install(self, *, expected=None):
        return adopt(
            *self.args, self.received, expected_manifest_sha256=expected or self.expected, cache_dir=self.cache
        )

    def assert_no_partial_cache(self):
        for pattern in ("archive.git", "*.pack", "*.idx", "*.bundle"):
            self.assertEqual(list(self.cache.rglob(pattern)), [], pattern)

    def test_portable_index_relocation_and_reuse(self):
        self.assertEqual({path.name for path in self.received.iterdir()}, {"index.idx", "manifest.json"})
        manifest = self.received / "manifest.json"
        self.assertEqual(digest(manifest), self.expected)
        metadata = json.loads(manifest.read_bytes())
        self.assertEqual(metadata["bundle_sha256"], self.bundle_digest)
        self.assertEqual(metadata["index_sha256"], digest(self.received / "index.idx"))
        self.assertEqual(metadata["refs"]["refs/tags/historical"], self.first)
        self.assertEqual(metadata["refs"]["HEAD"], self.head)
        with patch("history_records.export_binary", side_effect=AssertionError("target exported a bundle")):
            result = self.install()
            self.assertFalse(result["reused"])
            mirror = Path(result["mirror"])
            self.assertTrue(mirror.is_relative_to(self.cache))
            packs = list(self.cache.rglob("*.pack"))
            self.assertEqual(len(packs), 1)
            self.assertEqual(digest(packs[0]), metadata["pack_sha256"])
            self.assertEqual(list(self.cache.rglob("*.bundle")), [])
            pack_before = packs[0].stat()
            self.assertTrue(self.install()["reused"])
            self.assertEqual(list(self.cache.rglob("*.pack")), packs)
            self.assertEqual(packs[0].stat().st_mtime_ns, pack_before.st_mtime_ns)
            commits = list_commits(*self.args, cache_dir=self.cache)["items"]
            self.assertEqual([item["oid"] for item in commits], [self.head, self.first])
            file = read_file(*self.args, self.first, "readme.txt", cache_dir=self.cache)
            self.assertEqual(file["text"], "archived file\n")
            with self.assertRaises(LookupError):
                list_commits(self.db, "other", "project", self.revision, cache_dir=self.cache)

    def test_wrong_tenant_and_project_do_not_publish_cache(self):
        for tenant, project in (("other", "project"), ("tenant", "other")):
            with self.subTest(tenant=tenant, project=project):
                with self.assertRaises((LookupError, ValueError)):
                    adopt(
                        self.db,
                        tenant,
                        project,
                        self.revision,
                        self.received,
                        expected_manifest_sha256=self.expected,
                        cache_dir=self.cache,
                    )
                self.assert_no_partial_cache()

    def test_target_rejects_wrong_source_even_with_matching_manifest_digest(self):
        manifest = self.received / "manifest.json"
        metadata = json.loads(manifest.read_bytes())
        metadata["source"] = "other/project"
        manifest.write_text(json.dumps(metadata), encoding="utf-8")
        with self.assertRaises(ValueError):
            self.install(expected=digest(manifest))
        self.assert_no_partial_cache()

    def test_physical_database_digest_binds_the_relocated_file(self):
        with self.assertRaises(ValueError):
            adopt(
                *self.args,
                self.received,
                expected_manifest_sha256=self.expected,
                expected_db_sha256="0" * 64,
                cache_dir=self.cache,
            )
        self.assert_no_partial_cache()
        expected = digest(self.db)
        result = adopt(
            *self.args,
            self.received,
            expected_manifest_sha256=self.expected,
            expected_db_sha256=expected,
            cache_dir=self.cache,
        )
        self.assertEqual(result["database_sha256"], expected)
        self.assertEqual(Path(result["database"]), self.db.resolve())

    def test_partial_or_damaged_transfer_allows_cold_rebuild(self):
        index = self.received / "index.idx"
        original = index.read_bytes()
        index.chmod(0o600)
        index.unlink()
        with self.assertRaises((OSError, ValueError)):
            self.install()
        self.assert_no_partial_cache()
        index.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        with self.assertRaises(ValueError):
            self.install()
        self.assert_no_partial_cache()
        with self.assertRaises(ValueError):
            self.install(expected="0" * 64)
        self.assert_no_partial_cache()
        page = list_commits(*self.args, cache_dir=self.cache)
        self.assertEqual(page["items"][0]["oid"], self.head)
        file = read_file(*self.args, self.first, "readme.txt", cache_dir=self.cache)
        self.assertEqual(file["text"], "archived file\n")


if __name__ == "__main__":
    unittest.main()
