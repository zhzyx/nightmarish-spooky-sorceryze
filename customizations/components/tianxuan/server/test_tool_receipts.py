"""Persistent tool replay, isolation, transaction and HTTP contract regressions."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
import tianxuan_core as core
from api import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def scenario(tmp_path):
    tx = core.Tianxuan(str(tmp_path / "store.db"))
    account = tx.register("local", "owner@example.invalid", "secret")
    actor = account["user_id"]
    yield tx, actor, tmp_path
    tx.db.close()


def requirement(tx, actor, request_id="receipt-req", **kwargs):
    return tx.create_requirement(actor, request_id, "Title", "Outcome", "Scope", "Acceptance", **kwargs)


def counts(tx):
    return {
        table: tx.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("docs", "doc_versions", "issues", "events", "tool_receipts")
    }


def test_original_replay_does_not_append_event(scenario):
    tx, actor, _ = scenario
    req = requirement(tx, actor)
    first = tx.plan_tickets(actor, req["id"], [{"title": "same"}])
    events = tx.events(actor)
    assert tx.plan_tickets(actor, req["id"], [{"title": "same"}]) == first
    assert tx.events(actor) == events


def test_original_same_title_different_acceptance_is_not_swallowed(scenario):
    tx, actor, _ = scenario
    req = requirement(tx, actor)
    tx.plan_tickets(actor, req["id"], [{"title": "same", "acceptance": "before"}])
    result = tx.plan_tickets(actor, req["id"], [{"title": "same", "acceptance": "after"}])
    assert result[1]["acceptance"] == "after"
    assert len(tx.list_issues(actor, req["id"])) == 3


def test_original_request_id_is_tenant_local(scenario):
    tx, actor, _ = scenario
    other = tx.register("other", "other@example.invalid", "secret")["user_id"]
    first = requirement(tx, actor)
    second = requirement(tx, other)
    assert first["id"] != second["id"]
    assert first["tenant_id"] != second["tenant_id"]


def payloads(tx, actor):
    doc = tx.create_doc(actor, "document")
    req = requirement(tx, actor)
    issue = tx.create_issue(actor, "task")
    return {
        "doc.create": {"title": "created", "body_md": "body"},
        "doc.update": {"doc_id": doc["id"], "body_md": "changed", "expected_version": 1},
        "requirement.create": {
            "request_id": "new",
            "title": "new",
            "outcome": "out",
            "scope": "scope",
            "acceptance": "ok",
        },
        "requirement.plan": {"requirement_id": req["id"], "tickets": [{"title": "child"}]},
        "issue.create": {"title": "new issue"},
        "issue.transition": {"issue_id": issue["id"], "to_status": "planned"},
    }


@pytest.mark.parametrize(
    "tool", ["doc.create", "doc.update", "requirement.create", "requirement.plan", "issue.create", "issue.transition"]
)
@pytest.mark.parametrize("explicit", [False, True])
def test_every_write_tool_replays_original_result_without_writes(scenario, tool, explicit):
    tx, actor, _ = scenario
    payload = payloads(tx, actor)[tool]
    kwargs = {"call_id": "same"} if explicit else {}
    first = tx.dispatch_tool(actor, tool, payload, **kwargs)
    before = counts(tx)
    # Reordering dictionary fields must not change canonical identity.
    replay = tx.dispatch_tool(actor, tool, dict(reversed(list(payload.items()))), **kwargs)
    assert replay == first
    assert counts(tx) == before
    if tool == "doc.create":
        tx.update_doc(actor, first["id"], "later", 1)
        assert tx.dispatch_tool(actor, tool, payload, **kwargs) == first


@pytest.mark.parametrize(
    "tool", ["doc.create", "doc.update", "requirement.create", "requirement.plan", "issue.create", "issue.transition"]
)
def test_every_write_tool_rejects_different_payload_same_key(scenario, tool):
    tx, actor, _ = scenario
    payload = payloads(tx, actor)[tool]
    tx.dispatch_tool(actor, tool, payload, call_id="key")
    changed = dict(payload)
    field = (
        "body_md"
        if tool == "doc.update"
        else "to_status"
        if tool == "issue.transition"
        else "tickets"
        if tool == "requirement.plan"
        else "title"
    )
    changed[field] = [{"title": "child", "acceptance": "different"}] if field == "tickets" else "different"
    before = counts(tx)
    with pytest.raises(core.VersionConflict, match="call_id already used with different payload"):
        tx.dispatch_tool(actor, tool, changed, call_id="key")
    assert counts(tx) == before


def test_default_arguments_and_api_tool_shapes_share_identity(scenario):
    tx, actor, _ = scenario
    req = requirement(tx, actor)
    first = tx.dispatch_tool(
        actor, "requirement.plan", {"requirement_id": req["id"], "tickets": [{"title": "x"}]}, call_id="plan"
    )
    before = counts(tx)
    with TestClient(create_app(tx)) as client:
        response = client.post(
            f"/api/v1/requirements/{req['id']}/tickets",
            headers={"X-Actor": actor},
            json={
                "call_id": "plan",
                "tickets": [{"title": "x", "acceptance": "", "priority": "normal", "type": "task", "body_md": ""}],
            },
        )
    assert response.status_code == 200, response.text
    assert response.json() == first
    assert counts(tx) == before


def test_explicit_plan_keys_preserve_intentional_duplicate_tickets(scenario):
    tx, actor, _ = scenario
    req = requirement(tx, actor)
    tickets = [{"title": "duplicate"}, {"title": "duplicate"}]
    first = tx.plan_tickets(actor, req["id"], tickets, call_id="first")
    second = tx.plan_tickets(actor, req["id"], tickets, call_id="second")
    assert first[1]["id"] != first[2]["id"]
    assert {x["id"] for x in first[1:]}.isdisjoint({x["id"] for x in second[1:]})
    assert len(tx.list_issues(actor, req["id"])) == 5


def test_legacy_incremental_plan_preserves_full_specs_and_multiplicity(scenario):
    tx, actor, _ = scenario
    req = requirement(tx, actor)
    first = tx.plan_tickets(actor, req["id"], [{"title": "a"}, {"title": "a"}])
    extended = tx.plan_tickets(actor, req["id"], [{"title": "a"}, {"title": "a"}, {"title": "b", "body_md": "details"}])
    assert [x["id"] for x in first[1:]] == [x["id"] for x in extended[1:3]]
    assert extended[-1]["body_md"] == "details"
    assert len(tx.list_issues(actor, req["id"])) == 4


def test_tenant_actor_tool_and_explicit_legacy_namespaces_are_separate(scenario):
    tx, actor, _ = scenario
    teammate = tx.add_member(actor, "member@example.invalid", "secret", role="editor")["user_id"]
    other = tx.register("other", "other@example.invalid", "secret")["user_id"]
    docs = [tx.dispatch_tool(who, "doc.create", {"title": "same"}, call_id="scope") for who in (actor, teammate, other)]
    issue = tx.dispatch_tool(actor, "issue.create", {"title": "same"}, call_id="scope")
    assert len({row["id"] for row in [*docs, issue]}) == 4
    legacy = tx.dispatch_tool(actor, "doc.create", {"title": "legacy"})
    key = tx.db.execute("SELECT call_id FROM tool_receipts WHERE key_kind = 'legacy-v1'").fetchone()[0]
    explicit = tx.dispatch_tool(actor, "doc.create", {"title": "legacy"}, call_id=key)
    assert explicit["id"] != legacy["id"]


@pytest.mark.parametrize("changed", [False, True])
def test_same_key_across_independent_connections(scenario, changed):
    tx, actor, directory = scenario
    other = core.Tianxuan(str(directory / "store.db"))
    barrier = threading.Barrier(2)
    results, failures = [], []

    def run(store, title):
        try:
            barrier.wait(timeout=5)
            results.append(store.dispatch_tool(actor, "doc.create", {"title": title}, call_id="concurrent"))
        except BaseException as error:
            failures.append(error)

    workers = [
        threading.Thread(target=run, args=(store, title))
        for store, title in ((tx, "a"), (other, "b" if changed else "a"))
    ]
    try:
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=10)
        assert not any(worker.is_alive() for worker in workers)
        if changed:
            assert len(results) == len(failures) == 1
            assert isinstance(failures[0], core.VersionConflict)
        else:
            assert not failures
            assert results[0] == results[1]
        assert counts(tx)["docs"] == 1
        assert counts(tx)["tool_receipts"] == 1
        assert len([e for e in tx.events(actor) if e["type"] == "doc.created"]) == 1
    finally:
        other.db.close()


def test_receipt_survives_real_process_restart(scenario):
    tx, actor, directory = scenario
    first = tx.dispatch_tool(actor, "doc.create", {"title": "persist"}, call_id="restart")
    script = "from tianxuan_core import Tianxuan; import json,sys; t=Tianxuan(sys.argv[1]); print(json.dumps(t.dispatch_tool(sys.argv[2], 'doc.create', {'title':'persist'}, call_id='restart'))); t.db.close()"
    env = dict(os.environ, PYTHONPATH=str(Path(core.__file__).parent), PYTHONDONTWRITEBYTECODE="1")
    output = subprocess.run(
        [sys.executable, "-c", script, str(directory / "store.db"), actor],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=20,
    )
    assert json.loads(output.stdout) == first
    assert counts(tx)["docs"] == 1


@pytest.mark.parametrize("failure", ["child", "event", "receipt"])
def test_tree_events_and_receipt_rollback_atomically(scenario, failure):
    tx, actor, _ = scenario
    req = requirement(tx, actor)
    before = counts(tx)
    if failure == "child":
        sql = "CREATE TEMP TRIGGER fail BEFORE INSERT ON issues WHEN NEW.title = 'second' BEGIN SELECT RAISE(ABORT, 'sensitive child failure'); END"
    elif failure == "event":
        sql = "CREATE TEMP TRIGGER fail BEFORE INSERT ON events WHEN NEW.type = 'requirement.planned' BEGIN SELECT RAISE(ABORT, 'sensitive event failure'); END"
    else:
        sql = "CREATE TEMP TRIGGER fail BEFORE INSERT ON tool_receipts WHEN NEW.tool = 'requirement.plan' BEGIN SELECT RAISE(ABORT, 'sensitive receipt failure'); END"
    tx.db.execute(sql)
    with pytest.raises(core.StorageError, match="^storage operation failed$") as caught:
        tx.plan_tickets(actor, req["id"], [{"title": "first"}, {"title": "second"}], call_id="fail")
    assert isinstance(caught.value.__cause__, sqlite3.IntegrityError)
    assert not isinstance(caught.value, core.VersionConflict)
    assert counts(tx) == before
    assert tx.get_doc(req["id"])["progress"] == {}
    tx.db.execute("DROP TRIGGER fail")
    assert len(tx.plan_tickets(actor, req["id"], [{"title": "first"}, {"title": "second"}], call_id="fail")) == 3


def test_requirement_receipt_failure_rolls_back_document_version_and_event(scenario):
    tx, actor, _ = scenario
    before = counts(tx)
    tx.db.execute(
        "CREATE TEMP TRIGGER fail BEFORE INSERT ON tool_receipts BEGIN SELECT RAISE(ABORT, 'receipt failure'); END"
    )
    with pytest.raises(core.StorageError):
        requirement(tx, actor, call_id="create")
    assert counts(tx) == before


def test_failed_nested_call_preserves_outer_write_and_leaves_no_partial_tree(scenario):
    tx, actor, _ = scenario
    req = requirement(tx, actor)

    @core._connection_call
    def outer(store):
        doc = store.create_doc(actor, "outer")
        store.db.execute(
            "CREATE TEMP TRIGGER fail BEFORE INSERT ON issues WHEN NEW.title = 'bad' BEGIN SELECT RAISE(ABORT, 'bad'); END"
        )
        with pytest.raises(core.StorageError):
            store.plan_tickets(actor, req["id"], [{"title": "good"}, {"title": "bad"}], call_id="nested")
        return doc

    doc = outer(tx)
    assert tx.get_doc(doc["id"])["title"] == "outer"
    assert not tx.list_issues(actor)
    assert tx.db.execute("SELECT COUNT(*) FROM tool_receipts WHERE call_id='nested'").fetchone()[0] == 0


def test_caller_owned_transaction_is_not_committed_or_rolled_back(scenario):
    tx, actor, directory = scenario
    tx.db.execute("BEGIN")
    tx.db.execute("UPDATE users SET name='pending' WHERE id=?", (actor,))
    tx.dispatch_tool(actor, "doc.create", {"title": "pending"}, call_id="outer")
    with pytest.raises(core.VersionConflict):
        tx.dispatch_tool(actor, "doc.create", {"title": "different"}, call_id="outer")
    assert tx.db.in_transaction
    assert tx.db.execute("SELECT name FROM users WHERE id=?", (actor,)).fetchone()[0] == "pending"
    observer = sqlite3.connect(str(directory / "store.db"))
    try:
        assert observer.execute("SELECT COUNT(*) FROM docs").fetchone()[0] == 0
    finally:
        observer.close()
    tx.db.rollback()
    assert counts(tx)["docs"] == counts(tx)["tool_receipts"] == 0


def test_acl_and_role_revocation_are_checked_before_replay(scenario):
    tx, owner, _ = scenario
    actor = tx.add_member(owner, "member@example.invalid", "secret", role="editor")["user_id"]
    doc = tx.create_doc(owner, "shared")
    tx.set_visibility(owner, doc["id"], "private")
    tx.share_doc(owner, doc["id"], actor, "write")
    payload = {"doc_id": doc["id"], "body_md": "secret", "expected_version": 1}
    tx.dispatch_tool(actor, "doc.update", payload, call_id="edit")
    tx.unshare_doc(owner, doc["id"], actor)
    with pytest.raises(core.PermissionDenied):
        tx.dispatch_tool(actor, "doc.update", payload, call_id="edit")
    tx.dispatch_tool(actor, "doc.create", {"title": "own"}, call_id="create")
    tx.set_role(owner, actor, "viewer")
    with pytest.raises(core.PermissionDenied):
        tx.dispatch_tool(actor, "doc.create", {"title": "own"}, call_id="create")


def test_replayed_result_current_scope_is_checked(scenario):
    tx, actor, _ = scenario
    doc = tx.dispatch_tool(actor, "doc.create", {"title": "scope"}, call_id="scope")
    other = tx.register("other", "other@example.invalid", "secret")
    tx.db.execute("UPDATE docs SET space_id=? WHERE id=?", (other["space_id"], doc["id"]))
    tx.db.commit()
    with pytest.raises(core.NotFound):
        tx.dispatch_tool(actor, "doc.create", {"title": "scope"}, call_id="scope")


def test_http_conflicts_storage_errors_and_invalid_keys(scenario):
    tx, actor, _ = scenario
    with TestClient(create_app(tx)) as client:
        headers = {"X-Actor": actor}
        payload = {"title": "first", "call_id": "http"}
        first = client.post("/api/v1/docs", headers=headers, json=payload)
        assert first.status_code == 200
        assert client.post("/api/v1/docs", headers=headers, json=payload).json() == first.json()
        conflict = client.post("/api/v1/docs", headers=headers, json=payload | {"title": "other"})
        assert conflict.status_code == 409
        assert conflict.json() == {"detail": "call_id already used with different payload"}
        assert client.post("/api/v1/docs", headers=headers, json=payload | {"call_id": ""}).status_code == 422
        tx.db.execute(
            "CREATE TEMP TRIGGER fail BEFORE INSERT ON docs BEGIN SELECT RAISE(ABORT, 'secret database details'); END"
        )
        failure = client.post("/api/v1/docs", headers=headers, json={"title": "fail", "call_id": "fail"})
        assert failure.status_code == 500
        assert failure.json() == {"detail": "storage operation failed"}


def test_lock_timeout_is_stable_and_retryable(scenario):
    tx, actor, directory = scenario
    other = core.Tianxuan(str(directory / "store.db"))
    try:
        tx.db.execute("BEGIN IMMEDIATE")
        other.db.execute("PRAGMA busy_timeout=1")
        with TestClient(create_app(other)) as client:
            response = client.post(
                "/api/v1/docs", headers={"X-Actor": actor}, json={"title": "locked", "call_id": "locked"}
            )
        assert response.status_code == 503
        assert response.headers["retry-after"] == "1"
        tx.db.rollback()
        assert other.create_doc(actor, "locked", call_id="locked")["title"] == "locked"
    finally:
        tx.db.rollback()
        other.db.close()


@pytest.mark.parametrize("key", ["", " ", 123, "a" * 257])
def test_explicit_invalid_key_never_silently_falls_back(scenario, key):
    tx, actor, _ = scenario
    before = counts(tx)
    with pytest.raises(core.TianxuanError):
        tx.dispatch_tool(actor, "doc.create", {"title": "invalid"}, call_id=key)
    assert counts(tx) == before


def test_unknown_payload_fields_are_not_silently_ignored(scenario):
    tx, actor, _ = scenario
    with pytest.raises(core.TianxuanError):
        tx.dispatch_tool(actor, "doc.create", {"title": "x", "unexpected": True}, call_id="x")
    req = requirement(tx, actor)
    with pytest.raises(core.TianxuanError):
        tx.plan_tickets(actor, req["id"], [{"title": "x", "unexpected": True}], call_id="x")


def test_ordinary_manual_creation_keeps_duplicate_intent(scenario):
    tx, actor, _ = scenario
    first = tx.create_doc(actor, "same", "same")
    second = tx.create_doc(actor, "same", "same")
    assert first["id"] != second["id"]
    assert tx.create_issue(actor, "same")["id"] != tx.create_issue(actor, "same")["id"]
    with TestClient(create_app(tx)) as client:
        headers = {"X-Actor": actor}
        first = client.post("/api/v1/docs", headers=headers, json={"title": "same"})
        second = client.post("/api/v1/docs", headers=headers, json={"title": "same"})
        assert first.json()["id"] != second.json()["id"]


def test_pre_receipt_database_migrates_without_rebuilding_business_rows(scenario):
    tx, actor, directory = scenario
    req = requirement(tx, actor)
    first = tx.plan_tickets(actor, req["id"], [{"title": "old"}])
    events = tx.events(actor)
    # Shape of the previous schema: no receipt table, existing complete tree.
    tx.db.execute("DROP TABLE tool_receipts")
    tx.db.commit()
    reopened = core.Tianxuan(str(directory / "store.db"))
    try:
        assert reopened.plan_tickets(actor, req["id"], [{"title": "old"}]) == first
        assert reopened.events(actor) == events
        assert reopened.db.execute("SELECT COUNT(*) FROM tool_receipts").fetchone()[0] == 1
        assert len(reopened.list_issues(actor, req["id"])) == 2
    finally:
        reopened.db.close()


def test_composite_requirement_and_tree_failure_rolls_back_both_receipts(scenario):
    tx, actor, _ = scenario
    before = counts(tx)
    tx.db.execute(
        "CREATE TEMP TRIGGER fail BEFORE INSERT ON issues WHEN NEW.title = 'bad' BEGIN SELECT RAISE(ABORT, 'bad'); END"
    )

    @core._connection_call
    def create_and_plan(store):
        req = requirement(store, actor, call_id="requirement")
        store.plan_tickets(actor, req["id"], [{"title": "good"}, {"title": "bad"}], call_id="plan")

    with pytest.raises(core.StorageError):
        create_and_plan(tx)
    assert counts(tx) == before


def test_known_request_unique_constraint_is_conflict_not_generic_storage_failure(scenario):
    tx, actor, _ = scenario
    tx.create_doc(actor, "original", request_id="unique")
    before = counts(tx)
    with TestClient(create_app(tx)) as client:
        response = client.post(
            "/api/v1/docs",
            headers={"X-Actor": actor},
            json={"title": "other", "request_id": "unique", "call_id": "other"},
        )
    assert response.status_code == 409
    assert response.json() == {"detail": "request_id already exists in this tenant"}
    assert counts(tx) == before


def test_http_does_not_drop_unknown_fields_or_unsupported_ticket_fields(scenario):
    tx, actor, _ = scenario
    req = requirement(tx, actor)
    with TestClient(create_app(tx)) as client:
        headers = {"X-Actor": actor}
        assert (
            client.post("/api/v1/docs", headers=headers, json={"title": "x", "call_id": "x", "unknown": 1}).status_code
            == 422
        )
        assert (
            client.post(
                f"/api/v1/requirements/{req['id']}/tickets",
                headers=headers,
                json={"call_id": "x", "tickets": [{"title": "x", "unknown": 1}]},
            ).status_code
            == 422
        )


def test_conflicting_key_does_not_depend_on_new_target_existence(scenario):
    tx, actor, _ = scenario
    doc = tx.create_doc(actor, "doc")
    payload = {"doc_id": doc["id"], "body_md": "change", "expected_version": 1}
    tx.dispatch_tool(actor, "doc.update", payload, call_id="update")
    with pytest.raises(core.VersionConflict, match="call_id already used with different payload"):
        tx.dispatch_tool(actor, "doc.update", payload | {"doc_id": "missing"}, call_id="update")


def test_nested_explicit_keys_are_not_downgraded(scenario):
    tx, actor, _ = scenario
    original = tx._event
    nested = False

    def event(*args):
        nonlocal nested
        original(*args)
        if args[1] == "doc.created" and not nested:
            nested = True
            tx.create_issue(actor, "inside", call_id="inside")

    with patch.object(tx, "_event", event):
        tx.create_doc(actor, "outside", call_id="outside")
    with pytest.raises(core.VersionConflict):
        tx.create_issue(actor, "changed", call_id="inside")
    assert tx.db.execute("SELECT COUNT(*) FROM tool_receipts").fetchone()[0] == 2


def test_cli_call_id_reaches_existing_http_interfaces():
    import httpx
    import tianxuan_cli as cli

    seen = []

    def respond(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "test"})

    with httpx.Client(transport=httpx.MockTransport(respond), base_url="http://fixture/") as client:
        cli.create_doc(client, "doc", "body", "doc", call_id="cli-doc")
        cli.create_requirement(client, "req", "title", "out", "scope", "ok", call_id="cli-req")
    assert [entry["call_id"] for entry in seen] == ["cli-doc", "cli-req"]
    parsed = cli.build_parser().parse_args(["docs", "create", "--title", "x", "--call-id", "retry"])
    assert parsed.call_id == "retry"


@pytest.mark.parametrize(
    "tool", ["doc.create", "doc.update", "requirement.create", "requirement.plan", "issue.create", "issue.transition"]
)
def test_role_revocation_rechecks_every_write_tool(scenario, tool):
    tx, owner, _ = scenario
    actor = tx.add_member(owner, "writer@example.invalid", "secret", role="editor")["user_id"]
    payload = payloads(tx, actor)[tool]
    tx.dispatch_tool(actor, tool, payload, call_id="permission")
    tx.set_role(owner, actor, "viewer")
    before = counts(tx)
    with pytest.raises(core.PermissionDenied):
        tx.dispatch_tool(actor, tool, payload, call_id="permission")
    assert counts(tx) == before


@pytest.mark.parametrize("changed", [False, True])
def test_full_tree_same_key_serializes_across_connections(scenario, changed):
    tx, actor, directory = scenario
    req = requirement(tx, actor)
    other = core.Tianxuan(str(directory / "store.db"))
    barrier = threading.Barrier(2)
    results, failures = [], []

    def run(store, acceptance):
        try:
            barrier.wait(timeout=5)
            results.append(
                store.plan_tickets(
                    actor, req["id"], [{"title": "a", "acceptance": acceptance}, {"title": "b"}], call_id="tree"
                )
            )
        except BaseException as error:
            failures.append(error)

    workers = [
        threading.Thread(target=run, args=(store, acceptance))
        for store, acceptance in ((tx, "same"), (other, "different" if changed else "same"))
    ]
    try:
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=10)
        assert not any(worker.is_alive() for worker in workers)
        if changed:
            assert len(results) == len(failures) == 1
            assert isinstance(failures[0], core.VersionConflict)
        else:
            assert not failures
            assert results[0] == results[1]
        assert len(tx.list_issues(actor, req["id"])) == 3
        assert tx.get_doc(req["id"])["progress"]["total"] == 3
        assert tx.db.execute("SELECT COUNT(*) FROM tool_receipts WHERE tool='requirement.plan'").fetchone()[0] == 1
        assert len([e for e in tx.events(actor) if e["type"] == "requirement.planned"]) == 1
    finally:
        other.db.close()


def test_shared_requirement_plan_replay_does_not_bypass_revoked_acl(scenario):
    tx, owner, _ = scenario
    actor = tx.add_member(owner, "writer@example.invalid", "secret", role="editor")["user_id"]
    req = requirement(tx, owner)
    tx.set_visibility(owner, req["id"], "private")
    tx.share_doc(owner, req["id"], actor, "write")
    tx.plan_tickets(actor, req["id"], [{"title": "private"}], call_id="private")
    tx.unshare_doc(owner, req["id"], actor)
    before = counts(tx)
    with pytest.raises(core.PermissionDenied):
        tx.plan_tickets(actor, req["id"], [{"title": "private"}], call_id="private")
    assert counts(tx) == before
