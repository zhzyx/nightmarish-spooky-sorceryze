"""HTTP and domain consumers of issue-scoped approved native assets (#1602)."""

import base64
import hashlib
from pathlib import Path

import pytest
from api import create_app
from fastapi.testclient import TestClient
from native_store import NativeStore
from tianxuan_core import Tianxuan
from work_management import read_approved_asset

DATA = Path(__file__).resolve().parents[4] / "tests/data"


@pytest.fixture
def studio(tmp_path):
    store = Tianxuan(str(tmp_path / "work.db"))
    actor = store.register("studio", "owner@example.invalid", "secret")["user_id"]
    req = store.create_requirement(actor, "art", "Art", "Outcome", "Scope", "Review")["id"]
    store.set_visibility(actor, req, "private")
    parent = store.create_issue(actor, "Art", requirement_id=req)["id"]
    issue = store.create_issue(actor, "Character", parent_id=parent)["id"]
    native = NativeStore(tmp_path / "native.db")
    with TestClient(create_app(store, native_store=native)) as client:
        yield store, client, actor, issue, req
    store.db.close()


@pytest.mark.parametrize("kind,filename", [("concept", "images/icon.png"), ("model", "models/suzanne.glb")])
def test_consume_only_current_exact_approved_input(studio, kind, filename):
    store, client, owner, issue, req = studio

    def headers(actor):
        return {"Authorization": "Bearer " + store.issue_session(actor)}

    auth = headers(owner)
    data = (DATA / filename).read_bytes()
    path = Path(filename).name
    url = f"/api/v1/issues/{issue}/work"

    def publish(key, base=None):
        # A new native revision may bind the same asset content.
        edits = {path: base64.b64encode(data).decode(), "note.txt": base64.b64encode(key.encode()).decode()}
        result = client.post(
            "/api/v1/native/batches",
            headers=auth,
            json={"request_key": key, "changes": [dict(module="art", base=base, reads=None, edits=edits)]},
        )
        assert result.status_code == 200, result.text
        return result.json()["revisions"]["art"]

    binding = dict(kind=kind, module="art", revision=publish("one"), path=path)

    def submit(version, **changes):
        response = client.post(
            url + "/submit_asset",
            headers=auth,
            json={**binding, **changes, "expected_version": version, "call_id": str(version)},
        )
        assert response.status_code == 200, response.text

    def decide(version, decision):
        response = client.post(
            url + "/decide",
            headers=auth,
            json={**binding, "expected_version": version, "decision": decision, "call_id": str(version)},
        )
        assert response.status_code == 200, response.text

    def consume(identity=auth, target=issue, **changes):
        return client.get(f"/api/v1/issues/{target}/work/approved-asset", headers=identity, params=binding | changes)

    submit(0)
    assert consume().status_code == 409
    decide(1, "changes_requested")
    assert consume().status_code == 409
    submit(2)
    decide(3, "approved")
    second = publish("two", binding["revision"])
    result = consume()
    assert result.status_code == 200 and result.content == data
    assert "no-store" in result.headers["cache-control"]
    assert read_approved_asset(store, owner, issue, **binding) == data
    for changes in (
        {"module": "other"},
        {"revision": second},
        {"path": "note.txt"},
        {"kind": "model" if kind == "concept" else "concept"},
    ):
        assert consume(**changes).status_code == 409
    assert consume(target=store.create_issue(owner, "Other ticket")["id"]).status_code == 409
    other = store.register("other", "other@example.invalid", "secret")["user_id"]
    assert consume(headers(other)).status_code == 404
    assert 400 <= consume({}).status_code < 500

    invite = store.create_invite(owner, "reader@example.invalid", "viewer")
    reader = store.accept_invite(invite["code"], "secret")["user_id"]
    reader_auth = headers(reader)
    store.share_doc(owner, req, reader, "read")
    assert consume(reader_auth).content == data
    store.unshare_doc(owner, req, reader)
    assert consume(reader_auth).status_code == 403

    # Change both historical digests consistently; the original bytes must still be checked.
    digest = hashlib.sha256(data).hexdigest()
    with store.db:
        store.db.execute(
            "UPDATE issue_work_events SET data=replace(data,?,?) WHERE issue_id=?", (digest, "0" * 64, issue)
        )
    assert consume().status_code == 409
    with store.db:
        store.db.execute(
            "UPDATE issue_work_events SET data=replace(data,?,?) WHERE issue_id=?", ("0" * 64, digest, issue)
        )
    assert consume().content == data
    submit(4, revision=second)
    assert consume().status_code == 409
    assert consume(revision=second).status_code == 409


def test_approved_bytes_follow_native_source_acl_even_when_issue_remains_visible(studio):
    store, client, owner, issue, req = studio
    reader = store.accept_invite(store.create_invite(owner, "viewer@example.invalid", "viewer")["code"], "password")[
        "user_id"
    ]
    store.share_doc(owner, req, reader, "read")
    source = store.create_requirement(owner, "source", "Private source", "Input", "Scope", "Accept")["id"]
    module = store.bind_native_requirement(owner, source)
    store.set_visibility(owner, source, "private")
    store.share_doc(owner, source, reader, "read")
    content = (DATA / "images/icon.png").read_bytes()
    revision = store.work_native_store.submit(
        store.actor_context(owner)["tenant"],
        owner,
        "source",
        [dict(module=module, base=None, reads=None, edits={"icon.png": content})],
    )["revisions"][module]
    binding = dict(kind="concept", module=module, revision=revision, path="icon.png")
    url = f"/api/v1/issues/{issue}/work"
    owner_headers = {"Authorization": "Bearer " + store.issue_session(owner)}
    reader_headers = {"Authorization": "Bearer " + store.issue_session(reader)}
    for version, action, extra in [(0, "submit_asset", {}), (1, "decide", {"decision": "approved"})]:
        response = client.post(
            url + "/" + action,
            headers=owner_headers,
            json=dict(binding, expected_version=version, call_id=action, **extra),
        )
        assert response.status_code == 200, response.text
    assert client.get(url + "/approved-asset", headers=reader_headers, params=binding).content == content
    store.unshare_doc(owner, source, reader)
    assert any(ticket["id"] == issue for ticket in store.list_issues(reader))
    assert client.get(url + "/approved-asset", headers=reader_headers, params=binding).status_code == 403
