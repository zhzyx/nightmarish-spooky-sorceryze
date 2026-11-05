"""AINative v1 exchange contract validator; no provider or engine dependency.

Artifacts are immutable revisions in a self-contained manifest. Extensions retain
their payload; validation here covers references and binding claims, not geometry.
"""
import argparse
import json
from pathlib import Path

LEVELS = ("unbound", "semantic_mapped", "animation_retargeted",
          "target_bound", "roundtrip_verified")


def validate(manifest):
    """Return diagnostics without mutating or normalizing source data."""
    errors = []

    def check(ok, path, message):
        if not ok:
            errors.append(f"{path}: {message}")
        return ok

    if not check(isinstance(manifest, dict), "$", "expected object"):
        return errors
    check(type(manifest.get("schema_version")) is int and manifest["schema_version"] == 1,
          "$.schema_version", "unsupported version")
    assets = manifest.get("artifacts")
    if not check(isinstance(assets, list), "$.artifacts", "expected array"):
        return errors
    index = {}
    for i, asset in enumerate(assets):
        path = f"$.artifacts[{i}]"
        if not check(isinstance(asset, dict), path, "expected object"):
            continue
        aid = asset.get("id")
        if not check(isinstance(aid, str) and bool(aid.strip()), path, "id required"):
            continue
        if not check(aid not in index, path, "duplicate id"):
            continue
        index[aid] = asset
        check(isinstance(asset.get("type"), str) and bool(asset["type"].strip()),
              path, "type required (extension types allowed)")
        check(isinstance(asset.get("revision"), str) and bool(asset["revision"].strip()),
              path, "immutable revision required")
        check(isinstance(asset.get("payload"), dict), path, "payload object required")
    edges = {aid: set() for aid in index}

    def reference(ref, owner, path, allowed=None, production=True):
        if not check(isinstance(ref, dict), path, "expected versioned reference"):
            return None
        target = ref.get("id")
        if not check(isinstance(target, str) and target in index, path, "missing artifact"):
            return None
        obj = index[target]
        check(ref.get("revision") == obj.get("revision") and bool(ref.get("revision")),
              path, "revision mismatch")
        if allowed:
            check(obj.get("type") in allowed, path, "incompatible artifact type")
        if production:
            edges[owner].add(target)
        return obj

    for aid, asset in index.items():
        path = f"artifact:{aid}"
        deps = asset.get("dependencies", [])
        if check(isinstance(deps, list), path, "dependencies must be array"):
            for dep in deps:
                reference(dep, aid, path + ".dependencies")
        context = asset.get("context", [])
        if check(isinstance(context, list), path, "context must be array"):
            for entry in context:
                if not check(isinstance(entry, dict), path, "context entry must be object"):
                    continue
                check(isinstance(entry.get("role"), str) and bool(entry["role"]),
                      path, "context role required")
                check(isinstance(entry.get("scope"), str) and bool(entry["scope"]),
                      path, "context scope required")
                check(entry.get("strength") in ("reference", "constraint"),
                      path, "context strength required")
                has_text, has_ref = "text" in entry, "artifact" in entry
                check(has_text != has_ref, path, "context needs exactly one text or artifact")
                if has_text:
                    check(isinstance(entry["text"], str) and bool(entry["text"].strip()),
                          path, "context text required")
                if has_ref:
                    reference(entry["artifact"], aid, path + ".context")
        binding = asset.get("binding")
        if binding is None:
            continue
        if not check(isinstance(binding, dict), path, "binding must be object"):
            continue
        level = binding.get("level")
        check(level in LEVELS, path, "unknown compatibility level")
        if level != "unbound":
            reference(binding.get("skeleton"), aid, path + ".skeleton",
                      ("skeleton_profile",))
        if asset.get("type") == "garment" and level in ("target_bound", "roundtrip_verified"):
            reference(binding.get("fit_target"), aid, path + ".fit_target",
                      ("avatar_profile", "character"))
        if level == "roundtrip_verified":
            report = reference(binding.get("evidence"), aid, path + ".evidence",
                               ("validation_report",), production=False)
            if report is not None:
                payload = report.get("payload")
                check(isinstance(payload, dict) and payload.get("subject") ==
                      {"id": aid, "revision": asset.get("revision")},
                      path, "evidence subject must match exact artifact revision")

    # Iterative traversal supports large dependency chains without recursion failure.
    colors = {}
    for start in edges:
        stack = [(start, False)]
        while stack:
            node, exiting = stack.pop()
            if exiting:
                colors[node] = 2
                continue
            if colors.get(node) == 1:
                errors.append(f"artifact:{node}: dependency cycle")
                continue
            if colors.get(node) == 2:
                continue
            colors[node] = 1
            stack.append((node, True))
            stack.extend((dep, False) for dep in sorted(edges[node], reverse=True))
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        errors = validate(json.loads(args.manifest.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        errors = [str(exc)]
    print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
