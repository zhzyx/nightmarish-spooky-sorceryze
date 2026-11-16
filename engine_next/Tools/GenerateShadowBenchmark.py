# Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT

"""Generate self-authored source assets for the M4 A directional shadow subscene.

The scene contains a receiver plane and opaque, mirrored, and alpha-masked
spheres. Geometry and texture generation use the existing visual benchmark
helpers. Package compilation and GPU execution are separate operations.
"""

import argparse
import hashlib
import json
from pathlib import Path

import GenerateVisualBenchmarks as benchmarks


def material(name, color):
    return {
        "name": name,
        "pbrMetallicRoughness": {"baseColorFactor": color, "metallicFactor": 0, "roughnessFactor": 0.75},
    }


def add_receiver(builder):
    attributes = {}
    geometry = [
        ("POSITION", [-8, -1.2, -8, -8, -1.2, 8, 8, -1.2, 8, 8, -1.2, -8], 3),
        ("NORMAL", [0, 1, 0] * 4, 3),
        ("TANGENT", [1, 0, 0, 1] * 4, 4),
        ("TEXCOORD_0", [0, 0, 0, 1, 1, 1, 1, 0], 2),
    ]
    for name, values, components in geometry:
        attributes[name] = builder.accessor(values, components, 5126)
    position = builder.document["accessors"][attributes["POSITION"]]
    position["min"] = [-8, -1.2, -8]
    position["max"] = [8, -1.2, 8]
    # Counterclockwise triangles face +Y in the right-handed world.
    indices = builder.accessor([0, 1, 2, 0, 2, 3], 1, 5123)
    material_index = len(builder.document["materials"])
    builder.document["materials"].append(material("Receiver", [0.68, 0.68, 0.68, 1]))
    mesh_index = len(builder.document["meshes"])
    builder.document["meshes"].append({
        "name": "ReceiverPlane",
        "primitives": [{"attributes": attributes, "indices": indices, "material": material_index, "mode": 4}],
    })
    node_index = len(builder.document["nodes"])
    builder.document["nodes"].append({"name": "ReceiverPlane", "mesh": mesh_index})
    builder.document["scenes"][0]["nodes"].append(node_index)


def shadow_scene():
    builder = benchmarks.GlbBuilder()
    builder.document["asset"]["generator"] = "Engine Next self-authored directional shadow benchmark r1"
    builder.add_textures({"Mask.png": benchmarks.textures()["BaseColor.png"]})
    add_receiver(builder)
    builder.add_sphere("OpaqueOccluder", material("OpaqueRed", [0.72, 0.18, 0.10, 1]), [0, 0, 0], [1, 1, 1])
    builder.add_sphere(
        "MirroredOccluder", material("MirroredBlue", [0.08, 0.23, 0.65, 1]), [2, 0, -1], [-0.7, 0.7, 0.7]
    )
    masked = material("MaskedGold", [0.9, 0.65, 0.15, 1])
    masked["pbrMetallicRoughness"]["baseColorTexture"] = {"index": 0}
    masked.update({"alphaMode": "MASK", "alphaCutoff": 0.5, "doubleSided": True})
    builder.add_sphere("MaskedOccluder", masked, [-2, 0.15, -1], [0.8, 0.8, 0.8])
    return builder.finish()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Output directory for the A-Shadow source fixture")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    payload = shadow_scene()
    scene = benchmarks.write_scene(
        args.output,
        "A-Shadow",
        {"ShadowReceiver.glb": payload},
        benchmarks.build_request(
            "m4.bench.a.shadow",
            [benchmarks.entity(1, "ShadowReceiver", "m4.bench.a.shadow", payload, [0, 0, 0], "static")],
            [benchmarks.asset("m4.bench.a.shadow", "ShadowReceiver.glb")],
        ),
        "Receiver plane with opaque, mirrored, and alpha-masked spheres",
    )
    scene["camera"] = {
        "position": [6, 4, 8],
        "target": [0, -0.2, 0],
        "up": [0, 1, 0],
        "vertical_fov_degrees": 50,
        "near_plane": 0.05,
        "far_plane": 1000,
    }
    scene["directional_light"] = {"direction": [0.5, -0.8, -0.6], "color": [1, 0.9666667, 0.9], "illuminance": 3}
    scene["shadows"] = {
        "enabled": True,
        "resolution": 2048,
        "distance": 50,
        "split_lambda": 0.6,
        "depth_bias": 0.0005,
        "normal_bias": 0.01,
    }
    scene["exposure"] = 1
    scene["configuration_binding"] = (
        "Use schema_version 1 and bind source_package_sha256 to the compiled package digest."
    )
    manifest = {
        "schema_version": 1,
        "generator": "engine_next/Tools/GenerateShadowBenchmark.py",
        "revision": benchmarks.REVISION,
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "shared_generator_sha256": hashlib.sha256(Path(benchmarks.__file__).read_bytes()).hexdigest(),
        "provenance": "Self-authored procedural geometry and texture emitted as executor artifacts",
        "scope": "M4 A directional shadow subscene",
        "scenes": [scene],
    }
    (args.output / "BenchmarkManifest.json").write_bytes(benchmarks.json_bytes(manifest))
    print(json.dumps({"output": str(args.output), "scenes": [scene["request"]]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
