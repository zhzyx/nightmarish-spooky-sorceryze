# Copyright (c) 2026 Engine Next contributors. SPDX-License-Identifier: MIT

"""Generate a self-authored skinned and morphed humanoid for M4 scene E."""

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

import GenerateMaterialBenchmark as material_tools
import GenerateReflectionBenchmark as geometry
import GenerateVisualBenchmarks as benchmarks

ASSET_ID = "m4.bench.e.character"
FLOOR_ID = "m4.bench.e.floor"
BONES = [
    ("Pelvis", -1, (0, 1, 0)),
    ("Chest", 0, (0, 0.4, 0)),
    ("Neck", 1, (0, 0.3, 0)),
    ("Head", 2, (0, 0.15, 0)),
    ("ShoulderLeft", 1, (-0.3, 0.12, 0)),
    ("ElbowLeft", 4, (-0.34, 0, 0)),
    ("WristLeft", 5, (-0.3, 0, 0)),
    ("ShoulderRight", 1, (0.3, 0.12, 0)),
    ("ElbowRight", 7, (0.34, 0, 0)),
    ("WristRight", 8, (0.3, 0, 0)),
    ("HipLeft", 0, (-0.15, 0, 0)),
    ("KneeLeft", 10, (0, -0.45, 0)),
    ("AnkleLeft", 11, (0, -0.45, 0)),
    ("HipRight", 0, (0.15, 0, 0)),
    ("KneeRight", 13, (0, -0.45, 0)),
    ("AnkleRight", 14, (0, -0.45, 0)),
]


def normalize(vector):
    length = math.sqrt(sum(value * value for value in vector))
    return [value / length for value in vector]


def accessor(builder, values, components, component_type=5126):
    code = "f" if component_type == 5126 else "H"
    payload = struct.pack(f"<{len(values)}{code}", *values)
    rounded = struct.unpack(f"<{len(values)}{code}", payload)
    record = {
        "bufferView": builder.buffer_view(payload),
        "componentType": component_type,
        "count": len(values) // components,
        "type": {1: "SCALAR", 2: "VEC2", 3: "VEC3", 4: "VEC4", 16: "MAT4"}[components],
        "min": [min(rounded[axis::components]) for axis in range(components)],
        "max": [max(rounded[axis::components]) for axis in range(components)],
    }
    index = len(builder.document["accessors"])
    builder.document["accessors"].append(record)
    return index


def rotation_x_z(x, z):
    sx, cx = math.sin(x / 2), math.cos(x / 2)
    sz, cz = math.sin(z / 2), math.cos(z / 2)
    return [sx * cz, -sx * sz, cx * sz, cx * cz]


def empty_builder():
    builder = benchmarks.GlbBuilder()
    builder.binary.clear()
    builder.document["bufferViews"].clear()
    builder.document["accessors"].clear()
    builder.attributes.clear()
    return builder


def character():
    builder = empty_builder()
    document = builder.document
    document["asset"]["generator"] = "Engine Next self-authored E character r1"
    positions, normals, tangents, texcoords, joints, weights, morphs, morph_normals, indices = ([] for _ in range(9))
    sphere = benchmarks.sphere_geometry(rings=12, segments=24)

    def ellipsoid(center, scale, joint, end_joint=None, axis=1, direction=1, breathing=False):
        first = len(positions) // 3
        for vertex in range(len(sphere[0]) // 3):
            unit = sphere[0][vertex * 3 : vertex * 3 + 3]
            position = [center[index] + unit[index] * scale[index] for index in range(3)]
            normal = normalize([unit[index] / scale[index] for index in range(3)])
            tangent = [sphere[2][vertex * 4 + index] * scale[index] for index in range(3)]
            projection = sum(tangent[index] * normal[index] for index in range(3))
            tangent = normalize([tangent[index] - projection * normal[index] for index in range(3)])
            blend = max(0, min(1, (unit[axis] * direction - 0.6) / 0.4)) if end_joint is not None else 0
            positions.extend(position)
            normals.extend(normal)
            tangents.extend([*tangent, 1])
            texcoords.extend(sphere[3][vertex * 2 : vertex * 2 + 2])
            joints.extend([joint, joint if end_joint is None else end_joint, 0, 0])
            weights.extend([1 - blend, blend, 0, 0])
            morphs.extend([unit[0] * scale[0] * 0.06, 0, unit[2] * scale[2] * 0.06] if breathing else [0, 0, 0])
            target_normal = normalize([unit[0] / (scale[0] * 1.06), unit[1] / scale[1], unit[2] / (scale[2] * 1.06)])
            morph_normals.extend(
                [target_normal[index] - normal[index] for index in range(3)] if breathing else [0, 0, 0]
            )
        indices.extend(first + index for index in sphere[4])

    ellipsoid((0, 1.02, 0), (0.22, 0.18, 0.15), 0)
    ellipsoid((0, 1.36, 0), (0.29, 0.32, 0.16), 1, breathing=True)
    ellipsoid((0, 1.7, 0), (0.08, 0.1, 0.08), 2)
    ellipsoid((0, 1.91, 0), (0.15, 0.2, 0.14), 3)
    for sign, shoulder, elbow, wrist, hip, knee, ankle in ((-1, 4, 5, 6, 10, 11, 12), (1, 7, 8, 9, 13, 14, 15)):
        ellipsoid((sign * 0.47, 1.52, 0), (0.2, 0.085, 0.085), shoulder, elbow, 0, sign)
        ellipsoid((sign * 0.79, 1.52, 0), (0.18, 0.07, 0.07), elbow, wrist, 0, sign)
        ellipsoid((sign * 0.99, 1.52, 0), (0.09, 0.09, 0.05), wrist)
        ellipsoid((sign * 0.15, 0.78, 0), (0.115, 0.27, 0.12), hip, knee, 1, -1)
        ellipsoid((sign * 0.15, 0.32, 0), (0.085, 0.25, 0.095), knee, ankle, 1, -1)
        ellipsoid((sign * 0.15, 0.07, 0.065), (0.09, 0.07, 0.16), ankle)

    document["materials"] = [
        {
            "name": "BlueCharacter",
            "pbrMetallicRoughness": {
                "baseColorFactor": [0.07, 0.28, 0.65, 1],
                "metallicFactor": 0.15,
                "roughnessFactor": 0.5,
            },
        }
    ]
    attributes = {
        name: accessor(builder, values, components, component_type)
        for name, values, components, component_type in (
            ("POSITION", positions, 3, 5126),
            ("NORMAL", normals, 3, 5126),
            ("TANGENT", tangents, 4, 5126),
            ("TEXCOORD_0", texcoords, 2, 5126),
            ("JOINTS_0", joints, 4, 5123),
            ("WEIGHTS_0", weights, 4, 5126),
        )
    }
    document["meshes"] = [
        {
            "name": "Character",
            "weights": [0],
            "primitives": [
                {
                    "attributes": attributes,
                    "indices": accessor(builder, indices, 1, 5123),
                    "material": 0,
                    "mode": 4,
                    "targets": [
                        {"POSITION": accessor(builder, morphs, 3), "NORMAL": accessor(builder, morph_normals, 3)}
                    ],
                }
            ],
        }
    ]
    document["nodes"] = [{"name": "CharacterMesh", "mesh": 0, "skin": 0}]
    world_positions = []
    inverse_binds = []
    for index, (name, parent, translation) in enumerate(BONES):
        world = (
            list(translation)
            if parent < 0
            else [world_positions[parent][axis] + translation[axis] for axis in range(3)]
        )
        world_positions.append(world)
        node = {"name": name, "translation": list(translation)}
        document["nodes"].append(node)
        if parent >= 0:
            document["nodes"][parent + 1].setdefault("children", []).append(index + 1)
        inverse_binds.extend([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -world[0], -world[1], -world[2], 1])
    document["skins"] = [
        {
            "name": "CharacterRig",
            "joints": list(range(1, 17)),
            "skeleton": 1,
            "inverseBindMatrices": accessor(builder, inverse_binds, 16),
        }
    ]
    document["scenes"] = [{"nodes": [0, 1]}]
    times = [index / 4 for index in range(9)]
    time_accessor = accessor(builder, times, 1)
    samplers = []
    channels = []
    for bone, phase, amplitude, rest in (
        (4, 0, 0.4, 1.0),
        (7, math.pi, 0.4, -1.0),
        (10, math.pi, 0.45, 0),
        (13, 0, 0.45, 0),
        (11, 0, 0.6, 0),
        (14, math.pi, 0.6, 0),
    ):
        values = []
        for time in times:
            angle = amplitude * math.sin(math.pi * time + phase)
            if bone in (11, 14):
                angle = max(0, angle)
            values.extend(rotation_x_z(angle, rest))
        samplers.append({"input": time_accessor, "output": accessor(builder, values, 4), "interpolation": "LINEAR"})
        channels.append({"sampler": len(samplers) - 1, "target": {"node": bone + 1, "path": "rotation"}})
    samplers.append({
        "input": time_accessor,
        "output": accessor(builder, [0.5 - 0.5 * math.cos(math.pi * t) for t in times], 1),
        "interpolation": "LINEAR",
    })
    channels.append({"sampler": len(samplers) - 1, "target": {"node": 0, "path": "weights"}})
    document["animations"] = [{"name": "WalkAndBreathe", "samplers": samplers, "channels": channels}]
    return builder.finish(), {
        "joints": len(BONES),
        "vertices": len(positions) // 3,
        "triangles": len(indices) // 3,
        "duration_seconds": 2,
    }


def floor_mesh():
    builder = empty_builder()
    geometry.add_quad(
        builder,
        "Floor",
        [(-5, 0, 3), (5, 0, 3), (5, 0, -4), (-5, 0, -4)],
        [0, 1, 0],
        [1, 0, 0],
        geometry.material("Floor", [0.45, 0.45, 0.45], 0, 0.75),
    )
    return builder.finish()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--asset-tool", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    body, stats = character()
    floor = floor_mesh()
    entities = [
        benchmarks.entity(1, "AnimatedCharacter", ASSET_ID, body, [0, 0, 0], "static"),
        benchmarks.entity(2, "Floor", FLOOR_ID, floor, [0, 0, 0], "static"),
    ]
    scene = benchmarks.write_scene(
        args.output,
        "E",
        {"Character.glb": body, "Floor.glb": floor},
        benchmarks.build_request(
            "m4.bench.e",
            entities,
            [benchmarks.asset(ASSET_ID, "Character.glb"), benchmarks.asset(FLOOR_ID, "Floor.glb")],
        ),
        "Self-authored sixteen-joint character with skin blending and breathing morph",
    )
    scene["camera"] = {
        "position": [0, 1.15, 5.5],
        "target": [0, 1, 0],
        "up": [0, 1, 0],
        "vertical_fov_degrees": 42,
        "near_plane": 0.05,
        "far_plane": 100,
    }
    scene["animation"] = stats
    if args.asset_tool:
        compiled = material_tools.run_asset(
            args.asset_tool,
            [
                "compile",
                "--request",
                str(args.output / scene["request"]),
                "--source-root",
                str(args.output / "E"),
                "--output",
                str(args.output / "E.enpak"),
            ],
        )
        scene["source_package_sha256"] = compiled["package_digest"]
        scene["asset_tool_sha256"] = hashlib.sha256(args.asset_tool.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 1,
        "generator": "engine_next/Tools/GenerateAnimationBenchmark.py",
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "provenance": "Self-authored procedural geometry and animation, MIT",
        "scenes": [scene],
    }
    (args.output / "BenchmarkManifest.json").write_bytes(benchmarks.json_bytes(manifest))
    print(json.dumps({"output": str(args.output), **stats}))


if __name__ == "__main__":
    main()
