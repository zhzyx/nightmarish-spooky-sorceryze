"""Verify workspace projections against the actual entry, task and native head stores."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan

BASE = "/api/v1/workspace"


@pytest.fixture(autouse=True)
def _native_paths(monkeypatch):
    for name in ("duobao", "sinan-workorders"):
        monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / name))


def _client(domain, entry=None, native=None):
    from workspace_inventory import create_workspace_inventory_router

    app = FastAPI()
    app.state.store = domain
    app.include_router(create_workspace_inventory_router(entry, native))
    return TestClient(app)


def _bearer(domain, actor):
    return {"Authorization": f"Bearer {domain.issue_session(actor)}"}


def test_native_modules_use_tenant_and_live_requirement_acl(tmp_path, monkeypatch):
    from native_store import NativeStore

    monkeypatch.setattr("workspace_inventory.PAGE_SIZE", 1)
    domain = Tianxuan(str(tmp_path / "domain.db"))
    native = NativeStore(tmp_path / "native.db")
    owner = domain.register("First", "admin@example.test", "password123")
    actor, tenant = owner["user_id"], owner["tenant_id"]
    teammate = domain.add_member(actor, "reader@example.test", "password123")
    other = domain.register("Second", "other@example.test", "password123")
    requirement = domain.create_requirement(actor, "private", "Private", "outcome", "scope", "criteria")
    module = domain.bind_native_requirement(actor, requirement["id"])
    domain.set_visibility(actor, requirement["id"], "private")

    def seed(tenant_id, author, name):
        return native.submit(
            tenant_id,
            author,
            name,
            [{"module": name, "base": None, "reads": None, "edits": {"object.txt": b"data"}}],
        )["revisions"][name]

    first = seed(tenant, actor, "a-module")
    second = seed(tenant, actor, "z-module")
    seed(tenant, actor, module)
    seed(other["tenant_id"], other["user_id"], "other-module")

    with _client(domain, native=native) as client:
        assert client.get(f"{BASE}/modules").status_code == 401
        headers = _bearer(domain, teammate["user_id"])
        assert client.get(f"{BASE}/modules", headers=headers).json() == {
            "available": True,
            "modules": [{"module": "a-module", "revision": first}],
            "next_cursor": "a-module",
        }
        assert client.get(f"{BASE}/modules/after/a-module", headers=headers).json() == {
            "available": True,
            "modules": [{"module": "z-module", "revision": second}],
            "next_cursor": None,
        }
        assert (
            client.get(f"{BASE}/modules/after/a-module", headers=_bearer(domain, actor)).json()["modules"][0]["module"]
            == module
        )
        assert (
            client.get(f"{BASE}/modules", headers=_bearer(domain, other["user_id"])).json()["modules"][0]["module"]
            == "other-module"
        )
    domain.db.close()


def test_catalog_and_integration_modules_require_live_share_for_list_and_detail(tmp_path):
    from api import create_app
    from native_store import NativeStore

    domain = Tianxuan(str(tmp_path / "domain.db"))
    native = NativeStore(tmp_path / "native.db")
    owner = domain.register("First", "owner@example.test", "password123")
    actor, tenant = owner["user_id"], owner["tenant_id"]
    reader = domain.add_member(actor, "colleague@example.test", "password123")["user_id"]
    requirement = domain.create_requirement(actor, "workspace-native", "Private", "outcome", "scope", "criteria")
    issue = domain.create_issue(actor, "Private contribution", requirement_id=requirement["id"])
    domain.set_visibility(actor, requirement["id"], "private")
    dependency = domain.create_requirement(actor, "integration-input", "Input", "outcome", "scope", "criteria")
    dependency_module = domain.bind_native_requirement(actor, dependency["id"])
    domain.set_visibility(actor, dependency["id"], "private")
    product = "entry-" + "a" * 64
    module = product + "-code"
    integration = "b" * 64
    integrated_module = "integration-" + integration
    revs = native.submit(
        tenant,
        actor,
        "workspace-native-private",
        [
            {"module": name, "base": None, "reads": None, "edits": {"object.txt": b"private"}}
            for name in (module, integrated_module)
        ],
    )["revisions"]
    with domain._connection_lock:
        domain.db.execute("CREATE TABLE native_entry_catalogs(product TEXT PRIMARY KEY, origin TEXT NOT NULL)")
        domain.db.execute(
            "INSERT INTO native_entry_catalogs VALUES (?,?)",
            (
                product,
                json.dumps({
                    "tenant": tenant,
                    "requirement": requirement["id"],
                    "modules": {"code": module},
                }),
            ),
        )
        domain.db.execute("CREATE TABLE native_integrations(id TEXT PRIMARY KEY, plan TEXT NOT NULL)")
        domain.db.execute(
            "INSERT INTO native_integrations VALUES (?,?)",
            (
                integration,
                json.dumps({
                    "tenant": tenant,
                    "product": product,
                    "base": {},
                    "originals": [
                        {
                            "contract": {
                                "issue": issue["id"],
                                "source": {"definition": {"requirements": [{"id": requirement["id"]}]}},
                                "selected": {dependency_module: "c" * 64},
                            }
                        }
                    ],
                }),
            ),
        )

        domain.db.commit()

    with TestClient(create_app(domain, native_store=native, native_only=True)) as client:
        headers = _bearer(domain, reader)
        for shared, inputs_shared in ((False, False), (True, True), (True, False), (False, True)):
            if shared:
                domain.share_doc(actor, requirement["id"], reader)
            else:
                domain.unshare_doc(actor, requirement["id"], reader)
            if inputs_shared:
                domain.share_doc(actor, dependency["id"], reader)
            else:
                domain.unshare_doc(actor, dependency["id"], reader)
            page = client.get(f"{BASE}/modules", headers=headers)
            assert page.status_code == 200
            visible = {module} if shared else set()
            if shared and inputs_shared:
                visible.add(integrated_module)
            assert {item["module"] for item in page.json()["modules"]} == visible
            for name, revision in revs.items():
                response = client.get(f"/api/v1/native/modules/{name}/revisions/{revision}", headers=headers)
                assert response.status_code == (200 if name in visible else 403)
    domain.db.close()


def test_runs_project_real_owned_entries_and_authorized_tasks(tmp_path, monkeypatch):
    from native_execution_host import EntryLedger
    from native_workflow import NativeWorkflow

    monkeypatch.setattr("workspace_inventory.PAGE_SIZE", 1)
    domain = Tianxuan(str(tmp_path / "domain.db"))
    owner = domain.register("First", "admin@example.test", "password123")
    actor, tenant = owner["user_id"], owner["tenant_id"]
    teammate = domain.add_member(actor, "reader@example.test", "password123")["user_id"]
    other = domain.register("Second", "other@example.test", "password123")["user_id"]
    worker = SimpleNamespace(
        profiles={"local": None},
        workspace=SimpleNamespace(sources=lambda _tenant, selected: (selected, {})),
        installation=lambda _profile: "test-installation",
    )
    workflow = NativeWorkflow(domain, worker, SimpleNamespace(context=lambda *_: {}), None, lambda *_: True)
    ledger = EntryLedger(domain)
    entry = SimpleNamespace(domain=domain, workflow=workflow)

    headers = {person: _bearer(domain, person) for person in (actor, teammate, other)}

    def seed(person, key):
        req = domain.create_requirement(person, key, key, "outcome", "scope", "criteria")
        with ledger.transaction():
            run = ledger.enqueue(person, req["id"], key, {}, credential=headers[person]["Authorization"][7:])
        return req, run

    _, old_run = seed(actor, "older")
    latest, run = seed(actor, "latest")
    _, team_run = seed(teammate, "team")
    _, other_run = seed(other, "other")
    issue = domain.create_issue(actor, "child", requirement_id=latest["id"])
    task_id = workflow.authorize_task(
        actor,
        issue["id"],
        selected={"example": "0" * 64},
        writes={"example": "*"},
        dependencies={},
        profile="local",
        product="example",
        checks=["test"],
        mandate=run,
    )

    with _client(domain, entry=entry) as client:
        assert client.get(f"{BASE}/runs", headers=headers[actor]).json() == {
            "available": True,
            "runs": [
                {
                    "id": run,
                    "requirement_id": latest["id"],
                    "title": "latest",
                    "state": "pending",
                    "updated_at": None,
                    "tasks": [{"id": task_id, "issue_id": issue["id"], "title": issue["title"], "state": "ready"}],
                    "tasks_truncated": False,
                },
            ],
            "next_cursor": run,
        }
        assert client.get(f"{BASE}/runs/after/{run}", headers=headers[actor]).json()["runs"][0]["id"] == old_run
        assert client.get(f"{BASE}/runs/after/{old_run}", headers=headers[actor]).json()["runs"] == []
        assert client.get(f"{BASE}/runs/after/{team_run}", headers=headers[actor]).status_code == 404
        assert client.get(f"{BASE}/runs/after/{other_run}", headers=headers[actor]).status_code == 404
        assert client.get(f"{BASE}/runs", headers=headers[teammate]).json()["runs"][0]["id"] == team_run
        assert client.get(f"{BASE}/runs", headers=headers[other]).json()["runs"][0]["id"] == other_run
        shared = domain.create_requirement(actor, "shared", "Shared", "outcome", "scope", "criteria")
        with ledger.transaction():
            hidden_run = ledger.enqueue(
                teammate, shared["id"], "shared-run", {}, credential=headers[teammate]["Authorization"][7:]
            )
        assert client.get(f"{BASE}/runs", headers=headers[teammate]).json()["runs"][0]["id"] == hidden_run
        domain.set_visibility(actor, shared["id"], "private")
        assert client.get(f"{BASE}/runs", headers=headers[teammate]).json()["runs"][0]["id"] == team_run
        assert client.get(f"{BASE}/runs/after/{hidden_run}", headers=headers[teammate]).status_code == 404
    with _client(domain) as client:
        for name in ("runs", "modules"):
            assert client.get(f"{BASE}/{name}", headers=headers[actor]).json() == {
                "available": False,
                name: [],
                "next_cursor": None,
            }
    with domain._connection_lock:
        row = domain.db.execute("SELECT tenant,state FROM native_entry_intents WHERE id=?", (run,)).fetchone()
        assert tuple(row) == (tenant, "pending")
    domain.db.close()
