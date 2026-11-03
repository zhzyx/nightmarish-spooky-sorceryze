import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("guide_bridge", HERE / "bridge.py")
assert spec is not None and spec.loader is not None
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
WORK_ITEMS = HERE.parent / "issue-workorders/work_items.py"


class IssueGuideTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        adapter = self.root / "customizations/components/issue-workorders"
        adapter.mkdir(parents=True)
        shutil.copyfile(WORK_ITEMS, adapter / "work_items.py")
        (self.root / ".github").mkdir()
        (self.root / "work-items.json").write_text('{"repository":"test/repo"}', encoding="utf-8")
        (self.root / ".github/labels.json").write_text(
            '[{"name":"type:development","color":"123456","description":"dev"}]', encoding="utf-8"
        )
        self.module = bridge.work_items_module(self.root)
        self.request = {
            "request_id": "guide-req-1",
            "title": "Guide title",
            "category": "development",
            "outcome": "First line\n\nSecond line",
        }
        patcher = patch.object(bridge, "work_items_module", return_value=self.module)
        patcher.start()
        self.addCleanup(patcher.stop)

    def gh_environment(self, gh, authenticated=True):
        environment = patch.object(bridge, "host_environment", return_value={"OLYMPUS_GH": gh} if gh else {})
        login = patch.object(bridge, "gh_authenticated", return_value=authenticated)
        login.start()
        self.addCleanup(login.stop)
        return environment

    def test_draft_writes_document_and_previews_without_remote_calls(self):
        with patch.object(self.module, "gh") as gh, self.gh_environment(None):
            result = bridge.issue_draft(self.root, self.request)
        gh.assert_not_called()
        self.assertEqual(result["document"], "design-docs/guide-req-1.md")
        self.assertFalse(result["remote_created"])
        self.assertFalse(result["gh_available"])
        self.assertEqual(result["labels"], ["type:development", "status:needs-decision", "workspace:olympus"])
        text = (self.root / result["document"]).read_text(encoding="utf-8")
        self.assertIn("<!-- olympus-request:guide-req-1 -->", text)
        self.assertIn("> First line\n>\n> Second line", text)
        self.assertEqual(self.module.request_ids(text), {"guide-req-1"})

    def test_draft_is_idempotent_but_never_overwrites_other_content(self):
        with self.gh_environment(None):
            self.assertEqual(bridge.issue_draft(self.root, self.request)["state"], "document_created")
            self.assertEqual(bridge.issue_draft(self.root, self.request)["state"], "document_existing")
            with self.assertRaisesRegex(ValueError, "already exists"):
                bridge.issue_draft(self.root, dict(self.request, title="Other title"))

    def test_invalid_fields_rejected_before_writing(self):
        for change in (
            {"request_id": "../escape"},
            {"request_id": "Upper"},
            {"request_id": "a" * 81},
            {"title": "two\nlines"},
            {"title": ""},
            {"category": "unknown"},
            {"outcome": "   "},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                bridge.issue_draft(self.root, dict(self.request, **change))
        self.assertFalse((self.root / "design-docs").exists())

    def test_create_without_gh_returns_command_and_no_remote_side_effect(self):
        with self.gh_environment(None):
            bridge.issue_draft(self.root, self.request)
            with patch.object(self.module, "gh") as gh:
                result = bridge.issue_create(self.root, self.request)
        gh.assert_not_called()
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "gh_unavailable")
        self.assertIn("--request-id guide-req-1 --apply", result["command"])
        self.assertIn("'Guide title'", result["command"])

    def test_unauthenticated_gh_guides_login_without_remote_side_effect(self):
        with self.gh_environment("/fake/gh", authenticated=False):
            draft = bridge.issue_draft(self.root, self.request)
            with patch.object(self.module, "gh") as gh:
                created = bridge.issue_create(self.root, self.request)
                started = bridge.issue_start(self.root, {"issue_number": 42, "request_id": "guide-req-1"})
        gh.assert_not_called()
        self.assertEqual((draft["gh_available"], draft["gh_authenticated"]), (True, False))
        login = "/fake/gh auth login --hostname github.com --git-protocol https --web"
        self.assertEqual(draft["gh_login_command"], login)
        expected = (False, "gh_unauthenticated", login)
        self.assertEqual((created["ok"], created["error"], created["login_command"]), expected)
        self.assertIn("--request-id guide-req-1 --apply", created["command"])
        self.assertFalse(created["remote_created"])
        self.assertEqual((started["ok"], started["error"], started["login_command"]), expected)
        self.assertFalse(started["remote_changed"])

    def test_auth_status_is_read_only_and_failure_means_unauthenticated(self):
        tool = self.root / "bin/gh"
        tool.parent.mkdir()
        log = self.root / "gh-calls.txt"
        tool.write_text(
            '#!/bin/sh\necho "$@" >> ' + str(log) + "\n[ -f " + str(self.root / "logged-in") + " ]\n",
            encoding="utf-8",
        )
        tool.chmod(0o755)
        self.assertFalse(bridge.gh_authenticated(str(tool), {}))
        (self.root / "logged-in").write_text("", encoding="utf-8")
        self.assertTrue(bridge.gh_authenticated(str(tool), {}))
        self.assertFalse(bridge.gh_authenticated(str(self.root / "missing"), {}))
        self.assertEqual(log.read_text(encoding="utf-8").splitlines(), ["auth status --hostname github.com"] * 2)

    def test_login_command_quotes_gh_path(self):
        self.assertEqual(
            bridge.login_command("/Users/a b/gh"),
            "'/Users/a b/gh' auth login --hostname github.com --git-protocol https --web",
        )

    def test_create_uses_adapter_with_workspace_label(self):
        calls = []

        def fake(*args):
            calls.append(args)
            if args[0] == "api":
                return "[[]]"
            return "https://github.com/test/repo/issues/42"

        with self.gh_environment("/fake/gh"):
            bridge.issue_draft(self.root, self.request)
            with patch.object(self.module, "gh", side_effect=fake):
                result = bridge.issue_create(self.root, self.request)
        self.assertEqual((result["ok"], result["state"], result["number"]), (True, "created", 42))
        create = calls[-1]
        labels = [create[i + 1] for i, v in enumerate(create) if v == "--label"]
        self.assertEqual(labels, ["type:development", "status:needs-decision", "workspace:olympus"])

    def test_create_rejects_foreign_issue_url(self):
        with self.gh_environment("/fake/gh"):
            bridge.issue_draft(self.root, self.request)
            with patch.object(
                self.module, "gh", side_effect=lambda *a: "[[]]" if a[0] == "api" else "https://github.com/x/y/issues/1"
            ):
                with self.assertRaises(ValueError):
                    bridge.issue_create(self.root, self.request)

    def issue(self, labels, **values):
        value = {
            "number": 42,
            "state": "open",
            "body": "<!-- olympus-request:guide-req-1 -->",
            "labels": [{"name": n} for n in labels],
        }
        value.update(values)
        return json.dumps(value)

    def test_start_moves_unstarted_issue_to_in_progress(self):
        calls = []

        unstarted = ["type:development", "status:needs-decision", "workspace:olympus"]

        def fake(*args):
            calls.append(args)
            return self.issue(unstarted) if args[0] == "api" else ""

        with self.gh_environment("/fake/gh"), patch.object(self.module, "gh", side_effect=fake):
            result = bridge.issue_start(self.root, {"issue_number": 42, "request_id": "guide-req-1"})
        self.assertEqual(result["state"], "started")
        self.assertEqual(
            calls[-1],
            (
                "issue",
                "edit",
                "42",
                "--repo",
                "test/repo",
                "--add-label",
                "status:in-progress",
                "--remove-label",
                "status:needs-decision",
            ),
        )

    def test_start_leaves_active_issue_and_refuses_decided_or_foreign_issue(self):
        cases = (
            (["type:development", "status:in-review", "workspace:olympus"], {}, "already_active"),
            (["type:development", "status:blocked", "workspace:olympus"], {}, None),
            (["type:development", "status:done", "workspace:olympus"], {}, None),
            (["type:development", "status:needs-decision"], {}, None),
            (["type:development", "status:planned", "workspace:olympus"], {"state": "closed"}, None),
            (["type:development", "status:planned", "workspace:olympus"], {"body": "<!-- olympus-request:x -->"}, None),
            (["type:development", "status:planned", "workspace:olympus"], {"pull_request": {}}, None),
        )
        for labels, values, expected in cases:
            calls = []

            def fake(*args, labels=labels, values=values):
                calls.append(args)
                return self.issue(labels, **values)

            with self.subTest(labels=labels, values=values):
                with self.gh_environment("/fake/gh"), patch.object(self.module, "gh", side_effect=fake):
                    if expected:
                        self.assertEqual(
                            bridge.issue_start(self.root, {"issue_number": 42, "request_id": "guide-req-1"})["state"],
                            expected,
                        )
                    else:
                        with self.assertRaises(ValueError):
                            bridge.issue_start(self.root, {"issue_number": 42, "request_id": "guide-req-1"})
                self.assertEqual([c[0] for c in calls], ["api"])

    def test_gh_discovery_prefers_configuration_then_path(self):
        missing = str(self.root / "missing-gh")
        self.assertIsNone(bridge.find_gh({"OLYMPUS_GH": missing}))
        tool = self.root / "bin/gh"
        tool.parent.mkdir()
        tool.write_text("#!/bin/sh\n", encoding="utf-8")
        tool.chmod(0o755)
        self.assertEqual(bridge.find_gh({"OLYMPUS_GH": str(tool)}), str(tool))
        self.assertEqual(Path(bridge.find_gh({"PATH": str(tool.parent)})), tool)


if __name__ == "__main__":
    unittest.main()
