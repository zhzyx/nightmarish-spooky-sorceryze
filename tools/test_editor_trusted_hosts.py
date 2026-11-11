"""Logic tests run everywhere; MacOSIntegration uses real codesign and POSIX files."""

import contextlib
import io
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import editor_trusted_hosts as hosts

ENTRY = ("host", "ABCDEFGHIJ", "com.example.host", "a" * 40)


class RegistryLogic(unittest.TestCase):
    def test_exact_add_revoke_and_rollback(self):
        original = hosts.encode_registry([ENTRY])
        helper = ("helper", ENTRY[1], "com.example.helper", ENTRY[3])
        entries = hosts.change_registry(hosts.decode_registry(original), helper)
        self.assertEqual(len(entries), 2)
        self.assertEqual(hosts.encode_registry(hosts.change_registry(entries, helper, True)), original)
        self.assertEqual(hosts.change_registry([ENTRY], ENTRY, True), [])
        self.assertEqual(hosts.change_registry([ENTRY], ENTRY), [ENTRY])

    def test_role_upgrade_downgrade_and_exact_revocation(self):
        helper = ("helper", *ENTRY[1:])
        upgraded = hosts.change_registry([helper], ENTRY)
        self.assertEqual(upgraded, [ENTRY])
        self.assertEqual(hosts.change_registry(upgraded, helper, True), [ENTRY])
        downgraded = hosts.change_registry(upgraded, helper)
        self.assertEqual(downgraded, [helper])
        self.assertEqual(hosts.change_registry(downgraded, ENTRY, True), [helper])
        self.assertEqual(hosts.change_registry(downgraded, helper, True), [])
        self.assertEqual(hosts.change_registry([helper, ENTRY], ENTRY), [ENTRY])

    def test_invalid_policy_never_relaxes_matching(self):
        for data in (
            b"host\t*\t*\t*\n",
            b"\xff",
            b"\0",
            b"x" * 32769,
            ('host\tABCDEFGHIJ\tbad" or true\t' + "a" * 40).encode(),
            ("host\tABCDEFGHIJ\tgood\t" + "a" * 39).encode(),
        ):
            with self.subTest(data=data[:60]), self.assertRaises(hosts.TrustError):
                hosts.decode_registry(data)

    def test_permission_and_link_rejections(self):
        with patch.object(hosts.os, "getuid", return_value=501, create=True):
            for mode, uid, links in (
                (stat.S_IFREG | 0o644, 501, 1),
                (stat.S_IFREG | 0o600, 502, 1),
                (stat.S_IFREG | 0o600, 501, 2),
                (stat.S_IFLNK | 0o600, 501, 1),
            ):
                with self.assertRaises(hosts.TrustError):
                    hosts.check_private(SimpleNamespace(st_mode=mode, st_uid=uid, st_nlink=links))

    def test_signature_requirement_contains_all_pins(self):
        expression = hosts.requirement(ENTRY)
        for value in (*ENTRY[1:], "anchor apple generic", "cdhash"):
            self.assertIn(value, expression)

    def test_mock_signature_does_not_imply_platform_evidence(self):
        reply = SimpleNamespace(
            returncode=0,
            stdout="",
            stderr="Identifier=com.example.host\nTeamIdentifier=ABCDEFGHIJ\nCDHash=" + "a" * 40 + "\n",
        )
        with (
            patch.object(hosts.sys, "platform", "darwin"),
            patch.object(hosts.subprocess, "run", return_value=reply) as run,
        ):
            self.assertEqual(hosts.signed_identity(__file__, "host"), ENTRY)
            self.assertEqual(run.call_count, 3)
            self.assertIn(hosts.requirement(ENTRY), run.call_args.args[0])
        with (
            patch.object(hosts.sys, "platform", "darwin"),
            patch.object(hosts.subprocess, "run", return_value=SimpleNamespace(returncode=1)),
        ):
            with self.assertRaises(hosts.TrustError):
                hosts.signed_identity(__file__, "host")

    def test_changed_observed_identity_does_not_write(self):
        with (
            patch.object(hosts, "signed_identity", return_value=("host", *ENTRY[1:3], "b" * 40)),
            patch.object(hosts, "registry") as registry,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(
                hosts.main([
                    "register",
                    __file__,
                    "--role",
                    ENTRY[0],
                    "--team",
                    ENTRY[1],
                    "--identifier",
                    ENTRY[2],
                    "--cdhash",
                    ENTRY[3],
                ]),
                1,
            )
            registry.assert_not_called()

    @unittest.skipIf(sys.platform == "darwin", "non-macOS rejection")
    def test_registration_unsupported_on_other_platforms(self):
        with self.assertRaises(hosts.TrustError):
            hosts.signed_identity(__file__, "host")


@unittest.skipUnless(sys.platform == "darwin", "requires real macOS codesign and POSIX filesystem")
class MacOSIntegration(unittest.TestCase):
    def test_actual_adhoc_and_unsigned_executables_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "host"
            shutil.copy2("/usr/bin/true", candidate)
            subprocess.run(
                ["/usr/bin/codesign", "--force", "--sign", "-", str(candidate)], check=True, capture_output=True
            )
            with self.assertRaises(hosts.TrustError):
                hosts.signed_identity(candidate, "host")
            subprocess.run(["/usr/bin/codesign", "--remove-signature", str(candidate)], check=True, capture_output=True)
            with self.assertRaises(hosts.TrustError):
                hosts.signed_identity(candidate, "host")

    def test_actual_atomic_registration_and_revocation_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                self.assertEqual(hosts.read_registry(fd), [])
                hosts.write_registry(fd, [ENTRY])
                self.assertEqual(hosts.read_registry(fd), [ENTRY])
                hosts.write_registry(fd, hosts.change_registry(hosts.read_registry(fd), ENTRY, True))
                self.assertEqual(hosts.read_registry(fd), [])
                os.chmod(Path(directory) / "hosts-v1.tsv", 0o644)
                with self.assertRaises(hosts.TrustError):
                    hosts.read_registry(fd)
                os.unlink(Path(directory) / "hosts-v1.tsv")
                os.symlink("missing", Path(directory) / "hosts-v1.tsv")
                with self.assertRaises(OSError):
                    hosts.read_registry(fd)
            finally:
                os.close(fd)


if __name__ == "__main__":
    unittest.main()
