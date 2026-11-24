"""Real HTTP and ordinary files: native submissions do not need Git or Godot."""

import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from api import create_app
from native_repository import NativeRepository
from native_repository_api import domain_authority
from native_store import NativeStore
from repository_client import Client, Workspace, initialize
from tianxuan_core import Tianxuan


@pytest.fixture
def service(tmp_path):
    domain = Tianxuan(str(tmp_path / "domain.sqlite"))
    account = domain.register("native-client", "owner@example.invalid", "client-test-password")
    token = domain.issue_session(account["user_id"])
    repo = NativeRepository(NativeStore(tmp_path / "native.sqlite"), domain_authority(domain))
    app = create_app(domain, native_repository=repo)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(128)
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started
    config = tmp_path / "host.json"
    config.write_text(
        json.dumps({
            "api": "http://127.0.0.1:" + str(sock.getsockname()[1]),
            "repository": "gonggong",
            "token_env": "NATIVE_TEST_TOKEN",
        })
    )
    client = Client(config, token=token)
    client.request("POST", "/bootstrap", {"request_key": "initialize"})
    yield client, config, token
    server.should_exit = True
    thread.join(10)
    sock.close()
    assert not thread.is_alive()
    domain.db.close()


def test_plain_directory_cli_empty_path_and_replay(service, tmp_path, monkeypatch):
    client, config, token = service
    root = tmp_path / "work"
    root.mkdir()
    (root / "code.txt").write_text("first")
    client.request("POST", "/branches", {"branch": "task/one", "revision": None, "request_key": "branch"})
    initialize(client, root, "task/one", None)
    env = {**os.environ, "PATH": "", "NATIVE_TEST_TOKEN": token}
    cli = Path(__file__).resolve().parents[1] / "duobao/repository_client.py"
    command = [
        sys.executable,
        str(cli),
        "--config",
        str(config),
        "submit",
        "--workspace",
        str(root),
        "--request-key",
        "submit-one",
        "--message",
        "首次提交",
    ]
    first = subprocess.run(command, env=env, capture_output=True, text=True, check=True)
    receipt = json.loads(first.stdout)["data"]
    assert receipt["state"] == "received"
    assert not (root / ".git").exists() and not (root / "project.godot").exists()
    (root / "code.txt").write_text("still-unsubmitted")
    replay = subprocess.run(command, env=env, capture_output=True, text=True, check=True)
    assert json.loads(replay.stdout)["data"] == receipt
    assert Workspace(client, root).status()["files"][0]["path"] == "code.txt"


def test_stale_workspace_rejected_and_selected_deletion(service, tmp_path):
    client, _, _ = service
    client.request("POST", "/branches", {"branch": "task/stale", "revision": None, "request_key": "branch"})
    roots = [tmp_path / "a", tmp_path / "b"]
    for root in roots:
        root.mkdir()
        initialize(client, root, "task/stale", None)
    (roots[0] / "a").write_bytes(b"a")
    accepted = Workspace(client, roots[0]).submit("first", "first")
    (roots[1] / "b").write_bytes(b"b")
    with pytest.raises(ValueError, match="409"):
        Workspace(client, roots[1]).submit("stale", "stale")
    assert client.branch("task/stale")["revision"] == accepted["revision"]
    (roots[0] / "a").unlink()
    (roots[0] / "unselected").write_text("private draft")
    deleted = Workspace(client, roots[0]).submit("delete", "delete", ["a"])
    assert client.revision(deleted["revision"])["objects"] == {}


def test_trusted_destination_binding_and_link_rejection(service, tmp_path):
    client, _, _ = service
    root = tmp_path / "ordinary"
    root.mkdir()
    initialize(client, root, "main", None)
    state = json.loads((root / ".duobao-workspace.json").read_text())
    state["binding"] = "0" * 64
    (root / ".duobao-workspace.json").write_text(json.dumps(state))
    with pytest.raises(ValueError, match="trusted"):
        Workspace(client, root)


def test_dual_submission_uses_frozen_git_tree_and_replays(service, tmp_path, monkeypatch):
    from git_submission import mirror

    client, config, _ = service
    settings = json.loads(config.read_text())
    settings.update(source_repository="example/source", dual_submit=True)
    config.write_text(json.dumps(settings))
    root = tmp_path / "git-source"
    root.mkdir()

    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.DEVNULL).decode().strip()

    git("init")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    (root / "file.txt").write_text("committed")
    git("add", "file.txt")
    git("commit", "-m", "source")
    commit = git("rev-parse", "HEAD")
    (root / "file.txt").write_text("uncommitted private data")
    result = mirror(root, commit, "example/source", config=config, client=client)
    revision = client.revision(result["native_revision"])
    obj = revision["objects"]["file.txt"]
    assert client.request("GET", "/objects/" + obj) == b"committed"
    assert mirror(root, commit, "example/source", config=config, client=client) == result
    assert client.branch("main")["revision"] is None

    receipt_path = root / ".git/gonggong-duobao" / (commit + ".json")
    original_receipt = receipt_path.read_bytes()
    original_request = client.request

    def unavailable(*args, **kwargs):
        raise OSError("simulated transport outage")

    monkeypatch.setattr(client, "request", unavailable)
    with pytest.raises(OSError):
        mirror(root, commit, "example/source", config=config, client=client)
    assert receipt_path.read_bytes() == original_receipt
    monkeypatch.setattr(client, "request", original_request)

    # The destination cannot silently change even for the same source commit.
    original_binding = client.binding
    monkeypatch.setattr(client, "binding", "0" * 64)
    with pytest.raises(ValueError, match="another target"):
        mirror(root, commit, "example/source", config=config, client=client)
    assert receipt_path.read_bytes() == original_receipt
    monkeypatch.setattr(client, "binding", original_binding)

    # Another authorized writer in this tenant reuses verified received bytes.
    domain = Tianxuan(str(tmp_path / "domain.sqlite"))
    owner = client.request("GET", "/identity")["actor"]
    colleague = domain.add_member(owner, "colleague@example.invalid", "colleague-password")["user_id"]
    colleague_client = Client(config, token=domain.issue_session(colleague))
    assert mirror(root, commit, "example/source", config=config, client=colleague_client) == result
    foreign = domain.register("other", "foreign@example.invalid", "foreign-password")["user_id"]
    foreign_client = Client(config, token=domain.issue_session(foreign))
    with pytest.raises(ValueError, match="another tenant"):
        mirror(root, commit, "example/source", config=config, client=foreign_client)
    assert receipt_path.read_bytes() == original_receipt
    domain.db.close()

    # A dropped commit response leaves durable pending; retry reads the real ref.
    git("add", "file.txt")
    git("commit", "-m", "second source")
    second = git("rev-parse", "HEAD")

    def lose_response(method, path, *args, **kwargs):
        value = original_request(method, path, *args, **kwargs)
        if path == "/commits":
            raise OSError("response lost after commit")
        return value

    monkeypatch.setattr(client, "request", lose_response)
    with pytest.raises(OSError):
        mirror(root, second, "example/source", config=config, client=client)
    pending = root / ".git/gonggong-duobao" / (second + ".json")
    assert json.loads(pending.read_text())["state"] == "pending"
    monkeypatch.setattr(client, "request", original_request)
    recovered = mirror(root, second, "example/source", config=config, client=client)
    assert recovered["state"] == "received"
    assert recovered["native_revision"] == client.branch("git/" + second)["revision"]


def test_workspace_rejects_other_tenant_and_rebound_pending(service, tmp_path):
    client, config, _ = service
    root = tmp_path / "ordinary"
    root.mkdir()
    client.request("POST", "/branches", {"branch": "task/old", "revision": None, "request_key": "old"})
    initialize(client, root, "task/old", None)
    (root / "code").write_text("frozen")
    Workspace(client, root).submit("fixed-key", "message")
    domain = Tianxuan(str(tmp_path / "domain.sqlite"))
    foreign = domain.register("other", "foreign@example.invalid", "foreign-password")["user_id"]
    foreign_client = Client(config, token=domain.issue_session(foreign))
    with pytest.raises(ValueError, match="authenticated tenant"):
        Workspace(foreign_client, root)
    domain.db.close()
    state = json.loads((root / ".duobao-workspace.json").read_text())
    client.request("POST", "/branches", {"branch": "task/new", "revision": state["revision"], "request_key": "new"})
    state["branch"] = "task/new"
    (root / ".duobao-workspace.json").write_text(json.dumps(state))
    with pytest.raises(ValueError, match="another submission"):
        Workspace(client, root).submit("fixed-key", "message")
