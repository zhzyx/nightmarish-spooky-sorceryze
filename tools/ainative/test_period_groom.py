import copy
import math
import unittest

from period_groom import (
    GROOM_LIMITS,
    MAX_GROOM_TRIANGLES,
    MAX_GROOM_VERTICES,
    _scalp,
    _triangles,
    build_period_groom,
    measure_groom_spec,
    period_groom_schema,
    resolve_period_groom,
)


def fixture(height=1.8):
    hh = height / 7.5
    origin = [0, height - hh / 2, 0]
    count, rows = 24, 12
    vertices = [[0, height, 0]]
    for row in range(1, rows):
        phi = math.pi * row / rows
        for j in range(count):
            theta = 2 * math.pi * j / count
            vertices.append([
                0.32 * hh * math.sin(phi) * math.sin(theta),
                origin[1] + 0.5 * hh * math.cos(phi),
                0.37 * hh * math.sin(phi) * math.cos(theta),
            ])
    bottom = len(vertices)
    vertices.append([0, height - hh, 0])
    faces = [[0, 1 + j, 1 + (j + 1) % count] for j in range(count)]
    for row in range(rows - 2):
        for j in range(count):
            a, b = 1 + row * count + j, 1 + row * count + (j + 1) % count
            faces.append([a, a + count, b + count, b])
    faces.extend([[bottom, 1 + (rows - 2) * count + (j + 1) % count, 1 + (rows - 2) * count + j] for j in range(count)])
    return {
        "vertices": vertices,
        "faces": faces,
        "head_frame": {"origin": origin, "height": hh},
        "landmarks": {
            "eyeL": [0.03, origin[1] - 0.03 * hh, 0.06],
            "eyeR": [-0.03, origin[1] - 0.03 * hh, 0.06],
            "chin": [0, height - hh, 0],
        },
    }, {
        "height": height,
        "period_groom": {"version": 1, "hairstyle": "swept_back_bun", "facial_hair": "moustache_goatee"},
    }


class PeriodGroomTests(unittest.TestCase):
    def test_missing_null_is_exact_noop_without_reading_mesh(self):
        for character in ({}, {"period_groom": None}):
            before = copy.deepcopy(character)
            self.assertIsNone(resolve_period_groom(character))
            self.assertEqual(build_period_groom({}, character), [])
            self.assertEqual(character, before)

    def test_schema_and_numeric_validation_reject_untrusted_data(self):
        self.assertFalse(period_groom_schema()["additionalProperties"])
        _, character = fixture()
        for key, (low, high, _) in GROOM_LIMITS.items():
            for bad in (True, float("nan"), float("inf"), low - 0.001, high + 0.001, "code"):
                value = copy.deepcopy(character)
                value["period_groom"][key] = bad
                with self.assertRaises(ValueError):
                    resolve_period_groom(value)
        for change in ({"unknown": 1}, {"version": True}, {"hairstyle": "exec"}, {"facial_hair": "exec"}):
            value = copy.deepcopy(character)
            value["period_groom"].update(change)
            with self.assertRaises(ValueError):
                resolve_period_groom(value)

    def test_closed_positive_bounded_cages_at_small_and_large_heights(self):
        for height in (0.8, 2.4):
            canonical, character = fixture(height)
            before = copy.deepcopy((canonical, character))
            specs = build_period_groom(canonical, character)
            metrics = [measure_groom_spec(spec) for spec in specs]
            self.assertEqual(len(specs), 7)
            self.assertLessEqual(sum(m["vertices"] for m in metrics), MAX_GROOM_VERTICES)
            self.assertLessEqual(sum(m["triangles"] for m in metrics), MAX_GROOM_TRIANGLES)
            self.assertTrue(all(m["signed_volume"] > 1e-12 and m["minimum_triangle_area"] > 1e-12 for m in metrics))
            self.assertEqual((canonical, character), before)

    def test_scalp_boundary_seated_and_low_nape_preserved(self):
        canonical, character = fixture()
        frame = canonical["head_frame"]
        values = resolve_period_groom(character)
        vertices, faces, roots = _scalp(
            _triangles(canonical, frame["origin"][1] - frame["height"]), frame["origin"], frame["height"], values
        )
        metric = measure_groom_spec({"vertices": vertices, "faces": faces})
        self.assertEqual(metric["components"], 1)
        distances = [math.dist(root, outer) for root, outer in roots]
        self.assertLess(max(distances), 0.001)
        self.assertLess(roots[64][0][1], roots[0][0][1])

    def test_mutated_real_cage_rejects_open_inward_and_degenerate(self):
        canonical, character = fixture()
        spec = build_period_groom(canonical, character)[1]
        for mutate in ("open", "inward", "degenerate"):
            value = copy.deepcopy(spec)
            if mutate == "open":
                value["faces"].pop()
            elif mutate == "inward":
                value["faces"] = [face[::-1] for face in value["faces"]]
            else:
                value["vertices"][1] = value["vertices"][2]
            with self.assertRaises(ValueError):
                measure_groom_spec(value)

    def test_controls_change_actual_contour_and_none_preserves_head_only(self):
        canonical, character = fixture()
        original = build_period_groom(canonical, character)
        value = copy.deepcopy(character)
        value["period_groom"].update(bun_size=1.4, bun_back=1, moustache_width=1.4, goatee_length=1.5)
        altered = build_period_groom(canonical, value)
        self.assertGreater(max(p[0] for p in altered[1]["vertices"]), max(p[0] for p in original[1]["vertices"]))
        self.assertLess(min(p[1] for p in altered[4]["vertices"]), min(p[1] for p in original[4]["vertices"]))
        value["period_groom"]["facial_hair"] = "none"
        self.assertEqual(len(build_period_groom(canonical, value)), 4)


if __name__ == "__main__":
    unittest.main()
