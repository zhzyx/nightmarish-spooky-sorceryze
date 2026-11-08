"""Fixed bounded shape-from-silhouette interpreter for trusted turnaround input.

Importing this module uses only the standard library. The host, never a model,
supplies the source path and registration path. Blender's bundled NumPy,
OpenImageIO and OpenVDB are imported only by build(). No image is executed,
no generated code is evaluated, and no case-specific landmarks are embedded.
"""

import hashlib
import json
import math
import re
import struct
import sys
import time
from pathlib import Path
from types import ModuleType

MAX_IMAGE_BYTES = 32 * 1024 * 1024
MAX_IMAGE_PIXELS = 16000000
MAX_CONFIG_BYTES = 65536
MAX_VOXELS = 64000000
MAX_VERTICES = 1000000
MAX_TRIANGLES = 2000000
MAX_GLB_BYTES = 64 * 1024 * 1024
GRID_HEIGHT = 512
BUILD_SECONDS = 300
VIEWS = ("front", "back", "profile_left_facing", "profile_right_facing")


class TurnaroundError(ValueError):
    def __init__(self, code, **details):
        super().__init__(code)
        self.code = code
        self.details = details


def require(condition, code, **details):
    if not condition:
        raise TurnaroundError(code, **details)


def _number(value, low, high):
    return type(value) in (int, float) and low <= value <= high and math.isfinite(value)


def validate_registration(value):
    require(
        isinstance(value, dict)
        and set(value) - {"face_prior"} == {"version", "source_sha256", "source_plan_sha256", "height", "panels"},
        "registration_fields_invalid",
    )
    require(type(value["version"]) is int and value["version"] == 1, "registration_version_invalid")
    for key in ("source_sha256", "source_plan_sha256"):
        require(
            isinstance(value[key], str) and re.fullmatch("[0-9a-f]{64}", value[key]) is not None,
            "registration_digest_invalid",
            field=key,
        )
    require(_number(value["height"], 0.2, 3.0), "registration_height_invalid")
    if "face_prior" in value:
        prior = value["face_prior"]
        require(
            isinstance(prior, dict)
            and set(prior) == {"helper_sha256", "body_sha256"}
            and all(isinstance(v, str) and re.fullmatch("[0-9a-f]{64}", v) for v in prior.values()),
            "registration_face_prior_invalid",
        )
    panels = value["panels"]
    require(isinstance(panels, list) and len(panels) == 3, "registration_panels_invalid")
    labels = []
    for panel in panels:
        require(isinstance(panel, dict) and set(panel) == {"view", "box"}, "registration_panel_fields_invalid")
        require(panel["view"] in VIEWS, "registration_view_invalid")
        labels.append(panel["view"])
        box = panel["box"]
        require(
            isinstance(box, list) and len(box) == 4 and all(_number(component, 0, 1) for component in box),
            "registration_box_invalid",
        )
        require(box[2] - box[0] >= 0.01 and box[3] - box[1] >= 0.02, "registration_box_empty")
    require(
        len(set(labels)) == 3
        and "front" in labels
        and "back" in labels
        and sum(label.startswith("profile_") for label in labels) == 1,
        "registration_views_not_unique",
    )
    for index, panel in enumerate(panels):
        a = panel["box"]
        for previous in panels[:index]:
            b = previous["box"]
            intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
            smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
            require(
                intersection / smaller <= 0.10, "registration_panels_overlap", views=[panel["view"], previous["view"]]
            )
    return value


def _deadline(deadline):
    require(time.monotonic() < deadline, "build_time_budget_exceeded")


def _bilinear(array, x, y, np):
    x = np.clip(x, 0, array.shape[1] - 1)
    y = np.clip(y, 0, array.shape[0] - 1)
    ix, iy = x.astype(np.int32), y.astype(np.int32)
    jx, jy = np.minimum(ix + 1, array.shape[1] - 1), np.minimum(iy + 1, array.shape[0] - 1)
    tx, ty = x - ix, y - iy
    if array.ndim == 3:
        tx, ty = tx[..., None], ty[..., None]
    return (array[iy, ix] * (1 - tx) + array[iy, jx] * tx) * (1 - ty) + (
        array[jy, ix] * (1 - tx) + array[jy, jx] * tx
    ) * ty


def _morph(mask, dilate, np):
    padded = np.pad(mask, 1, constant_values=False)
    slices = [padded[y : y + mask.shape[0], x : x + mask.shape[1]] for y in range(3) for x in range(3)]
    return np.logical_or.reduce(slices) if dilate else np.logical_and.reduce(slices)


def _components(mask, np):
    """Run-length union labeling, bounded by the prevalidated image dimensions."""
    parents = []
    runs = []
    previous = []

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for y, row in enumerate(mask):
        changes = np.flatnonzero(np.diff(np.r_[False, row, False].astype(np.int8)))
        current = []
        for left, end in changes.reshape(-1, 2):
            index = len(parents)
            parents.append(index)
            left, right = int(left), int(end) - 1
            for old_left, old_right, old_index in previous:
                if old_right >= left - 1 and old_left <= right + 1:
                    parents[find(index)] = find(old_index)
            current.append((left, right, index))
            runs.append((y, left, right, index))
        previous = current
    sizes = {}
    for _, left, right, index in runs:
        root = find(index)
        sizes[root] = sizes.get(root, 0) + right - left + 1
    return runs, sizes, find


def _single_subject(mask, np, view):
    runs, sizes, find = _components(mask, np)
    require(bool(sizes), "foreground_not_found", view=view)
    ordered = sorted(sizes, key=sizes.get, reverse=True)
    main = ordered[0]
    require(
        len(ordered) < 2 or sizes[ordered[1]] < max(24, 0.08 * sizes[main]),
        "multiple_subjects_or_disconnected_foreground",
        view=view,
        largest_components=[sizes[key] for key in ordered[:4]],
    )
    result = np.zeros_like(mask)
    for y, left, right, index in runs:
        if find(index) == main:
            result[y, left : right + 1] = True
    return result, sum(sizes.values()) - sizes[main]


def _display_orientation(image, orientation, np):
    require(type(orientation) is int and 1 <= orientation <= 8, "source_orientation_unsupported")
    if orientation == 2:
        return image[:, ::-1]
    if orientation == 3:
        return image[::-1, ::-1]
    if orientation == 4:
        return image[::-1]
    if orientation == 5:
        return np.swapaxes(image, 0, 1)
    if orientation == 6:
        return np.rot90(image, 3)
    if orientation == 7:
        return np.swapaxes(image, 0, 1)[::-1, ::-1]
    if orientation == 8:
        return np.rot90(image, 1)
    return image


def _reject_ground_shadow(rgb, foreground, background, np, view):
    """Reject bottom-connected proportional background darkening only.

    Warm feet and strongly black materials are not candidates. If subtracting
    same-hue darkening substantially truncates foreground height, gray footwear
    or other foreground is ambiguous and the build fails instead of inventing it.
    """
    denominator = float(np.dot(background, background))
    if denominator < 0.01:
        return foreground, 0
    factor = (rgb * background).sum(axis=2) / denominator
    chromatic_error = np.linalg.norm(rgb - factor[:, :, None] * background, axis=2)
    bottom_band = np.arange(len(rgb))[:, None] >= 0.75 * len(rgb)
    candidate = bottom_band & (factor >= 0.22) & (factor < 0.98) & (chromatic_error <= 0.014)
    runs, _, find = _components(~foreground | candidate, np)
    exterior = {
        find(index)
        for y, left, right, index in runs
        if y in (0, len(rgb) - 1) or left == 0 or right == rgb.shape[1] - 1
    }
    connected = np.zeros_like(foreground)
    for y, left, right, index in runs:
        if find(index) in exterior:
            connected[y, left : right + 1] = True
    removed = foreground & candidate & connected
    if not removed.any():
        return foreground, 0
    result = foreground & ~removed
    raw_y = np.flatnonzero(foreground.any(axis=1))
    clean_y = np.flatnonzero(result.any(axis=1))
    require(
        len(clean_y) > 0 and int(raw_y[-1] - clean_y[-1]) <= max(3, 0.018 * len(rgb)),
        "foreground_ground_shadow_ambiguous",
        view=view,
    )
    return result, int(removed.sum())


def _read_views(source, registration, np, oiio, deadline):
    image_input = oiio.ImageInput.open(str(source))
    require(image_input is not None, "image_decode_failed")
    try:
        spec = image_input.spec()
        require(
            64 <= spec.width <= 12000
            and 64 <= spec.height <= 12000
            and spec.width * spec.height <= MAX_IMAGE_PIXELS
            and spec.nchannels in (3, 4),
            "image_dimensions_or_channels_unsupported",
        )
        image = image_input.read_image(format=oiio.FLOAT)
        require(image is not None, "image_decode_failed")
        image = np.asarray(image, dtype=np.float32)
        require(
            image.shape == (spec.height, spec.width, spec.nchannels) and bool(np.isfinite(image).all()),
            "image_nonfinite_or_shape_invalid",
        )
        image = np.clip(image, 0, 1)
        orientation = int(spec.get_int_attribute("Orientation", 1))
        image = _display_orientation(image, orientation, np)
    finally:
        image_input.close()
    views = {}
    for panel in registration["panels"]:
        _deadline(deadline)
        label = panel["view"]
        x0, y0, x1, y1 = panel["box"]
        left, top, right, bottom = (
            math.floor(x0 * image.shape[1]),
            math.floor(y0 * image.shape[0]),
            math.ceil(x1 * image.shape[1]),
            math.ceil(y1 * image.shape[0]),
        )
        crop = image[top:bottom, left:right]
        require(crop.shape[0] >= 64 and crop.shape[1] >= 16, "panel_resolution_too_small", view=label)
        factor = min(1, 768 / crop.shape[0], 1024 / crop.shape[1])
        if factor < 1:
            xx, yy = np.meshgrid(
                np.linspace(0, crop.shape[1] - 1, round(crop.shape[1] * factor)),
                np.linspace(0, crop.shape[0] - 1, round(crop.shape[0] * factor)),
            )
            crop = _bilinear(crop, xx, yy, np).astype(np.float32)
        rgb = crop[:, :, :3]
        boundary = np.concatenate((
            rgb[:2].reshape(-1, 3),
            rgb[-2:].reshape(-1, 3),
            rgb[:, :2].reshape(-1, 3),
            rgb[:, -2:].reshape(-1, 3),
        ))
        background = np.median(boundary, axis=0)
        spread = np.linalg.norm(boundary - background, axis=1)
        require(float(np.quantile(spread, 0.90)) <= 0.12, "background_not_uniform_at_panel_boundary", view=label)
        threshold = min(0.12, max(0.040, 4 * float(np.median(spread)) + 0.012))
        residual = rgb - background
        mask = np.linalg.norm(residual, axis=2) > threshold
        if crop.shape[2] == 4 and float(crop[:, :, 3].min()) < 0.1:
            mask = crop[:, :, 3] >= 0.5
            source_mask = "source_alpha"
            shadow_pixels = 0
        else:
            mask, shadow_pixels = _reject_ground_shadow(rgb, mask, background, np, label)
            source_mask = "uniform_boundary_background_with_bottom_connected_proportional_shadow_rejection"
        mask = _morph(_morph(mask, True, np), False, np)
        mask, removed = _single_subject(mask, np, label)
        yy, xx = np.nonzero(mask)
        require(len(xx) >= 128, "foreground_too_small", view=label)
        bounds = [int(xx.min()), int(yy.min()), int(xx.max()), int(yy.max())]
        require(
            bounds[2] - bounds[0] >= 16 and bounds[3] - bounds[1] >= 64, "foreground_resolution_too_small", view=label
        )
        require(
            bounds[0] >= 2 and bounds[1] >= 2 and bounds[2] < mask.shape[1] - 2 and bounds[3] < mask.shape[0] - 2,
            "subject_touches_panel_boundary",
            view=label,
            foreground_bounds=bounds,
            working_resolution=[mask.shape[1], mask.shape[0]],
        )
        occupancy = float(mask.mean())
        require(0.025 <= occupancy <= 0.80, "foreground_occupancy_ambiguous", view=label, occupancy=occupancy)
        middle_rows = mask[bounds[1] + (bounds[3] - bounds[1]) // 3 : bounds[1] + 2 * (bounds[3] - bounds[1]) // 3]
        centers = []
        for row in middle_rows:
            indices = np.flatnonzero(row)
            if len(indices):
                centers.append((indices[0] + indices[-1]) / 2)
        center = float(np.median(centers)) if centers else (bounds[0] + bounds[2]) / 2
        views[label] = dict(
            image=rgb,
            mask=mask,
            bounds=bounds,
            center_x=center,
            pixel_height=bounds[3] - bounds[1],
            panel=panel,
            metrics=dict(
                view=label,
                method=source_mask,
                foreground_pixels=int(mask.sum()),
                occupancy=occupancy,
                background_srgb=background.tolist(),
                contrast_threshold=threshold,
                source_exif_orientation_applied=orientation,
                removed_bottom_connected_shadow_pixels=shadow_pixels,
                removed_small_image_components_pixels=removed,
                bounds_in_working_crop=bounds,
                working_resolution=[mask.shape[1], mask.shape[0]],
            ),
        )
    return views


def _edt_1d(values, np):
    n = len(values)
    vertices = np.empty(n, dtype=np.int32)
    borders = np.empty(n + 1, dtype=np.float64)
    result = np.empty(n, dtype=np.float64)
    nearest = np.empty(n, dtype=np.int32)
    k = 0
    vertices[0], borders[0], borders[1] = 0, -1e30, 1e30
    for q in range(1, n):
        while True:
            p = int(vertices[k])
            crossing = ((values[q] + q * q) - (values[p] + p * p)) / (2 * q - 2 * p)
            if crossing > borders[k] or k == 0:
                break
            k -= 1
        k += 1
        vertices[k], borders[k], borders[k + 1] = q, crossing, 1e30
    k = 0
    for q in range(n):
        while borders[k + 1] < q:
            k += 1
        p = int(vertices[k])
        result[q], nearest[q] = (q - p) ** 2 + values[p], p
    return result, nearest


def _distance_to(features, np):
    """Exact separable Euclidean transform plus nearest feature coordinates."""
    require(bool(features.any()), "distance_transform_has_no_features")
    values = np.where(features, 0.0, 1e12)
    horizontal = np.empty_like(values)
    near_x = np.empty(features.shape, dtype=np.int32)
    for y in range(len(values)):
        horizontal[y], near_x[y] = _edt_1d(values[y], np)
    result = np.empty_like(values)
    near_y = np.empty(features.shape, dtype=np.int32)
    for x in range(values.shape[1]):
        result[:, x], near_y[:, x] = _edt_1d(horizontal[:, x], np)
    xx = np.broadcast_to(np.arange(values.shape[1]), values.shape)
    closest_x = near_x[near_y, xx]
    return np.sqrt(result).astype(np.float32), near_y, closest_x


def _smooth(array, sigma, axis, np):
    radius = max(1, math.ceil(3 * sigma))
    offsets = np.arange(-radius, radius + 1)
    weights = np.exp(-0.5 * (offsets / sigma) ** 2)
    weights /= weights.sum()
    padding = [(0, 0)] * array.ndim
    padding[axis] = (radius, radius)
    padded = np.pad(array, padding, mode="edge")
    result = np.zeros_like(array, dtype=np.float32)
    for index, weight in enumerate(weights):
        slices = [slice(None)] * array.ndim
        slices[axis] = slice(index, index + array.shape[axis])
        result += padded[tuple(slices)] * weight
    return result


def _skeleton(mask, np):
    """Fixed topology-preserving two-subiteration binary thinning."""
    result = mask.copy()
    for _ in range(256):
        changed = False
        for second in (False, True):
            p = np.pad(result, 1, constant_values=False)
            neighbors = [
                p[:-2, 1:-1],
                p[:-2, 2:],
                p[1:-1, 2:],
                p[2:, 2:],
                p[2:, 1:-1],
                p[2:, :-2],
                p[1:-1, :-2],
                p[:-2, :-2],
            ]
            count = sum(value.astype(np.uint8) for value in neighbors)
            transitions = sum((~a & b).astype(np.uint8) for a, b in zip(neighbors, neighbors[1:] + neighbors[:1]))
            a, b, c, d = (neighbors[index] for index in (0, 2, 4, 6))
            products = (a & b & d) | (a & c & d) if second else (a & b & c) | (b & c & d)
            remove = result & (count >= 2) & (count <= 6) & (transitions == 1) & ~products
            if remove.any():
                result[remove] = False
                changed = True
        if not changed:
            break
    require(bool(result.any()), "silhouette_skeleton_empty")
    return result


def _registered_mask(view, xs, ys, mirror, np):
    u = view["center_x"] + (-xs if mirror else xs) * view["pixel_height"]
    v = view["bounds"][1] + ys * view["pixel_height"]
    xx, yy = np.meshgrid(u, v)
    sampled = _bilinear(view["mask"].astype(np.float32), xx, yy, np)
    outside = (xx < 0) | (xx >= view["mask"].shape[1]) | (yy < 0) | (yy >= view["mask"].shape[0])
    sampled[outside] = 0
    return sampled >= 0.5


def _balanced_pair_ellipses(mask, front, back, np):
    """Full observed profile depth for two similar separated frontal branches.

    A narrow frontal foot can be long in the profile. Limiting its depth to a
    frontal medial radius incorrectly turns it into an ankle. Both opposing
    silhouettes must support a balanced pair; the lateral ellipse is centered
    on each actual branch. Three-branch arm/torso rows retain local depth caps.
    """
    ellipses = np.zeros(mask.shape, dtype=np.float32)
    confidence = np.zeros(len(mask), dtype=np.float32)

    def intervals(row):
        return [
            (int(a), int(b))
            for a, b in np.flatnonzero(np.diff(np.r_[False, row, False].astype(np.int8))).reshape(-1, 2)
            if b - a >= 3
        ]

    for y, row in enumerate(mask):
        groups = intervals(row)
        if len(groups) != 2 or len(intervals(front[y])) != 2 or len(intervals(back[y])) != 2:
            continue
        widths = [b - a for a, b in groups]
        balance = min(widths) / max(widths)
        if balance < 0.55 or groups[1][0] - groups[0][1] < 2:
            continue
        confidence[y] = float(_soft_range(0.55, 0.80, balance, np))
        for a, b in groups:
            center, radius = (a + b - 1) / 2, (b - a) / 2
            ellipses[y, a:b] = np.sqrt(np.maximum(0, 1 - ((np.arange(a, b) - center) / radius) ** 2))
    # Track the descendants of the longest stable balanced split. Tiny toe
    # fragments and one foot reaching the ground first do not become new limbs
    # and must not switch the depth model back to an ankle-width cap.
    support_rows = np.flatnonzero(mask.any(axis=1))
    if not len(support_rows):
        return ellipses, confidence
    lower_half = (support_rows[0] + support_rows[-1]) // 2
    stable = (confidence > 0.5) & (np.arange(len(mask)) >= lower_half)
    runs = np.flatnonzero(np.diff(np.r_[False, stable, False].astype(np.int8))).reshape(-1, 2)
    tracked = np.zeros(len(mask), dtype=bool)
    if len(runs):
        start, end = max(runs, key=lambda pair: pair[1] - pair[0])
        if end - start >= 8:
            anchor = int((start + end) // 2)
            groups = intervals(mask[anchor])
            centers = [(a + b - 1) / 2 for a, b in groups]
            widths = [b - a for a, b in groups]
            for y in range(anchor, len(mask)):
                pixels = np.flatnonzero(mask[y])
                if not len(pixels):
                    break
                middle = (centers[0] + centers[1]) / 2
                if mask[y, int((centers[0] + centers[1]) / 2)]:
                    break  # Rejoined observations no longer support two independently tracked feet.
                descendants = [pixels[pixels < middle], pixels[pixels >= middle]]
                if all(len(group) for group in descendants) and descendants[1][0] - descendants[0][-1] <= 1:
                    break
                valid = True
                for index, group in enumerate(descendants):
                    if len(group):
                        center = (group[0] + group[-1]) / 2
                        if abs(center - centers[index]) > max(5, 2 * widths[index]):
                            valid = False
                if not valid:
                    break
                ellipses[y] = 0
                for index, group in enumerate(descendants):
                    if not len(group):
                        continue
                    left, right = int(group[0]), int(group[-1]) + 1
                    center, radius = (left + right - 1) / 2, (right - left) / 2
                    ellipses[y, left:right] = np.sqrt(
                        np.maximum(0, 1 - ((np.arange(left, right) - center) / radius) ** 2)
                    )
                    centers[index] = center
                    widths[index] = max(3, right - left)
                confidence[y] = 1
                tracked[y] = True
    confidence = _smooth(confidence, 2.0, 0, np) * (confidence > 0)
    confidence[tracked] = 1
    return ellipses, confidence


def _fixed_face_module(name, expected_sha):
    require(name in ("turnaround_face", "anatomy_body"), "face_prior_source_mismatch")
    path = Path(__file__).with_name(name + ".py")
    require(path.is_file() and not path.is_symlink(), "face_prior_source_mismatch")
    source = path.read_bytes()
    require(
        hashlib.sha256(source).hexdigest() == expected_sha,
        "face_prior_source_mismatch",
    )
    # These two bundled modules are fixed host code. Compile the very bytes
    # checked above, bypassing timestamp-based bytecode caches.
    module = ModuleType(name)
    module.__file__ = str(path)
    exec(compile(source, str(path), "exec"), module.__dict__)
    return module


def _volume(views, np, deadline, face_prior=None):
    front, back = views["front"], views["back"]
    profile = next(value for key, value in views.items() if key.startswith("profile_"))
    half_width = max(
        max(abs(view["bounds"][side] - view["center_x"]) for side in (0, 2)) / view["pixel_height"]
        for view in (front, back)
    )
    xs = (
        np.arange(-math.ceil(half_width * GRID_HEIGHT) - 4, math.ceil(half_width * GRID_HEIGHT) + 5, dtype=np.float32)
        / GRID_HEIGHT
    )
    ys = np.arange(-4, GRID_HEIGHT + 5, dtype=np.float32) / GRID_HEIGHT
    mf = _registered_mask(front, xs, ys, False, np)
    mb = _registered_mask(back, xs, ys, True, np)
    union = int((mf | mb).sum())
    iou = float((mf & mb).sum() / max(1, union))
    require(iou >= 0.50, "front_back_silhouettes_inconsistent", intersection_over_union=iou)
    mask = mf & mb
    mask, removed = _single_subject(mask, np, "registered_front_back_intersection")
    require(removed <= 0.01 * int(mask.sum()), "registered_silhouettes_disconnect_anatomy")
    distance, _, _ = _distance_to(~mask, np)
    outside_distance, _, _ = _distance_to(mask, np)
    contour_distance = distance - outside_distance
    skeleton = _skeleton(mask, np)
    _, near_y, near_x = _distance_to(skeleton, np)
    radius = distance[near_y, near_x]
    radius = _smooth(_smooth(radius, 1.3, 0, np), 1.3, 1, np)
    radius = np.maximum(radius, 1)
    paired_ellipses, paired_confidence = _balanced_pair_ellipses(mask, mf, mb, np)
    _deadline(deadline)
    row_bounds = []
    for row in profile["mask"]:
        indexes = np.flatnonzero(row)
        row_bounds.append([float(indexes[0]), float(indexes[-1])] if len(indexes) else [float("nan"), float("nan")])
    row_bounds = np.asarray(row_bounds)
    for channel in range(2):
        valid = np.isfinite(row_bounds[:, channel])
        row_bounds[:, channel] = np.interp(
            np.arange(len(row_bounds)), np.flatnonzero(valid), row_bounds[valid, channel]
        )
        row_bounds[:, channel] = _smooth(row_bounds[:, channel], 1.5, 0, np)
    py = profile["bounds"][1] + ys * profile["pixel_height"]
    left, right = [np.interp(py, np.arange(len(row_bounds)), row_bounds[:, channel]) for channel in range(2)]
    orientation = -1 if profile["panel"]["view"] == "profile_left_facing" else 1
    centers = orientation * ((left + right) / 2 - profile["center_x"]) / profile["pixel_height"] * GRID_HEIGHT
    depth = np.maximum(1, (right - left) / 2 / profile["pixel_height"] * GRID_HEIGHT)
    z_min, z_max = math.floor(float((centers - depth).min())) - 5, math.ceil(float((centers + depth).max())) + 5
    zs = np.arange(z_min, z_max + 1, dtype=np.float32)
    shape = (len(xs), len(ys), len(zs))
    require(math.prod(shape) <= MAX_VOXELS, "voxel_budget_exceeded", dimensions=list(shape), voxels=math.prod(shape))
    field = np.full(shape, -3, dtype=np.float32)
    face = None
    face_sampling = {}
    if face_prior:
        helper = _fixed_face_module("turnaround_face", face_prior["helper_sha256"])
        anatomy = _fixed_face_module("anatomy_body", face_prior["body_sha256"])
        face, observed = helper.face_relief(front, xs, ys, centers, depth, np, anatomy, GRID_HEIGHT)
        face_sampling["face_geometry"] = {**observed, **face_prior}
    for y in range(len(ys)):
        _deadline(deadline)
        if not 0 <= ys[y] <= 1:
            continue
        # Local silhouette medial thickness bounds branch depth, so an arm is
        # not blindly extruded through the entire torso's profile thickness.
        rz = np.minimum(depth[y], radius[y] * 1.30)
        fraction = np.clip(distance[y] / radius[y], 0, 1)
        rounded = np.sqrt(np.maximum(0, 1 - (1 - fraction) ** 2))
        extent = rz * rounded * (1 - paired_confidence[y]) + depth[y] * paired_ellipses[y] * paired_confidence[y]
        high, low = centers[y] + extent, centers[y] - extent
        if face is not None:
            target, weights = face
            active = weights[y] > 0
            # Keep both measured silhouettes. The prior only shapes the front
            # between the rear shell and the observed sagittal envelope.
            fitted = np.clip(target[y, active], low[active] + 1, centers[y] + depth[y])
            high[active] += weights[y, active] * (fitted - high[active])
        row = np.minimum(high[:, None] - zs[None, :], zs[None, :] - low[:, None])
        # A continuous signed contour field avoids a three-cell artificial
        # jump immediately outside the silhouette before Gaussian filtering.
        row = np.minimum(row, (contour_distance[y] - 0.40)[:, None])
        field[:, y, :] = np.clip(row, -3, 3)
    for axis, sigma in ((0, 0.65), (1, 0.90), (2, 0.80)):
        field = _smooth(field, sigma, axis, np)
    return (
        field,
        (float(xs[0]) * GRID_HEIGHT, -4.0, float(zs[0])),
        dict(
            dimensions=list(shape),
            voxels=math.prod(shape),
            front_back_iou=iou,
            intersection_discarded_image_pixels=removed,
            fixed_height_samples=GRID_HEIGHT,
            local_depth_radius_factor=1.30,
            paired_frontal_branch_rows=int((paired_confidence > 0).sum()),
            paired_branch_depth_policy="shared_observed_profile_depth_with_tracked_terminal_descendants",
            gaussian_sigma_voxels=[0.65, 0.90, 0.80],
            top_bottom_only_alignment=True,
            **face_sampling,
        ),
        profile,
    )


def _quality(points, faces, np):
    import bmesh
    import bpy

    mesh = bpy.data.meshes.new("TrustedTurnaroundQualityOnly")
    mesh.from_pydata(points.tolist(), [], faces.tolist())
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        require(
            all(vertex.is_manifold for vertex in bm.verts) and all(edge.is_manifold for edge in bm.edges),
            "surface_not_closed_vertex_and_edge_manifold",
        )
        remaining = set(bm.verts)
        components = 0
        component_vertices = []
        while remaining:
            components += 1
            require(components <= 32, "surface_component_measurement_budget_exceeded")
            pending = [remaining.pop()]
            members = []
            while pending:
                vertex = pending.pop()
                members.append(vertex.index)
                for edge in vertex.link_edges:
                    neighbor = edge.other_vert(vertex)
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        pending.append(neighbor)
            component_vertices.append(members)
        if components != 1:
            summaries = []
            labels = np.empty(len(points), dtype=np.int32)
            for index, members in enumerate(component_vertices):
                labels[members] = index
            for index, members in enumerate(component_vertices):
                subset = points[members].astype(np.float64)
                triangles = points[faces[labels[faces[:, 0]] == index]].astype(np.float64) - subset.mean(axis=0)
                volume = float(
                    np.einsum("ij,ij->i", triangles[:, 0], np.cross(triangles[:, 1], triangles[:, 2])).sum() / 6
                )
                summaries.append(
                    dict(
                        vertices=len(members),
                        triangles=len(triangles),
                        signed_volume=volume,
                        bounds_min=subset.min(axis=0).tolist(),
                        bounds_max=subset.max(axis=0).tolist(),
                    )
                )
            raise TurnaroundError(
                "surface_disconnected",
                components=components,
                measurements=sorted(summaries, key=lambda item: item["vertices"], reverse=True),
            )
        volume = float(bm.calc_volume(signed=True))
        require(math.isfinite(volume) and volume > 1e-12, "surface_volume_not_positive")
        area = (
            np.linalg.norm(
                np.cross(points[faces[:, 1]] - points[faces[:, 0]], points[faces[:, 2]] - points[faces[:, 0]]), axis=1
            )
            / 2
        )
        require(
            bool(np.isfinite(area).all()) and float(area.min()) > 1e-12,
            "surface_degenerate_triangles",
            minimum_area=float(area.min()),
        )
        return dict(
            body_components=components, body_manifold=True, body_volume=volume, minimum_triangle_area=float(area.min())
        )
    finally:
        bm.free()
        bpy.data.meshes.remove(mesh)


def _projection_visibility(screen, down, depth, faces, np):
    """Bounded rasterized reconstructed-surface visibility in voxel pixels.

    Unadaptive VDB triangles span at most neighboring grid cells. Rasterize
    their actual barycentric depth, then include exact vertex samples for very
    thin triangles. This is visibility of the inferred mesh, not recovered
    visibility/depth of the unknown original subject.
    """
    minimum = float(screen.min())
    width = int(math.ceil(float(screen.max() - minimum))) + 5
    px = np.clip(np.rint(screen - minimum).astype(np.int32) + 2, 0, width - 1)
    py = np.clip(np.rint(down).astype(np.int32) + 4, 0, GRID_HEIGHT + 8)
    zbuffer = np.full((GRID_HEIGHT + 9, width), -1e20, dtype=np.float32)
    np.maximum.at(zbuffer, (py, px), depth)
    sx = (screen[faces] - minimum + 2).astype(np.float32)
    sy = (down[faces] + 4).astype(np.float32)
    dz = depth[faces].astype(np.float32)
    low_x = np.floor(sx.min(axis=1)).astype(np.int32)
    low_y = np.floor(sy.min(axis=1)).astype(np.int32)
    span = np.maximum(sx.max(axis=1) - sx.min(axis=1), sy.max(axis=1) - sy.min(axis=1))
    require(float(span.max()) <= 3.01, "surface_projection_triangle_span_invalid")
    ax, bx, cx = sx[:, 0], sx[:, 1], sx[:, 2]
    ay, by, cy = sy[:, 0], sy[:, 1], sy[:, 2]
    denominator = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    valid = np.abs(denominator) > 1e-10
    safe = np.where(valid, denominator, 1)
    for oy in range(5):
        yy = low_y + oy
        for ox in range(5):
            xx = low_x + ox
            wa = ((by - cy) * (xx - cx) + (cx - bx) * (yy - cy)) / safe
            wb = ((cy - ay) * (xx - cx) + (ax - cx) * (yy - cy)) / safe
            wc = 1 - wa - wb
            inside = (
                valid
                & (wa >= -1e-5)
                & (wb >= -1e-5)
                & (wc >= -1e-5)
                & (xx >= 0)
                & (xx < width)
                & (yy >= 0)
                & (yy < GRID_HEIGHT + 9)
            )
            values = wa * dz[:, 0] + wb * dz[:, 1] + wc * dz[:, 2]
            np.maximum.at(zbuffer, (yy[inside], xx[inside]), values[inside])
    gap = np.maximum(0, zbuffer[py, px] - depth - 0.25)
    return np.exp(-((gap / 1.25) ** 2))


def _chromaticity(colors, np):
    return colors / (colors.sum(axis=-1, keepdims=True) + 0.05)


def _soft_range(low, high, values, np):
    t = np.clip((values - low) / (high - low), 0, 1)
    return t * t * (3 - 2 * t)


def _other_branch_affinity(view, x, down, profile_color, mirror, np):
    """Appearance evidence for a different horizontal silhouette branch.

    Branches come from masks, without person labels or body coordinates. The
    bounded vertical tolerance covers modest differences in turnaround poses.
    """
    mask, image = view["mask"], view["image"]
    maximum = 16
    low = np.full((len(mask), maximum), np.nan, dtype=np.float32)
    high = low.copy()
    palette = np.full((len(mask), maximum, 3), np.nan, dtype=np.float32)
    counts = np.zeros(len(mask), dtype=np.int32)
    for row, values in enumerate(mask):
        edges = np.flatnonzero(np.diff(np.r_[False, values, False].astype(np.int8))).reshape(-1, 2)
        edges = [(int(a), int(b)) for a, b in edges if b - a >= 2]
        if not 2 <= len(edges) <= maximum:
            continue
        counts[row] = len(edges)
        for index, (a, b) in enumerate(edges):
            low[row, index], high[row, index] = a, b
            pixels = image[max(0, row - 2) : min(len(mask), row + 3), a:b]
            valid = mask[max(0, row - 2) : min(len(mask), row + 3), a:b]
            palette[row, index] = np.median(pixels[valid], axis=0)
    if not counts.any():
        return np.zeros(len(x), dtype=np.float32)
    u = view["center_x"] + (-x if mirror else x) / GRID_HEIGHT * view["pixel_height"]
    rows = np.rint(view["bounds"][1] + down / GRID_HEIGHT * view["pixel_height"]).astype(np.int32)
    tolerance = max(2, round(0.080 * view["pixel_height"]))
    target = _chromaticity(profile_color, np)
    affinity = np.zeros(len(x), dtype=np.float32)
    for offset in (-tolerance, -(tolerance // 2), 0, tolerance // 2, tolerance):
        rr = np.clip(rows + offset, 0, len(mask) - 1)
        for branch in range(maximum):
            valid = (counts[rr] > 1) & ((u < low[rr, branch] - 2) | (u > high[rr, branch] + 2))
            difference = np.linalg.norm(target - _chromaticity(palette[rr, branch], np), axis=1)
            score = 1 - _soft_range(0.025, 0.080, difference, np)
            affinity = np.maximum(affinity, np.where(valid & np.isfinite(score), score, 0))
    return affinity


def _colors(points_pixels, normals, faces, views, np, deadline):
    colors, weights = [], []
    x, down, z = points_pixels[:, 0], points_pixels[:, 1], points_pixels[:, 2]
    for label, view in views.items():
        _deadline(deadline)
        if label == "front":
            screen, depth, facing = x, z, normals[:, 2]
        elif label == "back":
            screen, depth, facing = -x, -z, -normals[:, 2]
        elif label == "profile_left_facing":
            screen, depth, facing = -z, x, normals[:, 0]
        else:
            screen, depth, facing = z, -x, -normals[:, 0]
        u = view["center_x"] + screen / GRID_HEIGHT * view["pixel_height"]
        v = view["bounds"][1] + down / GRID_HEIGHT * view["pixel_height"]
        inner = _morph(view["mask"], False, np)
        require(bool(inner.any()), "color_sampling_interior_empty", view=label)
        _, nearest_y, nearest_x = _distance_to(inner, np)
        clean = view["image"][nearest_y, nearest_x]
        colors.append(_bilinear(clean, u, v, np))
        visible = _projection_visibility(screen, down, depth, faces, np)
        weights.append(np.maximum(0, facing) ** 4 * visible)
    weights = np.asarray(weights)
    samples = np.asarray(colors)
    labels = list(views)
    front, back = labels.index("front"), labels.index("back")
    side = next(index for index, label in enumerate(labels) if label.startswith("profile_"))
    chroma = _chromaticity(samples, np)
    pair_difference = np.linalg.norm(chroma[front] - chroma[back], axis=1)
    agreement = 1 - _soft_range(0.045, 0.120, pair_difference, np)
    side_difference = np.minimum(
        np.linalg.norm(chroma[side] - chroma[front], axis=1), np.linalg.norm(chroma[side] - chroma[back], axis=1)
    )
    conflict = _soft_range(0.025, 0.090, side_difference, np)
    affinity = np.maximum(
        _other_branch_affinity(views["front"], x, down, samples[side], False, np),
        _other_branch_affinity(views["back"], x, down, samples[side], True, np),
    )
    disputed = agreement * conflict * affinity
    weights[side] *= np.exp(-16 * disputed)
    # Never inject the opposite observation into every vertex. Unobserved
    # grazing regions fall back to the dominant signed facing front/back.
    unobserved = weights.sum(axis=0) < 0.002
    choose_front = normals[:, 2] >= 0
    weights[front] += (unobserved & choose_front).astype(np.float32)
    weights[back] += (unobserved & ~choose_front).astype(np.float32)
    rgb = (samples * weights[:, :, None]).sum(axis=0) / weights.sum(axis=0)[:, None]
    linear = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    return np.column_stack((np.clip(linear, 0, 1), np.ones(len(linear)))).astype("<f4"), dict(
        profile_branch_conflict_vertices=int((disputed > 0.5).sum()),
        dominant_observation_fallback_vertices=int(unobserved.sum()),
        opposite_observation_unconditional_mix=False,
        angular_exponent=4,
        branch_vertical_tolerance_fraction=0.080,
    )


def _glb(points, normals, colors, faces, np):
    payload = bytearray()
    views, accessors = [], []

    def accessor(array, component, kind, target, bounds=False):
        array = np.ascontiguousarray(array)
        offset = len(payload)
        payload.extend(array.tobytes())
        payload.extend(b"\0" * (-len(payload) % 4))
        views.append(dict(buffer=0, byteOffset=offset, byteLength=array.nbytes, target=target))
        record = dict(bufferView=len(views) - 1, componentType=component, count=len(array), type=kind)
        if bounds:
            record.update(min=array.min(axis=0).tolist(), max=array.max(axis=0).tolist())
        accessors.append(record)
        return len(accessors) - 1

    position = accessor(points.astype("<f4"), 5126, "VEC3", 34962, True)
    normal = accessor(normals.astype("<f4"), 5126, "VEC3", 34962)
    color = accessor(colors, 5126, "VEC4", 34962)
    indices = accessor(faces.reshape(-1).astype("<u4"), 5125, "SCALAR", 34963)
    document = dict(
        asset=dict(version="2.0", generator="Maliang fixed registered silhouette surface"),
        scene=0,
        scenes=[dict(nodes=[0])],
        nodes=[dict(mesh=0, name="Registered observed surface")],
        meshes=[
            dict(
                primitives=[
                    dict(
                        attributes={"POSITION": position, "NORMAL": normal, "COLOR_0": color},
                        indices=indices,
                        material=0,
                    )
                ]
            )
        ],
        materials=[
            dict(
                name="Observed source color with baked illumination",
                pbrMetallicRoughness=dict(baseColorFactor=[1, 1, 1, 1], roughnessFactor=0.89, metallicFactor=0),
            )
        ],
        buffers=[dict(byteLength=len(payload))],
        bufferViews=views,
        accessors=accessors,
    )
    encoded = json.dumps(document, separators=(",", ":"), allow_nan=False).encode("utf8")
    encoded += b" " * (-len(encoded) % 4)
    total = 28 + len(encoded) + len(payload)
    require(total <= MAX_GLB_BYTES, "glb_byte_budget_exceeded", bytes=total)
    return (
        struct.pack("<4sII", b"glTF", 2, total)
        + struct.pack("<I4s", len(encoded), b"JSON")
        + encoded
        + struct.pack("<I4s", len(payload), b"BIN\0")
        + payload
    )


def build(source_path, registration_path, output_path):
    started = time.monotonic()
    deadline = started + BUILD_SECONDS
    source, config_path, output = (Path(value).resolve() for value in (source_path, registration_path, output_path))
    require(source.is_file() and 0 < source.stat().st_size <= MAX_IMAGE_BYTES, "source_file_invalid_or_too_large")
    require(
        config_path.is_file() and 0 < config_path.stat().st_size <= MAX_CONFIG_BYTES,
        "registration_file_invalid_or_too_large",
    )
    require(output.suffix.lower() == ".glb" and output.parent.is_dir(), "output_path_invalid")
    receipt_path = output.with_name(output.name + ".receipt.json")
    require(not output.exists() and not receipt_path.exists(), "output_exists")
    raw_source, raw_config = source.read_bytes(), config_path.read_bytes()
    require(
        raw_source.startswith(b"\x89PNG\r\n\x1a\n") or raw_source.startswith(b"\xff\xd8\xff"),
        "source_format_unsupported",
    )
    try:
        registration = validate_registration(json.loads(raw_config.decode("utf8")))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise TurnaroundError("registration_json_invalid") from error
    source_sha = hashlib.sha256(raw_source).hexdigest()
    require(source_sha == registration["source_sha256"], "source_digest_mismatch")
    try:
        import numpy as np
        import OpenImageIO as oiio
        import openvdb
    except ImportError as error:
        raise TurnaroundError("blender_bundled_image_or_volume_dependency_unavailable") from error
    views = _read_views(source, registration, np, oiio, deadline)
    field, origin, sampling, profile = _volume(views, np, deadline, registration.get("face_prior"))
    grid = openvdb.FloatGrid(background=-3.0)
    grid.copyFromArray(field)
    _deadline(deadline)
    vertices, triangles, quads = grid.convertToPolygons(isovalue=0, adaptivity=0)
    del field, grid
    vertices = np.asarray(vertices, dtype=np.float64)
    triangles, quads = (
        np.asarray(triangles, dtype=np.int32).reshape(-1, 3),
        np.asarray(quads, dtype=np.int32).reshape(-1, 4),
    )
    faces = np.concatenate((triangles, quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]))
    require(
        3 <= len(vertices) <= MAX_VERTICES and 1 <= len(faces) <= MAX_TRIANGLES,
        "surface_geometry_budget_exceeded",
        vertices=len(vertices),
        triangles=len(faces),
    )
    require(bool(np.isfinite(vertices).all()), "surface_nonfinite")
    pixels = vertices + np.asarray(origin)
    # VDB array order is X, down-from-head Y, frontal Z. Convert to glTF Y-up.
    points = (
        np.column_stack((pixels[:, 0], GRID_HEIGHT - pixels[:, 1], pixels[:, 2])) / GRID_HEIGHT * registration["height"]
    )
    signed = np.einsum("ij,ij->i", points[faces[:, 0]], np.cross(points[faces[:, 1]], points[faces[:, 2]])).sum() / 6
    if signed < 0:
        faces = faces[:, [0, 2, 1]]
    normals = np.zeros_like(points)
    face_normals = np.cross(points[faces[:, 1]] - points[faces[:, 0]], points[faces[:, 2]] - points[faces[:, 0]])
    for channel in range(3):
        np.add.at(normals, faces[:, channel], face_normals)
    lengths = np.linalg.norm(normals, axis=1)
    require(bool((lengths > 1e-15).all()), "surface_vertex_normal_invalid")
    normals /= lengths[:, None]
    measured_height = float(points[:, 1].max() - points[:, 1].min())
    require(measured_height > 0, "surface_empty_height")
    points[:, 1] -= points[:, 1].min()
    normalization = registration["height"] / measured_height
    points = (points * normalization).astype(np.float32)
    quality = _quality(points, faces, np)
    _deadline(deadline)
    color, color_metrics = _colors(pixels, normals, faces, views, np, deadline)
    blob = _glb(points, normals, color, faces, np)
    require(
        hashlib.sha256(source.read_bytes()).hexdigest() == source_sha and config_path.read_bytes() == raw_config,
        "trusted_input_changed_during_build",
    )
    receipt = dict(
        ok=True,
        version=2,
        source_plan_sha256=registration["source_plan_sha256"],
        source_image_sha256=source_sha,
        registration_sha256=hashlib.sha256(raw_config).hexdigest(),
        builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        sha256=hashlib.sha256(blob).hexdigest(),
        output_sha256=hashlib.sha256(blob).hexdigest(),
        vertices=len(points),
        triangles=len(faces),
        bytes=len(blob),
        observed_colors=True,
        reconstructed_mesh_visibility="triangle_depth_raster_with_vertex_samples_and_soft_visibility",
        color_visibility_transition_voxels=1.25,
        color_consistency=color_metrics,
        exact_hidden_surface_recovery_claimed=False,
        **quality,
        sampling=sampling,
        panels=[value["metrics"] for value in views.values()],
        profile_orientation=profile["panel"]["view"],
        height=registration["height"],
        uniform_height_normalization=normalization,
        bounds_min=points.min(axis=0).tolist(),
        bounds_max=points.max(axis=0).tolist(),
        generated_code_executed=False,
        neural_weights_loaded=False,
        removed_3d_components=0,
        appearance_limitations=[
            "Source illumination is baked into observed vertex colors; this is not recovered intrinsic albedo.",
            "Occluded surfaces and depth within the silhouettes are inferred, not exact recovery.",
            "Registration aligns head and feet only; inconsistent poses or perspective are unsupported.",
            "Single subject and approximately uniform boundary background are required.",
        ],
        elapsed_seconds=time.monotonic() - started,
    )
    encoded = (json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf8")
    with output.open("xb") as stream:
        stream.write(blob)
    with receipt_path.open("xb") as stream:
        stream.write(encoded)
    return receipt


def main():
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    require(len(args) == 3, "builder_arguments_invalid")
    receipt = build(*args)
    print("MALIANG_TURNAROUND_BUILD_OK " + json.dumps(receipt, ensure_ascii=False, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        code = error.code if isinstance(error, TurnaroundError) else "unexpected_builder_failure"
        details = error.details if isinstance(error, TurnaroundError) else {"type": type(error).__name__}
        print(
            "MALIANG_TURNAROUND_BUILD_FAILED "
            + json.dumps(dict(ok=False, reason=code, details=details), ensure_ascii=False),
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(1)
