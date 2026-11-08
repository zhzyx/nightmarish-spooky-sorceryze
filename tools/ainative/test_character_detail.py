import copy
import math
import unittest
from collections import defaultdict

from character_detail import (
    DETAIL_LIMITS,
    accessories,
    detail_schema,
    eyebrow_accessories,
    fabric_outward_offset,
    face_detail_offset,
    hair_detail_mask,
    hair_detail_offset,
    resolve_detail,
    trouser_waist,
)


def character(**changes):
    result = {
        "height": 1.8,
        "head_ratio": 7.5,
        "style": "realistic",
        "hair": "short",
        "clothing": "coverall",
        "detail": {},
    }
    result.update(changes)
    return result


def plane_fixture():
    # Deliberately tilted: fitting must use the actual surface, not a constant Z.
    vertices = [[x, y, 0.10 + 0.04 * x + 0.02 * y] for y in (0.0, 2.0) for x in (-0.5, 0.5)]
    faces = [[0, 1, 3, 2]]
    land = {
        "chin": [0, 1.56, 0.10],
        "hipL": [0.1, 0.93, 0],
        "hipR": [-0.1, 0.93, 0],
        "eyeL": [0.035, 1.68, 0.12],
        "eyeR": [-0.035, 1.68, 0.12],
    }
    return {"vertices": vertices, "faces": faces, "landmarks": land}, {
        "vertices": vertices,
        "faces": faces,
        "details": {"neck_top": 1.51},
    }


def neckline_fixture():
    canonical, _ = plane_fixture()
    rows = [(0.0, 0.24, 0.13), (0.8, 0.24, 0.14), (1.35, 0.24, 0.14), (1.45, 0.16, 0.12), (1.51, 0.07, 0.07)]
    count = 64
    vertices = [
        [rx * math.sin(2 * math.pi * i / count), y, rz * math.cos(2 * math.pi * i / count)]
        for y, rx, rz in rows
        for i in range(count)
    ]
    faces = [
        [row * count + i, row * count + (i + 1) % count, (row + 1) * count + (i + 1) % count, (row + 1) * count + i]
        for row in range(len(rows) - 1)
        for i in range(count)
    ]
    rim = vertices[-count:]
    return canonical, {"vertices": vertices, "faces": faces, "details": {"neck_top": 1.51, "neck_rim": rim}}


def clipped_components(faces, values):
    """Count the shared-edge clipped mask, including new boundary vertices."""
    adjacency = defaultdict(set)
    for face in faces:
        polygon = []
        for a, b in zip(face[-1:] + face[:-1], face):
            if (values[a] >= 0) != (values[b] >= 0):
                polygon.append(("e", min(a, b), max(a, b)))
            if values[b] >= 0:
                polygon.append(("v", b))
        polygon = list(dict.fromkeys(polygon))
        if len(polygon) >= 3:
            for a, b in zip(polygon, polygon[1:] + polygon[:1]):
                adjacency[a].add(b)
                adjacency[b].add(a)
    pending = set(adjacency)
    result = []
    while pending:
        stack, found = [next(iter(pending))], set()
        while stack:
            vertex = stack.pop()
            if vertex not in found:
                found.add(vertex)
                stack.extend(adjacency[vertex] - found)
        pending -= found
        result.append(len(found))
    return result


class MeshAssertions(unittest.TestCase):
    def assert_closed_mesh(self, mesh):
        points, faces = mesh["vertices"], mesh["faces"]
        self.assertTrue(all(len(point) == 3 and all(math.isfinite(value) for value in point) for point in points))
        self.assertLessEqual(len(points), 128)
        edges = defaultdict(list)
        neighbors = defaultdict(set)
        volume = 0.0
        for face in faces:
            self.assertGreaterEqual(len(face), 3)
            self.assertEqual(len(face), len(set(face)))
            self.assertTrue(all(isinstance(index, int) and 0 <= index < len(points) for index in face))
            for a, b in zip(face, face[1:] + face[:1]):
                edges[tuple(sorted((a, b)))].append((a, b))
                neighbors[a].add(b)
                neighbors[b].add(a)
            a = points[face[0]]
            for i in range(1, len(face) - 1):
                b, c = points[face[i]], points[face[i + 1]]
                ab = [b[axis] - a[axis] for axis in range(3)]
                ac = [c[axis] - a[axis] for axis in range(3)]
                normal = [ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2], ab[0] * ac[1] - ab[1] * ac[0]]
                self.assertGreater(sum(value * value for value in normal), 1e-20)
                volume += (
                    sum(
                        a[axis] * (b[(axis + 1) % 3] * c[(axis + 2) % 3] - b[(axis + 2) % 3] * c[(axis + 1) % 3])
                        for axis in range(3)
                    )
                    / 6
                )
        self.assertTrue(all(len(values) == 2 and values[0] == tuple(reversed(values[1])) for values in edges.values()))
        reached, pending = set(), [0]
        while pending:
            index = pending.pop()
            if index not in reached:
                reached.add(index)
                pending.extend(neighbors[index] - reached)
        self.assertEqual(len(reached), len(points))
        self.assertGreater(volume, 1e-12)


class CharacterDetailTests(MeshAssertions):
    def setUp(self):
        self.frame = {"origin": [0, 1.68, 0], "height": 0.24}
        self.eyes = {"L": [0.035, 1.69, 0.10], "R": [-0.035, 1.69, 0.10]}

    def test_optional_values_preserve_plan_and_old_zero_offsets(self):
        for raw in (None, {}, {key: None for key in DETAIL_LIMITS}):
            source = character(detail=raw)
            before = copy.deepcopy(source)
            detail = resolve_detail(source)
            self.assertEqual(detail, dict.fromkeys(DETAIL_LIMITS, 0.0))
            self.assertEqual(source, before)
            self.assertEqual(
                face_detail_offset([0.04, 1.61, 0.11], self.frame, self.eyes, detail, "realistic"), [0, 0, 0]
            )
            self.assertEqual(hair_detail_offset([0, 1.79, 0.05], self.frame, [0, 1, 0], detail), [0, 0, 0])
            self.assertEqual(fabric_outward_offset(0.4, 0.3, detail, "trousers"), 0)

    def test_new_hair_variant_defaults_are_explicit_and_overridable(self):
        detail = resolve_detail(character(hair="short_wavy", detail=None))
        self.assertEqual(detail["hair_volume"], 0.6)
        self.assertEqual(detail["hair_sweep"], 0.35)
        self.assertEqual(
            resolve_detail(character(hair="short_wavy", detail={"hair_volume": 0, "hair_sweep": 0}))["hair_volume"], 0
        )

    def test_rejects_nonfinite_bool_unknown_and_out_of_range_controls(self):
        for key, (low, high) in DETAIL_LIMITS.items():
            for invalid in (True, float("nan"), float("inf"), low - 0.001, high + 0.001, "1"):
                with self.subTest(key=key, invalid=invalid), self.assertRaises(ValueError):
                    resolve_detail(character(detail={key: invalid}))
        for invalid in ([], "details", {"execute": "anything"}):
            with self.assertRaises(ValueError):
                resolve_detail(character(detail=invalid))

    def test_schema_is_strict_nullable_and_matches_validated_control_domain(self):
        schema = detail_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), set(DETAIL_LIMITS))
        for key, limits in DETAIL_LIMITS.items():
            self.assertIn("null", schema["properties"][key]["type"])
            self.assertEqual((schema["properties"][key]["minimum"], schema["properties"][key]["maximum"]), limits)

    def test_full_outfit_coverage_for_all_legal_hem_extremes(self):
        for height in (0.8, 1.8, 2.4):
            for fraction in (0.35, 0.52, 0.602, 0.65):
                for clothing in ("tshirt_trousers", "coverall"):
                    top = trouser_waist(fraction * height, 0.53 * height, height, clothing)
                    self.assertGreaterEqual(top - fraction * height, 0.015 * height - 1e-12)
                    self.assertGreaterEqual(top, 0.53 * height)
                self.assertEqual(trouser_waist(fraction * height, 0.53 * height, height, "robe_belt"), 0.53 * height)
        with self.assertRaises(ValueError):
            trouser_waist(float("nan"), 1.0, 1.8, "coverall")

    def test_fabric_is_positive_bounded_periodic_and_has_local_ridges(self):
        detail = resolve_detail(character(detail={"cloth_ease": 0.7, "fold_amplitude": 1}))
        for kind in ("shirt", "trousers", "coverall"):
            values = []
            for step in range(51):
                for ray in range(24):
                    y, angle = step / 50, 2 * math.pi * ray / 24
                    value = fabric_outward_offset(y, angle, detail, kind)
                    self.assertGreaterEqual(value, 0.025 * 0.7)
                    self.assertLessEqual(value, 0.025 * 0.7 + 0.006 + 1e-12)
                    self.assertAlmostEqual(
                        value, fabric_outward_offset(y, angle + 2 * math.pi, detail, kind), places=12
                    )
                    values.append(value)
            self.assertGreater(max(values) - min(values), 0.001)

    def test_wave_hair_extends_nape_and_never_pushes_into_scalp(self):
        # Equal-height front and rear points: rear belongs to hair, front does not.
        self.assertGreater(hair_detail_mask([0, 1.65, -0.10], self.frame), 0)
        self.assertLess(hair_detail_mask([0, 1.65, 0.10], self.frame), 0)
        detail = resolve_detail(character(hair="short_wavy", detail={"hair_volume": 1, "hair_sweep": -1}))
        for step in range(1, 16):
            latitude = math.pi * step / 16
            for ray in range(24):
                theta = 2 * math.pi * ray / 24
                normal = [
                    math.sin(latitude) * math.cos(theta),
                    math.cos(latitude),
                    math.sin(latitude) * math.sin(theta),
                ]
                point = [self.frame["origin"][axis] + 0.12 * normal[axis] for axis in range(3)]
                offset = hair_detail_offset(point, self.frame, normal, detail)
                self.assertGreaterEqual(sum(a * b for a, b in zip(normal, offset)), 0)
                self.assertLess(math.sqrt(sum(value * value for value in offset)), 0.055)

    def test_expression_signs_locality_and_finite_extremes(self):
        corners = [[-0.0384, 1.6056, 0.11], [0.0384, 1.6056, 0.11]]
        smile = resolve_detail(character(detail={"smile": 1}))
        for point in corners:
            self.assertGreater(face_detail_offset(point, self.frame, self.eyes, smile, "realistic")[1], 0.005)
            self.assertLess(
                face_detail_offset([point[0], point[1], -0.11], self.frame, self.eyes, smile, "realistic")[1], 1e-8
            )
        for control in (-1, 1):
            detail = resolve_detail(character(detail={"forehead_height": control}))
            offset = face_detail_offset([0, 1.80, 0], self.frame, self.eyes, detail, "realistic")
            self.assertGreater(control * offset[1], 0)
            self.assertLessEqual(abs(offset[1]), 0.08 * self.frame["height"])
            self.assertEqual(face_detail_offset([0, 1.50, 0.10], self.frame, self.eyes, detail, "realistic"), [0, 0, 0])
        for sign in (-1, 1):
            detail = resolve_detail(character(detail={"brow_raise": sign}))
            self.assertGreater(
                sign * face_detail_offset([0.035, 1.714, 0.10], self.frame, self.eyes, detail, "stylized")[1], 0.001
            )

    def test_wave_bulk_has_visible_bounded_relief_instead_of_uniform_cap(self):
        detail = resolve_detail(character(hair="short_wavy", detail={"hair_volume": 1, "hair_sweep": 0}))
        relief = []
        for ray in range(64):
            theta = 2 * math.pi * ray / 64
            normal = [0.8 * math.cos(theta), 0.6, 0.8 * math.sin(theta)]
            point = [self.frame["origin"][axis] + 0.12 * normal[axis] for axis in range(3)]
            offset = hair_detail_offset(point, self.frame, normal, detail)
            relief.append(sum(a * b for a, b in zip(normal, offset)))
        self.assertGreater(max(relief) - min(relief), 0.008)
        self.assertLessEqual(max(relief), 0.195 * self.frame["height"])

    def test_folded_work_collar_has_broad_closed_plate_silhouette(self):
        canonical, garment = neckline_fixture()
        collars = [
            piece for piece in accessories(canonical, character(), garment) if piece["name"].startswith("WorkCollar")
        ]
        self.assertEqual(len(collars), 2)
        for piece in collars:
            self.assert_closed_mesh(piece)
            points = piece["vertices"]
            self.assertGreater(max(p[0] for p in points) - min(p[0] for p in points), 0.05 * 1.8)
            self.assertGreater(max(p[1] for p in points) - min(p[1] for p in points), 0.070 * 1.8)

    def test_coverall_trim_cages_are_closed_connected_and_fit_real_surface(self):
        canonical, garment = neckline_fixture()
        c = character(detail={"pocket_size": 1})
        before = copy.deepcopy((canonical, garment, c))
        pieces = accessories(canonical, c, garment)
        self.assertEqual(
            {piece["name"] for piece in pieces},
            {"WorkCollarL", "WorkCollarR", "WorkPlacket", "PocketPanelL", "PocketPanelR", "PocketLipL", "PocketLipR"},
        )
        for piece in pieces:
            self.assert_closed_mesh(piece)
            self.assertEqual(piece["group"], "closed_garment")
            self.assertTrue(all(point[2] > 0 for point in piece["vertices"]))
        self.assertEqual((canonical, garment, c), before)
        self.assertEqual(accessories(canonical, character(clothing="tshirt_trousers", detail=None), garment), [])

    def test_collar_fold_edge_is_on_actual_neckline_not_guessed_chest_height(self):
        canonical, garment = neckline_fixture()
        # A deliberately wrong descriptive height must not move the seam away
        # from the geometric rim. Its interpolation lies on actual ring edges.
        garment["details"]["neck_top"] = 1.45
        for piece in accessories(canonical, character(), garment):
            if not piece["name"].startswith("WorkCollar"):
                continue
            attachment = piece["attachment"]
            self.assertEqual(attachment["kind"], "fold_edge_on_actual_neckline")
            for index, point in zip(attachment["root_vertices"], attachment["rim_positions"]):
                vertex = piece["vertices"][index]
                self.assertAlmostEqual(vertex[0], point[0])
                self.assertAlmostEqual(vertex[1], point[1])
                self.assertAlmostEqual(vertex[2] - point[2], attachment["raw_surface_clearance"])
                self.assertAlmostEqual(point[1], 1.51)
                nearest_edge = float("inf")
                rim = garment["details"]["neck_rim"]
                for a, b in zip(rim, rim[1:] + rim[:1]):
                    edge = [bb - aa for aa, bb in zip(a, b)]
                    t = max(0, min(1, sum((p - aa) * d for p, aa, d in zip(point, a, edge)) / sum(d * d for d in edge)))
                    nearest_edge = min(nearest_edge, math.dist(point, [aa + t * d for aa, d in zip(a, edge)]))
                self.assertLess(nearest_edge, 1e-10)

    def test_actual_clipped_scalp_boundary_has_zero_detail_lift_and_continuous_ramp(self):
        from anatomy_body import BODY_FACES, BODY_HEAD_FRAME, BODY_VERTICES

        frame = dict(BODY_HEAD_FRAME)
        detail = resolve_detail(character(hair="short_wavy", detail={"hair_volume": 1, "hair_sweep": 1}))
        values = [hair_detail_mask(point, frame) for point in BODY_VERTICES]
        boundary = {}
        for face in BODY_FACES:
            for a, b in zip(face, face[1:] + face[:1]):
                if (values[a] >= 0) != (values[b] >= 0):
                    t = values[a] / (values[a] - values[b])
                    boundary[tuple(sorted((a, b)))] = [
                        p + t * (q - p) for p, q in zip(BODY_VERTICES[a], BODY_VERTICES[b])
                    ]
        self.assertGreater(len(boundary), 20)
        for point in boundary.values():
            exact = dict(frame, hairline_distance=0.0)
            self.assertEqual(hair_detail_offset(point, exact, [0, 1, 0], detail), [0, 0, 0])
            near = dict(frame, hairline_distance=0.005 * frame["height"])
            self.assertLess(math.dist(hair_detail_offset(point, near, [0, 1, 0], detail), [0, 0, 0]), 1e-5)

    def test_patch_panels_fit_between_observed_belt_and_hem_and_zero_omits(self):
        canonical, garment = plane_fixture()
        for hem, belt in ((0.45, 0.595), (0.48, 0.506), (0.65, 0.7)):
            c = character(clothing="robe_belt", hem_height=hem, belt_height=belt, detail={"pocket_size": 1})
            garment["details"]["hem"] = hem * c["height"]
            pieces = accessories(canonical, c, garment)
            panels = [piece for piece in pieces if piece["name"].startswith("PocketPanel")]
            self.assertEqual(len(panels), 2)
            for piece in pieces:
                self.assert_closed_mesh(piece)
            for panel in panels:
                self.assertGreater(min(p[1] for p in panel["vertices"]), hem * c["height"])
                self.assertLess(max(p[1] for p in panel["vertices"]), belt * c["height"])
            c["detail"]["pocket_size"] = 0
            self.assertEqual(accessories(canonical, c, garment), [])

    def test_eyebrows_are_closed_fitted_hair_and_old_plans_remain_unchanged(self):
        canonical, _ = plane_fixture()
        self.assertEqual(eyebrow_accessories(canonical, character(detail=None)), [])
        plain = eyebrow_accessories(canonical, character(detail={}))
        raised = eyebrow_accessories(canonical, character(detail={"brow_raise": 1}))
        cartoon = eyebrow_accessories(canonical, character(style="stylized"))
        for index, piece in enumerate(plain):
            self.assert_closed_mesh(piece)
            self.assertEqual(piece["material"], "AnatomyHair")
            self.assertGreater(
                min(point[1] for point in raised[index]["vertices"]), min(point[1] for point in piece["vertices"])
            )
            for x, y, z in piece["vertices"]:
                self.assertGreater(z, 0.10 + 0.04 * x + 0.02 * y)
            self.assert_closed_mesh(cartoon[index])
        real_width = max(point[1] for point in plain[0]["vertices"]) - min(point[1] for point in plain[0]["vertices"])
        cartoon_width = max(point[1] for point in cartoon[0]["vertices"]) - min(
            point[1] for point in cartoon[0]["vertices"]
        )
        self.assertGreater(cartoon_width, real_width)

    def test_invalid_surface_and_off_surface_accessories_fail_closed(self):
        canonical, garment = plane_fixture()
        c = character(clothing="robe_belt", hem_height=0.45, belt_height=0.595, detail={"pocket_size": 1})
        garment["faces"] = [[0, 1, 100]]
        with self.assertRaisesRegex(ValueError, "detail_mesh_invalid"):
            accessories(canonical, c, garment)
        canonical, garment = plane_fixture()
        garment["vertices"] = [[x + 4, y, z] for x, y, z in garment["vertices"]]
        with self.assertRaisesRegex(ValueError, "detail_projection_missed"):
            accessories(canonical, c, garment)

    def test_brow_projection_on_committed_anatomy_has_closed_surface_fitted_arcs(self):
        from anatomy_body import BODY_FACES, BODY_LANDMARKS, BODY_VERTICES

        # The ordinary CC0 asset is normalized to one unit in the source data.
        # Exercise the real nose/eye/forehead surface, not just the tilted plane.
        canonical = {
            "vertices": [[value * 1.8 for value in point] for point in BODY_VERTICES],
            "faces": BODY_FACES,
            "landmarks": {key: [value * 1.8 for value in point] for key, point in BODY_LANDMARKS.items()},
        }
        for style in ("realistic", "stylized"):
            meshes = eyebrow_accessories(canonical, character(style=style))
            self.assertEqual(len(meshes), 2)
            for mesh in meshes:
                self.assert_closed_mesh(mesh)
                self.assertGreater(min(point[1] for point in mesh["vertices"]), 1.4)

    def test_wave_scalp_mask_excludes_real_internal_mouth_without_component_deletion(self):
        from anatomy_body import (
            BODY_AGE_DELTAS,
            BODY_FACES,
            BODY_HEAD_FRAME,
            BODY_LANDMARK_AGE_DELTAS,
            BODY_LANDMARKS,
            BODY_VERTICES,
        )

        for age in (0, 0.65, 1):
            points = [
                [value + age * delta for value, delta in zip(point, change)]
                for point, change in zip(BODY_VERTICES, BODY_AGE_DELTAS)
            ]
            chin = BODY_LANDMARKS["chin"][1] + age * BODY_LANDMARK_AGE_DELTAS["chin"][1]
            top = max(point[1] for point in points)
            frame = {"origin": [0, (top + chin) / 2, BODY_HEAD_FRAME["origin"][2]], "height": top - chin}
            for width, depth in ((0.85, 0.85), (1, 1), (1.15, 1.15)):
                morphed = [
                    [p[0] * width, p[1], frame["origin"][2] + (p[2] - frame["origin"][2]) * depth] for p in points
                ]
                components = clipped_components(BODY_FACES, [hair_detail_mask(point, frame) for point in morphed])
                self.assertEqual(len(components), 1, (age, width, depth, components))


if __name__ == "__main__":
    unittest.main()
