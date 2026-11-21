"""Exercise the actual Git working tree, index and receiving bare branch."""

import subprocess
from concurrent.futures import ThreadPoolExecutor

import pytest
from selected_commit import diff, git, preview, receipt, receive
from selected_commit import submit as submit_workcopy


def submit(root, target, body, publish):
    return submit_workcopy(
        root, target, body, publish, lambda branch, base, sha: receipt(root.parent / "sample.git", branch, base, sha)
    )


@pytest.fixture
def copies(tmp_path):
    root, bare = tmp_path / "checkout", tmp_path / "sample.git"
    subprocess.run(["git", "init", "-q", "-b", "work", str(root)], check=True)
    for key, value in (("user.email", "g11@example.invalid"), ("user.name", "G11"), ("core.autocrlf", "false")):
        git(root, "config", key, value)
    for name in ("project.godot", "A.txt", "B.txt", "deleted.txt"):
        (root / name).write_bytes(b"old\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "initial")
    git(root, "clone", "-q", "--bare", str(root), str(bare))
    (root / "A.txt").write_bytes(b"chosen\n")
    (root / "B.txt").write_bytes(b"staged\n")
    git(root, "add", "B.txt")
    (root / "B.txt").write_bytes(b"working\n")
    return root, bare


def selection(root, paths):
    state = diff(root)
    return {**state, "paths": paths, "message": "用户选择的文件"}


def test_lost_receipt_and_concurrent_replay(copies):
    root, bare = copies
    request = selection(root, ["A.txt"])
    sent = []

    def lost(payload):
        sent.append(payload)
        receive(bare, **payload)
        raise OSError("response lost")

    with pytest.raises(OSError, match="lost"):
        submit(root, "sample", request, lost)
    assert git(root, "rev-parse", "HEAD").decode().strip() == request["base"]
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: receive(bare, **sent[0]), range(2)))
    received = submit(root, "sample", request, lambda body: receive(bare, **body))
    assert received == results[0] == results[1] == submit(root, "sample", request, lambda body: receive(bare, **body))
    assert git(bare, "rev-list", "--count", request["base"] + "..refs/heads/work") == b"1\n"
    assert git(root, "rev-parse", "HEAD") == git(bare, "rev-parse", "refs/heads/work")
    assert git(bare, "show", "work:A.txt") == b"chosen\n"
    assert git(bare, "show", "work:B.txt") == b"old\n"
    assert git(root, "show", ":B.txt") == b"staged\n"
    assert (root / "B.txt").read_bytes() == b"working\n"
    assert git(root, "diff", "--name-only", "HEAD") == b"B.txt\n"


def test_binary_delete_and_literal_names(copies):
    root, bare = copies
    name = "方[1] A.bin"
    (root / name).write_bytes(bytes(range(256)))
    (root / "deleted.txt").unlink()
    request = selection(root, [name, "deleted.txt"])
    assert "Binary files" in preview(root, request["base"], request["tree"], name)["diff"]
    submit(root, "sample", request, lambda p: receive(bare, **p))
    assert git(bare, "show", "work:" + name) == bytes(range(256))
    assert b"deleted.txt" not in git(bare, "ls-tree", "work")
    assert git(root, "show", ":B.txt") == b"staged\n"


def test_stale_bytes_and_moved_ref(copies):
    root, bare = copies
    request = selection(root, ["A.txt"])
    (root / "A.txt").write_bytes(b"new edits")
    with pytest.raises(ValueError, match="变化"):
        submit(root, "sample", request, lambda _: pytest.fail("stale selection sent"))
    git(root, "commit", "-qm", "other local commit")
    git(root, "push", str(bare), "HEAD:work")
    git(root, "reset", "--soft", request["base"])
    with pytest.raises(ValueError, match="前移"):
        submit(root, "sample", selection(root, ["A.txt"]), lambda p: receive(bare, **p))
    assert git(root, "rev-parse", "HEAD").decode().strip() == request["base"]


def test_partial_index_and_authenticated_branch_policy(copies, monkeypatch):
    from api import create_app
    from fastapi.testclient import TestClient
    from tianxuan_core import Tianxuan

    root, bare = copies
    monkeypatch.setenv("TIANXUAN_REPO_ROOT", str(bare.parent))
    store = Tianxuan(":memory:")
    actor = store.register("G11", "g11@example.invalid", "fixture-pass")["user_id"]
    viewer = store.add_member(actor, "viewer@example.invalid", "fixture-pass", role="viewer")
    client = TestClient(create_app(store, protected_branches=("release/*",)))
    admin = {"Authorization": "Bearer " + store.issue_session(actor)}
    read_only = {"Authorization": "Bearer " + store.issue_session(viewer["user_id"])}
    endpoint = "/api/v1/git/repos/sample.git/selected-commits"
    (root / "A.txt").write_bytes(b"old staging")
    git(root, "add", "A.txt")
    (root / "A.txt").write_bytes(b"chosen")
    request = selection(root, ["A.txt"])
    git(bare, "branch", "release/main", request["base"])
    git(bare, "symbolic-ref", "refs/heads/alias", "refs/heads/release/main")

    def publish(payload):
        assert client.post(endpoint, headers={"X-Actor": actor}, json=payload).status_code == 401
        assert client.post(endpoint, headers=read_only, json=payload).status_code == 403
        assert client.post(endpoint, headers=admin, json={**payload, "branch": "release/main"}).status_code == 403
        assert client.post(endpoint, headers=admin, json={**payload, "branch": "alias"}).status_code == 409
        assert (
            client.post(endpoint, headers={**admin, "content-length": str(32 << 20)}, content=b"{}").status_code == 413
        )
        response = client.post(endpoint, headers=admin, json=payload)
        assert response.status_code == 200, response.text
        return response.json()

    submit(root, "sample", request, publish)
    assert git(root, "show", ":A.txt") == b"old staging"
    assert git(bare, "show", "work:A.txt") == b"chosen"
    assert git(bare, "rev-parse", "refs/heads/release/main").decode().strip() == request["base"]
    store.db.close()


def test_staged_descendant_survives_file_replacement(copies):
    root, bare = copies
    folder = root / "folder"
    folder.mkdir()
    (folder / "old").write_bytes(b"old")
    git(root, "add", "folder/old")
    git(root, "commit", "-qm", "tracked directory", "--only", "folder")
    git(root, "push", str(bare), "HEAD:work")
    (folder / "extra").write_bytes(b"staged descendant")
    git(root, "add", "folder/extra")
    (folder / "extra").unlink()
    (folder / "old").unlink()
    folder.rmdir()
    folder.write_bytes(b"file replaces folder")
    request = selection(root, ["folder", "folder/old"])
    submit(root, "sample", request, lambda p: receive(bare, **p))
    assert git(root, "show", ":folder/extra") == b"staged descendant"
    assert git(bare, "show", "work:folder") == b"file replaces folder"
