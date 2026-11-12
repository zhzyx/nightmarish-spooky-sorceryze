"""Logic tests run everywhere; MacOSIntegration uses real codesign and POSIX files."""

import contextlib
import io
import os
import re
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
            stderr="Executable="
            + str(Path(__file__).resolve())
            + "\nIdentifier=com.example.host\nTeamIdentifier=ABCDEFGHIJ\nCDHash="
            + "a" * 40
            + "\n",
        )
        with (
            patch.object(hosts.sys, "platform", "darwin"),
            patch.object(
                hosts.subprocess,
                "run",
                side_effect=lambda args, **kwargs: (
                    SimpleNamespace(returncode=0, stdout="arm64", stderr="") if args[0] == "/usr/bin/lipo" else reply
                ),
            ) as run,
        ):
            self.assertEqual(hosts.signed_identity(__file__, "host"), ENTRY)
            self.assertEqual(run.call_count, 5)
            self.assertNotIn("--architecture", run.call_args_list[0].args[0])
            arguments = run.call_args.args[0]
            self.assertEqual(arguments[arguments.index("--architecture") + 1], "arm64")
            self.assertEqual(arguments[arguments.index("-R") + 1], "=" + hosts.requirement(ENTRY))
            self.assertFalse(hosts.requirement(ENTRY).startswith("="))
        with (
            patch.object(hosts.sys, "platform", "darwin"),
            patch.object(
                hosts.subprocess, "run", return_value=SimpleNamespace(returncode=1, stdout="", stderr="bad signature")
            ),
        ):
            with self.assertRaises(hosts.TrustError):
                hosts.signed_identity(__file__, "host")

    def test_requirement_failure_preserves_stage_and_codesign_diagnostic(self):
        valid = SimpleNamespace(returncode=0, stdout="", stderr="")
        details = SimpleNamespace(
            returncode=0,
            stdout="",
            stderr="Executable="
            + str(Path(__file__).resolve())
            + "\nIdentifier=com.example.host\nTeamIdentifier=ABCDEFGHIJ\nCDHash="
            + "a" * 40
            + "\n",
        )
        invalid = SimpleNamespace(
            returncode=1, stdout="", stderr="test requirement: code failed to satisfy specified code requirement(s)"
        )
        diagnostics = []
        with (
            patch.object(hosts.sys, "platform", "darwin"),
            patch.object(
                hosts.subprocess,
                "run",
                side_effect=[
                    valid,
                    details,
                    SimpleNamespace(returncode=0, stdout="arm64", stderr=""),
                    details,
                    invalid,
                ],
            ),
            self.assertRaisesRegex(hosts.TrustError, "exact_requirement: exit=1: test requirement"),
        ):
            hosts.signed_identity(__file__, "host", diagnostics=diagnostics)
        self.assertEqual(
            [item["stage"] for item in diagnostics], ["integrity", "identity", "slice_identity", "exact_requirement"]
        )
        self.assertEqual(diagnostics[-1]["stderr"], invalid.stderr)
        self.assertEqual(diagnostics[-1]["exit_code"], 1)

    def test_observed_slice_is_bound_independent_of_architecture_order(self):
        for selected in ("arm64", "x86_64"):
            with self.subTest(selected=selected):

                def run(args, **kwargs):
                    if args[0] == "/usr/bin/lipo":
                        return SimpleNamespace(returncode=0, stdout="x86_64 arm64", stderr="")
                    architecture = args[args.index("--architecture") + 1] if "--architecture" in args else selected
                    digest = "a" * 40 if architecture == selected else "b" * 40
                    return SimpleNamespace(
                        returncode=0,
                        stdout="",
                        stderr=f"Executable={Path(__file__).resolve()}\nIdentifier=com.example.host\nTeamIdentifier=ABCDEFGHIJ\nCDHash={digest}\n",
                    )

                with (
                    patch.object(hosts.sys, "platform", "darwin"),
                    patch.object(hosts.subprocess, "run", side_effect=run) as invoked,
                ):
                    self.assertEqual(hosts.signed_identity(__file__, "host"), ENTRY)
                    final = invoked.call_args.args[0]
                    self.assertEqual(final[final.index("--architecture") + 1], selected)
                    self.assertIn("=" + hosts.requirement(ENTRY), final)

    def test_duplicate_slice_identity_is_rejected(self):
        def run(args, **kwargs):
            if args[0] == "/usr/bin/lipo":
                return SimpleNamespace(returncode=0, stdout="x86_64 arm64", stderr="")
            return SimpleNamespace(
                returncode=0,
                stdout="",
                stderr=f"Executable={Path(__file__).resolve()}\nIdentifier=com.example.host\nTeamIdentifier=ABCDEFGHIJ\nCDHash={'a' * 40}\n",
            )

        with (
            patch.object(hosts.sys, "platform", "darwin"),
            patch.object(hosts.subprocess, "run", side_effect=run),
            self.assertRaisesRegex(hosts.TrustError, "host_observed_architecture_ambiguous"),
        ):
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
    def test_actual_universal_exact_digest_requires_same_slice(self):
        binary = "/usr/bin/true"
        architectures = subprocess.run(
            ["/usr/bin/lipo", "-archs", binary], check=True, capture_output=True, text=True
        ).stdout.split()
        if len(architectures) < 2:
            self.skipTest("system fixture is not universal; no cross-slice evidence")
        subprocess.run(["/usr/bin/codesign", "--verify", "--strict", binary], check=True, capture_output=True)
        details = subprocess.run(
            ["/usr/bin/codesign", "--display", "--verbose=4", "--architecture", architectures[0], binary],
            check=True,
            capture_output=True,
            text=True,
        )
        hashes = re.findall(r"^CDHash=([a-f0-9]{40})$", details.stdout + details.stderr, re.MULTILINE)
        self.assertEqual(len(hashes), 1)
        expression = '=anchor apple and cdhash H"' + hashes[0] + '"'
        subprocess.run(
            ["/usr/bin/codesign", "--verify", "--strict", "--architecture", architectures[0], "-R", expression, binary],
            check=True,
            capture_output=True,
        )
        other = subprocess.run(
            ["/usr/bin/codesign", "--verify", "--strict", "--architecture", architectures[1], "-R", expression, binary],
            capture_output=True,
        )
        self.assertNotEqual(other.returncode, 0)
        all_slices = subprocess.run(
            ["/usr/bin/codesign", "--verify", "--strict", "-R", expression, binary], capture_output=True
        )
        self.assertNotEqual(all_slices.returncode, 0)

    def test_actual_codesign_literal_requirement_is_not_a_filename(self):
        # Exercise Apple's actual -R parser, without modifying or registering
        # the system binary. This is syntax evidence, not third-party host trust.
        expression = "anchor apple"
        subprocess.run(
            ["/usr/bin/codesign", "--verify", "--strict", "-R", "=" + expression, "/usr/bin/true"],
            check=True,
            capture_output=True,
        )
        bare = subprocess.run(
            ["/usr/bin/codesign", "--verify", "--strict", "-R", expression, "/usr/bin/true"],
            capture_output=True,
        )
        self.assertNotEqual(bare.returncode, 0)

    def test_actual_adhoc_and_unsigned_executables_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "host"
            # Copy executable bytes without the system binary's protected flags.
            shutil.copyfile("/usr/bin/true", candidate)
            candidate.chmod(0o700)
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
