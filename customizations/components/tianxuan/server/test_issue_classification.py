"""Issue labels inherit project and ancestor permissions from their owning issue."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan, VersionConflict


def test_label_lookup_on_restricted_issues(tmp_path):
    store = Tianxuan(str(tmp_path / "domain.sqlite"))
    owner = store.register("Studio", "owner@example.invalid", "fixture-pass")["user_id"]
    editor = store.add_member(owner, "writer@example.invalid", "fixture-pass", role="editor")["user_id"]
    outsider = store.register("Other", "other@example.invalid", "fixture-pass")["user_id"]
    req = store.create_requirement(owner, "i17", "Private design", "why", "scope", "done")
    store.set_visibility(owner, req["id"], "private")
    project = "scope/A"
    parent = store.create_issue(owner, "parent", requirement_id=req["id"], project=project)
    ticket = store.create_issue(owner, "child", parent_id=parent["id"])
    store.set_issue_classification(owner, ticket["id"], project, "bug", ["hand off"], "task", [])
    route = f"/api/v1/issues/{ticket['id']}/classification"
    detail_route = f"/api/v1/issues/by-number/{ticket['number']}/detail"
    update = {"type": "task", "labels": [], "expected_type": "bug", "expected_labels": ["hand off"]}
    try:
        with TestClient(create_app(store)) as client:
            client.params = {"project": project}
            client.headers["Authorization"] = "Bearer " + store.issue_session(editor)
            assert client.get("/api/v1/issues", params={"label": "hand off"}).json()["issues"] == []
            assert client.get(detail_route).status_code == 403
            assert client.put(route, json=update).status_code == 403
            store.share_doc(owner, req["id"], editor, "read")
            read_only = client.get(detail_route).json()
            assert not read_only["can_classify"] and read_only["labels"] == ["hand off"]
            assert client.put(route, json=update).status_code == 403
            rows = client.get("/api/v1/issues", params={"label": "hand off"}).json()["issues"]
            assert [row["id"] for row in rows] == [ticket["id"]]
            filtered = client.get("/api/v1/issues", params={"label": "hand off", "q": ticket["title"]}).json()
            assert [row["id"] for row in filtered["issues"]] == [ticket["id"]]
            assert filtered["applied_search"]["q"] == ticket["title"]
            assert filtered["label_filter"] == {"name": "hand off", "project": ticket["project"]}
            assert (
                client.get("/api/v1/issues", params={"label": "hand off", "q": "no such title"}).json()["issues"] == []
            )
            client.headers["Authorization"] = "Bearer " + store.issue_session(outsider)
            assert client.get("/api/v1/issues", params={"label": "hand off"}).json()["issues"] == []
            assert client.put(route, json=update).status_code == 404
            client.headers["Authorization"] = "Bearer " + store.issue_session(owner)
            assert client.put(route, json=update).json() == {"type": "task", "labels": []}
            assert client.get("/api/v1/issues", params={"label": "hand off"}).json()["issues"] == []
    finally:
        store.db.close()


def test_label_and_type_edits_are_atomic(tmp_path):
    path = str(tmp_path / "domain.sqlite")
    first, second = Tianxuan(path), Tianxuan(path)
    actor = first.register("Studio", "owner@example.invalid", "fixture-pass")["user_id"]
    ticket = first.create_issue(actor, "Issue")
    start = Barrier(2)

    def change(connection, kind):
        start.wait(timeout=10)
        try:
            connection.set_issue_classification(actor, ticket["id"], ticket["project"], kind, [kind], "task", [])
            return kind
        except VersionConflict:
            return None

    try:
        with ThreadPoolExecutor(2) as pool:
            writes = [pool.submit(change, first, "bug"), pool.submit(change, second, "feature")]
            outcomes = [write.result() for write in writes]
        assert outcomes.count(None) == 1
        winner = next(kind for kind in outcomes if kind)
        detail = first.read_issue_detail(actor, ticket["project"], ticket["number"])
        assert detail["type"] == winner and detail["labels"] == [winner]
    finally:
        first.db.close()
        second.db.close()
