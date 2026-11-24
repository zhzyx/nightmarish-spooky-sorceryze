"""Import every reachable commit of a captured Git snapshot and publish its native catalog."""

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path

from git_archive import git
from inventory import canonical, record_line
from migration_archive import archive, verify_captured_refs
from migration_status import publish_import, read_import_status


def import_git_history(git_dir, database, tenant, actor, project):
    """Import a completed git_archive.capture directory into the designated project."""
    git_dir = Path(git_dir).resolve()
    database = Path(database).resolve()
    mirror = git_dir / "archive.git"
    history = json.loads((git_dir / "git-report.json").read_bytes())
    match = re.fullmatch(r"https://github\.com/([\w.-]+/[\w.-]+)\.git", history["source"])
    if not match:
        raise ValueError("Expected a captured GitHub source")
    source = match[1]
    if git(mirror, "rev-parse", "--is-shallow-repository") != "false":
        raise ValueError("Full history requires a non-shallow mirror")
    if git(mirror, "rev-parse", "--revs-only", "HEAD") != history["head"]:
        verify_captured_refs(mirror, git_dir / "history.bundle", history)
        raise ValueError("Captured HEAD differs from mirror")
    graph = git(mirror, "--no-replace-objects", "rev-list", "--parents", "--all").splitlines()
    if not graph or len(graph) != history["commit_count"]:
        verify_captured_refs(mirror, git_dir / "history.bundle", history)
        raise ValueError("Reachable commit count differs from capture")
    prefix = f"github:{source}/commit/"
    with tempfile.TemporaryDirectory() as tmp:
        manifest = Path(tmp) / "report.json"
        checksum = hashlib.sha256()
        with manifest.with_name("records.jsonl").open("wb") as stream:
            for row in sorted(graph):
                oid, *parents = row.split()
                line = record_line(
                    prefix + oid, "commit", {"oid": oid, "parents": parents}, (prefix + p for p in parents)
                )
                stream.write(line)
                checksum.update(line)
        manifest.write_bytes(
            canonical(
                dict(
                    source=source,
                    revision=history["head"],
                    historical_policy="record_only",
                    coverage="commits reachable from the captured Git refs",
                    counts={"commit": len(graph)},
                    records_sha256=checksum.hexdigest(),
                )
            )
        )
        receipt = archive(manifest, git_dir, None, database, tenant, actor)
    publication = publish_import(database, tenant, project, actor, receipt["module"], receipt["revision"])
    if read_import_status(database, tenant, project) != publication:
        raise ValueError("A different catalog is current for this project")
    return dict(receipt, publication=publication)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("git_dir", type=Path, help="completed git_archive.capture snapshot directory")
    parser.add_argument("database", type=Path, help="destination native SQLite database")
    for name in ("tenant", "actor", "project"):
        parser.add_argument("--" + name, required=True)
    print(json.dumps(import_git_history(**vars(parser.parse_args()))))
