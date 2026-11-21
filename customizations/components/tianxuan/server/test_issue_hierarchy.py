"""Hierarchy edits use the current project, inherited ACL and serialized parent precondition."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan, VersionConflict


def test_project_and_ancestor_permissions(tmp_path):
    store = Tianxuan(str(tmp_path / "domain.db"))
    owner = store.register("studio", "owner@example.invalid", "fixture-pass")["user_id"]
    editor = store.add_member(owner, "writer@example.invalid", "fixture-pass", role="editor")["user_id"]
    viewer = store.add_member(owner, "reader@example.invalid", "fixture-pass", role="viewer")["user_id"]
    outsider = store.register("foreign", "foreign@example.invalid", "fixture-pass")["user_id"]
    project = "studio/game"
    root = store.create_issue(owner, "Root", project=project)
    req = store.create_requirement(owner, "req", "Restricted", "why", "scope", "done")
    store.set_visibility(owner, req["id"], "private")
    private = store.create_issue(owner, "Private", parent_id=root["id"], requirement_id=req["id"])
    nested = store.create_issue(owner, "Nested", parent_id=private["id"])
    child = store.create_issue(owner, "Child", project=project)
    other_project = store.create_issue(owner, "Elsewhere", project="other")
    route = "/api/v1/issues/{}/hierarchy"
    assign = {"parent_number": nested["number"], "expected_parent_id": None}

    def sign_in(client, actor):
        client.headers["Authorization"] = "Bearer " + store.issue_session(actor)

    try:
        with TestClient(create_app(store)) as client:
            client.params = {"project": project}
            child_url = route.format(child["id"])
            sign_in(client, outsider)
            assert client.get(child_url).status_code == 404
            sign_in(client, viewer)
            assert client.get(child_url).json() == {"parent": None, "children": []}
            assert client.put(child_url, json=assign).status_code == 403
            sign_in(client, editor)
            assert client.get(route.format(root["id"])).json()["children"] == []
            assert client.get(route.format(nested["id"])).status_code == 403
            assert client.put(child_url, json=assign).status_code == 403
            store.share_doc(owner, req["id"], editor, "read")
            assert client.get(route.format(nested["id"])).json()["parent"]["id"] == private["id"]
            assert client.put(child_url, json=assign).status_code == 403
            store.share_doc(owner, req["id"], editor, "write")
            assert client.get(child_url, params={"project": "other"}).status_code == 404
            assert client.put(child_url, params={"project": "other"}, json=assign).status_code == 404
            assert client.put(child_url, json={**assign, "parent_number": other_project["number"]}).status_code == 404
            assert client.put(child_url, json=assign).json()["parent"]["id"] == nested["id"]
            assert client.put(child_url, json=assign).json()["parent"]["id"] == nested["id"]  # acknowledged retry
            assert (
                client.put(route.format(root["id"]), json={**assign, "parent_number": child["number"]}).status_code
                == 409
            )
            assert client.put(child_url, json={**assign, "parent_number": child["number"]}).status_code == 409
            store.unshare_doc(owner, req["id"], editor)
            assert client.get(child_url).status_code == 403
            assert (
                client.put(child_url, json={"parent_number": None, "expected_parent_id": nested["id"]}).status_code
                == 403
            )
            assert store.read_issue(owner, child["id"])["parent_id"] == nested["id"]
    finally:
        store.db.close()


@pytest.mark.parametrize("reciprocal", [False, True], ids=["competing-parents", "reciprocal-links"])
def test_simultaneous_edits_across_connections(tmp_path, reciprocal):
    path = str(tmp_path / "domain.db")
    first = Tianxuan(path)
    owner = first.register("studio", "owner@example.invalid", "fixture-pass")["user_id"]
    project = "studio/game"
    a, b, c = (first.create_issue(owner, title, project=project) for title in ("A", "B", "C"))
    second = Tianxuan(path)
    start = Barrier(2)

    def edit(connection, child, parent):
        start.wait(timeout=10)
        try:
            connection.set_issue_parent(owner, child["id"], project, parent["number"], None)
        except VersionConflict:
            return "conflict"
        return "accepted"

    try:
        with ThreadPoolExecutor(2) as pool:
            left = pool.submit(edit, first, a, b)
            right = pool.submit(edit, second, b if reciprocal else a, a if reciprocal else c)
            assert sorted([left.result(), right.result()]) == ["accepted", "conflict"]
        parents = [first.read_issue(owner, item["id"])["parent_id"] for item in (a, b, c)]
        expected = [[b["id"], None, None], [None, a["id"], None] if reciprocal else [c["id"], None, None]]
        assert parents in expected
    finally:
        second.db.close()
        first.db.close()
