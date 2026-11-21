"""Compare a fixed G01/G03 Git snapshot with a freshly exported project publication."""

import argparse
import hashlib
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

from history_git import _git, _publication
from history_records import export_binary


def refs_in(repo):
    if _git(repo, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise ValueError("Integrity verification requires complete history")
    lines = _git(repo, "for-each-ref", "--format=%(refname) %(objectname)").splitlines()
    refs = dict(line.decode("utf-8", "surrogateescape").split(" ", 1) for line in lines)
    head = _git(repo, "rev-parse", "--revs-only", "HEAD").decode("ascii").strip()
    if head:
        refs["HEAD"] = head
    return refs


def _read_object(stream, oid):
    header = stream.readline().split()
    if header == [oid, b"missing"]:
        return {"error": "missing_object"}
    if len(header) != 3 or header[0] != oid:
        raise ValueError(f"Unexpected object header for {oid.decode()}")
    _, kind, raw_size = header
    remaining = int(raw_size)
    content = hashlib.sha256()
    identity = hashlib.new("sha1" if len(oid) == 40 else "sha256", kind + b" " + raw_size + b"\0")
    while remaining:
        block = stream.read(min(remaining, 1024 * 1024))
        if not block:
            raise ValueError(f"Incomplete bytes for {oid.decode()}")
        content.update(block)
        identity.update(block)
        remaining -= len(block)
    if stream.read(1) != b"\n":
        raise ValueError(f"Missing object delimiter for {oid.decode()}")
    result = dict(type=kind.decode(), size=int(raw_size), sha256=content.hexdigest())
    if identity.hexdigest() != oid.decode():
        result.update(error="object_id_mismatch", computed_oid=identity.hexdigest())
    return result


def object_manifest(repo, refs):
    tips = "".join(oid + "\n" for oid in sorted(set(refs.values()))).encode("ascii")
    raw = _git(repo, "rev-list", "--objects", "--missing=print", "--stdin", data=tips)
    objects = {}
    names = {}
    for line in raw.split(b"\n")[:-1]:
        oid, _, name = line.partition(b" ")
        if oid.startswith(b"?"):
            objects[oid[1:].decode()] = {"error": "missing_object"}
        else:
            names[oid] = name.decode("utf-8", "surrogateescape")
    ordered = sorted(names)
    for pos in range(0, len(ordered), 2048):
        batch = ordered[pos : pos + 2048]
        # Keep large blobs off the Python heap. Batch order is exactly the request order.
        with tempfile.TemporaryFile() as stream:
            _git(repo, "cat-file", "--batch", data=b"\n".join(batch) + b"\n", stdout=stream)
            stream.seek(0)
            for oid in batch:
                detail = _read_object(stream, oid)
                if names[oid]:
                    detail["example_name"] = names[oid]
                objects[oid.decode()] = detail
    return objects


def compare(source, target, expected_refs):
    actual_refs = refs_in(source)
    if actual_refs != expected_refs:
        raise ValueError("Source HEAD or references differ from the fixed inventory")
    target_refs = refs_in(target)
    report_refs = []
    for name in sorted(actual_refs.keys() | target_refs.keys()):
        a, b = actual_refs.get(name), target_refs.get(name)
        if a is None:
            status = "unexpected"
        elif b is None:
            status = "missing"
        elif a != b:
            status = "changed"
        else:
            status = "matched"
        report_refs.append(dict(ref=name, source=a, target=b, status=status))

    left = object_manifest(source, actual_refs)
    right = object_manifest(target, target_refs)
    report_objects = []
    for oid in sorted(left.keys() | right.keys()):
        a, b = left.get(oid), right.get(oid)
        if a is None:
            status = "unexpected"
        elif b is None:
            status = "missing"
        elif "error" in a or "error" in b:
            status = "unverified"
        elif any(a[key] != b[key] for key in ("type", "size", "sha256")):
            status = "changed"
        else:
            status = "matched"
        report_objects.append(dict(oid=oid, source=a, target=b, status=status))
    ref_counts = Counter(row["status"] for row in report_refs)
    object_counts = Counter(row["status"] for row in report_objects)
    return {
        "complete": ref_counts["matched"] == len(report_refs) and object_counts["matched"] == len(report_objects),
        "ref_status_counts": dict(ref_counts),
        "object_status_counts": dict(object_counts),
        "refs": report_refs,
        "objects": report_objects,
    }


def audit_git_history(source_repo, inventory, database, tenant, project, revision):
    raw = Path(inventory).read_bytes()
    snapshot = json.loads(raw)
    source = snapshot["source"].removeprefix("https://github.com/").removesuffix(".git")
    origin = _git(source_repo, "config", "--get", "remote.origin.url").decode().strip()
    publication = _publication(database, tenant, project, revision)
    if origin != f"https://github.com/{source}.git" or publication["source"] != source:
        raise ValueError("Source repository identity differs from inventory or publication")
    refs = dict(snapshot.get("source_refs", snapshot.get("refs", {})))
    refs["HEAD"] = snapshot.get("main", snapshot.get("head"))
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        bundle = stage / "history.bundle"
        exported = export_binary(database, tenant, project, revision, f"github:{source}/history.bundle", bundle)
        target = stage / "target.git"
        _git(stage, "clone", "--mirror", "--template=", "--quiet", "--", str(bundle), str(target))
        report = compare(source_repo, target, refs)
    _publication(database, tenant, project, revision)
    return dict(publication=publication, inventory_sha256=hashlib.sha256(raw).hexdigest(), exported=exported, **report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("source_repo", "inventory", "database"):
        parser.add_argument(arg, type=Path)
    for arg in ("tenant", "project", "revision"):
        parser.add_argument("--" + arg, required=True)
    result = audit_git_history(**vars(parser.parse_args()))
    json.dump(result, sys.stdout, indent=2)
    print()
    sys.exit(0 if result["complete"] else 1)
