"""Bounded neutral CC0 face relief for an already registered human silhouette.

Importing needs only the standard library. The caller supplies its NumPy module
and the fixed anatomy_body data; no image paths, executable data or model code
are accepted here. This is a neutral anatomical prior, not recovered identity.
Insufficient paired eye-region evidence leaves the original volume unchanged.
"""

import math

MAX_IMAGE_PIXELS = 16000000
MAX_GRID_CELLS = 1600000
MAX_FACE_CELLS = 65536
MAX_SOURCE_VERTICES = 16000
MAX_SOURCE_FACES = 16000
VERSION = 1


def _smoothstep(value, np):
    value = np.clip(value, 0, 1)
    return value * value * (3 - 2 * value)


def _smooth_rows(values, sigma, np):
    """Small fixed Gaussian, without a SciPy or image-model dependency."""
    radius = min(24, max(1, math.ceil(3 * sigma)))
    positions = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-0.5 * (positions / sigma) ** 2)
    kernel /= kernel.sum()
    padded = np.pad(values, (radius, radius), mode="edge")
    result = np.zeros_like(values, dtype=np.float64)
    for offset, weight in enumerate(kernel):
        result += weight * padded[offset : offset + len(values)]
    return result


def eye_registration(view, np):
    """Find paired dark eye-region candidates, not certified pupils or cameras."""
    rgb, mask = view["image"], view["mask"]
    height, top = view["pixel_height"], view["bounds"][1]
    if (
        rgb.ndim != 3
        or rgb.shape[2] < 3
        or mask.shape != rgb.shape[:2]
        or rgb.shape[0] * rgb.shape[1] > MAX_IMAGE_PIXELS
        or not math.isfinite(height)
        or height < 128
    ):
        return None
    luminance = rgb[:, :, :3] @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    candidates = []
    for y in range(max(0, top + round(0.05 * height)), min(len(mask), top + round(0.145 * height))):
        edges = np.flatnonzero(mask[y])
        if not max(26, 0.052 * height) <= len(edges) <= 0.155 * height:
            continue
        width = int(edges[-1] - edges[0] + 1)
        center = (edges[-1] + edges[0]) / 2
        cheeks, radius = max(2, round(0.09 * width)), max(1, round(0.032 * width))
        if y - radius < 0 or y + cheeks + 2 * radius >= len(mask):
            continue
        pair = []
        for sign in (-1, 1):
            low, high = (
                (center - width * 0.31, center - width * 0.105)
                if sign < 0
                else (
                    center + width * 0.105,
                    center + width * 0.31,
                )
            )
            best = (-1.0, None)
            for x in range(round(low), round(high) + 1):
                if x - radius < 0 or x + radius >= mask.shape[1] or not mask[y, x]:
                    continue
                dark = luminance[y - radius : y + radius + 1, x - radius : x + radius + 1].mean()
                below = luminance[y + cheeks : y + cheeks + 2 * radius + 1, x - radius : x + radius + 1].mean()
                mid = luminance[y - radius : y + radius + 1, round(center) - radius : round(center) + radius + 1].mean()
                score = float(0.7 * (below - dark) + 0.3 * (mid - dark))
                if math.isfinite(score) and score > best[0]:
                    best = (score, x)
            pair.append(best)
        if pair[0][1] is None or pair[1][1] is None:
            continue
        x1, x2 = pair[0][1], pair[1][1]
        score = min(pair[0][0], pair[1][0]) - 0.5 * abs(center - (x1 + x2) / 2) / width
        if score >= 0.095 and 0.28 * width <= x2 - x1 <= 0.53 * width:
            candidates.append((score, y, x1, x2, width))
    if not candidates:
        return None
    score, y, x1, x2, width = max(candidates)
    return dict(score=float(score), center=(x1 + x2) / 2, eyes_y=y, pupil_span=x2 - x1, head_width=width)


def _raster_front(points, faces, px, py, shape, np):
    """Front-facing triangles only: an aperture cannot see the rear skull."""
    output = np.full(shape, -np.inf, np.float64)
    triangles = np.concatenate((faces[:, [0, 1, 2]], faces[:, [0, 2, 3]]))
    normal = np.cross(
        points[triangles[:, 1]] - points[triangles[:, 0]], points[triangles[:, 2]] - points[triangles[:, 0]]
    )
    length = np.linalg.norm(normal, axis=1)
    triangles = triangles[normal[:, 2] > 0.12 * length]
    for indices in triangles:
        xx, yy, zz = px[indices], py[indices], points[indices, 2]
        low_x, high_x = max(0, math.floor(xx.min())), min(shape[1] - 1, math.ceil(xx.max()))
        low_y, high_y = max(0, math.floor(yy.min())), min(shape[0] - 1, math.ceil(yy.max()))
        if low_x > high_x or low_y > high_y:
            continue
        denominator = (yy[1] - yy[2]) * (xx[0] - xx[2]) + (xx[2] - xx[1]) * (yy[0] - yy[2])
        if abs(denominator) < 1e-10:
            continue
        gx, gy = np.meshgrid(np.arange(low_x, high_x + 1), np.arange(low_y, high_y + 1))
        a = ((yy[1] - yy[2]) * (gx - xx[2]) + (xx[2] - xx[1]) * (gy - yy[2])) / denominator
        b = ((yy[2] - yy[0]) * (gx - xx[2]) + (xx[0] - xx[2]) * (gy - yy[2])) / denominator
        c = 1 - a - b
        z = np.where((a >= -1e-8) & (b >= -1e-8) & (c >= -1e-8), a * zz[0] + b * zz[1] + c * zz[2], -np.inf)
        window = output[low_y : high_y + 1, low_x : high_x + 1]
        np.maximum(window, z, out=window)
    return output


def _close_eyes(surface, body_x, body_y, landmarks, np):
    """Closed analytic globe fronts fill the two fixed body-cage apertures."""
    span = abs(landmarks["eyeL"][0] - landmarks["eyeR"][0])
    radius = 0.19 * span
    count = 0
    for name in ("eyeL", "eyeR"):
        eye = landmarks[name]
        squared = radius * radius - (body_x[None, :] - eye[0]) ** 2 - (body_y[:, None] - eye[1]) ** 2
        valid = squared >= 0
        front = eye[2] + np.sqrt(np.maximum(0, squared))
        changed = valid & (front > surface)
        count += int(changed.sum())
        surface[valid] = np.maximum(surface[valid], front[valid])
    return count


def face_relief(front, xs, ys, centers, depth, np, anatomy_body, grid_height=512):
    """Return (target depth, blend weight) in caller voxel units, or None/skip.

    Caller retains its original rear surface and silhouette. Blend the front
    toward the target between the rear shell and the observed profile front. A
    strictly positive weight always has a finite target. Inputs are untouched.
    The source height-one neutral head is positioned by observed paired feature
    span/row; profile residual is smoothed, not independently reset each row.
    """
    skipped = dict(version=VERSION, applied=False, reason="no_supported_pair_of_eye_features")
    if (
        type(grid_height) is not int
        or not 128 <= grid_height <= 1024
        or len(xs) < 2
        or len(ys) < 2
        or len(xs) * len(ys) > MAX_GRID_CELLS
        or len(centers) != len(ys)
        or len(depth) != len(ys)
        or not all(np.asarray(value).ndim == 1 for value in (xs, ys, centers, depth))
        or not all(bool(np.isfinite(value).all()) for value in (xs, ys, centers, depth))
        or not bool((np.diff(xs) > 0).all() and (np.diff(ys) > 0).all() and (depth > 0).all())
        or not bool(np.allclose(np.diff(xs), xs[1] - xs[0], rtol=0.0001, atol=1e-8))
        or not bool(np.allclose(np.diff(ys), ys[1] - ys[0], rtol=0.0001, atol=1e-8))
    ):
        raise ValueError("face_grid_invalid")
    registration = eye_registration(front, np)
    if registration is None:
        return None, skipped
    points = np.asarray(anatomy_body.BODY_VERTICES, dtype=np.float64)
    faces = np.asarray(anatomy_body.BODY_FACES, dtype=np.int32)
    if (
        points.ndim != 2
        or points.shape[1] != 3
        or not 1 <= len(points) <= MAX_SOURCE_VERTICES
        or faces.ndim != 2
        or faces.shape[1] != 4
        or not 1 <= len(faces) <= MAX_SOURCE_FACES
        or not bool(np.isfinite(points).all())
        or int(faces.min()) < 0
        or int(faces.max()) >= len(points)
    ):
        raise ValueError("face_anatomy_data_invalid")
    landmarks = anatomy_body.BODY_LANDMARKS
    eye = landmarks["eyeL"]
    eye_span = eye[0] - landmarks["eyeR"][0]
    if not math.isfinite(eye_span) or not 0.02 <= eye_span <= 0.06:
        raise ValueError("face_anatomy_data_invalid")
    height = front["pixel_height"]
    scale = registration["pupil_span"] / eye_span
    cx, cy = registration["center"], registration["eyes_y"]
    x = front["center_x"] + np.asarray(xs) * height
    y = front["bounds"][1] + np.asarray(ys) * height
    use_x = np.flatnonzero(abs(x - cx) < registration["head_width"] * 0.49)
    use_y = np.flatnonzero((y > cy - scale * 0.060) & (y < cy + scale * 0.070))
    if len(use_x) < 16 or len(use_y) < 20 or len(use_x) * len(use_y) > MAX_FACE_CELLS:
        return None, dict(skipped, reason="insufficient_face_samples")
    px = (points[:, 0] * scale + cx - x[use_x[0]]) / (x[1] - x[0])
    py = ((eye[1] - points[:, 1]) * scale + cy - y[use_y[0]]) / (y[1] - y[0])
    selected = faces[(points[faces, 1].max(axis=1) > eye[1] - 0.09) & (points[faces, 1].min(axis=1) < eye[1] + 0.08)]
    surface = _raster_front(points, selected, px, py, (len(use_y), len(use_x)), np)
    body_x = (x[use_x] - cx) / scale
    body_y = eye[1] - (y[use_y] - cy) / scale
    eye_samples = _close_eyes(surface, body_x, body_y, landmarks, np)
    finite = np.isfinite(surface)
    good_rows = finite.sum(axis=1) >= 8
    if int(good_rows.sum()) < 20:
        return None, dict(skipped, reason="insufficient_frontal_anatomy_samples")
    # Fill only across rows supported by the frontal skin, never with rear hits.
    row_front = np.zeros(len(use_y), np.float64)
    support = np.zeros_like(surface)
    for row in np.flatnonzero(good_rows):
        valid = np.flatnonzero(finite[row])
        surface[row] = np.interp(np.arange(len(use_x)), valid, surface[row, valid])
        row_front[row] = float(np.quantile(surface[row, valid], 0.98))
        support[row] = _smoothstep((np.arange(len(use_x)) - valid[0]) / 3, np) * _smoothstep(
            (valid[-1] - np.arange(len(use_x))) / 3, np
        )
    row_front = np.interp(np.arange(len(use_y)), np.flatnonzero(good_rows), row_front[good_rows])
    pixels_to_voxels = grid_height / height
    source_to_voxels = scale * pixels_to_voxels
    observed_front = np.asarray(centers)[use_y] + np.asarray(depth)[use_y]
    residual = observed_front - row_front * source_to_voxels
    sigma = max(1.25, 0.005 * grid_height)
    residual = _smooth_rows(residual, sigma, np)
    target = surface * source_to_voxels + residual[:, None]
    target = np.minimum(target, observed_front[:, None])
    # A neutral jaw/neck must not collapse a thin observed slab toward its
    # rear surface. This limits anatomical relief, rather than repairing or
    # deleting any resulting geometry after volume extraction.
    maximum_inset = np.minimum(0.022 * source_to_voxels, 0.55 * np.asarray(depth)[use_y])
    target = np.maximum(target, observed_front[:, None] - maximum_inset[:, None])
    down = (y[use_y] - cy) / scale
    vertical = _smoothstep((down + 0.048) / 0.022, np) * _smoothstep((0.064 - down) / 0.018, np)
    lateral = _smoothstep((0.42 - abs(x[use_x] - cx) / registration["head_width"]) / 0.15, np)
    weight = vertical[:, None] * lateral[None, :] * good_rows[:, None]
    # Interpolate internal apertures between frontal lids/skin; fade unsupported
    # projection fringes instead of introducing a binary weight edge at holes.
    weight *= support
    target[weight <= 0] = np.nan
    result_depth = np.full((len(ys), len(xs)), np.nan, np.float32)
    result_weight = np.zeros_like(result_depth)
    result_depth[np.ix_(use_y, use_x)] = target
    result_weight[np.ix_(use_y, use_x)] = weight
    return (result_depth, result_weight), dict(
        version=VERSION,
        applied=True,
        method="front_facing_neutral_cc0_with_closed_eye_caps_and_smoothed_profile_residual",
        registration="paired_dark_front_eye_region_candidates_not_certified_pupils",
        confidence=registration["score"],
        applied_grid_samples=int((result_weight > 0).sum()),
        closed_eye_samples=eye_samples,
        profile_residual_sigma_voxels=sigma,
        maximum_inset_fraction_of_profile_half_depth=0.55,
        identity_recovered=False,
        exact_hidden_surface_recovery_claimed=False,
    )
