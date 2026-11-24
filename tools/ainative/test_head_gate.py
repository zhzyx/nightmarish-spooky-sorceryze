"""Head-gate metadata contract tests; no inference or asset mutation."""
import base64
import copy
import hashlib
import json
import struct
import unittest

from mesh_vision import attach_capability_review, attach_head_review


def minimal_glb():
    document = json.dumps({"asset": {"version": "2.0"}, "buffers": [{"byteLength": 0}]}).encode()
    document += b" " * (-len(document) % 4)
    binary = struct.pack("<II", 0, 0x004E4942)
    return struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(document) + len(binary)) + struct.pack(
        "<II", len(document), 0x4E4F534A
    ) + document + binary


def humanoid_analysis():
    return {"subject": {"category": "humanoid", "description": "person", "structure": "head and neck"}}


def accepted_review():
    return dict(
        schema_version=2,
        passed=True,
        acceptance=dict(
            top_view="approximate_allowed",
            face="recognizable_identity_normal_proportions",
            animation="geometry_readiness_only_rig_unverified",
        ),
        head_gate=dict(
            applicable=True,
            complete_face=True,
            neck_join_pass=True,
            identity_pass=True,
            face_proportions_pass=True,
            animation_geometry_pass=True,
            observation="recognizable face; normal proportions; geometry ready, rig unverified",
        ),
        views=[dict(view=view, similar=True, observation="complete") for view in ("head_front", "head_three_quarter", "head_side")],
    )


class HeadReviewEmbeddingTests(unittest.TestCase):
    def test_review_is_embedded_without_changing_original_model(self):
        data = minimal_glb()
        revision = hashlib.sha256(data).hexdigest()
        model = dict(
            revision=revision,
            payload=dict(
                content_base64=base64.b64encode(data).decode(),
                content_sha256=revision,
                bytes=len(data),
                provenance=dict(task_id="source-task"),
            ),
        )
        original = copy.deepcopy(model)
        result = attach_head_review(model, accepted_review(), humanoid_analysis())
        self.assertEqual(model, original)
        self.assertNotEqual(result["revision"], revision)
        output = base64.b64decode(result["payload"]["content_base64"], validate=True)
        self.assertEqual(hashlib.sha256(output).hexdigest(), result["revision"])
        size = struct.unpack_from("<I", output, 12)[0]
        extras = json.loads(output[20 : 20 + size])["asset"]["extras"]
        embedded = extras["maliang_head_review"]
        self.assertEqual(embedded["geometry_sha256"], revision)
        self.assertEqual(embedded["head_geometry_mode"], "integrated")
        self.assertTrue(all(embedded["head_views"].values()))
        self.assertEqual(embedded["acceptance"]["top_view"], "approximate_allowed")
        self.assertTrue(embedded["head_gate"]["identity_pass"])
        self.assertTrue(embedded["head_gate"]["face_proportions_pass"])
        self.assertTrue(embedded["animation_geometry_ready"])
        self.assertFalse(embedded["rigging_verified"])
        self.assertFalse(embedded["animation_verified"])
        self.assertEqual(result["payload"]["provenance"]["geometry_sha256"], revision)
        recovered_review = accepted_review()
        recovered_review["orientation_recovery"] = dict(
            model_sha256=revision,
            previous_yaw_degrees=0.0,
            correction_degrees=-90.0,
            yaw_degrees=-90.0,
            geometry_changed=False,
        )
        recovered = attach_head_review(model, recovered_review, humanoid_analysis())
        output = base64.b64decode(recovered["payload"]["content_base64"], validate=True)
        size = struct.unpack_from("<I", output, 12)[0]
        frame = json.loads(output[20 : 20 + size])["asset"]["extras"]["maliang_review_frame"]
        self.assertEqual(frame["yaw_degrees"], -90.0)
        self.assertEqual(frame["source_sha256"], revision)
        self.assertTrue(frame["confirmed"])

    def test_capability_delivery_embeds_unresolved_review_without_head_acceptance(self):
        data = minimal_glb()
        revision = hashlib.sha256(data).hexdigest()
        model = dict(
            revision=revision,
            payload=dict(
                content_base64=base64.b64encode(data).decode(),
                content_sha256=revision,
                bytes=len(data),
                provenance=dict(task_id="source-task"),
            ),
        )
        rejected = accepted_review()
        rejected["passed"] = False
        rejected["issues"] = ["Body proportions require unsupported geometry editing"]
        result = attach_capability_review(model, rejected)
        output = base64.b64decode(result["payload"]["content_base64"], validate=True)
        size = struct.unpack_from("<I", output, 12)[0]
        extras = json.loads(output[20 : 20 + size])["asset"]["extras"]
        embedded = extras["maliang_capability_review"]
        self.assertTrue(embedded["capability_limited"])
        self.assertFalse(embedded["visual_review_passed"])
        self.assertEqual(embedded["geometry_sha256"], revision)
        self.assertEqual(embedded["unresolved_issues"], rejected["issues"])
        self.assertNotIn("maliang_head_review", extras)
        self.assertTrue(result["payload"]["provenance"]["capability_limited"])

    def test_non_humanoid_is_not_given_a_human_contract(self):
        model = dict(revision="a" * 64, payload={})
        analysis = humanoid_analysis()
        analysis["subject"]["category"] = "vase"
        self.assertIs(attach_head_review(model, accepted_review(), analysis), model)


if __name__ == "__main__":
    unittest.main()
