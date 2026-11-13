"""天璇端到端演示：注册 → 会话 → 文档 → 补丁 → 评论 → 链接 → 版本 → 需求 → 看板 → 导出。

不访问网络、不依赖外部服务；用 TestClient 走真实 HTTP 适配层。
运行：
    python demo.py
"""

from __future__ import annotations

from typing import Any

from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


def _ok(response: Any) -> dict[str, Any]:
    if response.status_code >= 400:
        raise RuntimeError(
            f"{response.request.method} {response.request.url} -> {response.status_code}: {response.text}"
        )
    return response.json()  # type: ignore[no-any-return]


def main() -> int:
    client = TestClient(create_app(Tianxuan(":memory:")))

    account = _ok(
        client.post(
            "/api/v1/auth/register",
            json={
                "tenant_name": "演示工坊",
                "email": "demo@example.com",
                "password": "demo-pass",
                "name": "Demo",
            },
        )
    )
    print("1. 注册租户/用户", account["user_id"])

    session = _ok(client.post("/api/v1/auth/session", json={"email": "demo@example.com", "password": "demo-pass"}))
    headers = {"Authorization": f"Bearer {session['token']}"}
    print("2. 会话 token", session["token"][:12] + "…", "role:", session["role"])

    document = _ok(
        client.post(
            "/api/v1/docs",
            headers=headers,
            json={"title": "AI Native 文档", "body_md": "# AI Native 文档\n\nA\n"},
        )
    )
    print("3. 创建文档", document["id"], "v", document["version"])

    patched = _ok(
        client.post(
            f"/api/v1/docs/{document['id']}/patch",
            headers=headers,
            json={"expected_version": 1, "patches": [{"find": "A\n", "replace": "A2\n"}]},
        )
    )
    print("4. 结构化补丁 ->", patched["body_md"].replace("\n", "\\n"), "v", patched["version"])

    comment = _ok(client.post(f"/api/v1/docs/{document['id']}/comments", headers=headers, json={"body": "请补充验收"}))
    print("5. 评论", comment["id"], "resolved:", comment["resolved"])

    linked = _ok(
        client.post(
            "/api/v1/docs",
            headers=headers,
            json={"title": "链接页", "body_md": "# 链接页\n\n参见 [[AI Native 文档]]\n"},
        )
    )
    links = _ok(client.get(f"/api/v1/docs/{linked['id']}/links", headers=headers))
    print("6. 链接", links["outgoing"], "反向链接", links["backlinks"])

    versions = _ok(client.get(f"/api/v1/docs/{document['id']}/versions", headers=headers))["versions"]
    diff = _ok(client.get(f"/api/v1/docs/{document['id']}/diff?from_version=1&to_version=2", headers=headers))["diff"]
    print("7. 版本", [item["version"] for item in versions], "diff 行数", len(diff.splitlines()))

    requirement = _ok(
        client.post(
            "/api/v1/requirements",
            headers=headers,
            json={
                "request_id": "demo-1",
                "title": "演示需求",
                "outcome": "可端到端演示",
                "scope": "文档、工单、导出",
                "acceptance": "演示脚本通过",
            },
        )
    )
    tickets = _ok(
        client.post(
            f"/api/v1/requirements/{requirement['id']}/tickets",
            headers=headers,
            json={"tickets": [{"title": "实现导出"}, {"title": "补齐验收"}]},
        )
    )["issues"]
    board = _ok(client.get("/api/v1/board", headers=headers))["columns"]
    print("8. 需求/工单/看板", len(tickets), {key: len(value) for key, value in board.items()})

    exported = _ok(client.get("/api/v1/requirements/demo-1/export", headers=headers))
    print("9. 需求导出", exported["filename"], len(exported["markdown"]), "chars")

    print("OK: 天璇端到端演示通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
