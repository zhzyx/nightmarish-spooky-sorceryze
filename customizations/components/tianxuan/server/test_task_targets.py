"""Retries and concurrent target edits share a durable issue-level revision."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan, VersionConflict


def test_return_retry_and_concurrent_corrections(tmp_path):
    database = str(tmp_path / "targets.sqlite")
    store = Tianxuan(database)
    try:
        actor = store.register("Studio", "program@example.invalid", "fixture-pass")["user_id"]
        doc = store.create_doc(actor, "桥", "拉杆")["id"]
        store.design_signoff(actor, doc, 1, "验证拉杆")
        item = dict(paragraph=1, title="拉杆", module_id="default", acceptance="开桥")
        issue = store.split_design(actor, doc, 1, "studio", [item], "split")[0]["id"]
        route = f"/api/v1/issues/{issue}/task-target"
        params = dict(project="studio")
        with TestClient(create_app(store), headers={"Authorization": "Bearer " + store.issue_session(actor)}) as client:
            payload = dict(document_id=doc, version=1, expected_revision=0, stage="预览")
            returned = client.put(route, json=payload, params=params).raise_for_status().json()
            assert returned["status"] == "returned" and returned["criteria"] == ""
            assert client.put(route, json=payload | {"criteria": None}, params=params).json() == returned
            assert client.put(route, json=payload, params=params).json() == returned
            comments = store.list_issue_comments(actor, issue)
            assert len(comments) == 1 and comments[0]["id"] == returned["return_comment_id"]
        barrier = Barrier(2)

        def correct(criteria):
            worker = Tianxuan(database)
            try:
                barrier.wait(10)
                return worker.set_task_target(actor, issue, "studio", doc, 1, 1, "预览", criteria)
            except VersionConflict:
                return None
            finally:
                worker.db.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(correct, ["桥展开至第 24 帧", "第 30 帧显示拉杆复位"]))
        (winner,) = [record for record in outcomes if record]
        assert winner["revision"] == 2 and winner["status"] == "defined"
        assert store.read_issue_detail(actor, "studio", 1)["task_target"] == winner
        assert store.list_issue_comments(actor, issue) == comments
        with pytest.raises(VersionConflict):
            store.set_task_target(actor, issue, "studio", doc, 1, 0, "预览", "")
    finally:
        store.db.close()
