"""Bounded, surface-fitted period grooming in glTF Y-up meters.

This trusted helper emits closed cages, never code, files, Blender operations or
neural output. A null/missing option emits nothing and leaves the old path intact.
The swept grooves represent modeled locks, not individually simulated hair.
"""

import math
from collections import defaultdict

GROOM_LIMITS = {
    "bun_size": (0.6, 1.4, 1.0),
    "bun_back": (0.0, 1.0, 0.65),
    "hairline": (-0.12, 0.12, 0.0),
    "sweep_depth": (0.0, 1.0, 0.65),
    "temple_gray": (0.0, 1.0, 0.55),
    "moustache_width": (0.6, 1.4, 1.0),
    "goatee_length": (0.5, 1.5, 1.0),
}
MAX_GROOM_VERTICES = 18000
MAX_GROOM_TRIANGLES = 36000
MAX_GROOM_SPECS = 8


def _require(condition, code):
    if not condition:
        raise ValueError(code)


def _number(value, low, high):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and low <= value <= high
    )


def _point(point):
    _require(isinstance(point, (list, tuple)) and len(point) == 3, "groom_point_invalid")
    _require(all(_number(x, -8, 8) for x in point), "groom_point_invalid")
    return tuple(float(x) for x in point)


def period_groom_schema():
    properties = {
        "version": {"type": "integer", "enum": [1]},
        "hairstyle": {"type": "string", "enum": ["swept_back_bun"]},
        "facial_hair": {"type": "string", "enum": ["moustache_goatee", "none"]},
    }
    properties.update({
        key: {"type": ["number", "null"], "minimum": low, "maximum": high}
        for key, (low, high, _) in GROOM_LIMITS.items()
    })
    return {
        "type": ["object", "null"],
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def resolve_period_groom(character):
    _require(isinstance(character, dict), "period_groom_invalid")
    raw = character.get("period_groom")
    if raw is None:
        return None
    _require(isinstance(raw, dict), "period_groom_invalid")
    _require(set(raw) <= set(GROOM_LIMITS) | {"version", "hairstyle", "facial_hair"}, "period_groom_fields_invalid")
    _require(type(raw.get("version")) is int and raw["version"] == 1, "period_groom_version_invalid")
    _require(raw.get("hairstyle") == "swept_back_bun", "period_groom_hair_invalid")
    _require(raw.get("facial_hair") in ("moustache_goatee", "none"), "period_groom_beard_invalid")
    result = {key: raw[key] for key in ("version", "hairstyle", "facial_hair")}
    for key, (low, high, default) in GROOM_LIMITS.items():
        value = raw.get(key)
        value = default if value is None else value
        _require(_number(value, low, high), "period_groom_" + key + "_invalid")
        result[key] = float(value)
    return result


def _sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _triangles(canonical, low_y):
    points = [_point(point) for point in canonical["vertices"]]
    _require(4 <= len(points) <= 100000, "groom_source_budget")
    result = []
    faces = canonical["faces"]
    _require(isinstance(faces, (list, tuple)) and len(faces) <= 100000, "groom_source_budget")
    for face in faces:
        _require(isinstance(face, (list, tuple)) and 3 <= len(face) <= 4, "groom_source_face_invalid")
        _require(all(type(index) is int and 0 <= index < len(points) for index in face), "groom_source_index_invalid")
        if max(points[index][1] for index in face) < low_y:
            continue
        for i in range(1, len(face) - 1):
            a, b, c = (points[index] for index in (face[0], face[i], face[i + 1]))
            result.append((a, _sub(b, a), _sub(c, a)))
    _require(bool(result), "groom_source_head_empty")
    return result


def _ray(triangles, origin, direction):
    nearest = None
    ox, oy, oz = origin
    dx, dy, dz = direction
    for a, e1, e2 in triangles:
        px, py, pz = dy * e2[2] - dz * e2[1], dz * e2[0] - dx * e2[2], dx * e2[1] - dy * e2[0]
        determinant = e1[0] * px + e1[1] * py + e1[2] * pz
        if abs(determinant) < 1e-13:
            continue
        tx, ty, tz = ox - a[0], oy - a[1], oz - a[2]
        u = (tx * px + ty * py + tz * pz) / determinant
        if not -1e-8 <= u <= 1 + 1e-8:
            continue
        qx, qy, qz = ty * e1[2] - tz * e1[1], tz * e1[0] - tx * e1[2], tx * e1[1] - ty * e1[0]
        v = (dx * qx + dy * qy + dz * qz) / determinant
        if v < -1e-8 or u + v > 1 + 1e-8:
            continue
        distance = (e2[0] * qx + e2[1] * qy + e2[2] * qz) / determinant
        if distance > 1e-7 and (nearest is None or distance < nearest):
            nearest = distance
    _require(nearest is not None, "groom_surface_ray_missed")
    return [origin[i] + direction[i] * nearest for i in range(3)]


def _scalp(triangles, origin, hh, values):
    count, rows = 128, 24
    points, roots = [], []
    for layer in (0, 1):
        pole = _ray(triangles, origin, (0, 1, 0))
        pole[1] += (0.014 if layer == 0 else -0.0015) * hh
        points.append(pole)
        for row in range(1, rows + 1):
            s = row / rows
            for j in range(count):
                theta = 2 * math.pi * j / count
                # High forehead, exposed ears, and low rear/nape; no detached ear islands.
                boundary = 1.51 - 0.41 * math.cos(theta) - 0.16 * math.sin(theta) ** 2 - values["hairline"]
                boundary += 0.012 * math.sin(11 * theta) + 0.006 * math.sin(23 * theta)
                phi = s * boundary
                direction = (math.sin(phi) * math.sin(theta), math.cos(phi), math.sin(phi) * math.cos(theta))
                root = _ray(triangles, origin, direction)
                fade = _smooth((1 - s) / 0.22)
                # Grooves converge toward the knot, fade into genuinely attached hair roots.
                groove = (0.5 + 0.5 * math.cos(88 * theta + 4.5 * s + 0.7 * math.sin(3 * theta))) ** 3
                bulk = (0.010 + 0.012 * values["sweep_depth"] * groove) * fade
                offset = (0.0025 + bulk) * hh if layer == 0 else -0.0015 * hh
                points.append([root[i] + direction[i] * offset for i in range(3)])
                if layer == 0 and row == rows:
                    roots.append((root, points[-1]))
    layer_size = 1 + rows * count
    faces = []
    for layer in (0, 1):
        base = layer * layer_size
        for j in range(count):
            face = [base, base + 1 + j, base + 1 + (j + 1) % count]
            faces.append(face if layer == 0 else face[::-1])
        for row in range(rows - 1):
            for j in range(count):
                a = base + 1 + row * count + j
                b = base + 1 + row * count + (j + 1) % count
                face = [a, a + count, b + count, b]
                faces.append(face if layer == 0 else face[::-1])
    start = 1 + (rows - 1) * count
    for j in range(count):
        a, b = start + j, start + (j + 1) % count
        faces.append([a, a + layer_size, b + layer_size, b])
    return points, faces, roots


def _bun(origin, hh, values):
    center = [origin[0], origin[1] + 0.49 * hh, origin[2] - (0.10 + 0.11 * values["bun_back"]) * hh]
    radii = [0.128 * hh * values["bun_size"], 0.105 * hh * values["bun_size"], 0.115 * hh * values["bun_size"]]
    count, rows = 96, 22
    points = [[center[0], center[1] + radii[1], center[2]]]
    for row in range(1, rows):
        phi = math.pi * row / rows
        for j in range(count):
            theta = 2 * math.pi * j / count
            groove = 1 + 0.025 * math.cos(44 * theta + 9 * phi) * math.sin(phi) ** 2
            points.append([
                center[0] + radii[0] * math.sin(phi) * math.sin(theta) * groove,
                center[1] + radii[1] * math.cos(phi),
                center[2] + radii[2] * math.sin(phi) * math.cos(theta) * groove,
            ])
    bottom = len(points)
    points.append([center[0], center[1] - radii[1], center[2]])
    faces = [[0, 1 + j, 1 + (j + 1) % count] for j in range(count)]
    for row in range(rows - 2):
        for j in range(count):
            a, b = 1 + row * count + j, 1 + row * count + (j + 1) % count
            faces.append([a, a + count, b + count, b])
    faces.extend([[bottom, 1 + (rows - 2) * count + (j + 1) % count, 1 + (rows - 2) * count + j] for j in range(count)])
    return points, faces


def _gray_temples(scalp, origin, hh, strength):
    """Thin rooted gray lock patches; their backing remains inside the dark hair."""
    result = []
    count, rows, columns = 128, 8, 31
    for sign, name in ((1, "PeriodGrayTempleL"), (-1, "PeriodGrayTempleR")):
        first = 20 if sign > 0 else 101
        vertices = []
        for layer in (0, 1):
            for row in range(rows):
                for column in range(columns):
                    along = column / (columns - 1) * 6
                    j = (first + int(along)) % count
                    fraction = along - int(along)
                    source_row = 17 + row
                    p = scalp[1 + (source_row - 1) * count + j]
                    q = scalp[1 + (source_row - 1) * count + (j + 1) % count]
                    point = [p[i] * (1 - fraction) + q[i] * fraction for i in range(3)]
                    delta = _sub(point, origin)
                    length = math.sqrt(_dot(delta, delta))
                    # A connected backing is hidden in the black hair; only narrow
                    # comb ridges emerge instead of a solid painted gray plate.
                    stripe = max(0, math.sin(column * math.pi / 3 + row * 0.18)) ** 3
                    edge = math.sin(math.pi * column / (columns - 1)) ** 0.4
                    offset = hh * (-0.001 + 0.005 * strength * stripe * edge) if layer == 0 else -0.003 * hh
                    vertices.append([point[i] + delta[i] / length * offset for i in range(3)])
        faces = []
        size = rows * columns
        for layer in (0, 1):
            base = layer * size
            for row in range(rows - 1):
                for column in range(columns - 1):
                    a = base + row * columns + column
                    face = [a, a + columns, a + columns + 1, a + 1]
                    faces.append(face if layer == 0 else face[::-1])
        border = list(range(columns))
        border += [row * columns + columns - 1 for row in range(1, rows)]
        border += [(rows - 1) * columns + column for column in range(columns - 2, -1, -1)]
        border += [row * columns for row in range(rows - 2, 0, -1)]
        for a, b in zip(border, border[1:] + border[:1]):
            faces.append([a, b, b + size, a + size])
        result.append((name, vertices, faces))
    return result


def _face_projector(triangles, origin, hh):
    def project(x, y):
        # Outside-to-inside ray ensures the frontmost actual surface is used.
        return _ray(triangles, (x, y, origin[2] + 2 * hh), (0, 0, -1))[2]

    return project


def _beard_patch(project, cx, cy, width, length, hh, kind, sign):
    count, rows = 64, 10

    def xy(s, theta):
        # Mustache wings drop outward; goatee narrows toward its lower tip.
        x = cx + width * s * math.cos(theta)
        y = cy + length * s * math.sin(theta)
        if kind == "moustache":
            y -= 0.45 * sign * (x - cx)
        else:
            x = cx + (x - cx) * (0.55 + 0.45 * (y - cy + length) / (2 * length))
        return x, y

    points = []
    for layer in (0, 1):
        x, y = xy(0, 0)
        points.append([x, y, project(x, y) + (0.010 if layer == 0 else -0.001) * hh])
        for row in range(1, rows + 1):
            s = row / rows
            for j in range(count):
                theta = 2 * math.pi * j / count
                x, y = xy(s, theta)
                skin_y = y
                # A pointed chin tuft extends below the chin, rooted in its upper portion.
                if kind == "goatee":
                    skin_y = max(y, cy - 0.035 * hh)
                z = project(x, skin_y)
                if kind == "goatee" and y < cy - 0.055 * hh:
                    z -= min(0.025 * hh, (cy - 0.055 * hh - y) * 0.4)
                fade = max(0, 1 - s * s) ** 0.7
                ridges = (0.5 + 0.5 * math.cos(220 * (x - cx) / hh + 11 * (y - cy) / hh)) ** 4
                offset = hh * (0.001 + fade * (0.008 + 0.003 * ridges)) if layer == 0 else -0.001 * hh
                points.append([x, y, z + offset])
    layer_size = 1 + count * rows
    faces = []
    for layer in (0, 1):
        base = layer * layer_size
        for j in range(count):
            face = [base, base + 1 + j, base + 1 + (j + 1) % count]
            faces.append(face if layer == 0 else face[::-1])
        for row in range(rows - 1):
            for j in range(count):
                a, b = base + 1 + row * count + j, base + 1 + row * count + (j + 1) % count
                face = [a, a + count, b + count, b]
                faces.append(face if layer == 0 else face[::-1])
    start = 1 + (rows - 1) * count
    for j in range(count):
        a, b = start + j, start + (j + 1) % count
        faces.append([a, a + layer_size, b + layer_size, b])
    return points, faces


def measure_groom_spec(spec):
    """Strict single-component cage contract; body/generic gates stay untouched."""
    points = [_point(point) for point in spec["vertices"]]
    faces = spec["faces"]
    _require(4 <= len(points) <= MAX_GROOM_VERTICES and len(faces) <= MAX_GROOM_TRIANGLES, "groom_budget_exceeded")
    edges, neighbors = defaultdict(list), defaultdict(set)
    volume, minimum_area, triangle_count = 0.0, float("inf"), 0
    for face in faces:
        _require(isinstance(face, (list, tuple)) and 3 <= len(face) <= 4, "groom_face_invalid")
        _require(
            len(set(face)) == len(face) and all(type(i) is int and 0 <= i < len(points) for i in face),
            "groom_index_invalid",
        )
        for a, b in zip(face, face[1:] + face[:1]):
            edges[min(a, b), max(a, b)].append((a, b))
            neighbors[a].add(b)
            neighbors[b].add(a)
        a = points[face[0]]
        for i in range(1, len(face) - 1):
            b, c = points[face[i]], points[face[i + 1]]
            area = math.sqrt(_dot(_cross(_sub(b, a), _sub(c, a)), _cross(_sub(b, a), _sub(c, a)))) / 2
            minimum_area = min(minimum_area, area)
            volume += _dot(a, _cross(b, c)) / 6
            triangle_count += 1
    _require(triangle_count <= MAX_GROOM_TRIANGLES, "groom_budget_exceeded")
    _require(all(len(v) == 2 and v[0] == v[1][::-1] for v in edges.values()), "groom_not_closed_oriented")
    seen, pending = set(), [0]
    while pending:
        current = pending.pop()
        if current not in seen:
            seen.add(current)
            pending.extend(neighbors[current] - seen)
    _require(len(seen) == len(points), "groom_not_single_component")
    _require(minimum_area > 1e-12 and volume > 1e-12, "groom_degenerate_or_inward")
    return {
        "vertices": len(points),
        "triangles": triangle_count,
        "components": 1,
        "closed_oriented": True,
        "signed_volume": volume,
        "minimum_triangle_area": minimum_area,
    }


def build_period_groom(canonical, character):
    values = resolve_period_groom(character)
    if values is None:
        return []
    frame = canonical["head_frame"]
    origin, hh = _point(frame["origin"]), frame["height"]
    _require(_number(hh, 0.08, 0.65), "groom_head_height_invalid")
    triangles = _triangles(canonical, origin[1] - 0.65 * hh)
    scalp, scalp_faces, _ = _scalp(triangles, origin, hh, values)
    bun, bun_faces = _bun(origin, hh, values)
    shapes = [("PeriodSweptScalp", scalp, scalp_faces), ("PeriodBun", bun, bun_faces)]
    if values["facial_hair"] != "none":
        landmarks = canonical["landmarks"]
        eye_y = (landmarks["eyeL"][1] + landmarks["eyeR"][1]) / 2
        chin_y = landmarks["chin"][1]
        mouth_y = chin_y + 0.35 * (eye_y - chin_y)
        project = _face_projector(triangles, origin, hh)
        for sign, label in ((-1, "R"), (1, "L")):
            vertices, faces = _beard_patch(
                project,
                sign * 0.067 * hh,
                mouth_y + 0.038 * hh,
                0.068 * hh * values["moustache_width"],
                0.020 * hh,
                hh,
                "moustache",
                sign,
            )
            shapes.append(("PeriodMoustache" + label, vertices, faces))
        vertices, faces = _beard_patch(
            project, 0, chin_y + 0.052 * hh, 0.095 * hh, 0.095 * hh * values["goatee_length"], hh, "goatee", 0
        )
        shapes.append(("PeriodGoatee", vertices, faces))
    specs = [
        {"name": name, "vertices": vertices, "faces": faces, "material": "AnatomyHair", "group": "trusted_groom_group"}
        for name, vertices, faces in shapes
    ]
    if values["temple_gray"] > 0:
        specs.extend(
            {
                "name": name,
                "vertices": vertices,
                "faces": faces,
                "material": "AnatomyHairGray",
                "group": "trusted_groom_group",
            }
            for name, vertices, faces in _gray_temples(scalp, origin, hh, values["temple_gray"])
        )
    _require(
        len(specs) <= MAX_GROOM_SPECS and sum(len(s["vertices"]) for s in specs) <= MAX_GROOM_VERTICES,
        "groom_budget_exceeded",
    )
    measures = [measure_groom_spec(spec) for spec in specs]
    _require(sum(m["triangles"] for m in measures) <= MAX_GROOM_TRIANGLES, "groom_budget_exceeded")
    return specs
