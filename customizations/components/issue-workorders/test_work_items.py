import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("work_items", Path(__file__).with_name("work_items.py"))
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class WorkItemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / ".github").mkdir()
        (self.root / "design-docs").mkdir()
        (self.root / "work-items.json").write_text('{"repository":"test/repo"}')
        (self.root / ".github/labels.json").write_text(
            '[{"name":"type:design","color":"123456","description":"design"}]'
        )
        (self.root / ".github/status-labels.json").write_text(
            json.dumps([
                {"name": "status:" + v, "color": "123456", "description": v}
                for v in ("needs-decision", "planned", "in-progress", "blocked", "in-review", "done", "cancelled")
            ])
        )
        (self.root / "design-docs/req.md").write_text("# Actual requirement\n")

    def create(self, apply=False, document="design-docs/req.md"):
        return module.issue(self.root, document, "Title", "design", "req-1", apply)

    def test_preview_has_no_network_side_effects(self):
        with patch.object(module, "gh") as gh:
            self.assertEqual(self.create()["state"], "planned")
            module.labels(self.root)
        gh.assert_not_called()

    def test_github_transport_eof_is_a_network_error(self):
        failed = subprocess.CompletedProcess([], 1, "", 'Get "https://api.github.com/user/repos": EOF\n')
        with patch.object(module.subprocess, "run", return_value=failed):
            with self.assertRaisesRegex(module.GitHubCommandError, "^GITHUB_NETWORK:") as raised:
                module.gh("api", "user/repos")
        self.assertNotIn("api.github.com", str(raised.exception))

    def test_document_cannot_escape_design_directory(self):
        with self.assertRaises(ValueError):
            self.create(document="../outside.md")

    def test_authorized_create_records_mandate_and_starts(self):
        def fake(*args):
            if args[:2] == ("api", "user"):
                return '{"login":"test-host"}'
            if args[0] == "api":
                return "[[]]"
            body = Path(args[args.index("--body-file") + 1]).read_text(encoding="utf-8")
            self.assertIn("user-request-100", body)
            self.assertIn("status:in-progress", args)
            self.assertNotIn("status:needs-decision", args)
            return "https://github.com/test/repo/issues/2"

        with patch.object(module, "gh", side_effect=fake):
            result = module.issue(self.root, "design-docs/req.md", "Title", "design", "req-1", True, "user-request-100")
        self.assertEqual(result["state"], "created")

    def test_authorized_retry_does_not_mutate_existing_closed_issue(self):
        existing = [
            [
                dict(
                    state="closed",
                    body="<!-- gonggong-request:req-1 -->",
                    html_url="https://github.com/test/repo/issues/1",
                )
            ]
        ]
        with patch.object(module, "gh", side_effect=['{"login":"test-host"}', json.dumps(existing)]) as gh:
            result = module.issue(self.root, "design-docs/req.md", "Title", "design", "req-1", True, "user-request-100")
        self.assertEqual(result["state"], "existing")
        self.assertEqual(gh.call_count, 2)

    def test_invalid_mandate_rejected_before_network(self):
        with patch.object(module, "gh") as gh:
            for value in ("", " ", "ref\nforged", 123):
                with self.assertRaises(ValueError):
                    module.issue(self.root, "design-docs/req.md", "Title", "design", "req-1", True, value)
        gh.assert_not_called()

    def test_unknown_category_rejected(self):
        with self.assertRaises(ValueError):
            module.issue(self.root, "design-docs/req.md", "Title", "unknown", "req-1")

    def test_existing_closed_issue_reused(self):
        response = [
            [
                {
                    "state": "closed",
                    "body": "<!-- gonggong-request:req-1 -->",
                    "html_url": "https://github.com/test/repo/issues/1",
                }
            ]
        ]
        with patch.object(module, "gh", side_effect=[json.dumps({"login": "test-host"}), json.dumps(response)]) as gh:
            self.assertEqual(self.create(True)["state"], "existing")
        self.assertEqual(gh.call_count, 2)

    def test_duplicate_remote_identity_rejected(self):
        response = [[{"body": "<!-- gonggong-request:req-1 -->"}] * 2]
        with patch.object(module, "gh", side_effect=[json.dumps({"login": "test-host"}), json.dumps(response)]):
            with self.assertRaises(ValueError):
                self.create(True)

    def test_existing_form_issue_reused(self):
        response = [
            [
                {
                    "state": "open",
                    "body": "### 稳定需求 ID\n\nreq-1\n",
                    "html_url": "https://github.com/test/repo/issues/1",
                }
            ]
        ]
        with patch.object(module, "gh", side_effect=[json.dumps({"login": "test-host"}), json.dumps(response)]) as gh:
            self.assertEqual(self.create(True)["state"], "existing")
        self.assertEqual(gh.call_count, 2)

    def test_existing_label_not_overwritten(self):
        existing = [{"name": "type:design"}] + module.read(self.root / ".github/status-labels.json")
        with patch.object(module, "gh", return_value=json.dumps([existing])) as gh:
            module.labels(self.root, True)
        self.assertEqual(gh.call_count, 1)

    def test_create_uses_exact_body_file(self):
        def fake(*args):
            if args[0] == "api":
                if args[1] == "user":
                    return '{"login":"test-host"}'
                return "[[]]"
            self.assertEqual(args[:2], ("issue", "create"))
            body = Path(args[args.index("--body-file") + 1]).read_text(encoding="utf-8")
            self.assertIn("<!-- gonggong-request:req-1 -->", body)
            self.assertIn("<!-- gonggong-host-git:test-host -->", body)
            self.assertIn("# Actual requirement", body)
            labels = [args[i + 1] for i, v in enumerate(args) if v == "--label"]
            self.assertEqual(labels, ["type:design", "status:needs-decision", "workspace:gonggong"])
            return "https://github.com/test/repo/issues/2"

        with patch.object(module, "gh", side_effect=fake):
            self.assertEqual(self.create(True)["state"], "created")

    def test_failed_validation_never_publishes_index(self):
        with patch.object(module.subprocess, "run") as run:
            run.return_value.returncode = 1
            with self.assertRaises(ValueError):
                module.collect(self.root, "req-1")
        self.assertFalse((self.root / "data-collection").exists())

    def test_forms_match_label_definitions(self):
        _, labels = module.config(module.ROOT)
        forms = [
            json.loads(
                (module.ROOT / ".github/ISSUE_TEMPLATE" / (label["name"].split(":")[1] + ".yml")).read_text(
                    encoding="utf-8"
                )
            )
            for label in labels
        ]
        self.assertEqual({x["name"] for x in labels}, {f["labels"][0] for f in forms})
        self.assertTrue(all(len([v for v in f["labels"] if v.startswith("type:")]) == 1 for f in forms))
        self.assertTrue(
            all([v for v in f["labels"] if v.startswith("status:")] == ["status:needs-decision"] for f in forms)
        )


if __name__ == "__main__":
    unittest.main()
