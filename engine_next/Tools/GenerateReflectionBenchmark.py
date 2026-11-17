# Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT

"""Generate self-authored screen-space reflection geometry using supported glTF.

The static fixture contains a low-roughness metal floor, three emissive colored
upright targets, a roughness strip, a thin occluder, and edge/near reflector
panels. It uses the shared deterministic GLB and M3 BuildRequest generators.
"""

import argparse
import copy
import hashlib
import json
from pathlib import Path

import GenerateVisualBenchmarks as benchmarks

SCENE_ID = "m4.bench.reflections"
CAMERA = {
    "position": [0, 2, 5],
    "target": [0, 0, 0],
    "up": [0, 1, 0],
    "vertical_fov_degrees": 50,
    "near_plane": 0.05,
    "far_plane": 1000,
}


def material(name, color, metallic=0, roughness=0.5, emissive=None):
    result = {
        "name": name,
        "pbrMetallicRoughness": {
            "baseColorFactor": [*color, 1],
            "metallicFactor": metallic,
            "roughnessFactor": roughness,
        },
    }
    if emissive is not None:
        result["emissiveFactor"] = emissive
    return result


def add_quad(builder, name, corners, normal, tangent, surface):
    attributes = {}
    channels = [
        ("POSITION", [component for corner in corners for component in corner], 3),
        ("NORMAL", normal * 4, 3),
        ("TANGENT", [*tangent, 1] * 4, 4),
        ("TEXCOORD_0", [0, 0, 1, 0, 1, 1, 0, 1], 2),
    ]
    for channel, values, components in channels:
        attributes[channel] = builder.accessor(values, components, 5126)
    position = builder.document["accessors"][attributes["POSITION"]]
    position["min"] = [min(corner[axis] for corner in corners) for axis in range(3)]
    position["max"] = [max(corner[axis] for corner in corners) for axis in range(3)]
    indices = builder.accessor([0, 1, 2, 0, 2, 3], 1, 5123)
    material_index = len(builder.document["materials"])
    builder.document["materials"].append(surface)
    mesh_index = len(builder.document["meshes"])
    builder.document["meshes"].append({
        "name": name,
        "primitives": [{"attributes": attributes, "indices": indices, "material": material_index, "mode": 4}],
    })
    node_index = len(builder.document["nodes"])
    builder.document["nodes"].append({"name": name, "mesh": mesh_index})
    builder.document["scenes"][0]["nodes"].append(node_index)


def floor_quad(builder, name, bounds, height, surface):
    left, near, right, far = bounds
    # Winding faces +Y. The first edge extends toward positive Z.
    add_quad(
        builder,
        name,
        [[left, height, far], [left, height, near], [right, height, near], [right, height, far]],
        [0, 1, 0],
        [1, 0, 0],
        surface,
    )


def upright_quad(builder, name, bounds, z, surface):
    left, bottom, right, top = bounds
    add_quad(
        builder,
        name,
        [[left, bottom, z], [right, bottom, z], [right, top, z], [left, top, z]],
        [0, 0, 1],
        [1, 0, 0],
        surface,
    )


def reflection_scene():
    builder = benchmarks.GlbBuilder()
    builder.document["asset"]["generator"] = "Engine Next self-authored SSR benchmark r1"
    floor_quad(builder, "MirrorFloor", [-4, 3.5, 4, -3], 0, material("MirrorMetal", [0.75] * 3, 1, 0.04))
    colors = {"Red": [1, 0.03, 0.02], "Green": [0.02, 1, 0.04], "Blue": [0.03, 0.08, 1]}
    for center, (name, color) in zip([-1.4, 0, 1.4], colors.items()):
        upright_quad(
            builder,
            name + "Target",
            [center - 0.4, 0.2, center + 0.4, 2.2],
            0,
            material(name, color, 0, 0.65, color),
        )
    roughness = [0.04, 0.2, 0.45, 0.75]
    for index, value in enumerate(roughness):
        left = -3 + index * 1.5
        floor_quad(
            builder,
            f"Roughness{index}",
            [left, 3.4, left + 1.5, 2.1],
            0.01,
            material(f"RoughMetal{index}", [0.75] * 3, 1, value),
        )
    upright_quad(builder, "ThinOccluder", [0.65, 0, 0.71, 1.6], 0.9, material("Occluder", [0.025] * 3))
    floor_quad(builder, "NearReflector", [-0.55, 3.2, 0.55, 2.95], 0.015, material("NearMetal", [0.9] * 3, 1, 0.04))
    floor_quad(builder, "LeftEdgeReflector", [-4, 2.2, -3.4, -0.5], 0.02, material("EdgeMetal", [0.9] * 3, 1, 0.04))
    return builder.finish()


def configurations():
    common = {
        "schema_version": 1,
        "camera": CAMERA,
        "exposure": 1,
        "directional_light": {"direction": [0.4, -0.8, -0.5], "color": [1, 1, 1], "illuminance": 2},
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
        "reflections": {
            "enabled": False,
            "max_distance": 30,
            "thickness": 0.1,
            "normal_bias": 0.02,
            "max_steps": 256,
            "max_roughness": 0.8,
        },
    }
    enabled = copy.deepcopy(common)
    enabled["reflections"]["enabled"] = True
    temporal = copy.deepcopy(enabled)
    temporal["temporal_aa"]["enabled"] = True
    return {"Off": common, "On": enabled, "OnTemporal": temporal}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    payload = reflection_scene()
    scene = benchmarks.write_scene(
        args.output,
        "Reflections",
        {"ReflectionScene.glb": payload},
        benchmarks.build_request(
            SCENE_ID,
            [benchmarks.entity(1, "ReflectionScene", SCENE_ID, payload, [0, 0, 0], "static")],
            [benchmarks.asset(SCENE_ID, "ReflectionScene.glb")],
        ),
        "Metal floor with RGB reflection targets, roughness strip, thin occluder and edge/near panels",
    )
    scene["camera"] = CAMERA
    scene["configuration_templates"] = configurations()
    scene["configuration_binding"] = "Insert source_package_sha256 from the compiled M3 source package."
    scene["roughness_strip"] = {
        "values": [0.04, 0.2, 0.45, 0.75],
        "x_bounds": [-3, -1.5, 0, 1.5, 3],
        "z_bounds": [2.1, 3.4],
    }
    scene["geometry_notes"] = {
        "mirror_floor": {"x": [-4, 4], "z": [-3, 3.5], "y": 0, "roughness": 0.04, "metallic": 1},
        "rgb_target_centers": [-1.4, 0, 1.4],
        "rgb_target_bounds_y": [0.2, 2.2],
        "thin_occluder_width": 0.06,
        "near_reflector_z": [2.95, 3.2],
        "analytical_reflection": "A target at world y=1,z=0 reflects through y=0 near z=5/3 from camera y=2,z=5. This lies within the primary metal floor and outside the roughness-strip overlay.",
    }
    manifest = {
        "schema_version": 1,
        "generator": "engine_next/Tools/GenerateReflectionBenchmark.py",
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "shared_generator_sha256": hashlib.sha256(Path(benchmarks.__file__).read_bytes()).hexdigest(),
        "revision": benchmarks.REVISION,
        "provenance": "Self-authored procedural geometry using supported metallic-roughness and emissive glTF factors",
        "comparison_status": "GPU hit coverage and image comparison remain to be measured",
        "scenes": [scene],
    }
    (args.output / "BenchmarkManifest.json").write_bytes(benchmarks.json_bytes(manifest))
    print(json.dumps({"output": str(args.output), "scenes": [scene["request"]]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
