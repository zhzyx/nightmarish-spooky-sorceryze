"""文曲：AI 阅读优先的 Markdown 文档工具。

与 ``customizations/components/tianxuan/server/tianxuan_core.py`` 的 Markdown 约定一致：
frontmatter（``id``/``title``/``lang``/``kind``/``version``，需求文档保留 ``request_id``）、
``[[wiki-link]]`` 引用、标题锚点写作 ``{#anchor}``。本模块只做确定性的纯函数变换，
不依赖网络与模型，供文档索引、检索、导出和离线合并复用。
"""

from __future__ import annotations

import difflib
import hashlib
import math
import re
from typing import Any, TypedDict

__all__ = [
    "build_ai_index",
    "classify",
    "export_markdown",
    "merge_offline",
    "normalize_markdown",
    "search",
]


class _Hunk(TypedDict):
    side: str
    start: int
    end: int
    lines: list[str]


FRONTMATTER_KEYS = ("id", "title", "lang", "kind", "version")

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_LATIN_RE = re.compile(r"[A-Za-z]{3,}")
_HEADING_RE = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$")
_ANCHOR_RE = re.compile(r"\s*\{#([^}]*)\}\s*$")
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_CLOSING_HASHES_RE = re.compile(r"\s+#+\s*$")

_LABEL_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("requirement", re.compile(r"需求|验收|acceptance|requirement", re.I)),
    ("design", re.compile(r"设计|架构|design|architecture", re.I)),
    ("ticket", re.compile(r"工单|缺陷|issue|ticket|bug", re.I)),
    ("code", re.compile(r"代码|提交|分支|commit|branch|pull request|\bpr\b", re.I)),
)


# ---------- 通用解析 ----------


def _to_lf(text: str) -> str:
    """统一换行为 LF，并去掉行首 UTF-8 BOM。"""
    return text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


def _frontmatter_end(lines: list[str]) -> int:
    """返回 frontmatter 结束行下标；不存在时返回 -1。"""
    if not lines or lines[0].strip() != "---":
        return -1
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return index
    return -1


def _split_frontmatter(markdown: str) -> tuple[dict[str, str], str]:
    """拆分简单 frontmatter（键值行），返回元数据与正文。"""
    text = _to_lf(markdown)
    lines = text.split("\n")
    end = _frontmatter_end(lines)
    if end < 0:
        return {}, text
    meta: dict[str, str] = {}
    for line in lines[1:end]:
        clean = line.strip()
        if not clean or clean.startswith("#") or ":" not in clean:
            continue
        key, value = clean.split(":", 1)
        meta[key.strip()] = _unquote(value.strip())
    return meta, "\n".join(lines[end + 1 :])


def _fence_flags(lines: list[str]) -> list[bool]:
    """标记 Markdown 围栏代码行，围栏内的 ``#`` 不是标题。"""
    flags: list[bool] = []
    fence: tuple[str, int] | None = None
    for line in lines:
        match = _FENCE_RE.match(line)
        if fence is None:
            if match is None:
                flags.append(False)
            else:
                fence = (match.group(1)[0], len(match.group(1)))
                flags.append(True)
            continue
        flags.append(True)
        if match is not None and match.group(1)[0] == fence[0] and len(match.group(1)) >= fence[1]:
            fence = None
    return flags


def _parse_heading(line: str) -> tuple[int, str, str | None] | None:
    """解析 ATX 标题，返回（级别、标题文本、显式锚点）。"""
    match = _HEADING_RE.match(line)
    if match is None:
        return None
    level = len(match.group(1))
    text = _CLOSING_HASHES_RE.sub("", (match.group(2) or "").strip()).strip()
    explicit: str | None = None
    anchor_match = _ANCHOR_RE.search(text)
    if anchor_match is not None:
        explicit = _slugify(anchor_match.group(1))
        text = text[: anchor_match.start()].strip()
    if not text:
        return None
    return level, text, explicit


def _headings(markdown: str) -> list[dict[str, Any]]:
    lines = markdown.split("\n")
    frontmatter_end = _frontmatter_end(lines)
    flags = _fence_flags(lines)
    headings: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        if index <= frontmatter_end or flags[index]:
            continue
        parsed = _parse_heading(line)
        if parsed is None:
            continue
        level, text, anchor = parsed
        headings.append({"level": level, "text": text, "anchor": anchor})
    return headings


def _slugify(text: str) -> str:
    """由标题文本生成稳定锚点；保留中日韩字符与单词字符。"""
    value = _ANCHOR_RE.sub("", text)
    value = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", value)
    value = _WIKI_LINK_RE.sub(r"\1", value)
    value = re.sub(r"<[^>]+>", "", value)
    value = value.replace("`", "").replace("*", "").replace("~", "")
    value = value.lower()
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"[^\w-]", "", value, flags=re.UNICODE)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "section"


def _unique_anchor(base: str, used: set[str]) -> str:
    anchor = base
    suffix = 1
    while anchor in used:
        anchor = f"{base}-{suffix}"
        suffix += 1
    return anchor


def _prose(markdown: str) -> str:
    """语言提示只看正文：去掉 frontmatter、代码块、链接目标与行内代码。"""
    body = _split_frontmatter(markdown)[1]
    lines = body.split("\n")
    flags = _fence_flags(lines)
    text = "\n".join(line for index, line in enumerate(lines) if not flags[index])
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[\[[^\]]*\]\]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"https?://\S+", " ", text)


def _summary(markdown: str) -> str:
    body = _split_frontmatter(markdown)[1]
    lines = body.split("\n")
    flags = _fence_flags(lines)
    for index, line in enumerate(lines):
        if flags[index]:
            continue
        clean = line.strip()
        if clean and not clean.startswith(("#", "---", ">", "-", "*", "|", "`", "<!--")):
            return clean
    return ""


def _language_hint(text: str) -> str:
    has_cjk = _CJK_RE.search(text) is not None
    has_latin = _LATIN_RE.search(text) is not None
    if has_cjk and has_latin:
        return "mixed"
    if has_cjk:
        return "zh"
    if has_latin:
        return "en"
    return "und"


def _estimate_tokens(markdown: str) -> int:
    """粗略 token 估算：中文字符按 1 个计，其余非空白字符按 4 个 1 token 计。"""
    cjk = len(_CJK_RE.findall(markdown))
    compact = re.sub(r"\s+", "", markdown)
    remaining = max(0, len(compact) - cjk)
    return cjk + math.ceil(remaining / 4)


def _document_body(document: dict[str, Any]) -> str:
    for key in ("body_md", "body", "markdown", "content"):
        value = document.get(key)
        if value is not None:
            return _to_lf(str(value))
    return ""


def _yaml_scalar(value: Any) -> str:
    """只生成简单标量；含特殊字符时使用双引号，保证 frontmatter 可回读。"""
    text = "" if value is None else re.sub(r"[\r\n]+", " ", str(value)).strip()
    plain = re.fullmatch(r"[A-Za-z0-9\u4e00-\u9fff_][A-Za-z0-9\u4e00-\u9fff _. \-]*", text)
    if plain is not None and ": " not in text and " #" not in text:
        return text
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _pick(document_value: Any, frontmatter_value: Any, default: Any) -> Any:
    if document_value is not None:
        return document_value
    if frontmatter_value is not None:
        return frontmatter_value
    return default


# ---------- 索引与归类 ----------


def normalize_markdown(markdown: str) -> str:
    """规范化 Markdown：LF、行尾无空格、单个结尾换行、稳定标题锚点。"""
    text = _to_lf(markdown)
    lines = [line.rstrip() for line in text.split("\n")]
    frontmatter_end = _frontmatter_end(lines)
    flags = _fence_flags(lines)
    used: set[str] = set()
    output: list[str] = []
    for index, line in enumerate(lines):
        if index > frontmatter_end and not flags[index]:
            parsed = _parse_heading(line)
            if parsed is not None:
                level, heading_text, explicit = parsed
                anchor = _unique_anchor(explicit or _slugify(heading_text), used)
                used.add(anchor)
                line = f"{'#' * level} {heading_text} {{#{anchor}}}"
        output.append(line)
    while output and not output[-1].strip():
        output.pop()
    if not output:
        return ""
    return "\n".join(output) + "\n"


def build_ai_index(markdown: str) -> dict[str, Any]:
    """构建 AI 阅读索引：标题与锚点、wiki 链接、摘要、语言、token 估算与内容哈希。"""
    normalized = normalize_markdown(markdown)
    return {
        "headings": _headings(normalized),
        "links": sorted(set(_WIKI_LINK_RE.findall(normalized))),
        "summary": _summary(normalized),
        "language": _language_hint(_prose(normalized)),
        "estimated_tokens": _estimate_tokens(normalized),
        "content_hash": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
    }


def classify(markdown: str) -> list[str]:
    """规则多标签归类，按 requirement/design/ticket/code/zh/en 固定顺序返回。"""
    text = _to_lf(markdown)
    tags = [label for label, pattern in _LABEL_RULES if pattern.search(text)]
    prose = _prose(text)
    if _CJK_RE.search(prose) is not None:
        tags.append("zh")
    if _LATIN_RE.search(prose) is not None:
        tags.append("en")
    return tags


# ---------- 检索 ----------


def _query_terms(needle: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()

    def add(term: str) -> None:
        if term and term not in seen:
            seen.add(term)
            terms.append(term)

    add(needle)
    for token in re.findall(r"[^\W_]+", needle, flags=re.UNICODE):
        add(token)
        if _CJK_RE.fullmatch(token) is not None and len(token) > 2:
            for start in range(len(token) - 1):
                add(token[start : start + 2])
    return terms


def _heading_texts(document: dict[str, Any], body: str) -> list[str]:
    provided = document.get("headings")
    if isinstance(provided, list):
        texts = []
        for heading in provided:
            if isinstance(heading, dict):
                value = heading.get("text") or heading.get("title")
            else:
                value = heading
            if value:
                texts.append(str(value).lower())
        if texts:
            return texts
    return [heading["text"].lower() for heading in _headings(body)]


def _score_document(needle: str, terms: list[str], title: str, body: str, headings: list[str]) -> int:
    score = 0
    for term in terms:
        score += min(title.count(term), 3) * 6
        score += min(sum(1 for heading in headings if term in heading), 3) * 3
        score += min(body.count(term), 6)
    if needle in title:
        score += 8
    if needle in body:
        score += 2
    return score


def _snippet(body: str, needle: str, terms: list[str], limit: int = 120) -> str:
    text = re.sub(r"\s+", " ", body).strip()
    if not text:
        return ""
    lowered = text.lower()
    index = -1
    for candidate in [needle, *terms]:
        found = lowered.find(candidate)
        if found >= 0 and (index < 0 or found < index):
            index = found
    if index < 0:
        return text[:limit] + ("…" if len(text) > limit else "")
    start = max(0, index - 40)
    end = min(len(text), start + limit)
    if start > 0 and end - start < limit:
        start = max(0, end - limit)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return prefix + text[start:end].strip() + suffix


def search(documents: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """无依赖检索：按标题、标题层级、正文加权排序，返回 id/score/snippet。"""
    needle = _to_lf(query).strip().lower()
    if not needle or not documents:
        return []
    terms = _query_terms(needle)
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for position, document in enumerate(documents):
        title = str(document.get("title") or "").lower()
        body = _split_frontmatter(_document_body(document))[1]
        body_lower = body.lower()
        headings = _heading_texts(document, body)
        score = _score_document(needle, terms, title, body_lower, headings)
        if score <= 0:
            continue
        ranked.append((
            -score,
            position,
            {"id": document.get("id"), "score": score, "snippet": _snippet(body, needle, terms)},
        ))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in ranked]


# ---------- 导出 ----------


def export_markdown(document: dict[str, Any]) -> str:
    """导出规范 Markdown：frontmatter 保留 id/title/lang/kind/version 与额外字段。"""
    meta, body = _split_frontmatter(_document_body(document))
    id_value = _pick(document.get("id"), meta.get("id"), "")
    title = _pick(document.get("title"), meta.get("title"), "")
    lang = _pick(document.get("lang"), meta.get("lang"), "zh")
    kind = _pick(document.get("kind"), meta.get("kind"), "doc")
    version = _pick(document.get("version"), meta.get("version"), 1)
    extras: dict[str, str] = {
        key: value for key, value in meta.items() if key not in FRONTMATTER_KEYS and value.strip()
    }
    request_id = document.get("request_id")
    if isinstance(request_id, str) and request_id.strip():
        extras.setdefault("request_id", request_id.strip())

    header = ["---"]
    header.extend([
        f"id: {_yaml_scalar(id_value)}",
        f"title: {_yaml_scalar(title)}",
        f"lang: {_yaml_scalar(lang)}",
        f"kind: {_yaml_scalar(kind)}",
        f"version: {_yaml_scalar(version)}",
    ])
    for key in sorted(extras):
        header.append(f"{key}: {_yaml_scalar(extras[key])}")
    header.append("---")

    exported_body = normalize_markdown(body).strip("\n")
    if not exported_body:
        return "\n".join(header) + "\n"
    return "\n".join(header) + "\n\n" + exported_body + "\n"


# ---------- 离线三方合并 ----------


def _merge_lines(markdown: str) -> list[str]:
    lines = [line.rstrip() for line in _to_lf(markdown).split("\n")]
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def _hunks(base: list[str], side: list[str], name: str) -> list[_Hunk]:
    matcher = difflib.SequenceMatcher(None, base, side, autojunk=False)
    hunks: list[_Hunk] = []
    for tag, base_start, base_end, side_start, side_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        hunks.append({
            "side": name,
            "start": base_start,
            "end": base_end,
            "lines": list(side[side_start:side_end]),
        })
    return hunks


def _hunk_overlaps(first: _Hunk, second: _Hunk) -> bool:
    first_start, first_end = first["start"], first["end"]
    second_start, second_end = second["start"], second["end"]
    if first_start == first_end and second_start == second_end:
        return first_start == second_start
    if first_start == first_end:
        return second_start <= first_start <= second_end
    if second_start == second_end:
        return first_start <= second_start <= first_end
    return max(first_start, second_start) < min(first_end, second_end)


def _group_hunks(hunks: list[_Hunk]) -> list[list[_Hunk]]:
    groups: list[list[_Hunk]] = []
    for hunk in sorted(hunks, key=lambda item: (item["start"], item["end"])):
        matched = next(
            (group for group in groups if any(_hunk_overlaps(hunk, other) for other in group)),
            None,
        )
        if matched is None:
            groups.append([hunk])
        else:
            matched.append(hunk)
    merged = True
    while merged:
        merged = False
        for index in range(len(groups)):
            for other_index in range(index + 1, len(groups)):
                if any(_hunk_overlaps(first, second) for first in groups[index] for second in groups[other_index]):
                    groups[index].extend(groups.pop(other_index))
                    merged = True
                    break
            if merged:
                break
    groups.sort(key=lambda group: min(item["start"] for item in group))
    return groups


def _apply_hunks(base: list[str], start: int, end: int, hunks: list[_Hunk]) -> list[str]:
    output: list[str] = []
    position = start
    for hunk in sorted(hunks, key=lambda item: (item["start"], item["end"])):
        output.extend(base[position : hunk["start"]])
        output.extend(hunk["lines"])
        position = hunk["end"]
    output.extend(base[position:end])
    return output


def _conflict_label(start: int, end: int, local_lines: int, remote_lines: int) -> str:
    location = f"lines {start + 1}-{end}" if end > start else f"line {start + 1}"
    return f"conflict at {location}: local {local_lines} line(s), remote {remote_lines} line(s)"


def _finish_lines(lines: list[str]) -> str:
    result = list(lines)
    while result and not result[-1].strip():
        result.pop()
    if not result:
        return ""
    return "\n".join(result) + "\n"


def merge_offline(base: str, local: str, remote: str) -> tuple[str, list[str]]:
    """按行三方合并；重叠修改写入 local/remote 冲突标记并返回冲突描述。"""
    base_lines = _merge_lines(base)
    local_lines = _merge_lines(local)
    remote_lines = _merge_lines(remote)
    if local_lines == base_lines:
        return _finish_lines(remote_lines), []
    if remote_lines == base_lines:
        return _finish_lines(local_lines), []
    if local_lines == remote_lines:
        return _finish_lines(local_lines), []

    groups = _group_hunks(_hunks(base_lines, remote_lines, "remote") + _hunks(base_lines, local_lines, "local"))
    merged: list[str] = []
    conflicts: list[str] = []
    position = 0
    for group in groups:
        start = min(hunk["start"] for hunk in group)
        end = max(hunk["end"] for hunk in group)
        merged.extend(base_lines[position:start])
        local_hunks = [hunk for hunk in group if hunk["side"] == "local"]
        remote_hunks = [hunk for hunk in group if hunk["side"] == "remote"]
        local_segment = _apply_hunks(base_lines, start, end, local_hunks)
        remote_segment = _apply_hunks(base_lines, start, end, remote_hunks)
        if not local_hunks:
            merged.extend(remote_segment)
        elif not remote_hunks:
            merged.extend(local_segment)
        elif local_segment == remote_segment:
            merged.extend(local_segment)
        else:
            merged.extend(["<<<<<<< local", *local_segment, "=======", *remote_segment, ">>>>>>> remote"])
            conflicts.append(_conflict_label(start, end, len(local_segment), len(remote_segment)))
        position = end
    merged.extend(base_lines[position:])
    return _finish_lines(merged), conflicts
