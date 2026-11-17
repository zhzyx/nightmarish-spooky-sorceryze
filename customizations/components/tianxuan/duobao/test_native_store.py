"""Behavioral invariants for Git-independent module collaboration."""

import base64
import contextlib
import io
import json
import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from native_cli import main
from native_store import Conflict, NativeStore, NativeStoreError


def change(module, edits, base=None, reads=(), **extra):
    return {"module": module, "base": base, "reads": None if reads is None else list(reads), "edits": edits, **extra}


class NativeStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="duobao-native-")
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "state.sqlite"
        self.store = NativeStore(self.database)

    def put(self, key, *changes, tenant="org", actor="worker"):
        return self.store.submit(tenant, actor, key, list(changes))["revisions"]

    def test_no_git_network_or_process_is_required(self):
        with (
            patch.dict(os.environ, {"PATH": ""}),
            patch("subprocess.Popen", side_effect=AssertionError("process")),
            patch("socket.socket", side_effect=AssertionError("network")),
        ):
            first = self.put("one", change("a", {"source": b"one\x00"}))["a"]
            second = self.put("two", change("a", {"source": b"two"}, first))["a"]
            self.assertEqual(self.store.read("org", "a", first, "source"), b"one\x00")
            self.assertEqual(self.store.read("org", "a", second, "source"), b"two")
            self.assertEqual(self.store.compose("org", {"a": second})["state"], "candidate")

    def test_unrelated_module_drift_never_invalidates_fixed_work(self):
        first = self.put("seed", change("a", {"a": b"0"}), change("b", {"b": b"0"}))
        for number in range(30):
            b = self.store.head("org", "b")
            self.put(f"background-{number}", change("b", {"b": str(number).encode()}, b))
        result = self.put("deliver-a", change("a", {"a": b"ready"}, first["a"]))
        self.assertEqual(self.store.read("org", "a", result["a"], "a"), b"ready")

    def test_same_module_disjoint_old_base_changes_preserve_both(self):
        base = self.put("seed", change("a", {"left": b"0", "right": b"0"}))["a"]
        self.put("left", change("a", {"left": b"1"}, base))
        result = self.put("right", change("a", {"right": b"2"}, base))["a"]
        self.assertEqual(self.store.read("org", "a", result, "left"), b"1")
        self.assertEqual(self.store.read("org", "a", result, "right"), b"2")

    def test_changed_read_and_unknown_read_reject_with_unchanged_state(self):
        base = self.put("seed", change("a", {"api": b"old"}))["a"]
        latest = self.put("api", change("a", {"api": b"new"}, base))["a"]
        for index, reads in enumerate((["api"], None)):
            with self.assertRaises(Conflict):
                self.put(f"stale-{index}", change("a", {"consumer": b"invalid"}, base, reads))
        self.assertEqual(self.store.head("org", "a"), latest)

    def test_missing_read_detects_concurrent_creation(self):
        base = self.put("seed", change("a", {}))["a"]
        self.put("create", change("a", {"optional-config": b"now exists"}, base))
        with self.assertRaises(Conflict):
            self.put("stale", change("a", {"result": b"assumed missing"}, base, ["optional-config"]))

    def test_competing_writers_one_wins_without_silent_overwrite(self):
        base = self.put("seed", change("a", {"item": b"old"}))["a"]

        def write(number):
            try:
                self.put(f"writer-{number}", change("a", {"item": str(number).encode()}, base))
                return "received"
            except Conflict:
                return "conflict"

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(write, range(8)))
        self.assertEqual(results.count("received"), 1)
        self.assertEqual(results.count("conflict"), 7)

    def test_250_independent_connections_no_global_revision_retries(self):
        base = self.put("seed", change("shared", {}))["shared"]

        def write(number):
            return self.put(f"task-{number}", change("shared", {f"object-{number}": str(number).encode()}, base))

        with ThreadPoolExecutor(max_workers=16) as executor:
            results = list(executor.map(write, range(250)))
        self.assertEqual(len(results), 250)
        final = self.store.revision("org", "shared", self.store.head("org", "shared"))
        self.assertEqual(len(final["objects"]), 250)

    def test_idempotency_after_restart_and_conflicting_reuse(self):
        data = [change("a", {"x": b"content"})]
        original = self.store.submit("org", "worker", "request", data)
        reopened = NativeStore(self.database)
        self.assertEqual(reopened.submit("org", "worker", "request", data), original)
        with self.assertRaises(Conflict):
            reopened.submit("org", "worker", "request", [change("a", {"x": b"other"})])
        with contextlib.closing(sqlite3.connect(self.database)) as db, db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM native_revisions").fetchone()[0], 1)

    def test_same_request_concurrency_returns_one_durable_result(self):
        def replay(_):
            return self.store.submit("org", "worker", "same", [change("a", {"x": b"x"})])

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(replay, range(24)))
        self.assertTrue(all(result == results[0] for result in results))
        with contextlib.closing(sqlite3.connect(self.database)) as db, db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM native_receipts").fetchone()[0], 1)

    def test_batch_atomicity_on_late_missing_dependency(self):
        with self.assertRaises(NativeStoreError):
            self.put("failed", change("a", {"a": b"a"}), change("b", {"b": b"b"}, dependencies={"missing": "0" * 64}))
        with contextlib.closing(sqlite3.connect(self.database)) as db, db:
            for table in ("native_heads", "native_blobs", "native_revisions", "native_receipts"):
                self.assertEqual(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)

    def test_transaction_storage_failure_rolls_back_and_retry_succeeds(self):
        with contextlib.closing(sqlite3.connect(self.database)) as db, db:
            db.execute(
                "CREATE TRIGGER fail_receipt BEFORE INSERT ON native_receipts BEGIN SELECT RAISE(ABORT,'injected'); END"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.put("request", change("a", {"x": b"x"}))
        self.assertIsNone(self.store.head("org", "a"))
        with contextlib.closing(sqlite3.connect(self.database)) as db, db:
            db.execute("DROP TRIGGER fail_receipt")
        self.assertIn("a", self.put("request", change("a", {"x": b"x"})))

    def test_batch_dependencies_and_immutable_composition(self):
        result = self.put(
            "pair", change("app", {"code": b"v1"}, dependencies={"api": "@batch"}), change("api", {"schema": b"v1"})
        )
        old = self.store.compose("org", {"app": result["app"]})
        self.assertEqual(old["modules"], result)
        newer = self.put("upgrade", change("api", {"schema": b"v2"}, result["api"]))["api"]
        self.assertEqual(self.store.compose("org", {"app": result["app"]}), old)
        with self.assertRaises(Conflict):
            self.store.compose("org", {"app": result["app"], "api": newer})

    def test_batch_cycle_and_missing_batch_member_reject_atomically(self):
        for deps in ({"b": "@batch"}, {"missing": "@batch"}):
            with self.assertRaises(NativeStoreError):
                self.put("cycle", change("a", {}, dependencies=deps), change("b", {}, dependencies={"a": "@batch"}))
            self.assertIsNone(self.store.head("org", "a"))

    def test_tenant_and_module_revision_isolation(self):
        original = self.put("seed", change("a", {"private": b"value"}))["a"]
        for tenant, module in (("other", "a"), ("org", "other")):
            with self.assertRaises(NativeStoreError):
                self.store.read(tenant, module, original, "private")
        with self.assertRaises(NativeStoreError):
            self.put("cross", change("consumer", {}, dependencies={"a": original}), tenant="other")

    def test_delete_prefix_conflict_and_invalid_input(self):
        base = self.put("seed", change("a", {"directory/file": b"x"}))["a"]
        with self.assertRaises(Conflict):
            self.put("prefix", change("a", {"directory": b"bad"}, base))
        deleted = self.put("delete", change("a", {"directory/file": None}, base))["a"]
        with self.assertRaises(NativeStoreError):
            self.store.read("org", "a", deleted, "directory/file")
        for path in ("../outside", "C:/host", "/absolute", "a\\b", "a//b"):
            with self.assertRaises(NativeStoreError):
                self.put("invalid", change("new", {path: b"x"}))

    def test_corruption_is_not_returned_as_valid_content(self):
        revision = self.put("seed", change("a", {"x": b"original"}))["a"]
        with contextlib.closing(sqlite3.connect(self.database)) as db, db:
            db.execute("UPDATE native_blobs SET content=?", (b"tampered",))
        with self.assertRaisesRegex(NativeStoreError, "integrity"):
            self.store.read("org", "a", revision, "x")

    def test_cli_actual_json_boundary_and_invalid_base64(self):
        source = [{"module": "cli", "base": None, "reads": [], "edits": {"x": base64.b64encode(b"hello").decode()}}]
        args = ["--db", str(self.database), "--tenant", "org", "submit", "--actor", "worker", "--request-key", "cli"]
        output = io.StringIO()
        with patch("sys.stdin", io.StringIO(json.dumps(source))), contextlib.redirect_stdout(output):
            self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(output.getvalue())["data"]["state"], "received")
        source[0]["edits"]["x"] = "!invalid!"
        with patch("sys.stdin", io.StringIO(json.dumps(source))), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(args), 2)

    def test_corrupt_dedup_hit_rejects_entire_batch_without_receipt(self):
        self.put("seed", change("a", {"x": b"original"}))
        with contextlib.closing(sqlite3.connect(self.database)) as db, db:
            db.execute("UPDATE native_blobs SET content=?", (b"tampered",))
        with self.assertRaisesRegex(NativeStoreError, "integrity"):
            self.put("corrupt", change("b", {"new": b"new", "x": b"original"}), change("c", {}))
        self.assertIsNone(self.store.head("org", "b"))
        self.assertIsNone(self.store.head("org", "c"))
        with contextlib.closing(sqlite3.connect(self.database)) as db, db:
            for table in ("native_blobs", "native_heads", "native_revisions", "native_receipts"):
                self.assertEqual(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 1)
            db.execute("UPDATE native_blobs SET content=?", (b"original",))
        self.assertIn("b", self.put("corrupt", change("b", {"new": b"new", "x": b"original"}), change("c", {})))


if __name__ == "__main__":
    unittest.main()
