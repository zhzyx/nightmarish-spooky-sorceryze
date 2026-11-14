"""Structural drift checks for M3 v1 schemas; no Artifact payload restriction."""

import json
import unittest
from pathlib import Path


class AssetSchemaTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]
        self.manifest = json.loads(
            (self.root / "engine_next/Schemas/AssetManifest-v1.json").read_text(encoding="utf-8")
        )

    def test_source_requires_exact_fields_and_kind_specific_provenance(self):
        source = self.manifest["properties"]["assets"]["items"]["properties"]["source"]
        self.assertFalse(source["additionalProperties"])
        self.assertEqual(source["required"], ["kind"])
        self.assertEqual(set(source["properties"]), {"kind", "artifact_id", "artifact_revision", "importer_version"})
        conditions = source["allOf"]
        self.assertEqual(conditions[0]["then"]["required"], ["artifact_id", "artifact_revision"])
        self.assertEqual(conditions[0]["then"]["not"], {"required": ["importer_version"]})
        self.assertEqual(conditions[1]["then"]["required"], ["importer_version"])
        self.assertEqual(
            conditions[1]["then"]["not"],
            {"anyOf": [{"required": ["artifact_id"]}, {"required": ["artifact_revision"]}]},
        )

    def test_dependency_identity_patterns_match_top_level_contract(self):
        asset = self.manifest["properties"]["assets"]["items"]["properties"]
        dependency = asset["dependencies"]["items"]["properties"]
        self.assertEqual(dependency["asset_id"]["pattern"], asset["asset_id"]["pattern"])
        self.assertEqual(dependency["revision"]["pattern"], asset["revision"]["pattern"])
        self.assertEqual(dependency["content_sha256"]["pattern"], asset["content_sha256"]["pattern"])

    def test_schema_does_not_define_or_wrap_artifact_payload(self):
        text = json.dumps(self.manifest)
        self.assertNotIn('"payload"', text)
        self.assertNotIn('"artifacts"', text)


if __name__ == "__main__":
    unittest.main()
