"""Markdown → DOCX 导出（python-docx）。"""

from __future__ import annotations

import re
from io import BytesIO

from docx import Document
from docx.shared import Pt

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_UNORDERED = re.compile(r"^[-*]\s+(.*)$")
_ORDERED = re.compile(r"^\d+\.\s+(.*)$")
_FENCE = re.compile(r"^```")
_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")


def _plain(text: str) -> str:
    text = _IMAGE.sub(r"\1", text)
    text = _LINK.sub(r"\1", text)
    return text.replace("`", "").replace("**", "").replace("*", "").strip()


def render_docx(title: str, body_md: str) -> bytes:
    document = Document()
    document.core_properties.title = title
    document.add_heading(title, level=0)

    code_lines: list[str] = []
    in_code = False
    for line in body_md.splitlines():
        if _FENCE.match(line.strip()):
            if in_code:
                paragraph = document.add_paragraph()
                run = paragraph.add_run("\n".join(code_lines))
                run.font.name = "Consolas"
                run.font.size = Pt(9)
                code_lines.clear()
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(line)
            continue
        stripped = line.strip()
        if not stripped:
            continue
        heading = _HEADING.match(stripped)
        if heading:
            document.add_heading(_plain(heading.group(2)), level=min(len(heading.group(1)), 4))
            continue
        unordered = _UNORDERED.match(stripped)
        if unordered:
            document.add_paragraph(_plain(unordered.group(1)), style="List Bullet")
            continue
        ordered = _ORDERED.match(stripped)
        if ordered:
            document.add_paragraph(_plain(ordered.group(1)), style="List Number")
            continue
        if stripped.startswith(">"):
            document.add_paragraph(_plain(stripped[1:].strip()), style="Quote")
            continue
        document.add_paragraph(_plain(stripped))

    if in_code and code_lines:
        paragraph = document.add_paragraph()
        run = paragraph.add_run("\n".join(code_lines))
        run.font.name = "Consolas"
        run.font.size = Pt(9)

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()
