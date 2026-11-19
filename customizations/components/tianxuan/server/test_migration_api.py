from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


def test_authenticated_http_and_ai_select_new_task():
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))

    def account(email):
        actor = store.register(email, email, "fixture-password")["user_id"]
        return {"X-Actor": actor}

    admin = account("a@example.org")
    other = account("b@example.org")
    base = "/api/v1/migration"
    assert client.get(base + "/status").status_code == 400
    assert client.get(base + "/status", headers=admin).json() == {"available": False}
    task = {"project": "org/repo", "title": "new task", "call_id": "test-new"}
    assert (
        client
        .post(base + "/tasks", json=task, headers=admin)
        .json()["url"]
        .startswith("https://github.com/org/repo/issues/new?")
    )
    assert client.put(base + "/entry?project=org/repo", json={"entry": "tianxuan"}, headers=admin).json() == {
        "entry": "tianxuan"
    }
    assert client.get(base + "/entry?project=org/repo", headers=other).json() == {"entry": "existing"}
    assert client.post(base + "/tasks", json=task, headers=admin).json()["entry"] == "existing"
    task["call_id"] = "new-selection"
    created = client.post(base + "/tasks", json=task, headers=admin)
    assert created.status_code == 200, created.text
    result = client.post("/api/v1/tools", headers=admin, json={"name": "migration.start", "payload": task})
    assert result.json() == created.json()
    assert len(store.list_issues(admin["X-Actor"])) == 1
    assert (
        client.post(base + "/tasks", json={**task, "source_id": "github:org/repo/issue/9"}, headers=admin).status_code
        == 422
    )
    assert client.post(base + "/tasks", json={**task, "mode": "record_only"}, headers=admin).status_code == 422


def test_offline_tenant_selection_and_role_checks(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    database = tmp_path / "domain.db"
    store = Tianxuan(str(database))
    admin = store.register("demo", "admin@example.org", "test-password")["user_id"]
    tenant = store.actor_context(admin)["tenant"]
    client = TestClient(create_app(store))
    headers = {"X-Actor": admin}
    script = Path(__file__).resolve().parents[1] / "migration" / "routing.py"
    subprocess.run(
        [sys.executable, str(script), str(database), "demo", "--tenant", tenant, "--set", "tianxuan"], check=True
    )
    url = "/api/v1/migration/entry?project=demo"
    assert client.get(url, headers=headers).json() == {"entry": "tianxuan"}
    doc = client.post("/api/v1/docs", headers=headers, json={"title": "Scope", "body_md": "scope"}).json()["id"]
    assert client.put(url + "&requirement=" + doc, headers=headers, json={"entry": "existing"}).json() == {
        "entry": "existing"
    }
    for role in ("viewer", "editor"):
        user = client.post(
            "/api/v1/users",
            headers=headers,
            json={"email": role + "@example.org", "password": "fixture-password", "role": role},
        ).json()
        member = {"X-Actor": user["user_id"]}
        assert client.put(url, headers=member, json={"entry": "existing"}).status_code == 403
        if role == "viewer":
            assert (
                client.post(
                    "/api/v1/tools",
                    headers=member,
                    json={
                        "name": "migration.start",
                        "payload": {"project": "demo", "title": "Denied", "call_id": "deny"},
                    },
                ).status_code
                == 403
            )
    assert client.get(url, headers=headers).json() == {"entry": "tianxuan"}
