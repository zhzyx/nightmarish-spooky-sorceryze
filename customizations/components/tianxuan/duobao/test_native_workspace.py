import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from native_store import Conflict, NativeStore, NativeStoreError
from native_workspace import MANIFEST, Limits, NativeWorkspace, portable


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


if __name__ == "__main__":
    unittest.main()
