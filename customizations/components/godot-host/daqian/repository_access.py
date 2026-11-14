"""Tianshu access belongs to authenticated collaborators of the bound Git origin."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "issue-workorders"))
import issue_gate
import work_items

DEFAULT_ACCOUNT_CACHE_TTL = 900.0
MAX_CACHED_ACCOUNTS = 16


class AccessDenied(ValueError):
    pass


class SessionChanged(AccessDenied):
    pass


def configured_login() -> str:
    # Local-only offline cache selection. Environment tokens override this config;
    # their identity cannot be established offline.
    if os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"):
        return ""
    try:
        return str(work_items.gh("config", "get", "user", "--host", "github.com")).strip()
    except work_items.GitHubCommandError:
        return ""


def fast_write_collaborator(root: str | os.PathLike[str]) -> dict[str, str]:
    """Verify repository write collaborator identity in one GraphQL roundtrip.

    Falls back to REST ``repos/{repo}`` + ``user`` when GraphQL is unavailable.
    """
    resolved = Path(root).resolve()
    repo = str(work_items.config(resolved)[0]["repository"])
    issue_gate.check_repository(resolved, repo)
    owner, name = repo.split("/", 1)
    query = """query($owner:String!,$name:String!){
      viewer { login databaseId }
      repository(owner:$owner,name:$name) { nameWithOwner databaseId viewerPermission }
    }"""
    try:
        response = json.loads(
            work_items.gh(
                "api",
                "graphql",
                "-f",
                "query=" + query,
                "-f",
                "owner=" + owner,
                "-f",
                "name=" + name,
            )
        )
        viewer = (response.get("data") or {}).get("viewer") or {}
        target = (response.get("data") or {}).get("repository") or {}
        if (
            isinstance(viewer.get("login"), str)
            and viewer["login"]
            and type(viewer.get("databaseId")) is int
            and isinstance(target.get("nameWithOwner"), str)
            and target["nameWithOwner"].casefold() == repo.casefold()
            and type(target.get("databaseId")) is int
            and target.get("viewerPermission") in {"WRITE", "MAINTAIN", "ADMIN"}
        ):
            return {
                "login": viewer["login"],
                "user_id": str(viewer["databaseId"]),
                "repo": repo,
                "repo_id": str(target["databaseId"]),
                "permission": str(target["viewerPermission"]).lower(),
            }
        raise AccessDenied("当前账号无此仓库的写入权限")
    except work_items.GitHubCommandError as error:
        if error.http_status not in (403, 404):
            raise
    user = json.loads(work_items.gh("api", "user"))
    if not isinstance(user.get("login"), str) or not user["login"] or type(user.get("id")) is not int:
        raise AccessDenied("无法核实当前 GitHub 账号")
    target = json.loads(work_items.gh("api", f"repos/{repo}"))
    perms = target.get("permissions") or {}
    if (
        not isinstance(target.get("full_name"), str)
        or target["full_name"].casefold() != repo.casefold()
        or type(target.get("id")) is not int
        or perms.get("push") is not True
    ):
        raise AccessDenied("当前账号无此仓库的写入权限")
    if str(work_items.gh("api", "user", "--jq", ".id")).strip() != str(user["id"]):
        raise AccessDenied("核验期间 GitHub 账号已切换")
    role = "admin" if perms.get("admin") else "maintain" if perms.get("maintain") else "write"
    return {
        "login": user["login"],
        "user_id": str(user["id"]),
        "repo": repo,
        "repo_id": str(target["id"]),
        "permission": role,
    }


def refresh_collaborator(root: str | os.PathLike[str]) -> dict[str, Any]:
    """Read the viewer and their explicit repository affiliations in one response per page."""
    repo = str(work_items.config(root)[0]["repository"])
    issue_gate.check_repository(Path(root), repo)
    query = """query($cursor:String) {
      viewer { login databaseId repositories(first:100, after:$cursor,
        affiliations:[OWNER,COLLABORATOR,ORGANIZATION_MEMBER],
        ownerAffiliations:[OWNER,COLLABORATOR,ORGANIZATION_MEMBER]) {
        nodes { nameWithOwner databaseId } pageInfo { endCursor hasNextPage }
      } }
    }"""
    cursor_args: list[str] = []
    first_user: int | None = None
    seen: set[str] = set()
    while True:
        try:
            response = json.loads(work_items.gh("api", "graphql", "-f", "query=" + query, *cursor_args))
        except work_items.GitHubCommandError as error:
            # Some installations grant a token REST access only.
            if error.http_status in (403, 404):
                return collaborator(root)
            raise
        viewer = response["data"]["viewer"]
        user_id = viewer["databaseId"]
        if type(user_id) is not int or not isinstance(viewer["login"], str) or not viewer["login"]:
            raise AccessDenied("无法核实当前 GitHub 账号")
        if first_user is not None and first_user != user_id:
            raise AccessDenied("核验期间 GitHub 账号已切换")
        first_user = user_id
        repos = viewer["repositories"]
        for row in repos["nodes"]:
            if row["nameWithOwner"].casefold() == repo.casefold() and type(row["databaseId"]) is int:
                return {
                    "login": viewer["login"],
                    "user_id": str(user_id),
                    "repo": repo,
                    "repo_id": str(row["databaseId"]),
                }
        page = repos["pageInfo"]
        if not page["hasNextPage"]:
            raise AccessDenied("当前账号未获此仓库的协作资格")
        cursor = page["endCursor"]
        if not isinstance(cursor, str) or not cursor or cursor in seen:
            raise AccessDenied("无法核实当前仓库的协作资格")
        seen.add(cursor)
        cursor_args = ["-f", "cursor=" + cursor]


def editor_parent_pid() -> int:
    parent = os.getppid()
    if os.name != "nt" or sys.prefix == sys.base_prefix:
        return parent
    # Windows venvs spawn the interpreter through a short-lived redirector.
    # Only unwrap the actual configured launcher, never an arbitrary ancestor.
    import ctypes
    import importlib
    from ctypes import wintypes

    winapi: Any = importlib.import_module("_winapi")
    kernel32: Any = getattr(ctypes, "windll").kernel32
    ntdll: Any = getattr(ctypes, "windll").ntdll
    try:
        handle = winapi.OpenProcess(0x1000, False, parent)  # PROCESS_QUERY_LIMITED_INFORMATION
    except OSError:
        return parent
    try:
        process = wintypes.HANDLE(handle)
        size = wintypes.DWORD(32768)
        image = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(process, 0, image, ctypes.byref(size)):
            return parent
        if os.path.normcase(image.value) != os.path.normcase(sys.executable):
            return parent
        # PROCESS_BASIC_INFORMATION ends with InheritedFromUniqueProcessId.
        info = (ctypes.c_size_t * 6)()
        status = ntdll.NtQueryInformationProcess(process, 0, info, ctypes.sizeof(info), None)
        return int(info[5]) if status == 0 and info[5] else parent
    finally:
        winapi.CloseHandle(handle)


def session_path(nonce: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", nonce):
        raise AccessDenied("编辑器会话无效")
    # Local user-owned state, outside the repository. A fresh capability is minted
    # in memory by each editor. Only its direct children share the same receipt.
    cache = (
        Path(os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
        / "gonggong"
        / "editor-sessions"
    )
    cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    return cache / f"{editor_parent_pid()}-{nonce}.json"


def _account_binding_key(nonce: str, root: Path, repo: str, local: str) -> str:
    cli_override = os.environ.get("GONGGONG_GH", "")
    components: list[str] = [nonce, str(root), repo, local]
    if cli_override:
        components.append(cli_override)
    return hashlib.sha256(json.dumps(components).encode()).hexdigest()


def session_actor(
    root: str | os.PathLike[str],
    nonce: str,
    *,
    allow_login: bool = False,
    cache_ttl: float = DEFAULT_ACCOUNT_CACHE_TTL,
) -> dict[str, Any]:
    if not nonce:
        return collaborator(root)
    resolved_root = Path(root).resolve()
    repo = str(work_items.config(resolved_root)[0]["repository"])
    issue_gate.check_repository(resolved_root, repo)
    path = session_path(nonce)
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    local = hashlib.sha256(token.encode()).hexdigest() if token else configured_login()
    # The binding is process-local in scope. No GitHub credential is saved.
    binding = _account_binding_key(nonce, resolved_root, repo, local)
    try:
        prior = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(prior, dict):
            prior = {}
    except (FileNotFoundError, ValueError):
        prior = {}
    if local and prior.get("binding") == binding and isinstance(prior.get("actor"), dict):
        cached_actor: dict[str, Any] = prior["actor"]
        return cached_actor
    if not allow_login:
        raise SessionChanged("编辑器登录账号或工作区已切换，请刷新工单")

    accounts_raw = prior.get("accounts")
    accounts: dict[str, dict[str, Any]] = dict(accounts_raw) if isinstance(accounts_raw, dict) else {}
    now = time.time()
    cached_entry = accounts.get(binding) if local else None
    if (
        isinstance(cached_entry, dict)
        and isinstance(cached_entry.get("verified_at_unix"), (int, float))
        and 0 <= now - float(cached_entry["verified_at_unix"]) <= cache_ttl
        and (token or not local or local.casefold() == str(cached_entry.get("login", "")).casefold())
    ):
        actor = dict(cached_entry)
    else:
        actor = refresh_collaborator(resolved_root)
        if not token and local and local.casefold() != str(actor["login"]).casefold():
            raise AccessDenied("核验期间 GitHub 账号已切换")
        actor["verified_at_unix"] = now

    if local:
        accounts[binding] = actor
        if len(accounts) > MAX_CACHED_ACCOUNTS:
            oldest = sorted(accounts.items(), key=lambda kv: float(kv[1].get("verified_at_unix", 0.0)))[0][0]
            accounts.pop(oldest, None)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False, encoding="utf-8") as stream:
        json.dump({"binding": binding, "actor": actor, "accounts": accounts}, stream)
    os.replace(stream.name, path)
    return actor


def collaborator(root: str | os.PathLike[str]) -> dict[str, str]:
    resolved_root = Path(root).resolve()
    repo = str(work_items.config(resolved_root)[0]["repository"])
    issue_gate.check_repository(resolved_root, repo)
    user = json.loads(work_items.gh("api", "user"))
    if not isinstance(user.get("login"), str) or not user["login"] or type(user.get("id")) is not int:
        raise AccessDenied("无法核实当前 GitHub 账号")
    # /user/repos enumerates explicitly accessible repos including inherited team
    # membership. Public read access, watchers and prior authorship do not grant entry.
    # Unlike checking /collaborators/:username this works for read-only collaborators.
    query = ".[] | select((.full_name | ascii_downcase) == " + json.dumps(repo.lower()) + ") | .id"
    matched = work_items.gh(
        "api", "user/repos?affiliation=owner,collaborator,organization_member&per_page=100", "--paginate", "--jq", query
    )
    ids = [json.loads(line) for line in matched.splitlines() if line.strip()]
    if not isinstance(ids, list) or len(ids) != 1 or type(ids[0]) is not int:
        raise AccessDenied("当前账号未获此仓库的协作资格")
    if str(work_items.gh("api", "user", "--jq", ".id")).strip() != str(user["id"]):
        raise AccessDenied("核验期间 GitHub 账号已切换")
    return {"login": user["login"], "user_id": str(user["id"]), "repo": repo, "repo_id": str(ids[0])}
