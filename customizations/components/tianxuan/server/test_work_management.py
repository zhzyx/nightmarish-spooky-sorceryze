"""Issue #1552 cross-entry, restart, authorization and concurrency contracts."""

import base64
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from api import create_app
from fastapi.testclient import TestClient
from native_store import NativeStore
from tianxuan_core import PermissionDenied, Tianxuan, UnknownTool, VersionConflict


@pytest.fixture
def work(tmp_path):
    path = tmp_path / "issues.db"
    store = Tianxuan(str(path))
    owner = store.register("studio", "owner@example.invalid", "password")["user_id"]
    issue = store.create_issue(owner, "Historical ticket")["id"]
    # Reopen a pre-feature database with its existing ticket and no work event table.
    store.db.execute("DROP TABLE issue_work_events")
    store.db.commit()
    store.db.close()
    store = Tianxuan(str(path))
    native = NativeStore(tmp_path / "assets.db")
    with TestClient(create_app(store, native_store=native)) as client:
        yield path, store, native, client, owner, issue
    store.db.close()


def test_historical_issue_plan_and_persistent_replay(work):
    path, store, native, client, actor, issue = work
    url = f"/api/v1/issues/{issue}/work"
    headers = {"Authorization": "Bearer " + store.issue_session(actor)}
    old = client.get(url, headers=headers)
    assert old.status_code == 200, old.text
    assert old.json()["version"] == old.json()["logged_minutes"] == 0
    plan = dict(
        iteration="Sprint 1",
        milestone="Release",
        roadmap="Art",
        estimated_minutes=90,
        status="Art review",
        custom_fields={"team": "models"},
    )
    payload = dict(expected_version=0, plan=plan)
    first = client.post(url + "/plan", headers=headers, json=dict(payload, call_id="plan"))
    assert first.status_code == 200, first.text
    assert first.json()["plan"] == plan
    updated = store.dispatch_tool(
        actor, "work.log", dict(issue_id=issue, expected_version=1, minutes=12, note="Sketch"), call_id="log"
    )
    assert updated["logged_minutes"] == 12
    reopened = Tianxuan(str(path))
    try:
        assert reopened.dispatch_tool(actor, "work.plan", dict(payload, issue_id=issue), call_id="plan") == first.json()
        assert reopened.dispatch_tool(actor, "work.read", {"issue_id": issue}) == updated
        with pytest.raises(VersionConflict):
            reopened.dispatch_tool(
                actor, "work.plan", dict(payload, issue_id=issue, plan={"status": "other"}), call_id="plan"
            )
    finally:
        reopened.db.close()


@pytest.mark.parametrize("same_key", [False, True])
def test_concurrent_connections_never_double_log(work, same_key):
    path, store, _, _, actor, issue = work
    ready = threading.Barrier(2)

    def log(key):
        other = Tianxuan(str(path))
        try:
            ready.wait(timeout=10)
            return other.dispatch_tool(
                actor, "work.log", dict(issue_id=issue, expected_version=0, minutes=5, note="paint"), call_id=key
            )
        except VersionConflict:
            return None
        finally:
            other.db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(log, ["a", "a" if same_key else "b"]))
    assert results.count(None) == (0 if same_key else 1)
    current = store.dispatch_tool(actor, "work.read", {"issue_id": issue})
    assert current["version"] == len(current["logs"]) == 1
    assert current["logged_minutes"] == 5


def test_revoked_ancestor_acl_covers_read_and_receipt_replay(work):
    _, store, _, client, owner, _ = work
    code = store.create_invite(owner, "editor@example.invalid", "editor")["code"]
    actor = store.accept_invite(code, "password")["user_id"]
    req = store.create_requirement(owner, "art", "Art", "Outcome", "Scope", "Accept")["id"]
    store.set_visibility(owner, req, "private")
    store.share_doc(owner, req, actor, "write")
    parent = store.create_issue(owner, "Private", requirement_id=req)["id"]
    issue = store.create_issue(owner, "Child", parent_id=parent)["id"]
    payload = dict(issue_id=issue, expected_version=0, minutes=5, note="work")
    store.dispatch_tool(actor, "work.log", payload, call_id="log")
    store.unshare_doc(owner, req, actor)
    with pytest.raises(PermissionDenied):
        store.dispatch_tool(actor, "work.log", payload, call_id="log")
    assert client.get(f"/api/v1/issues/{issue}/work", headers={"X-Actor": actor}).status_code in (403, 404)


@pytest.mark.parametrize("kind, filename", [("concept", "sketch.png"), ("model", "hero.glb")])
def test_human_decision_is_pinned_to_submitted_native_revision(work, kind, filename):
    _, store, _, client, actor, issue = work
    headers = {"Authorization": "Bearer " + store.issue_session(actor)}
    url = f"/api/v1/issues/{issue}/work"

    def publish(base, content, key):
        change = {"module": "art", "base": base, "reads": None, "edits": {filename: base64.b64encode(content).decode()}}
        result = client.post("/api/v1/native/batches", headers=headers, json={"request_key": key, "changes": [change]})
        assert result.status_code == 200, result.text
        return result.json()["revisions"]["art"]

    def post(action, payload):
        return client.post(url + "/" + action, headers=headers, json=payload)

    r1 = publish(None, b"first", "create")
    asset = dict(kind=kind, module="art", revision=r1, path=filename)
    invalid = post("submit_asset", dict(asset, path="missing", expected_version=0, call_id="missing"))
    assert 400 <= invalid.status_code < 500
    sent = post("submit_asset", dict(asset, expected_version=0, call_id="submit"))
    assert sent.status_code == 200, sent.text
    assert sent.json()["assets"][kind]["digest"] == hashlib.sha256(b"first").hexdigest()
    r2 = publish(r1, b"second", "replace")
    decision = dict(asset, decision="approved", note="Reviewed", expected_version=1)
    with pytest.raises(UnknownTool):
        store.dispatch_tool(actor, "work.decide", dict(decision, issue_id=issue))
    wrong = post("decide", dict(decision, revision=r2, call_id="wrong"))
    assert 400 <= wrong.status_code < 500
    confirmed = post("decide", dict(decision, call_id="human"))
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["assets"][kind]["decision"] == "approved"
    assert post("decide", dict(decision, call_id="human")).json() == confirmed.json()
    newer = post("submit_asset", dict(asset, revision=r2, expected_version=2, call_id="new"))
    assert newer.status_code == 200, newer.text
    assert newer.json()["assets"][kind]["decision"] != "approved"
    assert newer.json()["assets"][kind]["revision"] == r2


def test_roadmap_orders_plans_matches_detail_and_revokes_access(work):
    _, store, _, client, owner, issue = work
    code = store.create_invite(owner, "viewer@example.invalid", "viewer")["code"]
    viewer = store.accept_invite(code, "password")["user_id"]
    headers = {"Authorization": "Bearer " + store.issue_session(viewer)}
    req = store.create_requirement(owner, "secret", "Private", "Goal", "Scope", "Acceptance")["id"]
    store.set_visibility(owner, req, "private")
    store.share_doc(owner, req, viewer, "read")
    private = store.create_issue(owner, "Private issue", requirement_id=req)["id"]
    third = store.create_issue(owner, "Same roadmap")["id"]
    for issue_id, roadmap, milestone in [(issue, "B", "First"), (private, "A", "Two"), (third, "A", "One")]:
        store.dispatch_tool(
            owner,
            "work.plan",
            dict(issue_id=issue_id, expected_version=0, plan={"roadmap": roadmap, "milestone": milestone}),
            call_id=issue_id,
        )
    store.dispatch_tool(owner, "work.log", dict(issue_id=issue, expected_version=1, minutes=12), call_id="time")

    def read():
        response = client.get("/api/v1/work/roadmap", headers=headers)
        assert response.status_code == 200, response.text
        return response.json()["items"]

    rows = read()
    assert [row["id"] for row in rows] == [third, private, issue]
    for row in rows:
        details = client.get("/api/v1/issues/" + row["id"] + "/work", headers=headers).json()
        assert (row["plan"], row["logged_minutes"]) == (details["plan"], details["logged_minutes"])
    store.unshare_doc(owner, req, viewer)
    assert [row["id"] for row in read()] == [third, issue]
