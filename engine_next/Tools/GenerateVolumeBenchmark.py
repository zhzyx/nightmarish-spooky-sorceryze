# Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT

"""Generate a deterministic, self-authored fog and transparency benchmark.

The source scene uses the existing M3 BuildRequest and standard glTF alpha
modes. Supply --asset-tool to compile/cook both packages and bind all render
configurations to the resulting source digest.
"""

import argparse
import copy
import hashlib
import json
import math
import subprocess
from pathlib import Path

import GenerateReflectionBenchmark as geometry
import GenerateVisualBenchmarks as benchmarks

SCENE_ID = "m4.bench.volume"
CAMERA = {
    "position": [0, 1, 6],
    "target": [0, 1, 0],
    "up": [0, 1, 0],
    "vertical_fov_degrees": 50,
    "near_plane": 0.05,
    "far_plane": 100,
}


def material(name, color, *, alpha=1, metallic=0, roughness=0.7, emission=None, mode="OPAQUE"):
    value = {
        "name": name,
        "pbrMetallicRoughness": {
            "baseColorFactor": [*color, alpha],
            "metallicFactor": metallic,
            "roughnessFactor": roughness,
        },
        "occlusionTexture": {"index": 0, "strength": 1},
    }
    if emission is not None:
        value["emissiveFactor"] = emission
    if mode != "OPAQUE":
        value["alphaMode"] = mode
        value["doubleSided"] = True
    if mode == "MASK":
        value["alphaCutoff"] = 0.5
        value["pbrMetallicRoughness"]["baseColorTexture"] = {"index": 1}
    return value


def add_box(builder, name, low, high, surface):
    x0, y0, z0 = low
    x1, y1, z1 = high
    faces = [
        ("Right", [[x1, y0, z1], [x1, y0, z0], [x1, y1, z0], [x1, y1, z1]], [1, 0, 0], [0, 0, -1]),
        ("Left", [[x0, y0, z0], [x0, y0, z1], [x0, y1, z1], [x0, y1, z0]], [-1, 0, 0], [0, 0, 1]),
        ("Top", [[x0, y1, z1], [x1, y1, z1], [x1, y1, z0], [x0, y1, z0]], [0, 1, 0], [1, 0, 0]),
        ("Bottom", [[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1]], [0, -1, 0], [1, 0, 0]),
        ("Front", [[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], [0, 0, 1], [1, 0, 0]),
        ("Back", [[x1, y0, z0], [x0, y0, z0], [x0, y1, z0], [x1, y1, z0]], [0, 0, -1], [-1, 0, 0]),
    ]
    for suffix, corners, normal, tangent in faces:
        geometry.add_quad(builder, name + suffix, corners, normal, tangent, copy.deepcopy(surface))


def scene_geometry():
    builder = benchmarks.GlbBuilder()
    builder.document["asset"]["generator"] = "Engine Next self-authored volume benchmark r1"
    mask = bytearray()
    for y in range(8):
        for x in range(8):
            mask.extend([255, 255, 255, 255 if (x + y) % 2 else 0])
    builder.add_textures({
        "BlackOcclusion.png": benchmarks.png_rgba(1, 1, bytes([0, 0, 0, 255])),
        "MaskChecker.png": benchmarks.png_rgba(8, 8, bytes(mask)),
    })
    geometry.upright_quad(
        builder,
        "BackgroundWall",
        [-4, -1, 4, 4],
        -1,
        material("WallRadiance", [0, 0, 0], metallic=1, emission=[0.4, 0.4, 0.4]),
    )
    geometry.floor_quad(builder, "Floor", [-4, 4, 4, -2], -1, material("Floor", [0.3, 0.3, 0.3]))
    add_box(builder, "ThinOccluder", [0.9, -1, 0.2], [1.0, 1.2, 1.0], material("Occluder", [0.2] * 3))
    geometry.upright_quad(builder, "RoughPanel", [-3, 1.5, -1.8, 2.6], -0.7, material("Rough", [0.7, 0.3, 0.1]))
    geometry.upright_quad(
        builder, "MetalPanel", [1.8, 1.5, 3, 2.6], -0.7, material("Metal", [0.8, 0.8, 0.8], metallic=1, roughness=0.08)
    )
    layers = [(0.2, 0.25, [1, 0, 0]), (0.8, 0.5, [0, 1, 0]), (1.4, 0.75, [0, 0, 1])]
    for index, (depth, alpha, color) in enumerate(layers):
        geometry.upright_quad(
            builder,
            f"TransparentLayer{index}",
            [-0.6, -0.4, 0.6, 0.6],
            depth,
            material(f"Blend{index}", [0, 0, 0], alpha=alpha, metallic=1, emission=color, mode="BLEND"),
        )
    geometry.upright_quad(
        builder,
        "MaskChecker",
        [1.3, -0.5, 2.2, 0.6],
        0.5,
        material("Mask", [0, 0, 0], metallic=1, emission=[1, 1, 0], mode="MASK"),
    )
    return builder.finish()


def anchor(entity_id, name, position, *, parent=0, gameplay="static"):
    return {
        "entity_id": entity_id,
        "name": name,
        "node_type": "Node3D",
        "parent_entity_id": parent,
        "transform": {"translation": position, "rotation_xyzw": [0, 0, 0, 1], "scale": [1, 1, 1]},
        "gameplay": {"kind": gameplay},
        "assets": [],
    }


def configurations():
    common = {
        "schema_version": 1,
        "camera": copy.deepcopy(CAMERA),
        "exposure": 1,
        "exposure_settings": {"mode": "manual", "manual_ev100": math.log2(1 / 1.2)},
        "directional_light": {"direction": [0.5, -0.7, -0.5], "color": [1, 0.95, 0.9], "illuminance": 3},
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
    }
    homogeneous = copy.deepcopy(common)
    homogeneous["volumetric_fog"] = {
        "enabled": True,
        "distance": 25,
        "cell_pixels": 16,
        "depth_slices": 64,
        "density": 0.08,
        "height_falloff": 0,
        "albedo": [0, 0, 0],
        "emission": [0, 0, 0],
        "history_weight": 0,
    }
    emission = copy.deepcopy(homogeneous)
    emission["volumetric_fog"]["emission"] = [0.04, 0.02, 0.01]
    local = copy.deepcopy(common)
    local["volumetric_fog"] = {
        "enabled": True,
        "density": 0,
        "height_falloff": 0,
        "history_weight": 0.85,
        "local_volumes": [
            {"shape": "box", "entity_id": 11, "extent": [0.7, 1.4, 1.0], "density": 0.25, "albedo": [0.9, 0.9, 0.9]},
            {"shape": "sphere", "entity_id": 12, "extent": [0.9, 0.9, 0.9], "density": 0.3, "albedo": [0.7, 0.85, 1]},
        ],
    }
    particle = copy.deepcopy(common)
    particle["particles"] = [
        {
            "emitter_id": 1,
            "entity_id": 13,
            "enabled": True,
            "loop": True,
            "seed": 20261117,
            "rate": 20,
            "lifetime": 2,
            "position_spread": [0.25, 0.1, 0.25],
            "velocity": [0, 0.8, 0],
            "velocity_spread": [0.2, 0.15, 0.2],
            "start_size": 0.15,
            "end_size": 0.4,
            "start_color": [1, 0.35, 0.1, 0.8],
            "end_color": [1, 0.6, 0.2, 0],
        }
    ]
    combined = copy.deepcopy(local)
    combined["particles"] = copy.deepcopy(particle["particles"])
    combined["temporal_aa"]["enabled"] = True
    combined["volumetric_fog"]["density"] = 0.015
    combined["volumetric_fog"]["height_falloff"] = 0.1
    automatic = copy.deepcopy(combined)
    automatic["exposure_settings"] = {"mode": "automatic"}
    return {
        "Off": common,
        "Homogeneous": homogeneous,
        "HomogeneousEmission": emission,
        "Local": local,
        "Transparent": copy.deepcopy(common),
        "Particle": particle,
        "Combined": combined,
        "CombinedAutomatic": automatic,
    }


def run_asset(tool, arguments):
    result = subprocess.run(
        [str(tool), *arguments], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )
    if result.returncode:
        raise RuntimeError(f"next_asset failed with exit {result.returncode}: {result.stdout}{result.stderr}")
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--asset-tool", type=Path, help="Existing next_asset executable for compile/cook and bound configurations"
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    payload = scene_geometry()
    entities = [
        benchmarks.entity(1, "VolumeGeometry", SCENE_ID, payload, [0, 0, 0], "static"),
        anchor(11, "FogBoxAnchor", [-1.2, 0, 0.5], gameplay="player_spawn"),
        anchor(12, "FogSphereAnchor", [1.2, 0, 0.5], gameplay="player_spawn"),
        anchor(13, "ParticleSource", [0, -0.5, 0], parent=11),
    ]
    scene = benchmarks.write_scene(
        args.output,
        "Volume",
        {"VolumeScene.glb": payload},
        benchmarks.build_request(SCENE_ID, entities, [benchmarks.asset(SCENE_ID, "VolumeScene.glb")]),
        "Wall, occluder, material panels, three ordered transparent layers, MASK and movable effect anchors",
    )
    scene["camera"] = copy.deepcopy(CAMERA)
    scene["configuration_templates"] = configurations()
    scene["analytic_checks"] = {
        "wall": {"z": -1, "emissive_radiance": [0.4, 0.4, 0.4]},
        "absorption": {"density": 0.08, "transmittance": "exp(-density * physical camera-to-wall ray length)"},
        "emission": {
            "source_per_world_unit": [0.04, 0.02, 0.01],
            "scatter": "source/density * (1-transmittance), before tone mapping",
        },
        "wall_roi_world": {"x": [-0.3, 0.3], "y": [1.6, 2.1]},
        "transparent_layers_far_to_near": [
            {"z": 0.2, "alpha": 0.25, "emissive": [1, 0, 0]},
            {"z": 0.8, "alpha": 0.5, "emissive": [0, 1, 0]},
            {"z": 1.4, "alpha": 0.75, "emissive": [0, 0, 1]},
        ],
        "scope": "Off and Transparent both include standard GLB transparency; Off disables fog and particles only.",
    }
    if args.asset_tool:
        package = args.output / "Volume.enpak"
        cooked = args.output / "Volume.engpu"
        compiled = run_asset(
            args.asset_tool,
            [
                "compile",
                "--request",
                str(args.output / scene["request"]),
                "--source-root",
                str(args.output / "Volume"),
                "--output",
                str(package),
            ],
        )
        digest = compiled["package_digest"]
        run_asset(args.asset_tool, ["gpu-cook", "--package", str(package), "--output", str(cooked)])
        validated = run_asset(args.asset_tool, ["gpu-validate", "--package", str(cooked), "--source-digest", digest])
        configuration_dir = args.output / "Configurations"
        configuration_dir.mkdir(exist_ok=True)
        for name, template in scene["configuration_templates"].items():
            bound = copy.deepcopy(template)
            bound["source_package_sha256"] = digest
            (configuration_dir / f"{name}.json").write_bytes(benchmarks.json_bytes(bound))
        scene["source_package_sha256"] = digest
        scene["package"] = str(package)
        scene["gpu_package"] = str(cooked)
        scene["gpu_validation"] = validated
        scene["asset_tool_sha256"] = hashlib.sha256(args.asset_tool.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 1,
        "generator": "engine_next/Tools/GenerateVolumeBenchmark.py",
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "shared_generator_sha256": hashlib.sha256(Path(benchmarks.__file__).read_bytes()).hexdigest(),
        "geometry_helpers_sha256": hashlib.sha256(Path(geometry.__file__).read_bytes()).hexdigest(),
        "revision": benchmarks.REVISION,
        "provenance": "Self-authored procedural geometry and PNG textures, fixed particle seed 20261117",
        "scenes": [scene],
    }
    (args.output / "BenchmarkManifest.json").write_bytes(benchmarks.json_bytes(manifest))
    print(
        json.dumps({
            "output": str(args.output),
            "request": scene["request"],
            "source_package_sha256": scene.get("source_package_sha256"),
        })
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
