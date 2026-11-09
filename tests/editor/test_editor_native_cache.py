"""Native artifact publication and input selection checks, using disposable repositories."""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

import editor_native_cache as cache  # noqa: E402


class NativeCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "source"
        self.root.mkdir()
        self.store = self.base / "store"
        self.artifact = self.root / "bin/godot.windows.editor.x86_64.exe"
        self.console = self.artifact.with_suffix(".console.exe")
        self.outputs = [p.relative_to(self.root).as_posix() for p in (self.artifact, self.console)]
        self.artifact.parent.mkdir()
        self.test_script = self.root / "tests/editor/run_daqian_graph.py"
        self.test_script.parent.mkdir(parents=True)
        self.test_script.write_text("# validation")
        (self.root / ".gitignore").write_text("bin/\n*.inc\n.scons_node_count\n.scons_env.json\n")
        (self.root / "SConstruct").write_text("# fixture")
        self.native = self.root / "native.cpp"
        self.native.write_text("v1")
        self.git("init", "--quiet")
        self.git("add", ".")
        self.commit()
        self.sdk = self.base / "sdk"
        self.sdk.mkdir()
        self.cl = self.sdk / "cl.exe"
        self.cl.write_bytes(b"toolchain")
        self.probe = {
            "msvc": True,
            "unsupported": False,
            "sdk": ["14.4"],
            "git_info": {"git_hash": "", "git_timestamp": 0},
            "tools": {"CC": str(self.cl)},
            "native_sources": [],
            "generated_values": "fixture",
            "sources": [],
            "generated": self.outputs,
            "roots": [str(self.sdk)],
        }
        patcher = patch.object(cache, "probe", return_value=self.probe)
        patcher.start()
        self.addCleanup(patcher.stop)
        module = self.base / "scons" / "__init__.py"
        module.parent.mkdir()
        module.write_bytes(b"fixture")
        patcher = patch.dict(sys.modules, {"SCons": SimpleNamespace(__version__="fixture", __file__=str(module))})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.opts = dict(platform="windows", target="editor", arch="x86_64")
        self.env = {}
        self.runs = 0

    def git(self, *args):
        subprocess.run(["git", "-C", self.root, *args], check=True, capture_output=True)

    def commit(self):
        self.git("-c", "user.name=Test", "-c", "user.email=t@example.org", "commit", "-qam", "input")

    def produce(self):
        self.assertEqual(self.env[cache.REPRODUCIBLE], "1")
        self.runs += 1
        self.artifact.write_bytes(b"engine")
        self.console.write_bytes(b"launcher")

    def build(self, produce=None, **kwargs):
        return cache.build_or_reuse(
            self.root, self.opts, self.artifact, produce or self.produce, store=self.store, env=self.env, **kwargs
        )

    def test_hit_across_heads_materializes_both_outputs_and_fresh_provenance(self):
        self.env["CODEX_TOOL_CALL_ID"] = "producer"
        initial = self.build()
        self.assertEqual(initial["status"], "built")
        self.test_script.write_text("# new independent validation")
        self.commit()
        self.artifact.unlink()
        self.console.unlink()
        self.env["CODEX_TOOL_CALL_ID"] = "consumer"
        hit = self.build()
        self.assertEqual(hit["status"], "hit")
        self.assertEqual(hit["key"], initial["key"])
        self.assertEqual(hit["producer_head"], initial["consumer_head"])
        self.assertNotEqual(hit["producer_head"], hit["consumer_head"])
        self.assertEqual(hit["artifact_sha256"], cache.digest(self.artifact))
        self.assertEqual(self.console.read_bytes(), b"launcher")
        self.assertEqual(self.runs, 1)
        self.assertEqual(self.env, {"CODEX_TOOL_CALL_ID": "consumer"})

    def test_governance_and_external_package_edits_require_graph_evidence(self):
        detached = [
            "work-items.json",
            "design-docs/new-issue.md",
            "data-collection/requests/123.json",
            "editor/docks/daqian/issue_graph.gd",
            "tests/editor/daqian_layout.gd",
            "bin/gonggong-build-receipts/123.json",
        ]
        for name in detached:
            with self.subTest(name=name):
                self.assertTrue(cache.is_external_data(name, set()))
                self.assertFalse(cache.is_external_data(name, {name}))
        self.assertFalse(cache.is_external_data("data-collection/script.cpp", set()))
        self.assertFalse(cache.is_external_data("tests/cpp/test_foo.h", set()))

    def test_progress_file_changes_while_building(self):
        def produce():
            self.produce()
            (self.root / ".scons_node_count").write_text("1024")
            (self.root / ".scons_env.json").write_text("{}")
            (self.root / "bin/ui-report.json").write_text("{}")
            index = self.root / "bin/.vs/project/index"
            index.parent.mkdir(parents=True)
            index.write_bytes(b"IDE state")

        built = self.build(produce)
        self.assertEqual(built["status"], "built")
        self.assertEqual(self.build()["status"], "hit")
        self.probe["native_sources"] = [".scons_node_count"]
        self.assertNotEqual(cache.native_key(self.root, self.opts, self.artifact, self.env), built["key"])

    def test_generator_inputs_ignored_headers_toolchain_sdk_and_options_invalidate(self):
        def key():
            return cache.native_key(self.root, self.opts, self.artifact, self.env)

        observed = [key()]
        self.probe["native_sources"] = ["tests/editor/run_daqian_graph.py"]
        observed.append(key())
        self.test_script.write_text("# embedded now")
        observed.append(key())
        (self.root / "private.inc").write_text("#define X 1")
        observed.append(key())
        self.cl.write_bytes(b"new compiler")
        observed.append(key())
        (self.sdk / "sdk.h").write_text("new SDK")
        observed.append(key())
        self.opts["tests"] = "yes"
        observed.append(key())
        self.env["BUILD_NAME"] = "different"
        observed.append(key())
        self.assertEqual(len(observed), len(set(observed)))

    def test_cancellation_drift_failed_producer_do_not_publish(self):
        def drift():
            self.produce()
            self.native.write_text("drift")

        with self.assertRaisesRegex(ValueError, "inputs_changed"):
            self.build(drift)
        with self.assertRaises(RuntimeError):
            self.build(lambda: (_ for _ in ()).throw(RuntimeError("link failed")))

        def stop():
            self.produce()
            self.cancelled = True

        self.cancelled = False
        with self.assertRaises(InterruptedError):
            self.build(stop, cancelled=lambda: self.cancelled)
        self.assertFalse(any(p.is_dir() for p in self.store.iterdir()))
        self.assertEqual(self.build()["status"], "built")

    def test_scons_rebuilds_local_b_after_shared_a_restore(self):
        (self.root / "SConstruct").write_text(
            "import sys\n"
            f"sys.path.insert(0, {str(TOOLS)!r})\n"
            "from editor_native_cache import restored_target_dependencies\n"
            "env = Environment(tools=[])\n"
            "env.Decider('MD5-timestamp')\n"
            f"outputs = {self.outputs!r}\n"
            "for output in outputs:\n"
            "    env.Command(output, 'native.cpp', Copy('$TARGET', '$SOURCE'))\n"
            "restored_target_dependencies(env)\n"
            "Default(outputs)\n"
        )
        with (self.root / ".gitignore").open("a") as stream:
            stream.write(".sconsign*.dblite\n")

        def scons():
            result = subprocess.run(
                [sys.executable, "-m", "SCons", "-Q", "--max-drift=-1"],
                cwd=self.root,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout

        def source(version):
            self.native.write_bytes(version)
            timestamp = 1700000000 + 60 * version[0]
            os.utime(self.native, (timestamp, timestamp))

        source(b"A")
        self.assertEqual(self.build(scons)["status"], "built")
        source(b"B")
        scons()
        self.assertEqual(self.artifact.read_bytes(), b"B")
        for consumer in ("ordinary SCons", "shared miss"):
            with self.subTest(consumer=consumer):
                source(b"A")
                self.assertEqual(self.build(scons)["status"], "hit")
                self.assertEqual(self.artifact.read_bytes(), b"A")
                source(b"B")
                if consumer == "ordinary SCons":
                    scons()
                else:
                    receipt = self.build(scons)
                    self.assertEqual(receipt["status"], "built")
                    self.assertEqual((self.store / receipt["key"] / self.outputs[0]).read_bytes(), b"B")
                self.assertEqual(self.artifact.read_bytes(), b"B")
                self.assertEqual(self.console.read_bytes(), b"B")
                self.assertIn("up to date", scons())

    def test_corruption_quarantines_and_rebuilds(self):
        receipt = self.build()
        (self.store / receipt["key"] / self.outputs[1]).write_bytes(b"corrupt")
        self.assertEqual(self.build()["status"], "built")
        self.assertEqual(self.build()["status"], "hit")
        self.assertEqual(self.runs, 2)
        self.assertEqual(len(list(self.store.glob("*.corrupt-*"))), 1)

    def test_unknown_platform_falls_back_without_overriding_build_metadata(self):
        self.opts["platform"] = "macos"
        r = self.build(lambda: self.artifact.write_bytes(b"normal build"))
        self.assertEqual(r["status"], "uncached")
        self.assertFalse(self.store.exists())

    def test_two_worktrees_contend_for_single_producer(self):
        other = self.base / "second"
        self.git("worktree", "add", "-q", "--detach", str(other))
        script = r"""
import json, pathlib, sys, time
sys.path.insert(0, sys.argv[1])
import editor_native_cache as cache
root, store = map(pathlib.Path, sys.argv[2:])
output = root / "bin/editor.exe"
cache.identify = lambda *args: ("5" * 64, ["bin/editor.exe"])
def compile_native():
    with (store / "producer-runs").open("a") as record:
        print(root, file=record)
    time.sleep(0.4)
    output.parent.mkdir(exist_ok=True)
    output.write_bytes(b"editor")
receipt = cache.build_or_reuse(root, {}, output, compile_native, env={}, store=store)
print(json.dumps(receipt))
"""
        workers = [
            subprocess.Popen(
                [sys.executable, "-c", script, str(TOOLS), str(tree), str(self.store)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for tree in (self.root, other)
        ]
        try:
            receipts = []
            for proc in workers:
                out, error = proc.communicate(timeout=30)
                self.assertEqual(proc.returncode, 0, error)
                receipts.append(json.loads(out))
        finally:
            for proc in workers:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
        self.assertEqual(sorted(r["status"] for r in receipts), ["built", "hit"])
        self.assertEqual(len((self.store / "producer-runs").read_text().splitlines()), 1)
        self.assertEqual((other / "bin/editor.exe").read_bytes(), b"editor")

    def test_dead_process_releases_lock_and_waiter_can_cancel(self):
        path = self.base / "key.lock"
        script = (
            "import pathlib,sys,time; sys.path.insert(0,sys.argv[1]); import editor_native_cache as c; "
            "lock=c.single_flight(pathlib.Path(sys.argv[2]), None); lock.__enter__(); "
            "print('locked', flush=True); time.sleep(30)"
        )
        with subprocess.Popen([sys.executable, "-c", script, str(TOOLS), str(path)], stdout=subprocess.PIPE) as child:
            try:
                self.assertEqual(child.stdout.readline().strip(), b"locked")
                start = time.monotonic()
                with (
                    self.assertRaises(InterruptedError),
                    cache.single_flight(path, lambda: time.monotonic() - start > 0.3),
                ):
                    self.fail("entered another process's lock")
            finally:
                child.kill()
        with cache.single_flight(path, None):
            pass


if __name__ == "__main__":
    unittest.main()
