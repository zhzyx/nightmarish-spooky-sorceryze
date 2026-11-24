import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from audit_external_objects import audit_external_objects
from history_records import export_binary
from import_git_history import import_git_history
from migration_status import read_import_status


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args]).decode("utf-8").strip()


def make_snapshot(root):
    """Two commits: the reachable parent alone contains a pointer and a nested gitlink."""
    repo = root / "repo"
    child = root / "module"
    for directory in (repo, child):
        directory.mkdir()
        git(directory, "init", "-q", "-b", "main", "--object-format=sha1")
        git(directory, "config", "core.autocrlf", "false")
    git(child, "commit", "--allow-empty", "-qm", "pinned revision")
    pin = git(child, "rev-parse", "HEAD")
    git(child, "commit", "--allow-empty", "-qm", "later revision")
    module_path = "vendor/" + chr(0x6A21) + chr(0x5757)
    (repo / ".gitmodules").write_bytes(
        f'[submodule "sample"]\n\tpath = {module_path}\n\turl = ../module.git\n'.encode()
    )
    payload = b"historical LFS object\x00\xff\n"
    oid = hashlib.sha256(payload).hexdigest()
    (repo / "asset.bin").write_bytes(
        f"version https://git-lfs.github.com/spec/v1\noid sha256:{oid}\nsize {len(payload)}\n".encode()
    )
    git(repo, "add", ".gitmodules", "asset.bin")
    git(repo, "update-index", "--add", "--cacheinfo", f"160000,{pin},{module_path}")
    git(repo, "commit", "-qm", "external objects")
    commit = git(repo, "rev-parse", "HEAD")
    pointer = git(repo, "rev-parse", "HEAD:asset.bin")
    git(repo, "rm", "--cached", module_path, ".gitmodules", "asset.bin")
    git(repo, "commit", "-qm", "remove external references")
    folder = root / "capture"
    folder.mkdir()
    mirror = folder / "archive.git"
    git(repo, "clone", "-q", "--mirror", "--", str(repo), str(mirror))
    origin = "https://github.com/sample/repo.git"
    git(mirror, "remote", "set-url", "origin", origin)
    bundle = folder / "history.bundle"
    git(mirror, "bundle", "create", str(bundle), "--all")
    head = git(mirror, "rev-parse", "HEAD")
    inventory = folder / "git-report.json"
    inventory.write_text(
        json.dumps({
            "source": origin,
            "head": head,
            "refs": {"refs/heads/main": head},
            "commit_count": 2,
            "bundle": bundle.name,
            "bundle_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
            "bytes": bundle.stat().st_size,
            "lfs_objects": [oid],
            "submodule_repositories": "not verified",
        }),
        encoding="utf-8",
    )
    storage_key = Path(oid[:2], oid[2:4], oid)
    stored = mirror / "lfs" / "objects" / storage_key
    stored.parent.mkdir(parents=True)
    stored.write_bytes(payload)
    return folder, child, module_path, pin, commit, pointer, storage_key, payload


@pytest.fixture
def snapshot(tmp_path, monkeypatch):
    for key in list(os.environ):
        if key.upper().startswith("GIT_"):
            monkeypatch.delenv(key)
    for key, value in {
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Author",
        "GIT_COMMITTER_NAME": "Committer",
        "GIT_AUTHOR_EMAIL": "author@example.invalid",
        "GIT_COMMITTER_EMAIL": "committer@example.invalid",
        "GIT_AUTHOR_DATE": "2026-11-20T08:00:00+08:00",
        "GIT_COMMITTER_DATE": "2026-11-20T08:01:00+08:00",
    }.items():
        monkeypatch.setenv(key, value)
    return make_snapshot(tmp_path)


def exercise_target(snapshot, root):
    folder, child, module_path, pin, commit, pointer, key, payload = snapshot
    database = root / "native.sqlite"
    receipt = import_git_history(folder, database, "owners", "operator", "g06")
    publication = read_import_status(database, "owners", "g06")
    assert receipt["publication"] == publication
    target = database, "owners", "g06", receipt["revision"]
    restored = root / "restored"
    restored.mkdir()
    binary_prefix = "github:sample/repo/"
    for name in ("history.bundle", "git-report.json"):
        export_binary(*target, binary_prefix + name, restored / name)
    mirror = restored / "mirror.git"
    git(restored, "clone", "--quiet", "--mirror", "--", str(restored / "history.bundle"), str(mirror))
    git(mirror, "remote", "set-url", "origin", "https://github.com/sample/repo.git")
    destination = restored / "objects" / key
    destination.parent.mkdir(parents=True)
    binary = export_binary(*target, binary_prefix + "lfs/" + key.name, destination)
    assert destination.read_bytes() == payload
    # Target verifier only sees the exported payload and the supplied submodule repository.
    command = [
        sys.executable,
        str(Path(__file__).with_name("audit_external_objects.py")),
        str(mirror),
        str(restored / "git-report.json"),
        "--lfs-root",
        str(restored / "objects"),
        "--module",
        module_path,
        str(child),
    ]
    verified = json.loads(subprocess.check_output(command))
    assert verified["complete"] and verified["gitlink_tree_entries"] == 1
    assert verified["lfs"] == [
        dict(
            pointer_blob=pointer,
            oid=key.name,
            size=len(payload),
            actual_size=len(payload),
            actual_sha256=key.name,
            status="verified",
        )
    ]
    link = verified["submodules"][0]
    assert len(verified["submodules"]) == 1 and link["path"] == module_path
    assert link["example_commit"] == commit and link["root_tree"] == git(mirror, "rev-parse", commit + "^{tree}")
    assert link["revision"] == link["actual_oid"] == pin != git(child, "rev-parse", "HEAD")
    assert link["commit_tree"] == git(child, "rev-parse", pin + "^{tree}") and link["status"] == "verified"
    destination.unlink()
    empty_repo = root / "empty-module"
    git(root, "init", "-q", "--bare", str(empty_repo))
    missing_run = subprocess.run([*command[:-1], str(empty_repo)], capture_output=True, check=False)
    assert missing_run.returncode == 1
    missing = json.loads(missing_run.stdout)
    assert not missing["complete"]
    assert [(p["oid"], p["status"]) for p in missing["lfs"]] == [(key.name, "missing_payload")]
    assert [(p["revision"], p["status"]) for p in missing["submodules"]] == [(pin, "missing_revision")]
    return dict(
        publication=publication,
        lfs_source_id=binary_prefix + "lfs/" + key.name,
        lfs_export=binary,
        submodule_head=git(child, "rev-parse", "HEAD"),
        verified=verified,
        missing=missing,
    )


def test_target_positive_and_missing(snapshot, tmp_path):
    exercise_target(snapshot, tmp_path)


def test_corrupt_payload_unbound_module_and_inventory_drift(snapshot):
    folder, _, _, _, _, _, key, payload = snapshot
    mirror = folder / "archive.git"
    report = folder / "git-report.json"
    (mirror / "lfs" / "objects" / key).write_bytes(bytes(len(payload)))
    result = audit_external_objects(mirror, report)
    assert not result["complete"] and result["lfs"][0]["status"] == "payload_mismatch"
    assert result["submodules"][0]["status"] == "missing_repository"
    git(mirror, "update-ref", "refs/heads/later", "HEAD")
    with pytest.raises(ValueError, match="differ"):
        audit_external_objects(mirror, report)
