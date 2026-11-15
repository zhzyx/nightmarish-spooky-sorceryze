"""Markdown → PDF 导出（reportlab，内置 CJK CID 字体）。"""

from __future__ import annotations

import re
from io import BytesIO
from xml.sax.saxutils import escape

from markdown_images import parse_data_image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    Image,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
_FONT = "STSong-Light"

_TITLE = ParagraphStyle("Title", fontName=_FONT, fontSize=20, leading=28, spaceAfter=14)
_HEADING = ParagraphStyle("Heading", fontName=_FONT, fontSize=14, leading=21, spaceBefore=10, spaceAfter=4)
_BODY = ParagraphStyle("Body", fontName=_FONT, fontSize=10.5, leading=17, spaceAfter=4)
_CELL = ParagraphStyle("Cell", fontName=_FONT, fontSize=9, leading=12)
_CODE = ParagraphStyle(
    "Code",
    fontName=_FONT,
    fontSize=9,
    leading=13,
    backColor="#f5f2ea",
    borderPadding=6,
    spaceBefore=4,
    spaceAfter=8,
)
_QUOTE = ParagraphStyle("Quote", fontName=_FONT, fontSize=10, leading=16, leftIndent=14, textColor="#55504a")

_HEADING_MD = re.compile(r"^(#{1,6})\s+(.*)$")
_UNORDERED = re.compile(r"^[-*]\s+(.*)$")
_ORDERED = re.compile(r"^\d+\.\s+(.*)$")
_FENCE = re.compile(r"^```")
_TABLE_SEPARATOR = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$")
_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")


def _plain(text: str) -> str:
    text = _IMAGE.sub(r"\1", text)
    text = _LINK.sub(r"\1", text)
    return text.replace("`", "").replace("**", "").replace("*", "").strip()


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _table_flowables(headers: list[str], rows: list[list[str]]) -> Table:
    data: list[list[Paragraph]] = [[Paragraph(escape(cell), _CELL) for cell in headers]]
    for row in rows:
        padded = (row + [""] * len(headers))[: len(headers)]
        data.append([Paragraph(escape(cell), _CELL) for cell in padded])
    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0ece2")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9c0ae")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    return table


def _image_flowable(alt: str, data: bytes) -> Image:
    reader = ImageReader(BytesIO(data))
    width, height = reader.getSize()
    target_width = min(400.0, float(width))
    target_height = target_width * float(height) / float(width) if width else target_width
    return Image(BytesIO(data), width=target_width, height=target_height)


def render_pdf(title: str, body_md: str) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=title,
        leftMargin=46,
        rightMargin=46,
        topMargin=46,
        bottomMargin=46,
    )
    flowables: list[object] = [Paragraph(escape(title), _TITLE)]
    lines = body_md.splitlines()
    code_lines: list[str] = []
    in_code = False
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if _FENCE.match(stripped):
            if in_code:
                flowables.append(Preformatted("\n".join(code_lines), _CODE))
                flowables.append(Spacer(1, 4))
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
            try:
                flowables.append(_image_flowable(*image))
                flowables.append(Spacer(1, 8))
            except Exception:
                flowables.append(Paragraph(escape(_plain(stripped)), _BODY))
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
            flowables.append(_table_flowables(headers, rows))
            flowables.append(Spacer(1, 8))
            continue
        heading = _HEADING_MD.match(stripped)
        if heading:
            flowables.append(Paragraph(escape(_plain(heading.group(2))), _HEADING))
            index += 1
            continue
        unordered = _UNORDERED.match(stripped)
        if unordered:
            flowables.append(Paragraph("• " + escape(_plain(unordered.group(1))), _BODY))
            index += 1
            continue
        ordered = _ORDERED.match(stripped)
        if ordered:
            flowables.append(Paragraph("• " + escape(_plain(ordered.group(1))), _BODY))
            index += 1
            continue
        if stripped.startswith(">"):
            flowables.append(Paragraph(escape(_plain(stripped[1:].strip())), _QUOTE))
            index += 1
            continue
        flowables.append(Paragraph(escape(_plain(stripped)), _BODY))
        index += 1

    if in_code and code_lines:
        flowables.append(Preformatted("\n".join(code_lines), _CODE))
    document.build(flowables)
    return buffer.getvalue()
