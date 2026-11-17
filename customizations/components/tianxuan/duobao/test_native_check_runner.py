"""Actual isolated local commands; no models, network or production deployment."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from native_check_runner import NativeCheckRunner
from native_evidence import EvidenceCache
from native_release import NativeRelease
from native_store import Conflict, NativeStore, NativeStoreError


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="native-run-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.python = str(Path(sys.executable).resolve(strict=True))
        self.store = NativeStore(self.root / "native.sqlite")
        self.cache = EvidenceCache(
            self.store,
            {"check": {"version": "v1", "reads": None, "max_age_seconds": 3600}},
            lambda t, a, c, action: t == "test" and a == "runner",
        )
        self.candidate = self.make_candidate("first")
        self.registry = {
            "check": dict(
                argv=[
                    self.python,
                    "-c",
                    "import os,pathlib; assert pathlib.Path.cwd() == pathlib.Path(os.environ['DUOBAO_OUTPUT']); print('actual check')",
                ],
                env={k: v for k, v in os.environ.items() if k in {"SystemRoot", "WINDIR"}},
                toolchain="a" * 64,
                environment="b" * 64,
                timeout=3,
                log_bytes=4096,
            )
        }

    def make_candidate(self, key):
        revisions = self.store.submit(
            "test",
            "producer",
            key,
            [dict(module="core", base=self.store.head("test", "core"), reads=[], edits={"code": key.encode()})],
        )["revisions"]
        return self.store.compose("test", revisions)["id"]

    def runner(self, code=None, timeout=3, limit=4096):
        if code is not None:
            self.registry["check"]["argv"] = [self.python, "-c", code]
        self.registry["check"].update(timeout=timeout, log_bytes=limit)
        return NativeCheckRunner(
            self.cache,
            self.root,
            self.registry,
            lambda t, a, c, action: t == "test" and a == "runner",
            lambda c, s: Path(s["argv"][0]).is_file(),
        )

    def run_check(self, runner, key="run", **kwargs):
        return runner.execute("test", "runner", key, self.candidate, "check", **kwargs)

    def test_real_success_cache_restart_release_and_revocation(self):
        runner = self.runner()
        first = self.run_check(runner)
        self.assertEqual(first["outcome"], "passed")
        self.assertEqual(first["exit_code"], 0)
        self.assertIn(b"actual check", base64.b64decode(json.loads(first["log"])["output_base64"]))
        self.assertEqual(self.run_check(self.runner()), first)
        cached = self.run_check(runner, "second")
        self.assertEqual(cached["state"], "cached")
        self.assertEqual(cached["evidence"], first["evidence"])
        release = NativeRelease(
            self.cache,
            lambda db, t, a, p, action: t == "test" and a in {"reviewer", "publisher", "runner"},
            lambda db, t, c: {"producer"},
        )
        release.configure(
            "test",
            "publisher",
            "product",
            dict(checks={"check": runner.context("check", self.candidate)}, review_max_age_seconds=60),
        )
        review = release.approve(
            "test",
            "reviewer",
            "review",
            "product",
            self.candidate,
            {"check": first["evidence"]},
            "Test reviewer inspected actual execution",
        )
        published = release.publish("test", "publisher", "publish", "product", "test", review["id"], None)
        self.assertEqual(published["candidate"], self.candidate)
        self.cache.revoke("test", "runner", first["evidence"], "test revocation")
        self.assertEqual(self.run_check(runner, "third")["state"], "complete")

    def test_policy_change_during_process_cannot_relabel_result(self):
        runner = self.runner(
            "import os,pathlib,time; pathlib.Path(os.environ['DUOBAO_OUTPUT'],'started').write_text('yes'); time.sleep(0.5)"
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.run_check, runner)
            deadline = time.monotonic() + 5
            while not list(self.root.glob("native-check-*/output/started")):
                if time.monotonic() > deadline:
                    self.fail("Process did not start")
                time.sleep(0.01)
            self.cache.policies["check"]["version"] = "v2"
            with self.assertRaises(Conflict):
                future.result()
        self.assertIsNone(self.cache.lookup("test", self.candidate, "check", **runner.context("check", self.candidate)))
        self.assertEqual(runner.status("test", "runner", "run")["state"], "result")

    def test_policy_change_at_evidence_writeback_is_rejected(self):
        runner = self.runner()
        original = self.cache.record

        def changed(*args, **kwargs):
            self.cache.policies["check"]["version"] = "v2"
            return original(*args, **kwargs)

        with patch.object(self.cache, "record", changed), self.assertRaises(Conflict):
            self.run_check(runner)
        with self.store._connection() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM native_check_evidence").fetchone()[0], 0)
        # Restoring the original installation can recover the durable result,
        # without invoking a second subprocess.
        self.cache.policies["check"]["version"] = "v1"
        with patch.object(runner.helper, "run_owned", side_effect=AssertionError("duplicate execution")):
            self.assertEqual(self.run_check(runner)["state"], "complete")

    def test_binding_policy_snapshot_cannot_mix_scope_and_version(self):
        original = self.store._revision
        before = self.cache.binding("test", self.candidate, "check", **self.runner().context("check", self.candidate))

        def changed(*args, **kwargs):
            self.cache.policies["check"]["version"] = "v2"
            return original(*args, **kwargs)

        with patch.object(self.store, "_revision", changed):
            observed = self.cache.binding(
                "test", self.candidate, "check", **self.runner().context("check", self.candidate)
            )
        self.assertEqual(observed, before)

    def test_policy_change_at_cache_hit_cannot_change_reserved_binding(self):
        runner = self.runner()
        self.cache.policies["check"]["version"] = "v2"
        self.cache.record(
            "test",
            "runner",
            "prewarm",
            self.candidate,
            "check",
            **runner.context("check", self.candidate),
            outcome="passed",
            log=b"existing v2 fact",
        )
        self.cache.policies["check"]["version"] = "v1"
        original = self.cache.lookup

        def changed(*args, **kwargs):
            self.cache.policies["check"]["version"] = "v2"
            return original(*args, **kwargs)

        with patch.object(self.cache, "lookup", changed), self.assertRaises(Conflict):
            self.run_check(runner)
        self.assertEqual(runner.status("test", "runner", "run")["state"], "held")

    def test_real_failures(self):
        for key, code, timeout, reason in [
            ("exit", "raise SystemExit(7)", 3, None),
            ("timeout", "import time; time.sleep(30)", 0.15, "timeout"),
            ("output", "print('x'*200000)", 3, "output"),
            (
                "pollution",
                "import os,pathlib; (pathlib.Path(os.environ['DUOBAO_INPUT'])/'core/code').write_text('bad')",
                3,
                "input_pollution",
            ),
        ]:
            with self.subTest(key=key):
                result = self.run_check(self.runner(code, timeout), key)
                self.assertEqual(result["outcome"], "failed")
                if reason:
                    self.assertIn(reason, result["reasons"])
                else:
                    self.assertEqual(result["exit_code"], 7)
                self.assertLessEqual((Path(result["workspace"]) / "process.log").stat().st_size, 4096)

    def test_scoped_input_timestamp_pollution_without_content_change(self):
        self.cache.policies["check"]["reads"] = {"core": ["code"]}
        runner = self.runner(
            "import os,pathlib; p=pathlib.Path(os.environ['DUOBAO_INPUT'])/'core/code'; "
            "s=p.stat(); os.utime(p,ns=(s.st_atime_ns,s.st_mtime_ns+1000000000))"
        )
        result = self.run_check(runner)
        self.assertEqual(result["outcome"], "failed")
        self.assertIn("input_pollution", result["reasons"])
        self.assertEqual((Path(result["workspace"]) / "input/core/code").read_bytes(), b"first")

    def test_concurrent_duplicate_and_native_submit(self):
        runner = self.runner(
            "import os,pathlib,time; pathlib.Path(os.environ['DUOBAO_OUTPUT'],'started').write_text('yes'); time.sleep(1)"
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            future = pool.submit(self.run_check, runner)
            deadline = time.monotonic() + 5
            while not list(self.root.glob("native-check-*/output/started")):
                if time.monotonic() > deadline:
                    self.fail("Process did not start")
                time.sleep(0.01)
            duplicate = self.run_check(self.runner())
            self.assertEqual(duplicate["state"], "running")
            self.make_candidate("independent")
            self.assertFalse(future.done(), "Native submit must finish while the check is still running")
            self.assertEqual(future.result()["outcome"], "passed")
            self.assertEqual(len(list(self.root.glob("native-check-*"))), 1)

    def test_unknown_crash_window_is_held_without_respawn(self):
        runner = self.runner()
        with patch.object(runner.helper, "run_owned", side_effect=SystemExit("simulated controller crash")):
            with self.assertRaises(SystemExit):
                self.run_check(runner)
        restarted = self.runner()
        with patch.object(restarted.helper, "run_owned", side_effect=AssertionError("must not respawn")):
            self.assertEqual(self.run_check(restarted)["state"], "running")

    def test_result_writeback_failure_recovers_without_respawn(self):
        runner = self.runner()
        original = self.cache.record

        def lost_receipt(*args, **kwargs):
            original(*args, **kwargs)
            raise OSError("receipt lost after commit")

        with patch.object(self.cache, "record", side_effect=lost_receipt):
            with self.assertRaises(OSError):
                self.run_check(runner)
        self.assertEqual(runner.status("test", "runner", "run")["state"], "result")
        restarted = self.runner()
        with patch.object(restarted.helper, "run_owned", side_effect=AssertionError("must not respawn")):
            self.assertEqual(self.run_check(restarted)["outcome"], "passed")
        with self.store._connection() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM native_check_evidence").fetchone()[0], 1)

    def test_authority_registry_and_input_invalidation(self):
        runner = self.runner()
        with self.assertRaises(NativeStoreError):
            runner.execute("test", "intruder", "bad", self.candidate, "check")
        self.run_check(runner)
        self.registry["check"]["environment"] = "c" * 64
        changed = self.runner()
        with self.assertRaises(Conflict):
            self.run_check(changed)
        self.assertEqual(self.run_check(changed, "changed")["state"], "complete")
        self.candidate = self.make_candidate("second-input")
        self.assertEqual(self.run_check(changed, "changed-input")["state"], "complete")
        with patch.object(changed, "verify_installation", return_value=False):
            with self.assertRaises(NativeStoreError):
                self.run_check(changed, "unverified")

    def test_tool_rule_expiry_and_binary_log_bounds(self):
        runner = self.runner()
        self.run_check(runner)
        self.registry["check"]["toolchain"] = "d" * 64
        tool = self.runner()
        self.assertEqual(self.run_check(tool, "tool-change")["state"], "complete")
        self.cache.policies["check"]["version"] = "v2"
        self.assertEqual(self.run_check(tool, "rule-change")["state"], "complete")
        original_clock = self.cache.clock
        self.cache.clock = lambda: original_clock() + 4000
        self.assertEqual(self.run_check(tool, "expired")["state"], "complete")
        binary = self.runner("import sys; sys.stdout.buffer.write(bytes([0,255])*400000)", limit=900000)
        result = self.run_check(binary, "binary")
        self.assertEqual(result["outcome"], "passed")
        self.assertLess(len(result["log"].encode()), 1048576)
        self.assertTrue(json.loads(result["log"])["transcript_truncated"])

    def test_distinct_commands_execute_in_parallel(self):
        long = self.runner(
            "import os,pathlib,time; pathlib.Path(os.environ['DUOBAO_OUTPUT'],'started').write_text('yes'); time.sleep(1.5)"
        )
        short = self.runner("print('independent')")
        with ThreadPoolExecutor(max_workers=2) as pool:
            future = pool.submit(self.run_check, long, "long")
            deadline = time.monotonic() + 5
            while not list(self.root.glob("native-check-*/output/started")):
                if time.monotonic() > deadline:
                    self.fail("Long command did not start")
                time.sleep(0.01)
            self.assertEqual(self.run_check(short, "short")["outcome"], "passed")
            self.assertFalse(future.done())
            self.assertEqual(future.result()["outcome"], "passed")

    @unittest.skipUnless(os.name == "nt", "Windows kill-on-close Job crash fixture")
    def test_actual_controller_restart_retains_unknown_run(self):
        runner = self.runner(
            "import os,pathlib,time; pathlib.Path(os.environ['DUOBAO_OUTPUT'],'started').write_text('yes'); time.sleep(30)",
            60,
        )
        program = """
import json,sys
from native_check_runner import NativeCheckRunner
from native_store import NativeStore
from native_evidence import EvidenceCache
store=NativeStore(sys.argv[1])
cache=EvidenceCache(store, {'check': {'version':'v1','reads':None,'max_age_seconds':3600}}, lambda t,a,c,op: t=='test' and a=='runner')
runner=NativeCheckRunner(cache, sys.argv[2], json.loads(sys.argv[3]), lambda t,a,c,op: t=='test' and a=='runner', lambda c,s: True)
runner.execute('test','runner','run',sys.argv[4],'check')
"""
        process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                program,
                str(self.root / "native.sqlite"),
                str(self.root),
                json.dumps(self.registry),
                self.candidate,
            ],
            cwd=Path(__file__).parent,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 5
            while not list(self.root.glob("native-check-*/output/started")):
                if time.monotonic() > deadline or process.poll() is not None:
                    self.fail("Controller did not start actual child")
                time.sleep(0.01)
            process.kill()
            process.wait(timeout=5)
            # The Windows Job dies with its owner. POSIX crashes retain ownership
            # for external reconciliation; do not create this fixture there.
            self.assertEqual(self.run_check(runner)["state"], "running")
            self.assertEqual(len(list(self.root.glob("native-check-*"))), 1)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)

    def test_cancel_and_timeout_descendants(self):
        marker = self.root / "late-marker"
        child = f"import time,pathlib; time.sleep(1); pathlib.Path({str(marker)!r}).write_text('escaped')"
        code = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(30)"
        runner = self.runner(code, 0.2)
        self.assertIn("timeout", self.run_check(runner)["reasons"])
        time.sleep(1.2)
        self.assertFalse(marker.exists())
        event = threading.Event()
        event.set()
        result = self.run_check(runner, "cancelled", cancel=event)
        self.assertEqual(result["outcome"], "failed")
        self.assertIn("cancelled", result["reasons"])


if __name__ == "__main__":
    unittest.main()
