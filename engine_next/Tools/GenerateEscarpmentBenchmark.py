# Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT
"""Generate the M4 C benchmark: a masonry settlement on a forested rock escarpment."""

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

import GenerateGeometryBenchmark as geometry
import GenerateMaterialBenchmark as material
import GenerateVisualBenchmarks as benchmarks


class Surface:
    def __init__(self):
        self.vertices = []
        self.indices = []

    def quad(self, a, b, c, d):
        start = len(self.vertices)
        self.vertices.extend((a, b, c, d))
        self.indices.extend(start + n for n in (0, 1, 2, 0, 2, 3))

    def box(self, x, y, z, width, height, depth):
        x0, x1 = x - width / 2, x + width / 2
        z0, z1 = z - depth / 2, z + depth / 2
        a, b, c, d = (x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)
        e, f, g, h = [(px, y + height, pz) for px, _, pz in (a, b, c, d)]
        for corners in ((a, b, c, d), (h, g, f, e), (a, e, f, b), (c, g, h, d), (b, f, g, c), (d, h, e, a)):
            self.quad(*corners)

    def rings(self, rows):
        # Counterclockwise around +Y as seen from below. Ring order is bottom to top.
        start = len(self.vertices)
        size = len(rows[0])
        for row in rows:
            self.vertices.extend(row)
        for j in range(len(rows) - 1):
            for i in range(size):
                a = start + j * size + i
                b = start + j * size + (i + 1) % size
                self.indices.extend((a, a + size, b, b, a + size, b + size))
        for j in (0, len(rows) - 1):
            ring = rows[j]
            center = len(self.vertices)
            self.vertices.append(tuple(sum(p[k] for p in ring) / size for k in range(3)))
            for i in range(size):
                a = start + j * size + i
                b = start + j * size + (i + 1) % size
                self.indices.extend((center, a, b) if j == 0 else (center, b, a))

    def primitive(self, glb, color, name):
        normals = [[0.0, 0.0, 0.0] for _ in self.vertices]
        for i in range(0, len(self.indices), 3):
            a, b, c = self.indices[i : i + 3]
            p, q, r = (self.vertices[n] for n in (a, b, c))
            u = [q[k] - p[k] for k in range(3)]
            v = [r[k] - p[k] for k in range(3)]
            cross = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
            if math.hypot(*cross) < 1e-11:
                raise ValueError(f"Degenerate source triangle in {name}")
            for n in (a, b, c):
                for k in range(3):
                    normals[n][k] += cross[k]
        unit = [tuple(x / math.hypot(*n) for x in n) for n in normals]
        glb.attributes = {}
        for channel, values in (("POSITION", self.vertices), ("NORMAL", unit)):
            glb.attributes[channel] = glb.accessor([x for p in values for x in p], 3, 5126)
        mat = len(glb.document["materials"])
        glb.document["materials"].append({
            "name": name,
            "pbrMetallicRoughness": {"baseColorFactor": [*color, 1], "metallicFactor": 0, "roughnessFactor": 0.85},
        })
        return {"attributes": glb.attributes, "indices": glb.accessor(self.indices, 1, 5123), "material": mat}


def masonry():
    stone, roof, timber = Surface(), Surface(), Surface()
    # Staggered individual masonry courses, openings on both public facades.
    for course in range(22):
        y = 0.3 + 0.27 * course
        for side in (-1, 1):
            for i in range(16):
                x = (i - 7.5 + 0.22 * (course % 2)) * 0.52
                window = 7 <= course <= 15 and (2 <= i <= 4 or 11 <= i <= 13)
                door = side == 1 and course < 11 and 7 <= i <= 8
                if not window and not door:
                    stone.box(x, y, side * 2.6, 0.515, 0.265, 0.32)
            for i in range(10):
                stone.box(side * 4.15, y, (i - 4.5) * 0.49, 0.30, 0.265, 0.485)
    stone.box(0, 0, 0, 8.9, 0.30, 5.9)
    for side in (-1, 1):
        # Overlapping roof shingles follow both pitched planes.
        for j in range(12):
            z = side * j * 0.27
            for i in range(22):
                x = (i - 11) * 0.43
                a, b = 8.0 - j * 0.16, 8.0 - (j + 1) * 0.16
                q = [(x, a, z), (x + 0.425, a, z), (x + 0.425, b, z + side * 0.32), (x, b, z + side * 0.32)]
                roof.quad(*(reversed(q) if side == 1 else q))
        for x in (-3.9, 0, 3.9):
            timber.box(x, 0.3, side * 2.8, 0.22, 5.96, 0.16)
    return [
        (stone, (0.55, 0.42, 0.29), "Sandstone"),
        (roof, (0.32, 0.105, 0.065), "Clay shingles"),
        (timber, (0.2, 0.105, 0.06), "Facade beams"),
    ]


def outcrop():
    rock = Surface()
    rows = []
    for j in range(65):
        lat = -1.53 + 3.06 * j / 64
        row = []
        for i in range(96):
            a = math.tau * i / 96
            strata = (
                1
                + 0.10 * math.sin(5 * a + 2 * lat)
                + 0.055 * math.cos(9 * a - 5 * lat)
                + 0.045 * math.sin(27 * lat + 3 * a)
            )
            row.append((
                2.5 * math.cos(lat) * math.cos(a) * strata + 0.38 * math.sin(lat),
                1.65 * (1 + math.sin(lat)),
                1.8 * math.cos(lat) * math.sin(a) * strata,
            ))
        rows.append(row)
    rock.rings(rows)
    return [(rock, (0.31, 0.33, 0.30), "Stratified limestone")]


def conifer():
    trunk, leaves = Surface(), Surface()

    def whorl(surface, profile, segments):
        surface.rings([
            [
                (x + r * math.cos(math.tau * i / segments), y, z + r * math.sin(math.tau * i / segments))
                for i in range(segments)
            ]
            for x, y, z, r in profile
        ])

    whorl(trunk, [(0, 0, 0, 0.38), (0, 3, 0, 0.26), (0, 8, 0, 0.12), (0, 11, 0, 0.025)], 20)
    for j in range(16):
        y = 1.4 + j * 0.55
        length = 2.5 * (1 - j / 18)
        for i in range(14):
            angle = math.tau * i / 14 + j * 0.47
            dx, dz = math.cos(angle), math.sin(angle)
            for t in (0.35, 0.65, 0.93):
                x, z = length * t * dx, length * t * dz
                radius = (0.26 + 0.32 * (1 - t)) * (1 - j / 24)
                whorl(
                    leaves,
                    [
                        (x, y - t * 0.45, z, radius),
                        (x * 0.92, y + 0.22, z * 0.92, radius * 0.81),
                        (x * 0.8, y + 0.62, z * 0.8, 0.03),
                    ],
                    6,
                )
    return [(trunk, (0.22, 0.12, 0.07), "Pine bark"), (leaves, (0.08, 0.25, 0.12), "Needle shoots")]


def layout():
    placements = {key: [] for key in ("Masonry", "Outcrop", "Conifer", "Terrace")}
    for row in range(14):
        for column in range(12):
            x, z = (column - 5.5) * 16, -row * 18
            y = 0.45 * row + 0.8 * math.sin(column * 0.65)
            placements["Terrace"].append((x, y, z, 0, 1))
            placements["Masonry"].append((x - 1.5, y, z, math.pi * (column % 2), 0.88 + 0.08 * (row % 3)))
            for i, (ox, oz) in enumerate(((5, -6), (-5, -6))):
                placements["Outcrop"].append((x + ox, y, z + oz, row * 0.83 + i, 0.7 + 0.16 * ((column + i) % 4)))
            for i, (ox, oz) in enumerate(((-5, 6), (4, 6), (7, -2))):
                placements["Conifer"].append((x + ox, y, z + oz, column * 0.6 + i, 0.66 + 0.1 * ((row + i) % 5)))
    return placements


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--asset-tool", type=Path)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    terrain = Surface()
    terrain.box(0, -5, 0, 16, 5, 18)
    glb = benchmarks.GlbBuilder()
    # Discard the default sphere buffers. Only the four authored meshes are serialized.
    glb.binary.clear()
    for key in ("accessors", "bufferViews"):
        glb.document[key].clear()
    nodes = glb.document["nodes"]
    placements = layout()
    totals = {}
    for name, parts in (
        ("Masonry", masonry()),
        ("Outcrop", outcrop()),
        ("Conifer", conifer()),
        ("Terrace", [(terrain, (0.24, 0.27, 0.16), "Terrace ground")]),
    ):
        primitives = [s.primitive(glb, color, label) for s, color, label in parts]
        idx = len(glb.document["meshes"])
        glb.document["meshes"].append({"name": name, "primitives": primitives})
        for i, (x, y, z, angle, scale) in enumerate(placements[name]):
            nodes.append({
                "name": f"{name}{i:04d}",
                "mesh": idx,
                "translation": [x, y, z],
                "scale": [scale] * 3,
                "rotation": [0, math.sin(angle / 2), 0, math.cos(angle / 2)],
            })
        totals[name] = {
            "instances": len(placements[name]),
            "triangles_per_instance": sum(len(s.indices) // 3 for s, _, _ in parts),
        }
    glb.document["scenes"][0]["nodes"] = list(range(len(nodes)))
    glb.document["asset"]["generator"] = "Engine Next self-authored escarpment settlement"
    payload = glb.finish()
    asset_id = "m4.bench.c.escarpment.settlement"
    entities = [benchmarks.entity(1, "EscarpmentSettlement", asset_id, payload, [0, 0, 0], "static")]
    scene = benchmarks.write_scene(
        root,
        "Escarpment",
        {"Settlement.glb": payload},
        benchmarks.build_request("m4.bench.c.escarpment", entities, [benchmarks.asset(asset_id, "Settlement.glb")]),
        "Fourteen terraced streets with masonry facades, layered rock outcrops and conifer stands",
    )
    scene["camera"] = {
        "position": [0, 6, 21],
        "target": [0, 7, -65],
        "up": [0, 1, 0],
        "vertical_fov_degrees": 52,
        "near_plane": 0.1,
        "far_plane": 420,
    }
    scene["mesh_counts"] = totals
    scene["source_instance_count"] = len(nodes)
    scene["source_scene_triangles"] = sum(s["instances"] * s["triangles_per_instance"] for s in totals.values())
    if len(nodes) < 1000 or scene["source_scene_triangles"] < 10_000_000:
        raise ValueError("Insufficient benchmark geometry")
    if args.asset_tool:
        package, cooked = root / "Escarpment.enpak", root / "Escarpment.engpu"

        def run(command, *arguments):
            return material.run_asset(args.asset_tool, [command, *map(str, arguments)])

        digest = run(
            "compile", "--request", root / scene["request"], "--source-root", root / "Escarpment", "--output", package
        )["package_digest"]
        run("validate", "--package", package)
        run("gpu-cook-v3", "--package", package, "--output", cooked)
        run("gpu-validate", "--package", cooked, "--source-package", package)
        folder = root / "Configurations"
        folder.mkdir(exist_ok=True)
        for mode, template in geometry.configurations().items():
            config = copy.deepcopy(template)
            config.update(camera=scene["camera"], source_package_sha256=digest)
            if mode in ("Occlusion", "Temporal"):
                config["geometry_culling"].update(
                    lod_enabled=True,
                    pixel_error=2.0,
                    page_gpu_bytes=16777216,
                    page_staging_bytes=4194304,
                    max_page_loads=4,
                )
            (folder / f"{mode}.json").write_bytes(benchmarks.json_bytes(config))
        scene.update(source_package_sha256=digest, package=package.name, gpu_package=cooked.name)
    manifest = {
        "schema_version": 1,
        "license": "MIT",
        "provenance": "All geometry and materials generated by this project.",
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scenes": [scene],
    }
    (root / "BenchmarkManifest.json").write_bytes(benchmarks.json_bytes(manifest))
    print(json.dumps(totals), scene["source_instance_count"], scene["source_scene_triangles"])


if __name__ == "__main__":
    main()
