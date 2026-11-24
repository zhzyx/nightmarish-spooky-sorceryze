"""Multi-view, source-bound reconstruction of independent wearable garment shells.

The vision model supplies normalized visible-surface masks and a coverage claim.
Local triangle-ID renders determine actual source geometry. Only complete-visible
items with a closed, position-welded shell become ``wearable_shell`` artifacts.
"""

import base64
import copy
import hashlib
import json
import math
import shutil
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from api_planner import perform, validate_config
from extensions import canonical, require
from garment_auto import RENDER_VIEWS, _render
from geometry_repair import accessor_values
from garment_split import (
    BEHAVIORS,
    CATEGORIES,
    SLOTS,
    GarmentSource,
    _encode_glb,
    _extension_names,
    _identifier,
    _text,
    _write_new,
)
from provider_common import validate_jpeg, validate_png

SCHEMA_VERSION = 2
COVERAGE_STATES = ("complete_visible", "partial", "unknown")
MAX_IMAGE_BYTES = 32 * 1024 * 1024
MAX_REQUEST_BYTES = 48 * 1024 * 1024


def segmentation_schema():
    point = dict(type="array", minItems=2, maxItems=2, items=dict(type="number", minimum=0.0, maximum=1.0))
    polygon = dict(type="array", minItems=3, maxItems=32, items=point)
    mask = dict(
        type="object",
        properties=dict(
            view=dict(type="string", enum=list(RENDER_VIEWS)),
            polygons=dict(type="array", minItems=1, maxItems=8, items=polygon),
        ),
        required=["view", "polygons"],
        additionalProperties=False,
    )
    item = dict(
        type="object",
        properties=dict(
            id=dict(type="string"),
            label=dict(type="string"),
            category=dict(type="string", enum=list(CATEGORIES)),
            slot=dict(type="string", enum=list(SLOTS)),
            behavior=dict(type="string", enum=list(BEHAVIORS)),
            confidence=dict(type="number", minimum=0.0, maximum=1.0),
            evidence=dict(type="string"),
            needs_review=dict(type="boolean"),
            coverage=dict(type="string", enum=list(COVERAGE_STATES)),
            missing_regions=dict(type="array", maxItems=16, items=dict(type="string")),
            masks=dict(type="array", maxItems=len(RENDER_VIEWS), items=mask),
        ),
        required=[
            "id",
            "label",
            "category",
            "slot",
            "behavior",
            "confidence",
            "evidence",
            "needs_review",
            "coverage",
            "missing_regions",
            "masks",
        ],
        additionalProperties=False,
    )
    non_garment = dict(
        type="object",
        properties=dict(label=dict(type="string"), reason=dict(type="string")),
        required=["label", "reason"],
        additionalProperties=False,
    )
    return dict(
        type="object",
        properties=dict(
            schema_version=dict(type="integer", const=SCHEMA_VERSION),
            items=dict(type="array", items=item),
            non_garments=dict(type="array", items=non_garment),
            notes=dict(type="string"),
        ),
        required=["schema_version", "items", "non_garments", "notes"],
        additionalProperties=False,
    )


def segmentation_prompt(source):
    return (
        "Inspect every supplied MODEL VIEW independently as the same single character. Identify independently wearable "
        "garments, footwear, gloves, armor, shoulder pieces, bracers, belts, capes and mixed outfits. Group every visible "
        "panel belonging to one physical garment into that one item; never call one panel, sleeve, lower skirt or collar "
        "a complete garment. Keep embroidery and attached decoration with their parent garment. Use stable lowercase "
        "ASCII ids and separate genuinely independent left/right items. Hair, skin, weapons and non-worn props are "
        "non_garments.\n"
        "For each item, draw precise normalized visible-surface masks in every view where the item is visible. Coordinates "
        "are [x,y], origin TOP LEFT, range 0..1. Polygons must follow the actual garment boundary, exclude skin, hair and "
        "foreground overlapping items, and must not be bounding boxes. Use multiple polygons for disconnected visible "
        "islands of the same item. Do not paint inferred occluded surfaces into a view.\n"
        "Set coverage=complete_visible ONLY when the masks cover the item's complete visible outer surface across all "
        "supplied views, including front/back and both sides where present. Otherwise use partial or unknown and list "
        "missing_regions. complete_visible requires missing_regions=[]. A closed inner thickness will be reconstructed "
        "later, so unseen inner lining is not itself a missing visible region. Set needs_review=true for uncertain "
        "identity, sidedness, mask boundaries or coverage. Return one schema-conforming JSON object with no prose.\n"
        "Source is one immutable static GLB; local triangle-ID renders, not your text, will select the actual geometry. "
        + canonical(
            dict(
                source_sha256=source.sha256,
                coordinate_space="Y_up_+Z_front",
                views=list(RENDER_VIEWS),
                triangle_count=sum(len(entry["faces"]) for entry in source.primitives.values()),
            )
        )
    )


def _validate_simple_polygon(polygon):
    """Reject self-intersections that turn garment masks into diagonal holes."""
    points = [np.asarray(point, dtype=np.float64) for point in polygon]
    if len(points) < 3 or any(np.linalg.norm(points[index] - points[(index + 1) % len(points)]) <= 1e-12 for index in range(len(points))):
        raise ValueError("garment_segmentation_polygon_invalid")

    def orientation(a, b, c):
        return float((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))

    def intersects(a, b, c, d):
        ab_c, ab_d = orientation(a, b, c), orientation(a, b, d)
        cd_a, cd_b = orientation(c, d, a), orientation(c, d, b)
        if ab_c * ab_d < 0.0 and cd_a * cd_b < 0.0:
            return True
        for point, start, end, cross in ((c, a, b, ab_c), (d, a, b, ab_d), (a, c, d, cd_a), (b, c, d, cd_b)):
            if abs(cross) <= 1e-12 and (np.minimum(start, end) <= point).all() and (point <= np.maximum(start, end)).all():
                return True
        return False

    count = len(points)
    for first in range(count):
        a, b = points[first], points[(first + 1) % count]
        for second in range(first + 1, count):
            if second == first or second == (first + 1) % count or first == (second + 1) % count:
                continue
            c, d = points[second], points[(second + 1) % count]
            if intersects(a, b, c, d):
                raise ValueError("garment_segmentation_polygon_self_intersection")


def validate_segmentation(value):
    if not isinstance(value, dict) or set(value) != {"schema_version", "items", "non_garments", "notes"}:
        raise ValueError("garment_segmentation_invalid")
    if type(value["schema_version"]) is not int or value["schema_version"] != SCHEMA_VERSION:
        raise ValueError("garment_segmentation_invalid")
    if not isinstance(value["items"], list) or not isinstance(value["non_garments"], list):
        raise ValueError("garment_segmentation_invalid")
    if not isinstance(value["notes"], str) or len(value["notes"]) > 4096:
        raise ValueError("garment_segmentation_invalid")
    result = copy.deepcopy(value)
    identifiers = set()
    fields = {
        "id",
        "label",
        "category",
        "slot",
        "behavior",
        "confidence",
        "evidence",
        "needs_review",
        "coverage",
        "missing_regions",
        "masks",
    }
    for item in result["items"]:
        if not isinstance(item, dict) or set(item) != fields:
            raise ValueError("garment_segmentation_invalid")
        _identifier(item["id"])
        if item["id"] in identifiers:
            raise ValueError("garment_segmentation_duplicate_id")
        identifiers.add(item["id"])
        _text(item["label"], "garment_segmentation_invalid", 256)
        _text(item["evidence"], "garment_segmentation_invalid", 2048)
        if item["category"] not in CATEGORIES or item["slot"] not in SLOTS or item["behavior"] not in BEHAVIORS:
            raise ValueError("garment_segmentation_invalid")
        if type(item["confidence"]) not in (int, float) or not math.isfinite(item["confidence"]):
            raise ValueError("garment_segmentation_invalid")
        if not 0 <= float(item["confidence"]) <= 1 or not isinstance(item["needs_review"], bool):
            raise ValueError("garment_segmentation_invalid")
        if item["coverage"] not in COVERAGE_STATES:
            raise ValueError("garment_segmentation_invalid")
        missing = item["missing_regions"]
        if not isinstance(missing, list) or len(missing) > 16:
            raise ValueError("garment_segmentation_invalid")
        for region in missing:
            _text(region, "garment_segmentation_invalid", 256)
        if item["coverage"] == "complete_visible" and missing:
            raise ValueError("garment_segmentation_coverage_conflict")
        masks = item["masks"]
        if not isinstance(masks, list) or len(masks) > len(RENDER_VIEWS):
            raise ValueError("garment_segmentation_invalid")
        views = set()
        for mask in masks:
            if not isinstance(mask, dict) or set(mask) != {"view", "polygons"} or mask["view"] not in RENDER_VIEWS:
                raise ValueError("garment_segmentation_invalid")
            if mask["view"] in views or not isinstance(mask["polygons"], list) or not 1 <= len(mask["polygons"]) <= 8:
                raise ValueError("garment_segmentation_invalid")
            views.add(mask["view"])
            for polygon in mask["polygons"]:
                if not isinstance(polygon, list) or not 3 <= len(polygon) <= 32:
                    raise ValueError("garment_segmentation_invalid")
                for point in polygon:
                    if (
                        not isinstance(point, list)
                        or len(point) != 2
                        or any(type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1 for value in point)
                    ):
                        raise ValueError("garment_segmentation_invalid")
                _validate_simple_polygon(polygon)
    for entry in result["non_garments"]:
        if not isinstance(entry, dict) or set(entry) != {"label", "reason"}:
            raise ValueError("garment_segmentation_invalid")
        _text(entry["label"], "garment_segmentation_invalid", 256)
        _text(entry["reason"], "garment_segmentation_invalid", 2048)
    return result


def _image(path, view):
    path = Path(path).resolve()
    data = path.read_bytes()
    if not 0 < len(data) <= MAX_IMAGE_BYTES:
        raise ValueError("garment_segmentation_image_invalid")
    extension = path.suffix.lower()
    if extension == ".png":
        validate_png(data)
        mime = "image/png"
    elif extension in (".jpg", ".jpeg"):
        validate_jpeg(data)
        mime = "image/jpeg"
    else:
        raise ValueError("garment_segmentation_image_invalid")
    return dict(path=path, view=view, data=data, mime=mime, sha256=hashlib.sha256(data).hexdigest())


def _quality_review_schema(item_ids):
    defect = dict(
        type="object",
        properties=dict(
            view=dict(type="string", enum=list(RENDER_VIEWS)),
            kind=dict(type="string", enum=["missing_surface", "extraneous_surface", "proportion", "material", "other"]),
            observation=dict(type="string"),
        ),
        required=["view", "kind", "observation"],
        additionalProperties=False,
    )
    item = dict(
        type="object",
        properties=dict(
            id=dict(type="string", enum=list(item_ids)),
            passed=dict(type="boolean"),
            defects=dict(type="array", items=defect),
        ),
        required=["id", "passed", "defects"],
        additionalProperties=False,
    )
    return dict(
        type="object",
        properties=dict(
            schema_version=dict(type="integer", const=1),
            passed=dict(type="boolean"),
            items=dict(type="array", items=item),
            notes=dict(type="string"),
        ),
        required=["schema_version", "items", "passed", "notes"],
        additionalProperties=False,
    )


def _request_quality_review(config, inventory, source_views, generated_views, directory):
    config = validate_config(config)
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    item_ids = [item["id"] for item in inventory["items"]]
    schema = _quality_review_schema(item_ids)
    prompt = (
        "Compare each SOURCE character view with the EXTRACTED garment-collection view from the identical camera. "
        "Review every independently extracted garment, not the human body. Detect missing cloth, holes and point-like "
        "fragmentation in front, back, both sides AND top; also detect extraneous skin, hair, hands, boots or unrelated "
        "foreground items incorrectly included in a garment. Attached embroidery and ornament belong to their parent "
        "garment. A plausible front view cannot cancel a back, side or top defect. Mark an item passed only when no "
        "defects remain. The overall passed value is true only when every item passes. Return source-bound observations, "
        "not repair claims, using the exact supplied item ids."
        + canonical(dict(item_ids=item_ids, views=list(RENDER_VIEWS)))
    )
    content = [dict(type="text", text=prompt)]
    for source_entry, generated_entry in zip(source_views, generated_views):
        view = source_entry["view"]
        require(view == generated_entry["view"] and view in RENDER_VIEWS, "garment_quality_view_mismatch")
        for label, entry in (("SOURCE", source_entry), ("EXTRACTED", generated_entry)):
            content.append(dict(type="text", text=label + " " + view))
            content.append(
                dict(
                    type="image_url",
                    image_url=dict(url="data:" + entry["mime"] + ";base64," + base64.b64encode(entry["data"]).decode("ascii")),
                )
            )
    body = dict(
        model=config["model"],
        messages=[dict(role="user", content=content)],
        response_format=dict(type="json_schema", json_schema=dict(name="garment_quality_review", strict=True, schema=schema)),
        reasoning_effort="low",
        max_tokens=8192,
        stream=False,
    )
    raw = canonical(body).encode("utf-8")
    require(len(raw) <= MAX_REQUEST_BYTES, "garment_quality_request_too_large")
    (directory / "prompt.txt").write_text(prompt, encoding="utf-8")
    (directory / "schema.json").write_text(canonical(schema), encoding="utf-8")
    (directory / "api-request.json").write_bytes(raw)
    (directory / "planner-config.json").write_text(canonical(config), encoding="utf-8")
    plan_exists = (directory / "api-plan.json").is_file()
    receipt_exists = (directory / "api-receipt.json").is_file()
    require(plan_exists == receipt_exists, "garment_quality_response_incomplete")
    if not plan_exists:
        perform(config, directory)
    document = json.loads((directory / "api-plan.json").read_text(encoding="utf-8"))
    receipt = json.loads((directory / "api-receipt.json").read_text(encoding="utf-8"))
    require(
        receipt.get("request_sha256") == hashlib.sha256(raw).hexdigest()
        and receipt.get("instructions_sha256") == hashlib.sha256(canonical(document).encode("utf-8")).hexdigest(),
        "garment_quality_response_invalid",
    )
    require(
        isinstance(document, dict)
        and set(document) == {"schema_version", "items", "passed", "notes"}
        and document["schema_version"] == 1
        and type(document["passed"]) is bool
        and isinstance(document["items"], list)
        and isinstance(document["notes"], str),
        "garment_quality_response_invalid",
    )
    seen = set()
    computed = True
    for item in document["items"]:
        require(
            isinstance(item, dict)
            and set(item) == {"id", "passed", "defects"}
            and item["id"] in item_ids
            and item["id"] not in seen
            and type(item["passed"]) is bool
            and isinstance(item["defects"], list),
            "garment_quality_response_invalid",
        )
        seen.add(item["id"])
        for defect in item["defects"]:
            require(
                isinstance(defect, dict)
                and set(defect) == {"view", "kind", "observation"}
                and defect["view"] in RENDER_VIEWS
                and defect["kind"] in ("missing_surface", "extraneous_surface", "proportion", "material", "other"),
                "garment_quality_response_invalid",
            )
            _text(defect["observation"], "garment_quality_response_invalid", 2048)
        require(item["passed"] == (not item["defects"]), "garment_quality_response_invalid")
        computed = computed and item["passed"]
    require(seen == set(item_ids) and document["passed"] == computed, "garment_quality_response_invalid")
    return document


def _quality_gate(config, source, inventory, source_views, collection_path, evidence, godot_path, render_script, attempt=0):
    evidence = Path(evidence)
    quality = evidence / ("quality" if attempt == 0 else "quality-repair-%d" % attempt)
    receipt_path = quality / "quality-gate.json"
    collection_sha = hashlib.sha256(Path(collection_path).read_bytes()).hexdigest()
    if receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        require(
            receipt.get("source_sha256") == source.sha256 and receipt.get("collection_sha256") == collection_sha,
            "garment_quality_source_mismatch",
        )
        return receipt
    source_images = [_image(entry["path"], entry["label"]) for entry in source_views]
    points = np.concatenate([geometry["points"] for geometry in source.primitives.values()])
    camera_bounds = dict(min=points.min(axis=0).astype(float).tolist(), max=points.max(axis=0).astype(float).tolist())
    quality.mkdir(parents=True)
    (quality / "render").mkdir()
    generated_views = _render(collection_path, [], quality / "render", godot_path, render_script, camera_bounds=camera_bounds)
    generated_images = [_image(entry["path"], entry["label"]) for entry in generated_views]
    review = _request_quality_review(config, inventory, source_images, generated_images, quality / "review")
    receipt = dict(
        schema_version=1,
        source_sha256=source.sha256,
        camera_bounds=camera_bounds,
        collection_sha256=collection_sha,
        required_views=list(RENDER_VIEWS),
        source_views=[dict(view=entry["view"], path=str(entry["path"]), sha256=entry["sha256"]) for entry in source_images],
        generated_views=[dict(view=entry["view"], path=str(entry["path"]), sha256=entry["sha256"]) for entry in generated_images],
        review=review,
        visual_review_passed=review["passed"],
    )
    (quality / "quality-gate.json").write_text(canonical(receipt), encoding="utf-8")
    return receipt


def _view_mask_schema(view):
    point = dict(type="array", minItems=2, maxItems=2, items=dict(type="number", minimum=0.0, maximum=1.0))
    polygon = dict(type="array", minItems=3, maxItems=32, items=point)
    item = dict(
        type="object",
        properties=dict(
            id=dict(type="string"),
            visible=dict(type="boolean"),
            polygons=dict(type="array", maxItems=8, items=polygon),
            complete_visible=dict(type="boolean"),
            needs_review=dict(type="boolean"),
            missing_regions=dict(type="array", maxItems=8, items=dict(type="string")),
        ),
        required=["id", "visible", "polygons", "complete_visible", "needs_review", "missing_regions"],
        additionalProperties=False,
    )
    return dict(
        type="object",
        properties=dict(
            schema_version=dict(type="integer", const=2),
            view=dict(type="string", const=view),
            items=dict(type="array", items=item),
            notes=dict(type="string"),
        ),
        required=["schema_version", "view", "items", "notes"],
        additionalProperties=False,
    )


def _request_view_masks(config, semantic, entry, directory, comparison=None, guidance=""):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    view = entry["view"]
    schema = _view_mask_schema(view)
    prompt = (
        "The attached single MODEL VIEW is " + view + " of one character. The semantic garment inventory is supplied below. "
        "Return visible-surface polygons for these exact item ids in THIS view only. Coordinates are [x,y], origin TOP LEFT, "
        "range 0..1. Follow actual garment boundaries, exclude skin, hair and foreground overlaps, and never return a bounding "
        "box. Use multiple polygons for disconnected visible islands. For a base robe, coat or outfit, include its attached "
        "embroidery, chest plastron, ornamental panels and raised trim; never cut decoration-shaped holes out of the parent "
        "garment. Exclude a foreground region only when it is a separately listed independent wearable item. Do not infer "
        "occluded regions. Set visible=false and polygons=[] when the item is absent in this view. complete_visible=true only if every visible part of that item in "
        "this view is covered; otherwise false with missing_regions. Keep the exact supplied ids and never invent garments.\n"
        + canonical(
            dict(
                items=[
                    {key: item[key] for key in ("id", "label", "category", "slot", "behavior", "evidence")}
                    for item in semantic["items"]
                ]
            )
        )
    )
    if comparison is not None:
        require(comparison["view"] == view, "garment_segmentation_view_mismatch")
        prompt += (
            "\nThe second image is the EXTRACTED result from the same camera. Correct the SOURCE mask using these observed "
            "defects; fill unintended holes and exclude extraneous body, hand and footwear fragments. Return a simple "
            "non-self-intersecting outer contour for each continuous region; never let a polygon closing edge cut through "
            "the garment. Defect evidence:\n" + str(guidance)
        )
    content = [dict(type="text", text=prompt), dict(type="text", text="SOURCE MODEL VIEW " + view)]
    content.append(
        dict(
            type="image_url",
            image_url=dict(url="data:" + entry["mime"] + ";base64," + base64.b64encode(entry["data"]).decode("ascii")),
        )
    )
    if comparison is not None:
        content.append(dict(type="text", text="EXTRACTED MODEL VIEW " + view))
        content.append(
            dict(
                type="image_url",
                image_url=dict(url="data:" + comparison["mime"] + ";base64," + base64.b64encode(comparison["data"]).decode("ascii")),
            )
        )
    body = dict(
        model=config["model"],
        messages=[dict(role="user", content=content)],
        response_format=dict(type="json_schema", json_schema=dict(name="garment_view_masks", strict=True, schema=schema)),
        reasoning_effort="low",
        max_tokens=8192,
        stream=False,
    )
    raw = canonical(body).encode("utf-8")
    if len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("garment_segmentation_request_too_large")
    (directory / "prompt.txt").write_text(prompt, encoding="utf-8")
    (directory / "schema.json").write_text(canonical(schema), encoding="utf-8")
    (directory / "api-request.json").write_bytes(raw)
    (directory / "planner-config.json").write_text(canonical(config), encoding="utf-8")
    plan_exists = (directory / "api-plan.json").is_file()
    receipt_exists = (directory / "api-receipt.json").is_file()
    require(plan_exists == receipt_exists, "garment_segmentation_response_incomplete")
    if not plan_exists:
        perform(config, directory)
    receipt = json.loads((directory / "api-receipt.json").read_text(encoding="utf-8"))
    document = json.loads((directory / "api-plan.json").read_text(encoding="utf-8"))
    require(
        receipt.get("request_sha256") == hashlib.sha256(raw).hexdigest()
        and receipt.get("instructions_sha256") == hashlib.sha256(canonical(document).encode("utf-8")).hexdigest()
        and document.get("schema_version") == 2
        and document.get("view") == view
        and isinstance(document.get("items"), list)
        and isinstance(document.get("notes"), str),
        "garment_segmentation_response_invalid",
    )
    known = {item["id"] for item in semantic["items"]}
    seen = set()
    for item in document["items"]:
        require(
            isinstance(item, dict)
            and set(item) == {"id", "visible", "polygons", "complete_visible", "needs_review", "missing_regions"}
            and item["id"] in known
            and item["id"] not in seen
            and isinstance(item["visible"], bool)
            and isinstance(item["polygons"], list)
            and isinstance(item["complete_visible"], bool)
            and isinstance(item["needs_review"], bool)
            and isinstance(item["missing_regions"], list),
            "garment_segmentation_response_invalid",
        )
        seen.add(item["id"])
        require(item["visible"] or not item["polygons"], "garment_segmentation_response_invalid")
        for polygon in item["polygons"]:
            require(isinstance(polygon, list) and 3 <= len(polygon) <= 32, "garment_segmentation_response_invalid")
            for point in polygon:
                require(
                    isinstance(point, list)
                    and len(point) == 2
                    and all(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1 for value in point),
                    "garment_segmentation_response_invalid",
                )
            _validate_simple_polygon(polygon)
    return document


def _request_mask_batch(config, semantic, entry, directory):
    directory = Path(directory)
    if (directory / "api-plan.json").is_file() or len(semantic["items"]) <= 3:
        return _request_view_masks(config, semantic, entry, directory)
    midpoint = (len(semantic["items"]) + 1) // 2
    combined = dict(schema_version=2, view=entry["view"], items=[], notes="")
    for suffix, items in (("part-a", semantic["items"][:midpoint]), ("part-b", semantic["items"][midpoint:])):
        response = _request_mask_batch(config, dict(semantic, items=items), entry, directory / suffix)
        combined["items"].extend(response["items"])
    return combined


def request_segmentation(config, source, views, directory):
    from garment_inventory import request_inventory
    from garment_split import validate_inventory

    config = validate_config(config)
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    entries = [_image(entry["path"], entry["label"]) for entry in views]
    inspection = source.inspection()
    semantic_path = directory / "semantic" / "inventory.json"
    if semantic_path.is_file():
        receipt_path = directory / "semantic" / "inventory-receipt.json"
        require(receipt_path.is_file(), "garment_segmentation_response_incomplete")
        require(
            json.loads(receipt_path.read_text(encoding="utf-8")).get("source_sha256") == source.sha256,
            "garment_segmentation_source_mismatch",
        )
        semantic = validate_inventory(
            json.loads(semantic_path.read_text(encoding="utf-8")),
            {component["component_id"] for component in inspection["components"]},
        )
    else:
        semantic = request_inventory(config, inspection, views, directory / "semantic")
    merged = []
    responses = {}
    for entry in entries:
        view = entry["view"]
        full_directory = directory / ("view-" + view)
        if (full_directory / "api-plan.json").is_file():
            responses[view] = _request_view_masks(config, semantic, entry, full_directory)
            continue
        combined = dict(schema_version=2, view=view, items=[], notes="")
        for batch_index, start in enumerate(range(0, len(semantic["items"]), 6)):
            batch = dict(semantic, items=semantic["items"][start : start + 6])
            response = _request_mask_batch(
                config,
                batch,
                entry,
                directory / ("view-%s-batch-%d" % (view, batch_index)),
            )
            combined["items"].extend(response["items"])
        responses[view] = combined
    for base in semantic["items"]:
        item = dict(
            id=base["id"],
            label=base["label"],
            category=base["category"],
            slot=base["slot"],
            behavior=base["behavior"],
            confidence=base["confidence"],
            evidence=base["evidence"],
            needs_review=base["needs_review"],
            coverage="complete_visible",
            missing_regions=[],
            masks=[],
        )
        complete = True
        for view in RENDER_VIEWS:
            response = responses[view]
            candidates = [entry for entry in response["items"] if entry["id"] == item["id"]]
            require(len(candidates) <= 1, "garment_segmentation_response_invalid")
            if not candidates:
                continue
            mask = candidates[0]
            item["needs_review"] = item["needs_review"] or mask["needs_review"]
            complete = complete and mask["complete_visible"]
            for region in mask["missing_regions"]:
                text = view + ": " + str(region)
                if text not in item["missing_regions"]:
                    item["missing_regions"].append(text)
            if mask["visible"]:
                if not mask["polygons"]:
                    complete = False
                else:
                    item["masks"].append(dict(view=view, polygons=mask["polygons"]))
        views_with_masks = {mask["view"] for mask in item["masks"]}
        # Front/back plus at least one side are the minimum evidence for a
        # complete outer garment; top is supporting evidence, never sufficient.
        complete = complete and {"front", "back"} <= views_with_masks and bool({"left", "right"} & views_with_masks)
        item["coverage"] = "complete_visible" if complete else "partial"
        if not complete and not item["missing_regions"]:
            item["missing_regions"] = ["insufficient multi-view visible-surface coverage"]
        merged.append(item)
    result = validate_segmentation(
        dict(schema_version=2, items=merged, non_garments=semantic["non_garments"], notes=semantic["notes"])
    )
    (directory / "segmentation.json").write_text(canonical(result), encoding="utf-8")
    return result


EXCLUSION_ITEMS = (
    ("hair", "hair", "other"),
    ("exposed_skin", "exposed skin, face and neck; never gloves or clothing", "other"),
    ("hand_left", "anatomical left hand, including hand-shaped fragments beyond a cuff", "hand_left"),
    ("hand_right", "anatomical right hand, including hand-shaped fragments beyond a cuff", "hand_right"),
    ("footwear", "boots, shoes and soles that are not part of a robe or upper garment", "foot_right"),
    ("other_non_garment", "other visible non-garment content", "other"),
)


def _request_exclusions(config, source, views, directory):
    directory = Path(directory)
    path = directory / "exclusions.json"
    if path.is_file():
        result = json.loads(path.read_text(encoding="utf-8"))
        require(result.get("source_sha256") == source.sha256, "garment_exclusion_source_mismatch")
        return result
    semantic = dict(
        items=[
            dict(id=identifier, label=label, category="garment", slot=slot, behavior="skinned", evidence=label)
            for identifier, label, slot in EXCLUSION_ITEMS
        ]
    )
    responses = []
    for entry in views:
        response = _request_view_masks(config, semantic, _image(entry["path"], entry["label"]), directory / ("view-" + entry["label"]))
        responses.append(response)
    result = dict(schema_version=1, source_sha256=source.sha256, views=responses)
    directory.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical(result), encoding="utf-8")
    return result


def _excluded_pixels(exclusions, view, item, size):
    response = next((entry for entry in exclusions["views"] if entry["view"] == view), None)
    if response is None:
        return np.zeros((size[1], size[0]), dtype=bool)
    excluded = np.zeros((size[1], size[0]), dtype=bool)
    for entry in response["items"]:
        identifier = entry["id"]
        applies = identifier in ("hair", "exposed_skin", "other_non_garment")
        applies = applies or identifier == "hand_left" and item["slot"] != "hand_left"
        applies = applies or identifier == "hand_right" and item["slot"] != "hand_right"
        applies = applies or identifier == "footwear" and item["slot"] not in ("foot_left", "foot_right")
        if not applies or not entry["visible"]:
            continue
        mask, _area = _mask(entry, size)
        excluded |= mask
    return excluded


class _GlbWriter:
    def __init__(self, source, generator):
        self.source = source
        self.document = dict(
            asset=dict(version="2.0", generator=generator),
            scene=0,
            scenes=[dict(nodes=[])],
            nodes=[],
            meshes=[],
            buffers=[dict(byteLength=0)],
            bufferViews=[],
            accessors=[],
        )
        for key in ("samplers", "textures", "materials"):
            if key in source.document:
                self.document[key] = copy.deepcopy(source.document[key])
        self.images = copy.deepcopy(source.document.get("images", []))
        self.binary = bytearray()
        for image in self.images:
            if "bufferView" not in image:
                continue
            view = source.document["bufferViews"][image["bufferView"]]
            start = view.get("byteOffset", 0)
            image["bufferView"] = self._view(source.binary[start : start + view["byteLength"]])
        if self.images:
            self.document["images"] = self.images
        extensions = _extension_names(self.document.get("materials", [])) | _extension_names(
            self.document.get("textures", [])
        )
        if extensions:
            self.document["extensionsUsed"] = sorted(extensions)
            required = set(source.document.get("extensionsRequired", [])) & extensions
            if required:
                self.document["extensionsRequired"] = sorted(required)

    def _view(self, data, target=None):
        while len(self.binary) % 4:
            self.binary.append(0)
        view = dict(buffer=0, byteOffset=len(self.binary), byteLength=len(data))
        if target is not None:
            view["target"] = target
        self.binary.extend(data)
        self.document["bufferViews"].append(view)
        return len(self.document["bufferViews"]) - 1

    def _accessor(self, values, target, normalized=False, bounds=False):
        values = np.asarray(values)
        if values.ndim == 1:
            values = values.reshape(-1, 1)
        dtype = values.dtype.newbyteorder("<")
        component_types = {
            np.dtype("<i1"): 5120,
            np.dtype("<u1"): 5121,
            np.dtype("<i2"): 5122,
            np.dtype("<u2"): 5123,
            np.dtype("<u4"): 5125,
            np.dtype("<f4"): 5126,
        }
        if dtype not in component_types:
            raise ValueError("garment_complete_attribute_unsupported")
        values = np.ascontiguousarray(values.astype(dtype, copy=False))
        if dtype == np.dtype("<f4") and not np.isfinite(values).all():
            raise ValueError("garment_complete_output_invalid")
        widths = {1: "SCALAR", 2: "VEC2", 3: "VEC3", 4: "VEC4", 16: "MAT4"}
        if values.shape[1] not in widths:
            raise ValueError("garment_complete_attribute_unsupported")
        view = self._view(values.tobytes(), target)
        accessor = dict(
            bufferView=view,
            componentType=component_types[dtype],
            count=len(values),
            type=widths[values.shape[1]],
        )
        if normalized:
            accessor["normalized"] = True
        if bounds:
            accessor.update(min=values.min(axis=0).astype(float).tolist(), max=values.max(axis=0).astype(float).tolist())
        self.document["accessors"].append(accessor)
        return len(self.document["accessors"]) - 1

    def add_part(self, name, attributes, faces, material=None, normalized=None, source_node=None):
        output = dict(attributes={})
        for attribute, values in attributes.items():
            output["attributes"][attribute] = self._accessor(
                values,
                34962,
                bool(normalized and normalized.get(attribute)),
                bounds=attribute == "POSITION",
            )
        output["indices"] = self._accessor(np.asarray(faces, dtype="<u4").reshape(-1), 34963)
        if material is not None:
            output["material"] = material
        mesh_index = len(self.document["meshes"])
        self.document["meshes"].append(dict(name=name, primitives=[output]))
        node_index = len(self.document["nodes"])
        self.document["nodes"].append(dict(name=name, mesh=mesh_index))
        self.document["scenes"][0]["nodes"].append(node_index)

    def finish(self, extras):
        self.document["buffers"][0]["byteLength"] = len(self.binary)
        self.document["asset"]["extras"] = extras
        return _encode_glb(self.document, self.binary)


class _RiggedGlbWriter(_GlbWriter):
    """Compact generated geometry while preserving the complete original rig."""

    def __init__(self, source, generator, include_all_nodes=False):
        super().__init__(source, generator)
        self.document = copy.deepcopy(source.document)
        self.binary = bytearray(source.binary)
        self.include_all_nodes = include_all_nodes
        self.parts = {}

    def add_part(self, name, attributes, faces, material=None, normalized=None, source_node=None):
        require(type(source_node) is int and 0 <= source_node < len(self.document.get("nodes", [])), "garment_complete_node_invalid")
        self.parts.setdefault(source_node, []).append((name, attributes, faces, material, normalized))

    def finish(self, extras):
        for node_index, node in enumerate(self.document.get("nodes", [])):
            if "mesh" not in node:
                continue
            parts = self.parts.get(node_index)
            if not parts:
                if not self.include_all_nodes:
                    node.pop("mesh", None)
                    node.pop("skin", None)
                continue
            primitives = []
            for name, attributes, faces, material, normalized in parts:
                output = dict(attributes={})
                for attribute, values in attributes.items():
                    output["attributes"][attribute] = self._accessor(
                        values,
                        34962,
                        bool(normalized and normalized.get(attribute)),
                        bounds=attribute == "POSITION",
                    )
                output["indices"] = self._accessor(np.asarray(faces, dtype="<u4").reshape(-1), 34963)
                if material is not None:
                    output["material"] = material
                primitives.append(output)
            node["mesh"] = len(self.document["meshes"])
            self.document["meshes"].append(dict(name=node.get("name", "garment"), primitives=primitives))
        self.document["buffers"][0]["byteLength"] = len(self.binary)
        self.document["asset"]["extras"] = extras
        return _encode_glb(self.document, self.binary)


def _triangle_id_model(source, output, shift=0):
    require(shift in (0, 12), "garment_complete_triangle_id_shift_invalid")
    writer = (
        _RiggedGlbWriter(source, "AINative source triangle ID evidence", include_all_nodes=True)
        if source.rigged
        else _GlbWriter(source, "AINative source triangle ID evidence")
    )
    primitive_map = []
    global_start = 0
    for (node, primitive), geometry in source.primitives.items():
        faces = geometry["faces"]
        points = geometry["points"][faces].reshape(-1, 3).astype("<f4")
        uv0 = np.zeros((len(faces) * 3, 2), dtype="<f4")
        uv1 = np.zeros_like(uv0)
        identities = np.arange(global_start + 1, global_start + 1 + len(faces), dtype=np.uint32)
        chunks = (identities >> shift) & 0xFFF
        channels = np.stack((chunks & 15, (chunks >> 4) & 15, (chunks >> 8) & 15), axis=1)
        encoded = 0.2 + 0.8 * channels.astype(np.float64) / 15.0
        for face_index in range(len(faces)):
            uv0[face_index * 3 : face_index * 3 + 3] = encoded[face_index, :2]
            uv1[face_index * 3 : face_index * 3 + 3, 0] = encoded[face_index, 2]
        attributes = dict(POSITION=points, TEXCOORD_0=uv0, TEXCOORD_1=uv1)
        normalized = {}
        if source.rigged:
            for name in ("JOINTS_0", "WEIGHTS_0"):
                accessor_index = geometry["source"]["attributes"][name]
                values = source.accessor(accessor_index)
                attributes[name] = values[faces].reshape(-1, values.shape[-1])
                normalized[name] = source.document["accessors"][accessor_index].get("normalized") is True
        writer.add_part(
            "triangle-ids-%d-%d" % (node, primitive),
            attributes,
            np.arange(len(points), dtype="<u4").reshape(-1, 3),
            normalized=normalized,
            source_node=node,
        )
        primitive_map.append(dict(node=node, primitive=primitive, start=global_start, count=len(faces)))
        global_start += len(faces)
    data = writer.finish(
        dict(
            maliang_triangle_id_map=dict(
                schema_version=2,
                source_sha256=source.sha256,
                primitive_map=primitive_map,
                global_triangle_count=global_start,
                shift=shift,
                encoding="two_pass_4_bit_per_channel_triangle_index_plus_one",
            )
        )
    )
    _write_new(output, data)
    return primitive_map, hashlib.sha256(data).hexdigest()


def _position_weld(points):
    return np.unique(np.asarray(points), axis=0, return_inverse=True)[1]


def _edge_summary(welded_faces):
    directed = np.concatenate(
        (welded_faces[:, [0, 1]], welded_faces[:, [1, 2]], welded_faces[:, [2, 0]]), axis=0
    )
    undirected = np.sort(directed, axis=1)
    unique, first, inverse, counts = np.unique(
        undirected, axis=0, return_index=True, return_inverse=True, return_counts=True
    )
    boundary_indices = np.flatnonzero(counts == 1)
    nonmanifold_indices = np.flatnonzero(counts > 2)
    return dict(
        boundary=directed[first[boundary_indices]],
        boundary_count=len(boundary_indices),
        nonmanifold=unique[nonmanifold_indices],
        nonmanifold_count=len(nonmanifold_indices),
    )


def _vertex_normals(points, faces, welded):
    normals = np.zeros_like(points, dtype=np.float64)
    for triangle in welded[faces]:
        a, b, c = (int(value) for value in triangle)
        normal = np.cross(points[b] - points[a], points[c] - points[a])
        for index in (a, b, c):
            normals[index] += normal
    lengths = np.linalg.norm(normals, axis=1)
    lengths[lengths <= 1e-20] = 1.0
    return normals / lengths[:, None]


def _boundary_loops(boundary):
    unused = set(range(len(boundary)))
    loops = []
    while unused:
        first = min(unused)
        unused.remove(first)
        loop = [first]
        start, end = boundary[first]
        while end != start:
            candidates = [index for index in unused if boundary[index][0] == end]
            if not candidates:
                break
            next_index = min(candidates)
            unused.remove(next_index)
            loop.append(next_index)
            end = boundary[next_index][1]
        loops.append(loop)
    return loops


def _open_surface_primitive(source, key, face_ids, welded_positions):
    geometry = source.primitives[key]
    source_faces = geometry["faces"][face_ids]
    canonical_faces = np.sort(welded_positions[source_faces], axis=1)
    _unique, first = np.unique(canonical_faces, axis=0, return_index=True)
    source_faces = source_faces[first]
    used = np.unique(source_faces)
    remap = np.full(len(geometry["points"]), -1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    source_points = geometry["points"][used].astype(np.float64)
    unique_points, inverse = np.unique(source_points, axis=0, return_inverse=True)
    first = np.zeros(len(unique_points), dtype=np.int64)
    first[inverse] = np.arange(len(used))
    attributes = {}
    normalized = {}
    for name, accessor_index in geometry["source"]["attributes"].items():
        accessor = source.document["accessors"][accessor_index]
        values = source.accessor(accessor_index)[used]
        if name == "POSITION":
            attributes[name] = unique_points.astype(values.dtype)
        elif name == "NORMAL":
            normals = np.zeros_like(unique_points, dtype=np.float64)
            np.add.at(normals, inverse, values.astype(np.float64))
            lengths = np.linalg.norm(normals, axis=1)
            lengths[lengths <= 1e-20] = 1.0
            attributes[name] = (normals / lengths[:, None]).astype(values.dtype)
        else:
            attributes[name] = values[first]
        normalized[name] = accessor.get("normalized") is True
    return dict(
        attributes=attributes,
        faces=inverse[remap[source_faces]],
        material=geometry["source"].get("material"),
        normalized=normalized,
        source_vertices=len(used),
        output_vertices=len(unique_points),
        source_triangles=len(source_faces),
        position_welded=True,
        boundary_edges_before=-1,
        thickness_m=0.0,
        closed_position_welded=False,
    )


def _solidify_component(source, key, face_ids, thickness, welded_positions):
    geometry = source.primitives[key]
    source_primitive = geometry["source"]
    source_faces = geometry["faces"][face_ids]
    used = np.unique(source_faces)
    remap = np.full(len(geometry["points"]), -1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    outer_faces = remap[source_faces]
    points = geometry["points"][used].astype(np.float64)
    welded = welded_positions[used]
    welded_faces = welded[outer_faces]
    edges = _edge_summary(welded_faces)
    if edges["nonmanifold_count"]:
        raise ValueError("garment_complete_nonmanifold_selection")

    source_attributes = {}
    normalized = {}
    for name, accessor_index in source_primitive["attributes"].items():
        accessor = source.document["accessors"][accessor_index]
        source_attributes[name] = source.accessor(accessor_index)[used]
        normalized[name] = accessor.get("normalized") is True
    if "NORMAL" in source_attributes:
        outer_normals = source_attributes["NORMAL"].astype(np.float64)
        lengths = np.linalg.norm(outer_normals, axis=1)
        if (lengths <= 1e-20).any():
            outer_normals = _vertex_normals(geometry["points"], source_faces, welded_positions)[used]
        else:
            outer_normals /= lengths[:, None]
    else:
        outer_normals = _vertex_normals(geometry["points"], source_faces, welded_positions)[used]
    # UV/normal seams may duplicate a position with different source normals.
    # Inner offsets must still be identical or the welded shell reopens there.
    normal_sums = np.zeros((int(welded.max()) + 1, 3), dtype=np.float64)
    np.add.at(normal_sums, welded, outer_normals)
    normal_counts = np.bincount(welded).astype(np.float64)
    shared_normals = np.zeros_like(normal_sums)
    used_welded = np.flatnonzero(normal_counts > 0)
    shared_normals[used_welded] = normal_sums[used_welded] / normal_counts[used_welded, None]
    shared_lengths = np.linalg.norm(shared_normals, axis=1)
    for welded_id in used_welded[shared_lengths[used_welded] <= 1e-20]:
        shared_normals[welded_id] = outer_normals[np.flatnonzero(welded == welded_id)[0]]
        shared_lengths[welded_id] = np.linalg.norm(shared_normals[welded_id])
    shared_normals[used_welded] /= shared_lengths[used_welded, None]
    outer_normals = shared_normals[welded]

    count = len(used)
    inner_faces = outer_faces[:, ::-1] + count
    representative = np.zeros(int(welded.max()) + 1, dtype=np.int64)
    representative[welded] = np.arange(count)
    boundary = edges["boundary"]
    side_count = len(boundary)
    side_faces = np.empty((side_count * 2, 3), dtype=np.int64)
    side_outer = np.empty((side_count, 4), dtype=np.int64)
    for index, (wa, wb) in enumerate(boundary):
        a, b = int(representative[int(wa)]), int(representative[int(wb)])
        side_outer[index] = [a, b, a + count, b + count]
        base = 2 * count + index * 4
        side_faces[index * 2] = [base + 1, base, base + 2]
        side_faces[index * 2 + 1] = [base + 1, base + 2, base + 3]

    # A boundary pinch with degree > 2 cannot share one inner vertex across
    # several side-wall fans. Duplicate it per boundary loop with a tiny,
    # deterministic separation while leaving the visible outer surface intact.
    inner_extra = []
    inner_extra_positions = []
    inner_extra_normals = []
    outer_extra = []
    outer_extra_positions = []
    outer_extra_normals = []
    boundary_degrees = {}
    for a, b in boundary:
        boundary_degrees[int(a)] = boundary_degrees.get(int(a), 0) + 1
        boundary_degrees[int(b)] = boundary_degrees.get(int(b), 0) + 1
    for loop_index, loop in enumerate(_boundary_loops(boundary), 1):
        for welded_id in sorted(set(boundary[loop].reshape(-1).tolist())):
            if boundary_degrees[welded_id] <= 2:
                continue
            representative_index = int(representative[welded_id])
            offset = np.asarray([0.37, 0.61, 0.71]) * thickness * 0.01 * loop_index
            outer_index = -1 - len(outer_extra)
            outer_extra.append(representative_index)
            outer_extra_positions.append(points[representative_index] + offset)
            outer_extra_normals.append(outer_normals[representative_index])
            outer_faces[outer_faces == representative_index] = outer_index
            new_index = count + len(inner_extra)
            inner_extra.append(representative_index)
            inner_extra_positions.append(points[representative_index] - outer_normals[representative_index] * thickness + offset)
            inner_extra_normals.append(-outer_normals[representative_index])
            inner_faces[inner_faces == representative_index + count] = new_index
            for edge_index in loop:
                if boundary[edge_index][0] == welded_id:
                    side_outer[edge_index, 0] = outer_index
                    side_outer[edge_index, 2] = new_index
                if boundary[edge_index][1] == welded_id:
                    side_outer[edge_index, 1] = outer_index
                    side_outer[edge_index, 3] = new_index
    extra_count = len(inner_extra)
    outer_extra_count = len(outer_extra)
    for outer_index in range(outer_extra_count):
        outer_faces[outer_faces == -1 - outer_index] = 2 * count + extra_count + outer_index
        side_outer[side_outer == -1 - outer_index] = 2 * count + extra_count + outer_index
    side_base = 2 * count + extra_count + outer_extra_count
    for index in range(side_count):
        base = side_base + index * 4
        side_faces[index * 2] = [base + 1, base, base + 2]
        side_faces[index * 2 + 1] = [base + 1, base + 2, base + 3]

    attributes = {}
    for name, outer in source_attributes.items():
        outer = np.asarray(outer)
        inner = outer.copy()
        if name == "POSITION":
            inner = (points - outer_normals * thickness).astype(outer.dtype)
        elif name == "NORMAL":
            inner = (-outer_normals).astype(outer.dtype)
        extra = outer[inner_extra] if extra_count else np.empty((0,) + outer.shape[1:], dtype=outer.dtype)
        if name == "POSITION" and extra_count:
            extra = np.asarray(inner_extra_positions, dtype=outer.dtype)
        elif name == "NORMAL" and extra_count:
            extra = np.asarray(inner_extra_normals, dtype=outer.dtype)
        outer_extra_values = (
            outer[outer_extra]
            if outer_extra_count
            else np.empty((0,) + outer.shape[1:], dtype=outer.dtype)
        )
        if name == "POSITION" and outer_extra_count:
            outer_extra_values = np.asarray(outer_extra_positions, dtype=outer.dtype)
        elif name == "NORMAL" and outer_extra_count:
            outer_extra_values = np.asarray(outer_extra_normals, dtype=outer.dtype)
        side = (
            np.concatenate((outer, inner, extra, outer_extra_values), axis=0)[side_outer.reshape(-1)]
            if side_count
            else np.empty((0,) + outer.shape[1:], dtype=outer.dtype)
        )
        if name == "POSITION" and side_count:
            side_positions = np.concatenate(
                (
                    points,
                    points - outer_normals * thickness,
                    np.asarray(inner_extra_positions).reshape(-1, 3),
                    np.asarray(outer_extra_positions).reshape(-1, 3),
                ),
                axis=0,
            )
            side = side_positions[side_outer.reshape(-1)].astype(outer.dtype)
        elif name == "NORMAL" and side_count:
            side = np.zeros((side_count * 4,) + outer.shape[1:], dtype=outer.dtype)
        attributes[name] = np.concatenate((outer, inner, extra, outer_extra_values, side), axis=0)
    if "NORMAL" not in attributes:
        attributes["NORMAL"] = np.zeros((2 * count + extra_count + outer_extra_count + side_count * 4, 3), dtype="<f4")
        attributes["NORMAL"][:count] = outer_normals
        attributes["NORMAL"][count : 2 * count] = -outer_normals
        if extra_count:
            attributes["NORMAL"][2 * count : 2 * count + extra_count] = np.asarray(inner_extra_normals, dtype="<f4")
        if outer_extra_count:
            attributes["NORMAL"][2 * count + extra_count : side_base] = np.asarray(outer_extra_normals, dtype="<f4")
    if side_count:
        side_normals = attributes["NORMAL"][side_base:].astype(np.float64)
        for index in range(side_count):
            base = side_base + index * 4
            face = side_faces[index * 2]
            triangle = attributes["POSITION"][face].astype(np.float64)
            normal = np.cross(triangle[1] - triangle[0], triangle[2] - triangle[0])
            length = np.linalg.norm(normal)
            if length <= 1e-20:
                raise ValueError("garment_complete_degenerate_side")
            side_normals[index * 4 : index * 4 + 4] = normal / length
        attributes["NORMAL"][side_base:] = side_normals.astype(attributes["NORMAL"].dtype)
    faces = np.concatenate((outer_faces, inner_faces, side_faces), axis=0)
    welded_output = _position_weld(attributes["POSITION"])
    summary = _edge_summary(welded_output[faces])
    if summary["boundary_count"] or summary["nonmanifold_count"]:
        welded_faces = welded_output[faces]
        samples = []
        for edge in summary["nonmanifold"][:2]:
            incident = np.flatnonzero(
                (welded_faces == edge[0]).any(axis=1) & (welded_faces == edge[1]).any(axis=1)
            )
            zones = ["outer" if index < len(outer_faces) else "inner" if index < 2 * len(outer_faces) else "side" for index in incident]
            samples.append(dict(points=attributes["POSITION"][edge].tolist(), zones=zones))
        boundary_degrees = {}
        for a, b in edges["boundary"]:
            boundary_degrees[int(a)] = boundary_degrees.get(int(a), 0) + 1
            boundary_degrees[int(b)] = boundary_degrees.get(int(b), 0) + 1
        raise ValueError(
            "garment_complete_shell_not_closed: source_triangles=%d boundary=%d nonmanifold=%d max_boundary_degree=%d samples=%s"
            % (
                len(source_faces),
                summary["boundary_count"],
                summary["nonmanifold_count"],
                max(boundary_degrees.values(), default=0),
                canonical(samples),
            )
        )
    return dict(
        attributes=attributes,
        faces=faces,
        material=source_primitive.get("material"),
        normalized=normalized,
        source_vertices=len(used),
        source_triangles=len(source_faces),
        boundary_edges_before=edges["boundary_count"],
        thickness_m=thickness,
        closed_position_welded=True,
    )


def _edge_connected_groups(faces, welded_positions, excluded_vertices=frozenset(), cut_nonmanifold=False):
    parents = list(range(len(faces)))

    def root(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    incidents = {}
    for face_index, face in enumerate(welded_positions[faces]):
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            if int(a) in excluded_vertices or int(b) in excluded_vertices:
                continue
            edge = tuple(sorted((int(a), int(b))))
            incidents.setdefault(edge, []).append(face_index)
    for face_indices in incidents.values():
        if len(face_indices) < 2 or cut_nonmanifold and len(face_indices) > 2:
            continue
        target = root(face_indices[0])
        for face_index in face_indices[1:]:
            parents[root(face_index)] = target
    groups = {}
    for face_index in range(len(faces)):
        groups.setdefault(root(face_index), []).append(face_index)
    return [np.asarray(values, dtype=np.int64) for _root, values in sorted(groups.items())]


def _solidify_with_fan_split(source, key, face_ids, thickness, welded_positions, depth=0):
    try:
        return [_solidify_component(source, key, face_ids, thickness, welded_positions)]
    except ValueError as error:
        if depth >= 8 or "garment_complete_shell_not_closed" not in str(error):
            raise
    faces = source.primitives[key]["faces"][face_ids]
    boundary = _edge_summary(welded_positions[faces])["boundary"]
    degrees = {}
    for a, b in boundary:
        degrees[int(a)] = degrees.get(int(a), 0) + 1
        degrees[int(b)] = degrees.get(int(b), 0) + 1
    pinch_vertices = sorted(vertex for vertex, degree in degrees.items() if degree > 2)
    for vertex in pinch_vertices:
        groups = _edge_connected_groups(faces, welded_positions, {vertex})
        if len(groups) <= 1:
            continue
        parts = []
        for group in groups:
            parts.extend(_solidify_with_fan_split(source, key, face_ids[group], thickness, welded_positions, depth + 1))
        return parts
    return _solidify_spatial_split(source, key, face_ids, thickness, welded_positions, depth)


def _solidify_spatial_split(source, key, face_ids, thickness, welded_positions, depth):
    faces = source.primitives[key]["faces"][face_ids]
    points = source.primitives[key]["points"][faces].mean(axis=1)
    axis = int(np.argmax(np.ptp(points, axis=0))) if len(points) else 0
    if len(face_ids) < 2 or depth >= 24:
        raise ValueError("garment_complete_boundary_fan_unresolved")
    median = float(np.median(points[:, axis]))
    left = points[:, axis] <= median
    right = ~left
    if not left.any() or not right.any():
        raise ValueError("garment_complete_boundary_fan_unresolved")
    parts = []
    for mask in (left, right):
        parts.extend(
            _solidify_with_fan_split(
                source,
                key,
                face_ids[mask],
                thickness,
                welded_positions,
                depth + 1,
            )
        )
    return parts


def _solidify_primitive(source, key, face_ids, thickness, welded_positions):
    # Close each edge-connected shell independently. Rig exporters may emit
    # duplicate position triangles; deduplicate first, then cut true nonmanifold
    # joins into separate closed shells without changing the source model.
    face_ids = np.asarray(face_ids, dtype=np.int64)
    canonical_faces = np.sort(welded_positions[source.primitives[key]["faces"][face_ids]], axis=1)
    _unique, first = np.unique(canonical_faces, axis=0, return_index=True)
    face_ids = face_ids[first]
    selected = set(int(value) for value in face_ids)
    parts = []
    for component in source.components:
        if (component["node"], component["primitive"]) != key:
            continue
        component_faces = np.asarray(
            sorted(selected & {int(value) for value in component["_face_ids"]}), dtype=np.int64
        )
        if not len(component_faces):
            continue
        groups = _edge_connected_groups(
            source.primitives[key]["faces"][component_faces], welded_positions, cut_nonmanifold=True
        )
        for group_index, group in enumerate(groups):
            group_parts = _solidify_with_fan_split(
                source,
                key,
                component_faces[group],
                thickness,
                welded_positions,
            )
            for part in group_parts:
                part["source_component_id"] = component["component_id"]
                part["source_component_index"] = component["component_index"]
                part["edge_component_index"] = group_index
                part["fan_component_index"] = len(parts)
                parts.append(part)
    require(bool(parts), "garment_complete_selection_empty")
    return parts


def _mask(mask_record, size):
    image = Image.new("L", size, 0)
    draw = ImageDraw.Draw(image)
    width, height = size
    area = 0.0
    for polygon in mask_record["polygons"]:
        points = [(point[0] * (width - 1), point[1] * (height - 1)) for point in polygon]
        draw.polygon(points, fill=255)
        area += abs(
            sum(
                points[index][0] * points[(index + 1) % len(points)][1]
                - points[(index + 1) % len(points)][0] * points[index][1]
                for index in range(len(points))
            )
        ) * 0.5
    return np.asarray(image) > 0, area


def _camera_basis(view):
    offsets = {
        "front": (0.0, 0.03, 1.0),
        "right": (-1.0, 0.05, 0.0),
        "back": (0.0, 0.03, -1.0),
        "left": (1.0, 0.05, 0.0),
        "top": (0.0, 1.0, 0.001),
    }
    forward = -np.asarray(offsets[view], dtype=np.float64)
    forward /= np.linalg.norm(forward)
    reference_up = np.asarray([0.0, 0.0, 1.0] if abs(forward[1]) > 0.999 else [0.0, 1.0, 0.0])
    right = np.cross(forward, reference_up)
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    return forward, right, up


def _complete_subpixel_surfaces(source, primitive_map, inventory, selected_items, winner, raster, yaw_degrees=0.0):
    """Recover unsampled subdivision faces on the evidenced visible surface.

    Pixel ID rendering cannot sample every triangle of a dense source mesh. A
    candidate must lie inside the garment mask and on the depth plane of the
    visible triangle at the same pixel, with a compatible facing direction.
    Unlike connected-component expansion this cannot pull in a fused body.
    """
    from garment_split import _identity_node

    for key in source.primitives:
        current = key[0]
        while True:
            if not _identity_node(source.document["nodes"][current]):
                for assignment in selected_items:
                    assignment["evidence"]["subpixel_triangles"] = 0
                    assignment["evidence"]["subpixel_completion"] = "skipped_nonidentity_node_transform"
                return
            if current not in source.parents:
                break
            current = source.parents[current]
    if not selected_items or not any(assignment["selected"] for assignment in selected_items):
        return

    faces = []
    centroids = []
    normals = []
    point_offset = 0
    for entry in primitive_map:
        geometry = source.primitives[(entry["node"], entry["primitive"])]
        source_faces = geometry["faces"]
        require(len(source_faces) == entry["count"], "garment_complete_triangle_evidence_invalid")
        triangles = geometry["points"][source_faces].astype(np.float64)
        face_normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
        lengths = np.linalg.norm(face_normals, axis=1)
        lengths[lengths <= 1e-20] = 1.0
        faces.append(source_faces + point_offset)
        point_offset += len(geometry["points"])
        centroids.append(triangles.mean(axis=1))
        normals.append(face_normals / lengths[:, None])
    # Global point indices are needed only to retrieve the visible triangle;
    # build them from offsets without depending on vertex connectivity.
    points = np.concatenate([source.primitives[(entry["node"], entry["primitive"])]["points"] for entry in primitive_map]).astype(np.float64)
    faces = np.concatenate(faces)
    centroids = np.concatenate(centroids)
    normals = np.concatenate(normals)
    angle = math.radians(float(yaw_degrees))
    cosine, sine = math.cos(angle), math.sin(angle)
    rotation = np.asarray([[cosine, 0.0, sine], [0.0, 1.0, 0.0], [-sine, 0.0, cosine]])
    points = points @ rotation.T
    centroids = centroids @ rotation.T
    normals = normals @ rotation.T
    minimum = points.min(axis=0)
    maximum = points.max(axis=0)
    center = (minimum + maximum) * 0.5
    radius = max(float(np.linalg.norm(maximum - minimum) * 0.5), 0.001)
    distance = radius / math.sin(math.radians(21.0)) * 1.18
    tolerance = max(0.0015, float(np.linalg.norm(maximum - minimum)) * 0.0006)
    added = [set() for _assignment in selected_items]

    for view in RENDER_VIEWS:
        evidence = raster[view]
        identities = evidence["identities"]
        valid = evidence["valid"]
        height, width = identities.shape
        forward, right, up = _camera_basis(view)
        camera = center - forward * distance
        relative = centroids - camera
        depth = relative @ forward
        tangent = math.tan(math.radians(21.0))
        x = ((relative @ right) / np.maximum(depth, 1e-12) / tangent + 1.0) * 0.5 * (width - 1)
        y = (1.0 - (relative @ up) / np.maximum(depth, 1e-12) / tangent) * 0.5 * (height - 1)
        xi = np.rint(x).astype(np.int64)
        yi = np.rint(y).astype(np.int64)
        onscreen = (depth > 0.001) & (xi >= 0) & (xi < width) & (yi >= 0) & (yi < height)
        indices = np.arange(len(centroids))
        indices = indices[onscreen & (winner < 0)]
        if not len(indices):
            continue
        pixel_ids = identities[yi[indices], xi[indices]] - 1
        pixels_valid = valid[yi[indices], xi[indices]] & (pixel_ids >= 0)
        indices = indices[pixels_valid]
        pixel_ids = pixel_ids[pixels_valid]
        if not len(indices):
            continue
        facing = np.sum(normals[indices] * (-forward), axis=1) > 0.05
        indices = indices[facing]
        pixel_ids = pixel_ids[facing]
        if not len(indices):
            continue

        # Interpolate the visible triangle's inverse depth at the candidate
        # centroid pixel. This avoids comparing against an unrelated depth on
        # a steep fold or an overlapping garment.
        visible_triangles = points[faces[pixel_ids]].astype(np.float64)
        visible_relative = visible_triangles - camera
        visible_depth = visible_relative @ forward
        visible_x = ((visible_relative @ right) / np.maximum(visible_depth, 1e-12) / tangent + 1.0) * 0.5 * (width - 1)
        visible_y = (1.0 - (visible_relative @ up) / np.maximum(visible_depth, 1e-12) / tangent) * 0.5 * (height - 1)
        px, py = x[indices], y[indices]
        determinant = (visible_y[:, 1] - visible_y[:, 2]) * (visible_x[:, 0] - visible_x[:, 2]) + (visible_x[:, 2] - visible_x[:, 1]) * (visible_y[:, 0] - visible_y[:, 2])
        safe = np.abs(determinant) > 1e-12
        determinant[~safe] = 1.0
        barycentric = np.empty((len(indices), 3), dtype=np.float64)
        barycentric[:, 0] = ((visible_y[:, 1] - visible_y[:, 2]) * (px - visible_x[:, 2]) + (visible_x[:, 2] - visible_x[:, 1]) * (py - visible_y[:, 2])) / determinant
        barycentric[:, 1] = ((visible_y[:, 2] - visible_y[:, 0]) * (px - visible_x[:, 2]) + (visible_x[:, 0] - visible_x[:, 2]) * (py - visible_y[:, 2])) / determinant
        barycentric[:, 2] = 1.0 - barycentric[:, 0] - barycentric[:, 1]
        plane_depth = 1.0 / np.maximum(np.sum(barycentric / np.maximum(visible_depth, 1e-12), axis=1), 1e-12)
        # Extrapolation on the evidenced plane is intentional: dozens of dense
        # subdivision triangles can share one pixel, so their centroids need
        # not lie inside the particular sampled triangle's projected bounds.
        near_surface = safe & (np.abs(depth[indices] - plane_depth) <= tolerance)
        normal_match = np.sum(normals[indices] * normals[pixel_ids], axis=1) > 0.25
        indices = indices[near_surface & normal_match]
        if not len(indices):
            continue

        claimed = np.zeros(len(centroids), dtype=bool)
        masks = {}
        areas = {}
        for item_index, item in enumerate(inventory["items"]):
            record = next((mask for mask in item["masks"] if mask["view"] == view), None)
            if record is None or not selected_items[item_index]["selected"]:
                continue
            mask, area = _mask(record, (width, height))
            mask &= ~_excluded_pixels(raster[view]["exclusions"], view, item, (width, height))
            masks[item_index] = mask
            areas[item_index] = area
        for item_index in sorted(masks, key=lambda value: (-areas[value], value)):
            eligible = indices[masks[item_index][yi[indices], xi[indices]] & ~claimed[indices]]
            if len(eligible):
                added[item_index].update(int(value) for value in eligible)
                claimed[eligible] = True

    for item_index, assignment in enumerate(selected_items):
        expanded = np.asarray(sorted(added[item_index]), dtype=np.int64)
        assignment["evidence"]["subpixel_triangles"] = len(expanded)
        assignment["evidence"]["subpixel_depth_tolerance_m"] = tolerance
        if not len(expanded):
            continue
        winner[expanded] = item_index
        for entry in primitive_map:
            key = (entry["node"], entry["primitive"])
            local = expanded[(expanded >= entry["start"]) & (expanded < entry["start"] + entry["count"])] - entry["start"]
            if len(local):
                assignment["selected"].setdefault(key, np.asarray([], dtype=np.int64))
                assignment["selected"][key] = np.asarray(
                    sorted(set(assignment["selected"][key].astype(int).tolist()) | set(local.astype(int).tolist())),
                    dtype=np.int64,
                )
        assignment["evidence"]["selected_triangles"] = sum(len(value) for value in assignment["selected"].values())


def _fill_topology_pinholes(source, primitive_map, selected_items, winner):
    """Fill only unowned faces bounded by at least two selected neighbours."""
    starts = {(entry["node"], entry["primitive"]): entry["start"] for entry in primitive_map}
    adjacency_cache = {}
    for item_index, assignment in enumerate(selected_items):
        added_total = 0
        for key, face_ids in list(assignment["selected"].items()):
            if key not in adjacency_cache:
                geometry = source.primitives[key]
                faces = geometry["faces"]
                welded = _position_weld(geometry["points"])
                incidents = {}
                for face_index, face in enumerate(welded[faces]):
                    for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
                        incidents.setdefault(tuple(sorted((int(a), int(b)))), []).append(face_index)
                adjacency_cache[key] = (faces, incidents)
            faces, incidents = adjacency_cache[key]
            selected = np.zeros(len(faces), dtype=bool)
            selected[face_ids] = True
            neighbour_votes = np.zeros(len(faces), dtype=np.uint8)
            for incident in incidents.values():
                votes = sum(selected[face_index] for face_index in incident)
                if not votes:
                    continue
                for face_index in incident:
                    if not selected[face_index]:
                        neighbour_votes[face_index] += votes
            local = np.flatnonzero(neighbour_votes >= 2)
            if len(local):
                global_ids = local + starts[key]
                local = local[winner[global_ids] < 0]
            if not len(local):
                continue
            selected[local] = True
            winner[local + starts[key]] = item_index
            assignment["selected"][key] = np.flatnonzero(selected).astype(np.int64)
            added_total += len(local)
        assignment["evidence"]["topology_pinhole_triangles"] = added_total
        assignment["evidence"]["selected_triangles"] = sum(len(value) for value in assignment["selected"].values())


def _assign_triangles(source, inventory, primitive_map, render_report, render_root, exclusions=None):
    exclusions = exclusions or dict(views=[])
    total = sum(entry["count"] for entry in primitive_map)
    maps = {entry["view"]: entry for entry in render_report.get("triangle_id_maps", [])}
    require(set(maps) == set(RENDER_VIEWS), "garment_complete_triangle_evidence_missing")
    votes = [np.zeros(total, dtype=np.uint32) for _item in inventory["items"]]
    coverage = [dict(mask_pixels=0, assigned_pixels=0, conflicted_pixels=0) for _item in inventory["items"]]
    raster = {}
    for view in RENDER_VIEWS:
        entry = maps[view]
        def decode_pass(path_key, sha_key):
            path = Path(entry[path_key]).resolve()
            require(path.is_relative_to(Path(render_root).resolve()) and path.is_file(), "garment_complete_triangle_evidence_invalid")
            require(hashlib.sha256(path.read_bytes()).hexdigest() == entry[sha_key], "garment_complete_triangle_evidence_invalid")
            pixels = np.asarray(Image.open(path).convert("RGB"), dtype=np.float64)
            channels = np.rint((pixels / 255.0 - 0.2) * 15.0 / 0.8).astype(np.int64)
            expected = 0.2 + 0.8 * channels / 15.0
            color_valid = (channels >= 0).all(axis=2) & (channels <= 15).all(axis=2)
            color_valid &= (np.abs(pixels / 255.0 - expected) <= 4.0 / 255.0).all(axis=2)
            return pixels, channels, color_valid

        pixels, low, low_valid = decode_pass("path", "sha256")
        _high_pixels, high, high_valid = decode_pass("high_path", "high_sha256")
        identities = (
            low[:, :, 0]
            | (low[:, :, 1] << 4)
            | (low[:, :, 2] << 8)
            | (high[:, :, 0] << 12)
            | (high[:, :, 1] << 16)
            | (high[:, :, 2] << 20)
        )
        valid = low_valid & high_valid & (identities > 0) & (identities <= total)
        raster[view] = dict(identities=identities, valid=valid, exclusions=exclusions)
        masks = {}
        areas = {}
        for index, item in enumerate(inventory["items"]):
            record = next((mask for mask in item["masks"] if mask["view"] == view), None)
            if record is None:
                continue
            mask, area = _mask(record, (pixels.shape[1], pixels.shape[0]))
            mask &= ~_excluded_pixels(exclusions, view, item, (pixels.shape[1], pixels.shape[0]))
            masks[index] = mask
            areas[index] = area
            coverage[index]["mask_pixels"] += int(np.count_nonzero(mask & valid))
        unassigned = valid.copy()
        # Small, specific garments win over a surrounding robe or body-sized mask.
        for index in sorted(masks, key=lambda value: (-areas[value], value)):
            mask = masks[index]
            eligible = mask & valid & unassigned
            selected, counts = np.unique(identities[eligible], return_counts=True)
            votes[index][selected - 1] += counts.astype(np.uint32)
            coverage[index]["assigned_pixels"] += int(np.count_nonzero(eligible))
            coverage[index]["conflicted_pixels"] += int(np.count_nonzero(mask & valid & ~unassigned))
            unassigned[mask & valid] = False

    winner = np.full(total, -1, dtype=np.int64)
    best = np.zeros(total, dtype=np.uint32)
    second = np.zeros(total, dtype=np.uint32)
    for index, item_votes in enumerate(votes):
        better = item_votes > best
        second[better] = best[better]
        best[better] = item_votes[better]
        winner[better] = index
        remaining = ~better & (item_votes > 0)
        second[remaining] = np.maximum(second[remaining], item_votes[remaining])
    selected_items = []
    for index, item in enumerate(inventory["items"]):
        global_faces = np.flatnonzero((winner == index) & (votes[index] > 0))
        conflicted = np.flatnonzero((winner == index) & (second > 0) & (second * 2 >= best))
        selected = {}
        for mapping in primitive_map:
            start, count = mapping["start"], mapping["count"]
            local = global_faces[(global_faces >= start) & (global_faces < start + count)] - start
            if len(local):
                selected[(mapping["node"], mapping["primitive"])] = local.astype(np.int64)
        evidence = dict(coverage[index])
        evidence.update(
            selected_triangles=len(global_faces),
            conflicted_triangles=len(conflicted),
            conflict_ratio=float(len(conflicted) / max(1, len(global_faces))),
            mask_pixel_coverage=float(evidence["assigned_pixels"] / max(1, evidence["mask_pixels"])),
        )
        selected_items.append(dict(item=item, selected=selected, evidence=evidence))
    _complete_subpixel_surfaces(
        source,
        primitive_map,
        inventory,
        selected_items,
        winner,
        raster,
        float(render_report.get("yaw_degrees", 0.0)),
    )
    _fill_topology_pinholes(source, primitive_map, selected_items, winner)
    return selected_items


def _validate_id_report(report, source, id_sha256, id_high_sha256=None):
    require(
        report.get("model_sha256") == source.sha256
        and report.get("triangle_id_model_sha256") == id_sha256
        and (id_high_sha256 is None or report.get("triangle_id_model_high_sha256") == id_high_sha256),
        "garment_complete_triangle_evidence_invalid",
    )


def _default_thickness(source, item):
    points = np.concatenate([geometry["points"] for geometry in source.primitives.values()], axis=0)
    height = float(points[:, 1].max() - points[:, 1].min())
    factor = 0.002 if item["behavior"] in ("rigid", "mixed") else 0.0012
    return min(0.02, max(0.0002, height * factor))


def _load_generated_glb(path):
    # Input sources retain geometry_repair's 128 MiB guard. These are our own
    # deterministic evidence/output files and may legitimately exceed it.
    data = Path(path).read_bytes()
    require(28 <= len(data) <= 2 * 1024**3 and data[:4] == b"glTF", "garment_complete_output_invalid")
    require(struct.unpack_from("<I", data, 8)[0] == len(data), "garment_complete_output_invalid")
    size = struct.unpack_from("<I", data, 12)[0]
    require(20 + size + 8 <= len(data), "garment_complete_output_invalid")
    document = json.loads(data[20 : 20 + size])
    binary_size, kind = struct.unpack_from("<II", data, 20 + size)
    require(kind == 0x004E4942 and 28 + size + binary_size <= len(data), "garment_complete_output_invalid")
    return document, data[28 + size : 28 + size + binary_size]


def _generated_triangle_count(document):
    referenced = {node["mesh"] for node in document.get("nodes", []) if "mesh" in node}
    return sum(
        document["accessors"][primitive["indices"]]["count"] // 3
        for mesh_index, mesh in enumerate(document.get("meshes", []))
        if mesh_index in referenced
        for primitive in mesh.get("primitives", [])
        if "indices" in primitive
    )


def _accessor_raw(document, binary, index):
    accessor = document["accessors"][index]
    view = document["bufferViews"][accessor["bufferView"]]
    widths = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
    component_sizes = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
    item_size = component_sizes[accessor["componentType"]] * widths[accessor["type"]]
    start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    return binary[start : start + accessor["count"] * item_size]


def _validate_rigged_output(source, document, binary):
    require(document.get("skins") == source.document.get("skins"), "garment_complete_skin_invalid")
    require(len(document.get("nodes", [])) == len(source.document.get("nodes", [])), "garment_complete_skin_invalid")
    for skin_index, skin in enumerate(document.get("skins", [])):
        if "inverseBindMatrices" in skin:
            require(
                _accessor_raw(document, binary, skin["inverseBindMatrices"])
                == _accessor_raw(source.document, source.binary, skin["inverseBindMatrices"]),
                "garment_complete_skin_invalid",
            )
    for node in document.get("nodes", []):
        if "mesh" not in node:
            continue
        require("skin" in node, "garment_complete_skin_invalid")
        skin = document["skins"][node["skin"]]
        for primitive in document["meshes"][node["mesh"]]["primitives"]:
            attributes = primitive["attributes"]
            require("JOINTS_0" in attributes and "WEIGHTS_0" in attributes, "garment_complete_skin_invalid")
            positions = accessor_values(document, binary, attributes["POSITION"])
            joints = accessor_values(document, binary, attributes["JOINTS_0"])
            weights = accessor_values(document, binary, attributes["WEIGHTS_0"])
            require(len(positions) == len(joints) == len(weights), "garment_complete_skin_invalid")
            require(joints.max() < len(skin["joints"]), "garment_complete_skin_invalid")
            accessor = document["accessors"][attributes["WEIGHTS_0"]]
            numeric = weights.astype(np.float64)
            if accessor.get("componentType") == 5121:
                numeric /= 255.0
            elif accessor.get("componentType") == 5123:
                numeric /= 65535.0
            require(np.allclose(numeric.sum(axis=1), 1.0, rtol=0, atol=1e-4), "garment_complete_skin_invalid")


def _repair_quality_inventory(config, inventory, quality, evidence):
    """Return a generic, defect-bound mask revision for one retry attempt."""
    repaired = copy.deepcopy(inventory)
    source_views = {entry["view"]: entry for entry in quality["source_views"]}
    generated_views = {entry["view"]: entry for entry in quality["generated_views"]}
    records = []
    for review in quality["review"]["items"]:
        if review["passed"]:
            continue
        item = next(item for item in repaired["items"] if item["id"] == review["id"])
        semantic = dict(inventory, items=[item])
        views = sorted({defect["view"] for defect in review["defects"]})
        complete = True
        missing = []
        changed_views = []
        for view in views:
            defects = [defect for defect in review["defects"] if defect["view"] == view]
            try:
                response = _request_view_masks(
                    config,
                    semantic,
                    _image(source_views[view]["path"], view),
                    Path(evidence) / "quality-repair-requests" / item["id"] / view,
                    comparison=_image(generated_views[view]["path"], view),
                    guidance=canonical(defects),
                )
            except ValueError as error:
                if "polygon" not in str(error):
                    raise
                missing.append(view + ": invalid repaired contour")
                complete = False
                continue
            result = next(result for result in response["items"] if result["id"] == item["id"])
            polygons = []
            for polygon in result["polygons"]:
                _validate_simple_polygon(polygon)
                polygons.append(polygon)
            has_extraneous = any(defect["kind"] == "extraneous_surface" for defect in defects)
            if not has_extraneous:
                previous = next((mask for mask in item["masks"] if mask["view"] == view), None)
                if previous:
                    for polygon in previous["polygons"]:
                        _validate_simple_polygon(polygon)
                        polygons.append(polygon)
            item["masks"] = [mask for mask in item["masks"] if mask["view"] != view]
            if result["visible"] and polygons:
                item["masks"].append(dict(view=view, polygons=polygons[:8]))
            complete = complete and result["complete_visible"]
            for region in result["missing_regions"]:
                missing.append(view + ": " + region)
            changed_views.append(view)
        views_with_masks = {mask["view"] for mask in item["masks"]}
        complete = complete and {"front", "back"} <= views_with_masks and bool({"left", "right"} & views_with_masks)
        item["coverage"] = "complete_visible" if complete else "partial"
        item["missing_regions"] = list(dict.fromkeys(missing))
        item["needs_review"] = True
        records.append(dict(id=item["id"], views=changed_views, coverage=item["coverage"]))
    return repaired, dict(changed=canonical(repaired) != canonical(inventory), items=records)


def complete(source_path, output, evidence, godot_path, render_script, planner=None, quality_review=True, _inventory_override=None, _quality_attempt=0, _repair_history=None):
    source_path = Path(source_path).expanduser().resolve()
    output = Path(output).expanduser().resolve()
    evidence = Path(evidence).expanduser().resolve()
    require(source_path.is_file() and source_path.suffix.lower() == ".glb", "source_missing")
    require(not output.exists(), "garment_complete_output_exists")
    source = GarmentSource(source_path)
    evidence.mkdir(parents=True, exist_ok=True)
    low_path = evidence / "triangle-ids-low.glb"
    high_path = evidence / "triangle-ids-high.glb"
    if low_path.is_file() or high_path.is_file():
        require(low_path.is_file() and high_path.is_file(), "garment_complete_triangle_evidence_incomplete")
        low_document, _low_binary = _load_generated_glb(low_path)
        high_document, _high_binary = _load_generated_glb(high_path)
        low_extras = low_document["asset"]["extras"]["maliang_triangle_id_map"]
        high_extras = high_document["asset"]["extras"]["maliang_triangle_id_map"]
        require(
            low_extras["source_sha256"] == source.sha256
            and high_extras["source_sha256"] == source.sha256
            and low_extras["shift"] == 0
            and high_extras["shift"] == 12,
            "garment_segmentation_source_mismatch",
        )
        primitive_map = low_extras["primitive_map"]
        require(primitive_map == high_extras["primitive_map"], "garment_complete_triangle_evidence_invalid")
        id_sha256 = hashlib.sha256(low_path.read_bytes()).hexdigest()
        id_high_sha256 = hashlib.sha256(high_path.read_bytes()).hexdigest()
    else:
        primitive_map, id_sha256 = _triangle_id_model(source, low_path, shift=0)
        _high_map, id_high_sha256 = _triangle_id_model(source, high_path, shift=12)
    report_path = evidence / "render" / "renders" / "views.json"
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        render_root = report_path.parent
        for entry in report.get("triangle_id_maps", []):
            entry["path"] = str(render_root / Path(entry["path"]).name)
            entry["high_path"] = str(render_root / Path(entry["high_path"]).name)
        for entry in report.get("views", []):
            entry["path"] = str(render_root / Path(entry["path"]).name)
        views = [dict(path=entry["path"], label=entry["view"], component_id=None) for entry in report["views"]]
    else:
        (evidence / "render").mkdir(exist_ok=True)
        views = _render(
            source_path,
            [],
            evidence / "render",
            godot_path,
            render_script,
            triangle_id_model=low_path,
            triangle_id_model_high=high_path,
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
    _validate_id_report(report, source, id_sha256, id_high_sha256)
    if planner is None:
        from kimi_provider import DEFAULT_ENDPOINT, DEFAULT_MODEL

        planner = dict(endpoint=DEFAULT_ENDPOINT, model=DEFAULT_MODEL, key_env="KIMI_API_KEY")
    segmentation_path = evidence / "inventory" / "segmentation.json"
    if _inventory_override is not None:
        inventory = validate_segmentation(_inventory_override)
    elif segmentation_path.is_file():
        inventory = validate_segmentation(json.loads(segmentation_path.read_text(encoding="utf-8")))
    else:
        inventory = request_segmentation(planner, source, views, evidence / "inventory")
    exclusions = (
        _request_exclusions(planner, source, views, evidence / "exclusions")
        if quality_review
        else dict(views=[])
    )
    assignments = _assign_triangles(source, inventory, primitive_map, report, evidence / "render" / "renders", exclusions)
    output.mkdir(parents=True)
    records = []
    unresolved = []
    unresolved_items = []
    collection_parts = []
    welded_positions = {key: _position_weld(geometry["points"]) for key, geometry in source.primitives.items()}
    try:
        for assignment in assignments:
            item = assignment["item"]
            reasons = []
            if item["coverage"] != "complete_visible":
                reasons.append("coverage=" + item["coverage"])
            if not assignment["selected"]:
                reasons.append("no visible source triangles")
            if assignment["evidence"]["conflict_ratio"] > 0.05:
                reasons.append("triangle ownership conflicts")
            if assignment["evidence"].get("mask_pixel_coverage", 1.0) < 0.90:
                reasons.append("insufficient visible-pixel coverage")
            if reasons:
                unresolved_items.append(item["id"])
                unresolved.append(item["id"] + ": " + ", ".join(reasons))
                continue
            thickness = _default_thickness(source, item)
            parts = []
            open_surface = False
            try:
                for key, face_ids in assignment["selected"].items():
                    try:
                        component_parts = _solidify_primitive(source, key, face_ids, thickness, welded_positions[key])
                    except (ValueError, IndexError, FloatingPointError):
                        component_parts = [_open_surface_primitive(source, key, face_ids, welded_positions[key])]
                    for part in component_parts:
                        part.setdefault("source_component_index", 0)
                        part.setdefault("edge_component_index", 0)
                        part.setdefault("fan_component_index", 0)
                        part["name"] = item["id"] + "-%d-%d-c%d-e%d-f%d" % (
                            key[0],
                            key[1],
                            part["source_component_index"],
                            part["edge_component_index"],
                            part["fan_component_index"],
                        )
                        part["source_node"] = key[0]
                        part["open_surface"] = not part["closed_position_welded"]
                        open_surface = open_surface or part["open_surface"]
                        parts.append(part)
                if open_surface:
                    unresolved.append(item["id"] + ": open boundary; closed shell reconstruction unavailable")
                writer = (
                    _RiggedGlbWriter(source, "AINative complete wearable garment shell")
                    if source.rigged
                    else _GlbWriter(source, "AINative complete wearable garment shell")
                )
                for part in parts:
                    writer.add_part(
                        part["name"],
                        part["attributes"],
                        part["faces"],
                        part["material"],
                        part["normalized"],
                        source_node=part["source_node"],
                    )
                source_map = [
                    dict(node=key[0], primitive=key[1], source_triangles=face_ids.astype(int).tolist())
                    for key, face_ids in assignment["selected"].items()
                ]
                data = writer.finish(
                    dict(
                        maliang_garment_complete=dict(
                            schema_version=1,
                            operation="reconstruct_wearable_garment_shell",
                            item_id=item["id"],
                            coverage=item["coverage"],
                            source_sha256=source.sha256,
                            source_primitives=source_map,
                            source_not_overwritten=True,
                            body_removed=True,
                            inner_surface_reconstructed=not open_surface,
                            thickness_m=0.0 if open_surface else thickness,
                            closed_position_welded=not open_surface,
                            visual_review_passed=False,
                            fit_validated=False,
                            animation_validated=False,
                        )
                    )
                )
                path = output / (item["id"] + ".glb")
                _write_new(path, data)
                loaded, _loaded_binary = _load_generated_glb(path)
                if source.rigged:
                    _validate_rigged_output(source, loaded, _loaded_binary)
                observed = _generated_triangle_count(loaded)
                expected = sum(len(part["faces"]) for part in parts)
                require(observed == expected, "garment_complete_output_invalid")
                collection_parts.extend(parts)
                record = dict(
                    id=item["id"],
                    label=item["label"],
                    category=item["category"],
                    slot=item["slot"],
                    behavior=item["behavior"],
                    confidence=float(item["confidence"]),
                    review_state="needs_review" if item["needs_review"] else "automatic",
                    state="wearable_open" if open_surface else "wearable_shell",
                    coverage_state="complete_visible",
                    path=path.name,
                    sha256=hashlib.sha256(data).hexdigest(),
                    vertices=sum(len(part["attributes"]["POSITION"]) for part in parts),
                    triangles=observed,
                    source_triangles=sum(len(face_ids) for face_ids in assignment["selected"].values()),
                    source_primitives=source_map,
                    thickness_m=0.0 if open_surface else thickness,
                    closed_position_welded=not open_surface,
                    segmentation=assignment["evidence"],
                    visual_review_passed=False,
                    fit_validated=False,
                    animation_validated=False,
                    cloth_ready=False,
                )
                records.append(record)
            except (ValueError, IndexError, FloatingPointError) as error:
                unresolved_items.append(item["id"])
                unresolved.append(item["id"] + ": " + str(error))
        require(bool(records), "garment_complete_no_wearable: " + "; ".join(unresolved))
        collection_writer = (
            _RiggedGlbWriter(source, "AINative complete wearable garment collection")
            if source.rigged
            else _GlbWriter(source, "AINative complete wearable garment collection")
        )
        for part in collection_parts:
            collection_writer.add_part(
                part["name"],
                part["attributes"],
                part["faces"],
                part["material"],
                part["normalized"],
                source_node=part["source_node"],
            )
        collection_data = collection_writer.finish(
            dict(
                maliang_garment_complete=dict(
                    schema_version=1,
                    operation="reconstruct_wearable_garment_collection",
                    source_sha256=source.sha256,
                    item_ids=[record["id"] for record in records],
                    visual_review_passed=False,
                )
            )
        )
        _write_new(output / "_garments.glb", collection_data)
        collection = dict(
            path="_garments.glb",
            sha256=hashlib.sha256(collection_data).hexdigest(),
            vertices=sum(len(part["attributes"]["POSITION"]) for part in collection_parts),
            triangles=sum(len(part["faces"]) for part in collection_parts),
        )
        require(hashlib.sha256(source_path.read_bytes()).hexdigest() == source.sha256, "garment_split_source_changed")
        quality = None
        visual_review_passed = False
        if quality_review:
            quality = _quality_gate(
                planner,
                source,
                dict(inventory, items=records),
                views,
                output / "_garments.glb",
                evidence,
                godot_path,
                render_script,
                attempt=_quality_attempt,
            )
            visual_review_passed = quality["visual_review_passed"]
            for record in records:
                record["visual_review_passed"] = visual_review_passed
            if not visual_review_passed:
                for item in quality["review"]["items"]:
                    for defect in item["defects"]:
                        unresolved.append(
                            "visual quality gate: %s %s %s: %s"
                            % (item["id"], defect["view"], defect["kind"], defect["observation"])
                        )
        if quality is not None and not visual_review_passed and _quality_attempt < 1:
            repaired_inventory, repair_record = _repair_quality_inventory(planner, inventory, quality, evidence)
            if repair_record["changed"]:
                rejected = evidence / ("rejected-output-%02d" % _quality_attempt)
                require(not rejected.exists(), "garment_quality_retry_output_exists")
                shutil.move(str(output), str(rejected))
                history = list(_repair_history or []) + [repair_record]
                return complete(
                    source_path,
                    output,
                    evidence,
                    godot_path,
                    render_script,
                    planner=planner,
                    quality_review=quality_review,
                    _inventory_override=repaired_inventory,
                    _quality_attempt=_quality_attempt + 1,
                    _repair_history=history,
                )
        automatic = dict(
            schema_version=1,
            mode="multiview_triangle_segmentation_and_shell_reconstruction",
            source_sha256=source.sha256,
            recognized_item_count=len(inventory["items"]),
            selected_item_count=len(records),
            unresolved_items=unresolved_items,
            visual_review_passed=visual_review_passed,
            quality_gate_completed=quality is not None,
            quality_repair_attempt=_quality_attempt,
            quality_repair_history=_repair_history or [],
            human_confirmed=False,
            cloth_ready=False,
        )
        manifest = dict(
            schema_version=2,
            operation="reconstruct_wearable_garment_shell",
            status="capability_limited" if unresolved else "wearable_shell",
            capability_limited=bool(unresolved),
            source=str(source_path),
            source_sha256=source.sha256,
            source_not_overwritten=True,
            rigged=source.rigged,
            skeleton_preserved=source.rigged,
            skin_weights_preserved=source.rigged,
            inverse_bind_matrices_preserved=source.rigged,
            unreferenced_source_vertices_retained=False,
            items=records,
            collection=collection,
            unresolved=unresolved,
            unresolved_items=unresolved_items,
            inventory_sha256=hashlib.sha256(canonical(inventory).encode("utf-8")).hexdigest(),
            exclusions_sha256=hashlib.sha256(canonical(exclusions).encode("utf-8")).hexdigest(),
            hidden_body_reconstructed=False,
            body_removed=True,
            inner_surface_reconstructed=True,
            visual_review_passed=visual_review_passed,
            quality_gate=quality,
            quality_repair_attempt=_quality_attempt,
            quality_repair_history=_repair_history or [],
            fit_validated=False,
            animation_validated=False,
            cloth_ready=False,
            automatic_recognition=automatic,
            limitations=[
                "wearable_shell requires complete-visible masks and a closed position-welded shell; it is not visual or fit acceptance.",
                "The five-view source-vs-output quality gate covers missing and extraneous surfaces; a defect prevents visual acceptance.",
                "Inner thickness is reconstructed inference and is not claimed to reproduce an unseen original lining.",
                "Target-rig fitting, animation, collision and production cloth behavior remain downstream.",
            ],
        )
        manifest["manifest_revision"] = hashlib.sha256(canonical(manifest).encode("utf-8")).hexdigest()
        _write_new(output / "complete_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        (evidence / "complete-receipt.json").write_text(canonical(automatic), encoding="utf-8")
        return manifest
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise
