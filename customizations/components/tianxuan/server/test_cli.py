"""Tianxuan CLI tests: every request goes through httpx.MockTransport."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
import tianxuan_cli
from tianxuan_cli import (
    CliError,
    build_client,
    build_parser,
    create_doc,
    create_requirement,
    export_requirement,
    get_board,
    list_docs,
    list_issues,
    login,
    patch_doc,
    register,
)

Handler = Callable[[httpx.Request], httpx.Response]
BASE_URL = "http://tianxuan.test"


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TIANXUAN_API", raising=False)
    monkeypatch.delenv("TIANXUAN_TOKEN", raising=False)


def _record(handler: Handler) -> tuple[list[httpx.Request], Handler]:
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    return seen, wrapped


def _client(handler: Handler, token: str | None = None, actor: str | None = None) -> httpx.Client:
    client: httpx.Client = build_client(BASE_URL, token, actor, transport=httpx.MockTransport(handler))
    return client


def _json(request: httpx.Request) -> dict[str, Any]:
    payload = json.loads(request.content)
    assert isinstance(payload, dict)
    return {str(key): value for key, value in payload.items()}


def _stub_main_client(monkeypatch: pytest.MonkeyPatch, handler: Handler) -> None:
    def fake_build(
        base_url: str,
        token: str | None,
        actor: str | None,
        transport: httpx.BaseTransport | None = None,
    ) -> httpx.Client:
        client: httpx.Client = build_client(base_url, token, actor, httpx.MockTransport(handler))
        return client

    monkeypatch.setattr(tianxuan_cli, "build_client", fake_build)


def test_build_client_prefers_token_over_actor() -> None:
    seen, handler = _record(lambda request: httpx.Response(200, json={"columns": {}}))
    with _client(handler, token="txs_token", actor="user-1") as client:
        get_board(client)

    assert seen[0].headers["authorization"] == "Bearer txs_token"
    assert seen[0].headers.get("x-actor") is None


def test_build_client_falls_back_to_actor_header() -> None:
    seen, handler = _record(lambda request: httpx.Response(200, json={"columns": {}}))
    with _client(handler, actor="user-1") as client:
        get_board(client)

    assert seen[0].headers["x-actor"] == "user-1"
    assert seen[0].headers.get("authorization") is None


def test_login_posts_credentials_to_session_endpoint() -> None:
    seen, handler = _record(lambda request: httpx.Response(200, json={"token": "txs_demo", "user_id": "user-1"}))
    with _client(handler) as client:
        payload = login(client, "ai@example.com", "secret-pass")

    assert payload == {"token": "txs_demo", "user_id": "user-1"}
    request = seen[0]
    assert (request.method, request.url.path) == ("POST", "/api/v1/auth/session")
    assert _json(request) == {"email": "ai@example.com", "password": "secret-pass"}
    assert request.headers.get("authorization") is None
    assert request.headers.get("x-actor") is None


def test_register_posts_tenant_and_omits_missing_name() -> None:
    seen, handler = _record(lambda request: httpx.Response(200, json={"user_id": "user-1"}))
    with _client(handler) as client:
        register(client, "设计工坊", "ai@example.com", "secret-pass")

    request = seen[0]
    assert (request.method, request.url.path) == ("POST", "/api/v1/auth/register")
    assert _json(request) == {
        "tenant_name": "设计工坊",
        "email": "ai@example.com",
        "password": "secret-pass",
    }


def test_docs_create_posts_title_body_and_kind() -> None:
    seen, handler = _record(lambda request: httpx.Response(200, json={"id": "doc_1", "version": 1}))
    with _client(handler, token="txs_token") as client:
        payload = create_doc(client, "设计文档", "# 正文\n", "requirement")

    assert payload == {"id": "doc_1", "version": 1}
    request = seen[0]
    assert (request.method, request.url.path) == ("POST", "/api/v1/docs")
    assert _json(request) == {"title": "设计文档", "body_md": "# 正文\n", "kind": "requirement"}
    assert request.headers["authorization"] == "Bearer txs_token"


def test_docs_patch_sends_ordered_pairs_and_expected_version() -> None:
    seen, handler = _record(lambda request: httpx.Response(200, json={"id": "doc_1", "version": 4}))
    with _client(handler, token="txs_token") as client:
        payload = patch_doc(client, "doc_1", 3, [("A", "A2"), ("B", "B2")])

    assert payload["version"] == 4
    request = seen[0]
    assert (request.method, request.url.path) == ("POST", "/api/v1/docs/doc_1/patch")
    assert _json(request) == {
        "expected_version": 3,
        "patches": [{"find": "A", "replace": "A2"}, {"find": "B", "replace": "B2"}],
    }


def test_board_fetches_columns_with_get() -> None:
    columns = {"todo": [{"number": 1}], "done": []}
    seen, handler = _record(lambda request: httpx.Response(200, json={"columns": columns}))
    with _client(handler, token="txs_token") as client:
        payload = get_board(client)

    assert payload == {"columns": columns}
    request = seen[0]
    assert (request.method, request.url.path) == ("GET", "/api/v1/board")
    assert request.content == b""
    assert request.headers["authorization"] == "Bearer txs_token"


def test_requirements_create_posts_all_required_fields() -> None:
    seen, handler = _record(lambda request: httpx.Response(200, json={"id": "doc_req", "request_id": "REQ-7"}))
    with _client(handler, token="txs_token") as client:
        payload = create_requirement(
            client,
            "REQ-7",
            "离线补丁",
            "AI 可安全编辑文档",
            "文曲文档补丁接口",
            "补丁只接受唯一匹配",
        )

    assert payload["request_id"] == "REQ-7"
    request = seen[0]
    assert (request.method, request.url.path) == ("POST", "/api/v1/requirements")
    assert _json(request) == {
        "request_id": "REQ-7",
        "title": "离线补丁",
        "outcome": "AI 可安全编辑文档",
        "scope": "文曲文档补丁接口",
        "acceptance": "补丁只接受唯一匹配",
    }


def test_requirements_export_gets_markdown_document() -> None:
    seen, handler = _record(
        lambda request: httpx.Response(200, json={"filename": "REQ-7.md", "markdown": "---\nrequest_id: REQ-7\n"})
    )
    with _client(handler, token="txs_token") as client:
        payload = export_requirement(client, "REQ-7")

    assert payload["filename"] == "REQ-7.md"
    request = seen[0]
    assert (request.method, request.url.path) == ("GET", "/api/v1/requirements/REQ-7/export")


def test_docs_list_sends_kind_only_when_requested() -> None:
    seen, handler = _record(lambda request: httpx.Response(200, json={"docs": []}))
    with _client(handler, token="txs_token") as client:
        list_docs(client)
        list_docs(client, "requirement")

    assert seen[0].url.path == "/api/v1/docs"
    assert "kind" not in seen[0].url.params
    assert seen[1].url.params["kind"] == "requirement"


def test_issues_list_sends_status_filter_with_actor() -> None:
    seen, handler = _record(lambda request: httpx.Response(200, json={"issues": []}))
    with _client(handler, actor="user-1") as client:
        list_issues(client, "todo")

    request = seen[0]
    assert (request.method, request.url.path) == ("GET", "/api/v1/issues")
    assert request.url.params["status"] == "todo"
    assert request.headers["x-actor"] == "user-1"


def test_main_login_prints_token_json(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _stub_main_client(monkeypatch, lambda request: httpx.Response(200, json={"token": "txs_cli"}))

    code = tianxuan_cli.main(["login", "--email", "ai@example.com", "--password", "secret-pass"])

    captured = capsys.readouterr()
    assert code == 0
    assert json.loads(captured.out) == {"token": "txs_cli"}
    assert captured.err == ""


def test_main_docs_merge_reads_files_and_posts_three_way(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    base = tmp_path / "base.md"
    local = tmp_path / "local.md"
    base.write_text("# base\n", encoding="utf-8")
    local.write_text("# local\n", encoding="utf-8")
    seen, handler = _record(lambda request: httpx.Response(200, json={"status": "merged"}))
    _stub_main_client(monkeypatch, handler)

    code = tianxuan_cli.main([
        "--token",
        "txs_token",
        "docs",
        "merge",
        "doc_9",
        "--expected-version",
        "4",
        "--base",
        str(base),
        "--local",
        str(local),
    ])

    assert code == 0
    assert json.loads(capsys.readouterr().out) == {"status": "merged"}
    assert seen[0].url.path == "/api/v1/docs/doc_9/merge"
    assert _json(seen[0]) == {"base_md": "# base\n", "local_md": "# local\n", "expected_version": 4}


def test_main_docs_patch_keeps_repeated_pairs_in_order(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seen, handler = _record(lambda request: httpx.Response(200, json={"id": "doc_1", "version": 2}))
    _stub_main_client(monkeypatch, handler)

    code = tianxuan_cli.main([
        "--token",
        "txs_token",
        "docs",
        "patch",
        "doc_1",
        "--expected-version",
        "1",
        "--find",
        "A",
        "--replace",
        "A2",
        "--find",
        "B",
        "--replace",
        "B2",
    ])

    assert code == 0
    assert json.loads(capsys.readouterr().out) == {"id": "doc_1", "version": 2}
    assert _json(seen[0]) == {
        "expected_version": 1,
        "patches": [{"find": "A", "replace": "A2"}, {"find": "B", "replace": "B2"}],
    }


def test_main_reports_http_error_on_stderr(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _stub_main_client(monkeypatch, lambda request: httpx.Response(409, json={"detail": "version mismatch"}))

    code = tianxuan_cli.main([
        "--token",
        "txs_token",
        "docs",
        "patch",
        "doc_1",
        "--expected-version",
        "2",
        "--find",
        "a",
        "--replace",
        "b",
    ])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert "409" in captured.err
    assert "version mismatch" in captured.err


def test_docs_patch_rejects_unpaired_find_replace(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    called: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        called.append(request)
        return httpx.Response(200, json={})

    _stub_main_client(monkeypatch, handler)

    code = tianxuan_cli.main([
        "--token",
        "txs_token",
        "docs",
        "patch",
        "doc_1",
        "--expected-version",
        "1",
        "--find",
        "only-a-find",
    ])

    captured = capsys.readouterr()
    assert code == 1
    assert called == []
    assert "pairs" in captured.err


def test_parser_reads_api_and_token_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIANXUAN_API", "http://api.internal:9000")
    monkeypatch.setenv("TIANXUAN_TOKEN", "txs_env")

    args = build_parser().parse_args(["board"])

    assert args.api == "http://api.internal:9000"
    assert args.token == "txs_env"
    assert args.actor is None


def test_connection_failure_raises_cli_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with _client(handler, token="txs_token") as client:
        with pytest.raises(CliError, match="request failed"):
            get_board(client)
