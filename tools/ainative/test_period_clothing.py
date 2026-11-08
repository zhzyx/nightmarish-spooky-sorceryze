"""Dedicated bounded right-closing tunic regressions; old cohorts remain intact."""

import copy
import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

import sculpt_builder as core
from character_detail import period_surface_fold_offset

HIP_COVERAGE_PROBE = r'''"""Read actual exported meshes: horizontal radial coat-over-trouser clearance."""

import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

args = sys.argv[sys.argv.index("--") + 1 :]
source, plan_path, output = map(lambda value: Path(value).resolve(), args)
sha = hashlib.sha256(source.read_bytes()).hexdigest()
plan = json.loads(plan_path.read_text(encoding="utf8"))
character = plan["character"]
height = character["height"]
scale = height / 1.8
hem, belt = character["hem_height"] * height, character["belt_height"] * height
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(source))
coat, trousers = bpy.data.objects["Anatomy_shirt"], bpy.data.objects["Anatomy_trousers"]
coordinates = [coat.matrix_world @ vertex.co for vertex in coat.data.vertices]
tree = BVHTree.FromPolygons(coordinates, [list(face.vertices) for face in coat.data.polygons])
points = [trousers.matrix_world @ vertex.co for vertex in trousers.data.vertices]
points = [point for point in points if hem + 0.020 * scale <= point.z <= belt - 0.050 * scale]
assert points
distances = []
misses = []
for point in points:
    direction = Vector((point.x, point.y, 0))
    assert direction.length > 1e-6
    direction.normalize()
    location, _, _, distance = tree.ray_cast(point, direction, 1.0)
    if location is None:
        inward, _, _, depth = tree.ray_cast(point, -direction, 1.0)
        signed = -depth if inward is not None else None
        misses.append(dict(point_blender_z_up=list(point), signed_radial_clearance=signed))
        if signed is not None:
            distances.append(signed)
    else:
        distances.append(distance)
report = dict(
    scope="Actual exported GLB radial coverage only; not full cloth self-intersection or visual acceptance",
    source_sha256=sha,
    source_unchanged=hashlib.sha256(source.read_bytes()).hexdigest() == sha,
    covered_height_interval_m=[hem + 0.020 * scale, belt - 0.050 * scale],
    tested_trouser_vertices=len(points),
    outward_rays_missed=len(misses),
    minimum_signed_radial_clearance_m=min(distances),
    maximum_radial_clearance_m=max(distances),
    examples=sorted(misses, key=lambda item: item["signed_radial_clearance"] if item["signed_radial_clearance"] is not None else -100)[:8],
    result="pass" if not misses else "fail",
)
output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
print("ACTUAL_HIP_COVERAGE", json.dumps({key: value for key, value in report.items() if key != "examples"}))
'''

BLENDER = Path(os.environ.get("AINATIVE_TEST_BLENDER") or shutil.which("blender") or "__blender_unavailable__")


def fixture(height=1.8, angle=40, subdivision=1):
    character = core.character_defaults()
    character.update(
        height=height,
        head_ratio=7.1,
        age="mature",
        clothing="cross_collar_tunic",
        footwear="barefoot",
        hair="bald",
        arm_angle_degrees=angle,
        hem_height=0.40,
        belt_height=0.58,
        sleeve_length=1.0,
        trouser_width=1.2,
        detail={"cloth_ease": 0.2, "fold_amplitude": 0.65},
        cloth_color=[0.51, 0.48, 0.42, 1],
        trouser_color=[0.61, 0.58, 0.51, 1],
        accent_color=[0.46, 0.43, 0.37, 1],
    )
    return dict(
        version=2,
        name="Right closing tunic diagnostic",
        materials=[dict(name="unused", color=[0.5, 0.5, 0.5, 1], roughness=0.8)],
        regions=[],
        character=character,
        finish=dict(voxel_size=0.006, smooth_iterations=1, subdivision=subdivision),
        completion=dict(mode="plausible", inferred_regions=["character"]),
    )


def closed_measure(surface):
    vertices, faces = surface["vertices"], surface["faces"]
    edges = defaultdict(list)
    adjacency = defaultdict(set)
    volume = 0.0
    for face in faces:
        for a, b in zip(face, face[1:] + face[:1]):
            edges[tuple(sorted((a, b)))].append((a, b))
            adjacency[a].add(b)
            adjacency[b].add(a)
        a = vertices[face[0]]
        for index in range(1, len(face) - 1):
            b, c = vertices[face[index]], vertices[face[index + 1]]
            volume += (
                sum(a[i] * (b[(i + 1) % 3] * c[(i + 2) % 3] - b[(i + 2) % 3] * c[(i + 1) % 3]) for i in range(3)) / 6
            )
    seen, pending = set(), [0]
    while pending:
        vertex = pending.pop()
        if vertex not in seen:
            seen.add(vertex)
            pending.extend(adjacency[vertex] - seen)
    return (
        all(len(pair) == 2 and pair[0] == pair[1][::-1] for pair in edges.values()),
        len(seen) == len(vertices),
        volume,
    )


class PeriodClothingTests(unittest.TestCase):
    def test_pose_units_and_old_null_fallback(self):
        character = core.character_defaults()
        original = core._canonical_body(character)
        character["arm_angle_degrees"] = None
        self.assertEqual(core.resolve_arm_angle(character), 65)
        self.assertEqual(original, core._canonical_body(character))
        for angle in (20, 40, 65, 75):
            character["arm_angle_degrees"] = angle
            canonical = core._canonical_body(character)
            for side in ("L", "R"):
                shoulder, wrist = (canonical["landmarks"][key + side] for key in ("shoulder", "wrist"))
                delta = [b - a for a, b in zip(shoulder, wrist)]
                measured = math.degrees(math.atan2(-delta[1], abs(delta[0])))
                self.assertAlmostEqual(measured, angle, places=7)
                self.assertAlmostEqual(delta[2], 0, places=7)

    def test_reject_invalid_pose_data(self):
        for value in (True, False, float("nan"), float("inf"), 19.999, 75.001, "40", [40]):
            plan = fixture()
            plan["character"]["arm_angle_degrees"] = value
            with self.assertRaisesRegex(ValueError, "arm_angle"):
                core.validate_plan(plan)

    def test_plan_not_normalized_and_cross_closing_direction(self):
        plan = fixture()
        before = copy.deepcopy(plan)
        expanded, _ = core._compile_character(core.validate_plan(plan))
        self.assertEqual(plan, before)
        by_name = {region["name"]: region for region in expanded["regions"]}
        self.assertFalse(any("Shoe" in name or "Sandal" in name for name in by_name))
        lapel = by_name["Anatomy_RightClosingOuterLapel"]["surface"]["vertices"]
        self.assertGreater(sum(point[0] for point in lapel[:4]), 0)
        self.assertLess(sum(point[0] for point in lapel[-4:]), 0)
        for name in ("LeftWaistKnot", "LeftWaistTail1", "LeftWaistTail2"):
            self.assertTrue(all(point[0] > 0 for point in by_name["Anatomy_" + name]["surface"]["vertices"]))

    def test_closed_layered_front_belt_tails_and_cuffs_at_scale_extremes(self):
        for height, angle in ((0.8, 20), (1.8, 40), (2.4, 75)):
            expanded, _ = core._compile_character(core.validate_plan(fixture(height, angle)))
            closed = [
                region
                for region in expanded["regions"]
                if any(
                    key in region["name"]
                    for key in ("RightClosing", "LeftWaist", "CrossCollarBelt", "RolledCuff", "ActualBackNeck")
                )
            ]
            self.assertEqual(len(closed), 10)
            for region in closed:
                manifold, connected, volume = closed_measure(region["surface"])
                self.assertTrue(manifold and connected, region["name"])
                self.assertGreater(volume, 1e-12, region["name"])
                self.assertTrue(
                    all(math.isfinite(v) and abs(v) < 8 for point in region["surface"]["vertices"] for v in point)
                )

    def test_local_fold_bounds_and_oblique_variation(self):
        character = fixture()["character"]
        canonical = core._canonical_body(character)
        shoulder, wrist = (canonical["landmarks"][key + "L"] for key in ("shoulder", "wrist"))
        values = []
        for t in (0.1, 0.36, 0.48, 0.61, 0.76, 0.88):
            point = [a + t * (b - a) for a, b in zip(shoulder, wrist)]
            point[2] += 0.06
            delta = period_surface_fold_offset(point, (0, 0, 1), canonical, character, "shirt")
            self.assertTrue(0 <= delta[2] <= 0.02)
            values.append(delta[2])
        self.assertGreater(max(values) - min(values), 0.001)

    def test_available_coat_length_controls_both_tails_without_mutating_plan(self):
        for height in (0.8, 1.8, 2.4):
            for hem, belt in ((0.40, 0.58), (0.65, 0.70)):
                plan = fixture(height)
                plan["character"].update(hem_height=hem, belt_height=belt)
                before = copy.deepcopy(plan)
                expanded, _ = core._compile_character(core.validate_plan(plan))
                self.assertEqual(plan, before)
                by_name = {region["name"]: region for region in expanded["regions"]}
                for index in (1, 2):
                    surface = by_name["Anatomy_LeftWaistTail" + str(index)]["surface"]
                    closed, connected, volume = closed_measure(surface)
                    self.assertTrue(closed and connected)
                    self.assertGreater(volume, 1e-12)
                    self.assertGreaterEqual(
                        min(point[1] for point in surface["vertices"]), hem * height - 0.04 * height / 1.8
                    )
                if hem == 0.40:
                    # Existing ordinary coats retain exactly the old .20m
                    # second-tail centerline length; no source-data rewrite.
                    points = by_name["Anatomy_LeftWaistTail2"]["surface"]["vertices"]
                    begin = sum(point[1] for point in points[:4]) / 4
                    end = sum(point[1] for point in points[-4:]) / 4
                    self.assertAlmostEqual(begin - end, 0.20 * height / 1.8, places=12)

    def run_blender(self, plan):
        if not BLENDER.is_file():
            self.skipTest("Set AINATIVE_TEST_BLENDER for native clothing geometry checks")
        temporary = tempfile.TemporaryDirectory(prefix="maliang-clothing-")
        self.addCleanup(temporary.cleanup)
        folder = Path(temporary.name)
        source, output = folder / "plan.json", folder / "asset.glb"
        source.write_bytes(json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        result = subprocess.run(
            [
                str(BLENDER),
                "--background",
                "--factory-startup",
                "--disable-autoexec",
                "--threads",
                "4",
                "--python-exit-code",
                "1",
                "--python",
                str(Path(core.__file__).resolve()),
                "--",
                str(source),
                str(output),
            ],
            capture_output=True,
            text=True,
            encoding="utf8",
            errors="replace",
            timeout=180,
        )
        (folder / "builder.log").write_text(result.stdout + result.stderr, encoding="utf8")
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-2000:])
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
        receipt = json.loads(Path(str(output) + ".receipt.json").read_text(encoding="utf8"))
        self.assertEqual(receipt["body_components"], 1)
        self.assertTrue(
            all(
                q["components"] == 1 and q["manifold"] and q["volume"] > 0 and q["degenerate_triangles"] == 0
                for q in receipt["geometry"]
            )
        )
        self.assertEqual(
            receipt["character_operator"]["effective_arm_angle_degrees"], plan["character"]["arm_angle_degrees"]
        )
        self.assertTrue(receipt["character_operator"]["period_clothing"]["continuous_back"])
        self.assertEqual(
            receipt["runtime_input_sha256"]["period_groom_sha256"],
            hashlib.sha256(Path(core.__file__).with_name("period_groom.py").read_bytes()).hexdigest(),
        )
        self.assertLessEqual(receipt["vertices"], core.MAX_VERTICES)
        self.assertLessEqual(receipt["triangles"], core.MAX_TRIANGLES)
        self.assertLessEqual(output.stat().st_size, core.MAX_GLB_BYTES)
        probe_source = folder / "hip-coverage-probe.py"
        probe_source.write_bytes(HIP_COVERAGE_PROBE.encode("utf8"))
        coverage_output = folder / "hip-coverage.json"
        coverage_result = subprocess.run(
            [
                str(BLENDER),
                "--background",
                "--factory-startup",
                "--disable-autoexec",
                "--threads",
                "2",
                "--python-exit-code",
                "1",
                "--python",
                str(probe_source),
                "--",
                str(output),
                str(source),
                str(coverage_output),
            ],
            capture_output=True,
            text=True,
            encoding="utf8",
            errors="replace",
            timeout=60,
        )
        (folder / "coverage.log").write_text(coverage_result.stdout + coverage_result.stderr, encoding="utf8")
        self.assertEqual(coverage_result.returncode, 0, (coverage_result.stdout + coverage_result.stderr)[-2000:])
        coverage = json.loads(coverage_output.read_text(encoding="utf8"))
        self.assertGreater(coverage["tested_trouser_vertices"], 100)
        self.assertEqual(coverage["outward_rays_missed"], 0)
        self.assertGreater(coverage["minimum_signed_radial_clearance_m"], 0)

    def test_actual_blender_long_sleeves_bare_feet(self):
        self.run_blender(fixture())

    def test_actual_blender_subdivision2_small_and_large(self):
        for height, angle in ((0.8, 20), (2.4, 75)):
            self.run_blender(fixture(height, angle, subdivision=2))


if __name__ == "__main__":
    unittest.main(verbosity=2)
