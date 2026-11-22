"""Design splits are atomic across database connections and keep the source's read permissions."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from tianxuan_core import PermissionDenied, Tianxuan, TianxuanError, VersionConflict


def test_simultaneous_split_and_source_visibility(tmp_path):
    db = str(tmp_path / "tasks.sqlite")
    owner_store = Tianxuan(db)
    owner = owner_store.register("Studio", "owner@example.invalid", "owner-password")["user_id"]
    reader = owner_store.add_member(owner, "member@example.invalid", "member-password")["user_id"]
    # NBSP is content in the native paragraph picker; it must keep the first block contiguous.
    key = owner_store.create_doc(owner, "Design", "Program the action.\n\u00a0\nHandle repeats.\n\nAnimate it.")["id"]
    owner_store.design_signoff(owner, key, 1, "Both tasks work.")
    items = [
        dict(title=title, module_id="default", paragraph=index, acceptance=title + " works")
        for index, title in enumerate(["Program", "Animate"], 1)
    ]
    barrier = Barrier(2)

    def split(_):
        domain = Tianxuan(db)
        try:
            barrier.wait(10)
            return domain.split_design(owner, key, 1, "studio", items, "same-request")
        finally:
            domain.db.close()

    try:
        with pytest.raises(TianxuanError, match="source paragraph"):
            owner_store.split_design(owner, key, 1, "studio", [items[0] | {"paragraph": 3}], "invalid")
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.map(split, range(2))
        assert first == second
        assert len(first) == len(owner_store.list_issues(owner)) == 2
        assert len(owner_store.list_doc_issues(owner, key)) == 2
        assert len(owner_store.design_tasks(reader, key, 1, "studio")) == 2
        issue = first[0]
        changed_module = owner_store.create_business_module(owner, "studio", "QA", call_id="qa")
        owner_store.set_issue_module(owner, issue["id"], "studio", changed_module["id"])
        assert owner_store.read_issue(reader, issue["id"])["module_id"] == changed_module["id"]
        assert (
            owner_store.read_issue_detail(reader, "studio", issue["number"])["design_source"] == issue["design_source"]
        )
        owner_store.set_visibility(owner, key, "private")
        assert owner_store.read_issue_detail(reader, "studio", issue["number"])["design_source"] is None
        with pytest.raises(PermissionDenied):
            owner_store.design_tasks(reader, key, 1, "studio")
        with pytest.raises(PermissionDenied):
            owner_store.split_design(reader, key, 1, "studio", items, "same-request")
        with pytest.raises(VersionConflict):
            owner_store.split_design(owner, key, 1, "studio", items[:1], "same-request")
    finally:
        owner_store.db.close()
