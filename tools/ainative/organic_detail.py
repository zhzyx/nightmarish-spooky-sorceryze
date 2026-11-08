"""Bounded stdlib-only organic loft frames and repeated hollow-cup geometry.

All coordinates are Godot Y-up meters. No files, Blender, code strings, imports
from model data, or arbitrary callbacks are evaluated by this data interpreter.
"""

import math

MAX_PATTERNS = 8
MAX_CUPS = 512
CUP_SEGMENTS = 20
CUP_RING_COUNT = 6


def _require(ok, code):
    if not ok:
        raise ValueError(code)


def _number(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def _unit(vector):
    length = math.sqrt(sum(v * v for v in vector))
    _require(length > 1e-12, "organic_frame_zero_length")
    return [v / length for v in vector]


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def transported_frames(sections):
    """The exact fixed frame shared by loft geometry and detail placement."""
    frames = []
    previous = None
    for index, section in enumerate(sections):
        before = sections[max(0, index - 1)]["center"]
        after = sections[min(len(sections) - 1, index + 1)]["center"]
        tangent = _unit([b - a for a, b in zip(before, after)])
        right = list(previous) if previous is not None else [1, 0, 0]
        right = [a - b * _dot(right, tangent) for a, b in zip(right, tangent)]
        if _dot(right, right) < 1e-8:
            right = [0, 0, 1]
            right = [a - b * _dot(right, tangent) for a, b in zip(right, tangent)]
        right = _unit(right)
        previous = list(right)
        front = _unit(_cross(right, tangent))
        angle = math.radians(section["roll"])
        cosine, sine = math.cos(angle), math.sin(angle)
        # right x tangent = front, hence tangent x right = -front.
        rolled_right = [a * cosine - b * sine for a, b in zip(right, front)]
        rolled_front = [a * sine + b * cosine for a, b in zip(right, front)]
        frames.append(
            dict(
                center=list(section["center"]),
                right=rolled_right,
                front=rolled_front,
                tangent=tangent,
                radius=list(section["radius"]),
            )
        )
    return frames


def end_caps_schema():
    properties = dict(
        start=dict(type="string", enum=["flat", "rounded"]),
        end=dict(type="string", enum=["flat", "rounded"]),
        depth=dict(type="number", minimum=0.25, maximum=1.5),
    )
    return dict(
        anyOf=[
            dict(type="null"),
            dict(type="object", properties=properties, required=list(properties), additionalProperties=False),
        ],
        description="Loft end caps only; null preserves flat. Rounded dome depth is endpoint maximum radius times dimensionless depth.",
    )


def patterns_schema(name_schema):
    properties = dict(
        name=dict(type="string", minLength=1, maxLength=48, pattern=r"^[A-Za-z0-9_-]{1,48}$"),
        source_region=name_schema,
        material=name_schema,
        count=dict(type="integer", minimum=3, maximum=48),
        rows=dict(type="integer", enum=[1, 2]),
        start=dict(type="number", minimum=0, maximum=0.9),
        end=dict(type="number", minimum=0.1, maximum=1),
        side_degrees=dict(type="number", minimum=-180, maximum=180),
        row_spread_degrees=dict(type="number", minimum=0, maximum=90),
        radius=dict(type="number", minimum=0.003, maximum=0.15),
        radius_tip_scale=dict(type="number", minimum=0.2, maximum=1),
        depth=dict(type="number", minimum=0.15, maximum=0.75),
    )
    return dict(
        anyOf=[
            dict(type="null"),
            dict(
                type="array",
                maxItems=MAX_PATTERNS,
                items=dict(type="object", properties=properties, required=list(properties), additionalProperties=False),
            ),
        ],
        description="Fixed hollow suction cups along named lofts. count is PER ROW; cup centers occupy equal arc-length bin centers in [start,end), total count*rows <=512. radius is source-loft LOCAL Godot meters BEFORE the same source TRS; depth is radius multiplier. side_degrees 0=local right,90=local front. Completion annotations name each pattern, not generated cups.",
    )


def validate_caps(surface):
    caps = surface.get("end_caps")
    if caps is None:
        return
    _require(
        surface["kind"] == "loft" and isinstance(caps, dict) and set(caps) == {"start", "end", "depth"},
        "loft_end_caps_fields_invalid",
    )
    _require(
        caps["start"] in ("flat", "rounded")
        and caps["end"] in ("flat", "rounded")
        and _number(caps["depth"], 0.25, 1.5),
        "loft_end_caps_values_invalid",
    )


def validate_patterns(plan, name_ok):
    patterns = plan.get("repeat_patterns")
    if patterns is None:
        return
    _require(isinstance(patterns, list) and len(patterns) <= MAX_PATTERNS, "repeat_patterns_invalid")
    names = {region["name"] for region in plan["regions"]}
    if plan.get("character") is not None:
        names.add("character")
    materials = {material["name"] for material in plan["materials"]}
    regions = {region["name"]: region for region in plan["regions"]}
    total = 0
    fields = {
        "name",
        "source_region",
        "material",
        "count",
        "rows",
        "start",
        "end",
        "side_degrees",
        "row_spread_degrees",
        "radius",
        "radius_tip_scale",
        "depth",
    }
    for pattern in patterns:
        _require(isinstance(pattern, dict) and set(pattern) == fields, "repeat_pattern_fields_invalid")
        _require(
            name_ok(pattern["name"])
            and pattern["name"] not in names
            and len(pattern["name"]) <= 48
            and pattern["name"].isascii()
            and all(character.isalnum() or character in "_-" for character in pattern["name"]),
            "repeat_pattern_name_invalid",
        )
        names.add(pattern["name"])
        _require(
            isinstance(pattern["source_region"], str)
            and pattern["source_region"] in regions
            and regions[pattern["source_region"]]["surface"]["kind"] == "loft",
            "repeat_pattern_source_invalid",
        )
        _require(
            isinstance(pattern["material"], str) and pattern["material"] in materials, "repeat_pattern_material_invalid"
        )
        _require(
            type(pattern["count"]) is int
            and 3 <= pattern["count"] <= 48
            and type(pattern["rows"]) is int
            and pattern["rows"] in (1, 2),
            "repeat_pattern_count_invalid",
        )
        total += pattern["count"] * pattern["rows"]
        _require(
            _number(pattern["start"], 0, 0.9) and _number(pattern["end"], 0.1, 1) and pattern["start"] < pattern["end"],
            "repeat_pattern_interval_invalid",
        )
        for key, low, high in (
            ("side_degrees", -180, 180),
            ("row_spread_degrees", 0, 90),
            ("radius", 0.003, 0.15),
            ("radius_tip_scale", 0.2, 1),
            ("depth", 0.15, 0.75),
        ):
            _require(_number(pattern[key], low, high), "repeat_pattern_value_invalid:" + key)
        _require(pattern["rows"] == 1 or pattern["row_spread_degrees"] > 0, "repeat_pattern_rows_overlap")
    _require(total <= MAX_CUPS, "repeat_pattern_budget_exceeded")


def sample_frame(frames, fraction):
    lengths = [0.0]
    for a, b in zip(frames, frames[1:]):
        lengths.append(lengths[-1] + math.dist(a["center"], b["center"]))
    _require(lengths[-1] > 1e-12, "organic_path_zero_length")
    distance = fraction * lengths[-1]
    index = min(
        len(frames) - 2, next((i for i in range(len(frames) - 1) if lengths[i + 1] >= distance), len(frames) - 2)
    )
    t = (distance - lengths[index]) / max(1e-12, lengths[index + 1] - lengths[index])
    a, b = frames[index : index + 2]
    result = {
        key: [x + (y - x) * t for x, y in zip(a[key], b[key])] for key in ("center", "tangent", "right", "radius")
    }
    result["tangent"] = _unit(result["tangent"])
    right = result["right"]
    result["right"] = _unit([v - axis * _dot(right, result["tangent"]) for v, axis in zip(right, result["tangent"])])
    result["front"] = _unit(_cross(result["right"], result["tangent"]))
    return result


def cup_mesh(center, axis, tangent, radius, depth):
    """Closed solid dish: underside, outer wall, lip, concave bowl and floor."""
    axis = _unit(axis)
    u = _unit(_cross(tangent, axis))
    v = _unit(_cross(axis, u))
    profile = [(0.62, -0.10), (0.84, 0), (1.0, depth), (0.76, depth + 0.06), (0.58, 0.16), (0.16, 0.10)]
    vertices = []
    for radial, height in profile:
        for index in range(CUP_SEGMENTS):
            angle = 2 * math.pi * index / CUP_SEGMENTS
            vertices.append([
                center[i] + radius * (radial * (u[i] * math.cos(angle) + v[i] * math.sin(angle)) + height * axis[i])
                for i in range(3)
            ])
    faces = []
    for layer in range(len(profile) - 1):
        for index in range(CUP_SEGMENTS):
            a = layer * CUP_SEGMENTS + index
            b = layer * CUP_SEGMENTS + (index + 1) % CUP_SEGMENTS
            faces.append([a, b, b + CUP_SEGMENTS, a + CUP_SEGMENTS])
    # The lower disk and cavity floor close the material volume, not the mouth.
    faces.extend([
        list(reversed(range(CUP_SEGMENTS))),
        list(range((len(profile) - 1) * CUP_SEGMENTS, len(profile) * CUP_SEGMENTS)),
    ])
    return vertices, faces


def cup_triangle_budget(subdivision):
    """Exact Catmull-Clark/triangulated counts, including both 20-gon caps."""
    _require(type(subdivision) is int and 0 <= subdivision <= 2, "organic_subdivision_invalid")
    quads = CUP_SEGMENTS * (CUP_RING_COUNT - 1)
    if subdivision == 0:
        return 2 * quads + 2 * (CUP_SEGMENTS - 2)
    return 2 * (4 * quads + 2 * CUP_SEGMENTS) * 4 ** (subdivision - 1)


def expand_patterns(plan, interpolate_sections, max_triangles, max_vertices):
    """Trusted expansion; original input is never changed or semantically clamped."""
    patterns = plan.get("repeat_patterns") or []
    generated, measurements = [], []
    regions = {region["name"]: region for region in plan["regions"]}
    existing_names = set(regions)
    prior_source_placements = {}
    total = sum(pattern["count"] * pattern["rows"] for pattern in patterns)
    vertices_per_cup = CUP_SEGMENTS * CUP_RING_COUNT
    subdivision = plan["finish"]["subdivision"]
    _require(
        total * vertices_per_cup * 4**subdivision <= max_vertices
        and total * cup_triangle_budget(subdivision) <= max_triangles,
        "repeat_pattern_generated_budget_exceeded",
    )
    for pattern in patterns:
        source = regions[pattern["source_region"]]["surface"]
        frames = transported_frames(interpolate_sections(source["sections"]))
        count = 0
        placements = []
        source_placements = prior_source_placements.setdefault(pattern["source_region"], [])
        for row in range(pattern["rows"]):
            degrees = pattern["side_degrees"] + (row - (pattern["rows"] - 1) / 2) * pattern["row_spread_degrees"]
            angle = math.radians(degrees)
            cosine, sine = math.cos(angle), math.sin(angle)
            for index in range(pattern["count"]):
                t = (index + 0.5) / pattern["count"]
                frame = sample_frame(frames, pattern["start"] + (pattern["end"] - pattern["start"]) * t)
                rx = frame["radius"][1 if cosine >= 0 else 0]
                rz = frame["radius"][2 if sine >= 0 else 3]
                radius = pattern["radius"] * (1 + (pattern["radius_tip_scale"] - 1) * t)
                _require(radius <= 0.85 * min(rx, rz), "repeat_pattern_radius_exceeds_source_section")
                center = [
                    frame["center"][i] + frame["right"][i] * rx * cosine + frame["front"][i] * rz * sine
                    for i in range(3)
                ]
                axis = _unit([frame["right"][i] * cosine / rx + frame["front"][i] * sine / rz for i in range(3)])
                _require(
                    all(
                        math.dist(center, previous["center"]) >= 1.03 * (radius + previous["radius"])
                        for previous in source_placements
                    ),
                    "repeat_pattern_cup_overlap",
                )
                vertices, faces = cup_mesh(center, axis, frame["tangent"], radius, pattern["depth"])
                _require(
                    all(math.isfinite(v) and abs(v) <= 1000 for point in vertices for v in point),
                    "repeat_pattern_geometry_bounds_invalid",
                )
                name = pattern["name"] + "_R" + str(row + 1) + "_C" + str(index + 1).zfill(2)
                _require(name not in existing_names, "repeat_pattern_generated_name_collision")
                existing_names.add(name)
                placement = dict(
                    name=name,
                    center=center,
                    axis=axis,
                    radius=radius,
                    position=list(source["position"]),
                    rotation_degrees=list(source["rotation_degrees"]),
                    size=list(source["size"]),
                )
                placements.append(placement)
                source_placements.append(placement)
                shape = dict(
                    kind="cage",
                    position=list(source["position"]),
                    rotation_degrees=list(source["rotation_degrees"]),
                    size=list(source["size"]),
                    sections=[],
                    vertices=vertices,
                    faces=faces,
                )
                generated.append(dict(name=name, role="accessory", material=pattern["material"], surface=shape))
                count += 1
        measurements.append(
            dict(
                name=pattern["name"],
                source_region=pattern["source_region"],
                cups=count,
                rows=pattern["rows"],
                count_per_row=pattern["count"],
                hollow_closed_dishes=True,
                placements=placements,
            )
        )
    return generated, measurements
