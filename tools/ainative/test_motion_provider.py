"""Provider boundary validation only; actual model evidence lives in runtime."""

import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import test_motion
from extensions import NodeRegistry, validate_invocation
from motion import publish
from motion_jobs import alive, process_identity, process_state, write_new
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
