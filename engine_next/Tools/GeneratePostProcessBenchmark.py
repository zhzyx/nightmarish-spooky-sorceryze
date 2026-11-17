# Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT

"""Generate a self-authored emissive calibration card and isolated Bloom patch.

The GLB uses the supported metallic-roughness and emissive-factor paths. Three
front-facing planes provide a black surround, a large radiance-one card, and a
small radiance-one patch. A black occlusion texture removes environment light.
Compile the emitted BuildRequest, then bind the resulting package digest into
one of the render-configuration templates in the manifest before GPU execution.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

import GenerateVisualBenchmarks as benchmarks

SCENE_ID = "m4.bench.postprocess"
SCENE_NAME = "PostProcess"
CAMERA = {
    "position": [0, 0, 4],
    "target": [0, 0, 0],
    "up": [0, 1, 0],
    "vertical_fov_degrees": 50,
    "near_plane": 0.05,
    "far_plane": 1000,
}
GRAY_CARD_EV100 = math.log2(1 / (0.18 * 1.2))


def material(name, emissive):
    return {
        "name": name,
        "pbrMetallicRoughness": {
            "baseColorFactor": [0, 0, 0, 1],
            "metallicFactor": 1,
            "roughnessFactor": 1,
        },
        "emissiveFactor": [emissive, emissive, emissive],
        "occlusionTexture": {"index": 0, "strength": 1},
    }


def add_plane(builder, name, bounds, z, emissive):
    left, bottom, right, top = bounds
    geometry = [
        ("POSITION", [left, bottom, z, right, bottom, z, right, top, z, left, top, z], 3),
        ("NORMAL", [0, 0, 1] * 4, 3),
        ("TANGENT", [1, 0, 0, 1] * 4, 4),
        ("TEXCOORD_0", [0, 1, 1, 1, 1, 0, 0, 0], 2),
    ]
    attributes = {name: builder.accessor(values, components, 5126) for name, values, components in geometry}
    position = builder.document["accessors"][attributes["POSITION"]]
    position["min"] = [left, bottom, z]
    position["max"] = [right, top, z]
    indices = builder.accessor([0, 1, 2, 0, 2, 3], 1, 5123)
    material_index = len(builder.document["materials"])
    builder.document["materials"].append(material(name, emissive))
    mesh_index = len(builder.document["meshes"])
    builder.document["meshes"].append({
        "name": name,
        "primitives": [{"attributes": attributes, "indices": indices, "material": material_index, "mode": 4}],
    })
    node_index = len(builder.document["nodes"])
    builder.document["nodes"].append({"name": name, "mesh": mesh_index})
    builder.document["scenes"][0]["nodes"].append(node_index)


def calibration_scene():
    builder = benchmarks.GlbBuilder()
    builder.document["asset"]["generator"] = "Engine Next self-authored post-process benchmark r1"
    builder.add_textures({"BlackOcclusion.png": benchmarks.png_rgba(1, 1, bytes([0, 0, 0, 255]))})
    add_plane(builder, "BlackSurround", [-8, -8, 8, 8], -0.01, 0)
    add_plane(builder, "RadianceOneCard", [-0.8, -0.8, 0.8, 0.8], 0, 1)
    add_plane(builder, "RadianceOnePatch", [1.15, -0.1, 1.35, 0.1], 0, 1)
    return builder.finish()


def configuration_templates():
    common = {
        "schema_version": 1,
        "camera": CAMERA,
        "exposure": 1,
        "directional_light": {"direction": [0, 0, -1], "color": [1, 1, 1], "illuminance": 0},
        "point_lights": [],
        "spot_lights": [],
        "shadows": {
            "enabled": False,
            "resolution": 256,
            "distance": 50,
            "split_lambda": 0.6,
            "depth_bias": 0,
            "normal_bias": 0,
        },
        "temporal_aa": {"enabled": False, "history_weight": 0.9, "depth_threshold": 0.01},
        "bloom": {"enabled": False},
    }
    return {
        "ManualGray18": {**common, "exposure_settings": {"mode": "manual", "manual_ev100": GRAY_CARD_EV100}},
        "ManualEv10": {**common, "exposure_settings": {"mode": "manual", "manual_ev100": 10}},
        "BloomOff": {**common, "exposure": 4},
        "BloomOn": {
            **common,
            "exposure": 4,
            "bloom": {"enabled": True, "intensity": 0.1, "threshold": 1, "soft_knee": 0.5, "mip_count": 6},
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, required=True, help="Output directory for the post-process source fixture"
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    payload = calibration_scene()
    scene = benchmarks.write_scene(
        args.output,
        SCENE_NAME,
        {"Calibration.glb": payload},
        benchmarks.build_request(
            SCENE_ID,
            [benchmarks.entity(1, "Calibration", SCENE_ID, payload, [0, 0, 0], "static")],
            [benchmarks.asset(SCENE_ID, "Calibration.glb")],
        ),
        "Radiance-one emissive calibration card and isolated patch over a black surround",
    )
    scene["camera"] = CAMERA
    scene["geometry"] = [
        {"name": "BlackSurround", "xy_bounds": [-8, -8, 8, 8], "z": -0.01, "radiance": 0},
        {"name": "RadianceOneCard", "xy_bounds": [-0.8, -0.8, 0.8, 0.8], "z": 0, "radiance": 1},
        {"name": "RadianceOnePatch", "xy_bounds": [1.15, -0.1, 1.35, 0.1], "z": 0, "radiance": 1},
    ]
    scene["configuration_templates"] = configuration_templates()
    scene["configuration_binding"] = "Insert source_package_sha256 from the compiled source package into a template."
    scene["calibration"] = {
        "surface_radiance_rgb": [1, 1, 1],
        "manual_gray_ev100": GRAY_CARD_EV100,
        "manual_gray_expected_exposed_linear": 0.18,
        "manual_gray_expected_tonemapped_linear": 1 - math.exp(-0.18),
        "manual_gray_expected_output": (1 - math.exp(-0.18)) ** (1 / 2.2),
        "manual_ev10_expected_exposed_linear": 1 / (1.2 * 1024),
        "bloom_legacy_multiplier": 4,
        "bloom_expected_patch_exposed_linear": 4,
        "verification": "Measure an interior card ROI before tone mapping; allow RGBA16F rounding. Compare Bloom On/Off in the black patch surround.",
        "metering_scope": "The full histogram includes the black surround and card; it is not a uniform radiance-one image.",
    }
    manifest = {
        "schema_version": 1,
        "generator": "engine_next/Tools/GeneratePostProcessBenchmark.py",
        "revision": benchmarks.REVISION,
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "shared_generator_sha256": hashlib.sha256(Path(benchmarks.__file__).read_bytes()).hexdigest(),
        "provenance": "Self-authored procedural planes and black occlusion PNG emitted as executor artifacts",
        "comparison_status": "GPU calibration and Bloom measurements remain to be collected",
        "scenes": [scene],
    }
    (args.output / "BenchmarkManifest.json").write_bytes(benchmarks.json_bytes(manifest))
    print(json.dumps({"output": str(args.output), "scenes": [scene["request"]]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
