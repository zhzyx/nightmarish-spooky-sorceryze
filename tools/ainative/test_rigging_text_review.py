"""Post-rigging text-review tests; no network or AI inference."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import rigging_text_review


def accepted_document():
    return dict(
        schema_version=1,
        passed=True,
        summary="实测骨骼、蒙皮和 ROM 证据通过。",
        issues=[],
        repair=dict(command="none", parameters={}),
    )


def validation(passed=True):
    return dict(
        passed=passed,
        scene_valid=True,
        issues=[] if passed else ["抬臂时肩带内侧胸口出现明显外鼓。"],
        unsupported=[],
        movement_m={"raise_arms": 0.8, "squat": 0.4, "turn": 0.3},
        raise_chest_outward_m=0.01 if passed else 0.06,
    )


class RiggingTextReviewTests(unittest.TestCase):
    def request(self, root, report=None):
        source = root / "source.glb"
        candidate = root / "candidate.tscn"
        source.write_bytes(b"synthetic source")
        candidate.write_text("[gd_scene format=3]\n", encoding="utf-8")
        return dict(
            source=str(source),
            candidate=str(candidate),
            directory=str(root / "review"),
            validation=copy.deepcopy(report or validation()),
            attempts=[dict(attempt=1, repair="原始模板拟合")],
            retry_count=1,
            max_retries=3,
        )

    def run_review(self, document, report=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request = self.request(root, report)
            with patch.object(
                rigging_text_review, "_request_ai", return_value=(copy.deepcopy(document), {"provider": "fixture"})
            ) as call:
                result = rigging_text_review.review_candidate(request)
            evidence = call.call_args.args[0]
            self.assertEqual(evidence["evidence_kind"], "godot_measured_text_only")
            self.assertEqual(result["source_sha256"], hashlib.sha256((root / "source.glb").read_bytes()).hexdigest())
            self.assertEqual(
                result["candidate_sha256"], hashlib.sha256((root / "candidate.tscn").read_bytes()).hexdigest()
            )
            self.assertTrue((root / "review/review-receipt.json").is_file())
            return result

    def test_text_acceptance_binds_candidate_and_measured_evidence(self):
        result = self.run_review(accepted_document())
        self.assertTrue(result["passed"])
        self.assertTrue(result["local_passed"])
        self.assertTrue(result["text_only"])
        self.assertFalse(result["synthetic"])
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["repair"]["command"], "none")

    def test_local_gate_cannot_be_overridden_by_ai_pass(self):
        result = self.run_review(accepted_document(), validation(False))
        self.assertFalse(result["passed"])
        self.assertFalse(result["local_passed"])
        self.assertIn("本地硬门禁", result["summary"])
        self.assertTrue(any(issue["code"] == "local_gate_failed" for issue in result["issues"]))
        feedback = result["feedback"][0]
        self.assertEqual(feedback["node"], "humanoid_rig")
        self.assertEqual(feedback["tab"], "rigging")
        self.assertFalse(feedback["requires_source_ai_review"])

    def test_rejected_text_review_returns_structured_bounded_feedback(self):
        document = accepted_document()
        document.update(
            passed=False,
            summary="胸口外扩超过阈值。",
            issues=[
                dict(
                    code="chest_outward",
                    stage="rom",
                    check="raise_chest_outward_m",
                    message="胸口外扩超过身高 2.5%。",
                    actual=0.06,
                    threshold=0.045,
                    target="skin_weights",
                )
            ],
            repair=dict(command="refit_sagittal_leg_corrections", parameters={}),
        )
        result = self.run_review(document, validation(False))
        self.assertFalse(result["passed"])
        chest = next(item for item in result["feedback"] if item["code"] == "chest_outward")
        self.assertEqual(chest["control"], "skin_weights")
        self.assertEqual(chest["actual"], 0.06)
        self.assertEqual(chest["threshold"], 0.045)
        self.assertEqual(chest["recommended_command"], "refit_sagittal_leg_corrections")

    def test_invalid_or_unbounded_model_output_is_rejected(self):
        document = accepted_document()
        document["repair"] = dict(command="delete_checks", parameters={})
        with self.assertRaisesRegex(ValueError, "text_review_output_invalid"):
            self.run_review(document)
        document = accepted_document()
        document["passed"] = False
        with self.assertRaisesRegex(ValueError, "text_review_output_invalid"):
            self.run_review(document)

    def test_api_request_contains_only_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = dict(validation=validation(), source_sha256="a" * 64)

            def perform(_config, directory):
                raw = (directory / "api-request.json").read_bytes()
                document = accepted_document()
                (directory / "api-plan.json").write_text(json.dumps(document), encoding="utf-8")
                (directory / "api-receipt.json").write_text(
                    json.dumps(
                        dict(
                            request_sha256=hashlib.sha256(raw).hexdigest(),
                            instructions_sha256=hashlib.sha256(
                                rigging_text_review.canonical(document).encode()
                            ).hexdigest(),
                        )
                    ),
                    encoding="utf-8",
                )

            with patch.object(rigging_text_review.api_planner, "perform", side_effect=perform):
                rigging_text_review._request_ai(evidence, root / "request")
            body = json.loads((root / "request/api-request.json").read_text(encoding="utf-8"))
            content = body["messages"][0]["content"]
            self.assertIsInstance(content, str)
            self.assertIn("待审核 JSON 证据", content)
            self.assertNotIn("image_url", json.dumps(body))
            self.assertNotIn("base64", json.dumps(body))

    def test_configured_retry_limit_up_to_twelve_is_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request = self.request(root)
            request.update(
                attempts=[dict(attempt=index + 1, repair="肩胸权重边界迭代") for index in range(4)],
                retry_count=4,
                max_retries=12,
            )
            with patch.object(
                rigging_text_review, "_request_ai", return_value=(accepted_document(), {"provider": "fixture"})
            ) as call:
                result = rigging_text_review.review_candidate(request)
            self.assertEqual(result["retry_count"], 4)
            self.assertEqual(result["max_retries"], 12)
            self.assertEqual(call.call_args.args[0]["max_retries"], 12)

    def test_editor_host_dispatches_text_review_command(self):
        import editor_host

        request = {"source": "fixture.glb", "candidate": "candidate.tscn"}
        with patch("rigging_text_review.review_candidate", return_value={"passed": True, "text_only": True}) as review:
            result = editor_host.dispatch(SimpleNamespace(command="rigging-text-review"), request)
        self.assertEqual(result, {"passed": True, "text_only": True})
        review.assert_called_once_with(request)


if __name__ == "__main__":
    unittest.main()
