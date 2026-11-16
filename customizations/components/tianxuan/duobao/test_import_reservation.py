"""A failed competing import must not remove the first import's directory."""

import subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from git_service import GitService, GitServiceError


def test_same_name_import_does_not_remove_active_clone(tmp_path, monkeypatch):
    service = GitService()
    entered, release = Event(), Event()
    destination = tmp_path / "code.git"

    def clone(arguments, **kwargs):
        # Git may not have created the destination yet when its process starts.
        # The service must already own an exclusive reservation at this point.
        assert destination.is_dir()
        (destination / "HEAD").write_text("ref: refs/heads/main\n")
        entered.set()
        assert release.wait(10)
        return subprocess.CompletedProcess(arguments, 0, "", "")

    monkeypatch.setattr(service, "_run", clone)
    monkeypatch.setattr(service, "_symbolic_head", lambda *_: "main")
    monkeypatch.setattr(service, "_rev_parse", lambda *_: "a" * 40)
    monkeypatch.setattr(service, "list_branches", lambda *_: ["main"])
    monkeypatch.setattr(service, "list_tags", lambda *_: [])
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(service.import_repo, tmp_path, "code", "https://github.com/example/code.git")
        try:
            assert entered.wait(5)
            with pytest.raises(GitServiceError, match="already exists"):
                service.import_repo(tmp_path, "code", "https://github.com/example/code.git")
            assert (destination / "HEAD").read_text() == "ref: refs/heads/main\n"
        finally:
            release.set()
        assert first.result()["name"] == "code.git"


def test_failed_clone_cleans_only_owned_reservation(tmp_path, monkeypatch):
    service = GitService()
    sibling = tmp_path / "other.git"
    sibling.mkdir()
    monkeypatch.setattr(service, "_run", lambda args, **kwargs: subprocess.CompletedProcess(args, 128, "", "failed"))
    with pytest.raises(GitServiceError):
        service.import_repo(tmp_path, "failed", "https://github.com/example/code.git")
    assert not (tmp_path / "failed.git").exists()
    assert sibling.is_dir()
