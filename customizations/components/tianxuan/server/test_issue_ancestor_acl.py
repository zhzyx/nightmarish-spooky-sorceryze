"""Regression coverage for direct and inherited requirement ACLs."""

import pytest
from tianxuan_core import PermissionDenied, Tianxuan


@pytest.fixture
def state(tmp_path):
    tx = Tianxuan(str(tmp_path / "independent.db"))
    owner = tx.register("review", "review-owner@example.invalid", "password")["user_id"]
    invite = tx.create_invite(owner, "review-editor@example.invalid", "editor")
    actor = tx.accept_invite(invite["code"], "password")["user_id"]
    req = tx.create_requirement(owner, "r", "Requirement", "Outcome", "Scope", "Accept")
    tx.set_visibility(owner, req["id"], "private")
    tx.share_doc(owner, req["id"], actor, "write")
    yield tx, owner, actor, req
    tx.db.close()


def snapshot(tx):
    return "\n".join(tx.db.iterdump())


@pytest.mark.parametrize("depth", [1, 3])
@pytest.mark.parametrize("tool", ["issue.create", "issue.transition"])
@pytest.mark.parametrize("replay", [False, True])
def test_ancestor_acl_revocation_blocks_fresh_and_replayed_writes(state, depth, tool, replay):
    tx, owner, actor, req = state
    parent = tx.create_issue(owner, "private-root", requirement_id=req["id"])
    for i in range(depth):
        parent = tx.create_issue(actor, f"descendant-{i}", parent_id=parent["id"])
    payload = (
        {"title": "protected-child", "parent_id": parent["id"]}
        if tool == "issue.create"
        else {"issue_id": parent["id"], "to_status": "planned"}
    )
    if replay:
        tx.dispatch_tool(actor, tool, payload, call_id="review")
    tx.unshare_doc(owner, req["id"], actor)
    before = snapshot(tx)
    with pytest.raises(PermissionDenied):
        tx.dispatch_tool(actor, tool, payload, call_id="review")
    assert snapshot(tx) == before


@pytest.mark.parametrize("operation", ["create_issue", "transition_issue", "add_issue_comment", "sync_progress"])
def test_manual_mutation_rechecks_current_requirement_acl(state, operation):
    tx, owner, actor, req = state
    issue = tx.create_issue(owner, "linked", requirement_id=req["id"])
    tx.unshare_doc(owner, req["id"], actor)
    calls = {
        "create_issue": lambda: tx.create_issue(actor, "manual", requirement_id=req["id"]),
        "transition_issue": lambda: tx.transition_issue(actor, issue["id"], "planned"),
        "add_issue_comment": lambda: tx.add_issue_comment(actor, issue["id"], "comment"),
        "sync_progress": lambda: tx.sync_progress(req["id"], actor=actor),
    }
    before = snapshot(tx)
    with pytest.raises(PermissionDenied):
        calls[operation]()
    assert snapshot(tx) == before


def test_read_only_ancestor_share_keeps_comment_reads(state):
    tx, owner, actor, req = state
    parent = tx.create_issue(owner, "root", requirement_id=req["id"])
    child = tx.create_issue(owner, "child", parent_id=parent["id"])
    comment = tx.add_issue_comment(owner, child["id"], "visible")
    tx.share_doc(owner, req["id"], actor, "read")
    assert tx.list_issue_comments(actor, child["id"]) == [comment]
    before = snapshot(tx)
    with pytest.raises(PermissionDenied):
        tx.add_issue_comment(actor, child["id"], "cannot write")
    assert snapshot(tx) == before
    tx.unshare_doc(owner, req["id"], actor)
    with pytest.raises(PermissionDenied):
        tx.list_issue_comments(actor, child["id"])
