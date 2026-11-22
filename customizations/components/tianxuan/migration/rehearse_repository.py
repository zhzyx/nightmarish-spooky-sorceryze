"""Import a complete captured Git repository into a fresh native DB and verify an independent restore."""

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic

from git_archive import git
from import_git_history import import_git_history
from importer import restore_inventory
from relations import verify_relations


def objects(repo, reachable):
    ids = sorted(reachable)
    result = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)"],
        input="\n".join(ids) + "\n",
        text=True,
        capture_output=True,
        check=True,
    )
    observed = {}
    for expected, line in zip(ids, result.stdout.splitlines(), strict=True):
        oid, kind, size = line.split()
        if oid != expected:
            raise ValueError(f"Unexpected Git object for {expected}")
        observed[oid] = (kind, int(size))
    return observed


def rehearse(capture, destination, tenant, actor, project):
    started = datetime.now(timezone.utc).isoformat()
    capture = capture.resolve(strict=True)
    destination.mkdir(parents=True, exist_ok=False)
    source = capture / "archive.git"
    history = json.loads((capture / "git-report.json").read_bytes())
    db = destination / "native.db"
    start = monotonic()
    receipt = import_git_history(capture, db, tenant, actor, project)
    imported = monotonic()
    restored = destination / "restored"
    result = restore_inventory(db, tenant, receipt["module"], receipt["revision"], restored)
    prefix = f"github:{receipt['publication']['source']}/"
    bundle = restored / result["binaries"][prefix + "history.bundle"]["file"]
    with bundle.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != history["bundle_sha256"]:
            raise ValueError("The restored bundle differs from the capture")
    target = destination / "recovered.git"
    subprocess.run(["git", "clone", "--quiet", "--mirror", str(bundle), str(target)], check=True)
    refs = dict(
        line.split(" ", 1) for line in git(target, "for-each-ref", "--format=%(refname) %(objectname)").splitlines()
    )
    comparison = {r: [history["refs"].get(r), refs.get(r)] for r in sorted(history["refs"].keys() | refs.keys())}
    if any(a != b for a, b in comparison.values()) or git(target, "rev-parse", "HEAD") != history["head"]:
        raise ValueError("Restored refs differ from the capture")
    git(target, "fsck", "--full", "--no-dangling")
    before = {v.split(" ", 1)[0] for v in git(source, "rev-list", "--objects", "--all").splitlines()}
    after = {v.split(" ", 1)[0] for v in git(target, "rev-list", "--objects", "--all").splitlines()}
    checked = objects(target, after)
    if before != after or checked != objects(source, before):
        raise ValueError("Restored reachability or Git object contents differ from source")
    relations = verify_relations(restored / "records.jsonl", target)
    if not relations["complete"]:
        raise ValueError("Historical record links did not resolve")
    return dict(
        scope="All advertised Git refs and all reachable Git objects of the captured repository",
        started_at=started,
        git=git(target, "--version"),
        source_head=history["head"],
        snapshot_source=history["source"],
        import_and_publish_seconds=round(imported - start, 3),
        restore_and_verification_seconds=round(monotonic() - imported, 3),
        source_object_count=len(before),
        restored_object_count=len(after),
        objects_by_kind=dict(Counter(kind for kind, size in checked.values())),
        uncompressed_object_bytes=sum(size for kind, size in checked.values()),
        bundle_bytes=bundle.stat().st_size,
        bundle_sha256=history["bundle_sha256"],
        lfs_objects=history["lfs_objects"],
        submodules=[
            line for line in git(source, "ls-tree", "-r", history["head"]).splitlines() if line.startswith("160000 ")
        ],
        refs_count=len(refs),
        ref_mismatches=0,
        refs=comparison,
        git_fsck="passed",
        record_links=relations,
        archive_receipt=receipt,
        restored=result,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("destination", type=Path, help="new directory on the rehearsal host")
    for field in ("tenant", "actor", "project"):
        parser.add_argument("--" + field, required=True)
    print(json.dumps(rehearse(**vars(parser.parse_args())), ensure_ascii=False, indent=2))
