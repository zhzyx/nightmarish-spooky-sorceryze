import copy
import json
from pathlib import Path
import unittest

from contracts import validate

FIXTURE = Path(__file__).with_name("example.json")


class ContractsTest(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_valid_and_lossless(self):
        before = copy.deepcopy(self.doc)
        self.assertEqual(validate(self.doc), [])
        self.assertEqual(self.doc, before)
        self.assertEqual(validate(json.loads(json.dumps(self.doc))), [])

    def test_dangling_and_revision(self):
        for ref in ({"id": "absent", "revision": "1"},
                    {"id": "garment-source", "revision": "stale"}):
            with self.subTest(ref=ref):
                self.doc["artifacts"][-1]["dependencies"] = [ref]
                self.assertTrue(validate(self.doc))

    def test_cycles_including_context(self):
        self.doc["artifacts"][3]["context"] = [{
            "artifact": {"id": "garment-fit", "revision": "1"},
            "role": "structure", "scope": "torso", "strength": "constraint"}]
        self.assertTrue(any("cycle" in x for x in validate(self.doc)))

    def test_skeleton_is_not_body_envelope(self):
        self.doc["artifacts"][4]["binding"]["fit_target"]["id"] = "mixamo-profile"
        self.assertTrue(any("incompatible" in x for x in validate(self.doc)))

    def test_verified_requires_evidence(self):
        self.doc["artifacts"][4]["binding"]["level"] = "roundtrip_verified"
        self.assertTrue(validate(self.doc))

    def test_draft_needs_no_body_or_rig(self):
        self.doc["artifacts"] = [self.doc["artifacts"][3]]
        self.assertEqual(validate(self.doc), [])

    def test_report_backreference_is_not_production_cycle(self):
        subject = {"id": "garment-fit", "revision": "1"}
        self.doc["artifacts"].append({
            "id": "report", "revision": "1", "type": "validation_report",
            "payload": {"subject": subject}, "dependencies": [subject]})
        binding = self.doc["artifacts"][4]["binding"]
        binding["level"] = "roundtrip_verified"
        binding["evidence"] = {"id": "report", "revision": "1"}
        self.assertEqual(validate(self.doc), [])
        self.doc["artifacts"][-1]["payload"]["subject"] = {
            "id": "garment-fit", "revision": "old"}
        self.assertTrue(any("subject" in x for x in validate(self.doc)))

    def test_malformed_documents(self):
        for value in (None, [], {}, {"schema_version": True, "artifacts": []},
                      {"schema_version": 1, "artifacts": [None, {"id": []}]}):
            with self.subTest(value=value):
                self.assertTrue(validate(value))

    def test_duplicate_ids(self):
        self.doc["artifacts"].append(copy.deepcopy(self.doc["artifacts"][0]))
        self.assertTrue(any("duplicate" in x for x in validate(self.doc)))

    def test_context_requires_scope_and_exclusive_input(self):
        self.doc["artifacts"][3]["context"] = [{"text": "test", "artifact": {}}]
        self.assertTrue(validate(self.doc))


if __name__ == "__main__":
    unittest.main()
