import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from extensions import (NodeRegistry, canonical, provider_manifest, publish_new,
                        validate_invocation, validate_job, validate_outputs)


class ExtensionTests(unittest.TestCase):
    def setUp(self):
        self.registry = NodeRegistry()
        self.definition = {
            "id": "garment.fit", "version": "1",
            "inputs": {"source": {"types": ["garment"], "required": True},
                       "target": {"types": ["skeleton_profile"], "required": False}},
            "outputs": {"result": {"types": ["garment"], "required": True}},
            "context_types": ["text", "image"], "capabilities": ["garment.fit"],
            "parameters": {"properties": {"seed": {"type": "integer"}}, "required": ["seed"]}}
        self.registry.register(self.definition)
        self.manifest = json.loads(Path(__file__).with_name("example.json").read_text(encoding="utf-8"))
        self.provider = {"id": "fixture", "version": "1", "model": "synthetic",
                         "model_version": "1", "capabilities": ["garment.fit"],
                         "context_types": ["text", "image"], "available": True}
        self.request = {"node": "garment.fit", "version": "1",
                        "inputs": {"source": {"id": "garment-source", "revision": "1"}},
                        "parameters": {"seed": 0}, "context": [
                            {"text": "keep armor rigid", "role": "design", "scope": "torso", "strength": "constraint"}]}

    def key(self):
        return validate_invocation(self.registry, self.request, self.manifest, self.provider)

    def test_registration_roundtrip_and_immutability(self):
        self.registry.register(json.loads(canonical(self.definition)))
        readback = self.registry.get("garment.fit", "1")
        readback["context_types"].clear()
        self.assertEqual(self.registry.get("garment.fit", "1"), self.definition)
        self.definition["context_types"].clear()
        with self.assertRaises(ValueError):
            self.registry.register(self.definition)

    def test_reproducibility_and_invalidation(self):
        original = self.key()
        self.request = json.loads(canonical(self.request))
        self.assertEqual(original, self.key())
        self.request["parameters"]["seed"] = 1
        self.assertNotEqual(original, self.key())
        original = self.key()
        self.provider["model_version"] = "2"
        self.assertNotEqual(original, self.key())
        original = self.key()
        self.manifest["artifacts"][0]["payload"]["bone_axes"] = "changed"
        self.assertNotEqual(original, self.key())

    def test_node_immutability_preserves_json_numeric_types(self):
        definition = copy.deepcopy(self.definition)
        definition["version"] = "numeric-types"
        definition["parameters"]["properties"]["seed"]["enum"] = [1]
        self.registry.register(definition)
        for replacement in (1.0, True):
            changed = copy.deepcopy(definition)
            changed["parameters"]["properties"]["seed"]["enum"] = [replacement]
            with self.subTest(replacement=replacement), self.assertRaisesRegex(ValueError, "immutable"):
                self.registry.register(changed)
        self.assertEqual(canonical(self.registry.get("garment.fit", "numeric-types")), canonical(definition))

    def test_terminal_receipt_preserves_json_numeric_types(self):
        receipt = {"job_id": "numeric-job", "state": "succeeded", "outputs": {"result": {"value": 1}}, "error": None}
        validate_job(copy.deepcopy(receipt), receipt)
        for replacement in (1.0, True):
            changed = copy.deepcopy(receipt)
            changed["outputs"]["result"]["value"] = replacement
            with self.subTest(replacement=replacement), self.assertRaisesRegex(ValueError, "immutable"):
                validate_job(changed, receipt)

    def test_target_profiles_and_unbound_garment(self):
        self.key()
        for target in ("ue5-body-profile", "mixamo-profile"):
            self.request["inputs"]["target"] = {"id": target, "revision": "fixture-v1"}
            self.key()  # A request contract, NOT proof of real fitting.

    def test_input_type_revision_and_required_port(self):
        for inputs in ({}, {"source": {"id": "garment-source", "revision": "old"}},
                       {"source": {"id": "mixamo-profile", "revision": "fixture-v1"}}):
            self.request["inputs"] = inputs
            with self.subTest(inputs=inputs), self.assertRaises(ValueError):
                self.key()

    def test_parameter_dialect_rejects_unknown_and_bool_integer(self):
        for params in ({"seed": True}, {"seed": 1, "unregistered": 0}, {}):
            self.request["parameters"] = params
            with self.subTest(params=params), self.assertRaises(ValueError):
                self.key()
        self.definition["version"] = "2"
        self.definition["parameters"]["$ref"] = "ignored?"
        with self.assertRaises(ValueError):
            self.registry.register(self.definition)

    def test_context_and_capability_negotiation(self):
        image = {"id": "reference", "revision": "1", "type": "image", "payload": {"uri": "fixture://image"}}
        self.manifest["artifacts"].append(image)
        self.request["context"].append({"artifact": {"id": "reference", "revision": "1"},
                                         "role": "style", "scope": "sleeve", "strength": "reference"})
        self.key()
        self.provider["context_types"] = ["text"]
        with self.assertRaises(ValueError):
            self.key()
        self.provider["context_types"] = ["text", "image"]
        self.provider["capabilities"] = []
        with self.assertRaises(ValueError):
            self.key()

    def test_job_transitions_and_terminal_receipts(self):
        queued = {"job_id": "job", "state": "queued", "outputs": {}, "error": None}
        running = {**queued, "state": "running"}
        done = {**queued, "state": "succeeded", "outputs": {"result": {"id": "garment-fit", "revision": "1"}}}
        validate_job(running, queued)
        validate_job(done, running)
        validate_job(done, queued)  # A poll may skip a short-lived running state.
        validate_job(done, done)
        for invalid in ({**done, "job_id": "other"}, running, {**done, "outputs": {}}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_job(invalid, done)
        cancelled = {**queued, "state": "cancelled"}
        with self.assertRaises(ValueError):
            validate_job(done, cancelled)

    def test_output_port_contract(self):
        outputs = {"result": {"id": "garment-fit", "revision": "1"}}
        validate_outputs(self.registry, "garment.fit", "1", outputs, self.manifest)
        for bad in ({}, {"other": outputs["result"]}, {"result": {"id": "mixamo-profile", "revision": "fixture-v1"}}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_outputs(self.registry, "garment.fit", "1", bad, self.manifest)

    def test_publish_is_atomic_no_overwrite_and_copy_isolation(self):
        class Encoder:
            def encode(self, manifest):
                manifest["artifacts"].clear()
                return b"synthetic artifact, not Godot scene"
        before = copy.deepcopy(self.manifest)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "asset.bin"
            receipt = publish_new(Encoder(), self.manifest, target)
            self.assertEqual(receipt["bytes"], target.stat().st_size)
            original = target.read_bytes()
            with self.assertRaises(FileExistsError):
                publish_new(Encoder(), self.manifest, target)
            self.assertEqual(target.read_bytes(), original)
            with patch("extensions.os.link", side_effect=OSError("unsupported filesystem")):
                with self.assertRaises(OSError):
                    publish_new(Encoder(), self.manifest, Path(folder) / "failed.bin")
            self.assertEqual([p.name for p in Path(folder).iterdir()], ["asset.bin"])
        self.assertEqual(self.manifest, before)

    def test_bad_json_and_provider_definitions(self):
        for bad in ({1: "value"}, {"value": float("nan")}, ("tuple",)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                canonical(bad)
        for bad in (None, {}, {**self.provider, "available": "yes"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                provider_manifest(bad)


if __name__ == "__main__":
    unittest.main()
