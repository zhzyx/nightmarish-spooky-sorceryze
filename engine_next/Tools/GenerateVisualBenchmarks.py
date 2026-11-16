"""Generate self-authored, reproducible M3 packages for M4 visual scenes B and F.

All geometry and RGBA textures are created here using the Python standard library.
The BuildRequests describe executor artifacts and embed no external asset URLs.
"""

import argparse
import hashlib
import json
import math
import struct
import zlib
from pathlib import Path

REVISION = "r1"
TEXTURE_SIZE = 64
CAMERA = {"position": [0, 0, 5], "look_direction": [0, 0, -1], "vertical_fov_degrees": 50}


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def png_rgba(width, height, pixels):
    """Use stored DEFLATE blocks so compression-library updates cannot alter output."""
    if len(pixels) != width * height * 4:
        raise ValueError("RGBA byte count does not match image dimensions")
    stride = width * 4
    raw = b"".join(b"\0" + pixels[row * stride : (row + 1) * stride] for row in range(height))
    compressed = bytearray(b"\x78\x01")
    for offset in range(0, len(raw), 65535):
        block = raw[offset : offset + 65535]
        compressed.extend(struct.pack("<BHH", int(offset + len(block) == len(raw)), len(block), 65535 - len(block)))
        compressed.extend(block)
    compressed.extend(struct.pack(">I", zlib.adler32(raw)))

    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")


def textures():
    base = bytearray()
    normal = bytearray()
    orm = bytearray()
    emissive = bytearray()
    for row in range(TEXTURE_SIZE):
        for column in range(TEXTURE_SIZE):
            checker = (row // 8 + column // 8) % 2
            intensity = 255 if checker else 218
            base.extend((intensity, intensity, intensity, 255 if checker else 0))
            x = 0.18 * math.sin(2 * math.pi * column / 16)
            y = 0.18 * math.cos(2 * math.pi * row / 16)
            length = math.sqrt(x * x + y * y + 1)
            normal.extend(round(255 * (value / length * 0.5 + 0.5)) for value in (x, y, 1))
            normal.append(255)
            orm.extend((255 if checker else 205, 255, 255, 255))
            glow = column % 16 < 3 or row % 16 < 3
            emissive.extend((255 if glow else 0, 130 if glow else 0, 20 if glow else 0, 255))
    return {
        "BaseColor.png": png_rgba(TEXTURE_SIZE, TEXTURE_SIZE, base),
        "Normal.png": png_rgba(TEXTURE_SIZE, TEXTURE_SIZE, normal),
        "Orm.png": png_rgba(TEXTURE_SIZE, TEXTURE_SIZE, orm),
        "Emissive.png": png_rgba(TEXTURE_SIZE, TEXTURE_SIZE, emissive),
    }


def sphere_geometry(rings=24, segments=48):
    positions = []
    normals = []
    tangents = []
    texcoords = []
    indices = []
    for row in range(rings + 1):
        latitude = math.pi * row / rings
        for column in range(segments + 1):
            longitude = 2 * math.pi * column / segments
            position = (
                math.sin(latitude) * math.cos(longitude),
                math.cos(latitude),
                math.sin(latitude) * math.sin(longitude),
            )
            positions.extend(position)
            normals.extend(position)
            tangents.extend((-math.sin(longitude), 0, math.cos(longitude), 1))
            texcoords.extend((column / segments, row / rings))
    for row in range(rings):
        for column in range(segments):
            upper = row * (segments + 1) + column
            lower = upper + segments + 1
            if row > 0:
                indices.extend((upper, upper + 1, lower))
            if row < rings - 1:
                indices.extend((upper + 1, lower + 1, lower))
    return positions, normals, tangents, texcoords, indices


class GlbBuilder:
    def __init__(self):
        self.binary = bytearray()
        self.document = {
            "asset": {"version": "2.0", "generator": "EngineNext GenerateVisualBenchmarks r1"},
            "buffers": [{"byteLength": 0}],
            "bufferViews": [],
            "accessors": [],
            "meshes": [],
            "materials": [],
            "nodes": [],
            "scene": 0,
            "scenes": [{"nodes": []}],
        }
        geometry = sphere_geometry()
        self.attributes = {}
        for name, values, components in zip(
            ("POSITION", "NORMAL", "TANGENT", "TEXCOORD_0"), geometry[:4], (3, 3, 4, 2)
        ):
            self.attributes[name] = self.accessor(values, components, 5126)
        self.indices = self.accessor(geometry[4], 1, 5123)

    def buffer_view(self, payload):
        self.binary.extend(b"\0" * (-len(self.binary) % 4))
        index = len(self.document["bufferViews"])
        self.document["bufferViews"].append({"buffer": 0, "byteOffset": len(self.binary), "byteLength": len(payload)})
        self.binary.extend(payload)
        return index

    def accessor(self, values, components, component_type):
        format_code = "f" if component_type == 5126 else "H"
        view = self.buffer_view(struct.pack(f"<{len(values)}{format_code}", *values))
        accessor = {
            "bufferView": view,
            "componentType": component_type,
            "count": len(values) // components,
            "type": {1: "SCALAR", 2: "VEC2", 3: "VEC3", 4: "VEC4"}[components],
        }
        if components == 3 and "POSITION" not in self.attributes:
            accessor["min"] = [min(values[axis::components]) for axis in range(components)]
            accessor["max"] = [max(values[axis::components]) for axis in range(components)]
        index = len(self.document["accessors"])
        self.document["accessors"].append(accessor)
        return index

    def add_textures(self, images):
        self.document["images"] = []
        self.document["textures"] = []
        self.document["samplers"] = [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}]
        for name, payload in images.items():
            index = len(self.document["images"])
            self.document["images"].append({
                "bufferView": self.buffer_view(payload),
                "mimeType": "image/png",
                "name": name,
            })
            self.document["textures"].append({"source": index, "sampler": 0})

    def add_sphere(self, name, material, translation, scale):
        material_index = len(self.document["materials"])
        self.document["materials"].append(material)
        mesh_index = len(self.document["meshes"])
        self.document["meshes"].append({
            "name": name,
            "primitives": [
                {"attributes": self.attributes, "indices": self.indices, "material": material_index, "mode": 4}
            ],
        })
        node_index = len(self.document["nodes"])
        self.document["nodes"].append({"name": name, "mesh": mesh_index, "translation": translation, "scale": scale})
        self.document["scenes"][0]["nodes"].append(node_index)

    def finish(self):
        self.document["buffers"][0]["byteLength"] = len(self.binary)
        document = json.dumps(self.document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        document += b" " * (-len(document) % 4)
        binary = bytes(self.binary) + b"\0" * (-len(self.binary) % 4)
        length = 12 + 8 + len(document) + 8 + len(binary)
        return (
            struct.pack("<III", 0x46546C67, 2, length)
            + struct.pack("<II", len(document), 0x4E4F534A)
            + document
            + struct.pack("<II", len(binary), 0x004E4942)
            + binary
        )


def material_scene(images):
    builder = GlbBuilder()
    builder.add_textures(images)
    cases = []
    for row, metallic in enumerate((0, 0.5, 1)):
        for column, roughness in enumerate((0.15, 0.4, 0.7, 1)):
            index = row * 4 + column
            name = f"Sphere_M{metallic:g}_R{roughness:g}"
            material = {
                "name": name,
                "pbrMetallicRoughness": {
                    "baseColorFactor": [0.83, 0.55, 0.24, 1],
                    "baseColorTexture": {"index": 0},
                    "metallicFactor": metallic,
                    "roughnessFactor": roughness,
                    "metallicRoughnessTexture": {"index": 2},
                },
                "normalTexture": {"index": 1, "scale": 0.7},
                "occlusionTexture": {"index": 2, "strength": 0.6},
            }
            scale = [0.45, 0.45, 0.45]
            if index == 8:
                material["emissiveTexture"] = {"index": 3}
                material["emissiveFactor"] = [0.7, 0.3, 0.05]
            if index == 9:
                material.update({"alphaMode": "MASK", "alphaCutoff": 0.5, "doubleSided": True})
            if index == 10:
                scale[0] *= -1
            if index == 11:
                scale = [0.45 * 0.8, 0.45 * 1.1, 0.45 * 0.65]
            position = [-1.8 + column * 1.2, 1.2 - row * 1.2, 0]
            builder.add_sphere(name, material, position, scale)
            cases.append({
                "node": index,
                "name": name,
                "metallic_factor": metallic,
                "roughness_factor": roughness,
                "translation": position,
                "scale": scale,
                "emissive": index == 8,
                "alpha_mask": index == 9,
            })
    return builder.finish(), cases


def player_mesh(color, name):
    builder = GlbBuilder()
    body = {
        "name": name,
        "pbrMetallicRoughness": {"baseColorFactor": color, "metallicFactor": 0.1, "roughnessFactor": 0.45},
    }
    face = {
        "name": "Face",
        "pbrMetallicRoughness": {"baseColorFactor": [0.95, 0.83, 0.65, 1], "metallicFactor": 0, "roughnessFactor": 0.6},
    }
    builder.add_sphere("Body", body, [0, 0, 0], [0.35, 0.55, 0.28])
    builder.add_sphere("Head", face, [0, 0.7, 0], [0.24, 0.24, 0.24])
    builder.add_sphere("FacingMarker", body, [0, 0.7, 0.24], [0.08, 0.08, 0.12])
    return builder.finish()


def asset(asset_id, filename):
    return {
        "asset_id": asset_id,
        "revision": REVISION,
        "type": "mesh",
        "media_type": "model/gltf-binary",
        "dependencies": [],
        "source": {"kind": "executor_artifact", "artifact_id": asset_id, "artifact_revision": REVISION},
        "path": filename,
    }


def entity(entity_id, name, asset_id, payload, position, gameplay):
    return {
        "entity_id": entity_id,
        "name": name,
        "node_type": "MeshInstance3D",
        "parent_entity_id": 0,
        "transform": {"translation": position, "rotation_xyzw": [0, 0, 0, 1], "scale": [1, 1, 1]},
        "gameplay": {"kind": gameplay},
        "assets": [
            {
                "role": "mesh",
                "asset_id": asset_id,
                "revision": REVISION,
                "content_sha256": hashlib.sha256(payload).hexdigest(),
            }
        ],
    }


def build_request(scene_id, entities, assets):
    return {
        "schema_version": 1,
        "scene": {
            "schema_version": 1,
            "scene_id": scene_id,
            "scene_revision": REVISION,
            "simulation": {"fixed_step_ms": 16, "max_speed": 8},
            "entities": entities,
        },
        "assets": assets,
    }


def write_scene(root, name, files, request, description):
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    files["BuildRequest.json"] = json_bytes(request)
    files["SceneDocument.json"] = json_bytes(request["scene"])
    for filename, payload in files.items():
        (directory / filename).write_bytes(payload)
    return {
        "name": name,
        "description": description,
        "camera": CAMERA,
        "request": f"{name}/BuildRequest.json",
        "scene_document": f"{name}/SceneDocument.json",
        "files": [
            {"path": f"{name}/{filename}", "byte_size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
            for filename, payload in sorted(files.items())
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Output directory for B and F source fixtures")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    images = textures()
    material_glb, cases = material_scene(images)
    scene_b = write_scene(
        args.output,
        "B",
        {"Materials.glb": material_glb, **images},
        build_request(
            "m4.bench.b",
            [entity(1, "MaterialMatrix", "m4.bench.b", material_glb, [0, 0, 0], "static")],
            [asset("m4.bench.b", "Materials.glb")],
        ),
        "Twelve material spheres, three metallic rows and four roughness columns",
    )
    scene_b["material_cases"] = cases
    players = [player_mesh([0.05, 0.32, 0.9, 1], "PlayerBlue"), player_mesh([0.95, 0.22, 0.04, 1], "PlayerOrange")]
    scene_f = write_scene(
        args.output,
        "F",
        {"PlayerBlue.glb": players[0], "PlayerOrange.glb": players[1]},
        build_request(
            "m4.bench.f",
            [
                entity(1, "PlayerBlue", "m4.bench.f.blue", players[0], [-1, 0, 0], "player_spawn"),
                entity(2, "PlayerOrange", "m4.bench.f.orange", players[1], [1, 0, 0], "player_spawn"),
            ],
            [asset("m4.bench.f.blue", "PlayerBlue.glb"), asset("m4.bench.f.orange", "PlayerOrange.glb")],
        ),
        "Two player_spawn mesh entities with distinct self-authored avatar colors",
    )
    manifest = {
        "schema_version": 1,
        "generator": "engine_next/Tools/GenerateVisualBenchmarks.py",
        "revision": REVISION,
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "provenance": "Self-authored procedural geometry and textures emitted by this generator as executor artifacts",
        "comparison_status": "Unmeasured; no UE comparison or visual acceptance is asserted",
        "scenes": [scene_b, scene_f],
    }
    (args.output / "BenchmarkManifest.json").write_bytes(json_bytes(manifest))
    print(json.dumps({"output": str(args.output), "scenes": [scene["request"] for scene in manifest["scenes"]]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
