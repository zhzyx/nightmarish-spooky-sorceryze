"""Audit LFS payloads and pinned submodule revisions of an immutable migration snapshot."""

import argparse
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from history_git import _git

LFS_VERSIONS = {
    b"version https://git-lfs.github.com/spec/v1",
    b"version https://hawser.github.com/spec/v1",
}


def _batch(repo, objects):
    for offset in range(0, len(objects), 512):
        chunk = objects[offset : offset + 512]
        request = b"".join(oid + b"\n" for oid, _, _ in chunk)
        stream = io.BytesIO(_git(repo, "cat-file", "--batch", data=request))
        for oid, kind, size in chunk:
            if stream.readline().split() != [oid, kind, str(size).encode()]:
                raise ValueError("Reachable Git object changed during scan")
            yield oid.decode(), kind, stream.read(size)
            if stream.read(1) != b"\n":
                raise ValueError("Invalid Git batch framing")


def _tree_entries(raw, oid_bytes):
    offset = 0
    while offset < len(raw):
        space = raw.index(b" ", offset)
        nul = raw.index(b"\0", space)
        end = nul + 1 + oid_bytes
        if end > len(raw):
            raise ValueError("Incomplete Git tree")
        yield raw[offset:space], raw[space + 1 : nul], raw[nul + 1 : end].hex()
        offset = end


def _pointer(blob, raw):
    lines = raw.splitlines()
    if not lines or lines[0] not in LFS_VERSIONS:
        return None
    digests = [line[4:] for line in lines[1:] if line.startswith(b"oid ")]
    sizes = [line[5:] for line in lines[1:] if line.startswith(b"size ")]
    if (
        len(digests) != 1
        or not re.fullmatch(b"sha256:[0-9a-f]{64}", digests[0])
        or len(sizes) != 1
        or not sizes[0].isdigit()
    ):
        return {"pointer_blob": blob, "status": "invalid_pointer"}
    return {"pointer_blob": blob, "oid": digests[0][7:].decode(), "size": int(sizes[0])}


def _lfs_result(root, pointer):
    oid = pointer["oid"]
    try:
        with (root / oid[:2] / oid[2:4] / oid).open("rb") as stream:
            checksum = hashlib.sha256()
            size = 0
            while block := stream.read(1024 * 1024):
                checksum.update(block)
                size += len(block)
    except FileNotFoundError:
        return dict(pointer, status="missing_payload")
    digest = checksum.hexdigest()
    status = "verified" if digest == oid and size == pointer["size"] else "payload_mismatch"
    return dict(pointer, status=status, actual_sha256=digest, actual_size=size)


def _pin_result(repo, oid):
    if repo is None:
        return {"status": "missing_repository"}
    repo = Path(repo)
    # Git walks up from arbitrary directories. A binding must identify a repository root.
    if not (repo / ".git").exists() and not ((repo / "HEAD").is_file() and (repo / "objects").is_dir()):
        return {"status": "missing_repository"}
    request = oid.encode() + b"\n"
    output = _git(repo, "cat-file", "--batch-check", data=request).split()
    if output == [oid.encode(), b"missing"]:
        return {"status": "missing_revision"}
    if output[1] != b"commit":
        return {"status": "not_a_commit"}
    data = _git(repo, "cat-file", "commit", oid)
    obj = b"commit " + str(len(data)).encode() + b"\0" + data
    actual = hashlib.new("sha1" if len(oid) == 40 else "sha256", obj).hexdigest()
    return {
        "status": "verified" if actual == oid else "revision_mismatch",
        "actual_oid": actual,
        "commit_tree": data.splitlines()[0].removeprefix(b"tree ").decode("ascii"),
    }


def _pins(mirror, refs, commits, links, parents, modules):
    if not links:
        return []
    # Each distinct (path, pin) keeps a concrete historical root for replay.
    roots = {}
    for oid, _, data in _batch(mirror, commits):
        roots.setdefault(data.splitlines()[0].removeprefix(b"tree ").decode(), oid)
    tips = "".join(oid + "^{}\n" for oid in sorted(set(refs.values()))).encode()
    for line in _git(mirror, "cat-file", "--batch-check", data=tips).splitlines():
        oid, kind, _ = line.split()
        if kind == b"tree":
            roots.setdefault(oid.decode(), None)
    found = {}
    for tree, name, pin in links:
        pending = [(tree, name)]
        seen = set()
        while pending:
            current, path = pending.pop()
            if (current, path) in seen:
                continue
            seen.add((current, path))
            if current in roots:
                found.setdefault((path, pin), (current, roots[current]))
            pending.extend((parent, directory + b"/" + path) for parent, directory in parents[current])
    results = []
    for (name, pin), (tree, commit) in sorted(found.items()):
        path = name.decode("utf-8", "surrogateescape")
        result = _pin_result(modules.get(path), pin)
        results.append(dict(path=path, revision=pin, root_tree=tree, example_commit=commit, **result))
    return results


def audit_external_objects(mirror, inventory, *, lfs_root=None, modules=None):
    """Read the G01 inventory or G03 git-report and operator-supplied local object stores."""
    mirror = Path(mirror)
    inventory_bytes = Path(inventory).read_bytes()
    snapshot = json.loads(inventory_bytes)
    refs = snapshot.get("source_refs", snapshot.get("refs"))
    head = snapshot.get("main", snapshot.get("head"))
    origin = _git(mirror, "config", "--get", "remote.origin.url").decode().strip()
    source = snapshot["source"]
    expected = source if source.startswith("https://") else f"https://github.com/{source}.git"
    ref_rows = _git(mirror, "for-each-ref", "--format=%(refname) %(objectname)").decode().splitlines()
    actual_refs = dict(line.split(" ", 1) for line in ref_rows)
    actual_head = _git(mirror, "rev-parse", "HEAD").decode().strip()
    if not refs or actual_refs != refs or actual_head != head or origin != expected:
        raise ValueError("Source, HEAD or refs differ from the supplied inventory")
    if _git(mirror, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise ValueError("Shallow mirror cannot establish history coverage")
    tips = "".join(oid + "\n" for oid in sorted(set(refs.values()) | {head})).encode()
    reachable = _git(mirror, "rev-list", "--objects", "--no-object-names", "--stdin", data=tips)
    metadata = _git(mirror, "cat-file", "--batch-check", data=reachable)
    counts = Counter()
    inspect = []
    commits = []
    for row in metadata.splitlines():
        oid, kind, raw_size = row.split()
        size = int(raw_size)
        counts[kind.decode()] += 1
        if kind == b"tree" or (kind == b"blob" and size <= 1024):
            inspect.append((oid, kind, size))
        if kind == b"commit":
            commits.append((oid, kind, size))
    parents = defaultdict(list)
    links = []
    pointers = []
    for oid, kind, data in _batch(mirror, inspect):
        if kind == b"blob":
            pointer = _pointer(oid, data)
            if pointer:
                pointers.append(pointer)
            continue
        for mode, name, entry in _tree_entries(data, len(oid) // 2):
            if mode == b"40000":
                parents[entry].append((oid, name))
            elif mode == b"160000":
                links.append((oid, name, entry))
    root = Path(lfs_root) if lfs_root is not None else mirror / "lfs" / "objects"
    lfs = [_lfs_result(root, p) if "oid" in p else p for p in sorted(pointers, key=lambda p: p["pointer_blob"])]
    submodules = _pins(mirror, refs, commits, links, parents, modules or {})
    return {
        "source": origin,
        "head": head,
        "inventory_sha256": hashlib.sha256(inventory_bytes).hexdigest(),
        "ref_count": len(refs),
        "object_counts": dict(counts),
        "pointer_candidate_blobs": len(inspect) - counts["tree"],
        "gitlink_tree_entries": len(links),
        "lfs": lfs,
        "submodules": submodules,
        "complete": all(row["status"] == "verified" for row in lfs + submodules),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mirror", type=Path)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--lfs-root", type=Path, help="local LFS objects directory")
    parser.add_argument("--module", action="append", nargs=2, default=[], metavar=("GIT_PATH", "LOCAL_REPO"))
    args = parser.parse_args()
    bindings = {path: Path(repo) for path, repo in args.module}
    if len(bindings) != len(args.module):
        parser.error("each submodule path requires a unique local repository binding")
    report = audit_external_objects(args.mirror, args.inventory, lfs_root=args.lfs_root, modules=bindings)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["complete"] else 1)
