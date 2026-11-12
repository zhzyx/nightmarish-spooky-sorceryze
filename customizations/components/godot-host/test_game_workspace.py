"""Real isolated Git fixtures for installed-host / game-data separation."""

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "issue-workorders"))
import issue_gate
import work_items

spec = importlib.util.spec_from_file_location("paths", Path(__file__).with_name("workspace_paths.py"))
assert spec is not None and spec.loader is not None
paths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paths)


class GameWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.git("init")
        self.git("config", "core.autocrlf", "false")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "--allow-empty",
            "-m",
            "base",
        )
        self.git("remote", "add", "origin", "https://github.com/fixture/game.git")
        self.work = Mock()
        self.work.gh.side_effect = [
            json.dumps({"login": "fixture", "id": 123}),
            json.dumps({"full_name": "fixture/game", "permissions": {"push": True}}),
        ]

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)

    def test_data_only_and_idempotent(self):
        (self.root / "game").mkdir()
        (self.root / "game/project.godot").write_text("config_version=5")
        paths.prepare_game_workspace(self.root, self.work)
        settings = json.loads((self.root / "work-items.json").read_text())
        self.assertEqual(settings["repository"], "fixture/game")
        self.assertFalse((self.root / "framework").exists())
        self.assertFalse((self.root / "tools").exists())
        dataset = (self.root / "gonggong-diting-data/dataset.json").read_bytes()
        paths.prepare_game_workspace(self.root, self.work)
        self.assertEqual(dataset, (self.root / "gonggong-diting-data/dataset.json").read_bytes())
        self.assertEqual(self.work.gh.call_count, 2)

    def test_installed_storage_accepts_game_only_dataset(self):
        paths.prepare_game_workspace(self.root, self.work)
        host = Path(__file__).resolve().parents[3]
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                str(host / "customizations/platforms/data-collection/git-files/storage/diting_files.py"),
                "validate",
                "--repo",
                str(self.root),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["valid"])

    def ready_delivery(self):
        paths.prepare_game_workspace(self.root, self.work)
        settings = json.loads((self.root / "work-items.json").read_text())
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        store = issue_gate.INSTALLATION / "customizations/platforms/data-collection/git-files/storage/diting_files.py"
        event = dict(
            schema_version=1,
            event_id="request-test",
            tenant_id=settings["tenant_id"],
            request_id="req-test",
            kind="request",
            occurred_at="2026-11-12T00:00:00Z",
            source_ref="https://github.com/fixture/game/issues/6",
            agent=dict(
                id="controlled-test", version="1", definition_sha256="a" * 64, origin="external-authorized-host"
            ),
            evidence_refs=[],
            payload={"controlled_test": True},
        )
        input_file = self.root / "input.json"
        input_file.write_text(json.dumps(event))
        result = subprocess.run(
            [sys.executable, "-I", str(store), "record", "--repo", str(self.root), "--input", str(input_file)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        input_file.unlink()
        work_items.collect(self.root, "req-test")
        self.git("add", ".")
        row = dict(
            number=6,
            html_url=event["source_ref"],
            state="open",
            body="<!-- gonggong-request:req-test -->",
            labels=[{"name": name} for name in ("workspace:gonggong", "type:development", "status:in-progress")],
        )
        return row, store

    def test_real_formal_gate_session_collection_and_committed_storage(self):
        row, store = self.ready_delivery()
        with patch.object(work_items, "gh", return_value=json.dumps(row)):
            for session in (None, issue_gate.VerificationSession()):
                result = issue_gate.gate(self.root, 6, "req-test", session)
                self.assertEqual(result["state"], "local_checks_passed")
                self.assertFalse(result["approval_granted"])
        self.git(
            "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "controlled delivery"
        )
        result = subprocess.run(
            [sys.executable, "-I", str(store), "git-check", "--repo", str(self.root), "--require-committed"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / "framework").exists())
        self.assertFalse((self.root / "tools").exists())

    def test_engine_candidate_requires_exact_installed_framework(self):
        self.ready_delivery()
        shutil.copytree(
            issue_gate.INSTALLATION / "framework", self.root / "framework", ignore=shutil.ignore_patterns("__pycache__")
        )
        shutil.copyfile(issue_gate.INSTALLATION / "CURRENT_FRAMEWORK.json", self.root / "CURRENT_FRAMEWORK.json")
        issue_gate.verify_candidate_framework(self.root)
        verifier = self.root / "framework/tools/verify_framework.py"
        verifier.write_text("raise AssertionError('candidate code must never execute')")
        with self.assertRaisesRegex(ValueError, "exact candidate admission"):
            issue_gate.verify_candidate_framework(self.root)
        self.git("add", ".")
        self.git(
            "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "framework candidate"
        )
        shutil.rmtree(self.root / "framework")
        (self.root / "CURRENT_FRAMEWORK.json").unlink()
        with self.assertRaisesRegex(ValueError, "exact candidate admission"):
            issue_gate.verify_candidate_framework(self.root)

    def test_shared_publication_permission_labels_and_read_only_preview(self):
        paths.prepare_game_workspace(self.root, self.work)
        (self.root / "design-docs").mkdir()
        (self.root / "design-docs/task.md").write_text("# controlled requirement")

        def create(apply):
            return work_items.issue(self.root, "design-docs/task.md", "Test", "development", "req-test", apply)

        with patch.object(work_items, "gh") as remote:
            create(False)
            remote.assert_not_called()
        for allowed in (False, True):
            calls = []
            known = []

            def gh(*args):
                calls.append(args)
                if args == ("api", "user"):
                    return '{"login":"fixture"}'
                if args == ("api", "repos/fixture/game"):
                    return json.dumps({"full_name": "fixture/game", "permissions": {"push": allowed}})
                if args[0] == "api":
                    return json.dumps([known if "/labels?" in args[1] else []])
                if args[:2] == ("label", "create"):
                    self.assertTrue(allowed)
                    known.append({"name": args[2]})
                    return ""
                self.assertEqual(args[:2], ("issue", "create"))
                self.assertIn({"name": "workspace:gonggong"}, known)
                return "https://github.com/fixture/game/issues/6"

            with patch.object(work_items, "gh", side_effect=gh):
                if allowed:
                    self.assertEqual(create(True)["state"], "created")
                else:
                    with self.assertRaisesRegex(ValueError, "write permission"):
                        create(True)
                    self.assertTrue(all(c[0] == "api" for c in calls))

    def test_permission_denied_writes_nothing(self):
        self.work.gh.side_effect = [
            json.dumps({"login": "fixture", "id": 123}),
            json.dumps({"full_name": "fixture/game", "permissions": {"push": False}}),
        ]
        with self.assertRaises(ValueError):
            paths.prepare_game_workspace(self.root, self.work)
        self.assertFalse((self.root / "work-items.json").exists())

    def test_wrong_remote_identity_writes_nothing(self):
        self.work.gh.side_effect = [
            json.dumps({"login": "fixture", "id": 123}),
            json.dumps({"full_name": "fixture/other", "permissions": {"push": True}}),
        ]
        with self.assertRaises(ValueError):
            paths.prepare_game_workspace(self.root, self.work)
        self.assertFalse((self.root / ".github").exists())

    def test_existing_user_file_preserved(self):
        (self.root / ".github").mkdir()
        user_file = self.root / ".github/labels.json"
        user_file.write_text("[]")
        with self.assertRaises(ValueError):
            paths.prepare_game_workspace(self.root, self.work)
        self.assertEqual(user_file.read_text(), "[]")
        self.assertFalse((self.root / "work-items.json").exists())

    def test_missing_git_does_not_use_host(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                paths.prepare_game_workspace(Path(folder).resolve(), self.work)
        self.work.gh.assert_not_called()

    def test_framework_cannot_be_selected_by_game(self):
        (self.root / "CURRENT_FRAMEWORK.json").write_text('{"root":"evil"}')
        self.assertEqual(paths.framework_root(self.root), Path(__file__).resolve().parents[3] / "framework")

    def test_subdirectory_rejected_as_repository(self):
        sub = self.root / "game"
        sub.mkdir()
        with self.assertRaises(ValueError):
            paths.prepare_game_workspace(sub, self.work)
        self.work.gh.assert_not_called()


if __name__ == "__main__":
    unittest.main()
