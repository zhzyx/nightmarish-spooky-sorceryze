import copy
import hashlib
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

import numpy as np

from extensions import canonical
from garment_inventory import request_inventory
from garment_split import GarmentSource, spec_from_inventory, split, validate_inventory
from geometry_repair import accessor_values, load_glb


def png():
    def chunk(kind, body):
        return struct.pack(">I4s", len(body), kind) + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"\0\x80\x80\x80"))
        + chunk(b"IEND", b"")
    )


def accessor_bytes(document, binary, index, item_size):
    accessor = document["accessors"][index]
    view = document["bufferViews"][accessor["bufferView"]]
    start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    return binary[start : start + accessor["count"] * item_size]


def make_glb(path, *, transform=False, skin=False, invalid_skin=False, external=False, embedded_image=False, normalized_weights=False):
    document = dict(
        asset=dict(version="2.0"),
        scene=0,
        scenes=[dict(nodes=[0, 1])],
        nodes=[dict(name="body-and-shirt", mesh=0), dict(name="boot", mesh=1)],
        meshes=[dict(name="fused", primitives=[]), dict(name="separate", primitives=[])],
        buffers=[dict(byteLength=0)],
        bufferViews=[],
        accessors=[],
        materials=[dict(name="woven", pbrMetallicRoughness=dict(baseColorFactor=[0.2, 0.3, 0.4, 1]))],
    )
    binary = bytearray()

    def view(data, target=None):
        binary.extend(b"\0" * (-len(binary) % 4))
        record = dict(buffer=0, byteOffset=len(binary), byteLength=len(data))
        if target is not None:
            record["target"] = target
        binary.extend(data)
        document["bufferViews"].append(record)
        return len(document["bufferViews"]) - 1

    def accessor(values, kind, target):
        values = np.asarray(values)
        record = dict(
            bufferView=view(values.astype(values.dtype.newbyteorder("<")).tobytes(), target),
            componentType={np.dtype("<f4"): 5126, np.dtype("<u4"): 5125, np.dtype("<u2"): 5123}[values.dtype.newbyteorder("<")],
            count=values.size if kind == "SCALAR" else len(values),
            type=kind,
        )
        document["accessors"].append(record)
        return len(document["accessors"]) - 1

    def primitive(offset, joint=0):
        points = np.asarray(
            [[offset, 0, 0], [offset + 1, 0, 0], [offset, 1, 0]], dtype="<f4"
        )
        normals = np.tile(np.asarray([[0, 0, 1]], dtype="<f4"), (3, 1))
        uv = np.asarray([[0, 0], [1, 0], [0, 1]], dtype="<f4")
        indices = np.asarray([[0, 1, 2]], dtype="<u4")
        attributes = dict(
            POSITION=accessor(points, "VEC3", 34962),
            NORMAL=accessor(normals, "VEC3", 34962),
            TEXCOORD_0=accessor(uv, "VEC2", 34962),
        )
        return dict(
            attributes=attributes,
            indices=accessor(indices, "SCALAR", 34963),
            material=0,
        )

    # Two disconnected triangles deliberately share one primitive.
    document["meshes"][0]["primitives"] = [primitive(0), primitive(3)]
    first = document["meshes"][0]["primitives"][0]
    second = document["meshes"][0]["primitives"][1]
    attribute_keys = ["POSITION", "NORMAL", "TEXCOORD_0"]
    for key in (*attribute_keys, "indices"):
        first_index = first[key] if key == "indices" else first["attributes"][key]
        second_index = second[key] if key == "indices" else second["attributes"][key]
        first_accessor = document["accessors"][first_index]
        second_accessor = document["accessors"][second_index]
        first_view = document["bufferViews"][first_accessor["bufferView"]]
        second_view = document["bufferViews"][second_accessor["bufferView"]]
        first_data = binary[first_view["byteOffset"] : first_view["byteOffset"] + first_view["byteLength"]]
        second_data = binary[second_view["byteOffset"] : second_view["byteOffset"] + second_view["byteLength"]]
        merged = view(first_data + second_data, first_view.get("target"))
        first_accessor["bufferView"] = second_accessor["bufferView"] = merged
        first_accessor["count"] = second_accessor["count"] = 6 if key != "indices" else 2
        if key == "indices":
            first_accessor["componentType"] = second_accessor["componentType"] = 5123
            # Replace the merged index payload with a single six-index uint16 accessor.
            first_accessor["bufferView"] = second_accessor["bufferView"] = view(
                np.asarray([0, 1, 2, 3, 4, 5], dtype="<u2").tobytes(), 34963
            )
            first_accessor["count"] = second_accessor["count"] = 6
            first_accessor["type"] = second_accessor["type"] = "SCALAR"
        else:
            first_accessor["byteOffset"] = second_accessor.get("byteOffset", 0)
            second_accessor["byteOffset"] = 0
            first_accessor["componentType"] = second_accessor["componentType"] = (
                5125 if key == "JOINTS_0" else 5123 if key == "WEIGHTS_0" and normalized_weights else 5126
            )
            first_accessor["type"] = second_accessor["type"] = {
                "POSITION": "VEC3",
                "NORMAL": "VEC3",
                "TEXCOORD_0": "VEC2",
                "JOINTS_0": "VEC4",
                "WEIGHTS_0": "VEC4",
            }[key]
    # The fixture above leaves legacy views unreferenced; only the shared
    # accessors are retained, proving accessor-based rather than view-based copy.
    document["meshes"][0]["primitives"] = [first]
    document["accessors"] = [
        *(document["accessors"][first["attributes"][name]] for name in attribute_keys),
        document["accessors"][first["indices"]],
    ]
    first["attributes"] = {name: index for index, name in enumerate(attribute_keys)}
    first["indices"] = len(attribute_keys)
    document["meshes"][1]["primitives"] = [primitive(6, 1)]
    # Renumber the second mesh's accessors after the compaction above.
    start = len(document["accessors"]) - len(attribute_keys) - 1
    second_attributes = {name: start + index for index, name in enumerate(attribute_keys)}
    document["meshes"][1]["primitives"][0]["attributes"] = second_attributes
    document["meshes"][1]["primitives"][0]["indices"] = start + len(attribute_keys)
    if embedded_image:
        image_view = view(png())
        document.update(samplers=[{}], images=[dict(bufferView=image_view, mimeType="image/png")], textures=[dict(source=0)])
        document["materials"][0]["pbrMetallicRoughness"]["baseColorTexture"] = dict(index=0)
    if transform:
        document["nodes"][0]["translation"] = [1, 0, 0]
    if skin:
        for attributes, joint, count in ((first["attributes"], 0, 6), (second_attributes, 1, 3)):
            attributes["JOINTS_0"] = accessor(
                np.tile(np.asarray([[joint, 0, 0, 0]], dtype="<u4"), (count, 1)), "VEC4", 34962
            )
            if normalized_weights:
                attributes["WEIGHTS_0"] = accessor(
                    np.tile(np.asarray([[65535, 0, 0, 0]], dtype="<u2"), (count, 1)), "VEC4", 34962
                )
                document["accessors"][attributes["WEIGHTS_0"]]["normalized"] = True
            else:
                attributes["WEIGHTS_0"] = accessor(
                    np.tile(np.asarray([[1.0, 0.0, 0.0, 0.0]], dtype="<f4"), (count, 1)), "VEC4", 34962
                )
        identity = np.eye(4, dtype="<f4").reshape(1, 16)
        document["skins"] = [
            dict(
                joints=[0, 1],
                inverseBindMatrices=accessor(np.concatenate([identity, identity], axis=0), "MAT4", None),
            )
        ]
        document["nodes"][0]["skin"] = 0
        document["nodes"][1]["skin"] = 0
    if invalid_skin:
        document["skins"] = [dict(joints=[0])]
    if external:
        document["buffers"][0]["uri"] = "external.bin"
    document["buffers"][0]["byteLength"] = len(binary)
    encoded = json.dumps(document, separators=(",", ":")).encode()
    encoded += b" " * (-len(encoded) % 4)
    binary.extend(b"\0" * (-len(binary) % 4))
    raw = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(encoded) + 8 + len(binary))
    raw += struct.pack("<II", len(encoded), 0x4E4F534A) + encoded
    raw += struct.pack("<II", len(binary), 0x004E4942) + binary
    path.write_bytes(raw)
    return raw


def make_cape(path, columns=17, rows=41):
    points = []
    for row in range(rows):
        for column in range(columns):
            points.append([column / (columns - 1), row / (rows - 1), 0.03 * np.sin(column + row)])
    faces = []
    for row in range(rows - 1):
        for column in range(columns - 1):
            a = row * columns + column
            faces.extend([[a, a + 1, a + columns], [a + 1, a + columns + 1, a + columns]])
    document = dict(
        asset=dict(version="2.0"),
        scene=0,
        scenes=[dict(nodes=[0])],
        nodes=[dict(name="cape", mesh=0)],
        meshes=[dict(name="cape", primitives=[dict(attributes=dict(POSITION=0), indices=1)])],
        buffers=[dict(byteLength=0)],
        bufferViews=[],
        accessors=[],
    )
    binary = bytearray()
    for values, component, kind, target in (
        (np.asarray(points, dtype="<f4"), 5126, "VEC3", 34962),
        (np.asarray(faces, dtype="<u4").reshape(-1), 5125, "SCALAR", 34963),
    ):
        view = dict(buffer=0, byteOffset=len(binary), byteLength=values.nbytes, target=target)
        binary.extend(values.tobytes())
        document["bufferViews"].append(view)
        document["accessors"].append(
            dict(bufferView=len(document["bufferViews"]) - 1, componentType=component, count=len(values), type=kind)
        )
    document["buffers"][0]["byteLength"] = len(binary)
    encoded = json.dumps(document, separators=(",", ":")).encode()
    encoded += b" " * (-len(encoded) % 4)
    binary.extend(b"\0" * (-len(binary) % 4))
    raw = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(encoded) + 8 + len(binary))
    raw += struct.pack("<II", len(encoded), 0x4E4F534A) + encoded
    raw += struct.pack("<II", len(binary), 0x004E4942) + binary
    path.write_bytes(raw)
    return raw


def item(identifier, components, **changes):
    result = dict(
        id=identifier,
        label="Open vocabulary " + identifier,
        category="garment",
        slot="back",
        behavior="cloth",
        confidence=0.8,
        review_state="automatic",
        selection=dict(mode="components", component_ids=components),
    )
    result.update(changes)
    return result


def inventory(identifier, components, **changes):
    result = dict(
        id=identifier,
        label="披风" if identifier == "cape" else "胸甲",
        category="garment",
        slot="back",
        behavior="cloth",
        confidence=0.9,
        component_ids=components,
        evidence="Attached component preview",
        needs_review=False,
    )
    result.update(changes)
    return result


class GarmentSplitTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source.glb"
        self.raw = make_glb(self.source, embedded_image=True)
        self.geometry = GarmentSource(self.source)
        self.components = self.geometry.inspection()["components"]

    def tearDown(self):
        self.temporary.cleanup()

    def spec(self, items, name="output"):
        return dict(
            schema_version=1,
            source=str(self.source),
            source_sha256=self.geometry.sha256,
            output=str(self.root / name),
            items=items,
        )

    def test_inspection_has_stable_open_geometry_inventory(self):
        inspection = self.geometry.inspection()
        self.assertEqual(inspection["primitive_count"], 2)
        self.assertEqual(inspection["component_count"], 3)
        self.assertEqual(
            [entry["component_id"] for entry in inspection["components"]],
            [entry["component_id"] for entry in GarmentSource(self.source).inspection()["components"]],
        )
        self.assertEqual([entry["triangle_count"] for entry in inspection["components"]], [1, 1, 1])
        self.assertNotIn("_face_ids", inspection["components"][0])

    def test_component_split_preserves_attributes_material_and_source(self):
        result = split(
            self.spec(
                [
                    item("cape", [self.components[0]["component_id"]]),
                    item("armor", [self.components[2]["component_id"]], behavior="rigid", category="armor"),
                ]
            )
        )
        self.assertEqual(result["status"], "surface_split")
        self.assertFalse(result["cloth_ready"])
        self.assertEqual(self.source.read_bytes(), self.raw)
        for record in result["items"]:
            output = self.root / "output" / record["path"]
            document, binary = load_glb(output)
            self.assertEqual(len(document["meshes"]), 1)
            primitive = document["meshes"][0]["primitives"][0]
            self.assertEqual(document["accessors"][primitive["indices"]]["count"], 3)
            self.assertEqual(set(primitive["attributes"]), {"POSITION", "NORMAL", "TEXCOORD_0"})
            self.assertEqual(primitive["material"], 0)
            self.assertIn("images", document)
            self.assertEqual(document["images"][0]["mimeType"], "image/png")
            self.assertEqual(record["triangles"], 1)
            self.assertEqual(len(record["source_primitives"][0]["source_triangles"]), 1)
        self.assertEqual(result["collection"]["triangles"], 2)
        self.assertEqual(result["collection"]["path"], "_garments.glb")
        self.assertTrue((self.root / "output" / "_garments.glb").is_file())
        before = (self.root / "output" / "split_manifest.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "output_exists"):
            split(self.spec([item("cape", [self.components[0]["component_id"]])]))
        self.assertEqual((self.root / "output" / "split_manifest.json").read_bytes(), before)

    def test_rigged_split_preserves_skeleton_weights_and_inverse_binds(self):
        source = self.root / "rigged.glb"
        raw = make_glb(source, skin=True, embedded_image=True)
        geometry = GarmentSource(source)
        self.assertTrue(geometry.rigged)
        component = geometry.inspection()["components"][0]["component_id"]
        entry = item("cape", [component])
        result = split(
            dict(
                schema_version=1,
                source=str(source),
                source_sha256=geometry.sha256,
                output=str(self.root / "rigged-output"),
                items=[entry],
            )
        )
        self.assertTrue(result["rigged"])
        self.assertTrue(result["skeleton_preserved"])
        self.assertTrue(result["skin_weights_preserved"])
        self.assertTrue(result["unreferenced_source_vertices_retained"])
        original, original_binary = load_glb(source)
        output, output_binary = load_glb(self.root / "rigged-output" / "cape.glb")
        self.assertEqual(output["nodes"][0]["name"], original["nodes"][0]["name"])
        self.assertEqual(output["nodes"][0]["skin"], original["nodes"][0]["skin"])
        self.assertNotIn("mesh", output["nodes"][1])
        self.assertNotIn("skin", output["nodes"][1])
        self.assertEqual(output["skins"], original["skins"])
        self.assertEqual(output["scenes"], original["scenes"])
        self.assertEqual(len(output["meshes"]), len(original["meshes"]) + 1)
        original_primitive = original["meshes"][0]["primitives"][0]
        output_primitive = output["meshes"][-1]["primitives"][0]
        for name in ("POSITION", "JOINTS_0", "WEIGHTS_0", "NORMAL", "TEXCOORD_0"):
            self.assertEqual(output_primitive["attributes"][name], original_primitive["attributes"][name])
            np.testing.assert_array_equal(
                accessor_values(output, output_binary, output_primitive["attributes"][name]),
                accessor_values(original, original_binary, original_primitive["attributes"][name]),
            )
        self.assertEqual(
            accessor_values(output, output_binary, output_primitive["indices"]).reshape(-1).tolist(), [0, 1, 2]
        )
        self.assertEqual(
            accessor_bytes(output, output_binary, output["skins"][0]["inverseBindMatrices"], 64),
            accessor_bytes(original, original_binary, original["skins"][0]["inverseBindMatrices"], 64),
        )
        self.assertEqual(source.read_bytes(), raw)
        collection, _ = load_glb(self.root / "rigged-output" / "_garments.glb")
        self.assertEqual(collection["skins"], original["skins"])
        entry["review_state"] = "confirmed"
        entry["cloth"] = dict(kind="cape", box=[0, 0, -0.1, 1.2, 1.2, 0.3], columns=8, rows=6)
        limited = split(
            dict(
                schema_version=1,
                source=str(source),
                source_sha256=geometry.sha256,
                output=str(self.root / "rigged-cloth"),
                items=[entry],
            )
        )
        self.assertEqual(limited["status"], "capability_limited")
        self.assertEqual(limited["items"][0]["cloth"]["state"], "preparation_failed")
        self.assertTrue((self.root / "rigged-cloth" / "cape.glb").is_file())

    def test_normalized_uint16_skin_weights_are_accepted(self):
        source = self.root / "normalized-rigged.glb"
        make_glb(source, skin=True, normalized_weights=True)
        geometry = GarmentSource(source)
        self.assertTrue(geometry.rigged)
        component = geometry.inspection()["components"][0]["component_id"]
        result = split(
            dict(
                schema_version=1,
                source=str(source),
                source_sha256=geometry.sha256,
                output=str(self.root / "normalized-output"),
                items=[item("cape", [component])],
            )
        )
        self.assertEqual(result["status"], "surface_split")
        self.assertTrue(result["skin_weights_preserved"])

    def test_reviewed_triangle_selection_is_explicit_and_auditable(self):
        reviewed = item("cape", [], review_state="confirmed")
        reviewed["selection"] = dict(mode="reviewed_triangles", primitives=[dict(node=0, primitive=0, triangles=[1])])
        result = split(self.spec([reviewed], "reviewed"))
        record = result["items"][0]
        self.assertEqual(record["source_primitives"][0]["source_triangles"], [1])
        document, _binary = load_glb(self.root / "reviewed" / "cape.glb")
        position = document["accessors"][0]
        self.assertEqual(position["min"][0], 3.0)
        reviewed["review_state"] = "automatic"
        with self.assertRaisesRegex(ValueError, "confirmation_required"):
            split(self.spec([reviewed], "not-confirmed"))

    def test_unknown_overlap_out_of_range_and_empty_choices_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "unknown_component"):
            split(self.spec([item("cape", ["cmp_" + "0" * 64])], "unknown"))
        with self.assertRaisesRegex(ValueError, "owned_by_another"):
            split(
                self.spec(
                    [
                        item("cape", [self.components[0]["component_id"]]),
                        item("armor", [self.components[0]["component_id"]]),
                    ],
                    "overlap",
                )
            )
        reviewed = item("cape", [], review_state="confirmed")
        reviewed["selection"] = dict(mode="reviewed_triangles", primitives=[dict(node=0, primitive=0, triangles=[99])])
        with self.assertRaisesRegex(ValueError, "out_of_range"):
            split(self.spec([reviewed], "range"))
        with self.assertRaisesRegex(ValueError, "selection_empty"):
            split(self.spec([], "empty"))

    def test_rigged_transformed_external_and_changed_sources_are_rejected(self):
        cases = (
            (dict(invalid_skin=True), "skin_invalid"),
            (dict(transform=True), "transform_unsupported"),
            (dict(external=True), "external_dependency"),
        )
        for options, code in cases:
            with self.subTest(code=code):
                path = self.root / (code + ".glb")
                make_glb(path, **options)
                with self.assertRaisesRegex(ValueError, code):
                    GarmentSource(path)
        spec = self.spec([item("cape", [self.components[0]["component_id"]])], "changed")
        spec["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source_changed"):
            split(spec)

    def test_inventory_is_open_vocabulary_but_strictly_validated(self):
        document = dict(schema_version=1, items=[inventory("cape", [])], non_garments=[], notes="")
        self.assertEqual(validate_inventory(document)["items"][0]["label"], "披风")
        unknown = copy.deepcopy(document)
        unknown["items"][0]["component_ids"] = ["cmp_" + "0" * 64]
        with self.assertRaisesRegex(ValueError, "unknown_component"):
            validate_inventory(unknown, {self.components[0]["component_id"]})
        invalid = copy.deepcopy(document)
        invalid["items"][0]["confidence"] = 1.1
        with self.assertRaisesRegex(ValueError, "inventory_invalid"):
            validate_inventory(invalid)
        duplicate = copy.deepcopy(document)
        duplicate["items"].append(copy.deepcopy(duplicate["items"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate_id"):
            validate_inventory(duplicate)

    def test_inventory_spec_preserves_unresolved_and_review_states(self):
        inspection = self.geometry.inspection()
        document = dict(
            schema_version=1,
            items=[
                inventory("cape", [self.components[0]["component_id"]]),
                inventory("armor", [], needs_review=True),
            ],
            non_garments=[dict(label="sword", reason="held prop")],
            notes="",
        )
        spec = spec_from_inventory(self.source, self.root / "derived", document, inspection)
        self.assertEqual(spec["unresolved_items"], ["armor"])
        self.assertEqual(spec["items"][0]["review_state"], "automatic")
        confirmed = spec_from_inventory(self.source, self.root / "derived", document, inspection, confirmed=True)
        self.assertEqual(confirmed["items"][0]["review_state"], "confirmed")
        result = split(spec)
        self.assertEqual(result["status"], "capability_limited")
        self.assertEqual(result["items"][0]["review_state"], "automatic")
        self.assertFalse(result["items"][0]["visual_review_passed"])

    def test_cape_cloth_preparation_is_not_dynamic_acceptance(self):
        source = self.root / "cape-source.glb"
        raw = make_cape(source)
        geometry = GarmentSource(source)
        component = geometry.inspection()["components"][0]["component_id"]
        entry = item("cape", [component], review_state="confirmed")
        entry["cloth"] = dict(kind="cape", box=[0, 0, -0.1, 1.2, 1.2, 0.3], columns=8, rows=6)
        spec = dict(
            schema_version=1,
            source=str(source),
            source_sha256=geometry.sha256,
            output=str(self.root / "cloth"),
            items=[entry],
        )
        result = split(spec)
        record = result["items"][0]
        self.assertEqual(record["state"], "cloth_prepared")
        self.assertEqual(record["cloth"]["state"], "cloth_prepared")
        self.assertTrue(record["cloth"]["dynamic_acceptance_required"])
        self.assertFalse(record["cloth_ready"])
        self.assertFalse(result["cloth_ready"])
        binding = json.loads((self.root / "cloth" / "cape.cloth.json").read_text())
        self.assertEqual(binding["source_sha256"], record["sha256"])
        self.assertIn("reconstruction_error", binding)
        self.assertEqual(source.read_bytes(), raw)
        entry["review_state"] = "automatic"
        spec["output"] = str(self.root / "unconfirmed-cloth")
        with self.assertRaisesRegex(ValueError, "confirmation_required"):
            split(spec)

    def test_sparse_cloth_failure_preserves_surface_split(self):
        source = self.root / "sparse-cape.glb"
        make_cape(source, columns=5, rows=5)
        geometry = GarmentSource(source)
        component = geometry.inspection()["components"][0]["component_id"]
        entry = item("sparse", [component], review_state="confirmed")
        entry["cloth"] = dict(kind="cape", box=[0, 0, -0.1, 1.2, 1.2, 0.3], columns=8, rows=6)
        result = split(
            dict(
                schema_version=1,
                source=str(source),
                source_sha256=geometry.sha256,
                output=str(self.root / "sparse-output"),
                items=[entry],
            )
        )
        self.assertEqual(result["status"], "capability_limited")
        self.assertEqual(result["items"][0]["state"], "surface_split")
        self.assertEqual(result["items"][0]["cloth"]["state"], "preparation_failed")
        self.assertFalse(result["cloth_ready"])
        self.assertTrue((self.root / "sparse-output" / "sparse.glb").is_file())
        self.assertTrue(result["unresolved"])


class GarmentInventoryRequestTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source.glb"
        make_glb(self.source)
        self.inspection = GarmentSource(self.source).inspection()
        self.image = self.root / "preview.png"
        self.image.write_bytes(png())
        self.config = dict(endpoint="https://planner.example.com", model="vision-test", key_env="TEST_VISION_KEY")

    def tearDown(self):
        self.temporary.cleanup()

    def fake_perform(self, document):
        def perform(_config, directory):
            raw = (directory / "api-request.json").read_bytes()
            (directory / "api-plan.json").write_text(canonical(document), encoding="utf-8")
            (directory / "api-receipt.json").write_text(
                canonical(
                    dict(
                        request_sha256=hashlib.sha256(raw).hexdigest(),
                        instructions_sha256=hashlib.sha256(canonical(document).encode()).hexdigest(),
                    )
                ),
                encoding="utf-8",
            )

        return perform

    def test_component_response_requires_attached_visual_evidence(self):
        selected = self.inspection["components"][0]["component_id"]
        document = dict(schema_version=1, items=[inventory("cape", [selected])], non_garments=[], notes="")
        with patch("garment_inventory.perform", self.fake_perform(document)):
            result = request_inventory(
                self.config,
                self.inspection,
                [dict(path=self.image, label="front", component_id=selected)],
                self.root / "request",
            )
        self.assertEqual(result["items"][0]["component_ids"], [selected])
        receipt = json.loads((self.root / "request" / "inventory-receipt.json").read_text())
        self.assertEqual(receipt["status"], "recognized")
        self.assertFalse(receipt["human_confirmed"])
        prompt = (self.root / "request" / "prompt.txt").read_text()
        self.assertNotIn(str(self.source), prompt)
        self.assertIn(selected, prompt)

        other = self.inspection["components"][1]["component_id"]
        invalid = dict(schema_version=1, items=[inventory("cape", [other])], non_garments=[], notes="")
        with patch("garment_inventory.perform", self.fake_perform(invalid)):
            with self.assertRaisesRegex(ValueError, "evidence_missing"):
                request_inventory(
                    self.config,
                    self.inspection,
                    [dict(path=self.image, label="front", component_id=selected)],
                    self.root / "request-invalid",
                )

    def test_receipt_mismatch_is_not_accepted(self):
        selected = self.inspection["components"][0]["component_id"]
        document = dict(schema_version=1, items=[inventory("cape", [selected])], non_garments=[], notes="")

        def bad_receipt(_config, directory):
            self.fake_perform(document)(_config, directory)
            receipt = json.loads((directory / "api-receipt.json").read_text())
            receipt["request_sha256"] = "0" * 64
            (directory / "api-receipt.json").write_text(canonical(receipt))

        with patch("garment_inventory.perform", bad_receipt):
            with self.assertRaisesRegex(ValueError, "response_invalid"):
                request_inventory(
                    self.config,
                    self.inspection,
                    [dict(path=self.image, label="front", component_id=selected)],
                    self.root / "bad-receipt",
                )


if __name__ == "__main__":
    unittest.main()
