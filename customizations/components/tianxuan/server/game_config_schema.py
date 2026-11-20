"""Validated, portable game configuration stored in a versioned Wenqu document."""

from __future__ import annotations

import json
import math
import re
from typing import Any

ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
BLOCK = re.compile(r"^```game-config\s*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)
TYPES = {"number", "integer", "boolean", "string", "enum", "json", "reference"}
MAX_BYTES = 1_048_576
MAX_SAFE_INTEGER = 2**53 - 1


def _portable_numbers(value: Any) -> None:
    if type(value) is int or (type(value) is float and value.is_integer()):
        if abs(value) > MAX_SAFE_INTEGER:
            raise ValueError("integer values must fit the portable safe integer range; use strings for large IDs")
    elif isinstance(value, dict):
        for item in value.values():
            _portable_numbers(item)
    elif isinstance(value, list):
        for item in value:
            _portable_numbers(item)


def _object(value: Any, allowed: set[str], required: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) - allowed or required - set(value):
        raise ValueError(f"{label}: missing or unknown fields")


def _text(value: Any, label: str, maximum: int = 4096, *, required: bool = False) -> None:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ValueError(f"{label}: invalid text")


def _id(value: Any, label: str) -> None:
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError(f"{label}: use a letter followed by up to 63 letters, digits, _ or -")


def _number(value: Any) -> bool:
    return type(value) in (int, float) and (type(value) is int or math.isfinite(value))


def validate_features(features: Any) -> list[dict[str, Any]]:
    if not isinstance(features, list) or len(features) > 200:
        raise ValueError("features: expected an array with at most 200 features")
    try:
        _portable_numbers(features)
        encoded = json.dumps(features, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode()) > MAX_BYTES:
            raise ValueError("configuration exceeds 1 MiB")
    except (TypeError, OverflowError, RecursionError) as error:
        raise ValueError("configuration must be finite JSON") from error
    feature_ids: set[str] = set()
    entries: dict[tuple[str, str], dict[str, Any]] = {}
    for feature in features:
        _object(feature, {"id", "name", "description", "document_id", "entries"}, {"id", "name", "entries"}, "feature")
        _id(feature["id"], "feature id")
        _text(feature["name"], "feature name", 200, required=True)
        _text(feature.get("description", ""), "feature description")
        if feature.get("document_id") is not None:
            _text(feature["document_id"], "document id", 200, required=True)
        if feature["id"] in feature_ids:
            raise ValueError(f"duplicate feature id: {feature['id']}")
        feature_ids.add(feature["id"])
        if not isinstance(feature["entries"], list):
            raise ValueError("entries must be an array")
        for entry in feature["entries"]:
            _object(
                entry,
                {"id", "name", "kind", "type", "value", "default", "description", "min", "max", "options"},
                {"id", "name", "kind", "type", "value", "default"},
                "entry",
            )
            _id(entry["id"], "entry id")
            _text(entry["name"], "entry name", 200, required=True)
            _text(entry.get("description", ""), "entry description")
            if (
                entry["kind"] not in ("parameter", "content")
                or not isinstance(entry["type"], str)
                or entry["type"] not in TYPES
            ):
                raise ValueError("invalid entry kind or type")
            key = (feature["id"], entry["id"])
            if key in entries:
                raise ValueError(f"duplicate entry id: {key[0]}/{key[1]}")
            entries[key] = entry
            if len(entries) > 2000:
                raise ValueError("configuration exceeds 2000 entries")
            for bound in ("min", "max"):
                if bound in entry and (entry["type"] not in ("number", "integer") or not _number(entry[bound])):
                    raise ValueError(f"{bound}: expected a finite numeric bound on a number/integer")
            if "min" in entry and "max" in entry and entry["min"] > entry["max"]:
                raise ValueError("min must not exceed max")
            if entry["type"] == "enum":
                options = entry.get("options")
                if (
                    not isinstance(options, list)
                    or not options
                    or len(options) > 200
                    or any(
                        not isinstance(option, str)
                        or not option
                        or len(option) > 200
                        or "\n" in option
                        or "\r" in option
                        for option in options
                    )
                    or len(set(options)) != len(options)
                ):
                    raise ValueError("enum options must be distinct nonempty single-line strings")
            elif "options" in entry:
                raise ValueError("options are only valid for enum entries")
    for (feature_id, entry_id), entry in entries.items():
        for field in ("value", "default"):
            value, kind = entry[field], entry["type"]
            valid = True
            if kind in ("number", "integer"):
                valid = _number(value) and (kind != "integer" or type(value) is int)
                if valid:
                    valid = ("min" not in entry or value >= entry["min"]) and (
                        "max" not in entry or value <= entry["max"]
                    )
            elif kind == "boolean":
                valid = type(value) is bool
            elif kind in ("string", "enum"):
                valid = isinstance(value, str) and (kind != "enum" or value in entry["options"])
            elif kind == "reference":
                valid = (
                    isinstance(value, dict)
                    and set(value) == {"feature_id", "entry_id"}
                    and isinstance(value["feature_id"], str)
                    and isinstance(value["entry_id"], str)
                    and (value["feature_id"], value["entry_id"]) in entries
                )
            if not valid:
                raise ValueError(f"{feature_id}/{entry_id}.{field}: invalid {kind} or constraint/reference violation")
    # Detach nested caller-owned values; one validated snapshot is the authority.
    return json.loads(encoded)


def parse_config(body: str) -> list[dict[str, Any]]:
    if not isinstance(body, str) or len(body.encode()) > MAX_BYTES + 8192:
        raise ValueError("game configuration document exceeds limit")
    blocks = BLOCK.findall(body)
    if len(blocks) != 1:
        raise ValueError("game configuration requires exactly one game-config fenced JSON block")

    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON field: {key}")
            result[key] = value
        return result

    try:
        payload = json.loads(blocks[0], object_pairs_hook=unique_pairs)
    except (json.JSONDecodeError, RecursionError) as error:
        raise ValueError("invalid configuration JSON") from error
    _object(payload, {"schema_version", "features"}, {"schema_version", "features"}, "configuration")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise ValueError("unsupported configuration schema version")
    return validate_features(payload["features"])


def config_markdown(features: Any) -> str:
    payload = {"schema_version": 1, "features": validate_features(features)}
    # Compact JSON guarantees the same size budget as validation.
    return (
        "# Game configuration\n\n```game-config\n"
        + json.dumps(payload, ensure_ascii=False, allow_nan=False)
        + "\n```\n"
    )


def replace_config(body: str, features: Any) -> str:
    """Replace only the authoritative block, preserving collaborative prose byte-for-byte."""
    parse_config(body)
    replacement = BLOCK.search(config_markdown(features)).group(0)
    return BLOCK.sub(lambda _: replacement, body, count=1)
