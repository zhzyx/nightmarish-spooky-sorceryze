"""Small command line client for the Tianxuan HTTP API.

Every command maps to exactly one API call and prints the parsed JSON response
to stdout, so the tool is easy to consume from scripts and AI agents. Failures
are reported on stderr with a non-zero exit status.

Authentication is resolved once in :func:`build_client`: a token produces an
``Authorization: Bearer`` header, otherwise an explicit actor produces
``X-Actor``. Importing this module has no side effects.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

DEFAULT_API = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT = 30.0


class CliError(Exception):
    """User-facing failure: reported on stderr, exit status 1."""


def build_client(
    base_url: str,
    token: str | None,
    actor: str | None,
    transport: httpx.BaseTransport | None = None,
) -> httpx.Client:
    """Build a client with the authentication header for this invocation.

    A configured token wins over ``actor``; ``X-Actor`` is only sent when no
    token is present and an actor was explicitly supplied. ``transport`` is
    injectable so tests can supply ``httpx.MockTransport``.
    """
    base = base_url.strip()
    if not base:
        raise CliError("--api must not be empty")

    headers: dict[str, str] = {}
    token_value = (token or "").strip()
    actor_value = (actor or "").strip()
    if token_value:
        headers["Authorization"] = f"Bearer {token_value}"
    elif actor_value:
        headers["X-Actor"] = actor_value

    return httpx.Client(
        base_url=base.rstrip("/") + "/",
        headers=headers,
        timeout=DEFAULT_TIMEOUT,
        transport=transport,
    )


# ---------- HTTP plumbing ----------


def _request(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    try:
        response = client.request(method, path, json=json_body, params=params)
    except (httpx.HTTPError, httpx.InvalidURL) as error:
        raise CliError(f"request failed: {error}") from error
    return _decode(response)


def _decode(response: httpx.Response) -> dict[str, Any]:
    if response.is_error:
        raise CliError(f"HTTP {response.status_code}: {_error_detail(response)}")
    try:
        payload = response.json()
    except ValueError as error:
        raise CliError(f"HTTP {response.status_code}: response is not valid JSON") from error
    if not isinstance(payload, dict):
        raise CliError(f"HTTP {response.status_code}: expected a JSON object, got {type(payload).__name__}")
    return {str(key): value for key, value in payload.items()}


def _error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()
        return text or response.reason_phrase
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
        if detail is not None:
            return json.dumps(detail, ensure_ascii=False)
    return json.dumps(payload, ensure_ascii=False)


def _quote_id(value: str) -> str:
    return quote(value.strip(), safe="")


def _read_text(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise CliError(f"cannot read {path}: {error}") from error


# ---------- auth ----------


def register(
    client: httpx.Client,
    tenant: str,
    email: str,
    password: str,
    name: str | None = None,
) -> dict[str, Any]:
    """Register a tenant together with its first user."""
    body: dict[str, Any] = {"tenant_name": tenant, "email": email, "password": password}
    if name is not None:
        body["name"] = name
    return _request(client, "POST", "api/v1/auth/register", json_body=body)


def login(client: httpx.Client, email: str, password: str) -> dict[str, Any]:
    """Create a session; the response contains the ``token`` field."""
    body = {"email": email, "password": password}
    return _request(client, "POST", "api/v1/auth/session", json_body=body)


# ---------- docs ----------


def list_docs(client: httpx.Client, kind: str | None = None) -> dict[str, Any]:
    params = {"kind": kind} if kind is not None else None
    return _request(client, "GET", "api/v1/docs", params=params)


def get_doc(client: httpx.Client, doc_id: str) -> dict[str, Any]:
    return _request(client, "GET", f"api/v1/docs/{_quote_id(doc_id)}")


def create_doc(client: httpx.Client, title: str, body: str, kind: str) -> dict[str, Any]:
    payload = {"title": title, "body_md": body, "kind": kind}
    return _request(client, "POST", "api/v1/docs", json_body=payload)


def patch_doc(
    client: httpx.Client,
    doc_id: str,
    expected_version: int,
    patches: Sequence[tuple[str, str]],
) -> dict[str, Any]:
    """Apply unique find/replace pairs against an expected document version."""
    payload: dict[str, Any] = {
        "expected_version": expected_version,
        "patches": [{"find": find, "replace": replace} for find, replace in patches],
    }
    return _request(client, "POST", f"api/v1/docs/{_quote_id(doc_id)}/patch", json_body=payload)


def merge_doc(
    client: httpx.Client,
    doc_id: str,
    expected_version: int,
    base_md: str,
    local_md: str,
) -> dict[str, Any]:
    """Three-way merge an offline draft (``local``) edited from ``base``."""
    payload = {"base_md": base_md, "local_md": local_md, "expected_version": expected_version}
    return _request(client, "POST", f"api/v1/docs/{_quote_id(doc_id)}/merge", json_body=payload)


# ---------- issues and board ----------


def list_issues(client: httpx.Client, status: str | None = None) -> dict[str, Any]:
    params = {"status": status} if status is not None else None
    return _request(client, "GET", "api/v1/issues", params=params)


def get_board(client: httpx.Client) -> dict[str, Any]:
    return _request(client, "GET", "api/v1/board")


# ---------- requirements ----------


def create_requirement(
    client: httpx.Client,
    request_id: str,
    title: str,
    outcome: str,
    scope: str,
    acceptance: str,
) -> dict[str, Any]:
    payload = {
        "request_id": request_id,
        "title": title,
        "outcome": outcome,
        "scope": scope,
        "acceptance": acceptance,
    }
    return _request(client, "POST", "api/v1/requirements", json_body=payload)


def export_requirement(client: httpx.Client, request_id: str) -> dict[str, Any]:
    return _request(client, "GET", f"api/v1/requirements/{_quote_id(request_id)}/export")


# ---------- command adapters ----------


def _cmd_register(client: httpx.Client, args: argparse.Namespace) -> dict[str, Any]:
    return register(client, args.tenant, args.email, args.password, args.name)


def _cmd_login(client: httpx.Client, args: argparse.Namespace) -> dict[str, Any]:
    return login(client, args.email, args.password)


def _cmd_docs_list(client: httpx.Client, args: argparse.Namespace) -> dict[str, Any]:
    return list_docs(client, args.kind)


def _cmd_docs_get(client: httpx.Client, args: argparse.Namespace) -> dict[str, Any]:
    return get_doc(client, args.id)


def _cmd_docs_create(client: httpx.Client, args: argparse.Namespace) -> dict[str, Any]:
    return create_doc(client, args.title, args.body, args.kind)


def _cmd_docs_patch(client: httpx.Client, args: argparse.Namespace) -> dict[str, Any]:
    finds: list[str] = args.find
    replaces: list[str] = args.replace
    if len(finds) != len(replaces):
        raise CliError("--find and --replace must be given in matching pairs")
    patches = list(zip(finds, replaces, strict=True))
    return patch_doc(client, args.id, args.expected_version, patches)


def _cmd_docs_merge(client: httpx.Client, args: argparse.Namespace) -> dict[str, Any]:
    return merge_doc(
        client,
        args.id,
        args.expected_version,
        _read_text(args.base),
        _read_text(args.local),
    )


def _cmd_issues_list(client: httpx.Client, args: argparse.Namespace) -> dict[str, Any]:
    return list_issues(client, args.status)


def _cmd_board(client: httpx.Client, args: argparse.Namespace) -> dict[str, Any]:
    return get_board(client)


def _cmd_requirements_create(client: httpx.Client, args: argparse.Namespace) -> dict[str, Any]:
    return create_requirement(client, args.request_id, args.title, args.outcome, args.scope, args.acceptance)


def _cmd_requirements_export(client: httpx.Client, args: argparse.Namespace) -> dict[str, Any]:
    return export_requirement(client, args.request_id)


# ---------- argument parsing ----------


def build_parser() -> argparse.ArgumentParser:
    """Build the parser; environment defaults are read here, not at import."""
    parser = argparse.ArgumentParser(
        prog="tianxuan",
        description="Small CLI for the Tianxuan HTTP API. Every command prints JSON.",
    )
    parser.add_argument(
        "--api",
        default=os.environ.get("TIANXUAN_API") or DEFAULT_API,
        help="API base URL (env: TIANXUAN_API; default: %(default)s)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("TIANXUAN_TOKEN") or None,
        help="Bearer token (env: TIANXUAN_TOKEN)",
    )
    parser.add_argument(
        "--actor",
        default=None,
        help="X-Actor user ID, used only when no token is configured",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    register_parser = commands.add_parser("register", help="Register a tenant and its first user")
    register_parser.add_argument("--tenant", required=True, help="Tenant name")
    register_parser.add_argument("--email", required=True, help="Owner email")
    register_parser.add_argument("--password", required=True, help="Owner password")
    register_parser.add_argument("--name", default=None, help="Owner display name")
    register_parser.set_defaults(func=_cmd_register)

    login_parser = commands.add_parser("login", help="Create a session and print its token")
    login_parser.add_argument("--email", required=True, help="Account email")
    login_parser.add_argument("--password", required=True, help="Account password")
    login_parser.set_defaults(func=_cmd_login)

    docs_parser = commands.add_parser("docs", help="Read and edit Wenqu documents")
    docs_commands = docs_parser.add_subparsers(dest="docs_command", required=True, metavar="COMMAND")

    docs_list = docs_commands.add_parser("list", help="List documents")
    docs_list.add_argument("--kind", default=None, help="Filter by document kind")
    docs_list.set_defaults(func=_cmd_docs_list)

    docs_get = docs_commands.add_parser("get", help="Show one document")
    docs_get.add_argument("id", help="Document ID")
    docs_get.set_defaults(func=_cmd_docs_get)

    docs_create = docs_commands.add_parser("create", help="Create a document")
    docs_create.add_argument("--title", required=True, help="Document title")
    docs_create.add_argument("--body", default="", help="Markdown body")
    docs_create.add_argument("--kind", default="doc", help="Document kind (default: doc)")
    docs_create.set_defaults(func=_cmd_docs_create)

    docs_patch = docs_commands.add_parser("patch", help="Apply unique find/replace pairs")
    docs_patch.add_argument("id", help="Document ID")
    docs_patch.add_argument("--expected-version", type=int, required=True, help="Version the edit is based on")
    docs_patch.add_argument(
        "--find", action="append", required=True, metavar="TEXT", help="Text to replace (repeatable)"
    )
    docs_patch.add_argument(
        "--replace",
        action="append",
        default=[],
        metavar="TEXT",
        help="Replacement for the matching --find (repeatable)",
    )
    docs_patch.set_defaults(func=_cmd_docs_patch)

    docs_merge = docs_commands.add_parser("merge", help="Merge an offline draft")
    docs_merge.add_argument("id", help="Document ID")
    docs_merge.add_argument("--expected-version", type=int, required=True, help="Version the draft is based on")
    docs_merge.add_argument("--base", required=True, metavar="FILE", help="UTF-8 file with the common base")
    docs_merge.add_argument("--local", required=True, metavar="FILE", help="UTF-8 file with the local draft")
    docs_merge.set_defaults(func=_cmd_docs_merge)

    issues_parser = commands.add_parser("issues", help="Read Sinan issues")
    issues_commands = issues_parser.add_subparsers(dest="issues_command", required=True, metavar="COMMAND")
    issues_list = issues_commands.add_parser("list", help="List issues")
    issues_list.add_argument("--status", default=None, help="Filter by issue status")
    issues_list.set_defaults(func=_cmd_issues_list)

    board_parser = commands.add_parser("board", help="Show the issue board grouped by status")
    board_parser.set_defaults(func=_cmd_board)

    requirements_parser = commands.add_parser("requirements", help="Create and export Yanshi requirements")
    requirement_commands = requirements_parser.add_subparsers(
        dest="requirements_command",
        required=True,
        metavar="COMMAND",
    )

    requirements_create = requirement_commands.add_parser("create", help="Create a requirement document")
    requirements_create.add_argument("--request-id", required=True, help="Stable request ID")
    requirements_create.add_argument("--title", required=True, help="Requirement title")
    requirements_create.add_argument("--outcome", required=True, help="Expected outcome")
    requirements_create.add_argument("--scope", required=True, help="Scope of the change")
    requirements_create.add_argument("--acceptance", required=True, help="Acceptance criteria")
    requirements_create.set_defaults(func=_cmd_requirements_create)

    requirements_export = requirement_commands.add_parser("export", help="Export a requirement as Markdown")
    requirements_export.add_argument("request_id", help="Request ID")
    requirements_export.set_defaults(func=_cmd_requirements_export)

    return parser


# ---------- entry point ----------


def _emit(payload: dict[str, Any]) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def main(argv: Sequence[str] | None = None) -> int:
    """Run one command; return the process exit status."""
    args = build_parser().parse_args(argv)
    handler: Callable[[httpx.Client, argparse.Namespace], dict[str, Any]] = args.func
    try:
        with build_client(args.api, args.token, args.actor) as client:
            payload = handler(client, args)
    except CliError as error:
        print(f"tianxuan: error: {error}", file=sys.stderr)
        return 1
    _emit(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
