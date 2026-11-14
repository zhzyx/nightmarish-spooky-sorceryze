"""Real SQLite concurrency/rollback regression tests; no external services."""

import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from tianxuan_core import StorageError, Tianxuan, TianxuanError, VersionConflict


class DocumentTransactionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = tempfile.TemporaryDirectory(prefix="tianxuan-concurrency-")
        self.addCleanup(self.fixture.cleanup)
        self.path = str(Path(self.fixture.name) / "store.db")
        self.tx = Tianxuan(self.path)
        self.addCleanup(self.tx.db.close)
        self.actor = self.tx.register("test", "owner@example.invalid", "secret")["user_id"]
        self.doc = self.tx.create_doc(self.actor, "original", "base")

    def snapshot(self, tx=None):
        tx = tx or self.tx
        doc = tx.get_doc(self.doc["id"])
        versions = [
            dict(row)
            for row in tx.db.execute(
                "SELECT version, body_md FROM doc_versions WHERE doc_id = ? ORDER BY version", (self.doc["id"],)
            )
        ]
        events = [event for event in tx.events(self.actor) if event["target"] == self.doc["id"]]
        return doc, versions, events

    def assert_winner(self, body):
        doc, versions, events = self.snapshot()
        self.assertEqual((doc["version"], doc["body_md"]), (2, body))
        self.assertEqual(versions, [{"version": 1, "body_md": "base"}, {"version": 2, "body_md": body}])
        updated = [event for event in events if event["type"] == "doc.updated"]
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0]["payload"], {"version": 2})
        self.assertFalse(self.tx.db.in_transaction)
        observer = sqlite3.connect(self.path)
        try:
            self.assertEqual(
                observer.execute("SELECT version, body_md FROM docs WHERE id = ?", (self.doc["id"],)).fetchone(),
                (2, body),
            )
            self.assertEqual(
                observer.execute(
                    "SELECT version, body_md FROM doc_versions WHERE doc_id = ? ORDER BY version", (self.doc["id"],)
                ).fetchall(),
                [(1, "base"), (2, body)],
            )
            self.assertEqual(
                observer.execute(
                    "SELECT COUNT(*) FROM events WHERE target = ? AND type = 'doc.updated'", (self.doc["id"],)
                ).fetchone()[0],
                1,
            )
        finally:
            observer.close()

    def race(self, stores):
        start = threading.Barrier(len(stores) + 1)
        successes, errors = [], []

        def update(tx, body):
            try:
                start.wait(timeout=5)
                successes.append(tx.update_doc(self.actor, self.doc["id"], body, 1))
            except BaseException as error:
                errors.append(error)

        workers = [threading.Thread(target=update, args=(tx, f"writer-{index}")) for index, tx in enumerate(stores)]
        for worker in workers:
            worker.start()
        start.wait(timeout=5)
        for worker in workers:
            worker.join(timeout=10)
        self.assertTrue(all(not worker.is_alive() for worker in workers), "concurrent update did not finish")
        self.assertEqual(len(successes), 1, repr(errors))
        self.assertEqual(len(errors), len(stores) - 1)
        self.assertTrue(all(isinstance(error, VersionConflict) for error in errors), repr(errors))
        self.assertEqual(successes[0]["version"], 2)
        self.assert_winner(successes[0]["body_md"])

    def test_same_connection_only_one_update_wins(self):
        self.race([self.tx, self.tx])

    def test_independent_connections_reject_a_stale_snapshot(self):
        other = Tianxuan(self.path)
        self.addCleanup(other.db.close)
        read_barrier = threading.Barrier(2)

        def synchronized_read(original):
            first = True

            def get_doc(doc_id):
                nonlocal first
                result = original(doc_id)
                if first:
                    first = False
                    read_barrier.wait(timeout=5)
                return result

            return get_doc

        with (
            patch.object(self.tx, "get_doc", synchronized_read(self.tx.get_doc)),
            patch.object(other, "get_doc", synchronized_read(other.get_doc)),
        ):
            self.race([self.tx, other])

    def test_independent_connection_succeeds_after_competing_rollback(self):
        other = Tianxuan(self.path)
        self.addCleanup(other.db.close)
        inserted, read = threading.Event(), threading.Event()
        outcomes = {}
        original_event = self.tx._event
        original_read = other.get_doc

        def fail_after_event(*args):
            original_event(*args)
            inserted.set()
            if not read.wait(timeout=5):
                raise AssertionError("competing connection did not read")
            raise RuntimeError("injected competing rollback")

        def competing_read(doc_id):
            result = original_read(doc_id)
            read.set()
            return result

        def update(key, tx):
            try:
                outcomes[key] = tx.update_doc(self.actor, self.doc["id"], key, 1)
            except BaseException as error:
                outcomes[key] = error

        first = threading.Thread(target=update, args=("failed", self.tx))
        second = threading.Thread(target=update, args=("winner", other))
        with patch.object(self.tx, "_event", fail_after_event), patch.object(other, "get_doc", competing_read):
            first.start()
            try:
                self.assertTrue(inserted.wait(timeout=5))
                second.start()
            finally:
                for worker in (first, second):
                    if worker.ident is not None:
                        worker.join(timeout=10)
            self.assertFalse(first.is_alive() or second.is_alive())
        self.assertIsInstance(outcomes["failed"], RuntimeError)
        self.assertEqual(outcomes["winner"]["version"], 2)
        self.assert_winner("winner")
        self.assertFalse(other.db.in_transaction)

    def test_failure_after_each_write_rolls_back_all_rows(self):
        for helper in ("_version", "_event"):
            with self.subTest(helper=helper):
                before = self.snapshot()
                original = getattr(self.tx, helper)

                def fail_after_insert(*args, **kwargs):
                    original(*args, **kwargs)
                    raise RuntimeError("injected after real insert")

                with patch.object(self.tx, helper, fail_after_insert):
                    with self.assertRaisesRegex(RuntimeError, "injected"):
                        self.tx.update_doc(self.actor, self.doc["id"], "rolled back", 1, title="changed", status="done")
                self.assertEqual(self.snapshot(), before)
                self.assertFalse(self.tx.db.in_transaction)
        self.tx.update_doc(self.actor, self.doc["id"], "retry", 1)
        self.assert_winner("retry")

    def test_sql_failure_rolls_back_body_and_history(self):
        self.tx.db.execute(
            "CREATE TEMP TRIGGER reject_update_event BEFORE INSERT ON events "
            "WHEN NEW.type = 'doc.updated' BEGIN SELECT RAISE(ABORT, 'injected event failure'); END"
        )
        before = self.snapshot()
        with self.assertRaisesRegex(StorageError, "storage operation failed") as caught:
            self.tx.update_doc(self.actor, self.doc["id"], "rolled back", 1)
        self.assertIsInstance(caught.exception.__cause__, sqlite3.Error)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.tx.db.in_transaction)
        self.tx.db.execute("DROP TRIGGER reject_update_event")
        self.tx.update_doc(self.actor, self.doc["id"], "retry", 1)
        self.assert_winner("retry")

    def test_commit_failure_rolls_back_and_releases_connection(self):
        underlying = self.tx.db

        class CommitFailure:
            def __getattr__(self, name):
                return getattr(underlying, name)

            def commit(self):
                raise sqlite3.OperationalError("injected commit failure")

        before = self.snapshot()
        with patch.object(self.tx, "db", CommitFailure()):
            with self.assertRaisesRegex(StorageError, "storage operation failed") as caught:
                self.tx.update_doc(self.actor, self.doc["id"], "rolled back", 1)
        self.assertIsInstance(caught.exception.__cause__, sqlite3.Error)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.tx.db.in_transaction)
        self.tx.update_doc(self.actor, self.doc["id"], "retry", 1)
        self.assert_winner("retry")

    def interleave(self, first, second):
        """Pause a real uncommitted version insert while a second call starts.

        Release from the test thread, never wait for the competing domain call
        inside the paused transaction (it is correctly waiting on the lock).
        """
        inserted, release, competing = threading.Event(), threading.Event(), threading.Event()
        outputs, errors = {}, {}
        original = self.tx._version

        def pause(*args, **kwargs):
            original(*args, **kwargs)
            if threading.current_thread().name == "paused-editor":
                inserted.set()
                if not release.wait(timeout=5):
                    raise RuntimeError("test did not release the paused editor")

        def run(key, action):
            try:
                if key == "second":
                    competing.set()
                outputs[key] = action()
            except BaseException as error:
                errors[key] = error

        threads = [
            threading.Thread(name="paused-editor", target=run, args=("first", first)),
            threading.Thread(name="competing-call", target=run, args=("second", second)),
        ]
        with patch.object(self.tx, "_version", pause):
            threads[0].start()
            try:
                self.assertTrue(inserted.wait(timeout=5))
                threads[1].start()
                self.assertTrue(competing.wait(timeout=5))
            finally:
                release.set()
                for worker in threads:
                    if worker.ident is not None:
                        worker.join(timeout=10)
            self.assertTrue(all(not worker.is_alive() for worker in threads))
        return outputs, errors

    def test_same_connection_conflict_during_an_uncommitted_update(self):
        outputs, errors = self.interleave(
            lambda: self.tx.update_doc(self.actor, self.doc["id"], "winner", 1),
            lambda: self.tx.update_doc(self.actor, self.doc["id"], "stale", 1),
        )
        self.assertEqual(outputs["first"]["version"], 2)
        self.assertIsInstance(errors.get("second"), VersionConflict)
        self.assertEqual(len(errors), 1)
        self.assert_winner("winner")

    def test_other_call_rollback_cannot_undo_successful_update(self):
        outputs, errors = self.interleave(
            lambda: self.tx.update_doc(self.actor, self.doc["id"], "winner", 1),
            lambda: self.tx.register("duplicate", "owner@example.invalid", "secret"),
        )
        self.assertEqual(outputs["first"]["version"], 2)
        self.assertIsInstance(errors.get("second"), TianxuanError)
        self.assertEqual(len(errors), 1)
        self.assert_winner("winner")

    def test_other_call_commit_cannot_preserve_a_failed_update(self):
        original_event = self.tx._event

        def fail_event(*args):
            original_event(*args)
            if args[1] == "doc.updated":
                raise RuntimeError("injected update failure")

        before = self.snapshot()
        with patch.object(self.tx, "_event", fail_event):
            outputs, errors = self.interleave(
                lambda: self.tx.update_doc(self.actor, self.doc["id"], "rolled back", 1),
                lambda: self.tx.create_doc(self.actor, "unrelated", "survives"),
            )
        self.assertIsInstance(errors.get("first"), RuntimeError)
        self.assertEqual(len(errors), 1)
        self.assertEqual(self.tx.get_doc(outputs["second"]["id"])["body_md"], "survives")
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.tx.db.in_transaction)

    def test_comment_calls_share_the_transaction_boundary(self):
        comment = self.tx.add_comment(self.actor, self.doc["id"], "review")
        reply = self.tx.add_comment(self.actor, self.doc["id"], "reply", parent_id=comment["id"])
        self.assertEqual(len(self.tx.list_comments(self.actor, self.doc["id"])), 2)
        self.assertTrue(self.tx.resolve_comment(self.actor, comment["id"])["resolved"])
        self.assertFalse(self.tx.resolve_comment(self.actor, comment["id"], False)["resolved"])
        observer = Tianxuan(self.path)
        self.addCleanup(observer.db.close)
        self.assertEqual(observer.get_comment(reply["id"])["body"], "reply")
        self.assertFalse(observer.get_comment(comment["id"])["resolved"])

        original_event = self.tx._event

        def fail_event(*args):
            original_event(*args)
            if args[1] == "comment.resolved":
                raise RuntimeError("injected comment failure")

        with patch.object(self.tx, "_event", fail_event):
            outputs, errors = self.interleave(
                lambda: self.tx.update_doc(self.actor, self.doc["id"], "winner", 1),
                lambda: self.tx.resolve_comment(self.actor, comment["id"]),
            )
        self.assertEqual(outputs["first"]["version"], 2)
        self.assertIsInstance(errors.get("second"), RuntimeError)
        self.assert_winner("winner")
        self.assertFalse(observer.get_comment(comment["id"])["resolved"])
        self.assertEqual(len([event for event in self.tx.events(self.actor) if event["type"] == "comment.resolved"]), 1)

    def test_reader_cannot_observe_an_update_that_rolls_back(self):
        original_event = self.tx._event

        def fail_event(*args):
            original_event(*args)
            if args[1] == "doc.updated":
                raise RuntimeError("injected update failure")

        with patch.object(self.tx, "_event", fail_event):
            outputs, errors = self.interleave(
                lambda: self.tx.update_doc(self.actor, self.doc["id"], "rolled back", 1),
                lambda: self.tx.get_doc(self.doc["id"]),
            )
        self.assertIsInstance(errors.get("first"), RuntimeError)
        self.assertEqual(outputs["second"]["body_md"], "base")
        self.assertEqual(outputs["second"]["version"], 1)

    def test_nested_calls_do_not_commit_before_the_outer_call(self):
        requirement = self.tx.create_requirement(self.actor, "req", "title", "outcome", "scope", "acceptance")
        before = self.tx.events(self.actor)
        original = self.tx.sync_progress

        def fail_after_nested_write(doc_id, *, actor):
            original(doc_id, actor=actor)
            raise RuntimeError("injected after nested sync")

        with patch.object(self.tx, "sync_progress", fail_after_nested_write):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                self.tx.plan_tickets(self.actor, requirement["id"], [{"title": "child"}])
        self.assertEqual(self.tx.list_issues(self.actor, requirement["id"]), [])
        self.assertEqual(self.tx.get_doc(requirement["id"])["progress"], {})
        self.assertEqual(self.tx.events(self.actor), before)
        self.assertFalse(self.tx.db.in_transaction)

    def test_reads_do_not_start_a_write_transaction(self):
        statements = []
        self.tx.db.set_trace_callback(statements.append)
        try:
            self.tx.get_doc(self.doc["id"])
            self.tx.list_docs(self.actor)
            self.tx.versions(self.doc["id"])
            self.tx.events(self.actor)
        finally:
            self.tx.db.set_trace_callback(None)
        self.assertFalse(any(sql.upper().startswith("BEGIN") for sql in statements), statements)
        self.assertFalse(self.tx.db.in_transaction)

    def test_update_emits_only_one_commit_after_all_writes(self):
        statements = []
        self.tx.db.set_trace_callback(statements.append)
        try:
            self.tx.update_doc(self.actor, self.doc["id"], "winner", 1)
        finally:
            self.tx.db.set_trace_callback(None)
        commits = [index for index, sql in enumerate(statements) if sql == "COMMIT"]
        inserts = [index for index, sql in enumerate(statements) if sql.startswith("INSERT")]
        self.assertEqual(len(commits), 1, statements)
        self.assertEqual(len(inserts), 2, statements)
        self.assertGreater(commits[0], max(inserts))
        self.assert_winner("winner")


if __name__ == "__main__":
    unittest.main()
