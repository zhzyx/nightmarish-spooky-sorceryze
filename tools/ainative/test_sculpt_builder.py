"""Validate bounded sculpt data and real isolated Blender geometry, never online models."""

import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from sculpt_builder import (
    LOFT_STEPS,
    MAX_TRIANGLES,
    MAX_VERTICES,
    _canonical_body,
    _compile_character,
    _fitted_strap,
    _loft_sections,
    _section_outline,
    character_defaults,
    modeling_schema,
    resolve_age_blend,
    validate_plan,
)

SHOE_COVERAGE_PROBE = '"""Read-only forefoot-vs-closed-shoe probe; no source runtime imports."""\nimport hashlib\nimport json\nimport struct\nimport sys\nfrom pathlib import Path\n\nfrom mathutils import Vector\nfrom mathutils.bvhtree import BVHTree\n\nargs = sys.argv[sys.argv.index("--") + 1:]\nsource = Path(args[0])\ndata = source.read_bytes()\nsize = struct.unpack_from("<I", data, 12)[0]\ndocument = json.loads(data[20:20 + size])\nbinary = data[28 + size:]\n\n\ndef accessor(index):\n    a = document["accessors"][index]\n    view = document["bufferViews"][a["bufferView"]]\n    fmt, width = {5123: ("<H", 2), 5125: ("<I", 4), 5126: ("<fff", 12)}[a["componentType"]]\n    stride = view.get("byteStride", width)\n    start = view.get("byteOffset", 0) + a.get("byteOffset", 0)\n    values = [struct.unpack_from(fmt, binary, start + i * stride) for i in range(a["count"])]\n    return [v[0] for v in values] if width != 12 else values\n\n\ndef mesh(node):\n    assert not any(k in node for k in ("matrix", "translation", "rotation", "scale", "children"))\n    vertices, faces = [], []\n    for primitive in document["meshes"][node["mesh"]]["primitives"]:\n        assert primitive.get("mode", 4) == 4\n        offset = len(vertices)\n        vertices.extend(accessor(primitive["attributes"]["POSITION"]))\n        indices = accessor(primitive["indices"])\n        faces.extend(tuple(offset + n for n in indices[i:i + 3]) for i in range(0, len(indices), 3))\n    return vertices, faces\n\n\ndef inside(tree, point, tolerance):\n    nearest, normal, index, distance = tree.find_nearest(point)\n    if distance <= tolerance:\n        return True, distance\n    votes = 0\n    for raw in ((1, .3127, .1297), (-.233, 1, .117), (.137, -.293, 1)):\n        direction = Vector(raw).normalized()\n        origin = point.copy()\n        crossings = 0\n        for _ in range(128):\n            hit, _, _, _ = tree.ray_cast(origin, direction)\n            if hit is None:\n                break\n            crossings += 1\n            origin = hit + direction * 1e-6\n        else:\n            raise AssertionError("Ray did not terminate")\n        votes += crossings % 2\n    return votes >= 2, distance\n\n\nnodes = document["nodes"]\nbody_node = next(n for n in nodes if n.get("name", "").startswith("Reference "))\nbody, _ = mesh(body_node)\nheight = max(p[1] for p in body) - min(p[1] for p in body)\nreport = {"source_glb_sha256": hashlib.sha256(data).hexdigest(), "height": height, "foot_mask": "side-specific BODY Y < 0.065*height and Z >= foot_zmin + .55*foot_length; foot bounds use Y<.08*height; excludes heel/ankle opening", "tolerance_m": .0005 * height / 1.8, "feet": {}}\nfor side, label in ((-1, "L"), (1, "R")):\n    shoe, faces = mesh(next(n for n in nodes if n.get("name") == "Anatomy_Shoe" + label))\n    tree = BVHTree.FromPolygons(shoe, faces, all_triangles=True)\n    foot = [p for p in body if p[0] * side > 0 and p[1] < .08 * height]\n    zmin, zmax = min(p[2] for p in foot), max(p[2] for p in foot)\n    forefoot = [Vector(p) for p in foot if p[1] < .065 * height and p[2] >= zmin + .55 * (zmax - zmin)]\n    assert forefoot\n    outside = []\n    for point in forefoot:\n        covered, distance = inside(tree, point, report["tolerance_m"])\n        if not covered:\n            outside.append(distance)\n    report["feet"][label] = {"tested_body_vertices": len(forefoot), "outside_vertices": len(outside), "outside_ratio": len(outside) / len(forefoot), "maximum_outside_distance_m": max(outside, default=0)}\nassert all(foot["outside_vertices"] == 0 for foot in report["feet"].values()), report\nprint("SHOE_COVERAGE_OK", json.dumps(report))\n'

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "tools/ainative/sculpt_builder.py"
BLENDER = Path(os.environ.get("AINATIVE_TEST_BLENDER") or shutil.which("blender") or "__blender_unavailable__")


def surface(kind="ellipsoid", position=None, size=None, sections=None, vertices=None, faces=None):
    return dict(
        kind=kind,
        position=position or [0, 0.5, 0],
        rotation_degrees=[0, 0, 0],
        size=size or [1, 1, 1],
        sections=sections or [],
        vertices=vertices or [],
        faces=faces or [],
    )


def region(name="Body", shape=None, role="body", material="skin"):
    return dict(name=name, role=role, material=material, surface=shape or surface())


def plan():
    return dict(
        version=2,
        name="OrganicBody",
        materials=[dict(name="skin", color=[0.6, 0.35, 0.2, 1], roughness=0.75)],
        regions=[region()],
        finish=dict(voxel_size=0.06, smooth_iterations=2, subdivision=0),
        completion=dict(mode="plausible", inferred_regions=["Body"]),
    )


def section(center, radius):
    return dict(center=center, radius=radius, roll=0)


def branch_plan():
    value = plan()
    value["regions"] = [
        region(
            "Torso",
            surface(
                "loft",
                position=[0, 0, 0],
                sections=[
                    section([0, 0.3, 0], [0.22, 0.22, 0.16, 0.2]),
                    section([0, 0.8, 0], [0.32, 0.32, 0.2, 0.23]),
                    section([0, 1.1, 0], [0.25, 0.25, 0.16, 0.18]),
                ],
            ),
        ),
        region(
            "LeftBranch",
            surface(
                "loft",
                position=[0, 0, 0],
                sections=[
                    section([-0.17, 0.95, 0], [0.16] * 4),
                    section([-0.5, 0.85, 0.06], [0.13] * 4),
                    section([-0.8, 0.6, 0.16], [0.08] * 4),
                ],
            ),
        ),
        region(
            "RightBranch",
            surface(
                "loft",
                position=[0, 0, 0],
                sections=[
                    section([0.17, 0.95, 0], [0.16] * 4),
                    section([0.5, 0.85, 0.06], [0.13] * 4),
                    section([0.8, 0.6, 0.16], [0.08] * 4),
                ],
            ),
        ),
    ]
    value["finish"]["voxel_size"] = 0.035
    value["completion"]["inferred_regions"] = ["Torso", "LeftBranch", "RightBranch"]
    return value


def cage_surface():
    return surface(
        "cage",
        vertices=[
            [-0.5, -0.5, -0.5],
            [0.5, -0.5, -0.5],
            [0.5, 0.5, -0.5],
            [-0.5, 0.5, -0.5],
            [-0.5, -0.5, 0.5],
            [0.5, -0.5, 0.5],
            [0.5, 0.5, 0.5],
            [-0.5, 0.5, 0.5],
        ],
        faces=[[0, 1, 2, 3], [4, 7, 6, 5], [0, 4, 5, 1], [1, 5, 6, 2], [2, 6, 7, 3], [4, 0, 3, 7]],
    )


def reference_h1_plan():
    """Exact data from a genuine failed two-view plan; no model call or mesh fixture."""
    value = plan()
    character = character_defaults()
    character.update(
        accent_color=[0.46, 0.46, 0.45, 1],
        age="elder",
        belt_height=0.6,
        build=0.43,
        cloth_color=[0.5, 0.5, 0.49, 1],
        clothing="robe_belt",
        footwear="sandals",
        hair="bald",
        hair_color=[0.45, 0.45, 0.45, 1],
        hand_scale=1.02,
        head_depth=1.08,
        head_ratio=7.15,
        head_width=0.96,
        height=1.8,
        hem_height=0.45,
        hip_width=1.0,
        lapel_width=1.08,
        limb_length=1.0,
        neck_length=0.88,
        pose="A",
        shoulder_width=1.04,
        skin_color=[0.53, 0.53, 0.52, 1],
        sleeve_length=0.76,
        style="realistic",
        trouser_width=1.28,
    )
    character["face"].update(
        cheek_fullness=0.72,
        chin_length=1.12,
        ear_size=1.18,
        eye_size=0.8,
        eye_spacing=1.02,
        jaw_width=0.88,
        lip_fullness=0.7,
        mouth_width=1.04,
        nose_length=1.16,
        nose_width=1.04,
    )
    value.update(
        name="Reference elderly bald man in short belted wrap jacket",
        character=character,
        materials=[],
        regions=[],
        finish=dict(smooth_iterations=2, subdivision=1, voxel_size=0.004),
        completion=dict(inferred_regions=["character"], mode="reference_constrained"),
    )
    return value


def reference_photo_plan():
    """Exact immutable real photographic CLI plan, data only; no private path dependency."""
    return json.loads(
        '{"character":{"accent_color":[0.08,0.08,0.085,1],"age":"mature","belt_height":0.515,"build":0.5,"cloth_color":[0.035,0.045,0.105,1],"clothing":"tshirt_trousers","face":{"cheek_fullness":1.02,"chin_length":1.02,"ear_size":1.03,"eye_size":0.95,"eye_spacing":1.0,"jaw_width":0.98,"lip_fullness":0.87,"mouth_width":1.0,"nose_length":1.08,"nose_width":1.0},"footwear":"shoes","footwear_color":[0.045,0.043,0.04,1],"hair":"short","hair_color":[0.075,0.055,0.04,1],"hand_scale":1.0,"head_depth":1.04,"head_ratio":7.7,"head_width":0.97,"height":1.8,"hem_height":0.52,"hip_width":1.0,"lapel_width":0.6,"limb_length":1.0,"neck_length":0.94,"pose":"A","shoulder_width":1.03,"skin_color":[0.64,0.445,0.33,1],"sleeve_length":0.3802,"style":"realistic","trouser_color":[0.48,0.47,0.445,1],"trouser_width":1.08},"completion":{"inferred_regions":["character"],"mode":"reference_constrained"},"finish":{"smooth_iterations":2,"subdivision":2,"voxel_size":0.005},"materials":[],"name":"Reference man in navy T-shirt and gray trousers","regions":[],"version":2}'
    )


class ValidationTests(unittest.TestCase):
    def test_full_outfit_coverage_and_style_specific_eye_domain_preserve_plan(self):
        value = plan()
        value.update(materials=[], regions=[], character=character_defaults("stylized"))
        value["character"].update(hem_height=0.602, belt_height=0.602)
        value["completion"]["inferred_regions"] = ["character"]
        original = json.dumps(value, sort_keys=True)
        expanded, _ = _compile_character(validate_plan(value))
        shirt = next(r["surface"] for r in expanded["regions"] if r["name"] == "Anatomy_shirt")
        trousers = next(r["surface"] for r in expanded["regions"] if r["name"] == "Anatomy_trousers")
        self.assertGreater(
            max(v[1] for v in trousers["vertices"]), value["character"]["hem_height"] * value["character"]["height"]
        )
        self.assertLess(min(v[1] for v in shirt["vertices"]), max(v[1] for v in trousers["vertices"]))
        self.assertEqual(json.dumps(value, sort_keys=True), original)
        value["character"]["face"]["eye_size"] = 1.6
        validate_plan(value)
        value["character"]["style"] = "realistic"
        with self.assertRaisesRegex(ValueError, "realistic_eye_size"):
            validate_plan(value)
        value["character"]["style"] = "stylized"
        value["character"]["detail"] = {"smile": 0.7, "brow_raise": 0.2}
        validate_plan(value)
        value["character"]["detail"]["script"] = "bad"
        with self.assertRaisesRegex(ValueError, "detail"):
            validate_plan(value)

    def test_optional_age_blend_is_bounded_preserves_input_and_overrides_enum(self):
        value = reference_h1_plan()
        original = json.dumps(value, sort_keys=True)
        self.assertEqual(resolve_age_blend(value["character"]), 0.65)
        validate_plan(value)
        self.assertEqual(json.dumps(value, sort_keys=True), original)
        for age in (None, 0.0, 0.4, 1.0):
            candidate = json.loads(original)
            candidate["character"]["age_blend"] = age
            before = json.dumps(candidate, sort_keys=True)
            validate_plan(candidate)
            self.assertEqual(resolve_age_blend(candidate["character"]), 0.65 if age is None else age)
            self.assertEqual(json.dumps(candidate, sort_keys=True), before)
        for age in (-0.01, 1.01, True, "elder", float("nan")):
            candidate = json.loads(original)
            candidate["character"]["age_blend"] = age
            with self.assertRaises(ValueError):
                validate_plan(candidate)
        young = json.loads(original)
        young["character"]["age_blend"] = 0
        old = json.loads(original)
        old["character"]["age_blend"] = 1
        young_vertices = _canonical_body(young["character"])["vertices"]
        old_vertices = _canonical_body(old["character"])["vertices"]
        self.assertGreater(max(math.dist(a, b) for a, b in zip(young_vertices, old_vertices)), 0.015)

    def test_optional_independent_colors_preserve_input_and_fallback(self):
        original = reference_h1_plan()
        cases = [
            ({}, original["character"]["cloth_color"], original["character"]["accent_color"]),
            (
                {"trouser_color": None, "footwear_color": None},
                original["character"]["cloth_color"],
                original["character"]["accent_color"],
            ),
            (
                {"trouser_color": [0.7, 0.6, 0.5, 1], "footwear_color": [0.03, 0.04, 0.05, 1]},
                [0.7, 0.6, 0.5, 1],
                [0.03, 0.04, 0.05, 1],
            ),
        ]
        for additions, pants, shoes in cases:
            value = json.loads(json.dumps(original))
            value["character"].update(additions)
            before = json.dumps(value, sort_keys=True)
            validated = validate_plan(value)
            self.assertEqual(validated, value)
            expanded, _ = _compile_character(validated)
            materials = {entry["name"]: entry["color"] for entry in expanded["materials"]}
            self.assertEqual(materials["AnatomyCloth"], value["character"]["cloth_color"])
            self.assertEqual(materials["AnatomyTrouserCloth"], pants)
            self.assertEqual(materials["AnatomyFootwear"], shoes)
            self.assertEqual(json.dumps(value, sort_keys=True), before)
        for invalid in (True, "navy", [0, 0, 0], [0, 0, 0, 2], [0, 0, float("nan"), 1]):
            value = json.loads(json.dumps(original))
            value["character"]["trouser_color"] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_plan(value)

    def test_measured_section_rays_handle_vertices_coplanar_caps_and_reject_missing_sections(self):
        shape = cage_surface()
        for y in (-0.5, 0, 0.5):
            radii = _section_outline(shape["vertices"], shape["faces"], y, (0, 0), 1)
            self.assertEqual(len(radii), 64)
            for index, radius in enumerate(radii):
                angle = 2 * math.pi * index / 64
                self.assertAlmostEqual(radius, 0.5 / max(abs(math.cos(angle)), abs(math.sin(angle))), places=7)
        with self.assertRaises(ValueError):
            _section_outline(shape["vertices"], shape["faces"], 0, (2, 0), 1)
        vertices, faces = _fitted_strap(shape["vertices"], shape["faces"], -0.1, 0.1, (0, 0), 1)
        self.assertEqual((len(vertices), len(faces)), (256, 256))
        edges = {}
        for face in faces:
            for a, b in zip(face, face[1:] + face[:1]):
                edge = tuple(sorted((a, b)))
                edges[edge] = edges.get(edge, 0) + 1
        self.assertTrue(all(count == 2 for count in edges.values()))
        for point in vertices[:64]:
            self.assertGreaterEqual(math.hypot(max(0, abs(point[0]) - 0.5), max(0, abs(point[2]) - 0.5)), 0.007)

    def test_canonical_body_controls_preserve_topology_height_head_ratio_and_straight_a_pose(self):
        from anatomy_body import BODY_FACES, BODY_VERTICES

        for height, ratio, limb in [(1.8, 7.15, 1), (0.8, 5, 0.85), (2.4, 8.5, 1.15)]:
            c = character_defaults()
            c.update(height=height, head_ratio=ratio, limb_length=limb)
            body = _canonical_body(c)
            self.assertEqual(len(body["vertices"]), len(BODY_VERTICES))
            self.assertEqual(body["faces"], list(BODY_FACES))
            maximum = max(point[1] for point in body["vertices"])
            minimum = min(point[1] for point in body["vertices"])
            self.assertAlmostEqual(minimum, 0, places=7)
            self.assertAlmostEqual(maximum, height, places=7)
            self.assertAlmostEqual(height / (maximum - body["landmarks"]["chin"][1]), ratio, places=6)
            for side in ("L", "R"):
                shoulder, elbow, wrist = (body["landmarks"][key + side] for key in ("shoulder", "elbow", "wrist"))
                for a, b in ((shoulder, elbow), (elbow, wrist)):
                    delta = [b[i] - a[i] for i in range(3)]
                    length = sum(value * value for value in delta) ** 0.5
                    self.assertAlmostEqual(delta[2], 0, places=7)
                    self.assertAlmostEqual(abs(delta[0]) / length, 0.42261826174069944, places=6)

    def test_loft_interpolation_preserves_controls_and_positive_radii(self):
        controls = branch_plan()["regions"][1]["surface"]["sections"]
        samples = _loft_sections(controls)
        self.assertEqual(len(samples), (len(controls) - 1) * LOFT_STEPS + 1)
        self.assertEqual(samples[::LOFT_STEPS], controls)
        for index, sample in enumerate(samples[:-1]):
            span = index // LOFT_STEPS
            for channel, radius in enumerate(sample["radius"]):
                lower, upper = sorted((controls[span]["radius"][channel], controls[span + 1]["radius"][channel]))
                self.assertGreaterEqual(radius, lower)
                self.assertLessEqual(radius, upper)

    def test_character_is_strict_data_with_reserved_completion_root(self):
        value = plan()
        value.update(character=character_defaults(), materials=[], regions=[])
        value["completion"]["inferred_regions"] = ["character"]
        self.assertEqual(validate_plan(value), value)
        for key, invalid in [("height", True), ("head_ratio", 99), ("script", "pass")]:
            candidate = json.loads(json.dumps(value))
            candidate["character"][key] = invalid
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_plan(candidate)
        value["completion"]["inferred_regions"] = ["Anatomy_FingerL0"]
        with self.assertRaises(ValueError):
            validate_plan(value)

    def test_schema_closed_boundaries(self):
        schema = modeling_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["properties"]["regions"]["items"]["additionalProperties"])
        self.assertFalse(schema["properties"]["regions"]["items"]["properties"]["surface"]["additionalProperties"])

    def test_accepts_six_surface_kinds_and_independent_copy(self):
        for kind in ["box", "ellipsoid", "capsule", "cylinder"]:
            value = plan()
            value["regions"][0]["surface"]["kind"] = kind
            self.assertEqual(validate_plan(value), value)
        self.assertEqual(validate_plan(branch_plan()), branch_plan())
        value = plan()
        value["regions"][0]["surface"] = cage_surface()
        validated = validate_plan(value)
        validated["regions"].clear()
        self.assertEqual(len(value["regions"]), 1)

    def test_rejects_executable_fields_and_unknown_kinds(self):
        for level in ["plan", "region", "surface"]:
            value = plan()
            target = (
                value
                if level == "plan"
                else value["regions"][0]
                if level == "region"
                else value["regions"][0]["surface"]
            )
            target["script"] = "import os"
            with self.subTest(level=level), self.assertRaises(ValueError):
                validate_plan(value)
        value = plan()
        value["regions"][0]["surface"]["kind"] = "python"
        with self.assertRaises(ValueError):
            validate_plan(value)

    def test_rejects_names_unknown_materials_and_inferred_regions(self):
        for name in ["../bad", "a/b", "bad\nname", " leading", "trailing ", "", "x" * 81]:
            value = plan()
            value["name"] = name
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_plan(value)
        value = plan()
        value["regions"][0]["material"] = "unknown"
        with self.assertRaises(ValueError):
            validate_plan(value)
        value = plan()
        value["completion"]["inferred_regions"] = ["not-a-region"]
        with self.assertRaises(ValueError):
            validate_plan(value)

    def test_rejects_nonfinite_boolean_and_unbounded_values(self):
        for number in [True, float("nan"), float("inf"), 10**400, -101]:
            value = plan()
            value["regions"][0]["surface"]["position"][0] = number
            with self.subTest(number=number), self.assertRaises(ValueError):
                validate_plan(value)
        value = plan()
        value["finish"]["subdivision"] = True
        with self.assertRaises(ValueError):
            validate_plan(value)

    def test_rejects_invalid_cage_indices_open_surface_and_unused_arrays(self):
        for face in [[0, 1, 99], [0, 1, True], [0, 0, 2]]:
            value = plan()
            value["regions"][0]["surface"] = cage_surface()
            value["regions"][0]["surface"]["faces"][0] = face
            with self.subTest(face=face), self.assertRaises(ValueError):
                validate_plan(value)
        value = plan()
        value["regions"][0]["surface"] = cage_surface()
        value["regions"][0]["surface"]["faces"].pop()
        with self.assertRaises(ValueError):
            validate_plan(value)
        value = plan()
        value["regions"][0]["surface"]["vertices"] = [[0, 0, 0]]
        with self.assertRaises(ValueError):
            validate_plan(value)

    def test_rejects_empty_body_and_zero_length_loft_path(self):
        value = plan()
        value["regions"][0]["role"] = "accessory"
        with self.assertRaises(ValueError):
            validate_plan(value)
        value = branch_plan()
        value["regions"][0]["surface"]["sections"][1]["center"] = value["regions"][0]["surface"]["sections"][0][
            "center"
        ]
        with self.assertRaises(ValueError):
            validate_plan(value)

    def test_rejects_pinched_vertex_even_when_every_edge_has_two_faces(self):
        value = plan()
        shape = cage_surface()
        shape["vertices"] = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [-1, 0, 0], [0, -1, 0], [0, 0, -1]]
        shape["faces"] = [[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3], [0, 5, 4], [0, 4, 6], [0, 6, 5], [4, 5, 6]]
        value["regions"][0]["surface"] = shape
        with self.assertRaisesRegex(ValueError, "cage_nonmanifold_vertex"):
            validate_plan(value)


@unittest.skipUnless(BLENDER.is_file(), "Set AINATIVE_TEST_BLENDER or install Blender on PATH for real geometry checks")
class BlenderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="sculpt-builder-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def run_builder(self, value, name="result", renders=False):
        source = self.root / (name + ".json")
        source.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")
        output = self.root / (name + ".glb")
        arguments = [
            str(BLENDER),
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "--python-exit-code",
            "1",
            "--python",
            str(BUILDER),
            "--",
            str(source),
            str(output),
        ]
        if renders:
            arguments.append("--renders")
        result = subprocess.run(
            arguments, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180
        )
        log = result.stdout + result.stderr
        receipt = (
            json.loads(Path(str(output) + ".receipt.json").read_text(encoding="utf-8"))
            if Path(str(output) + ".receipt.json").is_file()
            else None
        )
        return result, output, receipt, log

    def test_exact_two_reference_parameters_use_continuous_body_and_closed_cloth(self):
        value = reference_h1_plan()
        canonical = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        self.assertEqual(
            hashlib.sha256(canonical).hexdigest(), "6649c944b6c82a7d3db800078248f5d56949d173e8e6da862f4bb3e0d639fdce"
        )
        result, output, receipt, log = self.run_builder(value)
        self.assertEqual(result.returncode, 0, log)
        self.assertEqual(receipt["body_components"], 1)
        self.assertTrue(receipt["body_manifold"])
        self.assertTrue(all(q["degenerate_triangles"] == 0 for q in receipt["geometry"]))
        self.assertLessEqual(receipt["triangles"], MAX_TRIANGLES)
        self.assertLessEqual(receipt["vertices"], MAX_VERTICES)
        self.assertLess(output.stat().st_size, 64 * 1024 * 1024)
        for fill in receipt["internal_voxel_fills"]:
            self.assertLess(fill["signed_volume"], 0)
            self.assertLessEqual(abs(fill["signed_volume"]), fill["volume_limit"])
            self.assertEqual(fill["contained_points"], fill["vertices"] + 1)
            self.assertEqual(fill["containment_passes"], fill["contained_points"] * 3)
            self.assertFalse(fill["outer_skin_modified"])
        self.assertEqual(receipt["internal_voxel_fills"], [])
        operator = receipt["character_operator"]
        self.assertEqual(operator["surface_implementation"], "continuous_cc0_body_v1")
        self.assertFalse(operator["voxel_remesh_applied"])
        self.assertIsNone(operator["effective_core_voxel_size"])
        self.assertEqual(operator["requested_voxel_size"], value["finish"]["voxel_size"])
        self.assertEqual(operator["requested_subdivision"], 1)
        self.assertEqual(operator["effective_body_subdivision"], 1)
        self.assertEqual(receipt["source_plan_sha256"], hashlib.sha256(canonical).hexdigest())
        names = {q["name"] for q in receipt["geometry"]}
        for name in (
            "Anatomy_Belt",
            "Anatomy_WrapPanel",
            "Anatomy_WrapInner",
            "Anatomy_RolledCuffL",
            "Anatomy_RolledCuffR",
        ):
            self.assertIn(name, names)
        self.assertIsNone(operator["requested_age_blend"])
        self.assertEqual(operator["effective_age_blend"], 0.65)

    def test_exact_photographic_controls_keep_connected_trouser_seat_independent_colors_and_closed_shoes(self):
        import struct

        value = reference_photo_plan()
        canonical = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        self.assertEqual(
            hashlib.sha256(canonical).hexdigest(), "107c3a5b44e18aadf87e90cccbb0f197092f003f33040f51e2d8c062a2b75f15"
        )
        result, output, receipt, log = self.run_builder(value, name="photo")
        self.assertEqual(result.returncode, 0, log)
        self.assertEqual(receipt["source_plan_sha256"], hashlib.sha256(canonical).hexdigest())
        self.assertEqual(receipt["body_components"], 1)
        self.assertTrue(receipt["body_manifold"])
        trousers = next(q for q in receipt["geometry"] if q["name"] == "Anatomy_trousers")
        self.assertEqual(trousers["components"], 1)
        self.assertTrue(
            all(
                q["manifold"] and q["components"] == 1 and q["volume"] > 0 and q["degenerate_triangles"] == 0
                for q in receipt["geometry"]
            )
        )
        data = output.read_bytes()
        length = struct.unpack_from("<I", data, 12)[0]
        document = json.loads(data[20 : 20 + length])
        colors = {
            material["name"]: material["pbrMetallicRoughness"]["baseColorFactor"] for material in document["materials"]
        }
        for actual, expected in zip(colors["AnatomyCloth"], value["character"]["cloth_color"]):
            self.assertAlmostEqual(actual, expected, places=6)
        for actual, expected in zip(colors["AnatomyTrouserCloth"], value["character"]["trouser_color"]):
            self.assertAlmostEqual(actual, expected, places=6)
        for actual, expected in zip(colors["AnatomyFootwear"], value["character"]["footwear_color"]):
            self.assertAlmostEqual(actual, expected, places=6)
        probe = self.root / "probe.py"
        probe.write_text(SHOE_COVERAGE_PROBE, encoding="utf8")
        checked = subprocess.run(
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
                str(output),
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        self.assertIn("SHOE_COVERAGE_OK", checked.stdout)

    def test_explicit_age_blend_is_truthfully_measured_without_source_normalization(self):
        value = reference_h1_plan()
        value["character"]["age_blend"] = 1.0
        result, _, receipt, log = self.run_builder(value, name="explicit_age")
        self.assertEqual(result.returncode, 0, log)
        self.assertEqual(receipt["character_operator"]["requested_age_blend"], 1)
        self.assertEqual(receipt["character_operator"]["effective_age_blend"], 1)
        self.assertEqual(receipt["character_operator"]["anatomy_age_weight"], 1)
        canonical = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        self.assertEqual(receipt["source_plan_sha256"], hashlib.sha256(canonical).hexdigest())

    def test_coverall_wavy_hair_expression_and_trim_are_closed_without_midriff(self):
        value = plan()
        value.update(materials=[], regions=[], character=character_defaults("stylized"))
        value["character"].update(
            clothing="coverall",
            hair="short_wavy",
            hem_height=0.602,
            belt_height=0.602,
            detail=dict(
                cloth_ease=0.25,
                fold_amplitude=0.2,
                hair_volume=0.75,
                hair_sweep=0.45,
                smile=0.75,
                brow_raise=0.25,
                forehead_height=-0.25,
                pocket_size=0.5,
            ),
        )
        value["character"]["face"]["eye_size"] = 1.5
        value["completion"]["inferred_regions"] = ["character"]
        value["finish"].update(subdivision=1, smooth_iterations=2)
        result, _, receipt, log = self.run_builder(value, name="coverall")
        self.assertEqual(result.returncode, 0, log)
        self.assertTrue(
            all(
                q["components"] == 1 and q["manifold"] and q["volume"] > 0 and q["degenerate_triangles"] == 0
                for q in receipt["geometry"]
            )
        )
        names = {q["name"] for q in receipt["geometry"]}
        self.assertIn("Anatomy_coverall", names)
        self.assertNotIn("Anatomy_shirt", names)
        self.assertNotIn("Anatomy_trousers", names)
        for name in (
            "Anatomy_Hair",
            "Anatomy_WorkCollarL",
            "Anatomy_WorkCollarR",
            "Anatomy_WorkPlacket",
            "Anatomy_CoverallWaist",
            "Anatomy_PocketPanelL",
            "Anatomy_PocketPanelR",
        ):
            self.assertIn(name, names)
        self.assertEqual(receipt["character_operator"]["garment_coverage"], "single_connected_coverall")
        self.assertEqual(receipt["character_operator"]["effective_detail"]["smile"], 0.75)
        for name in ("character_detail_sha256", "organic_detail_sha256"):
            self.assertEqual(len(receipt["runtime_input_sha256"][name]), 64)

    def test_character_does_not_remove_disconnected_external_body(self):
        value = plan()
        value["character"] = character_defaults()
        value["regions"] = [region("External", surface(position=[4, 0, 0]))]
        value["completion"]["inferred_regions"] = ["character", "External"]
        result, output, receipt, log = self.run_builder(value)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("body_disconnected", log)
        self.assertFalse(output.exists())
        self.assertIsNone(receipt)

    def test_internal_fill_requires_negative_volume_and_three_direction_containment(self):
        driver = self.root / "certify.py"
        driver.write_text(
            """import sys
import bpy,bmesh
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
sys.path.insert(0,sys.argv[-1])
from sculpt_builder import _fill_certified_internal_voxel_shells,_quality
for negative,external in [(True,False),(False,False),(True,True)]:
    bm=bmesh.new();bmesh.ops.create_cube(bm,size=1)
    before=set(bm.faces)
    bmesh.ops.create_cube(bm,size=.01,matrix=Matrix.Translation((2,0,0) if external else (0,0,0)))
    if negative:bmesh.ops.reverse_faces(bm,faces=list(set(bm.faces)-before))
    mesh=bpy.data.meshes.new('certificate');bm.to_mesh(mesh);bm.free()
    obj=bpy.data.objects.new('certificate',mesh)
    outer=sorted(tuple(vertex.co) for vertex in mesh.vertices if max(abs(value) for value in vertex.co)>.4 and max(abs(value) for value in vertex.co)<1)
    try:
        fills=_fill_certified_internal_voxel_shells(obj,.1,bmesh,Vector,BVHTree)
    except ValueError:
        assert not negative or external
    else:
        assert negative and not external and len(fills)==1
        assert fills[0]['signed_volume']<0 and fills[0]['containment_passes']==27
        assert sorted(tuple(vertex.co) for vertex in mesh.vertices)==outer
        assert _quality(obj,bmesh)['components']==1
print('CERTIFIED_FILL_BOUNDARIES_OK')
""",
            encoding="utf8",
        )
        result = subprocess.run(
            [
                str(BLENDER),
                "--background",
                "--factory-startup",
                "--disable-autoexec",
                "--python-exit-code",
                "1",
                "--python",
                str(driver),
                "--",
                str(BUILDER.parent),
            ],
            capture_output=True,
            text=True,
            encoding="utf8",
            errors="replace",
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CERTIFIED_FILL_BOUNDARIES_OK", result.stdout)

    def test_reserved_quad_diagonals_use_interior_refinement_without_dropping_boundary(self):
        driver = self.root / "triangulate.py"
        driver.write_text(
            """import sys,bmesh
sys.path.insert(0,sys.argv[-1])
from sculpt_builder import _triangulate_surface
bm=bmesh.new()
vertices=[bm.verts.new(point) for point in [(0,0,0),(1,0,0),(1,1,0),(0,1,0),(.5,.5,-1),(.5,.5,1)]]
bm.faces.new([vertices[i] for i in [0,1,2,3]])
bm.faces.new([vertices[i] for i in [0,2,4]])
bm.faces.new([vertices[i] for i in [1,3,5]])
triangles,materials=_triangulate_surface(bm)
assert len(bm.verts)==7 and len(triangles)==6 and len(materials)==6
edges={}
for triangle in triangles:
    for a,b in zip(triangle,triangle[1:]+triangle[:1]):
        edge=tuple(sorted((a,b)));edges[edge]=edges.get(edge,0)+1
for edge in [(0,1),(1,2),(2,3),(0,3)]:assert edges[edge]==1
assert edges[(0,2)]==1 and edges[(1,3)]==1
assert set(range(7))=={index for triangle in triangles for index in triangle}
assert tuple(bm.verts[6].co)==(.5,.5,0)
print('SURFACE_BOUNDARY_REFINEMENT_OK')
""",
            encoding="utf8",
        )
        result = subprocess.run(
            [
                str(BLENDER),
                "--background",
                "--factory-startup",
                "--disable-autoexec",
                "--python-exit-code",
                "1",
                "--python",
                str(driver),
                "--",
                str(BUILDER.parent),
            ],
            capture_output=True,
            text=True,
            encoding="utf8",
            errors="replace",
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SURFACE_BOUNDARY_REFINEMENT_OK", result.stdout)

    def test_character_scale_and_proportion_boundaries_keep_one_closed_body(self):
        for label, height, ratio, width, neck, limb in [
            ("small", 0.8, 5, 0.75, 1.25, 0.85),
            ("large", 2.4, 8.5, 1.25, 0.75, 1.15),
        ]:
            value = plan()
            value.update(
                materials=[], regions=[], character=character_defaults("stylized" if label == "small" else "realistic")
            )
            value["character"].update(
                height=height,
                head_ratio=ratio,
                shoulder_width=width,
                hip_width=width,
                neck_length=neck,
                limb_length=limb,
                hair="bald",
            )
            value["finish"].update(voxel_size=0.02, smooth_iterations=2)
            value["completion"]["inferred_regions"] = ["character"]
            result, _, receipt, log = self.run_builder(value, name=label)
            self.assertEqual(result.returncode, 0, log)
            self.assertEqual(receipt["body_components"], 1)
            self.assertTrue(receipt["body_manifold"])
            self.assertTrue(all(q["degenerate_triangles"] == 0 for q in receipt["geometry"]))

    def test_parametric_character_and_aged_wrap_clothes_are_closed_data_driven_surfaces(self):
        for label in ("adult", "elder", "stylized_width08"):
            value = plan()
            value.update(materials=[], regions=[], character=character_defaults())
            if label == "stylized_width08":
                value["character"] = character_defaults("stylized")
                value["character"]["trouser_width"] = 0.8
            value["finish"].update(voxel_size=0.008, smooth_iterations=2)
            value["completion"]["inferred_regions"] = ["character"]
            if label == "elder":
                value["character"].update(
                    age="elder",
                    hair="bald",
                    head_ratio=7.1,
                    clothing="robe_belt",
                    hem_height=0.44,
                    sleeve_length=0.75,
                    trouser_width=1.25,
                    footwear="sandals",
                    belt_height=0.58,
                )
                value["character"]["face"].update(jaw_width=0.9, cheek_fullness=0.8, nose_length=1.05)
            result, output, receipt, log = self.run_builder(value, name=label)
            self.assertEqual(result.returncode, 0, log)
            self.assertEqual(receipt["body_components"], 1)
            self.assertTrue(receipt["body_manifold"])
            self.assertTrue(
                all(
                    q["manifold"] and q["components"] == 1 and q["degenerate_triangles"] == 0 and q["volume"] > 0
                    for q in receipt["geometry"]
                )
            )
            self.assertLessEqual(receipt["triangles"], 500000)
            operator = receipt["character_operator"]
            self.assertFalse(operator["neural_weights_loaded"])
            self.assertFalse(operator["source_reference_mesh_imported"])
            self.assertFalse(operator["trusted_anatomy_base_used"])
            self.assertTrue(operator["trusted_anatomy_body_used"])
            self.assertEqual(len(operator["anatomy_base_sha256"]), 64)
            self.assertEqual(len(operator["framing_landmarks_not_visual_acceptance"]["digit_tips_L"]), 5)
            self.assertEqual(len(operator["framing_landmarks_not_visual_acceptance"]["digit_tips_R"]), 5)
            self.assertNotEqual(operator["expanded_plan_sha256"], receipt["source_plan_sha256"])
            self.assertEqual(receipt["sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
            names = {q["name"] for q in receipt["geometry"]}
            self.assertIn("Anatomy_shirt", names)
            self.assertIn("Anatomy_trousers", names)
            if label == "elder":
                self.assertIn("Anatomy_SandalSoleL", names)
            if label != "elder":
                self.assertIn("Anatomy_Hair", names)

    def test_connected_branches_fuse_to_one_manifold_body_and_complete_back(self):
        value = branch_plan()
        result, output, receipt, log = self.run_builder(value)
        self.assertEqual(result.returncode, 0, log)
        self.assertIn("MALIANG_SCULPT_BUILD_OK", log)
        self.assertEqual(receipt["regions"], 3)
        self.assertEqual(receipt["parts"], 1)
        self.assertEqual(receipt["body_components"], 1)
        self.assertTrue(receipt["body_manifold"])
        self.assertGreater(receipt["body_volume"], 0)
        self.assertGreater(receipt["vertices"], 100)
        self.assertEqual(receipt["geometry"][0]["degenerate_triangles"], 0)
        self.assertLess(receipt["geometry"][0]["bounds_min"][2], -0.1)
        self.assertGreater(receipt["geometry"][0]["bounds_max"][2], 0.1)
        self.assertLessEqual(receipt["triangles"], 250000)
        self.assertEqual(receipt["sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
        canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        self.assertEqual(receipt["source_plan_sha256"], hashlib.sha256(canonical.encode()).hexdigest())
        self.assertEqual(receipt["completion"], value["completion"])
        self.assertNotIn(str(self.root), json.dumps(receipt))

    def test_cage_and_explicit_closed_accessory_with_subdivision(self):
        value = plan()
        value["regions"][0]["surface"] = cage_surface()
        value["regions"].append(region("RingDetail", surface("capsule", [0, 1.3, 0], [0.2, 0.3, 0.2]), "accessory"))
        value["finish"].update(voxel_size=0.1, subdivision=1)
        result, output, receipt, log = self.run_builder(value)
        self.assertEqual(result.returncode, 0, log)
        self.assertEqual(receipt["parts"], 2)
        self.assertEqual(receipt["accessories"], 1)
        self.assertTrue(all(q["manifold"] and q["components"] == 1 and q["volume"] > 0 for q in receipt["geometry"]))

    def test_disconnected_body_is_not_silently_dropped(self):
        value = plan()
        value["regions"].append(region("DetachedBody", surface(position=[4, 0.5, 0])))
        result, output, receipt, log = self.run_builder(value)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("body_disconnected", log)
        self.assertFalse(output.exists())
        self.assertIsNone(receipt)

    def test_voxel_budget_is_checked_before_expensive_fusion(self):
        value = plan()
        value["regions"][0]["surface"]["size"] = [20, 20, 20]
        value["finish"]["voxel_size"] = 0.003
        result, output, receipt, log = self.run_builder(value)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("voxel_budget_exceeded", log)
        self.assertFalse(output.exists())
        self.assertIsNone(receipt)

    def test_output_is_not_overwritten(self):
        result, output, receipt, log = self.run_builder(plan())
        self.assertEqual(result.returncode, 0, log)
        before = output.read_bytes()
        repeated, _, _, repeated_log = self.run_builder(plan())
        self.assertNotEqual(repeated.returncode, 0)
        self.assertIn("output_exists", repeated_log)
        self.assertEqual(output.read_bytes(), before)

    def test_fixed_multiview_renders_are_created_without_desktop_control(self):
        result, output, receipt, log = self.run_builder(branch_plan(), renders=True)
        self.assertEqual(result.returncode, 0, log)
        self.assertEqual(
            receipt["renders"],
            ["preview_" + view + ".png" for view in ["front", "back", "left", "right", "threequarter"]],
        )
        for name in receipt["renders"]:
            self.assertEqual((output.parent / name).read_bytes()[:8], b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()
