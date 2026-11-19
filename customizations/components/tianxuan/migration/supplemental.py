"""Preserve exact historical GitHub commits discovered in PR and review records."""
import argparse
import json
from pathlib import Path
import re
import subprocess


def git(repo, *args, **kwargs):
    return subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True,
                          **kwargs)


def supplement(records, repo, origin):
    if git(repo, "remote", "get-url", "origin", check=True).stdout.strip() != origin:
        raise ValueError("Unexpected mirror origin")
    ids = set()
    with records.open("rb") as source:
        for line in source:
            if not line.endswith(b"\n") and records.suffix == ".partial":
                break
            row = json.loads(line)
            content = row["content"]
            if row["kind"] == "pull":
                ids.update([content.get("merge_commit_sha"), (content.get("head") or {}).get("sha"),
                            (content.get("base") or {}).get("sha")])
            for ref in row["relations"]:
                if "/commit/" in ref:
                    ids.add(ref.rsplit("/commit/", 1)[-1])
    ids.discard(None)
    if any(not re.fullmatch("[0-9a-f]{40}|[0-9a-f]{64}", oid) for oid in ids):
        raise ValueError("Invalid historical commit identifier")

    def missing():
        ordered = sorted(ids)
        result = git(repo, "cat-file", "--batch-check=%(objectname) %(objecttype)",
                     input="".join(oid + "\n" for oid in ordered), check=True)
        return [oid for oid, line in zip(ordered, result.stdout.splitlines(), strict=True)
                if line != oid + " commit"]

    pending = missing()
    errors = {}
    def fetch(batch):
        refs = [oid + ":refs/migration/historical/" + oid for oid in batch]
        result = git(repo, "fetch", "--no-tags", "--no-write-fetch-head", "origin", *refs)
        if result.returncode:
            if len(batch) == 1:
                errors[batch[0]] = result.stderr.strip()
            else:
                middle = len(batch) // 2
                fetch(batch[:middle])
                fetch(batch[middle:])
    for start in range(0, len(pending), 32):
        fetch(pending[start:start+32])
    absent = set(missing())
    reachable = set(git(repo, "rev-list", "--all", check=True).stdout.splitlines())
    unpinned = sorted(ids - absent - reachable)
    if unpinned:
        updates = "".join(f"create refs/migration/historical/{oid} {oid}\n" for oid in unpinned)
        git(repo, "update-ref", "--stdin", input=updates, check=True)
    return {"checked": len(ids), "pinned_existing": len(unpinned),
            "initially_missing": len(pending), "still_missing": sorted(absent),
            "fetch_errors": errors}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=Path)
    parser.add_argument("mirror", type=Path)
    parser.add_argument("origin")
    args = parser.parse_args()
    report = supplement(args.records, args.mirror, args.origin)
    print(json.dumps(report))
    raise SystemExit(bool(report["still_missing"] or report["fetch_errors"]))
