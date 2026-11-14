"""跨租户范围检查与需求/工单幂等回归（#1117 / #1118）。"""

from __future__ import annotations

import pytest
from tianxuan_core import NotFound, Tianxuan, VersionConflict


def _tenants() -> tuple[Tianxuan, str, str]:
    store = Tianxuan(":memory:")
    first = store.register("甲租户", "a@example.com", "secret-pass")["user_id"]
    second = store.register("乙租户", "b@example.com", "secret-pass")["user_id"]
    return store, str(first), str(second)


def _requirement(store: Tianxuan, actor: str, request_id: str = "req-scope") -> dict[str, Any]:
    return store.create_requirement(  # type: ignore[no-any-return]
        actor,
        request_id,
        "范围检查需求",
        "只允许本租户操作",
        "工单与需求",
        "跨租户一律拒绝",
    )


def test_cross_tenant_issue_and_requirement_operations_are_rejected() -> None:
    store, owner, other = _tenants()
    requirement = _requirement(store, owner)
    parent = store.create_issue(owner, "需求父单", type="requirement", requirement_id=requirement["id"])
    ticket = store.create_issue(
        owner,
        "实现工单",
        requirement_id=requirement["id"],
        parent_id=parent["id"],
    )

    with pytest.raises(NotFound):
        store.transition_issue(other, ticket["id"], "planned")
    with pytest.raises(NotFound):
        store.create_issue(other, "越权引用需求", requirement_id=requirement["id"])
    with pytest.raises(NotFound):
        store.create_issue(other, "越权引用父单", parent_id=ticket["id"])
    with pytest.raises(NotFound):
        store.plan_tickets(other, requirement["id"], [{"title": "越权拆单"}])

    assert store.get_issue(ticket["id"])["status"] == "backlog"
    assert store.list_issues(other, requirement["id"]) == []


def test_requirement_replay_is_idempotent_and_conflicts_on_change() -> None:
    store, actor, _ = _tenants()
    first = _requirement(store, actor, "req-idem")
    replay = _requirement(store, actor, "req-idem")
    assert replay["id"] == first["id"]
    assert replay["body_md"] == first["body_md"]

    with pytest.raises(VersionConflict):
        store.create_requirement(actor, "req-idem", "换标题", "目标", "范围", "验收")

    documents = store.list_docs(actor)
    assert len([doc for doc in documents if doc["kind"] == "requirement"]) == 1


def test_plan_tickets_replay_does_not_duplicate_tree() -> None:
    store, actor, _ = _tenants()
    requirement = _requirement(store, actor, "req-plan")
    first = store.plan_tickets(actor, requirement["id"], [{"title": "甲"}, {"title": "乙"}])
    replay = store.plan_tickets(actor, requirement["id"], [{"title": "甲"}, {"title": "乙"}])

    assert [issue["id"] for issue in replay] == [issue["id"] for issue in first]
    assert len(store.list_issues(actor, requirement["id"])) == 3

    extended = store.plan_tickets(actor, requirement["id"], [{"title": "甲"}, {"title": "丙"}])
    assert len(extended) == 3
    assert len(store.list_issues(actor, requirement["id"])) == 4
    assert {issue["title"] for issue in store.list_issues(actor, requirement["id"])} == {
        "范围检查需求",
        "甲",
        "乙",
        "丙",
    }
