"""Markdown 图片解析：data URI 直接解码，远程图片仅允许显式白名单主机。"""

from __future__ import annotations

import base64
import os
import re
import urllib.parse
import urllib.request

_IMAGE_LINE = re.compile(r"^!\[([^\]]*)\]\((data:image/(?:png|jpeg|jpg);base64,[^)]+|https?://[^)]+)\)$")
_MAX_BYTES = 5 * 1024 * 1024


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _allowed(url: str) -> bool:
    hosts = [item.strip() for item in os.environ.get("TIANXUAN_EXPORT_IMAGE_HOSTS", "").split(",") if item.strip()]
    if not hosts:
        return False
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme in {"http", "https"} and parsed.netloc in hosts


def parse_image(line: str) -> tuple[str, bytes] | None:
    match = _IMAGE_LINE.match(line.strip())
    if match is None:
        return None
    alt = match.group(1)
    source = match.group(2)
    if source.startswith("data:"):
        try:
            _header, payload = source.split(",", 1)
            return alt, base64.b64decode(payload, validate=True)
        except (ValueError, TypeError):
            return None
    if not _allowed(source):
        return None
    request = urllib.request.Request(source, headers={"User-Agent": "TianxuanExport/1.0"})
    try:
        with _OPENER.open(request, timeout=5.0) as response:
            if not _allowed(response.geturl()):
                return None
            if not response.headers.get_content_type().startswith("image/"):
                return None
            data = response.read(_MAX_BYTES + 1)
    except (OSError, ValueError):
        return None
    if len(data) > _MAX_BYTES:
        return None
    return alt, data


# 兼容旧调用方的名字；现在同时支持 data URI 与白名单远程图片。
parse_data_image = parse_image
