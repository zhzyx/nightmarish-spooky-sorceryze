"""Transactional release contract, including deterministic races and crash rollback."""

from __future__ import annotations

import copy
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from native_evidence import EvidenceCache
from native_release import NativeRelease
from native_store import Conflict, NativeStore, NativeStoreError


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="duobao-release-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "store.sqlite"
        self.store = NativeStore(self.path)
        self.now = 100.0
        self.checks = {
            "whole": {"version": "v1", "reads": None, "max_age_seconds": 60},
            "partial": {"version": "v1", "reads": {"core": None}, "max_age_seconds": 60},
        }
        self.cache = EvidenceCache(self.store, self.checks, lambda *args: True, clock=lambda: self.now)
        with self.store._connection(write=True) as db:
            db.execute("CREATE TABLE authority (tenant TEXT, actor TEXT, PRIMARY KEY(tenant,actor))")
            db.executemany(
                "INSERT INTO authority VALUES (?,?)",
                [(t, a) for t in ("org", "other") for a in ("admin", "reviewer", "runner", "producer")],
            )
        self.authors = {"producer"}
        self.release = NativeRelease(self.cache, self.authorize, lambda db, t, c: self.authors)
        self.context = dict(toolchain="a" * 64, environment="b" * 64, parameters={"mode": "release"})
        self.policy = dict(checks={"whole": self.context}, review_max_age_seconds=30)
        self.release.configure("org", "admin", "game", self.policy)
        self.serial = 0
        self.candidate = self.candidate_for()
        self.fact = self.record(self.candidate)
        self.review = self.approve(self.candidate, self.fact)

    @staticmethod
    def authorize(db, tenant, actor, scope, action):
        return db.execute("SELECT 1 FROM authority WHERE tenant=? AND actor=?", (tenant, actor)).fetchone() is not None

    def candidate_for(self, tenant="org"):
        self.serial += 1
        changes = [
            dict(
                module="core", base=self.store.head(tenant, "core"), reads=[], edits={"code": str(self.serial).encode()}
            ),
            dict(
                module="app",
                base=self.store.head(tenant, "app"),
                reads=[],
                edits={"entry": b"app"},
                dependencies={"core": "@batch"},
            ),
        ]
        revisions = self.store.submit(tenant, "producer", f"put-{self.serial}", changes)["revisions"]
        return self.store.compose(tenant, {"app": revisions["app"]})["id"]

    def record(self, candidate, outcome="passed", tenant="org"):
        self.serial += 1
        return self.cache.record(
            tenant,
            "runner",
            f"run-{self.serial}",
            candidate,
            "whole",
            **self.context,
            outcome=outcome,
            log=b"runner transcript",
        )["id"]

    def approve(self, candidate, fact, actor="reviewer", key=None):
        self.serial += 1
        return self.release.approve(
            "org",
            actor,
            key or f"review-{self.serial}",
            "game",
            candidate,
            {"whole": fact},
            "Read precise composition and all required results",
        )["id"]

    def publish(self, key="select", channel="stable", review=None, expected=None):
        return self.release.publish("org", "admin", key, "game", channel, review or self.review, expected)

    def selected(self, channel="stable"):
        return self.release.selected("org", "admin", "game", channel)

    def test_full_flow_restart_and_rollback(self):
        first = self.publish()
        self.assertEqual(set(first["modules"]), {"app", "core"})
        self.assertEqual(first, self.selected())
        second_candidate = self.candidate_for()
        second_review = self.approve(second_candidate, self.record(second_candidate))
        second = self.publish("second", review=second_review, expected=first["id"])
        rollback = self.publish("rollback", review=self.review, expected=second["id"])
        self.assertEqual(rollback["candidate"], first["candidate"])
        fresh_store = NativeStore(self.path)
        cache = EvidenceCache(fresh_store, self.checks, lambda *a: True, clock=lambda: self.now)
        restarted = NativeRelease(cache, self.authorize, lambda db, t, c: {"producer"})
        self.assertEqual(restarted.selected("org", "admin", "game", "stable"), rollback)
        self.assertEqual(len(restarted.events("org", "admin", "game")), 3)
        self.assertEqual(first["state"], "content_selected")

    def test_release_flow_without_network_process_or_git(self):
        with (
            patch("subprocess.Popen", side_effect=AssertionError("No external process")),
            patch("socket.socket", side_effect=AssertionError("No networking")),
            patch.dict("os.environ", {"PATH": "", "GIT_DIR": "nonexistent"}),
        ):
            candidate = self.candidate_for()
            fact = self.record(candidate)
            review = self.approve(candidate, fact)
            first = self.publish(review=review)
            self.assertEqual(self.selected(), first)
            rolled_back = self.publish("rollback", expected=first["id"])
            self.assertEqual(rolled_back["candidate"], self.candidate)

    def test_identity_source_and_required_policy_rejections(self):
        with self.assertRaises(NativeStoreError):
            self.approve(self.candidate, self.fact, "intruder")
        with self.assertRaises(NativeStoreError):
            self.approve(self.candidate, self.fact, "producer")
        for authors in (None, set()):
            self.authors = authors
            with self.assertRaises(NativeStoreError):
                self.approve(self.candidate, self.fact)
        self.authors = {"producer"}
        with self.assertRaises(NativeStoreError):
            self.release.approve("org", "reviewer", "missing", "game", self.candidate, {}, "reviewed")
        with self.assertRaises(NativeStoreError):
            self.release.configure(
                "org", "admin", "game", dict(checks={"partial": self.context}, review_max_age_seconds=30)
            )
        with self.assertRaises(NativeStoreError):
            self.release.configure(
                "org", "admin", "game", dict(checks={"absent": self.context}, review_max_age_seconds=30)
            )
        with self.assertRaises(NativeStoreError):
            self.release.configure("org", "intruder", "game", self.policy)

    def test_latest_failed_unknown_or_changed_evidence_rejects_prior_review(self):
        for outcome in ("failed", "unknown", "passed"):
            with self.subTest(outcome=outcome):
                self.record(self.candidate, outcome)
                with self.assertRaises(NativeStoreError):
                    self.publish()

    def test_revoked_evidence_rejects_publish_and_current_read(self):
        self.publish()
        self.cache.revoke("org", "runner", self.fact, "invalid runner result")
        with self.assertRaises(NativeStoreError):
            self.selected()
        with self.assertRaises(NativeStoreError):
            self.publish("again", "beta")

    def test_expiry_authority_policy_and_source_rechecked(self):
        for mutation in ("expiry", "reviewer", "runner", "policy", "source"):
            with self.subTest(mutation=mutation):
                if mutation == "expiry":
                    self.now = 130.0
                elif mutation in {"reviewer", "runner"}:
                    with self.store._connection(write=True) as db:
                        db.execute("DELETE FROM authority WHERE tenant='org' AND actor=?", (mutation,))
                elif mutation == "policy":
                    policy = copy.deepcopy(self.policy)
                    policy["review_max_age_seconds"] = 20
                    self.release.configure("org", "admin", "game", policy)
                else:
                    self.authors = {"producer", "another-author"}
                with self.assertRaises(NativeStoreError):
                    self.publish()
                self.now = 100.0
                with self.store._connection(write=True) as db:
                    db.execute("INSERT OR IGNORE INTO authority VALUES ('org','reviewer')")
                    db.execute("INSERT OR IGNORE INTO authority VALUES ('org','runner')")
                self.release.configure("org", "admin", "game", self.policy)

    def test_check_policy_drift_and_evidence_expiry(self):
        self.cache.policies["whole"]["version"] = "v2"
        with self.assertRaises(NativeStoreError):
            self.publish()
        self.cache.policies["whole"]["version"] = "v1"
        self.now = 160
        with self.assertRaises(NativeStoreError):
            self.approve(self.candidate, self.fact)

    def test_idempotent_receipts_events_and_revocation_no_resurrection(self):
        r = self.release.approve(
            "org", "reviewer", "review-retry", "game", self.candidate, {"whole": self.fact}, "reviewed"
        )
        self.assertEqual(
            r,
            self.release.approve(
                "org", "reviewer", "review-retry", "game", self.candidate, {"whole": self.fact}, "reviewed"
            ),
        )
        first = self.publish()
        self.assertEqual(first, self.publish())
        with self.assertRaises(Conflict):
            self.publish(channel="different")
        revoked = self.release.revoke("org", "admin", "revoke", self.review, "withdrawn")
        self.assertEqual(revoked, self.release.revoke("org", "admin", "revoke", self.review, "withdrawn"))
        self.assertEqual(first, self.publish())  # Receipt replay is explicitly historical.
        with self.assertRaises(NativeStoreError):
            self.publish("rollback", expected=first["id"])
        self.assertEqual(len(self.release.events("org", "admin", "game")), 1)

    def test_channels_and_same_channel_competitors(self):
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(self.publish, f"compete-{i}") for i in range(2)]
            results = []
            for future in futures:
                try:
                    results.append(future.result())
                except Conflict:
                    results.append("conflict")
        self.assertEqual(results.count("conflict"), 1)
        self.assertIsNotNone(self.publish("beta", "beta"))
        self.assertEqual(self.selected("beta")["candidate"], self.selected()["candidate"])

    def test_reader_snapshot_does_not_block_unrelated_publication(self):
        first = self.publish()
        entered = threading.Event()
        proceed = threading.Event()
        authorize = self.release.authorize

        def paused_reader(db, tenant, actor, scope, action):
            allowed = authorize(db, tenant, actor, scope, action)
            if action == "read":
                entered.set()
                if not proceed.wait(5):
                    raise RuntimeError("test synchronization timeout")
            return allowed

        self.release.authorize = paused_reader
        with ThreadPoolExecutor(2) as pool:
            reader = pool.submit(self.selected)
            try:
                self.assertTrue(entered.wait(5))
                writer = pool.submit(self.publish, "other", "other")
                self.assertEqual(writer.result(timeout=2)["state"], "content_selected")
            finally:
                proceed.set()
            self.assertEqual(reader.result(timeout=5), first)

    def test_event_cursor_is_bounded_and_product_scoped(self):
        expected = [self.publish(f"p-{i}", f"channel-{i}")["id"] for i in range(3)]
        self.release.configure("org", "admin", "other-product", self.policy)
        self.assertEqual(self.release.events("org", "admin", "other-product"), [])
        cursor = 0
        observed = []
        for _ in range(3):
            page = self.release.events("org", "admin", "game", after=cursor, limit=1)
            self.assertEqual(len(page), 1)
            self.assertGreater(page[0]["sequence"], cursor)
            cursor = page[0]["sequence"]
            observed.append(page[0]["record"]["id"])
        self.assertEqual(observed, expected)
        self.assertEqual(self.release.events("org", "admin", "game", after=cursor), [])
        for bad in (dict(after=-1), dict(after=True), dict(limit=0), dict(limit=1001)):
            with self.assertRaises(NativeStoreError):
                self.release.events("org", "admin", "game", **bad)

    def test_event_product_corruption_rejects_current_selection(self):
        self.publish()
        with self.store._connection(write=True) as db:
            db.execute("UPDATE native_release_events SET product='unrelated'")
        with self.assertRaises(NativeStoreError):
            self.selected()

    def test_revocation_commits_before_blocked_publish(self):
        entered = threading.Event()
        started = threading.Event()
        proceed = threading.Event()

        def runner_authority(tenant, actor, check, operation):
            if operation == "revoke":
                entered.set()
                if not proceed.wait(5):
                    raise RuntimeError("test synchronization timeout")
            return True

        self.cache.authorize = runner_authority
        with ThreadPoolExecutor(2) as pool:
            revoke = pool.submit(self.cache.revoke, "org", "runner", self.fact, "race")
            self.assertTrue(entered.wait(5))  # revoke owns BEGIN IMMEDIATE

            def publish():
                started.set()
                return self.publish()

            future = pool.submit(publish)
            self.assertTrue(started.wait(5))
            proceed.set()
            revoke.result(timeout=5)
            with self.assertRaises(NativeStoreError):
                future.result(timeout=5)
        self.assertIsNone(self.selected())

    def test_review_revocation_before_publish_and_reapproved_rollback(self):
        first = self.publish()
        candidate = self.candidate_for()
        review = self.approve(candidate, self.record(candidate))
        second = self.publish("second", review=review, expected=first["id"])
        self.release.revoke("org", "admin", "revoke-old", self.review, "needs another review")
        with self.assertRaises(NativeStoreError):
            self.publish("rollback-old", expected=second["id"])
        refreshed = self.approve(self.candidate, self.fact)
        restored = self.publish("rollback-fresh", review=refreshed, expected=second["id"])
        self.assertEqual(restored["candidate"], self.candidate)

    def test_unknown_composition_context_and_missing_atomic_event(self):
        with self.assertRaises(NativeStoreError):
            self.approve("f" * 64, self.fact)
        wrong = copy.deepcopy(self.policy)
        wrong["checks"]["whole"]["parameters"] = {"mode": "different"}
        self.release.configure("org", "admin", "game", wrong)
        with self.assertRaises(NativeStoreError):
            self.approve(self.candidate, self.fact)
        self.release.configure("org", "admin", "game", self.policy)
        self.publish()
        with self.store._connection(write=True) as db:
            db.execute("DELETE FROM native_release_events")
        with self.assertRaises(NativeStoreError):
            self.selected()

    def test_publish_before_revocation_has_historical_event_but_invalid_selection(self):
        entered = threading.Event()
        continue_publish = threading.Event()
        original = self.release.contributors

        def blocked(db, tenant, candidate):
            entered.set()
            if not continue_publish.wait(5):
                raise RuntimeError("test synchronization timeout")
            return original(db, tenant, candidate)

        self.release.contributors = blocked
        with ThreadPoolExecutor(2) as pool:
            publish = pool.submit(self.publish)
            self.assertTrue(entered.wait(5))
            revoke = pool.submit(self.cache.revoke, "org", "runner", self.fact, "withdrawn")
            continue_publish.set()
            self.assertEqual(publish.result(timeout=5)["state"], "content_selected")
            revoke.result(timeout=5)
        self.release.contributors = original
        with self.assertRaises(NativeStoreError):
            self.selected()
        self.assertEqual(len(self.release.events("org", "admin", "game")), 1)

    def test_event_failure_rolls_back_pointer_receipt_and_manifest(self):
        with self.store._connection(write=True) as db:
            db.execute(
                "CREATE TRIGGER fail_event BEFORE INSERT ON native_release_events "
                "BEGIN SELECT RAISE(ABORT,'injected event failure'); END"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.publish()
        self.assertIsNone(self.selected())
        with self.store._connection(write=True) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM native_release_records").fetchone()[0], 1)
            db.execute("DROP TRIGGER fail_event")
        self.assertEqual(self.publish()["state"], "content_selected")

    def test_corruption_rejected(self):
        with self.store._connection(write=True) as db:
            db.execute("UPDATE native_check_evidence SET log=? WHERE id=?", (b"tampered", self.fact))
        with self.assertRaises(NativeStoreError):
            self.publish()

    def test_record_and_blob_corruption_rejected_on_consumer_read(self):
        selected = self.publish()
        with self.store._connection(write=True) as db:
            db.execute("UPDATE native_blobs SET content=?", (b"tampered",))
        with self.assertRaises(NativeStoreError):
            self.selected()
        with self.store._connection(write=True) as db:
            db.execute("UPDATE native_release_records SET payload='{}' WHERE id=?", (selected["id"],))
        with self.assertRaises(NativeStoreError):
            self.selected()

    def test_tenant_product_isolation(self):
        self.publish()
        self.assertIsNone(self.release.selected("other", "admin", "game", "stable"))
        self.assertEqual(self.release.events("other", "admin", "game"), [])
        self.release.configure("other", "admin", "game", self.policy)
        with self.assertRaises(NativeStoreError):
            self.release.publish("other", "admin", "select", "game", "stable", self.review, None)
        self.release.configure("org", "admin", "other-product", self.policy)
        with self.assertRaises(NativeStoreError):
            self.release.publish("org", "admin", "select-other", "other-product", "stable", self.review, None)
        other_candidate = self.candidate_for("other")
        fact = self.record(other_candidate, tenant="other")
        review = self.release.approve(
            "other", "reviewer", "review", "game", other_candidate, {"whole": fact}, "reviewed"
        )
        result = self.release.publish("other", "admin", "select", "game", "stable", review["id"], None)
        self.assertEqual(result["candidate"], other_candidate)


if __name__ == "__main__":
    unittest.main()
