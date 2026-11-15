"""Markdown 图片解析（仅 data URI，避免导出时发起网络请求）。"""

from __future__ import annotations

import base64
import re

_DATA_IMAGE = re.compile(r"^!\[([^\]]*)\]\((data:image/(?:png|jpeg|jpg);base64,[^)]+)\)$")


def parse_data_image(line: str) -> tuple[str, bytes] | None:
    match = _DATA_IMAGE.match(line.strip())
    if match is None:
        return None
    header, payload = match.group(2).split(",", 1)
    try:
        return match.group(1), base64.b64decode(payload, validate=True)
    except (ValueError, TypeError):
        return None
