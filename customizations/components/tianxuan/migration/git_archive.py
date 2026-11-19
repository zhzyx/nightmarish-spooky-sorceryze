"""Capture and verify one Git mirror for the historical migration."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "duobao"))
from git_service import GitService


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], encoding="utf-8").strip()


def verify_bundle_relations(bundle, records):
    from relations import verify_relations

    with tempfile.TemporaryDirectory(dir=bundle.parent) as temp:
        restored = Path(temp) / "archive.git"
        subprocess.run(["git", "clone", "--quiet", "--mirror", "--", str(bundle.resolve()), str(restored)], check=True)
        result = verify_relations(records, restored)
        if not result["complete"]:
            raise ValueError(f"Unresolved bundled relations: {result['unresolved'][:5]}")
        return result


def capture(source, output, reference=None, records=None):
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", source):
        raise ValueError("expected GitHub OWNER/REPO")
    url = f"https://github.com/{source}.git"
    output.mkdir(parents=True, exist_ok=True)
    mirror = output / "archive.git"
    if not mirror.exists() and reference is not None:
        common = git(reference, "rev-parse", "--path-format=absolute", "--git-common-dir")
        import tempfile

        with tempfile.TemporaryDirectory(dir=output) as staging:
            staged = Path(staging) / "archive.git"
            subprocess.run(
                ["git", "clone", "--mirror", "--reference", common, "--dissociate", "--", url, str(staged)],
                check=True,
                timeout=3600,
            )
            staged.rename(mirror)
    if not mirror.exists():
        GitService().import_repo(output, mirror.name, url, allowed_hosts=["github.com"], timeout=3600)
    if git(mirror, "remote", "get-url", "origin") != url:
        raise ValueError("checkpoint source mismatch")
    if records is not None:
        from supplemental import supplement

        if (output / "history.bundle").exists():
            # Never change an already-published snapshot when new records arrive.
            from relations import verify_relations

            if not verify_relations(records, mirror)["complete"]:
                raise ValueError("New historical references require a new snapshot directory")
        else:
            result = supplement(records, mirror, url)
            if result["still_missing"]:
                raise ValueError(f"Unresolved historical commits: {result['still_missing']}")
    git(mirror, "fsck", "--full", "--no-dangling")
    refs = dict(
        line.split(" ", 1) for line in git(mirror, "for-each-ref", "--format=%(refname) %(objectname)").splitlines()
    )
    bundle = output / "history.bundle"
    if not bundle.exists():
        # A killed pack writer must never publish a partial bundle as a checkpoint.
        import tempfile

        with tempfile.TemporaryDirectory(dir=output) as temporary:
            staged = Path(temporary) / bundle.name
            git(mirror, "bundle", "create", str(staged.resolve()), "--all")
            git(mirror, "bundle", "verify", str(staged.resolve()))
            staged.replace(bundle)
    git(mirror, "bundle", "verify", str(bundle.resolve()))
    bundled = dict(
        line.split(" ", 1)[::-1] for line in git(mirror, "bundle", "list-heads", str(bundle.resolve())).splitlines()
    )
    if any(bundled.get(name) != oid for name, oid in refs.items()):
        raise ValueError("bundle refs differ from mirror")
    if records is not None:
        verify_bundle_relations(bundle, records)
    with bundle.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    lfs_ids = set()
    for line in git(mirror, "lfs", "ls-files", "--all", "--long").splitlines():
        oid = line.split(" ", 1)[0]
        if not re.fullmatch("[0-9a-f]{64}", oid):
            raise ValueError("unrecognized LFS object")
        lfs_ids.add(oid)
    if lfs_ids:
        git(mirror, "lfs", "fetch", "--all", "origin")
    for oid in lfs_ids:
        path = mirror / "lfs" / "objects" / oid[:2] / oid[2:4] / oid
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != oid:
                raise ValueError("LFS content mismatch")
    report = {
        "source": url,
        "head": git(mirror, "rev-parse", "HEAD"),
        "refs": refs,
        "commit_count": int(git(mirror, "rev-list", "--count", "--all")),
        "bundle": bundle.name,
        "bundle_sha256": digest,
        "bytes": bundle.stat().st_size,
        "lfs_objects": sorted(lfs_ids),
        "submodule_repositories": "not verified",
    }
    path = output / "git-report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--reference", type=Path, help="existing checkout to reuse for object transfer")
    parser.add_argument("--records", type=Path, help="include historical commits referenced by GitHub records")
    args = parser.parse_args()
    print(capture(args.source, args.output.resolve(), args.reference, args.records))
