import pytest
from git_archive import capture, git
from history_git import commit_mapping
from history_records import record_detail, search_records
from import_git_history import import_git_history
from migration_status import publish_import, read_import_status
from sync_merged_pull import sync
from test_import_git_history import row_counts, snapshot  # noqa: F401


def test_fast_forward_replay_and_stale_writer(snapshot, tmp_path, monkeypatch):  # noqa: F811
    folder, source_git = snapshot
    source = folder / "archive.git"
    merged = source_git("rev-parse", "main")
    parent = source_git("rev-parse", "main^1")
    # Only the pre-merge main exists in the destination.
    base = tmp_path / "before"
    base.mkdir()
    git(base, "init", "--bare", "--initial-branch=main", "archive.git")
    target = base / "archive.git"
    git(target, "fetch", "--no-tags", "--", str(source), parent + ":refs/heads/main")
    git(target, "remote", "add", "origin", "https://github.com/sample/repo.git")
    capture("sample/repo", base)
    db = tmp_path / "native.sqlite"
    previous = import_git_history(base, db, "tenant", "importer", "archive")["publication"]
    url = "https://github.com/sample/repo/pull/12"
    pr = dict(number=12, title="Old pull", body="p" * 70000, base={"ref": "main"}, merge_commit_sha=merged)
    review = dict(
        id=7,
        body="Approved",
        pull_request_url="https://api.github.com/repos/sample/repo/pulls/12",
        html_url=url + "#pullrequestreview-7",
        state="APPROVED",
    )
    monkeypatch.setattr("sync_merged_pull.github_pull", lambda *args: (pr, {"review": [review]}, dict(number=12)))
    args = db, "tenant", "importer", "archive", source, 12
    original_counts = row_counts(db)
    with pytest.raises(ValueError, match="OID differs"):
        sync(*args, parent)
    assert row_counts(db) == original_counts

    first = sync(*args, merged)
    status = first["publication"]
    scope = db, "tenant", "archive", status["revision"]
    assert commit_mapping(*scope, merged)["parents"][0] == parent
    assert status["source_revision"] == merged
    assert search_records(*scope, "#12", "pull")["total"] == 1
    assert search_records(*scope, "#12")["total"] == 1
    details = record_detail(*scope, first["source_id"])
    assert details["record"]["truncated"] and details["comments"]["items"][0]["content"] == review
    counts = row_counts(db)
    assert counts["migration_publications"] == 2
    repeated = sync(*args, merged)
    assert repeated["state"] == "already_synced" and repeated["publication"] == status
    with pytest.raises(ValueError, match="publication changed"):
        publish_import(
            db,
            "tenant",
            "archive",
            "stale",
            previous["module"],
            previous["revision"],
            expected_current=previous["revision"],
        )
    assert row_counts(db) == counts and read_import_status(db, "tenant", "archive") == status
