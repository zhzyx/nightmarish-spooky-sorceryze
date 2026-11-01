import base64
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("editor_restart_watchdog", ROOT / "tools/editor_restart_watchdog.py")
watchdog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watchdog)

TOKEN = "a1b2c3d4e5f6"
# A process identifier that cannot be waited on, so the handoff starts at once.
DEAD_PID = 0x7FFFFFF0


def encode_editor_arguments(values):
    """Mirror the host: base64 of JSON, so no quote survives to be stripped."""
    return base64.b64encode(json.dumps(values).encode("utf-8")).decode("ascii")


# Mirrors OS_Windows::_quote_command_line_argument, including its inability to
# escape quotes that are already inside the value.
GODOT_QUOTED_CHARACTERS = set(" &()[]{}^=;!'+,`~")


def quote_like_godot(value):
    return f'"{value}"' if any(character in GODOT_QUOTED_CHARACTERS for character in value) else value


class Child:
    """Stand-in for the launched editor, with an explicit liveness decision."""

    def __init__(self, returncode=None):
        self.returncode = returncode

    def poll(self):
        return self.returncode


class Fixture:
    def __init__(self, directory):
        self.base = Path(directory)
        self.new = self.base / "godot.new.exe"
        self.old = self.base / "godot.old.exe"
        self.ack = self.base / "ack.json"
        self.report = self.base / "report.json"
        for executable in (self.new, self.old):
            executable.write_bytes(b"")
        self.launched = []

    def write_ack(self, token=TOKEN, executable=None, dock_ready=True):
        self.ack.write_text(json.dumps({
            "token": token,
            "dock_ready": dock_ready,
            "executable": str(executable or self.new),
        }), encoding="utf-8")

    def arguments(self, ack_timeout=1.0):
        return ["--new", str(self.new), "--old", str(self.old), "--ack", str(self.ack),
                "--report", str(self.report), "--token", TOKEN, "--wait-pid", str(DEAD_PID),
                "--ack-timeout", str(ack_timeout),
                # Editor arguments look like options, which is exactly why they
                # must survive the watchdog's own option parsing untouched.
                "--editor-args-b64", encode_editor_arguments(["--editor", "--path", str(self.base)])]

    def outcome(self):
        return json.loads(self.report.read_text(encoding="utf-8"))


class RestartWatchdogTests(unittest.TestCase):
    def run_watchdog(self, fixture, launcher, ack_timeout=1.0):
        with patch.object(watchdog, "launch", launcher), patch.object(watchdog, "ACK_POLL_SECONDS", 0.01):
            return watchdog.main(fixture.arguments(ack_timeout))

    def test_acknowledged_handoff_keeps_the_new_editor(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(directory)

            seen = []

            def launcher(executable, arguments):
                fixture.launched.append(Path(executable))
                seen.append(arguments)
                fixture.write_ack()
                return Child()

            code = self.run_watchdog(fixture, launcher)
            self.assertEqual(code, 0)
            self.assertEqual(fixture.launched, [fixture.new])
            self.assertEqual(seen, [["--editor", "--path", str(fixture.base)]])
            self.assertEqual(fixture.outcome()["status"], "started")

    def test_editor_that_dies_without_acknowledging_is_rolled_back(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(directory)
            # A leftover acknowledgement from an earlier handoff must not count.
            fixture.write_ack()

            def launcher(executable, arguments):
                fixture.launched.append(Path(executable))
                return Child(3 if Path(executable) == fixture.new else None)

            code = self.run_watchdog(fixture, launcher)
            self.assertEqual(code, 1)
            self.assertEqual(fixture.launched, [fixture.new, fixture.old])
            outcome = fixture.outcome()
            self.assertEqual(outcome["status"], "rolled_back")
            self.assertIn("exited with code 3", outcome["error"])

    def test_editor_without_a_working_dock_is_rolled_back(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(directory)

            def launcher(executable, arguments):
                fixture.launched.append(Path(executable))
                if Path(executable) != fixture.new:
                    return Child()
                # Started, but the AI dock never reported itself as usable.
                fixture.write_ack(dock_ready=False)
                return Child(1)

            self.assertEqual(self.run_watchdog(fixture, launcher), 1)
            self.assertEqual(fixture.launched, [fixture.new, fixture.old])
            self.assertEqual(fixture.outcome()["status"], "rolled_back")

    def test_acknowledgement_from_another_handoff_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(directory)

            def launcher(executable, arguments):
                fixture.launched.append(Path(executable))
                if Path(executable) != fixture.new:
                    return Child()
                fixture.write_ack(token="ffffffffffff")
                return Child(0)

            self.assertEqual(self.run_watchdog(fixture, launcher), 1)
            self.assertEqual(fixture.outcome()["status"], "rolled_back")

    def test_a_live_but_silent_editor_is_neither_killed_nor_duplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(directory)

            def launcher(executable, arguments):
                fixture.launched.append(Path(executable))
                return Child()  # Alive, and never acknowledges.

            self.assertEqual(self.run_watchdog(fixture, launcher, ack_timeout=0.2), 1)
            self.assertEqual(fixture.launched, [fixture.new])
            self.assertEqual(fixture.outcome()["status"], "startup_unconfirmed")

    def test_invalid_handoff_targets_never_start_anything(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(directory)

            def launcher(executable, arguments):
                raise AssertionError("A rejected handoff must not launch an editor")

            arguments = fixture.arguments()
            arguments[arguments.index("--old") + 1] = str(fixture.new)
            with patch.object(watchdog, "launch", launcher):
                self.assertEqual(watchdog.main(arguments), 1)
            self.assertEqual(fixture.outcome()["status"], "failed")
            missing = fixture.arguments()
            missing[missing.index("--new") + 1] = str(fixture.base / "absent.exe")
            with patch.object(watchdog, "launch", launcher):
                self.assertEqual(watchdog.main(missing), 1)
            self.assertEqual(fixture.outcome()["status"], "failed")

    def test_a_surviving_old_editor_blocks_the_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(directory)

            def launcher(executable, arguments):
                raise AssertionError("A second editor must not own the same project")

            arguments = fixture.arguments()
            arguments[arguments.index("--wait-pid") + 1] = str(os.getppid())
            arguments += ["--exit-timeout", "0.2"]
            with patch.object(watchdog, "launch", launcher), patch.object(watchdog, "process_is_running", lambda pid: True):
                self.assertEqual(watchdog.main(arguments), 1)
            self.assertEqual(fixture.outcome()["status"], "failed")

    def test_the_real_launcher_starts_a_detached_process(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "started.txt"
            child = watchdog.launch(sys.executable, ["-c", f"open({str(marker)!r}, 'w').write('ok')"])
            self.assertEqual(child.wait(timeout=60), 0)
            self.assertTrue(marker.is_file())

    def test_a_running_process_is_detected_without_being_signalled(self):
        self.assertTrue(watchdog.process_is_running(os.getppid()))
        self.assertFalse(watchdog.process_is_running(os.getpid()))
        self.assertFalse(watchdog.process_is_running(DEAD_PID))
        self.assertFalse(watchdog.process_is_running(-1))

    @unittest.skipUnless(os.name == "nt", "Reproduces Windows command-line quoting")
    def test_editor_arguments_survive_the_host_command_line(self):
        """The host spawns this watchdog through OS_Windows::create_process.

        That quoting never escapes inner quotes, so a bare JSON array arrived
        with its quotes stripped and the handoff died before writing a report.
        Encoding keeps the value free of anything the quoting can damage.
        """
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            old = base / "godot.old.exe"
            old.write_bytes(b"")
            ack = base / "ack.json"
            report = base / "report.json"
            # The launched "editor" is Python itself, so an intact argument list
            # is the only way the acknowledgement can ever appear.
            payload = json.dumps({"token": TOKEN, "dock_ready": True, "executable": sys.executable})
            editor_arguments = ["-c", f"open({str(ack)!r}, 'w', encoding='utf-8').write({payload!r})"]
            arguments = ["-u", str(ROOT / "tools/editor_restart_watchdog.py"),
                         "--new", sys.executable, "--old", str(old), "--ack", str(ack),
                         "--report", str(report), "--token", TOKEN, "--wait-pid", str(DEAD_PID),
                         "--ack-timeout", "60",
                         "--editor-args-b64", encode_editor_arguments(editor_arguments)]
            command = " ".join(quote_like_godot(value) for value in [sys.executable, *arguments])
            result = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace", timeout=180)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(report.is_file(), "the watchdog exited before reporting")
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["status"], "started")


class SelfBuildResumeCheckTests(unittest.TestCase):
    def setUp(self):
        build_spec = importlib.util.spec_from_file_location("editor_self_build", ROOT / "tools/editor_self_build.py")
        self.worker = importlib.util.module_from_spec(build_spec)
        build_spec.loader.exec_module(self.worker)

    def test_the_startup_check_demands_a_matching_acknowledgement(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            artifact = project / "godot.windows.editor.dev.x86_64.self_update_a.mono.exe"
            token = self.worker.write_resume_fixture(project, project / "current.exe", artifact)
            journal = json.loads((project / ".godot/editor/ai_chat_resume.json").read_text(encoding="utf-8"))
            self.assertTrue(journal["smoke_check"])
            self.assertEqual(journal["restart"]["token"], token)
            self.assertEqual(journal["restart"]["tool_call_id"], journal["tool_calls"][0]["id"])
            self.assertIn("never acknowledged", self.worker.resume_ack_error(project, token, artifact))
            ack = project / ".godot/editor/ai_chat_restart_ack.json"
            ack.write_text(json.dumps({"token": "other", "dock_ready": True, "executable": str(artifact)}), encoding="utf-8")
            self.assertIn("different handoff", self.worker.resume_ack_error(project, token, artifact))
            ack.write_text(json.dumps({"token": token, "dock_ready": False, "executable": str(artifact)}), encoding="utf-8")
            self.assertIn("different handoff", self.worker.resume_ack_error(project, token, artifact))
            ack.write_text(json.dumps({"token": token, "dock_ready": True, "executable": str(artifact)}), encoding="utf-8")
            # A journal that survives would be answered again on every later start.
            self.assertIn("did not consume", self.worker.resume_ack_error(project, token, artifact))
            (project / ".godot/editor/ai_chat_resume.json").unlink()
            self.assertEqual(self.worker.resume_ack_error(project, token, artifact), "")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    unittest.main()
