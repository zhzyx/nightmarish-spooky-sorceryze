"""Static invariants for fixed CC0 anatomical data; no Blender or model calls."""

import ast
import math
import unittest
from collections import defaultdict
from pathlib import Path

SOURCE = Path(__file__).with_name("anatomy_base.py")
DATA_NAMES = {"SOURCE_SHA256", "EYE_CENTERS", "HEAD_VERTICES", "HEAD_FACES", "AGE_SOURCE_SHA256", "AGE_DELTAS"}
PINNED_OBJ_SHA256 = "8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c"
PINNED_AGE_TARGET_SHA256 = (
    "70e228ba7164737dae664454394536fc5935fa48d333c1a97d77e2dc6eacc5f5",
    "b0d2b1d58cba0358af59833740e70229265f7da1c20a11240f4123b7192cfd6d",
)


class AnatomyBaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Parse data without importing a module whose data-only property is under test.
        cls.module = ast.parse(SOURCE.read_text(encoding="utf-8"))
        cls.data = {}
        for statement in cls.module.body:
            if isinstance(statement, ast.Assign):
                for target in statement.targets:
                    if isinstance(target, ast.Name):
                        cls.data[target.id] = ast.literal_eval(statement.value)
        cls.vertices = cls.data["HEAD_VERTICES"]
        cls.faces = cls.data["HEAD_FACES"]
        cls.edges = defaultdict(list)
        cls.neighbors = defaultdict(set)
        cls.incident_faces = defaultdict(set)
        cls.face_neighbors = defaultdict(set)
        for face_index, face in enumerate(cls.faces):
            for vertex in face:
                cls.incident_faces[vertex].add(face_index)
            for corner in range(len(face)):
                start, end = face[corner], face[(corner + 1) % len(face)]
                cls.edges[tuple(sorted((start, end)))].append((face_index, start, end))
                cls.neighbors[start].add(end)
                cls.neighbors[end].add(start)
        for incident in cls.edges.values():
            for face_index, _, _ in incident:
                cls.face_neighbors[face_index].update(index for index, _, _ in incident if index != face_index)

    def test_module_contains_only_named_literal_data(self):
        assignments = []
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
            assignments.append(statement.targets[0].id)
            # literal_eval rejects calls, imports, comprehensions and executable expressions.
            ast.literal_eval(statement.value)
        self.assertEqual(set(assignments), DATA_NAMES)
        self.assertEqual(len(assignments), len(set(assignments)), "data constants must not be reassigned")

    def test_declared_source_is_the_pinned_cc0_obj(self):
        self.assertEqual(self.data["SOURCE_SHA256"], PINNED_OBJ_SHA256)

    def test_age_sources_are_pinned_in_young_then_old_order(self):
        self.assertEqual(self.data["AGE_SOURCE_SHA256"], PINNED_AGE_TARGET_SHA256)

    def test_age_deltas_are_finite_bounded_and_cover_the_derived_vertices(self):
        deltas = self.data["AGE_DELTAS"]
        self.assertEqual(len(deltas), len(self.vertices), "age data must use derived mesh indices")
        has_shape_change = False
        for delta in deltas:
            self.assertEqual(len(delta), 3)
            self.assertTrue(all(type(value) in (int, float) and math.isfinite(value) for value in delta))
            # Coordinates are normalized to one head height; the age basis must
            # remain a local shape change, rather than replace or translate a head.
            self.assertLess(math.hypot(*delta), 0.25, "age displacement exceeds one quarter of head height")
            has_shape_change |= any(value != 0 for value in delta)
        self.assertTrue(has_shape_change, "age basis must not silently become a no-op")

    def test_vertices_are_finite_three_dimensional_coordinates(self):
        self.assertTrue(self.vertices)
        for vertex in self.vertices:
            self.assertEqual(len(vertex), 3)
            self.assertTrue(all(type(value) in (int, float) and math.isfinite(value) for value in vertex))

    def test_triangle_indices_and_areas_are_valid(self):
        self.assertTrue(self.faces)
        for face in self.faces:
            self.assertEqual(len(face), 3)
            self.assertTrue(all(type(index) is int and 0 <= index < len(self.vertices) for index in face))
            self.assertEqual(len(set(face)), 3)
            a, b, c = (self.vertices[index] for index in face)
            u = tuple(b[axis] - a[axis] for axis in range(3))
            v = tuple(c[axis] - a[axis] for axis in range(3))
            normal = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
            self.assertTrue(any(value != 0 for value in normal), "zero-area triangle")

    def test_edges_are_closed_with_consistent_orientation(self):
        self.assertTrue(self.edges)
        for edge, incidents in self.edges.items():
            self.assertEqual(len(incidents), 2, f"boundary or nonmanifold edge: {edge}")
            _, start_a, end_a = incidents[0]
            _, start_b, end_b = incidents[1]
            self.assertEqual((start_a, end_a), (end_b, start_b), "adjacent triangles must use opposite edge winding")

    def test_all_vertices_form_one_connected_component(self):
        self.assertEqual(set(self.neighbors), set(range(len(self.vertices))), "unused or missing vertices")
        remaining = set(range(len(self.vertices)))
        self.assertTrue(remaining)
        pending = [remaining.pop()]
        while pending:
            for neighbor in self.neighbors[pending.pop()]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    pending.append(neighbor)
        self.assertFalse(remaining, "the head asset must be one connected component")

    def test_each_vertex_has_one_connected_face_fan(self):
        # Two closed shells touching at only one vertex pass edge checks but form a pinched vertex.
        for vertex in range(len(self.vertices)):
            remaining = set(self.incident_faces[vertex])
            self.assertTrue(remaining, "isolated vertex")
            pending = [remaining.pop()]
            while pending:
                neighbors = remaining.intersection(self.face_neighbors[pending.pop()])
                remaining.difference_update(neighbors)
                pending.extend(neighbors)
            self.assertFalse(remaining, f"disconnected face fans at vertex {vertex}")

    def test_oriented_head_has_positive_volume(self):
        contributions = []
        for face in self.faces:
            a, b, c = (self.vertices[index] for index in face)
            cross = (b[1] * c[2] - b[2] * c[1], b[2] * c[0] - b[0] * c[2], b[0] * c[1] - b[1] * c[0])
            contributions.append(sum(a[axis] * cross[axis] for axis in range(3)) / 6)
        volume = math.fsum(contributions)
        self.assertTrue(math.isfinite(volume) and volume > 0, "winding must enclose positive volume")

    def test_eye_anchors_are_finite_distinct_and_within_head_bounds(self):
        eyes = self.data["EYE_CENTERS"]
        self.assertTrue(eyes)
        self.assertEqual(len(set(eyes)), len(eyes))
        bounds = [
            (min(vertex[axis] for vertex in self.vertices), max(vertex[axis] for vertex in self.vertices))
            for axis in range(3)
        ]
        for eye in eyes:
            self.assertEqual(len(eye), 3)
            for axis, coordinate in enumerate(eye):
                self.assertTrue(type(coordinate) in (int, float) and math.isfinite(coordinate))
                self.assertTrue(bounds[axis][0] <= coordinate <= bounds[axis][1], "eye anchor outside head bounds")


if __name__ == "__main__":
    unittest.main()
