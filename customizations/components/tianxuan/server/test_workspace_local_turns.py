from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from types import SimpleNamespace
from uuid import uuid4

import pytest
from api import create_app
from fastapi import HTTPException
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan

ROOT = "/api/v1/workspace/conversations"


def headers(store, issuer, actor):
    return {"Authorization": "Bearer " + store.issue_access_key(issuer, actor, "local turn test")["key"]}


def state(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def completed(**changes):
    return {
        "id": str(uuid4()),
        "content": "Review the selected scene",
        "expected_version": 0,
        "answer": "    preserve_indented_code()\n\nA local answer.  \n",
        "model": "local-cli/model",
        **changes,
    }


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    database = str(tmp_path / "local-turns.sqlite")
    store = Tianxuan(database)
    actor = store.register("Local", "owner@example.invalid", "password123")["user_id"]
    auth = headers(store, actor, actor)

    def unexpected_model(*args):
        pytest.fail("saving a completed local turn must not invoke the server model")

    monkeypatch.setattr("workspace_conversations.workspace_reply", unexpected_model)
    try:
        with TestClient(create_app(store), headers=auth) as client:
            key = str(uuid4())
            empty = state(client.post(ROOT, json={"id": key}), 201)
            yield SimpleNamespace(
                store=store,
                actor=actor,
                auth=auth,
                database=database,
                client=client,
                url=f"{ROOT}/{key}",
                empty=empty,
            )
    finally:
        store.db.close()


def test_completed_local_turn_is_durable_and_does_not_grant_execution(workspace):
    ws = workspace
    payload = completed()
    saved = state(ws.client.post(ws.url + "/local-turns", json=payload))
    assert saved["version"] == 1
    assert saved["title"] == payload["content"]
    turn = saved["turns"][0]
    assert {key: turn[key] for key in ("id", "content", "answer", "model")} == {
        key: payload[key] for key in ("id", "content", "answer", "model")
    }
    assert turn["state"] == "answered" and turn["error"] is None
    assert turn["reply_source"] == "editor-local"
    for key in ("revisions", "current", "requirement_id", "requirement_version", "execution", "past_executions"):
        assert saved[key] == ws.empty[key]
    assert state(ws.client.get(ws.url)) == saved
    reopened = Tianxuan(ws.database)
    try:
        with TestClient(create_app(reopened), headers=ws.auth) as client:
            assert state(client.get(ws.url)) == saved
            # The unchanged Web draft flow can consume a synced local conversation.
            draft = state(
                client.post(
                    ws.url + "/design/direction/drafts",
                    json={
                        "expected_version": saved["version"],
                        "body": "Locally drafted direction",
                    },
                )
            )
            assert draft["current"] == {"direction": 1}
            assert draft["revisions"][0]["confirmed_at"] is None
            assert draft["execution"] is None
    finally:
        reopened.db.close()


def test_local_retry_only_accepts_the_original_completed_payload(workspace):
    ws = workspace
    payload = completed()
    saved = state(ws.client.post(ws.url + "/local-turns", json=payload))
    assert state(ws.client.post(ws.url + "/local-turns", json=payload)) == saved
    for changed in (
        {"content": "A different request"},
        {"answer": "A different answer"},
        {"model": "another-local-model"},
        {"expected_version": saved["version"]},
        {"context_snapshot": {"project": "game", "module_id": "default", "references": []}},
    ):
        assert ws.client.post(ws.url + "/local-turns", json={**payload, **changed}).status_code == 409
    assert state(ws.client.get(ws.url)) == saved
    # A second completion cannot silently replace an existing conversation revision.
    assert ws.client.post(ws.url + "/local-turns", json=completed()).status_code == 409
    later = state(ws.client.post(ws.url + "/local-turns", json=completed(expected_version=saved["version"])))
    assert len(later["turns"]) == 2
    assert state(ws.client.post(ws.url + "/local-turns", json=payload)) == later


@pytest.mark.parametrize(
    "changes",
    [
        {"answer": ""},
        {"answer": " \t\r\n\u3000"},
        {"answer": "a" * 16001},
        {"model": " "},
        {"model": "m" * 257},
        {"content": "x" * 8001},
        {"execution": {"state": "running"}},
        {"reply_source": "editor-local"},
    ],
)
def test_invalid_local_payload_does_not_change_history(workspace, changes):
    ws = workspace
    assert ws.client.post(ws.url + "/local-turns", json=completed(**changes)).status_code == 422
    assert state(ws.client.get(ws.url)) == ws.empty


def test_local_sync_accepts_text_limits_and_keeps_the_conversation_limit(workspace):
    ws = workspace
    payload = completed(content="c" * 8000, answer="a" * 16000, model="m" * 256)
    saved = state(ws.client.post(ws.url + "/local-turns", json=payload))
    assert saved["turns"][0]["answer"] == payload["answer"]
    for _ in range(99):
        saved = state(ws.client.post(ws.url + "/local-turns", json=completed(expected_version=saved["version"])))
    assert len(saved["turns"]) == 100
    response = ws.client.post(ws.url + "/local-turns", json=completed(expected_version=saved["version"]))
    assert response.status_code == 409
    assert state(ws.client.get(ws.url)) == saved
    assert state(ws.client.post(ws.url + "/local-turns", json=payload)) == saved


def test_local_sync_requires_the_conversation_owner_and_write_permission(workspace):
    ws = workspace
    teammate = ws.store.add_member(ws.actor, "member@example.invalid", "password123")["user_id"]
    viewer = ws.store.add_member(ws.actor, "viewer@example.invalid", "password123", role="viewer")["user_id"]
    outsider = ws.store.register("Other", "outside@example.invalid", "password123")["user_id"]
    payload = completed()
    with TestClient(create_app(ws.store)) as client:
        assert client.post(ws.url + "/local-turns", json=payload).status_code == 401
        for actor, issuer, expected in ((teammate, ws.actor, 404), (outsider, outsider, 404), (viewer, ws.actor, 403)):
            assert (
                client.post(
                    ws.url + "/local-turns",
                    headers=headers(ws.store, issuer, actor),
                    json=payload,
                ).status_code
                == expected
            )
    assert state(ws.client.get(ws.url)) == ws.empty


def test_local_context_keeps_existing_access_project_and_revision_checks(workspace):
    ws = workspace
    actor = ws.store.add_member(ws.actor, "editor@example.invalid", "password123")["user_id"]
    foreign_actor = ws.store.register("Other", "outside@example.invalid", "password123")["user_id"]
    requirement = ws.store.create_requirement(ws.actor, "private", "Private", "goal", "scope", "done")
    ws.store.set_visibility(ws.actor, requirement["id"], "private")
    issue = ws.store.create_issue(ws.actor, "Public")
    private = ws.store.create_issue(ws.actor, "Private", requirement_id=requirement["id"])
    foreign = ws.store.create_issue(foreign_actor, "Public")
    snapshot = {"project": issue["project"], "module_id": issue["module_id"], "issue_id": issue["id"], "references": []}
    ref = {"kind": "document", "object_id": requirement["id"], "revision": 1}
    with TestClient(create_app(ws.store), headers=headers(ws.store, ws.actor, actor)) as client:
        key = str(uuid4())
        empty = state(client.post(ROOT, json={"id": key}), 201)
        url = f"{ROOT}/{key}"
        for changed, expected in (
            ({"issue_id": private["id"]}, 403),
            ({"issue_id": foreign["id"]}, 404),
            ({"project": "elsewhere"}, 409),
            ({"module_id": "elsewhere"}, 409),
            ({"references": [ref]}, 403),
            ({"references": [{**ref, "revision": 0}]}, 422),
            ({"issue_id": None, "module_id": "missing"}, 404),
            ({"references": [{"kind": "issue", "object_id": issue["id"], "revision": "0" * 64}]}, 409),
        ):
            response = client.post(url + "/local-turns", json=completed(context_snapshot={**snapshot, **changed}))
            assert response.status_code == expected, response.text
        ws.store.share_doc(ws.actor, requirement["id"], actor, "read")
        missing = {**snapshot, "references": [{**ref, "revision": 2}]}
        assert client.post(url + "/local-turns", json=completed(context_snapshot=missing)).status_code == 404
        assert state(client.get(url)) == empty
        accepted = state(
            client.post(url + "/local-turns", json=completed(context_snapshot={**snapshot, "references": [ref]}))
        )
        assert accepted["turns"][0]["context_snapshot"] == {**snapshot, "references": [ref]}


def test_local_continuation_keeps_the_revision_used_by_the_local_model(workspace):
    ws = workspace
    doc = ws.store.create_doc(ws.actor, "Review", "Original paragraph")
    ref = {"kind": "document", "object_id": doc["id"], "revision": 1}
    snapshot = {"project": "game", "module_id": "default", "issue_id": None, "references": [ref]}
    first = state(ws.client.post(ws.url + "/local-turns", json=completed(context_snapshot=snapshot)))
    ws.store.update_doc(ws.actor, doc["id"], "Local reviewed edit", expected_version=1)
    continuation = {
        **snapshot,
        "continuation": {"preserve": "Keep the first decision"},
        "references": [
            {**ref, "kind": "document_edit", "revision": 2},
        ],
    }
    payload = completed(expected_version=first["version"], context_snapshot=continuation)
    # Another edit occurs after local inference and before uploading its answer.
    ws.store.update_doc(ws.actor, doc["id"], "New head unseen by the local model", expected_version=2)
    saved = state(ws.client.post(ws.url + "/local-turns", json=payload))
    assert saved["turns"][0] == first["turns"][0]
    turn = saved["turns"][1]
    assert turn["context_snapshot"] == continuation
    edit = turn["document_edits"][0]
    assert (edit["start_revision"], edit["revision"]) == (1, 2)
    assert edit["changes"] == [
        {
            "before": [{"paragraph": 1, "text": "Original paragraph"}],
            "after": [{"paragraph": 1, "text": "Local reviewed edit"}],
        }
    ]
    assert state(ws.client.post(ws.url + "/local-turns", json=payload)) == saved


def test_local_completion_never_overwrites_an_unanswered_server_turn(workspace, monkeypatch):
    ws = workspace

    def unavailable(*args):
        raise HTTPException(503, "No server model")

    monkeypatch.setattr("workspace_conversations.workspace_reply", unavailable)
    payload = completed()
    server_payload = {key: payload[key] for key in ("id", "content", "expected_version")}
    previous = state(ws.client.post(ws.url + "/turns", json=server_payload))
    assert previous["turns"][0]["state"] == "unanswered"
    assert (
        ws.client.post(ws.url + "/local-turns", json={**payload, "expected_version": previous["version"]}).status_code
        == 409
    )
    saved = state(
        ws.client.post(
            ws.url + "/local-turns",
            json={
                **payload,
                "id": str(uuid4()),
                "expected_version": previous["version"],
            },
        )
    )
    assert saved["turns"][0] == previous["turns"][0]
    assert saved["turns"][1]["state"] == "answered"


def test_local_completion_cannot_bypass_a_pending_server_turn(workspace, monkeypatch):
    ws = workspace
    started, release = Event(), Event()
    calls = []

    def delayed(*args):
        calls.append(args)
        started.set()
        assert release.wait(timeout=10)
        return {"content": "A late server answer", "model": "server"}

    monkeypatch.setattr("workspace_conversations.workspace_reply", delayed)
    server_turn = {"id": str(uuid4()), "content": "In flight", "expected_version": 0}
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(ws.client.post, ws.url + "/turns", json=server_turn)
        try:
            assert started.wait(timeout=5)
            pending = state(ws.client.get(ws.url))
            assert pending["turns"][0]["state"] == "pending"
            for key in (server_turn["id"], str(uuid4())):
                assert (
                    ws.client.post(
                        ws.url + "/local-turns",
                        json=completed(
                            id=key,
                            expected_version=pending["version"],
                        ),
                    ).status_code
                    == 409
                )
            assert state(ws.client.get(ws.url)) == pending
        finally:
            release.set()
        answered = state(future.result(timeout=5))
        assert answered["turns"][0]["answer"] == "A late server answer"
        assert len(calls) == 1


@pytest.mark.parametrize("same_id", [True, False])
def test_concurrent_local_uploads_commit_only_one_turn(workspace, same_id):
    ws = workspace
    barrier = Barrier(2)
    payload = completed()

    def upload(value):
        barrier.wait(timeout=5)
        return ws.client.post(ws.url + "/local-turns", json=value)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(upload, payload)
        second = pool.submit(upload, payload if same_id else {**payload, "id": str(uuid4())})
        responses = [first.result(timeout=10), second.result(timeout=10)]
    assert sorted(response.status_code for response in responses) == ([200, 200] if same_id else [200, 409])
    saved = state(ws.client.get(ws.url))
    assert saved["version"] == 1 and len(saved["turns"]) == 1
    if same_id:
        assert all(state(response) == saved for response in responses)
