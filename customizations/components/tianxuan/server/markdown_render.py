"""最小、安全的 Markdown → HTML 渲染。

只支持文档导出常用的块级/行内语法；所有文本先转义，再生成受控标签。
"""

from __future__ import annotations

import html
import re

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_UNORDERED = re.compile(r"^[-*]\s+(.*)$")
_ORDERED = re.compile(r"^\d+\.\s+(.*)$")
_FENCE = re.compile(r"^```([A-Za-z0-9_+-]*)\s*$")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_CODE_SPAN = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC = re.compile(r"\*([^*]+)\*")


def _inline(text: str) -> str:
    escaped = html.escape(text, quote=False)

    def code(match: re.Match[str]) -> str:
        return f"<code>{match.group(1)}</code>"

    def link(match: re.Match[str]) -> str:
        label = match.group(1)
        href = html.unescape(match.group(2))
        if not href.startswith(("http://", "https://")):
            return label
        return f'<a href="{html.escape(href, quote=True)}" rel="noreferrer">{label}</a>'

    escaped = _CODE_SPAN.sub(code, escaped)
    escaped = _LINK.sub(link, escaped)
    escaped = _BOLD.sub(r"<strong>\1</strong>", escaped)
    escaped = _ITALIC.sub(r"<em>\1</em>", escaped)
    return escaped


def render_markdown(text: str) -> str:
    lines = text.splitlines()
    output: list[str] = []
    paragraph: list[str] = []
    list_tag: str | None = None
    list_items: list[str] = []
    code_language = ""
    code_lines: list[str] = []
    in_code = False

    def flush_paragraph() -> None:
        if paragraph:
            output.append(f"<p>{_inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_tag
        if list_tag and list_items:
            items = "".join(f"<li>{_inline(item)}</li>" for item in list_items)
            output.append(f"<{list_tag}>{items}</{list_tag}>")
        list_tag = None
        list_items.clear()

    for line in lines:
        fence = _FENCE.match(line.strip())
        if fence:
            flush_paragraph()
            flush_list()
            if in_code:
                language = f' class="language-{code_language}"' if code_language else ""
                output.append(f"<pre><code{language}>{html.escape(chr(10).join(code_lines), quote=False)}</code></pre>")
                code_lines.clear()
                code_language = ""
                in_code = False
            else:
                in_code = True
                code_language = fence.group(1)
            continue
        if in_code:
            code_lines.append(line)
            continue

        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            flush_list()
            continue
        heading = _HEADING.match(stripped)
        if heading:
            flush_paragraph()
            flush_list()
            level = len(heading.group(1))
            output.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            continue
        unordered = _UNORDERED.match(stripped)
        if unordered:
            flush_paragraph()
            if list_tag != "ul":
                flush_list()
                list_tag = "ul"
            list_items.append(unordered.group(1))
            continue
        ordered = _ORDERED.match(stripped)
        if ordered:
            flush_paragraph()
            if list_tag != "ol":
                flush_list()
                list_tag = "ol"
            list_items.append(ordered.group(1))
            continue
        flush_list()
        paragraph.append(stripped)

    if in_code:
        language = f' class="language-{code_language}"' if code_language else ""
        output.append(f"<pre><code{language}>{html.escape(chr(10).join(code_lines), quote=False)}</code></pre>")
    flush_paragraph()
    flush_list()
    return "\n".join(output)
