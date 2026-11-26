"""Strict visual acceptance for labeled standalone-garment image views."""

import base64
import hashlib
import json
from pathlib import Path

from api_planner import validate_config
from extensions import canonical, require

MAX_REQUEST = 48 * 1024 * 1024
OBSERVED_VIEWS = [
    "front",
    "back",
    "left_side",
    "right_side",
    "three_quarter_front",
    "three_quarter_back",
    "top",
    "bottom",
    "inside",
    "unclear",
    "other",
]


def schema():
    strings = dict(type="string")
    issues = dict(type="array", items=strings)
    view = dict(
        type="object",
        properties=dict(
            label=strings,
            observed_view=dict(type="string", enum=OBSERVED_VIEWS),
            matches_label=dict(type="boolean"),
            garment_only=dict(type="boolean"),
            cuff_exterior_pass=dict(type="boolean"),
            closed_back_pass=dict(type="boolean"),
            flat_rear_belt_pass=dict(type="boolean"),
            horizontal_rear_layout_pass=dict(type="boolean"),
            evidence=strings,
            issues=issues,
        ),
        required=[
            "label",
            "observed_view",
            "matches_label",
            "garment_only",
            "cuff_exterior_pass",
            "closed_back_pass",
            "flat_rear_belt_pass",
            "horizontal_rear_layout_pass",
            "evidence",
            "issues",
        ],
        additionalProperties=False,
    )
    return dict(
        type="object",
        properties=dict(
            passed=dict(type="boolean"),
            same_garment=dict(type="boolean"),
            views=dict(type="array", items=view),
            summary=strings,
            issues=issues,
        ),
        required=["passed", "same_garment", "views", "summary", "issues"],
        additionalProperties=False,
    )


def review_prompt(source_text, entries):
    labels = ", ".join(entry["label"] for entry in entries)
    return (
        "Visually accept or reject these generated standalone-garment images. Judge only the pixels, never the "
        "requested labels or filenames. Requested labels: "
        + labels
        + ". Original request: "
        + source_text
        + "\nA valid 正面/front is a straight-on exterior front: the garment's vertical center is centered, both "
        "shoulders and both sleeves are presented at matching angles, and the front neckline/opening faces the camera. "
        "A three-quarter or oblique side view is not front. A valid 背面/back is the opposite exterior after a 180-degree "
        "vertical turn: the back neckline and rear construction face the camera, while front-only openings, plackets and "
        "chest ornaments are hidden unless the original request explicitly puts them on both sides. For every view, "
        "return all four rear-structure booleans; set them true for a non-back label. For a back label, evaluate each "
        "independently and never substitute one overall impression for these checks. cuff_exterior_pass is true only "
        "when no cuff opening, interior lining, turned-back cuff or emphasized wide cuff rim is visible. closed_back_pass "
        "is true only for a continuous closed pullover-style back with no vertical opening, placket, zipper, buttons, "
        "lacing or parted front panels. flat_rear_belt_pass is true only when the rear waist is flat and smooth with no "
        "front buckle, knot, clasp or large ornamental centerpiece. horizontal_rear_layout_pass is true only when broad "
        "flat rear fabric panels and clear horizontal elements such as a shoulder yoke, waist band or horizontal panel "
        "seams dominate over any long vertical center ornament. Any false check requires a concrete issue and "
        "matches_label=false. These defaults yield only to an explicit user request for a different rear design. "
        "Similarity to the front is not evidence of a back view. Do not accept a duplicated, mirrored, relabeled or "
        "oblique view. Every image must contain one isolated garment without a person, body, face, mannequin or hanger. "
        "When several images are supplied, they must depict the same garment design, not merely the same clothing "
        "category. Set every matches_label independently, set same_garment for the collection, and list concrete visible "
        "issues. If the angle, identity or a structure check is uncertain, reject rather than guess. passed may be true "
        "only when same_garment is true, every view matches its label and is garment-only, all four structure checks are "
        "true for every view, and all issues arrays are empty."
    )


def prepare_request(config, source_text, entries, directory):
    """Persist one bounded vision request; no network or credential access occurs here."""
    validate_config(config)
    require(isinstance(entries, list) and 1 <= len(entries) <= 8, "image_view_review_invalid")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    prompt = review_prompt(source_text, entries)
    content = [dict(type="text", text=prompt)]
    for index, entry in enumerate(entries):
        require(
            isinstance(entry, dict)
            and set(entry) == {"label", "data", "extension"}
            and isinstance(entry["label"], str)
            and entry["label"]
            and isinstance(entry["data"], bytes)
            and entry["data"]
            and entry["extension"] in (".png", ".jpg", ".jpeg"),
            "image_view_review_invalid",
        )
        content.append(dict(type="text", text="IMAGE " + str(index + 1) + "; requested label: " + entry["label"]))
        mime = "image/png" if entry["extension"] == ".png" else "image/jpeg"
        content.append(
            dict(
                type="image_url",
                image_url=dict(url="data:" + mime + ";base64," + base64.b64encode(entry["data"]).decode("ascii")),
            )
        )
    body = dict(
        model=config["model"],
        messages=[dict(role="user", content=content)],
        response_format=dict(
            type="json_schema", json_schema=dict(name="garment_view_review", strict=True, schema=schema())
        ),
        reasoning_effort="low",
        max_tokens=4096,
        stream=False,
    )
    raw = canonical(body).encode("utf-8")
    require(len(raw) <= MAX_REQUEST, "image_view_review_invalid")
    (directory / "prompt.txt").write_text(prompt, encoding="utf-8")
    (directory / "schema.json").write_text(canonical(schema()), encoding="utf-8")
    (directory / "api-request.json").write_bytes(raw)
    (directory / "planner-config.json").write_text(canonical(config), encoding="utf-8")
    return raw


def validate_response(document, entries, raw, directory):
    """Bind the response to this request and reject inconsistent model verdicts."""
    directory = Path(directory)
    receipt = json.loads((directory / "api-receipt.json").read_text(encoding="utf-8"))
    require(
        receipt["request_sha256"] == hashlib.sha256(raw).hexdigest()
        and receipt["instructions_sha256"] == hashlib.sha256(canonical(document).encode("utf-8")).hexdigest(),
        "image_view_review_invalid",
    )
    require(
        isinstance(document, dict) and set(document) == {"passed", "same_garment", "views", "summary", "issues"},
        "image_view_review_invalid",
    )
    require(
        type(document["passed"]) is bool
        and type(document["same_garment"]) is bool
        and isinstance(document["summary"], str)
        and isinstance(document["issues"], list)
        and all(isinstance(issue, str) for issue in document["issues"]),
        "image_view_review_invalid",
    )
    views = document["views"]
    require(isinstance(views, list) and len(views) == len(entries), "image_view_review_invalid")
    expected_labels = [entry["label"] for entry in entries]
    require([view.get("label") for view in views] == expected_labels, "image_view_review_invalid")
    structure_fields = (
        "cuff_exterior_pass",
        "closed_back_pass",
        "flat_rear_belt_pass",
        "horizontal_rear_layout_pass",
    )
    fields = {"label", "observed_view", "matches_label", "garment_only", "evidence", "issues"} | set(structure_fields)
    for view in views:
        require(
            isinstance(view, dict)
            and set(view) == fields
            and view["observed_view"] in OBSERVED_VIEWS
            and type(view["matches_label"]) is bool
            and type(view["garment_only"]) is bool
            and all(type(view[field]) is bool for field in structure_fields)
            and isinstance(view["evidence"], str)
            and view["evidence"].strip()
            and isinstance(view["issues"], list)
            and all(isinstance(issue, str) for issue in view["issues"]),
            "image_view_review_invalid",
        )
    expected = (
        document["same_garment"]
        and not document["issues"]
        and all(
            view["matches_label"]
            and view["garment_only"]
            and all(view[field] for field in structure_fields)
            and not view["issues"]
            for view in views
        )
    )
    require(document["passed"] == expected, "image_view_review_invalid")
    return document
