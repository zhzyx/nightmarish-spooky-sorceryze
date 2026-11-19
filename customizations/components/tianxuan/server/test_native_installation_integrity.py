"""Integrity/cache probes; no model or normal-entry acceptance claims."""

# ruff: noqa: E402, I001
import concurrent.futures
import hashlib
import json
import mmap
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
for folder in (HERE, HERE.parent / "duobao", HERE.parent / "sinan-workorders"):
    sys.path.insert(0, str(folder))
import native_installation as ni
from native_store import NativeStoreError


class InstallationIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "tool.exe"
        self.source.write_bytes(b"original" * 262144)
        command = {"argv": [str(self.source)], "env": {}}
        self.spec = {
            "version": 1,
            "identity": "integrity-test",
            "files": {str(self.source): hashlib.sha256(self.source.read_bytes()).hexdigest()},
            "commands": {role: command for role in ("planner", "producer", "checker", "reviewer", "dispatcher")},
            "principals": {role: role for role in ("producer", "checker", "reviewer", "publisher")},
            "scopes": {"text": {"outputs": ["docs/result.txt"]}},
            "complexity": {"small": ["text"]},
            "catalog": [{"id": "test", "capabilities": ["text"]}],
        }
        self.manifest = self.root / "installation.json"
        self.write_manifest()

    def write_manifest(self):
        self.manifest.write_text(json.dumps(self.spec), encoding="utf-8")
        self.digest = hashlib.sha256(self.manifest.read_bytes()).hexdigest()

    def install(self):
        result = ni.InstallationManifest(self.manifest, self.digest)
        self.addCleanup(result.close)
        return result

    def test_repeated_and_concurrent_verification_streams_source_once(self):
        with patch.object(ni, "_digest_stream", wraps=ni._digest_stream) as hashed:
            install = self.install()
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda _: install.verify(), range(31)))
            expected = 33 if install._cache else 64
            self.assertEqual(hashed.call_count, expected)

    def test_command_and_public_spec_cannot_poison_trusted_command(self):
        install = self.install()
        install.spec["commands"]["planner"]["argv"][0] = "untrusted"
        first = install.command("planner")
        first["argv"][0] = "untrusted"
        self.assertEqual(install.command("planner")["argv"], [str(self.source)])

    def test_same_length_restored_mtime_and_atomic_replacement(self):
        install = self.install()
        stamp = self.source.stat()
        replacement = self.root / "replacement.exe"
        replacement.write_bytes(b"modified" * 262144)
        if install._cache:
            with self.assertRaises(PermissionError):
                self.source.write_bytes(replacement.read_bytes())
            with self.assertRaises(PermissionError):
                os.replace(replacement, self.source)
            install.verify()
            install.close()
        os.replace(replacement, self.source)
        os.utime(self.source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        with self.assertRaises(NativeStoreError):
            ni.InstallationManifest(self.manifest, self.digest)
        with self.assertRaises(NativeStoreError):
            install.command("planner")

    def test_read_projection_does_not_admit_changed_executable(self):
        with patch.object(ni, "_retainable", return_value=False):
            install = self.install()
            self.source.write_bytes(b"changed after initial admission")
            install.verify_manifest()
            with self.assertRaises(NativeStoreError):
                install.command("producer")
            self.manifest.write_bytes(self.manifest.read_bytes() + b" ")
            with self.assertRaises(NativeStoreError):
                install.verify_manifest()

    def test_manifest_change_is_detected_even_with_restored_mtime(self):
        install = self.install()
        stamp = self.manifest.stat()
        self.manifest.write_bytes(self.manifest.read_bytes().replace(b"integrity-test", b"tampering-test"))
        os.utime(self.manifest, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        with self.assertRaises(NativeStoreError):
            install.verify()

    def test_close_is_terminal_and_allows_managed_readmission(self):
        install = self.install()
        install.close()
        install.close()
        with self.assertRaises(NativeStoreError):
            install.verify()
        self.source.write_bytes(b"updated")
        self.spec["files"][str(self.source)] = hashlib.sha256(b"updated").hexdigest()
        self.write_manifest()
        self.install().verify()

    def test_constructor_failure_releases_all_handles(self):
        self.spec["principals"]["checker"] = "producer"
        self.write_manifest()
        with self.assertRaises(NativeStoreError):
            ni.InstallationManifest(self.manifest, self.digest)
        self.source.write_bytes(b"no retained handle")

    def test_unknown_filesystem_full_hash_fallback_detects_in_place_change(self):
        with patch.object(ni, "_retainable", return_value=False):
            install = self.install()
            self.assertFalse(install._cache)
            stamp = self.source.stat()
            self.source.write_bytes(b"modified" * 262144)
            os.utime(self.source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            with self.assertRaises(NativeStoreError):
                install.verify()

    def test_changed_during_hash_rejected_and_handle_released(self):
        original = ni._identity
        count = 0

        def changed(stream):
            nonlocal count
            value = original(stream)
            count += 1
            return (*value[:-1], value[-1] + 1) if count == 2 else value

        with patch.object(ni, "_identity", side_effect=changed):
            with self.assertRaises(NativeStoreError):
                self.install()
        self.manifest.write_bytes(b"released")

    @unittest.skipUnless(os.name == "nt", "Windows sharing semantics")
    def test_existing_writer_and_writable_mapping_prevent_admission(self):
        with self.source.open("r+b"):
            with self.assertRaises(NativeStoreError):
                self.install()
        with self.source.open("r+b") as writer:
            mapped = mmap.mmap(writer.fileno(), 0)
        try:
            with self.assertRaises(NativeStoreError):
                self.install()
        finally:
            mapped.close()
        self.install().verify()

    @unittest.skipUnless(os.name == "nt", "Windows sharing semantics")
    def test_concurrent_writer_cannot_modify_admitted_source(self):
        install = self.install()
        if not install._cache:
            self.skipTest("Local NTFS required")

        def write(_):
            try:
                self.source.write_bytes(b"changed")
            except PermissionError:
                return True
            return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            self.assertTrue(all(pool.map(write, range(32))))
        install.verify()

    def test_symlink_replacement_rejected(self):
        self.source.unlink()
        other = self.root / "other.exe"
        other.write_bytes(b"original" * 262144)
        try:
            self.source.symlink_to(other)
        except OSError as exc:
            self.skipTest(str(exc))
        with self.assertRaises(NativeStoreError):
            self.install()

    def test_cached_protection_withdrawal_rejected(self):
        install = self.install()
        if not install._cache:
            self.skipTest("Immutable host source required")
        with patch.object(ni, "_retainable", return_value=False):
            with self.assertRaisesRegex(NativeStoreError, "protection withdrawn"):
                install.verify()

    @unittest.skipUnless(sys.platform == "linux", "Linux readonly mount")
    def test_real_linux_readonly_mount_reuses_digest(self):
        executable = str(Path(sys.executable).resolve())
        with open(executable, "rb") as source:
            if not os.fstatvfs(source.fileno()).f_flag & os.ST_RDONLY:
                self.skipTest("Run in read-only container image")
        self.spec["files"] = {executable: hashlib.sha256(Path(executable).read_bytes()).hexdigest()}
        for command in self.spec["commands"].values():
            command["argv"] = [executable]
        self.write_manifest()
        with patch.object(ni, "_digest_stream", wraps=ni._digest_stream) as hashed:
            install = self.install()
            self.assertIn(executable, install._cache)
            for _ in range(9):
                install.verify()
            self.assertEqual(hashed.call_count, 11)
            with patch.object(ni.os, "fstatvfs", return_value=type("Flags", (), {"f_flag": 0})()):
                with self.assertRaisesRegex(NativeStoreError, "protection withdrawn"):
                    install.verify()

    def test_revoked_authorizer_checked_before_cached_command(self):
        install = self.install()
        runtime = ni.InstalledPlannerRuntime(install, lambda _: False)
        with patch.object(install, "command", wraps=install.command) as command:
            with self.assertRaisesRegex(NativeStoreError, "credential withdrawn"):
                runtime.run({"source": "fixed"})
            command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
