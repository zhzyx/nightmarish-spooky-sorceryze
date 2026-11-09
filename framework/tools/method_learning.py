"""Append and recall scoped method-learning events through the Git-file Diting host."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = "customizations/platforms/data-collection/git-files/storage/diting_files.py"
DEFAULT_HOST_FILES = {
    ADAPTER: "abaabc29d3dfc0091bfe2652f5afb98960b39a984c6b122fc86a82d43b6a2425",
    "customizations/platforms/development/git/git_batch.py": "321fa41c59ec0e3b5532cca81450918530c7c091ac89ee14cec1fc53a61008c7",
}
DITING = {}


def bind_host(host_root=None):
    """The operator selects the installed adapter independently of the evidence repository."""
    if host_root is None:
        host_root = ROOT
        for name, expected in DEFAULT_HOST_FILES.items():
            path = host_root / name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError("Supply --host-root with a trusted Gonggong installation.")
    adapter = Path(host_root).resolve() / ADAPTER
    if not adapter.is_file():
        raise ValueError("Git-file host adapter unavailable. Supply --host-root with a trusted Gonggong installation.")
    DITING.update(runpy.run_path(str(adapter)))
FIELDS = {
    "propose": {"method", "when", "counterexample", "trial_plan"},
    "revise": {"method", "when", "counterexample", "trial_plan"},
    "verify": {"test", "expected", "observed"},
    "applied": {"task", "observed"},
    "counterexample": {"observed"},
    "withdraw": {"reason"},
}
ALLOWED = {
    None: {"propose"},
    "candidate": {"verify", "revise", "counterexample", "withdraw"},
    "verified": {"applied", "revise", "counterexample", "withdraw"},
    "inactive": {"revise"},
}
STATE = {
    "propose": "candidate", "revise": "candidate", "verify": "verified",
    "applied": "verified", "counterexample": "inactive", "withdraw": "inactive",
}


def name(value):
    if not isinstance(value, str) or not re.fullmatch("[a-z0-9][a-z0-9_-]{0,79}", value):
        raise ValueError("Expected a lower-case scope, tenant or lesson identifier")
    return value


def scope_request(scope):
    return "learning-" + name(scope)


def event_id(scope, lesson, revision):
    return "learn-" + DITING["digest"]([scope, lesson, revision])


def inside(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("Expected a project-relative path")
    path = (root / relative).resolve()
    path.relative_to(root)
    return path


def evidence(root, tenant, refs):
    if not isinstance(refs, list) or not refs:
        raise ValueError("A revision-pinned evidence file is required")
    for ref in refs:
        if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
            raise ValueError("Evidence requires path and sha256")
        path = inside(root, ref["path"])
        parts = [part.casefold() for part in path.relative_to(root).parts]
        if parts[:2] in (["gonggong-diting-data", "events"], ["olympus-hermes-data", "events"]):
            if len(parts) < 3 or parts[2] != tenant:
                raise ValueError("Evidence outside tenant")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if ref["sha256"] != actual:
            raise ValueError("Evidence changed: " + ref["path"])


def store_dir(repo, tenant, scope):
    root, data = DITING["location"](repo)
    meta = DITING["read"](data / "dataset.json")
    if meta.get("origin_framework") != "gonggong" or meta.get("storage") != "immutable_event_json":
        raise ValueError("Expected a registered Gonggong Diting Git-file dataset")
    path = data / "events" / name(tenant) / scope_request(scope)
    if path.resolve() != path:
        raise ValueError("Linked event directory")
    return root, path


def stored(path):
    if path.resolve() != path:
        raise ValueError("Linked event file")
    raw = DITING["read"](path)
    if "sha256" not in raw:
        raise ValueError("Missing stored event checksum")
    return DITING["event"](raw)


def origin_event(root, tenant, relative):
    path = inside(root, relative)
    origin = stored(path)
    expected = root / "gonggong-diting-data/events" / tenant / origin["request_id"] / (origin["event_id"] + ".json")
    if origin["tenant_id"] != tenant or path != expected:
        raise ValueError("Origin event outside tenant")
    return origin


def validate_action(payload):
    action = payload["action"]
    if action not in FIELDS or set(payload["details"]) != FIELDS[action]:
        raise ValueError("Invalid learning action or detail fields")
    if any(not isinstance(s, str) or not s.strip() for s in payload["details"].values()):
        raise ValueError("Nonempty learning details required")
    revision = payload["revision"]
    if type(revision) is not int or revision < 1:
        raise ValueError("Positive revision required")
    if action == "verify" and payload["details"]["expected"] != payload["details"]["observed"]:
        raise ValueError("Trial failed; record counterexample with the observed result")


def project(events, tenant, scope):
    lessons = {}
    for event in sorted(events, key=lambda e: e["payload"]["revision"]):
        p = event["payload"]
        validate_action(p)
        lesson = name(p["lesson"])
        prior = lessons.get(lesson, {})
        rev, action = p["revision"], p["action"]
        if (event["tenant_id"] != tenant or event["request_id"] != scope_request(scope)
                or p["scope"] != scope or event["kind"] != "analysis"
                or event["event_id"] != event_id(scope, lesson, rev)
                or p["previous"] != prior.get("head") or rev != prior.get("revision", 0) + 1
                or action not in ALLOWED[prior.get("state")]):
            raise ValueError("Invalid learning history or stale predecessor")
        candidate = action in {"propose", "revise"}
        lessons[lesson] = {
            "lesson": lesson, "revision": rev, "head": event["sha256"], "state": STATE[action],
            "method": p["details"] if candidate else prior["method"],
            "evidence": ([] if candidate else prior["evidence"]) + p["evidence"],
            "origins": ([] if candidate else prior["origins"]) + [p["origin"]],
        }
    return lessons


def history(folder):
    events = []
    for path in folder.glob("*.json"):
        event = stored(path)
        if path.stem != event["event_id"]:
            raise ValueError("Event filename mismatch")
        events.append(event)
    return events


def append(repo, tenant, entry):
    scope, lesson = name(entry["scope"]), name(entry["lesson"])
    root, folder = store_dir(repo, tenant, scope)
    payload = {key: entry[key] for key in ("scope", "lesson", "revision", "previous", "action", "details", "evidence")}
    validate_action(payload)
    origin = origin_event(root, tenant, entry["origin"])
    payload["origin"] = {"path": entry["origin"], "sha256": origin["sha256"]}
    revision = payload["revision"]
    refs = [origin["event_id"]]
    if revision > 1:
        refs.append(event_id(scope, lesson, revision - 1))
    event = DITING["event"]({
        "schema_version": 1, "tenant_id": tenant, "request_id": scope_request(scope),
        "event_id": event_id(scope, lesson, revision), "kind": "analysis", "agent": origin["agent"],
        "source_ref": origin["source_ref"], "occurred_at": entry["occurred_at"],
        "evidence_refs": refs, "payload": payload,
    })
    path = folder / (event["event_id"] + ".json")

    def replay():
        if stored(path) != event:
            raise ValueError("Revision occupied by another event")
        return {"head": event["sha256"], "state": "recorded_file", "idempotent": True}

    if path.exists():
        return replay()
    evidence(root, tenant, payload["evidence"])
    # Check this lesson only. Each ordinal has one immutable filename, so competing
    # transitions from the same head cannot both win the atomic create below.
    chain = [stored(folder / (event_id(scope, lesson, i) + ".json")) for i in range(1, revision)]
    latest = project([*chain, event], tenant, scope)[lesson]
    if latest["state"] == "verified":
        evidence(root, tenant, latest["evidence"])
    try:
        DITING["atomic_new"](path, event)
    except FileExistsError:
        return replay()
    return {"head": event["sha256"], "state": "recorded_file", "idempotent": False}


def recall(repo, tenant, scope):
    root, folder = store_dir(repo, tenant, scope)
    lessons = project(history(folder), tenant, scope)
    result, unavailable = [], []
    for key, lesson in sorted(lessons.items()):
        if lesson["state"] != "verified":
            continue
        try:
            evidence(root, tenant, lesson["evidence"])
            for ref in lesson["origins"]:
                if origin_event(root, tenant, ref["path"])["sha256"] != ref["sha256"]:
                    raise ValueError("Origin event changed: " + ref["path"])
        except (OSError, ValueError) as exc:
            unavailable.append({"lesson": key, "reason": str(exc)})
        else:
            result.append(lesson)
    return {"tenant": tenant, "scope": scope, "lessons": result, "unavailable": unavailable}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--host-root", type=Path, help="Trusted installation containing the Git-file adapter")
    parser.add_argument("--tenant", required=True)
    commands = parser.add_subparsers(required=True, dest="command")
    commands.add_parser("append").add_argument("input", type=Path)
    commands.add_parser("recall").add_argument("scope")
    commands.add_parser("status").add_argument("scope")
    commands.add_parser("scopes")
    args = parser.parse_args()
    bind_host(args.host_root)
    if args.command == "append":
        result = append(args.repo, args.tenant, DITING["read"](args.input))
    elif args.command == "scopes":
        _, folder = store_dir(args.repo, args.tenant, "catalog")
        result = sorted(name(p.name.removeprefix("learning-")) for p in folder.parent.glob("learning-*") if p.is_dir())
    elif args.command == "status":
        _, folder = store_dir(args.repo, args.tenant, args.scope)
        result = project(history(folder), args.tenant, args.scope)
    else:
        result = recall(args.repo, args.tenant, args.scope)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (KeyError, ValueError, OSError, TypeError) as exc:
        sys.exit(str(exc))

