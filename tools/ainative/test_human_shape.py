"""Synthetic static-humanoid tests for pre-rig body shape adjustment."""

import base64
import hashlib
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np
from comfy_provider import register as register_comfy
from extensions import NodeRegistry, validate_invocation, validate_parameters
from geometry_repair import HUMAN_LANDMARK_NAMES, accessor_values, load_glb, repair, write_glb
from kimi_provider import KimiNativeDirectProvider

LANDMARKS = {
    "head_top": [0.0, 1.8, 0.0],
    "chin": [0.0, 1.55, 0.0],
    "neck": [0.0, 1.5, 0.0],
    "shoulder_l": [0.2, 1.45, 0.0],
    "elbow_l": [0.45, 1.45, 0.0],
    "wrist_l": [0.7, 1.45, 0.0],
    "shoulder_r": [-0.2, 1.45, 0.0],
    "elbow_r": [-0.45, 1.45, 0.0],
    "wrist_r": [-0.7, 1.45, 0.0],
    "hip_l": [0.1, 0.95, 0.0],
    "knee_l": [0.1, 0.5, 0.0],
    "ankle_l": [0.1, 0.1, 0.0],
    "hip_r": [-0.1, 0.95, 0.0],
    "knee_r": [-0.1, 0.5, 0.0],
    "ankle_r": [-0.1, 0.1, 0.0],
}


def humanoid_fixture(path, rigged=False):
    document = {
        "asset": {"version": "2.0", "extras": {"maliang_head_review": {"passed": True}}},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"name": "Humanoid", "mesh": 0}],
        "meshes": [],
        "buffers": [{"byteLength": 0}],
        "bufferViews": [],
        "accessors": [],
    }
    if rigged:
        document["skins"] = [{"joints": [0]}]
    vertices = []
    indices = []
    size = 0.01

    def tetra(center, top=False):
        c = np.asarray(center, dtype=np.float64)
        if top:
            points = [c, c + [-size, -2 * size, size], c + [size, -2 * size, size], c + [0, -2 * size, -size]]
        else:
            points = [
                c + [size, size, size],
                c + [size, -size, -size],
                c + [-size, size, -size],
                c + [-size, -size, size],
            ]
        offset = len(vertices)
        vertices.extend(points)
        indices.extend(
            offset + index for triangle in ((0, 1, 2), (0, 3, 1), (0, 2, 3), (1, 3, 2)) for index in triangle
        )

    for name in HUMAN_LANDMARK_NAMES:
        tetra(LANDMARKS[name], top=name == "head_top")
    tetra([0.0, 1.2, 0.0])
    points = np.asarray(vertices, dtype="<f4")
    faces = np.asarray(indices, dtype="<u4")
    binary = bytearray(points.tobytes())
    document["bufferViews"].append({"buffer": 0, "byteOffset": 0, "byteLength": points.nbytes})
    document["accessors"].append({
        "bufferView": 0,
        "componentType": 5126,
        "count": len(points),
        "type": "VEC3",
        "min": points.min(axis=0).tolist(),
        "max": points.max(axis=0).tolist(),
    })
    document["bufferViews"].append({"buffer": 0, "byteOffset": len(binary), "byteLength": faces.nbytes})
    binary.extend(faces.tobytes())
    document["accessors"].append({"bufferView": 1, "componentType": 5125, "count": len(faces), "type": "SCALAR"})
    document["meshes"].append({
        "name": "Humanoid",
        "primitives": [{"attributes": {"POSITION": 0}, "indices": 1, "mode": 4}],
    })
    document["buffers"][0]["byteLength"] = len(binary)
    write_glb(document, binary, path)


def shape_spec(source, output, **changes):
    data = source.read_bytes()
    landmarks = dict(source_sha256=hashlib.sha256(data).hexdigest(), **LANDMARKS)
    value = dict(
        schema_version=1,
        source=str(source),
        source_sha256=hashlib.sha256(data).hexdigest(),
        output=str(output),
        operation="reshape_humanoid",
        reference_pose="T",
        landmarks=landmarks,
        target_height_m=1.9,
        target_head_ratio=9.0,
        arm_length_scale=1.2,
        leg_length_scale=1.1,
        build=0.4,
    )
    value.update(changes)
    return value


class HumanShapeTests(unittest.TestCase):
    def test_all_five_controls_are_measured_on_a_new_pre_rig_glb(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.glb"
            output = root / "shaped.glb"
            humanoid_fixture(source)
            original = source.read_bytes()
            result = repair(shape_spec(source, output))
            self.assertEqual(source.read_bytes(), original)
            self.assertTrue(result["source_not_overwritten"])
            self.assertAlmostEqual(result["measured"]["height_m"], 1.9, places=6)
            self.assertAlmostEqual(result["measured"]["head_ratio"], 9.0, places=5)
            normalize = result["uniform_height_scale"]
            for side in ("l", "r"):
                self.assertAlmostEqual(result["measured"]["arm_lengths_m"][side] / normalize, 0.6, places=5)
                self.assertAlmostEqual(result["measured"]["leg_lengths_m"][side] / normalize, 0.935, places=5)
            self.assertEqual(result["build"], 0.4)
            self.assertGreater(result["changed_vertices"], 0)
            self.assertFalse(result["topology_changed"])
            self.assertTrue(result["requires_new_head_review"])
            self.assertTrue(result["requires_new_rigging"])
            self.assertEqual(result["binding_stage"], "pre_rig_geometry_only")
            self.assertEqual(result["validation_mode"], "ainative_source_bound_landmarks_automatic")
            document, binary = load_glb(output)
            extras = document["asset"]["extras"]
            self.assertNotIn("maliang_head_review", extras)
            self.assertEqual(
                extras["maliang_humanoid_landmarks"]["validation_state"], "automatically_derived_review_required"
            )
            self.assertNotIn("confirmed", extras["maliang_humanoid_landmarks"])
            self.assertTrue(extras["maliang_humanoid_landmarks"]["review_required"])
            primitive = document["meshes"][0]["primitives"][0]
            points = accessor_values(document, binary, primitive["attributes"]["POSITION"], "VEC3")
            self.assertAlmostEqual(float(points[:, 1].max() - points[:, 1].min()), 1.9, places=5)
            self.assertAlmostEqual(float(points[:, 1].min()), 0.0, places=6)

    def test_automatic_source_binding_pose_and_rigged_input_are_enforced(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.glb"
            humanoid_fixture(source)
            with self.assertRaisesRegex(ValueError, "geometry_repair_reference_pose_invalid"):
                repair(shape_spec(source, root / "invalid-pose.glb", reference_pose="unknown"))
            with self.assertRaisesRegex(ValueError, "geometry_repair_spec_invalid"):
                repair(shape_spec(source, root / "legacy-confirmation.glb", confirmed=False))
            wrong = dict(source_sha256="0" * 64, **LANDMARKS)
            with self.assertRaisesRegex(ValueError, "geometry_repair_landmark_source_mismatch"):
                repair(shape_spec(source, root / "wrong.glb", landmarks=wrong))
            rigged = root / "rigged.glb"
            humanoid_fixture(rigged, rigged=True)
            with self.assertRaisesRegex(ValueError, "geometry_repair_rigged_source_unsupported"):
                repair(shape_spec(rigged, root / "postrig.glb"))
            self.assertFalse((root / "invalid-pose.glb").exists())
            self.assertFalse((root / "legacy-confirmation.glb").exists())
            self.assertFalse((root / "wrong.glb").exists())
            self.assertFalse((root / "postrig.glb").exists())

    def test_nine_head_target_and_parameter_bounds_are_not_weakened(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.glb"
            humanoid_fixture(source)
            with self.assertRaisesRegex(ValueError, "geometry_repair_parameters_invalid"):
                repair(shape_spec(source, root / "too-many-heads.glb", target_head_ratio=12.1))
            with self.assertRaisesRegex(ValueError, "geometry_repair_parameters_invalid"):
                repair(shape_spec(source, root / "bad-arm.glb", arm_length_scale=1.4))

    def test_rotated_anatomical_left_axis_preserves_arm_and_leg_controls(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.glb"
            humanoid_fixture(source)
            document, binary = load_glb(source)
            binary = bytearray(binary)
            theta = math.radians(-90.0)
            rotation = np.asarray([
                [math.cos(theta), 0.0, math.sin(theta)],
                [0.0, 1.0, 0.0],
                [-math.sin(theta), 0.0, math.cos(theta)],
            ])
            for mesh in document["meshes"]:
                for primitive in mesh["primitives"]:
                    index = primitive["attributes"]["POSITION"]
                    points = accessor_values(document, binary, index, "VEC3")
                    points[:] = np.asarray(points, dtype=np.float64) @ rotation.T
                    document["accessors"][index]["min"] = points.min(axis=0).tolist()
                    document["accessors"][index]["max"] = points.max(axis=0).tolist()
            write_glb(document, binary, source)
            rotated = {name: (rotation @ np.asarray(point)).tolist() for name, point in LANDMARKS.items()}
            spec = shape_spec(
                source,
                root / "rotated-output.glb",
                landmarks=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), **rotated),
            )
            result = repair(spec)
            normalize = result["uniform_height_scale"]
            for side in ("l", "r"):
                self.assertAlmostEqual(result["measured"]["arm_lengths_m"][side] / normalize, 0.6, places=5)
                self.assertAlmostEqual(result["measured"]["leg_lengths_m"][side] / normalize, 0.935, places=5)

    def test_node_contract_plans_and_executes_without_remote_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.glb"
            humanoid_fixture(source)
            spec = shape_spec(source, root / "unused.glb")
            data = source.read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            parameters = dict(
                height_cm=190,
                head_ratio=spec["target_head_ratio"],
                arm_length_scale=spec["arm_length_scale"],
                leg_length_scale=spec["leg_length_scale"],
                build=spec["build"],
                reference_pose="T",
                landmarks=spec["landmarks"],
            )
            artifact = dict(
                id="source",
                revision=sha,
                type="mesh",
                payload=dict(content_base64=base64.b64encode(data).decode(), content_sha256=sha, extension=".glb"),
            )
            manifest = dict(schema_version=1, artifacts=[artifact])
            request = dict(
                node="human_shape_adjust",
                version="1",
                inputs={"source": {"id": "source", "revision": sha}},
                parameters=parameters,
                context=[],
            )
            registry = NodeRegistry()
            register_comfy(registry)
            validate_parameters(registry.get("human_shape_adjust", "1")["parameters"], parameters)
            provider = dict(
                id="kimi_native",
                version="1",
                model="local-test",
                model_version="test",
                capabilities=["human_shape_adjust"],
                context_types=["text", "image"],
                available=True,
            )
            validate_invocation(registry, request, manifest, provider)
            for height_cm, height_m in ((170, 1.7), (180, 1.8), (190, 1.9)):
                with self.subTest(height_cm=height_cm):
                    converted = KimiNativeDirectProvider._adjust_plan(
                        None, dict(request, parameters=dict(parameters, height_cm=height_cm)), manifest
                    )
                    self.assertAlmostEqual(converted["repair"]["target_height_m"], height_m)
                    self.assertEqual(converted["original_parameters"]["height_cm"], height_cm)
            for invalid_height in (173, 180.5, 170.1, 10, 410, True, "180", None):
                with self.subTest(invalid_height=invalid_height):
                    with self.assertRaisesRegex(ValueError, "invalid_input"):
                        KimiNativeDirectProvider._adjust_plan(
                            None, dict(request, parameters=dict(parameters, height_cm=invalid_height)), manifest
                        )
            plan = KimiNativeDirectProvider._adjust_plan(None, request, manifest)
            self.assertEqual(plan["operation"], "reshape_humanoid")
            self.assertEqual(plan["repair"]["target_head_ratio"], 9.0)
            self.assertNotIn("task_id", plan)
            legacy = dict(request, parameters=dict(parameters, confirmed=False, prompt=""))
            validate_invocation(registry, legacy, manifest, provider)
            legacy_plan = KimiNativeDirectProvider._adjust_plan(None, legacy, manifest)
            self.assertNotIn("confirmed", legacy_plan["repair"])
            self.assertNotIn("prompt", legacy_plan["repair"])

            class Host:
                def _active(self, _key, _stage):
                    return True

                def write(self, _key, **values):
                    self.receipt = values["model3d_receipt"]
                    return {}

            host = Host()
            directory = root / "attempt"
            directory.mkdir()
            result = KimiNativeDirectProvider._repair_geometry(host, "a" * 64, plan, directory)
            self.assertTrue((directory / "generated.glb").is_file())
            self.assertEqual(result["payload"]["provenance"]["provider"], "local_geometry_repair")
            self.assertEqual(result["payload"]["provenance"]["operation"], "reshape_humanoid")
            self.assertFalse(result["payload"]["provenance"]["blender_used"])
            self.assertEqual(host.receipt["height_cm"], 190)
            self.assertEqual(result["payload"]["provenance"]["height_cm"], 190)
            self.assertEqual(host.receipt["geometry_repair"]["measured"]["height_m"], 1.9)


if __name__ == "__main__":
    unittest.main()
