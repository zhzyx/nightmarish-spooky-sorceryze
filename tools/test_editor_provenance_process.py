"""Portable ownership checks plus real Windows Job runtime acceptance.

The WindowsRuntimeTests class must run on a Windows worker; its skipped results
on other systems provide no Windows runtime evidence.
"""

import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

import editor_provenance_process as processes


class FakeAPI:
    def __init__(self):
        self.events = []
        self.count = 0

    def create(self, name):
        self.events.append(("create", name))
        return 123

    def assign(self, handle, child):
        self.events.append(("assign", handle, child.pid))
        self.count = 1

    def resume(self, child):
        self.events.append(("resume", child.pid))

    def active(self, handle):
        return self.count

    def terminate(self, handle):
        self.events.append(("terminate", handle))
        self.count = 0

    def close(self, handle):
        self.events.append(("close", handle))

    def open_query(self, name):
        self.events.append(("open", name))
        return 123


class OwnershipUnitTests(unittest.TestCase):
    def test_windows_abi_structures_have_expected_sizes(self):
        self.assertEqual(ctypes.sizeof(processes.THREADENTRY32), 28)
        self.assertEqual(ctypes.sizeof(processes.JOBOBJECT_BASIC_ACCOUNTING_INFORMATION), 48)
        if ctypes.sizeof(ctypes.c_void_p) == 8:
            self.assertEqual(ctypes.sizeof(processes.JOBOBJECT_EXTENDED_LIMIT_INFORMATION), 144)

    def test_spawn_is_suspended_and_assigned_before_resume(self):
        api = FakeAPI()
        child = mock.Mock(pid=456)
        with mock.patch.object(processes.subprocess, "Popen", return_value=child) as spawn:
            with processes.WindowsJob("1" * 32, api) as job:
                self.assertIs(job.spawn(["fixture", "arg"]), child)
                self.assertEqual(api.events[1:], [("assign", 123, 456), ("resume", 456)])
        self.assertEqual(spawn.call_args.kwargs["creationflags"], processes.CREATE_SUSPENDED)
        self.assertTrue(spawn.call_args.kwargs["close_fds"])
        self.assertEqual(api.events[-1], ("close", 123))

    def test_failed_assignment_kills_suspended_child_without_resuming(self):
        api = FakeAPI()
        child = mock.Mock(pid=456)
        child.poll.return_value = None
        api.assign = mock.Mock(side_effect=processes.ProcessError("assignment_failed"))
        with mock.patch.object(processes.subprocess, "Popen", return_value=child):
            with processes.WindowsJob("2" * 32, api) as job:
                with self.assertRaisesRegex(processes.ProcessError, "assignment_failed"):
                    job.spawn(["fixture"])
        child.kill.assert_called_once_with()
        child.wait.assert_called_once_with(timeout=5)
        self.assertFalse(any(event[0] == "resume" for event in api.events))

    def test_failed_resume_terminates_owned_job(self):
        api = FakeAPI()
        child = mock.Mock(pid=456)
        api.resume = mock.Mock(side_effect=processes.ProcessError("resume_failed"))
        with mock.patch.object(processes.subprocess, "Popen", return_value=child):
            with processes.WindowsJob("3" * 32, api) as job:
                with self.assertRaisesRegex(processes.ProcessError, "resume_failed"):
                    job.spawn(["fixture"])
        self.assertIn(("terminate", 123), api.events)
        child.kill.assert_not_called()

    def test_background_work_is_terminated_and_drain_confirmed(self):
        api = FakeAPI()
        with processes.WindowsJob("4" * 32, api) as job:
            api.count = 2
            self.assertTrue(job.quiesce())
            self.assertEqual(api.count, 0)
            self.assertFalse(job.quiesce())

    def test_recovery_only_queries_exact_private_job(self):
        api = FakeAPI()
        api.count = 1
        self.assertFalse(processes.job_is_quiet("5" * 32, api))
        self.assertEqual(api.events[0], ("open", processes.job_name("5" * 32)))
        self.assertNotIn(("terminate", 123), api.events)
        with self.assertRaisesRegex(processes.ProcessError, "job_name_invalid"):
            processes.job_is_quiet("arbitrary-job-name", api)


@unittest.skipUnless(os.name == "nt", "Real Windows Job runtime required; a skip is not acceptance")
class WindowsRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="provenance-job-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.token = uuid.uuid4().hex

    def wait_file(self, path):
        deadline = time.monotonic() + 8
        while not path.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(path.exists(), "owned child did not become ready")

    def test_real_suspended_assignment_resume_and_streams(self):
        with processes.WindowsJob(self.token) as job:
            child = job.spawn(
                [sys.executable, "-c", "import sys; print('job-out'); print('job-err',file=sys.stderr); sys.exit(7)"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            output, errors = child.communicate(timeout=8)
            self.assertEqual(child.returncode, 7)
            self.assertEqual(output.strip(), b"job-out")
            self.assertEqual(errors.strip(), b"job-err")
            self.assertFalse(job.quiesce())

    def test_real_leader_exit_does_not_leave_late_writer(self):
        late = self.root / "late-write"
        descendant = "from pathlib import Path; import time; time.sleep(.8); Path(" + repr(str(late)) + ").touch()"
        code = "import subprocess,sys; subprocess.Popen([sys.executable,'-c'," + repr(descendant) + "])"
        with processes.WindowsJob(self.token) as job:
            child = job.spawn([sys.executable, "-c", code])
            child.wait(timeout=8)
            self.assertEqual(child.returncode, 0)
            self.assertTrue(job.quiesce())
            self.assertEqual(job.api.active(job.handle), 0)
            time.sleep(0.9)
            self.assertFalse(late.exists())

    def test_real_cancel_terminates_child_and_grandchild(self):
        ready = self.root / "tree-ready"
        code = (
            "import subprocess,sys,time; from pathlib import Path; "
            "subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
            "Path(" + repr(str(ready)) + ").touch(); time.sleep(30)"
        )
        with processes.WindowsJob(self.token) as job:
            child = job.spawn([sys.executable, "-c", code])
            self.wait_file(ready)
            self.assertGreaterEqual(job.api.active(job.handle), 2)
            job.cancel()
            child.wait(timeout=8)
            self.assertEqual(job.api.active(job.handle), 0)

    def test_real_assignment_failure_never_executes_suspended_child(self):
        marker = self.root / "must-not-execute"
        with processes.WindowsJob(self.token) as job:
            with mock.patch.object(
                job.api, "assign", side_effect=processes.ProcessError("injected_assignment_failure")
            ):
                with self.assertRaisesRegex(processes.ProcessError, "injected_assignment_failure"):
                    job.spawn([
                        sys.executable,
                        "-c",
                        "from pathlib import Path; Path(" + repr(str(marker)) + ").touch()",
                    ])
            self.assertIsNotNone(job.child.poll())
            self.assertFalse(marker.exists())

    def test_real_wrapper_hardkill_closes_job_and_stops_entire_tree(self):
        ready = self.root / "wrapper-ready"
        worker = Path(processes.__file__).resolve().parent
        child_code = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); time.sleep(30)"
        code = (
            "import sys,time; from pathlib import Path; sys.path.insert(0," + repr(str(worker)) + "); "
            "from editor_provenance_process import WindowsJob; job=WindowsJob(" + repr(self.token) + "); "
            "job.spawn([sys.executable,'-c'," + repr(child_code) + "]); "
            "time.sleep(.3); Path(" + repr(str(ready)) + ").touch(); time.sleep(30)"
        )
        wrapper = subprocess.Popen([sys.executable, "-c", code])
        try:
            self.wait_file(ready)
            wrapper.kill()
            wrapper.wait(timeout=8)
            deadline = time.monotonic() + 8
            while not processes.job_is_quiet(self.token) and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(processes.job_is_quiet(self.token))
        finally:
            if wrapper.poll() is None:
                wrapper.kill()
                wrapper.wait(timeout=8)

    def test_real_guard_cancel_file_stops_job_tree_and_restores_source(self):
        import editor_provenance_guard as guard
        import test_editor_provenance_guard as fixtures

        fixture = fixtures.ProvenanceGuardTests("runTest")
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        marker = fixture.folder / "host-cancel-marker"
        ready = fixture.folder / "guard-child-ready"
        result_path = fixture.folder / "guard-job-result.json"
        late = fixture.folder / "descendant-must-not-write"
        descendant = (
            "from pathlib import Path; import time; time.sleep(.8); Path("
            + repr(str(late))
            + ").touch(); time.sleep(30)"
        )
        code = (
            "from pathlib import Path; import subprocess,sys,time; Path('design-docs/active-test.md').unlink(); "
            "subprocess.Popen([sys.executable,'-c'," + repr(descendant) + "]); "
            "Path(" + repr(str(ready)) + ").touch(); time.sleep(30)"
        )
        wrapper = subprocess.Popen(
            [
                sys.executable,
                str(Path(guard.__file__).resolve()),
                "--binding",
                str(fixture.binding),
                "--run",
                "--cancel-file",
                str(marker),
                "--result",
                str(result_path),
                "--",
                sys.executable,
                "-c",
                code,
            ],
            cwd=fixture.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            self.wait_file(ready)
            marker.touch()
            wrapper.communicate(timeout=12)
            self.assertEqual(wrapper.returncode, guard.EXIT_VIOLATION)
            self.assertEqual(fixture.doc.read_bytes(), fixture.before[fixture.doc])
            result = json.loads(result_path.read_text())
            self.assertTrue(result["cancelled"])
            self.assertFalse(result["ok"])
            self.assertTrue(processes.job_is_quiet(result["token"]))
            time.sleep(0.9)
            self.assertFalse(late.exists())
        finally:
            if wrapper.poll() is None:
                wrapper.kill()
                wrapper.communicate(timeout=8)


if __name__ == "__main__":
    unittest.main()
