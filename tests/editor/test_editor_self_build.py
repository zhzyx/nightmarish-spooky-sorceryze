import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("editor_self_build", ROOT / "tools/editor_self_build.py")
assert spec is not None and spec.loader is not None
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class SelfBuildTests(unittest.TestCase):
    def test_app_executable_uses_authoritative_compiled_features(self):
        features = {
            "platform": "macos",
            "target": "editor",
            "arch": "arm64",
            "dev_build": "no",
            "precision": "single",
            "module_mono_enabled": "no",
            "use_volk": "yes",
            "accesskit": "no",
        }
        result = worker.build_options(Path("Example.app/Contents/MacOS/Godot"), [], features)
        self.assertEqual(result["arch"], "arm64")
        self.assertEqual(result["use_volk"], "yes")
        self.assertEqual(result["extra_suffix"], "self_update_a")
        with self.assertRaisesRegex(ValueError, "Invalid authoritative"):
            worker.build_options(Path("Example.app/Contents/MacOS/Godot"), [], dict(features, arch="guessed"))

    def test_alternating_slots_preserve_configuration(self):
        first = worker.build_options(Path("godot.windows.editor.dev.x86_64.mono.exe"), ["msvc_version=14.3"])
        self.assertEqual(first["extra_suffix"], "self_update_a")
        self.assertEqual(first["module_mono_enabled"], "yes")
        self.assertEqual(first["dev_build"], "yes")
        second = worker.build_options(Path("godot.windows.editor.dev.x86_64.self_update_a.mono.exe"), [])
        self.assertEqual(second["extra_suffix"], "self_update_b")
        self.assertEqual(worker.artifact_path(first).name, "godot.windows.editor.dev.x86_64.self_update_a.mono.exe")
        self.assertEqual(first["msvc_version"], "14.3")

    def test_macos_artifacts_have_no_extension_and_alternate_slots(self):
        first = worker.build_options(Path("godot.macos.editor.x86_64"), [])
        self.assertEqual(first["extra_suffix"], "self_update_a")
        self.assertEqual(worker.artifact_path(first).name, "godot.macos.editor.x86_64.self_update_a")
        second = worker.build_options(Path("godot.macos.editor.x86_64.self_update_a"), [])
        self.assertEqual(second["extra_suffix"], "self_update_b")
        self.assertEqual(worker.artifact_path(second).name, "godot.macos.editor.x86_64.self_update_b")

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
            current.with_suffix(".exe.build.json").write_text(
                json.dumps({"msvc_version": "14.3", "extra_suffix": "old", "module_mono_enabled": "yes"})
            )
            options = worker.build_options(current, [])
            self.assertEqual(options["msvc_version"], "14.3")
            self.assertEqual(options["extra_suffix"], "self_update_b")

    def test_native_app_parent_and_external_snapshot_identify_running_slot(self):
        features = dict(
            platform="macos",
            target="editor",
            arch="arm64",
            dev_build="no",
            precision="single",
            module_mono_enabled="no",
        )
        with tempfile.TemporaryDirectory(prefix="private_sc_selfbuild_options_") as directory:
            app = Path(directory) / "godot.macos.editor.arm64.self_update_a.app"
            current = app / "Contents/MacOS/Godot"
            self.assertEqual(worker.build_options(current, [], features)["extra_suffix"], "self_update_b")
            app = Path(directory) / "Installed Engine.app"
            Path(str(app) + ".build.json").write_text(json.dumps({"extra_suffix": "self_update_a", "metal": "yes"}))
            options = worker.build_options(app / "Contents/MacOS/Godot", [], features)
            self.assertEqual(options["extra_suffix"], "self_update_b")
            self.assertEqual(options["metal"], "yes")

    def test_private_check_explicitly_unpacks_bundle_and_preserves_signed_bytes(self):
        import hashlib

        with tempfile.TemporaryDirectory(prefix="private_sc_selfbuild_copy_") as directory:
            root = Path(directory)
            artifact = root / "Fixture.app/Contents/MacOS/Godot"
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b"private signed-byte fixture")
            artifact.chmod(0o755)
            temporary = root / "check"
            temporary.mkdir()
            with patch.dict(os.environ, {"GONGGONG_WORKSPACE": "must-not-be-inherited"}):
                private = worker.private_check_editor(artifact, temporary)
                self.assertEqual(os.environ["GONGGONG_WORKSPACE"], "must-not-be-inherited")
            self.assertEqual(
                hashlib.sha256(private.read_bytes()).hexdigest(), hashlib.sha256(artifact.read_bytes()).hexdigest()
            )
            self.assertFalse(any(part.endswith(".app") for part in private.parts))
            self.assertTrue((private.parent / "_sc_").is_file())

    def test_scons_progress_is_available_without_a_terminal(self):
        import SCons.Script

        import methods

        callbacks = []
        progress = []
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("atexit.register", callbacks.append),
            patch.object(SCons.Script, "Progress", progress.append),
        ):
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
            with patch.dict(
                os.environ,
                {
                    "GODOT_BUILD_PROGRESS_FILE": str(path),
                    "GODOT_BUILD_COUNT_ONLY": "0",
                    "GODOT_BUILD_PROGRESS_TOTAL": "10",
                },
            ):
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

    def test_fresh_candidate_creates_bin_and_failed_build_never_publishes_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
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
                code = worker.main([
                    "--current",
                    str(current),
                    "--status",
                    str(status),
                    "--log",
                    str(log),
                    "--cancel",
                    str(root / "cancel"),
                ])
            self.assertEqual(code, 1)
            result = json.loads(status.read_text())
            self.assertEqual(result["stage"], "failed")
            self.assertIn("exit 7", result["error"])
            self.assertNotIn("executable", result)
            self.assertEqual(len(calls), 2)
            self.assertTrue((root / "bin").is_dir())
            self.assertFalse((root / "bin/editor_self_build.lock").exists())

    def test_failed_isolated_startup_does_not_publish_candidate_binding(self):
        import editor_engine_candidate as candidates
        import editor_source_manifest as manifests

        with tempfile.TemporaryDirectory(prefix="private_sc_selfbuild_failed_smoke_") as directory:
            root = Path(directory)
            status = root / "status.json"
            binding_path = root / "binding.json"
            old_manifest = root / "bin/godot.windows.editor.x86_64.self_update_a.exe.candidate.json"
            old_manifest.parent.mkdir()
            old_manifest.write_text('{"artifact_sha256":"previous-ready-generation"}')
            old_bytes = old_manifest.read_bytes()
            binding = dict(
                issue=1, request_id="offline-build-fixture", owner="offline", artifact_manifest=str(old_manifest)
            )
            binding_path.write_text(json.dumps(binding))
            checked = dict(binding, source_root=str(root), binding_path=str(binding_path))

            class Child:
                pid = 123
                returncode = 0

                def __init__(self, command, **kwargs):
                    if "--dry-run" in command:
                        worker.write_status(status, stage="counted", total=10)
                    else:
                        (root / "bin/godot.windows.editor.x86_64.self_update_a.exe").write_bytes(b"built fixture")

                def poll(self):
                    return self.returncode

            with (
                patch.object(worker, "ROOT", root),
                patch.object(worker.subprocess, "Popen", Child),
                patch.object(candidates, "prepare", return_value=checked),
                patch.object(manifests, "source_snapshot", return_value={}),
                patch.object(
                    manifests, "artifact_manifest", return_value=str(root / "fixture.candidate.json")
                ) as manifest,
                patch.object(worker, "private_check_editor", side_effect=ValueError("fixture isolated startup failed")),
            ):
                code = worker.main([
                    "--current",
                    str(root / "godot.windows.editor.x86_64.exe"),
                    "--status",
                    str(status),
                    "--log",
                    str(root / "build.log"),
                    "--cancel",
                    str(root / "cancel"),
                    "--binding",
                    str(binding_path),
                ])
            self.assertEqual(code, 1)
            self.assertFalse(manifest.called)
            self.assertEqual(old_manifest.read_bytes(), old_bytes)
            self.assertEqual(json.loads(binding_path.read_text()), binding)
            self.assertEqual(json.loads(status.read_text())["stage"], "failed")

    def check_artifact_layout(self, arguments, native_app):
        import editor_engine_candidate as candidates
        import editor_native_app as native
        import editor_source_manifest as manifests

        with tempfile.TemporaryDirectory(prefix="private_sc_selfbuild_layout_") as directory:
            root = Path(directory)
            status = root / "status.json"
            binding_path = root / "binding.json"
            binding = dict(issue=1, request_id="offline-build-layout", owner="offline")
            binding_path.write_text(json.dumps(binding))
            checked = dict(binding, source_root=str(root), binding_path=str(binding_path))
            raw = root / "bin/godot.macos.editor.arm64.self_update_a"
            local_store = root / "private-local-store"
            app = local_store / (raw.name + ".app")

            class Child:
                pid = 123
                returncode = 0

                def __init__(self, command, **kwargs):
                    if "--dry-run" in command:
                        worker.write_status(status, stage="counted", total=10)
                    elif "SCons" in command:
                        raw.write_bytes(b"mock compiled fixture")

                def poll(self):
                    return self.returncode

            def package(root, artifact, binding, project, destination):
                executable = destination / native.EXECUTABLE_RELATIVE
                executable.parent.mkdir(parents=True)
                executable.write_bytes(artifact.read_bytes())
                return destination

            def manifest(root, artifact, binding, project, options, before, app):
                path = Path(str(app if app else artifact) + ".candidate.json")
                path.write_text("{}")
                return str(path)

            with (
                patch.object(worker, "ROOT", root),
                patch.object(worker.subprocess, "Popen", Child),
                patch.object(candidates, "prepare", return_value=checked),
                patch.object(manifests, "source_snapshot", return_value={}),
                patch.object(manifests, "artifact_manifest", side_effect=manifest),
                patch.object(manifests, "verify_source", return_value={"ok": True}),
                patch.object(native, "package_app", side_effect=package) as packaged,
                patch.object(native, "native_output_dir", return_value=local_store),
                patch.object(worker, "private_check_editor", side_effect=lambda artifact, directory: artifact),
                patch.object(worker, "write_resume_fixture", return_value="mock-token"),
                patch.object(worker, "resume_ack_error", return_value=""),
            ):
                code = worker.main([
                    "--current",
                    str(root / "godot.macos.editor.arm64"),
                    "--status",
                    str(status),
                    "--log",
                    str(root / "build.log"),
                    "--cancel",
                    str(root / "cancel"),
                    "--binding",
                    str(binding_path),
                    *arguments,
                ])
            self.assertEqual(code, 0)
            result = json.loads(status.read_text())
            expected = app / native.EXECUTABLE_RELATIVE if native_app else raw
            expected_manifest = Path(str(app if native_app else raw) + ".candidate.json")
            self.assertEqual(result["stage"], "ready")
            self.assertEqual(result["executable"], str(expected))
            self.assertEqual(result["candidate_manifest"], str(expected_manifest))
            self.assertEqual(json.loads(binding_path.read_text())["artifact_manifest"], str(expected_manifest))
            self.assertEqual(packaged.called, native_app)
            if native_app:
                self.assertFalse(Path(str(expected) + ".candidate.json").exists())
                self.assertTrue(Path(str(app) + ".build.json").is_file())

    def test_legacy_host_without_layout_flag_keeps_raw_and_adjacent_manifest(self):
        self.check_artifact_layout([], False)

    def test_native_aware_host_explicitly_opts_into_app_and_external_manifest(self):
        self.check_artifact_layout(["--artifact-layout", "native_app"], True)


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(ROOT))
    unittest.main()
