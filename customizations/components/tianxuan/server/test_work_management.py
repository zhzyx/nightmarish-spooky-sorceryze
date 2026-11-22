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
    # Reopen a pre-feature database with its existing ticket.
    store.db.execute("DROP TABLE issue_work_events")
    store.db.execute("DROP TABLE project_issue_fields")
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


def test_project_field_update_preserves_plan_and_large_legacy_integer(work):
    path, store, _, client, actor, issue = work
    headers = {"Authorization": "Bearer " + store.issue_session(actor)}
    definitions = "/api/v1/work/field-definitions"
    for project, key, label in [("workspace", "area", "区域"), ("other", "review", "审核人")]:
        reply = client.put(f"{definitions}/{key}", params={"project": project}, headers=headers, json={"label": label})
        assert reply.status_code == 200
        assert reply.json() == {"project": project, "fields": [{"key": key, "label": label}]}
    assert client.put(
        f"{definitions}/area", params={"project": "other"}, headers=headers, json={"label": "片场"}
    ).is_success
    assert client.get(definitions, params={"project": "workspace"}, headers=headers).json()["fields"] == [
        {"key": "area", "label": "区域"}
    ]
    foreign = store.register("Other tenant", "other@example.invalid", "password")["user_id"]
    assert (
        client.get(
            definitions,
            params={"project": "workspace"},
            headers={"Authorization": "Bearer " + store.issue_session(foreign)},
        ).json()["fields"]
        == []
    )
    reader = store.add_member(actor, "viewer@example.invalid", "password", role="viewer")["user_id"]
    assert (
        client.put(
            f"{definitions}/blocked",
            params={"project": "workspace"},
            headers={"Authorization": "Bearer " + store.issue_session(reader)},
            json={"label": "blocked"},
        ).status_code
        == 403
    )

    old = {"custom_fields": {"legacy": 2**60 + 1, "signed": False}, "milestone": "RC1", "estimated_minutes": 80}
    url = f"/api/v1/issues/{issue}/work/plan"
    assert client.post(url, headers=headers, json={"expected_version": 0, "call_id": "seed", "plan": old}).is_success
    edit = {"expected_version": 1, "call_id": "field", "field_update": {"key": "area", "value": "south"}}
    assert client.post(url, params={"project": "other"}, headers=headers, json=edit).status_code == 404
    assert (
        client.get(f"/api/v1/issues/{issue}/work/flow", params={"project": "other"}, headers=headers).status_code == 404
    )
    invalid = dict(edit, field_update={"key": "review", "value": "foreign"})
    assert client.post(url, headers=headers, json=invalid).is_client_error
    reply = client.post(url, headers=headers, json=edit)
    assert reply.status_code == 200, reply.text
    assert reply.json()["plan"]["custom_fields"] == old["custom_fields"] | {"area": "south"}
    assert client.post(url, headers=headers, json=edit).json() == reply.json()
    assert client.post(url, headers=headers, json=dict(edit, call_id="stale")).status_code == 409
    reopened = Tianxuan(str(path))
    try:
        plan = reopened.dispatch_tool(actor, "work.read", {"issue_id": issue})["plan"]
        assert plan == reply.json()["plan"]
        assert plan["milestone"] == "RC1" and plan["estimated_minutes"] == 80
    finally:
        reopened.db.close()


def test_plan_membership_empty_groups_partial_update_and_stale_move(work):
    _, store, _, client, actor, issue = work
    project = store.get_issue(issue)["project"]
    store.create_issue(actor, "Unscheduled", project=project)
    store.create_issue(actor, "Other project", project="elsewhere")
    url = f"/api/v1/issues/{issue}/work/plan"
    headers = {"Authorization": "Bearer " + store.issue_session(actor)}

    def read():
        return client.get(url, headers=headers, params={"project": project}).raise_for_status().json()

    assert read() == {
        "id": issue,
        "version": 0,
        "plan": {"iteration": "", "milestone": ""},
        "counts": {"iteration": 2, "milestone": 2},
    }
    assert client.get(url, headers=headers, params={"project": "elsewhere"}).status_code == 404
    first = dict(expected_version=0, plan={"iteration": "Sprint"}, call_id="move")
    assert client.post(url, headers=headers, json=first).status_code == 200
    assert read()["counts"] == {"iteration": 1, "milestone": 2}
    assert (
        client.post(url, headers=headers, json=dict(first, plan={"milestone": "stale"}, call_id="late")).status_code
        == 409
    )
    assert read()["plan"] == {"iteration": "Sprint", "milestone": ""}
    clear = dict(expected_version=1, plan={"iteration": ""}, call_id="clear")
    assert client.post(url, headers=headers, json=clear).status_code == 200
    assert read()["counts"] == {"iteration": 2, "milestone": 2}


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


def test_project_roadmap_returns_only_visible_issue_and_parent_identifiers(work):
    _, store, _, client, owner, _ = work
    project = "studio/game"
    reader = store.add_member(owner, "reader@example.invalid", "password", role="viewer")["user_id"]
    headers = {"Authorization": "Bearer " + store.issue_session(reader)}
    module = store.create_business_module(owner, project, "场景", call_id="scene")
    outside = store.create_issue(owner, "同标题", project="studio/other")
    parent = store.create_issue(owner, "同标题", project=project, parent_id=outside["id"], module_id=module["id"])
    child = store.create_issue(owner, "同标题", parent_id=parent["id"])
    private = store.create_requirement(owner, "private", "Private", "Goal", "Scope", "Acceptance")["id"]
    store.set_visibility(owner, private, "private")
    store.create_issue(owner, "不可见", project=project, requirement_id=private)
    response = client.get("/api/v1/work/roadmap", params={"project": project}, headers=headers)
    assert response.status_code == 200
    projection = response.json()
    assert projection["project"] == project
    assert module["id"] in {m["id"] for m in projection["modules"] if m["name"] == "场景"}
    rows = {row["id"]: row for row in projection["items"]}
    assert rows.keys() == {parent["id"], child["id"]}
    assert rows[parent["id"]]["parent_id"] is None
    assert rows[child["id"]]["parent_id"] == parent["id"]
    for issue in [parent, child]:
        row = rows[issue["id"]]
        assert (row["number"], row["module_id"]) == (issue["number"], module["id"])


def test_creative_judgments_bind_initiator_across_delegated_revisions(work):
    _, store, _, client, owner, issue = work
    delegate = store.add_member(owner, "delegate@example.invalid", "password", role="editor")["user_id"]
    headers = {actor: {"Authorization": "Bearer " + store.issue_session(actor)} for actor in (owner, delegate)}
    path = f"/api/v1/issues/{issue}/work"
    ref = dict(kind="concept", module="art", path="character.png")
    revision = None
    for number in range(2):
        change = dict(
            module="art", base=revision, reads=None, edits={"character.png": base64.b64encode(bytes([number])).decode()}
        )
        revision = (
            client
            .post(
                "/api/v1/native/batches",
                headers=headers[delegate],
                json=dict(request_key=f"art-{number}", changes=[change]),
            )
            .raise_for_status()
            .json()["revisions"]["art"]
        )
        payload = {**ref, "expected_version": number, "revision": revision, "call_id": f"submit-{number}"}
        result = client.post(path + "/submit_asset", headers=headers[delegate], json=payload).raise_for_status().json()
        assert client.post(path + "/submit_asset", headers=headers[delegate], json=payload).json() == result
    judgments = client.get(path, headers=headers[owner]).raise_for_status().json()["creative_judgments"]
    assert len(judgments) == 2 and judgments[0]["revision"] != judgments[1]["revision"]
    assert [item["submission_version"] for item in judgments] == [1, 2]
    for item in judgments:
        assert (item["initiator"], item["responsible"], item["actor"], item["decision"]) == (
            owner,
            owner,
            delegate,
            "pending",
        )
    approval = dict(**ref, revision=revision, decision="approved", expected_version=2, call_id="approve")
    assert client.post(path + "/decide", headers=headers[delegate], json=approval).status_code == 403
    result = client.post(path + "/decide", headers=headers[owner], json=approval).raise_for_status().json()
    assert [item["decision"] for item in result["creative_judgments"]] == ["pending", "approved"]


def test_legacy_pending_judgment_reads_original_issue_creator(work):
    _, store, _, client, owner, issue = work
    delegate = store.add_member(owner, "old-editor@example.invalid", "password", role="editor")["user_id"]
    # A pre-H01 submission did not write the judgment owner into its event.
    store.db.execute(
        "INSERT INTO issue_work_events VALUES(?,?,?,?,?,?)",
        (
            issue,
            1,
            "work.submit_asset",
            '{"kind":"concept","path":"old.png","module":"art","revision":"old","decision":"pending","digest":"original"}',
            delegate,
            1,
        ),
    )
    store.db.commit()
    state = (
        client
        .get(f"/api/v1/issues/{issue}/work", headers={"Authorization": "Bearer " + store.issue_session(owner)})
        .raise_for_status()
        .json()
    )
    assert "initiator" not in state["history"][0]
    (judgment,) = state["creative_judgments"]
    assert (judgment["submission_version"], judgment["initiator"], judgment["responsible"]) == (1, owner, owner)


def test_transfer_preserves_independent_judgments_and_rechecks_owner(work):
    _, store, native, client, owner, issue = work
    delegate = store.add_member(owner, "artist@example.invalid", "password", role="editor")["user_id"]
    reader = store.add_member(owner, "reader@example.invalid", "password", role="viewer")["user_id"]
    stranger = store.register("elsewhere", "other@example.invalid", "password")["user_id"]
    auth = {actor: {"Authorization": "Bearer " + store.issue_session(actor)} for actor in (owner, delegate, stranger)}
    version = native.submit(
        store._tenant_of(owner),
        owner,
        "concept",
        [dict(module="art", base=None, reads=None, edits={"scene.png": b"scene"})],
    )["revisions"]["art"]
    ref = dict(kind="concept", module="art", revision=version, path="scene.png")
    base = f"/api/v1/issues/{issue}/work"

    def post(actor, operation, key, expected, **extra):
        return client.post(
            base + "/" + operation,
            headers=auth[actor],
            json={**ref, "call_id": key, "expected_version": expected, **extra},
        )

    def mine(actor):
        return [
            row["submission_version"]
            for row in client.get("/api/v1/work/my-judgments", headers=auth[actor]).raise_for_status().json()["items"]
        ]

    for i in range(2):
        post(owner, "submit_asset", f"submit-{i}", i).raise_for_status()
    assert mine(owner) == [1, 2] and mine(delegate) == []
    for target in (reader, stranger):
        assert post(owner, "transfer", target, 2, submission_version=1, target=target).status_code in (403, 404)
    with pytest.raises(UnknownTool):
        store.dispatch_tool(owner, "work.transfer", dict(issue_id=issue))
    handoff = dict(submission_version=1, target=delegate, note="Check the previous silhouette")
    first = post(owner, "transfer", "transfer", 2, **handoff).raise_for_status().json()
    assert post(owner, "transfer", "transfer", 2, **handoff).json() == first
    assert mine(owner) == [2] and mine(delegate) == [1] and mine(stranger) == []
    decide = dict(submission_version=1, decision="approved")
    assert post(owner, "decide", "stale", 2, **decide).status_code == 409
    assert post(owner, "decide", "fresh", 3, **decide).status_code == 403
    post(owner, "decide", "current", 3, submission_version=2, decision="approved").raise_for_status()
    result = (
        post(delegate, "decide", "pinned", 4, **{**decide, "decision": "changes_requested"}).raise_for_status().json()
    )
    assert [item["decision"] for item in result["creative_judgments"]] == ["changes_requested", "approved"]
    assert result["assets"]["concept"]["submission_version"] == 2
    assert result["history"][2]["note"] == handoff["note"]
    assert client.get(base + "/approved-asset", headers=auth[owner], params=ref).content == b"scene"
    assert mine(owner) == mine(delegate) == []
