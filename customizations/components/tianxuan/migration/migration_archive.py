"""Archive a captured inventory, Git bundle and attachments into a selected native DB."""

import argparse
import hashlib
import json
from pathlib import Path

from git_archive import git, verify_bundle_relations
from importer import import_inventory


def verify_captured_refs(mirror, bundle, history):
    refs = dict(
        line.split(" ", 1) for line in git(mirror, "for-each-ref", "--format=%(refname) %(objectname)").splitlines()
    )
    archived_refs = dict(
        line.split(" ", 1)[::-1] for line in git(mirror, "bundle", "list-heads", str(bundle)).splitlines()
    )
    archived_head = archived_refs.pop("HEAD", None)
    mirror_head = git(mirror, "rev-parse", "--revs-only", "HEAD") or None
    if refs != archived_refs or refs != history["refs"] or not (archived_head == mirror_head == history["head"]):
        expected = history["refs"]
        names = sorted(set(refs) | set(archived_refs) | set(expected))
        differences = {
            name: {"report": expected.get(name), "mirror": refs.get(name), "bundle": archived_refs.get(name)}
            for name in names
            if not (refs.get(name) == archived_refs.get(name) == expected.get(name))
        }
        if not (archived_head == mirror_head == history["head"]):
            differences["HEAD"] = {"report": history["head"], "mirror": mirror_head, "bundle": archived_head}
        raise ValueError("Git mirror, report and bundle differ: " + json.dumps(differences, sort_keys=True))

    # --quiet suppresses healthy objects but preserves the ?OID records for missing ones.
    missing = git(mirror, "--no-replace-objects", "rev-list", "--objects", "--all", "--quiet", "--missing=print")
    if missing:
        raise ValueError("Missing reachable Git objects in mirror: " + ", ".join(sorted(missing.splitlines())))


def archive(inventory, git_dir, attachment_dir, database, tenant, actor):
    manifest = json.loads(inventory.read_bytes())
    mirror = git_dir / "archive.git"
    history = json.loads((git_dir / "git-report.json").read_bytes())
    source = manifest["source"]
    if (
        history["source"] != f"https://github.com/{source}.git"
        or git(mirror, "remote", "get-url", "origin") != history["source"]
    ):
        raise ValueError("Inventory and Git mirror have different sources")
    bundle = (git_dir / "history.bundle").resolve()
    git(mirror, "bundle", "verify", str(bundle))
    verify_captured_refs(mirror, bundle, history)
    revision = manifest["revision"]
    if git(mirror, "rev-parse", "--verify", revision + "^{commit}") != revision:
        raise ValueError("Inventory revision missing from mirror")
    # Only reachable commits survive an export of all refs.
    if not git(mirror, "for-each-ref", "--count=1", "--contains", revision):
        raise ValueError("Inventory revision is unreachable from archive refs")
    verify_bundle_relations(bundle, inventory.with_name("records.jsonl"))
    attachments = (
        json.loads((attachment_dir / "attachments.json").read_bytes())
        if attachment_dir is not None
        else {"records": {}, "failures": []}
    )
    with inventory.with_name("records.jsonl").open("rb") as rows:
        ids = {row["source_id"] for raw in rows if (row := json.loads(raw))["kind"] == "attachment"}
    if attachments["failures"] or set(attachments["records"]) != ids:
        raise ValueError("Attachment coverage is incomplete")
    artifacts = {f"github:{source}/history.bundle": (git_dir / "history.bundle", history["bundle_sha256"])}
    git_report = git_dir / "git-report.json"
    artifacts[f"github:{source}/git-report.json"] = (git_report, hashlib.sha256(git_report.read_bytes()).hexdigest())
    for oid in history["lfs_objects"]:
        if len(oid) != 64 or any(c not in "0123456789abcdef" for c in oid):
            raise ValueError("invalid LFS digest")
        artifacts[f"github:{source}/lfs/{oid}"] = (mirror / "lfs" / "objects" / oid[:2] / oid[2:4] / oid, oid)
    for key, entry in attachments["records"].items():
        sha = entry["sha256"]
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError("Invalid attachment digest")
        artifacts[key] = (attachment_dir / sha, sha)
    return import_inventory(inventory, Path(database).resolve(), tenant, actor, artifacts=artifacts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inventory", "git_dir", "attachment_dir", "database"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--publish-project", help="Explicit visibility binding for this tenant and project")
    args = vars(parser.parse_args())
    project = args.pop("publish_project")
    receipt = args.pop("receipt")
    result = archive(**args)
    if project is not None:
        from migration_status import publish_import

        result["publication"] = publish_import(
            args["database"].resolve(), args["tenant"], project, args["actor"], result["module"], result["revision"]
        )
    receipt.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
