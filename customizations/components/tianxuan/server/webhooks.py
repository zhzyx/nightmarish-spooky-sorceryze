"""Gitea webhook 签名校验与事件归一化。

纯函数模块：不导入 FastAPI、数据库或 HTTP 客户端，便于单元测试与复用。签名采用
Gitea 约定的 HMAC-SHA256（``X-Gitea-Signature`` 十六进制，可选 ``sha256=`` 前缀）。
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from typing import Any

SUPPORTED_EVENTS = frozenset({"push", "pull_request"})


def verify_gitea_signature(secret: str, body: bytes, signature: str) -> bool:
    """校验 webhook 签名；secret、签名或请求体缺失时返回 False。"""
    if not isinstance(secret, str) or not secret:
        return False
    if not isinstance(signature, str) or not signature.strip():
        return False
    candidate = signature.strip().lower()
    if candidate.startswith("sha256="):
        candidate = candidate[len("sha256=") :]
    expected = hmac.new(secret.encode("utf-8"), bytes(body), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, candidate)


def _mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _number(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _repository(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    repository = _mapping(payload.get("repository"))
    if repository is None:
        return None
    full_name = _text(repository.get("full_name"))
    owner, separator, name = full_name.partition("/")
    if not separator or not owner or not name or "/" in name:
        return None
    return {
        "provider": "gitea",
        "owner": owner,
        "name": name,
        "full_name": full_name,
        "html_url": _text(repository.get("html_url")),
        "default_branch": _text(repository.get("default_branch")),
    }


def summarize_gitea_event(event: str, payload: Any) -> dict[str, Any] | None:
    """把受支持的 Gitea 事件归一化为 ``type/target/payload``；其他事件返回 ``None``。"""
    if not isinstance(event, str) or event not in SUPPORTED_EVENTS:
        return None
    if not isinstance(payload, Mapping):
        return None
    repository = _repository(payload)
    if repository is None:
        return None
    target = repository["full_name"]

    if event == "push":
        commits = payload.get("commits")
        pusher = _mapping(payload.get("pusher")) or {}
        return {
            "type": "repo.push",
            "target": target,
            "payload": {
                **repository,
                "ref": _text(payload.get("ref")),
                "before": _text(payload.get("before")),
                "after": _text(payload.get("after")),
                "created": bool(payload.get("created", False)),
                "deleted": bool(payload.get("deleted", False)),
                "forced": bool(payload.get("forced", False)),
                "commits": len(commits) if isinstance(commits, list) else 0,
                "pusher": _text(pusher.get("login")),
            },
        }

    pull_request = _mapping(payload.get("pull_request"))
    if pull_request is None:
        return None
    head = _mapping(pull_request.get("head")) or {}
    base = _mapping(pull_request.get("base")) or {}
    user = _mapping(pull_request.get("user")) or {}
    return {
        "type": "repo.pull_request",
        "target": target,
        "payload": {
            **repository,
            "action": _text(payload.get("action")),
            "number": _number(pull_request.get("number")),
            "title": _text(pull_request.get("title")),
            "state": _text(pull_request.get("state")),
            "merged": bool(pull_request.get("merged", False)),
            "html_url": _text(pull_request.get("html_url")),
            "user": _text(user.get("login")),
            "head": _text(head.get("ref")),
            "head_sha": _text(head.get("sha")),
            "base": _text(base.get("ref")),
            "base_sha": _text(base.get("sha")),
        },
    }
