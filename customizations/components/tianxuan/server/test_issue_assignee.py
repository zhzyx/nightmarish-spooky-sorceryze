"""The scoped property write shares the existing numbered detail and ACL."""

from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


def test_assignment_compare_clear_and_scope(tmp_path):
    store = Tianxuan(str(tmp_path / "domain.db"))
    admin = store.register("studio", "owner@example.invalid", "test-password")["user_id"]
    member = store.add_member(admin, "user@example.invalid", "test-password")["user_id"]
    foreign = store.register("other", "other@example.invalid", "test-password")["user_id"]
    issue = store.create_issue(admin, "场景检查", project="game")
    with TestClient(create_app(store), headers={"Authorization": "Bearer " + store.issue_session(admin)}) as client:
        route = f"/api/v1/issues/{issue['id']}/assignee"
        detail = f"/api/v1/issues/by-number/{issue['number']}/detail?project=game"

        def assign(user, previous, project="game"):
            return client.put(
                route, params={"project": project}, json={"assignee_id": user, "expected_assignee_id": previous}
            )

        assert assign(member, None, project="wrong").status_code == 404
        assert assign(foreign, None).status_code == 404
        assert client.put(route, params={"project": "game"}, json={}).status_code == 422
        assert client.get(detail).json()["assignee"] is None
        assigned = assign(member, None).json()
        assert assigned["assignee"]["id"] == member
        assert client.get(detail).json() == assigned
        assert assign(member, None).json() == assigned
        assert assign(admin, None).status_code == 409
        assert client.get(detail).json() == assigned
        assert assign(admin, member).json()["assignee"]["id"] == admin
        cleared = assign(None, admin).json()
        assert cleared["assignee"] is None and client.get(detail).json() == cleared
        assert cleared["revision"] == assigned["revision"]
        events = store.db.execute(
            "SELECT COUNT(*) FROM events WHERE target=? AND type='issue.assigned'", (issue["id"],)
        ).fetchone()
        assert events[0] == 3

    store.db.close()
