"""多宝 Gitea/Forgejo HTTP 客户端测试。

全部请求由 ``httpx.MockTransport`` 应答，测试不接触网络。每个用例同时检查
请求方法、路径、``Authorization`` 头与 JSON 请求体，并确认归一化结果只保留
约定字段、异常不泄露 token 且长度受限。
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest
from gitea_client import (
    GiteaAuthError,
    GiteaClient,
    GiteaConflict,
    GiteaError,
    GiteaNotFound,
    GiteaValidationError,
)

BASE_URL = "https://gitea.example"
TOKEN = "duobao-test-token-not-a-real-secret"

Handler = Callable[[httpx.Request], httpx.Response]
ClientFactory = Callable[[Handler], tuple[GiteaClient, list[httpx.Request]]]

REPO_PAYLOAD: dict[str, Any] = {
    "id": 42,
    "name": "duobao",
    "full_name": "octo/duobao",
    "default_branch": "main",
    "clone_url": "https://gitea.example/octo/duobao.git",
    "html_url": "https://gitea.example/octo/duobao",
    # 以下字段必须被归一化丢弃；token 绝不能进入返回值。
    "owner": {"login": "octo"},
    "private": False,
    "token": TOKEN,
}

EXPECTED_REPO: dict[str, Any] = {
    "id": 42,
    "name": "duobao",
    "full_name": "octo/duobao",
    "default_branch": "main",
    "clone_url": "https://gitea.example/octo/duobao.git",
    "html_url": "https://gitea.example/octo/duobao",
}

PR_PAYLOAD: dict[str, Any] = {
    "number": 7,
    "title": "feat: 接入 Gitea",
    "state": "open",
    "html_url": "https://gitea.example/octo/duobao/pulls/7",
    "head": {"ref": "feature/gitea", "sha": "a" * 40},
    "base": {"ref": "main", "sha": "b" * 40},
    "user": {"login": "octo"},
}

EXPECTED_PR: dict[str, Any] = {
    "number": 7,
    "title": "feat: 接入 Gitea",
    "state": "open",
    "html_url": "https://gitea.example/octo/duobao/pulls/7",
    "head": "feature/gitea",
    "base": "main",
}

INVALID_SEGMENTS = [
    "",
    "   ",
    ".",
    "..",
    "../octo",
    "octo/evil",
    "octo\\evil",
    "octo?x",
    "octo#x",
    "octo%2F",
    "oc to",
    " octo",
    "octo\n",
]

INVALID_REFS = [
    "",
    "   ",
    "..",
    "../main",
    "main..x",
    "bad name",
    "-evil",
    "refs/heads/main",
    "@",
    "main.",
    "a\\b",
    "a:b",
    "a?b",
    "a\nb",
    "/main",
    "main/",
    "main//x",
    "x.lock",
    ".hidden/main",
]


# ----------------------------------------------------------------------
# fixtures / helpers
# ----------------------------------------------------------------------
@pytest.fixture()
def make_client() -> Iterator[ClientFactory]:
    clients: list[GiteaClient] = []

    def factory(handler: Handler) -> tuple[GiteaClient, list[httpx.Request]]:
        requests: list[httpx.Request] = []

        def record(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return handler(request)

        client = GiteaClient(BASE_URL, TOKEN, transport=httpx.MockTransport(record))
        clients.append(client)
        return client, requests

    yield factory
    for client in clients:
        client.close()


def assert_authorized(request: httpx.Request) -> None:
    """确认认证头按 Gitea 约定设置，且 token 不在 URL 中。"""
    authorization = request.headers.get("Authorization")
    assert authorization is not None, "Authorization header is missing"
    assert authorization == f"token {TOKEN}", "Authorization header does not carry the configured token"
    assert TOKEN not in str(request.url)


def request_json(request: httpx.Request) -> dict[str, Any]:
    payload = json.loads(request.content)
    assert isinstance(payload, dict)
    return payload


def forbidden_handler(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected request: {request.method} {request.url}")


# ----------------------------------------------------------------------
# happy paths
# ----------------------------------------------------------------------
def test_create_repo_returns_normalized_payload(make_client: ClientFactory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/user/repos"
        assert request.url.query == b""
        assert_authorized(request)
        assert request_json(request) == {
            "name": "duobao",
            "private": True,
            "default_branch": "main",
        }
        return httpx.Response(201, json=REPO_PAYLOAD)

    client, requests = make_client(handler)
    repo = client.create_repo("duobao")

    assert repo == EXPECTED_REPO
    assert TOKEN not in str(repo)
    assert len(requests) == 1


def test_create_repo_forwards_private_and_default_branch(make_client: ClientFactory) -> None:
    payload = {**REPO_PAYLOAD, "name": "internal", "private": False, "default_branch": "develop"}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/user/repos"
        assert_authorized(request)
        assert request_json(request) == {
            "name": "internal",
            "private": False,
            "default_branch": "develop",
        }
        return httpx.Response(201, json=payload)

    client, _ = make_client(handler)
    repo = client.create_repo("internal", private=False, default_branch="develop")

    assert repo["name"] == "internal"
    assert repo["default_branch"] == "develop"


def test_get_repo_returns_normalized_payload(make_client: ClientFactory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/repos/octo/duobao"
        assert request.url.query == b""
        assert request.content == b""
        assert_authorized(request)
        return httpx.Response(200, json=REPO_PAYLOAD)

    client, requests = make_client(handler)
    repo = client.get_repo("octo", "duobao")

    assert repo == EXPECTED_REPO
    assert len(requests) == 1


def test_create_pull_request_returns_normalized_payload(make_client: ClientFactory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/repos/octo/duobao/pulls"
        assert_authorized(request)
        assert request_json(request) == {
            "title": "feat: 接入 Gitea",
            "head": "feature/gitea",
            "base": "main",
            "body": "接入自托管 Gitea。",
        }
        return httpx.Response(201, json=PR_PAYLOAD)

    client, requests = make_client(handler)
    pull = client.create_pull_request(
        "octo",
        "duobao",
        "feat: 接入 Gitea",
        "feature/gitea",
        "main",
        "接入自托管 Gitea。",
    )

    assert pull == EXPECTED_PR
    assert len(requests) == 1


def test_create_pull_request_default_body_is_empty(make_client: ClientFactory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request_json(request)["body"] == ""
        return httpx.Response(201, json=PR_PAYLOAD)

    client, _ = make_client(handler)
    assert client.create_pull_request("octo", "duobao", "title", "feature/gitea", "main") == EXPECTED_PR


def test_get_pull_request_returns_normalized_payload(make_client: ClientFactory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/repos/octo/duobao/pulls/7"
        assert_authorized(request)
        return httpx.Response(200, json=PR_PAYLOAD)

    client, requests = make_client(handler)
    pull = client.get_pull_request("octo", "duobao", 7)

    assert pull == EXPECTED_PR
    assert len(requests) == 1


def test_merge_pull_request_returns_normalized_payload(make_client: ClientFactory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/repos/octo/duobao/pulls/7/merge"
        assert_authorized(request)
        assert request_json(request) == {"Do": "merge"}
        return httpx.Response(200, json={"merged": True, "sha": "c" * 40, "message": "merged"})

    client, requests = make_client(handler)
    merged = client.merge_pull_request("octo", "duobao", 7)

    assert merged == {"merged": True, "sha": "c" * 40}
    assert len(requests) == 1


def test_merge_pull_request_without_sha_and_custom_method(make_client: ClientFactory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/repos/octo/duobao/pulls/7/merge"
        assert request_json(request) == {"Do": "squash"}
        return httpx.Response(200, json={"merged": True, "message": "squashed"})

    client, _ = make_client(handler)
    assert client.merge_pull_request("octo", "duobao", 7, method="squash") == {
        "merged": True,
        "sha": None,
    }


def test_list_issues_returns_normalized_payload(make_client: ClientFactory) -> None:
    issues_payload = [
        {
            "number": 1,
            "title": "第一个 Issue",
            "state": "open",
            "labels": [{"id": 3, "name": "bug", "color": "ff0000"}, "prio"],
            "body": "响应体字段必须被丢弃",
        },
        {
            "number": 2,
            "title": "第二个 Issue",
            "state": "closed",
            "labels": [],
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/repos/octo/duobao/issues"
        assert request.url.params.get("state") == "open"
        assert_authorized(request)
        return httpx.Response(200, json=issues_payload)

    client, requests = make_client(handler)
    issues = client.list_issues("octo", "duobao")

    assert issues == [
        {"number": 1, "title": "第一个 Issue", "state": "open", "labels": ["bug", "prio"]},
        {"number": 2, "title": "第二个 Issue", "state": "closed", "labels": []},
    ]
    assert len(requests) == 1


# ----------------------------------------------------------------------
# HTTP 错误映射
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (400, GiteaError),
        (401, GiteaAuthError),
        (403, GiteaAuthError),
        (404, GiteaNotFound),
        (409, GiteaConflict),
        (500, GiteaError),
    ],
)
def test_http_status_errors_are_mapped(
    make_client: ClientFactory,
    status: int,
    error_type: type[GiteaError],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"message": "server says no"})

    client, requests = make_client(handler)
    with pytest.raises(error_type) as raised:
        client.get_repo("octo", "duobao")

    error = raised.value
    assert type(error) is error_type
    assert error.status == status
    assert "server says no" in error.message
    assert "server says no" in str(error)
    assert len(requests) == 1


def test_error_redacts_token_from_message(make_client: ClientFactory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": f"token {TOKEN} is invalid", "error": TOKEN})

    client, _ = make_client(handler)
    with pytest.raises(GiteaAuthError) as raised:
        client.get_repo("octo", "duobao")

    error = raised.value
    assert TOKEN not in str(error)
    assert TOKEN not in repr(error)
    assert TOKEN not in error.message
    assert "***" in error.message


def test_error_message_is_bounded(make_client: ClientFactory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "x" * 10_000})

    client, _ = make_client(handler)
    with pytest.raises(GiteaError) as raised:
        client.get_repo("octo", "duobao")

    assert len(str(raised.value)) <= 400
    assert "x" * 10_000 not in str(raised.value)


# ----------------------------------------------------------------------
# 输入校验：请求发出前拒绝
# ----------------------------------------------------------------------
@pytest.mark.parametrize("invalid", INVALID_SEGMENTS)
def test_invalid_owner_or_repository_rejected_before_request(
    make_client: ClientFactory,
    invalid: str,
) -> None:
    client, requests = make_client(forbidden_handler)

    with pytest.raises(GiteaValidationError):
        client.get_repo(invalid, "duobao")
    with pytest.raises(GiteaValidationError):
        client.get_repo("octo", invalid)

    assert requests == []


@pytest.mark.parametrize("invalid", INVALID_SEGMENTS)
def test_invalid_repository_name_rejected_before_request(
    make_client: ClientFactory,
    invalid: str,
) -> None:
    client, requests = make_client(forbidden_handler)

    with pytest.raises(GiteaValidationError):
        client.create_repo(invalid)

    assert requests == []


@pytest.mark.parametrize("invalid", INVALID_REFS)
def test_invalid_pull_request_refs_rejected_before_request(
    make_client: ClientFactory,
    invalid: str,
) -> None:
    client, requests = make_client(forbidden_handler)

    with pytest.raises(GiteaValidationError):
        client.create_pull_request("octo", "duobao", "title", invalid, "main")
    with pytest.raises(GiteaValidationError):
        client.create_pull_request("octo", "duobao", "title", "feature/gitea", invalid)

    assert requests == []


@pytest.mark.parametrize("invalid", [0, -1, True, 1.5, "7", None])
def test_invalid_pull_request_number_rejected_before_request(
    make_client: ClientFactory,
    invalid: Any,
) -> None:
    client, requests = make_client(forbidden_handler)

    with pytest.raises(GiteaValidationError):
        client.get_pull_request("octo", "duobao", invalid)
    with pytest.raises(GiteaValidationError):
        client.merge_pull_request("octo", "duobao", invalid)

    assert requests == []


def test_invalid_default_branch_rejected_before_request(make_client: ClientFactory) -> None:
    client, requests = make_client(forbidden_handler)

    with pytest.raises(GiteaValidationError):
        client.create_repo("duobao", default_branch="../main")

    assert requests == []


def test_non_boolean_private_rejected_before_request(make_client: ClientFactory) -> None:
    client, requests = make_client(forbidden_handler)

    with pytest.raises(GiteaValidationError):
        client.create_repo("duobao", private="yes")  # type: ignore[arg-type]

    assert requests == []


def test_blank_pull_request_title_rejected_before_request(make_client: ClientFactory) -> None:
    client, requests = make_client(forbidden_handler)

    with pytest.raises(GiteaValidationError):
        client.create_pull_request("octo", "duobao", "   ", "feature/gitea", "main")

    assert requests == []


def test_invalid_merge_method_rejected_before_request(make_client: ClientFactory) -> None:
    client, requests = make_client(forbidden_handler)

    with pytest.raises(GiteaValidationError):
        client.merge_pull_request("octo", "duobao", 7, method="octopus")

    assert requests == []


def test_invalid_issue_state_rejected_before_request(make_client: ClientFactory) -> None:
    client, requests = make_client(forbidden_handler)

    with pytest.raises(GiteaValidationError):
        client.list_issues("octo", "duobao", state="opened")

    assert requests == []


def test_validation_error_is_gitea_and_value_error(make_client: ClientFactory) -> None:
    client, _ = make_client(forbidden_handler)

    with pytest.raises(ValueError) as raised:
        client.list_issues("octo", "duobao", state="opened")

    assert isinstance(raised.value, GiteaValidationError)
    assert isinstance(raised.value, GiteaError)
    assert raised.value.status == 0


# ----------------------------------------------------------------------
# 构造参数
# ----------------------------------------------------------------------
@pytest.mark.parametrize("token", ["", "   ", "bad token", "bad\ntoken"])
def test_invalid_token_rejected(token: str) -> None:
    with pytest.raises(GiteaValidationError):
        GiteaClient(BASE_URL, token, transport=httpx.MockTransport(forbidden_handler))


@pytest.mark.parametrize("base_url", ["", "   ", "gitea.example", "ftp://gitea.example"])
def test_invalid_base_url_rejected(base_url: str) -> None:
    with pytest.raises(GiteaValidationError):
        GiteaClient(base_url, TOKEN, transport=httpx.MockTransport(forbidden_handler))


def test_trailing_slash_in_base_url_is_normalized() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=REPO_PAYLOAD)

    client = GiteaClient(f"{BASE_URL}/", TOKEN, transport=httpx.MockTransport(handler))
    try:
        assert client.get_repo("octo", "duobao") == EXPECTED_REPO
    finally:
        client.close()

    assert requests[0].url.path == "/api/v1/repos/octo/duobao"
