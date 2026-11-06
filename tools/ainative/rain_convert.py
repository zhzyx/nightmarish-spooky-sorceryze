"""Private Rain v3.3 adapter. Evaluates original face rig into semantic morphs.

Run with Blender --disable-autoexec; never saves or edits the source .blend.
License: Rain Rig (CC) Blender Foundation | studio.blender.org (CC BY 4.0).
This is a reviewed asset-specific mapping, not automatic face rigging.
"""

import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import bpy
from mathutils import Vector

out = Path(sys.argv[-1]).resolve()
out.mkdir(parents=True, exist_ok=True)
rig = bpy.data.objects["RIG-rain"]
source = Path(bpy.data.filepath)
objects = [
    o
    for o in bpy.data.objects
    if o.type == "MESH"
    and o.name.startswith("GEO-rain-")
    and o.name not in ["GEO-rain-body_nomask", "GEO-rain-eyes_viewport", "GEO-rain-eye_cornea", "GEO-rain-eye_dots"]
]
for o in objects:
    for m in o.modifiers:
        if m.type == "SUBSURF":
            m.levels = 1
deps = bpy.context.evaluated_depsgraph_get()


def capture():
    bpy.context.view_layer.update()
    deps.update()
    result = {}
    for o in objects:
        e = o.evaluated_get(deps)
        mesh = e.to_mesh()
        result[o.name] = [o.matrix_world @ v.co for v in mesh.vertices]
        e.to_mesh_clear()
    return result


base = capture()
neutral = {p.name: p.matrix_basis.copy() for p in rig.pose.bones}


def reset():
    for p in rig.pose.bones:
        p.matrix_basis = neutral[p.name]


def move(name, world):
    p = rig.pose.bones[name]
    p.location += p.matrix.to_3x3().inverted() @ Vector(world)


def pose(channel):
    reset()
    if channel == "jawOpen":
        p = rig.pose.bones["MSTR-Jaw"]
        p.rotation_mode = "XYZ"
        p.rotation_euler.x = math.radians(24)
    elif channel in ["mouthSmile", "mouthFrown"]:
        for side in ["L", "R"]:
            move("ACT-Lips_Corner." + side, (0, 0, 0.018 if channel == "mouthSmile" else -0.014))
    elif channel == "browDown":
        for side in ["L", "R"]:
            move("MSTR-Eyebrow." + side, (0, 0, -0.018))
    elif channel == "eyeBlink":
        for side in ["L", "R"]:
            move("ACT-Eyelid_Upper." + side, (0, 0, -0.025))
            move("ACT-Eyelid_Lower." + side, (0, 0, 0.008))
    elif channel.startswith("look"):
        move(
            "TGT-Eyes",
            {"lookLeft": (0.35, 0, 0), "lookRight": (-0.35, 0, 0), "lookUp": (0, 0, 0.3), "lookDown": (0, 0, -0.3)}[
                channel
            ],
        )


channels = [
    "jawOpen",
    "mouthSmile",
    "mouthFrown",
    "browDown",
    "eyeBlink",
    "lookLeft",
    "lookRight",
    "lookUp",
    "lookDown",
]
samples = {}
for channel in channels:
    pose(channel)
    samples[channel] = capture()
    print("BAKED", channel, flush=True)
reset()
bpy.context.view_layer.update()
bone_data = {
    b.name: (b.matrix.copy(), b.length, b.parent.name if b.parent else None)
    for b in rig.pose.bones
    if b.bone.use_deform
}


def parent_for(name):
    p = rig.pose.bones[name].parent
    while p and p.name not in bone_data:
        p = p.parent
    return p.name if p else None


parents = {n: parent_for(n) for n in bone_data}
# Production controls are not deformation ancestors. Reconstruct the reviewed
# anatomical tree explicitly instead of silently exporting independent roots.
parents.update({
    "DEF-Pelvis": None,
    "DEF-Spine1": "DEF-Pelvis",
    "DEF-Spine2": "DEF-Spine1",
    "DEF-Spine3": "DEF-Spine2",
    "DEF-Neck": "DEF-Spine3",
    "DEF-Head": "DEF-Neck",
})
for side in ["L", "R"]:
    for chain, parent in [
        (["Upperarm1", "Upperarm2", "Forearm1", "Forearm2", "Hand"], "DEF-Spine3"),
        (["Thigh1", "Thigh2", "Shin1", "Shin2", "Foot", "Toe"], "DEF-Pelvis"),
    ]:
        for part in chain:
            name = "DEF-" + part + "." + side
            if name in bone_data:
                parents[name] = parent
                parent = name
for name, (matrix, length, _) in bone_data.items():
    if parents[name] is not None or name == "DEF-Pelvis":
        continue
    x, y, z = matrix.translation
    side = "L" if x > 0 else "R"
    if z > 1.31:
        parents[name] = "DEF-Head"
    elif abs(x) > 0.25:
        parents[name] = "DEF-Hand." + side if abs(x) > 0.5 else "DEF-Upperarm1." + side
    elif z < 0.8:
        parents[name] = "DEF-Foot." + side if z < 0.15 else "DEF-Shin1." + side
    else:
        parents[name] = "DEF-Pelvis"
# Capture evaluated geometry and weights before removing the production rig.
derived = []
for o in objects:
    mesh = bpy.data.meshes.new_from_object(o.evaluated_get(deps), preserve_all_data_layers=True, depsgraph=deps)
    mesh.transform(o.matrix_world)
    derived.append((o.name, mesh, [g.name for g in o.vertex_groups]))
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
arm = bpy.data.armatures.new("RainDeform")
target = bpy.data.objects.new("RainDeform", arm)
bpy.context.collection.objects.link(target)
bpy.context.view_layer.objects.active = target
target.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
for name, (matrix, length, _source_parent) in bone_data.items():
    b = arm.edit_bones.new(name)
    b.matrix = matrix
    b.length = max(length, 0.001)
for name, parent in parents.items():
    if parent:
        arm.edit_bones[name].parent = arm.edit_bones[parent]
bpy.ops.object.mode_set(mode="OBJECT")
stats: dict[str, dict[str, Any]] = {}


def smooth(a, b, x):
    t = max(0, min(1, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def custom(v, key):
    w = v.copy()
    x, y, z = v
    if key == "face_width":
        w.x += x * 0.35 * smooth(1.29, 1.41, z)
    elif key == "jaw_width":
        w.x += x * 0.4 * math.exp(-(((z - 1.37) / 0.065) ** 2))
    elif key == "nose_width":
        w.x += x * 0.6 * math.exp(-(((z - 1.445) / 0.033) ** 2)) * math.exp(-((x / 0.04) ** 2)) * smooth(0.10, 0.16, -y)
    else:
        t = max(0, min(1, (z - 0.83) / 0.37))
        fade = smooth(0.58, 0.83, z) * (1 - smooth(1.20, 1.40, z))
        weight = {"hips": max(0, 1 - 2 * t), "waist": 1 - abs(2 * t - 1), "chest": max(0, 2 * t - 1), "depth": 1}[
            key
        ] * fade
        if key == "depth":
            w.y += y * weight
        else:
            w.x += x * weight
    return w


for name, mesh, groups in derived:
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    # Collapse production B-bone/corrective influences into the reviewed body
    # FK joints. Keeping controller-era helper weights would tear the surface
    # when those helpers are no longer evaluated by CloudRig at runtime.
    mapped_weights = []

    def map_group(group, point):
        if not group.startswith("DEF-"):
            return None
        side = "L" if group.endswith(".L") else "R"
        for token, bone in [
            ("Upperarm", "Upperarm1"),
            ("Forearm", "Forearm1"),
            ("Hand", "Hand"),
            ("Finger", "Hand"),
            ("Thumb", "Hand"),
            ("Index", "Hand"),
            ("Middle", "Hand"),
            ("Ring", "Hand"),
            ("Pinky", "Hand"),
            ("Thigh", "Thigh1"),
            ("Shin", "Shin1"),
            ("Foot", "Foot"),
            ("Toe", "Foot"),
        ]:
            if group.startswith("DEF-" + token) or group.startswith("DEF-COR-" + token):
                return "DEF-" + bone + "." + side
        if group in ["DEF-Pelvis", "DEF-Spine1", "DEF-Spine2", "DEF-Spine3", "DEF-Neck", "DEF-Head"]:
            return group
        if "Scarf" in group or "Breast" in group or "Shoulder" in group:
            return "DEF-Spine3"
        return "DEF-Head" if point.z > 1.30 else "DEF-Spine3"

    for vertex in mesh.vertices:
        weights: dict[str, float] = {}
        for item in vertex.groups:
            mapped = map_group(groups[item.group], vertex.co)
            if mapped:
                weights[mapped] = weights.get(mapped, 0) + item.weight
        if not weights:
            weights = {"DEF-Head" if vertex.co.z > 1.30 else "DEF-Pelvis": 1}
        mapped_weights.append(weights)
    # New mesh vertices contain old group indices; clear them using a temporary
    # group table before installing the compact skin weights.
    for n in groups:
        obj.vertex_groups.new(name=n)
    obj.vertex_groups.clear()
    targets = sorted({n for weights in mapped_weights for n in weights})
    for n in targets:
        obj.vertex_groups.new(name=n)
    for i, weights in enumerate(mapped_weights):
        total = sum(weights.values())
        for n, w in weights.items():
            obj.vertex_groups[n].add([i], w / total, "REPLACE")
    mod = obj.modifiers.new("BodySkeleton", "ARMATURE")
    mod.object = target
    obj.parent = target
    obj.shape_key_add(name="Basis")
    stats[name] = {"vertices": len(mesh.vertices), "morph_max_delta": {}}
    for channel in channels + ["face_width", "jaw_width", "nose_width", "chest", "waist", "hips", "depth"]:
        key = obj.shape_key_add(name=channel)
        key.slider_min = -1
        points = samples[channel][name] if channel in channels else [custom(v, channel) for v in base[name]]
        assert len(points) == len(key.data)
        maximum = 0
        for i, v in enumerate(points):
            key.data[i].co = v
            maximum = max(maximum, (v - base[name][i]).length)
        stats[name]["morph_max_delta"][channel] = maximum
    # Bilinear correction transports jaw-open displacement through face DNA;
    # without this, a widened/narrowed jaw keeps the neutral-width mouth motion.
    for parameter in ["face_width", "jaw_width", "nose_width"]:
        key = obj.shape_key_add(name="corrective_" + parameter + "_jawOpen")
        key.slider_min = -1
        for i, v in enumerate(base[name]):
            opened = samples["jawOpen"][name][i]
            key.data[i].co = v + (custom(opened, parameter) - opened) - (custom(v, parameter) - v)
    # Consistent portable flat materials; retain geometric eyes/teeth/mouth.
    color = (0.58, 0.31, 0.20, 1)
    if "hair" in name or "eyebrow" in name or "eyelash" in name:
        color = (0.025, 0.012, 0.008, 1)
    elif "jeans" in name:
        color = (0.045, 0.12, 0.23, 1)
    elif "top" in name or "scarf" in name:
        color = (0.08, 0.32, 0.34, 1)
    elif "shoes" in name:
        color = (0.055, 0.04, 0.03, 1)
    elif "gums" in name or "tongue" in name:
        color = (0.7, 0.3, 0.28, 1)
    elif "eyes" in name:
        color = (0.85, 0.9, 0.87, 1)
    mat = bpy.data.materials.new(name + "-portable")
    mat.diffuse_color = color
    mat.use_nodes = True
    mat.node_tree.nodes.get("Principled BSDF").inputs["Base Color"].default_value = color
    mesh.materials.clear()
    mesh.materials.append(mat)
    for p in mesh.polygons:
        p.material_index = 0
        p.use_smooth = True
    if "eyes" in name:
        iris = bpy.data.materials.new("Iris")
        iris.diffuse_color = (0.035, 0.11, 0.065, 1)
        mesh.materials.append(iris)
        for p in mesh.polygons:
            center = sum((mesh.vertices[i].co for i in p.vertices), Vector()) / len(p.vertices)
            if center.y < -0.113 and abs(abs(center.x) - 0.052) < 0.021 and abs(center.z - 1.474) < 0.024:
                p.material_index = 1
bpy.ops.object.select_all(action="SELECT")
asset = out / "rain-semantic-v1.glb"
bpy.ops.export_scene.gltf(
    filepath=str(asset),
    export_format="GLB",
    export_animations=False,
    export_morph=True,
    export_morph_normal=True,
    export_skins=True,
    export_def_bones=True,
)
binding: dict[str, Any] = {
    "schema_version": 1,
    "mapping_version": "rain33-v1",
    "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    "asset_sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
    "morphs": {k: k for k in channels + ["face_width", "jaw_width", "nose_width", "chest", "waist", "hips", "depth"]},
    "credit": "Rain Rig (CC) Blender Foundation | studio.blender.org",
    "license": "https://creativecommons.org/licenses/by/4.0/",
    "source_url": "https://studio.blender.org/characters/rain/v3/",
    "source_package": "rain-v33.zip; internal rain_v3.2.blend",
    "method": "original CloudRig evaluated facial poses; reduced deform-only skeleton; manual semantic calibration; portable materials",
    "head_neck_owner": "body",
    "stats": stats,
}
binding["body_mapping"] = {
    "hips": "DEF-Pelvis",
    "spine": "DEF-Spine1",
    "chest": "DEF-Spine3",
    "neck": "DEF-Neck",
    "head": "DEF-Head",
}
binding["correctives"] = [
    {"morph": "corrective_" + p + "_jawOpen", "parameter": p, "channel": "jawOpen"}
    for p in ["face_width", "jaw_width", "nose_width"]
]
for side in ["L", "R"]:
    for semantic, bone in [
        ("upper_arm", "Upperarm1"),
        ("forearm", "Forearm1"),
        ("hand", "Hand"),
        ("thigh", "Thigh1"),
        ("shin", "Shin1"),
        ("foot", "Foot"),
    ]:
        binding["body_mapping"][semantic + "_" + side.lower()] = "DEF-" + bone + "." + side
(out / "face-binding.json").write_text(json.dumps(binding, indent=2))
print("EXPORTED", asset, flush=True)
