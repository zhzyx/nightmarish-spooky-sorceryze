"""Author a new cape binding with top anchors fitted to a measured body back surface."""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np


def back_z(x, y, faces):
    a, b, c = faces[:, 0], faces[:, 1], faces[:, 2]
    v0, v1 = b[:, :2] - a[:, :2], c[:, :2] - a[:, :2]
    v2 = np.array([x, y]) - a[:, :2]
    det = v0[:, 0] * v1[:, 1] - v0[:, 1] * v1[:, 0]
    safe = np.where(np.abs(det) > 1e-12, det, 1)
    u = (v2[:, 0] * v1[:, 1] - v2[:, 1] * v1[:, 0]) / safe
    v = (v0[:, 0] * v2[:, 1] - v0[:, 1] * v2[:, 0]) / safe
    valid = (np.abs(det) > 1e-12) & (u >= 0) & (v >= 0) & (u + v <= 1)
    if not valid.any():
        return None
    z = a[:, 2] + u * (b[:, 2] - a[:, 2]) + v * (c[:, 2] - a[:, 2])
    return float(z[valid].min())


if __name__ == "__main__":
    source, geometry, output = map(Path, sys.argv[1:])
    doc = json.loads(source.read_text())
    body = json.loads(geometry.read_text())
    faces = np.asarray(body["rest_body_faces"]).reshape(-1, 3, 3)
    vertices = np.asarray(doc["vertices"])
    proxy = np.asarray(doc["proxy"])
    mapping, weights = np.asarray(doc["mapping"]), np.asarray(doc["weights"])
    top_y = vertices[:, 1].max()
    top_vertices = np.flatnonzero(vertices[:, 1] > top_y - 1e-6)
    pins = np.zeros(len(proxy))
    for i in top_vertices:
        for k in range(4):
            if weights[i, k] > 1e-8:
                pins[mapping[i, k]] = 1
    for i in np.flatnonzero(pins):
        z = back_z(proxy[i, 0], proxy[i, 1], faces)
        if z is None:
            raise ValueError("Active top anchor has no actual back surface")
        proxy[i, 2] = z - 0.008
    for i in range(len(vertices)):
        influence = np.clip((vertices[i, 1] - (top_y - 0.12)) / 0.12, 0, 1)
        if influence <= 0:
            continue
        z = back_z(vertices[i, 0], vertices[i, 1], faces)
        if z is not None:
            vertices[i, 2] = (1 - influence) * vertices[i, 2] + influence * (z - 0.008)
    offsets = vertices - (proxy[mapping] * weights[:, :, None]).sum(axis=1)
    doc.update(
        proxy=proxy.tolist(),
        vertices=vertices.tolist(),
        offsets=offsets.tolist(),
        pins=pins.tolist(),
        pin_calibration={
            "method": "active render-top support only; actual rest-body back ray intersection + 8mm offset, 120mm blend band",
            "input_binding_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "body_geometry_sha256": hashlib.sha256(geometry.read_bytes()).hexdigest(),
            "target_profile_revision": body["profile_revision"],
            "source_scene_sha256": body["source_scene_sha256"],
            "active_pins": np.flatnonzero(pins).tolist(),
        },
    )
    doc.pop("binding_revision", None)
    doc["binding_revision"] = hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()
    with output.open("x", encoding="utf-8") as stream:
        json.dump(doc, stream, separators=(",", ":"))
    print(json.dumps(doc["pin_calibration"]))
