"""Selected materialized paths are checked against the authenticated base and live disk bytes."""

import json

import pytest
from api import create_app
from fastapi.testclient import TestClient
from native_store import NativeStore, _digest, _json
from native_workcopy_commit import NativeProject
from native_workspace import NativeWorkspace
from tianxuan_core import Tianxuan


@pytest.fixture
def setup(tmp_path):
    tmp_path = tmp_path.resolve()
    accounts = Tianxuan(":memory:")
    owner = accounts.register("G11", "owner@example.invalid", "native-test-password")
    token = accounts.issue_session(owner["user_id"])
    store = NativeStore(tmp_path / "native.db")
    module = "game"
    seed = store.submit(
        owner["tenant_id"],
        owner["user_id"],
        "seed",
        [
            {
                "module": module,
                "base": None,
                "reads": None,
                "edits": {
                    "sub/project.godot": b"config_version=5",
                    "sub/A": b"old",
                    "sub/B": b"other",
                    "private-outside": b"private",
                },
            }
        ],
    )
    root = tmp_path / "snapshot"
    NativeWorkspace(store).materialize(owner["tenant_id"], seed["revisions"], root)
    project = root / module / "sub"
    marker = root / ".duobao-source.json"
    headers = {"Authorization": "Bearer " + token}
    with TestClient(create_app(accounts, native_store=store, native_only=True)) as client:

        def request(method, path, data=None):
            response = client.request(method, "/api/v1/native/" + path, headers=headers, json=data)
            response.raise_for_status()
            return response.json()

        def open_project():
            return NativeProject(project, marker, "fixture", request, None)

        yield project, marker, open_project, store, accounts, owner, client
    accounts.db.close()


def test_binary_add_delete_and_leftover(setup):
    project, _, open_project, store, _, owner, _ = setup
    (project / "A").unlink()
    (project / "B").write_bytes(b"leave me")
    (project / "new.bin").write_bytes(bytes(range(256)))
    (project / ".godot").mkdir()
    (project / ".godot" / "cache.bin").write_bytes(b"private")
    work = open_project()
    state = work.diff()
    assert {entry["path"] for entry in state["files"]} == {"sub/A", "sub/B", "sub/new.bin"}
    selected = {e["path"]: e["digest"] for e in state["files"] if e["path"] != "sub/B"}
    body = {**state, "message": "selected", "paths": list(selected), "digests": selected}
    result = work.submit(body)
    revised = store.revision(owner["tenant_id"], "game", result["sha"])
    assert "sub/A" not in revised["objects"] and "private-outside" in revised["objects"]
    assert store.read(owner["tenant_id"], "game", result["sha"], "sub/new.bin") == bytes(range(256))
    assert [e["path"] for e in open_project().diff()["files"]] == ["sub/B"]
    assert open_project().submit(body) == result
    assert store.read(owner["tenant_id"], "game", result["sha"], "sub/B") == b"other"


def test_content_drift_tenant_and_scope(setup):
    project, marker, open_project, store, accounts, owner, client = setup
    (project / "A").write_bytes(b"first")
    work = open_project()
    state = work.diff()
    entry = state["files"][0]
    body = {**state, "message": "selected", "paths": [entry["path"]], "digests": {entry["path"]: entry["digest"]}}
    (project / "A").write_bytes(b"new bytes")
    with pytest.raises(ValueError, match="已变化"):
        work.submit(body)
    with pytest.raises(ValueError, match="超出项目"):
        work.submit({**body, "paths": ["private-outside"], "digests": {"private-outside": "deleted"}})
    assert store.head(owner["tenant_id"], "game") == state["base"]
    other = accounts.add_member(owner["user_id"], "other@example.invalid", "native-test-password", role="editor")
    response = client.get(
        "/api/v1/native/batches/seed", headers={"Authorization": "Bearer " + accounts.issue_session(other["user_id"])}
    )
    assert response.status_code == 200 and response.json()["receipt"] is None
    manifest = json.loads(marker.read_bytes())
    manifest.pop("source_digest")
    manifest["tenant"] = "another"
    manifest["source_digest"] = _digest(_json(manifest).encode())
    marker.write_bytes(_json(manifest).encode())
    with pytest.raises(ValueError, match="登录租户"):
        open_project()


@pytest.mark.parametrize("written", [True, False], ids=["reply-lost", "never-received"])
def test_reopen_reconciles_unknown_write(setup, written, record_property):
    project, _, open_project, store, _, owner, _ = setup
    (project / "A").write_bytes(b"confirmed")
    work = open_project()
    state = work.diff()
    selected = {e["path"]: e["digest"] for e in state["files"]}
    body = {**state, "message": "R06", "paths": list(selected), "digests": selected}
    calls = []
    request = work.request

    def transport(method, path, data=None):
        if path.startswith("batches"):
            calls.append((method, path.removeprefix("batches/") if method == "GET" else data["request_key"]))
        if method == "POST" and len(calls) == 2:
            if written:
                request(method, path, data)
            raise ConnectionError("lost response")
        return request(method, path, data)

    work.request = transport
    with pytest.raises(ConnectionError):
        work.submit(body)
    reopened = open_project()
    reopened.request = transport
    received = reopened.submit(body)
    key = received["request_key"]
    assert calls == [("GET", key), ("POST", key), ("GET", key)] + ([] if written else [("POST", key)])
    with store._connection() as db:
        effects = db.execute(
            "SELECT COUNT(*) FROM native_revisions WHERE tenant=? AND module=? AND id!=?",
            (owner["tenant_id"], "game", state["base"]),
        ).fetchone()[0]
    assert effects == 1
    assert store.read(owner["tenant_id"], "game", received["sha"], "sub/A") == b"confirmed"
    assert open_project().base == received["sha"]
    record_property("reconciliation", json.dumps({"written": written, "calls": calls, "effects": effects, **received}))


def test_rebound_receipt_retains_checkpoint(setup):
    project, _, open_project, _, _, _, _ = setup
    (project / "A").write_bytes(b"confirmed")
    work = open_project()
    state = work.diff()
    selected = {e["path"]: e["digest"] for e in state["files"]}
    body = {**state, "message": "R06", "paths": list(selected), "digests": selected}
    request = work.request

    def changed_receipt(method, path, data=None):
        result = request(method, path, data)
        if method == "POST":
            result["request_digest"] = "0" * 64
        return result

    work.request = changed_receipt
    with pytest.raises(ValueError, match="回执不匹配"):
        work.submit(body)
    assert open_project().base == state["base"]
    assert open_project().submit(body)["sha"] == open_project().base
