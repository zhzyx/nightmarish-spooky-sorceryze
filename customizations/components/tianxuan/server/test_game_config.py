"""Configuration saves, collaborative conflict, runtime receipts and ACL boundaries."""

from copy import deepcopy

import pytest
from api import create_app
from fastapi.testclient import TestClient
from game_config_schema import config_markdown, parse_config, validate_features
from starlette.websockets import WebSocketDisconnect
from tianxuan_core import Tianxuan


def features():
    return [
        {
            "id": "combat",
            "name": "战斗",
            "entries": [
                {
                    "id": "damage",
                    "name": "伤害",
                    "kind": "parameter",
                    "type": "number",
                    "value": 10,
                    "default": 10,
                    "min": 0,
                    "max": 100,
                },
                {"id": "enemy", "name": "敌人", "kind": "content", "type": "json", "value": {"hp": 20}, "default": {}},
                {
                    "id": "ref",
                    "name": "引用",
                    "kind": "parameter",
                    "type": "reference",
                    "value": {"feature_id": "combat", "entry_id": "enemy"},
                    "default": {"feature_id": "combat", "entry_id": "enemy"},
                },
            ],
        }
    ]


@pytest.fixture
def setup():
    store = Tianxuan()
    owner = store.register("config", "owner@example.com", "password")["user_id"]
    member = store.add_member(owner, "member@example.com", "password")["user_id"]
    viewer = store.add_member(owner, "viewer@example.com", "password", role="viewer")["user_id"]
    other = store.register("other", "other@example.com", "password")["user_id"]
    with TestClient(create_app(store)) as client:
        yield store, client, owner, member, viewer, other


def create(client, owner):
    response = client.post(
        "/api/v1/game-config/projects", headers={"X-Actor": owner}, json={"title": "测试游戏", "features": features()}
    )
    assert response.status_code == 201, response.text
    return response.json()


def save(client, actor, project, value, version=None):
    edited = deepcopy(project["features"])
    edited[0]["entries"][0]["value"] = value
    return client.put(
        f"/api/v1/game-config/projects/{project['id']}",
        headers={"X-Actor": actor},
        json={"title": project["title"], "features": edited, "expected_version": version or project["version"]},
    )


def receive(ws, kind):
    for _ in range(12):
        packet = ws.receive_json()
        if packet["type"] == kind:
            return packet
    raise AssertionError(kind)


@pytest.mark.parametrize(
    "change",
    [
        lambda f: f[0]["entries"][0].update(value=True),
        lambda f: f[0]["entries"][0].update(value=101),
        lambda f: f[0]["entries"][0].update(default=-1),
        lambda f: f[0]["entries"][0].update(value=float("nan")),
        lambda f: f[0]["entries"].append(deepcopy(f[0]["entries"][0])),
        lambda f: f.append(deepcopy(f[0])),
        lambda f: f[0]["entries"].pop(1),
        lambda f: f[0]["entries"][0].update(type="enum", options=["a", "a"]),
        lambda f: f[0]["entries"][0].update(id="../outside"),
        lambda f: f[0]["entries"][0].update(unknown=True),
    ],
)
def test_validation_rejects_invalid_snapshots(change):
    value = features()
    change(value)
    with pytest.raises(ValueError):
        validate_features(value)


def test_markdown_roundtrip_and_duplicate_json_fields():
    assert parse_config(config_markdown(features())) == features()
    with pytest.raises(ValueError):
        parse_config('```game-config\n{"schema_version":1,"schema_version":1,"features":[]}\n```')


@pytest.mark.parametrize("option", ["", "line\nbreak", "line\rbreak"])
def test_enum_options_are_lossless_in_line_editor(option):
    value = features()
    value[0]["entries"] = [
        {
            "id": "mode",
            "name": "模式",
            "kind": "parameter",
            "type": "enum",
            "value": "alpha",
            "default": "alpha",
            "options": ["alpha", option],
        }
    ]
    with pytest.raises(ValueError, match="single-line"):
        validate_features(value)


@pytest.mark.parametrize("number", [2**53, -(2**53), float(2**53), 1e100])
@pytest.mark.parametrize("location", ["value", "default", "min", "max", "nested_json"])
def test_nonportable_numbers_are_rejected(number, location):
    value = features()
    if location == "nested_json":
        value[0]["entries"][1]["value"] = {"nested": [number]}
    else:
        value[0]["entries"][0][location] = number
    with pytest.raises(ValueError, match="safe integer"):
        validate_features(value)


def test_safe_integer_boundary_and_fraction_remain_valid():
    value = features()
    value[0]["entries"][1]["value"] = {"ids": [2**53 - 1, -(2**53 - 1)], "fraction": 0.125}
    assert parse_config(config_markdown(value)) == value


def test_conflict_validation_generic_editor_restore_and_history(setup):
    store, client, owner, member, _, _ = setup
    project = create(client, owner)
    assert save(client, owner, project, 25).status_code == 200
    assert save(client, member, project, 30).status_code == 409
    assert save(client, owner, project, 101, version=2).status_code == 400
    path = f"/api/v1/docs/{project['id']}"
    invalid = client.patch(path, headers={"X-Actor": owner}, json={"body_md": "broken", "expected_version": 2})
    assert invalid.status_code == 400
    assert store.get_doc(project["id"])["version"] == 2
    restored = client.post(path + "/versions/1/restore", headers={"X-Actor": owner}, json={"expected_version": 2})
    assert restored.status_code == 200, restored.text
    current = client.get(f"/api/v1/game-config/projects/{project['id']}", headers={"X-Actor": owner}).json()
    assert current["version"] == 3 and current["features"][0]["entries"][0]["value"] == 10
    history = client.get(path + "/versions", headers={"X-Actor": owner}).json()["versions"]
    assert [row["version"] for row in history] == [1, 2, 3]


def test_acl_tenant_and_readonly(setup):
    _, client, owner, member, viewer, other = setup
    project = create(client, owner)
    assert save(client, viewer, project, 20).status_code == 403
    path = f"/api/v1/game-config/projects/{project['id']}"
    assert client.get(path, headers={"X-Actor": other}).status_code in (403, 404)
    assert client.get("/api/v1/game-config/projects", headers={"X-Actor": other}).json() == {"projects": []}
    private = client.patch(
        f"/api/v1/docs/{project['id']}/visibility", headers={"X-Actor": owner}, json={"visibility": "private"}
    )
    assert private.status_code == 200, private.text
    assert client.get(path, headers={"X-Actor": member}).status_code == 403
    assert client.get("/api/v1/game-config/projects", headers={"X-Actor": member}).json() == {"projects": []}


def test_form_save_preserves_collaborative_document_prose(setup):
    store, client, owner, member, _, _ = setup
    project = create(client, owner)
    prefix, suffix = "# 战斗设计\n\n保留 `说明` 与链接。\n", "\n\n## 协作记录\n保留尾部文字。\n"
    body = prefix + config_markdown(project["features"]) + suffix
    store.update_doc(member, project["id"], body, 1)
    assert save(client, owner, project, 20).status_code == 409
    assert store.get_doc(project["id"])["body_md"] == body
    project["version"], project["title"] = 2, "新标题"
    assert save(client, owner, project, 20).status_code == 200
    current = store.get_doc(project["id"])
    expected = deepcopy(project["features"])
    expected[0]["entries"][0]["value"] = 20
    assert current["body_md"] == prefix + config_markdown(expected) + suffix
    assert current["title"] == "新标题" and current["version"] == 3


def test_live_update_ack_reconnect_and_no_false_application(setup):
    _, client, owner, _, viewer, _ = setup
    project = create(client, owner)
    path = f"/api/v1/ws/game-config/{project['id']}?kind=runtime"
    with client.websocket_connect(path) as game:
        game.send_json({"type": "subscribe", "actor": viewer, "name": "Godot test"})
        assert receive(game, "snapshot")["project"]["version"] == 1
        initial = receive(game, "clients")["clients"]
        assert initial[0]["status"] == "pending"
        game.send_json({"type": "applied", "version": 99})
        assert receive(game, "error")
        game.send_json({"type": "applied", "version": 1})
        assert receive(game, "clients")["clients"][0]["status"] == "applied"
        assert save(client, owner, project, 28).status_code == 200
        changed = receive(game, "snapshot")["project"]
        assert changed["version"] == 2 and changed["features"][0]["entries"][0]["value"] == 28
        assert receive(game, "clients")["clients"][0]["status"] == "pending"
        game.send_json({"type": "applied", "version": 1})
        assert receive(game, "error")
        game.send_json({"type": "failed", "version": 2, "error": "business validation failed"})
        failed = receive(game, "clients")["clients"][0]
        assert failed["status"] == "failed" and failed["version"] == 1
    assert client.get(f"/api/v1/game-config/projects/{project['id']}/clients", headers={"X-Actor": owner}).json() == {
        "clients": []
    }
    with client.websocket_connect(path) as game:
        game.send_json({"type": "subscribe", "actor": viewer})
        assert receive(game, "snapshot")["project"]["version"] == 2
        assert receive(game, "clients")["clients"][0]["status"] == "pending"


def test_bearer_socket_and_revocation(setup, monkeypatch):
    store, client, owner, _, _, _ = setup
    project = create(client, owner)
    token = store.issue_session(owner)
    monkeypatch.delenv("TIANXUAN_ALLOW_ACTOR_HEADER")
    with client.websocket_connect(f"/api/v1/ws/game-config/{project['id']}") as ws:
        ws.send_json({"type": "subscribe", "token": token})
        assert receive(ws, "snapshot")["project"]["id"] == project["id"]
        receive(ws, "clients")
        store.revoke_session(token)
        ws.send_json({"type": "ping"})
        with pytest.raises(WebSocketDisconnect):
            for _ in range(3):
                ws.receive_json()


def test_other_worker_document_write_is_observed(tmp_path):
    db = str(tmp_path / "config.db")
    first, second = Tianxuan(db), Tianxuan(db)
    owner = first.register("shared", "shared@example.com", "password")["user_id"]
    with TestClient(create_app(first)) as client:
        project = create(client, owner)
        with client.websocket_connect(f"/api/v1/ws/game-config/{project['id']}") as ws:
            ws.send_json({"type": "subscribe", "actor": owner})
            receive(ws, "snapshot")
            receive(ws, "clients")
            edited = features()
            edited[0]["entries"][0]["value"] = 42
            second.update_doc(owner, project["id"], config_markdown(edited), 1)
            assert receive(ws, "snapshot")["project"]["features"][0]["entries"][0]["value"] == 42


def test_config_ui_save_notifies_existing_document_editor(setup):
    _, client, owner, _, _, _ = setup
    project = create(client, owner)
    with client.websocket_connect(f"/api/v1/ws/docs/{project['id']}?actor={owner}") as ws:
        receive(ws, "snapshot")
        receive(ws, "presence")
        assert save(client, owner, project, 33).status_code == 200
        assert receive(ws, "changed") == {"type": "changed"}


def test_account_cookie_and_personal_key_runtime(monkeypatch):
    monkeypatch.setenv("TIANXUAN_AUTH_MODE", "accounts")
    monkeypatch.setenv("TIANXUAN_REQUIRE_KEYS", "0")
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://testserver")
    store = Tianxuan()
    registered = store.register("accounts", "account@example.com", "password")
    owner = registered["user_id"]
    monkeypatch.setenv("TIANXUAN_TENANT_ID", registered["tenant_id"])
    with TestClient(create_app(store), base_url="https://testserver") as client:
        origin = {"Origin": "https://testserver"}
        assert (
            client.post(
                "/api/v1/auth/session", headers=origin, json={"email": "account@example.com", "password": "password"}
            ).status_code
            == 200
        )
        response = client.post(
            "/api/v1/game-config/projects", headers=origin, json={"title": "Cookie", "features": features()}
        )
        assert response.status_code == 201, response.text
        project = response.json()
        with client.websocket_connect(f"wss://testserver/api/v1/ws/game-config/{project['id']}", headers=origin) as ws:
            ws.send_json({"type": "subscribe"})
            assert receive(ws, "snapshot")["project"]["id"] == project["id"]
        key = store.issue_access_key(owner, owner, "runtime")["key"]
        client.cookies.clear()
        with client.websocket_connect(
            f"/api/v1/ws/game-config/{project['id']}?kind=runtime", headers={"Authorization": f"Bearer {key}"}
        ) as ws:
            ws.send_json({"type": "subscribe", "name": "Production key"})
            assert receive(ws, "snapshot")["project"]["version"] == 1
            receive(ws, "clients")
            ws.send_json({"type": "applied", "version": 1})
            assert receive(ws, "clients")["clients"][0]["status"] == "applied"


def test_new_account_workspace_config_remains_tenant_isolated(monkeypatch):
    monkeypatch.setenv("TIANXUAN_AUTH_MODE", "accounts")
    monkeypatch.setenv("TIANXUAN_REQUIRE_KEYS", "0")
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://testserver")
    monkeypatch.setenv("TIANXUAN_TENANT_ID", "original-deployment")
    store = Tianxuan()
    owner = store.register("new", "new@example.com", "password")["user_id"]
    other = store.register("other", "other@example.com", "password")["user_id"]
    with TestClient(create_app(store), base_url="https://testserver") as client:
        headers = {"Authorization": "Bearer " + store.issue_session(owner)}
        response = client.post(
            "/api/v1/game-config/projects", headers=headers, json={"title": "New workspace", "features": features()}
        )
        assert response.status_code == 201, response.text
        other_headers = {"Authorization": "Bearer " + store.issue_session(other)}
        assert client.get("/api/v1/game-config/projects", headers=other_headers).json() == {"projects": []}
        assert client.get(
            f"/api/v1/game-config/projects/{response.json()['id']}", headers=other_headers
        ).status_code in (403, 404)
