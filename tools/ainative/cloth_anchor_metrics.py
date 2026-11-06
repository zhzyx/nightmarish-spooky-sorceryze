"""Exact point-to-triangle distances for the exported posed shoulder/back surface."""

import json
import sys
from pathlib import Path

import numpy as np


def distances(points, faces):
    triangles = np.asarray(faces).reshape(-1, 3, 3)
    a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
    ab, ac = b - a, c - a
    normals = np.cross(ab, ac)
    normal_sq = np.sum(normals * normals, axis=1)
    result = []
    signed = []
    for p in points:
        ap = p - a
        scalar = np.sum(ap * normals, axis=1) / np.maximum(normal_sq, 1e-20)
        projected = p - scalar[:, None] * normals
        v = projected - a
        d00, d01, d11 = np.sum(ab * ab, axis=1), np.sum(ab * ac, axis=1), np.sum(ac * ac, axis=1)
        d20, d21 = np.sum(v * ab, axis=1), np.sum(v * ac, axis=1)
        denom = np.maximum(d00 * d11 - d01 * d01, 1e-20)
        u, w = (d11 * d20 - d01 * d21) / denom, (d00 * d21 - d01 * d20) / denom
        inside = (u >= 0) & (w >= 0) & (u + w <= 1) & (normal_sq > 1e-20)
        best = np.where(inside, np.linalg.norm(projected - p, axis=1), np.inf)
        for x, y in [(a, b), (b, c), (c, a)]:
            xy = y - x
            fraction = np.clip(np.sum((p - x) * xy, axis=1) / np.maximum(np.sum(xy * xy, axis=1), 1e-20), 0, 1)
            best = np.minimum(best, np.linalg.norm(x + fraction[:, None] * xy - p, axis=1))
        closest = int(best.argmin())
        result.append(float(best[closest]))
        # Godot imported triangle winding is clockwise, so outward is -cross(ab, ac).
        sign = np.sign(np.dot(p - a[closest], -normals[closest]))
        signed.append(float(best[closest] * sign))
    return result, signed


if __name__ == "__main__":
    source = Path(sys.argv[1])
    doc = json.loads(source.read_text())
    report = {
        "method": "exact closest point over all exported actual posed upper-body triangles",
        "pin_target_max_error_m": doc["pin_target_max_error_m"],
    }
    for key in ["pins", "targets", "render_top"]:
        values, signed = distances(np.asarray(doc[key]), doc["body_faces"])
        report[key] = {
            "min_m": min(values),
            "p50_m": float(np.median(values)),
            "max_m": max(values),
            "distances_m": values,
            "signed_min_m": min(signed),
            "signed_max_m": max(signed),
        }
    destination = source.with_name(source.stem.replace("-geometry", "-metrics") + ".json")
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps(report))
