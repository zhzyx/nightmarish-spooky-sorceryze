"""Read-only, commit-bound integration inventory. Does not authorize publication."""

import argparse
import json
import subprocess
from bisect import bisect_left
from collections import Counter
from pathlib import Path


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def commit(repo, ref):
    return git(repo, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").decode().strip()


def inventory(repo, revision):
    """Inventory every tracked object at one immutable revision, without checkout."""
    revision = commit(repo, revision)
    entries = []
    for entry in git(repo, "ls-tree", "-rlz", revision).split(b"\0"):
        if not entry:
            continue
        meta, name = entry.split(b"\t", 1)
        mode, kind, oid, size = meta.split()
        path = name.decode("utf-8", "surrogateescape")
        entries.append({
            "path": path,
            "mode": mode.decode(),
            "kind": kind.decode(),
            "oid": oid.decode(),
            "bytes": None if size == b"-" else int(size),
        })
    return {
        "revision": revision,
        "files": len(entries),
        "bytes": sum(e["bytes"] or 0 for e in entries),
        "roots": dict(sorted(Counter(e["path"].split("/")[0] for e in entries).items())),
        "extensions": dict(sorted(Counter(Path(e["path"]).suffix for e in entries).items())),
        "entries": entries,
    }


def changed(repo, base, tip):
    # No rename heuristics: both source deletion and destination addition must
    # participate in conflict detection. NUL handles spaces, tabs and newlines.
    return {
        p.decode("utf-8", "surrogateescape")
        for p in git(repo, "diff", "--name-only", "--no-renames", "-z", base, tip, "--").split(b"\0")
        if p
    }


def overlap(left, right):
    # Include file/directory transitions (a versus a/b) as structural overlap.
    right = sorted(set(right))
    members = set(right)
    matches = set()
    for name in left:
        parts = name.split("/")
        if any("/".join(parts[:end]) in members for end in range(1, len(parts) + 1)):
            matches.add(name)
            continue
        position = bisect_left(right, name + "/")
        if position < len(right) and right[position].startswith(name + "/"):
            matches.add(name)
    return sorted(matches)


def plan(repo, target, contributions):
    target = commit(repo, target)
    snapshots = []
    ids = set()
    for item in contributions:
        identity = item["id"]
        if not isinstance(identity, str) or not identity or identity in ids:
            raise ValueError("Contribution IDs must be unique nonempty strings")
        ids.add(identity)
        tip = commit(repo, item["tip"])
        bases = git(repo, "merge-base", "--all", target, tip).decode().splitlines()
        if len(bases) != 1:
            raise ValueError("A unique merge base is required: " + identity)
        base = bases[0]
        writes = changed(repo, base, tip)
        # A missing read set means unknown dependencies, never independence.
        reads = item.get("reads")
        if reads is not None and (
            not isinstance(reads, list)
            or any(
                not isinstance(p, str)
                or not p
                or p.startswith("/")
                or "\\" in p
                or any(part in {"", ".", ".."} for part in p.split("/"))
                for p in reads
            )
        ):
            raise ValueError("Read paths must be repository-relative POSIX paths")
        dependencies = item.get("depends_on", [])
        if not isinstance(dependencies, list) or any(not isinstance(d, str) for d in dependencies):
            raise ValueError("depends_on must be an array of IDs")
        snapshots.append({
            "id": identity,
            "tip": tip,
            "base": base,
            "already_included": base == tip,
            "writes": sorted(writes),
            "reads": reads,
            "depends_on": dependencies,
            "target_overlap": overlap(writes | set(reads or []), changed(repo, base, target)),
            "target_dependencies_unknown": reads is None and target != base,
        })
    for item in snapshots:
        if set(item["depends_on"]) - ids or item["id"] in item["depends_on"]:
            raise ValueError("Unknown or self dependency: " + item["id"])
    edges = []
    for index, left in enumerate(snapshots):
        for right in snapshots[index + 1 :]:
            if left["already_included"] or right["already_included"]:
                continue
            paths = sorted(
                set(
                    overlap(left["writes"], right["writes"])
                    + overlap(left["writes"], right["reads"] or [])
                    + overlap(right["writes"], left["reads"] or [])
                )
            )
            unknown = left["reads"] is None or right["reads"] is None
            if paths or unknown:
                edges.append({
                    "left": left["id"],
                    "right": right["id"],
                    "paths": paths,
                    "unknown_dependencies": unknown,
                })
    conflicts = {frozenset((e["left"], e["right"])) for e in edges}
    done = {s["id"] for s in snapshots if s["already_included"]}
    remaining = [s for s in snapshots if s["id"] not in done]
    waves = []
    while remaining:
        wave = []
        for item in remaining:
            if set(item["depends_on"]) <= done and all(
                frozenset((item["id"], other)) not in conflicts for other in wave
            ):
                wave.append(item["id"])
        if not wave:
            raise ValueError("Dependency cycle")
        waves.append(wave)
        done.update(wave)
        remaining = [s for s in remaining if s["id"] not in done]
    return {
        "schema_version": 1,
        "target": target,
        "contributions": snapshots,
        "conflicts": edges,
        "preparation_waves": waves,
        "authority": "advisory_only",
        "semantic_compatibility": "unverified",
        "publication": "requires_integrated_candidate_validation_and_target_readback",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--target", default="HEAD")
    parser.add_argument("--contributions", type=Path, help="JSON array; paths relative to invocation cwd")
    args = parser.parse_args()
    result = (
        plan(args.repo, args.target, json.loads(args.contributions.read_text(encoding="utf-8")))
        if args.contributions
        else inventory(args.repo, args.target)
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
