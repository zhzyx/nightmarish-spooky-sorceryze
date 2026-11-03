"""Migration regressions use synthetic isolated repositories, never production facts."""

import importlib.util
import json
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(p, name):
    spec = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


api = load(ROOT / "framework/extensions/diting-files/diting_files.py", "migration_data")
paths = load(ROOT / "customizations/components/godot-host/workspace_paths.py", "migration_paths")


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True)
        for name, origin in [("gonggong-diting-data", "gonggong"), ("olympus-hermes-data", "olympus")]:
            d = self.root / name
            d.mkdir()
            (d / "dataset.json").write_text(
                json.dumps({
                    "schema_version": 1,
                    "dataset_id": str(uuid.uuid4()),
                    "name": name,
                    "origin_framework": origin,
                })
            )

    def event(self, tenant="old-tenant", ident="event-1"):
        return api.event({
            "schema_version": 1,
            "event_id": ident,
            "tenant_id": tenant,
            "request_id": "synthetic-request",
            "kind": "request",
            "occurred_at": "2026-01-01T00:00:00Z",
            "source_ref": "synthetic-only",
            "agent": {"id": "fixture", "version": "test", "origin": "synthetic", "definition_sha256": "0" * 64},
            "payload": {"test_only": True},
            "evidence_refs": [],
        })

    def save(self, name, event):
        p = self.root / name / "events" / event["tenant_id"] / event["request_id"] / (event["event_id"] + ".json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(event))
        return p

    def test_old_bytes_unchanged_after_new_record(self):
        p = self.save("olympus-hermes-data", self.event())
        before = p.read_bytes()
        input = self.root / "input.json"
        input.write_text(json.dumps(self.event("new-tenant", "new-event")))
        api.record(self.root, input)
        self.assertEqual(p.read_bytes(), before)
        self.assertEqual(api.analyze(self.root, "old-tenant")["events"], 1)
        self.assertEqual(api.analyze(self.root, "new-tenant")["events"], 1)

    def test_identical_cross_source_identity_deduplicated(self):
        e = self.event()
        self.save("olympus-hermes-data", e)
        self.save("gonggong-diting-data", e)
        self.assertEqual(api.analyze(self.root, "old-tenant")["events"], 1)

    def test_conflicting_cross_source_identity_rejected(self):
        e = self.event()
        self.save("olympus-hermes-data", e)
        e.pop("sha256")
        e["payload"]["test_only"] = "conflict"
        self.save("gonggong-diting-data", api.event(e))
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            api.analyze(self.root, "old-tenant")

    def test_conflicting_write_is_rejected_before_persistence(self):
        e = self.event()
        self.save("olympus-hermes-data", e)
        e.pop("sha256")
        e["payload"]["test_only"] = "conflict"
        f = self.root / "input.json"
        f.write_text(json.dumps(api.event(e)))
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            api.record(self.root, f)
        self.assertEqual(api.load(self.root)[3], {})

    def test_identical_historical_write_returns_without_copy(self):
        e = self.event()
        self.save("olympus-hermes-data", e)
        f = self.root / "input.json"
        f.write_text(json.dumps(e))
        self.assertTrue(api.record(self.root, f)["historical_read_only"])
        self.assertEqual(api.load(self.root)[3], {})

    def test_cross_tenant_reference_rejected(self):
        self.save("gonggong-diting-data", self.event())
        e = self.event("other-tenant", "event-2")
        e.pop("sha256")
        e["evidence_refs"] = ["event-1"]
        self.save("gonggong-diting-data", api.event(e))
        with self.assertRaisesRegex(ValueError, "Missing evidence"):
            api.load(self.root)

    def test_historical_checksum_not_rewritten(self):
        p = self.save("olympus-hermes-data", self.event())
        v = json.loads(p.read_text())
        v["payload"] = {"changed": True}
        p.write_text(json.dumps(v))
        with self.assertRaisesRegex(ValueError, "checksum"):
            api.analyze(self.root, "old-tenant")

    def test_pointer_rejects_escape(self):
        (self.root / "CURRENT_FRAMEWORK.json").write_text(
            json.dumps({
                "path_base": "this_file_directory",
                "root": "../outside",
                "manifest": "framework-manifest.json",
            })
        )
        with self.assertRaises(ValueError):
            paths.framework_root(self.root)

    def test_pointer_independent_of_cwd(self):
        target = self.root / "current"
        target.mkdir()
        (target / "framework-manifest.json").write_text("{}")
        (self.root / "CURRENT_FRAMEWORK.json").write_text(
            json.dumps({"path_base": "this_file_directory", "root": "current", "manifest": "framework-manifest.json"})
        )
        self.assertEqual(paths.framework_root(self.root), target)

    def test_legacy_metadata_not_accepted_as_current(self):
        p = self.root / "gonggong-diting-data/dataset.json"
        v = json.loads(p.read_text())
        v["origin_framework"] = "olympus"
        p.write_text(json.dumps(v))
        with self.assertRaisesRegex(ValueError, "manifest"):
            api.load(self.root)


if __name__ == "__main__":
    unittest.main()
