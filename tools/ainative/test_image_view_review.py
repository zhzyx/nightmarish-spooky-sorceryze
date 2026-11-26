import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import image_view_review
from extensions import canonical


class ImageViewReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.config = dict(endpoint="https://example.invalid/v1", model="kimi-k2.5", key_env="KIMI_API_KEY")
        self.entries = [
            dict(label="正面", data=b"front-pixels", extension=".png"),
            dict(label="背面", data=b"back-pixels", extension=".png"),
        ]

    def tearDown(self):
        self.temporary.cleanup()

    def prepare(self):
        directory = self.root / "review"
        raw = image_view_review.prepare_request(self.config, "只要衣服，正面和背面", self.entries, directory)
        return directory, raw

    def document(self, passed=True, observed=("front", "back")):
        issues = [] if passed else ["requested view does not match pixels"]
        return dict(
            passed=passed,
            same_garment=True,
            views=[
                dict(
                    label=label,
                    observed_view=observed[index],
                    matches_label=passed,
                    garment_only=True,
                    cuff_exterior_pass=passed,
                    closed_back_pass=passed,
                    flat_rear_belt_pass=passed,
                    horizontal_rear_layout_pass=passed,
                    evidence="visible garment orientation and construction",
                    issues=issues,
                )
                for index, label in enumerate(("正面", "背面"))
            ],
            summary="view review complete",
            issues=issues,
        )

    def write_receipt(self, directory, raw, document):
        (directory / "api-receipt.json").write_text(
            canonical(
                dict(
                    request_sha256=hashlib.sha256(raw).hexdigest(),
                    instructions_sha256=hashlib.sha256(canonical(document).encode("utf-8")).hexdigest(),
                )
            ),
            encoding="utf-8",
        )

    def test_request_contains_both_images_and_strict_view_definitions(self):
        directory, raw = self.prepare()
        body = json.loads(raw)
        self.assertEqual(body["model"], "kimi-k2.5")
        self.assertEqual(body["response_format"]["json_schema"]["strict"], True)
        self.assertEqual(sum(item["type"] == "image_url" for item in body["messages"][0]["content"]), 2)
        prompt = (directory / "prompt.txt").read_text(encoding="utf-8")
        self.assertIn("A three-quarter or oblique side view is not front", prompt)
        self.assertIn("Similarity to the front is not evidence of a back view", prompt)
        self.assertIn("same garment design", prompt)
        self.assertIn("cuff_exterior_pass", prompt)
        self.assertIn("closed_back_pass", prompt)
        self.assertIn("flat_rear_belt_pass", prompt)
        self.assertIn("horizontal_rear_layout_pass", prompt)
        self.assertIn("continuous closed pullover-style back", prompt)
        self.assertIn("horizontal elements such as a shoulder yoke", prompt)
        self.assertIn("matches_label=false", prompt)
        self.assertIn("reject rather than guess", prompt)
        saved_config = json.loads((directory / "planner-config.json").read_text(encoding="utf-8"))
        self.assertEqual(saved_config, self.config)
        self.assertNotIn("api_key", saved_config)

    def test_valid_front_and_back_response_passes(self):
        directory, raw = self.prepare()
        document = self.document()
        self.write_receipt(directory, raw, document)
        self.assertIs(image_view_review.validate_response(document, self.entries, raw, directory), document)

    def test_side_mislabeled_front_is_a_valid_rejection(self):
        directory, raw = self.prepare()
        document = self.document(passed=False, observed=("three_quarter_front", "front"))
        self.write_receipt(directory, raw, document)
        reviewed = image_view_review.validate_response(document, self.entries, raw, directory)
        self.assertFalse(reviewed["passed"])
        self.assertEqual(reviewed["views"][0]["observed_view"], "three_quarter_front")
        self.assertEqual(reviewed["views"][1]["observed_view"], "front")

    def test_back_cuff_and_belt_defects_are_a_valid_rejection(self):
        directory, raw = self.prepare()
        document = self.document(passed=False, observed=("front", "back"))
        defects = ["cuff interiors and a large front-style belt buckle are visible on the back"]
        document["issues"] = defects
        document["views"][1]["issues"] = defects
        self.write_receipt(directory, raw, document)
        reviewed = image_view_review.validate_response(document, self.entries, raw, directory)
        self.assertFalse(reviewed["passed"])
        self.assertEqual(reviewed["views"][1]["issues"], defects)

    def test_horizontal_layout_is_an_independent_hard_gate(self):
        directory, raw = self.prepare()
        document = self.document()
        document["views"][1]["horizontal_rear_layout_pass"] = False
        self.write_receipt(directory, raw, document)
        with self.assertRaisesRegex(ValueError, "image_view_review_invalid"):
            image_view_review.validate_response(document, self.entries, raw, directory)

        document["passed"] = False
        document["issues"] = ["vertical front-like composition dominates the back"]
        document["views"][1]["matches_label"] = False
        document["views"][1]["issues"] = document["issues"]
        self.write_receipt(directory, raw, document)
        reviewed = image_view_review.validate_response(document, self.entries, raw, directory)
        self.assertFalse(reviewed["passed"])
        self.assertFalse(reviewed["views"][1]["horizontal_rear_layout_pass"])

    def test_inconsistent_pass_or_request_binding_is_rejected(self):
        directory, raw = self.prepare()
        document = self.document()
        document["views"][0]["matches_label"] = False
        document["views"][0]["issues"] = ["oblique view"]
        self.write_receipt(directory, raw, document)
        with self.assertRaisesRegex(ValueError, "image_view_review_invalid"):
            image_view_review.validate_response(document, self.entries, raw, directory)

        document = self.document()
        self.write_receipt(directory, raw, document)
        with self.assertRaisesRegex(ValueError, "image_view_review_invalid"):
            image_view_review.validate_response(document, self.entries, b"different request", directory)


if __name__ == "__main__":
    unittest.main()
