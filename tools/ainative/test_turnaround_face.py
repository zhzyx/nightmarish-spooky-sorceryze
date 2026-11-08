"""Synthetic registration, projection and bounded neutral-face regression tests."""

import copy
import unittest
from types import SimpleNamespace

import anatomy_body
from turnaround_face import _close_eyes, _raster_front, _smooth_rows, eye_registration, face_relief

NUMPY_AVAILABLE = True
try:
    import numpy as np
except ImportError:
    NUMPY_AVAILABLE = False


def synthetic_view(paired=True):
    image = np.full((620, 440, 3), 0.65, np.float32)
    mask = np.zeros(image.shape[:2], bool)
    mask[35:600, 195:255] = True
    if paired:
        image[82:87, 211:216] = 0.08
        image[82:87, 234:239] = 0.08
    return dict(image=image, mask=mask, pixel_height=565, bounds=[195, 35, 255, 600], center_x=225)


def grid():
    xs = np.arange(-190, 191, dtype=np.float32) / 512
    ys = np.arange(-4, 517, dtype=np.float32) / 512
    centers = np.zeros(len(ys), np.float32)
    depth = np.full(len(ys), 24.0, np.float32)
    return xs, ys, centers, depth


@unittest.skipUnless(NUMPY_AVAILABLE, "NumPy is supplied by the Blender runtime")
class TurnaroundFaceTests(unittest.TestCase):
    def test_uniform_or_unpaired_features_skip_without_array_mutation(self):
        view = synthetic_view(False)
        arrays = grid()
        snapshots = [a.copy() for a in arrays]
        self.assertIsNone(eye_registration(view, np))
        field, report = face_relief(view, *arrays, np, anatomy_body)
        self.assertIsNone(field)
        self.assertFalse(report["applied"])
        view["image"][82:87, 211:216] = 0.08
        self.assertIsNone(eye_registration(view, np))
        for original, current in zip(snapshots, arrays):
            np.testing.assert_array_equal(original, current)

    def test_paired_front_features_have_bounded_registration(self):
        result = eye_registration(synthetic_view(), np)
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result["score"], 0.095)
        self.assertTrue(0.28 * result["head_width"] <= result["pupil_span"] <= 0.53 * result["head_width"])

    def test_back_facing_skull_quad_cannot_fill_an_eye_aperture(self):
        # First quad has +Z winding. Rear quad has -Z winding and is deeper.
        points = np.array(
            [[-2, -2, 1], [2, -2, 1], [2, 2, 1], [-2, 2, 1], [-3, -3, -5], [-3, 3, -5], [3, 3, -5], [3, -3, -5]], float
        )
        faces = np.array([[0, 1, 2, 3], [4, 5, 6, 7]])
        output = _raster_front(points, faces, points[:, 0] + 3, points[:, 1] + 3, (7, 7), np)
        self.assertEqual(output[3, 3], 1)
        self.assertFalse(np.isfinite(output[0, 0]))

    def test_closed_eye_caps_supply_finite_front_without_rear_depth(self):
        landmarks = anatomy_body.BODY_LANDMARKS
        eye = landmarks["eyeL"]
        x = np.linspace(-0.05, 0.05, 101)
        y = np.linspace(eye[1] - 0.01, eye[1] + 0.01, 41)
        output = np.full((len(y), len(x)), -np.inf)
        count = _close_eyes(output, x, y, landmarks, np)
        self.assertGreater(count, 100)
        for label in ("eyeL", "eyeR"):
            ix = int(np.argmin(abs(x - landmarks[label][0])))
            self.assertTrue(np.isfinite(output[20, ix]))
            self.assertGreater(output[20, ix], landmarks[label][2])
        self.assertFalse(np.isfinite(output[20, 50]))

    def test_profile_residual_smoothing_removes_alternating_row_stripes(self):
        signal = np.array([0.0, 1.0] * 64)
        smoothed = _smooth_rows(signal, 2.56, np)
        self.assertLess(float(np.std(smoothed[16:-16])), 0.005)
        self.assertLess(float(np.max(abs(np.diff(smoothed)))), 0.2)
        np.testing.assert_allclose(_smooth_rows(np.full(30, 8.0), 2.56, np), 8.0, atol=1e-12)

    def test_actual_cc0_data_gives_finite_localized_relief_and_immutable_inputs(self):
        view = synthetic_view()
        arrays = grid()
        snapshots = [a.copy() for a in arrays]
        image = view["image"].copy()
        field, report = face_relief(view, *arrays, np, anatomy_body)
        self.assertTrue(report["applied"])
        self.assertFalse(report["identity_recovered"])
        target, weights = field
        self.assertEqual(target.shape, (len(arrays[1]), len(arrays[0])))
        self.assertTrue(np.isfinite(target[weights > 0]).all())
        self.assertGreater(int((weights > 0).sum()), 500)
        self.assertTrue(((weights >= 0) & (weights <= 1)).all())
        self.assertTrue((target[weights > 0] <= 24).all())
        self.assertEqual(float(weights[:, :150].sum()), 0)
        self.assertEqual(float(weights[:, -150:].sum()), 0)
        self.assertEqual(float(weights[140:].sum()), 0)
        self.assertGreater(report["closed_eye_samples"], 0)
        self.assertGreaterEqual(float(target[weights > 0].min()), 24.0 * (1 - 0.55) - 1e-5)
        for before, after in zip(snapshots, arrays):
            np.testing.assert_array_equal(before, after)
        np.testing.assert_array_equal(view["image"], image)

    def test_invalid_grid_budget_nan_and_nonmonotonic_coordinates_reject(self):
        for index, mutate in (
            (0, lambda a: a.__setitem__(3, float("nan"))),
            (0, lambda a: a.__setitem__(3, a[2])),
            (0, lambda a: a.__setitem__(3, a[3] + 0.0001)),
            (3, lambda a: a.__setitem__(3, -1)),
        ):
            arrays = list(grid())
            mutate(arrays[index])
            with self.assertRaisesRegex(ValueError, "face_grid_invalid"):
                face_relief(synthetic_view(), *arrays, np, anatomy_body)
        with self.assertRaisesRegex(ValueError, "face_grid_invalid"):
            face_relief(synthetic_view(), *grid(), np, anatomy_body, grid_height=True)

    def test_thin_profile_limits_relief_without_touching_rear_surface(self):
        arrays = list(grid())
        arrays[-1][:] = 2.0
        field, report = face_relief(synthetic_view(), *arrays, np, anatomy_body)
        self.assertTrue(report["applied"])
        target, weight = field
        self.assertGreaterEqual(float(target[weight > 0].min()), 0.9 - 1e-5)
        self.assertLessEqual(float(target[weight > 0].max()), 2.0)

    def test_invalid_anatomy_topology_rejects_before_projection(self):
        invalid = SimpleNamespace(BODY_VERTICES=[(0, 0, 0)], BODY_FACES=[(0, 1, 2, 3)], BODY_LANDMARKS={})
        with self.assertRaisesRegex(ValueError, "face_anatomy_data_invalid"):
            face_relief(synthetic_view(), *grid(), np, invalid)

    def test_missing_registration_does_not_touch_unavailable_anatomy(self):
        field, report = face_relief(synthetic_view(False), *grid(), np, SimpleNamespace())
        self.assertIsNone(field)
        self.assertEqual(report["reason"], "no_supported_pair_of_eye_features")

    def test_registration_ignores_nonfinite_contrast_candidates(self):
        view = copy.deepcopy(synthetic_view())
        view["image"][:] = np.nan
        self.assertIsNone(eye_registration(view, np))


if __name__ == "__main__":
    unittest.main()
