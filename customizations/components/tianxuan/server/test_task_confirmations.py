"""Issue-level confirmation binds the signed design, current definition, owner and target."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


def test_confirmation_lifecycle_and_reassignment(tmp_path):
    store = Tianxuan(str(tmp_path / "tasks.sqlite"))
    try:
        owner = store.register("Studio", "owner@example.invalid", "fixture-pass")["user_id"]
        member = store.add_member(owner, "member@example.invalid", "fixture-pass")["user_id"]
        viewer = store.add_member(owner, "viewer@example.invalid", "fixture-pass", role="viewer")["user_id"]
        headers = {who: {"Authorization": "Bearer " + store.issue_session(who)} for who in (owner, member, viewer)}
        doc = store.create_doc(owner, "机关", "拉杆")["id"]
        store.design_signoff(owner, doc, 1, "开桥")
        issue = store.split_design(
            owner, doc, 1, "studio", [dict(title="拉杆", paragraph=1, module_id="default", acceptance="开桥")], "split"
        )[0]["id"]
        route = f"/api/v1/issues/{issue}/task-confirmation"
        params = {"project": "studio"}
        with TestClient(create_app(store), headers=headers[owner]) as client:
            client.params = params

            def read():
                return client.get("/api/v1/issues/by-number/1/detail").raise_for_status().json()

            def put(payload, who=owner):
                return client.put(route, json=payload, headers=headers[who])

            payload = dict(
                document_id=doc,
                version=1,
                issue_revision=read()["revision"],
                target_revision=1,
                expected_revision=0,
                status="confirmed",
            )
            assert read()["task_confirmation"] is None
            assert put(payload).status_code == 409
            store.set_task_target(owner, issue, "studio", doc, 1, 0, "原型", "")
            assert put(payload).status_code == 409
            store.set_task_target(owner, issue, "studio", doc, 1, 1, "原型", "开桥")
            assert put(payload).status_code == 409
            payload["target_revision"] = 2
            assert put(payload | {"version": 2}).status_code == 409
            assert put(payload | {"document_id": "other"}).status_code == 409
            assert put(payload | {"issue_revision": "0" * 64}).status_code == 409
            assert put(payload | {"confirmed_by": owner}).status_code == 422
            assert client.put(route, json=payload, params={"project": "other"}).status_code == 404
            assert put(payload, member).status_code == put(payload, viewer).status_code == 403
            client.patch(f"/api/v1/docs/{doc}", json={"expected_version": 1, "body_md": "草稿 v2"}).raise_for_status()
            confirmed = put(payload).raise_for_status().json()
            assert confirmed["version"] == 1 and confirmed["revision"] == 1 and confirmed["confirmed_by"] == owner
            assert put(payload).json() == read()["task_confirmation"] == confirmed
            revoked_payload = payload | {"status": "revoked", "expected_revision": 1}
            revoked = put(revoked_payload).raise_for_status().json()
            assert revoked["revision"] == 2 and revoked["confirmed_by"] is None and revoked["status"] == "revoked"
            assert put(revoked_payload).json() == revoked
            assert put(payload).status_code == 409
            payload["expected_revision"] = 2
            assert put(payload).raise_for_status().json()["revision"] == 3
            store.set_issue_assignee(owner, issue, "studio", member, None)
            after = read()
            assert after["task_target"]["responsible_user"] == owner
            assert after["task_confirmation"]["responsible_user"] == member
            assert after["task_confirmation"]["status"] == "pending"
            payload["expected_revision"] = after["task_confirmation"]["revision"]
            assert put(payload).status_code == 403
            assert put(payload, member).raise_for_status().json()["confirmed_by"] == member
            store.set_issue_assignee(owner, issue, "studio", None, member)
            assert read()["task_confirmation"]["status"] == "pending" and put(payload).status_code == 409
            payload["expected_revision"] = read()["task_confirmation"]["revision"]
            confirmed = put(payload).raise_for_status().json()
            client.put(
                f"/api/v1/issues/{issue}/classification",
                json={"type": "bug", "labels": [], "expected_type": after["type"], "expected_labels": []},
            ).raise_for_status()
            assert read()["task_confirmation"]["status"] == "pending"
            assert put(payload).status_code == 409
            payload.update(expected_revision=confirmed["revision"], issue_revision=read()["revision"])
            confirmed = put(payload).raise_for_status().json()
            store.set_task_target(owner, issue, "studio", doc, 1, 2, "验证", "完全展开")
            assert read()["task_confirmation"]["status"] == "pending" and put(payload).status_code == 409
            store.set_visibility(owner, doc, "private")
            assert (
                client.get("/api/v1/issues/by-number/1/detail", headers=headers[member]).json()["task_confirmation"]
                is None
            )
            assert put(payload, member).status_code == 404
    finally:
        store.db.close()


def test_concurrent_confirmation_retries(tmp_path):
    database = str(tmp_path / "concurrent.sqlite")
    store = Tianxuan(database)
    try:
        owner = store.register("Studio", "owner@example.invalid", "fixture-pass")["user_id"]
        doc = store.create_doc(owner, "桥", "拉杆")["id"]
        store.design_signoff(owner, doc, 1, "开桥")
        issue = store.split_design(
            owner, doc, 1, "studio", [dict(title="拉杆", paragraph=1, module_id="default", acceptance="开桥")], "split"
        )[0]["id"]
        store.set_task_target(owner, issue, "studio", doc, 1, 0, "原型", "开桥")
        revision = store.issue_snapshot(owner, issue)["revision"]
        barrier = Barrier(2)

        def confirm():
            connection = Tianxuan(database)
            try:
                barrier.wait(10)
                return connection.set_task_confirmation(owner, issue, "studio", doc, 1, 1, revision, 0, "confirmed")
            finally:
                connection.db.close()

        with ThreadPoolExecutor(2) as pool:
            result = [pool.submit(confirm) for _ in range(2)]
        records = [worker.result() for worker in result]
        assert records[0] == records[1] == store.read_issue_detail(owner, "studio", 1)["task_confirmation"]
        assert records[0]["revision"] == 1
    finally:
        store.db.close()
