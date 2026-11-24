import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest
from git_archive import capture
from history_git import commit_mapping, list_commits
from history_records import record_detail
from import_git_history import import_git_history
from migration_status import read_import_status


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
        "GIT_AUTHOR_DATE": "2026-11-18T08:00:00+08:00",
        "GIT_COMMITTER_DATE": "2026-11-18T08:01:00+08:00",
    }.items():
        monkeypatch.setenv(key, value)
    repo = tmp_path / "source"
    repo.mkdir()
    git = ["git", "-C", str(repo)]

    def run(*args):
        return subprocess.check_output([*git, *args], encoding="utf-8").strip()

    run("init", "-q", "-b", "main", "--object-format=sha1")
    run("commit", "--allow-empty", "-qm", "root")
    run("checkout", "-qb", "topic")
    (repo / "topic").write_bytes(b"topic\n")
    run("add", "topic")
    run("commit", "-qm", "topic")
    run("checkout", "-q", "main")
    (repo / "main").write_bytes(b"main\n")
    run("add", "main")
    run("commit", "-qm", "main")
    run("merge", "-q", "--no-ff", "topic", "-m", "merge")
    run("checkout", "-q", "topic")
    run("commit", "--allow-empty", "-qm", "topic-only tip")
    run("checkout", "-q", "main")
    folder = tmp_path / "snapshot"
    folder.mkdir()
    mirror = folder / "archive.git"
    run("clone", "-q", "--mirror", "--", str(repo), str(mirror))
    subprocess.run(
        ["git", "-C", str(mirror), "remote", "set-url", "origin", "https://github.com/sample/repo.git"], check=True
    )
    capture("sample/repo", folder)
    return folder, run


def row_counts(db):
    tables = ("native_blobs", "native_heads", "native_revisions", "native_receipts", "migration_publications")
    with closing(sqlite3.connect(db)) as connection:
        return {table: connection.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] for table in tables}


def test_replay_and_resolve_all_source_commits(snapshot, tmp_path):
    folder, source_git = snapshot
    db = tmp_path / "native.sqlite"
    args = [
        sys.executable,
        str(Path(__file__).with_name("import_git_history.py")),
        str(folder),
        str(db),
        "--tenant",
        "owners",
        "--actor",
        "operator",
        "--project",
        "isolated",
    ]
    first = json.loads(subprocess.check_output(args))
    first_counts = row_counts(db)
    assert json.loads(subprocess.check_output(args)) == first
    assert row_counts(db) == first_counts
    assert first_counts["migration_publications"] == 1
    assert first["publication"] == read_import_status(db, "owners", "isolated")
    target = (db, "owners", "isolated", first["revision"])
    oids = set(source_git("rev-list", "--all").splitlines())
    assert len(oids) == 5 and first["counts"] == {"commit": len(oids)}
    assert len(source_git("show", "-s", "--format=%P", "refs/heads/main", "--").split()) == 2
    results = list_commits(*target)["items"]
    assert len(results) == len(oids) and {item["oid"] for item in results} == oids
    for oid in oids:
        tree, *parents = source_git("show", "-s", "--format=%T %P", oid).split()
        mapping = commit_mapping(*target, oid)
        sid = f"github:sample/repo/commit/{oid}"
        assert mapping["source_id"] == sid and mapping["oid"] == oid
        assert mapping["module"] == first["module"]
        assert mapping["tree"] == tree and mapping["parents"] == parents
        assert record_detail(*target, sid)["record"]["content"] == {"oid": oid, "parents": parents}


def test_changed_snapshot_preserves_current_publication(snapshot, tmp_path):
    folder, _ = snapshot
    db = tmp_path / "native.sqlite"
    args = folder, db, "owners", "operator", "isolated"
    first = import_git_history(*args)
    report = folder / "git-report.json"
    data = json.loads(report.read_bytes())
    data["commit_count"] -= 1
    report.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="commit count"):
        import_git_history(*args)
    assert read_import_status(db, "owners", "isolated") == first["publication"]


@pytest.mark.parametrize("revision", ["HEAD:main", "HEAD^{tree}"])
def test_missing_reachable_object_blocks_initial_import_and_replay(snapshot, tmp_path, revision):
    folder, git = snapshot
    db = tmp_path / "published.sqlite"
    fresh = tmp_path / "new.sqlite"
    args = ("owners", "operator", "isolated")
    publication = import_git_history(folder, db, *args)["publication"]
    counts = row_counts(db)
    oid = git("rev-parse", revision)
    obj = folder / "archive.git" / "objects" / oid[:2] / oid[2:]
    held = tmp_path / "held-object"
    obj.rename(held)
    try:
        for target in (fresh, db):
            with pytest.raises(ValueError, match=oid):
                import_git_history(folder, target, *args)
        assert not fresh.exists()
        assert row_counts(db) == counts
        assert read_import_status(db, "owners", "isolated") == publication
    finally:
        held.rename(obj)
    assert import_git_history(folder, db, *args)["publication"] == publication
