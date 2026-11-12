"""Real synthetic process trees; no model/SDK/network/GUI dependencies."""

import ast
import hashlib
import importlib.util
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kimi_provider import KimiNativeDirectProvider
from kimi_work_image_provider import KimiWorkImageProvider
from modeling_provider import ModelingProvider
from motion_jobs import alive, process_identity
from owned_process import OwnedCommand, OwnedScope, owned_scope, run_owned

FIXTURE = r"""
import os, pathlib, subprocess, sys, time
root, mode, role = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
(root / (role + '.pid')).write_text(str(os.getpid()))
if role != 'grandchild':
    subprocess.Popen([sys.executable, __file__, str(root), mode, 'child' if role == 'parent' else 'grandchild'])
if role != 'parent':
    time.sleep(30)
else:
    deadline = time.monotonic() + 5
    while not (root / 'grandchild.pid').exists() and time.monotonic() < deadline:
        time.sleep(.01)
    (root / 'ready').touch()
    if mode == 'success':
        print('complete', flush=True)
    elif mode == 'error':
        raise SystemExit(9)
    elif mode == 'flood':
        while True:
            os.write(1, b'x' * 65536)
            os.write(2, b'y' * 65536)
    elif mode == 'fast_flood':
        os.write(1, b'x' * 65536)
    else:
        time.sleep(30)
"""


class AdapterProcessTests(unittest.TestCase):
    def test_retained_launch_observes_output_even_when_reader_thread_is_delayed(self):
        # Parent returns only after all launcher markers are visible, while the
        # actual child keeps its inherited pipe open and must remain alive.
        original = OwnedCommand._drain
        started = threading.Event()
        release = threading.Event()

        def delayed(command, *args):
            started.set()
            if not release.wait(5):
                raise AssertionError("test failed to release delayed reader")
            return original(command, *args)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pid_file = root / "child.pid"
            log_path = root / "launch.log"
            code = (
                "import subprocess,sys; from pathlib import Path; "
                'child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"]); '
                f"Path({str(pid_file)!r}).write_text(str(child.pid)); "
                'print("Job log: /fixture/worker.log"); print("Job PID file: /fixture/worker.pid")'
            )
            scope = OwnedScope()
            identity = None
            try:
                with patch.object(OwnedCommand, "_drain", delayed), log_path.open("wb") as stream:
                    result = run_owned(
                        [sys.executable, "-c", code],
                        stdout=stream,
                        limit=4096,
                        timeout=3,
                        active=lambda: True,
                        fail=lambda reason: self.fail(reason),
                        scope=scope,
                    )
                    self.assertTrue(started.is_set())
                    self.assertFalse(release.is_set())
                    self.assertEqual(result, 0)
                    self.assertEqual(
                        log_path.read_bytes().splitlines(),
                        [b"Job log: /fixture/worker.log", b"Job PID file: /fixture/worker.pid"],
                    )
                    identity = process_identity(int(pid_file.read_text()))
                    self.assertTrue(alive(identity))
                    self.assertTrue(scope.commands[0].readers[0].is_alive())
                    release.set()
                    with tempfile.TemporaryFile() as watch:
                        self.assertEqual(
                            run_owned(
                                [sys.executable, "-c", 'print("done: fixture")'],
                                stdout=watch,
                                limit=4096,
                                timeout=2,
                                active=lambda: True,
                                fail=lambda reason: self.fail(reason),
                            ),
                            0,
                        )
                        watch.seek(0)
                        self.assertEqual(watch.read().splitlines(), [b"done: fixture"])
                    self.assertTrue(alive(identity))
            finally:
                release.set()
                scope.close()
            deadline = time.monotonic() + 3
            while alive(identity) and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertFalse(alive(identity))

    def test_short_command_without_descendants_reaps_zombie_leader(self):
        with tempfile.TemporaryFile() as output:
            command = OwnedCommand(
                [sys.executable, "-c", 'print("done")'], stdout=output, stderr=None, env=None, limit=100
            )
            deadline = time.monotonic() + 5
            while command.poll() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(command.poll(), 0)
            command.close()
            self.assertEqual(command.process.returncode, 0)
            output.seek(0)
            self.assertEqual(output.read().splitlines(), [b"done"])

    def test_all_real_adapters_clean_owned_descendants_and_bound_output(self):
        for provider_type in (ModelingProvider, KimiWorkImageProvider, KimiNativeDirectProvider):
            for mode in ("success", "error", "timeout", "cancel", "flood", "fast_flood", "callback_error"):
                with (
                    self.subTest(provider=provider_type.__name__, mode=mode),
                    tempfile.TemporaryDirectory() as temporary,
                ):
                    root = Path(temporary)
                    script = root / "fixture.py"
                    script.write_text(FIXTURE)
                    (root / "runtime").mkdir()
                    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
                    outsider = process_identity(unrelated.pid)
                    self.assertIsNotNone(outsider)
                    identities = []
                    provider = provider_type.__new__(provider_type)
                    failures = []

                    def active(*_args):
                        if (root / "ready").exists():
                            if not identities:
                                identities.extend(
                                    process_identity(int(path.read_text())) for path in root.glob("*.pid")
                                )
                            if mode == "callback_error":
                                raise RuntimeError("synthetic callback failure")
                            if mode == "cancel":
                                return False
                        return True

                    provider._active = active
                    provider.finish = lambda *args: failures.append(args)
                    args = [sys.executable, str(script), str(root), mode, "parent"]
                    # Windows starts three interpreters before the ready marker.
                    timeout = 3.0 if os.name == "nt" else 0.6
                    started = time.monotonic()
                    try:
                        with (
                            patch("modeling_provider.MAX_EVENTS_BYTES", 4096),
                            patch("kimi_work_image_provider.MAX_LOG_BYTES", 4096),
                            patch("kimi_provider.MAX_LOG_BYTES", 4096),
                        ):
                            if provider_type == ModelingProvider:

                                def invoke():
                                    return provider._run_owned("fixture", args, root, "builder", timeout=timeout)

                            else:

                                def invoke():
                                    return provider._run_owned("fixture", args, "output.log", "fixture", timeout, root)

                            if mode == "callback_error":
                                with self.assertRaisesRegex(RuntimeError, "synthetic callback"):
                                    invoke()
                            else:
                                result = invoke()
                                self.assertEqual(result, {"success": 0, "error": 9}.get(mode))
                        self.assertLess(time.monotonic() - started, 7)
                        self.assertEqual(len(list(root.glob("*.pid"))), 3)
                        # Identity reads can race the exited leader; descendants
                        # must be dead and the unrelated handle must stay live.
                        for path in root.glob("*.pid"):
                            deadline = time.monotonic() + 3
                            while process_identity(int(path.read_text())) and time.monotonic() < deadline:
                                time.sleep(0.02)
                            self.assertIsNone(process_identity(int(path.read_text())), path.name)
                        self.assertTrue(alive(outsider))
                        self.assertIsNone(unrelated.poll())
                        for path in (
                            list(root.glob("*.log")) + list(root.glob("*.stdout")) + list(root.glob("*.stderr"))
                        ):
                            self.assertLessEqual(path.stat().st_size, 4096)
                        self.assertEqual(bool(failures), mode in ("timeout", "flood", "fast_flood"))
                    finally:
                        unrelated.kill()
                        unrelated.wait(timeout=5)
                        # Only fixture-owned PIDs, with creation identities,
                        # could be cleaned here if an assertion ever regresses.
                        for identity in identities:
                            if alive(identity):
                                os.kill(identity["pid"], 9)

    def test_async_launch_tree_is_cleaned_after_watch_or_parse_terminal(self):
        for provider_type in (KimiWorkImageProvider, KimiNativeDirectProvider):
            for outcome in ("success", "error", "timeout", "cancel", "flood", "parse_error"):
                with (
                    self.subTest(provider=provider_type.__name__, outcome=outcome),
                    tempfile.TemporaryDirectory() as temporary,
                ):
                    root = Path(temporary)
                    script = root / "fixture.py"
                    script.write_text(FIXTURE)
                    (root / "runtime").mkdir()
                    provider = provider_type.__new__(provider_type)
                    cancelled = False
                    provider._active = lambda *_args: not cancelled
                    failures = []
                    provider.finish = lambda *args: failures.append(args)
                    identities = []

                    @owned_scope
                    def execute(owner):
                        self.assertEqual(
                            owner._run_owned(
                                "fixture",
                                [sys.executable, str(script), str(root), "success", "parent"],
                                "launch.log",
                                "image_launch",
                                3,
                                root,
                            ),
                            0,
                        )
                        identities.extend(
                            process_identity(int((root / (role + ".pid")).read_text()))
                            for role in ("child", "grandchild")
                        )
                        self.assertTrue(all(alive(identity) for identity in identities))
                        if outcome == "parse_error":
                            raise RuntimeError("synthetic parse failure")
                        nonlocal cancelled
                        cancelled = outcome == "cancel"
                        code = {
                            "success": "pass",
                            "error": "raise SystemExit(7)",
                            "flood": 'import os; os.write(1, b"x" * 65536)',
                        }.get(outcome, "import time; time.sleep(30)")
                        result = owner._run_owned(
                            "fixture", [sys.executable, "-c", code], "watch.log", "image_generation", 0.15, root
                        )
                        self.assertEqual(result, {"success": 0, "error": 7}.get(outcome))

                    with (
                        patch("kimi_work_image_provider.MAX_LOG_BYTES", 4096),
                        patch("kimi_provider.MAX_LOG_BYTES", 4096),
                    ):
                        if outcome == "parse_error":
                            with self.assertRaisesRegex(RuntimeError, "synthetic parse"):
                                execute(provider)
                        else:
                            execute(provider)
                    deadline = time.monotonic() + 3
                    while any(alive(identity) for identity in identities) and time.monotonic() < deadline:
                        time.sleep(0.02)
                    self.assertFalse(any(alive(identity) for identity in identities))
                    self.assertEqual(bool(failures), outcome in ("timeout", "flood"))

    @unittest.skipIf(os.name == "nt", "POSIX leader pinning; Windows uses a Job handle")
    def test_async_launch_retains_pinned_leader_until_scope_finishes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = root / "fixture.py"
            script.write_text(FIXTURE)
            (root / "runtime").mkdir()
            provider = KimiWorkImageProvider.__new__(KimiWorkImageProvider)
            provider._active = lambda *_args: True
            provider.finish = lambda *_args: self.fail("unexpected durable failure")
            identities = []

            @owned_scope
            def execute(owner):
                result = owner._run_owned(
                    "fixture",
                    [sys.executable, str(script), str(root), "success", "parent"],
                    "output.log",
                    "image_launch",
                    3,
                    root,
                )
                self.assertEqual(result, 0)
                command = owner._generation_scope.commands[0]
                self.assertIsNone(command.process.returncode)
                self.assertEqual(command.poll(), 0)
                identities.extend(
                    process_identity(int((root / (role + ".pid")).read_text())) for role in ("child", "grandchild")
                )
                self.assertTrue(all(alive(identity) for identity in identities))

            execute(provider)
            deadline = time.monotonic() + 3
            while any(alive(identity) for identity in identities) and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertFalse(any(alive(identity) for identity in identities))


class EmbeddedBundleTests(unittest.TestCase):
    def test_actual_scons_sources_ship_resolvable_windows_helper(self):
        repository = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location(
            "owned_bundle_builders", repository / "editor/ainative/builders.py"
        )
        builders = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builders)
        tree = ast.parse((repository / "editor/SCsub").read_text())
        block = next(
            node for node in tree.body if isinstance(node, ast.If) and ast.unparse(node.test) == "env.editor_build"
        )
        statements = []
        for statement in block.body:
            statements.append(statement)
            if (
                isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Call)
                and ast.unparse(statement.value.func) == "env.CommandNoCache"
            ):
                break

        class SourceNode:
            def __init__(self, path):
                self.path = path
                self.name = path.name

            def get_abspath(self):
                return str(self.path.resolve())

            def __str__(self):
                return "active-SConscript-relative/" + self.name

        captured = {}

        def command(target, sources, action):
            captured.update(target=target, sources=sources, action=action)

        environment = SimpleNamespace(CommandNoCache=command, Run=lambda action: action)
        exec(
            compile(ast.Module(body=statements, type_ignores=[]), "editor/SCsub", "exec"),
            {
                "env": environment,
                "ainative_builders": builders,
                "Glob": lambda pattern: [SourceNode(path) for path in repository.glob(pattern.removeprefix("#"))],
            },
        )
        helper = repository / "tools/editor_provenance_process.py"
        self.assertIn(helper, [Path(str(source)).resolve() for source in captured["sources"]])
        files = builders.bundle_files(captured["sources"])
        self.assertEqual(files["tools/editor_provenance_process.py"], helper.read_text())
        with tempfile.TemporaryDirectory() as temporary:
            installed = Path(temporary).resolve()
            for name in ("owned_process.py", "editor_provenance_process.py"):
                destination = installed / "tools" / name
                destination.parent.mkdir(exist_ok=True)
                destination.write_text(files["tools/" + name])
            spec = importlib.util.spec_from_file_location(
                "installed_owned_process", installed / "tools/owned_process.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.os = SimpleNamespace(name="nt")
            installed_helper = installed / "tools/editor_provenance_process.py"
            self.assertEqual(module._windows_helper_path(), installed_helper)
            self.assertEqual(
                module.implementation_fingerprint()[1], hashlib.sha256(installed_helper.read_bytes()).hexdigest()
            )
            self.assertEqual(Path(module._windows_module().__file__), installed_helper)
            # The build action uses the same closed graph, and a helper change
            # must invalidate the emitted source/hash bundle.
            header = installed / "bundle.gen.h"
            captured["action"]([header], captured["sources"], None)
            self.assertIn("tools/editor_provenance_process.py", header.read_text())
            before = module.implementation_fingerprint()
            installed_helper.write_text(installed_helper.read_text() + "\n# isolated revision\n")
            self.assertNotEqual(module.implementation_fingerprint(), before)
            installed_helper.unlink()
            with self.assertRaises(FileNotFoundError):
                module.implementation_fingerprint()
            with self.assertRaises(FileNotFoundError):
                module._windows_module()


class WindowsOwnershipTests(unittest.TestCase):
    def test_windows_pipe_observation_handles_pending_eof_and_unknown(self):
        import owned_process

        class Peek:
            def __init__(self, ok, pending):
                self.ok, self.pending = ok, pending

            def __call__(self, handle, buffer, size, read, available, remaining):
                self.handle = handle
                available._obj.value = self.pending
                return self.ok

        for ok, pending, error, expected in ((True, 7, 0, 7), (True, 0, 0, 0), (False, 0, 109, None)):
            peek = Peek(ok, pending)
            with (
                patch.object(owned_process, "os", SimpleNamespace(name="nt")),
                patch.dict(sys.modules, {"msvcrt": SimpleNamespace(get_osfhandle=lambda fd: fd + 100)}),
                patch.object(
                    owned_process.ctypes, "WinDLL", return_value=SimpleNamespace(PeekNamedPipe=peek), create=True
                ),
                patch.object(owned_process.ctypes, "get_last_error", return_value=error, create=True),
            ):
                self.assertEqual(owned_process._pipe_pending(SimpleNamespace(fileno=lambda: 9)), expected)
                self.assertEqual(peek.handle, 109)
        with (
            patch.object(owned_process, "os", SimpleNamespace(name="nt")),
            patch.dict(sys.modules, {"msvcrt": SimpleNamespace(get_osfhandle=lambda fd: fd)}),
            patch.object(
                owned_process.ctypes, "WinDLL", return_value=SimpleNamespace(PeekNamedPipe=Peek(False, 0)), create=True
            ),
            patch.object(owned_process.ctypes, "get_last_error", return_value=5, create=True),
        ):
            with self.assertRaisesRegex(OSError, "pipe_query_failed"):
                owned_process._pipe_pending(SimpleNamespace(fileno=lambda: 9))

    def test_suspended_assignment_precedes_resume_and_cleanup(self):
        calls = []

        class API:
            def create(self, name):
                calls.append("create")
                return 42

            def assign(self, job, process):
                calls.append("assign")

            def resume(self, process):
                calls.append("resume")

            def terminate(self, job):
                calls.append("terminate")

            def active(self, job):
                return 0

            def close(self, job):
                calls.append("close")

        with tempfile.TemporaryFile() as output, patch("owned_process.subprocess.Popen") as spawn:
            spawn.return_value.stdout = None
            spawn.return_value.stderr = None
            spawn.return_value.poll.return_value = 0
            command = OwnedCommand(["synthetic"], stdout=output, stderr=None, env={}, limit=10, windows_api=API())
            command.close()
        self.assertEqual(calls, ["create", "assign", "resume", "terminate", "close"])
        self.assertEqual(spawn.call_args.kwargs["creationflags"], 0x08000004)
        self.assertFalse(spawn.call_args.kwargs["start_new_session"])

    def test_assignment_failure_never_resumes_and_closes_job(self):
        calls = []

        class API:
            def create(self, name):
                return 42

            def assign(self, job, process):
                raise OSError("assignment rejected")

            def resume(self, process):
                calls.append("resume")

            def terminate(self, job):
                calls.append("terminate")

            def active(self, job):
                return 0

            def close(self, job):
                calls.append("close")

        with tempfile.TemporaryFile() as output, patch("owned_process.subprocess.Popen") as spawn:
            spawn.return_value.poll.return_value = None
            with self.assertRaisesRegex(OSError, "assignment rejected"):
                OwnedCommand(["synthetic"], stdout=output, stderr=None, env={}, limit=10, windows_api=API())
            spawn.return_value.kill.assert_called_once()
        self.assertEqual(calls, ["close"])


if __name__ == "__main__":
    unittest.main()
