"""Package format and atomic update tests; these do not claim native loader execution."""

import base64
import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import package_tianshu_board as package


def encode(data):
    payload = json.dumps(data, sort_keys=True)
    return json.dumps(dict(payload=payload, sha256=hashlib.sha256(payload.encode()).hexdigest())).encode()


class BoardPackage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        for name in ("editor_board_entry.py", "board.py", "board_delta.py", "progress.py"):
            (self.source / name).write_text("# " + name + "\n", encoding="utf-8")
        self.output = self.root / "board.json"
        self.pin = package.pack(self.source, "A", self.output)
        self.raw = self.output.read_bytes()
        self.data = package.validate(self.raw, self.pin)

    def test_deterministic_update_rollback_and_snapshot(self):
        self.assertEqual(package.pack(self.source, "A", self.output), self.pin)
        (self.source / "board.py").write_text("# candidate B\n")
        second = package.pack(self.source, "B", self.output)
        self.assertNotEqual(second, self.pin)
        self.assertEqual(package.validate(self.raw)["version"], "A")
        self.output.write_bytes(self.raw)
        self.assertEqual(package.validate(self.output.read_bytes(), self.pin)["version"], "A")

    def test_failed_replace_preserves_old_and_cleans_temporary(self):
        before = set(self.root.iterdir())
        with patch.object(package.os, "replace", side_effect=PermissionError("sharing violation")):
            with self.assertRaises(PermissionError):
                package.pack(self.source, "B", self.output)
        self.assertEqual(self.output.read_bytes(), self.raw)
        self.assertEqual(set(self.root.iterdir()), before)

    @unittest.skipUnless(sys.platform == "win32", "Windows sharing semantics")
    def test_real_windows_locked_destination(self):
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateFileW(str(self.output), 0x80000000, 1, None, 3, 0, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        try:
            with self.assertRaises(PermissionError):
                package.pack(self.source, "B", self.output)
            self.assertEqual(self.output.read_bytes(), self.raw)
        finally:
            kernel.CloseHandle(handle)
        package.pack(self.source, "B", self.output)
        self.assertEqual(package.validate(self.output.read_bytes())["version"], "B")

    def test_reject_bad_pin_payload_and_oversize(self):
        for raw, pin in (
            (self.raw, "0" * 64),
            (self.raw.replace(b"payload", b"changed"), None),
            (b"x" * (package.LIMIT + 1), None),
        ):
            with self.subTest(pin=pin, length=len(raw)), self.assertRaises((ValueError, KeyError)):
                package.validate(raw, pin)

    def test_reject_bad_fields_and_digests(self):
        changes = [
            ("abi", "unknown/2"),
            ("version", " "),
            ("version", 2),
            ("bundle_base64", "???"),
            ("bundle_sha256", "0" * 64),
            ("entries", {}),
            ("entries", {**self.data["entries"], "board.py": "0" * 64}),
        ]
        for field, value in changes:
            with self.subTest(field=field, value=value), self.assertRaises((ValueError, TypeError)):
                package.validate(encode({**self.data, field: value}))

    def test_reject_zip_ambiguity_traversal_symlink_duplicate_and_corruption(self):
        for kind in ("traversal", "duplicate", "symlink", "compressed", "corrupt", "trailing", "local_name"):
            data = copy.deepcopy(self.data)
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w") as archive:
                for index, name in enumerate(package.NAMES):
                    entry = zipfile.ZipInfo("../board.py" if kind == "traversal" and index == 1 else name)
                    entry.create_system = 0
                    if kind == "symlink" and index == 1:
                        entry.create_system = 3
                        entry.external_attr = 0o120777 << 16
                    if kind == "compressed":
                        entry.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(entry, b"# test\n")
                if kind == "duplicate":
                    archive.writestr("board.py", b"# duplicate\n")
            bundle = stream.getvalue()
            if kind == "corrupt":
                bundle = bundle[:-9]
            if kind == "trailing":
                bundle += b"ignored bytes"
            if kind == "local_name":
                bundle = bundle.replace(b"__main__.py", b"__evil__.py", 1)
            data["bundle_base64"] = base64.b64encode(bundle).decode()
            data["bundle_sha256"] = hashlib.sha256(bundle).hexdigest()
            data["entries"] = {name: hashlib.sha256(b"# test\n").hexdigest() for name in package.NAMES}
            with self.subTest(kind=kind), self.assertRaises((ValueError, zipfile.BadZipFile)):
                package.validate(encode(data))

    def test_slots_and_manifest_pin(self):
        self.assertEqual(
            package.installed_package(Path("/x/godot.self_update_a.exe")).name, "tianshu-board.self_update_a.json"
        )
        self.assertEqual(
            package.installed_package(Path("/x/App.app/Contents/MacOS/Godot")),
            Path("/x/App.app/Contents/Resources/tianshu-board.json"),
        )
        executable = self.root / "godot.exe"
        package.installed_package(executable).write_bytes(self.raw)
        manifest = dict(executable=str(executable), tianshu_board_sha256=self.pin)
        package.verify_candidate_package(manifest)
        manifest["tianshu_board_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            package.verify_candidate_package(manifest)


if __name__ == "__main__":
    unittest.main()
