"""Static anatomical asset invariants; no Blender, asset downloads or model calls."""

import ast
import math
import unittest
from collections import defaultdict
from pathlib import Path

SOURCE = Path(__file__).with_name("anatomy_body.py")
DATA_NAMES = {
    "BODY_SOURCE_SHA256",
    "BODY_NORMALIZATION",
    "BODY_BASE_HEAD_FRAME",
    "BODY_HEAD_FRAME",
    "BODY_SOURCE_INDICES",
    "BODY_VERTICES",
    "BODY_AGE_DELTAS",
    "BODY_FACES",
    "BODY_ARM_WEIGHTS",
    "BODY_HAND_WEIGHTS",
    "BODY_FOREARM_WEIGHTS",
    "BODY_FOREARM_CHAIN_BONES",
    "BODY_LANDMARKS",
    "BODY_LANDMARK_AGE_DELTAS",
    "BODY_DIGIT_TIPS",
    "BODY_DIGIT_TIP_AGE_DELTAS",
}
PINNED_SOURCES = {
    "base.obj": "8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c",
    "caucasian-male-young.target": "70e228ba7164737dae664454394536fc5935fa48d333c1a97d77e2dc6eacc5f5",
    "caucasian-male-old.target": "b0d2b1d58cba0358af59833740e70229265f7da1c20a11240f4123b7192cfd6d",
    "default.mhskel": "99f179bce0aa850b45d4191a1d0d234c5851f881c057439470ded3bddf729a24",
    "default_weights.mhw": "0f3641d651ae3d00ad6b4ccee43142edb109d3bd909d27d9e4139ef1beed8625",
}


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


class AnatomyBodyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Do not import a module whose data-only property is under test.
        cls.module = ast.parse(SOURCE.read_text(encoding="utf-8"))
        cls.data = {
            statement.targets[0].id: ast.literal_eval(statement.value)
            for statement in cls.module.body
            if isinstance(statement, ast.Assign) and isinstance(statement.targets[0], ast.Name)
        }
        cls.vertices = cls.data["BODY_VERTICES"]
        cls.faces = cls.data["BODY_FACES"]
        cls.edges = defaultdict(list)
        cls.neighbors = defaultdict(set)
        cls.incident_faces = defaultdict(set)
        cls.face_neighbors = defaultdict(set)
        for face_index, face in enumerate(cls.faces):
            for vertex in face:
                cls.incident_faces[vertex].add(face_index)
            for corner, start in enumerate(face):
                end = face[(corner + 1) % len(face)]
                cls.edges[tuple(sorted((start, end)))].append((face_index, start, end))
                cls.neighbors[start].add(end)
                cls.neighbors[end].add(start)
        for incidents in cls.edges.values():
            for face_index, _, _ in incidents:
                cls.face_neighbors[face_index].update(index for index, _, _ in incidents if index != face_index)

    def assert_vector(self, vector):
        self.assertEqual(len(vector), 3)
        self.assertTrue(all(type(value) in (int, float) and math.isfinite(value) for value in vector))

    def test_module_contains_only_named_literal_data(self):
        names = []
        for index, statement in enumerate(self.module.body):
            if (
                index == 0
                and isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Constant)
                and isinstance(statement.value.value, str)
            ):
                continue
            self.assertIsInstance(statement, ast.Assign)
            self.assertEqual(len(statement.targets), 1)
            self.assertIsInstance(statement.targets[0], ast.Name)
            names.append(statement.targets[0].id)
            ast.literal_eval(statement.value)
        self.assertEqual(set(names), DATA_NAMES)
        self.assertEqual(len(names), len(set(names)), "asset constants must not be reassigned")

    def test_sources_are_the_pinned_cc0_mesh_targets_and_rig_data(self):
        self.assertEqual(self.data["BODY_SOURCE_SHA256"], PINNED_SOURCES)

    def test_vertices_are_finite_three_dimensional_coordinates(self):
        self.assertTrue(self.vertices)
        for vertex in self.vertices:
            self.assert_vector(vertex)

    def test_quads_have_valid_indices_and_positive_triangle_areas(self):
        self.assertTrue(self.faces)
        for face in self.faces:
            self.assertEqual(len(face), 4)
            self.assertTrue(all(type(index) is int and 0 <= index < len(self.vertices) for index in face))
            self.assertEqual(len(set(face)), len(face))
            for indices in ((face[0], face[1], face[2]), (face[0], face[2], face[3])):
                a, b, c = (self.vertices[index] for index in indices)
                normal = cross(
                    tuple(b[axis] - a[axis] for axis in range(3)), tuple(c[axis] - a[axis] for axis in range(3))
                )
                self.assertGreater(math.hypot(*normal), 0, "degenerate triangle in quad fan")

    def test_edges_are_closed_and_consistently_oriented(self):
        for edge, incidents in self.edges.items():
            self.assertEqual(len(incidents), 2, f"boundary or nonmanifold edge {edge}")
            _, start_a, end_a = incidents[0]
            _, start_b, end_b = incidents[1]
            self.assertEqual((start_a, end_a), (end_b, start_b))

    def test_body_is_one_connected_component_without_unused_vertices(self):
        self.assertEqual(set(self.neighbors), set(range(len(self.vertices))))
        remaining = set(range(len(self.vertices)))
        self.assertTrue(remaining)
        pending = [remaining.pop()]
        while pending:
            reached = remaining.intersection(self.neighbors[pending.pop()])
            remaining.difference_update(reached)
            pending.extend(reached)
        self.assertFalse(remaining)

    def test_each_vertex_has_a_single_manifold_face_fan(self):
        for vertex in range(len(self.vertices)):
            remaining = set(self.incident_faces[vertex])
            self.assertTrue(remaining)
            pending = [remaining.pop()]
            while pending:
                reached = remaining.intersection(self.face_neighbors[pending.pop()])
                remaining.difference_update(reached)
                pending.extend(reached)
            self.assertFalse(remaining, f"pinched vertex {vertex}")

    def test_outward_body_has_finite_positive_volume(self):
        contributions = []
        for face in self.faces:
            for indices in ((face[0], face[1], face[2]), (face[0], face[2], face[3])):
                a, b, c = (self.vertices[index] for index in indices)
                normal = cross(b, c)
                contributions.append(sum(a[axis] * normal[axis] for axis in range(3)) / 6)
        volume = math.fsum(contributions)
        self.assertTrue(math.isfinite(volume) and volume > 0)

    def test_baseline_is_grounded_with_one_unit_crown_height(self):
        self.assertEqual(min(vertex[1] for vertex in self.vertices), 0)
        self.assertEqual(max(vertex[1] for vertex in self.vertices), 1)
        self.assertEqual(self.data["BODY_LANDMARKS"]["head_top"][1], 1)
        normalization = self.data["BODY_NORMALIZATION"]
        self.assertEqual(set(normalization), {"floor_y", "height", "center_x", "center_z"})
        self.assertTrue(all(type(value) in (int, float) and math.isfinite(value) for value in normalization.values()))
        self.assertGreater(normalization["height"], 0)

    def test_age_vectors_match_the_mesh_and_are_finite_nonzero(self):
        deltas = self.data["BODY_AGE_DELTAS"]
        self.assertEqual(len(deltas), len(self.vertices))
        for vector in deltas:
            self.assert_vector(vector)
        self.assertTrue(any(any(value != 0 for value in vector) for vector in deltas))

    def test_source_indices_are_unique_nonnegative_and_cover_the_mesh(self):
        indices = self.data["BODY_SOURCE_INDICES"]
        self.assertEqual(len(indices), len(self.vertices))
        self.assertEqual(len(set(indices)), len(indices))
        self.assertTrue(all(type(index) is int and index >= 0 for index in indices))

    def test_arm_forearm_and_hand_weights_are_bounded_normalized_pairs(self):
        arms = self.data["BODY_ARM_WEIGHTS"]
        forearms = self.data["BODY_FOREARM_WEIGHTS"]
        hands = self.data["BODY_HAND_WEIGHTS"]
        for weights in (arms, forearms, hands):
            self.assertEqual(len(weights), len(self.vertices))
            for pair in weights:
                self.assertEqual(len(pair), 2)
                self.assertTrue(
                    all(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1 for value in pair)
                )
                self.assertLessEqual(sum(pair), 1 + 1e-10)
            self.assertTrue(all(any(pair[side] > 0 for pair in weights) for side in (0, 1)))
        for arm, forearm, hand in zip(arms, forearms, hands):
            self.assertTrue(
                all(hand[side] <= forearm[side] + 1e-10 and forearm[side] <= arm[side] + 1e-10 for side in (0, 1)),
                "hand must be within forearm, which must be within its arm chain",
            )

    def test_forearm_bone_chains_are_unique_and_keep_their_side_and_endpoints(self):
        chains = self.data["BODY_FOREARM_CHAIN_BONES"]
        self.assertEqual(set(chains), {"L", "R"})
        for side, names in chains.items():
            self.assertEqual(len(names), len(set(names)))
            self.assertTrue(all(isinstance(name, str) and name.endswith("." + side) for name in names))
            self.assertTrue({"lowerarm01." + side, "wrist." + side}.issubset(names))
        self.assertFalse(set(chains["L"]).intersection(chains["R"]))

    def test_landmarks_and_age_deltas_are_finite_with_matching_keys(self):
        points, deltas = self.data["BODY_LANDMARKS"], self.data["BODY_LANDMARK_AGE_DELTAS"]
        self.assertEqual(set(points), set(deltas))
        self.assertTrue(
            {
                "head_top",
                "chin",
                "eyeL",
                "eyeR",
                "shoulderL",
                "shoulderR",
                "elbowL",
                "elbowR",
                "wristL",
                "wristR",
            }.issubset(points)
        )
        for values in (points, deltas):
            for name, vector in values.items():
                self.assertIsInstance(name, str)
                self.assert_vector(vector)
        for name in ("BODY_BASE_HEAD_FRAME", "BODY_HEAD_FRAME"):
            frame = self.data[name]
            self.assert_vector(frame["origin"])
            self.assertTrue(
                type(frame["height"]) in (int, float) and math.isfinite(frame["height"]) and frame["height"] > 0
            )

    def test_both_hands_have_five_finite_digit_anchors_and_deltas(self):
        points, deltas = self.data["BODY_DIGIT_TIPS"], self.data["BODY_DIGIT_TIP_AGE_DELTAS"]
        self.assertEqual(set(points), {"L", "R"})
        self.assertEqual(set(deltas), set(points))
        for side in points:
            for vectors in (points[side], deltas[side]):
                self.assertEqual(len(vectors), 5)
                for vector in vectors:
                    self.assert_vector(vector)


if __name__ == "__main__":
    unittest.main()
