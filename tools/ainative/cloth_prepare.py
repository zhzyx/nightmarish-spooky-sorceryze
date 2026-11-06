"""Author-derived cloth binding; original AI GLB is read-only. Requires numpy.

Select largest vertex-connected component explicitly, preserve its triangles,
then fit a meter cage and bind to an authored sheet/cylinder simulation proxy.
No inference and no claim that the AI source was repaired.
"""

import argparse
import hashlib
import json
import struct
from pathlib import Path

import numpy as np


def prepare(source, kind, box, columns=24, rows=16, cloth_top=None):
    raw = source.read_bytes()
    magic, version, length = struct.unpack_from("<III", raw)
    if (magic, version, length) != (0x46546C67, 2, len(raw)):
        raise ValueError("Expected self-contained GLB 2")
    size, tag = struct.unpack_from("<II", raw, 12)
    doc = json.loads(raw[20 : 20 + size])
    if any("uri" in b for b in doc["buffers"]):
        raise ValueError("External buffers refused")
    binary = raw[28 + size :]

    def accessor(index):
        a = doc["accessors"][index]
        v = doc["bufferViews"][a["bufferView"]]
        dtype = {5126: "<f4", 5125: "<u4", 5123: "<u2", 5121: "u1"}[a["componentType"]]
        width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3}[a["type"]]
        offset = v.get("byteOffset", 0) + a.get("byteOffset", 0)
        return np.ndarray(
            (a["count"], width),
            dtype=dtype,
            buffer=binary,
            offset=offset,
            strides=(v.get("byteStride", np.dtype(dtype).itemsize * width), np.dtype(dtype).itemsize),
        ).copy()

    # Generated sources currently have one identity-transform mesh. Refuse silent transforms.
    meshes = [n for n in doc["nodes"] if "mesh" in n]
    if len(meshes) != 1 or any(k in meshes[0] for k in ("matrix", "rotation", "translation", "scale")):
        raise ValueError("Requires one identity-transform source mesh; inspect before extending")
    parents_by_node = {child: i for i, node in enumerate(doc["nodes"]) for child in node.get("children", [])}
    ancestor = doc["nodes"].index(meshes[0])
    visited = set()
    while ancestor in parents_by_node:
        if ancestor in visited:
            raise ValueError("Cyclic source hierarchy")
        visited.add(ancestor)
        ancestor = parents_by_node[ancestor]
        if any(k in doc["nodes"][ancestor] for k in ("matrix", "rotation", "translation", "scale")):
            raise ValueError("Transformed source ancestor requires explicit reviewed bake")
    primitives = doc["meshes"][meshes[0]["mesh"]]["primitives"]
    if len(primitives) != 1:
        raise ValueError("Single source primitive required")
    p = primitives[0]
    vertices = accessor(p["attributes"]["POSITION"]).astype(float)
    faces = accessor(p["indices"]).reshape(-1, 3).astype(int)
    parents = list(range(len(vertices)))

    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    for a, b, c in faces:
        r = root(int(a))
        parents[root(int(b))] = r
        parents[root(int(c))] = r
    labels = np.array([root(i) for i in range(len(vertices))])
    ids, counts = np.unique(labels, return_counts=True)
    keep = labels == ids[counts.argmax()]
    remap = np.full(len(vertices), -1)
    remap[keep] = np.arange(keep.sum())
    faces = remap[faces[np.all(keep[faces], axis=1)]]
    selected = vertices[keep]
    lo, extent = selected.min(axis=0), np.ptp(selected, axis=0)
    fitted = np.array(box[:3]) + (selected - lo) / extent * np.array(box[3:])
    selected_count = len(fitted)
    if cloth_top is not None:
        if kind != "skirt" or not box[1] < cloth_top < box[1] + box[4]:
            raise ValueError("cloth_top must lie inside skirt cage")
        fitted = fitted[fitted[:, 1] <= cloth_top]
        box = list(box)
        box[4] = cloth_top - box[1]
    # Author retopology: sample the selected source surface into a regular open
    # sheet/cylinder. This intentionally collapses the AI mesh's overlapping layers.
    # Preserve source and label the output as a derived asset, never original topology.
    center = np.array(box[:3]) + np.array(box[3:]) / 2
    rendered, render_faces = [], []
    rw, rh = 64, 40
    source_angles = np.arctan2(fitted[:, 2] - center[2], fitted[:, 0] - center[0])
    for yy in range(rh + 1):
        height = box[1] + box[4] * (1 - yy / rh)
        band = np.abs(fitted[:, 1] - height) <= box[4] / rh
        section = fitted[band]
        section_angles = source_angles[band]
        for xx in range(rw if kind == "skirt" else rw + 1):
            if kind == "skirt":
                angle = xx / rw * 2 * np.pi
                delta = np.abs((section_angles - angle + np.pi) % (2 * np.pi) - np.pi)
                samples = section[delta < 2 * np.pi / rw]
                radius = (
                    np.median(np.linalg.norm(samples[:, [0, 2]] - center[[0, 2]], axis=1))
                    if len(samples)
                    else np.mean(box[3::2]) * 0.5
                )
                rendered.append([center[0] + np.cos(angle) * radius, height, center[2] + np.sin(angle) * radius])
            else:
                low, high = np.quantile(section[:, 0], [0.005, 0.995])
                xpos = low + (high - low) * xx / rw
                samples = section[np.abs(section[:, 0] - xpos) < box[3] / rw]
                zpos = np.median(samples[:, 2]) if len(samples) else np.median(section[:, 2])
                rendered.append([xpos, height, zpos])
    rwidth = rw if kind == "skirt" else rw + 1
    for yy in range(rh):
        for xx in range(rw):
            a, b = yy * rwidth + xx, yy * rwidth + (xx + 1) % rwidth
            render_faces.extend([[a, b, a + rwidth], [b, b + rwidth, a + rwidth]])
    authored = np.array(rendered)
    nearest_row = np.clip(np.rint((box[1] + box[4] - fitted[:, 1]) / box[4] * rh).astype(int), 0, rh)
    if kind == "skirt":
        nearest_column = np.rint((source_angles / (2 * np.pi) % 1) * rw).astype(int) % rw
    else:
        lows = authored[nearest_row * rwidth, 0]
        highs = authored[nearest_row * rwidth + rw, 0]
        nearest_column = np.clip(
            np.rint((fitted[:, 0] - lows) / np.maximum(highs - lows, 1e-6) * rw).astype(int), 0, rw
        )
    errors = np.linalg.norm(fitted - authored[nearest_row * rwidth + nearest_column], axis=1)
    reconstruction_error = dict(
        method="source-to-authored nearest parameter-grid vertex, not closest surface distance",
        p50_m=float(np.quantile(errors, 0.5)),
        p95_m=float(np.quantile(errors, 0.95)),
        max_m=float(errors.max()),
    )
    fitted = authored
    faces = np.array(render_faces)
    # glTF and Godot share Y-up; winding is reversed on glTF import into Godot.
    faces = faces[:, [0, 2, 1]]
    center = np.array(box[:3]) + np.array(box[3:]) / 2
    u = (
        (np.arctan2(fitted[:, 2] - center[2], fitted[:, 0] - center[0]) / (2 * np.pi)) % 1
        if kind == "skirt"
        else (fitted[:, 0] - box[0]) / box[3]
    )
    v = (box[1] + box[4] - fitted[:, 1]) / box[4]
    proxy = []
    for y in range(rows + 1):
        for x in range(columns if kind == "skirt" else columns + 1):
            height = box[1] + box[4] * (1 - y / rows)
            if kind == "skirt":
                angle = x / columns * 2 * np.pi
                # Wider hem, waist follows source cage; explicit authored proxy.
                radius = 0.72 + 0.28 * y / rows
                proxy.append([
                    center[0] + np.cos(angle) * box[3] * 0.5 * radius,
                    height,
                    center[2] + np.sin(angle) * box[5] * 0.5 * radius,
                ])
            else:
                proxy.append([box[0] + x / columns * box[3], height, center[2]])
    width = columns if kind == "skirt" else columns + 1
    x = np.minimum((u * columns).astype(int), columns - 1)
    y = np.minimum((v * rows).astype(int), rows - 1)
    tx, ty = u * columns - x, v * rows - y
    nx = (x + 1) % width
    mapping = np.stack([y * width + x, y * width + nx, (y + 1) * width + x, (y + 1) * width + nx], axis=1)
    weights = np.stack([(1 - tx) * (1 - ty), tx * (1 - ty), (1 - tx) * ty, tx * ty], axis=1)
    offsets = fitted - (np.array(proxy)[mapping] * weights[:, :, None]).sum(axis=1)
    edges = set()
    for yy in range(rows + 1):
        for xx in range(width):
            for dx, dy in [(1, 0), (0, 1), (1, 1), (-1, 1), (2, 0), (0, 2)]:
                nx, ny = xx + dx, yy + dy
                if ny > rows or (kind != "skirt" and not 0 <= nx < width):
                    continue
                a, b = yy * width + xx, ny * width + nx % width
                if a != b:
                    edges.add(tuple(sorted((a, b))))
    result = dict(
        schema=1,
        source=str(source.resolve()),
        source_sha256=hashlib.sha256(raw).hexdigest(),
        derivation="largest connected source component + authored parameterized proxy; original untouched",
        kind=kind,
        original_vertices=len(vertices),
        selected_component_vertices=selected_count,
        render_derivation="authored 64x40 source-sampled sheet/cylinder retopology, overlapping source layers collapsed",
        retained_vertices=len(fitted),
        component_sizes=sorted(counts.tolist(), reverse=True),
        box=box,
        reconstruction_error=reconstruction_error,
        cloth_top=cloth_top,
        vertices=fitted.tolist(),
        indices=faces.flatten().tolist(),
        proxy=proxy,
        edges=sorted(edges),
        mapping=mapping.tolist(),
        weights=weights.tolist(),
        offsets=offsets.tolist(),
        pins=[1.0 if i < width else 0.0 for i in range(len(proxy))],
        columns=columns,
        rows=rows,
    )
    result["binding_revision"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--kind", choices=["cape", "skirt"], required=True)
    parser.add_argument("--box", nargs=6, type=float, required=True)
    parser.add_argument("--columns", type=int, default=24)
    parser.add_argument("--rows", type=int, default=16)
    parser.add_argument("--cloth-top", type=float)
    args = parser.parse_args()
    result = prepare(args.source, args.kind, args.box, args.columns, args.rows, args.cloth_top)
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    with args.destination.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, separators=(",", ":"))
    print(
        json.dumps({
            k: result[k]
            for k in ["source_sha256", "original_vertices", "retained_vertices", "component_sizes", "binding_revision"]
        })
    )
