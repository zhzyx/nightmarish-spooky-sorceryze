"""Preview one versioned design paragraph while preserving its surrounding Markdown."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from fastapi import HTTPException
from gateway import ModelGateway, workspace_reply
from pydantic import BaseModel, Field
from tianxuan_core import Tianxuan, VersionConflict

# String.strip_edges() in the native paragraph picker treats code points <= 32 as whitespace.
GODOT_EDGE_WHITESPACE = "".join(chr(i) for i in range(33))


class ParagraphSuggestion(BaseModel):
    expected_version: int = Field(strict=True, ge=1)
    paragraph: int = Field(strict=True, ge=1)
    instruction: str = Field(min_length=1, max_length=4000)


def paragraph_span(body: str, number: int) -> tuple[int, int]:
    # The Godot picker groups consecutive nonblank LF/CRLF lines. Spans exclude
    # the final line ending so even mixed separators survive accepting a change.
    start = None
    end = 0
    count = 0
    for line in re.finditer(r"([^\n]*)(?:\n|$)", body):
        content = line[1].removesuffix("\r")
        if not content.strip(GODOT_EDGE_WHITESPACE):
            if start is not None and count == number:
                return start, end
            start = None
        else:
            if start is None:
                count += 1
                start = line.start()
            end = line.start() + len(content)
    raise VersionConflict("paragraph does not exist in the specified document revision")


def suggest_paragraph(
    store: Tianxuan, gateway: ModelGateway | None, actor: str, doc_id: str, payload: ParagraphSuggestion
) -> dict[str, Any]:
    tenant = store.actor_context(actor)["tenant"]
    if os.environ.get("TIANXUAN_AUTH_MODE") == "accounts" and tenant != os.environ.get("TIANXUAN_TENANT_ID"):
        raise HTTPException(403, "this workspace has no access to the configured model")
    instruction = payload.instruction.strip()
    if not instruction:
        raise HTTPException(422, "please describe the requested edit")
    body = store.editable_doc_body(actor, doc_id, payload.expected_version)
    start, end = paragraph_span(body, payload.paragraph)
    original = body[start:end]
    reply = workspace_reply(
        gateway,
        tenant,
        actor,
        [
            {
                "role": "system",
                "content": "Revise only the supplied Markdown paragraph according to the instruction. "
                "Return one replacement paragraph, preserving meaningful indentation. Do not add commentary.",
            },
            {
                "role": "user",
                "content": json.dumps({"paragraph": original, "instruction": instruction}, ensure_ascii=False),
            },
        ],
    )
    replacement = reply["content"].strip("\r\n").replace("\r\n", "\n")
    if "\r" in replacement or any(not line.strip(GODOT_EDGE_WHITESPACE) for line in replacement.split("\n")):
        raise HTTPException(502, "the model must return a single nonblank paragraph")
    use_crlf = "\r\n" in original
    if "\n" not in original:
        use_crlf = body.startswith("\r\n", end) or (end == len(body) and body.endswith("\r\n", 0, start))
    if use_crlf:
        replacement = replacement.replace("\n", "\r\n")
    # Check again after the model call, which runs outside the database lock.
    store.editable_doc_body(actor, doc_id, payload.expected_version)
    return {
        "document_id": doc_id,
        "expected_version": payload.expected_version,
        "paragraph": payload.paragraph,
        "original": original,
        "replacement": replacement,
        "candidate_body": body[:start] + replacement + body[end:],
    }
