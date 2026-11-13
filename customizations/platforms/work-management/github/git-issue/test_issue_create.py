import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import issue_create as m


class TransportTests(unittest.TestCase):
    def test_selected_cli_and_single_request_budget_survive_shared_transport_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "selected gh"
            executable.write_text("fixture")
            executable.chmod(0o755)
            api = m.GitHub(str(executable))
            with patch.object(
                m.github_runtime.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "[[1],[2]]", "")
            ) as run:
                self.assertEqual(api.call("api", "--paginate", "--slurp", "repos/a/b/issues"), "[[1],[2]]")
                self.assertEqual(run.call_args.kwargs["timeout"], 600)
                self.assertEqual(run.call_args.args[0][0], str(executable))
                api.call("issue", "create")
                self.assertEqual(run.call_args.kwargs["timeout"], 90)
            with patch.object(
                m.github_runtime.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired("fixture", 600, output="partial"),
            ) as run:
                with self.assertRaises(m.github_runtime.GitHubCommandError):
                    api.find({"repository": "a/b", "marker": "fixture"})
                run.assert_called_once()


class Fake:
    def __init__(self):
        self.issues = []
        self.creates = 0
        self.fail = False

    def actor(self):
        return "tester"

    def find(self, p):
        return self.issues

    def create(self, p, body):
        self.creates += 1
        if self.fail:
            raise RuntimeError("unknown network result")
        self.issues = [
            {
                "html_url": "https://github.com/a/b/issues/1",
                "number": 1,
                "body": body,
                "user": {"login": "tester"},
                "updated_at": "2026-11-03T00:00:00Z",
            }
        ]
        return self.issues[0]["html_url"]

    def get(self, p, url):
        return self.issues[0]


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "authority.json").write_text("{}")
        self.p = m.plan(
            {
                "request_id": "sample-task",
                "title": "test",
                "body": "intent",
                "type": "development",
                "owner": "host",
                "acceptance": "proof",
                "authority_ref": "authority.json",
            },
            {"repository": "a/b", "workspace_id": "gonggong", "workspace_label": "workspace:gonggong"},
        )
        self.api = Fake()
        self.settings = {"enabled": True, "approved_plan_sha256": self.p["plan_sha256"]}

    def test_pre_migration_plan_cannot_publish(self):
        del self.p["adapter_sha256"]
        del self.p["plan_sha256"]
        self.p["plan_sha256"] = m.digest(self.p)
        self.settings["approved_plan_sha256"] = self.p["plan_sha256"]
        with self.assertRaisesRegex(ValueError, "current adapter"):
            m.execute(self.p, self.settings, self.root, self.api, lambda e: True)
        self.assertEqual(self.api.creates, 0)

    def test_plan_binds_shared_runtime_and_refuses_changed_loaded_dependency(self):
        import hashlib

        self.assertEqual(
            self.p["adapter_sha256"],
            m.digest({
                "adapter": hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest(),
                "github_runtime": hashlib.sha256(m._RUNTIME_PATH.read_bytes()).hexdigest(),
            }),
        )
        changed = self.root / "changed-runtime.py"
        changed.write_text("different installed dependency")
        with patch.object(m, "_RUNTIME_PATH", changed):
            with self.assertRaisesRegex(ValueError, "runtime changed; restart"):
                m.execute(self.p, self.settings, self.root, self.api, lambda e: True)
            with self.assertRaisesRegex(ValueError, "runtime changed; restart"):
                m.adapter_digest()
        self.assertEqual(self.api.creates, 0)
        self.assertFalse((self.root / "data-collection/git-issue").exists())

    def test_disabled(self):
        self.settings["enabled"] = False
        with self.assertRaises(ValueError):
            m.execute(self.p, self.settings, self.root, self.api, lambda e: True)
        self.assertEqual(self.api.creates, 0)

    def test_create_reuse_actor(self):
        a = m.execute(self.p, self.settings, self.root, self.api, lambda e: True)
        b = m.execute(self.p, self.settings, self.root, self.api, lambda e: True)
        self.assertEqual((a["action"], b["action"], self.api.creates), ("created", "reused", 1))
        self.assertIn("host-git-account:tester", self.api.issues[0]["body"])

    def test_unknown_no_retry(self):
        self.api.fail = True
        with self.assertRaises(RuntimeError):
            m.execute(self.p, self.settings, self.root, self.api, lambda e: True)
        with self.assertRaises(ValueError):
            m.execute(self.p, self.settings, self.root, self.api, lambda e: True)
        self.assertEqual(self.api.creates, 1)

    def test_reporting_failure_no_create(self):
        with self.assertRaises(ValueError):
            m.execute(self.p, self.settings, self.root, self.api, lambda e: False)
        self.assertEqual(self.api.creates, 0)

    def test_tampered_plan(self):
        self.p["title"] = "changed"
        with self.assertRaises(ValueError):
            m.execute(self.p, self.settings, self.root, self.api, lambda e: True)

    def test_duplicate_remote(self):
        self.api.issues = [{}, {}]
        with self.assertRaises(ValueError):
            m.execute(self.p, self.settings, self.root, self.api, lambda e: True)

    def test_embedded_marker_not_reused(self):
        self.api.issues = [
            {"html_url": "https://github.com/a/b/issues/1", "number": 1, "body": "unrelated\n" + self.p["marker"]}
        ]
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            m.execute(self.p, self.settings, self.root, self.api, lambda e: True)

    def test_all_body_fields_reject_markers(self):
        for field in ("owner", "acceptance", "authority_ref"):
            request = {
                "request_id": "sample-task",
                "title": "test",
                "body": "intent",
                "type": "development",
                "owner": "host",
                "acceptance": "proof",
                "authority_ref": "authority.json",
            }
            request[field] = "<!-- gonggong-request:other -->"
            with self.assertRaises(ValueError):
                m.plan(
                    request, {"repository": "a/b", "workspace_id": "gonggong", "workspace_label": "workspace:gonggong"}
                )


if __name__ == "__main__":
    unittest.main()
