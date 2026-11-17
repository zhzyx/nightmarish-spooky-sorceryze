# Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT

"""Generate deterministic, self-authored material comparison scene B.

Supply --asset-tool to compile and cook the M3 package and bind the configuration
variants to its digest. The scene and textures use the existing GLB contract.
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

SCENE_ID = "m4.bench.b.materials"
ASSET_ID = "m4.bench.materials"
SEED = 20261117
CAMERA = {
    "position": [0, 2.6, 8.5],
    "target": [0, 0, 0],
    "up": [0, 1, 0],
    "vertical_fov_degrees": 46,
    "near_plane": 0.05,
    "far_plane": 100,
}


def material(name, color, metallic, roughness, *, normal=False, alpha=1):
    surface = {
        "name": name,
        "pbrMetallicRoughness": {
            "baseColorFactor": [*color, alpha],
            "metallicFactor": metallic,
            "roughnessFactor": roughness,
        },
    }
    if normal:
        surface["normalTexture"] = {"index": 0, "scale": 0.5}
    if alpha < 1:
        surface["alphaMode"] = "BLEND"
        surface["doubleSided"] = True
    return surface


def scene_geometry():
    images = {"MaterialNormal.png": benchmarks.textures()["Normal.png"]}
    builder = benchmarks.GlbBuilder()
    builder.document["asset"]["generator"] = "Engine Next self-authored material benchmark r1"
    builder.add_textures(images)
    cases = [
        ("Plastic", [0.12, 0.32, 0.75], 0, 0.3, [-2.4, 0.85, 0], False, False),
        ("Metal", [0.8, 0.8, 0.8], 1, 0.3, [-0.8, 0.85, 0], False, False),
        ("CoatedPlastic", [0.75, 0.12, 0.06], 0, 0.4, [0.8, 0.85, 0], False, False),
        ("PositiveAnisotropy", [0.85, 0.6, 0.2], 1, 0.4, [2.4, 0.85, 0], False, False),
        ("NegativeAnisotropy", [0.85, 0.6, 0.2], 1, 0.4, [-2.4, -0.75, 0], False, False),
        ("RotatedAnisotropy", [0.85, 0.6, 0.2], 1, 0.4, [-0.8, -0.75, 0], False, False),
        ("MirroredNormal", [0.4, 0.65, 0.8], 0.65, 0.35, [0.8, -0.75, 0], True, True),
    ]
    identities = []
    for name, color, metallic, roughness, position, normal, mirrored in cases:
        scale = [-0.6 if mirrored else 0.6, 0.6, 0.6]
        builder.add_sphere(name, material(name, color, metallic, roughness, normal=normal), position, scale)
        identities.append({
            "name": name,
            "material_index": len(builder.document["materials"]) - 1,
            "node_index": len(builder.document["nodes"]) - 1,
            "geometry": "sphere",
            "position": position,
            "scale": scale,
            "metallic": metallic,
            "roughness": roughness,
            "normal_map": normal,
            "negative_determinant": mirrored,
            "alpha_mode": "OPAQUE",
        })
    geometry.upright_quad(
        builder,
        "BlendNormalPanel",
        [1.8, -1.35, 3, -0.15],
        0.25,
        material("BlendNormalPanel", [0.15, 0.8, 0.4], 0.25, 0.35, normal=True, alpha=0.55),
    )
    identities.append({
        "name": "BlendNormalPanel",
        "material_index": len(builder.document["materials"]) - 1,
        "node_index": len(builder.document["nodes"]) - 1,
        "geometry": "plane",
        "bounds_xy": [1.8, -1.35, 3, -0.15],
        "z": 0.25,
        "metallic": 0.25,
        "roughness": 0.35,
        "normal_map": True,
        "negative_determinant": False,
        "alpha_mode": "BLEND",
        "alpha": 0.55,
    })
    geometry.floor_quad(builder, "MirrorFloor", [-4, 3, 4, -2], -1.4, material("MirrorFloor", [0.5] * 3, 1, 0.08))
    geometry.upright_quad(builder, "Backdrop", [-4, -1.4, 4, 2], -1.2, material("Backdrop", [0.12, 0.14, 0.18], 0, 0.8))
    staging = [
        {"name": "MirrorFloor", "material_index": 8, "purpose": "SSR receiver"},
        {"name": "Backdrop", "material_index": 9, "purpose": "Opaque surface behind the BLEND panel"},
    ]
    return builder.finish(), images, identities, staging


def override(index, *, clearcoat=0, anisotropy=0, rotation=0):
    return {
        "asset_id": ASSET_ID,
        "material_index": index,
        "clearcoat": {"factor": clearcoat, "roughness": 0.12},
        "anisotropy": {"strength": anisotropy, "rotation_radians": rotation},
    }


def configurations():
    common = {
        "schema_version": 1,
        "camera": copy.deepcopy(CAMERA),
        "exposure": 1,
        "exposure_settings": {"mode": "manual", "manual_ev100": math.log2(1 / 1.2)},
        "directional_light": {"direction": [0.5, -0.7, -0.5], "color": [1, 0.96, 0.9], "illuminance": 3},
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
    zero = copy.deepcopy(common)
    zero["material_overrides"] = [override(index) for index in range(10)]
    coat = copy.deepcopy(common)
    coat["material_overrides"] = [override(index, clearcoat=1) for index in [0, 1, 2, 6, 7]]
    anisotropy = copy.deepcopy(common)
    anisotropy["material_overrides"] = [
        override(index, anisotropy=-0.85 if index == 4 else 0.85, rotation=math.pi / 2 if index == 5 else 0)
        for index in [1, 3, 4, 5, 6, 7]
    ]
    rotated = copy.deepcopy(anisotropy)
    for entry in rotated["material_overrides"]:
        entry["anisotropy"]["rotation_radians"] += math.pi / 2
    combined = copy.deepcopy(common)
    combined["material_overrides"] = [
        override(
            index,
            clearcoat=1 if index in [0, 1, 2, 6, 7] else 0,
            anisotropy=(-0.85 if index == 4 else 0.85) if index in [1, 3, 4, 5, 6, 7] else 0,
            rotation=math.pi / 2 if index == 5 else 0,
        )
        for index in range(8)
    ]
    environment = copy.deepcopy(combined)
    environment["directional_light"]["illuminance"] = 0
    ssr = copy.deepcopy(combined)
    ssr["reflections"] = {
        "enabled": True,
        "max_distance": 30,
        "thickness": 0.1,
        "normal_bias": 0.02,
        "max_steps": 128,
        "max_roughness": 0.8,
    }
    temporal = copy.deepcopy(ssr)
    temporal["temporal_aa"]["enabled"] = True
    temporal["bloom"] = {"enabled": True, "intensity": 0.1, "mip_count": 6}
    return {
        "Default": common,
        "ZeroOverrides": zero,
        "Clearcoat": coat,
        "Anisotropy": anisotropy,
        "AnisotropyRotated": rotated,
        "Combined": combined,
        "EnvironmentOnly": environment,
        "SSRCombined": ssr,
        "TAABloomCombined": temporal,
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
    parser.add_argument("--asset-tool", type=Path, help="Existing next_asset for compile/cook and bound configurations")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    payload, images, cases, staging = scene_geometry()
    scene = benchmarks.write_scene(
        args.output,
        "B-Materials",
        {"Materials.glb": payload, **images},
        benchmarks.build_request(
            SCENE_ID,
            [benchmarks.entity(1, "MaterialCases", ASSET_ID, payload, [0, 0, 0], "static")],
            [benchmarks.asset(ASSET_ID, "Materials.glb")],
        ),
        "Seven material spheres and one BLEND panel, with a mirror floor and opaque backdrop",
    )
    scene["camera"] = copy.deepcopy(CAMERA)
    scene["asset_id"] = ASSET_ID
    scene["material_cases"] = cases
    scene["staging_materials"] = staging
    scene["configuration_templates"] = configurations()
    scene["configuration_binding"] = "Insert the compiled M3 source package digest into source_package_sha256."
    scene["comparison_pairs"] = [
        {
            "first": "Default",
            "second": "ZeroOverrides",
            "expected": "Identical output pixels under identical run parameters",
        },
        {"first": "Anisotropy", "second": "AnisotropyRotated", "expected": "Orientation-dependent highlight changes"},
    ]
    scene["pending_configurations"] = [
        {
            "name": "DirectOnly",
            "status": "pending",
            "reason": "The current render configuration has no environment-disable field.",
        }
    ]
    if args.asset_tool:
        package = args.output / "Materials.enpak"
        cooked = args.output / "Materials.engpu"
        compiled = run_asset(
            args.asset_tool,
            [
                "compile",
                "--request",
                str(args.output / scene["request"]),
                "--source-root",
                str(args.output / "B-Materials"),
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
        scene["package"] = package.name
        scene["gpu_package"] = cooked.name
        scene["gpu_validation_status"] = validated.get("status", "passed")
        scene["asset_tool"] = {
            "name": args.asset_tool.name,
            "sha256": hashlib.sha256(args.asset_tool.read_bytes()).hexdigest(),
        }
    manifest = {
        "schema_version": 1,
        "generator": "engine_next/Tools/GenerateMaterialBenchmark.py",
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "shared_generator_sha256": hashlib.sha256(Path(benchmarks.__file__).read_bytes()).hexdigest(),
        "geometry_helpers_sha256": hashlib.sha256(Path(geometry.__file__).read_bytes()).hexdigest(),
        "revision": benchmarks.REVISION,
        "seed": SEED,
        "provenance": "Self-authored procedural geometry and PNG texture, licensed under MIT with this project",
        "comparison_status": "GPU comparisons and external-engine measurements are pending",
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
