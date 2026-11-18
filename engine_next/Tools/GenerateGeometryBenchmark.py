# Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT

"""Generate a deterministic 1,000-instance, 10-million-triangle geometry scene."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

import GenerateMaterialBenchmark as material_tools
import GenerateVisualBenchmarks as benchmarks

ASSET_ID = "m4.bench.geometry.sphere"
SCENE_ID = "m4.bench.geometry"
INSTANCE_COUNT = 1000
TRIANGLES_PER_INSTANCE = 10000
CAMERA = {
    "position": [0, 12, 28],
    "target": [0, 10, -14],
    "up": [0, 1, 0],
    "vertical_fov_degrees": 40,
    "near_plane": 0.05,
    "far_plane": 250,
}


def mesh():
    builder = benchmarks.GlbBuilder()
    data = benchmarks.sphere_geometry(rings=51, segments=100)
    assert len(data[4]) // 3 == TRIANGLES_PER_INSTANCE
    builder.attributes = {}
    for channel, values, components in zip(("POSITION", "NORMAL", "TANGENT", "TEXCOORD_0"), data[:4], (3, 3, 4, 2)):
        builder.attributes[channel] = builder.accessor(values, components, 5126)
    builder.indices = builder.accessor(data[4], 1, 5123)
    builder.add_sphere(
        "TenThousandTriangleSphere",
        {
            "name": "BlueDielectric",
            "pbrMetallicRoughness": {
                "baseColorFactor": [0.15, 0.45, 0.8, 1],
                "metallicFactor": 0.15,
                "roughnessFactor": 0.45,
            },
        },
        [0, 0, 0],
        [1, 1, 1],
    )
    builder.document["asset"]["generator"] = "Engine Next self-authored geometry benchmark r1"
    nodes = []
    for depth in range(10):
        for row in range(10):
            for column in range(10):
                index = len(nodes)
                nodes.append({
                    "name": f"Sphere{index:04d}",
                    "mesh": 0,
                    "translation": [(column - 4.5) * 4, row * 2.2 + 1, -depth * 3],
                    "scale": [-1 if index % 4 == 0 else 1, 1, 1],
                })
    builder.document["nodes"] = nodes
    builder.document["scenes"][0]["nodes"] = list(range(INSTANCE_COUNT))
    return builder.finish()


def configurations():
    common = {
        "schema_version": 1,
        "camera": copy.deepcopy(CAMERA),
        "exposure": 1,
        "directional_light": {"direction": [0.4, -0.8, -0.5], "color": [1, 1, 1], "illuminance": 3},
        "point_lights": [],
        "spot_lights": [],
        "shadows": {
            "enabled": False,
            "resolution": 1024,
            "distance": 50,
            "split_lambda": 0.6,
            "depth_bias": 0.0005,
            "normal_bias": 0.01,
        },
        "temporal_aa": {"enabled": False, "history_weight": 0.9, "depth_threshold": 0.01},
        "bloom": {"enabled": False},
        "reflections": {"enabled": False},
        "volumetric_fog": {"enabled": False},
        "particles": [],
    }
    frustum = copy.deepcopy(common)
    frustum["geometry_culling"] = {"enabled": True, "occlusion": False, "max_commands": 262144}
    occlusion = copy.deepcopy(frustum)
    occlusion["geometry_culling"]["occlusion"] = True
    fallback = copy.deepcopy(occlusion)
    fallback["geometry_culling"]["max_commands"] = 1
    temporal = copy.deepcopy(occlusion)
    temporal["temporal_aa"]["enabled"] = True
    return {"Off": common, "Frustum": frustum, "Occlusion": occlusion, "Fallback": fallback, "Temporal": temporal}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--asset-tool", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    payload = mesh()
    entities = [benchmarks.entity(1, "SphereField", ASSET_ID, payload, [0, 0, 0], "static")]
    scene = benchmarks.write_scene(
        args.output,
        "Geometry",
        {"Sphere.glb": payload},
        benchmarks.build_request(SCENE_ID, entities, [benchmarks.asset(ASSET_ID, "Sphere.glb")]),
        "One thousand independently identified sphere instances, each with ten thousand source triangles",
    )
    scene["camera"] = copy.deepcopy(CAMERA)
    scene["source_instance_count"] = INSTANCE_COUNT
    scene["source_triangles_per_instance"] = TRIANGLES_PER_INSTANCE
    scene["source_scene_triangles"] = INSTANCE_COUNT * TRIANGLES_PER_INSTANCE
    scene["mirrored_instances"] = 250
    scene["configuration_templates"] = configurations()
    if args.asset_tool:
        package = args.output / "Geometry.enpak"
        cooked = args.output / "Geometry.engpu"
        compiled = material_tools.run_asset(
            args.asset_tool,
            [
                "compile",
                "--request",
                str(args.output / scene["request"]),
                "--source-root",
                str(args.output / "Geometry"),
                "--output",
                str(package),
            ],
        )
        digest = compiled["package_digest"]
        material_tools.run_asset(args.asset_tool, ["gpu-cook", "--package", str(package), "--output", str(cooked)])
        material_tools.run_asset(args.asset_tool, ["gpu-validate", "--package", str(cooked), "--source-digest", digest])
        directory = args.output / "Configurations"
        directory.mkdir(exist_ok=True)
        for name, template in scene["configuration_templates"].items():
            configuration = copy.deepcopy(template)
            configuration["source_package_sha256"] = digest
            (directory / f"{name}.json").write_bytes(benchmarks.json_bytes(configuration))
        scene["source_package_sha256"] = digest
        scene["package"] = package.name
        scene["gpu_package"] = cooked.name
        scene["asset_tool_sha256"] = hashlib.sha256(args.asset_tool.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 1,
        "generator": "engine_next/Tools/GenerateGeometryBenchmark.py",
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "shared_generator_sha256": hashlib.sha256(Path(benchmarks.__file__).read_bytes()).hexdigest(),
        "provenance": "Self-authored procedural geometry, licensed under MIT with this project",
        "scenes": [scene],
    }
    (args.output / "BenchmarkManifest.json").write_bytes(benchmarks.json_bytes(manifest))
    print(json.dumps({"output": str(args.output), "source_scene_triangles": scene["source_scene_triangles"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
