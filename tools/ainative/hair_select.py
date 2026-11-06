"""Blender-only, explicit posterior surface sampling of the reviewed AI source.

This produces an authored open rear hair panel, not automatic hair segmentation.
Input GLB triangle IDs and barycentric coordinates remain independently auditable.
"""

import hashlib
import json
import struct
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def main():
    source, destination = (Path(p).resolve() for p in sys.argv[sys.argv.index("--") + 1 :])
    destination.mkdir(parents=True, exist_ok=False)
    raw = source.read_bytes()
    size = struct.unpack_from("<I", raw, 12)[0]
    doc = json.loads(raw[20 : 20 + size])
    binary = raw[28 + size :]

    def accessor(index):
        a = doc["accessors"][index]
        view = doc["bufferViews"][a["bufferView"]]
        count = {"SCALAR": 1, "VEC3": 3}[a["type"]]
        fmt = "<" + {5126: "f", 5125: "I", 5123: "H"}[a["componentType"]] * count
        start = view.get("byteOffset", 0) + a.get("byteOffset", 0)
        stride = view.get("byteStride", struct.calcsize(fmt))
        return [struct.unpack_from(fmt, binary, start + i * stride) for i in range(a["count"])]

    primitive = doc["meshes"][0]["primitives"][0]
    points = [Vector(v) for v in accessor(primitive["attributes"]["POSITION"])]
    indices = [i[0] for i in accessor(primitive["indices"])]
    faces = [indices[i : i + 3] for i in range(0, len(indices), 3)]
    tree = BVHTree.FromPolygons(points, faces, all_triangles=True)
    vertices, samples, triangles = [], [], []
    columns, rows = 25, 33
    for row in range(rows):
        t = row / (rows - 1)
        y = 0.91 - t * 1.10
        width = (0.17 + 0.17 * min(1, t * 5)) * (1 - 0.55 * t)
        for col in range(columns):
            x = (col / (columns - 1) * 2 - 1) * width
            hit, normal, face_id, distance = tree.ray_cast(Vector((x, y, 2)), Vector((0, 0, -1)))
            if hit is None:
                raise ValueError(f"Reviewed posterior selection misses at {row}, {col}")
            a, b, c = (points[i] for i in faces[face_id])
            ab, ac, ah = b - a, c - a, hit - a
            d = ab.dot(ab) * ac.dot(ac) - ab.dot(ac) ** 2
            v = (ac.dot(ac) * ah.dot(ab) - ab.dot(ac) * ah.dot(ac)) / d
            w = (ab.dot(ab) * ah.dot(ac) - ab.dot(ac) * ah.dot(ab)) / d
            vertices.append(list(hit))
            samples.append({"source_triangle": face_id, "barycentric": [1 - v - w, v, w]})
    horizontal_jump = max(
        abs(vertices[r * columns + c][2] - vertices[r * columns + c + 1][2])
        for r in range(rows)
        for c in range(columns - 1)
    )
    vertical_jump = max(
        abs(vertices[r * columns + c][2] - vertices[(r + 1) * columns + c][2])
        for r in range(rows - 1)
        for c in range(columns)
    )
    if max(horizontal_jump, vertical_jump) > 0.06:
        raise ValueError("Posterior selection crosses a depth discontinuity; review its boundary")
    for r in range(rows - 1):
        for c in range(columns - 1):
            a = r * columns + c
            triangles.extend([[a, a + 1, a + columns], [a + 1, a + columns + 1, a + columns]])
    result = {
        "schema_version": 1,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_kind": "AI image-to-mesh; explicit authored posterior selection",
        "selection": "Orthographic +Z first-hit posterior surface; open panel, no cap or interior",
        "coordinates": "original GLB Y-up; Blender display=(x,-z,y)",
        "limitations": "Original generated head rejected. Sampled rear surface only; authored retopology, not AI strands. Lower broken source excluded.",
        "columns": columns,
        "rows": rows,
        "selection_bounds": {"y_top": 0.91, "y_bottom": -0.19, "width_taper": 0.55},
        "continuity": {"limit": 0.06, "horizontal_jump": horizontal_jump, "vertical_jump": vertical_jump},
        "vertices": vertices,
        "triangles": triangles,
        "samples": samples,
        "guides": [[r * columns + c for r in range(rows)] for c in range(columns)],
    }
    (destination / "posterior.json").write_text(json.dumps(result, indent=2), encoding="utf8")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mesh = bpy.data.meshes.new("Authored rear surface")
    mesh.from_pydata([(p[0], -p[2], p[1]) for p in vertices], [], triangles)
    obj = bpy.data.objects.new("Posterior only - no generated face", mesh)
    bpy.context.collection.objects.link(obj)
    material = bpy.data.materials.new("Diagnostic brown")
    material.diffuse_color = (0.19, 0.07, 0.025, 1)
    mesh.materials.append(material)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 12
    scene.render.resolution_x = scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.world = bpy.data.worlds.new("World")
    scene.world.color = (0.25, 0.25, 0.25)
    for offset in [(3, -4, 4), (-3, 2, 3)]:
        light = bpy.data.lights.new("Area", "AREA")
        light.energy, light.size = 600, 5
        ob = bpy.data.objects.new("Area", light)
        scene.collection.objects.link(ob)
        ob.location = offset
        ob.rotation_euler = (-ob.location).to_track_quat("-Z", "Y").to_euler()
    camera = bpy.data.cameras.new("Camera")
    camera.type, camera.ortho_scale = "ORTHO", 2
    ob = bpy.data.objects.new("Camera", camera)
    scene.collection.objects.link(ob)
    scene.camera = ob
    for name, offset in [("back", (0, -3, 0.2)), ("side", (3, 0, 0.2)), ("inside", (0, 3, 0.2)), ("below", (1, 2, -2))]:
        ob.location = Vector(offset)
        ob.rotation_euler = (Vector((0, 0, 0.15)) - ob.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(destination / (name + ".png"))
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
