"""Number lookup applies the same current tenant, project and visibility as opening an issue."""

from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


def test_number_lookup_scope_and_visibility(tmp_path):
    path = str(tmp_path / "domain.db")
    store = Tianxuan(path)
    admin = store.register("studio", "owner@example.invalid", "fixture-pass")["user_id"]
    viewer = store.add_member(admin, "viewer@example.invalid", "fixture-pass", role="viewer")["user_id"]
    outsider = store.register("other", "other@example.invalid", "fixture-pass")["user_id"]
    requirement = store.create_requirement(admin, "private", "Private", "why", "scope", "done")
    store.set_visibility(admin, requirement["id"], "private")
    private = store.create_issue(admin, "Private", requirement_id=requirement["id"])
    child = store.create_issue(admin, "Private child", parent_id=private["id"])
    other = store.create_issue(outsider, "Same number in another tenant")
    assert other["number"] == private["number"]
    viewer_token = store.issue_session(viewer)
    outsider_token = store.issue_session(outsider)
    store.db.close()

    store = Tianxuan(path)
    with TestClient(create_app(store)) as client:
        base = "/api/v1/issues/by-number/"
        client.headers["Authorization"] = "Bearer " + viewer_token
        assert client.get(base + str(child["number"])).status_code == 403
        store.share_doc(admin, requirement["id"], viewer, "read")
        assert client.get(base + str(child["number"])).json() == child
        for number in [0, -1, 500, 2**63]:
            assert client.get(base + str(number)).status_code == 404
        assert client.get(base + str(child["number"]), params={"project": "elsewhere"}).status_code == 404
        client.headers["Authorization"] = "Bearer " + outsider_token
        assert client.get(base + str(child["number"])).status_code == 404
        assert client.get(base + str(other["number"])).json() == other
    store.db.close()


def test_detail_uses_current_definition_and_independent_assignee(tmp_path):
    path = str(tmp_path / "domain.db")
    store = Tianxuan(path)
    admin = store.register("studio", "owner@example.invalid", "fixture-pass")["user_id"]
    viewer = store.add_member(admin, "reader@example.invalid", "fixture-pass", name="Reader", role="viewer")["user_id"]
    req = store.create_requirement(admin, "req", "Original", "why", "scope", "done")
    issue = store.create_issue(admin, "Fix", requirement_id=req["id"])
    route = f"/api/v1/issues/by-number/{issue['number']}/detail"
    token = store.issue_session(viewer)
    # A pre-I02 database has issues but no assignment relation.
    store.db.execute("DROP TABLE issue_assignees")
    store.db.close()
    store = Tianxuan(path)
    with TestClient(create_app(store)) as client:
        client.headers["Authorization"] = "Bearer " + token
        before = client.get(route).json()
        assert before["assignee"] is None
        assert before["revision"] == store.issue_snapshot(viewer, issue["id"])["revision"]
        with store.db:
            store.db.execute("INSERT INTO issue_assignees VALUES (?,?)", (issue["id"], viewer))
        store.transition_issue(admin, issue["id"], "planned")
        assigned = client.get(route).json()
        assert assigned["assignee"] == {"id": viewer, "name": "Reader"}
        assert assigned["status"] == "planned"
        assert assigned["revision"] == before["revision"]
        store.update_doc(admin, req["id"], "Changed requirement", req["version"])
        changed = client.get(route).json()
        assert changed["revision"] != before["revision"]
        assert changed["revision"] == store.issue_snapshot(viewer, issue["id"])["revision"]
        store.set_visibility(admin, req["id"], "private")
        assert client.get(route).status_code == 403
        assert client.get(route, params={"project": "other"}).status_code == 404
        assert client.get("/api/v1/issues/by-number/99999/detail").status_code == 404
    store.db.close()
