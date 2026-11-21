"""AINative automatic humanoid landmark estimation on one immutable static GLB.

Rendered-view AI estimates normalized anatomical landmarks. Local geometry checks
bind them to the source and reject low-confidence or implausible output before any
body-shape deformation. No manual-confirmation claim is manufactured.
"""

import base64
import hashlib
import json
import math
from pathlib import Path

import api_planner
import geometry_repair
import numpy as np
import rigging_review
from extensions import canonical, require


def landmark_schema():
    point = dict(type="array", minItems=3, maxItems=3, items=dict(type="number", minimum=-2.0, maximum=2.0))
    landmarks = dict(
        type="object",
        properties={name: point for name in geometry_repair.HUMAN_LANDMARK_NAMES},
        required=list(geometry_repair.HUMAN_LANDMARK_NAMES),
        additionalProperties=False,
    )
    return dict(
        type="object",
        properties=dict(
            schema_version=dict(type="integer", const=1),
            reference_pose=dict(type="string", enum=["T", "A"]),
            rendered_front_view=dict(type="string", enum=["front", "right", "back", "left"]),
            confidence=dict(type="string", enum=["high", "medium", "low"]),
            landmarks=landmarks,
            observations=dict(type="string"),
        ),
        required=["schema_version", "reference_pose", "rendered_front_view", "confidence", "landmarks", "observations"],
        additionalProperties=False,
    )


def _prompt():
    names = list(geometry_repair.HUMAN_LANDMARK_NAMES)
    return (
        """Estimate anatomical landmarks for ONE existing static humanoid GLB from its rendered views. This is source-bound AI estimation, not a claim of exact motion-capture measurement. Inspect front, right, back, left, top, upper/lower body and head views independently. Identify whether the actual reference pose is T or A; A means both arms slope downward but elbows/wrists remain observable. rendered_front_view is the full-body view that actually shows anatomical front. confidence=low for a non-humanoid, duplicate subject, missing limbs, unclear front, occluded joints or inconsistent views. Return schema_version=1 and every required landmark exactly once.
Coordinate contract: Y-up; each point is [x,y,z] normalized by FULL VISIBLE MODEL HEIGHT. y=0 at the lowest geometry and y=1 at the highest head geometry. x=0 and z=0 at the full-model bounding-box X/Z center; x and z are offsets divided by the same full height. Anatomical left is +X in the front view and anatomical front is +Z. head_top is the highest head/skull/hair geometry, chin is the lower face/chin landmark, and neck is the neck root above the torso. shoulder/elbow/wrist and hip/knee/ankle are anatomical joint centers, not surface silhouettes. Left/right must never be swapped. Estimate z from right/left/head_side evidence, not by inventing a flat Z=0 body. Do not output pixel coordinates, meters, a skeleton, skin weights or an animation claim.
Required landmark names:
"""
        + canonical(names)
        + "\n"
    )


def _request_ai(entries, directory, planner):
    api_planner.validate_config(planner)
    directory.mkdir()
    prompt = _prompt()
    content = [dict(type="text", text=prompt)]
    for entry in entries:
        path = Path(entry["path"])
        content.append(dict(type="text", text="IMAGE " + entry["image_id"] + "; role/view: " + entry["label"]))
        content.append(
            dict(
                type="image_url",
                image_url=dict(url="data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()),
            )
        )
    schema = landmark_schema()
    body = dict(
        model=planner["model"],
        messages=[dict(role="user", content=content)],
        response_format=dict(
            type="json_schema", json_schema=dict(name="human_shape_landmarks", strict=True, schema=schema)
        ),
        reasoning_effort="low",
        max_tokens=16384,
        stream=False,
    )
    raw = canonical(body).encode("utf-8")
    require(len(raw) <= api_planner.MAX_REQUEST, "vision_request_too_large")
    (directory / "prompt.txt").write_text(prompt, encoding="utf-8")
    (directory / "schema.json").write_text(canonical(schema), encoding="utf-8")
    (directory / "api-request.json").write_bytes(raw)
    api_planner.perform(planner, directory)
    document = json.loads((directory / "api-plan.json").read_text(encoding="utf-8"))
    receipt = json.loads((directory / "api-receipt.json").read_text(encoding="utf-8"))
    require(
        receipt.get("request_sha256") == hashlib.sha256(raw).hexdigest()
        and receipt.get("instructions_sha256") == hashlib.sha256(canonical(document).encode()).hexdigest(),
        "vision_output_invalid",
    )
    return document, receipt


def _source_points(source):
    document, binary = geometry_repair.load_glb(source)
    require(not document.get("skins"), "geometry_repair_rigged_source_unsupported")
    for node in document.get("nodes", []):
        if "mesh" not in node:
            continue
        require(
            "matrix" not in node
            and "rotation" not in node
            and "scale" not in node
            and all(abs(float(value)) <= 1e-12 for value in node.get("translation", [0, 0, 0])),
            "geometry_repair_transform_unsupported",
        )
    result = []
    for mesh in document.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            points = geometry_repair.accessor_values(document, binary, primitive["attributes"]["POSITION"], "VEC3")
            require(np.isfinite(points).all(), "human_shape_auto_fit_geometry_invalid")
            result.append(np.asarray(points, dtype=np.float64))
    require(bool(result), "human_shape_auto_fit_geometry_invalid")
    return np.concatenate(result)


def _validate_document(document):
    require(
        isinstance(document, dict)
        and set(document)
        == {"schema_version", "reference_pose", "rendered_front_view", "confidence", "landmarks", "observations"}
        and document.get("schema_version") == 1
        and document.get("reference_pose") in ("T", "A")
        and isinstance(document.get("observations"), str),
        "human_shape_auto_fit_output_invalid",
    )
    require(document["rendered_front_view"] == "front", "human_shape_auto_fit_front_required")
    require(document["confidence"] in ("high", "medium"), "human_shape_auto_fit_low_confidence")
    landmarks = document["landmarks"]
    require(
        isinstance(landmarks, dict) and set(landmarks) == set(geometry_repair.HUMAN_LANDMARK_NAMES),
        "human_shape_auto_fit_output_invalid",
    )
    normalized = {}
    for name in geometry_repair.HUMAN_LANDMARK_NAMES:
        point = landmarks[name]
        require(
            isinstance(point, list)
            and len(point) == 3
            and all(type(value) in (int, float) and math.isfinite(value) and -2.0 <= value <= 2.0 for value in point)
            and -1e-6 <= point[1] <= 1.0 + 1e-6,
            "human_shape_auto_fit_output_invalid",
        )
        normalized[name] = [float(value) for value in point]
        normalized[name][1] = min(1.0, max(0.0, normalized[name][1]))
    # The visible geometry maximum defines this landmark's Y, not an AI guess.
    normalized["head_top"][1] = 1.0
    return normalized


def _restore_source_normalized(normalized, points, yaw_degrees):
    """Convert render-stage normalized coordinates back to the source frame."""
    if not yaw_degrees:
        return normalized
    lower = points.min(axis=0)
    upper = points.max(axis=0)
    height = float(upper[1] - lower[1])
    source_center = np.asarray([(lower[0] + upper[0]) / 2.0, lower[1], (lower[2] + upper[2]) / 2.0])
    theta = math.radians(yaw_degrees)
    cosine, sine = math.cos(theta), math.sin(theta)
    rotation = np.asarray([[cosine, 0.0, sine], [0.0, 1.0, 0.0], [-sine, 0.0, cosine]])
    inverse = rotation.T
    rotated = points @ rotation.T
    rotated_lower = rotated.min(axis=0)
    rotated_upper = rotated.max(axis=0)
    stage_center = np.asarray([
        (rotated_lower[0] + rotated_upper[0]) / 2.0,
        lower[1],
        (rotated_lower[2] + rotated_upper[2]) / 2.0,
    ])
    center_correction = inverse @ (stage_center - source_center) / height
    return {
        name: (inverse @ np.asarray(point, dtype=np.float64) + center_correction).tolist()
        for name, point in normalized.items()
    }


def fit_landmarks(source, directory, godot_path, render_script, planner):
    source = Path(source).expanduser().resolve()
    directory = Path(directory).expanduser().resolve()
    require(source.is_file() and source.suffix.lower() == ".glb", "human_shape_source_invalid")
    require(not directory.exists(), "human_shape_auto_fit_output_exists")
    directory.mkdir(parents=True)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    points = _source_points(source)
    lower = points.min(axis=0)
    upper = points.max(axis=0)
    height = float(upper[1] - lower[1])
    require(height > 1e-6, "human_shape_auto_fit_geometry_invalid")
    center = np.asarray([(lower[0] + upper[0]) / 2.0, lower[1], (lower[2] + upper[2]) / 2.0])
    entries = rigging_review._render(source, directory, godot_path, render_script)
    document, api_receipt = _request_ai(entries, directory / "request", planner)
    api_receipts = [api_receipt]
    orientation = None
    initial_front = document.get("rendered_front_view")
    if initial_front != "front" and initial_front in rigging_review.REVIEW_FRONT_YAW:
        correction = float(rigging_review.REVIEW_FRONT_YAW[initial_front])
        orientation_directory = directory / "orientation"
        orientation_directory.mkdir()
        entries = rigging_review._render(
            source,
            orientation_directory,
            godot_path,
            render_script,
            yaw_degrees=correction,
        )
        document, corrected_receipt = _request_ai(entries, directory / "request-front-recovery", planner)
        api_receipts.append(corrected_receipt)
        orientation = dict(
            model_sha256=source_sha,
            previous_yaw_degrees=0.0,
            correction_degrees=correction,
            yaw_degrees=correction,
            previous_rendered_front_view=initial_front,
            geometry_changed=False,
        )
    normalized = _validate_document(document)
    if orientation is not None:
        normalized = _restore_source_normalized(normalized, points, orientation["correction_degrees"])
    landmarks = {}
    for name, point in normalized.items():
        world = center + np.asarray(point, dtype=np.float64) * height
        landmarks[name] = world.tolist()
    bound = dict(source_sha256=source_sha, **landmarks)
    # Reuse the same anatomical consistency contract as manual overrides.
    geometry_repair._human_landmarks(dict(landmarks=bound), source_sha)
    distances = {}
    for name in geometry_repair.HUMAN_LANDMARK_NAMES:
        distance = float(np.linalg.norm(points - np.asarray(landmarks[name]), axis=1).min() / height)
        distances[name] = distance
        require(distance <= 0.18, "human_shape_auto_fit_geometry_mismatch")
    result = dict(
        schema_version=1,
        source_sha256=source_sha,
        reference_pose=document["reference_pose"],
        landmarks=bound,
        normalized_landmarks=normalized,
        quality="ai_estimated_geometry_checked",
        confidence=document["confidence"],
        observations=document["observations"],
        rendered_front_view="front",
        orientation_recovery=orientation,
        geometry_checks=dict(
            maximum_landmark_distance_over_height=max(distances.values()),
            landmark_distances_over_height=distances,
            threshold_over_height=0.18,
            source_vertices=len(points),
        ),
        source_not_overwritten=hashlib.sha256(source.read_bytes()).hexdigest() == source_sha,
        requires_visual_review=True,
        manual_confirmation=False,
        api_receipt=api_receipts[-1],
        api_receipts=api_receipts,
    )
    (directory / "landmarks-receipt.json").write_text(canonical(result), encoding="utf-8")
    return result
