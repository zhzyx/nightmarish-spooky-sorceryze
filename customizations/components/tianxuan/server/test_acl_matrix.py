"""天璇文档 ACL 回归矩阵。

| 场景 | 读 | 写 |
| --- | --- | --- |
| 租户可见文档的查看者 | 全部读接口放行 | PATCH/merge/patch/评论拒绝 |
| 私有文档的非共享成员 | 列表隐藏，其余读接口拒绝 | 评论拒绝 |
| 私有文档的读共享 | 全部读接口放行 | PATCH/merge/patch/评论拒绝 |
| 私有文档的写共享 | 不单独断言 | PATCH/merge/patch/评论放行 |
| 私有文档的所有者与管理员 | 全部读接口放行 | 评论放行 |
| 私有文档的非共享 WebSocket | 连接以 4403 关闭 | — |
| 私有文档的读共享 WebSocket | 收到 snapshot | — |

每个用例使用全新的内存领域核心，只验证 HTTP/WebSocket 适配层的 ACL 映射，
不重测领域规则；未共享的私有文档统一期望 403，未知文档仍期望 404。
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from api import create_app
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from tianxuan_core import Tianxuan

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin-pass"
MEMBER_PASSWORD = "member-pass"
BASE_MD = "# ACL 矩阵\n\n租户可见的正文。\n"
UPDATED_MD = "# ACL 矩阵\n\n更新后的正文。\n"
MERGED_MD = UPDATED_MD + "\n离线补充。\n"
PATCHED_MD = MERGED_MD.replace("离线补充", "补丁补充")


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(create_app(Tianxuan(":memory:"))) as test_client:
        yield test_client


def _session(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/session", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _register_admin(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": "ACL 矩阵工坊",
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
            "name": "Admin",
        },
    )
    assert response.status_code == 200, response.text
    return _session(client, ADMIN_EMAIL, ADMIN_PASSWORD)


def _add_member(client: TestClient, admin: dict[str, str], email: str, role: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/users",
        headers=admin,
        json={"email": email, "password": MEMBER_PASSWORD, "role": role},
    )
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def _member_session(client: TestClient, email: str) -> dict[str, str]:
    return _session(client, email, MEMBER_PASSWORD)


def _create_doc(client: TestClient, headers: dict[str, str], title: str, body: str = BASE_MD) -> dict[str, Any]:
    response = client.post("/api/v1/docs", headers=headers, json={"title": title, "body_md": body})
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def _make_private(client: TestClient, headers: dict[str, str], doc_id: str) -> None:
    response = client.patch(f"/api/v1/docs/{doc_id}/visibility", headers=headers, json={"visibility": "private"})
    assert response.status_code == 200, response.text
    assert response.json()["visibility"] == "private"


def _share(client: TestClient, headers: dict[str, str], doc_id: str, user_id: str, permission: str) -> None:
    response = client.post(
        f"/api/v1/docs/{doc_id}/shares",
        headers=headers,
        json={"user_id": user_id, "permission": permission},
    )
    assert response.status_code == 200, response.text
    assert response.json()["permission"] == permission


def _listed_ids(client: TestClient, headers: dict[str, str]) -> set[str]:
    response = client.get("/api/v1/docs", headers=headers)
    assert response.status_code == 200, response.text
    return {item["id"] for item in response.json()["docs"]}


def _assert_read_access(client: TestClient, headers: dict[str, str], doc_id: str, expected: int) -> None:
    """逐个读取接口断言状态码：get/export/ai-view/classify/comments/versions/diff/links。"""
    base = f"/api/v1/docs/{doc_id}"
    calls: list[tuple[str, str, str, dict[str, int] | None]] = [
        ("get", "GET", base, None),
        ("export", "GET", f"{base}/export", None),
        ("ai-view", "GET", f"{base}/ai-view", None),
        ("classify", "POST", f"{base}/classify", None),
        ("comments", "GET", f"{base}/comments", None),
        ("versions", "GET", f"{base}/versions", None),
        ("diff", "GET", f"{base}/diff", {"from_version": 1, "to_version": 2}),
        ("links", "GET", f"{base}/links", None),
    ]
    for name, method, path, params in calls:
        response = client.request(method, path, headers=headers, params=params)
        assert response.status_code == expected, f"{name}: {response.status_code} {response.text}"


def _assert_write_denied(client: TestClient, headers: dict[str, str], doc_id: str, expected_version: int) -> None:
    """写接口统一断言 403：PATCH、merge、patch、创建评论。"""
    calls: list[tuple[str, str, str, dict[str, Any]]] = [
        (
            "update",
            "PATCH",
            f"/api/v1/docs/{doc_id}",
            {"body_md": "# 拒绝\n", "expected_version": expected_version},
        ),
        (
            "merge",
            "POST",
            f"/api/v1/docs/{doc_id}/merge",
            {"base_md": BASE_MD, "local_md": "# 拒绝\n", "expected_version": expected_version},
        ),
        (
            "patch",
            "POST",
            f"/api/v1/docs/{doc_id}/patch",
            {
                "expected_version": expected_version,
                "patches": [{"find": "正文", "replace": "拒绝"}],
            },
        ),
        ("comment", "POST", f"/api/v1/docs/{doc_id}/comments", {"body": "不应写入"}),
    ]
    for name, method, path, payload in calls:
        response = client.request(method, path, headers=headers, json=payload)
        assert response.status_code == 403, f"{name}: {response.status_code} {response.text}"


def test_tenant_document_viewer_reads_but_cannot_write(client: TestClient) -> None:
    admin = _register_admin(client)
    _add_member(client, admin, "viewer@example.com", "viewer")
    viewer = _member_session(client, "viewer@example.com")

    document = _create_doc(client, admin, "租户可见文档")
    updated = client.patch(
        f"/api/v1/docs/{document['id']}",
        headers=admin,
        json={"body_md": UPDATED_MD, "expected_version": document["version"]},
    )
    assert updated.status_code == 200, updated.text

    assert document["id"] in _listed_ids(client, viewer)
    _assert_read_access(client, viewer, document["id"], 200)
    _assert_write_denied(client, viewer, document["id"], updated.json()["version"])


def test_private_document_hides_from_unshared_members_but_not_owner_or_admin(client: TestClient) -> None:
    admin = _register_admin(client)
    owner = _add_member(client, admin, "owner@example.com", "editor")
    owner_headers = _member_session(client, "owner@example.com")
    _add_member(client, admin, "editor@example.com", "editor")
    editor_headers = _member_session(client, "editor@example.com")
    _add_member(client, admin, "viewer@example.com", "viewer")
    viewer = _member_session(client, "viewer@example.com")

    document = _create_doc(client, owner_headers, "私有文档")
    _make_private(client, owner_headers, document["id"])
    updated = client.patch(
        f"/api/v1/docs/{document['id']}",
        headers=owner_headers,
        json={"body_md": UPDATED_MD, "expected_version": document["version"]},
    )
    assert updated.status_code == 200, updated.text

    for headers in (viewer, editor_headers):
        assert document["id"] not in _listed_ids(client, headers)
        _assert_read_access(client, headers, document["id"], 403)
        comment = client.post(
            f"/api/v1/docs/{document['id']}/comments",
            headers=headers,
            json={"body": "不应评论"},
        )
        assert comment.status_code == 403, comment.text

    assert document["id"] in _listed_ids(client, admin)
    for headers in (owner_headers, admin):
        _assert_read_access(client, headers, document["id"], 200)
        comment = client.post(
            f"/api/v1/docs/{document['id']}/comments",
            headers=headers,
            json={"body": "可以评论"},
        )
        assert comment.status_code == 200, comment.text
    assert owner["role"] == "editor"


def test_read_share_grants_reads_but_not_writes(client: TestClient) -> None:
    admin = _register_admin(client)
    viewer = _add_member(client, admin, "viewer@example.com", "viewer")
    viewer_headers = _member_session(client, "viewer@example.com")

    document = _create_doc(client, admin, "读共享文档")
    _make_private(client, admin, document["id"])
    updated = client.patch(
        f"/api/v1/docs/{document['id']}",
        headers=admin,
        json={"body_md": UPDATED_MD, "expected_version": document["version"]},
    )
    assert updated.status_code == 200, updated.text
    _share(client, admin, document["id"], viewer["user_id"], "read")

    assert document["id"] in _listed_ids(client, viewer_headers)
    _assert_read_access(client, viewer_headers, document["id"], 200)
    _assert_write_denied(client, viewer_headers, document["id"], updated.json()["version"])


def test_write_share_grants_writes_and_comments(client: TestClient) -> None:
    admin = _register_admin(client)
    editor = _add_member(client, admin, "editor@example.com", "editor")
    editor_headers = _member_session(client, "editor@example.com")

    document = _create_doc(client, admin, "写共享文档")
    _make_private(client, admin, document["id"])
    _share(client, admin, document["id"], editor["user_id"], "write")

    updated = client.patch(
        f"/api/v1/docs/{document['id']}",
        headers=editor_headers,
        json={"body_md": UPDATED_MD, "expected_version": document["version"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2

    merged = client.post(
        f"/api/v1/docs/{document['id']}/merge",
        headers=editor_headers,
        json={"base_md": UPDATED_MD, "local_md": MERGED_MD, "expected_version": 2},
    )
    assert merged.status_code == 200, merged.text
    assert merged.json()["status"] == "applied"
    assert merged.json()["doc"]["version"] == 3

    patched = client.post(
        f"/api/v1/docs/{document['id']}/patch",
        headers=editor_headers,
        json={"expected_version": 3, "patches": [{"find": "离线补充", "replace": "补丁补充"}]},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["version"] == 4
    assert patched.json()["body_md"] == PATCHED_MD

    comment = client.post(
        f"/api/v1/docs/{document['id']}/comments",
        headers=editor_headers,
        json={"body": "写共享可以评论"},
    )
    assert comment.status_code == 200, comment.text
    assert comment.json()["author"] == editor["user_id"]


def test_private_document_list_filtering_and_admin_always_sees(client: TestClient) -> None:
    admin = _register_admin(client)
    _add_member(client, admin, "owner@example.com", "editor")
    owner_headers = _member_session(client, "owner@example.com")
    viewer = _add_member(client, admin, "viewer@example.com", "viewer")
    viewer_headers = _member_session(client, "viewer@example.com")

    tenant_doc = _create_doc(client, admin, "租户文档")
    private_doc = _create_doc(client, owner_headers, "私有文档")
    _make_private(client, owner_headers, private_doc["id"])

    viewer_ids = _listed_ids(client, viewer_headers)
    assert tenant_doc["id"] in viewer_ids
    assert private_doc["id"] not in viewer_ids

    assert private_doc["id"] in _listed_ids(client, admin)
    assert private_doc["id"] in _listed_ids(client, owner_headers)

    _share(client, owner_headers, private_doc["id"], viewer["user_id"], "read")
    assert private_doc["id"] in _listed_ids(client, viewer_headers)


def test_websocket_private_document_requires_share(client: TestClient) -> None:
    admin = _register_admin(client)
    _add_member(client, admin, "owner@example.com", "editor")
    owner_headers = _member_session(client, "owner@example.com")
    viewer = _add_member(client, admin, "viewer@example.com", "viewer")

    document = _create_doc(client, owner_headers, "私有实时文档")
    _make_private(client, owner_headers, document["id"])

    with pytest.raises(WebSocketDisconnect) as denied:
        with client.websocket_connect(f"/api/v1/ws/docs/{document['id']}?actor={viewer['user_id']}") as websocket:
            websocket.receive_json()
    assert denied.value.code == 4403

    _share(client, owner_headers, document["id"], viewer["user_id"], "read")
    with client.websocket_connect(f"/api/v1/ws/docs/{document['id']}?actor={viewer['user_id']}") as websocket:
        snapshot = websocket.receive_json()
        assert snapshot["type"] == "snapshot"
        assert snapshot["doc"]["id"] == document["id"]
        assert websocket.receive_json()["type"] == "presence"


def test_unknown_document_returns_404_for_authorized_actor(client: TestClient) -> None:
    admin = _register_admin(client)
    missing = "doc_missing"
    assert client.get(f"/api/v1/docs/{missing}", headers=admin).status_code == 404
    for suffix in ("export", "ai-view", "versions", "links", "comments"):
        assert client.get(f"/api/v1/docs/{missing}/{suffix}", headers=admin).status_code == 404, suffix
    assert client.post(f"/api/v1/docs/{missing}/classify", headers=admin).status_code == 404
    assert (
        client.patch(
            f"/api/v1/docs/{missing}",
            headers=admin,
            json={"body_md": "x", "expected_version": 1},
        ).status_code
        == 404
    )
