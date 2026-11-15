"""Markdown → DOCX 导出（python-docx）。"""

from __future__ import annotations

import re
from io import BytesIO

from docx import Document
from docx.document import Document as DocumentType
from docx.shared import Inches, Pt
from docx.table import _Cell
from docx.text.paragraph import Paragraph
from markdown_images import parse_data_image

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_UNORDERED = re.compile(r"^[-*]\s+(.*)$")
_ORDERED = re.compile(r"^\d+\.\s+(.*)$")
_FENCE = re.compile(r"^```")
_TABLE_SEPARATOR = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$")
_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_INLINE = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)")


def _plain(text: str) -> str:
    text = _IMAGE.sub(r"\1", text)
    text = _LINK.sub(r"\1", text)
    return text


def _add_runs(paragraph: Paragraph, text: str) -> None:
    for token in _INLINE.split(_plain(text)):
        if not token:
            continue
        if token.startswith("**") and token.endswith("**") and len(token) > 4:
            run = paragraph.add_run(token[2:-2])
            run.bold = True
        elif token.startswith("`") and token.endswith("`") and len(token) > 2:
            run = paragraph.add_run(token[1:-1])
            run.font.name = "Consolas"
            run.font.size = Pt(9)
        elif token.startswith("*") and token.endswith("*") and len(token) > 2:
            run = paragraph.add_run(token[1:-1])
            run.italic = True
        else:
            paragraph.add_run(token)


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _add_table(document: DocumentType, headers: list[str], rows: list[list[str]]) -> None:
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for index, header in enumerate(headers):
        cell: _Cell = table.rows[0].cells[index]
        cell.text = ""
        _add_runs(cell.paragraphs[0], header)
    for row in rows:
        padded = (row + [""] * len(headers))[: len(headers)]
        cells = table.add_row().cells
        for index, value in enumerate(padded):
            cells[index].text = ""
            _add_runs(cells[index].paragraphs[0], value)


def render_docx(title: str, body_md: str) -> bytes:
    document = Document()
    document.core_properties.title = title
    title_paragraph = document.add_heading("", level=0)
    _add_runs(title_paragraph, title)

    lines = body_md.splitlines()
    code_lines: list[str] = []
    in_code = False
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if _FENCE.match(stripped):
            if in_code:
                paragraph = document.add_paragraph()
                run = paragraph.add_run("\n".join(code_lines))
                run.font.name = "Consolas"
                run.font.size = Pt(9)
                code_lines.clear()
            in_code = not in_code
            index += 1
            continue
        if in_code:
            code_lines.append(line)
            index += 1
            continue
        if not stripped:
            index += 1
            continue

        image = parse_data_image(stripped)
        if image is not None:
            alt, data = image
            try:
                paragraph = document.add_paragraph()
                paragraph.add_run().add_picture(BytesIO(data), width=Inches(4))
            except Exception:
                _add_runs(document.add_paragraph(), alt or stripped)
            index += 1
            continue
        next_line = lines[index + 1].strip() if index + 1 < len(lines) else ""
        if "|" in stripped and _TABLE_SEPARATOR.match(next_line):
            headers = _cells(stripped)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip() and "|" in lines[index]:
                rows.append(_cells(lines[index]))
                index += 1
            _add_table(document, headers, rows)
            continue

        heading = _HEADING.match(stripped)
        if heading:
            paragraph = document.add_heading("", level=min(len(heading.group(1)), 4))
            _add_runs(paragraph, heading.group(2))
            index += 1
            continue
        unordered = _UNORDERED.match(stripped)
        if unordered:
            paragraph = document.add_paragraph(style="List Bullet")
            _add_runs(paragraph, unordered.group(1))
            index += 1
            continue
        ordered = _ORDERED.match(stripped)
        if ordered:
            paragraph = document.add_paragraph(style="List Number")
            _add_runs(paragraph, ordered.group(1))
            index += 1
            continue
        if stripped.startswith(">"):
            paragraph = document.add_paragraph(style="Quote")
            _add_runs(paragraph, stripped[1:].strip())
            index += 1
            continue
        paragraph = document.add_paragraph()
        _add_runs(paragraph, stripped)
        index += 1

    if in_code and code_lines:
        paragraph = document.add_paragraph()
        run = paragraph.add_run("\n".join(code_lines))
        run.font.name = "Consolas"
        run.font.size = Pt(9)

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()
