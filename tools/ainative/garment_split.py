"""Traceable garment-surface extraction from an immutable, static GLB.

The tool separates semantic recognition, source-triangle selection and cloth
preparation. It does not reconstruct a hidden body, repair arbitrary topology,
or mark a prepared cloth binding as dynamically accepted.
"""

import argparse
import copy
import hashlib
import json
import math
import re
import shutil
import struct
from pathlib import Path

import numpy as np

from extensions import canonical
from geometry_repair import accessor_values, load_glb

CATEGORIES = ("garment", "armor", "accessory")
SLOTS = (
    "head",
    "upper_body",
    "lower_body",
    "full_body",
    "back",
    "waist",
    "arm_left",
    "arm_right",
    "hand_left",
    "hand_right",
    "leg_left",
    "leg_right",
    "foot_left",
    "foot_right",
    "other",
)
BEHAVIORS = ("rigid", "skinned", "cloth", "mixed")
REVIEW_STATES = ("automatic", "needs_review", "confirmed")
ID_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?")
DTYPES = {
    5120: "<i1",
    5121: "<u1",
    5122: "<i2",
    5123: "<u2",
    5125: "<u4",
    5126: "<f4",
}
COMPONENT_TYPES = {np.dtype(value): key for key, value in DTYPES.items()}
TYPE_WIDTHS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def _text(value, code="garment_split_spec_invalid", limit=512):
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or value != value.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValueError(code)
    return value


def _identifier(value):
    if not isinstance(value, str) or ID_PATTERN.fullmatch(value) is None:
        raise ValueError("garment_split_item_id_invalid")
    return value


def _number(value, code="garment_split_spec_invalid"):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(code)
    return float(value)


def _integer(value, code="garment_split_spec_invalid"):
    number = _number(value, code)
    if not number.is_integer():
        raise ValueError(code)
    return int(number)


def _write_new(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        with path.open("xb") as stream:
            stream.write(data)
    else:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(data)


def _identity_node(node):
    identity = (
        "matrix" not in node
        or len(node["matrix"]) == 16
        and np.allclose(
            node["matrix"],
            [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
            rtol=0,
            atol=1e-12,
        )
    )
    for key, expected in (("translation", [0, 0, 0]), ("rotation", [0, 0, 0, 1]), ("scale", [1, 1, 1])):
        if key in node and (
            len(node[key]) != len(expected) or not np.allclose(node[key], expected, rtol=0, atol=1e-12)
        ):
            return False
    return bool(identity)


def _encode_glb(document, binary):
    encoded = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded += b" " * (-len(encoded) % 4)
    payload = bytes(binary) + b"\0" * (-len(binary) % 4)
    result = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(encoded) + 8 + len(payload))
    result += struct.pack("<II", len(encoded), 0x4E4F534A) + encoded
    result += struct.pack("<II", len(payload), 0x004E4942) + payload
    return result


class GarmentSource:
    """Validated static or rigged geometry with stable connected components."""

    def __init__(self, path):
        self.path = Path(path).resolve()
        self.raw = self.path.read_bytes()
        if len(self.raw) < 20 or struct.unpack_from("<I", self.raw, 4)[0] != 2:
            raise ValueError("garment_split_source_invalid")
        self.sha256 = hashlib.sha256(self.raw).hexdigest()
        self.document, self.binary = load_glb(self.path)
        self.rigged = bool(self.document.get("skins"))
        buffers = self.document.get("buffers")
        if not isinstance(buffers, list) or len(buffers) != 1 or "uri" in buffers[0]:
            raise ValueError("garment_split_external_dependency")
        self._validate_views()

        def embedded_dependencies(value):
            if isinstance(value, dict):
                if "uri" in value and (
                    not isinstance(value["uri"], str) or not value["uri"].startswith("data:")
                ):
                    raise ValueError("garment_split_external_dependency")
                for child in value.values():
                    embedded_dependencies(child)
            elif isinstance(value, list):
                for child in value:
                    embedded_dependencies(child)

        embedded_dependencies(self.document)
        self.parents = {
            child: index
            for index, node in enumerate(self.document.get("nodes", []))
            for child in node.get("children", [])
        }
        self.primitives = {}
        self.components = []
        self._read_geometry()
        if self.rigged:
            self._validate_skins()

    def _validate_views(self):
        for view in self.document.get("bufferViews", []):
            if view.get("buffer", 0) != 0:
                raise ValueError("garment_split_external_dependency")
            start = view.get("byteOffset", 0)
            length = view.get("byteLength")
            if (
                type(start) is not int
                or type(length) is not int
                or start < 0
                or length < 0
                or start + length > len(self.binary)
            ):
                raise ValueError("garment_split_source_invalid")
        for accessor in self.document.get("accessors", []):
            if "sparse" in accessor:
                raise ValueError("garment_split_sparse_accessor_unsupported")

    def _assert_identity(self, node_index):
        visited = set()
        current = node_index
        while True:
            if current in visited:
                raise ValueError("garment_split_source_hierarchy_invalid")
            visited.add(current)
            node = self.document["nodes"][current]
            if not _identity_node(node):
                raise ValueError("garment_split_transform_unsupported")
            if current not in self.parents:
                return
            current = self.parents[current]

    def accessor(self, index, expected=None):
        return np.asarray(accessor_values(self.document, self.binary, index, expected)).copy()

    def _read_geometry(self):
        nodes = self.document.get("nodes", [])
        meshes = self.document.get("meshes", [])
        for node_index, node in enumerate(nodes):
            if "mesh" not in node:
                continue
            if not self.rigged:
                self._assert_identity(node_index)
            if type(node["mesh"]) is not int or not 0 <= node["mesh"] < len(meshes):
                raise ValueError("garment_split_source_invalid")
            mesh = meshes[node["mesh"]]
            for primitive_index, primitive in enumerate(mesh.get("primitives", [])):
                if primitive.get("mode", 4) != 4 or primitive.get("extensions") or primitive.get("targets"):
                    raise ValueError("garment_split_primitive_unsupported")
                attributes = primitive.get("attributes", {})
                if "POSITION" not in attributes:
                    raise ValueError("garment_split_source_invalid")
                points = self.accessor(attributes["POSITION"], "VEC3")
                if points.dtype != np.dtype("<f4") or not np.isfinite(points).all() or not len(points):
                    raise ValueError("garment_split_source_invalid")
                if "indices" in primitive:
                    indices = self.accessor(primitive["indices"], "SCALAR").reshape(-1)
                    if len(indices) % 3:
                        raise ValueError("garment_split_source_invalid")
                    faces = indices.astype(np.int64).reshape(-1, 3)
                else:
                    if len(points) % 3:
                        raise ValueError("garment_split_source_invalid")
                    faces = np.arange(len(points), dtype=np.int64).reshape(-1, 3)
                if not len(faces) or faces.min() < 0 or faces.max() >= len(points):
                    raise ValueError("garment_split_source_invalid")
                key = (node_index, primitive_index)
                self.primitives[key] = dict(
                    node=node_index,
                    primitive=primitive_index,
                    mesh=node["mesh"],
                    node_name=node.get("name", "node-" + str(node_index)),
                    mesh_name=mesh.get("name", "mesh-" + str(node["mesh"])),
                    points=points,
                    faces=faces,
                    source=primitive,
                )
                self._add_components(key)
        if not self.primitives:
            raise ValueError("garment_split_mesh_missing")

    def _validate_skins(self):
        nodes = self.document.get("nodes", [])
        skins = self.document.get("skins", [])
        for skin in skins:
            if not isinstance(skin, dict) or not isinstance(skin.get("joints"), list) or not skin["joints"]:
                raise ValueError("garment_split_skin_invalid")
            if any(type(joint) is not int or not 0 <= joint < len(nodes) for joint in skin["joints"]):
                raise ValueError("garment_split_skin_invalid")
            if "skeleton" in skin and (
                type(skin["skeleton"]) is not int or not 0 <= skin["skeleton"] < len(nodes)
            ):
                raise ValueError("garment_split_skin_invalid")
            if "inverseBindMatrices" in skin:
                accessor = self.document["accessors"][skin["inverseBindMatrices"]]
                if (
                    accessor.get("componentType") != 5126
                    or accessor.get("type") != "MAT4"
                    or accessor.get("count", 0) < len(skin["joints"])
                ):
                    raise ValueError("garment_split_skin_invalid")
        linked = 0
        for node_index, node in enumerate(nodes):
            if "mesh" not in node:
                continue
            has_skin = "skin" in node
            if has_skin and (type(node["skin"]) is not int or not 0 <= node["skin"] < len(skins)):
                raise ValueError("garment_split_skin_invalid")
            mesh = self.document["meshes"][node["mesh"]]
            for primitive_index, primitive in enumerate(mesh.get("primitives", [])):
                attributes = primitive.get("attributes", {})
                has_joints = "JOINTS_0" in attributes or "WEIGHTS_0" in attributes
                if has_skin or has_joints:
                    if not has_skin or "JOINTS_0" not in attributes or "WEIGHTS_0" not in attributes:
                        raise ValueError("garment_split_skin_invalid")
                    joint_values = self.accessor(attributes["JOINTS_0"], "VEC4")
                    weight_values = self.accessor(attributes["WEIGHTS_0"], "VEC4")
                    points = self.primitives[(node_index, primitive_index)]["points"]
                    if len(joint_values) != len(points) or len(weight_values) != len(points):
                        raise ValueError("garment_split_skin_invalid")
                    joint_accessor = self.document["accessors"][attributes["JOINTS_0"]]
                    weight_accessor = self.document["accessors"][attributes["WEIGHTS_0"]]
                    if joint_accessor.get("componentType") not in (5121, 5123, 5125):
                        raise ValueError("garment_split_skin_invalid")
                    if (
                        weight_accessor.get("componentType") not in (5121, 5123, 5126)
                        or weight_accessor.get("componentType") in (5121, 5123)
                        and weight_accessor.get("normalized") is not True
                    ):
                        raise ValueError("garment_split_skin_invalid")
                    weights = weight_values.astype(np.float64)
                    if weight_accessor.get("componentType") in (5121, 5123):
                        weights /= 255.0 if weight_accessor["componentType"] == 5121 else 65535.0
                    if (
                        not np.isfinite(joint_values).all()
                        or not np.isfinite(weight_values).all()
                        or (joint_values < 0).any()
                        or (weight_values < 0).any()
                    ):
                        raise ValueError("garment_split_skin_invalid")
                    skin = skins[node["skin"]]
                    if joint_values.max() >= len(skin["joints"]):
                        raise ValueError("garment_split_skin_invalid")
                    if not np.allclose(weights.sum(axis=1), 1.0, rtol=0, atol=1e-4):
                        raise ValueError("garment_split_skin_invalid")
                    linked += 1
        if not linked:
            raise ValueError("garment_split_skin_invalid")

    def _add_components(self, key):
        geometry = self.primitives[key]
        points, faces = geometry["points"], geometry["faces"]
        parents = list(range(len(points)))

        def root(index):
            while parents[index] != index:
                parents[index] = parents[parents[index]]
                index = parents[index]
            return index

        for a, b, c in faces:
            parent = root(int(a))
            parents[root(int(b))] = parent
            parents[root(int(c))] = parent
        face_roots = np.asarray([root(int(face[0])) for face in faces])
        groups = {}
        for face_index, value in enumerate(face_roots):
            groups.setdefault(int(value), []).append(face_index)
        ordered = sorted(groups.values(), key=lambda values: values[0])
        for component_index, face_ids in enumerate(ordered):
            face_ids = np.asarray(face_ids, dtype=np.int64)
            digest = hashlib.sha256()
            digest.update(self.sha256.encode("ascii"))
            digest.update(struct.pack("<III", key[0], key[1], component_index))
            digest.update(face_ids.astype("<u4").tobytes())
            component_id = "cmp_" + digest.hexdigest()
            used = np.unique(faces[face_ids])
            selected = points[used]
            self.components.append(
                dict(
                    component_id=component_id,
                    node=key[0],
                    primitive=key[1],
                    component_index=component_index,
                    node_name=geometry["node_name"],
                    mesh_name=geometry["mesh_name"],
                    material=geometry["source"].get("material"),
                    vertex_count=len(used),
                    triangle_count=len(face_ids),
                    bounds_min=selected.min(axis=0).astype(float).tolist(),
                    bounds_max=selected.max(axis=0).astype(float).tolist(),
                    _face_ids=face_ids,
                )
            )

    def inspection(self):
        def clean(value):
            if isinstance(value, dict):
                return {key: clean(child) for key, child in value.items() if not key.startswith("_")}
            if isinstance(value, list):
                return [clean(child) for child in value]
            if isinstance(value, np.integer):
                return int(value)
            return value

        return clean(
            dict(
                schema_version=1,
                source=str(self.path),
                source_sha256=self.sha256,
                coordinate_space="Y_up_source_coordinates",
                topology="vertex_connected_components_per_primitive",
                static=not self.rigged,
                rigged=self.rigged,
                skins=self.rigged,
                node_transforms_preserved=self.rigged,
                primitive_count=len(self.primitives),
                component_count=len(self.components),
                components=self.components,
                limitations=[
                    "Component IDs describe connectivity, not semantic garment boundaries.",
                    "Fused garment and body surfaces require reviewed source-triangle selection.",
                ],
            )
        )

    def component_map(self):
        return {component["component_id"]: component for component in self.components}


def validate_inventory(value, known_components=None):
    """Validate open-vocabulary AI output without treating it as human review."""
    if not isinstance(value, dict) or set(value) != {"schema_version", "items", "non_garments", "notes"}:
        raise ValueError("garment_inventory_invalid")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("garment_inventory_invalid")
    if not isinstance(value["items"], list) or not isinstance(value["non_garments"], list):
        raise ValueError("garment_inventory_invalid")
    if (
        not isinstance(value["notes"], str)
        or len(value["notes"]) > 4096
        or any(ord(character) < 32 and character not in "\n\t" for character in value["notes"])
    ):
        raise ValueError("garment_inventory_invalid")
    result = copy.deepcopy(value)
    identifiers = set()
    for item in result["items"]:
        fields = {"id", "label", "category", "slot", "behavior", "confidence", "component_ids", "evidence", "needs_review"}
        if not isinstance(item, dict) or set(item) != fields:
            raise ValueError("garment_inventory_invalid")
        _identifier(item["id"])
        if item["id"] in identifiers:
            raise ValueError("garment_inventory_duplicate_id")
        identifiers.add(item["id"])
        _text(item["label"], "garment_inventory_invalid", 256)
        _text(item["evidence"], "garment_inventory_invalid", 2048)
        if item["category"] not in CATEGORIES or item["slot"] not in SLOTS or item["behavior"] not in BEHAVIORS:
            raise ValueError("garment_inventory_invalid")
        confidence = _number(item["confidence"], "garment_inventory_invalid")
        if not 0 <= confidence <= 1 or not isinstance(item["needs_review"], bool):
            raise ValueError("garment_inventory_invalid")
        components = item["component_ids"]
        if (
            not isinstance(components, list)
            or any(not isinstance(component, str) or not component.startswith("cmp_") for component in components)
            or len(set(components)) != len(components)
        ):
            raise ValueError("garment_inventory_components_invalid")
        for component in components:
            if known_components is not None and component not in known_components:
                raise ValueError("garment_inventory_unknown_component")
    for item in result["non_garments"]:
        if not isinstance(item, dict) or set(item) != {"label", "reason"}:
            raise ValueError("garment_inventory_invalid")
        _text(item["label"], "garment_inventory_invalid", 256)
        _text(item["reason"], "garment_inventory_invalid", 2048)
    return result


def _validate_cloth(value, review_state, behavior):
    if not isinstance(value, dict) or not {"kind", "box"} <= set(value):
        raise ValueError("garment_split_cloth_invalid")
    if set(value) - {"kind", "box", "columns", "rows", "cloth_top"}:
        raise ValueError("garment_split_cloth_invalid")
    if value["kind"] not in ("cape", "skirt") or behavior not in ("cloth", "mixed"):
        raise ValueError("garment_split_cloth_invalid")
    if review_state != "confirmed":
        raise ValueError("garment_split_cloth_confirmation_required")
    if not isinstance(value["box"], list) or len(value["box"]) != 6:
        raise ValueError("garment_split_cloth_invalid")
    box = [_number(component, "garment_split_cloth_invalid") for component in value["box"]]
    if any(component <= 0 for component in box[3:]):
        raise ValueError("garment_split_cloth_invalid")
    for key in ("columns", "rows"):
        if key in value:
            value[key] = _integer(value[key], "garment_split_cloth_invalid")
            if not 4 <= value[key] <= 128:
                raise ValueError("garment_split_cloth_invalid")
    if "cloth_top" in value:
        _number(value["cloth_top"], "garment_split_cloth_invalid")


def _validate_item(item):
    required = {"id", "label", "category", "slot", "behavior", "confidence", "review_state", "selection"}
    if not isinstance(item, dict) or not required <= set(item) or set(item) - required - {"cloth"}:
        raise ValueError("garment_split_spec_invalid")
    _identifier(item["id"])
    _text(item["label"], limit=256)
    if item["category"] not in CATEGORIES or item["slot"] not in SLOTS or item["behavior"] not in BEHAVIORS:
        raise ValueError("garment_split_spec_invalid")
    confidence = _number(item["confidence"])
    if not 0 <= confidence <= 1 or item["review_state"] not in REVIEW_STATES:
        raise ValueError("garment_split_spec_invalid")
    selection = item["selection"]
    if not isinstance(selection, dict) or "mode" not in selection:
        raise ValueError("garment_split_selection_invalid")
    if selection["mode"] == "components":
        if set(selection) != {"mode", "component_ids"} or not isinstance(selection["component_ids"], list):
            raise ValueError("garment_split_selection_invalid")
        if not selection["component_ids"] or len(set(selection["component_ids"])) != len(selection["component_ids"]):
            raise ValueError("garment_split_selection_invalid")
        for component in selection["component_ids"]:
            if not isinstance(component, str) or not component.startswith("cmp_"):
                raise ValueError("garment_split_selection_invalid")
    elif selection["mode"] == "reviewed_triangles":
        if set(selection) != {"mode", "primitives"} or item["review_state"] != "confirmed":
            raise ValueError("garment_split_review_confirmation_required")
        if not isinstance(selection["primitives"], list) or not selection["primitives"]:
            raise ValueError("garment_split_selection_invalid")
        for primitive in selection["primitives"]:
            if not isinstance(primitive, dict) or set(primitive) != {"node", "primitive", "triangles"}:
                raise ValueError("garment_split_selection_invalid")
            primitive["node"] = _integer(primitive["node"], "garment_split_selection_invalid")
            primitive["primitive"] = _integer(primitive["primitive"], "garment_split_selection_invalid")
            triangles = primitive["triangles"]
            if not isinstance(triangles, list) or not triangles:
                raise ValueError("garment_split_selection_invalid")
            primitive["triangles"] = [
                _integer(triangle, "garment_split_selection_invalid") for triangle in triangles
            ]
            if len(set(primitive["triangles"])) != len(primitive["triangles"]) or any(
                triangle < 0 for triangle in primitive["triangles"]
            ):
                raise ValueError("garment_split_selection_invalid")
    else:
        raise ValueError("garment_split_selection_invalid")
    if "cloth" in item:
        _validate_cloth(item["cloth"], item["review_state"], item["behavior"])


def _selected_primitives(source, item):
    selection = item["selection"]
    selected = {}

    def add(key, face_ids):
        target = selected.setdefault(key, set())
        for face_id in face_ids:
            if int(face_id) in target:
                raise ValueError("garment_split_duplicate_selection")
            target.add(int(face_id))

    if selection["mode"] == "components":
        components = source.component_map()
        for component_id in selection["component_ids"]:
            if component_id not in components:
                raise ValueError("garment_inventory_unknown_component")
            component = components[component_id]
            add((component["node"], component["primitive"]), component["_face_ids"])
    else:
        for primitive in selection["primitives"]:
            key = (primitive["node"], primitive["primitive"])
            if key not in source.primitives:
                raise ValueError("garment_split_primitive_missing")
            count = len(source.primitives[key]["faces"])
            if any(face_id >= count for face_id in primitive["triangles"]):
                raise ValueError("garment_split_triangle_out_of_range")
            add(key, primitive["triangles"])
    if not selected:
        raise ValueError("garment_split_selection_empty")
    return {key: np.asarray(sorted(value), dtype=np.int64) for key, value in selected.items()}


def _extension_names(values):
    result = set()
    if isinstance(values, dict):
        for key, value in values.items():
            if key == "extensions" and isinstance(value, dict):
                result.update(value)
            else:
                result.update(_extension_names(value))
    elif isinstance(values, list):
        for value in values:
            result.update(_extension_names(value))
    return result


def _build_rigged_glb(source, item, selected):
    """Replace only index buffers while preserving the complete original rig."""
    document = copy.deepcopy(source.document)
    binary = bytearray(source.binary)
    document.setdefault("asset", {})["generator"] = "AINative rig-preserving garment surface split"
    original_meshes = copy.deepcopy(source.document["meshes"])
    document["meshes"] = copy.deepcopy(original_meshes)
    source_map = []
    output_triangles = 0
    output_vertices = 0

    def append_indices(faces):
        nonlocal binary
        while len(binary) % 4:
            binary.append(0)
        values = np.asarray(faces, dtype="<u4").reshape(-1)
        view = dict(buffer=0, byteOffset=len(binary), byteLength=values.nbytes, target=34963)
        binary.extend(values.tobytes())
        document["bufferViews"].append(view)
        document["accessors"].append(
            dict(
                bufferView=len(document["bufferViews"]) - 1,
                componentType=5125,
                count=len(values),
                type="SCALAR",
            )
        )
        return len(document["accessors"]) - 1

    for node_index, node in enumerate(document.get("nodes", [])):
        if "mesh" not in node:
            continue
        selected_primitives = [
            (primitive_index, selected[(node_index, primitive_index)])
            for primitive_index in range(len(original_meshes[node["mesh"]]["primitives"]))
            if (node_index, primitive_index) in selected
        ]
        if not selected_primitives:
            node.pop("mesh", None)
            node.pop("skin", None)
            continue
        original_mesh = original_meshes[node["mesh"]]
        primitives = []
        for primitive_index, face_ids in selected_primitives:
            primitive = copy.deepcopy(original_mesh["primitives"][primitive_index])
            faces = source.primitives[(node_index, primitive_index)]["faces"][face_ids]
            primitive["indices"] = append_indices(faces)
            primitives.append(primitive)
            output_triangles += len(faces)
            output_vertices += len(np.unique(faces))
            source_map.append(
                dict(
                    node=node_index,
                    primitive=primitive_index,
                    source_triangles=face_ids.astype(int).tolist(),
                )
            )
        node["mesh"] = len(document["meshes"])
        document["meshes"].append(
            dict(name=item["id"] + "-" + original_mesh.get("name", "mesh"), primitives=primitives)
        )
    document["buffers"][0]["byteLength"] = len(binary)
    extras = document.setdefault("asset", {}).setdefault("extras", {})
    extras.pop("maliang_head_review", None)
    extras["maliang_garment_split"] = dict(
        schema_version=1,
        operation="extract_visible_garment_surface_preserve_rig",
        item_id=item["id"],
        label=item["label"],
        behavior=item["behavior"],
        review_state=item["review_state"],
        source_sha256=source.sha256,
        selection_mode=item["selection"]["mode"],
        source_primitives=source_map,
        source_not_overwritten=True,
        rigged=True,
        skeleton_preserved=True,
        skin_weights_preserved=True,
        inverse_bind_matrices_preserved=True,
        unreferenced_source_vertices_retained=True,
        hidden_body_reconstructed=False,
        visual_review_passed=False,
        cloth_ready=False,
    )
    return _encode_glb(document, binary), source_map, output_vertices, output_triangles


def _build_glb(source, item, selected):
    if source.rigged:
        return _build_rigged_glb(source, item, selected)
    document = dict(
        asset=dict(version="2.0", generator="AINative traceable garment surface split"),
        scene=0,
        scenes=[dict(nodes=[])],
        nodes=[],
        meshes=[],
        buffers=[dict(byteLength=0)],
        bufferViews=[],
        accessors=[],
    )
    for key in ("samplers", "textures", "materials"):
        if key in source.document:
            document[key] = copy.deepcopy(source.document[key])
    images = copy.deepcopy(source.document.get("images", []))
    binary = bytearray()

    def append_view(data, target=None):
        while len(binary) % 4:
            binary.append(0)
        view = dict(buffer=0, byteOffset=len(binary), byteLength=len(data))
        if target is not None:
            view["target"] = target
        binary.extend(data)
        document["bufferViews"].append(view)
        return len(document["bufferViews"]) - 1

    for image in images:
        if "bufferView" not in image:
            continue
        view = source.document["bufferViews"][image["bufferView"]]
        start = view.get("byteOffset", 0)
        image["bufferView"] = append_view(source.binary[start : start + view["byteLength"]])
    if images:
        document["images"] = images
    extensions = _extension_names(document.get("materials", [])) | _extension_names(document.get("textures", []))
    if extensions:
        document["extensionsUsed"] = sorted(extensions)
        required = set(source.document.get("extensionsRequired", [])) & extensions
        if required:
            document["extensionsRequired"] = sorted(required)

    def append_accessor(values, target, normalized=False):
        values = np.asarray(values)
        if values.ndim == 1:
            values = values.reshape(-1, 1)
        dtype = values.dtype.newbyteorder("<")
        if dtype not in COMPONENT_TYPES:
            raise ValueError("garment_split_attribute_unsupported")
        values = np.ascontiguousarray(values.astype(dtype, copy=False))
        if dtype == np.dtype("<f4") and not np.isfinite(values).all():
            raise ValueError("garment_split_output_invalid")
        component_type = COMPONENT_TYPES[dtype]
        width = values.shape[1]
        if width not in TYPE_WIDTHS.values():
            raise ValueError("garment_split_attribute_unsupported")
        view = append_view(values.tobytes(), target)
        accessor = dict(
            bufferView=view,
            componentType=component_type,
            count=len(values),
            type=next(key for key, size in TYPE_WIDTHS.items() if size == width),
        )
        if normalized:
            accessor["normalized"] = True
        document["accessors"].append(accessor)
        return len(document["accessors"]) - 1

    source_map = []
    output_triangles = 0
    output_vertices = 0
    for (node_index, primitive_index), face_ids in sorted(selected.items()):
        geometry = source.primitives[(node_index, primitive_index)]
        source_primitive = geometry["source"]
        faces = geometry["faces"][face_ids]
        for face in faces:
            points = geometry["points"][face]
            if len(set(int(index) for index in face)) != 3:
                raise ValueError("garment_split_degenerate_triangle")
            if np.linalg.norm(np.cross(points[1] - points[0], points[2] - points[0])) <= 1e-20:
                raise ValueError("garment_split_degenerate_triangle")
        used = np.unique(faces)
        remap = np.full(len(geometry["points"]), -1, dtype=np.int64)
        remap[used] = np.arange(len(used))
        remapped = remap[faces].astype("<u4")
        output_primitive = dict(attributes={}, indices=0)
        for name, accessor_index in source_primitive["attributes"].items():
            source_accessor = source.document["accessors"][accessor_index]
            values = source.accessor(accessor_index)[used]
            output_primitive["attributes"][name] = append_accessor(
                values, 34962, source_accessor.get("normalized") is True
            )
            if name == "POSITION":
                document["accessors"][output_primitive["attributes"][name]].update(
                    min=values.min(axis=0).astype(float).tolist(),
                    max=values.max(axis=0).astype(float).tolist(),
                )
        output_primitive["indices"] = append_accessor(remapped.reshape(-1), 34963)
        if "material" in source_primitive:
            output_primitive["material"] = source_primitive["material"]
        mesh_index = len(document["meshes"])
        document["meshes"].append(dict(name=item["id"] + "-" + geometry["mesh_name"], primitives=[output_primitive]))
        output_node = len(document["nodes"])
        document["nodes"].append(dict(name=item["id"] + "-" + geometry["node_name"], mesh=mesh_index))
        document["scenes"][0]["nodes"].append(output_node)
        source_map.append(
            dict(node=node_index, primitive=primitive_index, source_triangles=face_ids.astype(int).tolist())
        )
        output_triangles += len(faces)
        output_vertices += len(used)
    document["buffers"][0]["byteLength"] = len(binary)
    document["asset"]["extras"] = dict(
        maliang_garment_split=dict(
            schema_version=1,
            operation="extract_visible_garment_surface",
            item_id=item["id"],
            label=item["label"],
            behavior=item["behavior"],
            review_state=item["review_state"],
            source_sha256=source.sha256,
            selection_mode=item["selection"]["mode"],
            source_primitives=source_map,
            source_not_overwritten=True,
            hidden_body_reconstructed=False,
            visual_review_passed=False,
            cloth_ready=False,
        )
    )
    return _encode_glb(document, binary), source_map, output_vertices, output_triangles


def spec_from_inventory(source_path, output, inventory, inspection, confirmed=False):
    """Convert only evidence-bound component candidates; keep other items unresolved."""
    known = {component["component_id"] for component in inspection.get("components", [])}
    inventory = validate_inventory(inventory, known)
    if inspection.get("schema_version") != 1 or inspection.get("source_sha256") != hashlib.sha256(
        Path(source_path).read_bytes()
    ).hexdigest():
        raise ValueError("garment_split_inspection_source_mismatch")
    items = []
    unresolved = []
    for entry in inventory["items"]:
        if not entry["component_ids"]:
            unresolved.append(entry["id"])
            continue
        review_state = "confirmed" if confirmed else "needs_review" if entry["needs_review"] else "automatic"
        items.append(
            dict(
                id=entry["id"],
                label=entry["label"],
                category=entry["category"],
                slot=entry["slot"],
                behavior=entry["behavior"],
                confidence=entry["confidence"],
                review_state=review_state,
                selection=dict(mode="components", component_ids=entry["component_ids"]),
            )
        )
    return dict(
        schema_version=1,
        source=str(Path(source_path).resolve()),
        source_sha256=inspection["source_sha256"],
        output=str(Path(output).resolve()),
        items=items,
        unresolved_items=unresolved,
        inventory_sha256=hashlib.sha256(canonical(inventory).encode("utf-8")).hexdigest(),
    )


def split(spec):
    required = {"schema_version", "source", "source_sha256", "output", "items"}
    if not isinstance(spec, dict) or not required <= set(spec):
        raise ValueError("garment_split_spec_invalid")
    if set(spec) - required - {"unresolved_items", "inventory_sha256"}:
        raise ValueError("garment_split_spec_invalid")
    if type(spec["schema_version"]) is not int or spec["schema_version"] != 1 or not isinstance(spec["items"], list):
        raise ValueError("garment_split_spec_invalid")
    if not spec["items"]:
        raise ValueError("garment_split_selection_empty")
    unresolved = spec.get("unresolved_items", [])
    if not isinstance(unresolved, list) or any(not isinstance(value, str) for value in unresolved):
        raise ValueError("garment_split_spec_invalid")
    for item in spec["items"]:
        _validate_item(item)
    identifiers = [item["id"] for item in spec["items"]]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("garment_split_duplicate_id")
    source = GarmentSource(spec["source"])
    if source.sha256 != spec["source_sha256"]:
        raise ValueError("garment_split_source_changed")
    selections = {}
    occupied = {}
    for item in spec["items"]:
        selected = _selected_primitives(source, item)
        for (node, primitive), face_ids in selected.items():
            for face_id in face_ids:
                identity = (node, primitive, int(face_id))
                if identity in occupied:
                    raise ValueError("garment_split_triangle_owned_by_another_item")
                occupied[identity] = item["id"]
        if "cloth" in item and len(selected) != 1:
            raise ValueError("garment_split_cloth_requires_one_primitive")
        selections[item["id"]] = selected
    output = Path(spec["output"]).resolve()
    if output.exists():
        raise ValueError("garment_split_output_exists")
    if output == source.path or source.path in output.parents:
        raise ValueError("garment_split_output_invalid")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    try:
        records = []
        capability_limited = bool(unresolved)
        unresolved_messages = ["Items without evidence-bound geometry: " + value for value in unresolved]
        for item in spec["items"]:
            data, source_map, vertices, triangles = _build_glb(source, item, selections[item["id"]])
            path = output / (item["id"] + ".glb")
            _write_new(path, data)
            loaded = GarmentSource(path)
            observed_triangles = sum(len(geometry["faces"]) for geometry in loaded.primitives.values())
            if observed_triangles != triangles:
                raise ValueError("garment_split_output_invalid")
            record = dict(
                id=item["id"],
                label=item["label"],
                category=item["category"],
                slot=item["slot"],
                behavior=item["behavior"],
                confidence=item["confidence"],
                review_state=item["review_state"],
                state="surface_split",
                path=path.name,
                sha256=hashlib.sha256(data).hexdigest(),
                vertices=vertices,
                triangles=triangles,
                selection_mode=item["selection"]["mode"],
                source_primitives=source_map,
                visual_review_passed=False,
                cloth_ready=False,
            )
            if "cloth" in item:
                from cloth_prepare import prepare

                settings = item["cloth"]
                binding_path = output / (item["id"] + ".cloth.json")
                try:
                    if source.rigged:
                        raise ValueError("garment_split_cloth_rigged_source_unsupported")
                    binding = prepare(
                        path,
                        settings["kind"],
                        settings["box"],
                        settings.get("columns", 24),
                        settings.get("rows", 16),
                        settings.get("cloth_top"),
                    )
                    encoded = json.dumps(binding, ensure_ascii=False, separators=(",", ":"))
                    _write_new(binding_path, encoded)
                    record.update(
                        state="cloth_prepared",
                        cloth=dict(
                            state="cloth_prepared",
                            kind=settings["kind"],
                            path=binding_path.name,
                            sha256=hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
                            binding_revision=binding["binding_revision"],
                            reconstruction_error=binding["reconstruction_error"],
                            dynamic_acceptance_required=True,
                        ),
                    )
                except (ValueError, IndexError, FloatingPointError) as error:
                    capability_limited = True
                    message = item["id"] + " cloth preparation: " + str(error)
                    unresolved_messages.append(message)
                    record["cloth"] = dict(state="preparation_failed", dynamic_acceptance_required=True)
            records.append(record)
        combined_selection = {}
        for selected in selections.values():
            for key, face_ids in selected.items():
                combined_selection.setdefault(key, set()).update(int(value) for value in face_ids)
        combined_selection = {
            key: np.asarray(sorted(value), dtype=np.int64) for key, value in combined_selection.items()
        }
        review_states = {item["review_state"] for item in spec["items"]}
        collection_review = (
            "needs_review"
            if "needs_review" in review_states
            else "confirmed"
            if review_states == {"confirmed"}
            else "automatic"
        )
        collection_item = dict(
            id="garment_collection",
            label="Extracted garment collection",
            behavior="mixed",
            review_state=collection_review,
            selection=dict(mode="multiple"),
        )
        collection_data, collection_map, collection_vertices, collection_triangles = _build_glb(
            source, collection_item, combined_selection
        )
        collection_path = output / "_garments.glb"
        _write_new(collection_path, collection_data)
        loaded_collection = GarmentSource(collection_path)
        if sum(len(geometry["faces"]) for geometry in loaded_collection.primitives.values()) != collection_triangles:
            raise ValueError("garment_split_output_invalid")
        collection = dict(
            path=collection_path.name,
            sha256=hashlib.sha256(collection_data).hexdigest(),
            vertices=collection_vertices,
            triangles=collection_triangles,
            source_primitives=collection_map,
        )
        if hashlib.sha256(source.path.read_bytes()).hexdigest() != source.sha256:
            raise ValueError("garment_split_source_changed")
        manifest = dict(
            schema_version=1,
            operation="extract_visible_garment_surface",
            status="capability_limited" if capability_limited else "surface_split",
            capability_limited=capability_limited,
            source=str(source.path),
            source_sha256=source.sha256,
            source_not_overwritten=True,
            rigged=source.rigged,
            skeleton_preserved=source.rigged,
            skin_weights_preserved=source.rigged,
            inverse_bind_matrices_preserved=source.rigged,
            unreferenced_source_vertices_retained=source.rigged,
            items=records,
            collection=collection,
            unresolved=unresolved_messages,
            hidden_body_reconstructed=False,
            visual_review_passed=False,
            cloth_ready=False,
            limitations=[
                "Extracted surfaces may be open and are not automatically complete wearable garments.",
                "AI review_state=automatic is not human or visual acceptance.",
                "cloth_prepared is not cloth_ready; actual animation and collision acceptance remain required.",
            ],
        )
        if source.rigged:
            manifest["limitations"].append(
                "Unreferenced source vertices are retained to preserve exact skin attributes and inverse binds; only selected triangles are rendered."
            )
        if "inventory_sha256" in spec:
            if not isinstance(spec["inventory_sha256"], str) or len(spec["inventory_sha256"]) != 64:
                raise ValueError("garment_split_spec_invalid")
            manifest["inventory_sha256"] = spec["inventory_sha256"]
        manifest["manifest_revision"] = hashlib.sha256(canonical(manifest).encode("utf-8")).hexdigest()
        _write_new(output / "split_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        return manifest
    except Exception:
        shutil.rmtree(output)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect_command = commands.add_parser("inspect")
    inspect_command.add_argument("source", type=Path)
    inspect_command.add_argument("output", type=Path)
    split_command = commands.add_parser("split")
    split_command.add_argument("spec", type=Path)
    inventory_command = commands.add_parser("inventory-spec")
    inventory_command.add_argument("source", type=Path)
    inventory_command.add_argument("inspection", type=Path)
    inventory_command.add_argument("inventory", type=Path)
    inventory_command.add_argument("output", type=Path)
    inventory_command.add_argument("spec_output", type=Path)
    inventory_command.add_argument("--confirmed", action="store_true")
    args = parser.parse_args()
    if args.command == "inspect":
        result = GarmentSource(args.source).inspection()
        _write_new(args.output, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    elif args.command == "inventory-spec":
        inspection = json.loads(args.inspection.read_text(encoding="utf-8"))
        inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
        result = spec_from_inventory(args.source, args.output, inventory, inspection, args.confirmed)
        _write_new(args.spec_output, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    else:
        result = split(json.loads(args.spec.read_text(encoding="utf-8")))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
