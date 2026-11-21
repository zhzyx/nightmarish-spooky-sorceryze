"""Deterministic local geometry repair on an immutable source GLB.

align_neck translates a named head mesh so its neck-band center meets the body
neck-band center. reshape_crown deforms only a confirmed hairline-up region of
an integrated mesh, preserving lower positions and topology. No remote generation,
Blender, texture rewrite, source overwrite, or unsupported general-editing claim.
"""

import copy
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

import numpy as np

MAX_SOURCE_BYTES = 128 * 1024 * 1024
LEGACY_BYTES = 64 * 1024 * 1024
LEGACY_VERTICES = 1_000_000
LEGACY_TRIANGLES = 2_000_000


def load_glb(path):
    data = Path(path).read_bytes()
    if not 28 <= len(data) <= MAX_SOURCE_BYTES or data[:4] != b"glTF":
        raise ValueError("geometry_repair_source_invalid")
    if struct.unpack_from("<I", data, 8)[0] != len(data):
        raise ValueError("geometry_repair_source_invalid")
    size = struct.unpack_from("<I", data, 12)[0]
    if 20 + size + 8 > len(data):
        raise ValueError("geometry_repair_source_invalid")
    document = json.loads(data[20 : 20 + size])
    binary_size, kind = struct.unpack_from("<II", data, 20 + size)
    if kind != 0x004E4942 or 28 + size + binary_size > len(data):
        raise ValueError("geometry_repair_source_invalid")
    binary = data[28 + size : 28 + size + binary_size]
    return document, binary


def write_glb(document, binary, output):
    encoded = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded += b" " * (-len(encoded) % 4)
    payload = bytes(binary) + b"\0" * (-len(binary) % 4)
    result = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(encoded) + 8 + len(payload))
    result += struct.pack("<II", len(encoded), 0x4E4F534A) + encoded
    result += struct.pack("<II", len(payload), 0x004E4942) + payload
    Path(output).write_bytes(result)
    return result


def accessor_values(document, binary, index, expected=None):
    accessor = document["accessors"][index]
    view = document["bufferViews"][accessor["bufferView"]]
    component = accessor["componentType"]
    dtype = {5126: "<f4", 5125: "<u4", 5123: "<u2", 5121: "<u1"}.get(component)
    width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}.get(accessor["type"])
    if dtype is None or width is None or expected is not None and accessor["type"] != expected:
        raise ValueError("geometry_repair_source_invalid")
    item_size = np.dtype(dtype).itemsize
    start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    return np.ndarray(
        (accessor["count"], width),
        dtype=np.dtype(dtype),
        buffer=binary,
        offset=start,
        strides=(view.get("byteStride", item_size * width), item_size),
    )


def named_mesh(document, name):
    matches = [(index, mesh) for index, mesh in enumerate(document.get("meshes", [])) if mesh.get("name") == name]
    if len(matches) != 1:
        raise ValueError("geometry_repair_mesh_missing")
    index, mesh = matches[0]
    nodes = [node for node in document.get("nodes", []) if node.get("mesh") == index]
    if len(nodes) != 1:
        raise ValueError("geometry_repair_transform_unsupported")
    node = nodes[0]
    if (
        "matrix" in node
        or "rotation" in node
        or "scale" in node
        or any(abs(float(value)) > 1e-12 for value in node.get("translation", [0, 0, 0]))
    ):
        raise ValueError("geometry_repair_transform_unsupported")
    return mesh


def positions(document, binary, mesh):
    result = []
    for primitive in mesh["primitives"]:
        if primitive.get("mode", 4) != 4:
            raise ValueError("geometry_repair_source_invalid")
        values = accessor_values(document, binary, primitive["attributes"]["POSITION"], "VEC3")
        if values.dtype != np.dtype("<f4") or not np.isfinite(values).all():
            raise ValueError("geometry_repair_source_invalid")
        result.append(values)
    if not result:
        raise ValueError("geometry_repair_mesh_missing")
    return result


def center(points, neck_y, band_height, lower):
    low = neck_y - band_height if lower else neck_y
    high = neck_y + band_height
    joined = np.concatenate(points)
    band = joined[(joined[:, 1] >= low) & (joined[:, 1] <= high)]
    if len(band) < 3:
        raise ValueError("geometry_repair_neck_band_empty")
    return np.median(band[:, [0, 2]], axis=0), len(band)


def align_neck(document, binary, spec):
    document = copy.deepcopy(document)
    binary = bytearray(binary)
    head = named_mesh(document, spec["head_mesh"])
    body = named_mesh(document, spec["body_mesh"])
    head_points = positions(document, binary, head)
    body_points = positions(document, binary, body)
    neck_y = float(spec["neck_y"])
    band_height = float(spec["band_height"])
    if not math.isfinite(neck_y) or not 0.0001 <= band_height <= 0.1:
        raise ValueError("geometry_repair_parameters_invalid")
    head_center, head_count = center(head_points, neck_y, band_height, False)
    body_center, body_count = center(body_points, neck_y, band_height, True)
    axes = spec.get("axes", ["z"])
    if not axes or set(axes) - {"x", "z"} or len(set(axes)) != len(axes):
        raise ValueError("geometry_repair_parameters_invalid")
    full_delta = body_center - head_center
    delta = {"x": 0.0, "z": 0.0}
    for index, axis in enumerate(("x", "z")):
        if axis in axes:
            delta[axis] = float(full_delta[index])
    if not math.isfinite(delta["x"] + delta["z"]) or math.hypot(delta["x"], delta["z"]) > float(
        spec["max_translation"]
    ):
        raise ValueError("geometry_repair_translation_exceeded")
    if math.hypot(delta["x"], delta["z"]) < 1e-9:
        raise ValueError("geometry_repair_already_aligned")
    changed = 0
    for values in head_points:
        values[:, 0] += np.float32(delta["x"])
        values[:, 2] += np.float32(delta["z"])
        changed += len(values)
    for primitive in head["primitives"]:
        index = primitive["attributes"]["POSITION"]
        values = accessor_values(document, binary, index, "VEC3")
        document["accessors"][index]["min"] = values.min(axis=0).tolist()
        document["accessors"][index]["max"] = values.max(axis=0).tolist()
    extras = document.setdefault("asset", {}).setdefault("extras", {})
    # Geometry changed: a prior visual approval can never be reused silently.
    extras.pop("maliang_head_review", None)
    record = dict(
        schema_version=1,
        operation="align_neck",
        source_sha256=hashlib.sha256(Path(spec["source"]).read_bytes()).hexdigest(),
        head_mesh=spec["head_mesh"],
        body_mesh=spec["body_mesh"],
        neck_y=neck_y,
        band_height=band_height,
        axes=axes,
        head_center_xz=head_center.tolist(),
        body_center_xz=body_center.tolist(),
        translation_xz=[delta["x"], delta["z"]],
        changed_vertices=changed,
        head_band_vertices=head_count,
        body_band_vertices=body_count,
        requires_new_head_review=True,
    )
    extras["maliang_geometry_repair"] = record
    return document, binary, record


def _record_repair(document, record):
    extras = document.setdefault("asset", {}).setdefault("extras", {})
    # Any position change invalidates approval of the old geometry.
    extras.pop("maliang_head_review", None)
    previous = extras.get("maliang_geometry_repair")
    if previous is not None:
        extras.setdefault("maliang_geometry_repair_history", []).append(previous)
    extras["maliang_geometry_repair"] = record


def _refresh_crown_normals(document, binary, primitive, changed):
    attributes = primitive["attributes"]
    if "NORMAL" not in attributes or not changed.any():
        return
    points = accessor_values(document, binary, attributes["POSITION"], "VEC3")
    normals = accessor_values(document, binary, attributes["NORMAL"], "VEC3")
    if normals.dtype != np.dtype("<f4") or len(normals) != len(points) or not np.isfinite(normals).all():
        raise ValueError("geometry_repair_normal_invalid")
    if "indices" in primitive:
        triangles = accessor_values(document, binary, primitive["indices"], "SCALAR").reshape(-1, 3)
    else:
        triangles = np.arange(len(points), dtype=np.uint32).reshape(-1, 3)
    affected = np.isin(triangles, np.flatnonzero(changed)).any(axis=1)
    triangles = triangles[affected]
    if not len(triangles):
        # Every changed position is unreferenced by a render triangle, so no
        # face normal needs to change.
        return
    cross = np.cross(
        points[triangles[:, 1]] - points[triangles[:, 0]],
        points[triangles[:, 2]] - points[triangles[:, 0]],
    )
    accumulated = np.zeros((len(points), 3), dtype=np.float32)
    for corner in range(3):
        np.add.at(accumulated, triangles[:, corner], cross)
    indices = np.flatnonzero(changed)
    lengths = np.linalg.norm(accumulated[indices], axis=1)
    used = np.isin(indices, triangles)
    if not np.isfinite(lengths).all() or np.any((lengths <= 1e-12) & used):
        raise ValueError("geometry_repair_normal_invalid")
    # An unreferenced position has no face normal to refresh; preserve its
    # original attribute instead of inventing a value or rejecting valid GLB.
    refresh = indices[lengths > 1e-12]
    normals[refresh] = accumulated[refresh] / lengths[lengths > 1e-12, None]


def reshape_crown(document, binary, spec):
    """Compress only a confirmed hairline-up region, never a facial region.

    The caller binds the exact source, expected crown height and hairline. This
    operator does not infer identity or claim arbitrary face editing.
    """
    if spec.get("confirmed") is not True:
        raise ValueError("geometry_repair_confirmation_required")
    source_geometry_sha256 = hashlib.sha256(binary).hexdigest()
    document = copy.deepcopy(document)
    binary = bytearray(binary)
    mesh = named_mesh(document, spec["mesh"])
    number_fields = (
        "hairline_y",
        "blend_height",
        "crown_scale",
        "front_pivot_x",
        "front_scale",
        "expected_head_top_y",
        "review_yaw_degrees",
    )
    values = {key: float(spec[key]) for key in number_fields}
    if (
        not all(math.isfinite(value) for value in values.values())
        or not 0.0001 <= values["blend_height"] <= 0.05
        or not 0.5 <= values["crown_scale"] <= 1.25
        or not 0.5 <= values["front_scale"] <= 1.25
        or not -180.0 <= values["review_yaw_degrees"] <= 180.0
        or values["hairline_y"] >= values["expected_head_top_y"]
    ):
        raise ValueError("geometry_repair_parameters_invalid")
    changed_count = 0
    protected_count = 0
    accessors = set()
    for primitive in mesh["primitives"]:
        position_index = primitive["attributes"]["POSITION"]
        if position_index in accessors:
            raise ValueError("geometry_repair_transform_unsupported")
        accessors.add(position_index)
    original_points = [points.copy() for points in positions(document, binary, mesh)]
    head_top = max(float(points[:, 1].max()) for points in original_points)
    body_bottom = min(float(points[:, 1].min()) for points in original_points)
    if not math.isclose(head_top, values["expected_head_top_y"], abs_tol=0.00001):
        raise ValueError("geometry_repair_landmark_mismatch")
    if body_bottom >= values["hairline_y"]:
        raise ValueError("geometry_repair_landmark_mismatch")
    for primitive, original in zip(mesh["primitives"], original_points):
        points = accessor_values(document, binary, primitive["attributes"]["POSITION"], "VEC3")
        y = original[:, 1]
        t = np.clip((y - values["hairline_y"]) / values["blend_height"], 0.0, 1.0)
        weight = t * t * (3.0 - 2.0 * t)
        points[:, 1] = values["hairline_y"] + (y - values["hairline_y"]) * (
            1.0 + (values["crown_scale"] - 1.0) * weight
        )
        points[:, 0] += (
            (values["front_scale"] - 1.0) * np.maximum(original[:, 0] - values["front_pivot_x"], 0.0) * weight
        )
        protected = y <= values["hairline_y"]
        # Preserve the boundary bit-for-bit even when the JSON landmark cannot
        # be represented exactly as float32; do not relax this protection check.
        points[protected] = original[protected]
        changed = np.any(points != original, axis=1)
        if not np.array_equal(points[protected], original[protected]):
            raise ValueError("geometry_repair_protected_region_changed")
        _refresh_crown_normals(document, binary, primitive, changed)
        index = primitive["attributes"]["POSITION"]
        document["accessors"][index]["min"] = points.min(axis=0).tolist()
        document["accessors"][index]["max"] = points.max(axis=0).tolist()
        changed_count += int(changed.sum())
        protected_count += int(protected.sum())
    if not changed_count:
        raise ValueError("geometry_repair_region_empty")
    record = dict(
        schema_version=1,
        operation="reshape_crown",
        source_sha256=hashlib.sha256(Path(spec["source"]).read_bytes()).hexdigest(),
        source_geometry_sha256=source_geometry_sha256,
        mesh=spec["mesh"],
        **values,
        changed_vertices=changed_count,
        protected_vertices=protected_count,
        protected_positions_unchanged=True,
        topology_changed=False,
        decimated=False,
        requires_new_head_review=True,
        capability_scope="confirmed_hairline_up_only_not_general_face_repair",
    )
    _record_repair(document, record)
    extras = document["asset"]["extras"]
    extras["maliang_review_frame"] = dict(
        schema_version=1,
        yaw_degrees=values["review_yaw_degrees"],
        confirmed=True,
        source_sha256=record["source_sha256"],
    )
    extras["maliang_geometry_recipe"] = dict(
        operation="reshape_crown",
        source_sha256=record["source_sha256"],
        geometry_sha256=source_geometry_sha256,
        confirmed=True,
        parameters={key: values[key] for key in number_fields},
        mesh=spec["mesh"],
    )
    return document, binary, record


HUMAN_LANDMARK_NAMES = (
    "head_top", "chin", "neck",
    "shoulder_l", "elbow_l", "wrist_l",
    "shoulder_r", "elbow_r", "wrist_r",
    "hip_l", "knee_l", "ankle_l",
    "hip_r", "knee_r", "ankle_r",
)


def _smoothstep_array(low, high, value):
    t = np.clip((value - low) / max(high - low, 1e-12), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _chain_projection(points, chain):
    """Return nearest original/deformed chain points for an Nx3 array."""
    best_distance = np.full(len(points), np.inf)
    best_closest = np.zeros_like(points)
    best_deformed = np.zeros_like(points)
    best_segment = np.zeros(len(points), dtype=np.int64)
    best_t = np.zeros(len(points), dtype=np.float64)
    for index in range(len(chain) - 1):
        start, end = chain[index], chain[index + 1]
        direction = end - start
        length_squared = float(np.dot(direction, direction))
        if length_squared <= 1e-12:
            raise ValueError("geometry_repair_landmark_mismatch")
        t = np.clip(np.sum((points - start) * direction, axis=1) / length_squared, 0.0, 1.0)
        closest = start + t[:, None] * direction
        distance = np.linalg.norm(points - closest, axis=1)
        selected = distance < best_distance
        best_distance[selected] = distance[selected]
        best_closest[selected] = closest[selected]
        best_segment[selected] = index
        best_t[selected] = t[selected]
    return best_distance, best_closest, best_segment, best_t


def _scaled_chain_displacement(points, chain, scale):
    scaled = chain[0] + (chain - chain[0]) * scale
    best_distance = np.full(len(points), np.inf)
    best_delta = np.zeros_like(points)
    best_closest = np.zeros_like(points)
    for index in range(len(chain) - 1):
        start, end = chain[index], chain[index + 1]
        direction = end - start
        length_squared = float(np.dot(direction, direction))
        if length_squared <= 1e-12:
            raise ValueError("geometry_repair_landmark_mismatch")
        t = np.clip(np.sum((points - start) * direction, axis=1) / length_squared, 0.0, 1.0)
        closest = start + t[:, None] * direction
        distance = np.linalg.norm(points - closest, axis=1)
        deformed = scaled[index] + t[:, None] * (scaled[index + 1] - scaled[index])
        selected = distance < best_distance
        best_distance[selected] = distance[selected]
        best_delta[selected] = (deformed - closest)[selected]
        best_closest[selected] = closest[selected]
    return best_distance, best_closest, best_delta


def _human_landmarks(spec, source_sha256):
    value = spec["landmarks"]
    if not isinstance(value, dict) or set(value) != {"source_sha256", *HUMAN_LANDMARK_NAMES}:
        raise ValueError("geometry_repair_landmarks_invalid")
    if value["source_sha256"] != source_sha256:
        raise ValueError("geometry_repair_landmark_source_mismatch")
    result = {}
    for name in HUMAN_LANDMARK_NAMES:
        point = value[name]
        if (
            not isinstance(point, list) or len(point) != 3
            or any(type(component) not in (int, float) or not math.isfinite(component) for component in point)
        ):
            raise ValueError("geometry_repair_landmarks_invalid")
        result[name] = np.asarray(point, dtype=np.float64)
    if result["shoulder_l"][0] <= result["shoulder_r"][0] or result["hip_l"][0] <= result["hip_r"][0]:
        raise ValueError("geometry_repair_landmark_mismatch")
    if not result["head_top"][1] > result["chin"][1] > result["neck"][1]:
        raise ValueError("geometry_repair_landmark_mismatch")
    for side in ("l", "r"):
        if not result["hip_" + side][1] > result["knee_" + side][1] > result["ankle_" + side][1]:
            raise ValueError("geometry_repair_landmark_mismatch")
    return result


def _human_parameters(spec, source_sha256):
    if spec.get("reference_pose") not in ("T", "A"):
        raise ValueError("geometry_repair_reference_pose_invalid")
    bounds = dict(
        target_height_m=(0.2, 4.0), target_head_ratio=(3.0, 12.0),
        arm_length_scale=(0.75, 1.35), leg_length_scale=(0.75, 1.35), build=(-1.0, 1.0),
    )
    values = {}
    for name, limit in bounds.items():
        raw = spec[name]
        if type(raw) not in (int, float) or not math.isfinite(raw) or not limit[0] <= raw <= limit[1]:
            raise ValueError("geometry_repair_parameters_invalid")
        values[name] = float(raw)
    values["landmarks"] = _human_landmarks(spec, source_sha256)
    values["reference_pose"] = spec["reference_pose"]
    return values


def reshape_humanoid(document, binary, spec):
    """Deform a source-validated static humanoid before skeleton/skin generation.

    Coordinates are Y-up world/local coordinates with anatomical left at +X.
    Node transforms and existing skins are deliberately outside this V1 contract.
    """
    source_sha256 = hashlib.sha256(Path(spec["source"]).read_bytes()).hexdigest()
    source_geometry_sha256 = hashlib.sha256(bytes(binary)).hexdigest()
    parameters = _human_parameters(spec, source_sha256)
    landmarks = parameters["landmarks"]
    if document.get("skins"):
        raise ValueError("geometry_repair_rigged_source_unsupported")
    for node in document.get("nodes", []):
        if "mesh" not in node:
            continue
        if "matrix" in node or "rotation" in node or "scale" in node or any(
            abs(float(value)) > 1e-12 for value in node.get("translation", [0, 0, 0])
        ):
            raise ValueError("geometry_repair_transform_unsupported")
    document = copy.deepcopy(document)
    binary = bytearray(binary)
    primitives = []
    originals = []
    accessors = set()
    for mesh in document.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            if primitive.get("mode", 4) != 4:
                raise ValueError("geometry_repair_source_invalid")
            index = primitive["attributes"]["POSITION"]
            if index in accessors:
                raise ValueError("geometry_repair_transform_unsupported")
            accessors.add(index)
            points = accessor_values(document, binary, index, "VEC3")
            if points.dtype != np.dtype("<f4") or not np.isfinite(points).all():
                raise ValueError("geometry_repair_source_invalid")
            primitives.append(primitive)
            originals.append(np.asarray(points, dtype=np.float64).copy())
    if not originals:
        raise ValueError("geometry_repair_mesh_missing")
    joined = np.concatenate(originals)
    source_height = float(joined[:, 1].max() - joined[:, 1].min())
    if source_height <= 1e-6 or abs(float(joined[:, 1].max()) - landmarks["head_top"][1]) > source_height * 0.002:
        raise ValueError("geometry_repair_landmark_mismatch")
    hips = (landmarks["hip_l"] + landmarks["hip_r"]) / 2.0
    chains = [np.asarray([hips, landmarks["neck"]])]
    for side in ("l", "r"):
        chains.append(np.asarray([landmarks[name + "_" + side] for name in ("shoulder", "elbow", "wrist")]))
    for side in ("l", "r"):
        chains.append(np.asarray([landmarks[name + "_" + side] for name in ("hip", "knee", "ankle")]))

    def pre_head(points):
        result = np.asarray(points, dtype=np.float64).copy()
        if parameters["build"]:
            head_weight = _smoothstep_array(landmarks["neck"][1], landmarks["chin"][1], result[:, 1])
            foot_level = min(landmarks["ankle_l"][1], landmarks["ankle_r"][1])
            foot_weight = 1.0 - _smoothstep_array(foot_level, foot_level + source_height * 0.08, result[:, 1])
            nearest_distance = np.full(len(result), np.inf)
            nearest = np.zeros_like(result)
            nearest_chain = np.zeros(len(result), dtype=np.int64)
            for chain_index, chain in enumerate(chains):
                distance, closest, _segment, _t = _chain_projection(result, chain)
                selected = distance < nearest_distance
                nearest_distance[selected] = distance[selected]
                nearest[selected] = closest[selected]
                nearest_chain[selected] = chain_index
            radius = source_height * 0.16
            region = 1.0 - _smoothstep_array(radius * 0.45, radius, nearest_distance)
            protect = np.maximum(head_weight, foot_weight)
            # Hands keep their size; only the arm up to the wrist follows build.
            for side_index, side in enumerate(("l", "r"), 1):
                wrist = landmarks["wrist_" + side]
                elbow = landmarks["elbow_" + side]
                direction = wrist - elbow
                direction /= np.linalg.norm(direction)
                beyond = np.sum((result - wrist) * direction, axis=1)
                hand = _smoothstep_array(-source_height * 0.015, source_height * 0.035, beyond)
                same_chain = nearest_chain == side_index
                protect[same_chain] = np.maximum(protect[same_chain], hand[same_chain])
            weight = region * (1.0 - protect)
            factor = 1.0 + parameters["build"] * 0.25
            result = nearest + (result - nearest) * (1.0 + (factor - 1.0) * weight[:, None])
        for side in ("l", "r"):
            chain = np.asarray([landmarks[name + "_" + side] for name in ("shoulder", "elbow", "wrist")])
            distance, closest, delta = _scaled_chain_displacement(result, chain, parameters["arm_length_scale"])
            side_sign = 1.0 if side == "l" else -1.0
            lateral = (result[:, 0] - hips[0]) * side_sign
            side_weight = _smoothstep_array(0.0, source_height * 0.04, lateral)
            region = 1.0 - _smoothstep_array(source_height * 0.06, source_height * 0.16, distance)
            root_blend = _smoothstep_array(0.0, np.linalg.norm(chain[1] - chain[0]) * 0.2,
                                           np.linalg.norm(closest - chain[0], axis=1))
            result += delta * (side_weight * region * root_blend)[:, None]
        for side in ("l", "r"):
            chain = np.asarray([landmarks[name + "_" + side] for name in ("hip", "knee", "ankle")])
            distance, closest, delta = _scaled_chain_displacement(result, chain, parameters["leg_length_scale"])
            side_sign = 1.0 if side == "l" else -1.0
            lateral = (result[:, 0] - hips[0]) * side_sign
            side_weight = _smoothstep_array(0.0, source_height * 0.04, lateral)
            region = 1.0 - _smoothstep_array(source_height * 0.07, source_height * 0.18, distance)
            root_blend = _smoothstep_array(0.0, np.linalg.norm(chain[1] - chain[0]) * 0.15,
                                           np.linalg.norm(closest - chain[0], axis=1))
            result += delta * (side_weight * region * root_blend)[:, None]
        return result

    landmark_array = np.asarray([landmarks[name] for name in HUMAN_LANDMARK_NAMES])
    pre_landmark_array = pre_head(landmark_array)
    pre_landmarks = dict(zip(HUMAN_LANDMARK_NAMES, pre_landmark_array))
    pre_points = [pre_head(points) for points in originals]
    bottom = min(float(points[:, 1].min()) for points in pre_points)
    top = float(pre_landmarks["head_top"][1])
    chin = float(pre_landmarks["chin"][1])
    neck = float(pre_landmarks["neck"][1])
    denominator = parameters["target_head_ratio"] * (top - chin) - (top - neck)
    if denominator <= 1e-9:
        raise ValueError("geometry_repair_parameters_invalid")
    head_scale = (neck - bottom) / denominator
    if not 0.25 <= head_scale <= 2.0:
        raise ValueError("geometry_repair_proportion_limit_exceeded")

    def apply_head(points):
        weight = _smoothstep_array(neck, chin, points[:, 1])
        pivot = pre_landmarks["neck"]
        return points + (points - pivot) * ((head_scale - 1.0) * weight[:, None])

    headed = [apply_head(points) for points in pre_points]
    headed_landmarks = dict(zip(HUMAN_LANDMARK_NAMES, apply_head(pre_landmark_array)))
    all_headed = np.concatenate(headed)
    lower = all_headed.min(axis=0)
    upper = all_headed.max(axis=0)
    height = float(upper[1] - lower[1])
    if height <= 1e-9:
        raise ValueError("geometry_repair_output_invalid")
    normalize = parameters["target_height_m"] / height
    origin = np.asarray([(lower[0] + upper[0]) / 2.0, lower[1], (lower[2] + upper[2]) / 2.0])

    def final_points(points):
        return (points - origin) * normalize

    changed_count = 0
    tangents_removed = 0
    for primitive, original, transformed in zip(primitives, originals, headed):
        final = final_points(transformed).astype("<f4")
        if not np.isfinite(final).all():
            raise ValueError("geometry_repair_output_invalid")
        points = accessor_values(document, binary, primitive["attributes"]["POSITION"], "VEC3")
        changed = np.any(final != original.astype("<f4"), axis=1)
        points[:] = final
        changed_count += int(changed.sum())
        if "TANGENT" in primitive["attributes"]:
            del primitive["attributes"]["TANGENT"]
            tangents_removed += 1
        _refresh_crown_normals(document, binary, primitive, changed)
        index = primitive["attributes"]["POSITION"]
        document["accessors"][index]["min"] = points.min(axis=0).tolist()
        document["accessors"][index]["max"] = points.max(axis=0).tolist()
    final_landmark_array = final_points(np.asarray([headed_landmarks[name] for name in HUMAN_LANDMARK_NAMES]))
    final_landmarks = dict(zip(HUMAN_LANDMARK_NAMES, final_landmark_array))
    final_head_height = float(final_landmarks["head_top"][1] - final_landmarks["chin"][1])
    measured_height = parameters["target_height_m"]
    measured_ratio = measured_height / final_head_height
    if not math.isclose(measured_ratio, parameters["target_head_ratio"], rel_tol=2e-5, abs_tol=2e-5):
        raise ValueError("geometry_repair_output_invalid")
    record = dict(
        schema_version=1,
        operation="reshape_humanoid",
        source_sha256=source_sha256,
        source_geometry_sha256=source_geometry_sha256,
        reference_pose=parameters["reference_pose"],
        target_height_m=parameters["target_height_m"],
        target_head_ratio=parameters["target_head_ratio"],
        arm_length_scale=parameters["arm_length_scale"],
        leg_length_scale=parameters["leg_length_scale"],
        build=parameters["build"],
        head_scale=head_scale,
        uniform_height_scale=normalize,
        measured=dict(
            height_m=measured_height,
            head_ratio=measured_ratio,
            arm_lengths_m={
                side: float(np.linalg.norm(final_landmarks["elbow_" + side] - final_landmarks["shoulder_" + side])
                            + np.linalg.norm(final_landmarks["wrist_" + side] - final_landmarks["elbow_" + side]))
                for side in ("l", "r")
            },
            leg_lengths_m={
                side: float(np.linalg.norm(final_landmarks["knee_" + side] - final_landmarks["hip_" + side])
                            + np.linalg.norm(final_landmarks["ankle_" + side] - final_landmarks["knee_" + side]))
                for side in ("l", "r")
            },
        ),
        landmarks={name: final_landmarks[name].tolist() for name in HUMAN_LANDMARK_NAMES},
        changed_vertices=changed_count,
        tangents_removed=tangents_removed,
        topology_changed=False,
        decimated=False,
        requires_new_head_review=True,
        requires_new_rigging=True,
        binding_stage="pre_rig_geometry_only",
        validation_mode="ainative_source_bound_landmarks_automatic",
        capability_scope="source_bound_static_T_or_A_pose_landmarked_humanoid_v1",
    )
    _record_repair(document, record)
    extras = document["asset"]["extras"]
    extras.pop("maliang_head_landmarks", None)
    extras.pop("maliang_review_frame", None)
    extras.pop("maliang_geometry_recipe", None)
    extras["maliang_humanoid_landmarks"] = dict(
        schema_version=1,
        validation_state="automatically_derived_review_required",
        derived_from_source_sha256=source_sha256,
        reference_pose=parameters["reference_pose"],
        coordinate_space="Y_up_meters_left_positive_X",
        landmarks=record["landmarks"],
        review_required=True,
    )
    return document, binary, record


def repair(spec):
    common = {"schema_version", "source", "source_sha256", "output", "operation"}
    operation_fields = {
        "align_neck": {"head_mesh", "body_mesh", "neck_y", "band_height", "max_translation", "axes"},
        "reshape_crown": {
            "mesh",
            "confirmed",
            "hairline_y",
            "blend_height",
            "crown_scale",
            "front_pivot_x",
            "front_scale",
            "expected_head_top_y",
            "review_yaw_degrees",
        },
        "reshape_humanoid": {
            "reference_pose", "landmarks", "target_height_m", "target_head_ratio",
            "arm_length_scale", "leg_length_scale", "build",
        },
    }
    if not isinstance(spec, dict) or spec.get("schema_version") != 1:
        raise ValueError("geometry_repair_spec_invalid")
    operation = spec.get("operation")
    if operation not in operation_fields:
        raise ValueError("geometry_repair_operation_unsupported")
    if set(spec) != common | operation_fields[operation]:
        raise ValueError("geometry_repair_spec_invalid")
    source = Path(spec["source"])
    output = Path(spec["output"])
    receipt = output.with_name(output.name + ".receipt.json")
    if output.exists() or receipt.exists() or output.suffix.lower() != ".glb" or source.resolve() == output.resolve():
        raise ValueError("geometry_repair_output_invalid")
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    if source_sha != spec["source_sha256"]:
        raise ValueError("geometry_repair_source_changed")
    document, binary = load_glb(source)
    operators = dict(align_neck=align_neck, reshape_crown=reshape_crown, reshape_humanoid=reshape_humanoid)
    document, binary, record = operators[operation](document, binary, spec)
    result = write_glb(document, binary, output)
    loaded, output_binary = load_glb(output)
    vertices = triangles = 0
    for mesh in loaded.get("meshes", []):
        for primitive in mesh["primitives"]:
            points = accessor_values(loaded, output_binary, primitive["attributes"]["POSITION"], "VEC3")
            if not np.isfinite(points).all():
                raise ValueError("geometry_repair_output_invalid")
            vertices += len(points)
            if "indices" in primitive:
                indices = accessor_values(loaded, output_binary, primitive["indices"], "SCALAR")
                if indices.size and indices.max() >= len(points):
                    raise ValueError("geometry_repair_output_invalid")
                triangles += len(indices) // 3
            else:
                triangles += len(points) // 3
    record.update(
        output=str(output),
        output_sha256=hashlib.sha256(result).hexdigest(),
        bytes=len(result),
        vertices=vertices,
        triangles=triangles,
        source_not_overwritten=hashlib.sha256(source.read_bytes()).hexdigest() == source_sha,
        within_legacy_budget=len(result) <= LEGACY_BYTES
        and vertices <= LEGACY_VERTICES
        and triangles <= LEGACY_TRIANGLES,
    )
    receipt.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Expected geometry repair spec JSON")
    spec_path = Path(sys.argv[1])
    if spec_path.stat().st_size > 65536:
        raise SystemExit("Repair spec too large")
    request = json.loads(spec_path.read_text(encoding="utf-8"))
    print(json.dumps(repair(request), ensure_ascii=False, indent=2))
