import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "customizations/components/godot-host/daqian"))
board = importlib.import_module("board")
delta = board.board_delta


class BoardDelta(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.args = SimpleNamespace(
            repo=self.root,
            follow=[],
            project=True,
            personal_history=False,
            editor_session="a" * 32,
            delta=self.root / "input",
        )
        self.actor = {"repo": "test/repo", "repo_id": "7", "user_id": "8", "login": "owner"}
        self.source = dict(
            number=18,
            title="Issue",
            user={"login": "owner"},
            state="open",
            updated_at="first",
            labels=[],
            assignees=[],
            html_url="https://github.com/test/repo/issues/18",
            issue_dependencies_summary={"total_blocked_by": 0},
            body="<!-- gonggong-request:test-18 -->",
        )
        self.enterContext(patch.object(delta, "cache_path", return_value=self.root / "cache.sqlite"))
        self.enterContext(patch.object(board.progress, "receipt_root", return_value=self.root / "receipts"))
        self.enterContext(patch("subprocess.check_output", return_value=str(self.root / ".git")))
        self.enterContext(patch.dict(os.environ, {"DAQIAN_PLAN_SSH_HOST": ""}))
        self.seed()

    def seed(self):
        import plan_store

        self.item = board.project_row(self.root, self.root / "receipts", self.actor, self.source)
        with plan_store.connect(self.root) as db:
            self.item.update(board.plan_summary(db, self.item))
        self.assertTrue(
            delta.seed(self.args, self.actor, {18: board.progress.dispatch_revision(self.source)}, [self.item])
        )
        self.target = {key: self.item[key] for key in ("number", "updated", "request", "delta_stamp")}

    def read(self, mode="progress", target=None, actor=None):
        self.args.delta.write_text(json.dumps({"mode": mode, "items": [target or self.target]}))
        return delta.read_changes(self.args, actor or self.actor)

    def test_progress_is_local_only_and_compared_to_the_consumers_stamp(self):
        with patch.object(board.work_items, "gh", side_effect=AssertionError("unexpected remote call")):
            self.assertEqual(self.read()["updates"], [])
            with patch.object(board.progress, "workers_for_snapshot", return_value=["worker"]):
                result = self.read()["updates"]
                self.assertEqual([row["workers"] for row in result], [["worker"]])
                self.assertEqual(self.read()["updates"], result)  # Lost response can be replayed.
                self.assertEqual(
                    self.read(target=dict(self.target, delta_stamp=result[0]["delta_stamp"]))["updates"], []
                )

    def test_unknown_changed_or_other_scope_never_fetches_arbitrary_issues(self):
        with patch.object(board.work_items, "gh", side_effect=AssertionError("unexpected remote call")):
            for target in [
                dict(self.target, number=19),
                dict(self.target, updated="wrong"),
                dict(self.target, request="changed"),
            ]:
                self.assertEqual(self.read("source", target)["reconcile"], [target["number"]])
            self.assertEqual(self.read(actor=dict(self.actor, user_id="other"))["reconcile"], [18])
            self.args.project = False
            self.assertEqual(self.read()["reconcile"], [18])

    def test_single_issue_read_updates_revision_and_closed_project_issue_is_removed(self):
        new = dict(self.source, title="Updated", updated_at="next")
        with patch.object(board.work_items, "gh", return_value=json.dumps(new)) as gh:
            updated = self.read("source")["updates"][0]
            gh.assert_called_once_with("api", "repos/test/repo/issues/18")
        self.assertEqual((updated["number"], updated["title"], updated["updated"]), (18, "Updated", "next"))
        self.target = {key: updated[key] for key in self.target}
        with patch.object(board.work_items, "gh", return_value=json.dumps(dict(new, state="closed"))):
            self.assertEqual(self.read("source")["removed"], [18])
        self.assertEqual(self.read()["reconcile"], [18])

    def test_legacy_start_invalidates_only_its_bound_source(self):
        key = "daqian-direct-" + "a" * 20
        self.source.update(
            user={"id": 7, "login": "owner"},
            labels=[{"name": label} for label in ("workspace:gonggong", "type:development", "status:planned")],
            body=f"<!-- gonggong-request:{key} -->\n<!-- gonggong-intake:daqian-direct -->\n"
            "\n\n## 原始需求\n\nTest focus.\n\n<!-- gonggong-host-git:owner -->",
        )
        self.seed()
        binding = {
            "actor": self.actor["user_id"],
            "number": 18,
            "url": self.item["url"],
            "revision": "first",
            "request_id": key,
            "source_sha256": self.item["source_sha256"],
        }
        folder = self.root / "receipts" / "daqian-direct" / key
        folder.mkdir(parents=True)

        def write_start(source):
            (folder / "start.json").write_text(json.dumps({"binding": source, "result": {"ready": True}}))

        with patch.object(board.work_items, "gh", side_effect=AssertionError("ordinary progress contacted GitHub")):
            self.assertEqual(self.read()["source_required"], [])  # Route/model events.
            write_start(dict(binding, actor="other"))
            self.assertEqual(self.read()["source_required"], [])
            write_start(dict(binding, revision="other"))
            self.assertEqual(self.read()["source_required"], [])
            # A second collaborator's start is a reason to re-read GitHub, not
            # an entitlement to their routing history or proof the status changed.
            write_start(dict(binding, actor="9"))
            self.assertEqual(self.read()["source_required"], [18])
            write_start(binding)
            self.assertEqual(self.read()["source_required"], [18])
        (folder / ".flush.lock").write_bytes(b"0")
        with patch("bridge.outbox_lock", side_effect=ValueError("busy")), patch.object(board.work_items, "gh") as gh:
            self.assertEqual(self.read("source")["source_required"], [18])
            gh.assert_not_called()
        with patch.object(board.work_items, "gh", return_value=json.dumps(self.source)) as gh:
            self.read("source")  # Failed mutation: authoritative status remains planned.
            self.assertEqual(self.read()["source_required"], [])
            gh.assert_called_once_with("api", "repos/test/repo/issues/18")
        write_start(binding)
        os.utime(folder / "start.json", (10, 10))
        self.assertEqual(self.read()["source_required"], [18])
        active = dict(
            self.source,
            updated_at="second",
            labels=[{"name": label} for label in ("workspace:gonggong", "type:development", "status:in-progress")],
        )
        with patch.object(board.work_items, "gh", return_value=json.dumps(active)) as gh:
            updated = self.read("source")["updates"][0]
            self.assertEqual((updated["status"], updated["updated"]), ("in-progress", "second"))
            gh.assert_called_once_with("api", "repos/test/repo/issues/18")

    def test_personal_dependency_changes_require_membership_reconciliation(self):
        self.args.project = False
        self.args.personal_history = True
        self.seed()
        source = dict(self.source, issue_dependencies_summary={"total_blocked_by": 1})
        with patch.object(
            board.work_items,
            "gh",
            side_effect=[json.dumps(source), json.dumps([[{"html_url": "https://github.com/test/repo/issues/19"}]])],
        ) as gh:
            self.assertEqual(self.read("source")["reconcile"], [18])
            self.assertEqual(gh.call_count, 2)
        with patch.object(board.work_items, "gh", return_value=json.dumps(dict(self.source, state="closed"))):
            self.assertTrue(self.read("source")["updates"][0]["closed"])


if __name__ == "__main__":
    unittest.main()
