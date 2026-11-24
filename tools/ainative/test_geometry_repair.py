"""Deterministic align_neck tests with synthetic GLBs; no service calls."""
import base64
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np

from comfy_provider import register as register_comfy
from extensions import NodeRegistry, validate_parameters
from geometry_repair import load_glb, repair, write_glb
from kimi_provider import KimiNativeDirectProvider
from mesh_vision import select_retry_adjust_request


def fixture(path, integrated=False, normals=False):
    document = {
        "asset": {"version": "2.0", "extras": {"maliang_head_review": {"passed": True}}},
        "scene": 0,
        "scenes": [{"nodes": [0] if integrated else [0, 1]}],
        "nodes": (
            [{"name": "IntegratedCharacter", "mesh": 0}]
            if integrated
            else [{"name": "PriestBody", "mesh": 0}, {"name": "ReferenceHead", "mesh": 1}]
        ),
        "meshes": [],
        "buffers": [{"byteLength": 0}],
        "bufferViews": [],
        "accessors": [],
    }
    binary = bytearray()

    def add_accessor(values, value_type):
        while len(binary) % 4:
            binary.append(0)
        view = len(document["bufferViews"])
        document["bufferViews"].append({"buffer": 0, "byteOffset": len(binary), "byteLength": values.nbytes})
        binary.extend(values.tobytes())
        index = len(document["accessors"])
        entry = {
            "bufferView": view,
            "componentType": 5126 if values.dtype == np.dtype("<f4") else 5125,
            "count": len(values),
            "type": value_type,
        }
        if value_type == "VEC3":
            entry.update(min=values.min(axis=0).tolist(), max=values.max(axis=0).tolist())
        document["accessors"].append(entry)
        return index

    def add_mesh(name, points):
        points = np.asarray(points, dtype="<f4")
        position = add_accessor(points, "VEC3")
        attributes = {"POSITION": position}
        if normals:
            normal_values = np.tile(np.asarray([[0, 0, 1]], dtype="<f4"), (len(points), 1))
            attributes["NORMAL"] = add_accessor(normal_values, "VEC3")
        index = add_accessor(np.asarray([0, 1, 2], dtype="<u4"), "SCALAR")
        document["meshes"].append({
            "name": name,
            "primitives": [{"attributes": attributes, "indices": index, "mode": 4}],
        })

    if integrated:
        add_mesh("IntegratedCharacter", [
            [0, 0, 0], [1, 0, 0], [0, 1.0, 0], [.5, 1.1, .1], [.2, 1.05, .1], [.4, 1.05, .1],
        ])
    else:
        add_mesh("PriestBody", [[0, .95, 0], [1, 1, 0], [0, 1.05, 0]])
        add_mesh("ReferenceHead", [[1, 1, .1], [2, 1.02, .1], [1, 1.04, .1]])
    document["buffers"][0]["byteLength"] = len(binary)
    encoded = json.dumps(document).encode()
    encoded += b" " * (-len(encoded) % 4)
    payload = bytes(binary) + b"\0" * (-len(binary) % 4)
    result = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(encoded) + 8 + len(payload))
    result += struct.pack("<II", len(encoded), 0x4E4F534A) + encoded
    result += struct.pack("<II", len(payload), 0x004E4942) + payload
    path.write_bytes(result)


class GeometryRepairTests(unittest.TestCase):
    def test_align_neck_changes_only_head_and_invalidates_old_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.glb"
            output = root / "repaired.glb"
            fixture(source)
            original = source.read_bytes()
            spec = dict(
                schema_version=1,
                source=str(source),
                source_sha256=hashlib.sha256(original).hexdigest(),
                output=str(output),
                operation="align_neck",
                head_mesh="ReferenceHead",
                body_mesh="PriestBody",
                neck_y=1.0,
                band_height=.1,
                max_translation=.2,
                axes=["z"],
            )
            result = repair(spec)
            self.assertEqual(source.read_bytes(), original)
            self.assertTrue(result["source_not_overwritten"])
            self.assertAlmostEqual(result["translation_xz"][1], -.1, places=6)
            document, binary = load_glb(output)
            self.assertNotIn("maliang_head_review", document["asset"]["extras"])
            self.assertTrue(document["asset"]["extras"]["maliang_geometry_repair"]["requires_new_head_review"])
            head = document["meshes"][1]
            accessor = document["accessors"][head["primitives"][0]["attributes"]["POSITION"]]
            view = document["bufferViews"][accessor["bufferView"]]
            points = np.frombuffer(binary, dtype="<f4", count=9, offset=view["byteOffset"]).reshape(3, 3)
            self.assertAlmostEqual(float(points[0, 2]), 0.0, places=6)
            self.assertAlmostEqual(float(points[0, 0]), 1.0, places=6)
            with self.assertRaisesRegex(ValueError, "geometry_repair_output_invalid"):
                repair(spec)

    def crown_spec(self, source, output):
        return dict(
            schema_version=1,
            source=str(source),
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            output=str(output),
            operation="reshape_crown",
            mesh="IntegratedCharacter",
            confirmed=True,
            hairline_y=.9,
            blend_height=.05,
            crown_scale=.8,
            front_pivot_x=0.0,
            front_scale=.5,
            expected_head_top_y=1.1,
            review_yaw_degrees=-90.0,
        )

    def test_crown_repair_preserves_face_topology_and_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.glb"
            output = root / "repaired.glb"
            fixture(source, integrated=True, normals=True)
            source_document, source_binary = load_glb(source)
            source_primitive = source_document["meshes"][0]["primitives"][0]
            source_accessor = source_document["accessors"][source_primitive["attributes"]["POSITION"]]
            source_view = source_document["bufferViews"][source_accessor["bufferView"]]
            source_binary = bytearray(source_binary)
            struct.pack_into("<f", source_binary, source_view["byteOffset"] + 7 * 4, .462)
            write_glb(source_document, source_binary, source)
            source_vertices = np.frombuffer(
                source_binary, dtype="<f4", count=18, offset=source_view["byteOffset"]
            ).reshape(6, 3).copy()
            original = source.read_bytes()
            spec = self.crown_spec(source, output)
            spec["hairline_y"] = .462
            result = repair(spec)
            self.assertEqual(source.read_bytes(), original)
            self.assertTrue(result["protected_positions_unchanged"])
            self.assertFalse(result["topology_changed"])
            self.assertFalse(result["decimated"])
            document, binary = load_glb(output)
            primitive = document["meshes"][0]["primitives"][0]
            points = np.asarray(document["accessors"][primitive["attributes"]["POSITION"]]["min"])
            self.assertTrue(np.isfinite(points).all())
            accessor = document["accessors"][primitive["attributes"]["POSITION"]]
            view = document["bufferViews"][accessor["bufferView"]]
            vertices = np.frombuffer(binary, dtype="<f4", count=18, offset=view["byteOffset"]).reshape(6, 3)
            self.assertAlmostEqual(float(vertices[3, 1]), .9724, places=6)
            self.assertAlmostEqual(float(vertices[3, 0]), .25, places=6)
            self.assertEqual(vertices[:3].tolist(), source_vertices[:3].tolist())
            self.assertEqual(float(vertices[2, 1]), float(np.float32(.462)))
            self.assertNotIn("maliang_head_review", document["asset"]["extras"])
            self.assertEqual(document["asset"]["extras"]["maliang_review_frame"]["yaw_degrees"], -90.0)
            spec["confirmed"] = False
            spec["output"] = str(root / "unconfirmed.glb")
            with self.assertRaisesRegex(ValueError, "geometry_repair_confirmation_required"):
                repair(spec)
            self.assertFalse(Path(spec["output"]).exists())

    def test_source_change_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.glb"
            fixture(source)
            spec = dict(
                schema_version=1,
                source=str(source),
                source_sha256="0" * 64,
                output=str(root / "new.glb"),
                operation="align_neck",
                head_mesh="ReferenceHead",
                body_mesh="PriestBody",
                neck_y=1.0,
                band_height=.1,
                max_translation=.2,
                axes=["z"],
            )
            with self.assertRaisesRegex(ValueError, "geometry_repair_source_changed"):
                repair(spec)
            self.assertFalse(Path(spec["output"]).exists())

    def test_neck_only_failure_selects_previous_model_local_repair(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.glb"
            fixture(source)
            document, binary = load_glb(source)
            document["asset"]["extras"]["maliang_head_landmarks"] = dict(
                confirmed=True,
                head_geometry_mode="merged",
                body_neck_y=1.0,
            )
            write_glb(document, binary, source)
            data = source.read_bytes()
            previous = dict(
                id="previous",
                revision=hashlib.sha256(data).hexdigest(),
                type="mesh",
                payload=dict(content_base64=base64.b64encode(data).decode()),
            )
            request = dict(node="image_to_mesh", version="2", inputs={}, parameters={"prompt": ""}, context=[])
            analysis = dict(subject=dict(category="humanoid", description="person", structure="body", expected_details="face"))
            rejected = dict(
                subject_match=True,
                proportions_pass=True,
                head_gate=dict(applicable=True, complete_face=True, neck_join_pass=False),
                issues=["neck-to-collar seam or gap is visible"],
            )
            child, selected = select_retry_adjust_request(request, analysis, previous, rejected)
            self.assertEqual(child["node"], "model_adjust")
            self.assertEqual(child["inputs"]["source"]["revision"], previous["revision"])
            self.assertEqual(child["parameters"]["operation"], "align_neck")
            self.assertEqual(child["parameters"]["repair"]["neck_y"], 1.0)
            self.assertEqual(selected, [])

    def test_provider_executes_local_repair_without_remote_service(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.glb"
            fixture(source)
            data = source.read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            previous = dict(
                id="previous",
                revision=sha,
                type="mesh",
                payload=dict(
                    content_base64=base64.b64encode(data).decode(),
                    content_sha256=sha,
                ),
            )
            plan = dict(
                operation="align_neck",
                source_model=previous,
                source_geometry={},
                repair=dict(
                    head_mesh="ReferenceHead",
                    body_mesh="PriestBody",
                    neck_y=1.0,
                    band_height=.1,
                    max_translation=.2,
                    axes=["z"],
                ),
            )

            class Host:
                def _active(self, _key, _stage):
                    return True

                def write(self, _key, **values):
                    self.receipt = values["model3d_receipt"]
                    return {}

            host = Host()
            directory = root / "attempt"
            directory.mkdir()
            artifact = KimiNativeDirectProvider._repair_geometry(host, "a" * 64, plan, directory)
            output = directory / "generated.glb"
            self.assertTrue(output.is_file())
            self.assertEqual(artifact["revision"], hashlib.sha256(output.read_bytes()).hexdigest())
            self.assertEqual(artifact["payload"]["provenance"]["source_model_sha256"], sha)
            self.assertEqual(artifact["payload"]["provenance"]["service"], "deterministic_glb_operator")
            self.assertFalse(artifact["payload"]["provenance"]["blender_used"])
            self.assertEqual(host.receipt["operation"], "align_neck")

    def test_model_adjust_v2_declares_only_bounded_local_operations(self):
        registry = NodeRegistry()
        register_comfy(registry)
        repair_parameters = dict(
            mesh="IntegratedCharacter",
            confirmed=True,
            hairline_y=.9,
            blend_height=.05,
            crown_scale=.8,
            front_pivot_x=0.0,
            front_scale=.5,
            expected_head_top_y=1.1,
            review_yaw_degrees=-90.0,
        )
        parameters = dict(prompt="", operation="reshape_crown", repair=repair_parameters)
        schema = registry.get("model_adjust", "2")["parameters"]
        validate_parameters(schema, parameters)
        with self.assertRaisesRegex(ValueError, "parameter enum mismatch"):
            validate_parameters(schema, dict(parameters, operation="arbitrary_edit"))
        with self.assertRaisesRegex(ValueError, "unknown parameter"):
            validate_parameters(registry.get("model_adjust", "1")["parameters"], parameters)

    def test_crown_recipe_is_selected_once_and_bound_to_the_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.glb"
            fixture(source, integrated=True, normals=True)
            spec = self.crown_spec(source, Path(temporary) / "output.glb")
            data = source.read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            document, binary = load_glb(source)
            document["asset"]["extras"]["maliang_geometry_recipe"] = dict(
                operation="reshape_crown",
                source_sha256=sha,
                geometry_sha256=hashlib.sha256(binary).hexdigest(),
                confirmed=True,
                mesh=spec["mesh"],
                parameters={
                    key: spec[key]
                    for key in (
                        "hairline_y", "blend_height", "crown_scale", "front_pivot_x",
                        "front_scale", "expected_head_top_y", "review_yaw_degrees",
                    )
                },
            )
            data = write_glb(document, binary, source)
            previous = dict(
                id="previous",
                revision=hashlib.sha256(data).hexdigest(),
                type="mesh",
                payload=dict(
                    content_base64=base64.b64encode(data).decode(),
                    content_sha256=hashlib.sha256(data).hexdigest(),
                ),
            )
            rejected = dict(
                subject_match=True,
                proportions_pass=True,
                head_gate=dict(applicable=True, complete_face=True, neck_join_pass=True),
                issues=["hairstyle is too tall"],
            )
            request = dict(node="image_to_mesh", version="2", inputs={}, parameters={"prompt": ""}, context=[])
            child, selected = select_retry_adjust_request(request, {}, previous, rejected)
            self.assertEqual(child["version"], "2")
            self.assertEqual(child["parameters"]["operation"], "reshape_crown")
            self.assertEqual(child["parameters"]["repair"]["hairline_y"], .9)
            self.assertEqual(selected, [])
            document["asset"]["extras"]["maliang_geometry_recipe"]["geometry_sha256"] = "0" * 64
            data = write_glb(document, binary, source)
            previous["revision"] = hashlib.sha256(data).hexdigest()
            previous["payload"] = dict(
                content_base64=base64.b64encode(data).decode(),
                content_sha256=hashlib.sha256(data).hexdigest(),
            )
            with self.assertRaisesRegex(ValueError, "model3d_geometry_edit_unsupported"):
                select_retry_adjust_request(request, {}, previous, rejected)


if __name__ == "__main__":
    unittest.main()
