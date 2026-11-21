"""Local humanoid AI-review adapter tests; no network or AI inference."""

import copy
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import rigging_review

VIEWS = (
    "front",
    "right",
    "back",
    "left",
    "top",
    "detail_upper_front",
    "detail_lower_front",
    "head_front",
    "head_three_quarter",
    "head_side",
)


def minimal_glb():
    document = json.dumps({"asset": {"version": "2.0"}, "buffers": [{"byteLength": 0}]}).encode()
    document += b" " * (-len(document) % 4)
    binary = struct.pack("<II", 0, 0x004E4942)
    return (
        struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(document) + len(binary))
        + struct.pack("<II", len(document), 0x4E4F534A)
        + document
        + binary
    )


def accepted_document():
    return dict(
        schema_version=2,
        passed=True,
        subject_match=True,
        proportions_pass=True,
        details_pass=True,
        views=[dict(view=view, similar=True, observation="usable") for view in VIEWS],
        head_gate=dict(
            applicable=True,
            complete_face=True,
            neck_join_pass=True,
            identity_pass=True,
            face_proportions_pass=True,
            animation_geometry_pass=True,
            observation="complete humanoid geometry; rig unverified",
        ),
        acceptance=dict(
            top_view="approximate_allowed",
            face="recognizable_identity_normal_proportions",
            animation="geometry_readiness_only_rig_unverified",
        ),
        issues=[],
        retry_guidance="",
        rendered_front_view="front",
    )


class RiggingReviewTests(unittest.TestCase):
    def run_review(self, document, recovered=None):
        original = minimal_glb()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.glb"
            source.write_bytes(original)
            entries = [dict(image_id="generated-" + view, label=view, path="unused") for view in VIEWS]
            responses = [(copy.deepcopy(document), {"provider": "fixture"})]
            responses.append((copy.deepcopy(recovered or document), {"provider": "fixture-recovery"}))
            with (
                patch.object(rigging_review, "_render", return_value=entries),
                patch.object(rigging_review, "_request_ai", side_effect=responses),
            ):
                result = rigging_review.review_local_model(dict(source=str(source), directory=str(root / "review")))
            self.assertEqual(source.read_bytes(), original)
            receipt = json.loads((root / "review/review-receipt.json").read_text())
            self.assertEqual(receipt["source_sha256"], hashlib.sha256(original).hexdigest())
            self.assertEqual(result["source_sha256"], hashlib.sha256(original).hexdigest())
            return result

    def test_accepted_ai_review_creates_source_bound_automatic_head_gate(self):
        result = self.run_review(accepted_document())
        self.assertTrue(result["passed"])
        review = result["head_review"]
        self.assertEqual(review["mode"], "automatic")
        self.assertTrue(review["ai_reviewed"])
        self.assertNotIn("manual_confirmation", review)
        self.assertEqual(review["source_sha256"], result["source_sha256"])
        self.assertEqual(review["geometry_sha256"], result["source_sha256"])
        self.assertTrue(all(review["head_views"][view] for view in rigging_review.REQUIRED_HEAD_VIEWS))
        self.assertFalse(review["rigging_verified"])
        self.assertFalse(review["animation_verified"])

    def test_non_humanoid_ai_result_has_no_head_acceptance(self):
        document = accepted_document()
        document.update(passed=False, subject_match=False, issues=["Not a complete humanoid"])
        result = self.run_review(document)
        self.assertFalse(result["passed"])
        self.assertNotIn("head_review", result)

    def test_wrong_front_view_cannot_be_accepted(self):
        document = accepted_document()
        document["rendered_front_view"] = "back"
        result = self.run_review(document)
        self.assertFalse(result["passed"])
        self.assertNotIn("head_review", result)
        self.assertTrue(any("front" in issue for issue in result["issues"]))

    def test_front_orientation_gets_one_bounded_render_recovery(self):
        initial = accepted_document()
        initial["rendered_front_view"] = "left"
        result = self.run_review(initial, accepted_document())
        self.assertTrue(result["passed"])
        recovery = result["review_document"]["orientation_recovery"]
        self.assertEqual(recovery["correction_degrees"], -90.0)
        self.assertEqual(recovery["previous_rendered_front_view"], "left")
        self.assertFalse(recovery["geometry_changed"])
        self.assertEqual(len(result["api_receipts"]), 2)

    def test_incomplete_ai_review_cannot_be_accepted(self):
        document = accepted_document()
        document["views"].pop()
        result = self.run_review(document)
        self.assertFalse(result["passed"])
        self.assertNotIn("head_review", result)
        self.assertTrue(result["review_document"]["review_incomplete"])

    def test_editor_host_dispatches_the_ai_only_review_command(self):
        from types import SimpleNamespace

        import editor_host

        request = {"source": "fixture.glb", "directory": "private-review"}
        with patch("rigging_review.review_local_model", return_value={"passed": True}) as review:
            result = editor_host.dispatch(SimpleNamespace(command="rigging-review"), request)
        self.assertEqual(result, {"passed": True})
        review.assert_called_once_with(request)


if __name__ == "__main__":
    unittest.main()
