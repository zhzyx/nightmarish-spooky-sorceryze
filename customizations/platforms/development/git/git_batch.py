"""Bounded-process, raw-byte Git evidence reads. No filters or persistent cache."""

import os
import subprocess


def run(root, *args, input=None, allowed=(0,)):
    result = subprocess.run(["git", "-C", str(root), *args], input=input, capture_output=True, timeout=120)
    if result.returncode not in allowed:
        raise ValueError("Git evidence query failed: " + args[0])
    return result.stdout


def tracked(root):
    return set(run(root, "ls-files", "-z").split(b"\0")) - {b""}


def ignored(root, names):
    if not names:
        return set()
    data = b"\0".join(names) + b"\0"
    return set(run(root, "check-ignore", "--no-index", "-z", "--stdin", input=data, allowed=(0, 1)).split(b"\0")) - {
        b""
    }


def objects(root, revision, prefixes):
    """Return raw blob bytes keyed by repository-relative byte paths."""
    if revision == ":":
        output = run(root, "ls-files", "--stage", "-z", "--", *prefixes)
    elif revision == "HEAD":
        output = run(root, "ls-tree", "-r", "-z", "HEAD", "--", *prefixes)
    else:
        raise ValueError("Expected index or HEAD")
    entries = {}
    for record in output.split(b"\0"):
        if not record:
            continue
        header, name = record.split(b"\t", 1)
        parts = header.split()
        mode = parts[0]
        if revision == ":":
            oid, stage = parts[1:]
            if stage != b"0":
                raise ValueError("Unmerged evidence in index")
        else:
            kind, oid = parts[1:]
            if kind != b"blob":
                raise ValueError("Non-blob evidence")
        if mode not in (b"100644", b"100755"):
            raise ValueError("Linked or non-file Git evidence")
        entries[name] = oid
    ids = sorted(set(entries.values()))
    if not ids:
        return {}
    output = run(root, "cat-file", "--batch", input=b"\n".join(ids) + b"\n")
    blobs, offset = {}, 0
    for oid in ids:
        end = output.index(b"\n", offset)
        header = output[offset:end].split()
        if len(header) != 3 or header[:2] != [oid, b"blob"]:
            raise ValueError("Missing or invalid Git object")
        size = int(header[2])
        start = end + 1
        offset = start + size + 1
        if size < 0 or output[offset - 1 : offset] != b"\n":
            raise ValueError("Truncated Git object")
        blobs[oid] = output[start : start + size]
    if offset != len(output):
        raise ValueError("Unexpected Git object response")
    return {name: blobs[oid] for name, oid in entries.items()}


def encoded(path, root):
    return os.fsencode(path.relative_to(root).as_posix())
