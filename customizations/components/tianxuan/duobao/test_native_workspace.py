import base64
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from native_store import Conflict, NativeStore, NativeStoreError
from native_workspace import (
    MANIFEST,
    Limits,
    NativeWorkspace,
    _capture_stage_owner,
    _cleanup_owned_stage,
    _rename_prepared,
    portable,
)


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = NativeStore(self.root / "native.sqlite")
        self.ws = NativeWorkspace(self.store)
        self.counter = 0
        self.dep = self.create("dep", {"data": b"dependency"})
        self.base = self.create(
            "app", {"a.txt": b"old", "delete.txt": b"delete", "large.txt": b"x" * 100000}, {"dep": self.dep}
        )
        self.selected = {"app": self.base}

    def create(self, module, edits, dependencies=None, base=None):
        self.counter += 1
        change = {"module": module, "base": base, "reads": None, "edits": edits}
        if dependencies is not None:
            change["dependencies"] = dependencies
        return self.store.submit("org", "actor", "req" + str(self.counter), [change])["revisions"][module]

    def snapshot(self):
        path = self.root / "work"
        self.ws.materialize("org", self.selected, path)
        return path

    def cli(self, command, request, tenant="org"):
        proc = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("native_workspace_cli.py")),
                "--db",
                str(self.root / "native.sqlite"),
                "--tenant",
                tenant,
                command,
            ],
            input=json.dumps(request).encode(),
            capture_output=True,
            cwd=self.root,
            env={**os.environ, "PATH": ""},
            timeout=30,
        )
        return proc.returncode, json.loads(proc.stdout)

    def test_materializers_reject_replacement_before_helper_entry(self):
        import native_check_inputs as ci
        import native_workspace as nw

        for kind in ("workspace", "check"):
            with self.subTest(kind=kind):
                destination = self.root / (kind + "-published")
                original = self.root / (kind + "-created")
                stages = []

                def replace(stage, dest, limits, owner):
                    _rename_prepared(stage, original, limits, owner)
                    stage.mkdir()
                    (stage / "foreign").write_bytes(b"foreign")
                    stages.append(stage)
                    return _rename_prepared(stage, dest, limits, owner)

                module = nw if kind == "workspace" else ci
                with patch.object(module, "_rename_prepared", replace):
                    with self.assertRaisesRegex(NativeStoreError, "identity or ancestry") as error:
                        if kind == "workspace":
                            self.ws.materialize("org", self.selected, destination)
                        else:
                            ci.CheckInputView("{}", Limits()).materialize(None, "org", destination)
                self.assertFalse(destination.exists())
                self.assertTrue(original.is_dir())
                self.assertEqual((stages[0] / "foreign").read_bytes(), b"foreign")
                self.assertTrue(error.exception.__notes__)

    def test_changed_normal_ancestor_preserves_same_owned_stage(self):
        parent = self.root / "parent"
        parent.mkdir()
        stage = parent / "stage"
        stage.mkdir()
        owner = _capture_stage_owner(stage)
        (stage / "owned").write_bytes(b"owned")
        parent.rename(self.root / "old-parent")
        parent.mkdir()
        (self.root / "old-parent" / "stage").rename(stage)
        with patch.object(Path, "rename") as rename:
            with self.assertRaisesRegex(NativeStoreError, "identity or ancestry"):
                _rename_prepared(stage, parent / "published", Limits(), owner)
        rename.assert_not_called()
        original = PermissionError(13, "first failure")
        _cleanup_owned_stage(stage, owner, original)
        self.assertEqual((stage / "owned").read_bytes(), b"owned")
        self.assertTrue(original.__notes__)
        self.assertTrue((self.root / "old-parent").is_dir())

    def test_cli_empty_path_roundtrip_restart(self):
        path = self.root / "work"
        code, result = self.cli("materialize", {"selected": self.selected, "destination": str(path)})
        self.assertEqual(code, 0, result)
        self.assertFalse((path / ".git").exists())
        subprocess.run(
            [sys.executable, "-c", "from pathlib import Path; Path('app/a.txt').write_text('new')"],
            cwd=path,
            env={**os.environ, "PATH": ""},
            check=True,
        )
        (path / "app/delete.txt").unlink()
        (path / "app/empty").write_bytes(b"")
        (path / "app/binary").write_bytes(b"\xff\x00")
        (path / MANIFEST).write_text('{"tenant":"other","modules":{}}')
        code, candidate = self.cli("collect", {"selected": self.selected, "workspace": str(path)})
        self.assertEqual(code, 0, candidate)
        self.assertIsNone(candidate["data"]["changes"][0]["reads"])
        request = {"selected": self.selected, "workspace": str(path), "actor": "actor", "request_key": "cli"}
        code, result = self.cli("submit", request)
        self.assertEqual(code, 0, result)
        self.assertEqual(self.cli("submit", request)[1], result)
        fresh = NativeStore(self.root / "native.sqlite")
        rev = result["data"]["revisions"]["app"]
        self.assertEqual(fresh.read("org", "app", rev, "binary"), b"\xff\x00")
        self.assertEqual(fresh.revision("org", "app", rev)["dependencies"], {"dep": self.dep})
        self.assertNotIn("delete.txt", fresh.revision("org", "app", rev)["objects"])

    def test_unrelated_drift_pins_and_atomic_conflict(self):
        path = self.snapshot()
        self.create("unrelated", {"file": b"other"})
        self.create("dep", {"data": b"new dep"}, base=self.dep)
        self.assertEqual((path / "dep/data").read_bytes(), b"dependency")
        (path / "app/a.txt").write_bytes(b"updated")
        result = self.ws.submit("org", "actor", "success", self.selected, path)
        self.assertEqual(
            self.store.revision("org", "app", result["revisions"]["app"])["dependencies"], {"dep": self.dep}
        )
        (path / "dep/data").write_bytes(b"changed")
        heads = {m: self.store.head("org", m) for m in ("app", "dep")}
        with self.assertRaises(Conflict):
            self.ws.submit("org", "actor", "conflict", self.selected, path)
        self.assertEqual(heads, {m: self.store.head("org", m) for m in heads})

    def test_unknown_reads_reject_drift_before_decoding_new_head(self):
        original = self.create("bounded", {"a": b"old"})
        workspace = NativeWorkspace(self.store, Limits(request_bytes=512))
        target = self.root / "bounded-work"
        workspace.materialize("org", {"bounded": original}, target)
        advanced = self.create("bounded", {f"extra-{n}": b"x" for n in range(200)}, base=original)
        (target / "bounded/a").write_bytes(b"local change")
        read_revision = self.store._revision
        decoded = []

        def observed(db, tenant, module, revision):
            decoded.append(revision)
            self.assertNotEqual(revision, advanced, "known conflict decoded the unneeded new head")
            return read_revision(db, tenant, module, revision)

        with patch.object(self.store, "_revision", side_effect=observed), self.assertRaises(Conflict):
            workspace.submit("org", "actor", "bounded-conflict", {"bounded": original}, target)
        self.assertNotIn(advanced, decoded)
        self.assertEqual(self.store.head("org", "bounded"), advanced)

    def test_cross_module_atomic_success(self):
        path = self.snapshot()
        for module, name in (("app", "a.txt"), ("dep", "data")):
            (path / module / name).write_bytes(b"edited")
        result = self.ws.submit("org", "actor", "batch", self.selected, path)
        self.assertEqual(set(result["revisions"]), {"app", "dep"})

    def test_paths_aliases_and_existing_destination(self):
        for name in ("../x", "/x", "a\\b", "a:b", "CON.txt", "LPT¹.log", "x.", "x ", ".git", "SHORT~1", "a//b"):
            with self.subTest(name=name), self.assertRaises(NativeStoreError):
                portable(name)
        path = self.snapshot()
        (path / "keep").write_bytes(b"user")
        with self.assertRaises(NativeStoreError):
            self.ws.materialize("org", self.selected, path)
        self.assertEqual((path / "keep").read_bytes(), b"user")
        alias = self.create("alias", {"A/a": b"a", "a/b": b"b"})
        with self.assertRaises(NativeStoreError):
            self.ws.materialize("org", {"alias": alias}, self.root / "alias")
        with self.assertRaises(NativeStoreError):
            self.ws.materialize("other", self.selected, self.root / "other")

    def test_source_corruption_and_write_failure_unpublished(self):
        original = Path.open
        writes = []

        def fail_write(path, mode="r", *args, **kwargs):
            if mode == "xb":
                writes.append(path)
                if len(writes) == 2:
                    raise OSError("injected second file write failure")
            return original(path, mode, *args, **kwargs)

        with patch.object(Path, "open", fail_write):
            with self.assertRaises(OSError):
                self.snapshot()
        self.assertEqual(len(writes), 2)
        self.assertFalse((self.root / "work").exists())
        self.assertEqual(list(self.root.glob(".duobao-stage-*")), [])
        with self.store._connection(write=True) as db:
            db.execute("UPDATE native_blobs SET content=? WHERE tenant=?", (b"bad", "org"))
        with self.assertRaises(NativeStoreError):
            self.snapshot()
        self.assertFalse((self.root / "work").exists())

    def test_scan_unknown_module_and_directory_budget(self):
        path = self.snapshot()
        (path / "unknown").mkdir()
        with self.assertRaises(NativeStoreError):
            self.ws.collect("org", self.selected, path)
        with self.assertRaises(NativeStoreError):
            NativeWorkspace(self.store, Limits(entries=1)).materialize("org", self.selected, self.root / "limited")

    @unittest.skipIf(os.name == "nt", "POSIX fifo test")
    def test_nonregular_file_rejected(self):
        path = self.snapshot()
        os.mkfifo(path / "app/fifo")
        with self.assertRaises(NativeStoreError):
            self.ws.collect("org", self.selected, path)

    def test_resource_limits(self):
        for limit in (Limits(files=1), Limits(file_bytes=2), Limits(total_bytes=2), Limits(modules=1)):
            with self.subTest(limit=limit), self.assertRaises(NativeStoreError):
                NativeWorkspace(self.store, limit).materialize("org", self.selected, self.root / "bad")
        path = self.snapshot()
        (path / "app/oversize").write_bytes(b"x" * 100001)
        with self.assertRaises(NativeStoreError):
            NativeWorkspace(self.store, Limits(file_bytes=100000)).collect("org", self.selected, path)
        with self.assertRaises(NativeStoreError):
            NativeWorkspace(self.store, Limits(entries=1)).collect("org", self.selected, path)
        proc = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("native_workspace_cli.py")),
                "--db",
                str(self.root / "native.sqlite"),
                "--tenant",
                "org",
                "collect",
            ],
            input=b" " * (Limits().request_bytes + 1),
            stdout=subprocess.PIPE,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 2)

    def test_delta_pagination_binary_empty_binding_and_transfer(self):
        after = self.create(
            "app", {"a.txt": b"new", "delete.txt": None, "empty": b"", "binary": b"\xff\x00"}, base=self.base
        )
        adapter = NativeWorkspace(self.store, Limits(page_items=1))
        pages, cursor = [], None
        while True:
            page = adapter.delta("org", "app", self.base, after, cursor=cursor)
            self.assertEqual(page, adapter.delta("org", "app", self.base, after, cursor=cursor))
            pages.append(page)
            cursor = page["next_cursor"]
            if cursor is None:
                break
            with self.assertRaises(NativeStoreError):
                adapter.delta("org", "app", after, self.base, cursor=cursor)
        items = {i["name"]: i for p in pages for i in p["items"]}
        self.assertEqual(set(items), {"a.txt", "delete.txt", "empty", "binary"})
        self.assertEqual(items["empty"]["content"], "")
        self.assertEqual(base64.b64decode(items["binary"]["content"]), b"\xff\x00")
        self.assertEqual(items["binary"]["encoding"], "base64")
        self.assertLess(len(json.dumps(pages).encode()), 100000)
        huge = self.create("app", {"large.txt": b"y" * 100000}, base=after)
        page = NativeWorkspace(self.store, Limits(page_bytes=1000)).delta("org", "app", after, huge)
        self.assertTrue(page["truncated"])
        self.assertTrue(page["items"][0]["content_omitted"])
        self.assertIsNone(page["next_cursor"])

    def test_links_rejected(self):
        path = self.snapshot()
        link = path / "app/link"
        try:
            link.symlink_to(self.root / "native.sqlite")
        except OSError as error:
            self.skipTest("Host cannot create symlink: " + str(error))
        with self.assertRaises(NativeStoreError):
            self.ws.collect("org", self.selected, path)

    @unittest.skipUnless(os.name == "nt", "Windows junction test")
    def test_windows_junction_rejected(self):
        path = self.snapshot()
        junction = path / "app/junction"
        subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(self.root)], check=True, capture_output=True)
        try:
            with self.assertRaises(NativeStoreError):
                self.ws.collect("org", self.selected, path)
        finally:
            junction.rmdir()


class DeviceAliasCodepointTests(unittest.TestCase):
    def test_reserved_aliases_are_exact_unicode_codepoints(self):
        # Numeric codepoints prevent source transcoding from silently changing
        # both the production guard and its expected test strings together.
        for prefix in ("COM", "LPT"):
            for codepoint in (185, 178, 179):
                name = prefix + chr(codepoint) + ".log"
                with self.subTest(prefix=prefix, codepoint=codepoint), self.assertRaises(NativeStoreError):
                    portable(name)
            for codepoint in (0x9E7F, 0x864F, 0x9C81):
                name = prefix + chr(codepoint) + ".log"
                with self.subTest(prefix=prefix, codepoint=codepoint):
                    self.assertEqual(portable(name), name)


@unittest.skipUnless(os.name == "nt", "Windows directory rename semantics")
class WindowsRenameTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stage = self.root / "stage"
        self.stage.mkdir()
        self.owner = _capture_stage_owner(self.stage)
        (self.stage / "file").write_bytes(b"original")
        os.utime(self.stage / "file", (946684800, 946684800))
        self.destination = self.root / "destination"

    def test_real_child_handle_release_and_held_budget(self):
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
        handle = kernel.CreateFileW(str(self.stage / "file"), 0x80000000, 7, None, 3, 0, None)
        self.assertNotEqual(handle, wintypes.HANDLE(-1).value)
        try:
            with self.assertRaises(OSError) as old:
                self.stage.rename(self.destination)
            self.assertEqual(old.exception.winerror, 5)
            started = time.monotonic()
            with self.assertRaises(OSError) as held:
                _rename_prepared(self.stage, self.destination, Limits(), self.owner)
            self.assertEqual(held.exception.winerror, 5)
            self.assertLess(time.monotonic() - started, 1)
            self.assertFalse(self.destination.exists())
            timer = threading.Timer(0.04, kernel.CloseHandle, args=(handle,))
            timer.start()
            try:
                _rename_prepared(self.stage, self.destination, Limits(), self.owner)
            finally:
                timer.join()
                handle = None
            self.assertEqual((self.destination / "file").read_bytes(), b"original")
        finally:
            if handle is not None:
                kernel.CloseHandle(handle)

    def test_permanent_errors_and_retry_mutations_fail_closed(self):
        for mode in ("denied", "errno_only", "destination", "content", "replacement", "junction"):
            with self.subTest(mode=mode):
                if mode != "denied":
                    self.tearDown_case()
                original = PermissionError(13, "permanent denial")
                if mode != "errno_only":
                    original.winerror = 5
                owner = self.owner
                calls = []

                def deny(path, destination):
                    calls.append(path)
                    if len(calls) == 1:
                        if mode == "destination":
                            destination.mkdir()
                        elif mode == "content":
                            (path / "file").write_bytes(b"changed")
                        elif mode in ("replacement", "junction"):
                            os.rename(path, self.root / "original-stage")
                            if mode == "replacement":
                                path.mkdir()
                            else:
                                subprocess.run(
                                    ["cmd", "/c", "mklink", "/J", str(path), str(self.root / "original-stage")],
                                    check=True,
                                    capture_output=True,
                                )
                    raise original

                with patch.object(Path, "rename", deny):
                    with self.assertRaises(PermissionError) as error:
                        _rename_prepared(self.stage, self.destination, Limits(), self.owner)
                self.assertIs(error.exception, original)
                self.assertEqual(len(calls), 4 if mode == "denied" else 1)
                if mode in ("replacement", "junction"):
                    _cleanup_owned_stage(self.stage, owner, original)
                    self.assertTrue(self.stage.exists())
                    self.assertTrue((self.root / "original-stage/file").exists())

    def test_changed_normal_ancestor_between_retries_preserves_first_error(self):
        outer = self.root / "outer"
        outer.mkdir()
        stage = outer / "stage"
        stage.mkdir()
        (stage / "owned").write_bytes(b"owned")
        owner = _capture_stage_owner(stage)
        original = PermissionError(13, "first denial")
        original.winerror = 5
        calls = []

        def deny(path, destination):
            calls.append(path)
            os.rename(outer, self.root / "old-outer")
            outer.mkdir()
            os.rename(self.root / "old-outer" / "stage", stage)
            raise original

        with patch.object(Path, "rename", deny):
            with self.assertRaises(PermissionError) as error:
                _rename_prepared(stage, outer / "destination", Limits(), owner)
        self.assertIs(error.exception, original)
        self.assertEqual(len(calls), 1)
        _cleanup_owned_stage(stage, owner, original)
        self.assertEqual((stage / "owned").read_bytes(), b"owned")
        self.assertTrue(original.__notes__)

    def tearDown_case(self):
        self.temp.cleanup()
        self.setUp()


if __name__ == "__main__":
    unittest.main()
