"""Read-only, commit-bound integration inventory, wave planner, and tree composer.

Does not authorize publication or mutate refs, index, or working files.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from bisect import bisect_left
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

_ENGINE_ROOTS = frozenset({
    "core",
    "drivers",
    "editor",
    "engine_next",
    "main",
    "modules",
    "platform",
    "scene",
    "servers",
})
_ENGINE_ROOT_FILES = frozenset({
    "SConstruct",
    "cpp.hint",
    "custom.py",
    "gles3_builders.py",
    "glsl_builders.py",
    "methods.py",
    "platform_methods.py",
    "scu_builders.py",
    "version.py",
})
_TELEMETRY_ROOTS = frozenset({
    "archive",
    "data-collection",
    "distribution",
    "gonggong-diting-data",
    "olympus-hermes-data",
    "releases",
})
_DOC_ROOTS = frozenset({"Markdown", "design-docs", "doc"})
_HOST_ROOTS = frozenset({"apps", "customizations", "deploy", "integrations", "tools"})
_TEST_ROOTS = frozenset({"project", "samples", "tests"})


def git(repo: Path, *args: str, env: Mapping[str, str] | None = None) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), *args], env=env)


def commit(repo: Path, ref: str) -> str:
    return git(repo, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").decode().strip()


def classify_boundary(path: str) -> str:
    """Assign a tracked repository path to a deterministic architectural boundary."""
    parts = PurePosixPath(path).parts
    first = parts[0]
    if len(parts) == 1:
        if first in _ENGINE_ROOT_FILES:
            return "engine_native"
        if first == "CURRENT_FRAMEWORK.json":
            return "framework_governance"
        if first in {"gonggong-workspace.json", "work-items.json", ".gonggong-local.example.json"}:
            return "host_adapters_and_apps"
        if PurePosixPath(first).suffix in {".md", ".txt"}:
            return "documentation_and_specs"
        return "ci_and_repo_config"
    if first == "thirdparty":
        return "thirdparty"
    if first == "framework" or parts[:2] == ("integrations", "gonggong") or path == "customizations/host-agents.json":
        return "framework_governance"
    if first in _ENGINE_ROOTS:
        return "engine_native"
    if first in _TELEMETRY_ROOTS:
        return "telemetry_and_evidence"
    if first in _DOC_ROOTS:
        return "documentation_and_specs"
    if first in _HOST_ROOTS:
        return "host_adapters_and_apps"
    if first in _TEST_ROOTS:
        return "tests_and_samples"
    return "ci_and_repo_config"


def binary_paths(repo: Path, revision: str) -> set[str]:
    """Identify blobs Git classifies as binary at an immutable revision."""
    raw = git(repo, "diff", "--numstat", "--no-renames", "-z", EMPTY_TREE, revision, "--").split(b"\0")
    binaries: set[str] = set()
    for record in raw:
        if not record:
            continue
        parts = record.decode("utf-8", "surrogateescape").split("\t", 2)
        if len(parts) == 3 and parts[0] == "-" and parts[1] == "-":
            binaries.add(parts[2])
    return binaries


def inventory(repo: Path, revision: str) -> dict[str, Any]:
    """Inventory every tracked object at one immutable revision, without checkout."""
    revision = commit(repo, revision)
    binaries = binary_paths(repo, revision)
    entries: list[dict[str, Any]] = []
    boundary_files: Counter[str] = Counter()
    boundary_bytes: Counter[str] = Counter()
    binary_bytes = 0
    for entry in git(repo, "ls-tree", "-rlz", revision).split(b"\0"):
        if not entry:
            continue
        meta, name = entry.split(b"\t", 1)
        mode, kind, oid, size = meta.split()
        path = name.decode("utf-8", "surrogateescape")
        byte_count = None if size == b"-" else int(size)
        is_binary = path in binaries
        boundary = classify_boundary(path)
        boundary_files[boundary] += 1
        boundary_bytes[boundary] += byte_count or 0
        if is_binary:
            binary_bytes += byte_count or 0
        entries.append({
            "path": path,
            "mode": mode.decode(),
            "kind": kind.decode(),
            "oid": oid.decode(),
            "bytes": byte_count,
            "binary": is_binary,
            "boundary": boundary,
        })
    total_bytes = sum(e["bytes"] or 0 for e in entries)
    return {
        "revision": revision,
        "files": len(entries),
        "bytes": total_bytes,
        "text_files": len(entries) - len(binaries),
        "binary_files": len(binaries),
        "text_bytes": total_bytes - binary_bytes,
        "binary_bytes": binary_bytes,
        "boundaries": {
            key: {"files": boundary_files[key], "bytes": boundary_bytes[key]} for key in sorted(boundary_files)
        },
        "roots": dict(sorted(Counter(e["path"].split("/")[0] for e in entries).items())),
        "extensions": dict(sorted(Counter(Path(e["path"]).suffix for e in entries).items())),
        "entries": entries,
    }


def changed(repo: Path, base: str, tip: str, *, env: Mapping[str, str] | None = None) -> set[str]:
    # No rename heuristics: both source deletion and destination addition must
    # participate in conflict detection. NUL handles spaces, tabs and newlines.
    return {
        p.decode("utf-8", "surrogateescape")
        for p in git(repo, "diff", "--name-only", "--no-renames", "-z", base, tip, "--", env=env).split(b"\0")
        if p
    }


def overlap(left: Iterable[str], right: Iterable[str]) -> list[str]:
    # Include file/directory transitions (a versus a/b) as structural overlap.
    ordered_right = sorted(set(right))
    members = set(ordered_right)
    matches: set[str] = set()
    for name in left:
        parts = name.split("/")
        if any("/".join(parts[:end]) in members for end in range(1, len(parts) + 1)):
            matches.add(name)
            continue
        position = bisect_left(ordered_right, name + "/")
        if position < len(ordered_right) and ordered_right[position].startswith(name + "/"):
            matches.add(name)
    return sorted(matches)


def plan(repo: Path, target: str, contributions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    target = commit(repo, target)
    snapshots: list[dict[str, Any]] = []
    ids: set[str] = set()
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
    edges: list[dict[str, Any]] = []
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
    waves: list[list[str]] = []
    while remaining:
        wave: list[str] = []
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


def _tree_entries(
    repo: Path,
    tree_or_commit: str,
    paths: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, tuple[str, str]]:
    if not paths:
        return {}
    raw = git(repo, "ls-tree", "-rz", tree_or_commit, "--", *paths, env=env).split(b"\0")
    entries: dict[str, tuple[str, str]] = {}
    for record in raw:
        if not record:
            continue
        meta, name = record.split(b"\t", 1)
        mode, _, oid = meta.split()
        entries[name.decode("utf-8", "surrogateescape")] = (mode.decode(), oid.decode())
    return entries


def _quarantine_env(repo: Path, scratch: Path) -> dict[str, str]:
    objects_dir = Path(os.fsdecode(git(repo, "rev-parse", "--git-path", "objects")).strip())
    if not objects_dir.is_absolute():
        objects_dir = (repo / objects_dir).resolve()
    env = os.environ.copy()
    existing_alt = env.get("GIT_ALTERNATE_OBJECT_DIRECTORIES", "")
    alternates = [str(objects_dir)] + ([existing_alt] if existing_alt else [])
    env["GIT_OBJECT_DIRECTORY"] = str(scratch)
    env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = os.pathsep.join(alternates)
    env["GIT_AUTHOR_NAME"] = "Heqi Speculative Composer"
    env["GIT_AUTHOR_EMAIL"] = "heqi@example.invalid"
    env["GIT_COMMITTER_NAME"] = "Heqi Speculative Composer"
    env["GIT_COMMITTER_EMAIL"] = "heqi@example.invalid"
    return env


def compose(
    repo: Path,
    target: str,
    contributions: Sequence[Mapping[str, Any]],
    *,
    write_objects: bool = False,
) -> dict[str, Any]:
    """Speculatively compose non-conflicting wave contributions in memory.

    Uses Git's object-level ``merge-tree --write-tree`` inside an ephemeral
    quarantine object directory by default, leaving ``.git``, ``HEAD``, index,
    and working tree completely untouched. Conflicting or dependency-blocked
    contributions are isolated without aborting independent contributions.
    """
    planned = plan(repo, target, contributions)
    target_commit = planned["target"]
    target_tree = git(repo, "rev-parse", target_commit + "^{tree}").decode().strip()
    by_id = {item["id"]: item for item in planned["contributions"]}

    def _run_fold(env: Mapping[str, str] | None) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
        acc_commit = target_commit
        acc_tree = target_tree
        accumulated_writes: set[str] = set()
        accepted_ids = {item["id"] for item in planned["contributions"] if item["already_included"]}
        integrated: list[dict[str, Any]] = []
        isolated: list[dict[str, Any]] = []

        for wave_index, wave in enumerate(planned["preparation_waves"]):
            for cid in wave:
                item = by_id[cid]
                missing_deps = sorted(set(item["depends_on"]) - accepted_ids)
                if missing_deps:
                    isolated.append({
                        "id": cid,
                        "wave": wave_index,
                        "reason": "dependency_isolated",
                        "blocked_by": missing_deps,
                        "paths": [],
                    })
                    continue
                if item["target_dependencies_unknown"]:
                    isolated.append({
                        "id": cid,
                        "wave": wave_index,
                        "reason": "target_dependencies_unknown",
                        "blocked_by": [],
                        "paths": [],
                    })
                    continue
                if item["reads"] is None and accumulated_writes:
                    isolated.append({
                        "id": cid,
                        "wave": wave_index,
                        "reason": "unknown_read_dependencies",
                        "blocked_by": [],
                        "paths": [],
                    })
                    continue
                prior_overlap = sorted(
                    set(
                        item["target_overlap"]
                        + overlap(item["writes"], accumulated_writes)
                        + overlap(item["reads"] or [], accumulated_writes)
                    )
                )
                if prior_overlap:
                    isolated.append({
                        "id": cid,
                        "wave": wave_index,
                        "reason": "path_or_read_overlap",
                        "blocked_by": [],
                        "paths": prior_overlap,
                    })
                    continue

                proc = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(repo),
                        "merge-tree",
                        "--write-tree",
                        "-z",
                        f"--merge-base={item['base']}",
                        acc_commit,
                        item["tip"],
                    ],
                    capture_output=True,
                    env=env,
                )
                if proc.returncode != 0:
                    parts = [p.decode("utf-8", "surrogateescape") for p in proc.stdout.split(b"\0") if p]
                    isolated.append({
                        "id": cid,
                        "wave": wave_index,
                        "reason": "tree_merge_conflict",
                        "blocked_by": [],
                        "paths": parts[1:],
                    })
                    continue

                next_tree = proc.stdout.split(b"\0", 1)[0].decode().strip()
                step_changes = sorted(changed(repo, acc_tree, next_tree, env=env))
                expected_entries = _tree_entries(repo, item["tip"], item["writes"], env=env)
                actual_entries = _tree_entries(repo, next_tree, item["writes"], env=env)
                if step_changes != item["writes"] or actual_entries != expected_entries:
                    isolated.append({
                        "id": cid,
                        "wave": wave_index,
                        "reason": "non_commutative_tree_delta",
                        "blocked_by": [],
                        "paths": step_changes,
                    })
                    continue

                acc_commit = (
                    git(
                        repo,
                        "-c",
                        "commit.gpgsign=false",
                        "commit-tree",
                        next_tree,
                        "-p",
                        acc_commit,
                        "-p",
                        item["tip"],
                        "-m",
                        f"Speculative fold: {cid}",
                        env=env,
                    )
                    .decode()
                    .strip()
                )
                acc_tree = next_tree
                accumulated_writes.update(item["writes"])
                accepted_ids.add(cid)
                integrated.append({
                    "id": cid,
                    "tip": item["tip"],
                    "base": item["base"],
                    "wave": wave_index,
                    "writes": item["writes"],
                    "tree_after": acc_tree,
                })
        return acc_tree, integrated, isolated

    if write_objects:
        env = os.environ.copy()
        env["GIT_AUTHOR_NAME"] = "Heqi Speculative Composer"
        env["GIT_AUTHOR_EMAIL"] = "heqi@example.invalid"
        env["GIT_COMMITTER_NAME"] = "Heqi Speculative Composer"
        env["GIT_COMMITTER_EMAIL"] = "heqi@example.invalid"
        composed_tree, integrated, isolated = _run_fold(env)
    else:
        with tempfile.TemporaryDirectory(prefix="heqi-quarantine-") as scratch:
            composed_tree, integrated, isolated = _run_fold(_quarantine_env(repo, Path(scratch)))

    return {
        **planned,
        "target_tree": target_tree,
        "composed_tree": composed_tree if write_objects else None,
        "ephemeral_composed_tree": composed_tree,
        "objects_persisted": write_objects,
        "integrated": integrated,
        "isolated": isolated,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--target", default="HEAD")
    parser.add_argument("--contributions", type=Path, help="JSON array; paths relative to invocation cwd")
    parser.add_argument(
        "--compose",
        action="store_true",
        help="Speculatively compose non-conflicting contributions in memory via git merge-tree",
    )
    parser.add_argument(
        "--write-objects",
        action="store_true",
        help="Persist composed tree objects into the repository object store (requires --compose)",
    )
    args = parser.parse_args()
    if args.write_objects and not args.compose:
        parser.error("--write-objects requires --compose")
    if args.compose and not args.contributions:
        parser.error("--compose requires --contributions")
    if args.contributions:
        items = json.loads(args.contributions.read_text(encoding="utf-8"))
        result = (
            compose(args.repo, args.target, items, write_objects=args.write_objects)
            if args.compose
            else plan(args.repo, args.target, items)
        )
    else:
        result = inventory(args.repo, args.target)
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
