"""Evidence reuse must follow actual scoped inputs, never a moving global head."""

from __future__ import annotations

import contextlib
import copy
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from native_evidence import EvidenceCache
from native_store import Conflict, NativeStore, NativeStoreError


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="duobao-evidence-")
        self.addCleanup(self.temporary.cleanup)
        self.database = Path(self.temporary.name) / "store.sqlite"
        self.store = NativeStore(self.database)
        self.clock = 100.0
        self.allowed = {"validator"}
        self.policies = {
            "scoped": {"version": "v1", "reads": {"shared": ["a", "missing"]}, "max_age_seconds": 60},
            "module": {"version": "v1", "reads": {"shared": None}, "max_age_seconds": 60},
            "unknown": {"version": "v1", "reads": None, "max_age_seconds": 60},
        }
        self.cache = self.new_cache()
        self.serial = 0
        self.base = self.put("shared", {"a": b"first", "b": b"second"})
        self.candidate = self.store.compose("org", {"shared": self.base})["id"]
        self.context = {"toolchain": "a" * 64, "environment": "b" * 64, "parameters": {"mode": "test"}}

    def new_cache(self, policies=None):
        return EvidenceCache(
            self.store,
            self.policies if policies is None else policies,
            lambda tenant, actor, check, operation: tenant == "org" and actor in self.allowed,
            clock=lambda: self.clock,
        )

    def put(self, module, edits, base=None, tenant="org", dependencies=None):
        self.serial += 1
        change = {"module": module, "base": base, "reads": [], "edits": edits}
        if dependencies is not None:
            change["dependencies"] = dependencies
        return self.store.submit(tenant, "producer", f"edit-{self.serial}", [change])["revisions"][module]

    def record(self, key="run", candidate=None, check="scoped", outcome="passed", actor="validator"):
        return self.cache.record(
            "org",
            actor,
            key,
            candidate or self.candidate,
            check,
            **self.context,
            outcome=outcome,
            log=b"real runner log",
        )

    def lookup(self, candidate=None, check="scoped", context=None):
        return self.cache.lookup("org", candidate or self.candidate, check, **(context or self.context))

    def compose(self, revision, **extra):
        return self.store.compose("org", {"shared": revision, **extra})["id"]

    def test_disjoint_object_and_unrelated_module_reuse_original_fact(self):
        original = self.record()
        changed = self.put("shared", {"b": b"updated"}, self.base)
        noise = self.put("noise", {"anything": b"unrelated"})
        next_candidate = self.compose(changed, noise=noise)
        self.assertNotEqual(next_candidate, self.candidate)
        hit = self.lookup(next_candidate)
        self.assertEqual(hit["evidence"]["id"], original["id"])
        self.assertEqual(hit["evidence"]["candidate"], self.candidate)
        self.assertEqual(hit["requested_candidate"], next_candidate)
        self.assertEqual(hit["state"], "cached_check_fact")

    def test_read_change_delete_and_missing_creation_invalidate(self):
        self.record()
        changed = self.put("shared", {"a": b"different"}, self.base)
        self.assertIsNone(self.lookup(self.compose(changed)))
        deleted = self.put("shared", {"a": None}, changed)
        self.assertIsNone(self.lookup(self.compose(deleted)))
        restored = self.put("shared", {"a": b"first", "missing": b"now-present"}, deleted)
        self.assertIsNone(self.lookup(self.compose(restored)))

    def test_unknown_and_whole_module_scopes_are_conservative(self):
        for check in ("module", "unknown"):
            self.record(key=check, check=check)
        changed = self.put("shared", {"b": b"updated"}, self.base)
        for check in ("module", "unknown"):
            self.assertIsNone(self.lookup(self.compose(changed), check=check))

    def test_exact_dependency_change_invalidates(self):
        dep = self.put("dep", {"schema": b"v1"})
        linked = self.put("shared", {}, self.base, dependencies={"dep": dep})
        candidate = self.compose(linked)
        self.record(candidate=candidate)
        newer_dep = self.put("dep", {"schema": b"v2"}, dep)
        newer = self.put("shared", {}, linked, dependencies={"dep": newer_dep})
        self.assertIsNone(self.lookup(self.compose(newer)))
        self.assertIsNotNone(self.lookup(candidate))

    def test_rule_toolchain_environment_and_parameters_invalidate(self):
        self.record()
        for name, value in (("toolchain", "c" * 64), ("environment", "d" * 64), ("parameters", {"mode": "other"})):
            context = {**self.context, name: value}
            self.assertIsNone(self.lookup(context=context))
        updated = copy.deepcopy(self.policies)
        updated["scoped"]["version"] = "v2"
        self.assertIsNone(self.new_cache(updated).lookup("org", self.candidate, "scoped", **self.context))

    def test_dependency_content_corruption_rejects_cached_fact(self):
        dep = self.put("dep", {"schema": b"dependency"})
        linked = self.put("shared", {}, self.base, dependencies={"dep": dep})
        candidate = self.compose(linked)
        self.record(candidate=candidate)
        with contextlib.closing(sqlite3.connect(self.database)) as db, db:
            db.execute("UPDATE native_blobs SET content=? WHERE content=?", (b"corrupt", b"dependency"))
        with self.assertRaisesRegex(NativeStoreError, "dependency integrity"):
            self.lookup(candidate)

    def test_corrupt_request_reference_does_not_replay_another_run(self):
        self.record("one")
        other = self.record("two", outcome="failed")
        with contextlib.closing(sqlite3.connect(self.database)) as db, db:
            db.execute("UPDATE native_check_requests SET evidence_id=? WHERE request_key='one'", (other["id"],))
        with self.assertRaisesRegex(NativeStoreError, "receipt integrity"):
            self.record("one")

    def test_host_scope_is_copied_and_caller_cannot_install_unknown_check(self):
        original = self.record()
        self.policies["scoped"]["reads"] = {"shared": ["b"]}
        self.assertEqual(self.lookup()["evidence"]["id"], original["id"])
        with self.assertRaises(NativeStoreError):
            self.record(check="uninstalled")
        with self.assertRaises(NativeStoreError):
            self.record(actor="producer")

    def test_failed_unknown_and_revoked_latest_fact_never_fall_back_to_old_pass(self):
        self.record()
        self.record("failed", outcome="failed")
        self.assertIsNone(self.lookup())
        self.record("unknown", outcome="unknown")
        self.assertIsNone(self.lookup())
        latest = self.record("fresh")
        self.cache.revoke("org", "validator", latest["id"], "invalid test fixture")
        self.cache.revoke("org", "validator", latest["id"], "invalid test fixture")
        self.assertIsNone(self.lookup())
        with self.assertRaises(Conflict):
            self.cache.revoke("org", "validator", latest["id"], "different reason")

    def test_expiry_future_clock_and_runner_revocation_are_checked_on_lookup(self):
        self.record()
        self.clock = 159.9
        self.assertIsNotNone(self.lookup())
        self.clock = 160
        self.assertIsNone(self.lookup())
        self.clock = 99
        self.assertIsNone(self.lookup())
        self.clock = 100
        self.allowed.clear()
        self.assertIsNone(self.lookup())

    def test_durable_replay_and_conflicting_reuse(self):
        original = self.record()
        self.clock = 120
        self.cache = self.new_cache()
        self.assertEqual(self.record(), original)
        with self.assertRaises(Conflict):
            self.record(outcome="failed")

    def test_same_request_parallel_records_have_one_identity(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.record(), range(24)))
        self.assertEqual(len({item["id"] for item in results}), 1)
        with contextlib.closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM native_check_evidence").fetchone()[0], 1)

    def test_storage_failure_rolls_back_evidence_and_retry_succeeds(self):
        with contextlib.closing(sqlite3.connect(self.database)) as db, db:
            db.execute(
                "CREATE TRIGGER reject_receipt BEFORE INSERT ON native_check_requests BEGIN SELECT RAISE(ABORT,'test'); END"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.record()
        with contextlib.closing(sqlite3.connect(self.database)) as db, db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM native_check_evidence").fetchone()[0], 0)
            db.execute("DROP TRIGGER reject_receipt")
        self.assertEqual(self.record()["outcome"], "passed")

    def test_tenants_do_not_share_cached_evidence(self):
        self.record()
        revision = self.put("shared", {"a": b"first", "b": b"second"}, tenant="other")
        candidate = self.store.compose("other", {"shared": revision})["id"]
        self.assertEqual(candidate, self.candidate)
        self.assertIsNone(self.cache.lookup("other", candidate, "scoped", **self.context))

    def test_input_and_evidence_corruption_never_return_pass(self):
        original = self.record()
        with contextlib.closing(sqlite3.connect(self.database)) as db, db:
            db.execute("UPDATE native_check_evidence SET log=?", (b"corrupt",))
        with self.assertRaisesRegex(NativeStoreError, "integrity"):
            self.lookup()
        with contextlib.closing(sqlite3.connect(self.database)) as db, db:
            db.execute("UPDATE native_check_evidence SET log=?", (b"real runner log",))
            db.execute("UPDATE native_blobs SET content=?", (b"corrupt",))
        with self.assertRaisesRegex(NativeStoreError, "integrity"):
            self.lookup()
        self.assertEqual(original["outcome"], "passed")

    def test_invalid_policy_log_context_and_revoker_rejected(self):
        with self.assertRaises(NativeStoreError):
            self.new_cache({"invalid": {"version": "v1", "reads": {}, "max_age_seconds": 60}})
        with self.assertRaises(NativeStoreError):
            self.new_cache({"invalid": {"version": "v1", "reads": None, "max_age_seconds": True}})
        with self.assertRaises(NativeStoreError):
            self.cache.binding("org", self.candidate, "scoped", **{**self.context, "environment": "unknown"})
        original = self.record()
        with self.assertRaises(NativeStoreError):
            self.cache.revoke("org", "producer", original["id"], "unauthorized")
        self.clock = float("nan")
        with self.assertRaises(NativeStoreError):
            self.record("bad-clock")


if __name__ == "__main__":
    unittest.main()
