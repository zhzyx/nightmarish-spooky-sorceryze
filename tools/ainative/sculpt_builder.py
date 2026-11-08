"""Fixed Blender interpreter for bounded JSON-v2 sculpt plans; never executes model code.

Validation and schema functions use only Python's standard library. Blender is
imported only by build(), so the same validation runs before any model job starts.
The resulting sculpt is a connected manifold surface, not animation retopology.
"""

import hashlib
import json
import math
import sys
from pathlib import Path

# Blender --python does not add its fixed script directory to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from anatomy_base import AGE_DELTAS, AGE_SOURCE_SHA256, HEAD_FACES, HEAD_VERTICES  # noqa: E402
from anatomy_base import SOURCE_SHA256 as ANATOMY_BASE_SHA256  # noqa: E402
from character_detail import (
    PATCH_POCKET_SCOPE,
    cross_collar_accessories,
    detail_schema,
    enclose_tunic_over_trousers,
    eyebrow_accessories,
    fabric_outward_offset,
    face_detail_offset,
    hair_detail_mask,
    hair_detail_offset,
    period_fabric_offset,
    period_surface_fold_offset,
    resolve_detail,
    trouser_waist,
)
from character_detail import accessories as character_accessories  # noqa: E402
from organic_detail import (  # noqa: E402
    end_caps_schema,
    expand_patterns,
    patterns_schema,
    transported_frames,
    validate_caps,
    validate_patterns,
)
from period_groom import (  # noqa: E402
    build_period_groom,
    measure_groom_spec,
    period_groom_schema,
    resolve_period_groom,
)

KINDS = ("box", "ellipsoid", "capsule", "cylinder", "loft", "cage")
MAX_PLAN_BYTES = 2 * 1024 * 1024
MAX_GLB_BYTES = 64 * 1024 * 1024
MAX_TRIANGLES = 2000000
MAX_VERTICES = 1000000
MAX_VOXELS = 64000000
RADIAL = 32
LOFT_STEPS = 8
CHARACTER_AGE_WEIGHTS = {"adult": 0.0, "mature": 0.35, "elder": 0.65}


def resolve_arm_angle(character):
    value = character.get("arm_angle_degrees")
    require(value is None or _number(value, 20, 75), "character_arm_angle_invalid")
    return 65.0 if value is None else float(value)


def resolve_age_blend(character):
    value = character.get("age_blend")
    if value is None:
        return CHARACTER_AGE_WEIGHTS[character["age"]]
    require(_number(value, 0, 1), "character_age_blend_invalid")
    return float(value)


CHARACTER_LIMITS = {
    "height": (0.8, 2.4),
    "head_ratio": (5, 8.5),
    "build": (-1, 1),
    "shoulder_width": (0.75, 1.25),
    "hip_width": (0.75, 1.25),
    "neck_length": (0.75, 1.25),
    "limb_length": (0.85, 1.15),
    "hand_scale": (0.8, 1.2),
    "head_width": (0.85, 1.15),
    "head_depth": (0.85, 1.15),
    "hem_height": (0.35, 0.65),
    "sleeve_length": (0.35, 1.0),
    "trouser_width": (0.8, 1.6),
    "belt_height": (0.48, 0.7),
    "lapel_width": (0.6, 1.5),
}
FACE_LIMITS = {
    "jaw_width": (0.8, 1.2),
    "chin_length": (0.8, 1.2),
    "cheek_fullness": (0.7, 1.3),
    "nose_length": (0.7, 1.3),
    "nose_width": (0.7, 1.3),
    "eye_size": (0.8, 1.6),
    "eye_spacing": (0.8, 1.2),
    "mouth_width": (0.8, 1.2),
    "lip_fullness": (0.7, 1.3),
    "ear_size": (0.7, 1.3),
}


def character_defaults(style="realistic"):
    result = {key: 1.0 for key in CHARACTER_LIMITS}
    result.update(
        style=style,
        age="adult",
        height=1.8,
        head_ratio=7.5 if style == "realistic" else 6.0,
        build=0.0,
        pose="A",
        face={key: 1.0 for key in FACE_LIMITS},
        hair="short",
        clothing="tshirt_trousers",
        footwear="shoes",
        hem_height=0.52,
        sleeve_length=0.35,
        trouser_width=1.0,
        belt_height=0.61,
        lapel_width=1.0,
        skin_color=[0.63, 0.40, 0.28, 1],
        hair_color=[0.055, 0.035, 0.023, 1],
        cloth_color=[0.13, 0.15, 0.18, 1],
        accent_color=[0.28, 0.18, 0.08, 1],
    )
    return result


def _validate_character(character):
    keys = {
        *CHARACTER_LIMITS,
        "style",
        "age",
        "pose",
        "face",
        "hair",
        "clothing",
        "footwear",
        "skin_color",
        "hair_color",
        "cloth_color",
        "accent_color",
    }
    optional_colors = {"trouser_color", "footwear_color"}
    optional = optional_colors | {"age_blend", "detail", "arm_angle_degrees", "period_groom"}
    require(isinstance(character, dict) and keys <= set(character) <= keys | optional, "character_fields_invalid")
    require(
        character["style"] in ("realistic", "stylized")
        and character["age"] in ("adult", "mature", "elder")
        and character["pose"] == "A",
        "character_style_invalid",
    )
    require(
        character["hair"] in ("short", "short_wavy", "bald")
        and character["clothing"] in ("tshirt_trousers", "robe_belt", "coverall", "cross_collar_tunic"),
        "character_outfit_invalid",
    )
    require(character["footwear"] in ("shoes", "sandals", "barefoot"), "character_footwear_invalid")
    resolve_detail(character)
    resolve_arm_angle(character)
    resolve_period_groom(character)
    require(
        all(_number(character[key], *bounds) for key, bounds in CHARACTER_LIMITS.items()), "character_morph_invalid"
    )
    require(
        character["clothing"] not in ("robe_belt", "cross_collar_tunic")
        or character["hem_height"] < character["belt_height"] - 0.025,
        "character_belt_above_hem_required",
    )
    require(
        _keys(character["face"], FACE_LIMITS)
        and all(_number(character["face"][key], *bounds) for key, bounds in FACE_LIMITS.items()),
        "character_face_invalid",
    )
    require(character["style"] == "stylized" or character["face"]["eye_size"] <= 1.2, "realistic_eye_size_invalid")
    require(
        all(_vector(character[key], 4, 0, 1) for key in ("skin_color", "hair_color", "cloth_color", "accent_color")),
        "character_colors_invalid",
    )
    require(
        all(character.get(key) is None or _vector(character[key], 4, 0, 1) for key in optional_colors),
        "character_optional_colors_invalid",
    )
    require(character.get("age_blend") is None or _number(character["age_blend"], 0, 1), "character_age_blend_invalid")


def require(condition, code):
    if not condition:
        raise ValueError(code)


def _name(value):
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 80
        and value == value.strip()
        and not any(ord(c) < 32 or ord(c) == 127 or c in '/\\.:@%"' for c in value)
    )


def _number(value, minimum, maximum):
    return type(value) in (int, float) and minimum <= value <= maximum and math.isfinite(value)


def _vector(value, size, minimum, maximum):
    return isinstance(value, list) and len(value) == size and all(_number(v, minimum, maximum) for v in value)


def _keys(value, names):
    return isinstance(value, dict) and set(value) == set(names)


def validate_plan(plan):
    required = {"version", "name", "materials", "regions", "finish", "completion"}
    require(
        isinstance(plan, dict) and required <= set(plan) <= required | {"character", "repeat_patterns"},
        "plan_fields_invalid",
    )
    character = plan.get("character")
    if character is not None:
        _validate_character(character)
    require(
        type(plan["version"]) is int and plan["version"] == 2 and _name(plan["name"]), "plan_version_or_name_invalid"
    )
    materials = plan["materials"]
    require(
        isinstance(materials, list) and (0 if character is not None else 1) <= len(materials) <= 32, "materials_invalid"
    )
    names = set()
    for material in materials:
        require(_keys(material, ("name", "color", "roughness")), "material_fields_invalid")
        require(
            _name(material["name"])
            and material["name"] not in names
            and (character is None or not material["name"].startswith("Anatomy")),
            "material_name_invalid",
        )
        require(_vector(material["color"], 4, 0, 1) and _number(material["roughness"], 0, 1), "material_values_invalid")
        names.add(material["name"])
    regions = plan["regions"]
    require(isinstance(regions, list) and (0 if character is not None else 1) <= len(regions) <= 64, "regions_invalid")
    region_names = set()
    control_vertices = 0
    for region in regions:
        require(_keys(region, ("name", "role", "material", "surface")), "region_fields_invalid")
        require(
            _name(region["name"])
            and region["name"] not in region_names
            and (character is None or not region["name"].startswith("Anatomy_")),
            "region_name_invalid",
        )
        region_names.add(region["name"])
        require(
            region["role"] in ("body", "accessory") and _name(region["material"]) and region["material"] in names,
            "region_role_or_material_invalid",
        )
        surface = region["surface"]
        require(
            isinstance(surface, dict)
            and {"kind", "position", "rotation_degrees", "size", "sections", "vertices", "faces"}
            <= set(surface)
            <= {"kind", "position", "rotation_degrees", "size", "sections", "vertices", "faces", "end_caps"},
            "surface_fields_invalid",
        )
        require(surface["kind"] in KINDS, "surface_kind_invalid")
        validate_caps(surface)
        require(_vector(surface["position"], 3, -100, 100), "surface_position_invalid")
        require(_vector(surface["rotation_degrees"], 3, -3600, 3600), "surface_rotation_invalid")
        require(_vector(surface["size"], 3, 0.001, 20), "surface_size_invalid")
        require(all(isinstance(surface[k], list) for k in ("sections", "vertices", "faces")), "surface_arrays_invalid")
        if surface["kind"] == "loft":
            sections = surface["sections"]
            require(
                2 <= len(sections) <= 64 and not surface["vertices"] and not surface["faces"], "loft_arrays_invalid"
            )
            previous = None
            for section in sections:
                require(_keys(section, ("center", "radius", "roll")), "section_fields_invalid")
                require(
                    _vector(section["center"], 3, -100, 100)
                    and _vector(section["radius"], 4, 0.001, 20)
                    and _number(section["roll"], -3600, 3600),
                    "section_values_invalid",
                )
                if previous is not None:
                    require(
                        sum((a - b) ** 2 for a, b in zip(previous, section["center"])) > 1e-12,
                        "section_path_zero_length",
                    )
                previous = section["center"]
            control_vertices += len(sections)
        elif surface["kind"] == "cage":
            vertices, faces = surface["vertices"], surface["faces"]
            require(
                not surface["sections"] and 4 <= len(vertices) <= 2048 and 4 <= len(faces) <= 4096,
                "cage_arrays_invalid",
            )
            require(all(_vector(v, 3, -100, 100) for v in vertices), "cage_vertices_invalid")
            edge_uses = {}
            vertex_faces = {index: set() for index in range(len(vertices))}
            face_keys = set()
            for face_index, face in enumerate(faces):
                require(
                    isinstance(face, list)
                    and 3 <= len(face) <= 4
                    and all(type(i) is int and 0 <= i < len(vertices) for i in face)
                    and len(set(face)) == len(face),
                    "cage_indices_invalid",
                )
                key = tuple(sorted(face))
                require(key not in face_keys, "cage_duplicate_face")
                face_keys.add(key)
                for vertex in face:
                    vertex_faces[vertex].add(face_index)
                for a, b in zip(face, face[1:] + face[:1]):
                    edge = tuple(sorted((a, b)))
                    edge_uses[edge] = edge_uses.get(edge, 0) + 1
            require(edge_uses and all(count == 2 for count in edge_uses.values()), "cage_not_closed_manifold")
            for vertex, incident in vertex_faces.items():
                require(bool(incident), "cage_isolated_vertex")
                pending = [next(iter(incident))]
                visited = set()
                while pending:
                    face_index = pending.pop()
                    if face_index in visited:
                        continue
                    visited.add(face_index)
                    face = faces[face_index]
                    corner = face.index(vertex)
                    neighbors = {face[(corner - 1) % len(face)], face[(corner + 1) % len(face)]}
                    pending.extend(index for index in incident - visited if neighbors.intersection(faces[index]))
                require(visited == incident, "cage_nonmanifold_vertex")
            control_vertices += len(vertices)
        else:
            require(
                not surface["sections"] and not surface["vertices"] and not surface["faces"], "primitive_arrays_invalid"
            )
    require(control_vertices <= 8192, "control_vertex_budget_exceeded")
    require(character is not None or any(region["role"] == "body" for region in regions), "body_required")
    finish = plan["finish"]
    require(_keys(finish, ("voxel_size", "smooth_iterations", "subdivision")), "finish_fields_invalid")
    require(_number(finish["voxel_size"], 0.003, 0.1), "voxel_size_invalid")
    require(
        type(finish["smooth_iterations"]) is int and 0 <= finish["smooth_iterations"] <= 8, "smooth_iterations_invalid"
    )
    require(type(finish["subdivision"]) is int and 0 <= finish["subdivision"] <= 2, "subdivision_invalid")
    completion = plan["completion"]
    require(
        _keys(completion, ("mode", "inferred_regions"))
        and completion["mode"] in ("plausible", "reference_constrained"),
        "completion_invalid",
    )
    validate_patterns(plan, _name)
    region_names.update(pattern["name"] for pattern in (plan.get("repeat_patterns") or []))
    inferred = completion["inferred_regions"]
    if character is not None:
        region_names.add("character")
    require(
        isinstance(inferred, list)
        and all(isinstance(v, str) and v in region_names for v in inferred)
        and len(set(inferred)) == len(inferred),
        "completion_regions_invalid",
    )
    return json.loads(json.dumps(plan, ensure_ascii=False, allow_nan=False))


def modeling_schema():
    def vector(length, minimum, maximum):
        return dict(
            type="array", minItems=length, maxItems=length, items=dict(type="number", minimum=minimum, maximum=maximum)
        )

    def obj(properties):
        return dict(type="object", properties=properties, required=list(properties), additionalProperties=False)

    name = dict(
        type="string",
        minLength=1,
        maxLength=80,
        pattern=r'^[^\s\x00-\x1f\x7f/\\.:@%"](?:[^\x00-\x1f\x7f/\\.:@%"]*[^\s\x00-\x1f\x7f/\\.:@%"])?$',
    )
    section = obj(
        dict(
            center=vector(3, -100, 100),
            radius=vector(4, 0.001, 20),
            roll=dict(type="number", minimum=-3600, maximum=3600),
        )
    )
    surface = obj(
        dict(
            kind=dict(type="string", enum=list(KINDS)),
            end_caps=end_caps_schema(),
            position=vector(3, -100, 100),
            rotation_degrees=vector(3, -3600, 3600),
            size=vector(3, 0.001, 20),
            sections=dict(type="array", maxItems=64, items=section),
            vertices=dict(type="array", maxItems=2048, items=vector(3, -100, 100)),
            faces=dict(
                type="array",
                maxItems=4096,
                items=dict(type="array", minItems=3, maxItems=4, items=dict(type="integer", minimum=0, maximum=2047)),
            ),
        )
    )
    character_properties = {
        key: dict(type="number", minimum=bounds[0], maximum=bounds[1]) for key, bounds in CHARACTER_LIMITS.items()
    }
    character_properties.update(
        style=dict(type="string", enum=["realistic", "stylized"]),
        age=dict(type="string", enum=["adult", "mature", "elder"]),
        pose=dict(type="string", enum=["A"]),
        face=obj({
            key: dict(type="number", minimum=bounds[0], maximum=bounds[1]) for key, bounds in FACE_LIMITS.items()
        }),
        hair=dict(type="string", enum=["short", "short_wavy", "bald"]),
        clothing=dict(type="string", enum=["tshirt_trousers", "robe_belt", "coverall", "cross_collar_tunic"]),
        footwear=dict(type="string", enum=["shoes", "sandals", "barefoot"]),
    )
    for key in ("skin_color", "hair_color", "cloth_color", "accent_color"):
        character_properties[key] = vector(4, 0, 1)
    for key in ("trouser_color", "footwear_color"):
        character_properties[key] = dict(anyOf=[dict(type="null"), vector(4, 0, 1)])
    character_properties["face"]["properties"]["eye_size"]["description"] = (
        "Realistic eyes .8..1.2; stylized eyes .8..1.6. Stylized values above1 scale eyelids and globes consistently."
    )
    character_properties["detail"] = detail_schema()
    character_properties["period_groom"] = period_groom_schema()
    character_properties["arm_angle_degrees"] = dict(
        anyOf=[dict(type="null"), dict(type="number", minimum=20, maximum=75)],
        description="A-pose arm angle in degrees DOWN FROM HORIZONTAL; null preserves historical 65 degrees. The same two-bone pose moves body, hands, and garment.",
    )
    character_properties["age_blend"] = dict(anyOf=[dict(type="null"), dict(type="number", minimum=0, maximum=1)])
    return obj(
        dict(
            version=dict(type="integer", const=2),
            name=name,
            materials=dict(
                type="array",
                minItems=0,
                maxItems=32,
                items=obj(dict(name=name, color=vector(4, 0, 1), roughness=dict(type="number", minimum=0, maximum=1))),
            ),
            regions=dict(
                type="array",
                minItems=0,
                maxItems=64,
                items=obj(
                    dict(
                        name=name, role=dict(type="string", enum=["body", "accessory"]), material=name, surface=surface
                    )
                ),
            ),
            finish=obj(
                dict(
                    voxel_size=dict(type="number", minimum=0.003, maximum=0.1),
                    smooth_iterations=dict(type="integer", minimum=0, maximum=8),
                    subdivision=dict(type="integer", minimum=0, maximum=2),
                )
            ),
            completion=obj(
                dict(
                    mode=dict(type="string", enum=["plausible", "reference_constrained"]),
                    inferred_regions=dict(type="array", maxItems=64, items=name),
                )
            ),
            character=dict(anyOf=[dict(type="null"), obj(character_properties)]),
            repeat_patterns=patterns_schema(name),
        )
    )


def _gaussian(x, y, cx, cy, sx, sy):
    return math.exp(-0.5 * (((x - cx) / sx) ** 2 + ((y - cy) / sy) ** 2))


def _head_dimensions(c):
    height = c["height"] / c["head_ratio"]
    return height, c["height"] - height / 2, height / 0.24


def _face_offset(x, y, c):
    _, _, s = _head_dimensions(c)
    f = c["face"]
    x /= s
    y /= s
    eyes = 0.032 * f["eye_spacing"]
    z = 0.0
    for sign in (-1, 1):
        z -= 0.009 * _gaussian(x, y, sign * eyes, 0.024, 0.017 * f["eye_size"], 0.010)
        z += 0.005 * _gaussian(x, y, sign * eyes, 0.040, 0.024, 0.008)
        z += 0.0055 * f["cheek_fullness"] * _gaussian(x, y, sign * 0.043, -0.012, 0.022, 0.018)
    z += 0.011 * f["nose_length"] * _gaussian(x, y, 0, 0.003, 0.008 * f["nose_width"], 0.029)
    z += 0.022 * f["nose_length"] * _gaussian(x, y, 0, -0.014, 0.011 * f["nose_width"], 0.009)
    for sign in (-1, 1):
        z += 0.0065 * _gaussian(x, y, sign * 0.012 * f["nose_width"], -0.020, 0.0065, 0.006)
        z -= 0.002 * _gaussian(x, y, sign * 0.008 * f["mouth_width"], -0.047, 0.008, 0.0025)
    width = 0.025 * f["mouth_width"]
    z += 0.0042 * f["lip_fullness"] * _gaussian(x, y, 0, -0.047, width, 0.0030)
    z += 0.0055 * f["lip_fullness"] * _gaussian(x, y, 0, -0.055, width * 0.9, 0.0038)
    z -= 0.0032 * _gaussian(x, y, 0, -0.051, width, 0.0013)
    z += 0.004 * _gaussian(x, y, 0, -0.083, 0.025, 0.013)
    age = resolve_age_blend(c)
    for line in (0.059, 0.070):
        z -= age * 0.0015 * _gaussian(x, y, 0, line, 0.05, 0.0015)
    for sign in (-1, 1):
        z -= age * 0.003 * _gaussian(x, y, sign * 0.027, -0.036, 0.005, 0.023)
        z += age * 0.002 * _gaussian(x, y, sign * eyes, 0.011, 0.019, 0.004)
    return z * s


def _head_point(t, angle, c):
    hh, cy, s = _head_dimensions(c)
    f = c["face"]
    radial = math.sqrt(max(0, 1 - t * t))
    jaw = 0.17 * (2 - f["jaw_width"]) * math.exp(-(((t + 0.58) / 0.23) ** 2))
    rx = hh * 0.33 * c["head_width"] * (1 - jaw)
    rz = hh * (0.34 if math.sin(angle) >= 0 else 0.39) * c["head_depth"]
    x = rx * radial * math.cos(angle)
    localy = hh * 0.5 * t * (1 + (f["chin_length"] - 1) * max(0, -t) * 0.4)
    z = rz * radial * math.sin(angle)
    if math.sin(angle) > 0:
        z += _face_offset(x, localy, c) * min(1, math.sin(angle) * 4)
    return [x, cy + localy, z]


def _head_front(x, y, c):
    hh, cy, _ = _head_dimensions(c)
    t = max(-0.98, min(0.98, (y - cy) / (hh * 0.5)))
    radial = math.sqrt(1 - t * t)
    jaw = 0.17 * (2 - c["face"]["jaw_width"]) * math.exp(-(((t + 0.58) / 0.23) ** 2))
    rx = hh * 0.33 * c["head_width"] * (1 - jaw)
    return hh * 0.34 * c["head_depth"] * math.sqrt(max(0, radial * radial - (x / rx) ** 2)) + _face_offset(x, y - cy, c)


def _head_cage(c):
    # The CC0 canonical cage supplies anatomy, while bounded input parameters
    # deform that cage. Neither reference meshes nor generated code are loaded.
    age = resolve_age_blend(c)
    return [
        _anatomy_point([value + change * age for value, change in zip(point, delta)], c)
        for point, delta in zip(HEAD_VERTICES, AGE_DELTAS)
    ], list(HEAD_FACES)


def _eye_age_delta(anchor):
    nearest = sorted(
        range(len(HEAD_VERTICES)), key=lambda index: sum((a - b) ** 2 for a, b in zip(anchor, HEAD_VERTICES[index]))
    )[:24]
    weights = [1 / (sum((a - b) ** 2 for a, b in zip(anchor, HEAD_VERTICES[index])) + 0.0001) for index in nearest]
    return [
        sum(AGE_DELTAS[index][axis] * weight for index, weight in zip(nearest, weights)) / sum(weights)
        for axis in range(3)
    ]


def _smoothstep(lower, upper, value):
    t = max(0, min(1, (value - lower) / (upper - lower)))
    return t * t * (3 - 2 * t)


def _canonical_body(character):
    """Morph one closed CC0 control surface; no skin components are spliced."""
    from anatomy_body import (
        BODY_AGE_DELTAS,
        BODY_ARM_WEIGHTS,
        BODY_DIGIT_TIP_AGE_DELTAS,
        BODY_DIGIT_TIPS,
        BODY_FACES,
        BODY_FOREARM_WEIGHTS,
        BODY_HAND_WEIGHTS,
        BODY_HEAD_FRAME,
        BODY_LANDMARK_AGE_DELTAS,
        BODY_LANDMARKS,
        BODY_SOURCE_SHA256,
        BODY_VERTICES,
    )

    c = character
    detail = resolve_detail(c)
    age = resolve_age_blend(c)

    def aged(point, delta):
        return [value + change * age for value, change in zip(point, delta)]

    points = [aged(point, delta) for point, delta in zip(BODY_VERTICES, BODY_AGE_DELTAS)]
    landmarks = {key: aged(point, BODY_LANDMARK_AGE_DELTAS[key]) for key, point in BODY_LANDMARKS.items()}
    digits = {
        side: [aged(point, delta) for point, delta in zip(BODY_DIGIT_TIPS[side], BODY_DIGIT_TIP_AGE_DELTAS[side])]
        for side in ("L", "R")
    }
    chin = landmarks.get("chin", landmarks["jaw"])
    top = max(point[1] for point in points)
    head_height = top - chin[1]
    head_origin = list(BODY_HEAD_FRAME["origin"])
    head_origin[1] = (top + chin[1]) / 2
    eye_mid = [(landmarks["eyeL"][axis] + landmarks["eyeR"][axis]) / 2 for axis in range(3)]
    face_eyes = {side: tuple(landmarks["eye" + side]) for side in ("L", "R")}
    hip_y = (landmarks["hipL"][1] + landmarks["hipR"][1]) / 2
    shoulders = {side: landmarks["shoulder" + side] for side in ("L", "R")}
    f = c["face"]

    def face(point):
        x, y, z = point
        px, py = x, y
        front = max(0, min(1, (z - eye_mid[2] + 0.28 * head_height) / (0.18 * head_height)))
        jaw = math.exp(-0.5 * ((y - chin[1] - 0.13 * head_height) / (0.18 * head_height)) ** 2) * front
        x *= 1 + (f["jaw_width"] - 1) * jaw * 0.85
        y -= (
            0.09
            * head_height
            * (f["chin_length"] - 1)
            * math.exp(-0.5 * ((py - chin[1]) / (0.10 * head_height)) ** 2)
            * front
        )
        for side in ("L", "R"):
            eye = face_eyes[side]
            sign = 1 if eye[0] >= 0 else -1
            patch = _gaussian(px, py, eye[0], eye[1], 0.115 * head_height, 0.085 * head_height) * front
            x += eye[0] * (f["eye_spacing"] - 1) * patch
            x += (px - eye[0]) * (f["eye_size"] - 1) * patch
            y += (py - eye[1]) * (f["eye_size"] - 1) * patch
            cheek = (
                _gaussian(px, py, eye[0] * 1.35, eye[1] - 0.16 * head_height, 0.11 * head_height, 0.11 * head_height)
                * front
            )
            z += 0.035 * head_height * (f["cheek_fullness"] - 1) * cheek
            ear = (
                (1 if sign * px > 0 else 0)
                * max(0, min(1, (abs(px) / head_height - 0.26) / 0.065))
                * math.exp(-0.5 * ((py - eye[1] + 0.03 * head_height) / (0.16 * head_height)) ** 2)
            )
            x += (px - sign * 0.27 * head_height) * (f["ear_size"] - 1) * ear
            y += (py - eye[1] + 0.03 * head_height) * (f["ear_size"] - 1) * ear
        nose = _gaussian(px, py, 0, eye_mid[1] - 0.14 * head_height, 0.105 * head_height, 0.14 * head_height) * front
        x *= 1 + (f["nose_width"] - 1) * nose
        z += 0.15 * head_height * (f["nose_length"] - 1) * nose
        mouth = _gaussian(px, py, 0, chin[1] + 0.19 * head_height, 0.14 * head_height, 0.055 * head_height) * front
        x *= 1 + (f["mouth_width"] - 1) * mouth
        z += 0.028 * head_height * (f["lip_fullness"] - 1) * mouth
        head_weight = _smoothstep(chin[1] - 0.22 * head_height, chin[1] + 0.08 * head_height, py)
        x = px + (x * c["head_width"] - px) * head_weight
        z = point[2] + ((head_origin[2] + (z - head_origin[2]) * c["head_depth"]) - point[2]) * head_weight
        y = point[1] + (y - point[1]) * head_weight
        offset = face_detail_offset(
            [x, y, z], {"origin": head_origin, "height": head_height}, face_eyes, detail, c["style"]
        )
        return [x + offset[0], y + offset[1], z + offset[2]]

    def base(point, arm_weights=(0, 0)):
        x, y, z = face(point)
        arm = sum(arm_weights)
        head_weight = _smoothstep(chin[1] - 0.22 * head_height, chin[1] + 0.08 * head_height, point[1])
        shoulder_y = (shoulders["L"][1] + shoulders["R"][1]) / 2
        g_shoulder = math.exp(-0.5 * ((y - shoulder_y) / 0.07) ** 2) * (1 - head_weight)
        g_hip = math.exp(-0.5 * ((y - hip_y) / 0.12) ** 2)
        g_build = math.exp(-0.5 * ((y - (hip_y + shoulder_y) / 2) / 0.15) ** 2) * (1 - head_weight) * (1 - arm)
        x *= (
            1
            + (c["shoulder_width"] - 1) * g_shoulder * (1 - arm)
            + (c["hip_width"] - 1) * g_hip * (1 - arm)
            + 0.12 * c["build"] * g_build
        )
        z *= 1 + 0.20 * c["build"] * g_build
        x += sum(
            shoulders[side][0] * (c["shoulder_width"] - 1) * weight for side, weight in zip(("L", "R"), arm_weights)
        )
        y += 0.06 * (c["neck_length"] - 1) * _smoothstep(shoulder_y - 0.01, chin[1], y)
        if y < hip_y:
            y *= c["limb_length"]
        else:
            y += hip_y * (c["limb_length"] - 1)
        return [x, y, z]

    shoulder_points = {side: base(shoulders[side], (1, 0) if side == "L" else (0, 1)) for side in ("L", "R")}
    wrist_points = {side: base(landmarks["wrist" + side], (1, 0) if side == "L" else (0, 1)) for side in ("L", "R")}

    def rotation_between(source, target):
        def unit(vector):
            length = math.sqrt(sum(value * value for value in vector))
            require(length > 1e-12, "canonical_bone_length_zero")
            return [value / length for value in vector]

        a, b = unit(source), unit(target)
        cosine = max(-1, min(1, sum(x * y for x, y in zip(a, b))))
        axis = [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
        sine = math.sqrt(sum(value * value for value in axis))
        if sine < 1e-12:
            require(cosine > 0, "canonical_bone_rotation_opposite")
            return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        axis = [value / sine for value in axis]
        x, y, z = axis
        cross = [[0, -z, y], [z, 0, -x], [-y, x, 0]]
        return [
            [cosine * (1 if i == j else 0) + (1 - cosine) * axis[i] * axis[j] + sine * cross[i][j] for j in range(3)]
            for i in range(3)
        ]

    def rotate(matrix, vector):
        return [sum(value * coordinate for value, coordinate in zip(row, vector)) for row in matrix]

    poses = {}
    for side in ("L", "R"):
        arm = (1, 0) if side == "L" else (0, 1)
        shoulder = shoulder_points[side]
        elbow = base(landmarks["elbow" + side], arm)
        wrist = wrist_points[side]
        elbow = [shoulder[i] + (elbow[i] - shoulder[i]) * c["limb_length"] for i in range(3)]
        wrist = [shoulder[i] + (wrist[i] - shoulder[i]) * c["limb_length"] for i in range(3)]
        sign = 1 if shoulder[0] >= 0 else -1
        angle = math.radians(resolve_arm_angle(c))
        direction = [sign * math.cos(angle), -math.sin(angle), 0]
        upper = rotation_between([elbow[i] - shoulder[i] for i in range(3)], direction)
        elbow_pos = [
            shoulder[i] + value for i, value in enumerate(rotate(upper, [elbow[i] - shoulder[i] for i in range(3)]))
        ]
        wrist_pos = [
            shoulder[i] + value for i, value in enumerate(rotate(upper, [wrist[i] - shoulder[i] for i in range(3)]))
        ]
        lower = rotation_between([wrist_pos[i] - elbow_pos[i] for i in range(3)], direction)
        poses[side] = dict(shoulder=shoulder, wrist=wrist, elbow=elbow_pos, upper=upper, lower=lower)

    def pose(point, arm_weights=(0, 0), hand_weights=(0, 0), forearm_weights=(0, 0)):
        p = base(point, arm_weights)
        result = list(p)
        for side, weight, hand in zip(("L", "R"), arm_weights, hand_weights):
            if not weight:
                continue
            shoulder = shoulder_points[side]
            wrist = poses[side]["wrist"]
            target = [shoulder[i] + (p[i] - shoulder[i]) * c["limb_length"] for i in range(3)]
            target = [target[i] + (target[i] - wrist[i]) * (c["hand_scale"] - 1) * hand for i in range(3)]
            rotated = [
                shoulder[i] + value
                for i, value in enumerate(rotate(poses[side]["upper"], [target[i] - shoulder[i] for i in range(3)]))
            ]
            result = [value + weight * (new - old) for value, new, old in zip(result, rotated, p)]
        for side, weight in zip(("L", "R"), forearm_weights):
            if not weight:
                continue
            elbow = poses[side]["elbow"]
            rotated = [
                elbow[i] + value
                for i, value in enumerate(rotate(poses[side]["lower"], [result[i] - elbow[i] for i in range(3)]))
            ]
            result = [value + weight * (new - value) for value, new in zip(result, rotated)]
        return result

    points = [
        pose(point, arm, hand, forearm)
        for point, arm, hand, forearm in zip(points, BODY_ARM_WEIGHTS, BODY_HAND_WEIGHTS, BODY_FOREARM_WEIGHTS)
    ]
    new_landmarks = {}
    for key, point in landmarks.items():
        side = key[-1] if key[-1:] in ("L", "R") and key.startswith(("shoulder", "elbow", "wrist", "palm")) else None
        arm = (1, 0) if side == "L" else (0, 1) if side == "R" else (0, 0)
        new_landmarks[key] = pose(
            point, arm, arm if key.startswith("palm") else (0, 0), arm if key.startswith(("wrist", "palm")) else (0, 0)
        )
    digits = {
        side: [
            pose(
                point,
                (1, 0) if side == "L" else (0, 1),
                (1, 0) if side == "L" else (0, 1),
                (1, 0) if side == "L" else (0, 1),
            )
            for point in values
        ]
        for side, values in digits.items()
    }
    landmarks = new_landmarks
    chin = landmarks.get("chin", landmarks["jaw"])
    top = max(point[1] for point in points)
    bottom = min(point[1] for point in points)
    current_head = top - chin[1]
    target_head = (top - bottom - current_head) / (c["head_ratio"] - 1)
    head_scale = target_head / current_head

    def head_size(point):
        weight = _smoothstep(chin[1] - 0.22 * current_head, chin[1] + 0.08 * current_head, point[1])
        pivot = (0, chin[1], head_origin[2])
        return [value + (value - pivot[i]) * (head_scale - 1) * weight for i, value in enumerate(point)]

    points = [head_size(point) for point in points]
    landmarks = {key: head_size(point) for key, point in landmarks.items()}
    digits = {side: [head_size(point) for point in values] for side, values in digits.items()}
    low = min(point[1] for point in points)
    high = max(point[1] for point in points)
    scale = c["height"] / (high - low)
    middle = (landmarks["hipL"][1] + landmarks["shoulderL"][1]) / 2
    torso_z = [
        point[2]
        for point, weights in zip(points, BODY_ARM_WEIGHTS)
        if abs(point[1] - middle) < 0.02 and sum(weights) < 0.1
    ]
    z_center = (min(torso_z) + max(torso_z)) / 2 if torso_z else 0

    def meters(point):
        return [point[0] * scale, (point[1] - low) * scale, (point[2] - z_center) * scale]

    return dict(
        vertices=[meters(point) for point in points],
        faces=list(BODY_FACES),
        landmarks={key: meters(point) for key, point in landmarks.items()},
        digits={side: [meters(point) for point in values] for side, values in digits.items()},
        arm_weights=BODY_ARM_WEIGHTS,
        source_sha256=BODY_SOURCE_SHA256,
        head_frame=dict(
            origin=[
                0,
                c["height"] - (c["height"] - meters(landmarks["chin"])[1]) / 2,
                (head_origin[2] - z_center) * scale,
            ],
            height=c["height"] - meters(landmarks["chin"])[1],
        ),
    )


def _anatomy_point(point, c):
    x, y, z = point
    f = c["face"]
    age = resolve_age_blend(c)
    original_x, original_y = x, y
    front = max(0, min(1, (z - 0.23) / 0.14))
    jaw = math.exp(-0.5 * ((y + 0.34) / 0.15) ** 2)
    x *= 1 + (f["jaw_width"] - 1) * jaw * 0.85
    y -= 0.09 * (f["chin_length"] - 1) * math.exp(-0.5 * ((y + 0.46) / 0.11) ** 2)
    for sign in (-1, 1):
        eye = _gaussian(original_x, original_y, sign * 0.13377, -0.02472, 0.115, 0.085) * front
        x += sign * 0.13377 * (f["eye_spacing"] - 1) * eye
        x += (original_x - sign * 0.13377) * (f["eye_size"] - 1) * eye
        y += (original_y + 0.02472) * (f["eye_size"] - 1) * eye
        y -= age * (original_y + 0.02472) * 0.22 * eye
        cheek = _gaussian(original_x, original_y, sign * 0.19, -0.19, 0.11, 0.11) * front
        z += 0.055 * (f["cheek_fullness"] - 1) * cheek
        y -= age * 0.025 * cheek
        z -= age * 0.008 * _gaussian(original_x, original_y, sign * 0.105, -0.24, 0.016, 0.09) * front
        x -= sign * age * 0.025 * cheek
        z -= age * 0.009 * _gaussian(original_x, original_y, sign * 0.105, -0.24, 0.014, 0.09) * front
        y -= age * 0.016 * _gaussian(original_x, original_y, sign * 0.115, -0.325, 0.045, 0.05) * front
        z += age * 0.020 * _gaussian(original_x, original_y, sign * 0.20, -0.37, 0.06, 0.065) * front
        z -= age * 0.005 * _gaussian(original_x, original_y, sign * 0.14, -0.081, 0.07, 0.012) * front
    nose = _gaussian(original_x, original_y, 0, -0.115, 0.105, 0.14) * front
    x *= 1 + (f["nose_width"] - 1) * nose
    z += 0.20 * (f["nose_length"] - 1) * nose
    mouth = _gaussian(original_x, original_y, 0, -0.325, 0.14, 0.055) * front
    x *= 1 + (f["mouth_width"] - 1) * mouth
    z += 0.04 * (f["lip_fullness"] - 1) * mouth
    ear = max(0, min(1, (abs(original_x) - 0.26) / 0.065)) * math.exp(-0.5 * ((original_y + 0.04) / 0.16) ** 2)
    x += (original_x - math.copysign(0.27, original_x)) * (f["ear_size"] - 1) * ear
    y += (original_y + 0.04) * (f["ear_size"] - 1) * ear
    for line in (0.15, 0.205):
        z -= age * 0.008 * _gaussian(original_x, original_y, 0, line, 0.19, 0.01) * front
    # Tuck the fixed asset's capped neck extension inside the continuous neck.
    # Chin/front-jaw vertices remain untouched by this local attachment morph.
    neck = max(0, min(1, (-original_y - 0.35) / 0.23)) * max(0, min(1, (0.40 - point[2]) / 0.15))
    x *= 1 - 0.40 * neck
    z = 0.05 + (z - 0.05) * (1 - 0.40 * neck)
    hh, cy, _ = _head_dimensions(c)
    return [x * hh * c["head_width"], cy + y * hh, z * hh * c["head_depth"]]


def _garment_shell(canonical, c, kind, inner_layer=False):
    """Clip one trusted BODY surface with shared edge caching, then add ease.

    The returned surface is intentionally open at collar, hem and cuffs. The
    fixed build stage adds cloth thickness and verifies every resulting mesh.
    """
    detail = resolve_detail(c)
    positions = canonical["vertices"]
    source_faces = canonical["faces"]
    land = canonical["landmarks"]
    scale = c["height"] / 1.8
    hip_y = (land["hipL"][1] + land["hipR"][1]) / 2
    hem = c["hem_height"] * c["height"]
    clip_hem = max(hem, hip_y - 0.02 * c["height"])
    neck_top = land.get("chin", land["jaw"])[1] - 0.045 * scale
    belt = c["belt_height"] * c["height"]
    v_bottom = (
        neck_top - 0.105 * scale
        if c["clothing"] == "cross_collar_tunic"
        else min(belt + 0.20 * scale, neck_top - 0.10 * scale)
    )
    # The decorative GI belt may sit low; trousers must always retain their seat.
    waist = trouser_waist(hem, hip_y + 0.035 * c["height"], c["height"], c["clothing"])
    cuff = (land["ankleL"][1] + land["ankleR"][1]) / 2 + 0.005 * c["height"]
    if kind == "coverall":
        clip_hem = hip_y - 0.02 * c["height"]
    normals = [[0.0, 0.0, 0.0] for _ in positions]
    for face in source_faces:
        p = positions[face[0]]
        for i in range(1, len(face) - 1):
            a = [positions[face[i]][axis] - p[axis] for axis in range(3)]
            b = [positions[face[i + 1]][axis] - p[axis] for axis in range(3)]
            normal = [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
            for index in face:
                for axis in range(3):
                    normals[index][axis] += normal[axis]
    records = []
    for index, (point, normal, weights) in enumerate(zip(positions, normals, canonical["arm_weights"])):
        x, y, z = point
        arm = sum(weights)
        if kind == "hair":
            hh = c["height"] / c["head_ratio"]
            center = c["height"] - hh / 2
            masks = [
                hair_detail_mask(point, canonical["head_frame"])
                if c["hair"] == "short_wavy"
                else y - (center + 0.10 * hh + 0.30 * z + 0.25 * abs(x))
            ]
        elif kind in ("shirt", "coverall"):
            side = "L" if weights[0] >= weights[1] else "R"
            s, e, w = (land[key + side] for key in ("shoulder", "elbow", "wrist"))
            upper = math.dist(s, e)
            lower = math.dist(e, w)
            direction = [(w[i] - s[i]) / (upper + lower) for i in range(3)]
            along = sum((point[i] - s[i]) * direction[i] for i in range(3)) / (upper + lower)
            sleeve = c["sleeve_length"] - along if arm > 0.1 else 1
            v = (
                abs(x) - max(0, y - v_bottom) * (0.065 * scale / max(0.05 * scale, neck_top + 0.05 * scale - v_bottom))
                if z > 0
                else 0.2 * scale
            )
            if c["clothing"] not in ("robe_belt", "cross_collar_tunic") or inner_layer:
                v = 0.2 * scale
            masks = [
                (y - cuff if kind == "coverall" else y - clip_hem) if arm < 0.1 else 1,
                neck_top + 0.45 * abs(x) - y,
                sleeve,
                v,
            ]
        else:
            masks = [waist - y, y - cuff, 0.10 - arm]
        records.append([list(point), list(normal), masks, [arm]])
    faces = [list(face) for face in source_faces]
    for mask in range(1 if kind == "hair" else 4 if kind in ("shirt", "coverall") else 3):
        cache = {}
        clipped = []
        for face in faces:
            output = []
            for a, b in zip(face[-1:] + face[:-1], face):
                va, vb = records[a][2][mask], records[b][2][mask]
                if (va >= 0) != (vb >= 0):
                    key = tuple(sorted((a, b)))
                    if va == 0:
                        cache[key] = a
                    elif vb == 0:
                        cache[key] = b
                    elif key not in cache:
                        t = va / (va - vb)
                        record = []
                        for channel in range(4):
                            record.append([v + (w - v) * t for v, w in zip(records[a][channel], records[b][channel])])
                        record[2][mask] = 0.0
                        cache[key] = len(records)
                        records.append(record)
                    output.append(cache[key])
                if vb >= 0:
                    output.append(b)
            output = list(dict.fromkeys(output))
            if len(output) >= 3:
                clipped.append(output)
        faces = clipped
    used = sorted({index for face in faces for index in face})
    mapping = {old: new for new, old in enumerate(used)}

    def envelope_table(side=None):
        lower = clip_hem if side is None else cuff
        upper = (land["shoulderL"][1] + land["shoulderR"][1]) / 2 if side is None else hip_y - 0.12 * c["height"]
        require(upper > lower, "garment_envelope_range_invalid")
        count = 16
        bins = [[] for _ in range(count)]
        for point, weights in zip(positions, canonical["arm_weights"]):
            if sum(weights) > 0.1 or not lower <= point[1] <= upper or (side is not None and point[0] * side <= 0):
                continue
            index = min(count - 1, int((point[1] - lower) / (upper - lower) * count))
            bins[index].append(point)
        rows = []
        for values in bins:
            if not values:
                rows.append(None)
                continue
            cx = 0 if side is None else (min(p[0] for p in values) + max(p[0] for p in values)) / 2
            cz = (min(p[2] for p in values) + max(p[2] for p in values)) / 2
            clearance = 0.025 * scale if side is None else 0.012 * scale
            loosen = 1 if side is None else max(1, c["trouser_width"])
            rx = max(abs(p[0] - cx) for p in values) * loosen + clearance
            front = max(point[2] - cz for point in values) + clearance
            back = max(cz - point[2] for point in values) + clearance
            rows.append([cx, cz, rx, front, back])
        valid = [index for index, row in enumerate(rows) if row is not None]
        require(bool(valid), "garment_envelope_samples_empty")
        for index, row in enumerate(rows):
            if row is None:
                rows[index] = list(rows[min(valid, key=lambda other: abs(other - index))])
        if side is not None:
            floor = (
                0.56
                + 0.20 * min(0.6, max(0, c["trouser_width"] - 1)) / 0.6
                + (0.10 if c["clothing"] == "robe_belt" else 0)
            )
            maximum = [max(row[channel] for row in rows) * floor for channel in (2, 3, 4)]
            for row in rows:
                for channel, minimum in zip((2, 3, 4), maximum):
                    row[channel] = max(row[channel], minimum)
        for _ in range(6):
            previous = [list(row) for row in rows]
            for index, row in enumerate(rows):
                for channel in range(5):
                    row[channel] = (
                        previous[max(0, index - 1)][channel]
                        + 2 * previous[index][channel]
                        + previous[min(count - 1, index + 1)][channel]
                    ) / 4
        return lower, upper, rows

    tables = (
        {0: envelope_table(), -1: envelope_table(-1), 1: envelope_table(1)}
        if kind == "coverall"
        else {0: envelope_table()}
        if kind == "shirt"
        else {side: envelope_table(side) for side in (-1, 1)}
        if kind == "trousers"
        else {}
    )

    def sample_envelope(y, side):
        lower, upper, rows = tables[side]
        position = max(0, min(len(rows) - 1, (y - lower) / (upper - lower) * (len(rows) - 1)))
        index = min(len(rows) - 2, int(position))
        fraction = position - index
        return [a + (b - a) * fraction for a, b in zip(rows[index], rows[index + 1])]

    vertices = []
    mask_values = []
    arm_values = []
    for index in used:
        point, normal, masks, attributes = records[index]
        length = math.sqrt(sum(value * value for value in normal))
        normal = [value / max(1e-12, length) for value in normal]
        if kind == "hair":
            hh = canonical["head_frame"]["height"]
            hair_root_blend = _smoothstep(0.004 * hh, 0.20 * hh, max(0, masks[0]))
            ease = (0.0007 + (0.005 - 0.0007) * hair_root_blend) * scale
        elif kind in ("shirt", "coverall"):
            waist_weight = (
                math.exp(-0.5 * ((point[1] - belt) / (0.07 * scale)) ** 2)
                if c["clothing"] in ("robe_belt", "cross_collar_tunic")
                else 0
            )
            ease = (
                0.025 - 0.015 * waist_weight + 0.010 * math.exp(-0.5 * ((point[1] - clip_hem) / (0.07 * scale)) ** 2)
            ) * scale
        else:
            loosen = 1 - _smoothstep(hip_y - 0.10 * scale, hip_y + 0.04 * scale, point[1])
            ease = max(0.010, (0.012 + 0.070 * (c["trouser_width"] - 1) * loosen)) * scale
            if normal[0] * point[0] < 0 and point[1] < hip_y - 0.10 * scale:
                ease = min(ease, max(0, abs(point[0]) - 0.005 * scale) / max(1e-8, abs(normal[0])))
        expanded = [value + offset * ease for value, offset in zip(point, normal)]
        arm = attributes[0]
        arm_values.append(arm)
        if kind == "shirt" or kind == "coverall" and point[1] >= hip_y - 0.02 * c["height"]:
            cx, cz, rx, front, back = sample_envelope(point[1], 0)
            target_x = max(-rx, min(rx, (point[0] - cx) * rx / max(0.01 * scale, rx - 0.025 * scale)))
            radial = max(0, 1 - (abs(target_x) / rx) ** 4) ** 0.25
            target = [
                cx + target_x,
                point[1],
                cz + (front if point[2] >= cz else -back) * radial,
            ]
            shoulder_y = (land["shoulderL"][1] + land["shoulderR"][1]) / 2
            shoulder_half = (abs(land["shoulderL"][0]) + abs(land["shoulderR"][0])) / 2
            central = 1 - _smoothstep(0.65 * shoulder_half, 0.95 * shoulder_half, abs(point[0]))
            blend = (1 - _smoothstep(shoulder_y - 0.025 * scale, shoulder_y + 0.025 * scale, point[1])) * max(
                1 - min(1, arm * 2), central
            )
            if kind == "coverall":
                blend *= _smoothstep(hip_y - 0.02 * c["height"], hip_y + 0.02 * c["height"], point[1])
            expanded = [a + (b - a) * blend for a, b in zip(expanded, target)]
        elif kind in ("trousers", "coverall"):
            side = 1 if point[0] >= 0 else -1
            cx, cz, rx, front, back = sample_envelope(point[1], side)
            angle = math.atan2(point[2] - cz, point[0] - cx)
            target = [
                cx + rx * math.cos(angle),
                point[1],
                cz + (front if math.sin(angle) >= 0 else back) * math.sin(angle),
            ]
            target[0] = side * max(0.005 * scale, side * target[0])
            blend = 1 - _smoothstep(hip_y - 0.18 * c["height"], hip_y - 0.10 * c["height"], point[1])
            expanded = [a + (b - a) * blend for a, b in zip(expanded, target)]
        if kind == "hair":
            offset = hair_detail_offset(
                point, dict(canonical["head_frame"], hairline_distance=masks[0]), normal, detail
            )
            expanded = [value + change for value, change in zip(expanded, offset)]
        else:
            extra = c["height"] * fabric_outward_offset(
                max(0, min(1, point[1] / c["height"])), math.atan2(point[2], point[0]), detail, kind
            )
            expanded = [value + direction * extra for value, direction in zip(expanded, normal)]
        minimum_clearance = ((0.0007 + (0.0045 - 0.0007) * hair_root_blend) if kind == "hair" else 0.012) * scale
        clearance = sum((value - original) * direction for value, original, direction in zip(expanded, point, normal))
        if clearance < minimum_clearance:
            expanded = [
                value + direction * (minimum_clearance - clearance) for value, direction in zip(expanded, normal)
            ]
        if c["clothing"] == "cross_collar_tunic":
            expanded = period_fabric_offset(point, expanded, normal, arm, canonical, c, kind)
        vertices.append(expanded)
        mask_values.append(masks)
    if c["clothing"] == "cross_collar_tunic" and kind == "trousers":
        for point in vertices:
            side = 1 if point[0] >= 0 else -1
            cx, cz = sample_envelope(cuff, side)[:2]
            gather = 1 - _smoothstep(cuff + 0.008 * scale, cuff + 0.125 * scale, point[1])
            x, z = point[0] - cx, point[2] - cz
            distance = math.hypot(x, z)
            desired = (0.041 + 0.0025 * math.sin(10 * math.atan2(z, x))) * scale
            if distance > desired:
                ratio = 1 + (desired / distance - 1) * gather
                point[0], point[2] = cx + x * ratio, cz + z * ratio
    faces = [[mapping[index] for index in face] for face in faces]
    if kind == "shirt" and hem < clip_hem - 1e-6:
        counts = {}
        directed = {}
        for face in faces:
            for a, b in zip(face, face[1:] + face[:1]):
                key = tuple(sorted((a, b)))
                counts[key] = counts.get(key, 0) + 1
                directed[key] = (a, b)
        edges = [
            directed[key]
            for key, count in counts.items()
            if count == 1 and abs(mask_values[key[0]][0]) < 1e-7 and abs(mask_values[key[1]][0]) < 1e-7
        ]
        following = {a: b for a, b in edges}
        require(bool(edges) and len(following) == len(edges), "garment_hem_loop_invalid")
        loop = [edges[0][0]]
        while following[loop[-1]] != loop[0]:
            loop.append(following[loop[-1]])
            require(len(loop) <= len(edges), "garment_hem_loop_invalid")
        require(len(loop) == len(edges), "garment_hem_multiple_loops")
        original = list(loop)
        extension_steps = 6 if c["clothing"] == "cross_collar_tunic" else 2
        for step in range(1, extension_steps + 1):
            next_loop = []
            t = step / extension_steps
            for index in original:
                point = vertices[index]
                next_loop.append(len(vertices))
                vertices.append([point[0] * (1 + 0.12 * t), point[1] + (hem - point[1]) * t, point[2] * (1 + 0.12 * t)])
                arm_values.append(0.0)
            for a, b, na, nb in zip(loop, loop[1:] + loop[:1], next_loop, next_loop[1:] + next_loop[:1]):
                faces.append([b, a, na, nb])
            loop = next_loop
    require(bool(vertices) and bool(faces), "garment_surface_empty")
    collars = {}
    if kind == "shirt" and c["clothing"] == "robe_belt":
        counts = {}
        for face in faces:
            for a, b in zip(face, face[1:] + face[:1]):
                edge = tuple(sorted((a, b)))
                counts[edge] = counts.get(edge, 0) + 1
        boundary = {
            index
            for edge, count in counts.items()
            if count == 1 and all(index < len(mask_values) and abs(mask_values[index][3]) < 1e-7 for index in edge)
            for index in edge
        }
        triangles = [
            (vertices[face[0]], vertices[face[i]], vertices[face[i + 1]])
            for face in faces
            for i in range(1, len(face) - 1)
        ]

        def front_surface(x, y, fallback):
            found = []
            for a, b, d in triangles:
                denominator = (b[1] - d[1]) * (a[0] - d[0]) + (d[0] - b[0]) * (a[1] - d[1])
                if abs(denominator) < 1e-14:
                    continue
                wa = ((b[1] - d[1]) * (x - d[0]) + (d[0] - b[0]) * (y - d[1])) / denominator
                wb = ((d[1] - a[1]) * (x - d[0]) + (a[0] - d[0]) * (y - d[1])) / denominator
                wd = 1 - wa - wb
                if min(wa, wb, wd) >= -1e-6:
                    found.append(a[2] * wa + b[2] * wb + d[2] * wd)
            return max(found) if found else fallback

        for sign in (-1, 1):
            path = sorted(
                (
                    vertices[index]
                    for index in boundary
                    if vertices[index][0] * sign >= -1e-7 and vertices[index][2] > 0
                ),
                key=lambda point: -point[1],
            )
            if len(path) < 2:
                continue
            band = []
            for step in range(12):
                target_y = path[0][1] + (path[-1][1] - path[0][1]) * step / 11
                segment = next(
                    (i for i in range(len(path) - 1) if path[i][1] >= target_y >= path[i + 1][1]), len(path) - 2
                )
                a, b = path[segment], path[segment + 1]
                fraction = (target_y - a[1]) / min(-1e-9, b[1] - a[1])
                point = [a[i] + (b[i] - a[i]) * fraction for i in range(3)]
                width = 0.025 * scale * c["lapel_width"]
                for fraction_width in (0, 0.1, 0.9, 1):
                    x = point[0] + sign * width * fraction_width
                    band.append([x, point[1], front_surface(x, point[1], point[2]) + 0.009 * scale])
            collars[sign] = (
                band,
                [[i * 4 + j, i * 4 + j + 1, (i + 1) * 4 + j + 1, (i + 1) * 4 + j] for i in range(11) for j in range(3)],
            )
    details = dict(arms=arm_values, neck_top=neck_top, v_bottom=v_bottom, hem=hem, cuff_y=cuff)
    if kind in ("shirt", "coverall"):
        details["belt_center"] = sample_envelope(belt, 0)[:2]
        edge_counts = {}
        for face in faces:
            for a, b in zip(face, face[1:] + face[:1]):
                edge = tuple(sorted((a, b)))
                edge_counts[edge] = edge_counts.get(edge, 0) + 1
        neck_edges = [
            edge
            for edge, count in edge_counts.items()
            if count == 1 and all(index < len(mask_values) and abs(mask_values[index][1]) < 1e-7 for index in edge)
        ]
        adjacency = {}
        for a, b in neck_edges:
            adjacency.setdefault(a, []).append(b)
            adjacency.setdefault(b, []).append(a)
        details["neck_rim_indices"] = sorted(adjacency)
        details["neck_rim"] = []
        if adjacency and all(len(neighbors) == 2 for neighbors in adjacency.values()):
            first = min(adjacency)
            loop = [first]
            previous = None
            current = first
            while True:
                following = next(index for index in sorted(adjacency[current]) if index != previous)
                if following == first:
                    break
                require(following not in loop, "garment_neck_rim_invalid")
                loop.append(following)
                previous, current = current, following
            require(len(loop) == len(adjacency), "garment_neck_rim_multiple_loops")
            details["neck_rim"] = [list(vertices[index]) for index in loop]
        if c["clothing"] == "cross_collar_tunic":
            endpoints = sorted(index for index, neighbors in adjacency.items() if len(neighbors) == 1)
            require(
                len(endpoints) == 2 and all(len(neighbors) in (1, 2) for neighbors in adjacency.values()),
                "period_back_collar_boundary_invalid",
            )
            path = [endpoints[0]]
            previous = None
            while path[-1] != endpoints[1]:
                following = next(index for index in adjacency[path[-1]] if index != previous)
                require(following not in path, "period_back_collar_boundary_invalid")
                previous = path[-1]
                path.append(following)
            require(len(path) == len(adjacency), "period_back_collar_boundary_invalid")
            details["period_neck_path"] = [list(vertices[index]) for index in path]
        if c["clothing"] == "coverall":
            require(len(details["neck_rim"]) >= 4, "garment_neck_rim_missing")
    if kind in ("trousers", "coverall"):
        details["cuff_centers"] = {side: sample_envelope(cuff, side)[:2] for side in (-1, 1)}
        counts = {}
        directed = {}
        for face in faces:
            for a, b in zip(face, face[1:] + face[:1]):
                edge = tuple(sorted((a, b)))
                counts[edge] = counts.get(edge, 0) + 1
                directed[edge] = (a, b)
        following = {
            directed[edge][0]: directed[edge][1]
            for edge, count in counts.items()
            if count == 1 and all(abs(mask_values[index][0 if kind == "coverall" else 1]) < 1e-7 for index in edge)
        }
        loops = {}
        while following:
            first = next(iter(following))
            loop = [first]
            current = following.pop(first)
            while current != first:
                require(current in following and len(loop) <= len(vertices), "garment_cuff_boundary_invalid")
                loop.append(current)
                current = following.pop(current)
            side = 1 if sum(vertices[index][0] for index in loop) > 0 else -1
            require(side not in loops and len(loop) >= 3, "garment_cuff_boundary_ambiguous")
            loops[side] = [vertices[index] for index in loop]
        require(set(loops) == {-1, 1}, "garment_cuff_boundary_missing")
        details["cuff_loops"] = loops
    return vertices, faces, collars, details


def _section_outline(vertices, faces, y, center, scale, samples=64):
    """Measure a garment's pre-thickness horizontal outer surface, never guess it."""
    epsilon = 1e-8 * scale
    segments = []
    for face in faces:
        for i in range(1, len(face) - 1):
            triangle = [vertices[face[0]], vertices[face[i]], vertices[face[i + 1]]]
            if all(abs(point[1] - y) <= epsilon for point in triangle):
                continue
            points = []
            for a, b in zip(triangle, triangle[1:] + triangle[:1]):
                da, db = a[1] - y, b[1] - y
                if abs(da) <= epsilon:
                    points.append((a[0], a[2]))
                if da * db < 0 and abs(da) > epsilon and abs(db) > epsilon:
                    fraction = da / (da - db)
                    points.append((a[0] + (b[0] - a[0]) * fraction, a[2] + (b[2] - a[2]) * fraction))
            unique = []
            for point in points:
                if not any(math.dist(point, other) <= epsilon for other in unique):
                    unique.append(point)
            if len(unique) == 2:
                segments.append(unique)
    require(bool(segments), "garment_section_empty")
    radii = []
    for index in range(samples):
        angle = 2 * math.pi * index / samples
        dx, dz = math.cos(angle), math.sin(angle)
        hits = []
        for a, b in segments:
            vx, vz = b[0] - a[0], b[1] - a[1]
            ax, az = a[0] - center[0], a[1] - center[1]
            denominator = dx * vz - dz * vx
            if abs(denominator) < 1e-12:
                continue
            distance = (ax * vz - az * vx) / denominator
            fraction = (ax * dz - az * dx) / denominator
            if distance > epsilon and -1e-7 <= fraction <= 1 + 1e-7:
                hits.append(distance)
        require(bool(hits), "garment_section_ray_unresolved:" + str(index))
        radii.append(min(hits))
    return radii


def _fitted_strap(vertices, faces, bottom, top, center, scale, clearance=0.010, thickness=0.005):
    lower = _section_outline(vertices, faces, bottom, center, scale)
    upper = _section_outline(vertices, faces, top, center, scale)
    result = []
    n = len(lower)
    for y, radii, extra in (
        (bottom, lower, clearance),
        (bottom, lower, clearance + thickness),
        (top, upper, clearance + thickness),
        (top, upper, clearance),
    ):
        for index, radius in enumerate(radii):
            angle = 2 * math.pi * index / n
            radius += extra * scale
            result.append([center[0] + radius * math.cos(angle), y, center[1] + radius * math.sin(angle)])
    quads = [
        [
            layer * n + index,
            layer * n + (index + 1) % n,
            ((layer + 1) % 4) * n + (index + 1) % n,
            ((layer + 1) % 4) * n + index,
        ]
        for layer in range(4)
        for index in range(n)
    ]
    return result, quads


def _rolled_cuff(loop, center, scale, samples=64):
    lengths = [math.dist(a, b) for a, b in zip(loop, loop[1:] + loop[:1])]
    total = sum(lengths)
    require(total > 0.001 * scale, "garment_cuff_boundary_too_small")
    points = []
    for index in range(samples):
        distance = total * index / samples
        segment = 0
        while segment < len(lengths) - 1 and distance > lengths[segment]:
            distance -= lengths[segment]
            segment += 1
        a, b = loop[segment], loop[(segment + 1) % len(loop)]
        t = distance / max(1e-12, lengths[segment])
        points.append([v + (w - v) * t for v, w in zip(a, b)])
    vertices = []
    for height, radius in ((0.002, 0.006), (0.002, 0.014), (0.028, 0.014), (0.028, 0.006)):
        for point in points:
            dx, dz = point[0] - center[0], point[2] - center[1]
            length = math.hypot(dx, dz)
            require(length > 1e-6 * scale, "garment_cuff_center_invalid")
            vertices.append([
                point[0] + dx / length * radius * scale,
                point[1] + height * scale,
                point[2] + dz / length * radius * scale,
            ])
    faces = [
        [
            layer * samples + i,
            layer * samples + (i + 1) % samples,
            ((layer + 1) % 4) * samples + (i + 1) % samples,
            ((layer + 1) % 4) * samples + i,
        ]
        for layer in range(4)
        for i in range(samples)
    ]
    return vertices, faces


def _wrap_panel(vertices, faces, arms, details, c, inner=False):
    """A separate thickened front layer makes the GI overlap physically visible."""
    scale = c["height"] / 1.8
    hem = details["hem"]
    bottom = details["v_bottom"]
    top = details["neck_top"]
    slope = 0.065 * scale / max(0.05 * scale, top + 0.05 * scale - bottom)
    center_z = details["belt_center"][1]
    records = []
    for point, arm in zip(vertices, arms):
        x, y, z = point
        seam = (
            slope * (y - bottom)
            if y >= bottom
            else -0.065 * scale * min(1, (bottom - y) / max(0.05 * scale, bottom - hem))
        )
        records.append([
            list(point),
            [(top - 0.12 * scale - 0.60 * x - y) if inner else x - seam, z - center_z, 0.15 - arm],
        ])
    clipped = [list(face) for face in faces]
    for mask in range(3):
        cache = {}
        following = []
        for face in clipped:
            output = []
            for a, b in zip(face[-1:] + face[:-1], face):
                va, vb = records[a][1][mask], records[b][1][mask]
                if (va >= 0) != (vb >= 0):
                    edge = tuple(sorted((a, b)))
                    if va == 0:
                        cache[edge] = a
                    elif vb == 0:
                        cache[edge] = b
                    elif edge not in cache:
                        t = va / (va - vb)
                        record = [
                            [v + (w - v) * t for v, w in zip(records[a][channel], records[b][channel])]
                            for channel in range(2)
                        ]
                        record[1][mask] = 0
                        cache[edge] = len(records)
                        records.append(record)
                    output.append(cache[edge])
                if vb >= 0:
                    output.append(b)
            output = list(dict.fromkeys(output))
            if len(output) >= 3:
                following.append(output)
        clipped = following
    used = sorted({index for face in clipped for index in face})
    mapping = {old: new for new, old in enumerate(used)}
    require(bool(used) and bool(clipped), "wrap_panel_empty")
    return [
        [records[index][0][0], records[index][0][1], records[index][0][2] + (-0.007 if inner else 0.006) * scale]
        for index in used
    ], [[mapping[index] for index in face] for face in clipped]


def _compile_character(original):
    c = original["character"]
    canonical = _canonical_body(c)
    scale = c["height"] / 1.8
    hh, headcy, hs = _head_dimensions(c)
    result = json.loads(json.dumps(original))
    result.pop("character", None)
    result["materials"] += [
        dict(name="AnatomySkin", color=c["skin_color"], roughness=0.75),
        dict(name="AnatomyHair", color=c["hair_color"], roughness=0.82),
        dict(
            name="AnatomyHairGray",
            color=[0.45 * value + 0.55 * gray for value, gray in zip(c["hair_color"][:3], (0.30, 0.29, 0.27))]
            + [c["hair_color"][3]],
            roughness=0.88,
        ),
        dict(name="AnatomyCloth", color=c["cloth_color"], roughness=0.8),
        dict(name="AnatomyTrouserCloth", color=c.get("trouser_color") or c["cloth_color"], roughness=0.8),
        dict(name="AnatomyFootwear", color=c.get("footwear_color") or c["accent_color"], roughness=0.7),
        dict(name="AnatomyAccent", color=c["accent_color"], roughness=0.7),
        dict(name="AnatomyEyeWhite", color=[0.8, 0.79, 0.72, 1], roughness=0.32),
        dict(name="AnatomyIris", color=[0.08, 0.07, 0.045, 1], roughness=0.35),
        dict(name="AnatomyPupil", color=[0.005, 0.005, 0.005, 1], roughness=0.25),
    ]
    regions = result["regions"]
    groups = {
        "head": [],
        "handL": [],
        "handR": [],
        "shirt": [],
        "trousers": [],
        "canonical": [],
        "shell": [],
        "closed_garment": [],
        "no_subdivision": [],
        "neckline_pins": {},
        "body_metadata": canonical,
        "period_groom": [],
    }

    def add(
        name,
        kind="ellipsoid",
        pos=None,
        size=None,
        sections=None,
        role="body",
        material="AnatomySkin",
        group=None,
        vertices=None,
        faces=None,
        trusted_skin=False,
        trusted_cloth=False,
        trusted_accessory=False,
    ):
        name = "Anatomy_" + name
        shape = dict(
            kind=kind,
            position=pos or [0, 0, 0],
            rotation_degrees=[0, 0, 0],
            size=size or [1, 1, 1],
            sections=sections or [],
            vertices=vertices or [],
            faces=faces or [],
        )
        region = dict(name=name, role=role, material=material, surface=shape)
        if material == "AnatomySkin" and not trusted_skin:
            return region
        if material in ("AnatomyCloth", "AnatomyTrouserCloth") and not trusted_cloth:
            return region
        if name.startswith("Anatomy_Belt") and not trusted_accessory:
            return region
        regions.append(region)
        if group:
            groups[group].append(name)
        return regions[-1]

    def loft(name, points, radii, **kwargs):
        return add(
            name,
            "loft",
            sections=[
                dict(
                    center=[v * scale for v in point],
                    radius=[v * scale for v in radius] if isinstance(radius, list) else [radius * scale] * 4,
                    roll=0,
                )
                for point, radius in zip(points, radii)
            ],
            **kwargs,
        )

    build = c["build"]
    hips = c["hip_width"]
    shoulders = c["shoulder_width"]
    hipy = 0.96 + (c["limb_length"] - 1) * 0.2
    neckbase = (c["height"] - hh - 0.095 * scale * c["neck_length"]) / scale
    compression = max(0, 1.405 - neckbase)
    torso = [
        [0, 0.87, 0],
        [0, 0.96, -0.005],
        [0, 1.07, 0],
        [0, 1.18 - 0.7 * compression, 0],
        [0, 1.30 - 0.9 * compression, 0],
        [0, neckbase - 0.025, 0],
        [0, neckbase + 0.015, 0],
    ]
    radii = [
        [0.12 * hips, 0.12 * hips, 0.09, 0.11],
        [0.15 * hips, 0.15 * hips, 0.105, 0.13],
        [0.125 * (1 + 0.2 * build)] * 2 + [0.10 * (1 + 0.3 * build), 0.11],
        [0.15 * (1 + 0.15 * build)] * 2 + [0.115 * (1 + 0.2 * build), 0.12],
        [0.195 * shoulders] * 2 + [0.12, 0.125],
        [0.205 * shoulders] * 2 + [0.095, 0.11],
        [0.105, 0.105, 0.074, 0.08],
    ]
    loft("Torso", torso, radii)
    necktop = (c["height"] - hh + 0.055 * scale) / scale
    loft(
        "Neck",
        [
            [0, neckbase - 0.045, -0.018],
            [0, neckbase + 0.015, -0.018],
            [0, neckbase + 0.065, 0.005],
            [0, necktop, 0.010],
        ],
        [
            [0.11, 0.11, 0.065, 0.085],
            [0.065, 0.065, 0.047, 0.067],
            [0.050, 0.050, 0.074, 0.055],
            [0.050, 0.050, 0.074, 0.055],
        ],
    )
    add("Body", "cage", vertices=canonical["vertices"], faces=canonical["faces"], group="canonical", trusted_skin=True)
    for sign, label in [(-1, "L"), (1, "R")]:
        # Eyeballs sit inside the actual canonical eyelid rims, not on a flat face.
        source_side = "R" if sign < 0 else "L"
        ex, ey, ez = canonical["landmarks"]["eye" + source_side]
        eye_scale = max(1, c["face"]["eye_size"]) if c["style"] == "stylized" else 1
        for name, offset, dims, mat in [
            ("Eye", 0, [0.025, 0.025, 0.025], "AnatomyEyeWhite"),
            ("Iris", 0.0115, [0.0105, 0.0105, 0.003], "AnatomyIris"),
            ("Pupil", 0.0130, [0.0045, 0.005, 0.0015], "AnatomyPupil"),
        ]:
            add(
                name + label,
                pos=[ex, ey, ez + offset * hs * eye_scale],
                size=[v * hs * eye_scale for v in dims],
                role="accessory",
                material=mat,
            )
        shoulder = [value / scale for value in canonical["landmarks"]["shoulder" + source_side]]
        shoulderx = abs(shoulder[0])
        shouldery = shoulder[1]
        armfactor = c["limb_length"]
        elbow = [value / scale for value in canonical["landmarks"]["elbow" + source_side]]
        wrist = [value / scale for value in canonical["landmarks"]["wrist" + source_side]]
        loft(
            "Arm" + label,
            [
                [sign * shoulderx, shouldery, 0],
                [sign * (shoulderx + 0.065), shouldery - 0.105, 0],
                elbow,
                [sign * (shoulderx + 0.19), shouldery - 0.39 * armfactor, 0.02],
                wrist,
            ],
            [0.078 * (1 + 0.12 * build), 0.068, 0.048, 0.044, 0.032],
        )
        palm = [wrist[0] + sign * 0.012, wrist[1] - 0.044 * c["hand_scale"], wrist[2] + 0.006]
        handscale = scale * c["hand_scale"]
        add(
            "Wrist" + label,
            pos=[v * scale for v in wrist],
            size=[0.065 * handscale, 0.090 * handscale, 0.061 * handscale],
            group="hand" + label,
        )
        add(
            "Palm" + label,
            pos=[v * scale for v in palm],
            size=[0.078 * handscale, 0.108 * handscale, 0.031 * handscale],
            group="hand" + label,
        )
        for index, length in enumerate([0.073, 0.082, 0.077, 0.060]):
            x = palm[0] + sign * (index - 1.5) * 0.017 * c["hand_scale"]
            y = palm[1] - 0.030 * c["hand_scale"]
            z = palm[2]
            loft(
                "Finger" + label + str(index),
                [
                    [x, y, z],
                    [x, y - length * 0.45 * c["hand_scale"], z + 0.003],
                    [x, y - length * c["hand_scale"], z + 0.008],
                ],
                [0.0070 * c["hand_scale"], 0.0067 * c["hand_scale"], 0.0048 * c["hand_scale"]],
                group="hand" + label,
            )
        loft(
            "Thumb" + label,
            [
                [palm[0] - sign * 0.025, palm[1] + 0.018, palm[2]],
                [palm[0] - sign * 0.050, palm[1] - 0.010, palm[2] + 0.010],
                [palm[0] - sign * 0.060, palm[1] - 0.042, palm[2] + 0.014],
            ],
            [0.012, 0.010, 0.0075],
            group="hand" + label,
        )
        lx = sign * 0.09 * hips
        loft(
            "Leg" + label,
            [
                [lx, hipy, 0.0],
                [sign * 0.10 * hips, 0.77, 0.0],
                [sign * 0.105, 0.53, 0.015],
                [sign * 0.105, 0.33, -0.005],
                [sign * 0.105, 0.105, 0],
            ],
            [0.105 * (1 + 0.1 * build), 0.092, 0.064, 0.063, 0.044],
        )
        # Ankles and the broad metatarsal surface overlap at every allowed scale;
        # a pointed ellipsoid can leave individual toes detached at fine voxels.
        add(
            "Ankle" + label,
            pos=[sign * 0.105 * scale, 0.105 * scale, 0],
            size=[0.085 * scale, 0.13 * scale, 0.105 * scale],
        )
        loft(
            "Foot" + label,
            [
                [sign * 0.105, 0.060, -0.050],
                [sign * 0.105, 0.050, 0],
                [sign * 0.105, 0.035, 0.080],
                [sign * 0.105, 0.030, 0.155],
            ],
            [
                [0.043, 0.043, 0.030, 0.040],
                [0.052, 0.052, 0.025, 0.045],
                [0.056, 0.056, 0.023, 0.033],
                [0.052, 0.052, 0.018, 0.022],
            ],
        )
        # Clothes are connected solids with deliberate overlap; no separated cuffs/waist panels.
        sleeve_fraction = c["sleeve_length"]

        def sleeve_point(t):
            a, b, fraction = (shoulder, elbow, t * 2) if t <= 0.5 else (elbow, wrist, (t - 0.5) * 2)
            return [a[i] + (b[i] - a[i]) * fraction for i in range(3)]

        sleeve_end = sleeve_point(sleeve_fraction)
        loft(
            "Sleeve" + label,
            [
                [sign * (shoulderx - 0.070), shouldery - 0.025, shoulder[2]],
                sleeve_point(sleeve_fraction * 0.45),
                sleeve_end,
            ],
            [0.085, 0.088, 0.083 - 0.025 * sleeve_fraction],
            role="accessory",
            material="AnatomyCloth",
            group="shirt",
        )
        width = c["trouser_width"]
        trouser_x = 0.105 + 0.045 * (width - 1)
        if c["clothing"] in ("tshirt_trousers", "robe_belt"):
            loft(
                "TrouserLeg" + label,
                [
                    [sign * 0.075 * hips, hipy + 0.04, 0.0],
                    [sign * 0.09 * hips, 0.87, 0],
                    [sign * trouser_x * hips, 0.76, 0],
                    [sign * trouser_x, 0.53, 0.015],
                    [sign * trouser_x, 0.30, -0.005],
                    [sign * 0.105, 0.09, 0],
                ],
                [
                    [radius * width] * 2 + [radius * (1 + 0.5 * (width - 1))] * 2
                    for radius in [0.088, 0.098, 0.103, 0.077, 0.074, 0.057]
                ],
                role="accessory",
                material="AnatomyCloth",
                group="trousers",
            )
        foot = [point for point in canonical["vertices"] if point[1] < 0.08 * c["height"] and point[0] * sign > 0]
        require(bool(foot), "canonical_foot_bounds_empty")
        xmin, xmax = min(point[0] for point in foot) / scale, max(point[0] for point in foot) / scale
        zmin, zmax = min(point[2] for point in foot) / scale, max(point[2] for point in foot) / scale
        fx = (xmin + xmax) / 2
        fz = (zmin + zmax) / 2
        fw = xmax - xmin
        fl = zmax - zmin
        strap_z = zmin + 0.62 * fl
        dorsal = [point[1] / scale for point in foot if abs(point[2] / scale - strap_z) < 0.025]
        strap_y = (max(dorsal) if dorsal else 0.055) + 0.005
        if c["footwear"] == "sandals":
            add(
                "SandalSole" + label,
                pos=[fx * scale, 0.010 * scale, fz * scale],
                size=[(fw + 0.012) * scale, 0.020 * scale, (fl + 0.018) * scale],
                role="accessory",
                material="AnatomyFootwear",
            )
            loft(
                "SandalStrap" + label,
                [
                    [xmin - 0.003, strap_y - 0.010, strap_z],
                    [fx, strap_y, strap_z],
                    [xmax + 0.003, strap_y - 0.010, strap_z],
                ],
                [[0.008, 0.008, 0.010, 0.010]] * 3,
                role="accessory",
                material="AnatomyFootwear",
            )
        elif c["footwear"] == "shoes":
            front_height = max(point[1] / scale for point in foot if point[2] / scale >= zmin + 0.55 * fl) + 0.025
            toe_height = max(0.070, front_height - 0.015)
            sections = [
                (zmin - 0.020, 0.060, 0.50 * fw + 0.010, 0.070, 0.090),
                (zmin - 0.012, 0.060, 0.50 * fw + 0.010, 0.070, 0.090),
                (zmin + 0.25 * fl, 0.060, 0.56 * fw + 0.010, 0.070, max(0.09, front_height - 0.06)),
                (
                    zmin + 0.70 * fl,
                    (front_height - 0.01) / 2,
                    0.58 * fw + 0.010,
                    (front_height + 0.01) / 2,
                    (front_height + 0.01) / 2,
                ),
                (
                    zmax + 0.012,
                    (toe_height - 0.01) / 2,
                    0.55 * fw + 0.010,
                    (toe_height + 0.01) / 2,
                    (toe_height + 0.01) / 2,
                ),
                (
                    zmax + 0.025,
                    (toe_height - 0.01) / 2,
                    0.55 * fw + 0.010,
                    (toe_height + 0.01) / 2,
                    (toe_height + 0.01) / 2,
                ),
            ]
            vv = []
            ff = []
            n = 32
            for z, cy, rx, down, up in sections:
                for index in range(n):
                    angle = 2 * math.pi * index / n
                    a, b = math.cos(angle), math.sin(angle)
                    x = math.copysign(abs(a) ** 0.7, a)
                    y = math.copysign(abs(b) ** 0.7, b)
                    vv.append([(fx + rx * x) * scale, (cy + (up if y >= 0 else down) * y) * scale, z * scale])
            for layer in range(len(sections) - 1):
                for index in range(n):
                    ff.append([
                        layer * n + index,
                        layer * n + (index + 1) % n,
                        (layer + 1) * n + (index + 1) % n,
                        (layer + 1) * n + index,
                    ])
            ff.extend([list(reversed(range(n))), list(range((len(sections) - 1) * n, len(sections) * n))])
            add("Shoe" + label, "cage", vertices=vv, faces=ff, role="accessory", material="AnatomyFootwear")
    if c["clothing"] == "tshirt_trousers":
        cloth_radii = [[v + 0.014 for v in radius] for radius in radii]
        hem = c["hem_height"] * 1.8
        upper = [(point, radius) for point, radius in zip(torso, cloth_radii) if point[1] > hem + 0.03]
        loft(
            "Shirt",
            [[0, hem, 0], *[point for point, _ in upper]],
            [cloth_radii[1], *[radius for _, radius in upper]],
            role="accessory",
            material="AnatomyCloth",
            group="shirt",
        )
    else:
        hem = c["hem_height"] * 1.8
        belt = c["belt_height"] * 1.8
        jacket = [
            ([0, hem, 0], [0.23 * hips, 0.23 * hips, 0.16, 0.18]),
            ([0, belt, 0], [0.16 + 0.015 * build, 0.16 + 0.015 * build, 0.13 + 0.008 * build, 0.14 + 0.01 * build]),
            ([0, 1.33, 0], [0.22 * shoulders, 0.22 * shoulders, 0.14, 0.15]),
            ([0, neckbase - 0.025, 0], [0.25 * shoulders, 0.25 * shoulders, 0.135, 0.15]),
            ([0, neckbase + 0.03, 0], [0.095, 0.095, 0.09, 0.10]),
        ]
        jacket.sort(key=lambda item: item[0][1])
        loft(
            "Robe",
            [point for point, _ in jacket],
            [radius for _, radius in jacket],
            role="accessory",
            material="AnatomyCloth",
            group="shirt",
        )
        loft(
            "Belt",
            [[0, belt - 0.025, 0], [0, belt + 0.025, 0]],
            [[0.173 + 0.015 * build, 0.173 + 0.015 * build, 0.148 + 0.008 * build, 0.160 + 0.01 * build]] * 2,
            role="accessory",
            material="AnatomyAccent",
        )
        for sign, label in [(-1, "L"), (1, "R")]:
            middle = (neckbase + belt + 0.10) / 2
            points = [
                [sign * 0.077, neckbase + 0.025, 0.122],
                [sign * 0.055, middle, 0.170],
                [-sign * 0.020, belt + 0.085, 0.184],
                [-sign * 0.075, belt - 0.015, 0.178],
            ]
            vv = []
            ff = []
            for index, point in enumerate(points):
                previous = points[max(0, index - 1)]
                following = points[min(len(points) - 1, index + 1)]
                dx, dy = following[0] - previous[0], following[1] - previous[1]
                length = math.hypot(dx, dy)
                right = (dy / length, -dx / length)
                width = 0.030 * c["lapel_width"]
                for side, depth in [(-1, -0.0025), (1, -0.0025), (1, 0.0025), (-1, 0.0025)]:
                    vv.append([
                        (point[0] + right[0] * width * side) * scale,
                        (point[1] + right[1] * width * side) * scale,
                        (point[2] + depth) * scale,
                    ])
                if index:
                    for j in range(4):
                        ff.append([
                            (index - 1) * 4 + j,
                            (index - 1) * 4 + (j + 1) % 4,
                            index * 4 + (j + 1) % 4,
                            index * 4 + j,
                        ])
            last = 4 * (len(points) - 1)
            ff.extend([[3, 2, 1, 0], [last, last + 1, last + 2, last + 3]])
            add("Lapel" + label, "cage", vertices=vv, faces=ff, role="accessory", material="AnatomyCloth")
        add(
            "BeltKnot",
            pos=[0.035 * scale, belt * scale, (0.158 + 0.008 * build) * scale],
            size=[0.052 * scale, 0.042 * scale, 0.027 * scale],
            role="accessory",
            material="AnatomyAccent",
        )
        for sign, label in [(-1, "L"), (1, "R")]:
            loft(
                "BeltTie" + label,
                [
                    [0.035, belt - 0.012, 0.160 + 0.008 * build],
                    [0.035 + sign * 0.030, belt - 0.090, 0.164 + 0.008 * build],
                    [0.035 + sign * 0.045, belt - 0.165, 0.161 + 0.008 * build],
                ],
                [[0.013, 0.013, 0.003, 0.003]] * 3,
                role="accessory",
                material="AnatomyAccent",
            )
    width = 1 + 0.20 * (c["trouser_width"] - 1)
    loft(
        "TrouserSeat",
        [[0, 0.87, 0], [0, 0.97, -0.005], [0, 1.015, 0]],
        [
            [0.16 * hips * width, 0.16 * hips * width, 0.115, 0.14],
            [0.167 * hips * width, 0.167 * hips * width, 0.12, 0.145],
            [0.15 * hips * width, 0.15 * hips * width, 0.11, 0.13],
        ],
        role="accessory",
        material="AnatomyCloth",
        group="trousers",
    )
    for sign, label in [(-1, "L"), (1, "R")]:
        vv = []
        ff = []
        n = 32
        rx = 0.059 * c["trouser_width"]
        rz = 0.059 * (1 + 0.5 * (c["trouser_width"] - 1))
        for y, thickness in [(0.092, -0.007), (0.092, 0.005), (0.125, 0.005), (0.125, -0.007)]:
            for index in range(n):
                angle = 2 * math.pi * index / n
                vv.append([
                    (sign * 0.105 + (rx + thickness) * math.cos(angle)) * scale,
                    y * scale,
                    (rz + thickness) * math.sin(angle) * scale,
                ])
        for layer in range(4):
            for index in range(n):
                ff.append([
                    layer * n + index,
                    layer * n + (index + 1) % n,
                    ((layer + 1) % 4) * n + (index + 1) % n,
                    ((layer + 1) % 4) * n + index,
                ])
        add("TrouserCuff" + label, "cage", vertices=vv, faces=ff, role="accessory", material="AnatomyCloth")
    for kind in ("coverall",) if c["clothing"] == "coverall" else ("shirt", "trousers"):
        garment_vertices, garment_faces, collars, details = _garment_shell(canonical, c, kind)
        if c["clothing"] == "cross_collar_tunic" and kind == "shirt":
            trouser_control, _, _, _ = _garment_shell(canonical, c, "trousers")
            garment_vertices = enclose_tunic_over_trousers(garment_vertices, trouser_control, c)
        add(
            kind,
            "cage",
            vertices=garment_vertices,
            faces=garment_faces,
            role="accessory",
            material="AnatomyCloth" if kind in ("shirt", "coverall") else "AnatomyTrouserCloth",
            group="shell",
            trusted_cloth=True,
        )
        if details.get("neck_rim_indices"):
            groups["neckline_pins"]["Anatomy_" + kind] = details["neck_rim_indices"]
        for side, (band_vertices, band_faces) in collars.items():
            add(
                "Collar" + ("L" if side < 0 else "R"),
                "cage",
                vertices=band_vertices,
                faces=band_faces,
                role="accessory",
                material="AnatomyCloth",
                group="shell",
                trusted_cloth=True,
            )
        if kind == "shirt" and c["clothing"] == "robe_belt":
            inner_vertices, inner_faces, _, inner_details = _garment_shell(canonical, c, "shirt", inner_layer=True)
            inner_vertices, inner_faces = _wrap_panel(
                inner_vertices, inner_faces, inner_details["arms"], inner_details, c, inner=True
            )
            add(
                "WrapInner",
                "cage",
                vertices=inner_vertices,
                faces=inner_faces,
                role="accessory",
                material="AnatomyCloth",
                group="shell",
                trusted_cloth=True,
            )
            panel_vertices, panel_faces = _wrap_panel(garment_vertices, garment_faces, details["arms"], details, c)
            add(
                "WrapPanel",
                "cage",
                vertices=panel_vertices,
                faces=panel_faces,
                role="accessory",
                material="AnatomyCloth",
                group="shell",
                trusted_cloth=True,
            )
            belt_y = c["belt_height"] * c["height"]
            center = details["belt_center"]
            belt_vertices, belt_faces = _fitted_strap(
                garment_vertices, garment_faces, belt_y - 0.018 * scale, belt_y + 0.018 * scale, center, scale
            )
            add(
                "Belt",
                "cage",
                vertices=belt_vertices,
                faces=belt_faces,
                role="accessory",
                material="AnatomyAccent",
                group="closed_garment",
                trusted_accessory=True,
            )
            front = max(point[2] for point in belt_vertices) / scale
            add(
                "BeltKnot",
                pos=[0.035 * scale, belt_y, (front + 0.010) * scale],
                size=[0.052 * scale, 0.042 * scale, 0.027 * scale],
                role="accessory",
                material="AnatomyAccent",
                group="closed_garment",
                trusted_accessory=True,
            )
            for sign, label in [(-1, "L"), (1, "R")]:
                normalized_y = belt_y / scale
                loft(
                    "BeltTie" + label,
                    [
                        [0.035, normalized_y - 0.012, front + 0.012],
                        [0.035 + sign * 0.030, normalized_y - 0.090, front + 0.016],
                        [0.035 + sign * 0.045, normalized_y - 0.165, front + 0.013],
                    ],
                    [[0.013, 0.013, 0.003, 0.003]] * 3,
                    role="accessory",
                    material="AnatomyAccent",
                    group="closed_garment",
                    trusted_accessory=True,
                )
        for accessory in (
            character_accessories(
                canonical, c, dict(vertices=garment_vertices, faces=garment_faces, kind=kind, details=details)
            )
            if kind == "coverall"
            or kind == "shirt"
            and c["clothing"] == "robe_belt"
            or kind == "trousers"
            and c["clothing"] == "tshirt_trousers"
            else []
        ):
            add(
                accessory["name"],
                "cage",
                vertices=accessory["vertices"],
                faces=accessory["faces"],
                role="accessory",
                material="AnatomyTrouserCloth"
                if kind == "trousers" and accessory["material"] == "AnatomyCloth"
                else accessory["material"],
                group="no_subdivision",
                trusted_cloth=True,
            )
        if c["clothing"] == "cross_collar_tunic" and kind == "shirt":
            for item in cross_collar_accessories(
                canonical, c, dict(vertices=garment_vertices, faces=garment_faces, details=details)
            ):
                add(
                    item["name"],
                    "cage",
                    vertices=item["vertices"],
                    faces=item["faces"],
                    role="accessory",
                    material=item["material"],
                    group="no_subdivision",
                    trusted_cloth=True,
                    trusted_accessory=True,
                )
            belt_y = c["belt_height"] * c["height"]
            belt_vertices, belt_faces = _fitted_strap(
                garment_vertices,
                garment_faces,
                belt_y - 0.017 * scale,
                belt_y + 0.017 * scale,
                details["belt_center"],
                scale,
                clearance=0.009,
                thickness=0.003,
            )
            # The fixed section sampler walks clockwise from +X; reverse the
            # resulting new belt shell once so its source winding is outward.
            belt_faces = [list(reversed(face)) for face in belt_faces]
            add(
                "CrossCollarBelt",
                "cage",
                vertices=belt_vertices,
                faces=belt_faces,
                role="accessory",
                material="AnatomyAccent",
                group="no_subdivision",
                trusted_accessory=True,
            )
        if kind == "coverall":
            belt_y = c["belt_height"] * c["height"]
            vv, ff = _fitted_strap(
                garment_vertices,
                garment_faces,
                belt_y - 0.012 * scale,
                belt_y + 0.012 * scale,
                details["belt_center"],
                scale,
                clearance=0.007,
                thickness=0.003,
            )
            add(
                "CoverallWaist",
                "cage",
                vertices=vv,
                faces=ff,
                role="accessory",
                material="AnatomyCloth",
                group="closed_garment",
                trusted_cloth=True,
            )
        if kind in ("trousers", "coverall"):
            for side, label in [(-1, "L"), (1, "R")]:
                cuff_vertices, cuff_faces = _rolled_cuff(
                    details["cuff_loops"][side], details["cuff_centers"][side], scale
                )
                add(
                    "RolledCuff" + label,
                    "cage",
                    vertices=cuff_vertices,
                    faces=cuff_faces,
                    role="accessory",
                    material="AnatomyTrouserCloth",
                    group="closed_garment",
                    trusted_cloth=True,
                )
    for eyebrow in eyebrow_accessories(canonical, c):
        add(
            eyebrow["name"],
            "cage",
            vertices=eyebrow["vertices"],
            faces=eyebrow["faces"],
            role="accessory",
            material="AnatomyHair",
            group="no_subdivision",
        )
    for spec in build_period_groom(canonical, c):
        measure = measure_groom_spec(spec)
        groups["period_groom"].append(dict(name="Anatomy_" + spec["name"], material=spec["material"], **measure))
        add(
            spec["name"],
            "cage",
            vertices=spec["vertices"],
            faces=spec["faces"],
            role="accessory",
            material=spec["material"],
            group="no_subdivision",
        )
    if resolve_period_groom(c) is None and c["hair"] in ("short", "short_wavy"):
        hair_vertices, hair_faces, _, _ = _garment_shell(canonical, c, "hair")
        add(
            "Hair",
            "cage",
            vertices=hair_vertices,
            faces=hair_faces,
            role="accessory",
            material="AnatomyHair",
            group="shell",
        )
    return result, groups


def _monotone_span(values, index, t):
    """A positive radius stays inside its adjacent controls with smooth slopes."""
    a, b = values[index : index + 2]
    delta = b - a
    previous = a - values[index - 1] if index else delta
    following = values[index + 2] - b if index + 2 < len(values) else delta
    before = 2 * previous * delta / (previous + delta) if previous * delta > 0 else 0
    after = 2 * delta * following / (delta + following) if delta * following > 0 else 0
    return (
        (2 * t**3 - 3 * t**2 + 1) * a
        + (t**3 - 2 * t**2 + t) * before
        + (-2 * t**3 + 3 * t**2) * b
        + (t**3 - t**2) * after
    )


def _loft_sections(controls):
    """Interpolate the bounded cross-section controls, never replace or drop them.

    Catmull-Rom centerlines pass through every supplied center. Radii and roll
    use monotone Hermite interpolation so a positive radius cannot overshoot.
    The fixed eight samples per span and 32 radial samples bound generated data.
    """
    result = []
    for index in range(len(controls) - 1):
        p0 = controls[max(0, index - 1)]["center"]
        p1 = controls[index]["center"]
        p2 = controls[index + 1]["center"]
        p3 = controls[min(len(controls) - 1, index + 2)]["center"]
        for step in range(LOFT_STEPS):
            t = step / LOFT_STEPS
            center = [
                0.5
                * (
                    (2 * a)
                    + (-previous + b) * t
                    + (2 * previous - 5 * a + 4 * b - following) * t * t
                    + (-previous + 3 * a - 3 * b + following) * t * t * t
                )
                for previous, a, b, following in zip(p0, p1, p2, p3)
            ]
            result.append(
                dict(
                    center=center,
                    radius=[
                        _monotone_span([control["radius"][channel] for control in controls], index, t)
                        for channel in range(4)
                    ],
                    roll=controls[index]["roll"] + (controls[index + 1]["roll"] - controls[index]["roll"]) * t,
                )
            )
    result.append(controls[-1])
    return result


def _loft(surface, Vector, Quaternion):
    frames = transported_frames(_loft_sections(surface["sections"]))
    vertices, faces = [], []
    for index, frame in enumerate(frames):
        left_radius, right_radius, front_radius, back_radius = frame["radius"]
        for segment in range(RADIAL):
            angle = 2 * math.pi * segment / RADIAL
            x, z = math.cos(angle), math.sin(angle)
            vertices.append(
                tuple(
                    frame["center"][i]
                    + frame["right"][i] * x * (right_radius if x >= 0 else left_radius)
                    + frame["front"][i] * z * (front_radius if z >= 0 else back_radius)
                    for i in range(3)
                )
            )
        if index:
            for segment in range(RADIAL):
                a = (index - 1) * RADIAL + segment
                b = (index - 1) * RADIAL + (segment + 1) % RADIAL
                faces.append((a, a + RADIAL, b + RADIAL, b))
    caps = surface.get("end_caps")
    for end, frame, ring, direction in (
        ("start", frames[0], list(range(RADIAL)), -1),
        ("end", frames[-1], list(range((len(frames) - 1) * RADIAL, len(frames) * RADIAL)), 1),
    ):
        if caps is None or caps[end] == "flat":
            faces.append(tuple(ring if direction < 0 else reversed(ring)))
            continue
        depth = max(frame["radius"]) * caps["depth"]
        previous = ring
        for layer in range(1, 5):
            latitude = (math.pi / 2) * layer / 5
            radial = math.cos(latitude)
            axial = math.sin(latitude) * depth * direction
            following = []
            for segment in range(RADIAL):
                original = vertices[ring[segment]]
                following.append(len(vertices))
                vertices.append(
                    tuple(
                        frame["center"][i] + (original[i] - frame["center"][i]) * radial + frame["tangent"][i] * axial
                        for i in range(3)
                    )
                )
            for a, b, na, nb in zip(previous, previous[1:] + previous[:1], following, following[1:] + following[:1]):
                face = (a, b, nb, na)
                faces.append(face if direction < 0 else tuple(reversed(face)))
            previous = following
        pole = len(vertices)
        vertices.append(tuple(frame["center"][i] + frame["tangent"][i] * depth * direction for i in range(3)))
        for a, b in zip(previous, previous[1:] + previous[:1]):
            faces.append((a, b, pole) if direction < 0 else (b, a, pole))
    return vertices, faces


def _surface_mesh(surface, bpy, bmesh, Vector, Euler, Quaternion, primitive_segments=(32, 24)):
    kind = surface["kind"]
    if kind == "loft":
        vertices, faces = _loft(surface, Vector, Quaternion)
    elif kind == "cage":
        vertices, faces = surface["vertices"], surface["faces"]
    else:
        bm = bmesh.new()
        if kind == "box":
            bmesh.ops.create_cube(bm, size=1.0)
        elif kind in ("ellipsoid", "capsule"):
            bmesh.ops.create_uvsphere(
                bm,
                u_segments=primitive_segments[0],
                v_segments=primitive_segments[1],
                radius=0.25 if kind == "capsule" else 0.5,
            )
            for vertex in bm.verts:
                x, y, z = vertex.co
                vertex.co = (x, z + (0.25 if z >= 0 else -0.25) if kind == "capsule" else z, y)
        else:
            bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=20, radius1=0.5, radius2=0.5, depth=1.0)
            for vertex in bm.verts:
                x, y, z = vertex.co
                vertex.co = (x, z, y)
        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        vertices = [tuple(v.co) for v in bm.verts]
        faces = [tuple(v.index for v in face.verts) for face in bm.faces]
        bm.free()
    rotation = Euler(tuple(math.radians(value) for value in surface["rotation_degrees"]), "YXZ").to_matrix()
    position, scale = Vector(surface["position"]), Vector(surface["size"])
    transformed = []
    for point in vertices:
        point = rotation @ Vector(tuple(point[i] * scale[i] for i in range(3))) + position
        require(all(math.isfinite(v) and abs(v) <= 1000 for v in point), "geometry_bounds_invalid")
        transformed.append((point.x, -point.z, point.y))
    mesh = bpy.data.meshes.new("SculptRegion")
    mesh.from_pydata(transformed, [], faces)
    mesh.update()
    return mesh


def _quality(obj, bmesh, repair_normals=True):
    mesh = obj.data
    require(len(mesh.vertices) > 3 and len(mesh.polygons) > 3, "geometry_empty")
    for vertex in mesh.vertices:
        require(all(math.isfinite(v) and abs(v) <= 1000 for v in vertex.co), "geometry_nonfinite")
    bm = bmesh.new()
    bm.from_mesh(mesh)
    if repair_normals:
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        if bm.calc_volume(signed=True) < 0:
            bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
        bm.to_mesh(mesh)
        mesh.update()
    components = 0
    unseen = set(bm.verts)
    while unseen:
        components += 1
        stack = [unseen.pop()]
        while stack:
            vertex = stack.pop()
            for edge in vertex.link_edges:
                neighbor = edge.other_vert(vertex)
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    stack.append(neighbor)
    manifold = all(edge.is_manifold and len(edge.link_faces) == 2 for edge in bm.edges) and all(
        vertex.is_manifold for vertex in bm.verts
    )
    isolated = any(not vertex.link_faces for vertex in bm.verts)
    volume = bm.calc_volume(signed=True)
    bm.free()
    mesh.calc_loop_triangles()
    degenerate = sum(triangle.area <= 1e-12 for triangle in mesh.loop_triangles)
    bounds_min = [min(vertex.co[index] for vertex in mesh.vertices) for index in range(3)]
    bounds_max = [max(vertex.co[index] for vertex in mesh.vertices) for index in range(3)]
    return dict(
        name=obj.name,
        vertices=len(mesh.vertices),
        triangles=len(mesh.loop_triangles),
        components=components,
        manifold=manifold and not isolated,
        volume=volume,
        degenerate_triangles=degenerate,
        bounds_min=[bounds_min[0], bounds_min[2], -bounds_max[1]],
        bounds_max=[bounds_max[0], bounds_max[2], -bounds_min[1]],
    )


def _selected(obj, bpy):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _triangulate_surface(bm):
    """Constrain diagonals against existing surface edges after exact unions.

    General boolean n-gons can share nonconsecutive vertices with a neighbor.
    An unconstrained tessellator may reuse that neighbor's edge, creating four
    incident triangles. Ear clipping chooses an interior alternative instead.
    No vertices, surface components or faces are dropped.
    """
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    bm.normal_update()
    reserved = {tuple(sorted(v.index for v in edge.verts)) for edge in bm.edges}
    triangles = []
    materials = []
    for face in bm.faces:
        ring = [v.index for v in face.verts]
        boundary = {tuple(sorted((a, b))) for a, b in zip(ring, ring[1:] + ring[:1])}
        axis = max(range(3), key=lambda i: abs(face.normal[i]))
        axes = [i for i in range(3) if i != axis]
        points = {index: (bm.verts[index].co[axes[0]], bm.verts[index].co[axes[1]]) for index in ring}
        signed = sum(
            points[a][0] * points[b][1] - points[b][0] * points[a][1] for a, b in zip(ring, ring[1:] + ring[:1])
        )
        direction = 1 if signed >= 0 else -1

        def cross(a, b, c):
            pa, pb, pc = points[a], points[b], points[c]
            return direction * ((pb[0] - pa[0]) * (pc[1] - pa[1]) - (pb[1] - pa[1]) * (pc[0] - pa[0]))

        emitted = []
        while len(ring) > 3:
            ears = []
            for i, b in enumerate(ring):
                a, c = ring[i - 1], ring[(i + 1) % len(ring)]
                diagonal = tuple(sorted((a, c)))
                area = cross(a, b, c)
                if area <= 1e-18 or (diagonal in reserved and diagonal not in boundary):
                    continue
                if any(
                    index not in (a, b, c) and min(cross(a, b, index), cross(b, c, index), cross(c, a, index)) >= -1e-18
                    for index in ring
                ):
                    continue
                score = area
                if len(ring) == 4:
                    remaining = ring[:i] + ring[i + 1 :]
                    score = min(area, cross(*remaining))
                ears.append((score, i, (a, b, c)))
            if not ears:
                # Some valid boolean/subdivision quads have BOTH diagonals
                # already used by neighboring surface cells. Add one interior
                # Steiner vertex instead of duplicating an edge or dropping a face.
                span = max(
                    max(points[index][axis] for index in ring) - min(points[index][axis] for index in ring)
                    for axis in (0, 1)
                )
                lo = [min(points[index][axis] for index in ring) - span for axis in (0, 1)]
                hi = [max(points[index][axis] for index in ring) + span for axis in (0, 1)]
                kernel = [(lo[0], lo[1]), (hi[0], lo[1]), (hi[0], hi[1]), (lo[0], hi[1])]
                for a, b in zip(ring, ring[1:] + ring[:1]):
                    pa, pb = points[a], points[b]

                    def halfplane(point):
                        return direction * ((pb[0] - pa[0]) * (point[1] - pa[1]) - (pb[1] - pa[1]) * (point[0] - pa[0]))

                    clipped = []
                    for previous, current in zip(kernel[-1:] + kernel[:-1], kernel):
                        old, new = halfplane(previous), halfplane(current)
                        if (old >= 0) != (new >= 0):
                            fraction = old / (old - new)
                            clipped.append(tuple(previous[i] + fraction * (current[i] - previous[i]) for i in (0, 1)))
                        if new >= 0:
                            clipped.append(current)
                    kernel = clipped
                    if not kernel:
                        break
                require(len(kernel) >= 3, "surface_triangulation_constrained_failed")
                center = tuple(sum(point[axis] for point in kernel) / len(kernel) for axis in (0, 1))
                coordinate = None
                for i in range(1, len(ring) - 1):
                    a, b, c = ring[0], ring[i], ring[i + 1]
                    pa, pb, pc = points[a], points[b], points[c]
                    denominator = (pb[1] - pc[1]) * (pa[0] - pc[0]) + (pc[0] - pb[0]) * (pa[1] - pc[1])
                    if abs(denominator) <= 1e-24:
                        continue
                    wa = ((pb[1] - pc[1]) * (center[0] - pc[0]) + (pc[0] - pb[0]) * (center[1] - pc[1])) / denominator
                    wb = ((pc[1] - pa[1]) * (center[0] - pc[0]) + (pa[0] - pc[0]) * (center[1] - pc[1])) / denominator
                    wc = 1 - wa - wb
                    if min(wa, wb, wc) >= -1e-8:
                        coordinate = bm.verts[a].co * wa + bm.verts[b].co * wb + bm.verts[c].co * wc
                        break
                require(coordinate is not None, "surface_triangulation_kernel_invalid")
                vertex = bm.verts.new(coordinate)
                vertex.index = len(bm.verts) - 1
                bm.verts.ensure_lookup_table()
                emitted.extend((a, b, vertex.index) for a, b in zip(ring, ring[1:] + ring[:1]))
                ring = []
                break
            _, index, triangle = max(ears)
            emitted.append(triangle)
            ring.pop(index)
        if ring:
            emitted.append(tuple(ring))
        for triangle in emitted:
            triangles.append(triangle)
            materials.append(face.material_index)
            reserved.update(tuple(sorted((a, b))) for a, b in zip(triangle, triangle[1:] + triangle[:1]))
    return triangles, materials


def _apply(obj, modifier, bpy):
    _selected(obj, bpy)
    require("FINISHED" in bpy.ops.object.modifier_apply(modifier=modifier.name), "modifier_failed")


def _join_meshes(objects, bpy, name):
    require(bool(objects), "operator_group_empty")
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    if len(objects) > 1:
        bpy.ops.object.join()
    result = bpy.context.view_layer.objects.active
    result.name = name
    return result


def _exact_union(objects, bpy, bmesh, name, require_connected=True):
    require(bool(objects), "operator_group_empty")
    result = objects[0]
    result.name = name
    for operand in objects[1:]:
        operand_name = operand.name
        modifier = result.modifiers.new("FixedAnatomyUnion", "BOOLEAN")
        modifier.operation = "UNION"
        modifier.solver = "EXACT"
        modifier.object = operand
        _apply(result, modifier, bpy)
        bpy.data.objects.remove(operand, do_unlink=True)
        quality = _quality(result, bmesh)
        require(
            quality["manifold"] and quality["volume"] > 1e-12,
            "anatomy_union_invalid:" + operand_name + ":" + json.dumps(quality, sort_keys=True),
        )
    quality = _quality(result, bmesh)
    require(
        (not require_connected or quality["components"] == 1) and quality["manifold"] and quality["volume"] > 1e-12,
        "anatomy_union_disconnected",
    )
    return result


def _voxel_fusion(objects, bpy, bmesh, name, voxel, smoothing):
    points = [v.co for obj in objects for v in obj.data.vertices]
    dimensions = [max(v[i] for v in points) - min(v[i] for v in points) for i in range(3)]
    require(math.prod(math.ceil(value / voxel) + 3 for value in dimensions) <= MAX_VOXELS, "voxel_budget_exceeded")
    result = _join_meshes(objects, bpy, name)
    modifier = result.modifiers.new("FixedLocalAnatomyFusion", "REMESH")
    modifier.mode = "VOXEL"
    modifier.voxel_size = voxel
    modifier.adaptivity = 0
    modifier.use_remove_disconnected = False
    _apply(result, modifier, bpy)
    if smoothing:
        modifier = result.modifiers.new("FixedLocalAnatomySmooth", "SMOOTH")
        modifier.factor = 0.45
        modifier.iterations = smoothing
        _apply(result, modifier, bpy)
    quality = _quality(result, bmesh)
    require(quality["components"] == 1 and quality["manifold"] and quality["volume"] > 1e-12, "anatomy_detail_invalid")
    return result


def _cloth_drape(obj, character, kind):
    """Small fixed folds on the connected garment, with bounded displacement.

    These are geometry details of a procedural garment, not simulated fabric or
    an assertion that unobserved folds were recovered from a reference image.
    """
    scale = character["height"] / 1.8
    hh, _, _ = _head_dimensions(character)
    neckbase = (character["height"] - hh - 0.095 * scale * character["neck_length"]) / scale
    for vertex in obj.data.vertices:
        x, y, z = vertex.co.x / scale, vertex.co.z / scale, -vertex.co.y / scale
        sign = -1 if x < 0 else 1
        dx, dy, dz = x, 0, z
        if kind == "trousers":
            dx = x - sign * (0.105 + 0.045 * (character["trouser_width"] - 1))
            angle = math.atan2(dz, dx)
            folds = (
                0.0018
                * character["trouser_width"]
                * math.sin(angle * 5 + 0.5 * math.sin(y * 3))
                * math.exp(-0.5 * ((y - 0.77) / 0.17) ** 2)
            )
            knee = 0.515 + 0.012 * math.cos(angle)
            folds += (
                0.0024
                * (
                    math.exp(-0.5 * ((y - knee) / 0.014) ** 2)
                    - 0.65 * math.exp(-0.5 * ((y - knee - 0.024) / 0.018) ** 2)
                )
                * (0.3 + 0.7 * abs(math.sin(angle)))
            )
            for crease in (0.155, 0.215):
                center = crease + 0.008 * math.sin(angle * 2 + sign * 0.7)
                folds += 0.0018 * (
                    math.exp(-0.5 * ((y - center) / 0.012) ** 2)
                    - 0.6 * math.exp(-0.5 * ((y - center - 0.018) / 0.016) ** 2)
                )
            envelope = max(0, min(1, (y - 0.09) / 0.05)) * max(0, min(1, (0.94 - y) / 0.12))
        else:
            shoulderx = 0.195 * character["shoulder_width"]
            shouldery = neckbase - 0.045
            if abs(x) > shoulderx + 0.035:
                ax, ay, az = sign * 0.235, -0.505 * character["limb_length"], 0.025
                projection = max(
                    0,
                    min(
                        character["sleeve_length"],
                        ((x - sign * shoulderx) * ax + (y - shouldery) * ay + z * az) / (ax * ax + ay * ay + az * az),
                    ),
                )
                dx = x - sign * shoulderx - ax * projection
                dy = y - shouldery - ay * projection
                dz = z - az * projection
                angle = math.atan2(dz, dx)
                elbow = 0.51 + 0.025 * math.sin(angle)
                folds = 0.0026 * (
                    math.exp(-0.5 * ((projection - elbow) / 0.025) ** 2)
                    - 0.65 * math.exp(-0.5 * ((projection - elbow - 0.045) / 0.035) ** 2)
                )
                folds *= math.sin(math.pi * projection / max(0.01, character["sleeve_length"])) ** 2
                envelope = 1
            else:
                angle = math.atan2(dz, dx)
                belt = character["belt_height"] * 1.8
                folds = 0.0015 * math.sin(angle * 6 + y * 3)
                folds += 0.0015 * math.sin(angle * 5 + 0.5 * y) * math.exp(-0.5 * ((y - belt - 0.07) / 0.10) ** 2)
                hem = character["hem_height"] * 1.8
                envelope = max(0, min(1, (y - hem) / 0.05)) * max(0, min(1, (neckbase - 0.10 - y) / 0.15))
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        if length > 1e-8:
            distance = folds * envelope * scale / length
            vertex.co.x += dx * distance
            vertex.co.z += dy * distance
            vertex.co.y -= dz * distance
    obj.data.update()


def _cut_wrap_neck(garment, character, bpy, bmesh, Vector, Euler, Quaternion):
    scale = character["height"] / 1.8
    hh, _, _ = _head_dimensions(character)
    neckbase = (character["height"] - hh - 0.095 * scale * character["neck_length"]) / scale
    belt = character["belt_height"] * 1.8
    surfaces = [
        dict(
            kind="cylinder",
            position=[0, (neckbase - 0.07 + 1.95) / 2 * scale, 0.005 * scale],
            rotation_degrees=[0, 0, 0],
            size=[0.15 * scale, (1.95 - neckbase + 0.07) * scale, 0.19 * scale],
            sections=[],
            vertices=[],
            faces=[],
        )
    ]
    triangle = [(-0.11, neckbase + 0.13), (0.11, neckbase + 0.13), (0, belt + 0.10)]
    vertices = [[x * scale, y * scale, z * scale] for z in (0.025, 0.40) for x, y in triangle]
    surfaces.append(
        dict(
            kind="cage",
            position=[0, 0, 0],
            rotation_degrees=[0, 0, 0],
            size=[1, 1, 1],
            sections=[],
            vertices=vertices,
            faces=[[0, 2, 1], [3, 4, 5], [0, 1, 4, 3], [1, 2, 5, 4], [2, 0, 3, 5]],
        )
    )
    for surface in surfaces:
        mesh = _surface_mesh(surface, bpy, bmesh, Vector, Euler, Quaternion)
        operand = bpy.data.objects.new("FixedNeckOpeningCutter", mesh)
        bpy.context.collection.objects.link(operand)
        _quality(operand, bmesh)
        modifier = garment.modifiers.new("FixedWrapNeckOpening", "BOOLEAN")
        modifier.operation = "DIFFERENCE"
        modifier.solver = "EXACT"
        modifier.object = operand
        _apply(garment, modifier, bpy)
        bpy.data.objects.remove(operand, do_unlink=True)
    quality = _quality(garment, bmesh)
    require(
        quality["components"] == 1 and quality["manifold"] and quality["volume"] > 0, "garment_neck_opening_invalid"
    )


def _blend_back_neck(obj, character):
    scale = character["height"] / 1.8
    hh, _, _ = _head_dimensions(character)
    center = character["height"] - hh - 0.012 * scale
    weights = {}
    for vertex in obj.data.vertices:
        x, y, z = vertex.co.x, vertex.co.z, -vertex.co.y
        if abs(x) > 0.10 * scale or abs(y - center) > 0.11 * scale or z > 0.055 * scale:
            continue
        weight = (
            math.exp(-0.5 * ((y - center) / (0.047 * scale)) ** 2)
            * math.exp(-0.5 * (x / (0.080 * scale)) ** 4)
            * max(0, min(1, (0.055 * scale - z) / (0.04 * scale)))
        )
        if weight > 0.01:
            weights[vertex.index] = weight
    neighbors = {index: set() for index in weights}
    for edge in obj.data.edges:
        a, b = edge.vertices
        if a in neighbors:
            neighbors[a].add(b)
        if b in neighbors:
            neighbors[b].add(a)
    for _ in range(5):
        updates = {}
        for index, indices in neighbors.items():
            if not indices:
                continue
            current = obj.data.vertices[index].co
            average = sum((obj.data.vertices[neighbor].co for neighbor in indices), current * 0) / len(indices)
            delta = (average - current) * (0.45 * weights[index])
            if delta.length > 0.003 * scale:
                delta *= 0.003 * scale / delta.length
            updates[index] = current + delta
        for index, coordinate in updates.items():
            obj.data.vertices[index].co = coordinate
    obj.data.update()


def _fill_certified_internal_voxel_shells(obj, voxel, bmesh, Vector, BVHTree):
    """Fill only tiny negative-volume VDB cavities of the trusted solid human.

    External or positive components fail. Every cavity vertex and its centroid
    must lie strictly inside the oriented positive skin in three ray directions.
    The outer skin is never edited. This is deliberately not a size filter or a
    generic-plan repair, and each numerical fill is recorded in the receipt.
    """
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    unseen = set(bm.verts)
    components = []
    while unseen:
        vertices = {unseen.pop()}
        stack = list(vertices)
        while stack:
            vertex = stack.pop()
            for edge in vertex.link_edges:
                neighbor = edge.other_vert(vertex)
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    vertices.add(neighbor)
                    stack.append(neighbor)
        faces = {face for vertex in vertices for face in vertex.link_faces}
        center = sum((vertex.co for vertex in vertices), Vector()) / len(vertices)
        volume = 0.0
        for face in faces:
            points = [vertex.co - center for vertex in face.verts]
            for i in range(1, len(points) - 1):
                volume += points[0].dot(points[i].cross(points[i + 1])) / 6
        components.append(dict(vertices=vertices, faces=faces, center=center, volume=volume))
    if len(components) == 1:
        bm.free()
        return []
    positive = [component for component in components if component["volume"] > 0]
    require(len(positive) == 1, "body_disconnected:not_single_positive_skin")
    skin = positive[0]
    require(all(vertex.is_manifold for vertex in skin["vertices"]), "body_not_closed_manifold")
    coordinates = [tuple(vertex.co) for vertex in bm.verts]
    tree = BVHTree.FromPolygons(coordinates, [[vertex.index for vertex in face.verts] for face in skin["faces"]])
    directions = [
        Vector(direction).normalized() for direction in ((1, 0.371, 0.529), (0.433, 1, 0.217), (0.193, 0.619, 1))
    ]
    epsilon = max(1e-8, voxel * 0.0001)

    def inside(point, direction):
        origin = point.copy()
        crossings = 0
        for _ in range(512):
            location, _, _, _ = tree.ray_cast(origin, direction, 4000)
            if location is None:
                return crossings % 2 == 1
            crossings += 1
            origin = location + direction * epsilon
        return False

    fills = []
    to_fill = []
    for component in components:
        if component is skin:
            continue
        vertices = component["vertices"]
        volume = component["volume"]
        bounds = [
            (min(vertex.co[i] for vertex in vertices), max(vertex.co[i] for vertex in vertices)) for i in range(3)
        ]
        require(
            volume < 0
            and abs(volume) <= voxel**3 * 0.25
            and len(vertices) <= 64
            and all(high - low <= 2 * voxel for low, high in bounds),
            "body_disconnected:uncertified_component",
        )
        points = [vertex.co.copy() for vertex in vertices] + [component["center"]]
        distances = [tree.find_nearest(point)[3] for point in points]
        require(
            all(distance is not None and distance > epsilon for distance in distances)
            and all(inside(point, direction) for point in points for direction in directions),
            "body_disconnected:external_or_ambiguous_component",
        )
        fills.append(
            dict(
                kind="certified_internal_negative_voxel_cavity",
                scope="trusted_character_solid_union_only",
                signed_volume=volume,
                volume_limit=voxel**3 * 0.25,
                extent_limit=2 * voxel,
                vertices=len(vertices),
                faces=len(component["faces"]),
                centroid_blender=list(component["center"]),
                bounds_blender=bounds,
                containment_directions=3,
                contained_points=len(points),
                containment_passes=len(points) * 3,
                minimum_skin_distance=min(distances),
                component_count_before=len(components),
                component_count_after=1,
                outer_skin_vertices=len(skin["vertices"]),
                outer_skin_modified=False,
            )
        )
        to_fill.extend(vertices)
    bmesh.ops.delete(bm, geom=to_fill, context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return fills


def _renders(objects, output_dir, bpy, Vector):
    points = [vertex.co for obj in objects for vertex in obj.data.vertices]
    minimum = Vector(tuple(min(v[i] for v in points) for i in range(3)))
    maximum = Vector(tuple(max(v[i] for v in points) for i in range(3)))
    center = (minimum + maximum) / 2
    extent = max(maximum - minimum)
    require(extent > 0, "render_bounds_invalid")
    camera_data = bpy.data.cameras.new("SculptPreviewCamera")
    camera = bpy.data.objects.new("SculptPreviewCamera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = extent * 1.3
    scene = bpy.context.scene
    scene.camera = camera
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.background_type = "WORLD"
    scene.world.color = (0.15, 0.15, 0.15)
    paths = []
    for name, direction in [
        ("front", (0, -1, 0)),
        ("back", (0, 1, 0)),
        ("left", (-1, 0, 0)),
        ("right", (1, 0, 0)),
        ("threequarter", (1, -1, 0.45)),
    ]:
        camera.location = center + Vector(direction).normalized() * extent * 3
        camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
        destination = output_dir / ("preview_" + name + ".png")
        require(not destination.exists(), "render_output_exists")
        scene.render.filepath = str(destination)
        bpy.ops.render.render(write_still=True)
        paths.append(destination.name)
    return paths


def build(plan, output_path, renders=False):
    plan = validate_plan(plan)
    original_plan = json.loads(json.dumps(plan))
    character = plan.get("character")
    anatomy_groups = {}
    if character is not None:
        plan, anatomy_groups = _compile_character(plan)
    generated_patterns, pattern_measurements = expand_patterns(plan, _loft_sections, MAX_TRIANGLES, MAX_VERTICES)
    plan["regions"].extend(generated_patterns)
    plan.pop("repeat_patterns", None)
    output = Path(output_path).resolve()
    require(output.suffix.lower() == ".glb" and output.parent.is_dir(), "output_path_invalid")
    require(not output.exists() and not output.with_name(output.name + ".receipt.json").exists(), "output_exists")
    if renders:
        require(
            not any(
                (output.parent / ("preview_" + view + ".png")).exists()
                for view in ("front", "back", "left", "right", "threequarter")
            ),
            "render_output_exists",
        )
    import bmesh
    import bpy
    from mathutils import Euler, Quaternion, Vector
    from mathutils.bvhtree import BVHTree

    # Factory startup and disable-autoexec are still required by the host. This
    # interpreter only creates data and never opens a model-supplied blend file.
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    materials = {}
    for definition in plan["materials"]:
        material = bpy.data.materials.new(definition["name"])
        material.diffuse_color = definition["color"]
        material.use_nodes = True
        shader = material.node_tree.nodes.get("Principled BSDF")
        shader.inputs["Base Color"].default_value = definition["color"]
        shader.inputs["Roughness"].default_value = definition["roughness"]
        materials[definition["name"]] = material
    body, accessories = [], []
    region_objects = {}
    pre_smoothed_lofts = []
    raw_loft_triangle_estimate = sum(
        8 * ((len(r["surface"]["sections"]) - 1) * LOFT_STEPS * RADIAL + 2 * RADIAL + 8 * RADIAL)
        for r in plan["regions"]
        if character is None and r["role"] == "body" and r["surface"]["kind"] == "loft"
    )
    require(raw_loft_triangle_estimate <= MAX_TRIANGLES, "source_loft_approximation_budget_exceeded")
    for region in plan["regions"]:
        small_factory_detail = character is not None and region["name"].startswith((
            "Anatomy_Eye",
            "Anatomy_Iris",
            "Anatomy_Pupil",
            "Anatomy_BeltKnot",
        ))
        mesh = _surface_mesh(
            region["surface"], bpy, bmesh, Vector, Euler, Quaternion, (24, 16) if small_factory_detail else (32, 24)
        )
        obj = bpy.data.objects.new(region["name"], mesh)
        region_objects[region["name"]] = obj
        bpy.context.collection.objects.link(obj)
        obj.data.materials.append(materials[region["material"]])
        if character is None and region["role"] == "body" and region["surface"]["kind"] == "loft":
            modifier = obj.modifiers.new("FixedContinuousLoftApproximation", "SUBSURF")
            modifier.subdivision_type = "CATMULL_CLARK"
            modifier.levels = 1
            modifier.render_levels = 1
            _apply(obj, modifier, bpy)
            pre_smoothed_lofts.append(region["name"])
        if obj.name in anatomy_groups.get("shell", []):
            if not obj.name.startswith(("Anatomy_Collar", "Anatomy_Wrap", "Anatomy_Hair")):
                modifier = obj.modifiers.new("FixedGarmentRelaxation", "SMOOTH")
                modifier.factor = 0.35
                modifier.iterations = 4
                if obj.name in anatomy_groups.get("neckline_pins", {}):
                    pins = set(anatomy_groups["neckline_pins"][obj.name])
                    near = set(pins)
                    for edge in obj.data.edges:
                        if any(index in pins for index in edge.vertices):
                            near.update(edge.vertices)
                    transition = set(near)
                    for edge in obj.data.edges:
                        if any(index in near for index in edge.vertices):
                            transition.update(edge.vertices)
                    group = obj.vertex_groups.new(name="FixedRelaxationAwayFromNeck")
                    for vertex in obj.data.vertices:
                        group.add(
                            [vertex.index],
                            0 if vertex.index in near else 0.5 if vertex.index in transition else 1,
                            "REPLACE",
                        )
                    modifier.vertex_group = group.name
                _apply(obj, modifier, bpy)
            if character["clothing"] == "cross_collar_tunic" and obj.name in ("Anatomy_shirt", "Anatomy_trousers"):
                modifier = obj.modifiers.new("FixedLinenControlRefinement", "SUBSURF")
                modifier.levels = modifier.render_levels = 1
                _apply(obj, modifier, bpy)
                obj.data.update()
                kind = "shirt" if obj.name == "Anatomy_shirt" else "trousers"
                for vertex in obj.data.vertices:
                    point = [vertex.co.x, vertex.co.z, -vertex.co.y]
                    normal = [vertex.normal.x, vertex.normal.z, -vertex.normal.y]
                    delta = period_surface_fold_offset(point, normal, anatomy_groups["body_metadata"], character, kind)
                    vertex.co += Vector((delta[0], -delta[2], delta[1]))
                obj.data.update()
            modifier = obj.modifiers.new("FixedGarmentThickness", "SOLIDIFY")
            modifier.thickness = (
                (0.002 if obj.name == "Anatomy_Hair" or character["clothing"] == "cross_collar_tunic" else 0.004)
                * character["height"]
                / 1.8
            )
            modifier.offset = 0
            modifier.use_even_offset = False
            modifier.use_rim = True
            _apply(obj, modifier, bpy)
        check = _quality(obj, bmesh)
        require(
            check["components"] == 1
            and check["manifold"]
            and check["volume"] > 1e-12
            and check["degenerate_triangles"] == 0,
            "region_not_closed_manifold:" + region["name"] + ":" + json.dumps(check, sort_keys=True),
        )
        (body if region["role"] == "body" else accessories).append(obj)
    body_region_count = len(body)
    fine_body = {name for key in ("head", "handL", "handR") for name in anatomy_groups.get(key, [])}
    body = [obj for obj in body if obj.name not in fine_body]
    coordinates = [v.co for obj in body for v in obj.data.vertices]
    dimensions = [max(v[i] for v in coordinates) - min(v[i] for v in coordinates) for i in range(3)]
    voxel = plan["finish"]["voxel_size"]
    voxels = 0 if character is not None else math.prod(math.ceil(extent / voxel) + 3 for extent in dimensions)
    require(voxels <= MAX_VOXELS, "voxel_budget_exceeded")
    subdivision = plan["finish"]["subdivision"]
    accessory_estimate = sum(len(obj.data.polygons) * 2 * (4**subdivision) for obj in accessories)
    require(accessory_estimate <= MAX_TRIANGLES, "subdivision_budget_exceeded")
    source_trees = []
    body_materials = {obj.data.materials[0].name for obj in body}
    if len(body_materials) > 1:
        for obj in body:
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            source_trees.append((BVHTree.FromBMesh(bm), obj.data.materials[0]))
            bm.free()
    single_body_material = body[0].data.materials[0]
    if character is not None:
        sculpt = _exact_union(body, bpy, bmesh, plan["name"], require_connected=False)
    else:
        sculpt = _join_meshes(body, bpy, plan["name"])
        modifier = sculpt.modifiers.new("FixedVoxelFusion", "REMESH")
        modifier.mode = "VOXEL"
        modifier.voxel_size = voxel
        modifier.adaptivity = 0
        modifier.use_remove_disconnected = False
        modifier.use_smooth_shade = True
        _apply(sculpt, modifier, bpy)
    internal_voxel_fills = []
    check = _quality(sculpt, bmesh)
    require(check["components"] == 1, "body_disconnected")
    require(check["manifold"] and check["volume"] > 1e-12, "body_not_closed_manifold")
    if plan["finish"]["smooth_iterations"]:
        modifier = sculpt.modifiers.new("FixedSculptSmooth", "SMOOTH")
        modifier.factor = 0.12 if character is not None else 0.5
        modifier.iterations = plan["finish"]["smooth_iterations"]
        _apply(sculpt, modifier, bpy)
    if character is not None:
        for key in ("shirt", "trousers"):
            joined = [obj for obj in accessories if obj.name in anatomy_groups.get(key, [])]
            if joined:
                accessories = [obj for obj in accessories if obj not in joined]
                garment = _exact_union(joined, bpy, bmesh, "Anatomy_" + key)
                if key == "shirt" and character["clothing"] == "robe_belt":
                    _cut_wrap_neck(garment, character, bpy, bmesh, Vector, Euler, Quaternion)
                modifier = garment.modifiers.new("FixedGarmentSurface", "SUBSURF")
                modifier.subdivision_type = "CATMULL_CLARK"
                modifier.levels = 2
                modifier.render_levels = 2
                _apply(garment, modifier, bpy)
                _cloth_drape(garment, character, key)
                accessories.append(garment)
    objects = [sculpt] + accessories

    def levels_for(obj):
        if obj.name in anatomy_groups.get("no_subdivision", []):
            return 0
        return (
            max(1, subdivision)
            if character is not None
            and (
                obj is sculpt
                or obj.name in anatomy_groups.get("shell", [])
                or obj.name in anatomy_groups.get("closed_garment", [])
            )
            else subdivision
        )

    estimate = sum(
        sum(
            (len(polygon.vertices) - 2)
            if levels_for(obj) == 0
            else 2 * len(polygon.vertices) * (4 ** (levels_for(obj) - 1))
            for polygon in obj.data.polygons
        )
        for obj in objects
    )
    require(estimate <= MAX_TRIANGLES, "subdivision_budget_exceeded:" + str(estimate))
    for obj in objects:
        levels = levels_for(obj)
        if levels:
            modifier = obj.modifiers.new("FixedSculptSubdivision", "SUBSURF")
            modifier.subdivision_type = "CATMULL_CLARK"
            modifier.levels = levels
            modifier.render_levels = levels
            _apply(obj, modifier, bpy)
    # Cup locations are declared on the source loft. Seat the full final cup on
    # the actual fused surface rather than assuming remeshing preserved it.
    pattern_seating = []
    if generated_patterns:
        by_name = {obj.name: obj for obj in accessories}
        region_roles = {region["name"]: region["role"] for region in original_plan["regions"]}
        target_trees = {}
        for measurement in pattern_measurements:
            target = (
                sculpt
                if region_roles[measurement["source_region"]] == "body"
                else region_objects[measurement["source_region"]]
            )
            if target.name not in target_trees:
                bm = bmesh.new()
                bm.from_mesh(target.data)
                target_trees[target.name] = BVHTree.FromBMesh(bm)
                bm.free()
            tree = target_trees[target.name]
            seated_centers = []
            for placement in measurement["placements"]:
                rotation = Euler(
                    tuple(math.radians(value) for value in placement["rotation_degrees"]), "YXZ"
                ).to_matrix()
                local = rotation @ Vector(
                    tuple(placement["center"][i] * placement["size"][i] for i in range(3))
                ) + Vector(placement["position"])
                axis = rotation @ Vector(tuple(placement["axis"][i] / placement["size"][i] for i in range(3)))
                anchor = Vector((local.x, -local.z, local.y))
                axis = Vector((axis.x, -axis.z, axis.y)).normalized()
                found, normal, _, distance = tree.find_nearest(anchor)
                limit = max(3 * voxel, 0.4 * placement["radius"] * max(placement["size"]))
                require(
                    found is not None and distance <= limit and normal.dot(axis) >= 0.2,
                    "repeat_pattern_anchor_not_exposed:"
                    + placement["name"]
                    + ":"
                    + json.dumps(
                        dict(
                            distance=distance, limit=limit, alignment=normal.dot(axis) if normal is not None else None
                        ),
                        sort_keys=True,
                    ),
                )
                orientation = axis.rotation_difference(normal)
                seating_depth = min(0.001, 0.03 * placement["radius"] * min(placement["size"]))
                destination = found - normal * seating_depth
                world_radius = placement["radius"] * max(placement["size"])
                require(
                    all(
                        (destination - other).length >= 0.98 * (world_radius + radius)
                        for other, radius in seated_centers
                    ),
                    "repeat_pattern_seated_cup_overlap:" + placement["name"],
                )
                seated_centers.append((destination.copy(), world_radius))
                obj = by_name[placement["name"]]
                for vertex in obj.data.vertices:
                    vertex.co = destination + orientation @ (vertex.co - anchor)
                obj.data.update()
                pattern_seating.append(
                    dict(
                        name=obj.name,
                        source_to_surface_distance=distance,
                        distance_limit=limit,
                        seating_depth=seating_depth,
                        normal_alignment=normal.dot(axis),
                    )
                )
    cleanup = []
    for obj in objects:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        before = (len(bm.verts), len(bm.faces))
        tolerance = min(voxel * 0.001, 0.00002)
        # Valid anatomical lip/eyelid surfaces can be only micrometers apart.
        # Proximity alone does not justify merging their distinct topology.
        obj.data.calc_loop_triangles()
        needs_cleanup = any(triangle.area <= 1e-12 for triangle in obj.data.loop_triangles)
        if needs_cleanup:
            bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=tolerance)
            bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=tolerance)
        cleanup.append(
            dict(
                name=obj.name,
                tolerance=tolerance,
                merged_vertices=before[0] - len(bm.verts),
                dissolved_faces=before[1] - len(bm.faces),
            )
        )
        before_triangulation = len(bm.verts)
        triangles, face_materials = _triangulate_surface(bm)
        cleanup[-1]["triangulation_inserted_vertices"] = len(bm.verts) - before_triangulation
        coordinates = [tuple(vertex.co) for vertex in bm.verts]
        obj.data.clear_geometry()
        obj.data.from_pydata(coordinates, [], triangles)
        for polygon, material_index in zip(obj.data.polygons, face_materials):
            polygon.material_index = material_index
        bm.free()
        obj.data.update()
    # Transfer nearest source-region material onto the fused body. The operation
    # does not preserve a source rig, UV map or animation-ready edge flow.
    material_order = list(materials.values())
    sculpt.data.materials.clear()
    for material in material_order:
        sculpt.data.materials.append(material)
    for polygon in sculpt.data.polygons:
        if source_trees:
            best = min(
                ((tree.find_nearest(polygon.center)[3], material) for tree, material in source_trees),
                key=lambda value: value[0],
            )
            polygon.material_index = material_order.index(best[1])
        else:
            polygon.material_index = material_order.index(single_body_material)
    qualities = [_quality(obj, bmesh) for obj in objects]
    for q in qualities:
        require(
            q["components"] == 1 and q["manifold"] and q["volume"] > 1e-12 and q["degenerate_triangles"] == 0,
            "final_geometry_invalid:" + json.dumps(q, sort_keys=True),
        )
    triangle_count = sum(q["triangles"] for q in qualities)
    require(triangle_count <= MAX_TRIANGLES, "triangle_budget_exceeded")
    require(sum(q["vertices"] for q in qualities) <= MAX_VERTICES, "vertex_budget_exceeded")
    for obj in objects:
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = sculpt
    require(
        "FINISHED"
        in bpy.ops.export_scene.gltf(
            filepath=str(output),
            export_format="GLB",
            use_selection=True,
            export_yup=True,
            export_apply=True,
            export_materials="EXPORT",
        ),
        "export_failed",
    )
    data = output.read_bytes()
    require(20 < len(data) <= MAX_GLB_BYTES and data[:4] == b"glTF", "output_glb_invalid")
    receipt = dict(
        ok=True,
        version=2,
        blender_version=bpy.app.version_string,
        regions=len(plan["regions"]),
        body_regions=body_region_count,
        accessories=len(accessories),
        parts=len(objects),
        vertices=sum(q["vertices"] for q in qualities),
        triangles=triangle_count,
        body_components=qualities[0]["components"],
        body_manifold=qualities[0]["manifold"],
        body_volume=qualities[0]["volume"],
        geometry=qualities,
        cleanup=cleanup,
        internal_voxel_fills=internal_voxel_fills,
        voxel_cells=voxels,
        bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        output_sha256=hashlib.sha256(data).hexdigest(),
        source_plan_sha256=hashlib.sha256(
            json.dumps(
                original_plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest(),
        completion=original_plan["completion"],
        expanded_plan_sha256=hashlib.sha256(
            json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest(),
        organic_detail=dict(
            loft_sampling=dict(radial=RADIAL, samples_per_span=LOFT_STEPS, cap_latitude_rings=4),
            pre_voxel_loft_subdivision=1 if pre_smoothed_lofts else 0,
            pre_smoothed_loft_count=len(pre_smoothed_lofts),
            pre_smoothed_lofts=pre_smoothed_lofts,
            patterns=pattern_measurements,
            generated_cups=len(generated_patterns),
            surface_seating=pattern_seating,
            rounded_caps=[
                dict(name=r["name"], end_caps=r["surface"]["end_caps"])
                for r in original_plan["regions"]
                if r["surface"].get("end_caps") is not None
            ],
        ),
        topology="closed_manifold_sculpt_not_animation_retopology",
        generated_code_executed=False,
        runtime_input_sha256={
            name + "_sha256": hashlib.sha256(Path(__file__).with_name(name + ".py").read_bytes()).hexdigest()
            for name in ("character_detail", "organic_detail", "period_groom")
        },
    )
    if character is not None:
        body_metadata = anatomy_groups["body_metadata"]
        landmarks = {"head_center": [0, character["height"] - character["height"] / character["head_ratio"] / 2, 0]}
        for label in ("L", "R"):
            source_side = "R" if label == "L" else "L"
            landmarks["hand_" + label] = body_metadata["landmarks"]["palm" + source_side]
            landmarks["digit_tips_" + label] = body_metadata["digits"][source_side]
        receipt["character_operator"] = {
            "kind": "trusted_parametric_anatomy_v1",
            "parameters": character,
            "expanded_plan_sha256": hashlib.sha256(
                json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            ).hexdigest(),
            "neural_weights_loaded": False,
            "source_reference_mesh_imported": False,
            "surface_implementation": "continuous_cc0_body_v1",
            "trusted_anatomy_base_used": False,
            "trusted_anatomy_body_used": True,
            "anatomy_body_source_sha256": body_metadata["source_sha256"],
            "anatomy_base_sha256": ANATOMY_BASE_SHA256,
            "anatomy_age_source_sha256": list(AGE_SOURCE_SHA256),
            "anatomy_age_weight": resolve_age_blend(character),
            "patch_pocket_scope": PATCH_POCKET_SCOPE,
            "requested_detail": character.get("detail"),
            "effective_detail": resolve_detail(character),
            "garment_coverage": "single_connected_coverall"
            if character["clothing"] == "coverall"
            else "overlapping_full_outfit_waist",
            "requested_arm_angle_degrees": character.get("arm_angle_degrees"),
            "effective_arm_angle_degrees": resolve_arm_angle(character),
            "period_groom": dict(
                requested=character.get("period_groom"),
                effective=resolve_period_groom(character),
                meshes=anatomy_groups["period_groom"],
            )
            if resolve_period_groom(character) is not None
            else None,
            "period_clothing": dict(
                kind="right_closing_cross_collar_tunic_v1",
                outer_lapel_direction="subject_left_neck_to_subject_right_waist",
                belt_knot_side="subject_left_positive_x",
                footwear=character["footwear"],
                continuous_back=True,
                gathered_trouser_ankles=True,
            )
            if character["clothing"] == "cross_collar_tunic"
            else None,
            "requested_age_blend": character.get("age_blend"),
            "effective_age_blend": resolve_age_blend(character),
            "fixed_small_accessory_uv_segments": [24, 16],
            "fine_detail_fusion": "continuous_canonical_body_no_skin_fusion",
            "requested_voxel_size": original_plan["finish"]["voxel_size"],
            "voxel_remesh_applied": False,
            "effective_core_voxel_size": None,
            "requested_smooth_iterations": original_plan["finish"]["smooth_iterations"],
            "effective_smooth_iterations": plan["finish"]["smooth_iterations"],
            "smoothing_factor": 0.12,
            "requested_subdivision": original_plan["finish"]["subdivision"],
            "effective_body_subdivision": max(1, subdivision),
            "fixed_minimum_body_subdivision": 1,
            "garment_surface_implementation": "clipped_canonical_surface_with_solid_cloth_thickness",
            "effective_garment_subdivision": max(1, subdivision),
            "garment_thickness": (0.002 if character["clothing"] == "cross_collar_tunic" else 0.004)
            * character["height"]
            / 1.8,
            "hair_shell_thickness": 0.002 * character["height"] / 1.8 if character["hair"] != "bald" else 0,
            "framing_landmarks_not_visual_acceptance": landmarks,
        }
    if renders:
        receipt["renders"] = _renders(objects, output.parent, bpy, Vector)
    with output.with_name(output.name + ".receipt.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return receipt


def main():
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    require(
        len(arguments) in (2, 3) and (len(arguments) == 2 or arguments[2] == "--renders"), "builder_arguments_invalid"
    )
    source = Path(arguments[0])
    require(source.is_file() and source.stat().st_size <= MAX_PLAN_BYTES, "plan_file_invalid")
    plan = json.loads(source.read_text(encoding="utf-8"))
    receipt = build(plan, arguments[1], len(arguments) == 3)
    print("MALIANG_SCULPT_BUILD_OK " + json.dumps(receipt, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            "MALIANG_SCULPT_BUILD_FAILED " + (str(error) if isinstance(error, ValueError) else type(error).__name__),
            file=sys.stderr,
        )
        import traceback

        traceback.print_exc()
        raise SystemExit(1)
