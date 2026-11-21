from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from api import create_app
from fastapi.testclient import TestClient
from gateway import ModelGateway
from tianxuan_core import Tianxuan
from workspace_conversations import require_workspace_approval

ROOT = "/api/v1/workspace/conversations"


def headers(store, issuer, user):
    return {"Authorization": "Bearer " + store.issue_access_key(issuer, user, "workspace test")["key"]}


def get_state(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def test_context_snapshot_survives_selection_revision_and_module_changes(tmp_path, monkeypatch):
    database = str(tmp_path / "messages.sqlite")
    store = Tianxuan(database)
    actor = store.register("Studio", "maker@example.invalid", "password123")["user_id"]
    auth = headers(store, actor, actor)
    project = "studio/game"
    selections = []
    for key in ("first", "second"):
        module = store.create_business_module(actor, project, "Lighting", call_id=key)
        issue = store.create_issue(actor, "Review", project=project, module_id=module["id"])
        document = store.create_doc(actor, "Lighting", f"{key} original")
        selections.append({
            "project": project,
            "module_id": module["id"],
            "issue_id": issue["id"],
            "references": [{"kind": "document", "object_id": document["id"], "revision": document["version"]}],
        })
    monkeypatch.setenv("TIANXUAN_CHAT_MODEL", "test-model")
    monkeypatch.setenv("TIANXUAN_CHAT_BASE_URL", "https://configured.example/v1")
    monkeypatch.setenv("TIANXUAN_CHAT_MODEL_KEY", "workspace-fixture")
    model_requests = []

    def reply(request):
        model_requests.append(json.loads(request.content)["messages"])
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "received"}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 1},
                "model": "test-model",
            },
        )

    gateway = ModelGateway(":memory:", transport=httpx.MockTransport(reply))
    conversation_id = str(uuid4())
    url = f"{ROOT}/{conversation_id}"
    with TestClient(create_app(store, gateway=gateway), headers=auth) as client:
        get_state(client.post(ROOT, json={"id": conversation_id}), 201)
        selection = selections[0]
        first = {"id": str(uuid4()), "expected_version": 0, "content": "Review this", "context_snapshot": selection}
        response = get_state(client.post(url + "/turns", json=first))
        assert response["turns"][0]["state"] == "answered"
        selection = selections[1]
        original = response["turns"][0]["context_snapshot"]["references"][0]
        store.update_doc(actor, original["object_id"], "first revised", expected_version=1)
        store.set_issue_module(actor, selections[0]["issue_id"], project, selection["module_id"])
        # A transport retry addresses the committed turn, even after the original issue moved.
        assert get_state(client.post(url + "/turns", json=first)) == response
        assert client.post(url + "/turns", json={**first, "context_snapshot": selection}).status_code == 409
        assert (
            client.post(
                url + "/turns",
                json={
                    **first,
                    "id": str(uuid4()),
                    "expected_version": response["version"],
                },
            ).status_code
            == 409
        )
        second = {**first, "id": str(uuid4()), "expected_version": response["version"], "context_snapshot": selection}
        result = get_state(client.post(url + "/turns", json=second))
        assert result["turns"][1]["state"] == "answered"
    assert len(model_requests) == 2
    model_snapshots = [
        json.loads(message["content"])["context_snapshot"] for message in model_requests[1] if message["role"] == "user"
    ]
    assert model_snapshots == selections
    assert json.loads(model_requests[0][0]["content"])["context_snapshot"] == selections[0]
    gateway.close()
    store.db.close()

    reopened = Tianxuan(database)
    with TestClient(create_app(reopened), headers=auth) as client:
        turns = get_state(client.get(url))["turns"]
        assert [turn["context_snapshot"] for turn in turns] == selections
        bodies = []
        for turn in turns:
            reference = turn["context_snapshot"]["references"][0]
            path = f"/api/v1/docs/{reference['object_id']}/versions/{reference['revision']}"
            bodies.append(get_state(client.get(path))["body_md"])
        assert bodies == ["first original", "second original"]
        current = get_state(client.get(f"/api/v1/docs/{original['object_id']}"))
        assert (current["version"], current["body_md"]) == (2, "first revised")
    reopened.db.close()


def test_context_rejects_inaccessible_or_unversioned_selection_without_recording_a_turn():
    store = Tianxuan()
    owner = store.register("Team", "owner@example.invalid", "password123")["user_id"]
    actor = store.add_member(owner, "editor@example.invalid", "password123")["user_id"]
    outsider = store.register("Outside", "outside@example.invalid", "password123")["user_id"]
    requirement = store.create_requirement(owner, "private", "Private", "goal", "scope", "done")
    store.set_visibility(owner, requirement["id"], "private")
    issue = store.create_issue(owner, "Public")
    private = store.create_issue(owner, "Private", requirement_id=requirement["id"])
    foreign = store.create_issue(outsider, "Public")
    ref = {"kind": "document", "object_id": requirement["id"], "revision": 1}
    snapshot = {"project": issue["project"], "module_id": issue["module_id"], "issue_id": issue["id"], "references": []}
    key = str(uuid4())
    url = f"{ROOT}/{key}"
    with TestClient(create_app(store), headers=headers(store, owner, actor)) as client:
        empty = get_state(client.post(ROOT, json={"id": key}), 201)
        turn = {"id": str(uuid4()), "expected_version": 0, "content": "Discuss"}
        for changes, expected in (
            ({"issue_id": private["id"]}, 403),
            ({"issue_id": foreign["id"]}, 404),
            ({"project": "elsewhere"}, 409),
            ({"module_id": "another"}, 409),
            ({"references": [ref]}, 403),
            ({"references": [{**ref, "revision": 0}]}, 422),
            ({"references": [{"kind": "editor", "object_id": "res://a.gd", "revision": "HEAD"}]}, 422),
            ({"issue_id": None, "module_id": "missing"}, 404),
        ):
            response = client.post(url + "/turns", json={**turn, "context_snapshot": {**snapshot, **changes}})
            assert response.status_code == expected, response.text
        store.share_doc(owner, requirement["id"], actor, "read")
        missing = {**snapshot, "references": [{**ref, "revision": 2}]}
        assert client.post(url + "/turns", json={**turn, "context_snapshot": missing}).status_code == 404
        assert get_state(client.get(url)) == empty
        local = {"kind": "editor", "object_id": "res://scenes/Hero.tscn#Arm", "revision": "e" * 64}
        selection = {**snapshot, "issue_id": None, "references": [local]}
        result = get_state(client.post(url + "/turns", json={**turn, "context_snapshot": selection}))
        assert result["turns"][0]["context_snapshot"] == selection
        assert result["turns"][0]["state"] == "unanswered"
    store.db.close()


def test_conversation_and_confirmations_are_private_durable_and_idempotent(tmp_path, monkeypatch):
    for name in ("duobao", "sinan-workorders"):
        monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / name))
    from native_execution_host import EntryLedger
    from native_store import NativeStoreError

    path = str(tmp_path / "workspace.sqlite")
    store = Tianxuan(path)
    first = store.register("First", "first@example.invalid", "password123")
    actor = first["user_id"]
    second = store.add_member(actor, "second@example.invalid", "password123")["user_id"]
    outsider = store.register("Other", "outside@example.invalid", "password123")["user_id"]
    viewer = store.add_member(actor, "viewer@example.invalid", "password123", role="viewer")["user_id"]
    owner_headers = headers(store, actor, actor)
    teammate_headers = headers(store, actor, second)
    other_headers = headers(store, outsider, outsider)
    viewer_headers = headers(store, actor, viewer)
    monkeypatch.setenv("TIANXUAN_REQUIRE_KEYS", "1")
    monkeypatch.setenv("TIANXUAN_TENANT_ID", first["tenant_id"])
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://workspace.example")
    monkeypatch.setenv("TIANXUAN_CHAT_MODEL", "test-model")
    monkeypatch.setenv("TIANXUAN_CHAT_BASE_URL", "https://configured.example/v1")
    monkeypatch.setenv("TIANXUAN_CHAT_MODEL_KEY", "workspace-fixture")
    calls = []

    def send(request):
        assert request.url == httpx.URL("https://configured.example/v1/chat/completions")
        assert request.headers["Authorization"] == "Bearer workspace-fixture"
        calls.append(json.loads(request.content)["messages"])
        return httpx.Response(
            200,
            json={
                "model": "test-model",
                "choices": [{"message": {"content": "stage suggestion"}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7},
            },
        )

    gateway = ModelGateway(":memory:", transport=httpx.MockTransport(send))
    ledger = EntryLedger(store)
    notifications = []

    def entries():
        with store._connection_lock:
            return [dict(row) for row in store.db.execute("SELECT * FROM native_entry_intents")]

    def notify(entry):
        assert not store.db.in_transaction
        assert entry in {row["id"] for row in entries()}
        notifications.append(entry)

    async def idle():
        pass

    native = SimpleNamespace(
        domain=store,
        ledger=ledger,
        start=idle,
        stop=idle,
        entries=entries,
        task_references=lambda key, actor: [],
        role_calls=lambda key: [],
        policy_reference=lambda *_: None,
        consumer=SimpleNamespace(notify=notify, failures=[]),
        installation=SimpleNamespace(
            verify=lambda: {
                "mode": "fixture",
                "identity": "fixture",
                "scopes": {"code": {}, "docs": {}},
                "catalog": [{"id": "available-model", "available": True}, {"id": "inactive-model", "available": False}],
            }
        ),
        execution_nodes=None,
        runtime_installation=None,
        notify_dependency_change=lambda: None,
        validate_dependencies=lambda *_: [],
    )
    key = str(uuid4())
    url = f"{ROOT}/{key}"
    original_db = list(store.db.iterdump())
    with TestClient(create_app(store, gateway=gateway, native_entry=native)) as client:
        assert client.get(ROOT).status_code == 401
        assert client.post(ROOT, headers=viewer_headers, json={"id": key}).status_code == 403
        assert client.get(ROOT, headers=other_headers).status_code == 403
        assert get_state(client.get(ROOT, headers=owner_headers)) == {"conversations": [], "next": None}
        assert client.get(url, headers=owner_headers).status_code == 404
        assert list(store.db.iterdump()) == original_db
        conversation = get_state(client.post(ROOT, headers=owner_headers, json={"id": key}), 201)
        assert get_state(client.post(ROOT, headers=owner_headers, json={"id": key}), 201) == conversation
        assert client.get(url, headers=teammate_headers).status_code == 404
        assert get_state(client.get(ROOT, headers=teammate_headers))["conversations"] == []
        # An identical client-generated ID in a different owner namespace divulges nothing.
        assert get_state(client.post(ROOT, headers=teammate_headers, json={"id": key}), 201)["turns"] == []

        version_zero = {"expected_version": 0}
        assert (
            client.post(
                url + "/execution",
                headers=owner_headers,
                json={**version_zero, "requirement_version": 1, "scopes": ["code"]},
            ).status_code
            == 409
        )
        assert (
            client.post(
                url + "/design/direction/drafts",
                headers=owner_headers,
                json={
                    **version_zero,
                    "body": "draft without a conversation",
                },
            ).status_code
            == 409
        )
        turn = {"id": str(uuid4()), "content": "灯光需求", **version_zero}
        conversation = get_state(client.post(url + "/turns", headers=owner_headers, json=turn))
        assert conversation["turns"][0]["state"] == "answered"
        assert conversation["turns"][0]["content"] == "\u706f\u5149\u9700\u6c42"
        assert get_state(client.post(url + "/turns", headers=owner_headers, json=turn)) == conversation
        assert client.post(url + "/turns", headers=owner_headers, json={**turn, "content": "other"}).status_code == 409
        assert len(calls) == 1
        assert (
            get_state(
                client.post(
                    url + "/design/direction/suggest",
                    headers=owner_headers,
                    json={"expected_version": conversation["version"], "lang": "zh"},
                )
            )["content"]
            == "stage suggestion"
        )
        assert "灯光需求" in calls[-1][1]["content"]
        assert get_state(client.get(url, headers=owner_headers)) == conversation

        def modify(path, **body):
            nonlocal conversation
            conversation = get_state(
                client.post(
                    url + path,
                    headers=owner_headers,
                    json={
                        **body,
                        "expected_version": conversation["version"],
                    },
                )
            )
            return conversation

        def draft(stage, body, **details):
            modify(f"/design/{stage}/drafts", body=body, **details)
            return conversation["current"][stage]

        def confirm(stage, revision):
            modify(f"/design/{stage}/confirm", revision=revision)

        assert (
            client.post(
                url + "/design/plan/drafts",
                headers=owner_headers,
                json={
                    "expected_version": conversation["version"],
                    "body": "premature plan",
                },
            ).status_code
            == 409
        )
        direction = draft("direction", "Lighting direction")
        newer = draft("direction", "Revised lighting direction")
        assert (
            client.post(
                url + "/design/direction/confirm",
                headers=owner_headers,
                json={
                    "expected_version": conversation["version"],
                    "revision": direction,
                },
            ).status_code
            == 409
        )
        confirm("direction", newer)
        prior_plan = draft("plan", "Unchanged old plan")
        confirm("plan", prior_plan)
        confirm("direction", draft("direction", "Final direction"))
        assert "plan" not in conversation["current"]
        assert conversation["revisions"][prior_plan - 1]["confirmed_at"] is not None
        assert (
            client.post(
                url + "/requirement",
                headers=owner_headers,
                json={
                    "expected_version": conversation["version"],
                },
            ).status_code
            == 409
        )
        confirm("plan", draft("plan", "Final plan"))
        design = draft("design", "Final design", title="Lighting", acceptance="Scene renders")
        confirm("design", design)
        version = conversation["version"]
        modify("/requirement")
        requirement = conversation["requirement_id"]
        assert requirement.startswith("doc_")
        assert (
            get_state(
                client.post(
                    url + "/requirement",
                    headers=owner_headers,
                    json={"expected_version": version},
                )
            )["requirement_id"]
            == requirement
        )
        doc = store.get_doc_shared(actor, requirement)
        for token in ("Final direction", "Final plan", "Final design", "Scene renders"):
            assert token in doc["body_md"]
        assert "Unchanged old plan" not in doc["body_md"]
        with store._connection_lock:
            approval = require_workspace_approval(store, actor, requirement, doc["version"])
            assert approval == {
                "actor": actor,
                "tenant": first["tenant_id"],
                "requirement": requirement,
                "conversation": key,
                "version": doc["version"],
                "revisions": conversation["current"],
            }
            with pytest.raises(NativeStoreError):
                require_workspace_approval(store, second, requirement, doc["version"])
            with pytest.raises(NativeStoreError):
                require_workspace_approval(store, actor, requirement, doc["version"] + 1)

        launch = {
            "expected_version": conversation["version"],
            "requirement_version": doc["version"],
            "scopes": ["code", "docs"],
            "model": "available-model",
        }
        for invalid in ({"scopes": ["outside"]}, {"scopes": ["code", "code"]}, {"model": "inactive-model"}):
            assert client.post(url + "/execution", headers=owner_headers, json={**launch, **invalid}).status_code == 422
        assert entries() == []
        assert client.post(url + "/execution", headers=teammate_headers, json=launch).status_code == 409
        modify("/execution", scopes=launch["scopes"], model=launch["model"], requirement_version=doc["version"])
        execution = conversation["execution"]
        assert execution["requirement_version"] == doc["version"]
        assert execution["model"] == "available-model"
        assert get_state(client.post(url + "/execution", headers=owner_headers, json=launch)) == conversation
        assert (
            client.post(url + "/execution", headers=owner_headers, json={**launch, "scopes": ["docs"]}).status_code
            == 409
        )
        assert notifications == [execution["entry"]]
        assert json.loads(entries()[0]["payload"])["choices"] == {
            "scopes": ["code", "docs"],
            "dependencies": [],
            "model": "available-model",
        }
        native_url = f"/api/v1/native/entry/{execution['entry']}"
        native_status = get_state(client.get(native_url, headers=owner_headers))
        assert native_status["state"] == "pending" and native_status["role_calls"] == []
        assert client.get(native_url, headers=teammate_headers).status_code == 404

        with store._connection_lock:
            edited = store.update_doc(second, requirement, doc["body_md"] + "Later edit", doc["version"])
            with pytest.raises(NativeStoreError):
                require_workspace_approval(store, actor, requirement)

        review_url = url + "/requirement-review"
        assert client.get(review_url, headers=teammate_headers).status_code == 409
        review = get_state(client.get(review_url, headers=owner_headers))
        assert review["author"] == second and review["body_md"].endswith("Later edit")
        restored = store.restore_doc(actor, requirement, doc["version"], edited["version"])
        assert restored["body_md"] == doc["body_md"]
        with pytest.raises(NativeStoreError, match="source revision"):
            ledger.authorize(execution["entry"])
        stale = {"expected_version": conversation["version"], "document_version": review["version"]}
        assert client.post(review_url, headers=owner_headers, json=stale).status_code == 409
        review = get_state(client.get(review_url, headers=owner_headers))
        assert review["version"] == restored["version"] and review["author"] == actor
        assert review["approved_version"] == doc["version"]
        confirm_new = {**stale, "document_version": review["version"]}
        modify("/requirement-review", document_version=review["version"])
        assert get_state(client.post(review_url, headers=owner_headers, json=confirm_new)) == conversation
        assert conversation["execution"] is None and conversation["past_executions"] == [execution]
        assert client.post(url + "/execution", headers=owner_headers, json=launch).status_code == 409
        modify("/execution", scopes=["docs"], requirement_version=review["version"])
        second_execution = conversation["execution"]
        assert second_execution["entry"] != execution["entry"]
        assert notifications == [execution["entry"], second_execution["entry"]]
        assert len(entries()) == 2
        with store._connection_lock:
            assert require_workspace_approval(store, actor, requirement)["version"] == restored["version"]
            rows = store.db.execute(
                "SELECT version,source,previous_version FROM workspace_requirement_approvals ORDER BY version"
            ).fetchall()
            assert [tuple(row) for row in rows] == [
                (doc["version"], "design_confirmation", None),
                (restored["version"], "document_reconfirmation", doc["version"]),
            ]

    store.db.close()
    gateway.close()
    store = Tianxuan(path)
    with TestClient(create_app(store)) as restarted:
        saved = get_state(restarted.get(url, headers=owner_headers))
        assert saved == conversation
        assert get_state(restarted.get(ROOT, headers=owner_headers))["conversations"][0]["id"] == key
        assert store.get_doc_shared(actor, requirement)["id"] == requirement
    store.db.close()


def test_unconfigured_model_preserves_text_and_manual_design(tmp_path, monkeypatch):
    monkeypatch.delenv("TIANXUAN_REQUIRE_KEYS", raising=False)
    monkeypatch.delenv("TIANXUAN_AUTH_MODE", raising=False)
    store = Tianxuan(str(tmp_path / "workspace.sqlite"))
    actor = store.register("Manual", "manual@example.invalid", "password123")["user_id"]
    auth = headers(store, actor, actor)
    with TestClient(create_app(store)) as client:
        key = str(uuid4())
        get_state(client.post(ROOT, headers=auth, json={"id": key}), 201)
        url = f"{ROOT}/{key}"
        result = get_state(
            client.post(
                url + "/turns",
                headers=auth,
                json={
                    "id": str(uuid4()),
                    "content": "Manual requirement context",
                    "expected_version": 0,
                },
            )
        )
        assert result["turns"][0]["state"] == "unanswered"
        assert result["turns"][0]["error"] == 503
        assert (
            client.post(
                url + "/design/direction/suggest",
                headers=auth,
                json={
                    "expected_version": result["version"],
                    "lang": "en",
                },
            ).status_code
            == 503
        )
        result = get_state(
            client.post(
                url + "/design/direction/drafts",
                headers=auth,
                json={
                    "expected_version": result["version"],
                    "body": "User-authored direction",
                },
            )
        )
        assert result["current"] == {"direction": 1}
    store.db.close()


def test_pending_turn_replay_and_stop_waiting_do_not_repeat_or_accept_late_reply(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    monkeypatch.delenv("TIANXUAN_REQUIRE_KEYS", raising=False)
    monkeypatch.delenv("TIANXUAN_AUTH_MODE", raising=False)
    monkeypatch.setenv("TIANXUAN_CHAT_MODEL", "test-model")
    monkeypatch.setenv("TIANXUAN_CHAT_BASE_URL", "https://configured.example/v1")
    monkeypatch.setenv("TIANXUAN_CHAT_MODEL_KEY", "workspace-fixture")
    store = Tianxuan(str(tmp_path / "workspace.sqlite"))
    actor = store.register("Pending", "pending@example.invalid", "password123")["user_id"]
    auth = headers(store, actor, actor)
    started, release = Event(), Event()
    called = []

    def send(request):
        called.append(request.url)
        started.set()
        assert release.wait(timeout=10)
        return httpx.Response(
            200,
            json={
                "model": "test-model",
                "choices": [{"message": {"content": "late reply"}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7},
            },
        )

    gateway = ModelGateway(":memory:", transport=httpx.MockTransport(send))
    with TestClient(create_app(store, gateway=gateway)) as client, ThreadPoolExecutor(max_workers=1) as pool:
        key = str(uuid4())
        get_state(client.post(ROOT, headers=auth, json={"id": key}), 201)
        url = f"{ROOT}/{key}"
        turn = {"id": str(uuid4()), "content": "Wait for the previous send", "expected_version": 0}
        submitted = pool.submit(client.post, url + "/turns", headers=auth, json=turn)
        try:
            assert started.wait(timeout=5)
            pending = get_state(client.get(url, headers=auth))
            assert pending["turns"][0]["state"] == "pending"
            assert get_state(client.post(url + "/turns", headers=auth, json=turn)) == pending
            assert (
                client.post(
                    url + "/turns",
                    headers=auth,
                    json={
                        **turn,
                        "id": str(uuid4()),
                        "expected_version": pending["version"],
                    },
                ).status_code
                == 409
            )
            stopped = get_state(
                client.post(
                    f"{url}/turns/{turn['id']}/stop-waiting",
                    headers=auth,
                    json={"expected_version": pending["version"]},
                )
            )
        finally:
            release.set()
        assert get_state(submitted.result(5)) == stopped
        assert stopped["turns"][0]["state"] == "unanswered"
        assert stopped["turns"][0]["answer"] is None
        assert len(called) == 1
    store.db.close()
    gateway.close()
