import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("editor_self_build", ROOT / "tools/editor_self_build.py")
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class SelfBuildTests(unittest.TestCase):
    def test_alternating_slots_preserve_configuration(self):
        first = worker.build_options(Path("godot.windows.editor.dev.x86_64.mono.exe"), ["msvc_version=14.3"])
        self.assertEqual(first["extra_suffix"], "self_update_a")
        self.assertEqual(first["module_mono_enabled"], "yes")
        self.assertEqual(first["dev_build"], "yes")
        second = worker.build_options(Path("godot.windows.editor.dev.x86_64.self_update_a.mono.exe"), [])
        self.assertEqual(second["extra_suffix"], "self_update_b")
        self.assertEqual(worker.artifact_path(first).name, "godot.windows.editor.dev.x86_64.self_update_a.mono.exe")
        self.assertEqual(first["msvc_version"], "14.3")

    def test_protected_flags_and_invalid_input(self):
        current = Path("godot.windows.editor.dev.x86_64.mono.exe")
        for value in ["extra_suffix=live", "platform=linuxbsd", "target=template_release", "--clean", "ninja=yes"]:
            with self.assertRaises(ValueError):
                worker.build_options(current, [value])
        with self.assertRaises(ValueError):
            worker.build_options(Path("unknown.exe"), [])

    def test_snapshot_preserves_toolchain_options(self):
        with tempfile.TemporaryDirectory() as directory:
            current = Path(directory) / "godot.windows.editor.dev.x86_64.self_update_a.mono.exe"
            current.with_suffix(".exe.build.json").write_text(json.dumps({"msvc_version": "14.3", "extra_suffix": "old", "module_mono_enabled": "yes"}))
            options = worker.build_options(current, [])
            self.assertEqual(options["msvc_version"], "14.3")
            self.assertEqual(options["extra_suffix"], "self_update_b")

    def test_scons_progress_is_available_without_a_terminal(self):
        import methods
        import SCons.Script
        callbacks = []
        progress = []
        with tempfile.TemporaryDirectory() as directory, patch("atexit.register", callbacks.append), patch.object(SCons.Script, "Progress", progress.append):
            path = Path(directory) / "status.json"
            env = {"ninja": False, "progress": False}
            with patch.dict(os.environ, {"GODOT_BUILD_PROGRESS_FILE": str(path), "GODOT_BUILD_COUNT_ONLY": "1"}):
                methods.show_progress(env)
                for index in range(10):
                    progress[0](str(index))
                callbacks[0]()
                self.assertEqual(json.loads(path.read_text())["total"], 10)
            callbacks.clear()
            progress.clear()
            with patch.dict(os.environ, {"GODOT_BUILD_PROGRESS_FILE": str(path), "GODOT_BUILD_COUNT_ONLY": "0", "GODOT_BUILD_PROGRESS_TOTAL": "10"}):
                methods.show_progress(env)
                progress[0]("first.cpp")
                self.assertEqual(json.loads(path.read_text())["percent"], 9)
                for index in range(20):
                    progress[0](str(index))
                self.assertEqual(json.loads(path.read_text())["percent"], 99)
                self.assertNotEqual(json.loads(path.read_text())["stage"], "ready")

    def test_compressed_resume_fixture_preserves_history_and_pending_call(self):
        import base64
        import gzip
        import hashlib
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            token = worker.write_resume_fixture(project, project / "old.exe", project / "new.exe", "compressed")
            path = project / ".godot/editor/ai_chat_resume.json"
            self.assertLess(path.stat().st_size, 16 * 1024 * 1024)
            envelope = json.loads(path.read_text(encoding="utf-8"))
            raw = gzip.decompress(base64.b64decode(envelope["payload"], validate=True))
            self.assertGreater(len(raw), 16 * 1024 * 1024)
            self.assertEqual(len(raw), envelope["uncompressed_bytes"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), envelope["sha256"])
            journal = json.loads(raw)
            self.assertEqual(journal["restart"]["token"], token)
            self.assertEqual(journal["tool_calls"][0]["id"], journal["restart"]["tool_call_id"])
            self.assertIn("保留约束", journal["messages"][0]["content"])
            self.assertTrue(journal["smoke_check"])
            # An earlier passing check must not mask a failed later case.
            ack = project / ".godot/editor/ai_chat_restart_ack.json"
            ack.write_text("{}", encoding="utf-8")
            worker.write_resume_fixture(project, project / "old.exe", project / "new.exe", "oversized_declared")
            self.assertFalse(ack.exists())
            self.assertGreater(json.loads(path.read_text(encoding="utf-8"))["uncompressed_bytes"], 64 * 1024 * 1024)

    def test_failed_build_never_publishes_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bin").mkdir()
            status = root / "status.json"
            log = root / "build.log"
            current = root / "bin/godot.windows.editor.dev.x86_64.mono.exe"
            calls = []

            class Child:
                pid = 123

                def __init__(self, command, **kwargs):
                    import io
                    self.stdout = io.BytesIO()
                    calls.append(command)
                    if "--dry-run" in command:
                        worker.write_status(status, stage="counted", total=10)
                        self.returncode = 0
                    else:
                        self.returncode = 7

                def poll(self):
                    return self.returncode

            with patch.object(worker, "ROOT", root), patch.object(worker.subprocess, "Popen", Child):
                code = worker.main(["--current", str(current), "--status", str(status), "--log", str(log), "--cancel", str(root / "cancel")])
            self.assertEqual(code, 1)
            result = json.loads(status.read_text())
            self.assertEqual(result["stage"], "failed")
            self.assertIn("exit 7", result["error"])
            self.assertNotIn("executable", result)
            self.assertEqual(len(calls), 2)
            self.assertFalse((root / "bin/editor_self_build.lock").exists())


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    unittest.main()
