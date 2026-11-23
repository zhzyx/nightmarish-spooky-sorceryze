"""Repository acceptance: exact refs, independent authority, bounded real objects."""

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from native_repository import MODULE, NativeRepository, RepositoryForbidden, manifest_paths
from native_store import Conflict, NativeStore, NativeStoreError

ISSUE = "iss_" + "a" * 32


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = NativeStore(Path(self.tmp.name) / "native.db")
        self.roles = {"admin": "admin", "author": "editor", "reviewer": "editor", "viewer": "viewer"}

        def authorize(t, a, op):
            role = self.roles.get(a)
            return (
                t == "org"
                and role is not None
                and (op == "read" or role == "admin" or (op != "admin" and role == "editor"))
            )

        self.repo = NativeRepository(self.store, authorize)
        self.repo.bootstrap("org", "admin", "gonggong", "bootstrap")
        self.repo.create_branch("org", "author", "gonggong", "branch", "task", None)
        self.serial = 0

    def commit(self, value=b"hello", expected=None, branch="task"):
        self.serial += 1
        digest = hashlib.sha256(value).hexdigest()
        self.repo.put_object("org", "author", "gonggong", digest, value)
        return self.repo.commit(
            "org", "author", "gonggong", f"commit-{self.serial}", branch, expected, {"src/file": digest}, "change"
        )

    def candidate(self, revision, expected=None):
        self.serial += 1
        return self.repo.create_candidate(
            "org", "author", "gonggong", f"candidate-{self.serial}", "task", "main", revision, expected, ISSUE
        )

    def checked(self):
        commit = self.commit()
        candidate = self.candidate(commit["revision"])
        check = self.repo.run_checks("org", "author", "gonggong", candidate["id"], "checks")
        self.assertEqual("checked", check["state"])
        review = self.repo.review(
            "org", "reviewer", "gonggong", candidate["id"], "review", "Read immutable diff and actual check logs"
        )
        return candidate, review

    def test_complete_replay_restart_and_protected_main(self):
        candidate, review = self.checked()
        args = ("org", "author", "gonggong", candidate["id"], "merge", review["id"])
        result = self.repo.merge(*args)
        self.assertEqual(result, self.repo.merge(*args))
        restarted = NativeRepository(NativeStore(self.store.database), self.repo.authorize)
        self.assertEqual(result, restarted.merge(*args))
        self.assertEqual(candidate["revision"], restarted.branch("org", "viewer", "gonggong", "main")["revision"])
        self.assertIsNone(self.store.head("org", MODULE))
        for operation in (
            lambda: self.repo.commit("org", "admin", "gonggong", "direct", "main", candidate["revision"], {}, "bypass"),
            lambda: self.repo.create_branch("org", "admin", "gonggong", "direct2", "main", None),
        ):
            with self.assertRaises(RepositoryForbidden):
                operation()

    def test_independent_review_required_and_revocation(self):
        commit = self.commit()
        candidate = self.candidate(commit["revision"])
        with self.assertRaises(NativeStoreError):
            self.repo.review("org", "reviewer", "gonggong", candidate["id"], "early", "review")
        self.repo.run_checks("org", "author", "gonggong", candidate["id"], "checks")
        with self.assertRaises(NativeStoreError):
            self.repo.review("org", "author", "gonggong", candidate["id"], "self", "self review")
        review = self.repo.review("org", "reviewer", "gonggong", candidate["id"], "independent", "review")
        self.roles["reviewer"] = "viewer"
        with self.assertRaises(NativeStoreError):
            self.repo.merge("org", "admin", "gonggong", candidate["id"], "merge", review["id"])
        self.assertIsNone(self.repo.branch("org", "admin", "gonggong", "main")["revision"])

    def test_source_drift_fails_before_main_advances(self):
        candidate, review = self.checked()
        self.commit(b"later", candidate["revision"])
        with self.assertRaises(Conflict):
            self.repo.merge("org", "author", "gonggong", candidate["id"], "merge", review["id"])
        self.assertIsNone(self.repo.branch("org", "admin", "gonggong", "main")["revision"])

    def test_exact_review_target_cas_expiry_and_corrupt_inputs(self):
        candidate, review = self.checked()
        self.repo.create_branch("org", "author", "gonggong", "other-branch", "other", None)
        other = self.commit(b"another", branch="other")
        second = self.repo.create_candidate(
            "org", "author", "gonggong", "other-candidate", "other", "main", other["revision"], None, ISSUE
        )
        self.repo.run_checks("org", "author", "gonggong", second["id"], "other-checks")
        second_review = self.repo.review(
            "org", "reviewer", "gonggong", second["id"], "other-review", "Read another exact candidate"
        )
        with self.assertRaises(NativeStoreError):
            self.repo.merge("org", "author", "gonggong", second["id"], "wrong-review", review["id"])
        self.repo.merge("org", "author", "gonggong", candidate["id"], "first", review["id"])
        with self.assertRaises(Conflict):
            self.repo.merge("org", "author", "gonggong", second["id"], "stale-target", second_review["id"])
        self.assertEqual(candidate["revision"], self.repo.branch("org", "admin", "gonggong", "main")["revision"])

    def test_expired_check_and_corruption_cannot_publish(self):
        candidate, review = self.checked()
        now = self.repo.cache._time()
        self.repo.cache.clock = lambda: now + 86401
        with self.assertRaises(NativeStoreError):
            self.repo.merge("org", "author", "gonggong", candidate["id"], "expired", review["id"])
        self.repo.cache.clock = lambda: now
        with self.store._connection(write=True) as db:
            db.execute("UPDATE native_blobs SET content=?", (b"bad",))
        with self.assertRaises(NativeStoreError):
            self.repo.merge("org", "author", "gonggong", candidate["id"], "corrupt", review["id"])
        self.assertIsNone(self.repo.branch("org", "admin", "gonggong", "main")["revision"])

    def test_large_translation_object_and_100000_file_limit(self):
        value = b"x" * 15920543
        digest = hashlib.sha256(value).hexdigest()
        self.repo.put_object("org", "author", "gonggong", digest, value)
        self.assertEqual(value, self.repo.object("org", "viewer", "gonggong", digest))
        manifest = {f"files/{index}.txt": digest for index in range(100000)}
        result = self.repo.commit(
            "org", "author", "gonggong", "max-files", "task", None, manifest, "maximum file count"
        )
        self.assertEqual(100000, len(self.repo.revision("org", "viewer", "gonggong", result["revision"])["objects"]))
        manifest["overflow"] = digest
        with self.assertRaises(NativeStoreError):
            self.repo.commit("org", "author", "gonggong", "overflow", "task", result["revision"], manifest, "too many")

    def test_full_manifest_idempotency_and_concurrent_cas(self):
        digest = hashlib.sha256(b"shared").hexdigest()
        self.repo.put_object("org", "author", "gonggong", digest, b"shared")
        manifest = {f"src/{index:05d}.txt": digest for index in range(32321)}
        args = ("org", "author", "gonggong", "full", "task", None, manifest, "full engine manifest")
        result = self.repo.commit(*args)
        self.assertEqual(result, self.repo.commit(*args))
        self.assertEqual(32321, len(self.repo.revision("org", "viewer", "gonggong", result["revision"])["objects"]))
        with self.assertRaises(Conflict):
            self.repo.commit(*args[:-1], "different")

        def advance(index):
            try:
                self.repo.commit(
                    "org", "author", "gonggong", f"race-{index}", "task", result["revision"], manifest, str(index)
                )
                return "ok"
            except Conflict:
                return "conflict"

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(["conflict", "ok"], sorted(pool.map(advance, range(2))))

    def test_corruption_tenant_isolation_and_path_rejection(self):
        self.commit()
        digest = hashlib.sha256(b"hello").hexdigest()
        with self.assertRaises(RepositoryForbidden):
            self.repo.object("other", "admin", "gonggong", digest)
        with self.store._connection(write=True) as db:
            db.execute("UPDATE native_blobs SET content=?", (b"broken",))
        with self.assertRaises(NativeStoreError):
            self.repo.put_object("org", "author", "gonggong", digest, b"hello")
        with self.assertRaises(NativeStoreError):
            self.repo.object("org", "admin", "gonggong", digest)
        for path in ("../x", ".git/config", "a/../b", "C:/x", "CON.txt", "foo.", "lpt" + chr(0xB9)):
            with self.subTest(path=path), self.assertRaises(NativeStoreError):
                manifest_paths({path: digest})
        for mapping in ({"a": digest, "A": digest}, {"a": digest, "a/b": digest}):
            with self.assertRaises(NativeStoreError):
                manifest_paths(mapping)

    def test_installed_failed_semantic_check_blocks_review(self):
        repo = NativeRepository(
            self.store, self.repo.authorize, {"semantic": lambda *args: (False, b"actual test exit 1")}
        )
        repo.bootstrap("org", "admin", "gonggong", "policy-v2")
        candidate = self.candidate(self.commit()["revision"])
        result = repo.run_checks("org", "author", "gonggong", candidate["id"], "failed")
        self.assertEqual("failed", result["state"])
        with self.assertRaises(NativeStoreError):
            repo.review("org", "reviewer", "gonggong", candidate["id"], "reject", "review")

    def test_real_process_empty_path_and_no_git(self):
        script = """import hashlib, pathlib
from native_store import NativeStore
from native_repository import NativeRepository
assert not pathlib.Path('.git').exists()
s=NativeStore(pathlib.Path.cwd()/'isolated.db')
r=NativeRepository(s,lambda *a:True)
r.bootstrap('org','admin','gonggong','init')
r.create_branch('org','author','gonggong','branch','task',None)
b=b'ordinary directory, no project.godot'; d=hashlib.sha256(b).hexdigest()
r.put_object('org','author','gonggong',d,b)
c=r.commit('org','author','gonggong','commit','task',None,{'README':d},'first')
k=r.create_candidate('org','author','gonggong','candidate','task','main',c['revision'],None,'iss_'+'a'*32)
r.run_checks('org','author','gonggong',k['id'],'checks')
v=r.review('org','reviewer','gonggong',k['id'],'review','independent exact review')
result=r.merge('org','author','gonggong',k['id'],'merge',v['id'])
assert r.branch('org','author','gonggong','main')['revision']==c['revision']
print(result['state'])
"""
        env = {**os.environ, "PATH": "", "PYTHONPATH": str(Path(__file__).parent)}
        result = subprocess.run(
            [sys.executable, "-c", script], env=env, cwd=self.tmp.name, capture_output=True, text=True
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("merged", result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
