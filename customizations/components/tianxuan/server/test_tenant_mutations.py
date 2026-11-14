"""Every rejected mutation leaves the complete SQLite database unchanged."""

from __future__ import annotations

import pytest
from tianxuan_core import NotFound, PermissionDenied, Tianxuan, TianxuanError


@pytest.fixture()
def scenario():
    tx = Tianxuan()
    a = tx.register("Tenant A", "a@example.invalid", "fixture")
    b = tx.register("Tenant B", "b@example.invalid", "fixture")
    members = {}
    for label, owner in (("a", a), ("b", b)):
        for role in ("editor", "viewer"):
            members[f"{label}_{role}"] = tx.add_member(
                owner["user_id"], f"{label}-{role}@example.invalid", "fixture", role=role
            )["user_id"]
    doc = tx.create_doc(a["user_id"], "Document", "original")
    req = tx.create_requirement(a["user_id"], "req-a", "Requirement", "goal", "scope", "accept")
    issue = tx.create_issue(a["user_id"], "Issue", requirement_id=req["id"])
    comment = tx.add_comment(a["user_id"], doc["id"], "original")
    yield tx, a, b, members, doc, req, issue, comment
    tx.db.close()


def unchanged(tx, call, error=NotFound):
    before = list(tx.db.iterdump())
    with pytest.raises(error):
        call()
    assert list(tx.db.iterdump()) == before
    assert not tx.db.in_transaction


def operations(s, actor):
    tx, a, _, members, doc, req, issue, comment = s
    return {
        "update_doc": lambda: tx.update_doc(actor, doc["id"], "changed", 1),
        "set_visibility": lambda: tx.set_visibility(actor, doc["id"], "private"),
        "share_doc": lambda: tx.share_doc(actor, doc["id"], members["a_viewer"], "write"),
        "unshare_doc": lambda: tx.unshare_doc(actor, doc["id"], members["a_viewer"]),
        "add_comment": lambda: tx.add_comment(actor, doc["id"], "changed"),
        "resolve_comment": lambda: tx.resolve_comment(actor, comment["id"]),
        "create_issue_requirement": lambda: tx.create_issue(actor, "child", requirement_id=req["id"]),
        "create_issue_parent": lambda: tx.create_issue(actor, "child", parent_id=issue["id"]),
        "plan_tickets": lambda: tx.plan_tickets(actor, req["id"], [{"title": "child"}]),
        "transition_issue": lambda: tx.transition_issue(actor, issue["id"], "in-progress"),
        "add_issue_comment": lambda: tx.add_issue_comment(actor, issue["id"], "changed"),
        "sync_progress": lambda: tx.sync_progress(req["id"], actor=actor),
        "create_doc_space": lambda: tx.create_doc(actor, "new", space_id=a["space_id"]),
        "set_role": lambda: tx.set_role(actor, members["a_viewer"], "editor"),
    }


MUTATIONS = (
    "update_doc set_visibility share_doc unshare_doc add_comment resolve_comment "
    "create_issue_requirement create_issue_parent plan_tickets transition_issue "
    "add_issue_comment sync_progress create_doc_space set_role"
).split()


@pytest.mark.parametrize("name", MUTATIONS)
@pytest.mark.parametrize("identity", ["foreign_admin", "foreign_editor", "foreign_viewer", "missing"])
def test_mutator_actor_tenant_boundary(scenario, name, identity):
    tx, _, b, members, *_ = scenario
    actor = {
        "foreign_admin": b["user_id"],
        "foreign_editor": members["b_editor"],
        "foreign_viewer": members["b_viewer"],
        "missing": "missing",
    }[identity]
    # Existing role denial can precede the scope check; both retain their HTTP mappings.
    unchanged(tx, operations(scenario, actor)[name], (NotFound, PermissionDenied))


@pytest.mark.parametrize("name", MUTATIONS)
def test_mutator_same_tenant_admin(scenario, name):
    operations(scenario, scenario[1]["user_id"])[name]()


@pytest.mark.parametrize(
    "name", ["create_doc", "create_requirement", "create_issue", "add_member", "create_invite", "issue_session"]
)
def test_creation_rejects_missing_identity(scenario, name):
    tx = scenario[0]
    calls = {
        "create_doc": lambda: tx.create_doc("missing", "title"),
        "create_requirement": lambda: tx.create_requirement("missing", "id", "title", "goal", "scope", "accept"),
        "create_issue": lambda: tx.create_issue("missing", "title"),
        "add_member": lambda: tx.add_member("missing", "new@example.invalid", "fixture"),
        "create_invite": lambda: tx.create_invite("missing", "new@example.invalid"),
        "issue_session": lambda: tx.issue_session("missing"),
    }
    unchanged(tx, calls[name])


@pytest.mark.parametrize(
    "reference", ["space", "requirement", "parent", "comment_parent", "share_user", "unshare_user"]
)
@pytest.mark.parametrize("missing", [False, True])
def test_invalid_related_reference(scenario, reference, missing):
    tx, a, b, _, doc, req, issue, _ = scenario
    foreign_doc = tx.create_requirement(b["user_id"], "req-b", "B", "goal", "scope", "accept")
    foreign_issue = tx.create_issue(b["user_id"], "B", requirement_id=foreign_doc["id"])
    foreign_comment = tx.add_comment(b["user_id"], foreign_doc["id"], "B")
    ids = {
        "space": b["space_id"],
        "requirement": foreign_doc["id"],
        "parent": foreign_issue["id"],
        "comment_parent": foreign_comment["id"],
        "share_user": b["user_id"],
        "unshare_user": b["user_id"],
    }
    target = "missing" if missing else ids[reference]
    actor = a["user_id"]
    calls = {
        "space": lambda: tx.create_doc(actor, "title", space_id=target),
        "requirement": lambda: tx.create_issue(actor, "title", requirement_id=target, parent_id=issue["id"]),
        "parent": lambda: tx.create_issue(actor, "title", requirement_id=req["id"], parent_id=target),
        "comment_parent": lambda: tx.add_comment(actor, doc["id"], "body", parent_id=target),
        "share_user": lambda: tx.share_doc(actor, doc["id"], target),
        "unshare_user": lambda: tx.unshare_doc(actor, doc["id"], target),
    }
    unchanged(tx, calls[reference])


@pytest.mark.parametrize("bad_ref", ["requirement", "parent", "space"])
@pytest.mark.parametrize("name", ["transition_issue", "add_issue_comment", "create_issue_parent"])
def test_legacy_mixed_references_rejected_before_writes(scenario, bad_ref, name):
    tx, a, b, _, _, req, issue, _ = scenario
    if bad_ref == "requirement":
        target = tx.create_requirement(b["user_id"], "req-b", "B", "goal", "scope", "accept")["id"]
        tx.db.execute("UPDATE issues SET requirement_id = ? WHERE id = ?", (target, issue["id"]))
    elif bad_ref == "parent":
        target = tx.create_issue(b["user_id"], "B")["id"]
        tx.db.execute("UPDATE issues SET parent_id = ? WHERE id = ?", (target, issue["id"]))
    else:
        tx.db.execute("UPDATE docs SET space_id = ? WHERE id = ?", (b["space_id"], req["id"]))
    tx.db.commit()
    unchanged(tx, operations(scenario, a["user_id"])[name])


def test_non_requirement_and_wrong_comment_parent(scenario):
    tx, a, _, _, doc, req, _, _ = scenario
    actor = a["user_id"]
    unchanged(tx, lambda: tx.create_issue(actor, "title", requirement_id=doc["id"]), TianxuanError)
    parent = tx.add_comment(actor, req["id"], "parent")
    unchanged(tx, lambda: tx.add_comment(actor, doc["id"], "reply", parent_id=parent["id"]), TianxuanError)
    unchanged(tx, lambda: tx.sync_progress(req["id"]), TypeError)


def test_same_tenant_sharing_and_private_comments(scenario):
    tx, a, _, members, doc, _, _, _ = scenario
    owner, editor, viewer = a["user_id"], members["a_editor"], members["a_viewer"]
    tx.set_visibility(owner, doc["id"], "private")
    unchanged(tx, lambda: tx.update_doc(editor, doc["id"], "changed", 1), PermissionDenied)
    unchanged(tx, lambda: tx.add_comment(editor, doc["id"], "comment"), PermissionDenied)
    tx.share_doc(owner, doc["id"], editor, "read")
    comment = tx.add_comment(editor, doc["id"], "comment")
    unchanged(tx, lambda: tx.resolve_comment(editor, comment["id"]), PermissionDenied)
    tx.share_doc(owner, doc["id"], editor, "write")
    tx.update_doc(editor, doc["id"], "changed", 1)
    tx.resolve_comment(editor, comment["id"])
    tx.share_doc(owner, doc["id"], viewer, "write")
    unchanged(tx, lambda: tx.update_doc(viewer, doc["id"], "changed", 2), PermissionDenied)


def test_bootstrap_token_exceptions_and_actor_sessions(scenario):
    tx, a, *_ = scenario
    invite = tx.create_invite(a["user_id"], "invited@example.invalid")
    invited = tx.accept_invite(invite["code"], "fixture")
    assert invited["tenant_id"] == a["tenant_id"]
    token = tx.issue_session(invited["user_id"])
    assert tx.user_for_token(token) == invited["user_id"]
    assert tx.revoke_session(token)
    assert tx.user_for_token(token) is None
    unchanged(tx, lambda: tx.accept_invite("missing", "fixture"), TianxuanError)


@pytest.mark.parametrize("tool", ["doc.update", "requirement.plan", "issue.create", "issue.transition"])
def test_mutating_dispatch_preserves_scope(scenario, tool):
    tx, _, b, _, doc, req, issue, _ = scenario
    payload = {
        "doc.update": {"doc_id": doc["id"], "body_md": "changed", "expected_version": 1},
        "requirement.plan": {"requirement_id": req["id"], "tickets": [{"title": "child"}]},
        "issue.create": {"title": "child", "requirement_id": req["id"]},
        "issue.transition": {"issue_id": issue["id"], "to_status": "in-progress"},
    }[tool]
    unchanged(tx, lambda: tx.dispatch_tool(b["user_id"], tool, payload))


def test_parent_cycle_rejected_without_partial_child(scenario):
    tx, a, _, _, _, _, issue, _ = scenario
    tx.db.execute("UPDATE issues SET parent_id = ? WHERE id = ?", (issue["id"], issue["id"]))
    tx.db.commit()
    unchanged(tx, lambda: tx.create_issue(a["user_id"], "child", parent_id=issue["id"]), TianxuanError)


@pytest.mark.parametrize(
    "name", ["update_doc", "set_visibility", "share_doc", "unshare_doc", "add_comment", "resolve_comment"]
)
def test_legacy_document_space_rejected(scenario, name):
    tx, a, b, _, doc, *_ = scenario
    tx.db.execute("UPDATE docs SET space_id = ? WHERE id = ?", (b["space_id"], doc["id"]))
    tx.db.commit()
    unchanged(tx, operations(scenario, a["user_id"])[name])
