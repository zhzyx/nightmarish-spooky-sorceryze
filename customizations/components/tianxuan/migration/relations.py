"""Verify historical references against the inventory and the supplied Git object store."""

import json
import re
import subprocess
from pathlib import Path

GITHUB_ID = re.compile(r"github:([^/]+/[^/]+)/([^/]+)/(.+)", re.DOTALL)
OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")


def verify_relations(records_path, mirror_path):
    records = Path(records_path)
    known = set()
    scope = None
    with records.open("rb") as stream:
        for line in stream:
            source_id = json.loads(line)["source_id"]
            match = GITHUB_ID.fullmatch(source_id)
            if not match or source_id in known:
                raise ValueError("Invalid or duplicate source ID: " + source_id)
            if scope is None:
                scope = match[1].casefold()
            if match[1].casefold() != scope:
                raise ValueError("Mixed source repositories")
            known.add(source_id)

    unresolved = []
    external = []
    pending = []
    checked = 0
    with records.open("rb") as stream:
        for line in stream:
            row = json.loads(line)
            content = row["content"]
            origin = row["source_id"]
            repository = GITHUB_ID.fullmatch(origin)[1]
            targets = list(row["relations"])
            if row["kind"] == "requirement":
                targets.append(f"github:{repository}/blob/{content['blob']}")
            if row["kind"] == "commit":
                targets.append(origin)
            for target in targets:
                checked += 1
                edge = {"source_id": origin, "target": target}
                match = GITHUB_ID.fullmatch(target)
                if not match:
                    unresolved.append(dict(edge, reason="invalid_source_id"))
                    continue
                repo, kind, key = match.groups()
                if repo.casefold() != scope:
                    external.append(dict(edge, reason="external_repository"))
                    continue
                if kind in {"commit", "blob"}:
                    if not OID.fullmatch(key):
                        unresolved.append(dict(edge, reason="invalid_object_id"))
                        continue
                    if row["kind"] == "pull":
                        refs = []
                        for role in ("head", "base"):
                            ref = content.get(role) or {}
                            if ref.get("sha") == key:
                                remote = (ref.get("repo") or {}).get("full_name")
                                refs.append(
                                    dict(
                                        role=role,
                                        ref=ref.get("ref"),
                                        repository=remote,
                                        fork=(remote.casefold() != scope) if remote else None,
                                    )
                                )
                        if content.get("merge_commit_sha") == key:
                            refs.append({"role": "merge_commit_sha"})
                        edge["historical_refs"] = refs
                    pending.append((key, kind, edge))
                elif target not in known:
                    unresolved.append(dict(edge, reason="inventory_target_absent"))

    ids = sorted({key for key, _, _ in pending})
    found = subprocess.run(
        [
            "git",
            "--no-replace-objects",
            "-C",
            str(mirror_path),
            "cat-file",
            "--batch-check=%(objectname) %(objecttype)",
        ],
        input="".join(key + "\n" for key in ids),
        text=True,
        capture_output=True,
        check=True,
    ).stdout.splitlines()
    types = {}
    for key, answer in zip(ids, found, strict=True):
        returned, kind = answer.split()
        if key != returned:
            raise RuntimeError("Git returned a different object identity")
        types[key] = kind
    for key, expected, edge in pending:
        if types[key] != expected:
            unresolved.append(
                dict(edge, reason="git_object_absent_or_wrong_type", observed=types[key], expected=expected)
            )
    return dict(
        complete=not unresolved,
        checked=checked,
        resolved=checked - len(unresolved) - len(external),
        unresolved=unresolved,
        external=external,
    )
