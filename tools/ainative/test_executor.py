"""Synthetic fault injection only. No actual model/API or geometry generation."""

import copy
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from executor import Executor, snapshot_file
from extensions import NodeRegistry


class SyntheticProvider:
    """External service stand-in retained across executor restarts."""

    def __init__(self):
        self.jobs = {}
        self.submits = 0
        self.lost_receipt = False
        self.fail = False
        self.lookup_enabled = True
        self.model_version = "1"
        self.entered = self.release = None

    def describe(self):
        return {
            "id": "synthetic",
            "version": "1",
            "model": "no-generation-fixture",
            "model_version": self.model_version,
            "available": True,
            "capabilities": ["echo"],
            "context_types": ["text", "image"],
        }

    def submit(self, request, manifest, idempotency_key):
        self.submits += 1
        job_id = idempotency_key
        self.jobs[job_id] = {"job_id": job_id, "state": "queued", "outputs": {}, "error": None}
        if self.entered:
            self.entered.set()
            self.release.wait(5)
        if self.lost_receipt:
            raise RuntimeError("secret-token-must-not-persist")
        return copy.deepcopy(self.jobs[job_id])

    def poll(self, job_id):
        if self.fail:
            return {"job_id": job_id, "state": "failed", "outputs": {}, "error": "secret-error"}
        return {
            "job_id": job_id,
            "state": "succeeded",
            "outputs": {"result": {"id": "out-" + job_id, "revision": "1"}},
            "error": None,
        }

    def result_manifest(self, job_id):
        return {
            "schema_version": 1,
            "artifacts": [{"id": "out-" + job_id, "revision": "1", "type": "image", "payload": {"synthetic": True}}],
        }

    def lookup(self, key):
        return copy.deepcopy(self.jobs.get(key)) if self.lookup_enabled else None

    def cancel(self, job_id):
        return None


def fixture():
    registry = NodeRegistry()
    registry.register({
        "id": "echo",
        "version": "1",
        "inputs": {"source": {"types": ["image"], "required": True}},
        "outputs": {"result": {"types": ["image"], "required": True}},
        "context_types": ["text", "image"],
        "parameters": {},
        "capabilities": ["echo"],
    })
    request = {
        "node": "echo",
        "version": "1",
        "inputs": {"source": {"id": "source", "revision": "1"}},
        "parameters": {},
        "context": [],
    }
    graph = [{"id": "first", "provider": "synthetic", "request": request, "links": {}}]
    manifest = {
        "schema_version": 1,
        "artifacts": [{"id": "source", "revision": "1", "type": "image", "payload": {"synthetic": True}}],
    }
    return registry, graph, manifest


def build_cli_fixture():
    """Explicit synthetic factory for subprocess bridge tests; never a real provider."""
    return fixture()[0], {"synthetic": SyntheticProvider()}


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.database = Path(self.tmp.name) / "jobs.sqlite"
        self.registry, self.graph, self.manifest = fixture()
        self.provider = SyntheticProvider()
        self.executor = self.open()

    def open(self):
        return Executor(self.database, self.registry, {"synthetic": self.provider})

    def tearDown(self):
        self.executor.close()
        self.tmp.cleanup()

    def create(self):
        return self.executor.create(self.graph, self.manifest)

    def finish(self, run):
        for _ in range(8):
            if self.executor.step(run)["state"] == "succeeded":
                return self.executor.export(run)
        self.fail("did not complete")

    def test_known_job_restart_and_cache(self):
        run = self.create()
        self.executor.step(run)
        self.executor.close()
        self.executor = self.open()
        self.assertTrue(self.finish(run)["manifest"]["artifacts"])
        self.finish(self.create())
        self.assertEqual(self.provider.submits, 1)

    def test_node_preview_is_immutable_and_cache_survives_target_run(self):
        second = copy.deepcopy(self.graph[0])
        second["id"] = "second"
        second["request"]["inputs"] = {}
        second["links"] = {"source": {"node": "first", "port": "result"}}
        self.graph.append(second)
        run = self.create()
        with self.assertRaisesRegex(ValueError, "successful result"):
            self.executor.export_node(run, "first")
        self.executor.step(run)
        self.executor.step(run)
        self.assertEqual(self.executor.status(run)["state"], "running")
        snapshot = self.executor.export_node(run, "first")
        self.finish(run)
        self.assertEqual(self.executor.export_node(run, "first")["outputs"], snapshot["outputs"])
        submits = self.provider.submits
        self.finish(self.create())
        self.assertEqual(self.provider.submits, submits)
        snapshot["manifest"]["artifacts"].clear()
        self.assertTrue(self.executor.export_node(run, "first")["manifest"]["artifacts"])
        self.executor.cancel(run)
        with self.assertRaisesRegex(ValueError, "cancelled"):
            self.executor.export_node(run, "first")

    def test_unknown_submission_reconcile_never_replays(self):
        self.provider.lost_receipt = True
        self.provider.lookup_enabled = False
        run = self.create()
        self.assertEqual(self.executor.step(run)["state"], "reconcile")
        self.executor.close()
        self.executor = self.open()
        for _ in range(3):
            self.assertEqual(self.executor.step(run)["state"], "reconcile")
        self.assertEqual(self.provider.submits, 1)
        self.provider.lookup_enabled = True
        self.finish(run)
        self.assertEqual(self.provider.submits, 1)
        self.assertNotIn("secret-token", str(self.executor.status(run)))

    def test_confirmed_failure_retry(self):
        run = self.create()
        self.provider.fail = True
        self.executor.step(run)
        self.assertEqual(self.executor.step(run)["state"], "failed")
        self.assertNotIn("secret-error", str(self.executor.status(run)))
        self.executor.retry(run, "first")
        self.provider.fail = False
        self.finish(run)
        self.assertEqual(self.provider.submits, 2)

    def test_dag_merge_and_cycle(self):
        second = copy.deepcopy(self.graph[0])
        second["id"] = "second"
        second["request"]["inputs"] = {}
        second["links"] = {"source": {"node": "first", "port": "result"}}
        self.graph.append(second)
        result = self.finish(self.create())
        self.assertEqual(len(result["outputs"]), 2)
        self.graph[0]["request"]["inputs"] = {}
        self.graph[0]["links"] = {"source": {"node": "second", "port": "result"}}
        with self.assertRaisesRegex(ValueError, "cycle"):
            self.create()

    def test_cancel_late_submit_and_concurrent_drive(self):
        run = self.create()
        self.provider.entered, self.provider.release = threading.Event(), threading.Event()
        errors = []

        def worker():
            executor = self.open()
            try:
                executor.step(run)
            except BaseException as exc:
                errors.append(exc)
            finally:
                executor.close()

        thread = threading.Thread(target=worker)
        thread.start()
        self.assertTrue(self.provider.entered.wait(3))
        self.executor.step(run)  # Lookup only; must not submit while original call runs.
        response = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("executor_cli.py")),
                "--db",
                str(self.database),
                "cancel",
                "--run",
                run,
            ],
            capture_output=True,
            text=True,
            timeout=4,
            check=True,
        )
        self.assertEqual(json.loads(response.stdout)["result"]["state"], "cancelled")
        self.provider.release.set()
        thread.join(5)
        self.assertFalse(errors)
        self.assertEqual(self.provider.submits, 1)
        self.assertEqual(self.executor.status(run)["state"], "cancelled")
        with self.assertRaises(ValueError):
            self.executor.export(run)
        self.assertEqual(self.executor.db.execute("SELECT count(*) FROM cache").fetchone()[0], 0)

    def test_invalid_results_not_cached(self):
        run = self.create()
        self.executor.step(run)
        self.provider.result_manifest = lambda job_id: {"schema_version": 1, "artifacts": []}
        self.executor.step(run)
        self.assertEqual(self.executor.status(run)["state"], "running")
        self.assertEqual(self.executor.db.execute("SELECT count(*) FROM cache").fetchone()[0], 0)
        self.assertEqual(self.provider.submits, 1)

    def test_immutable_and_content_model_context_invalidation(self):
        self.finish(self.create())
        self.manifest["artifacts"][0]["payload"]["synthetic"] = False
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.create()
        self.manifest["artifacts"][0]["revision"] = "2"
        self.graph[0]["request"]["inputs"]["source"]["revision"] = "2"
        self.finish(self.create())
        self.provider.model_version = "2"
        self.finish(self.create())
        self.graph[0]["request"]["context"] = [
            {"text": "changed", "role": "design", "scope": "all", "strength": "constraint"}
        ]
        self.finish(self.create())
        self.assertEqual(self.provider.submits, 4)

    def test_source_snapshots(self):
        source = Path(self.tmp.name) / "source.bin"
        source.write_bytes(b"one")
        first = snapshot_file(source)
        source.write_bytes(b"two")
        self.assertNotEqual(first, snapshot_file(source))
        self.manifest["artifacts"][0]["payload"] = first
        self.finish(self.create())
        self.manifest["artifacts"][0]["payload"] = snapshot_file(source)
        self.manifest["artifacts"][0]["revision"] = "2"
        self.graph[0]["request"]["inputs"]["source"]["revision"] = "2"
        self.finish(self.create())
        self.assertEqual(self.provider.submits, 2)
        self.manifest["artifacts"][0]["payload"] = {"uri": "source.bin"}
        with self.assertRaisesRegex(ValueError, "snapshot"):
            self.create()

    def test_malformed_receipt_and_remote_cancel(self):
        run = self.create()
        original = self.provider.submit
        self.provider.submit = lambda *args: {}
        self.assertEqual(self.executor.step(run)["state"], "reconcile")
        self.assertIsNone(self.executor.status(run)["nodes"]["first"]["job"])
        self.provider.submit = original
        run = self.create()
        self.executor.step(run)
        self.provider.poll = lambda job_id: {"job_id": job_id, "state": "cancelled", "outputs": {}, "error": None}
        self.assertEqual(self.executor.step(run)["state"], "cancelled")
        with self.assertRaises(ValueError):
            self.executor.export(run)

    def test_optional_link_rejected(self):
        definition = self.registry.get("echo", "1")
        definition["id"] = "optional"
        definition["outputs"]["result"]["required"] = False
        self.registry.register(definition)
        second = copy.deepcopy(self.graph[0])
        second["id"] = "second"
        second["request"]["inputs"] = {}
        second["links"] = {"source": {"node": "first", "port": "result"}}
        self.graph[0]["request"]["node"] = "optional"
        self.graph.append(second)
        with self.assertRaisesRegex(ValueError, "must be required"):
            self.create()

    def test_crash_after_external_acceptance(self):
        original = self.provider.submit

        def crash(*args):
            original(*args)
            raise SystemExit("simulated process death")

        self.provider.submit = crash
        run = self.create()
        with self.assertRaises(SystemExit):
            self.executor.step(run)
        self.executor.close()
        self.executor = self.open()
        self.finish(run)
        self.assertEqual(self.provider.submits, 1)

    def test_restart_definition_drift_blocks_known_job(self):
        run = self.create()
        self.executor.step(run)
        self.executor.close()
        definition = self.registry.get("echo", "1")
        definition["outputs"]["result"]["types"] = ["mesh"]
        self.registry = NodeRegistry()
        self.registry.register(definition)
        self.executor = self.open()
        status = self.executor.step(run)
        self.assertEqual(status["nodes"]["first"]["error"], "provider_operation_failed")
        self.assertEqual(status["nodes"]["first"]["job"]["state"], "queued")
        self.assertEqual(self.provider.submits, 1)
        self.assertEqual(self.executor.db.execute("SELECT count(*) FROM cache").fetchone()[0], 0)

    def test_profile_revision_invalidates_cache(self):
        self.manifest["artifacts"].append({
            "id": "profile",
            "revision": "1",
            "type": "skeleton_profile",
            "payload": {"synthetic": True, "axes": "Y"},
        })
        self.finish(self.create())
        self.manifest["artifacts"][-1]["revision"] = "2"
        self.manifest["artifacts"][-1]["payload"]["axes"] = "Z"
        self.finish(self.create())
        self.assertEqual(self.provider.submits, 2)

    def test_cli_cross_process_lifecycle(self):
        script = str(Path(__file__).with_name("executor_cli.py"))

        def call(command, run=None, payload=None, factory="does_not_exist:must_not_load"):
            args = [sys.executable, script, "--db", str(self.database), "--factory", factory, command]
            if run:
                args += ["--run", run]
            process = subprocess.run(
                args, input=json.dumps(payload) if payload else None, capture_output=True, text=True, timeout=5
            )
            return process.returncode, json.loads(process.stdout)

        code, created = call(
            "create",
            payload={"graph": self.graph, "manifest": self.manifest},
            factory="test_executor:build_cli_fixture",
        )
        self.assertEqual(code, 0)
        run = created["result"]["run_id"]
        self.assertEqual(call("step", run, factory="test_executor:build_cli_fixture")[0], 0)
        self.assertEqual(call("status", run)[1]["result"]["nodes"]["first"]["job"]["state"], "queued")
        self.assertEqual(
            call("step", run, factory="test_executor:build_cli_fixture")[1]["result"]["state"], "succeeded"
        )
        code, exported = call("export", run)
        self.assertEqual(code, 0)
        self.assertTrue(exported["result"]["outputs"]["first"]["result"]["id"])
        self.assertEqual(call("cancel", run)[1]["result"]["state"], "cancelled")
        code, failure = call("export", run)
        self.assertEqual(code, 1)
        self.assertEqual(failure, {"ok": False, "error": "executor_command_failed"})

    def test_immediate_success_conflict_preserves_known_job(self):
        original = self.provider.submit

        def immediate(*args):
            queued = original(*args)
            return {
                "job_id": queued["job_id"],
                "state": "succeeded",
                "error": None,
                "outputs": {"result": {"id": "source", "revision": "1"}},
            }

        self.provider.submit = immediate
        conflicting = copy.deepcopy(self.manifest)
        conflicting["artifacts"][0]["payload"] = {"synthetic": "conflicting"}
        self.provider.result_manifest = lambda job_id: conflicting
        status = self.executor.step(self.create())
        self.assertEqual(status["nodes"]["first"]["error"], "invalid_result")
        self.assertTrue(status["nodes"]["first"]["job"]["job_id"])
        self.assertEqual(self.executor.db.execute("SELECT count(*) FROM cache").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
