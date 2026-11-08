"""Fixed, bounded character details in glTF Y-up coordinates.

This module only returns numbers and closed mesh cages. It does not import
Blender, evaluate generated code, run a simulator or change the source plan.
Offsets for faces/hair use head-height units. Fabric offsets are fractions of
the whole character height and must be applied outward by the trusted caller.
"""

import math

PATCH_POCKET_SCOPE = "raised patch panel, no functional pocket interior"

DETAIL_LIMITS = {
    "cloth_ease": (0.0, 1.0),
    "fold_amplitude": (0.0, 1.0),
    "hair_volume": (0.0, 1.0),
    "hair_sweep": (-1.0, 1.0),
    "smile": (0.0, 1.0),
    "brow_raise": (-1.0, 1.0),
    "forehead_height": (-1.0, 1.0),
    "pocket_size": (0.0, 1.0),
}
DETAIL_DESCRIPTIONS = {
    "cloth_ease": "Additional outward cloth volume: 0 preserves the old fit, 1 adds at most 0.025 body heights.",
    "fold_amplitude": "Positive-only broad fabric ridges: 0 off, 1 adds at most 0.006 body heights; not cloth simulation.",
    "hair_volume": "Short-wave bulk from 0 to 1; missing/null resolves to 0.6 only for short_wavy, otherwise 0.",
    "hair_sweep": "Hair sweep along X: negative to subject-right, positive to subject-left; short_wavy defaults to 0.35.",
    "smile": "Raises mouth corners from 0 neutral to 1 smiling; does not open the mouth or expose invented teeth.",
    "brow_raise": "Positive raises brow, negative lowers it; bounded to 0.055 head heights before style scaling.",
    "forehead_height": "Positive raises upper cranium, negative shortens/rounds it; maximum 0.08 head heights.",
    "pocket_size": "Observed front patch pockets only: 0 omits them, 1 uses the maximum bounded pocket size.",
}


def _number(value, lower, upper):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and lower <= value <= upper
    )


def _require(condition, code):
    if not condition:
        raise ValueError(code)


def _point(value):
    _require(isinstance(value, (list, tuple)) and len(value) == 3, "detail_point_invalid")
    _require(all(_number(component, -8, 8) for component in value), "detail_point_invalid")
    return tuple(float(component) for component in value)


def _smooth(lower, upper, value):
    t = max(0.0, min(1.0, (value - lower) / (upper - lower)))
    return t * t * (3 - 2 * t)


def _gaussian(x, y, cx, cy, sx, sy):
    return math.exp(-0.5 * (((x - cx) / sx) ** 2 + ((y - cy) / sy) ** 2))


def detail_schema():
    """Strict fresh-CLI schema; old plans may omit/null the whole detail object."""
    return {
        "type": ["object", "null"],
        "properties": {
            key: {
                "type": ["number", "null"],
                "minimum": lower,
                "maximum": upper,
                "description": DETAIL_DESCRIPTIONS[key],
            }
            for key, (lower, upper) in DETAIL_LIMITS.items()
        },
        "required": list(DETAIL_LIMITS),
        "additionalProperties": False,
    }


def resolve_detail(character):
    """Validate optional details without inserting anything into the source dict."""
    _require(isinstance(character, dict), "character_detail_invalid")
    raw = character.get("detail")
    _require(raw is None or isinstance(raw, dict), "character_detail_invalid")
    values = {} if raw is None else raw
    _require(set(values) <= set(DETAIL_LIMITS), "character_detail_fields_invalid")
    result = {}
    for key, (lower, upper) in DETAIL_LIMITS.items():
        value = values.get(key)
        _require(value is None or _number(value, lower, upper), "character_detail_value_invalid")
        fallback = (
            0.6
            if key == "hair_volume" and character.get("hair") == "short_wavy"
            else 0.35
            if key == "hair_sweep" and character.get("hair") == "short_wavy"
            else 0.0
        )
        result[key] = fallback if value is None else float(value)
    return result


def _detail(detail):
    _require(isinstance(detail, dict) and set(detail) == set(DETAIL_LIMITS), "resolved_detail_invalid")
    _require(all(_number(detail[key], *limits) for key, limits in DETAIL_LIMITS.items()), "resolved_detail_invalid")


def _frame(headframe):
    _require(isinstance(headframe, dict), "detail_headframe_invalid")
    origin = _point(headframe.get("origin"))
    height = headframe.get("height")
    _require(_number(height, 0.03, 2.0), "detail_headframe_invalid")
    return origin, float(height)


def _eyes(eye_centers):
    values = list(eye_centers.values()) if isinstance(eye_centers, dict) else eye_centers
    _require(isinstance(values, (list, tuple)) and len(values) == 2, "detail_eyes_invalid")
    return [_point(point) for point in values]


def face_detail_offset(point, headframe, eye_centers, detail, style):
    """Continuous local changes: +smile corners, +brow up, +forehead taller.

    The original real-anatomy eyelid/globe fit remains the core builder's job.
    Forehead changes affect the upper cranium on all sides, not the neck.
    """
    x, y, z = _point(point)
    origin, hh = _frame(headframe)
    eyes = _eyes(eye_centers)
    _detail(detail)
    _require(style in ("realistic", "stylized"), "detail_style_invalid")
    x -= origin[0]
    eye_y = sum(eye[1] for eye in eyes) / 2
    eye_z = sum(eye[2] for eye in eyes) / 2
    front = _smooth(eye_z - 0.24 * hh, eye_z - 0.04 * hh, z)
    dy = 0.08 * hh * detail["forehead_height"] * _smooth(eye_y + 0.07 * hh, origin[1] + 0.43 * hh, y)
    dz = 0.0
    mouth_y = origin[1] - 0.31 * hh
    style_gain = 1.25 if style == "stylized" else 1.0
    for eye in eyes:
        side = -1 if eye[0] < origin[0] else 1
        corner = _gaussian(x, y, side * 0.16 * hh, mouth_y, 0.075 * hh, 0.055 * hh)
        dy += 0.045 * hh * detail["smile"] * corner * front * style_gain
        cheek = _gaussian(x, y, side * 0.20 * hh, mouth_y + 0.11 * hh, 0.11 * hh, 0.09 * hh)
        dz += 0.009 * hh * detail["smile"] * cheek * front
        brow = _gaussian(x, y, eye[0] - origin[0], eye[1] + 0.10 * hh, 0.12 * hh, 0.045 * hh)
        dy += 0.055 * hh * detail["brow_raise"] * brow * front * style_gain
    return [0.0, dy, dz]


def hair_detail_mask(point, headframe):
    """Signed external-scalp mask, positive kept, with a lower back/nape.

    The fixed BODY asset includes internal mouth surfaces. The low cutoff is
    reserved for the rear hemisphere, so low-Z surfaces inside the face are
    excluded analytically, without deleting disconnected geometry afterward.
    """
    x, y, z = _point(point)
    origin, hh = _frame(headframe)
    qz = (z - origin[2]) / hh
    front = _smooth(-0.40, -0.10, qz)
    side = _smooth(0.20, 0.42, abs(x - origin[0]) / hh)
    cutoff = origin[1] + hh * (-0.30 + 0.50 * front + 0.035 * side)
    fringe = 0.035 * hh * _smooth(-0.08, 0.12, qz) * (0.5 + 0.5 * math.sin(14 * (x - origin[0]) / hh + 1.5 * qz))
    cutoff -= fringe
    return y - cutoff


def hair_detail_offset(point, headframe, normal, detail):
    """Short-wave bulk with scalp-seated roots and tangential crown sweep.

    The caller supplies exact clipped hairline_distance when available. This
    prevents interpolation errors in the nonlinear mask lifting a boundary.
    Extra bulk and sweep both reach zero at the hairline; the core separately
    tapers its base clearance and cloth thickness to seat the physical rim.
    """
    x, y, z = _point(point)
    origin, hh = _frame(headframe)
    direction = _point(normal)
    length = math.sqrt(sum(component * component for component in direction))
    _require(length > 1e-10, "detail_normal_invalid")
    normal = [component / length for component in direction]
    _detail(detail)
    distance = headframe.get("hairline_distance")
    if distance is None:
        distance = hair_detail_mask(point, headframe)
    _require(_number(distance, -8, 8), "detail_hairline_distance_invalid")
    root_weight = _smooth(0.004 * hh, 0.20 * hh, max(0.0, distance))
    qx, qy, qz = (value / hh for value in (x - origin[0], y - origin[1], z - origin[2]))
    top = _smooth(-0.05, 0.40, qy)
    phase = 7 * math.atan2(qz, qx) + 5 * qy + 1.2 * math.sin(3 * qz)
    ridge = (0.5 + 0.5 * math.sin(phase)) ** 2
    bulk = hh * detail["hair_volume"] * (0.025 + 0.095 * top + 0.075 * ridge * (0.35 + 0.65 * top))
    tangent = [1 - normal[0] * normal[0], -normal[0] * normal[1], -normal[0] * normal[2]]
    sweep = 0.10 * hh * detail["hair_sweep"] * top
    return [root_weight * (component * bulk + sideways * sweep) for component, sideways in zip(normal, tangent)]


def fabric_outward_offset(height_fraction, angle, detail, kind):
    """Nonnegative displacement / body height, never an inward cloth crease.

    Ease is broad additional volume. Two low-frequency ridge families modulate
    the positive folds around lower-leg/knee or gathered waist/torso regions.
    They are fixed geometry, not recovered or simulated fabric.
    """
    _require(_number(height_fraction, 0, 1) and _number(angle, -1e6, 1e6), "detail_fabric_coordinate_invalid")
    _require(kind in ("shirt", "trousers", "coverall"), "detail_fabric_kind_invalid")
    _detail(detail)
    y = float(height_fraction)
    theta = math.remainder(float(angle), 2 * math.pi)
    if kind == "trousers" or kind == "coverall" and y < 0.54:
        gather = math.exp(-0.5 * ((y - 0.12) / 0.055) ** 2)
        gather += 0.65 * math.exp(-0.5 * ((y - 0.32) / 0.065) ** 2)
    else:
        gather = math.exp(-0.5 * ((y - 0.58) / 0.08) ** 2)
        gather += 0.55 * math.exp(-0.5 * ((y - 0.72) / 0.10) ** 2)
    gather = min(1.0, gather)
    ridge = (0.5 + 0.5 * math.cos(5 * theta + 0.7 * math.sin(8 * y))) ** 3
    cross = 0.5 + 0.5 * math.sin(19 * y + 1.3 * math.sin(2 * theta))
    folds = 0.006 * detail["fold_amplitude"] * gather * (0.7 * ridge + 0.3 * cross)
    return 0.025 * detail["cloth_ease"] + folds


def trouser_waist(shirt_hem_y, body_waist_y, height, clothing):
    """Full outfits cover the abdomen: trouser top overlaps a high shirt hem.

    This defines the generated high-waist garment, not an input-plan rewrite.
    A decorative robe belt never controls the anatomical trouser-seat cut.
    The coverall caller uses a single shell; the same value is its trim seam.
    """
    _require(_number(height, 0.8, 2.4), "detail_height_invalid")
    _require(_number(shirt_hem_y, 0, height) and _number(body_waist_y, 0, height), "detail_waist_invalid")
    _require(clothing in ("tshirt_trousers", "robe_belt", "coverall"), "detail_clothing_invalid")
    return float(body_waist_y) if clothing == "robe_belt" else max(float(body_waist_y), shirt_hem_y + 0.015 * height)


def _projector(vertices, faces, maximum_gap):
    """Frontmost +Z ray intersection with a trusted finite mesh, no callback."""
    _require(isinstance(vertices, (list, tuple)) and 3 <= len(vertices) <= 1000000, "detail_mesh_invalid")
    points = [_point(point) for point in vertices]
    _require(isinstance(faces, (list, tuple)) and 1 <= len(faces) <= 1000000, "detail_mesh_invalid")
    triangles = []
    for face in faces:
        _require(isinstance(face, (list, tuple)) and 3 <= len(face) <= 64, "detail_mesh_invalid")
        _require(
            all(isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(points) for index in face),
            "detail_mesh_invalid",
        )
        for i in range(1, len(face) - 1):
            a, b, c = (points[index] for index in (face[0], face[i], face[i + 1]))
            denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(denominator) > 1e-14:
                triangles.append((a, b, c, denominator))
    _require(bool(triangles), "detail_projection_empty")

    def project(x, y):
        found = []
        for a, b, c, denominator in triangles:
            wa = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / denominator
            wb = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / denominator
            wc = 1 - wa - wb
            if min(wa, wb, wc) >= -1e-7:
                found.append(a[2] * wa + b[2] * wb + c[2] * wc)
        if found:
            return max(found)
        nearest = min(points, key=lambda point: (point[0] - x) ** 2 + (point[1] - y) ** 2)
        _require(math.hypot(nearest[0] - x, nearest[1] - y) <= maximum_gap, "detail_projection_missed")
        return nearest[2]

    return project


def _closed_ribbon(path, width, depth, clearance, project):
    """Closed quad tube following a monotonic X or Y front-surface path."""
    _require(2 <= len(path) <= 32 and width > 0 and depth > 0 and clearance > 0, "detail_ribbon_invalid")
    vertices = []
    for index, (x, y) in enumerate(path):
        before = path[max(0, index - 1)]
        after = path[min(len(path) - 1, index + 1)]
        dx, dy = after[0] - before[0], after[1] - before[1]
        length = math.hypot(dx, dy)
        _require(length > 1e-10, "detail_ribbon_invalid")
        ox, oy = -dy / length * width / 2, dx / length * width / 2
        left = [x + ox, y + oy]
        right = [x - ox, y - oy]
        zl, zr = project(*left) + clearance, project(*right) + clearance
        vertices.extend([[*right, zr], [*left, zl], [*left, zl + depth], [*right, zr + depth]])
    faces = [[3, 2, 1, 0], [len(vertices) - 4 + i for i in range(4)]]
    for start in range(0, len(vertices) - 4, 4):
        for i in range(4):
            j = (i + 1) % 4
            faces.append([start + i, start + j, start + 4 + j, start + 4 + i])
    # The path may point downward; orient its whole closed shell by signed volume.
    volume = 0.0
    for face in faces:
        a = vertices[face[0]]
        for i in range(1, len(face) - 1):
            b, c = vertices[face[i]], vertices[face[i + 1]]
            volume += (
                a[0] * (b[1] * c[2] - b[2] * c[1])
                + a[1] * (b[2] * c[0] - b[0] * c[2])
                + a[2] * (b[0] * c[1] - b[1] * c[0])
            )
    _require(abs(volume) > 1e-14, "detail_ribbon_volume_invalid")
    if volume < 0:
        faces = [list(reversed(face)) for face in faces]
    return vertices, faces


def _cage(name, vertices, faces, material="AnatomyCloth"):
    return {"name": name, "vertices": vertices, "faces": faces, "material": material, "group": "closed_garment"}


def _closed_panel(left, right, bottom, top, depth, clearance, project):
    """Thin closed raised patch panel, no functional pocket interior."""
    _require(right > left and top > bottom and depth > 0 and clearance > 0, "detail_panel_invalid")
    return _closed_quad([(left, bottom), (right, bottom), (right, top), (left, top)], depth, clearance, project)


def _closed_quad(corners, depth, clearance, project):
    """A small convex cloth plate fitted on a bounded six-by-six sample grid."""
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(corners, corners[1:] + corners[:1]))
    _require(abs(area) > 1e-12, "detail_panel_invalid")
    if area < 0:
        corners = list(reversed(corners))
    steps = 6
    side = steps + 1
    back = []
    for row in range(side):
        t = row / steps
        for column in range(side):
            u = column / steps
            x, y = [
                (1 - t) * ((1 - u) * corners[0][axis] + u * corners[1][axis])
                + t * ((1 - u) * corners[3][axis] + u * corners[2][axis])
                for axis in range(2)
            ]
            back.append([x, y, project(x, y) + clearance])
    return _solid_grid(back, side, depth)


def _solid_grid(back, side, depth):
    """Close a small sampled fabric plate and orient its whole shell outward."""
    steps = side - 1
    layer = side * side
    vertices = back + [[x, y, z + depth] for x, y, z in back]
    faces = []
    for row in range(steps):
        for column in range(steps):
            a = row * side + column
            quad = [a, a + 1, a + side + 1, a + side]
            faces.extend([list(reversed(quad)), [index + layer for index in quad]])
    boundary = list(range(side))
    boundary += [row * side + steps for row in range(1, side)]
    boundary += [steps * side + column for column in range(steps - 1, -1, -1)]
    boundary += [row * side for row in range(steps - 1, 0, -1)]
    for a, b in zip(boundary, boundary[1:] + boundary[:1]):
        faces.append([a, b, b + layer, a + layer])
    volume = 0.0
    for face in faces:
        a = vertices[face[0]]
        for i in range(1, len(face) - 1):
            b, c = vertices[face[i]], vertices[face[i + 1]]
            volume += sum(
                a[axis] * (b[(axis + 1) % 3] * c[(axis + 2) % 3] - b[(axis + 2) % 3] * c[(axis + 1) % 3])
                for axis in range(3)
            )
    _require(abs(volume) > 1e-14, "detail_panel_volume_invalid")
    if volume < 0:
        faces = [list(reversed(face)) for face in faces]
    return vertices, faces


def _neck_roots(rim, sign, height):
    """Interpolate actual neckline edges along the front-to-side fold seam."""
    _require(isinstance(rim, (list, tuple)) and 8 <= len(rim) <= 4096, "detail_neck_rim_missing")
    rim = [_point(point) for point in rim]
    cx = (min(point[0] for point in rim) + max(point[0] for point in rim)) / 2
    cz = (min(point[2] for point in rim) + max(point[2] for point in rim)) / 2
    _require(
        0.025 * height < max(point[0] for point in rim) - min(point[0] for point in rim) < 0.25 * height,
        "detail_neck_rim_invalid",
    )
    entries = sorted((math.atan2(point[0] - cx, point[2] - cz), point) for point in rim)
    entries.append((entries[0][0] + 2 * math.pi, entries[0][1]))
    roots = []
    for step in range(7):
        target = sign * (0.16 + 1.04 * step / 6)
        if target < entries[0][0]:
            target += 2 * math.pi
        found = None
        for (a, pa), (b, pb) in zip(entries, entries[1:]):
            if a <= target <= b and b - a > 1e-10:
                t = (target - a) / (b - a)
                found = [p + t * (q - p) for p, q in zip(pa, pb)]
                break
        _require(found is not None, "detail_neck_rim_invalid")
        roots.append(found)
    return roots


def _attached_collar(roots, sign, height, project):
    clearance = 0.0015 * height
    back = []
    for row in range(7):
        toward_root = row / 6
        for column, root in enumerate(roots):
            u = column / 6
            bottom_x = root[0] + sign * height * (0.020 + 0.012 * math.sin(math.pi * u))
            bottom_y = root[1] - height * (0.075 * (1 - u) + 0.035 * u)
            x = bottom_x + toward_root * (root[0] - bottom_x)
            y = bottom_y + toward_root * (root[1] - bottom_y)
            z = root[2] if row == 6 else project(x, y)
            back.append([x, y, z + clearance])
    vertices, faces = _solid_grid(back, 7, 0.0014 * height)
    return (
        vertices,
        faces,
        {
            "kind": "fold_edge_on_actual_neckline",
            "root_vertices": list(range(42, 49)),
            "rim_positions": roots,
            "raw_surface_clearance": clearance,
        },
    )


def accessories(canonical, character, garment):
    """Closed collar/placket and observed raised patch panels with top lips.

    The core builds the joined coverall and measures its waistband. These small
    front pieces are fitted against that actual raw shell, not guessed ellipses.
    Every returned piece is closed; it must not be shrunk by global subdivision.
    """
    detail = resolve_detail(character)
    _require(isinstance(canonical, dict) and isinstance(garment, dict), "detail_accessory_invalid")
    _require(_number(character.get("height"), 0.8, 2.4), "detail_height_invalid")
    height = character["height"]
    if character.get("clothing") != "coverall" and detail["pocket_size"] == 0:
        return []
    land = canonical["landmarks"]
    chin = _point(land.get("chin", land.get("jaw")))
    hip = (_point(land["hipL"])[1] + _point(land["hipR"])[1]) / 2
    neck = garment.get("details", {}).get("neck_top", chin[1] - 0.025 * height)
    _require(_number(neck, 0, height), "detail_accessory_neck_invalid")
    project = _projector(garment["vertices"], garment["faces"], 0.06 * height)
    result = []
    if character.get("clothing") == "coverall":
        rim = garment.get("details", {}).get("neck_rim")
        for sign, label in ((-1, "R"), (1, "L")):
            roots = _neck_roots(rim, sign, height)
            vertices, faces, attachment = _attached_collar(roots, sign, height, project)
            cage = _cage("WorkCollar" + label, vertices, faces)
            cage["attachment"] = attachment
            result.append(cage)
        front_rim = max((_point(point) for point in rim), key=lambda point: point[2] - 0.5 * abs(point[0]))
        top, bottom = front_rim[1] - 0.010 * height, hip - 0.035 * height
        _require(top > bottom + 0.05 * height, "detail_accessory_placket_invalid")
        path = [(0, top + (bottom - top) * i / 8) for i in range(9)]
        vertices, faces = _closed_ribbon(path, 0.011 * height, 0.0015 * height, 0.001 * height, project)
        result.append(_cage("WorkPlacket", vertices, faces))
    if detail["pocket_size"] > 0:
        size = 0.5 + 0.5 * detail["pocket_size"]
        belt = character.get("belt_height", 0.60) * height
        if character.get("clothing") == "coverall":
            hem = hip - 0.16 * height
            pocket_top = min(belt - 0.020 * height, hip + 0.025 * height)
        elif character.get("clothing") == "tshirt_trousers":
            # These are trouser patch panels. The shirt hem or its unused
            # decorative-belt parameter cannot move them above/below the seat.
            hem = hip - 0.16 * height
            belt = hip + 0.035 * height
            pocket_top = hip + 0.010 * height
        else:
            hem = garment.get("details", {}).get("hem", character.get("hem_height", 0.45) * height)
            pocket_top = min(belt - 0.020 * height, hip + 0.050 * height)
        lower, upper = hem + 0.003 * height, belt - 0.003 * height
        _require(upper - lower > 0.018 * height, "detail_pocket_placement_invalid")
        pocket_top = min(upper, max(pocket_top, lower + 0.018 * height))
        pocket_bottom = max(lower, pocket_top - 0.095 * height * size)
        for sign, label in ((-1, "R"), (1, "L")):
            center = sign * 0.075 * height
            width = 0.065 * height * size
            left, right = center - width / 2, center + width / 2
            vertices, faces = _closed_panel(
                left, right, pocket_bottom, pocket_top, 0.0015 * height, 0.002 * height, project
            )
            result.append(_cage("PocketPanel" + label, vertices, faces))
            path = [(left, pocket_top), (right, pocket_top)]
            vertices, faces = _closed_ribbon(path, 0.006 * height, 0.001 * height, 0.0035 * height, project)
            result.append(_cage("PocketLip" + label, vertices, faces))
    return result


def eyebrow_accessories(canonical, character):
    """Dark, closed eyebrow arcs on the actual morphed face, never a texture.

    Old plans without a detail object retain the old output. A new explicit
    detail object enables these thin hair arcs, including a neutral expression.
    """
    detail = resolve_detail(character)
    if character.get("detail") is None:
        return []
    _require(isinstance(canonical, dict), "detail_accessory_invalid")
    height = character.get("height")
    ratio = character.get("head_ratio")
    _require(_number(height, 0.8, 2.4) and _number(ratio, 5, 8.5), "detail_headframe_invalid")
    _require(character.get("style") in ("realistic", "stylized"), "detail_style_invalid")
    hh = height / ratio
    project = _projector(canonical["vertices"], canonical["faces"], 0.035 * hh)
    stylized = character["style"] == "stylized"
    result = []
    for label in ("L", "R"):
        eye = _point(canonical["landmarks"]["eye" + label])
        path = []
        for i in range(9):
            t = -1 + i / 4
            x = eye[0] + t * (0.115 if stylized else 0.105) * hh
            # Eye anchor is already deformed by the core. The added arc sits
            # above it; +brow_raise moves the visible hair arc upward too.
            y = eye[1] + hh * (0.072 + 0.035 * (1 - t * t) + 0.045 * detail["brow_raise"])
            path.append((x, y))
        vertices, faces = _closed_ribbon(path, (0.030 if stylized else 0.016) * hh, 0.006 * hh, 0.0025 * hh, project)
        result.append(_cage("Eyebrow" + label, vertices, faces, "AnatomyHair"))
    return result
