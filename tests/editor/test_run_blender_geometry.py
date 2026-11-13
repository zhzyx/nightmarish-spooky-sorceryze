"""Fail-closed runner checks; these do not claim Windows geometry acceptance."""

import io
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import run_blender_geometry as runner


class RunnerTests(unittest.TestCase):
    def execute_cases(self, behavior=None, count=3):
        def body(case):
            if case._testMethodName == runner.TEST_NAMES[0] and behavior:
                behavior(case)

        case = type("Fixture", (unittest.TestCase,), dict.fromkeys(runner.TEST_NAMES, body))
        suite = unittest.TestSuite(case(name) for name in runner.TEST_NAMES[:count])
        result = unittest.TextTestRunner(stream=io.StringIO(), resultclass=runner.AcceptanceResult).run(suite)
        return runner.summarize(result)

    def test_only_three_successes_are_accepted(self):
        self.assertTrue(runner.accepted(self.execute_cases()))
        for count in (0, 1, 2):
            with self.subTest(count=count):
                self.assertFalse(runner.accepted(self.execute_cases(count=count)))

    def test_skip_failure_error_and_wrong_names_cannot_pass(self):
        for behavior in (
            lambda case: case.skipTest("missing Blender"),
            lambda case: case.fail("original geometry assertion"),
            lambda case: 1 / 0,
        ):
            with self.subTest(behavior=behavior):
                self.assertFalse(runner.accepted(self.execute_cases(behavior)))
        wrong = self.execute_cases()
        wrong["names"] = ["different_test"] * 3
        self.assertFalse(runner.accepted(wrong))
        for category in ("expected_failures", "unexpected_successes"):
            wrong = self.execute_cases()
            wrong[category] = ["unexpected outcome"]
            self.assertFalse(runner.accepted(wrong))

    def test_compiler_failure_diagnostics_are_preserved(self):
        def failure(case):
            raise subprocess.CalledProcessError(1, ["csc.exe"], output=b"compiler diagnostic", stderr=b"compiler error")

        result = self.execute_cases(failure)
        self.assertFalse(runner.accepted(result))
        self.assertIn("compiler diagnostic", result["errors"][0]["traceback"])
        self.assertIn("compiler error", result["errors"][0]["traceback"])

    def test_isolated_environment_does_not_inherit_credentials_or_profiles(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            with patch.dict(
                os.environ, {"OPENAI_API_KEY": "sentinel", "GH_TOKEN": "sentinel", "HOME": "/private/host"}
            ):
                env = runner.isolated_environment(directory, directory / "blender.exe")
            self.assertNotIn("OPENAI_API_KEY", env)
            self.assertNotIn("GH_TOKEN", env)
            for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "BLENDER_USER_CONFIG"):
                self.assertTrue(Path(env[key]).is_relative_to(directory))
                self.assertTrue(Path(env[key]).is_dir())

    def test_preflight_failure_writes_nonzero_report_without_launching(self):
        with tempfile.TemporaryDirectory() as name:
            output = Path(name) / "evidence"
            with (
                patch.object(runner, "source_evidence", return_value={"revision": "fixture"}),
                patch.object(runner, "preflight", side_effect=RuntimeError("compiler missing")),
                patch.object(runner, "run_owned_worker") as launch,
            ):
                self.assertEqual(runner.run(Path(name) / "blender.exe", output), 1)
            launch.assert_not_called()
            report = json.loads((output / "result.json").read_text())
            self.assertFalse(report["success"])
            self.assertIn("compiler missing", "".join(report["diagnostics"]))
            self.assertTrue(report["cleanup"]["temporary_removed"])

    def test_timeout_cleans_private_directory_and_preserves_partial_evidence(self):
        with tempfile.TemporaryDirectory() as name:
            output = Path(name) / "evidence"
            created = []

            def fail(blender, output, environment, report):
                temporary = Path(environment["HOME"]).parent
                created.append(temporary)
                (Path(environment["TEMP"]) / "builder.stderr").write_text("original builder diagnostic")
                report["cleanup"]["processes_quiet"] = True
                raise subprocess.TimeoutExpired("owned worker", runner.TIMEOUT)

            with (
                patch.object(runner, "source_evidence", return_value={"revision": "fixture"}),
                patch.object(runner, "preflight"),
                patch.object(runner, "run_owned_worker", side_effect=fail),
            ):
                self.assertEqual(runner.run(Path(name) / "blender.exe", output), 1)
            self.assertEqual(len(created), 1)
            self.assertFalse(created[0].exists())
            report = json.loads((output / "result.json").read_text())
            self.assertFalse(report["success"])
            self.assertTrue(report["cleanup"]["temporary_removed"])
            self.assertIn("TimeoutExpired", "".join(report["diagnostics"]))
            saved = output / "interrupted-fixtures/temp/builder.stderr"
            self.assertEqual(saved.read_text(), "original builder diagnostic")
            self.assertIn(saved.relative_to(output).as_posix(), [item["path"] for item in report["artifacts"]])

    def test_job_timeout_quiesces_and_closes_without_hiding_original_error(self):
        with tempfile.TemporaryDirectory() as name:
            sys_path = str(runner.ROOT / "tools")
            sys.path.insert(0, sys_path)
            from editor_provenance_process import WindowsJob

            report = dict(diagnostics=[], cleanup={})
            with (
                patch.object(WindowsJob, "__init__", return_value=None),
                patch.object(WindowsJob, "spawn") as spawn,
                patch.object(WindowsJob, "quiesce", return_value=True) as quiet,
                patch.object(WindowsJob, "close") as close,
            ):
                spawn.return_value.wait.side_effect = [subprocess.TimeoutExpired("worker", 1), 143]
                with self.assertRaises(subprocess.TimeoutExpired):
                    runner.run_owned_worker(Path(name) / "blender.exe", Path(name), {}, report)
            quiet.assert_called_once()
            close.assert_called_once()
            self.assertTrue(report["cleanup"]["processes_quiet"])
            self.assertTrue(report["diagnostics"])

    def test_worker_rejects_wrong_blender_version_before_loading_original_tests(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            executable = folder / "blender.exe"
            executable.write_bytes(b"version fixture")
            version = subprocess.CompletedProcess([], 0, b"Blender 4.5.10\n", b"")
            with (
                patch.object(runner, "preflight", return_value=executable),
                patch.object(runner.subprocess, "run", return_value=version),
            ):
                self.assertEqual(runner.worker(executable, folder), 1)
            report = json.loads((folder / "worker-result.json").read_text())
            self.assertFalse(report["success"])
            self.assertNotIn("tests", report)
            self.assertEqual(report["runtime"]["version"], "Blender 4.5.10\n")

    def test_official_lts_header_reaches_test_fixture(self):
        class Fixture(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                raise RuntimeError("original fixture reached")

        for test_name in runner.TEST_NAMES:
            setattr(Fixture, test_name, lambda self: None)
        module = types.ModuleType("test_sculpt_provider")
        setattr(module, "SculptTests", Fixture)
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            executable = folder / "blender.exe"
            executable.write_bytes(b"version fixture")
            version = subprocess.CompletedProcess([], 0, b"Blender 4.5.11 LTS\r\n\tbuild hash: 4db51e9d1e1e\r\n", b"")
            with (
                patch.object(runner, "preflight", return_value=executable),
                patch.object(runner.subprocess, "run", return_value=version),
                patch.dict(sys.modules, {"test_sculpt_provider": module}),
            ):
                self.assertEqual(runner.worker(executable, folder), 1)
            report = json.loads((folder / "worker-result.json").read_text())
            self.assertIn("original fixture reached", report["tests"]["errors"][0]["traceback"])
            self.assertFalse(report["success"])

    def test_ci_bootstrap_evidence_is_preserved(self):
        with tempfile.TemporaryDirectory() as name:
            output = Path(name)
            for filename in ("runtime-download.json", "execution-scope.json", "runner.log"):
                (output / filename).write_text("bootstrap")
            with (
                patch.object(runner, "source_evidence", return_value={"revision": "fixture"}),
                patch.object(runner, "preflight", side_effect=RuntimeError("real preflight reached")),
            ):
                self.assertEqual(runner.run(output / "blender.exe", output), 1)
            report = json.loads((output / "result.json").read_text())
            self.assertIn("real preflight reached", "".join(report["diagnostics"]))
            self.assertEqual((output / "runtime-download.json").read_text(), "bootstrap")
            self.assertEqual(report["externally_finalized_artifacts"], ["runner.log"])
            self.assertNotIn("runner.log", [item["path"] for item in report["artifacts"]])

    def test_cleanup_failure_cannot_turn_three_passes_into_success(self):
        with tempfile.TemporaryDirectory() as name:
            output = Path(name) / "evidence"
            created = []

            def success(blender, output, environment, report):
                created.append(Path(environment["HOME"]).parent)
                report["cleanup"]["processes_quiet"] = True
                report["worker_returncode"] = 0
                runner.write_json(output / "worker-result.json", dict(success=True, tests=self.execute_cases()))

            try:
                with (
                    patch.object(runner, "source_evidence", return_value={"revision": "fixture"}),
                    patch.object(runner, "preflight"),
                    patch.object(runner, "run_owned_worker", side_effect=success),
                    patch.object(runner, "remove_temporary", side_effect=OSError("cleanup denied")),
                ):
                    self.assertEqual(runner.run(Path(name) / "blender.exe", output), 1)
                report = json.loads((output / "result.json").read_text())
                self.assertFalse(report["success"])
                self.assertFalse(report["cleanup"]["temporary_removed"])
                self.assertEqual(report["cleanup"]["retained_temporary_directory"], str(created[0]))
            finally:
                for path in created:
                    runner.remove_temporary(path)


if __name__ == "__main__":
    unittest.main()
