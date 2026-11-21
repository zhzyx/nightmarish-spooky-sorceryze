"""Synchronize one merged GitHub pull and its original review into an existing Duobao project."""

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from git_archive import capture, git
from history_records import record_detail
from importer import digest, import_inventory, restore_inventory
from inventory import canonical, command, record_line
from migration_status import publish_import, read_import_status
from relations import OID, verify_relations


def github_pull(source, number):
    def api(path):
        return json.loads(command("gh", "api", f"repos/{source}/{path}"))

    def pages(path):
        for page in json.loads(command("gh", "api", "--paginate", "--slurp", f"repos/{source}/{path}?per_page=100")):
            yield from page

    pr = api(f"pulls/{number}")
    if not pr["merged"] or not pr["merged_at"] or pr["html_url"] != f"https://github.com/{source}/pull/{number}":
        raise ValueError("Expected a merged pull from the published source")
    comments = {}
    for kind, route in (
        ("issue_comment", f"issues/{number}/comments"),
        ("review", f"pulls/{number}/reviews"),
        ("review_comment", f"pulls/{number}/comments"),
    ):
        comments[kind] = list(pages(route))
    return pr, comments, api(f"issues/{number}")


def ancestor(repo, earlier, later):
    status = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", earlier, later]).returncode
    if status not in (0, 1):
        raise ValueError("Cannot compare Git history")
    return status == 0


def add_merge(snapshot, artifacts, source, mirror, branch, oid):
    """Fetch only the selected merge into a private copy of the published history."""
    prefix = f"github:{source}/"
    dest = snapshot / "archive.git"
    bundle = artifacts.pop(prefix + "history.bundle")[0]
    git(snapshot, "clone", "--quiet", "--mirror", "--", str(bundle), str(dest))
    git(dest, "remote", "set-url", "origin", f"https://github.com/{source}.git")
    ref = "refs/heads/" + branch
    git(mirror, "check-ref-format", ref)
    source_tip = git(mirror, "show-ref", "--verify", "--hash", ref)
    if not ancestor(mirror, oid, source_tip):
        raise ValueError("Merged commit is outside its original target branch")
    old = git(dest, "show-ref", "--verify", "--hash", ref)
    git(dest, "fetch", "--no-tags", "--", str(mirror), oid)
    if ancestor(dest, oid, old):
        return dest, old, old, []
    if not ancestor(dest, old, oid):
        raise ValueError("Target branch diverged from the published history")
    graph = git(dest, "--no-replace-objects", "rev-list", "--parents", oid, "--not", "--all").splitlines()
    git(dest, "update-ref", ref, oid, old)
    capture(source, snapshot)
    report = snapshot / "git-report.json"
    metadata = json.loads(report.read_bytes())
    artifacts[prefix + "history.bundle"] = snapshot / "history.bundle", metadata["bundle_sha256"]
    artifacts[prefix + "git-report.json"] = report, digest(report.read_bytes())
    for value in metadata["lfs_objects"]:
        artifacts[prefix + "lfs/" + value] = dest / "lfs" / "objects" / value[:2] / value[2:4] / value, value
    return dest, old, oid, graph


def update_inventory(staged, source, pr, comments, issue, old_tip, new_tip, graph):
    prefix = f"github:{source}/"
    pull_id = prefix + "pull/" + str(pr["number"])
    merge = pr["merge_commit_sha"]
    changes = {}

    def add(kind, key, content, links=()):
        sid = prefix + kind + "/" + str(key)
        changes[sid] = (kind, content, set(links))

    add("pull", pr["number"], dict(pr, migration_synced_merge=merge), [prefix + "commit/" + merge])
    projection_id = prefix + "pull_issue_projection/" + str(pr["number"])
    for kind, group in comments.items():
        for item in group:
            links = [pull_id]
            if item.get("pull_request_review_id"):
                links.append(prefix + "review/" + str(item["pull_request_review_id"]))
            if item.get("in_reply_to_id"):
                links.append(prefix + "review_comment/" + str(item["in_reply_to_id"]))
            add(kind, item["id"], item, links)
    for entry in graph:
        oid, *parents = entry.split()
        add("commit", oid, {"oid": oid, "parents": parents}, [prefix + "commit/" + p for p in parents])

    report_path = staged / "report.json"
    report = json.loads(report_path.read_bytes())
    records = staged / "records.jsonl"
    replacement = staged / "updated.jsonl"
    checksum = hashlib.sha256()
    counts = Counter()
    with records.open("rb") as previous, replacement.open("wb") as stream:

        def write(line, kind):
            stream.write(line)
            checksum.update(line)
            counts[kind] += 1

        for line in previous:
            row = json.loads(line)
            sid = row["source_id"]
            if sid == projection_id:
                # A full legacy inventory also has GitHub's issue projection of this PR.
                add("pull_issue_projection", pr["number"], issue, [pull_id])
            if sid in changes:
                kind, content, links = changes.pop(sid)
                # Preserve inventory enrichment, including previously archived commit membership.
                line = record_line(sid, kind, row["content"] | content, links.union(row["relations"]))
            write(line, row["kind"])
        for sid, (kind, content, links) in sorted(changes.items()):
            write(record_line(sid, kind, content, links), kind)
    replacement.replace(records)
    if report["revision"] == old_tip:
        report["revision"] = new_tip
    report.update(counts=dict(counts), records_sha256=checksum.hexdigest())
    report_path.write_bytes(canonical(report) + b"\n")
    return report_path


def sync(database, tenant, actor, project, mirror, number, expected_merge):
    if number < 1 or not OID.fullmatch(expected_merge):
        raise ValueError("Expected a pull number and full immutable merge OID")
    current = read_import_status(database, tenant, project)
    if not current:
        raise ValueError("Publish the target project baseline before synchronization")
    source = current["source"]
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", source):
        raise ValueError("Invalid published GitHub source")
    mirror = Path(mirror).resolve()
    if git(mirror, "remote", "get-url", "origin") != f"https://github.com/{source}.git":
        raise ValueError("Source mirror belongs to another repository")
    pull_id = f"github:{source}/pull/{number}"
    try:
        prior = record_detail(database, tenant, project, current["revision"], pull_id)["record"]
    except LookupError:
        prior = None
    receipt = {
        "source_id": pull_id,
        "pull_url": f"https://github.com/{source}/pull/{number}",
        "merge_oid": expected_merge,
    }
    if prior and prior["content"].get("migration_synced_merge") == expected_merge:
        return dict(receipt, state="already_synced", publication=current)
    pr, comments, issue = github_pull(source, number)
    if pr["merge_commit_sha"] != expected_merge:
        raise ValueError("Original PR merge OID differs from the expected merge")
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        staged = root / "inventory"
        binary_base = current["module"], current["revision"]
        restored = restore_inventory(
            database, tenant, *binary_base, staged, binary_ids={f"github:{source}/history.bundle"}
        )
        artifacts = {k: (staged / v["file"], v["sha256"]) for k, v in restored["binaries"].items()}
        mirror_copy, old, new, graph = add_merge(root, artifacts, source, mirror, pr["base"]["ref"], expected_merge)
        manifest = update_inventory(staged, source, pr, comments, issue, old, new, graph)
        verified = verify_relations(staged / "records.jsonl", mirror_copy)
        if not verified["complete"]:
            raise ValueError(f"Unresolved archive relations: {verified['unresolved'][:5]}")
        candidate = import_inventory(manifest, database, tenant, actor, artifacts=artifacts, binary_base=binary_base)
    result = publish_import(
        database,
        tenant,
        project,
        actor,
        candidate["module"],
        candidate["revision"],
        expected_current=current["revision"],
    )
    return dict(
        receipt,
        state="synced",
        publication=result,
        previous_revision=current["revision"],
        branch_before=old,
        branch_after=new,
        new_commits=len(graph),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("mirror", type=Path)
    parser.add_argument("number", type=int)
    parser.add_argument("expected_merge")
    for field in ("tenant", "actor", "project"):
        parser.add_argument("--" + field, required=True)
    print(json.dumps(sync(**vars(parser.parse_args())), ensure_ascii=False))
