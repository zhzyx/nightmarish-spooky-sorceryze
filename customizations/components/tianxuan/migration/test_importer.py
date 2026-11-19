import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import tempfile
import unittest

from importer import NativeStore, canonical, digest, import_inventory, restore_inventory, write_verified


class ArchiveTests(unittest.TestCase):
    def test_two_actors_reconcile_a_simultaneous_first_write(self):
        barrier = Barrier(2)

        class SynchronizedStore(NativeStore):
            def head(self, tenant, module):
                result = super().head(tenant, module)
                if result is None:
                    barrier.wait(timeout=10)
                return result

        with tempfile.TemporaryDirectory() as temp:
            store = SynchronizedStore(Path(temp) / "race.db")
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(write_verified, store, "tenant", actor, {"data": b"abc"})
                           for actor in ("worker1", "worker2")]
                self.assertEqual(futures[0].result(), futures[1].result())

    def test_retry_readback_and_invalid_input(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = {"state": "open", "body": "旧任务"}
            row = dict(source_id="github:a/b/issue/1", kind="issue", mode="record_only",
                       content=source, sha256=digest(canonical(source)), relations=[])
            line = canonical(row) + b"\n"
            (root / "records.jsonl").write_bytes(line)
            report = dict(historical_policy="record_only", source="a/b", revision="sample",
                          records_sha256=digest(line), counts={"issue": 1})
            manifest = root / "report.json"
            manifest.write_bytes(canonical(report))
            binary = root / "sample.bin"
            binary.write_bytes(bytes(range(256)))
            artifacts = {"sample": (binary, digest(binary.read_bytes()))}
            db = root / "native.db"
            args = manifest, db, "tenant", "migration"
            first = import_inventory(*args, artifacts=artifacts)
            self.assertEqual(first, import_inventory(*args, artifacts=artifacts))
            store = NativeStore(db)
            def read(ref, key):
                return store.read("tenant", ref["module"], ref["revision"], key)
            catalog = json.loads(read(first, "catalog.json"))
            batch, = catalog["record_batches"]
            self.assertEqual(line, read(batch, batch["order"][0]))
            blob, = catalog["binaries"]["sample"]["blocks"]
            self.assertEqual(binary.read_bytes(), read(blob, "bytes"))
            destination = root / "restored"
            restored = restore_inventory(db, "tenant", first["module"], first["revision"], destination)
            self.assertEqual((destination / "records.jsonl").read_bytes(), line)
            self.assertEqual((destination / restored["binaries"]["sample"]["file"]).read_bytes(),
                             binary.read_bytes())
            with self.assertRaises(FileExistsError):
                restore_inventory(db, "tenant", first["module"], first["revision"], destination)
            binary.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "Binary"):
                import_inventory(*args, artifacts=artifacts)
            row["content"]["state"] = "closed"
            (root / "records.jsonl").write_bytes(canonical(row))
            with self.assertRaisesRegex(ValueError, "Invalid"):
                import_inventory(*args)


if __name__ == "__main__":
    unittest.main()
