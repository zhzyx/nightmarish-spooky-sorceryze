"""Verify the shared completion gate, compare-and-set semantics and older ticket history."""

import base64

import pytest
from api import create_app
from fastapi.testclient import TestClient
from native_store import NativeStore
from tianxuan_core import Tianxuan


@pytest.fixture
def service(tmp_path):
    store = Tianxuan(str(tmp_path / "db"))
    actor = store.register("I15", "a@example.invalid", "password")["user_id"]
    req = store.create_requirement(actor, "case", "Requirement", "Objective", "Scope", "Acceptance")
    store.set_visibility(actor, req["id"], "private")
    issue = store.create_issue(actor, "Test", requirement_id=req["id"], acceptance="Check the reviewed result")
    for stage in ("in-progress", "in-review"):
        store.transition_issue(actor, issue["id"], stage)
    url = "/api/v1/issues/" + issue["id"]
    with TestClient(
        create_app(store, native_store=NativeStore(tmp_path / "native")),
        headers={"Authorization": "Bearer " + store.issue_session(actor)},
    ) as client:
        yield store, actor, issue, client, url
    store.db.close()


def args(client, url, key):
    data = client.get(url + "/lifecycle").json()
    return dict(
        revision=data["revision"], expected_version=data["version"], asset_version=data["asset_version"], call_id=key
    )


@pytest.mark.parametrize("retained", [True, False])
def test_historical_ticket_after_database_upgrade(tmp_path, retained):
    import issue_lifecycle

    path = str(tmp_path / "old.db")
    store = Tianxuan(path)
    actor = store.register("Old", "a@example.invalid", "password")["user_id"]
    issue = store.create_issue(actor, "Legacy")
    with store.db:
        store.db.execute("DROP TABLE issue_lifecycle")
        store.db.execute("UPDATE issues SET status='done' WHERE id=?", (issue["id"],))
        if retained:
            store._event(
                issue["tenant_id"], "issue.transitioned", actor, issue["id"], {"from": "in-review", "to": "done"}
            )
    store.db.close()
    upgraded = Tianxuan(path)
    try:
        state = issue_lifecycle.read(upgraded, actor, issue["id"], issue["project"])
        assert state["accepted"] is None and state["reopen_to"] == "in-review"
        prior = ["historical"] if retained else []
        assert [row["kind"] for row in state["history"]] == prior
        call = (
            actor,
            issue["id"],
            issue["project"],
            "reopen",
            state["version"],
            state["revision"],
            None,
            "reopen",
            state["asset_version"],
        )
        assert issue_lifecycle.mutate(upgraded, *call) == issue_lifecycle.mutate(upgraded, *call)
        revised = issue_lifecycle.read(upgraded, actor, issue["id"], issue["project"])
        assert revised["number"] == issue["number"] and revised["status"] == "in-review"
        assert [row["kind"] for row in revised["history"]] == prior + ["reopened"]
    finally:
        upgraded.db.close()


@pytest.mark.parametrize("route", ["patch", "advance", "tool"])
def test_old_callers_require_evidence_and_work_with_current_receipt(service, route):
    store, actor, issue, client, url = service
    payload = args(client, url, "cycle")

    def advance():
        if route == "patch":
            return client.patch(url, json={"to_status": "done"})
        if route == "tool":
            return client.post(
                "/api/v1/tools",
                json={"name": "issue.transition", "payload": {"issue_id": issue["id"], "to_status": "done"}},
            )
        return client.post(
            url + "/work/flow/advance",
            json={"to_status": "done", "expected_version": payload["expected_version"], "call_id": "legacy-advance"},
        )

    assert advance().status_code == 409
    other = store.create_issue(actor, "Other")
    bad = store.add_issue_comment(actor, other["id"], "Reviewed")
    assert client.post(url + "/lifecycle/accept", json=dict(payload, comment=bad["id"])).status_code == 409
    evidence = store.add_issue_comment(actor, issue["id"], "Verified the accepted deliverable")
    assert advance().status_code == 409  # Posting a comment alone never certifies its contents.
    accepted = client.post(url + "/lifecycle/accept", json=dict(payload, comment=evidence["id"]))
    assert accepted.status_code == 200, accepted.text
    assert advance().status_code == 200
    assert [i["kind"] for i in client.get(url + "/lifecycle").json()["history"]] == ["accepted", "closed"]


def test_project_acl_replay_current_revision_and_managed_boundary(service):
    store, owner, issue, client, url = service
    editor = store.add_member(owner, "editor@example.invalid", "password", role="editor")["user_id"]
    viewer = store.add_member(owner, "viewer@example.invalid", "password", role="viewer")["user_id"]
    for actor in [editor, viewer]:
        store.share_doc(owner, issue["requirement_id"], actor, "write" if actor == editor else "read")
    edit = {"Authorization": "Bearer " + store.issue_session(editor)}
    readonly = {"Authorization": "Bearer " + store.issue_session(viewer)}
    payload = args(client, url, "accept")
    evidence = store.add_issue_comment(owner, issue["id"], "Observed the submitted candidate")
    acknowledge = dict(payload, comment=evidence["id"])
    for op, body in [("close", payload), ("accept", acknowledge), ("reopen", payload)]:
        assert client.post(url + "/lifecycle/" + op, json=body, headers=readonly).status_code == 403
    assert client.post(url + "/lifecycle/accept?project=other", json=acknowledge, headers=edit).status_code == 404
    assert client.post(url + "/lifecycle/accept", json=acknowledge, headers=edit).status_code == 200
    store.share_doc(owner, issue["requirement_id"], editor, "read")
    assert client.post(url + "/lifecycle/accept", json=acknowledge, headers=edit).status_code == 403
    req = store.get_doc(issue["requirement_id"])
    store.update_doc(owner, req["id"], req["body_md"] + " updated criteria", req["version"])
    assert client.post(url + "/lifecycle/close", json=payload).status_code == 409
    assert client.patch(url, json={"to_status": "done"}).status_code == 409
    with store.db:
        store.db.execute("INSERT INTO native_managed_issues VALUES (?,?,NULL)", (issue["id"], "contract"))
    state = client.get(url + "/lifecycle").json()
    assert state["managed"] and not state["can_close"]
    assert (
        client.post(url + "/lifecycle/accept", json=dict(args(client, url, "new"), comment=evidence["id"])).status_code
        == 409
    )


def test_current_asset_approval_is_required_and_new_submission_invalidates_receipt(service):
    store, owner, issue, client, url = service

    def publish(key, base, data):
        change = dict(module="art", base=base, reads=None, edits={"hero.glb": base64.b64encode(data).decode()})
        response = client.post("/api/v1/native/batches", json={"request_key": key, "changes": [change]})
        assert response.status_code == 200, response.text
        return response.json()["revisions"]["art"]

    r1 = publish("a", None, b"first")
    binding = dict(kind="model", revision=r1, module="art", path="hero.glb")
    assert (
        client.post(url + "/work/submit_asset", json=dict(binding, expected_version=0, call_id="submit")).status_code
        == 200
    )
    evidence = store.add_issue_comment(owner, issue["id"], "Reviewed the pinned model")
    confirm = dict(args(client, url, "signoff"), comment=evidence["id"])
    assert client.post(url + "/lifecycle/accept", json=confirm).status_code == 409
    assert (
        client.post(
            url + "/work/decide", json=dict(binding, expected_version=1, call_id="approve", decision="approved")
        ).status_code
        == 200
    )
    confirm = dict(args(client, url, "signoff"), comment=evidence["id"])
    assert client.post(url + "/lifecycle/accept", json=confirm).status_code == 200
    r2 = publish("b", r1, b"second")
    assert (
        client.post(
            url + "/work/submit_asset", json=dict(binding, revision=r2, expected_version=2, call_id="second")
        ).status_code
        == 200
    )
    assert client.get(url + "/lifecycle").json()["accepted"] is None
    assert client.patch(url, json={"to_status": "done"}).status_code == 409


def test_ordinary_parent_cannot_replace_its_own_evidence_with_unrelated_native_receipts(service):
    from issue_lifecycle import close_native_aggregate
    from tianxuan_core import TransitionRejected

    store, owner, _, client, _ = service
    parent = store.create_issue(owner, "Aggregate", type="requirement")
    child = store.create_issue(owner, "Managed", parent_id=parent["id"])
    for stage in ("in-progress", "in-review"):
        store.transition_issue(owner, parent["id"], stage)
    with store.db:
        store.db.execute("INSERT INTO native_managed_issues VALUES (?,?,?)", (child["id"], "contract", "release"))
        store.db.execute("UPDATE issues SET status='done' WHERE id=?", (child["id"],))
    url = "/api/v1/issues/" + parent["id"]
    assert client.patch(url, json={"to_status": "done"}).status_code == 409
    with pytest.raises(TransitionRejected):
        close_native_aggregate(store, owner, parent["id"], {"different-plan"})
    assert close_native_aggregate(store, owner, parent["id"], {child["id"]})["status"] == "done"


def test_manual_evidence_cannot_waive_managed_child_acceptance(service):
    store, owner, _, client, _ = service
    parent = store.create_issue(owner, "Aggregate", type="requirement")
    child = store.create_issue(owner, "Native", parent_id=parent["id"])
    with store.db:
        store.db.execute("INSERT INTO native_managed_issues VALUES (?,?,NULL)", (child["id"], "contract"))
    for stage in ("in-progress", "in-review"):
        store.transition_issue(owner, parent["id"], stage)
    url = "/api/v1/issues/" + parent["id"]
    comment = store.add_issue_comment(owner, parent["id"], "Read the separate manual evidence")
    assert (
        client.post(
            url + "/lifecycle/accept", json=dict(args(client, url, "confirm"), comment=comment["id"])
        ).status_code
        == 200
    )
    assert client.post(url + "/lifecycle/close", json=args(client, url, "try")).status_code == 409
    assert store.get_issue(parent["id"])["status"] == "in-review"
