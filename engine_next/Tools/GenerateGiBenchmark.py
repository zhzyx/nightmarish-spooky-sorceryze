# Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT

"""Generate the self-authored A-room GI fixture and optional cooked packages."""

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

import GenerateMaterialBenchmark as materials
import GenerateReflectionBenchmark as geometry
import GenerateVisualBenchmarks as benchmarks

SCENE_ID = "m4.bench.a.gi"
ASSET_ID = "m4.bench.gi.room"
SEED = 20261118
CAMERA = {
    "position": [0, 2.5, 3.8],
    "target": [0, 2.1, -1.5],
    "up": [0, 1, 0],
    "vertical_fov_degrees": 75,
    "near_plane": 0.05,
    "far_plane": 100,
}


def surface(name, color, metallic=0, roughness=0.8, emissive=None):
    result = geometry.material(name, color, metallic, roughness, emissive)
    result["doubleSided"] = True
    return result


def add_surface(builder, records, name, corners, normal, tangent, material):
    edge_a = [corners[1][axis] - corners[0][axis] for axis in range(3)]
    edge_b = [corners[2][axis] - corners[0][axis] for axis in range(3)]
    cross = [
        edge_a[1] * edge_b[2] - edge_a[2] * edge_b[1],
        edge_a[2] * edge_b[0] - edge_a[0] * edge_b[2],
        edge_a[0] * edge_b[1] - edge_a[1] * edge_b[0],
    ]
    if sum(cross[axis] * normal[axis] for axis in range(3)) <= 0:
        raise ValueError(f"Invalid authored winding for {name}")
    records.append({
        "name": name,
        "material_index": len(builder.document["materials"]),
        "node_index": len(builder.document["nodes"]),
        "corners": corners,
        "normal": normal,
        "base_color": material["pbrMetallicRoughness"]["baseColorFactor"],
        "emissive": material.get("emissiveFactor", [0, 0, 0]),
    })
    geometry.add_quad(builder, name, corners, normal, tangent, material)


def room_geometry():
    builder = benchmarks.GlbBuilder()
    builder.document["asset"]["generator"] = "Engine Next self-authored A-room GI benchmark r1"
    records = []
    add_surface(
        builder,
        records,
        "WhiteFloor",
        [[-4, 0, -4], [-4, 0, 4], [4, 0, 4], [4, 0, -4]],
        [0, 1, 0],
        [1, 0, 0],
        surface("WhiteFloor", [0.75] * 3),
    )
    add_surface(
        builder,
        records,
        "WhiteCeiling",
        [[-4, 5, -4], [4, 5, -4], [4, 5, 4], [-4, 5, 4]],
        [0, -1, 0],
        [1, 0, 0],
        surface("WhiteCeiling", [0.75] * 3),
    )
    add_surface(
        builder,
        records,
        "RedWall",
        [[-4, 0, 4], [-4, 0, -4], [-4, 5, -4], [-4, 5, 4]],
        [1, 0, 0],
        [0, 0, -1],
        surface("RedWall", [0.75, 0.025, 0.025]),
    )
    add_surface(
        builder,
        records,
        "GreenWall",
        [[4, 0, -4], [4, 0, 4], [4, 5, 4], [4, 5, -4]],
        [-1, 0, 0],
        [0, 0, 1],
        surface("GreenWall", [0.025, 0.65, 0.04]),
    )
    add_surface(
        builder,
        records,
        "WhiteBack",
        [[-4, 0, -4], [4, 0, -4], [4, 5, -4], [-4, 5, -4]],
        [0, 0, 1],
        [1, 0, 0],
        surface("WhiteBack", [0.75] * 3),
    )
    add_surface(
        builder,
        records,
        "BlueInset",
        [[-0.85, 0.6, -3.98], [0.85, 0.6, -3.98], [0.85, 2.4, -3.98], [-0.85, 2.4, -3.98]],
        [0, 0, 1],
        [1, 0, 0],
        surface("BlueInset", [0.035, 0.09, 0.75]),
    )
    add_surface(
        builder,
        records,
        "CeilingEmitter",
        [[-1.2, 4.98, -2.6], [1.2, 4.98, -2.6], [1.2, 4.98, 0.4], [-1.2, 4.98, 0.4]],
        [0, -1, 0],
        [1, 0, 0],
        surface("CeilingEmitter", [0, 0, 0], emissive=[1, 0.85, 0.6]),
    )
    # Closed, thin baffle. Each face has its own legal glTF primitive.
    x0, x1, y0, y1, z0, z1 = -0.12, 0.12, 0, 2.4, -0.8, 1.0
    faces = [
        ("Front", [[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], [0, 0, 1], [1, 0, 0]),
        ("Back", [[x1, y0, z0], [x0, y0, z0], [x0, y1, z0], [x1, y1, z0]], [0, 0, -1], [-1, 0, 0]),
        ("Left", [[x0, y0, z0], [x0, y0, z1], [x0, y1, z1], [x0, y1, z0]], [-1, 0, 0], [0, 0, 1]),
        ("Right", [[x1, y0, z1], [x1, y0, z0], [x1, y1, z0], [x1, y1, z1]], [1, 0, 0], [0, 0, -1]),
        ("Top", [[x0, y1, z0], [x0, y1, z1], [x1, y1, z1], [x1, y1, z0]], [0, 1, 0], [1, 0, 0]),
        ("Bottom", [[x0, y0, z1], [x0, y0, z0], [x1, y0, z0], [x1, y0, z1]], [0, -1, 0], [1, 0, 0]),
    ]
    for face, corners, normal, tangent in faces:
        add_surface(builder, records, "Baffle" + face, corners, normal, tangent, surface("Baffle", [0.55] * 3))
    for name, position, metallic, roughness in [
        ("RoughSphere", [-1.7, 0.85, 0.1], 0, 0.85),
        ("MetalSphere", [1.7, 0.8, 0.1], 1, 0.18),
    ]:
        material_index = len(builder.document["materials"])
        builder.add_sphere(name, surface(name, [0.7] * 3, metallic, roughness), position, [0.8] * 3)
        records.append({
            "name": name,
            "material_index": material_index,
            "node_index": len(builder.document["nodes"]) - 1,
            "position": position,
            "radius": 0.8,
            "metallic": metallic,
            "roughness": roughness,
        })
    return builder.finish(), records


def configurations(records):
    common = {
        "schema_version": 1,
        "camera": copy.deepcopy(CAMERA),
        "exposure": 1,
        "exposure_settings": {"mode": "manual", "manual_ev100": math.log2(1 / 1.2)},
        "directional_light": {"direction": [0.2, -0.3, -1], "color": [1, 1, 1], "illuminance": 3},
        "point_lights": [],
        "spot_lights": [],
        "shadows": {
            "enabled": True,
            "resolution": 1024,
            "distance": 30,
            "split_lambda": 0.6,
            "depth_bias": 0.0005,
            "normal_bias": 0.01,
        },
        "temporal_aa": {"enabled": False, "history_weight": 0.9, "depth_threshold": 0.01},
        "bloom": {"enabled": False},
        "reflections": {"enabled": False},
        "volumetric_fog": {"enabled": False},
        "particles": [],
        "global_illumination": {
            "enabled": True,
            "world_bounds": {"minimum": [-4.4, 0.2, -8], "maximum": [4.4, 4.8, 8]},
            "probe_counts": [12, 8, 12],
            "clipmap_levels": 2,
            "updates_per_frame": 256,
            "rays_per_probe": 64,
            "trace_distance": 24,
            "hysteresis": 0.85,
            "normal_bias": 0.08,
            "view_bias": 0.04,
            "bounce_strength": 1,
            "history_change_threshold": 0.25,
            "max_gpu_bytes": 134217728,
        },
    }
    off = copy.deepcopy(common)
    off["global_illumination"]["enabled"] = False
    single = copy.deepcopy(common)
    single["global_illumination"]["bounce_strength"] = 0
    dynamic = copy.deepcopy(common)
    dynamic["light_animation"] = {
        "loop": True,
        "interpolation": "step",
        "keyframes": [
            {"seconds": 0, "multiplier": 0.05},
            {"seconds": 3, "multiplier": 1},
            {"seconds": 6, "multiplier": 0.05},
            {"seconds": 9, "multiplier": 1},
            {"seconds": 12, "multiplier": 0.05},
        ],
    }
    combined = copy.deepcopy(common)
    combined["reflections"] = {"enabled": True, "max_distance": 24, "max_steps": 128}
    combined["material_overrides"] = [
        {
            "asset_id": ASSET_ID,
            "material_index": entry["material_index"],
            "clearcoat": {"factor": 1, "roughness": 0.18},
            "anisotropy": {"strength": 0.65 if entry["name"] == "MetalSphere" else 0, "rotation_radians": 0.6},
        }
        for entry in records
        if entry["name"] in {"RoughSphere", "MetalSphere"}
    ]
    reference = copy.deepcopy(common)
    reference["global_illumination"]["updates_per_frame"] = 2304
    reference["global_illumination"]["rays_per_probe"] = 256
    return {
        "Off": off,
        "SingleBounce": single,
        "MultipleBounce": common,
        "DynamicLight": dynamic,
        "MaterialCombined": combined,
        "StaticReference": reference,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--asset-tool", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    payload, records = room_geometry()
    scene = benchmarks.write_scene(
        args.output,
        "A-GI",
        {"GiRoom.glb": payload},
        benchmarks.build_request(
            SCENE_ID,
            [benchmarks.entity(1, "GiRoom", ASSET_ID, payload, [0, 0, 0], "static")],
            [benchmarks.asset(ASSET_ID, "GiRoom.glb")],
        ),
        "Open-front 8x5x8 room with RGB surfaces, emissive ceiling, closed baffle and two material spheres",
    )
    scene["camera"] = copy.deepcopy(CAMERA)
    scene["surfaces"] = records
    scene["configuration_templates"] = configurations(records)
    scene["configuration_binding"] = "Insert compiled M3 source digest into source_package_sha256."
    scene["inspection_targets"] = {
        "red_bounce_floor": [-2.8, 0, -1.8],
        "green_bounce_floor": [2.8, 0, -1.8],
        "baffle_shadow_floor": [0.4, 0, -1.8],
        "emissive_ceiling": [0, 4.98, -1.1],
    }
    scene["measurement_notes"] = [
        "All standard configurations use 2304 probes, 256 updates and 64 rays per probe; a complete sweep is nine submissions.",
        "Use at least 180 static frames before comparing linear HDR; record actual history validity and update telemetry.",
        "SingleBounce disables previous-probe feedback; MultipleBounce enables feedback with identical direct lights.",
        "DynamicLight uses the production directional-light timeline and requires actual frame times for transition measurements.",
        "StaticReference raises the ray/update budget for offline comparison; its timings are separate from standard configurations.",
        "The environment fallback remains present in Off, so colour-bleed and occlusion comparisons require measured HDR differences.",
    ]
    if args.asset_tool:
        package = args.output / "GiRoom.enpak"
        cooked = args.output / "GiRoom.engpu"
        compiled = materials.run_asset(
            args.asset_tool,
            [
                "compile",
                "--request",
                str(args.output / scene["request"]),
                "--source-root",
                str(args.output / "A-GI"),
                "--output",
                str(package),
            ],
        )
        digest = compiled["package_digest"]
        materials.run_asset(args.asset_tool, ["gpu-cook", "--package", str(package), "--output", str(cooked)])
        validated = materials.run_asset(
            args.asset_tool, ["gpu-validate", "--package", str(cooked), "--source-digest", digest]
        )
        config_dir = args.output / "Configurations"
        config_dir.mkdir(exist_ok=True)
        for name, template in scene["configuration_templates"].items():
            bound = copy.deepcopy(template)
            bound["source_package_sha256"] = digest
            (config_dir / f"{name}.json").write_bytes(benchmarks.json_bytes(bound))
        scene.update({
            "source_package_sha256": digest,
            "package": package.name,
            "gpu_package": cooked.name,
            "gpu_validation_status": validated.get("status", "passed"),
            "asset_tool": {
                "name": args.asset_tool.name,
                "sha256": hashlib.sha256(args.asset_tool.read_bytes()).hexdigest(),
            },
        })
    manifest = {
        "schema_version": 1,
        "generator": "engine_next/Tools/GenerateGiBenchmark.py",
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "shared_generators": {
            Path(module.__file__).name: hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
            for module in (benchmarks, geometry, materials)
        },
        "seed": SEED,
        "provenance": "Self-authored deterministic geometry, MIT project license",
        "measurement_status": "GPU GI measurements pending",
        "scenes": [scene],
    }
    (args.output / "BenchmarkManifest.json").write_bytes(benchmarks.json_bytes(manifest))
    print(json.dumps({"output": str(args.output), "source_package_sha256": scene.get("source_package_sha256")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
