from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan

CHATS = "/api/v1/workspace/conversations"


def test_issue_rooms_are_private_stable_and_bound_to_the_selected_issue(tmp_path):
    database = str(tmp_path / "rooms.db")
    store = Tianxuan(database)
    actor = store.register("Studio", "owner@example.invalid", "test-password")["user_id"]
    other = store.add_member(actor, "editor@example.invalid", "test-password", role="editor")["user_id"]
    project = "studio/rooms"
    a, b = [store.create_issue(actor, "Same", project=project) for _ in range(2)]
    params = {"project": project, "module_id": a["module_id"]}
    route = f"{CHATS}/for-issue/{a['id']}"
    owner_auth, other_auth = [
        {"Authorization": "Bearer " + store.issue_access_key(actor, user, "fixture")["key"]} for user in (actor, other)
    ]
    with TestClient(create_app(store), headers=owner_auth) as client:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.map(lambda _: client.post(route, params=params, json={}).json()["id"], range(2))
        assert first == second
        assert client.post(route, params=params | {"module_id": "missing"}, json={}).status_code == 409
        assert client.post(route, params=params, headers=other_auth, json={}).json()["id"] != first
        assert client.get(f"{CHATS}/{first}", headers=other_auth).status_code == 404
        selection = {**params, "issue_id": a["id"], "references": []}
        turn = {"id": str(uuid4()), "expected_version": 0, "content": "question"}
        bad_ref = {"kind": "issue", "object_id": b["id"], "revision": store.issue_snapshot(actor, b["id"])["revision"]}
        for invalid in [selection | {"references": [bad_ref]}, selection | {"issue_id": b["id"]}]:
            reply = client.post(f"{CHATS}/{first}/turns", json=turn | {"context_snapshot": invalid})
            assert reply.status_code == 409
        assert client.get(f"{CHATS}/{first}").json()["turns"] == []
    store.db.close()
    reopened = Tianxuan(database)
    with TestClient(create_app(reopened), headers=owner_auth) as client:
        assert client.post(route, params=params, json={}).json()["id"] == first
    reopened.db.close()
