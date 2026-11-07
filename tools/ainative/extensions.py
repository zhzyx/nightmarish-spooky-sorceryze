"""Serializable domain extension contracts, independent of execution and Godot UI."""

import copy
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING or __package__:
    from .contracts import validate
else:
    from contracts import validate


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    """Reject non-JSON and non-finite values rather than silently losing data."""

    def walk(item):
        if isinstance(item, dict):
            require(all(isinstance(k, str) for k in item), "JSON keys must be strings")
            for child in item.values():
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)
        else:
            require(item is None or type(item) in (str, bool, int, float), "JSON value required")
            require(type(item) is not float or math.isfinite(item), "finite number required")

    walk(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def names(value):
    return isinstance(value, list) and all(text(v) for v in value) and len(set(value)) == len(value)


def validate_schema(schema):
    """Small explicit schema dialect: flat typed properties, required keys, enums."""
    require(isinstance(schema, dict) and set(schema) <= {"properties", "required"}, "unsupported schema keyword")
    props, required = schema.get("properties", {}), schema.get("required", [])
    require(isinstance(props, dict) and all(text(k) for k in props), "invalid properties")
    require(names(required) and set(required) <= set(props), "invalid required properties")
    for spec in props.values():
        require(isinstance(spec, dict) and set(spec) <= {"type", "enum"}, "unsupported property keyword")
        require(
            spec.get("type") in ("string", "integer", "number", "boolean", "object", "array"),
            "unsupported property type",
        )
        if "enum" in spec:
            require(isinstance(spec["enum"], list) and bool(spec["enum"]), "enum must be nonempty")
            canonical(spec["enum"])


def validate_parameters(schema, params):
    validate_schema(schema)
    canonical(params)
    require(isinstance(params, dict), "parameters must be object")
    props = schema.get("properties", {})
    require(set(params) <= set(props), "unknown parameter")
    require(set(schema.get("required", [])) <= set(params), "missing parameter")
    kinds = {
        "string": (str,),
        "integer": (int,),
        "number": (int, float),
        "boolean": (bool,),
        "object": (dict,),
        "array": (list,),
    }
    for key, value in params.items():
        spec = props[key]
        require(type(value) in kinds[spec["type"]], "parameter type mismatch: " + key)
        if "enum" in spec:
            require(canonical(value) in [canonical(v) for v in spec["enum"]], "parameter enum mismatch: " + key)


class NodeRegistry:
    """Definitions are copied at both boundaries; a registered version cannot change."""

    def __init__(self):
        self._nodes = {}

    def register(self, definition):
        canonical(definition)
        require(isinstance(definition, dict), "node definition must be object")
        require(
            set(definition) == {"id", "version", "inputs", "outputs", "context_types", "parameters", "capabilities"},
            "invalid node fields",
        )
        require(text(definition["id"]) and text(definition["version"]), "node identity required")
        for field in ("inputs", "outputs"):
            ports = definition[field]
            require(isinstance(ports, dict) and all(text(k) for k in ports), "invalid ports")
            for port in ports.values():
                require(isinstance(port, dict) and set(port) == {"types", "required"}, "invalid port")
                require(
                    names(port["types"]) and bool(port["types"]) and type(port["required"]) is bool,
                    "invalid port types",
                )
        require(bool(definition["outputs"]), "output port required")
        require(names(definition["context_types"]) and names(definition["capabilities"]), "invalid capabilities")
        validate_schema(definition["parameters"])
        key = (definition["id"], definition["version"])
        require(
            key not in self._nodes or canonical(self._nodes[key]) == canonical(definition),
            "registered node version is immutable",
        )
        self._nodes[key] = copy.deepcopy(definition)

    def get(self, node_id, version):
        require(text(node_id) and text(version), "node identity required")
        require((node_id, version) in self._nodes, "unregistered node version")
        return copy.deepcopy(self._nodes[node_id, version])


def provider_manifest(value):
    canonical(value)
    require(
        isinstance(value, dict)
        and set(value) == {"id", "version", "model", "model_version", "capabilities", "context_types", "available"},
        "invalid provider manifest",
    )
    require(
        all(text(value[k]) for k in ("id", "version", "model", "model_version")), "provider and model versions required"
    )
    require(names(value["capabilities"]) and names(value["context_types"]), "invalid provider capabilities")
    require(type(value["available"]) is bool, "available must be boolean")
    return copy.deepcopy(value)


def validate_invocation(registry, request, manifest, provider):
    """Validate one ready invocation, returning a content-sensitive reproducibility key."""
    canonical(request)
    require(
        isinstance(request, dict) and set(request) == {"node", "version", "inputs", "parameters", "context"},
        "invalid invocation",
    )
    require(text(request["node"]) and text(request["version"]), "node identity required")
    definition = registry.get(request["node"], request["version"])
    canonical(manifest)
    require(not validate(manifest), "invalid artifact manifest")
    index = {a["id"]: a for a in manifest["artifacts"]}

    def resolve(ref):
        require(isinstance(ref, dict) and set(ref) == {"id", "revision"}, "versioned reference required")
        require(text(ref["id"]) and ref["id"] in index, "missing input artifact")
        asset = index[ref["id"]]
        require(ref["revision"] == asset["revision"], "stale input revision")
        return asset

    inputs = request["inputs"]
    require(isinstance(inputs, dict) and set(inputs) <= set(definition["inputs"]), "unknown input port")
    for key, port in definition["inputs"].items():
        require(not port["required"] or key in inputs, "missing required input: " + key)
        if key in inputs:
            require(resolve(inputs[key])["type"] in port["types"], "input type mismatch: " + key)
    validate_parameters(definition["parameters"], request["parameters"])
    provider = provider_manifest(provider)
    require(provider["available"], "provider unavailable")
    require(set(definition["capabilities"]) <= set(provider["capabilities"]), "provider lacks node capability")
    context = request["context"]
    require(isinstance(context, list), "context must be array")
    for entry in context:
        require(
            isinstance(entry, dict)
            and set(entry) in ({"text", "role", "scope", "strength"}, {"artifact", "role", "scope", "strength"}),
            "invalid context entry",
        )
        require(
            text(entry["role"]) and text(entry["scope"]) and entry["strength"] in ("reference", "constraint"),
            "invalid context semantics",
        )
        kind = resolve(entry["artifact"])["type"] if "artifact" in entry else "text"
        require("text" not in entry or text(entry["text"]), "context text required")
        require(kind in definition["context_types"] and kind in provider["context_types"], "unsupported context type")
    # Conservative: all bundled assets contribute, including profile payloads.
    return hashlib.sha256(canonical([definition, request, manifest, provider]).encode()).hexdigest()


STATES = {
    "queued": {"queued", "running", "succeeded", "failed", "cancelled"},
    "running": {"running", "succeeded", "failed", "cancelled"},
    "succeeded": {"succeeded"},
    "failed": {"failed"},
    "cancelled": {"cancelled"},
}


def validate_job(snapshot, previous=None):
    canonical(snapshot)
    require(
        isinstance(snapshot, dict) and set(snapshot) == {"job_id", "state", "outputs", "error"}, "invalid job snapshot"
    )
    require(
        text(snapshot["job_id"]) and text(snapshot["state"]) and snapshot["state"] in STATES,
        "invalid job identity/state",
    )
    require(isinstance(snapshot["outputs"], dict), "outputs must be object")
    if snapshot["state"] == "succeeded":
        require(bool(snapshot["outputs"]) and snapshot["error"] is None, "success needs outputs and no error")
    else:
        require(not snapshot["outputs"], "only succeeded jobs expose outputs")
        require(
            text(snapshot["error"]) if snapshot["state"] == "failed" else snapshot["error"] is None, "invalid job error"
        )
    if previous is not None:
        validate_job(previous)
        require(snapshot["job_id"] == previous["job_id"], "job identity changed")
        require(snapshot["state"] in STATES[previous["state"]], "illegal job transition")
        if previous["state"] in ("succeeded", "failed", "cancelled"):
            require(canonical(snapshot) == canonical(previous), "terminal receipt is immutable")


def validate_outputs(registry, node_id, version, outputs, manifest):
    canonical(outputs)
    canonical(manifest)
    require(not validate(manifest), "invalid output manifest")
    definition = registry.get(node_id, version)
    ports = definition["outputs"]
    require(isinstance(outputs, dict) and set(outputs) <= set(ports), "unknown output port")
    index = {a["id"]: a for a in manifest["artifacts"]}
    for key, port in ports.items():
        require(not port["required"] or key in outputs, "missing output")
        if key in outputs:
            ref = outputs[key]
            require(isinstance(ref, dict) and set(ref) == {"id", "revision"}, "invalid output reference")
            require(text(ref["id"]) and ref["id"] in index, "missing output artifact")
            asset = index[ref["id"]]
            require(
                ref["revision"] == asset["revision"] and asset["type"] in port["types"], "output type/revision mismatch"
            )


class Provider(Protocol):
    def describe(self) -> dict[str, Any]: ...
    def submit(self, request: dict[str, Any], manifest: dict[str, Any], idempotency_key: str) -> dict[str, Any]: ...
    def poll(self, job_id: str) -> dict[str, Any]: ...
    def cancel(self, job_id: str) -> dict[str, Any]: ...


class PublishAdapter(Protocol):
    """Encoder must be pure: no filesystem writes or source mutation."""

    def encode(self, manifest: dict[str, Any]) -> bytes: ...


def publish_new(adapter: PublishAdapter, manifest: dict[str, Any], target):
    """Atomically expose one new file; never overwrite a source or existing target.

    The trusted adapter encodes in memory. A same-directory temporary is hard-linked
    with exclusive creation, then removed. Filesystems without hardlinks fail closed.
    Multi-file Godot scene publication belongs to the domain PublishAdapter layer.
    """
    canonical(manifest)
    require(not validate(manifest), "invalid publication manifest")
    target = Path(target)
    require(target.parent.is_dir(), "publication directory must exist")
    payload = adapter.encode(copy.deepcopy(manifest))
    require(isinstance(payload, bytes), "adapter must return bytes")
    fd, temporary = tempfile.mkstemp(prefix=".ainative-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {"path": str(target), "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}
