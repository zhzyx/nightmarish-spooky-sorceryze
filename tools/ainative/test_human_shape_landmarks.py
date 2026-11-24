"""Automatic landmark fitting tests with synthetic AI receipts; no inference."""

import base64
import copy
import hashlib
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import human_shape_landmarks
import numpy as np
from geometry_repair import HUMAN_LANDMARK_NAMES, accessor_values, load_glb
from kimi_provider import KimiNativeDirectProvider
from test_human_shape import LANDMARKS, humanoid_fixture


class HumanShapeLandmarkTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source.glb"
        humanoid_fixture(self.source)
        self.original = self.source.read_bytes()
        document, binary = load_glb(self.source)
        primitive = document["meshes"][0]["primitives"][0]
        points = np.asarray(
            accessor_values(document, binary, primitive["attributes"]["POSITION"], "VEC3"), dtype=np.float64
        )
        lower = points.min(axis=0)
        upper = points.max(axis=0)
        height = float(upper[1] - lower[1])
        center = np.asarray([(lower[0] + upper[0]) / 2.0, lower[1], (lower[2] + upper[2]) / 2.0])
        self.normalized = {
            name: ((np.asarray(LANDMARKS[name]) - center) / height).tolist() for name in HUMAN_LANDMARK_NAMES
        }
        self.document = dict(
            schema_version=1,
            reference_pose="T",
            rendered_front_view="front",
            confidence="high",
            landmarks=copy.deepcopy(self.normalized),
            observations="synthetic source-bound estimate",
        )
        self.entries = [dict(image_id="front", label="front", path="unused")]
        self.fit_count = 0

    def tearDown(self):
        self.temporary.cleanup()

    def fit(self, document=None):
        self.fit_count += 1
        directory = self.root / ("automatic-" + str(self.fit_count))
        with (
            patch.object(human_shape_landmarks.rigging_review, "_render", return_value=self.entries),
            patch.object(
                human_shape_landmarks,
                "_request_ai",
                return_value=(copy.deepcopy(document or self.document), {"provider": "synthetic"}),
            ),
        ):
            return human_shape_landmarks.fit_landmarks(
                self.source, directory, "godot", "render.gd", {"endpoint": "unused"}
            )

    def test_ai_estimate_is_source_bound_and_checked_against_geometry(self):
        result = self.fit()
        sha = hashlib.sha256(self.original).hexdigest()
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual(result["source_sha256"], sha)
        self.assertEqual(result["landmarks"]["source_sha256"], sha)
        self.assertEqual(result["quality"], "ai_estimated_geometry_checked")
        self.assertTrue(result["requires_visual_review"])
        self.assertFalse(result["manual_confirmation"])
        self.assertLess(result["geometry_checks"]["maximum_landmark_distance_over_height"], 0.02)
        for name in HUMAN_LANDMARK_NAMES:
            for component in range(3):
                self.assertAlmostEqual(result["landmarks"][name][component], LANDMARKS[name][component], places=6)
        self.assertTrue((self.root / "automatic-1/landmarks-receipt.json").is_file())

    def test_low_confidence_and_wrong_front_stop_before_deformation(self):
        low = copy.deepcopy(self.document)
        low["confidence"] = "low"
        with self.assertRaisesRegex(ValueError, "human_shape_auto_fit_low_confidence"):
            self.fit(low)
        wrong = copy.deepcopy(self.document)
        wrong["rendered_front_view"] = "back"
        with self.assertRaisesRegex(ValueError, "human_shape_auto_fit_front_required"):
            self.fit(wrong)

    def test_left_front_recovers_once_and_restores_source_coordinates(self):
        initial = copy.deepcopy(self.document)
        initial["rendered_front_view"] = "left"
        initial["confidence"] = "low"
        final = copy.deepcopy(self.document)
        document, binary = load_glb(self.source)
        primitive = document["meshes"][0]["primitives"][0]
        points = np.asarray(accessor_values(document, binary, primitive["attributes"]["POSITION"]), dtype=np.float64)
        lower = points.min(axis=0)
        upper = points.max(axis=0)
        height = float(upper[1] - lower[1])
        theta = math.radians(-90.0)
        rotation = np.asarray([
            [math.cos(theta), 0.0, math.sin(theta)],
            [0.0, 1.0, 0.0],
            [-math.sin(theta), 0.0, math.cos(theta)],
        ])
        rotated = points @ rotation.T
        rotated_lower = rotated.min(axis=0)
        rotated_upper = rotated.max(axis=0)
        stage_center = np.asarray([
            (rotated_lower[0] + rotated_upper[0]) / 2.0,
            lower[1],
            (rotated_lower[2] + rotated_upper[2]) / 2.0,
        ])
        final["landmarks"] = {
            name: ((rotation @ np.asarray(LANDMARKS[name]) - stage_center) / height).tolist()
            for name in HUMAN_LANDMARK_NAMES
        }
        with (
            patch.object(human_shape_landmarks.rigging_review, "_render", return_value=self.entries) as rendered,
            patch.object(
                human_shape_landmarks,
                "_request_ai",
                side_effect=[(initial, {"provider": "initial"}), (final, {"provider": "recovered"})],
            ) as requested,
        ):
            result = human_shape_landmarks.fit_landmarks(
                self.source, self.root / "recovery", "godot", "render.gd", {"endpoint": "unused"}
            )
        self.assertEqual(rendered.call_count, 2)
        self.assertEqual(requested.call_count, 2)
        self.assertEqual(result["orientation_recovery"]["correction_degrees"], -90.0)
        self.assertFalse(result["orientation_recovery"]["geometry_changed"])
        self.assertEqual(len(result["api_receipts"]), 2)
        for name in HUMAN_LANDMARK_NAMES:
            for component in range(3):
                self.assertAlmostEqual(result["landmarks"][name][component], LANDMARKS[name][component], places=6)

    def test_faraway_landmarks_fail_local_geometry_check(self):
        document = copy.deepcopy(self.document)
        # Preserve schema/anatomical ordering while moving both wrists far from mesh.
        for side in ("l", "r"):
            document["landmarks"]["wrist_" + side][1] = 0.02
        with self.assertRaisesRegex(ValueError, "human_shape_auto_fit_geometry_mismatch"):
            self.fit(document)

    def test_default_five_parameter_node_runs_through_automatic_landmarks(self):
        sha = hashlib.sha256(self.original).hexdigest()
        artifact = dict(
            id="source",
            revision=sha,
            type="mesh",
            payload=dict(
                content_base64=base64.b64encode(self.original).decode(),
                content_sha256=sha,
                extension=".glb",
            ),
        )
        request = dict(
            node="human_shape_adjust",
            version="1",
            inputs={"source": {"id": "source", "revision": sha}},
            parameters=dict(height_cm=190, head_ratio=9.0, arm_length_scale=1.2, leg_length_scale=1.1, build=0.4),
            context=[],
        )
        manifest = dict(schema_version=1, artifacts=[artifact])
        plan = KimiNativeDirectProvider._adjust_plan(None, request, manifest)
        self.assertIsNone(plan["repair"]["landmarks"])
        legacy = dict(
            request, parameters=dict(request["parameters"], reference_pose="T", landmarks={"source_sha256": ""})
        )
        legacy_plan = KimiNativeDirectProvider._adjust_plan(None, legacy, manifest)
        self.assertIsNone(legacy_plan["repair"]["landmarks"])
        automatic = dict(
            source_sha256=sha,
            reference_pose="T",
            landmarks=dict(source_sha256=sha, **LANDMARKS),
            quality="ai_estimated_geometry_checked",
            requires_visual_review=True,
        )

        class Host:
            config = dict(review_godot_path="godot", review_script_path="review.gd", planner={"endpoint": "unused"})

            def _active(self, _key, _stage):
                return True

            def write(self, _key, **values):
                self.receipt = values["model3d_receipt"]
                return {}

        host = Host()
        directory = self.root / "provider-auto"
        directory.mkdir()
        with patch.object(human_shape_landmarks, "fit_landmarks", return_value=automatic) as fitted:
            result = KimiNativeDirectProvider._repair_geometry(host, "a" * 64, plan, directory)
        fitted.assert_called_once()
        self.assertTrue((directory / "generated.glb").is_file())
        provenance = result["payload"]["provenance"]
        self.assertEqual(provenance["landmark_estimation"], "ainative_ai_geometry_checked")
        self.assertEqual(provenance["automatic_landmarks"]["source_sha256"], sha)
        self.assertAlmostEqual(provenance["geometry_repair"]["measured"]["head_ratio"], 9.0, places=5)
        self.assertEqual(
            host.receipt["geometry_repair"]["automatic_landmarks"]["quality"], "ai_estimated_geometry_checked"
        )

    def test_schema_declares_every_landmark_without_manual_confirmation(self):
        schema = human_shape_landmarks.landmark_schema()
        landmarks = schema["properties"]["landmarks"]
        self.assertEqual(set(landmarks["required"]), set(HUMAN_LANDMARK_NAMES))
        self.assertNotIn("confirmed", schema["properties"])
        self.assertNotIn("confirmed", landmarks["properties"])


if __name__ == "__main__":
    unittest.main()
