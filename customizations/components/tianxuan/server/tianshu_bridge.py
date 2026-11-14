"""天璇 → 天枢 互通桥。

天枢（引擎内工作台）通过本 CLI 读取/写入天璇文档、需求与工单；
天璇侧把外部工单标识（如 GitHub Issue URL）与文档/工单绑定。

用法：
    python tianshu_bridge.py --api http://127.0.0.1:8000 --actor usr_xxx \
        context --external-id https://github.com/owner/repo/issues/123

所有命令输出 JSON 信封：``{"ok": true, "data": ...}`` 或 ``{"ok": false, "error": "..."}``。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

TIMEOUT = 20
urlopen = urllib.request.urlopen


class BridgeError(Exception):
    """API 调用或参数错误。"""


def _endpoint(api: str, path: str, params: dict[str, str] | None = None) -> str:
    base = api.rstrip("/")
    if params:
        return f"{base}{path}?{urllib.parse.urlencode(params)}"
    return f"{base}{path}"


def _request(
    api: str,
    method: str,
    path: str,
    *,
    actor: str = "",
    token: str = "",
    params: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif actor:
        headers["X-Actor"] = actor
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(_endpoint(api, path, params), data=data, method=method, headers=headers)
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
        except ValueError:
            parsed = detail
        raise BridgeError(f"HTTP {error.code}: {parsed}") from error
    except urllib.error.URLError as error:
        raise BridgeError(f"API unreachable: {error.reason}") from error
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except ValueError as error:
        raise BridgeError("API returned non-JSON response") from error
    if not isinstance(parsed, dict):
        raise BridgeError("API response must be a JSON object")
    return parsed


def status(args: argparse.Namespace) -> dict[str, Any]:
    health = _request(args.api, "GET", "/api/v1/health", actor=args.actor, token=args.token)
    gitea = _request(args.api, "GET", "/api/v1/gitea/status", actor=args.actor, token=args.token)
    return {"health": health, "gitea": gitea}


def context(args: argparse.Namespace) -> dict[str, Any]:
    return _request(
        args.api,
        "GET",
        "/api/v1/external-context",
        actor=args.actor,
        token=args.token,
        params={"system": args.system, "external_id": args.external_id},
    )


def publish(args: argparse.Namespace) -> dict[str, Any]:
    tickets = [
        {"title": title, "acceptance": "", "type": args.ticket_type, "priority": "normal"} for title in args.ticket
    ]
    return _request(
        args.api,
        "POST",
        "/api/v1/requirements/from-external",
        actor=args.actor,
        token=args.token,
        body={
            "system": args.system,
            "external_id": args.external_id,
            "request_id": args.request_id,
            "title": args.title,
            "outcome": args.outcome,
            "scope": args.scope,
            "acceptance": args.acceptance,
            "tickets": tickets,
        },
    )


def link(args: argparse.Namespace) -> dict[str, Any]:
    return _request(
        args.api,
        "POST",
        "/api/v1/external-links",
        actor=args.actor,
        token=args.token,
        body={
            "system": args.system,
            "external_id": args.external_id,
            "target_type": args.target_type,
            "target_id": args.target_id,
        },
    )


def docs_list(args: argparse.Namespace) -> dict[str, Any]:
    params = {"kind": args.kind} if args.kind else None
    return _request(args.api, "GET", "/api/v1/docs", actor=args.actor, token=args.token, params=params)


def docs_get(args: argparse.Namespace) -> dict[str, Any]:
    return _request(
        args.api,
        "GET",
        f"/api/v1/docs/{urllib.parse.quote(args.doc_id, safe='')}",
        actor=args.actor,
        token=args.token,
    )


def issues_list(args: argparse.Namespace) -> dict[str, Any]:
    params: dict[str, str] = {}
    if args.status:
        params["status"] = args.status
    if args.requirement_id:
        params["requirement_id"] = args.requirement_id
    return _request(args.api, "GET", "/api/v1/issues", actor=args.actor, token=args.token, params=params or None)


def board(args: argparse.Namespace) -> dict[str, Any]:
    return _request(args.api, "GET", "/api/v1/board", actor=args.actor, token=args.token)


def _write(args: argparse.Namespace, envelope: dict[str, Any]) -> None:
    text = json.dumps(envelope, ensure_ascii=False, indent=2)
    if args.result:
        target = args.result
        temporary = target.with_suffix(target.suffix + ".partial")
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, target)
    print(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="天璇 ↔ 天枢互通桥")
    parser.add_argument("--api", default=os.environ.get("TIANXUAN_API", "http://127.0.0.1:8000"))
    parser.add_argument("--actor", default=os.environ.get("TIANXUAN_ACTOR", ""))
    parser.add_argument("--token", default=os.environ.get("TIANXUAN_TOKEN", ""))
    parser.add_argument("--result", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="天璇健康与 Gitea 状态").set_defaults(func=status)

    p = sub.add_parser("context", help="读取外部工单在天璇内的需求/文档/工单")
    p.add_argument("--system", default="tianshu")
    p.add_argument("--external-id", required=True)
    p.set_defaults(func=context)

    p = sub.add_parser("publish", help="从天枢工单创建天璇需求与工单树")
    p.add_argument("--system", default="tianshu")
    p.add_argument("--external-id", required=True)
    p.add_argument("--request-id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--outcome", required=True)
    p.add_argument("--scope", required=True)
    p.add_argument("--acceptance", required=True)
    p.add_argument("--ticket", action="append", default=[])
    p.add_argument("--ticket-type", default="task")
    p.set_defaults(func=publish)

    p = sub.add_parser("link", help="绑定外部工单到天璇文档或工单")
    p.add_argument("--system", default="tianshu")
    p.add_argument("--external-id", required=True)
    p.add_argument("--target-type", choices=["doc", "issue"], required=True)
    p.add_argument("--target-id", required=True)
    p.set_defaults(func=link)

    p = sub.add_parser("docs", help="文档读取")
    docs_sub = p.add_subparsers(dest="docs_command", required=True)
    p_list = docs_sub.add_parser("list")
    p_list.add_argument("--kind")
    p_list.set_defaults(func=docs_list)
    p_get = docs_sub.add_parser("get")
    p_get.add_argument("doc_id")
    p_get.set_defaults(func=docs_get)

    p = sub.add_parser("issues", help="工单读取")
    issues_sub = p.add_subparsers(dest="issues_command", required=True)
    p_list = issues_sub.add_parser("list")
    p_list.add_argument("--status")
    p_list.add_argument("--requirement-id")
    p_list.set_defaults(func=issues_list)

    sub.add_parser("board", help="工单看板").set_defaults(func=board)

    args = parser.parse_args(argv)
    try:
        data = args.func(args)
        envelope = {"ok": True, "data": data}
        code = 0
    except (BridgeError, ValueError) as error:
        envelope = {"ok": False, "error": str(error)}
        code = 1
    _write(args, envelope)
    return code


if __name__ == "__main__":
    sys.exit(main())
