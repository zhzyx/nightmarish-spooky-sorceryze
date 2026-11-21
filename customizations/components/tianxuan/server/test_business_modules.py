"""Project-scoped business modules through the same authenticated API used by issue clients."""

import json

from api import create_app
from fastapi.testclient import TestClient
from native_store import NativeStore
from tianxuan_core import Tianxuan

MODULES = "/api/v1/business-modules"


def test_same_name_rename_and_reference_survive_restart(tmp_path):
    database = str(tmp_path / "domain.db")
    store = Tianxuan(database)
    actor = store.register("studio", "maker@example.org", "fixture-pass")["user_id"]
    auth = {"Authorization": "Bearer " + store.issue_session(actor)}
    project = {"project": "studio/game"}
    native = NativeStore(tmp_path / "native.db")
    with TestClient(create_app(store, native_store=native, native_only=True), headers=auth) as client:

        def create(key):
            response = client.post(MODULES, params=project, json={"name": "场景", "call_id": key})
            assert response.status_code == 200, response.text
            return response.json()

        first, second = create("one"), create("two")
        assert first["id"] != second["id"]
        assert create("one") == first
        payload = {"title": "装饰场景", **project, "module_id": first["id"]}
        request = {"name": "issue.create", "payload": payload, "call_id": "build"}
        issue = client.post("/api/v1/tools", json=request).json()
        assert (issue["project"], issue["module_id"]) == (project["project"], first["id"])
        renamed = client.patch(MODULES + "/" + first["id"], params=project, json={"name": "城镇"}).json()
        assert renamed == {**first, "name": "城镇"}
        assert create("one") == first  # Replayed receipt must not undo the rename.
    store.db.close()

    reopened = Tianxuan(database)
    with TestClient(
        create_app(reopened, native_store=NativeStore(native.database), native_only=True), headers=auth
    ) as client:
        modules = client.get(MODULES, params=project).json()["modules"]
        assert {item["id"]: item["name"] for item in modules} == {
            "default": "默认模块",
            first["id"]: "城镇",
            second["id"]: "场景",
        }
        assert client.get("/api/v1/issues").json()["issues"] == [issue]
        assert client.post("/api/v1/tools", json=request).json() == issue
    reopened.db.close()


def test_project_tenant_and_role_scope():
    store = Tianxuan()
    actor = store.register("studio", "owner@example.org", "fixture-pass")["user_id"]
    other = store.register("another", "other@example.org", "fixture-pass")["user_id"]
    viewer = store.add_member(actor, "view@example.org", "fixture-pass", role="viewer")["user_id"]
    module = store.create_business_module(actor, "game", "战斗", call_id="create")
    with TestClient(create_app(store)) as client:
        url = MODULES + "/" + module["id"]
        for account, project in ((actor, "other-game"), (other, "game")):
            headers = {"X-Actor": account}
            scope = {"project": project}
            assert client.get(MODULES, params=scope, headers=headers).json()["modules"] == [
                {"id": "default", **scope, "name": "默认模块"}
            ]
            assert client.patch(url, params=scope, headers=headers, json={"name": "x"}).status_code == 404
            request = {"name": "issue.create", "payload": {"title": "x", **scope, "module_id": module["id"]}}
            assert client.post("/api/v1/tools", headers=headers, json=request).status_code == 404
        headers = {"X-Actor": viewer}
        scope = {"project": "game"}
        assert module in client.get(MODULES, params=scope, headers=headers).json()["modules"]
        assert client.patch(url, params=scope, headers=headers, json={"name": "x"}).status_code == 403
        assert (
            client.post(MODULES, params=scope, headers=headers, json={"name": "x", "call_id": "x"}).status_code == 403
        )
    store.db.close()


def test_existing_database_and_create_receipt_migrate_once(tmp_path):
    database = str(tmp_path / "old.db")
    store = Tianxuan(database)
    owner = store.register("studio", "maker@example.org", "fixture-pass")
    actor = owner["user_id"]
    ordinary = store.create_issue(actor, "old", call_id="old-call")
    migrated = store.create_issue(actor, "imported")
    child = store.create_issue(actor, "child", parent_id=migrated["id"])
    # The previous schema had neither reference field; migration.start kept the project in its receipt.
    store.db.execute("ALTER TABLE issues DROP COLUMN project")
    store.db.execute("ALTER TABLE issues DROP COLUMN module_id")
    store.db.execute("DROP TABLE business_modules")
    store.db.execute(
        "CREATE TABLE migration_starts(tenant, actor, call_id, request, result, PRIMARY KEY(tenant,actor,call_id))"
    )
    store.db.execute(
        "INSERT INTO migration_starts VALUES(?,?,?,?,?)",
        (
            owner["tenant_id"],
            actor,
            "m",
            json.dumps({"project": "team/other"}),
            json.dumps({"issue_id": migrated["id"]}),
        ),
    )
    old_result = {key: value for key, value in ordinary.items() if key not in ("project", "module_id")}
    store.db.execute("UPDATE tool_receipts SET result_json=? WHERE call_id='old-call'", (json.dumps(old_result),))
    store.db.commit()
    store.db.close()

    for _ in range(2):
        upgraded = Tianxuan(database)
        rows = upgraded.list_issues(actor)
        assert [(row["id"], row["project"], row["module_id"]) for row in rows] == [
            (ordinary["id"], "workspace", "default"),
            (migrated["id"], "team/other", "default"),
            (child["id"], "team/other", "default"),
        ]
        assert upgraded.create_issue(actor, "old", call_id="old-call") == old_result
        upgraded.rename_business_module(actor, "team/other", "default", "迁入")
        assert upgraded.list_business_modules(actor, "workspace")[0]["name"] == "默认模块"
        assert upgraded.list_business_modules(actor, "team/other")[0]["name"] == "迁入"
        upgraded.db.close()
