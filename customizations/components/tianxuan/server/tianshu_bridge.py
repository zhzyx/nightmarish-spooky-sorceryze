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
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, cast

TIMEOUT = 20
urlopen = urllib.request.urlopen
LOCAL_API = "http://127.0.0.1:8000"
GONGGONG_API = "https://167-172-70-41.sslip.io"
GONGGONG_REPO = "gonggong.git"
GONGGONG_SOURCE = "zhzyx/nightmarish-spooky-sorceryze"


class BridgeError(Exception):
    """API 调用或参数错误。"""


class BridgeHTTPError(BridgeError):
    def __init__(self, status: int, response: Any):
        super().__init__(f"HTTP {status}: {response}")
        self.status = status
        self.detail = response.get("detail") if isinstance(response, dict) else None


def duobao_route(args: argparse.Namespace) -> dict[str, str]:
    """Select the host-owned route. The checkout can only identify its source repository."""
    repository = os.environ.get("TIANXUAN_GIT_REPO", "")
    configured = {"api": args.api or LOCAL_API, "repository": repository}
    project = getattr(args, "project", None) or args.workspace or Path.cwd()
    project = project.resolve()
    for directory in (project, *project.parents):
        if (directory / ".git").exists():
            break
        if (directory / ".duobao-source.json").exists():
            return configured
    else:
        return configured
    # Read the local repository identity, including linked worktrees. Checkout
    # files, remote URL rewriting and includes cannot supply a destination.
    try:
        config = subprocess.run(
            [
                os.environ.get("GIT_EXECUTABLE") or "git",
                "-C",
                str(directory),
                "config",
                "--local",
                "--no-includes",
                "--null",
                "--get-regexp",
                r"^(remote\.origin\.url|gonggong\.releasesnapshot)$",
            ],
            env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
            capture_output=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired as error:
        raise BridgeError("无法及时读取项目仓库标识") from error
    if config.returncode not in (0, 1):
        raise BridgeError("无法读取当前项目的 Git 仓库标识")
    records = [record.partition(b"\n") for record in config.stdout.split(b"\0") if record]
    origins = [value.lower() for key, _, value in records if key == b"remote.origin.url"]
    if not origins and any(key == b"gonggong.releasesnapshot" for key, _, _ in records):
        raise BridgeError("下载包使用独立的 Git 快照。请打开真实共工 Git 工作副本，再从多宝分支、提交或合入。")
    if repository or (args.api and args.api.rstrip("/") != GONGGONG_API):
        return configured
    allowed = {
        (prefix + GONGGONG_SOURCE + suffix).encode()
        for prefix in ("https://github.com/", "git@github.com:", "ssh://git@github.com/")
        for suffix in ("", ".git")
    }
    if len(origins) == 1 and origins[0] in allowed:
        return {"api": GONGGONG_API, "repository": GONGGONG_REPO}
    return configured


def _cache_file(api: str, provider: str, subject: str) -> Path | None:
    setting = os.environ.get("TIANXUAN_TOKEN_CACHE", "")
    if setting.strip().lower() in {"off", "none", "0"}:
        return None
    base = Path(setting) if setting.strip() else Path(tempfile.gettempdir()) / "tianxuan-token-cache"
    digest = hashlib.sha256(f"{api}|{provider}|{subject}".encode()).hexdigest()[:24]
    return base / f"{digest}.json"


def _read_cached_token(api: str, provider: str, subject: str) -> str:
    path = _cache_file(api, provider, subject)
    if path is None or not path.is_file():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if float(payload.get("expires_at", 0)) <= time.time():
            return ""
        return str(payload.get("token", ""))
    except (OSError, ValueError, TypeError):
        return ""


def _write_cached_token(api: str, provider: str, subject: str, token: str) -> None:
    path = _cache_file(api, provider, subject)
    if path is None:
        return
    ttl = float(os.environ.get("TIANXUAN_TOKEN_TTL", "900"))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".partial")
        temporary.write_text(json.dumps({"token": token, "expires_at": time.time() + ttl}), encoding="utf-8")
        os.replace(temporary, path)
        try:
            path.chmod(0o600)
        except OSError:
            pass
    except OSError:
        return


def _endpoint(api: str, path: str, params: dict[str, str] | None = None) -> str:
    base = api.rstrip("/")
    if params:
        return f"{base}{path}?{urllib.parse.urlencode(params)}"
    return f"{base}{path}"


def _response_bytes(request, limit=None) -> bytes:
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            raw = response.read() if limit is None else response.read(limit + 1)
            if limit is not None and len(raw) > limit:
                raise BridgeError("对象超出差异预览上限")
            return bytes(raw)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
        except ValueError:
            parsed = detail
        raise BridgeHTTPError(error.code, parsed) from error
    except urllib.error.URLError as error:
        raise BridgeError(f"API unreachable: {error.reason}") from error


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
    raw = _response_bytes(request).decode("utf-8")
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except ValueError as error:
        raise BridgeError("API returned non-JSON response") from error
    if not isinstance(parsed, dict):
        raise BridgeError("API response must be a JSON object")
    return parsed


def _read_git_workcopy(args: argparse.Namespace, body: dict[str, Any]) -> dict[str, Any]:
    import selected_commit

    if body.get("mode") == "native":
        raise BridgeError("未找到物化来源，请重新打开工程")
    if args.command == "workcopy-diff":
        return cast(dict[str, Any], selected_commit.diff(args.project))
    return cast(dict[str, Any], selected_commit.preview(args.project, body["base"], body["tree"], body["path"]))


def workcopy_operation(args: argparse.Namespace) -> dict[str, Any]:
    import selected_commit

    body = json.loads(args.request.read_text(encoding="utf-8")) if getattr(args, "request", None) else {}
    marker = None
    for directory in (args.project, *args.project.parents):
        if (directory / ".git").exists():
            break
        if (directory / ".duobao-source.json").exists():
            marker = directory / ".duobao-source.json"
            break
    if marker:
        from native_workcopy_commit import NativeProject

        def request(method, path, data=None):
            return _request(args.api, method, "/api/v1/native/" + path, actor=args.actor, token=args.token, body=data)

        def read(path, limit):
            req = urllib.request.Request(
                _endpoint(args.api, "/api/v1/native/" + path), headers={"Authorization": "Bearer " + args.token}
            )
            return _response_bytes(req, limit)

        project = NativeProject(args.project, marker, args.api, request, read)
        if args.command == "workcopy-diff":
            return cast(dict[str, Any], project.diff())
        if body.get("mode") != "native":
            raise BridgeError("项目来源已变化，请刷新")
        if args.command == "workcopy-preview":
            return cast(dict[str, Any], project.preview(body))
        return cast(dict[str, Any], project.submit(body))
    if body.get("mode") == "native":
        raise BridgeError("未找到物化来源，请重新打开工程")
    if args.command in ("workcopy-diff", "workcopy-preview"):
        return _read_git_workcopy(args, body)
    name = body.get("repo") or args.repo_name
    if args.bound_repo and name != args.bound_repo:
        raise BridgeError("项目路由绑定的多宝仓库为 " + args.bound_repo)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in (".", ".."):
        raise BridgeError("多宝仓库名称无效")
    path = "/api/v1/git/repos/" + urllib.parse.quote(name, safe="") + "/selected-commits"

    def publish(payload):
        return _request(args.api, "POST", path, actor=args.actor, token=args.token, body=payload)

    def lookup(branch, base, sha):
        return _request(
            args.api,
            "GET",
            path + "/" + sha,
            actor=args.actor,
            token=args.token,
            params={"branch": branch, "base": base},
        )

    return cast(
        dict[str, Any], selected_commit.submit(args.project, [args.api, name, args.actor], body, publish, lookup)
    )


def merge_request(args: argparse.Namespace) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.repo_name) or args.repo_name in (".", ".."):
        raise BridgeError("多宝仓库名称无效")
    path = "/api/v1/git/repos/" + urllib.parse.quote(args.repo_name, safe="") + "/merge-requests"
    identity = {"actor": args.actor, "token": args.token}
    if args.command == "merge-request":
        sent = {"source": args.source, "target": args.target, "candidate": args.candidate}
        if args.issue_id:
            sent["issue_id"] = args.issue_id
        item = _request(args.api, "POST", path, **identity, body=sent)
        if any(item.get(key) != value for key, value in sent.items()):
            raise BridgeError("合入请求回执与提交的候选不匹配")
    else:
        if not re.fullmatch(r"mr_[0-9a-f]{64}", args.request_id):
            raise BridgeError("请输入完整的合入请求编号")
        path += "/" + args.request_id
        operation = {
            "merge-conflicts": "conflicts",
            "merge-resolve": "resolve",
            "merge-review": "review",
            "merge-deliver": "deliver",
        }.get(args.command)
        if operation:
            path += "/" + operation
        if operation == "resolve":
            item = _request(args.api, "POST", path, **identity, body={"files": json.loads(args.files)})
        elif operation == "review":
            item = _request(args.api, "POST", path, **identity, body={"decision": args.decision})
        elif operation == "deliver":
            item = _request(args.api, "POST", path, **identity, body={})
        else:
            item = _request(args.api, "GET", path, **identity)
        if operation != "resolve" and item.get("id") != args.request_id:
            raise BridgeError("合入请求回执编号不匹配")
    return item


def branch_operation(args: argparse.Namespace) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.repo_name) or args.repo_name in (".", ".."):
        raise BridgeError("多宝仓库名称无效")
    if not args.branch.strip() or args.branch.startswith("-"):
        raise BridgeError("分支名称无效")
    path = "/api/v1/git/repos/" + urllib.parse.quote(args.repo_name, safe="")
    identity = {"actor": args.actor, "token": args.token}
    if args.command == "branch-create":
        if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", args.start):
            raise BridgeError("创建起点须为完整提交 OID")
        created = _request(
            args.api, "POST", path + "/branches", **identity, body={"name": args.branch, "start": args.start}
        )
        if created.get("sha") != args.start or created.get("branch") != args.branch:
            raise BridgeError("多宝创建回执不匹配，请回读后再试")
    tip = _request(args.api, "GET", path + "/branch-tip", **identity, params={"branch": args.branch})
    if tip.get("branch") != args.branch or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", str(tip.get("sha", ""))):
        raise BridgeError("未收到目标分支的精确提交")
    if args.command == "branch-create" and tip["sha"] != args.start:
        raise BridgeError("分支在创建后已前移，请重新读取")
    return {"branch": args.branch, "sha": tip["sha"]}


def status(args: argparse.Namespace) -> dict[str, Any]:
    health = _request(args.api, "GET", "/api/v1/health", actor=args.actor, token=args.token)
    capabilities = _request(args.api, "GET", "/api/v1/capabilities", actor=args.actor, token=args.token)
    result = {"health": health, "capabilities": capabilities}
    if capabilities.get("git"):
        result["gitea"] = _request(args.api, "GET", "/api/v1/gitea/status", actor=args.actor, token=args.token)
    return result


def context(args: argparse.Namespace) -> dict[str, Any]:
    return _request(
        args.api,
        "GET",
        "/api/v1/external-context",
        actor=args.actor,
        token=args.token,
        params={"system": args.system, "external_id": args.external_id},
    )


def archive_history(args: argparse.Namespace) -> dict[str, Any]:
    """Pin the publication for every page, file and source shown in one search."""

    def read(endpoint: str, **params: str) -> dict[str, Any]:
        return _request(
            args.api,
            "GET",
            "/api/v1/migration/" + endpoint,
            actor=args.actor,
            token=args.token,
            params={"project": args.project, **params},
        )

    revision = args.revision
    if not revision:
        status = read("status")
        if not status.get("available") or not status.get("catalog_revision"):
            raise BridgeError("该项目没有可访问的多宝归档")
        revision = status["catalog_revision"]
    query = {"revision": revision}
    if args.path:
        query["path"] = args.path
    if not args.commit:
        return {**read("history/commits", **query, offset=str(args.offset)), "revision": revision}
    file = None
    file_error = ""
    if args.path:
        try:
            file = read("history/file", **query, commit=args.commit)
        except BridgeHTTPError as error:
            if (error.status, error.detail) not in (
                (404, "Archive item unavailable"),
                (422, "Invalid or unsupported archive content or query"),
            ):
                raise
            file_error = "该修订没有可预览的文本文件：" + args.path
    mapping = read("history/commit", revision=revision, commit=args.commit)
    return {"source": mapping, "file": file, "file_error": file_error}


def historical_issue(args: argparse.Namespace) -> dict[str, Any]:
    source_id = args.source_id
    link = re.fullmatch(r"https://github\.com/([\w.-]+/[\w.-]+)/issues/([1-9]\d*)/?", source_id)
    pull = re.fullmatch(
        r"https://github\.com/([\w.-]+/[\w.-]+)/pull/([1-9]\d*)"
        r"(?:/(?:files)?)?(?:#(issuecomment-|pullrequestreview-|discussion_r)([1-9]\d*))?",
        source_id,
    )
    expected_kind = "issue"
    if link:
        source_id = f"github:{link[1]}/issue/{link[2]}"
    elif pull:
        expected_kind = {
            None: "pull",
            "issuecomment-": "issue_comment",
            "pullrequestreview-": "review",
            "discussion_r": "review_comment",
        }[pull[3]]
        source_id = f"github:{pull[1]}/{expected_kind}/{pull[4] or pull[2]}"
    params = {"project": args.project, "source_id": source_id}

    def read(action: str, **query: str) -> dict[str, Any]:
        return _request(
            args.api,
            "GET",
            "/api/v1/migration/history/" + action,
            actor=args.actor,
            token=args.token,
            params={**params, **query},
        )

    detail = read("detail", limit="50" if expected_kind == "pull" else "1")
    row = detail["record"]
    if row["kind"] != expected_kind or row["source_id"] != source_id:
        raise BridgeError("该标识未指向历史工单")
    content = row["content"]
    if pull and pull[3]:
        original = content.get("html_url") or content.get("url", "")
        canonical = f"https://github.com/{pull[1]}/pull/{pull[2]}#{pull[3]}{pull[4]}"
        if original.replace("/files#", "#") != canonical:
            raise BridgeError("评审不属于指定的 PR")
    body = content.get("body") or ""
    if row.get("truncated"):
        chunks = []
        offset = 0
        while True:
            page = read("body", revision=detail["revision"], offset=str(offset))
            chunks.append(page["text"])
            if page["next_offset"] is None:
                break
            if page["next_offset"] <= offset:
                raise BridgeError("历史工单正文分页无效")
            offset = page["next_offset"]
        body = "".join(chunks)
    if pull and expected_kind == "pull":
        links = []
        page = detail["comments"]
        while True:
            for entry in page["items"]:
                item = entry["content"]
                original = item.get("html_url") or item.get("url", "")
                if original.replace("/files#", "#").startswith(f"https://github.com/{pull[1]}/pull/{pull[2]}#"):
                    links.append(original)
            offset = page["offset"] + len(page["items"])
            if offset >= page["total"] or not page["items"]:
                break
            page = read("detail", revision=detail["revision"], offset=str(offset), limit="50")["comments"]
        if links:
            body += "\n\n将原始链接复制到上方输入框可读取归档评审：\n" + "\n".join(links)
    return {
        "source_id": source_id,
        "title": content.get("title") or ("PR 归档评审" if pull and pull[3] else ""),
        "state": content.get("state", ""),
        "body": body,
        "revision": detail["revision"],
    }


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


def _transition(args: argparse.Namespace, issue_id: str, status: str) -> dict[str, Any]:
    return _request(
        args.api,
        "PATCH",
        f"/api/v1/issues/{urllib.parse.quote(issue_id, safe='')}",
        actor=args.actor,
        token=args.token,
        body={"to_status": status},
    )


def sync_tickets(args: argparse.Namespace) -> dict[str, Any]:
    """把天枢已完成的计划节点标题同步为天璇子工单 done。"""
    context = _request(
        args.api,
        "GET",
        "/api/v1/external-context",
        actor=args.actor,
        token=args.token,
        params={"system": args.system, "external_id": args.external_id},
    )
    children = [issue for issue in context.get("issues", []) if isinstance(issue, dict) and issue.get("parent_id")]
    by_title: dict[str, list[dict[str, Any]]] = {}
    for candidate in children:
        by_title.setdefault(str(candidate.get("title", "")), []).append(candidate)
    path = ["backlog", "planned", "in-progress", "in-review", "done"]
    updated: list[dict[str, Any]] = []
    missing: list[str] = []
    for title in args.done:
        candidates = by_title.get(title, [])
        if not candidates:
            missing.append(title)
            continue
        if len(candidates) > 1:
            missing.append(f"{title} (ambiguous)")
            continue
        issue: dict[str, Any] = candidates[0]
        status = str(issue.get("status", "backlog"))
        if status == "done":
            updated.append(issue)
            continue
        if status not in path:
            missing.append(f"{title} (status={status})")
            continue
        current = issue
        for target in path[path.index(status) + 1 :]:
            current = _transition(args, str(current["id"]), target)
        updated.append(current)
    return {"updated": updated, "missing": missing}


def _write(args: argparse.Namespace, envelope: dict[str, Any]) -> None:
    text = json.dumps(envelope, ensure_ascii=False, indent=2)
    if args.result:
        target = args.result
        temporary = target.with_suffix(target.suffix + ".partial")
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, target)
    print(text)


def _normalize_result(argv: list[str]) -> list[str]:
    """天枢宿主会把 ``--result`` 追加在命令末尾；统一移到全局位置。"""
    if "--result" not in argv:
        return argv
    index = argv.index("--result")
    if index + 1 >= len(argv):
        return argv
    value = argv[index + 1]
    rest = argv[:index] + argv[index + 2 :]
    return ["--result", value, *rest]


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    arguments = _normalize_result(arguments)
    parser = argparse.ArgumentParser(description="天璇 ↔ 天枢互通桥")
    parser.add_argument("--api", default=os.environ.get("TIANXUAN_API"))
    parser.add_argument("--workspace", type=Path, help="当前打开的项目目录（多宝 Git 路由）")
    parser.add_argument("--actor", default=os.environ.get("TIANXUAN_ACTOR", ""))
    parser.add_argument("--token")
    parser.add_argument("--identity-provider", default=os.environ.get("TIANXUAN_IDENTITY_PROVIDER", ""))
    parser.add_argument("--identity-subject", default=os.environ.get("TIANXUAN_IDENTITY_SUBJECT", ""))
    parser.add_argument("--identity-secret", default=os.environ.get("TIANXUAN_IDENTITY_SECRET", ""))
    parser.add_argument("--result", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="天璇健康与 Gitea 状态").set_defaults(func=status)
    sub.add_parser("duobao-route", help="本地读取当前项目的多宝仓库").set_defaults(func=duobao_route)

    for command in ("workcopy-diff", "workcopy-preview", "workcopy-submit"):
        workcopy = sub.add_parser(command)
        workcopy.add_argument("--project", required=True, type=Path)
        if command != "workcopy-diff":
            workcopy.add_argument("--request", required=True, type=Path)
        workcopy.set_defaults(func=workcopy_operation)

    for command in (
        "merge-request",
        "merge-request-status",
        "merge-conflicts",
        "merge-resolve",
        "merge-review",
        "merge-deliver",
    ):
        merge = sub.add_parser(command)
        merge.add_argument("--repo-name", default="")
        if command == "merge-request":
            merge.add_argument("--source", required=True)
            merge.add_argument("--target", required=True)
            merge.add_argument("--candidate", required=True)
            merge.add_argument("--issue-id", default="")
        else:
            merge.add_argument("--request-id", required=True)
        if command == "merge-resolve":
            merge.add_argument("--files", required=True)
        if command == "merge-review":
            merge.add_argument("--decision", choices=("APPROVED", "REQUEST_CHANGES"), required=True)
        merge.set_defaults(func=merge_request)

    for command in ("branch-create", "branch-tip"):
        branch = sub.add_parser(command)
        branch.add_argument("--repo-name", default="")
        branch.add_argument("--branch", required=True)
        if command == "branch-create":
            branch.add_argument("--start", required=True)
        branch.set_defaults(func=branch_operation)

    p = sub.add_parser("context", help="读取外部工单在天璇内的需求/文档/工单")
    p.add_argument("--system", default="tianshu")
    p.add_argument("--external-id", required=True)
    p.set_defaults(func=context)

    p = sub.add_parser("archive-history", help="读取多宝归档提交、文件及原始映射")
    p.add_argument("--project", required=True)
    p.add_argument("--revision")
    p.add_argument("--path", default="")
    p.add_argument("--commit")
    p.add_argument("--offset", default=0, type=int)
    p.set_defaults(func=archive_history)

    p = sub.add_parser("historical-issue", help="只读打开已归档的历史工单")
    p.add_argument("--project", required=True)
    p.add_argument("--source-id", required=True)
    p.set_defaults(func=historical_issue)

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

    p = sub.add_parser("sync", help="把天枢完成节点同步为天璇工单完成")
    p.add_argument("--system", default="tianshu")
    p.add_argument("--external-id", required=True)
    p.add_argument("--done", action="append", required=True, help="已完成的计划节点标题")
    p.set_defaults(func=sync_tickets)

    args = parser.parse_args(arguments)
    try:
        if args.func in (duobao_route, branch_operation, merge_request, workcopy_operation):
            route = duobao_route(args)
            if args.func == duobao_route:
                # A caller-supplied URL can contain private information.
                location = route["api"] if route["api"] in (LOCAL_API, GONGGONG_API) else "configured"
                _write(args, {"ok": True, "data": {"api": location, "repository": route["repository"]}})
                return 0
            args.bound_repo = route["repository"] if not args.api and not os.environ.get("TIANXUAN_GIT_REPO") else ""
            args.api = route["api"]
            args.repo_name = getattr(args, "repo_name", "") or route["repository"]
            if args.bound_repo and args.repo_name != args.bound_repo:
                raise BridgeError("项目路由绑定的多宝仓库为 " + args.bound_repo)
        else:
            args.api = args.api or LOCAL_API
        if getattr(args, "bound_repo", "") and args.command in ("workcopy-diff", "workcopy-preview"):
            # Automatic routing has identified a Git checkout, not a materialized
            # native project. These reads never use the remote service or identity.
            body = json.loads(args.request.read_text(encoding="utf-8")) if getattr(args, "request", None) else {}
            _write(args, {"ok": True, "data": _read_git_workcopy(args, body)})
            return 0
        if getattr(args, "bound_repo", ""):
            # Legacy launchers may supply credentials for the old loopback
            # default. Only an explicit token or this origin's cache is bound.
            if not args.token and args.identity_provider and args.identity_subject:
                args.token = _read_cached_token(args.api, args.identity_provider, args.identity_subject)
            if not args.token and (os.environ.get("TIANXUAN_TOKEN") or args.identity_provider or args.identity_secret):
                raise BridgeError(
                    "当前凭据未绑定多宝公网服务。请在可信启动器显式设置 TIANXUAN_API 并使用目标服务的身份。"
                )
            if not args.token:
                args.actor = ""
                args.token = ""
        else:
            args.token = args.token or os.environ.get("TIANXUAN_TOKEN", "")
        if not args.token and args.identity_provider:
            if not args.identity_subject:
                raise BridgeError("identity subject is required")
            token = _read_cached_token(args.api, args.identity_provider, args.identity_subject)
            if not token:
                resolved = _request(
                    args.api,
                    "POST",
                    "/api/v1/identity/resolve",
                    body={
                        "provider": args.identity_provider,
                        "subject": args.identity_subject,
                        "secret": args.identity_secret,
                    },
                )
                token = str(resolved.get("token", ""))
                if not token:
                    raise BridgeError("identity resolve returned no token")
                _write_cached_token(args.api, args.identity_provider, args.identity_subject, token)
            args.token = token
        data = args.func(args)
        envelope = {"ok": True, "data": data}
        code = 0
    except (BridgeError, ValueError, OSError, TimeoutError) as error:
        envelope = {"ok": False, "error": str(error)}
        code = 1
    _write(args, envelope)
    return code


if __name__ == "__main__":
    sys.exit(main())
