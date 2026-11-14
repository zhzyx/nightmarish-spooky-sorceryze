"""Markdown 导出渲染测试。"""

from __future__ import annotations

from markdown_render import render_markdown


def test_render_blocks_and_inline() -> None:
    rendered = render_markdown(
        "# 标题\n\n**加粗** 与 *斜体* 与 `code`\n\n- 一\n- 二\n\n1. 甲\n2. 乙\n\n```py\nprint(1)\n```\n"
    )
    assert "<h1>标题</h1>" in rendered
    assert "<strong>加粗</strong>" in rendered
    assert "<em>斜体</em>" in rendered
    assert "<code>code</code>" in rendered
    assert "<ul><li>一</li><li>二</li></ul>" in rendered
    assert "<ol><li>甲</li><li>乙</li></ol>" in rendered
    assert '<pre><code class="language-py">print(1)</code></pre>' in rendered


def test_render_escapes_html_and_rejects_unsafe_links() -> None:
    rendered = render_markdown(
        "<script>alert(1)</script>\n\n[x](javascript:alert(1))\n\n[ok](https://example.com/a?b=1&c=2)\n\n"
        "```\n<img src=x onerror=alert(1)>\n```\n"
    )
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered
    assert 'href="javascript:' not in rendered
    assert '<a href="https://example.com/a?b=1&amp;c=2" rel="noreferrer">ok</a>' in rendered
    assert "&lt;img src=x onerror=alert(1)&gt;" in rendered


def test_render_unclosed_fence_still_escapes() -> None:
    rendered = render_markdown("```\n<b>未闭合\n")
    assert "<b>" not in rendered
    assert "&lt;b&gt;未闭合" in rendered


def test_render_tables_quotes_images_and_rules() -> None:
    rendered = render_markdown(
        "> 引用一行\n\n"
        "| 名称 | 值 |\n"
        "| --- | --- |\n"
        "| A | 1 |\n"
        "| B | 2 |\n\n"
        "![图](https://example.com/x.png)\n\n"
        "![坏](javascript:alert(1))\n\n"
        "---\n"
    )
    assert "<blockquote>引用一行</blockquote>" in rendered
    assert "<table><thead><tr><th>名称</th><th>值</th></tr></thead>" in rendered
    assert "<td>A</td><td>1</td>" in rendered
    assert '<img src="https://example.com/x.png" alt="图" loading="lazy" />' in rendered
    assert "javascript:" not in rendered
    assert "<hr />" in rendered
