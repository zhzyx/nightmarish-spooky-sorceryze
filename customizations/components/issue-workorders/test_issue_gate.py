import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import issue_gate as gate


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.issue = {
            "number": 6,
            "html_url": "https://github.com/test/repo/issues/6",
            "state": "open",
            "labels": [{"name": "type:development"}, {"name": "status:in-progress"}, {"name": "workspace:gonggong"}],
            "body": "<!-- gonggong-request:req-6 -->",
            "updated_at": "2026-11-02T01:00:00Z",
        }

    def check(self, value=None):
        return gate.check_issue(value or self.issue, "test/repo", 6, "req-6", {"type:development"})

    def test_bound_issue_does_not_grant_membership_from_public_read_or_partial_labels(self):
        row = dict(
            number=6,
            title="work",
            url=self.issue["html_url"],
            state="OPEN",
            body=self.issue["body"],
            updatedAt=self.issue["updated_at"],
            labels={"nodes": self.issue["labels"], "pageInfo": {"hasNextPage": False}},
        )
        repo = dict(nameWithOwner="test/repo", databaseId=12, viewerPermission="WRITE", issue=row)
        response = dict(data={"viewer": {"login": "alice", "databaseId": 7}, "repository": repo})
        with patch.object(gate.work_items, "gh", side_effect=lambda *args: json.dumps(response)) as gh:
            source, actor = gate.read_bound_issue("test/repo", 6)
            self.assertEqual(actor["user_id"], "7")
            self.assertEqual(self.check(source), self.check())
            gh.assert_called_once()
            repo["viewerPermission"] = "READ"
            self.assertIsNone(gate.read_bound_issue("test/repo", 6)[1])
            row["labels"]["pageInfo"]["hasNextPage"] = True
            self.assertEqual(gate.read_bound_issue("test/repo", 6), (None, None))

    def test_storage_adapter_rejects_unregistered_import_before_execution(self):
        self.setup_gate()
        storage = "customizations/platforms/data-collection/git-files/storage"
        (self.root / storage / "tempfile.py").write_text("raise AssertionError()")
        with self.assertRaisesRegex(ValueError, "Platform file set or digest"):
            gate.verify_platform_adapter(self.root, storage)

    def test_real_issue_and_form_id(self):
        self.check()
        self.issue["body"] = "### 稳定需求 ID\r\n\r\nreq-6\r\n\r\n### 目标\r\nSome task"
        self.check()

    def test_invalid_issue(self):
        for mutation in (
            {"number": 7},
            {"html_url": "https://github.com/other/repo/issues/6"},
            {"pull_request": {}},
            {"state": "closed"},
            {"body": "<!-- gonggong-request:req-7 -->"},
            {"body": "<!-- gonggong-request:req-6 -->\n<!-- gonggong-request:req-7 -->"},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.check({**self.issue, **mutation})

    def test_invalid_labels(self):
        for names in (
            [],
            ["type:development"],
            ["status:in-progress"],
            ["type:unknown", "status:in-progress"],
            ["type:development", "type:bug", "status:in-progress"],
            ["type:development", "status:planned"],
            ["type:development", "status:done"],
            ["type:development", "status:in-progress", "status:in-review"],
        ):
            with self.subTest(names=names), self.assertRaises(ValueError):
                self.check({**self.issue, "labels": [{"name": n} for n in names]})

    def test_commit_gate_rejects_missing_workspace_before_framework_execution(self):
        self.setup_gate()
        self.issue["labels"] = [v for v in self.issue["labels"] if v["name"] != "workspace:gonggong"]
        with (
            patch.object(gate.work_items, "gh", return_value=json.dumps(self.issue)),
            patch.object(gate, "validate_command") as run,
        ):
            with self.assertRaisesRegex(ValueError, "workspace:gonggong"):
                gate.gate(self.root, 6, "req-6")
            run.assert_not_called()

    def setup_gate(self, events=True):
        # The formal gate checks platform bytes before invoking the mocked validator.
        import hashlib

        storage = "customizations/platforms/data-collection/git-files/storage"
        (self.root / storage).mkdir(parents=True)
        (self.root / storage / "diting_files.py").write_bytes(b"# fixture")
        batch = "customizations/platforms/development/git/git_batch.py"
        (self.root / batch).parent.mkdir(parents=True)
        (self.root / batch).write_bytes(b"# fixture")
        lock = self.root / "integrations/gonggong/frozen-distribution.json"
        lock.parent.mkdir(parents=True)
        lock.write_text(
            json.dumps({
                "host_files": {batch: hashlib.sha256(b"# fixture").hexdigest()},
                "platform_files": {storage: {"diting_files.py": hashlib.sha256(b"# fixture").hexdigest()}},
            })
        )

        if events:
            directory = self.root / "gonggong-diting-data/events/local/req-6"
            directory.mkdir(parents=True)
            (directory / "event.json").write_text(
                json.dumps({
                    "request_id": "req-6",
                    "tenant_id": "local",
                    "kind": "request",
                    "source_ref": self.issue["html_url"],
                })
            )
        for target, kwargs in (
            ("check_repository", {}),
            (
                "git",
                {
                    "side_effect": lambda root, *args: (
                        b"gonggong-diting-data/events/local/req-6/event.json\0"
                        if args[:2] == ("ls-files", "-z")
                        else b""
                    )
                },
            ),
            ("check_history", {}),
            ("check_collection", {}),
            ("check_pr_evidence", {"return_value": {"matching_event": True, "matching_collection": True}}),
            ("snapshot", {"return_value": "digest"}),
            ("environment", {"return_value": {}}),
            (
                "work_items.config",
                {"return_value": ({"repository": "test/repo", "tenant_id": "local"}, [{"name": "type:development"}])},
            ),
            ("work_items.gh", {"return_value": json.dumps(self.issue)}),
        ):
            p = patch("issue_gate." + target, **kwargs)
            p.start()
            self.addCleanup(p.stop)

    def test_formal_gate_calls_existing_tools(self):
        self.setup_gate()
        with patch.object(gate, "validate_command", side_effect=[{"mode": "approved_file_integrity"}, {}]) as run:
            result = gate.gate(self.root, 6, "req-6")
        self.assertNotIn("--candidate", run.call_args_list[0].args[0])
        self.assertEqual(run.call_count, 2)
        self.assertIn("git-check", run.call_args_list[1].args[0])
        self.assertNotIn("--require-committed", run.call_args_list[1].args[0])
        self.assertEqual(result["state"], "local_checks_passed")
        self.assertFalse(result["approval_granted"])
        self.assertFalse(result["diting_ingestion_confirmed"])
        self.assertEqual(len(result["events"]), 1)

    def test_missing_collection_fails(self):
        self.setup_gate(events=False)
        with patch.object(gate, "validate_command", side_effect=[{"mode": "approved_file_integrity"}, {}]):
            with self.assertRaisesRegex(ValueError, "No actual Diting events"):
                gate.gate(self.root, 6, "req-6")

    def test_formal_or_diting_failure_fails(self):
        self.setup_gate()
        for outcome in (
            [ValueError("formal failure")],
            [{"mode": "candidate"}],
            [{"mode": "approved_file_integrity"}, ValueError("Diting failure")],
        ):
            with self.subTest(outcome=outcome), patch.object(gate, "validate_command", side_effect=outcome):
                with self.assertRaises(ValueError):
                    gate.gate(self.root, 6, "req-6")

    def test_mutating_content_fails(self):
        self.setup_gate()
        with (
            patch.object(gate, "validate_command", side_effect=[{"mode": "approved_file_integrity"}, {}]),
            patch.object(gate, "snapshot", side_effect=["before", "after"]),
        ):
            with self.assertRaisesRegex(ValueError, "changed during check"):
                gate.gate(self.root, 6, "req-6")

    def test_unstaged_content_or_untracked_event_fails(self):
        self.setup_gate()
        for calls in ([ValueError("unstaged content")], [b"", ValueError("event not staged")]):
            with (
                self.subTest(calls=calls),
                patch.object(gate, "git", side_effect=calls),
                patch.object(gate, "validate_command", side_effect=[{"mode": "approved_file_integrity"}, {}]),
            ):
                with self.assertRaises(ValueError):
                    gate.gate(self.root, 6, "req-6")

    def test_tenant_kind_and_exact_source_binding(self):
        self.setup_gate()
        path = self.root / "gonggong-diting-data/events/local/req-6/event.json"
        original = json.loads(path.read_text())
        for mutation in (
            {"tenant_id": "other"},
            {"kind": "step"},
            {"source_ref": "https://github.com/other/repo/issues/6"},
            {"source_ref": "github:test/repo:issue:60"},
        ):
            path.write_text(json.dumps({**original, **mutation}))
            with (
                self.subTest(mutation=mutation),
                patch.object(gate, "validate_command", side_effect=[{"mode": "approved_file_integrity"}, {}]),
            ):
                with self.assertRaises(ValueError):
                    gate.gate(self.root, 6, "req-6")
        path.write_text(json.dumps({**original, "source_ref": "github:test/repo:issue:6"}))
        with patch.object(gate, "validate_command", side_effect=[{"mode": "approved_file_integrity"}, {}]):
            self.assertEqual(gate.gate(self.root, 6, "req-6")["state"], "local_checks_passed")

    def test_history_cannot_be_rewritten(self):
        path = self.root / "gonggong-diting-data/events/local/old/event.json"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"changed")
        name = path.relative_to(self.root).as_posix().encode()
        with patch.dict(gate.BATCH, {"objects": lambda *args: {name: b"original"}}):
            with self.assertRaisesRegex(ValueError, "history must remain immutable"):
                gate.check_history(self.root)

    def test_issue_changed_during_validation_fails(self):
        self.setup_gate()
        updated = {**self.issue, "updated_at": "2026-11-02T02:00:00Z"}
        with (
            patch.object(gate.work_items, "gh", side_effect=[json.dumps(self.issue), json.dumps(updated)]),
            patch.object(gate, "validate_command", side_effect=[{"mode": "approved_file_integrity"}, {}]),
        ):
            with self.assertRaisesRegex(ValueError, "changed during check"):
                gate.gate(self.root, 6, "req-6")

    def test_validator_errors_do_not_echo_credentials(self):
        with patch.object(gate.subprocess, "run") as run:
            run.return_value.returncode = 1
            run.return_value.stderr = "secret-token"
            with self.assertRaisesRegex(ValueError, "^Formal failed; run the trusted validator locally for details$"):
                gate.validate_command(["python"], self.root, {}, "Formal")

    def test_other_origin_rejected(self):
        with patch.object(gate, "git", side_effect=[str(self.root).encode(), b"git@github.com:other/repo.git"]):
            with self.assertRaisesRegex(ValueError, "origin must match"):
                gate.check_repository(self.root, "test/repo")

    def test_retired_source_locator_is_not_loaded(self):
        (self.root / ".gonggong-local.json").write_text('{"GONGGONG_FRAMEWORK_SOURCE":"absent"}')
        with patch.dict(os.environ, {}, clear=True):
            self.assertNotIn("GONGGONG_FRAMEWORK_SOURCE", gate.environment(self.root))


if __name__ == "__main__":
    unittest.main()
