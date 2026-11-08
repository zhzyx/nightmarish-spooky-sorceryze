"""Strict data and actual Blender tests for trusted organic pattern expansion."""

import copy
import math
import unittest
from collections import Counter

import test_sculpt_builder as base_tests
from organic_detail import cup_mesh, cup_triangle_budget, expand_patterns, transported_frames, validate_caps
from sculpt_builder import MAX_TRIANGLES, MAX_VERTICES, _loft, _loft_sections, validate_plan
from test_sculpt_builder import BLENDER, plan, region, section, surface

TRANSFORM_NORMAL_PROBE = 'import sys,json,math\nfrom pathlib import Path\nsys.path.insert(0,sys.argv[sys.argv.index("--")+1])\nimport bpy,bmesh\nfrom mathutils import Vector,Euler,Quaternion\nimport sculpt_builder as core\nplan=json.loads(Path(sys.argv[-1]).read_text())\nregions,measurements=core.expand_patterns(plan,core._loft_sections,core.MAX_TRIANGLES,core.MAX_VERTICES)\nplacements=[p for m in measurements for p in m["placements"]]\nfor region,placement in zip(regions,placements):\n mesh=core._surface_mesh(region["surface"],bpy,bmesh,Vector,Euler,Quaternion)\n points=[mesh.vertices[3*20+i].co for i in (0,5,10)]\n actual=(points[1]-points[0]).cross(points[2]-points[0]).normalized()\n rotation=Euler(tuple(math.radians(v) for v in placement["rotation_degrees"]),"YXZ").to_matrix()\n normal=rotation@Vector(tuple(placement["axis"][i]/placement["size"][i] for i in range(3)))\n normal=Vector((normal.x,-normal.z,normal.y)).normalized()\n assert abs(actual.dot(normal))>1-1e-6,(actual[:],normal[:])\n assert all(math.isfinite(v) and abs(v)<1000 for vertex in mesh.vertices for v in vertex.co)\nprint("TRANSFORMED_MOUTH_NORMAL_OK",len(regions))\n'


def original_organic_plan():
    """Exact genuine N7 data protects the dense-sweep positive-island regression."""
    import json

    return json.loads(
        '{"character":null,"completion":{"inferred_regions":["mantle","head","arm_upper_left","arm_rear_left","arm_middle_left","arm_lower_left","arm_front_left","arm_front_right","arm_lower_right","arm_upper_right","eye_left_ridge","eye_right_ridge","eye_left","eye_right","pupil_left","pupil_right","sucker_01","sucker_02","sucker_03","sucker_04","sucker_05","sucker_06","sucker_07","sucker_08","sucker_09","sucker_10","sucker_11","sucker_12"],"mode":"plausible"},"finish":{"smooth_iterations":3,"subdivision":1,"voxel_size":0.012},"materials":[{"color":[0.69,0.19,0.055,1],"name":"orange_skin","roughness":0.43},{"color":[0.81,0.36,0.19,1],"name":"sucker_flesh","roughness":0.48},{"color":[0.56,0.29,0.065,1],"name":"iris_gold","roughness":0.3},{"color":[0.017,0.012,0.007,1],"name":"pupil_black","roughness":0.23}],"name":"Orange octopus with eight curled arms","regions":[{"material":"orange_skin","name":"mantle","role":"body","surface":{"faces":[],"kind":"loft","position":[0,0,0],"rotation_degrees":[0,0,0],"sections":[{"center":[0.19,1.76,-0.1],"radius":[0.25,0.28,0.25,0.25],"roll":-30},{"center":[0.39,1.94,-0.15],"radius":[0.43,0.43,0.37,0.36],"roll":-30},{"center":[0.6,2.19,-0.19],"radius":[0.5,0.49,0.43,0.42],"roll":-30},{"center":[0.75,2.44,-0.22],"radius":[0.43,0.42,0.39,0.38],"roll":-30},{"center":[0.79,2.63,-0.23],"radius":[0.28,0.28,0.27,0.27],"roll":-30},{"center":[0.77,2.73,-0.23],"radius":[0.08,0.08,0.09,0.09],"roll":-30}],"size":[1,1,1],"vertices":[]}},{"material":"orange_skin","name":"head","role":"body","surface":{"faces":[],"kind":"loft","position":[0,0,0],"rotation_degrees":[0,0,0],"sections":[{"center":[-0.05,1.05,0.13],"radius":[0.49,0.49,0.27,0.28],"roll":0},{"center":[-0.05,1.29,0.12],"radius":[0.45,0.45,0.31,0.29],"roll":0},{"center":[-0.04,1.53,0.08],"radius":[0.32,0.33,0.32,0.28],"roll":0},{"center":[0,1.78,0.02],"radius":[0.28,0.3,0.28,0.27],"roll":0},{"center":[0.08,1.94,-0.02],"radius":[0.23,0.25,0.22,0.23],"roll":0}],"size":[1,1,1],"vertices":[]}},{"material":"orange_skin","name":"arm_upper_left","role":"body","surface":{"faces":[],"kind":"loft","position":[0,0,0],"rotation_degrees":[0,0,0],"sections":[{"center":[-0.19,1.49,0.02],"radius":[0.24,0.24,0.21,0.21],"roll":0},{"center":[-0.53,1.54,0.01],"radius":[0.21,0.21,0.18,0.18],"roll":0},{"center":[-0.94,1.61,0],"radius":[0.17,0.17,0.145,0.145],"roll":0},{"center":[-1.18,1.79,0.01],"radius":[0.135,0.135,0.12,0.12],"roll":0},{"center":[-1.24,2.04,0.04],"radius":[0.105,0.105,0.095,0.095],"roll":0},{"center":[-1.13,2.22,0.08],"radius":[0.08,0.08,0.075,0.075],"roll":0},{"center":[-0.94,2.25,0.1],"radius":[0.058,0.058,0.055,0.055],"roll":0},{"center":[-0.83,2.15,0.12],"radius":[0.038,0.038,0.038,0.038],"roll":0},{"center":[-0.84,2.05,0.13],"radius":[0.023,0.023,0.023,0.023],"roll":0},{"center":[-0.9,2.04,0.13],"radius":[0.008,0.008,0.008,0.008],"roll":0}],"size":[1,1,1],"vertices":[]}},{"material":"orange_skin","name":"arm_rear_left","role":"body","surface":{"faces":[],"kind":"loft","position":[0,0,0],"rotation_degrees":[0,0,0],"sections":[{"center":[-0.15,1.5,-0.14],"radius":[0.21,0.21,0.18,0.18],"roll":0},{"center":[-0.42,1.65,-0.23],"radius":[0.16,0.16,0.14,0.14],"roll":0},{"center":[-0.47,1.89,-0.26],"radius":[0.12,0.12,0.105,0.105],"roll":0},{"center":[-0.39,2.12,-0.24],"radius":[0.09,0.09,0.08,0.08],"roll":0},{"center":[-0.41,2.27,-0.19],"radius":[0.066,0.066,0.06,0.06],"roll":0},{"center":[-0.53,2.34,-0.13],"radius":[0.043,0.043,0.04,0.04],"roll":0},{"center":[-0.65,2.33,-0.1],"radius":[0.025,0.025,0.024,0.024],"roll":0},{"center":[-0.7,2.27,-0.08],"radius":[0.008,0.008,0.008,0.008],"roll":0}],"size":[1,1,1],"vertices":[]}},{"material":"orange_skin","name":"arm_middle_left","role":"body","surface":{"faces":[],"kind":"loft","position":[0,0,0],"rotation_degrees":[0,0,0],"sections":[{"center":[-0.23,1.31,0.09],"radius":[0.25,0.25,0.21,0.21],"roll":0},{"center":[-0.6,1.22,0.1],"radius":[0.21,0.21,0.18,0.18],"roll":0},{"center":[-0.97,1.37,0.12],"radius":[0.17,0.17,0.14,0.14],"roll":0},{"center":[-1.28,1.39,0.15],"radius":[0.13,0.13,0.115,0.115],"roll":0},{"center":[-1.47,1.23,0.19],"radius":[0.1,0.1,0.09,0.09],"roll":0},{"center":[-1.54,1.01,0.23],"radius":[0.071,0.071,0.065,0.065],"roll":0},{"center":[-1.5,0.88,0.26],"radius":[0.047,0.047,0.043,0.043],"roll":0},{"center":[-1.39,0.86,0.28],"radius":[0.029,0.029,0.028,0.028],"roll":0},{"center":[-1.33,0.94,0.29],"radius":[0.009,0.009,0.009,0.009],"roll":0}],"size":[1,1,1],"vertices":[]}},{"material":"orange_skin","name":"arm_lower_left","role":"body","surface":{"faces":[],"kind":"loft","position":[0,0,0],"rotation_degrees":[0,0,0],"sections":[{"center":[-0.25,1.22,0.19],"radius":[0.25,0.25,0.22,0.22],"roll":0},{"center":[-0.55,1.03,0.24],"radius":[0.22,0.22,0.19,0.19],"roll":0},{"center":[-0.88,0.87,0.28],"radius":[0.18,0.18,0.16,0.16],"roll":0},{"center":[-1.1,0.64,0.31],"radius":[0.14,0.14,0.125,0.125],"roll":0},{"center":[-1.13,0.39,0.35],"radius":[0.1,0.1,0.09,0.09],"roll":0},{"center":[-1.17,0.22,0.39],"radius":[0.067,0.067,0.06,0.06],"roll":0},{"center":[-1.31,0.16,0.41],"radius":[0.043,0.043,0.04,0.04],"roll":0},{"center":[-1.43,0.2,0.42],"radius":[0.026,0.026,0.025,0.025],"roll":0},{"center":[-1.44,0.27,0.43],"radius":[0.014,0.014,0.014,0.014],"roll":0},{"center":[-1.39,0.28,0.43],"radius":[0.006,0.006,0.006,0.006],"roll":0}],"size":[1,1,1],"vertices":[]}},{"material":"orange_skin","name":"arm_front_left","role":"body","surface":{"faces":[],"kind":"loft","position":[0,0,0],"rotation_degrees":[0,0,0],"sections":[{"center":[-0.07,1.18,0.28],"radius":[0.25,0.25,0.23,0.23],"roll":0},{"center":[-0.16,0.93,0.38],"radius":[0.22,0.22,0.2,0.2],"roll":0},{"center":[-0.35,0.66,0.47],"radius":[0.185,0.185,0.16,0.16],"roll":0},{"center":[-0.51,0.4,0.52],"radius":[0.15,0.15,0.13,0.13],"roll":0},{"center":[-0.5,0.18,0.57],"radius":[0.115,0.115,0.1,0.1],"roll":0},{"center":[-0.38,0.035,0.61],"radius":[0.08,0.08,0.07,0.07],"roll":0},{"center":[-0.21,0.005,0.64],"radius":[0.051,0.051,0.047,0.047],"roll":0},{"center":[-0.12,0.065,0.66],"radius":[0.029,0.029,0.028,0.028],"roll":0},{"center":[-0.15,0.14,0.67],"radius":[0.009,0.009,0.009,0.009],"roll":0}],"size":[1,1,1],"vertices":[]}},{"material":"orange_skin","name":"arm_front_right","role":"body","surface":{"faces":[],"kind":"loft","position":[0,0,0],"rotation_degrees":[0,0,0],"sections":[{"center":[0.17,1.19,0.23],"radius":[0.25,0.25,0.22,0.22],"roll":0},{"center":[0.25,0.9,0.3],"radius":[0.22,0.22,0.19,0.19],"roll":0},{"center":[0.45,0.65,0.34],"radius":[0.18,0.18,0.16,0.16],"roll":0},{"center":[0.71,0.46,0.38],"radius":[0.135,0.135,0.12,0.12],"roll":0},{"center":[0.91,0.27,0.42],"radius":[0.095,0.095,0.084,0.084],"roll":0},{"center":[0.93,0.1,0.46],"radius":[0.066,0.066,0.059,0.059],"roll":0},{"center":[0.85,0.015,0.49],"radius":[0.042,0.042,0.039,0.039],"roll":0},{"center":[0.76,0.005,0.51],"radius":[0.024,0.024,0.023,0.023],"roll":0},{"center":[0.72,0.04,0.52],"radius":[0.008,0.008,0.008,0.008],"roll":0}],"size":[1,1,1],"vertices":[]}},{"material":"orange_skin","name":"arm_lower_right","role":"body","surface":{"faces":[],"kind":"loft","position":[0,0,0],"rotation_degrees":[0,0,0],"sections":[{"center":[0.24,1.27,0.07],"radius":[0.24,0.24,0.2,0.2],"roll":0},{"center":[0.56,1.13,0.08],"radius":[0.21,0.21,0.18,0.18],"roll":0},{"center":[0.88,1.09,0.12],"radius":[0.17,0.17,0.145,0.145],"roll":0},{"center":[1.17,0.98,0.16],"radius":[0.13,0.13,0.115,0.115],"roll":0},{"center":[1.32,0.8,0.21],"radius":[0.095,0.095,0.084,0.084],"roll":0},{"center":[1.31,0.62,0.25],"radius":[0.066,0.066,0.06,0.06],"roll":0},{"center":[1.18,0.56,0.28],"radius":[0.045,0.045,0.041,0.041],"roll":0},{"center":[1.09,0.62,0.3],"radius":[0.03,0.03,0.028,0.028],"roll":0},{"center":[1.11,0.71,0.31],"radius":[0.019,0.019,0.018,0.018],"roll":0},{"center":[1.17,0.7,0.31],"radius":[0.007,0.007,0.007,0.007],"roll":0}],"size":[1,1,1],"vertices":[]}},{"material":"orange_skin","name":"arm_upper_right","role":"body","surface":{"faces":[],"kind":"loft","position":[0,0,0],"rotation_degrees":[0,0,0],"sections":[{"center":[0.22,1.47,-0.09],"radius":[0.22,0.22,0.19,0.19],"roll":0},{"center":[0.55,1.4,-0.13],"radius":[0.19,0.19,0.16,0.16],"roll":0},{"center":[0.88,1.48,-0.14],"radius":[0.15,0.15,0.13,0.13],"roll":0},{"center":[1.17,1.39,-0.1],"radius":[0.115,0.115,0.1,0.1],"roll":0},{"center":[1.42,1.42,-0.05],"radius":[0.086,0.086,0.077,0.077],"roll":0},{"center":[1.55,1.57,0.01],"radius":[0.062,0.062,0.057,0.057],"roll":0},{"center":[1.51,1.75,0.06],"radius":[0.043,0.043,0.04,0.04],"roll":0},{"center":[1.39,1.8,0.09],"radius":[0.029,0.029,0.027,0.027],"roll":0},{"center":[1.3,1.77,0.11],"radius":[0.018,0.018,0.017,0.017],"roll":0},{"center":[1.28,1.71,0.12],"radius":[0.007,0.007,0.007,0.007],"roll":0}],"size":[1,1,1],"vertices":[]}},{"material":"orange_skin","name":"eye_left_ridge","role":"body","surface":{"faces":[],"kind":"ellipsoid","position":[-0.2,1.92,0.13],"rotation_degrees":[0,-30,-10],"sections":[],"size":[0.24,0.3,0.26],"vertices":[]}},{"material":"orange_skin","name":"eye_right_ridge","role":"body","surface":{"faces":[],"kind":"ellipsoid","position":[0.2,1.83,0.23],"rotation_degrees":[0,25,-15],"sections":[],"size":[0.32,0.32,0.28],"vertices":[]}},{"material":"iris_gold","name":"eye_left","role":"accessory","surface":{"faces":[],"kind":"ellipsoid","position":[-0.263,1.93,0.238],"rotation_degrees":[0,-35,-10],"sections":[],"size":[0.105,0.16,0.075],"vertices":[]}},{"material":"iris_gold","name":"eye_right","role":"accessory","surface":{"faces":[],"kind":"ellipsoid","position":[0.224,1.84,0.359],"rotation_degrees":[0,15,-18],"sections":[],"size":[0.145,0.18,0.075],"vertices":[]}},{"material":"pupil_black","name":"pupil_left","role":"accessory","surface":{"faces":[],"kind":"ellipsoid","position":[-0.281,1.933,0.269],"rotation_degrees":[0,-35,-10],"sections":[],"size":[0.047,0.09,0.022],"vertices":[]}},{"material":"pupil_black","name":"pupil_right","role":"accessory","surface":{"faces":[],"kind":"ellipsoid","position":[0.233,1.842,0.395],"rotation_degrees":[0,15,16],"sections":[],"size":[0.104,0.047,0.024],"vertices":[]}},{"material":"sucker_flesh","name":"sucker_01","role":"accessory","surface":{"faces":[],"kind":"ellipsoid","position":[-0.36,0.71,0.607],"rotation_degrees":[0,0,-30],"sections":[],"size":[0.105,0.13,0.065],"vertices":[]}},{"material":"sucker_flesh","name":"sucker_02","role":"accessory","surface":{"faces":[],"kind":"ellipsoid","position":[-0.445,0.55,0.636],"rotation_degrees":[0,0,-24],"sections":[],"size":[0.1,0.125,0.065],"vertices":[]}},{"material":"sucker_flesh","name":"sucker_03","role":"accessory","surface":{"faces":[],"kind":"ellipsoid","position":[-0.49,0.39,0.646],"rotation_degrees":[0,0,0],"sections":[],"size":[0.095,0.12,0.06],"vertices":[]}},{"material":"sucker_flesh","name":"sucker_04","role":"accessory","surface":{"faces":[],"kind":"ellipsoid","position":[-0.475,0.245,0.666],"rotation_degrees":[0,0,15],"sections":[],"size":[0.085,0.105,0.055],"vertices":[]}},{"material":"sucker_flesh","name":"sucker_05","role":"accessory","surface":{"faces":[],"kind":"ellipsoid","position":[-0.405,0.13,0.682],"rotation_degrees":[0,0,35],"sections":[],"size":[0.075,0.09,0.05],"vertices":[]}},{"material":"sucker_flesh","name":"sucker_06","role":"accessory","surface":{"faces":[],"kind":"ellipsoid","position":[-0.84,0.86,0.426],"rotation_degrees":[0,0,-55],"sections":[],"size":[0.105,0.13,0.06],"vertices":[]}},{"material":"sucker_flesh","name":"sucker_07","role":"accessory","surface":{"faces":[],"kind":"ellipsoid","position":[-0.98,0.745,0.43],"rotation_degrees":[0,0,-40],"sections":[],"size":[0.095,0.12,0.055],"vertices":[]}},{"material":"sucker_flesh","name":"sucker_08","role":"accessory","surface":{"faces":[],"kind":"ellipsoid","position":[-1.075,0.6,0.44],"rotation_degrees":[0,0,-15],"sections":[],"size":[0.08,0.105,0.05],"vertices":[]}},{"material":"sucker_flesh","name":"sucker_09","role":"accessory","surface":{"faces":[],"kind":"ellipsoid","position":[0.86,1.005,0.248],"rotation_degrees":[0,0,75],"sections":[],"size":[0.085,0.115,0.055],"vertices":[]}},{"material":"sucker_flesh","name":"sucker_10","role":"accessory","surface":{"faces":[],"kind":"ellipsoid","position":[1.015,0.96,0.263],"rotation_degrees":[0,0,65],"sections":[],"size":[0.08,0.105,0.05],"vertices":[]}},{"material":"sucker_flesh","name":"sucker_11","role":"accessory","surface":{"faces":[],"kind":"ellipsoid","position":[-1.22,1.88,0.12],"rotation_degrees":[0,0,-15],"sections":[],"size":[0.075,0.1,0.045],"vertices":[]}},{"material":"sucker_flesh","name":"sucker_12","role":"accessory","surface":{"faces":[],"kind":"ellipsoid","position":[-1.16,1.74,0.115],"rotation_degrees":[0,0,-35],"sections":[],"size":[0.085,0.11,0.05],"vertices":[]}}],"version":2}'
    )


def patterned_plan():
    value = plan()
    value["regions"] = [
        region(
            "Arm",
            surface(
                "loft",
                position=[0, 0, 0],
                sections=[
                    section([0, 0, 0], [0.18] * 4),
                    section([0, 0.5, 0], [0.15] * 4),
                    section([0, 1, 0], [0.10] * 4),
                ],
            ),
        )
    ]
    value["regions"][0]["surface"]["end_caps"] = {"start": "rounded", "end": "rounded", "depth": 0.75}
    value["repeat_patterns"] = [
        dict(
            name="Cups",
            source_region="Arm",
            material="skin",
            count=8,
            rows=2,
            start=0.08,
            end=0.88,
            side_degrees=90,
            row_spread_degrees=32,
            radius=0.035,
            radius_tip_scale=0.5,
            depth=0.5,
        )
    ]
    value["completion"]["inferred_regions"] = ["Arm", "Cups"]
    value["finish"].update(voxel_size=0.035, subdivision=1)
    return value


def volume(vertices, faces):
    result = 0
    for face in faces:
        a = vertices[face[0]]
        for index in range(1, len(face) - 1):
            b, c = (vertices[face[i]] for i in (index, index + 1))
            result += (
                sum(
                    x * y
                    for x, y in zip(
                        a, (b[1] * c[2] - b[2] * c[1], b[2] * c[0] - b[0] * c[2], b[0] * c[1] - b[1] * c[0])
                    )
                )
                / 6
            )
    return result


class OrganicDataTests(unittest.TestCase):
    def test_exact_cap_aware_preflight_triangle_budget_and_safe_pattern_identifiers(self):
        self.assertEqual([cup_triangle_budget(level) for level in (0, 1, 2)], [236, 880, 3520])
        for level in (0, 1, 2):
            value = patterned_plan()
            pattern = value["repeat_patterns"][0]
            pattern.update(name="P" * 48, count=3, rows=1)
            value["completion"]["inferred_regions"] = ["Arm", pattern["name"]]
            value["finish"]["subdivision"] = level
            validate_plan(value)
            exact = 3 * cup_triangle_budget(level)
            with self.assertRaisesRegex(ValueError, "generated_budget"):
                expand_patterns(value, _loft_sections, exact - 1, MAX_VERTICES)
            generated, _ = expand_patterns(value, _loft_sections, exact, MAX_VERTICES)
            self.assertEqual(len(generated), 3)
            self.assertTrue(all(len(r["name"].encode()) <= 55 for r in generated))
        for name in ("P" * 49, "吸盘", "Pattern Name"):
            value = patterned_plan()
            value["repeat_patterns"][0]["name"] = name
            with self.assertRaisesRegex(ValueError, "name_invalid"):
                validate_plan(value)

    def test_fixed_cup_is_closed_positive_and_has_open_concave_mouth(self):
        vertices, faces = cup_mesh([0, 0, 0], [0, 0, 1], [0, 1, 0], 0.05, 0.5)
        edges = Counter(tuple(sorted((a, b))) for face in faces for a, b in zip(face, face[1:] + face[:1]))
        self.assertTrue(all(n == 2 for n in edges.values()))
        self.assertGreater(volume(vertices, faces), 0)
        # Raised annular lip surrounds a lower cavity floor, not a bead/disk cap.
        self.assertGreater(max(v[2] for v in vertices), 0.025)
        inner = [v for v in vertices if math.hypot(v[0], v[1]) < 0.01]
        self.assertTrue(inner)
        self.assertLess(max(v[2] for v in inner), 0.5 * max(v[2] for v in vertices))
        self.assertGreater(min(v[2] for v in inner), 0.03 * 0.05)

    def test_rounded_cap_extends_endpoint_without_dropping_original_control_rings(self):
        shape = patterned_plan()["regions"][0]["surface"]
        rounded_v, rounded_f = _loft(shape, None, None)
        flat = copy.deepcopy(shape)
        flat.pop("end_caps")
        flat_v, flat_f = _loft(flat, None, None)
        self.assertEqual(rounded_v[: len(flat_v)], flat_v)
        self.assertGreater(len(rounded_f), len(flat_f))
        self.assertLess(min(p[1] for p in rounded_v), min(p[1] for p in flat_v))
        self.assertGreater(max(p[1] for p in rounded_v), max(p[1] for p in flat_v))
        null = copy.deepcopy(flat)
        null["end_caps"] = None
        self.assertEqual(_loft(null, None, None), (flat_v, flat_f))

    def test_patterns_preserve_source_and_use_matching_transported_frame(self):
        value = patterned_plan()
        before = copy.deepcopy(value)
        validate_plan(value)
        generated, receipt = expand_patterns(value, _loft_sections, MAX_TRIANGLES, MAX_VERTICES)
        self.assertEqual(value, before)
        self.assertEqual(len(generated), 16)
        self.assertEqual(receipt[0]["cups"], 16)
        self.assertTrue(
            all(
                r["role"] == "accessory" and volume(r["surface"]["vertices"], r["surface"]["faces"]) > 0
                for r in generated
            )
        )
        frames = transported_frames(_loft_sections(value["regions"][0]["surface"]["sections"]))
        self.assertTrue(all(abs(sum(a * b for a, b in zip(f["right"], f["tangent"]))) < 1e-12 for f in frames))
        self.assertGreater(min(p[2] for r in generated for p in r["surface"]["vertices"]), 0.07)

    def test_strict_caps_patterns_targets_and_budgets(self):
        for mutate in (
            lambda v: v["regions"][0]["surface"]["end_caps"].update(depth=True),
            lambda v: v["regions"][0]["surface"]["end_caps"].update(script="print(1)"),
            lambda v: v["repeat_patterns"][0].update(source_region="missing"),
            lambda v: v["repeat_patterns"][0].update(material="missing"),
            lambda v: v["repeat_patterns"][0].update(count=True),
            lambda v: v["repeat_patterns"][0].update(start=0.9, end=0.2),
            lambda v: v["repeat_patterns"][0].update(rows=2, row_spread_degrees=0),
            lambda v: v["repeat_patterns"][0].update(radius=float("inf")),
            lambda v: v["repeat_patterns"][0].update(name="Arm"),
            lambda v: v["completion"]["inferred_regions"].append("Cups_R1_C01"),
        ):
            value = patterned_plan()
            mutate(value)
            with self.assertRaises(ValueError):
                validate_plan(value)
        value = patterned_plan()
        value["repeat_patterns"] = [
            dict(value["repeat_patterns"][0], name="Pattern" + str(i), count=48, rows=2) for i in range(8)
        ]
        with self.assertRaisesRegex(ValueError, "budget"):
            validate_plan(value)
        value = patterned_plan()
        with self.assertRaisesRegex(ValueError, "generated_budget"):
            expand_patterns(value, _loft_sections, 10, 10)
        overlap = patterned_plan()
        overlap["repeat_patterns"].append(dict(overlap["repeat_patterns"][0], name="DuplicateCups"))
        with self.assertRaisesRegex(ValueError, "cup_overlap"):
            expand_patterns(overlap, _loft_sections, MAX_TRIANGLES, MAX_VERTICES)
        dense = patterned_plan()
        dense["repeat_patterns"][0].update(count=48, start=0.4, end=0.41)
        with self.assertRaisesRegex(ValueError, "cup_overlap"):
            expand_patterns(dense, _loft_sections, MAX_TRIANGLES, MAX_VERTICES)
        value["repeat_patterns"][0]["radius"] = 0.15
        with self.assertRaisesRegex(ValueError, "exceeds_source"):
            expand_patterns(value, _loft_sections, MAX_TRIANGLES, MAX_VERTICES)
        shape = surface()
        shape["end_caps"] = {"start": "rounded", "end": "flat", "depth": 1}
        with self.assertRaises(ValueError):
            validate_caps(shape)


@unittest.skipUnless(BLENDER.is_file(), "Set AINATIVE_TEST_BLENDER for actual closed cup tests")
class OrganicBlenderTests(unittest.TestCase):
    def setUp(self):
        self.runner = base_tests.BlenderTests(methodName="test_cage_and_explicit_closed_accessory_with_subdivision")
        self.runner.setUp()
        self.addCleanup(self.runner.doCleanups)

    def test_nonuniform_rotated_curved_loft_keeps_inverse_transpose_cup_normals_and_finite_world_geometry(self):
        import subprocess

        from test_sculpt_builder import BUILDER

        value = patterned_plan()
        shape = value["regions"][0]["surface"]
        shape.update(size=[1.3, 0.9, 0.7], position=[-0.1, 0.2, 0.3], rotation_degrees=[18, -24, 31])
        shape["sections"][1]["center"] = [0.1, 0.5, 0.12]
        shape["sections"][2]["center"] = [0.25, 1, 0.05]
        value["repeat_patterns"][0].update(count=5, radius=0.025, row_spread_degrees=55)
        result, _, receipt, log = self.runner.run_builder(value, name="transformed")
        self.assertEqual(result.returncode, 0, log)
        self.assertTrue(
            all(
                q["manifold"] and q["volume"] > 0 and all(math.isfinite(v) for v in q["bounds_min"] + q["bounds_max"])
                for q in receipt["geometry"]
            )
        )
        probe = self.runner.root / "normal_probe.py"
        probe.write_text(TRANSFORM_NORMAL_PROBE, encoding="utf8")
        result = subprocess.run(
            [
                str(BLENDER),
                "--background",
                "--factory-startup",
                "--disable-autoexec",
                "--python-exit-code",
                "1",
                "--python",
                str(probe),
                "--",
                str(BUILDER.parent),
                str(self.runner.root / "transformed.json"),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("TRANSFORMED_MOUTH_NORMAL_OK", result.stdout)

    def test_genuine_original_organic_plan_preserves_data_flat_caps_and_all_regions(self):
        import hashlib
        import json

        value = original_organic_plan()
        digest = hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
        self.assertEqual(digest, "55f09e20cf7e98b9862de56ea00ac483392e4c0ef1ee58c79a1bdedb76d47597")
        result, _, receipt, log = self.runner.run_builder(value, name="original_organic")
        self.assertEqual(result.returncode, 0, log)
        self.assertEqual(receipt["source_plan_sha256"], digest)
        self.assertEqual(receipt["regions"], 28)
        self.assertEqual(receipt["body_regions"], 12)
        self.assertEqual(receipt["parts"], 17)
        detail = receipt["organic_detail"]
        self.assertEqual(detail["generated_cups"], 0)
        self.assertEqual(detail["rounded_caps"], [])
        self.assertEqual(detail["pre_smoothed_loft_count"], 10)
        self.assertEqual(detail["loft_sampling"], dict(radial=32, samples_per_span=8, cap_latitude_rings=4))
        self.assertTrue(
            all(
                q["components"] == 1 and q["manifold"] and q["volume"] > 0 and q["degenerate_triangles"] == 0
                for q in receipt["geometry"]
            )
        )

    def test_long_declared_accessory_source_reference_maps_to_actual_object(self):
        value = patterned_plan()
        long_name = "LongSource" * 8
        value["regions"][0].update(name=long_name, role="accessory")
        value["regions"][0]["surface"]["position"] = [2, 0, 0]
        value["regions"].append(region("Body", surface()))
        value["repeat_patterns"][0].update(name="P" * 48, source_region=long_name, count=3, rows=1)
        value["completion"]["inferred_regions"] = ["Body", long_name, "P" * 48]
        validate_plan(value)
        result, _, receipt, log = self.runner.run_builder(value, name="long_source")
        self.assertEqual(result.returncode, 0, log)
        self.assertEqual(receipt["organic_detail"]["generated_cups"], 3)
        self.assertEqual(receipt["organic_detail"]["patterns"][0]["source_region"], long_name)
        self.assertEqual(len(receipt["organic_detail"]["surface_seating"]), 3)

    def test_actual_rounded_loft_and_sixteen_hollow_cups_are_closed_positive_components(self):
        value = patterned_plan()
        result, _, receipt, log = self.runner.run_builder(value)
        self.assertEqual(result.returncode, 0, log)
        self.assertEqual(receipt["parts"], 17)
        self.assertEqual(receipt["body_components"], 1)
        self.assertEqual(receipt["organic_detail"]["generated_cups"], 16)
        self.assertTrue(all(q["triangles"] == 880 for q in receipt["geometry"] if q["name"].startswith("Cups_")))
        self.assertNotEqual(receipt["source_plan_sha256"], receipt["expanded_plan_sha256"])
        self.assertTrue(
            all(
                q["components"] == 1 and q["manifold"] and q["volume"] > 0 and q["degenerate_triangles"] == 0
                for q in receipt["geometry"]
            )
        )


if __name__ == "__main__":
    unittest.main()
