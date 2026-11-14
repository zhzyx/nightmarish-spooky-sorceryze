"""Markdown → PDF 导出（reportlab，内置 CJK CID 字体）。"""

from __future__ import annotations

import re
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, Preformatted, SimpleDocTemplate, Spacer

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
_FONT = "STSong-Light"

_TITLE = ParagraphStyle("Title", fontName=_FONT, fontSize=20, leading=28, spaceAfter=14)
_HEADING = ParagraphStyle("Heading", fontName=_FONT, fontSize=14, leading=21, spaceBefore=10, spaceAfter=4)
_BODY = ParagraphStyle("Body", fontName=_FONT, fontSize=10.5, leading=17, spaceAfter=4)
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
_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")


def _plain(text: str) -> str:
    text = _IMAGE.sub(r"\1", text)
    text = _LINK.sub(r"\1", text)
    return text.replace("`", "").replace("**", "").replace("*", "").strip()


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
    code_lines: list[str] = []
    in_code = False
    for line in body_md.splitlines():
        stripped = line.strip()
        if _FENCE.match(stripped):
            if in_code:
                flowables.append(Preformatted("\n".join(code_lines), _CODE))
                flowables.append(Spacer(1, 4))
                code_lines.clear()
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not stripped:
            continue
        heading = _HEADING_MD.match(stripped)
        if heading:
            flowables.append(Paragraph(escape(_plain(heading.group(2))), _HEADING))
            continue
        unordered = _UNORDERED.match(stripped)
        if unordered:
            flowables.append(Paragraph("• " + escape(_plain(unordered.group(1))), _BODY))
            continue
        ordered = _ORDERED.match(stripped)
        if ordered:
            flowables.append(Paragraph("• " + escape(_plain(ordered.group(1))), _BODY))
            continue
        if stripped.startswith(">"):
            flowables.append(Paragraph(escape(_plain(stripped[1:].strip())), _QUOTE))
            continue
        flowables.append(Paragraph(escape(_plain(stripped)), _BODY))

    if in_code and code_lines:
        flowables.append(Preformatted("\n".join(code_lines), _CODE))
    document.build(flowables)
    return buffer.getvalue()
