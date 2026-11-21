"""Module-scoped issue lookup and reassignment through authenticated product routes."""

from api import create_app
from fastapi.testclient import TestClient
from native_store import NativeStore
from tianxuan_core import Tianxuan

ISSUES = "/api/v1/issues"
TOOLS = "/api/v1/tools"
PROJECT = {"project": "studio/game"}


def test_same_title_module_index_and_restart(tmp_path):
    database = str(tmp_path / "domain.db")
    native_db = tmp_path / "native.db"
    store = Tianxuan(database)
    owner = store.register("studio", "maker@example.org", "fixture-pass")["user_id"]
    headers = {"Authorization": "Bearer " + store.issue_session(owner)}
    with TestClient(
        create_app(store, native_store=NativeStore(native_db), native_only=True), headers=headers
    ) as client:
        modules = []
        for key in ("main", "side"):
            response = client.post("/api/v1/business-modules", params=PROJECT, json={"name": "场景", "call_id": key})
            assert response.status_code == 200, response.text
            modules.append(response.json()["id"])
        main, side = modules
        issues = []
        for key, module in (("first", main), ("second", main), ("third", side)):
            response = client.post(
                TOOLS,
                json={
                    "name": "issue.create",
                    "call_id": key,
                    "payload": {**PROJECT, "module_id": module, "title": "检查"},
                },
            )
            assert response.status_code == 200, response.text
            issues.append(response.json())
        first, second, third = issues
        assert len({row["number"] for row in issues}) == len({row["id"] for row in issues}) == 3
        for row in issues:
            assert client.get(f"{ISSUES}/{row['id']}").json() == row
        scope = {**PROJECT, "module_id": main}
        assert client.get(ISSUES, params=scope).json()["issues"] == [first, second]
        assert client.post(TOOLS, json={"name": "issue.list", "payload": scope}).json()["issues"] == [first, second]
        target = f"{ISSUES}/{second['id']}/module"
        moved = client.put(target, params=PROJECT, json={"module_id": side}).json()
        assert {**moved, "module_id": main, "updated_at": second["updated_at"]} == second
        assert moved["module_id"] == side
        assert client.put(target, params=PROJECT, json={"module_id": side}).json() == moved
    store.db.close()

    reopened = Tianxuan(database)
    with TestClient(
        create_app(reopened, native_store=NativeStore(native_db), native_only=True), headers=headers
    ) as client:
        for module, expected in ((main, [first]), (side, [moved, third]), ("default", [])):
            scope = {**PROJECT, "module_id": module}
            assert client.get(ISSUES, params=scope).json()["issues"] == expected
            assert client.post(TOOLS, json={"name": "issue.list", "payload": scope}).json()["issues"] == expected
        assert client.get(ISSUES).json()["issues"] == [first, moved, third]
        assert client.get(f"{ISSUES}/{second['id']}").json() == moved
    reopened.db.close()


def test_scoped_issues_and_acl():
    store = Tianxuan()
    owner = store.register("studio", "owner@example.org", "fixture-pass")["user_id"]
    other = store.register("other", "other@example.org", "fixture-pass")["user_id"]
    editor = store.add_member(owner, "editor@example.org", "fixture-pass", role="editor")["user_id"]
    viewer = store.add_member(owner, "viewer@example.org", "fixture-pass", role="viewer")["user_id"]
    module = store.create_business_module(owner, PROJECT["project"], "场景", call_id="one")["id"]
    requirement = store.create_requirement(owner, "req", "R", "ok", "scope", "done")
    store.set_visibility(owner, requirement["id"], "private")
    root = store.create_issue(owner, "same", **PROJECT, requirement_id=requirement["id"])
    child = store.create_issue(owner, "same", parent_id=root["id"])
    public = store.create_issue(owner, "same", **PROJECT)
    elsewhere = store.create_issue(owner, "same", project="other-game")
    workspace = store.create_issue(owner, "same")
    foreign = store.create_issue(other, "same", **PROJECT)

    with TestClient(create_app(store)) as client:
        params = {**PROJECT, "module_id": "default"}
        client.headers["Authorization"] = "Bearer " + store.issue_session(owner)
        assert client.get(ISSUES, params={"module_id": "default"}).json()["issues"] == [workspace]
        assert client.get(ISSUES, params={"project": "other-game", "module_id": "default"}).json()["issues"] == [
            elsewhere
        ]
        assert client.get(ISSUES, params={**params, "requirement_id": requirement["id"], "status": "backlog"}).json()[
            "issues"
        ] == [root]
        assert client.get(ISSUES, params={**params, "status": "done"}).json()["issues"] == []
        url = f"{ISSUES}/{public['id']}/module"
        assert client.put(url, params={"project": "other-game"}, json={"module_id": "default"}).status_code == 404
        assert (
            client.put(
                f"{ISSUES}/{elsewhere['id']}/module", params={"project": "other-game"}, json={"module_id": module}
            ).status_code
            == 404
        )
        assert client.get(ISSUES, params={"project": "other-game", "module_id": module}).status_code == 404
        assert client.get(f"{ISSUES}/{foreign['id']}").status_code == 404
        assert (
            client.put(f"{ISSUES}/{foreign['id']}/module", params=PROJECT, json={"module_id": module}).status_code
            == 404
        )

        client.headers["Authorization"] = "Bearer " + store.issue_session(viewer)
        assert client.get(ISSUES, params=params).json()["issues"] == [public]
        assert client.get(f"{ISSUES}/{public['id']}").json() == public
        assert client.put(url, params=PROJECT, json={"module_id": module}).status_code == 403

        client.headers["Authorization"] = "Bearer " + store.issue_session(editor)
        assert client.post(TOOLS, json={"name": "issue.list", "payload": params}).json()["issues"] == [public]
        child_url = f"{ISSUES}/{child['id']}"
        assert client.get(child_url).status_code == 403
        assert client.put(child_url + "/module", params=PROJECT, json={"module_id": module}).status_code == 403
        store.share_doc(owner, requirement["id"], editor, "read")
        assert client.get(child_url).json() == child
        assert client.put(child_url + "/module", params=PROJECT, json={"module_id": module}).status_code == 403
        assert client.get(ISSUES, params=params).json()["issues"] == [root, child, public]
        assert client.put(url, params=PROJECT, json={"module_id": module}).json()["id"] == public["id"]
        assert client.get(ISSUES, params=params).json()["issues"] == [root, child]
    store.db.close()
