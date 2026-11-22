"""One explicit vision request for open-vocabulary wearable inventory.

Whole-model images establish semantics. Component IDs may be returned only when
an attached preview explicitly names those IDs; image labels never authorize an
unseen fused-surface triangle boundary. No retry or hidden fallback is used.
"""

import argparse
import base64
import hashlib
import json
from pathlib import Path

from api_planner import perform, validate_config
from extensions import canonical
from garment_split import BEHAVIORS, CATEGORIES, SLOTS, validate_inventory
from provider_common import validate_png

MAX_IMAGE_BYTES = 32 * 1024 * 1024
MAX_REQUEST_BYTES = 48 * 1024 * 1024


def inventory_schema():
    item = dict(
        type="object",
        properties=dict(
            id=dict(type="string"),
            label=dict(type="string"),
            category=dict(type="string", enum=list(CATEGORIES)),
            slot=dict(type="string", enum=list(SLOTS)),
            behavior=dict(type="string", enum=list(BEHAVIORS)),
            confidence=dict(type="number", minimum=0, maximum=1),
            component_ids=dict(type="array", items=dict(type="string"), uniqueItems=True),
            evidence=dict(type="string"),
            needs_review=dict(type="boolean"),
        ),
        required=[
            "id",
            "label",
            "category",
            "slot",
            "behavior",
            "confidence",
            "component_ids",
            "evidence",
            "needs_review",
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
            schema_version=dict(type="integer", const=1),
            items=dict(type="array", items=item),
            non_garments=dict(type="array", items=non_garment),
            notes=dict(type="string"),
        ),
        required=["schema_version", "items", "non_garments", "notes"],
        additionalProperties=False,
    )


def inventory_prompt(inspection):
    public_inspection = {
        key: value
        for key, value in inspection.items()
        if key not in ("source", "limitations")
    }
    return (
        "Inspect every attached image independently. Identify ALL visible wearable items on the same subject, including "
        "ordinary clothing, underwear, footwear, gloves, armor, shoulder pieces, bracers, belts, capes and mixed outfits. "
        "Use open-vocabulary labels and separate left/right or layered instances when visible. Hair, weapons and non-worn "
        "props belong in non_garments. Recommend behavior=rigid for hard armor, skinned for fitted flexible pieces, cloth "
        "for free cloth regions, and mixed when both are present. This is semantic recognition, not human acceptance.\n"
        "Whole-model images are named MODEL VIEW <label>. Component evidence is named COMPONENT <exact component_id>. "
        "A component_id may be returned only when at least one attached COMPONENT image explicitly names it and the "
        "visible component matches the item. Never infer a component from filename, ordering or bounds alone. If the "
        "boundary is fused, ambiguous, or only visible in whole-model views, return an empty component_ids array and set "
        "needs_review=true. Empty component_ids means recognized semantics only, not permission to cut the mesh. Never "
        "invent triangle IDs, occluded garments, internal layers, complete body geometry or topology repair. Use stable "
        "lowercase ASCII ids and preserve the exact supplied component_id strings. Return one schema-conforming JSON "
        "object with no prose outside it.\n"
        "Source geometry inventory (paths deliberately removed):\n"
        + canonical(public_inspection)
    )


def _image(path, label, component_id, known_components):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("garment_inventory_image_invalid")
    path = path.resolve()
    data = path.read_bytes()
    if not 0 < len(data) <= MAX_IMAGE_BYTES:
        raise ValueError("garment_inventory_image_invalid")
    extension = path.suffix.lower()
    try:
        if extension == ".png":
            validate_png(data)
            mime = "image/png"
        elif extension in (".jpg", ".jpeg"):
            from provider_common import validate_jpeg

            validate_jpeg(data)
            mime = "image/jpeg"
        else:
            raise ValueError("garment_inventory_image_invalid")
    except ValueError:
        raise ValueError("garment_inventory_image_invalid") from None
    if not isinstance(label, str) or not label.strip() or any(ord(character) < 32 for character in label):
        raise ValueError("garment_inventory_image_invalid")
    if component_id is not None and component_id not in known_components:
        raise ValueError("garment_inventory_unknown_component")
    return dict(
        path=path,
        label=label,
        component_id=component_id,
        mime=mime,
        data=data,
        sha256=hashlib.sha256(data).hexdigest(),
    )


def request_inventory(config, inspection, images, directory):
    """Perform one owned request; retain its private directory on uncertainty."""
    config = validate_config(config)
    if not isinstance(inspection, dict) or inspection.get("schema_version") != 1:
        raise ValueError("garment_split_inspection_invalid")
    components = inspection.get("components")
    if not isinstance(components, list):
        raise ValueError("garment_split_inspection_invalid")
    known = {component.get("component_id") for component in components if isinstance(component, dict)}
    if len(known) != len(components):
        raise ValueError("garment_split_inspection_invalid")
    if not isinstance(images, list) or not images:
        raise ValueError("garment_inventory_images_required")
    entries = [
        _image(entry.get("path"), entry.get("label"), entry.get("component_id"), known)
        if isinstance(entry, dict)
        else None
        for entry in images
    ]
    if any(entry is None for entry in entries):
        raise ValueError("garment_inventory_image_invalid")
    attached_components = {entry["component_id"] for entry in entries if entry["component_id"] is not None}
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    prompt = inventory_prompt(inspection)
    schema = inventory_schema()
    content = [dict(type="text", text=prompt)]
    for entry in entries:
        identity = (
            "COMPONENT " + entry["component_id"] + "; view: " + entry["label"]
            if entry["component_id"] is not None
            else "MODEL VIEW " + entry["label"]
        )
        content.append(dict(type="text", text=identity))
        content.append(
            dict(
                type="image_url",
                image_url=dict(
                    url="data:" + entry["mime"] + ";base64," + base64.b64encode(entry["data"]).decode("ascii")
                ),
            )
        )
    body = dict(
        model=config["model"],
        messages=[dict(role="user", content=content)],
        response_format=dict(
            type="json_schema", json_schema=dict(name="garment_inventory", strict=True, schema=schema)
        ),
        reasoning_effort="low",
        max_tokens=16384,
        stream=False,
    )
    raw = canonical(body).encode("utf-8")
    if len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("garment_inventory_request_too_large")
    (directory / "prompt.txt").write_text(prompt, encoding="utf-8")
    (directory / "schema.json").write_text(canonical(schema), encoding="utf-8")
    (directory / "api-request.json").write_bytes(raw)
    (directory / "planner-config.json").write_text(canonical(config), encoding="utf-8")
    evidence = dict(
        inspection_sha256=hashlib.sha256(canonical(inspection).encode("utf-8")).hexdigest(),
        images=[
            dict(label=entry["label"], component_id=entry["component_id"], sha256=entry["sha256"])
            for entry in entries
        ],
        attached_component_ids=sorted(attached_components),
    )
    (directory / "evidence.json").write_text(canonical(evidence), encoding="utf-8")
    # api_planner deliberately performs no retry and never prints the credential.
    perform(config, directory)
    receipt = json.loads((directory / "api-receipt.json").read_text(encoding="utf-8"))
    document = json.loads((directory / "api-plan.json").read_text(encoding="utf-8"))
    if (
        receipt.get("request_sha256") != hashlib.sha256(raw).hexdigest()
        or receipt.get("instructions_sha256") != hashlib.sha256(canonical(document).encode("utf-8")).hexdigest()
    ):
        raise ValueError("garment_inventory_response_invalid")
    result = validate_inventory(document, known)
    for item in result["items"]:
        if not set(item["component_ids"]) <= attached_components:
            raise ValueError("garment_inventory_component_evidence_missing")
    encoded = canonical(result)
    (directory / "inventory.json").write_text(encoded, encoding="utf-8")
    response_receipt = dict(
        status="recognized",
        source_sha256=inspection.get("source_sha256"),
        inventory_sha256=hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        item_count=len(result["items"]),
        evidence_bound_item_count=sum(bool(item["component_ids"]) for item in result["items"]),
        unresolved_item_count=sum(not bool(item["component_ids"]) for item in result["items"]),
        visual_review_passed=False,
        human_confirmed=False,
        cloth_ready=False,
        api_receipt=receipt,
    )
    (directory / "inventory-receipt.json").write_text(canonical(response_receipt), encoding="utf-8")
    return result


def _assignment(value, flag):
    if "=" not in value:
        raise ValueError("garment_inventory_image_invalid")
    name, path = value.split("=", 1)
    if not name or not path:
        raise ValueError("garment_inventory_image_invalid")
    return dict(label=name, path=path, component_id=name if flag == "component" else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("inspection", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--image", action="append", default=[], help="View label=PNG/JPEG path")
    parser.add_argument("--component", action="append", default=[], help="Exact component_id=PNG/JPEG path")
    args = parser.parse_args()
    inspection = json.loads(args.inspection.read_text(encoding="utf-8"))
    images = [_assignment(value, "image") for value in args.image]
    images += [_assignment(value, "component") for value in args.component]
    result = request_inventory(json.loads(args.config.read_text(encoding="utf-8")), inspection, images, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
