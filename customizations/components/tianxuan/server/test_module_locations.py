"""Private module work locations through the authenticated product routes."""

from uuid import uuid4

from api import create_app
from fastapi.testclient import TestClient
from native_store import NativeStore
from tianxuan_core import Tianxuan

MODULES = "/api/v1/business-modules"
PROJECT = {"project": "studio/game"}
PASSWORD = "location-fixture-password"


def login(client, email):
    result = client.post("/api/v1/auth/session", json={"email": email, "password": PASSWORD})
    assert result.status_code == 200, result.text
    return {"Authorization": "Bearer " + result.json()["token"]}


def location(module):
    return f"{MODULES}/{module}/location"


def expect_location(response, expected):
    assert response.status_code == 200, response.text
    assert response.json() == {"location": expected}
    assert "no-store" in response.headers["Cache-Control"]


def test_switch_module_reopen_and_switch_accounts(tmp_path, monkeypatch):
    database = str(tmp_path / "domain.db")
    store = Tianxuan(database)
    first = store.register("Studio", "alice@example.org", PASSWORD)
    alice = first["user_id"]
    store.add_member(alice, "bob@example.org", PASSWORD)
    monkeypatch.setenv("TIANXUAN_AUTH_MODE", "accounts")
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://studio.example")
    monkeypatch.setenv("TIANXUAN_TENANT_ID", first["tenant_id"])

    def application(domain):
        return create_app(domain, native_store=NativeStore(tmp_path / "native.db"), native_only=True)

    with TestClient(application(store)) as client:
        assert client.get(location("default"), headers={"X-Actor": alice}).status_code == 401
        a_headers = login(client, "alice@example.org")
        b_headers = login(client, "bob@example.org")
        side = client.post(MODULES, params=PROJECT, headers=a_headers, json={"name": "Scenes", "call_id": "side"})
        assert side.status_code == 200
        side_id = side.json()["id"]
        first_issue = store.create_issue(alice, "Lighting", **PROJECT)
        second_issue = store.create_issue(alice, "Materials", module_id=side_id, **PROJECT)
        conversation = str(uuid4())
        assert (
            client.post("/api/v1/workspace/conversations", headers=a_headers, json={"id": conversation}).status_code
            == 201
        )
        main_state = {"issue_id": first_issue["id"], "conversation_id": conversation, "position": "issue/comments#7"}
        side_state = {"issue_id": second_issue["id"], "conversation_id": None, "position": "issue/details"}
        bob_state = {"issue_id": first_issue["id"], "conversation_id": None, "position": "issue/history"}

        def get(module, headers, params=PROJECT):
            return client.get(location(module), params=params, headers=headers)

        def put(module, headers, state):
            return client.put(location(module), params=PROJECT, headers=headers, json=state)

        expect_location(get("default", a_headers), None)
        expect_location(put("default", a_headers, main_state), main_state)
        expect_location(get(side_id, a_headers), None)
        expect_location(put(side_id, a_headers, side_state), side_state)
        expect_location(get("default", a_headers), main_state)
        expect_location(get("default", a_headers, {"project": "studio/other"}), None)
        assert get(side_id, a_headers, {"project": "studio/other"}).status_code == 404
        assert put(side_id, a_headers, main_state).status_code == 404
        expect_location(get(side_id, a_headers), side_state)

        expect_location(get("default", b_headers), None)
        assert put("default", b_headers, main_state).status_code == 404
        assert put("default", b_headers, {**bob_state, "actor": alice}).status_code == 422
        expect_location(put("default", b_headers, bob_state), bob_state)
        expect_location(get("default", a_headers), main_state)
        assert client.post("/api/v1/auth/logout", headers=a_headers).status_code == 200
        assert get("default", a_headers).status_code == 401
    store.db.close()

    reopened = Tianxuan(database)
    with TestClient(application(reopened)) as client:
        a_headers = login(client, "alice@example.org")
        for module, headers, expected in (
            ("default", a_headers, main_state),
            (side_id, a_headers, side_state),
            ("default", b_headers, bob_state),
            (side_id, b_headers, None),
        ):
            expect_location(client.get(location(module), params=PROJECT, headers=headers), expected)
        # Replacing a position is atomic and an identical retry leaves that position intact.
        updated = {**main_state, "position": "issue/comments#12"}
        for _ in range(2):
            expect_location(client.put(location("default"), params=PROJECT, headers=a_headers, json=updated), updated)
        expect_location(client.get(location("default"), params=PROJECT, headers=b_headers), bob_state)
    reopened.db.close()


def test_location_rechecks_issue_ancestors_and_module(tmp_path):
    store = Tianxuan(str(tmp_path / "domain.db"))
    owner = store.register("Studio", "owner@example.org", PASSWORD)["user_id"]
    reader = store.add_member(owner, "reader@example.org", PASSWORD)["user_id"]
    requirement = store.create_requirement(owner, "req", "Lighting", "scope", "design", "done")
    parent = store.create_issue(owner, "Parent", requirement_id=requirement["id"], **PROJECT)
    child = store.create_issue(owner, "Child", parent_id=parent["id"])
    side = store.create_business_module(owner, PROJECT["project"], "Side", call_id="side")
    private = {"issue_id": child["id"], "conversation_id": None, "position": "issue/design#private-anchor"}
    url = location("default")
    with TestClient(create_app(store)) as client:
        reader_headers = {"Authorization": "Bearer " + store.issue_session(reader)}
        expect_location(client.put(url, params=PROJECT, headers=reader_headers, json=private), private)
        store.set_visibility(owner, requirement["id"], "private")
        expect_location(client.get(url, params=PROJECT, headers=reader_headers), None)
        assert client.put(url, params=PROJECT, headers=reader_headers, json=private).status_code == 403
        store.share_doc(owner, requirement["id"], reader, "read")
        expect_location(client.get(url, params=PROJECT, headers=reader_headers), private)
        store.set_issue_module(owner, child["id"], PROJECT["project"], side["id"])
        expect_location(client.get(url, params=PROJECT, headers=reader_headers), None)
        assert client.put(url, params=PROJECT, headers=reader_headers, json=private).status_code == 404
        expect_location(client.get(location(side["id"]), params=PROJECT, headers=reader_headers), None)
    store.db.close()


def test_default_module_isolation_and_legacy_actor_header(monkeypatch):
    monkeypatch.setenv("TIANXUAN_ALLOW_ACTOR_HEADER", "1")
    store = Tianxuan()
    first = store.register("One", "one@example.org", PASSWORD)["user_id"]
    second = store.register("Two", "two@example.org", PASSWORD)["user_id"]
    viewer = store.add_member(first, "viewer@example.org", PASSWORD, role="viewer")["user_id"]
    private_issue = store.create_issue(first, "Private to One", **PROJECT)["id"]
    with TestClient(create_app(store)) as client:
        url = location("default")
        own = {"Authorization": "Bearer " + store.issue_session(first)}
        foreign = {"Authorization": "Bearer " + store.issue_session(second)}
        read_only = {"Authorization": "Bearer " + store.issue_session(viewer)}
        state = {"issue_id": private_issue, "conversation_id": None, "position": "issue/body"}
        expect_location(client.put(url, params=PROJECT, headers=own, json=state), state)
        assert client.get(url, params=PROJECT, headers={"X-Actor": first}).status_code == 401
        expect_location(client.get(url, params=PROJECT, headers={**foreign, "X-Actor": first}), None)
        assert client.put(url, params=PROJECT, headers=foreign, json=state).status_code == 404
        assert client.put(url, params=PROJECT, headers=read_only, json=state).status_code == 403
        missing_chat = {**state, "conversation_id": str(uuid4())}
        assert client.put(url, params=PROJECT, headers=own, json=missing_chat).status_code == 404
        expect_location(client.get(url, params=PROJECT, headers=own), state)
        foreign_state = {"issue_id": None, "conversation_id": None, "position": "module/overview"}
        expect_location(client.put(url, params=PROJECT, headers=foreign, json=foreign_state), foreign_state)
        expect_location(client.get(url, params=PROJECT, headers=foreign), foreign_state)
        expect_location(client.get(url, params=PROJECT, headers=own), state)
    store.db.close()
