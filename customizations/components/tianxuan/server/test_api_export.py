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
    response = client.get(f"/api/v1/docs/{doc['id']}/export/file", headers=headers, params={"format": "rtf"})
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


def test_export_docx_preserves_inline_and_table() -> None:
    from io import BytesIO

    from docx import Document

    client, headers = _client()
    doc = client.post(
        "/api/v1/docs",
        headers=headers,
        json={
            "title": "富文本",
            "body_md": "**加粗** 与 `代码`\n\n| 名称 | 值 |\n| --- | --- |\n| A | 1 |\n",
        },
    ).json()
    response = client.get(f"/api/v1/docs/{doc['id']}/export/file", headers=headers, params={"format": "docx"})
    document = Document(BytesIO(response.content))
    runs = [run for paragraph in document.paragraphs for run in paragraph.runs]
    assert any(run.bold and run.text == "加粗" for run in runs)
    assert any(run.font.name == "Consolas" and run.text == "代码" for run in runs)
    assert len(document.tables) == 1
    assert document.tables[0].cell(1, 0).text == "A"
    assert document.tables[0].cell(1, 1).text == "1"


def test_export_pdf() -> None:
    client, headers = _client()
    doc = client.post(
        "/api/v1/docs",
        headers=headers,
        json={"title": "PDF 导出", "body_md": "# 标题\n\n正文内容\n\n- 列表一\n- 列表二\n"},
    ).json()
    response = client.get(f"/api/v1/docs/{doc['id']}/export/file", headers=headers, params={"format": "pdf"})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 1000


def test_pdf_table_flowable_and_export() -> None:
    from pdf_export import _table_flowables
    from reportlab.platypus import Table

    table = _table_flowables(["名称", "值"], [["A", "1"], ["B", "2"]])
    assert isinstance(table, Table)
    assert table._cellvalues[1][0].text == "A"
    assert table._cellvalues[2][1].text == "2"

    client, headers = _client()
    doc = client.post(
        "/api/v1/docs",
        headers=headers,
        json={"title": "PDF 表格", "body_md": "| 名称 | 值 |\n| --- | --- |\n| A | 1 |\n"},
    ).json()
    response = client.get(f"/api/v1/docs/{doc['id']}/export/file", headers=headers, params={"format": "pdf"})
    assert response.status_code == 200, response.text
    assert response.content.startswith(b"%PDF")


DATA_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def test_export_data_uri_image_to_pdf_and_docx() -> None:
    from io import BytesIO

    from docx import Document

    client, headers = _client()
    doc = client.post(
        "/api/v1/docs",
        headers=headers,
        json={"title": "图片", "body_md": f"![图]({DATA_PNG})\n"},
    ).json()

    pdf = client.get(f"/api/v1/docs/{doc['id']}/export/file", headers=headers, params={"format": "pdf"})
    assert pdf.status_code == 200
    assert b"/Subtype /Image" in pdf.content

    docx = client.get(f"/api/v1/docs/{doc['id']}/export/file", headers=headers, params={"format": "docx"})
    assert docx.status_code == 200
    document = Document(BytesIO(docx.content))
    assert len(document.inline_shapes) == 1
