"""Real isolated Git/owned-app tests; no production settings or entry is touched."""

import hashlib
import json
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import editor_candidate_activation as activation
import editor_native_app as native


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="engine-activation-")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name).resolve()
        self.root = self.folder / "source"
        self.root.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Isolated fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        (self.root / "engine.cpp").write_text("verified source\n")
        self.git("add", "engine.cpp")
        self.git("commit", "-m", "candidate")
        self.head = self.git("rev-parse", "HEAD")
        self.common = self.root / ".git"
        self.app = self.folder / "Original Engine.app"
        self.entry = self.app / "Contents/MacOS/Godot"
        self.entry.parent.mkdir(parents=True)
        shutil.copyfile("/usr/bin/true", self.entry)
        self.entry.chmod(0o755)
        with (self.app / "Contents/Info.plist").open("wb") as stream:
            plistlib.dump(
                {
                    "CFBundleExecutable": "Godot",
                    "CFBundleIdentifier": "local.gonggong.activation-fixture",
                    "CFBundleName": "Isolated activation fixture",
                    "CFBundlePackageType": "APPL",
                    "CFBundleVersion": "1",
                },
                stream,
            )
        self.artifact = self.folder / "candidate-engine"
        self.artifact.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
        self.artifact.chmod(0o755)
        self.project = self.folder / "project"
        self.project.mkdir()
        (self.project / "project.godot").write_text("config_version=5\n")
        binding_path = self.common / "gonggong-engine-candidates/fixture.json"
        self.binding = dict(
            state="prepared",
            source_root=str(self.root),
            issue=1,
            request_id="isolated-fixture",
            owner="fixture-owner",
            branch="fixture",
            base_sha=self.head,
            common_dir=str(self.common),
            repository="fixture/repo",
            initial_launch_executable=str(self.entry),
            binding_path=str(binding_path),
        )
        activation.atomic_json(binding_path, self.binding)
        inputs = {"engine.cpp": {"mode": "100644", "sha256": activation.digest(self.root / "engine.cpp")}}
        self.manifest = dict(
            schema_version=1,
            binding=self.binding,
            source_inputs=inputs,
            source_digest=hashlib.sha256(
                json.dumps(inputs, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
            ).hexdigest(),
            executable=str(self.artifact),
            artifact_sha256=activation.digest(self.artifact),
            project_root=str(self.project),
        )
        self.manifest_path = self.folder / "engine.candidate.json"
        self.save()
        self.report = dict(
            pr_state="MERGED",
            repository="fixture/repo",
            issue=1,
            request_id="isolated-fixture",
            candidate=self.head,
            current_main=self.head,
            delivered_paths_differ=[],
            issue_receipt=dict(state="CLOSED", reason="COMPLETED", labels=["status:done"]),
        )

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), *args], check=True, capture_output=True, text=True
        ).stdout.strip()

    def save(self):
        activation.atomic_json(self.manifest_path, self.manifest)

    def refusal(self, error):
        original = self.entry.read_bytes()
        with self.assertRaisesRegex(activation.ActivationError, error):
            activation.activate(self.manifest_path, self.report)
        self.assertEqual(self.entry.read_bytes(), original)

    def native_candidate(self):
        (self.root / "bin").mkdir()
        app = self.root / "bin/native.self_update_a.app"
        native.package_app(self.root, "/usr/bin/true", self.binding, self.project, app, self.app)
        self.manifest["native_app"] = native.descriptor(self.root, app)
        self.manifest["executable"] = str(app / native.EXECUTABLE_RELATIVE)
        self.manifest["artifact_sha256"] = native.digest(app / native.EXECUTABLE_RELATIVE)
        self.manifest_path = native.manifest_path(app)
        self.save()
        return app

    @unittest.skipUnless(sys.platform == "darwin", "real native App copy and signature")
    def test_native_activation_copies_whole_sealed_app_without_resigning(self):
        source = self.native_candidate()

        def snapshot(app):
            return {p.relative_to(app).as_posix(): p.read_bytes() for p in app.rglob("*") if p.is_file()}

        expected = snapshot(source)
        real = activation.command
        commands = []

        def observe(args, **kwargs):
            commands.append(args)
            return real(args, **kwargs)

        with patch.object(activation, "command", observe):
            result = activation.activate(self.manifest_path, self.report)
            again = activation.activate(self.manifest_path, self.report)
        self.assertEqual(result["state"], "activated")
        self.assertTrue(again["reused"])
        self.assertEqual(expected, snapshot(self.app))
        self.assertEqual(expected, snapshot(source))
        self.assertFalse(any("--sign" in command for command in commands))
        native.native_executable(self.entry)
        native.verify_signature(self.app)

    @unittest.skipUnless(sys.platform == "darwin", "real native signature refusal")
    def test_native_tampered_resource_preserves_original_entry(self):
        source = self.native_candidate()
        (source / "Contents/Resources/tampered.txt").write_text("unsigned resource")
        self.refusal("activation_native_app_invalid")

    @unittest.skipUnless(sys.platform == "darwin", "real native recovery")
    def test_native_interrupted_swap_restores_original_and_retries(self):
        self.native_candidate()
        original = self.entry.read_bytes()
        real = activation.os.replace

        def interrupt(source, target):
            if str(source).endswith(".app") and "-activate-" in str(source) and Path(target) == self.app:
                raise OSError("fixture interrupted native rename")
            return real(source, target)

        with patch.object(activation.os, "replace", interrupt):
            with self.assertRaisesRegex(OSError, "interrupted native"):
                activation.activate(self.manifest_path, self.report)
        self.assertEqual(original, self.entry.read_bytes())
        self.assertEqual(activation.activate(self.manifest_path, self.report)["state"], "activated")

    def test_unaccepted_issue_preserves_original_entry(self):
        self.report["issue_receipt"]["state"] = "OPEN"
        self.refusal("awaiting_acceptance")

    def test_missing_main_and_changed_delivery_preserve_original(self):
        self.report["pr_state"] = "OPEN"
        self.refusal("awaiting_acceptance")
        self.report["pr_state"] = "MERGED"
        self.report["delivered_paths_differ"] = ["engine.cpp"]
        self.refusal("delivered_source_changed")

    def test_uncommitted_build_inputs_cannot_use_old_head_as_proof(self):
        (self.root / "engine.cpp").write_text("uncommitted build input\n")
        self.manifest["source_inputs"]["engine.cpp"]["sha256"] = activation.digest(self.root / "engine.cpp")
        self.manifest["source_digest"] = hashlib.sha256(
            json.dumps(
                self.manifest["source_inputs"], sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest()
        self.save()
        self.refusal("source_not_committed")

    def test_artifact_drift(self):
        self.artifact.write_text("changed artifact")
        self.refusal("artifact_changed")

    def test_source_drift_after_build(self):
        (self.root / "engine.cpp").write_text("later edit\n")
        self.refusal("source_changed_after_build")

    def test_committed_checkout_line_endings_match_actual_build_bytes(self):
        (self.root / ".gitattributes").write_text("*.props text eol=crlf\n")
        (self.root / "dependency.props").write_bytes(b"first\r\nsecond\r\n")
        self.git("add", ".gitattributes", "dependency.props")
        self.git("commit", "-m", "checkout CRLF input")
        inputs = {
            name: {"mode": "100644", "sha256": activation.digest(self.root / name)}
            for name in ("engine.cpp", ".gitattributes", "dependency.props")
        }
        activation.source_matches(self.root, self.git("rev-parse", "HEAD"), inputs)
        inputs["dependency.props"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(activation.ActivationError, "source_not_committed"):
            activation.source_matches(self.root, self.git("rev-parse", "HEAD"), inputs)

    @unittest.skipUnless(sys.platform == "darwin", "owned macOS application entry")
    def test_later_main_commits_are_not_claimed_as_built_candidate(self):
        (self.root / "dependency.cpp").write_text("later unrelated main dependency\n")
        self.git("add", "dependency.cpp")
        self.git("commit", "-m", "later main commit")
        later_main = self.git("rev-parse", "HEAD")
        self.report["current_main"] = later_main
        self.git("checkout", "--detach", self.head)
        result = activation.activate(self.manifest_path, self.report)
        self.assertEqual(result["source_commit"], self.head)
        self.assertEqual(result["main_commit"], later_main)
        self.assertTrue(result["main_advanced"])
        self.assertEqual(result["activation_mode"], "accepted_candidate")

    def test_private_owner_binding_changed(self):
        private = dict(self.binding, owner="other-owner")
        activation.atomic_json(self.binding["binding_path"], private)
        self.refusal("binding_changed")

    def test_candidate_must_be_in_actual_main_receipt(self):
        self.git("checkout", "--orphan", "unrelated")
        self.git("commit", "--allow-empty", "-m", "unrelated")
        self.report["current_main"] = self.git("rev-parse", "HEAD")
        self.git("checkout", "main")
        self.refusal("candidate_not_in_main")

    @unittest.skipUnless(sys.platform == "darwin", "owned macOS application entry")
    def test_original_app_switch_sign_verify_and_idempotent_recovery(self):
        result = activation.activate(self.manifest_path, self.report)
        self.assertEqual(result["state"], "activated")
        self.assertTrue(Path(result["backup"]).is_dir())
        subprocess.run(
            ["/usr/bin/codesign", "--verify", "--deep", "--strict", str(self.app)], check=True, capture_output=True
        )
        args = subprocess.run([str(self.entry)], check=True, capture_output=True, text=True).stdout.splitlines()
        self.assertEqual(args, ["--editor", "--path", str(self.project)])
        args = subprocess.run(
            [str(self.entry), "--version"], check=True, capture_output=True, text=True
        ).stdout.splitlines()
        self.assertEqual(args, ["--version"])
        again = activation.activate(self.manifest_path, self.report)
        self.assertTrue(again["reused"])
        self.assertEqual(result["backup"], again["backup"])

    @unittest.skipUnless(sys.platform == "darwin", "owned macOS application entry")
    def test_failed_signing_keeps_original_app(self):
        real = activation.command

        def fail_sign(args, **kwargs):
            if args[0] == "/usr/bin/codesign":
                raise activation.ActivationError("fixture_signing_failed")
            return real(args, **kwargs)

        with patch.object(activation, "command", fail_sign):
            self.refusal("fixture_signing_failed")
        self.assertFalse(list(self.app.parent.glob(".*-activate-*.app")))

    @unittest.skipUnless(sys.platform == "darwin", "owned macOS application entry")
    def test_reused_app_signature_drift_is_not_reported_successful(self):
        activation.activate(self.manifest_path, self.report)
        info_path = self.app / "Contents/Info.plist"
        with info_path.open("rb") as stream:
            info = plistlib.load(stream)
        info["CFBundleName"] = "Changed after activation"
        with info_path.open("wb") as stream:
            plistlib.dump(info, stream)
        self.refusal("activation_command_failed")

    @unittest.skipUnless(sys.platform == "darwin", "owned macOS application entry")
    def test_interrupted_swap_recovers_previous_entry(self):
        original = self.entry.read_bytes()
        real = activation.os.replace

        def interrupt(source, target):
            if str(source).endswith(".app") and "-activate-" in str(source) and Path(target) == self.app:
                raise OSError("fixture interrupted final rename")
            return real(source, target)

        with patch.object(activation.os, "replace", interrupt):
            with self.assertRaises(OSError):
                activation.activate(self.manifest_path, self.report)
        self.assertEqual(self.entry.read_bytes(), original)
        result = activation.activate(self.manifest_path, self.report)
        self.assertEqual(result["state"], "activated")


if __name__ == "__main__":
    unittest.main()
