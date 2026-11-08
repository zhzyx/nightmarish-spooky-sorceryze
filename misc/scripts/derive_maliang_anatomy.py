"""Derive fixed CC0 head data from the pinned MakeHuman OBJ, using Blender.

Run Blender --background --factory-startup --disable-autoexec --python THIS
-- SOURCE.obj OUTPUT.py [YOUNG.target OLD.target]. This authoring utility is
not a runtime model tool. Optional pinned targets add a neutral age difference.
No MakeHuman program code is used. The resulting mesh data remains CC0-1.0.
"""

import hashlib
import json
import sys
from pathlib import Path


def main():
    import bmesh

    args = sys.argv[sys.argv.index("--") + 1 :]
    if len(args) not in (2, 4):
        raise ValueError("Expected pinned OBJ, new output and optional young/old targets")
    source, output = map(Path, args[:2])
    data = source.read_bytes()
    expected = "8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c"
    if hashlib.sha256(data).hexdigest() != expected or output.exists():
        raise ValueError("Pinned source required; output must be new")
    vertices, faces, group = [], [], ""
    for line in data.decode("utf-8").splitlines():
        tokens = line.split()
        if not tokens:
            continue
        if tokens[0] == "v":
            vertices.append(tuple(map(float, tokens[1:4])))
        elif tokens[0] == "g":
            group = tokens[1]
        elif tokens[0] == "f" and group == "body":
            faces.append([int(token.split("/")[0]) - 1 for token in tokens[1:]])
    bm = bmesh.new()
    source_index = bm.verts.layers.int.new("source_index")
    points = [bm.verts.new(vertex) for vertex in vertices]
    for index, point in enumerate(points):
        point[source_index] = index + 1
    for face in faces:
        bm.faces.new([points[index] for index in face])
    bmesh.ops.delete(bm, geom=[vertex for vertex in bm.verts if not vertex.link_faces], context="VERTS")
    bmesh.ops.bisect_plane(
        bm,
        geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
        plane_co=(0, 6.0, 0),
        plane_no=(0, 1, 0),
        dist=1e-7,
        clear_inner=True,
        clear_outer=False,
    )
    # The authoring selection is the head above a documented neck plane.
    # Helpers, clothes, eyeball proxies, rig data and the reference asset are absent.
    if min(vertex.co.y for vertex in bm.verts) < 5.9999:
        raise ValueError("Head clipping orientation invalid")
    boundary = [edge for edge in bm.edges if edge.is_boundary]
    bmesh.ops.holes_fill(bm, edges=boundary, sides=0)
    bmesh.ops.triangulate(bm, faces=list(bm.faces), quad_method="BEAUTY", ngon_method="BEAUTY")
    bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    if not all(edge.is_manifold for edge in bm.edges):
        raise ValueError("Derived head must be closed manifold")
    if bm.calc_volume(signed=True) < 0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    top, chin, center_z = 8.4913, 6.19075, 0.16075
    center_y, height = (top + chin) / 2, top - chin
    normalized = [
        (
            round(vertex.co.x / height, 8),
            round((vertex.co.y - center_y) / height, 8),
            round((vertex.co.z - center_z) / height, 8),
        )
        for vertex in bm.verts
    ]
    triangles = [tuple(vertex.index for vertex in face.verts) for face in bm.faces]
    eyes = tuple(
        (
            round(sign * 0.30775 / height, 8),
            round((7.28415 - center_y) / height, 8),
            round((1.24535 - center_z) / height, 8),
        )
        for sign in (-1, 1)
    )
    header = '''# SPDX-License-Identifier: CC0-1.0
# Mesh data copyright (c) 2020 Data Collection AB, Joel Palmius, Jonas Hauquier.
"""Fixed anatomical control data derived from MakeHuman's CC0 base mesh.

Source commit: a8bc2d54ff0ac92e78ff71431b1023eda42bf482
Source: https://github.com/makehumancommunity/makehuman/blob/a8bc2d54ff0ac92e78ff71431b1023eda42bf482/makehuman/data/3dobjs/base.obj
Reproduce with misc/scripts/derive_maliang_anatomy.py and that pinned OBJ.
Only the body group above original Y=6 is retained, neck/eye openings capped,
and faces triangulated. Coordinates remain Y-up, +Z front; head crown/chin
span one unit around Y=0, with a short neck extension below the chin.
This is fixed asset data, not a neural model or a user reference reconstruction.
"""

SOURCE_SHA256 = "8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c"
'''
    text = header + "\nEYE_CENTERS = " + repr(eyes) + "\n\nHEAD_VERTICES = (\n"
    text += "".join("    " + repr(vertex) + ",\n" for vertex in normalized) + ")\n\nHEAD_FACES = (\n"
    text += "".join("    " + repr(face) + ",\n" for face in triangles) + ")\n"
    age_deltas = []
    if len(args) == 4:
        expected_targets = (
            "70e228ba7164737dae664454394536fc5935fa48d333c1a97d77e2dc6eacc5f5",
            "b0d2b1d58cba0358af59833740e70229265f7da1c20a11240f4123b7192cfd6d",
        )
        targets = []
        for filename, expected_target in zip(args[2:], expected_targets):
            raw = Path(filename).read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected_target:
                raise ValueError("Pinned CC0 age target required")
            delta = {}
            for line in raw.decode("utf-8").splitlines():
                tokens = line.split()
                if not tokens or tokens[0].startswith("#"):
                    continue
                index = int(tokens[0])
                if index in delta or not 0 <= index < len(vertices):
                    raise ValueError("Invalid age target vertex")
                delta[index] = tuple(map(float, tokens[1:4]))
            targets.append(delta)
        for vertex in bm.verts:
            index = vertex[source_index] - 1
            original = vertices[index] if 0 <= index < len(vertices) else None
            # New neck-plane intersection vertices have interpolated custom data;
            # only an exact surviving original point may use its sparse delta.
            matched = original is not None and sum((vertex.co[i] - original[i]) ** 2 for i in range(3)) < 1e-10
            if matched:
                young, old = (target.get(index, (0.0, 0.0, 0.0)) for target in targets)
                age_deltas.append(tuple(round((old[i] - young[i]) / height, 8) for i in range(3)))
            else:
                age_deltas.append((0.0, 0.0, 0.0))
        text += "\n# Difference of same-baseline old/young CC0 targets: age shape only.\n"
        text += "# These source asset names do not describe or infer the user's ethnicity.\n"
        text += "AGE_SOURCE_SHA256 = (\n" + "".join('    "' + value + '",\n' for value in expected_targets) + ")\n"
        text += "\nAGE_DELTAS = (\n" + "".join("    " + repr(delta) + ",\n" for delta in age_deltas) + ")\n"
    output.write_bytes(text.encode("utf-8"))
    print(
        json.dumps(
            dict(
                vertices=len(normalized),
                triangles=len(triangles),
                volume=bm.calc_volume(signed=True),
                bounds=[[min(v[i] for v in normalized), max(v[i] for v in normalized)] for i in range(3)],
                sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                nonzero_age_deltas=sum(any(value != 0 for value in delta) for delta in age_deltas),
            )
        )
    )
    bm.free()


if __name__ == "__main__":
    main()
