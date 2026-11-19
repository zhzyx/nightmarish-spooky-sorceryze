"""Budgeted document reads and replay-safe AI patches."""

import pytest
from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import NotFound, PermissionDenied, Tianxuan, VersionConflict


@pytest.fixture
def scenario():
    store = Tianxuan()
    actor = store.register("AI docs", "ai@example.invalid", "password")["user_id"]
    doc = store.create_doc(actor, "Guide", "# Guide\nalpha\nbeta\n```\n# Code\n```\n")
    yield store, actor, doc
    store.db.close()


def test_read_budget_and_version(scenario):
    store, actor, doc = scenario
    payload = {"doc_id": doc["id"], "start_line": 2, "max_lines": 1, "max_chars": 3, "expected_version": 1}
    result = store.dispatch_tool(actor, "doc.read", payload)
    assert result["body_md"] == "alp"
    assert result["range"]["truncated"]
    assert len(result["machine"]["headings"]) == 1
    assert result["machine"]["content_hash"]
    assert "body_md" not in store.dispatch_tool(actor, "doc.read", {"doc_id": doc["id"], "include_body": False})
    store.update_doc(actor, doc["id"], "changed", 1)
    with pytest.raises(VersionConflict):
        store.dispatch_tool(actor, "doc.read", payload)


def test_patch_retry_conflict_and_revoked_role(scenario):
    store, actor, doc = scenario
    payload = {"doc_id": doc["id"], "expected_version": 1, "patches": [{"find": "alpha", "replace": "new"}]}
    result = store.dispatch_tool(actor, "doc.patch", payload, call_id="retry")
    events = store.events(actor)
    assert store.dispatch_tool(actor, "doc.patch", payload, call_id="retry") == result
    assert store.events(actor) == events
    with pytest.raises(VersionConflict):
        store.dispatch_tool(actor, "doc.patch", payload, call_id="fresh")
    store.set_role(actor, actor, "viewer")
    with pytest.raises(PermissionDenied):
        store.dispatch_tool(actor, "doc.patch", payload, call_id="retry")


def test_cross_tenant_and_search(scenario):
    store, actor, doc = scenario
    other = store.register("Other", "other@example.invalid", "password")["user_id"]
    assert store.dispatch_tool(actor, "doc.search", {"q": "alpha"})["results"][0]["id"] == doc["id"]
    assert store.dispatch_tool(other, "doc.search", {"q": "alpha"}) == {"results": []}
    with pytest.raises(NotFound):
        store.dispatch_tool(other, "doc.read", {"doc_id": doc["id"]})
    with pytest.raises(NotFound):
        store.dispatch_tool(
            other, "doc.patch", {"doc_id": doc["id"], "expected_version": 1, "patches": []}, call_id="x"
        )


def test_http_budget_and_patch_retry(scenario):
    store, actor, doc = scenario
    client = TestClient(create_app(store))
    headers = {"X-Actor": actor}
    base = f"/api/v1/docs/{doc['id']}"
    result = client.get(base + "/ai-view?include_body=false", headers=headers)
    assert result.status_code == 200
    assert "body_md" not in result.json()
    assert client.get(base + "/ai-view?max_chars=0", headers=headers).status_code == 422
    payload = {"expected_version": 1, "patches": [{"find": "alpha", "replace": "new"}], "call_id": "http-retry"}
    first = client.post(base + "/patch", headers=headers, json=payload)
    retry = client.post(base + "/patch", headers=headers, json=payload)
    assert first.status_code == retry.status_code == 200
    assert first.json() == retry.json()


def test_patch_replay_checks_revoked_document_share(scenario):
    store, owner, doc = scenario
    editor = store.add_member(owner, "editor@example.invalid", "password", role="editor")["user_id"]
    store.set_visibility(owner, doc["id"], "private")
    store.share_doc(owner, doc["id"], editor, "write")
    payload = {"doc_id": doc["id"], "expected_version": 1, "patches": [{"find": "alpha", "replace": "new"}]}
    store.dispatch_tool(editor, "doc.patch", payload, call_id="shared")
    store.unshare_doc(owner, doc["id"], editor)
    with pytest.raises(PermissionDenied):
        store.dispatch_tool(editor, "doc.patch", payload, call_id="shared")


def test_patch_replay_checks_new_field_restriction(scenario):
    store, owner, doc = scenario
    editor = store.add_member(owner, "field@example.invalid", "password", role="editor")["user_id"]
    payload = {
        "doc_id": doc["id"],
        "expected_version": 1,
        "patches": [{"find": "alpha", "replace": "new"}],
    }
    store.dispatch_tool(editor, "doc.patch", payload, call_id="field")
    store.set_doc_field_permission(owner, doc["id"], "body_md", "admin")
    with pytest.raises(PermissionDenied):
        store.dispatch_tool(editor, "doc.patch", payload, call_id="field")


def test_public_http_tools_viewer_and_workspace_boundary(scenario, monkeypatch):
    store, owner, doc = scenario
    viewer = store.add_member(owner, "reader@example.invalid", "password", role="viewer")["user_id"]
    monkeypatch.setenv("TIANXUAN_AUTH_MODE", "accounts")
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://docs.example.invalid")
    monkeypatch.setenv("TIANXUAN_TENANT_ID", "existing-private-deployment")
    client = TestClient(create_app(store))
    headers = {"Authorization": "Bearer " + store.issue_session(viewer)}
    for name, payload in (
        ("doc.read", {"doc_id": doc["id"], "include_body": False}),
        ("doc.search", {"q": "alpha"}),
        ("doc.list", {}),
    ):
        response = client.post("/api/v1/tools", headers=headers, json={"name": name, "payload": payload})
        assert response.status_code == 200, response.text
    denied = client.post(
        "/api/v1/tools",
        headers=headers,
        json={
            "name": "doc.create",
            "payload": {"title": "denied"},
            "call_id": "viewer",
        },
    )
    assert denied.status_code == 403
    owner_headers = {"Authorization": "Bearer " + store.issue_session(owner)}
    denied = client.post(
        "/api/v1/tools",
        headers=owner_headers,
        json={
            "name": "issue.create",
            "payload": {"title": "denied"},
        },
    )
    assert denied.status_code == 403
    payload = {
        "name": "doc.patch",
        "call_id": "http-tool",
        "payload": {"doc_id": doc["id"], "expected_version": 1, "patches": [{"find": "alpha", "replace": "new"}]},
    }
    first = client.post("/api/v1/tools", headers=owner_headers, json=payload)
    retry = client.post("/api/v1/tools", headers=owner_headers, json=payload)
    assert first.status_code == retry.status_code == 200
    assert first.json() == retry.json()
    assert (
        client.post("/api/v1/tools", headers=owner_headers, json={"name": "doc.read", "payload": {}}).status_code == 422
    )
