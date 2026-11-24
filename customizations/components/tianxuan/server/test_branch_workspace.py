"""Real Git checkouts covering preserve/switch/recover failure boundaries."""

import shutil
import subprocess
from pathlib import Path

import pytest
from branch_workspace import branch_state, change


def git(repo, *args):
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], text=True, encoding="utf-8", stderr=subprocess.PIPE
    ).strip()


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_EXECUTABLE", shutil.which("git"))
    root = tmp_path / "checkout"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "g10-fixture@example.invalid")
    git(root, "config", "user.name", "G10 fixture")
    git(root, "config", "core.autocrlf", "false")
    subproject = root / "game [review]"
    subproject.mkdir()
    for directory in (root, subproject):
        (directory / "project.godot").write_bytes(b"config_version=5\n")
    (subproject / "script.gd").write_bytes(b"# base\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "original")
    git(root, "branch", "side")
    return subproject


def switch(project, branch, preserve=False):
    state = branch_state(project)
    target = git(project, "show-ref", "--verify", "--hash", "refs/heads/" + branch)
    return change(project, "switch", branch, target, f"{state['branch']}@{state['head']}", preserve)


def restore(project, oid):
    state = branch_state(project)
    return change(project, "restore", "", "", f"{state['branch']}@{state['head']}", False, oid)


def test_local_tag_names_and_exact_multiple_recoveries(project):
    git(project, "tag", "main")
    git(project, "tag", "side")
    script = project / "script.gd"
    drafts = []
    for version in (b"first", b"second"):
        staged = b"# staged " + version + b"\n"
        working = staged + b"# working\n"
        script.write_bytes(staged)
        git(project, "add", "--", "script.gd")
        script.write_bytes(working)
        (project / "draft.txt").write_bytes(version)
        assert switch(project, "side", preserve=True)["branch"] == "side"
        assert script.read_bytes() == b"# base\n"
        state = switch(project, "main")
        assert state["branch"] == "main" and state["recovery"]
        drafts.append((state["recovery"], staged, working, version))
    assert drafts[0][0] != drafts[1][0]
    with pytest.raises(ValueError, match="OID"):
        restore(project, drafts[0][0])
    assert not branch_state(project)["dirty"]
    for oid, staged, working, version in reversed(drafts):
        state = restore(project, oid)
        assert state["recovery"] != oid
        assert script.read_bytes() == working
        assert git(project, "show", ":./script.gd") == staged.decode().strip()
        assert (project / "draft.txt").read_bytes() == version
        git(project, "restore", "--staged", "--worktree", "--", "script.gd")
        (project / "draft.txt").unlink()
    assert branch_state(project)["recovery"] == ""
    assert set(git(project, "stash", "list", "--format=%H").splitlines()) == {item[0] for item in drafts}


def test_legacy_stash_created_with_ambiguous_short_branch(project):
    head = git(project, "rev-parse", "HEAD")
    git(project, "tag", "main")
    (project / "script.gd").write_bytes(b"# previous editor\n")
    git(project, "stash", "push", "-m", "workbench-g10/heads/main/" + head)
    oid = git(project, "rev-parse", "refs/stash")
    assert branch_state(project)["recovery"] == oid
    assert restore(project, oid)["recovery"] == ""
    assert (project / "script.gd").read_bytes() == b"# previous editor\n"


def test_reject_target_missing_current_nested_project_before_stash(project):
    git(project, "switch", "side")
    git(project, "rm", "--", "project.godot")
    git(project, "commit", "-qm", "only root project remains")
    git(project, "switch", "main")
    script = project / "script.gd"
    script.write_bytes(b"# draft\n")
    git(project, "add", "--", "script.gd")
    (project / "draft.txt").write_bytes(b"untracked")
    before = branch_state(project)
    with pytest.raises(ValueError, match="未包含当前项目文件"):
        switch(project, "side", preserve=True)
    assert branch_state(project) == before
    assert git(project, "stash", "list") == ""
    assert script.read_bytes() == b"# draft\n"
    assert git(project, "show", ":./script.gd") == "# draft"
    assert (project / "draft.txt").read_bytes() == b"untracked"


def test_failed_restore_leaves_same_oid_available(project):
    draft = project / "draft.txt"
    draft.write_bytes(b"recover")
    switch(project, "side", preserve=True)
    oid = switch(project, "main")["recovery"]
    exclude = Path(git(project, "rev-parse", "--path-format=absolute", "--git-path", "info/exclude"))
    with exclude.open("a", encoding="utf-8") as output:
        output.write("\ndraft.txt\n")
    draft.write_bytes(b"ignored occupant")
    assert not branch_state(project)["dirty"]
    with pytest.raises(subprocess.CalledProcessError):
        restore(project, oid)
    assert branch_state(project)["recovery"] == oid
    assert draft.read_bytes() == b"ignored occupant"
    draft.unlink()
    assert restore(project, oid)["recovery"] == ""
    assert draft.read_bytes() == b"recover"
