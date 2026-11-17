"""Provider boundary validation only; actual model evidence lives in runtime."""

import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import test_motion
from extensions import NodeRegistry, validate_invocation
from motion import publish
from motion_jobs import alive, exclusive, process_identity, process_state, write_new
from motion_provider import MotionProvider, register


class MotionBoundaryTests(unittest.TestCase):
    def test_unsupported_image_context_is_rejected(self):
        registry = NodeRegistry()
        register(registry)
        request = {
            "node": "text_to_motion",
            "version": "1",
            "inputs": {},
            "parameters": {"prompt": "walk"},
            "context": [
                {
                    "artifact": {"id": "image", "revision": "1"},
                    "role": "style",
                    "scope": "generation",
                    "strength": "reference",
                }
            ],
        }
        manifest = {
            "schema_version": 1,
            "artifacts": [{"id": "image", "revision": "1", "type": "image", "payload": {}}],
        }
        provider = {
            "id": "contract",
            "version": "1",
            "model": "contract",
            "model_version": "1",
            "available": True,
            "capabilities": ["text_to_motion", "video_to_motion"],
            "context_types": ["text"],
        }
        with self.assertRaisesRegex(ValueError, "unsupported context type"):
            validate_invocation(registry, request, manifest, provider)


class MotionLockTests(unittest.TestCase):
    def test_existing_lock_file_content_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "job.lock"
            path.write_bytes(b"existing lock marker")
            with exclusive(path):
                pass
            self.assertEqual(path.read_bytes(), b"existing lock marker")

    def test_empty_file_lock_preserves_size_and_nonblocking_conflict(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "job.lock"
            with exclusive(path):
                self.assertEqual(path.stat().st_size, 0)
                with self.assertRaises(BlockingIOError):
                    with exclusive(path, blocking=False):
                        self.fail("The second handle acquired an exclusive lock")
            with exclusive(path, blocking=False):
                self.assertEqual(path.stat().st_size, 0)
            path.unlink()

    def test_empty_file_lock_excludes_another_process(self):
        code = (
            "import sys\n"
            "from pathlib import Path\n"
            "from motion_jobs import exclusive\n"
            "with exclusive(sys.argv[1]):\n"
            "    Path(sys.argv[2]).write_text('locked', encoding='utf-8')\n"
            "    sys.stdin.read(1)\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "job.lock"
            ready = Path(temporary) / "ready"
            child = subprocess.Popen(
                [sys.executable, "-c", code, str(path), str(ready)],
                cwd=Path(__file__).resolve().parent,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                deadline = time.monotonic() + 10
                while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(ready.exists(), "Child did not acquire the lock")
                self.assertEqual(path.stat().st_size, 0)
                with self.assertRaises(BlockingIOError):
                    with exclusive(path, blocking=False):
                        self.fail("Another process acquired the held lock")
            finally:
                try:
                    _, error = child.communicate("x", timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    _, error = child.communicate(timeout=10)
            self.assertEqual(child.returncode, 0, error)
            with exclusive(path, blocking=False):
                pass
            path.unlink()

    def test_waiter_opened_empty_file_before_holder_does_not_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "job.lock"
            waiter_opened = threading.Event()
            holder_acquired = threading.Event()
            waiter_progress = threading.Event()
            streams = []
            entered = []
            errors = []
            original_open = open
            original_sleep = time.sleep

            def controlled_open(*args, **kwargs):
                stream = original_open(*args, **kwargs)
                streams.append(stream)
                if threading.current_thread().name == "motion-lock-waiter":
                    waiter_opened.set()
                    if not holder_acquired.wait(10):
                        stream.close()
                        raise TimeoutError("holder did not acquire the empty file")
                return stream

            def controlled_sleep(seconds):
                if threading.current_thread().name == "motion-lock-waiter":
                    waiter_progress.set()
                original_sleep(seconds)

            def waiter():
                try:
                    with exclusive(path):
                        entered.append("waiter")
                except BaseException as error:
                    errors.append(error)
                finally:
                    waiter_progress.set()

            def holder():
                try:
                    with exclusive(path):
                        entered.append("holder")
                        holder_acquired.set()
                        if not waiter_progress.wait(10):
                            raise TimeoutError("waiter did not attempt the held lock")
                except BaseException as error:
                    errors.append(error)

            first = threading.Thread(target=waiter, name="motion-lock-waiter")
            second = threading.Thread(target=holder, name="motion-lock-holder")
            try:
                with (
                    patch("motion_jobs.open", side_effect=controlled_open, create=True),
                    patch("motion_jobs.time.sleep", side_effect=controlled_sleep),
                ):
                    first.start()
                    self.assertTrue(waiter_opened.wait(10))
                    second.start()
                    first.join(15)
                    second.join(15)
                    self.assertFalse(first.is_alive())
                    self.assertFalse(second.is_alive())
                self.assertEqual(errors, [])
                self.assertEqual(entered, ["holder", "waiter"])
                self.assertTrue(all(stream.closed for stream in streams))
                self.assertEqual(path.stat().st_size, 0)
                path.unlink()
            finally:
                holder_acquired.set()
                waiter_progress.set()
                if first.ident is not None:
                    first.join(15)
                if second.ident is not None:
                    second.join(15)
                for stream in streams:
                    stream.close()

    def test_body_exception_releases_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "job.lock"
            with self.assertRaisesRegex(RuntimeError, "body failure"):
                with exclusive(path):
                    raise RuntimeError("body failure")
            with exclusive(path, blocking=False):
                pass
            path.unlink()

    def test_unlock_exception_still_closes_handle(self):
        if os.name == "nt":
            import msvcrt as lock_module

            lock_name, unlock = "locking", lock_module.LK_UNLCK
        else:
            import fcntl as lock_module

            lock_name, unlock = "flock", lock_module.LOCK_UN
        original_lock = getattr(lock_module, lock_name)
        original_open = open
        streams = []

        def controlled_open(*args, **kwargs):
            stream = original_open(*args, **kwargs)
            streams.append(stream)
            return stream

        def fail_unlock(descriptor, mode, *args):
            if mode == unlock:
                raise OSError("unlock failure")
            return original_lock(descriptor, mode, *args)

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "job.lock"
            try:
                with (
                    patch("motion_jobs.open", side_effect=controlled_open, create=True),
                    patch.object(lock_module, lock_name, side_effect=fail_unlock),
                    self.assertRaisesRegex(OSError, "unlock failure"),
                ):
                    with exclusive(path):
                        pass
                self.assertTrue(all(stream.closed for stream in streams))
                with exclusive(path, blocking=False):
                    pass
                path.unlink()
            finally:
                for stream in streams:
                    stream.close()


class MotionRecoveryTests(unittest.TestCase):
    """Explicit fault injection; synthetic documents are not model evidence."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.provider = MotionProvider.__new__(MotionProvider)
        self.provider.storage = Path(self.tmp.name)
        self.provider.config = {}
        self.provider.fingerprint = "fixture"
        self.provider.model_version = "fixture"
        self.key = "a" * 64
        self.request = {
            "node": "text_to_motion",
            "version": "1",
            "inputs": {},
            "parameters": {"prompt": "contract fixture"},
            "context": [],
        }
        self.manifest = {"schema_version": 1, "artifacts": []}

    def tearDown(self):
        self.tmp.cleanup()

    def test_os_identity_is_live_and_pid_reuse_is_rejected(self):
        identity = process_identity(os.getpid())
        self.assertTrue(alive(identity))
        self.assertFalse(alive(dict(identity, created="wrong-creation-identity")))

    def test_actual_child_identity_and_exit_recovery(self):
        directory = self.provider.storage / self.key
        directory.mkdir()
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            identity = process_identity(child.pid)
            self.assertIsNotNone(identity)
            write_new(directory / "model-process.json", {"process": identity})
            self.assertEqual(self.provider.poll(self.key)["state"], "running")
            self.assertEqual(self.provider.lookup(self.key)["state"], "running")
            self.assertEqual(process_state(dict(identity, created="reused")), "dead")
        finally:
            child.kill()
            child.wait(timeout=5)
        self.assertEqual(process_state(identity), "dead")
        self.assertEqual(self.provider.poll(self.key)["state"], "failed")
        self.assertEqual(self.provider.lookup(self.key)["state"], "failed")

    def test_identity_unavailable_stays_unknown_without_replay(self):
        directory = self.provider.storage / self.key
        directory.mkdir()
        write_new(directory / "model-process.json", {"process": process_identity(os.getpid())})
        with (
            patch("motion_jobs.process_identity", return_value=None),
            patch("motion_provider.subprocess.Popen") as spawn,
        ):
            with self.assertRaisesRegex(ValueError, "reconciliation_required"):
                self.provider.poll(self.key)
            self.assertFalse((directory / "receipt.json").exists())
            spawn.assert_not_called()
        self.assertEqual(process_state(None), "unknown")
        self.assertEqual(process_state({"pid": -1, "created": "invalid"}), "unknown")

    def test_intent_interruption_requires_reconciliation_without_replay(self):
        def interrupted(path, value):
            if path.name == "config.json":
                raise RuntimeError("injected crash after durable intent")
            return write_new(path, value)

        with (
            patch("motion_provider.write_new", side_effect=interrupted),
            patch("motion_provider.subprocess.Popen") as spawn,
        ):
            with self.assertRaises(RuntimeError):
                self.provider.submit(self.request, self.manifest, self.key)
            with self.assertRaisesRegex(ValueError, "reconciliation_required"):
                self.provider.submit(self.request, self.manifest, self.key)
            spawn.assert_not_called()

    def test_concurrent_same_key_launches_once(self):
        with patch("motion_provider.subprocess.Popen", return_value=SimpleNamespace(pid=os.getpid())) as spawn:
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(
                    pool.map(lambda _: self.provider.submit(self.request, self.manifest, self.key), range(4))
                )
            self.assertEqual(spawn.call_count, 1)
            self.assertTrue(all(r["state"] == "running" for r in results))

    def test_result_before_receipt_recovers_and_terminal_is_immutable(self):
        directory = self.provider.storage / self.key
        directory.mkdir()
        write_new(
            directory / "intent.json",
            {"request": self.request, "manifest": self.manifest, "provider": self.provider.describe()},
        )
        publish(test_motion.MotionContractTests().document(), directory / "motion.json")

        def interrupted(path, value):
            if path.name == "receipt.json":
                raise RuntimeError("injected crash before receipt")
            return write_new(path, value)

        with patch("motion_provider.write_new", side_effect=interrupted):
            with self.assertRaises(RuntimeError):
                self.provider.lookup(self.key)
        result = self.provider.lookup(self.key)
        self.assertEqual(result["state"], "succeeded")
        before = (directory / "receipt.json").read_bytes()
        self.assertEqual(self.provider.lookup(self.key), result)
        self.assertEqual(self.provider.cancel(self.key), result)
        self.assertEqual(before, (directory / "receipt.json").read_bytes())

    def test_video_result_cannot_change_invocation_source_revision(self):
        directory = self.provider.storage / self.key
        directory.mkdir()
        request = dict(self.request, node="video_to_motion", inputs={"source": {"id": "video", "revision": "0" * 64}})
        write_new(
            directory / "intent.json",
            {"request": request, "manifest": self.manifest, "provider": self.provider.describe()},
        )
        document = test_motion.MotionContractTests().document()
        document["provenance"]["input_sha256"] = "1" * 64
        publish(document, directory / "motion.json")
        with self.assertRaisesRegex(ValueError, "differs from invocation source"):
            self.provider.lookup(self.key)
        self.assertFalse((directory / "receipt.json").exists())


if __name__ == "__main__":
    unittest.main()
