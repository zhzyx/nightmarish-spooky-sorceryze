"""Current session/member/invite/ACL calls share document transaction ownership."""

import sqlite3
import threading
import unittest
from unittest.mock import patch

import test_tianxuan_concurrency as concurrency
from tianxuan_core import NotFound, PermissionDenied, StorageError, Tianxuan, TianxuanError, _token_hash


class CurrentBoundaryTests(unittest.TestCase):
    def setUp(self):
        concurrency.DocumentTransactionTests.setUp(self)
        self.member = self.tx.add_member(self.actor, "member@example.invalid", "secret")["user_id"]
        self.viewer = self.tx.add_member(self.actor, "viewer@example.invalid", "secret", role="viewer")["user_id"]

    def dump(self):
        return list(self.tx.db.iterdump())

    def interleave(self, action, *, fail_update=True):
        """Hold a real version INSERT; competing calls must wait for its outcome."""
        inserted, release, started, finished = (threading.Event() for _ in range(4))
        output, errors = {}, {}
        original_version, original_event = self.tx._version, self.tx._event

        def pause(*args):
            original_version(*args)
            inserted.set()
            if not release.wait(5):
                raise AssertionError("editor release timed out")

        def event(*args):
            original_event(*args)
            if fail_update and args[1] == "doc.updated":
                raise RuntimeError("injected editor failure")

        def edit():
            try:
                output["editor"] = self.tx.update_doc(self.actor, self.doc["id"], "uncommitted", 1)
            except BaseException as error:
                errors["editor"] = error

        def compete():
            started.set()
            try:
                output["other"] = action()
            except BaseException as error:
                errors["other"] = error
            finally:
                finished.set()

        threads = [threading.Thread(target=edit), threading.Thread(target=compete)]
        with patch.object(self.tx, "_version", pause), patch.object(self.tx, "_event", event):
            threads[0].start()
            try:
                self.assertTrue(inserted.wait(5))
                threads[1].start()
                self.assertTrue(started.wait(5))
                self.assertFalse(finished.wait(0.1), "competing public call bypassed connection ownership")
                with sqlite3.connect(self.path) as observer:
                    self.assertEqual(
                        observer.execute(
                            "SELECT version, body_md FROM docs WHERE id = ?", (self.doc["id"],)
                        ).fetchone(),
                        (1, "base"),
                    )
            finally:
                release.set()
                for worker in threads:
                    if worker.ident is not None:
                        worker.join(10)
        self.assertTrue(all(not worker.is_alive() for worker in threads))
        if fail_update:
            self.assertIsInstance(errors.get("editor"), RuntimeError)
        else:
            self.assertEqual(output["editor"]["version"], 2)
        self.assertFalse(self.tx.db.in_transaction)
        self.assertEqual(self.tx._call_depth, 0)
        return output, errors

    def test_new_mutators_cannot_commit_a_failed_document(self):
        issue = self.tx.create_issue(self.actor, "concurrent comment")
        revoked = self.tx.issue_session(self.member)
        expired = self.tx.issue_session(self.member, ttl_seconds=-1)
        invited = self.tx.create_invite(self.actor, "accepted@example.invalid", role="viewer")
        actions = {
            "add_issue_comment": lambda: self.tx.add_issue_comment(self.actor, issue["id"], "concurrent"),
            "issue_session": lambda: self.tx.issue_session(self.member),
            "revoke_session": lambda: self.tx.revoke_session(revoked),
            "expired_session_delete": lambda: self.tx.user_for_token(expired),
            "add_member": lambda: self.tx.add_member(self.actor, "added@example.invalid", "secret"),
            "set_role": lambda: self.tx.set_role(self.actor, self.member, "viewer"),
            "create_invite": lambda: self.tx.create_invite(self.actor, "new@example.invalid"),
            "accept_invite": lambda: self.tx.accept_invite(invited["code"], "secret"),
            "set_visibility": lambda: self.tx.set_visibility(self.actor, self.doc["id"], "private"),
            "share_doc": lambda: self.tx.share_doc(self.actor, self.doc["id"], self.viewer),
            "unshare_doc": lambda: self.tx.unshare_doc(self.actor, self.doc["id"], self.viewer),
        }
        for name, action in actions.items():
            with self.subTest(method=name):
                output, errors = self.interleave(action)
                self.assertEqual(set(errors), {"editor"})
                self.assertIn("other", output)
                self.assertEqual(self.tx.get_doc(self.doc["id"])["body_md"], "base")
                self.assertEqual([v["version"] for v in self.tx.versions(self.doc["id"])], [1])
                self.assertFalse(any(e["type"] == "doc.updated" for e in self.tx.events(self.actor)))
        observer = Tianxuan(self.path)
        self.addCleanup(observer.db.close)
        self.assertIsNone(observer.user_for_token(revoked))
        self.assertIsNone(observer.user_for_token(expired))
        self.assertEqual(observer.role_of(self.member), "viewer")
        self.assertIsNotNone(observer.authenticate("accepted@example.invalid", "secret"))
        self.assertEqual(observer.get_doc(self.doc["id"])["visibility"], "private")
        self.assertEqual(observer.list_shares(self.actor, self.doc["id"]), [])

    def test_new_readers_wait_and_cannot_observe_rolled_back_version(self):
        issue = self.tx.create_issue(self.actor, "comment reads")
        comment = self.tx.add_issue_comment(self.actor, issue["id"], "persisted")
        token = self.tx.issue_session(self.member)
        actions = {
            "get_issue_comment": lambda: self.tx.get_issue_comment(comment["id"]),
            "list_issue_comments": lambda: self.tx.list_issue_comments(self.actor, issue["id"]),
            "user_for_token": lambda: self.tx.user_for_token(token),
            "role_of": lambda: self.tx.role_of(self.member),
            "list_members": lambda: self.tx.list_members(self.actor),
            "version": lambda: self.tx.version(self.doc["id"], 1),
            "get_doc_shared": lambda: self.tx.get_doc_shared(self.member, self.doc["id"]),
            "list_shares": lambda: self.tx.list_shares(self.actor, self.doc["id"]),
        }
        for name, action in actions.items():
            with self.subTest(method=name):
                output, errors = self.interleave(action)
                self.assertEqual(set(errors), {"editor"})
                if name in {"version", "get_doc_shared"}:
                    self.assertEqual(output["other"]["body_md"], "base")
        _, errors = self.interleave(lambda: self.tx.version(self.doc["id"], 2))
        self.assertIsInstance(errors["other"], NotFound)

    def test_duplicate_and_permission_errors_do_not_rollback_other_success(self):
        invite = self.tx.create_invite(self.actor, "owner@example.invalid")
        actions = [
            (
                lambda: self.tx.add_member(self.actor, "owner@example.invalid", "secret"),
                TianxuanError,
                "member rejected",
            ),
            (lambda: self.tx.accept_invite(invite["code"], "secret"), TianxuanError, "already registered"),
            (
                lambda: self.tx.add_member(self.viewer, "denied@example.invalid", "secret"),
                PermissionDenied,
                "only admin",
            ),
            (
                lambda: self.tx.set_visibility(self.member, self.doc["id"], "private"),
                PermissionDenied,
                "only the owner",
            ),
        ]
        for action, error_type, message in actions:
            with self.subTest(error=message):
                self.doc = self.tx.create_doc(self.actor, "fresh", "base")
                output, errors = self.interleave(action, fail_update=False)
                self.assertIsInstance(errors.get("other"), error_type)
                self.assertIn(message, str(errors["other"]))
                self.assertEqual(output["editor"]["version"], 2)
                observer = Tianxuan(self.path)
                try:
                    self.assertEqual(observer.version(self.doc["id"], 2)["body_md"], "uncommitted")
                finally:
                    observer.db.close()

    def test_member_invite_role_and_sharing_event_failures_rollback(self):
        invite = self.tx.create_invite(self.actor, "rollback@example.invalid")
        self.tx.share_doc(self.actor, self.doc["id"], self.member)
        issue = self.tx.create_issue(self.actor, "comment rollback")
        actions = {
            "issue.comment_added": lambda: self.tx.add_issue_comment(self.actor, issue["id"], "rollback"),
            "user.added": lambda: self.tx.add_member(self.actor, "rollback-member@example.invalid", "secret"),
            "user.invited": lambda: self.tx.accept_invite(invite["code"], "secret"),
            "user.role_changed": lambda: self.tx.set_role(self.actor, self.member, "viewer"),
            "doc.visibility_changed": lambda: self.tx.set_visibility(self.actor, self.doc["id"], "private"),
            "doc.shared": lambda: self.tx.share_doc(self.actor, self.doc["id"], self.member, "write"),
            "doc.unshared": lambda: self.tx.unshare_doc(self.actor, self.doc["id"], self.member),
        }
        original_event = self.tx._event
        for event_type, action in actions.items():
            with self.subTest(event=event_type):
                before = self.dump()

                def fail(*args):
                    original_event(*args)
                    if args[1] == event_type:
                        raise RuntimeError("injected after real event")

                with patch.object(self.tx, "_event", fail), self.assertRaisesRegex(RuntimeError, "injected"):
                    action()
                self.assertEqual(self.dump(), before)
                self.assertFalse(self.tx.db.in_transaction)
                self.assertEqual(self.tx._call_depth, 0)
                action()

    def test_session_and_invite_commit_failure_rolls_back(self):
        expired = self.tx.issue_session(self.member, ttl_seconds=-1)
        valid = self.tx.issue_session(self.member)
        actions = {
            "issue_session": lambda: self.tx.issue_session(self.member),
            "expired_session_delete": lambda: self.tx.user_for_token(expired),
            "revoke_session": lambda: self.tx.revoke_session(valid),
            "create_invite": lambda: self.tx.create_invite(self.actor, "commit@example.invalid"),
        }
        underlying = self.tx.db

        class FailCommit:
            def __getattr__(self, name):
                return getattr(underlying, name)

            def commit(self):
                raise sqlite3.OperationalError("injected commit failure")

        for name, action in actions.items():
            with self.subTest(method=name):
                before = self.dump()
                with (
                    patch.object(self.tx, "db", FailCommit()),
                    self.assertRaisesRegex(StorageError, "storage operation failed") as caught,
                ):
                    action()
                self.assertIsInstance(caught.exception.__cause__, sqlite3.OperationalError)
                self.assertEqual(self.dump(), before)
                self.assertFalse(self.tx.db.in_transaction)
                action()
        self.assertIsNone(self.tx.user_for_token(expired))
        self.assertIsNone(self.tx.user_for_token(valid))

    def test_expired_and_malformed_session_cleanup_commits(self):
        for malformed in (False, True):
            token = self.tx.issue_session(self.member, ttl_seconds=-1)
            if malformed:
                self.tx.db.execute(
                    "UPDATE sessions SET expires_at = ? WHERE token_hash = ?", ("invalid", _token_hash(token))
                )
                self.tx.db.commit()
            self.assertIsNone(self.tx.user_for_token(token))
            with sqlite3.connect(self.path) as observer:
                self.assertIsNone(
                    observer.execute("SELECT * FROM sessions WHERE token_hash = ?", (_token_hash(token),)).fetchone()
                )

    def test_invite_errors_keep_original_semantics_and_state(self):
        expired = self.tx.create_invite(self.actor, "expired@example.invalid", ttl_seconds=-1)
        malformed = self.tx.create_invite(self.actor, "malformed@example.invalid")
        self.tx.db.execute(
            "UPDATE invites SET expires_at = ? WHERE token_hash = ?", ("invalid", _token_hash(malformed["code"]))
        )
        self.tx.db.commit()
        for code, message in [
            (expired["code"], "has expired"),
            (malformed["code"], "invalid expiry"),
            ("missing", "invalid or already used"),
        ]:
            before = self.dump()
            with self.assertRaisesRegex(TianxuanError, message):
                self.tx.accept_invite(code, "secret")
            self.assertEqual(self.dump(), before)
            self.assertFalse(self.tx.db.in_transaction)

    def test_shared_read_holds_boundary_through_acl_check(self):
        self.tx.set_visibility(self.actor, self.doc["id"], "private")
        self.tx.share_doc(self.actor, self.doc["id"], self.member)
        read_started, release, revoke_started, revoke_done = (threading.Event() for _ in range(4))
        original = self.tx._can_read
        output, errors = {}, []

        def pause(*args):
            read_started.set()
            if not release.wait(5):
                raise AssertionError("ACL read release timed out")
            return original(*args)

        def read():
            try:
                output["doc"] = self.tx.get_doc_shared(self.member, self.doc["id"])
            except BaseException as error:
                errors.append(error)

        def revoke():
            revoke_started.set()
            try:
                self.tx.unshare_doc(self.actor, self.doc["id"], self.member)
            except BaseException as error:
                errors.append(error)
            finally:
                revoke_done.set()

        threads = [threading.Thread(target=read), threading.Thread(target=revoke)]
        with patch.object(self.tx, "_can_read", pause):
            threads[0].start()
            try:
                self.assertTrue(read_started.wait(5))
                threads[1].start()
                self.assertTrue(revoke_started.wait(5))
                self.assertFalse(revoke_done.wait(0.1))
            finally:
                release.set()
                for thread in threads:
                    if thread.ident is not None:
                        thread.join(10)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(output["doc"]["body_md"], "base")
        with self.assertRaises(PermissionDenied):
            self.tx.get_doc_shared(self.member, self.doc["id"])

    def test_nested_new_mutators_never_commit_the_outer_transaction(self):
        valid = self.tx.issue_session(self.member)
        expired = self.tx.issue_session(self.member, ttl_seconds=-1)
        invite = self.tx.create_invite(self.actor, "nested-invite@example.invalid")
        self.tx.share_doc(self.actor, self.doc["id"], self.member)
        actions = {
            "issue_session": lambda: self.tx.issue_session(self.member),
            "revoke_session": lambda: self.tx.revoke_session(valid),
            "expired_session_delete": lambda: self.tx.user_for_token(expired),
            "add_member": lambda: self.tx.add_member(self.actor, "nested@example.invalid", "secret"),
            "set_role": lambda: self.tx.set_role(self.actor, self.member, "viewer"),
            "create_invite": lambda: self.tx.create_invite(self.actor, "nested-new@example.invalid"),
            "accept_invite": lambda: self.tx.accept_invite(invite["code"], "secret"),
            "set_visibility": lambda: self.tx.set_visibility(self.actor, self.doc["id"], "private"),
            "share_doc": lambda: self.tx.share_doc(self.actor, self.doc["id"], self.member, "write"),
            "unshare_doc": lambda: self.tx.unshare_doc(self.actor, self.doc["id"], self.member),
        }
        original = self.tx._event
        for name, action in actions.items():
            with self.subTest(method=name):
                before = self.dump()
                statements = []

                def nested(*args):
                    original(*args)
                    if args[1] == "doc.updated":
                        action()
                        raise RuntimeError("injected after nested call")

                self.tx.db.set_trace_callback(statements.append)
                try:
                    with patch.object(self.tx, "_event", nested), self.assertRaisesRegex(RuntimeError, "injected"):
                        self.tx.update_doc(self.actor, self.doc["id"], "nested", 1)
                finally:
                    self.tx.db.set_trace_callback(None)
                self.assertEqual(self.dump(), before)
                self.assertNotIn("COMMIT", statements)
                self.assertEqual(statements.count("ROLLBACK"), 1)
                self.assertFalse(self.tx.db.in_transaction)
                self.assertEqual(self.tx._call_depth, 0)

    def test_new_readers_do_not_acquire_sqlite_write_lock(self):
        token = self.tx.issue_session(self.member)
        observer = sqlite3.connect(self.path)
        self.addCleanup(observer.close)
        observer.execute("BEGIN IMMEDIATE")
        statements = []
        self.tx.db.set_trace_callback(statements.append)
        try:
            self.assertEqual(self.tx.user_for_token(token), self.member)
            self.tx.role_of(self.member)
            self.tx.list_members(self.actor)
            self.tx.version(self.doc["id"], 1)
            self.tx.get_doc_shared(self.member, self.doc["id"])
            self.tx.list_shares(self.actor, self.doc["id"])
        finally:
            self.tx.db.set_trace_callback(None)
            observer.rollback()
        self.assertFalse(
            any(sql.split()[0].upper() in {"BEGIN", "COMMIT", "INSERT", "UPDATE", "DELETE"} for sql in statements)
        )


if __name__ == "__main__":
    unittest.main()
