"""Cross-entry acceptance for ordinary dependencies and custom work stages (#1629)."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan, TianxuanError


@pytest.fixture
def fixture(tmp_path):
    path = tmp_path / "flow.db"
    store = Tianxuan(str(path))
    owner = store.register("studio", "owner@example.invalid", "secret")["user_id"]
    headers = {"Authorization": "Bearer " + store.issue_session(owner)}
    issue = store.create_issue(owner, "Sculpt")["id"]
    with TestClient(create_app(store), headers=headers) as client:
        yield path, store, owner, client, issue
    store.db.close()


def config():
    stages = [
        dict(id=state, progress=progress, human=human)
        for state, progress, human in [
            ("backlog", 0, False),
            ("sculpt", 40, False),
            ("in-review", 75, True),
            ("done", 100, False),
        ]
    ]
    edges = [
        {"from": src, "to": dst}
        for src, dst in [
            ("backlog", "sculpt"),
            ("sculpt", "backlog"),
            ("sculpt", "in-review"),
            ("in-review", "sculpt"),
            ("in-review", "done"),
        ]
    ]
    return dict(stages=stages, edges=edges)


def flow_url(issue):
    return f"/api/v1/issues/{issue}/work/flow"


def post(client, issue, action, version, **payload):
    return client.post(
        flow_url(issue) + "/" + action,
        json=dict(expected_version=version, call_id=f"{issue}-{action}-{version}", **payload),
    )


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def denied(response):
    assert 400 <= response.status_code < 500, response.text


def test_progress_release_backwards_and_human_gate_across_entries(fixture):
    _, store, owner, client, issue = fixture
    parent = store.create_issue(owner, "Review input")["id"]
    assert not ok(client.get(flow_url(issue)))["configured"]
    configured = ok(post(client, issue, "configure", 0, **config()))
    assert configured["version"] == 1
    moved = ok(post(client, issue, "advance", 1, to_status="sculpt"))
    assert moved["progress"] == 40
    linked = ok(post(client, issue, "dependencies", 2, dependencies=[parent]))
    assert linked["dependencies"][0]["id"] == parent
    denied(post(client, issue, "advance", 3, to_status="in-review"))
    denied(client.patch(f"/api/v1/issues/{issue}", json={"to_status": "in-review"}))
    assert ok(post(client, issue, "advance", 3, to_status="backlog"))["progress"] == 0
    for status in ("in-progress", "in-review", "done"):
        assert store.transition_issue(owner, parent, status)["status"] == status
    assert ok(post(client, issue, "advance", 4, to_status="sculpt"))["progress"] == 40
    reviewed = ok(post(client, issue, "advance", 5, to_status="in-review"))
    assert reviewed["version"] == 6
    before = ok(client.get(flow_url(issue)))
    denied(post(client, issue, "advance", 6, to_status="done"))
    denied(client.patch(f"/api/v1/issues/{issue}", json={"to_status": "done"}))
    with pytest.raises(TianxuanError):
        store.dispatch_tool(owner, "issue.transition", dict(issue_id=issue, to_status="done"))
    with pytest.raises(TianxuanError):
        store.dispatch_tool(owner, "flow.judge", dict(issue_id=issue, to_status="done", expected_version=6))
    rewritten = config()
    for stage in rewritten["stages"]:
        stage["human"] = False
    with pytest.raises(TianxuanError):
        store.dispatch_tool(
            owner, "flow.configure", dict(issue_id=issue, expected_version=6, **rewritten), call_id="rewrite"
        )
    assert ok(client.get(flow_url(issue))) == before
    result = ok(post(client, issue, "judge", 6, to_status="done"))
    assert result["progress"] == 100 and result["status"] == "done"
    assert ok(post(client, issue, "judge", 6, to_status="done")) == result
    row = next(x for x in ok(client.get("/api/v1/work/roadmap"))["items"] if x["id"] == issue)
    assert row["progress"] == 100


@pytest.mark.parametrize("cycle", [True, False])
def test_concurrent_connections_serialize_dependency_cycle_and_retry(fixture, cycle):
    path, store, owner, client, issue = fixture
    other = store.create_issue(owner, "Prerequisite")["id"]
    barrier = threading.Barrier(2)

    def set_dep(pair):
        source, dest = pair
        tx = Tianxuan(str(path))
        try:
            barrier.wait(timeout=10)
            return tx.dispatch_tool(
                owner,
                "flow.dependencies",
                dict(issue_id=source, expected_version=0, dependencies=[dest]),
                call_id=source,
            )
        except TianxuanError:
            return None
        finally:
            tx.db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(set_dep, [(issue, other), (other, issue) if cycle else (issue, other)]))
    assert results.count(None) == int(cycle)
    if not cycle:
        assert results[0] == results[1]
    views = [ok(client.get(flow_url(x))) for x in (issue, other)]
    assert sum(len(view["dependencies"]) for view in views) == 1
    assert sum(view["version"] for view in views) == 1


def test_dependency_acl_revocation_and_scope(fixture):
    _, store, owner, client, issue = fixture
    req = store.create_requirement(owner, "art", "Private", "Goal", "Scope", "Accept")["id"]
    store.set_visibility(owner, req, "private")
    parent = store.create_issue(owner, "Parent", requirement_id=req)["id"]
    private = store.create_issue(owner, "secret", parent_id=parent)["id"]
    inv = store.create_invite(owner, "editor@example.invalid", "editor")
    actor = store.accept_invite(inv["code"], "secret")["user_id"]
    store.share_doc(owner, req, actor, "read")
    foreign = store.register("other", "other@example.invalid", "secret")["user_id"]
    alien = store.create_issue(foreign, "Other")["id"]
    for invalid in (issue, alien):
        denied(post(client, issue, "dependencies", 0, dependencies=[invalid]))
    payload = dict(issue_id=issue, dependencies=[private], expected_version=0)
    saved = store.dispatch_tool(actor, "flow.dependencies", payload, call_id="set")
    assert saved["dependencies"][0]["id"] == private
    store.unshare_doc(owner, req, actor)
    with pytest.raises(TianxuanError):
        store.dispatch_tool(actor, "flow.dependencies", payload, call_id="set")
    limited = {"Authorization": "Bearer " + store.issue_session(actor)}
    for url in [flow_url(issue), "/api/v1/work/roadmap"]:
        response = client.get(url, headers=limited)
        assert private not in response.text and '"secret"' not in response.text


def test_native_managed_done_without_acceptance_does_not_release_and_rejects_ordinary_edits(fixture):
    _, store, owner, client, issue = fixture
    prereq = store.create_issue(owner, "Native")["id"]
    for status in ("in-progress", "in-review", "done"):
        store.transition_issue(owner, prereq, status)
    with store.db:
        store.db.execute(
            "INSERT INTO native_managed_issues(issue_id,definition) VALUES (?,?)", (prereq, "native-contract")
        )
    denied(post(client, prereq, "configure", 0, **config()))
    ok(post(client, issue, "dependencies", 0, dependencies=[prereq]))
    denied(post(client, issue, "advance", 1, to_status="in-progress"))
    assert store.get_issue(issue)["status"] == "backlog"


def test_default_legacy_progress_and_stale_operation(fixture):
    _, store, owner, client, issue = fixture
    dep = store.create_issue(owner, "Depends")["id"]
    first = ok(post(client, issue, "dependencies", 0, dependencies=[dep]))
    assert ok(post(client, issue, "dependencies", 0, dependencies=[dep])) == first
    denied(post(client, issue, "dependencies", 0, dependencies=[]))
    denied(client.patch(f"/api/v1/issues/{issue}", json={"to_status": "in-progress"}))
    with pytest.raises(TianxuanError):
        store.dispatch_tool(owner, "issue.transition", dict(issue_id=issue, to_status="in-progress"))
    ok(post(client, issue, "dependencies", 1, dependencies=[]))
    assert ok(client.patch(f"/api/v1/issues/{issue}", json={"to_status": "in-progress"}))["status"] == "in-progress"


def test_existing_stages_can_be_configured_from_public_ai_api_and_judged_only_by_human(fixture):
    _, _, _, client, issue = fixture
    state = ok(client.post("/api/v1/tools", json={"name": "flow.read", "payload": {"issue_id": issue}}))
    for stage in state["stages"]:
        if stage["id"] == "backlog":
            stage["human"] = True
    payload = dict(issue_id=issue, expected_version=0, stages=state["stages"], edges=state["edges"])
    configured = ok(client.post("/api/v1/tools", json=dict(name="flow.configure", payload=payload, call_id="design")))
    assert configured["configured"]
    action = dict(issue_id=issue, expected_version=1, to_status="in-progress")
    for name in ("flow.judge", "flow.advance"):
        denied(client.post("/api/v1/tools", json=dict(name=name, payload=action, call_id="machine")))
    assert ok(post(client, issue, "judge", 1, to_status="in-progress"))["status"] == "in-progress"
