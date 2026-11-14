"""文档导出接口测试。"""

from __future__ import annotations

from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


def _client() -> tuple[TestClient, dict[str, str]]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    admin = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "导出租户", "email": "export@example.com", "password": "secret-pass"},
    ).json()
    return client, {"X-Actor": admin["user_id"]}


def test_export_markdown_and_html() -> None:
    client, headers = _client()
    doc = client.post(
        "/api/v1/docs",
        headers=headers,
        json={
            "title": "导出/测试",
            "body_md": "# 标题\n\n**加粗** 与 `代码`\n\n```sh\necho hi\n```\n\n<script>alert(1)</script>\n",
        },
    ).json()

    markdown = client.get(f"/api/v1/docs/{doc['id']}/export/file", headers=headers, params={"format": "md"})
    assert markdown.status_code == 200
    assert markdown.headers["content-type"].startswith("text/markdown")
    assert "attachment;" in markdown.headers["content-disposition"]
    assert markdown.headers["content-disposition"].startswith("attachment; filename=document.md;")
    assert "filename*=UTF-8''" in markdown.headers["content-disposition"]
    assert markdown.text == "# 标题\n\n**加粗** 与 `代码`\n\n```sh\necho hi\n```\n\n<script>alert(1)</script>\n"

    html = client.get(f"/api/v1/docs/{doc['id']}/export/file", headers=headers, params={"format": "html"})
    assert html.status_code == 200
    assert html.headers["content-type"].startswith("text/html")
    assert "<h1>标题</h1>" in html.text
    assert "<strong>加粗</strong>" in html.text
    assert "<code>代码</code>" in html.text
    assert '<pre><code class="language-sh">echo hi</code></pre>' in html.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html.text
    assert "<script>alert(1)</script>" not in html.text


def test_export_rejects_unknown_format() -> None:
    client, headers = _client()
    doc = client.post("/api/v1/docs", headers=headers, json={"title": "格式", "body_md": "x"}).json()
    response = client.get(f"/api/v1/docs/{doc['id']}/export/file", headers=headers, params={"format": "pdf"})
    assert response.status_code == 400


def test_export_requires_actor() -> None:
    client, headers = _client()
    doc = client.post("/api/v1/docs", headers=headers, json={"title": "权限", "body_md": "x"}).json()
    response = client.get(f"/api/v1/docs/{doc['id']}/export/file")
    assert response.status_code in {400, 401, 403}


def test_export_docx() -> None:
    from io import BytesIO

    from docx import Document

    client, headers = _client()
    doc = client.post(
        "/api/v1/docs",
        headers=headers,
        json={"title": "Word 导出", "body_md": "# 标题\n\n正文 **加粗**\n\n- 一\n- 二\n"},
    ).json()
    response = client.get(f"/api/v1/docs/{doc['id']}/export/file", headers=headers, params={"format": "docx"})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert response.content.startswith(b"PK")
    document = Document(BytesIO(response.content))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "Word 导出" in text
    assert "标题" in text
    assert "正文 加粗" in text
