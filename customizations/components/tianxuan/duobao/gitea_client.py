"""多宝 Gitea/Forgejo HTTP 客户端。

自托管 Gitea/Forgejo 实例为多宝提供在线仓库能力：本模块封装仓库创建与查询、
Pull Request 创建/查询/合并以及 Issue 列表，并把响应裁剪为稳定字段。

安全边界：

- token 只写入 ``Authorization`` 请求头；异常、日志与归一化结果都不包含它；
- 服务端错误只读取 ``message``/``error`` 字段，脱敏并截断，不转储响应体；
- owner、仓库名、分支名与编号在发请求前校验，拒绝 ``..``、路径分隔符、空白
  与控制字符，避免调用方输入改变请求路径。

本模块只做 HTTP 映射与字段归一化；权限、评审与合入编排由多宝上层负责。
"""

from __future__ import annotations

import re
from types import TracebackType
from typing import Any

import httpx

__all__ = [
    "GiteaAuthError",
    "GiteaClient",
    "GiteaConflict",
    "GiteaError",
    "GiteaNotFound",
    "GiteaValidationError",
]

#: 服务端错误摘要的最大长度（字符），避免把整段响应体带进异常。
_MAX_ERROR_DETAIL = 200

#: Gitea 合并接口 ``Do`` 字段允许的取值。
_MERGE_METHODS = ("merge", "rebase", "rebase-merge", "squash", "fast-forward-only")

#: Gitea Issue 列表接口允许的 ``state`` 取值。
_ISSUE_STATES = ("open", "closed", "all")

#: owner/repo 等单个路径段中禁止出现的字符（URL 分隔符与编码前缀）。
_SEGMENT_FORBIDDEN = frozenset("/\\?#%:")

#: Git ref 明确禁止的字符（与 ``git check-ref-format`` 一致）。
_REF_FORBIDDEN = re.compile(r"[~^:?*\[\\]")
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_WHITESPACE = re.compile(r"\s+")


class GiteaError(Exception):
    """Gitea 请求失败。

    ``status`` 是 HTTP 状态码；本地校验失败或响应不可解析时 ``status`` 为 0，
    表示请求没有成功往返。``message`` 已脱敏且长度受限，``str()`` 只包含它与
    状态码，不含 token 或完整响应体。
    """

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(f"HTTP {status}: {message}" if status else message)


class GiteaAuthError(GiteaError):
    """401/403：token 缺失、无效或权限不足。"""


class GiteaNotFound(GiteaError):
    """404：仓库、Pull Request 或 Issue 不存在。"""


class GiteaConflict(GiteaError):
    """409：资源冲突（例如同名仓库或同一 head 的 PR 已存在）。"""


class GiteaValidationError(GiteaError, ValueError):
    """本地输入未通过校验，请求未发出；``status`` 恒为 0。"""

    def __init__(self, message: str) -> None:
        super().__init__(0, message)


_STATUS_ERRORS: dict[int, type[GiteaError]] = {
    401: GiteaAuthError,
    403: GiteaAuthError,
    404: GiteaNotFound,
    409: GiteaConflict,
}


# ----------------------------------------------------------------------
# 输入校验
# ----------------------------------------------------------------------
def _validate_base_url(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GiteaValidationError("base URL must be a non-empty http(s) URL")
    base_url = value.strip().rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        raise GiteaValidationError("base URL must use http or https")
    return base_url


def _validate_token(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GiteaValidationError("token must be a non-empty string")
    token = value.strip()
    if _CONTROL_CHARACTERS.search(token) or any(character.isspace() for character in token):
        raise GiteaValidationError("token must not contain whitespace or control characters")
    return token


def _validate_timeout(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise GiteaValidationError("timeout must be a positive number of seconds")
    return float(value)


def _validate_segment(value: Any, label: str) -> str:
    """校验 owner/repo 等单个 URL 路径段。"""
    if not isinstance(value, str) or not value:
        raise GiteaValidationError(f"{label} must be a non-empty string")
    if value != value.strip():
        raise GiteaValidationError(f"{label} must not have leading or trailing whitespace")
    if _CONTROL_CHARACTERS.search(value) or any(character.isspace() for character in value):
        raise GiteaValidationError(f"{label} must not contain whitespace or control characters")
    if value == "." or ".." in value:
        raise GiteaValidationError(f"{label} must not contain '.' or '..'")
    forbidden = sorted({character for character in value if character in _SEGMENT_FORBIDDEN})
    if forbidden:
        raise GiteaValidationError(f"{label} contains unsupported characters: {''.join(forbidden)}")
    return value


def _validate_branch(value: Any, label: str) -> str:
    """校验分支名；允许 ``feature/x`` 这类分层写法，但拒绝 Git 无效 ref。"""
    if not isinstance(value, str) or not value:
        raise GiteaValidationError(f"{label} must be a non-empty string")
    if value != value.strip():
        raise GiteaValidationError(f"{label} must not have leading or trailing whitespace")
    if _CONTROL_CHARACTERS.search(value) or any(character.isspace() for character in value):
        raise GiteaValidationError(f"{label} must not contain whitespace or control characters")
    if ".." in value or value.startswith("-") or value == "@" or "@{" in value:
        raise GiteaValidationError(f"invalid {label}: {value!r}")
    if _REF_FORBIDDEN.search(value):
        raise GiteaValidationError(f"invalid {label}: {value!r}")
    if value.startswith("refs/"):
        raise GiteaValidationError(f"{label} must be a short branch name, not a full ref: {value!r}")
    if value.startswith("/") or value.endswith("/") or "//" in value:
        raise GiteaValidationError(f"invalid {label}: {value!r}")
    if value.endswith("."):
        raise GiteaValidationError(f"invalid {label}: {value!r}")
    for part in value.split("/"):
        if part.startswith(".") or part.endswith(".lock"):
            raise GiteaValidationError(f"invalid {label}: {value!r}")
    return value


def _validate_text(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise GiteaValidationError(f"{label} must be a string")
    if not allow_empty and not value.strip():
        raise GiteaValidationError(f"{label} must be a non-empty string")
    return value


def _validate_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise GiteaValidationError(f"{label} must be a boolean")
    return value


def _validate_number(value: Any, label: str = "pull request number") -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise GiteaValidationError(f"{label} must be a positive integer")
    return value


def _validate_choice(value: Any, allowed: tuple[str, ...], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise GiteaValidationError(f"{label} must be one of: {', '.join(allowed)}")
    return value


# ----------------------------------------------------------------------
# 响应归一化
# ----------------------------------------------------------------------
def _mapping(payload: Any, label: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise GiteaError(0, f"unexpected {label} response: expected a JSON object")
    return payload


def _string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    return value if isinstance(value, str) else ""


def _integer(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _normalize_repo(payload: Any) -> dict[str, Any]:
    """把仓库响应裁剪为 ``id/name/full_name/default_branch/clone_url/html_url``。"""
    data = _mapping(payload, "repository")
    return {
        "id": _integer(data, "id"),
        "name": _string(data, "name"),
        "full_name": _string(data, "full_name"),
        "default_branch": _string(data, "default_branch"),
        "clone_url": _string(data, "clone_url"),
        "html_url": _string(data, "html_url"),
    }


def _branch_field(value: Any) -> str:
    """PR 的 head/base 在 Gitea 中是对象，归一化只保留分支名。"""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        ref = value.get("ref")
        if isinstance(ref, str):
            return ref
    return ""


def _normalize_branch(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise GiteaError(0, "unexpected branch response: expected a JSON object")
    name = payload.get("name")
    if not isinstance(name, str) or not name:
        raise GiteaError(0, "unexpected branch response: missing name")
    commit = payload.get("commit")
    commit_sha = commit.get("id") if isinstance(commit, dict) else None
    return {
        "name": name,
        "protected": bool(payload.get("protected", False)),
        "commit_sha": commit_sha if isinstance(commit_sha, str) else "",
    }


def _normalize_pull_request(payload: Any) -> dict[str, Any]:
    """把 PR 响应裁剪为 ``number/title/state/html_url/head/base``。"""
    data = _mapping(payload, "pull request")
    return {
        "number": _integer(data, "number"),
        "title": _string(data, "title"),
        "state": _string(data, "state"),
        "html_url": _string(data, "html_url"),
        "head": _branch_field(data.get("head")),
        "base": _branch_field(data.get("base")),
    }


def _normalize_merge(payload: Any) -> dict[str, Any]:
    """把合并响应裁剪为 ``merged/sha``；Gitea 未返回 sha 时为 ``None``。"""
    data = _mapping(payload, "merge")
    merged = data.get("merged")
    sha = data.get("sha")
    if not isinstance(sha, str) or not sha:
        sha = data.get("merge_commit_sha")
    return {
        "merged": merged if isinstance(merged, bool) else True,
        "sha": sha if isinstance(sha, str) and sha else None,
    }


def _label_names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for item in value:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str) and name:
                names.append(name)
    return names


def _normalize_issue(payload: Any) -> dict[str, Any]:
    """把 Issue 裁剪为 ``number/title/state/labels``，labels 只保留名称。"""
    data = _mapping(payload, "issue")
    return {
        "number": _integer(data, "number"),
        "title": _string(data, "title"),
        "state": _string(data, "state"),
        "labels": _label_names(data.get("labels")),
    }


# ----------------------------------------------------------------------
# 错误
# ----------------------------------------------------------------------
def _bounded(text: str, limit: int = _MAX_ERROR_DETAIL) -> str:
    collapsed = _WHITESPACE.sub(" ", text).strip()
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[: limit - 1]}…"


def _redact(text: str, token: str) -> str:
    # 先脱敏再截断，避免截断把 token 切成仍可识别的片段。
    return text.replace(token, "***") if token else text


def _response_detail(response: httpx.Response, token: str) -> str:
    """只取服务端错误的简短 message/error 字段，绝不转储响应体。"""
    try:
        payload = response.json()
    except ValueError:
        return ""
    if not isinstance(payload, dict):
        return ""
    for key in ("message", "error"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return _bounded(_redact(value, token))
    return ""


def _status_error(response: httpx.Response, method: str, path: str, token: str) -> GiteaError:
    detail = _response_detail(response, token) or response.reason_phrase or "request failed"
    message = _bounded(_redact(f"{method} {path}: {detail}", token))
    error_type = _STATUS_ERRORS.get(response.status_code, GiteaError)
    return error_type(response.status_code, message)


# ----------------------------------------------------------------------
# 客户端
# ----------------------------------------------------------------------
class GiteaClient:
    """自托管 Gitea/Forgejo 的同步 HTTP 客户端。

    ``transport`` 用于注入测试或自定义传输层；``timeout`` 单位为秒。
    token 只用于构造 ``Authorization: token <token>`` 请求头，并保留一份
    私有副本仅用于从错误信息中脱敏。
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = _validate_base_url(base_url)
        self._token = _validate_token(token)
        timeout_value = _validate_timeout(timeout)
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"token {self._token}"},
            transport=transport,
            timeout=timeout_value,
        )

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> GiteaClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    # ------------------------------------------------------------------
    # 仓库
    # ------------------------------------------------------------------
    def create_repo(self, name: str, private: bool = True, default_branch: str = "main") -> dict[str, Any]:
        """在当前 token 所属用户下创建仓库。"""
        name = _validate_segment(name, "repository name")
        private = _validate_bool(private, "private")
        default_branch = _validate_branch(default_branch, "default branch")
        payload = self._request(
            "POST",
            "/api/v1/user/repos",
            json_body={"name": name, "private": private, "default_branch": default_branch},
        )
        return _normalize_repo(payload)

    def list_repos(self, owner: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """列出当前用户或指定 owner 的仓库。"""
        if owner is None:
            path = "/api/v1/user/repos"
        else:
            path = f"/api/v1/users/{_validate_segment(owner, 'owner')}/repos"
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise GiteaValidationError("limit must be an integer between 1 and 100")
        payload = self._request("GET", path, params={"limit": str(limit)})
        if not isinstance(payload, list):
            raise GiteaError(0, f"GET {path} returned an unexpected payload")
        return [_normalize_repo(item) for item in payload]

    def get_repo(self, owner: str, name: str) -> dict[str, Any]:
        """按 owner/name 读取仓库。"""
        owner = _validate_segment(owner, "repository owner")
        name = _validate_segment(name, "repository name")
        return _normalize_repo(self._request("GET", f"/api/v1/repos/{owner}/{name}"))

    # ------------------------------------------------------------------
    # Pull Request
    # ------------------------------------------------------------------
    def list_branches(self, owner: str, repo: str) -> list[dict[str, Any]]:
        """列出仓库分支。"""
        owner = _validate_segment(owner, "repository owner")
        repo = _validate_segment(repo, "repository name")
        payload = self._request("GET", f"/api/v1/repos/{owner}/{repo}/branches")
        if not isinstance(payload, list):
            raise GiteaError(0, "unexpected branches response: expected a JSON array")
        return [_normalize_branch(item) for item in payload]

    def list_pull_requests(self, owner: str, repo: str, state: str = "open") -> list[dict[str, Any]]:
        """列出 Pull Request；``state`` 支持 ``open``/``closed``/``all``。"""
        owner = _validate_segment(owner, "repository owner")
        repo = _validate_segment(repo, "repository name")
        state = _validate_choice(state, _ISSUE_STATES, "pull request state")
        payload = self._request(
            "GET",
            f"/api/v1/repos/{owner}/{repo}/pulls",
            params={"state": state},
        )
        if not isinstance(payload, list):
            raise GiteaError(0, "unexpected pulls response: expected a JSON array")
        return [_normalize_pull_request(item) for item in payload]

    def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: str = "",
    ) -> dict[str, Any]:
        """创建同仓库内 ``head`` -> ``base`` 的 Pull Request。"""
        owner = _validate_segment(owner, "repository owner")
        repo = _validate_segment(repo, "repository name")
        title = _validate_text(title, "pull request title")
        head = _validate_branch(head, "pull request head")
        base = _validate_branch(base, "pull request base")
        body = _validate_text(body, "pull request body", allow_empty=True)
        payload = self._request(
            "POST",
            f"/api/v1/repos/{owner}/{repo}/pulls",
            json_body={"title": title, "head": head, "base": base, "body": body},
        )
        return _normalize_pull_request(payload)

    def get_pull_request(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        """按编号读取 Pull Request。"""
        owner = _validate_segment(owner, "repository owner")
        repo = _validate_segment(repo, "repository name")
        number = _validate_number(number)
        return _normalize_pull_request(self._request("GET", f"/api/v1/repos/{owner}/{repo}/pulls/{number}"))

    def merge_pull_request(
        self,
        owner: str,
        repo: str,
        number: int,
        method: str = "merge",
    ) -> dict[str, Any]:
        """合并 Pull Request；``method`` 对应 Gitea 的 ``Do`` 字段。"""
        owner = _validate_segment(owner, "repository owner")
        repo = _validate_segment(repo, "repository name")
        number = _validate_number(number)
        method = _validate_choice(method, _MERGE_METHODS, "merge method")
        payload = self._request(
            "POST",
            f"/api/v1/repos/{owner}/{repo}/pulls/{number}/merge",
            json_body={"Do": method},
        )
        return _normalize_merge(payload)

    # ------------------------------------------------------------------
    # Issue
    # ------------------------------------------------------------------
    def list_issues(self, owner: str, repo: str, state: str = "open") -> list[dict[str, Any]]:
        """列出仓库 Issue；``state`` 支持 ``open``/``closed``/``all``。"""
        owner = _validate_segment(owner, "repository owner")
        repo = _validate_segment(repo, "repository name")
        state = _validate_choice(state, _ISSUE_STATES, "issue state")
        payload = self._request(
            "GET",
            f"/api/v1/repos/{owner}/{repo}/issues",
            params={"state": state},
        )
        if not isinstance(payload, list):
            raise GiteaError(0, "unexpected issues response: expected a JSON array")
        return [_normalize_issue(item) for item in payload]

    # ------------------------------------------------------------------
    # 传输
    # ------------------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> Any:
        try:
            response = self._client.request(method, path, json=json_body, params=params)
        except httpx.HTTPError as error:
            detail = _bounded(_redact(str(error), self._token))
            raise GiteaError(
                0,
                f"{method} {path} failed: {type(error).__name__}: {detail}",
            ) from error
        if not response.is_success:
            raise _status_error(response, method, path, self._token)
        try:
            return response.json()
        except ValueError as error:
            raise GiteaError(0, f"{method} {path} returned a non-JSON response") from error
