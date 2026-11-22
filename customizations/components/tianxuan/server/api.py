"""天璇 FastAPI 传输适配器。

本层只做 HTTP 映射：提取 actor 头、校验请求体、把领域异常翻译为状态码。
租户、版本、状态机等语义全部由 tianxuan_core.Tianxuan 负责，适配器不复制规则。

actor 约定：需要身份的端点从请求头 ``X-Actor`` 读取用户 ID（当前切片的临时身份，
真正的认证与授权在后续切片接入）。列表端点统一返回 ``{"<name>": [...]}`` 包装，
与领域层 AI 工具面的返回结构保持一致。
"""

from __future__ import annotations

import asyncio
import difflib
import html
import json
import os
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any, cast
from urllib.parse import quote

from access_control import configure_access
from anyio import from_thread
from duobao_bridge import (
    GitService,
    GitServiceError,
    PolicyError,
    approved_reviewers,
    ensure_branch_mutation_allowed,
    ensure_checks_passed,
    ensure_merge_allowed,
    ensure_pr_merge_allowed,
    parse_protected_branches,
)
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response
from gateway import ModelGateway, create_model_router, workspace_actor
from gitea_bridge import GiteaClient, GiteaError
from identity import allow_identity_attempt, get_identity_adapter
from markdown_render import render_markdown
from paragraph_suggestion import ParagraphSuggestion, suggest_paragraph
from schemas import (
    BusinessModuleCreate,
    BusinessModuleName,
    CommentCreateRequest,
    CommentResolveRequest,
    CommitStatusRequest,
    DesignSignoffRequest,
    DesignSplitRequest,
    DocCreateRequest,
    DocIssueLinkRequest,
    DocMergeRequest,
    DocPatchRequest,
    DocRestoreRequest,
    DocShareRequest,
    DocUpdateRequest,
    DocVisibilityRequest,
    ExactMergeRequest,
    ExternalLinkRequest,
    ExternalRequirementRequest,
    FieldPermissionRequest,
    GitBranchCreateRequest,
    GitImportRequest,
    GitTagCreateRequest,
    IdentityLinkRequest,
    IdentityRebindRequest,
    IdentityResolveRequest,
    InviteAcceptRequest,
    InviteCreateRequest,
    IssueAssigneeRequest,
    IssueClassificationRequest,
    IssueCommentCreateRequest,
    IssueModuleRequest,
    IssueParentRequest,
    IssueTransitionRequest,
    LoginRequest,
    MemberCreateRequest,
    MergeQueueCreateRequest,
    ModuleLocationRequest,
    PullRequestCreateRequest,
    PullRequestMergeRequest,
    PullRequestReviewRequest,
    RegisterRequest,
    ReleaseCreateRequest,
    ReleaseUpdateRequest,
    RepoCreateRequest,
    RepoFileWriteRequest,
    RepoLinkRequest,
    RequirementCommitRequest,
    RequirementCreateRequest,
    RoleUpdateRequest,
    SelectedGitCommitRequest,
    TaskTargetRequest,
    TicketsRequest,
    ToolCallRequest,
)
from tianxuan_core import (
    DEFAULT_PROJECT,
    NotFound,
    PermissionDenied,
    StorageBusy,
    StorageError,
    Tianxuan,
    TianxuanError,
    TransitionRejected,
    VersionConflict,
)
from webhooks import summarize_gitea_event, verify_gitea_signature
from wenqu_bridge import build_ai_index, export_markdown, merge_offline, merge_paragraphs
from wenqu_bridge import classify as classify_markdown


def _actor_header_enabled() -> bool:
    """X-Actor 只作为显式开启的兼容入口，默认必须使用 Bearer 会话。"""
    return os.environ.get("TIANXUAN_ALLOW_ACTOR_HEADER", "0").strip() == "1"


def _require_actor(
    request: Request,
    x_actor: str | None = Header(default=None, alias="X-Actor"),
    authorization: str | None = Header(default=None),
) -> str:
    """读取操作者：优先 Bearer 会话 token；X-Actor 需要显式开启并指向真实用户。"""
    verified = getattr(request.state, "verified_actor", None)
    if verified:
        return str(verified)
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token.strip():
            session_actor = request.app.state.store.user_for_token(token.strip())
            if not session_actor:
                raise HTTPException(status_code=401, detail="invalid or expired bearer token")
            return str(session_actor)
    header_actor = (x_actor or "").strip()
    if header_actor:
        if request.app.state.native_only or not _actor_header_enabled():
            raise HTTPException(
                status_code=401,
                detail="X-Actor is disabled; create a session with POST /api/v1/auth/session and send a Bearer token",
            )
        return header_actor
    raise HTTPException(status_code=400, detail="X-Actor header or Bearer token is required")


def _websocket_actor(store: Tianxuan, query_params: Any, *, allow_header: bool = True) -> str | None:
    """WebSocket 身份：优先 token 查询参数；X-Actor 仅在兼容模式开启时接受。"""
    token = (query_params.get("token") or "").strip()
    if token:
        actor = store.user_for_token(token)
        return str(actor) if actor else None
    actor = (query_params.get("actor") or "").strip()
    if actor and allow_header and _actor_header_enabled():
        return actor
    return None


ActorDep = Annotated[str, Depends(_require_actor)]


def _private_actor(request: Request) -> str:
    # A private location always needs an authenticated session, including in legacy mode.
    if not getattr(request.state, "verified_actor", None) and not request.headers.get("authorization"):
        raise HTTPException(status_code=401, detail="authenticated account required")
    return _require_actor(request, x_actor=None, authorization=request.headers.get("authorization"))


PrivateActorDep = Annotated[str, Depends(_private_actor)]


async def _selected_commit_body(request: Request) -> SelectedGitCommitRequest:
    from native_api import _body
    from pydantic import ValidationError

    data = await _body(request, max_bytes=28 * 1024 * 1024)
    try:
        return SelectedGitCommitRequest.model_validate(data)
    except ValidationError:
        raise HTTPException(422, "invalid selected commit request") from None


class DocRooms:
    """单进程文档房间：连接、成员与广播；跨进程 fan-out 由部署层负责。"""

    def __init__(self, store: Tianxuan) -> None:
        self._store = store
        self._peers: dict[str, set[WebSocket]] = {}
        self._actors: dict[WebSocket, str] = {}

    def join(self, doc_id: str, websocket: WebSocket, actor: str) -> None:
        self._peers.setdefault(doc_id, set()).add(websocket)
        self._actors[websocket] = actor

    def leave(self, doc_id: str, websocket: WebSocket) -> None:
        peers = self._peers.get(doc_id)
        if peers is not None:
            peers.discard(websocket)
            if not peers:
                self._peers.pop(doc_id, None)
        self._actors.pop(websocket, None)

    def actors(self, doc_id: str) -> list[str]:
        return sorted(self._actors.get(peer, "") for peer in self._peers.get(doc_id, ()))

    async def broadcast(self, doc_id: str, payload: dict[str, Any]) -> None:
        for peer in list(self._peers.get(doc_id, ())):
            actor = self._actors.get(peer)
            if actor is None:
                continue
            try:
                try:
                    self._store.get_doc_shared(actor, doc_id)
                except (NotFound, PermissionDenied):
                    await peer.close(code=4403)
                    self.leave(doc_id, peer)
                    continue
                await peer.send_json(payload)
            except (OSError, RuntimeError, WebSocketDisconnect):
                self.leave(doc_id, peer)


def _find_requirement(store: Tianxuan, actor: str, request_id: str) -> dict[str, Any]:
    for row in store.list_docs(actor):
        document = store.get_doc(row["id"])
        if document["request_id"] == request_id and document["kind"] == "requirement":
            return document  # type: ignore[no-any-return]
    raise NotFound(f"requirement not found: {request_id}")


def _requirement_markdown(requirement: dict[str, Any], issues: list[dict[str, Any]]) -> str:
    lines = [
        "---",
        f"request_id: {requirement['request_id']}",
        "kind: requirement",
        f"lang: {requirement['lang']}",
        f"doc_id: {requirement['id']}",
        f"version: {requirement['version']}",
        "---",
        "",
        requirement["body_md"].rstrip(),
        "",
        "## 工单",
        "",
    ]
    if not issues:
        lines.append("（暂无工单）")
    for issue in issues:
        lines.append(f"- [ ] #{issue['number']} {issue['title']} ({issue['status']})")
    return "\n".join(lines).rstrip() + "\n"


def _gitea_client(sudo: str = "") -> GiteaClient:
    base_url = os.environ.get("TIANXUAN_GITEA_URL", "").strip()
    token = os.environ.get("TIANXUAN_GITEA_TOKEN", "").strip()
    if not base_url or not token:
        raise HTTPException(
            status_code=400,
            detail="TIANXUAN_GITEA_URL and TIANXUAN_GITEA_TOKEN are required",
        )
    return GiteaClient(base_url, token, sudo=sudo)


def _gitea_sudo(store: Tianxuan, actor: str) -> str:
    """读取操作者绑定的 Gitea 用户名；未绑定时使用服务身份（只用于读路径）。"""
    try:
        return str(store.identity_subject_for_user(actor, "gitea"))
    except NotFound:
        return ""


def _require_gitea_identity(store: Tianxuan, actor: str) -> str:
    """写操作必须以操作者自己的 Gitea 身份执行。"""
    try:
        return str(store.identity_subject_for_user(actor, "gitea"))
    except NotFound:
        raise PermissionDenied(
            "link a Gitea identity first (provider 'gitea', subject = Gitea username) before writing repositories"
        ) from None


def _repo_root() -> Path:
    root = os.environ.get("TIANXUAN_REPO_ROOT", "").strip()
    if not root:
        raise HTTPException(status_code=400, detail="TIANXUAN_REPO_ROOT is not configured")
    return Path(root).resolve()


def _repo_under_root(name: str) -> Path:
    root_path = _repo_root()
    candidate = (root_path / name).resolve()
    if not candidate.is_relative_to(root_path):
        raise HTTPException(status_code=400, detail="repo escapes TIANXUAN_REPO_ROOT")
    return candidate


def _run_import_job(
    store: Tianxuan,
    job_id: str,
    root: Path,
    name: str,
    source: str,
    allow_local: bool,
    allowed_hosts: tuple[str, ...],
    fetch_lfs: bool,
) -> None:
    """后台执行镜像导入并记录阶段；异常写入任务而不影响请求线程。"""
    try:
        store.update_import_job(job_id, status="running", phase="cloning", message="cloning source repository")
        path = GitService().import_repo(
            root,
            name,
            source,
            allow_local=allow_local,
            allowed_hosts=allowed_hosts,
            fetch_lfs=fetch_lfs,
        )
        store.update_import_job(
            job_id,
            status="succeeded",
            phase="done",
            message="import finished",
            path=str(path),
        )
    except Exception as error:  # noqa: BLE001 - background job must record any failure
        store.update_import_job(job_id, status="failed", phase="failed", error=str(error))


def _policy_patterns(app: FastAPI) -> tuple[str, ...]:
    return tuple(getattr(app.state, "protected_branches", ()) or ())


def _require_editor_role(store: Tianxuan, actor: str, action: str) -> None:
    if store.role_of(actor) == "viewer":
        raise PermissionDenied(f"viewer cannot {action}")


def create_app(
    store: Tianxuan,
    gateway: ModelGateway | None = None,
    merge_queue: Any | None = None,
    protected_branches: Sequence[str] = (),
    required_approvals: int = 0,
    required_checks: Sequence[str] = (),
    native_store: Any | None = None,
    native_only: bool = False,
    native_workflow: Any | None = None,
    native_entry: Any | None = None,
) -> FastAPI:
    """为给定领域核心实例构建 HTTP 应用；可选的模型网关与多宝合入队列挂载到同一应用。"""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app):
        if native_entry is not None:
            await native_entry.start()
        try:
            yield
        finally:
            if native_entry is not None:
                await native_entry.stop()

    app = FastAPI(title="Tianxuan API", version="0.1.0", lifespan=lifespan)
    app.state.store = store
    app.state.native_only = native_only
    from work_management_api import create_work_router

    store.work_native_store = native_store
    app.include_router(create_work_router(store, _require_actor))
    from migration_api import migration_routes
    from migration_history_api import HISTORY_TOOLS, history_routes

    migration_router, migration_tool = migration_routes(store, _require_actor, native_store)
    app.include_router(migration_router)
    history_router, history_tool = history_routes(store, _require_actor, native_store)
    app.include_router(history_router)
    configure_access(app, store)
    from workspace_conversations import create_workspace_conversation_router
    from workspace_inventory import create_workspace_inventory_router

    app.include_router(create_workspace_conversation_router(store, gateway, native_entry))
    app.include_router(create_workspace_inventory_router(native_entry, native_store))
    if native_entry is not None:
        from native_entry_api import create_entry_router

        app.state.native_entry = native_entry
        app.include_router(create_entry_router(native_entry))

        @app.middleware("http")
        async def native_mutation_event(request, call_next):
            response = await call_next(request)
            # API mutations have committed before the response. Wake waiting
            # dependency consumers for credential, source and sharing changes.
            if request.method in {"POST", "PUT", "PATCH", "DELETE"} and response.status_code < 400:
                native_entry.notify_dependency_change()
            return response

    if native_workflow is not None:
        from native_api import create_native_workflow_router

        if native_workflow.domain is not store:
            raise ValueError("Native workflow must use authenticated domain store")
        app.include_router(create_native_workflow_router(native_workflow))
    if native_store is not None:
        from business_asset_api import create_business_asset_router
        from issue_revision_api import create_issue_revision_router
        from issue_upload_api import create_issue_upload_router
        from native_api import create_native_router

        app.state.native_store = native_store
        app.include_router(create_native_router(native_store))
        app.include_router(create_business_asset_router(store, native_store))
        app.include_router(create_issue_revision_router(store, native_store))
        app.include_router(create_issue_upload_router(store, native_store))
    app.state.gateway = gateway
    app.state.merge_queue = merge_queue
    app.state.protected_branches = parse_protected_branches(protected_branches)
    app.state.required_approvals = required_approvals
    app.state.required_checks = tuple(required_checks)
    rooms = DocRooms(store)

    def notify_document_change(document: dict[str, Any]) -> dict[str, Any]:
        from_thread.run(rooms.broadcast, document["id"], {"type": "changed"})
        return document

    from game_config_api import create_game_config_router

    app.include_router(create_game_config_router(store, _require_actor, notify_document_change))

    if gateway is not None:
        app.include_router(create_model_router(gateway))

    # ---------- 领域异常 -> HTTP 状态码 ----------
    # Starlette 按异常的 MRO 查找处理器，VersionConflict/TransitionRejected
    # 是 TianxuanError 的子类，注册更具体的类型即可得到 409 而不是 400。

    @app.exception_handler(GitServiceError)
    def git_error(_request: Request, _error: GitServiceError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "invalid repository operation"})

    @app.exception_handler(StorageBusy)
    def _storage_busy(_request: Request, exc: StorageBusy) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)}, headers={"Retry-After": "1"})

    @app.exception_handler(StorageError)
    def _storage_error(_request: Request, exc: StorageError) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    @app.exception_handler(NotFound)
    def _not_found(_request: Request, exc: NotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(VersionConflict)
    def _version_conflict(_request: Request, exc: VersionConflict) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(TransitionRejected)
    def _transition_rejected(_request: Request, exc: TransitionRejected) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(PermissionDenied)
    def _permission_denied(_request: Request, exc: PermissionDenied) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(TianxuanError)
    def _domain_error(_request: Request, exc: TianxuanError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    # ---------- 健康检查 ----------

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/metrics")
    def metrics(actor: ActorDep) -> Response:
        """Prometheus 文本指标；需要管理员 Bearer 会话。"""
        if store.role_of(actor) != "admin":
            raise PermissionDenied("only an admin can read metrics")
        docs = store.list_docs(actor)
        issues = store.list_issues(actor)
        imports = store.list_import_jobs(actor, 100)
        lines = [
            "# HELP tianxuan_docs_total Documents visible to the actor.",
            "# TYPE tianxuan_docs_total gauge",
            f"tianxuan_docs_total {len(docs)}",
            "# HELP tianxuan_issues_total Issues in the tenant.",
            "# TYPE tianxuan_issues_total gauge",
            f"tianxuan_issues_total {len(issues)}",
            "# HELP tianxuan_import_jobs_total Recent import jobs.",
            "# TYPE tianxuan_import_jobs_total gauge",
            f"tianxuan_import_jobs_total {len(imports)}",
        ]
        if merge_queue is not None:
            lines.extend([
                "# HELP tianxuan_merge_queue_queued Queued merge candidates.",
                "# TYPE tianxuan_merge_queue_queued gauge",
                f"tianxuan_merge_queue_queued {merge_queue.count_items('queued')}",
                "# HELP tianxuan_merge_workers Active merge workers.",
                "# TYPE tianxuan_merge_workers gauge",
                f"tianxuan_merge_workers {len(merge_queue.list_workers())}",
            ])
        return Response(content="\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")

    @app.get("/api/v1/ready")
    def readiness() -> JSONResponse:
        """就绪检查：数据库可读、仓库根可用；返回 503 表示不应接收流量。"""
        checks: dict[str, Any] = {}
        try:
            checks["database"] = store.ping()
        except Exception:
            checks["database"] = False
        repo_root = "" if native_only else os.environ.get("TIANXUAN_REPO_ROOT", "").strip()
        if repo_root:
            checks["repo_root"] = Path(repo_root).is_dir()
        else:
            checks["repo_root"] = None
        if merge_queue is not None:
            checks["merge_worker"] = merge_queue.worker_running
        degraded = checks["database"] is not True or checks["repo_root"] is False
        return JSONResponse(
            status_code=503 if degraded else 200,
            content={"status": "degraded" if degraded else "ready", "checks": checks},
        )

    # ---------- 身份 ----------

    def check_account_attempt(request: Request) -> None:
        if os.environ.get("TIANXUAN_AUTH_MODE") != "accounts":
            return
        from identity import allow_identity_attempt

        expected = os.environ.get("TIANXUAN_PUBLIC_ORIGIN", "").rstrip("/")
        origin = request.headers.get("origin")
        if origin and origin != expected:
            raise HTTPException(403, "same-origin request required")
        if not allow_identity_attempt("account-login", request.client.host if request.client else "unknown"):
            raise HTTPException(429, "too many authentication attempts")

    @app.post("/api/v1/auth/register")
    def register(payload: RegisterRequest, request: Request) -> dict[str, str]:
        check_account_attempt(request)
        return store.register(payload.tenant_name, payload.email, payload.password, payload.name or "")  # type: ignore[no-any-return]

    @app.post("/api/v1/auth/login")
    def login(payload: LoginRequest) -> dict[str, str]:
        account = store.authenticate(payload.email, payload.password)
        if account is None:
            raise HTTPException(status_code=401, detail="invalid email or password")
        return account  # type: ignore[no-any-return]

    @app.post("/api/v1/auth/session")
    def create_session(payload: LoginRequest, request: Request):
        check_account_attempt(request)
        account = store.authenticate(payload.email, payload.password)
        if account is None:
            raise HTTPException(status_code=401, detail="invalid email or password")
        token = store.issue_session(account["user_id"])
        if os.environ.get("TIANXUAN_AUTH_MODE") == "accounts":
            from access_control import COOKIE, SESSION_COOKIE
            from fastapi.responses import JSONResponse

            result = account if request.headers.get("origin") else {**account, "token": token}
            response = JSONResponse(result, headers={"Cache-Control": "no-store"})
            response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="strict")
            response.set_cookie(
                SESSION_COOKIE, token, max_age=86400, secure=True, httponly=True, samesite="strict", path="/"
            )
            return response
        return {**account, "token": token}

    @app.post("/api/v1/auth/logout")
    def logout(request: Request, authorization: str | None = Header(default=None)):
        if os.environ.get("TIANXUAN_AUTH_MODE") == "accounts":
            from access_control import SESSION_COOKIE
            from fastapi.responses import JSONResponse

            token = request.cookies.get(SESSION_COOKIE, "")
            if authorization:
                scheme, _, value = authorization.partition(" ")
                if scheme.lower() == "bearer":
                    token = value.strip()
            response = JSONResponse({"revoked": store.revoke_session(token)})
            response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="strict")
            return response
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise HTTPException(status_code=400, detail="Bearer token is required")
        return {"revoked": store.revoke_session(token.strip())}

    if native_only and native_store is None:
        raise ValueError("native_only requires a native store")

    # ---------- 成员与角色 ----------

    @app.get("/api/v1/users")
    def list_members(actor: ActorDep) -> dict[str, list[dict[str, Any]]]:
        return {"users": store.list_members(actor)}

    @app.post("/api/v1/users")
    def add_member(payload: MemberCreateRequest, actor: ActorDep) -> dict[str, Any]:
        return store.add_member(actor, payload.email, payload.password, payload.name, payload.role)  # type: ignore[no-any-return]

    @app.patch("/api/v1/users/{user_id}/role")
    def set_role(user_id: str, payload: RoleUpdateRequest, actor: ActorDep) -> dict[str, Any]:
        return store.set_role(actor, user_id, payload.role)  # type: ignore[no-any-return]

    @app.post("/api/v1/invites")
    def create_invite(payload: InviteCreateRequest, actor: ActorDep) -> dict[str, Any]:
        return store.create_invite(actor, payload.email, payload.role)  # type: ignore[no-any-return]

    @app.post("/api/v1/invites/accept")
    def accept_invite(payload: InviteAcceptRequest) -> dict[str, Any]:
        return store.accept_invite(payload.code, payload.password, payload.name)  # type: ignore[no-any-return]

    # ---------- 文曲：文档 ----------

    @app.get("/api/v1/docs")
    def list_docs(actor: ActorDep, kind: str | None = Query(default=None)) -> dict[str, list[dict[str, Any]]]:
        return {"docs": store.list_docs(actor, kind)}

    @app.post("/api/v1/docs")
    def create_doc(payload: DocCreateRequest, actor: ActorDep) -> dict[str, Any]:
        return store.create_doc(  # type: ignore[no-any-return]
            actor,
            payload.title,
            payload.body_md,
            lang=payload.lang,
            kind=payload.kind,
            request_id=payload.request_id,
            call_id=payload.call_id,
        )

    @app.get("/api/v1/docs/{doc_id}")
    def get_doc(doc_id: str, actor: ActorDep) -> dict[str, Any]:
        return store.get_doc_shared(actor, doc_id)  # type: ignore[no-any-return]

    @app.get("/api/v1/docs/{doc_id}/export/file")
    def download_doc(doc_id: str, actor: ActorDep, format: str = Query(default="md")) -> Response:
        document = store.get_doc_shared(actor, doc_id)
        fmt = format.strip().lower()
        if fmt not in {"md", "markdown", "html", "docx", "pdf"}:
            raise HTTPException(status_code=400, detail=f"unsupported export format: {format}")
        title = str(document.get("title", "document"))
        body_md = str(document.get("body_md", ""))
        safe_name = (
            "".join(
                character for character in title if character not in '\\/:*?"<>|' and character not in "\r\n"
            ).strip()
            or "document"
        )
        content: str | bytes
        if fmt in {"md", "markdown"}:
            content = body_md
            media_type = "text/markdown; charset=utf-8"
            extension = "md"
        elif fmt == "html":
            content = (
                '<!doctype html><html lang="zh"><head><meta charset="utf-8">'
                f"<title>{html.escape(title)}</title>"
                "<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
                "max-width:880px;margin:40px auto;padding:0 24px;line-height:1.7;color:#1b1a17}"
                "pre{background:#f6f3ec;padding:14px 16px;border-radius:8px;overflow:auto}"
                "code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.92em}"
                "blockquote{border-left:3px solid #c9c0ae;margin:0;padding-left:14px;color:#5d584f}"
                "</style></head><body>"
                f'<h1>{html.escape(title)}</h1><div class="markdown">{render_markdown(body_md)}</div>'
                "</body></html>"
            )
            media_type = "text/html; charset=utf-8"
            extension = "html"
        elif fmt == "docx":
            from docx_export import render_docx

            content = render_docx(title, body_md)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            extension = "docx"
        else:
            from pdf_export import render_pdf

            content = render_pdf(title, body_md)
            media_type = "application/pdf"
            extension = "pdf"
        disposition = f"attachment; filename=document.{extension}; filename*=UTF-8''{quote(safe_name)}.{extension}"
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": disposition},
        )

    @app.patch("/api/v1/docs/{doc_id}")
    def update_doc(doc_id: str, payload: DocUpdateRequest, actor: ActorDep) -> dict[str, Any]:
        updated = store.update_doc(
            actor,
            doc_id,
            payload.body_md,
            payload.expected_version,
            title=payload.title,
            status=payload.status,
            call_id=payload.call_id,
        )

        # ---------- 偃师：需求与工单 ----------
        return notify_document_change(updated)

    @app.post("/api/v1/requirements")
    def create_requirement(payload: RequirementCreateRequest, actor: ActorDep) -> dict[str, Any]:
        return store.create_requirement(  # type: ignore[no-any-return]
            actor,
            payload.request_id,
            payload.title,
            payload.outcome,
            payload.scope,
            payload.acceptance,
            lang=payload.lang,
            call_id=payload.call_id,
        )

    @app.post("/api/v1/requirements/{doc_id}/tickets")
    def plan_tickets(doc_id: str, payload: TicketsRequest, actor: ActorDep) -> dict[str, list[dict[str, Any]]]:
        tickets = [ticket.model_dump() for ticket in payload.tickets]
        return {"issues": store.plan_tickets(actor, doc_id, tickets, call_id=payload.call_id)}

    # ---------- 司南：工单 ----------

    @app.get("/api/v1/business-modules")
    def business_modules(actor: ActorDep, project: str = DEFAULT_PROJECT) -> dict[str, list[dict[str, Any]]]:
        return {"modules": store.list_business_modules(actor, project)}

    @app.post("/api/v1/business-modules")
    def create_module(payload: BusinessModuleCreate, actor: ActorDep, project: str = DEFAULT_PROJECT) -> dict[str, Any]:
        return cast(dict[str, Any], store.create_business_module(actor, project, payload.name, call_id=payload.call_id))

    @app.patch("/api/v1/business-modules/{module_id}")
    def rename_module(
        module_id: str, payload: BusinessModuleName, actor: ActorDep, project: str = DEFAULT_PROJECT
    ) -> dict[str, Any]:
        return cast(dict[str, Any], store.rename_business_module(actor, project, module_id, payload.name))

    @app.get("/api/v1/business-modules/{module_id}/location")
    def module_location(
        module_id: str, actor: PrivateActorDep, response: Response, project: str = DEFAULT_PROJECT
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "private, no-store"
        return {"location": store.module_location(actor, project, module_id)}

    @app.put("/api/v1/business-modules/{module_id}/location")
    def save_module_location(
        module_id: str,
        payload: ModuleLocationRequest,
        actor: PrivateActorDep,
        response: Response,
        project: str = DEFAULT_PROJECT,
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "private, no-store"
        location = store.save_module_location(
            actor,
            project,
            module_id,
            payload.issue_id,
            str(payload.conversation_id) if payload.conversation_id else None,
            payload.position,
        )
        return {"location": location}

    @app.get("/api/v1/issues")
    def list_issues(
        actor: ActorDep,
        status: str | None = Query(default=None),
        requirement_id: str | None = Query(default=None),
        project: str | None = Query(default=None),
        module_id: str | None = Query(default=None),
        assignee: str | None = Query(default=None),
        q: str | None = Query(default=None),
        label: str | None = Query(default=None, min_length=1, max_length=128),
    ) -> dict[str, Any]:
        issues = store.list_issues(
            actor,
            requirement_id,
            project=project,
            module_id=module_id,
            status=status,
            assignee=assignee,
            keyword=q,
            label=label,
        )
        result: dict[str, Any] = {"issues": issues}
        if assignee or q:
            result["applied_search"] = {"assignee": assignee or "", "q": q or ""}
        if label is not None:
            result["label_filter"] = {"name": label.strip(), "project": project or DEFAULT_PROJECT}
        return result

    @app.get("/api/v1/issues/by-number/{number}")
    def read_issue_number(number: int, actor: ActorDep, project: str = DEFAULT_PROJECT) -> dict[str, Any]:
        return cast(dict[str, Any], store.read_issue_number(actor, project, number))

    @app.get("/api/v1/issues/by-number/{number}/detail")
    def read_issue_detail(number: int, actor: ActorDep, project: str = DEFAULT_PROJECT) -> dict[str, Any]:
        return cast(dict[str, Any], store.read_issue_detail(actor, project, number))

    @app.put("/api/v1/issues/{issue_id}/task-target")
    def set_task_target(
        issue_id: str, payload: TaskTargetRequest, actor: ActorDep, project: str = DEFAULT_PROJECT
    ) -> dict[str, Any]:
        return cast(dict[str, Any], store.set_task_target(actor, issue_id, project, **payload.model_dump()))

    @app.put("/api/v1/issues/{issue_id}/classification")
    def set_issue_classification(
        issue_id: str, payload: IssueClassificationRequest, actor: ActorDep, project: str = DEFAULT_PROJECT
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            store.set_issue_classification(
                actor, issue_id, project, payload.type, payload.labels, payload.expected_type, payload.expected_labels
            ),
        )

    @app.get("/api/v1/issues/{issue_id}/hierarchy")
    def issue_hierarchy(issue_id: str, actor: ActorDep, project: str = DEFAULT_PROJECT) -> dict[str, Any]:
        return cast(dict[str, Any], store.issue_hierarchy(actor, issue_id, project))

    @app.put("/api/v1/issues/{issue_id}/hierarchy")
    def set_issue_parent(
        issue_id: str, payload: IssueParentRequest, actor: ActorDep, project: str = DEFAULT_PROJECT
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            store.set_issue_parent(actor, issue_id, project, payload.parent_number, payload.expected_parent_id),
        )

    @app.get("/api/v1/issues/{issue_id}")
    def read_issue(issue_id: str, actor: ActorDep) -> dict[str, Any]:
        return cast(dict[str, Any], store.read_issue(actor, issue_id))

    @app.put("/api/v1/issues/{issue_id}/assignee")
    def set_issue_assignee(
        issue_id: str, payload: IssueAssigneeRequest, actor: ActorDep, project: str = DEFAULT_PROJECT
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            store.set_issue_assignee(actor, issue_id, project, payload.assignee_id, payload.expected_assignee_id),
        )

    @app.put("/api/v1/issues/{issue_id}/module")
    def set_issue_module(
        issue_id: str, payload: IssueModuleRequest, actor: ActorDep, project: str = DEFAULT_PROJECT
    ) -> dict[str, Any]:
        return cast(dict[str, Any], store.set_issue_module(actor, issue_id, project, payload.module_id))

    @app.patch("/api/v1/issues/{issue_id}")
    def transition_issue(issue_id: str, payload: IssueTransitionRequest, actor: ActorDep) -> dict[str, Any]:
        return store.transition_issue(actor, issue_id, payload.to_status, call_id=payload.call_id)  # type: ignore[no-any-return]

    @app.post("/api/v1/issues/{issue_id}/comments")
    def create_issue_comment(issue_id: str, payload: IssueCommentCreateRequest, actor: ActorDep) -> dict[str, Any]:
        return store.add_issue_comment(  # type: ignore[no-any-return]
            actor, issue_id, payload.body, payload.parent_id, call_id=payload.call_id
        )

    @app.get("/api/v1/issues/{issue_id}/comments")
    def list_issue_comments(issue_id: str, actor: ActorDep) -> dict[str, list[dict[str, Any]]]:
        return {"comments": store.list_issue_comments(actor, issue_id)}

    # ---------- 跨系统：天枢 ↔ 天璇 ----------

    @app.post("/api/v1/external-links")
    def create_external_link(payload: ExternalLinkRequest, actor: ActorDep) -> dict[str, Any]:
        return store.link_external(  # type: ignore[no-any-return]
            actor, payload.system, payload.external_id, payload.target_type, payload.target_id
        )

    @app.get("/api/v1/external-links")
    def list_external_links(
        actor: ActorDep,
        system: str = Query(min_length=1),
        external_id: str = Query(min_length=1),
    ) -> dict[str, list[dict[str, Any]]]:
        return {"links": store.external_targets(actor, system, external_id)}

    @app.get("/api/v1/external-context")
    def external_context(
        actor: ActorDep,
        system: str = Query(min_length=1),
        external_id: str = Query(min_length=1),
    ) -> dict[str, Any]:
        return store.external_context(actor, system, external_id)  # type: ignore[no-any-return]

    @app.post("/api/v1/requirements/from-external")
    def requirement_from_external(payload: ExternalRequirementRequest, actor: ActorDep) -> dict[str, Any]:
        return store.create_requirement_from_external(  # type: ignore[no-any-return]
            actor,
            payload.system,
            payload.external_id,
            payload.request_id,
            payload.title,
            payload.outcome,
            payload.scope,
            payload.acceptance,
            [ticket.model_dump() for ticket in payload.tickets],
        )

    @app.get("/api/v1/docs/{doc_id}/external-links")
    def doc_external_links(doc_id: str, actor: ActorDep) -> dict[str, list[dict[str, Any]]]:
        return {"links": store.external_links_for(actor, "doc", doc_id)}

    @app.get("/api/v1/issues/{issue_id}/external-links")
    def issue_external_links(issue_id: str, actor: ActorDep) -> dict[str, list[dict[str, Any]]]:
        return {"links": store.external_links_for(actor, "issue", issue_id)}

    # ---------- 身份适配 ----------

    @app.post("/api/v1/identity/links")
    def create_identity_link(payload: IdentityLinkRequest, actor: ActorDep) -> dict[str, Any]:
        return store.link_identity(  # type: ignore[no-any-return]
            actor, payload.provider, payload.subject, payload.user_id
        )

    @app.get("/api/v1/identity/links")
    def list_identity_links(
        actor: ActorDep,
        provider: str | None = Query(default=None),
        subject: str | None = Query(default=None),
    ) -> dict[str, list[dict[str, Any]]]:
        return {"links": store.list_identity_links(actor, provider, subject)}

    @app.patch("/api/v1/identity/links/{link_id}")
    def rebind_identity_link(link_id: str, payload: IdentityRebindRequest, actor: ActorDep) -> dict[str, Any]:
        return store.rebind_identity(actor, link_id, payload.user_id)  # type: ignore[no-any-return]

    @app.delete("/api/v1/identity/links/{link_id}")
    def delete_identity_link(link_id: str, actor: ActorDep) -> dict[str, Any]:
        return store.unlink_identity(actor, link_id)  # type: ignore[no-any-return]

    @app.get("/api/v1/identity/events")
    def list_identity_events(
        actor: ActorDep,
        limit: int = Query(default=50, ge=1, le=200),
        event_type: str | None = Query(default=None),
    ) -> dict[str, list[dict[str, Any]]]:
        try:
            return {"events": store.identity_events(actor, limit, event_type)}
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/api/v1/identity/resolve")
    def resolve_external_identity(payload: IdentityResolveRequest, request: Request) -> dict[str, Any]:
        client_key = payload.subject.strip() or "unknown"
        if not allow_identity_attempt(payload.provider, client_key):
            raise HTTPException(status_code=429, detail="too many identity attempts")
        adapter = get_identity_adapter(payload.provider)
        if adapter is None:
            raise HTTPException(status_code=400, detail=f"unknown identity provider: {payload.provider}")
        if not adapter.verify(payload.subject, payload.secret):
            raise HTTPException(status_code=403, detail="identity verification failed")
        link = store.resolve_identity(payload.provider, payload.subject)
        token = store.issue_session(link["user_id"])
        return {
            "provider": payload.provider,
            "subject": payload.subject,
            "user_id": link["user_id"],
            "tenant_id": link["tenant_id"],
            "token": token,
        }

    # ---------- 事件流 ----------

    @app.get("/api/v1/events")
    def list_events(actor: ActorDep, limit: int = Query(default=100, ge=1, le=500)) -> dict[str, list[dict[str, Any]]]:
        return {"events": store.events(actor, limit)}

    @app.post("/api/v1/events/prune")
    def prune_events(
        actor: ActorDep,
        older_than_days: int = Query(default=90, ge=1, le=3650),
        type_prefix: str | None = Query(default=None),
    ) -> dict[str, int]:
        return {"deleted": store.prune_events(actor, older_than_days, type_prefix)}

    # ---------- 文曲：检索、导出、AI 视图、归类 ----------

    @app.get("/api/v1/search")
    def search_docs(
        actor: ActorDep,
        q: str = Query(min_length=1),
        limit: int = Query(default=20, ge=1, le=100),
    ) -> dict[str, list[dict[str, Any]]]:
        return cast(dict[str, list[dict[str, Any]]], store.search_docs(actor, q, limit))

    @app.get("/api/v1/docs/{doc_id}/export")
    def export_doc(doc_id: str, actor: ActorDep) -> dict[str, str]:
        document = store.get_doc_shared(actor, doc_id)
        return {"filename": f"{doc_id}.md", "markdown": export_markdown(document)}

    @app.get("/api/v1/docs/{doc_id}/ai-view")
    def ai_view(
        doc_id: str,
        actor: ActorDep,
        include_body: bool = True,
        start_line: int = Query(default=1, ge=1),
        max_lines: int | None = Query(default=None, ge=1),
        max_chars: int | None = Query(default=None, ge=1),
        expected_version: int | None = Query(default=None, ge=1),
    ) -> dict[str, Any]:
        store.get_doc_shared(actor, doc_id)
        result = store.ai_view(
            doc_id,
            include_body=include_body,
            start_line=start_line,
            max_lines=max_lines,
            max_chars=max_chars,
            expected_version=expected_version,
        )
        return cast(dict[str, Any], result)

    @app.post("/api/v1/docs/{doc_id}/classify")
    def classify_doc(doc_id: str, actor: ActorDep) -> dict[str, list[str]]:
        document = store.get_doc_shared(actor, doc_id)
        return {"tags": classify_markdown(document["body_md"])}

    # ---------- 文曲：离线草稿合并 ----------

    def merge_inputs(doc_id: str, payload: DocMergeRequest, actor: str) -> tuple[dict[str, Any], str]:
        document = store.get_doc_shared(actor, doc_id, write=True)
        if not 1 <= payload.expected_version <= document["version"]:
            raise VersionConflict("draft base version is outside document history")
        base = store.version(doc_id, payload.expected_version)["body_md"]
        if payload.base_md != base:
            raise VersionConflict("draft base content does not match its version")
        return document, base

    @app.post("/api/v1/docs/{doc_id}/merge/preview")
    def preview_paragraph_merge(doc_id: str, payload: DocMergeRequest, actor: ActorDep) -> Any:
        document, base = merge_inputs(doc_id, payload, actor)
        remote = document["body_md"]
        merged, conflicts = merge_paragraphs(base, payload.local_md, remote)
        if conflicts:
            return JSONResponse(
                status_code=409,
                content={
                    "status": "conflict",
                    "remote_md": remote,
                    "remote_version": document["version"],
                },
            )
        return {"status": "ready", "body_md": merged, "remote_version": document["version"]}

    @app.post("/api/v1/docs/{doc_id}/merge")
    def merge_doc(doc_id: str, payload: DocMergeRequest, actor: ActorDep) -> Any:
        document, base = merge_inputs(doc_id, payload, actor)
        if document["version"] == payload.expected_version:
            updated = store.update_doc(actor, doc_id, payload.local_md, payload.expected_version)
            return {"status": "applied", "doc": notify_document_change(updated)}
        merged_md, conflicts = merge_offline(base, payload.local_md, document["body_md"])
        if conflicts:
            return JSONResponse(
                status_code=409,
                content={
                    "status": "conflict",
                    "conflicts": conflicts,
                    "remote_version": document["version"],
                },
            )
        updated = store.update_doc(actor, doc_id, merged_md, document["version"])
        return {"status": "merged", "doc": notify_document_change(updated), "remote_version": document["version"]}

    # ---------- 文曲：文档链接与反向链接 ----------

    @app.get("/api/v1/docs/{doc_id}/links")
    def doc_links(doc_id: str, actor: ActorDep) -> dict[str, list[dict[str, Any]]]:
        document = store.get_doc_shared(actor, doc_id)
        documents = [store.get_doc(row["id"]) for row in store.list_docs(actor)]
        by_title = {item["title"]: item["id"] for item in documents}
        by_title.update({item["id"]: item["id"] for item in documents})
        outgoing = []
        for target in build_ai_index(document["body_md"])["links"]:
            target_id = by_title.get(target)
            outgoing.append({"target": target, "doc_id": target_id, "resolved": target_id is not None})
        backlinks = []
        for other in documents:
            if other["id"] == doc_id:
                continue
            links = set(build_ai_index(other["body_md"])["links"])
            if document["id"] in links or document["title"] in links:
                backlinks.append({"doc_id": other["id"], "title": other["title"]})
        return {"outgoing": outgoing, "backlinks": backlinks}

    @app.get("/api/v1/docs/{doc_id}/issues")
    def list_doc_issues(doc_id: str, actor: ActorDep) -> dict[str, list[dict[str, Any]]]:
        return {"issues": store.list_doc_issues(actor, doc_id)}

    @app.post("/api/v1/docs/{doc_id}/issues")
    def link_doc_issue(doc_id: str, payload: DocIssueLinkRequest, actor: ActorDep) -> dict[str, Any]:
        return store.link_doc_issue(actor, doc_id, payload.issue_id)  # type: ignore[no-any-return]

    @app.delete("/api/v1/docs/{doc_id}/issues/{issue_id}")
    def unlink_doc_issue(doc_id: str, issue_id: str, actor: ActorDep) -> dict[str, Any]:
        return store.unlink_doc_issue(actor, doc_id, issue_id)  # type: ignore[no-any-return]

    @app.get("/api/v1/issues/{issue_id}/docs")
    def list_issue_docs(issue_id: str, actor: ActorDep) -> dict[str, list[dict[str, Any]]]:
        return {"docs": store.list_issue_docs(actor, issue_id)}

    # ---------- 偃师：需求导出与落库 ----------

    @app.get("/api/v1/requirements/{request_id}/export")
    def export_requirement(request_id: str, actor: ActorDep) -> dict[str, str]:
        requirement = _find_requirement(store, actor, request_id)
        issues = store.list_issues(actor, requirement_id=requirement["id"])
        return {"filename": f"{request_id}.md", "markdown": _requirement_markdown(requirement, issues)}

    @app.post("/api/v1/requirements/{request_id}/commit")
    def commit_requirement(request_id: str, payload: RequirementCommitRequest, actor: ActorDep) -> dict[str, str]:
        requirement = _find_requirement(store, actor, request_id)
        issues = store.list_issues(actor, requirement_id=requirement["id"])
        markdown = _requirement_markdown(requirement, issues)
        root = os.environ.get("TIANXUAN_REPO_ROOT", "").strip()
        if not root:
            raise HTTPException(status_code=400, detail="TIANXUAN_REPO_ROOT is not configured")
        root_path = Path(root).resolve()
        repo_path = (root_path / payload.repo).resolve()
        if not repo_path.is_relative_to(root_path):
            raise HTTPException(status_code=400, detail="repo escapes TIANXUAN_REPO_ROOT")
        relative = f"design/{request_id}.md"
        try:
            sha = GitService().commit(
                repo_path,
                payload.branch,
                payload.message or f"docs: add requirement {request_id}",
                {relative: markdown},
                payload.author_name,
                payload.author_email,
            )
        except (GitServiceError, OSError) as error:
            raise HTTPException(status_code=400, detail=f"commit failed: {error}") from error
        return {"commit": sha, "path": relative, "branch": payload.branch}

    # ---------- 司南：看板 ----------

    @app.get("/api/v1/board")
    def issue_board(actor: ActorDep) -> dict[str, dict[str, list[dict[str, Any]]]]:
        columns: dict[str, list[dict[str, Any]]] = {}
        for issue in store.list_issues(actor):
            columns.setdefault(issue["status"], []).append(issue)
        return {"columns": columns}

    # ---------- 文曲：AI 结构化补丁 ----------

    @app.post("/api/v1/docs/{doc_id}/paragraph-suggestion")
    def preview_paragraph(doc_id: str, payload: ParagraphSuggestion, request: Request) -> dict[str, Any]:
        actor = workspace_actor(request, write=True)
        preview: dict[str, Any] = suggest_paragraph(store, gateway, actor, doc_id, payload)
        return preview

    @app.post("/api/v1/docs/{doc_id}/patch")
    def patch_doc(doc_id: str, payload: DocPatchRequest, actor: ActorDep) -> dict[str, Any]:
        result = store.patch_doc(
            actor,
            doc_id,
            payload.expected_version,
            [operation.model_dump() for operation in payload.patches],
            call_id=payload.call_id,
        )
        return notify_document_change(result)

    # ---------- 文曲：版本历史与差异 ----------

    @app.get("/api/v1/docs/{doc_id}/versions")
    def list_versions(doc_id: str, actor: ActorDep) -> dict[str, list[dict[str, Any]]]:
        store.get_doc_shared(actor, doc_id)
        return {"versions": store.versions(doc_id)}

    @app.get("/api/v1/docs/{doc_id}/versions/{version}")
    def get_version(doc_id: str, version: int, actor: ActorDep) -> dict[str, Any]:
        store.get_doc_shared(actor, doc_id)
        return store.version(doc_id, version)  # type: ignore[no-any-return]

    @app.get("/api/v1/docs/{doc_id}/versions/{version}/signoff")
    def get_design_signoff(doc_id: str, version: int, actor: ActorDep) -> dict[str, Any]:
        return {"signoff": store.design_signoff(actor, doc_id, version)}

    @app.post("/api/v1/docs/{doc_id}/versions/{version}/signoff")
    def confirm_design(doc_id: str, version: int, payload: DesignSignoffRequest, actor: ActorDep) -> dict[str, Any]:
        return {"signoff": store.design_signoff(actor, doc_id, version, payload.acceptance)}

    @app.get("/api/v1/docs/{doc_id}/versions/{version}/tasks")
    def design_tasks(doc_id: str, version: int, actor: ActorDep, project: str = DEFAULT_PROJECT) -> dict[str, Any]:
        return {"tasks": store.design_tasks(actor, doc_id, version, project)}

    @app.post("/api/v1/docs/{doc_id}/versions/{version}/tasks")
    def split_design(
        doc_id: str, version: int, payload: DesignSplitRequest, actor: ActorDep, project: str = DEFAULT_PROJECT
    ) -> dict[str, Any]:
        items = [item.model_dump() for item in payload.items]
        return {"tasks": store.split_design(actor, doc_id, version, project, items, payload.call_id)}

    @app.post("/api/v1/docs/{doc_id}/versions/{version}/restore")
    def restore_version(doc_id: str, version: int, payload: DocRestoreRequest, actor: ActorDep) -> dict[str, Any]:
        updated = store.restore_doc(actor, doc_id, version, payload.expected_version, call_id=payload.call_id)
        return notify_document_change(updated)

    @app.get("/api/v1/docs/{doc_id}/diff")
    def diff_versions(
        doc_id: str,
        actor: ActorDep,
        from_version: int = Query(ge=1),
        to_version: int = Query(ge=1),
    ) -> dict[str, str]:
        store.get_doc_shared(actor, doc_id)
        before = store.version(doc_id, from_version)["body_md"]
        after = store.version(doc_id, to_version)["body_md"]
        diff = "\n".join(
            difflib.unified_diff(
                before.splitlines(),
                after.splitlines(),
                fromfile=f"v{from_version}",
                tofile=f"v{to_version}",
                lineterm="",
            )
        )
        return {"diff": diff}

    # ---------- 多宝：Gitea 仓库接入 ----------

    @app.get("/api/v1/gitea/status")
    def gitea_status() -> dict[str, Any]:
        return {
            "configured": bool(os.environ.get("TIANXUAN_GITEA_URL") and os.environ.get("TIANXUAN_GITEA_TOKEN")),
            "owner": os.environ.get("TIANXUAN_GITEA_OWNER", ""),
        }

    @app.get("/api/v1/repos")
    def list_repos(
        actor: ActorDep,
        owner: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> dict[str, list[dict[str, Any]]]:
        client = _gitea_client(_gitea_sudo(store, actor))
        try:
            with client:
                return {"repos": client.list_repos(owner, limit)}
        except GiteaError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/api/v1/repos")
    def create_repo(payload: RepoCreateRequest, actor: ActorDep) -> dict[str, Any]:
        if store.role_of(actor) != "admin":
            raise PermissionDenied("only an admin can create repositories")
        client = _gitea_client(_require_gitea_identity(store, actor))
        try:
            with client:
                return client.create_repo(  # type: ignore[no-any-return]
                    payload.name, payload.private, payload.default_branch
                )
        except GiteaError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/v1/repos/{owner}/{name}")
    def get_repo(owner: str, name: str, actor: ActorDep) -> dict[str, Any]:
        client = _gitea_client(_gitea_sudo(store, actor))
        try:
            with client:
                return client.get_repo(owner, name)  # type: ignore[no-any-return]
        except GiteaError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/v1/repos/{owner}/{name}/branches")
    def list_repo_branches(owner: str, name: str, actor: ActorDep) -> dict[str, list[dict[str, Any]]]:
        client = _gitea_client(_gitea_sudo(store, actor))
        try:
            with client:
                return {"branches": client.list_branches(owner, name)}
        except GiteaError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/api/v1/repos/{owner}/{name}/releases")
    def create_repo_release(
        owner: str,
        name: str,
        payload: ReleaseCreateRequest,
        actor: ActorDep,
    ) -> dict[str, Any]:
        _require_editor_role(store, actor, "create releases")
        client = _gitea_client(_require_gitea_identity(store, actor))
        try:
            with client:
                return client.create_release(  # type: ignore[no-any-return]
                    owner, name, payload.tag_name, payload.name, payload.body, payload.draft, payload.prerelease
                )
        except GiteaError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.patch("/api/v1/repos/{owner}/{name}/releases/{release_id}")
    def update_repo_release(
        owner: str,
        name: str,
        release_id: int,
        payload: ReleaseUpdateRequest,
        actor: ActorDep,
    ) -> dict[str, Any]:
        _require_editor_role(store, actor, "update releases")
        client = _gitea_client(_require_gitea_identity(store, actor))
        try:
            with client:
                return client.update_release(  # type: ignore[no-any-return]
                    owner,
                    name,
                    release_id,
                    name=payload.name,
                    body=payload.body,
                    draft=payload.draft,
                    prerelease=payload.prerelease,
                )
        except GiteaError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/v1/repos/{owner}/{name}/releases")
    def list_repo_releases(
        owner: str,
        name: str,
        actor: ActorDep,
    ) -> dict[str, list[dict[str, Any]]]:
        client = _gitea_client(_gitea_sudo(store, actor))
        try:
            with client:
                return {"releases": client.list_releases(owner, name)}
        except GiteaError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/v1/repos/{owner}/{name}/pulls")
    def list_repo_pulls(
        owner: str,
        name: str,
        actor: ActorDep,
        state: str = Query(default="open"),
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=30, ge=1, le=100),
    ) -> dict[str, list[dict[str, Any]]]:
        client = _gitea_client(_gitea_sudo(store, actor))
        try:
            with client:
                return {"pulls": client.list_pull_requests(owner, name, state, page, limit)}
        except GiteaError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/api/v1/repos/{owner}/{name}/pulls")
    def create_repo_pull(
        owner: str,
        name: str,
        payload: PullRequestCreateRequest,
        actor: ActorDep,
    ) -> dict[str, Any]:
        _require_editor_role(store, actor, "create pull requests")
        client = _gitea_client(_require_gitea_identity(store, actor))
        try:
            with client:
                return client.create_pull_request(  # type: ignore[no-any-return]
                    owner, name, payload.title, payload.head, payload.base, payload.body
                )
        except GiteaError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/api/v1/repos/{owner}/{name}/pulls/{number}/merge")
    def merge_repo_pull(
        owner: str,
        name: str,
        number: int,
        payload: PullRequestMergeRequest,
        actor: ActorDep,
    ) -> dict[str, Any]:
        client = _gitea_client(_require_gitea_identity(store, actor))
        try:
            with client:
                pull = client.get_pull_request(owner, name, number)
                base = str(pull.get("base") or "")
                if not base:
                    raise HTTPException(status_code=502, detail="pull request base branch is missing")
                required = int(getattr(app.state, "required_approvals", 0) or 0)
                reviews = client.list_reviews(owner, name, number) if required else []
                ensure_pr_merge_allowed(
                    base,
                    _policy_patterns(app),
                    actor_role=store.role_of(actor),
                    approvals=approved_reviewers(reviews),
                    required_approvals=required,
                    path="direct",
                )
                required_checks = tuple(getattr(app.state, "required_checks", ()) or ())
                if required_checks:
                    head_sha = str(pull.get("head_sha") or "")
                    if not head_sha:
                        raise HTTPException(status_code=502, detail="pull request head sha is missing")
                    ensure_checks_passed(client.list_commit_statuses(owner, name, head_sha), required_checks)
                return client.merge_pull_request(  # type: ignore[no-any-return]
                    owner, name, number, payload.method
                )
        except PolicyError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except GiteaError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/v1/repos/{owner}/{name}/pulls/{number}/reviews")
    def list_repo_pull_reviews(owner: str, name: str, number: int, actor: ActorDep) -> dict[str, list[dict[str, Any]]]:
        client = _gitea_client(_gitea_sudo(store, actor))
        try:
            with client:
                return {"reviews": client.list_reviews(owner, name, number)}
        except GiteaError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/api/v1/repos/{owner}/{name}/pulls/{number}/reviews")
    def create_repo_pull_review(
        owner: str,
        name: str,
        number: int,
        payload: PullRequestReviewRequest,
        actor: ActorDep,
    ) -> dict[str, Any]:
        _require_editor_role(store, actor, "review pull requests")
        client = _gitea_client(_require_gitea_identity(store, actor))
        try:
            with client:
                return client.create_review(  # type: ignore[no-any-return]
                    owner, name, number, event=payload.event, body=payload.body
                )
        except GiteaError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/v1/repos/{owner}/{name}/commits/{sha}/statuses")
    def list_repo_commit_statuses(
        owner: str,
        name: str,
        sha: str,
        actor: ActorDep,
    ) -> dict[str, list[dict[str, Any]]]:
        client = _gitea_client(_gitea_sudo(store, actor))
        try:
            with client:
                return {"statuses": client.list_commit_statuses(owner, name, sha)}
        except GiteaError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/api/v1/repos/{owner}/{name}/statuses/{sha}")
    def create_repo_commit_status(
        owner: str,
        name: str,
        sha: str,
        payload: CommitStatusRequest,
        actor: ActorDep,
    ) -> dict[str, Any]:
        _require_editor_role(store, actor, "write commit statuses")
        client = _gitea_client(_gitea_sudo(store, actor))
        try:
            with client:
                return client.create_commit_status(  # type: ignore[no-any-return]
                    owner,
                    name,
                    sha,
                    state=payload.state,
                    context=payload.context,
                    description=payload.description,
                    target_url=payload.target_url,
                )
        except GiteaError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    # ---------- 多宝：仓库绑定与 webhook ----------

    @app.post("/api/v1/repo-links")
    def bind_repo_link(payload: RepoLinkRequest, actor: ActorDep) -> dict[str, Any]:
        return store.bind_repo(actor, payload.provider, payload.owner, payload.name)  # type: ignore[no-any-return]

    @app.get("/api/v1/repo-links")
    def list_repo_links(actor: ActorDep) -> dict[str, list[dict[str, Any]]]:
        return {"links": store.list_repo_links(actor)}

    @app.delete("/api/v1/repo-links/{link_id}")
    def unbind_repo_link(link_id: str, actor: ActorDep) -> dict[str, Any]:
        return store.unbind_repo(actor, link_id)  # type: ignore[no-any-return]

    @app.post("/api/v1/webhooks/gitea")
    async def gitea_webhook(request: Request) -> JSONResponse:
        secret = os.environ.get("TIANXUAN_GITEA_WEBHOOK_SECRET", "").strip()
        if not secret:
            raise HTTPException(status_code=503, detail="Gitea webhook is not configured")
        body = await request.body()
        if not verify_gitea_signature(secret, body, request.headers.get("X-Gitea-Signature", "")):
            raise HTTPException(status_code=401, detail="invalid webhook signature")
        event = request.headers.get("X-Gitea-Event", "").strip()
        delivery = request.headers.get("X-Gitea-Delivery", "").strip()
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise HTTPException(status_code=400, detail="invalid webhook payload") from None
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="invalid webhook payload")
        summary = summarize_gitea_event(event, payload)
        if summary is None:
            return JSONResponse(status_code=202, content={"accepted": False, "reason": "unsupported event"})
        repository = summary["payload"]
        try:
            tenant_id = store.tenant_for_repo(
                "gitea",
                str(repository.get("owner", "")),
                str(repository.get("name", "")),
            )
        except TianxuanError:
            return JSONResponse(status_code=202, content={"accepted": False, "reason": "invalid repository"})
        if tenant_id is None:
            return JSONResponse(status_code=202, content={"accepted": False, "reason": "unlinked repository"})
        store.record_repo_event(
            tenant_id,
            str(summary["type"]),
            str(summary["target"]),
            {**repository, "delivery": delivery, "event": event},
        )
        return JSONResponse(status_code=202, content={"accepted": True, "type": summary["type"]})

    # ---------- 文曲：可见性与共享 ----------

    @app.patch("/api/v1/docs/{doc_id}/visibility")
    def set_visibility(doc_id: str, payload: DocVisibilityRequest, actor: ActorDep) -> dict[str, Any]:
        return store.set_visibility(actor, doc_id, payload.visibility)  # type: ignore[no-any-return]

    @app.post("/api/v1/docs/{doc_id}/shares")
    def share_doc(doc_id: str, payload: DocShareRequest, actor: ActorDep) -> dict[str, Any]:
        return store.share_doc(  # type: ignore[no-any-return]
            actor, doc_id, payload.user_id, payload.permission, payload.expires_at
        )

    @app.get("/api/v1/docs/{doc_id}/field-permissions")
    def list_doc_field_permissions(doc_id: str, actor: ActorDep) -> dict[str, list[dict[str, Any]]]:
        return {"permissions": store.list_doc_field_permissions(actor, doc_id)}

    @app.put("/api/v1/docs/{doc_id}/field-permissions")
    def set_doc_field_permission(
        doc_id: str,
        payload: FieldPermissionRequest,
        actor: ActorDep,
    ) -> dict[str, Any]:
        return store.set_doc_field_permission(  # type: ignore[no-any-return]
            actor, doc_id, payload.field, payload.min_role
        )

    @app.get("/api/v1/docs/{doc_id}/shares")
    def list_doc_shares(doc_id: str, actor: ActorDep) -> dict[str, list[dict[str, Any]]]:
        return {"shares": store.list_shares(actor, doc_id)}

    @app.delete("/api/v1/docs/{doc_id}/shares/{user_id}")
    def unshare_doc(doc_id: str, user_id: str, actor: ActorDep) -> dict[str, Any]:
        return store.unshare_doc(actor, doc_id, user_id)  # type: ignore[no-any-return]

    @app.get("/api/v1/requirements/{request_id}/git-file")
    def requirement_git_file(
        request_id: str,
        actor: ActorDep,
        repo: str = Query(min_length=1),
        ref: str = Query(min_length=1),
    ) -> dict[str, str]:
        _find_requirement(store, actor, request_id)
        root = os.environ.get("TIANXUAN_REPO_ROOT", "").strip()
        if not root:
            raise HTTPException(status_code=400, detail="TIANXUAN_REPO_ROOT is not configured")
        root_path = Path(root).resolve()
        repo_path = (root_path / repo).resolve()
        if not repo_path.is_relative_to(root_path):
            raise HTTPException(status_code=400, detail="repo escapes TIANXUAN_REPO_ROOT")
        relative = f"design/{request_id}.md"
        try:
            markdown = GitService().read_file(repo_path, ref, relative)
        except (GitServiceError, OSError) as error:
            raise HTTPException(status_code=400, detail=f"read failed: {error}") from error
        return {"path": relative, "ref": ref, "markdown": markdown}

    # ---------- 多宝：本地 Git 仓库浏览 ----------

    @app.get("/api/v1/git/repos")
    def list_git_repos(actor: ActorDep) -> dict[str, list[str]]:
        root = os.environ.get("TIANXUAN_REPO_ROOT", "").strip()
        if not root:
            raise HTTPException(status_code=400, detail="TIANXUAN_REPO_ROOT is not configured")
        root_path = Path(root)
        if not root_path.is_dir():
            return {"repos": []}
        names = sorted(entry.name for entry in root_path.iterdir() if entry.is_dir() and entry.name.endswith(".git"))
        return {"repos": names}

    @app.get("/api/v1/git/repos/{name}/branches")
    def git_branches(name: str, actor: ActorDep) -> dict[str, list[str]]:
        repo = _repo_under_root(name)
        try:
            return {"branches": GitService().list_branches(repo)}
        except (GitServiceError, OSError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/v1/git/repos/{name}/selected-commits/{sha}")
    def selected_commit_receipt(name: str, sha: str, branch: str, base: str, actor: PrivateActorDep) -> dict[str, str]:
        from selected_commit import receipt

        repo = _repo_under_root(name)
        try:
            GitService().branch_tip(repo, branch)
            return cast(dict[str, str], receipt(repo, branch, base, sha))
        except (GitServiceError, ValueError, OSError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/v1/git/repos/{name}/selected-commits")
    def receive_selected_commit(
        name: str, actor: PrivateActorDep, payload: Annotated[SelectedGitCommitRequest, Depends(_selected_commit_body)]
    ) -> dict[str, str]:
        from selected_commit import receive

        repo = _repo_under_root(name)
        try:
            ensure_merge_allowed(payload.branch, _policy_patterns(app), actor_role=store.role_of(actor), path="direct")
            # Resolve a real repository root and the exact branch, as for the G10 toolbar.
            GitService().branch_tip(repo, payload.branch)
            return cast(dict[str, str], receive(repo, **payload.model_dump()))
        except PolicyError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except (GitServiceError, ValueError, OSError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/v1/git/repos/{name}/branch-tip")
    def git_branch_tip(name: str, actor: ActorDep, branch: str = Query(min_length=1)) -> dict[str, str]:
        repo = _repo_under_root(name)
        try:
            return {"branch": branch, "sha": GitService().branch_tip(repo, branch)}
        except (GitServiceError, OSError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/v1/git/repos/{name}/log")
    def git_log(
        name: str,
        actor: ActorDep,
        ref: str = Query(default="HEAD", min_length=1),
        limit: int = Query(default=20, ge=1, le=100),
    ) -> dict[str, list[dict[str, Any]]]:
        repo = _repo_under_root(name)
        try:
            return {"commits": GitService().log(repo, ref, limit)}
        except (GitServiceError, OSError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/v1/git/repos/{name}/diff")
    def git_diff(
        name: str,
        actor: ActorDep,
        a: str = Query(min_length=1),
        b: str = Query(min_length=1),
    ) -> dict[str, str]:
        repo = _repo_under_root(name)
        try:
            return {"diff": GitService().diff(repo, a, b)}
        except (GitServiceError, OSError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/v1/git/repos/{name}/tree")
    def git_tree(
        name: str,
        actor: ActorDep,
        ref: str = Query(default="HEAD", min_length=1),
        path: str = Query(default=""),
    ) -> dict[str, list[dict[str, Any]]]:
        repo = _repo_under_root(name)
        try:
            return {"entries": GitService().list_tree(repo, ref, path)}
        except (GitServiceError, OSError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/v1/git/repos/{name}/search")
    def git_search(
        name: str,
        actor: ActorDep,
        q: str = Query(min_length=1, max_length=200),
        ref: str = Query(default="HEAD", min_length=1),
        path: str = Query(default=""),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, list[dict[str, Any]]]:
        repo = _repo_under_root(name)
        try:
            return {"results": GitService().search(repo, q, ref, path, limit)}
        except (GitServiceError, OSError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/v1/git/repos/{name}/blame")
    def git_blame(
        name: str,
        actor: ActorDep,
        path: str = Query(min_length=1),
        ref: str = Query(default="HEAD", min_length=1),
        limit: int = Query(default=2000, ge=1, le=5000),
    ) -> dict[str, list[dict[str, Any]]]:
        repo = _repo_under_root(name)
        try:
            return {"lines": GitService().blame(repo, ref, path, limit)}
        except (GitServiceError, OSError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/api/v1/git/repos/{name}/branches")
    def create_git_branch(
        name: str,
        payload: GitBranchCreateRequest,
        actor: ActorDep,
    ) -> dict[str, str]:
        repo = _repo_under_root(name)
        try:
            ensure_branch_mutation_allowed(
                payload.name,
                _policy_patterns(app),
                actor_role=store.role_of(actor),
                operation="create",
            )
        except PolicyError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        try:
            sha = GitService().branch(repo, payload.name, payload.start)
        except (GitServiceError, OSError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"branch": payload.name, "sha": sha}

    @app.delete("/api/v1/git/repos/{name}/branches/{branch:path}")
    def delete_git_branch(name: str, branch: str, actor: ActorDep) -> dict[str, Any]:
        repo = _repo_under_root(name)
        try:
            ensure_branch_mutation_allowed(
                branch,
                _policy_patterns(app),
                actor_role=store.role_of(actor),
                operation="delete",
            )
        except PolicyError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        try:
            GitService().delete_branch(repo, branch)
        except (GitServiceError, OSError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"branch": branch, "deleted": True}

    @app.get("/api/v1/git/repos/{name}/tags")
    def git_tags(name: str, actor: ActorDep) -> dict[str, list[dict[str, str]]]:
        repo = _repo_under_root(name)
        try:
            return {"tags": GitService().list_tags(repo)}
        except (GitServiceError, OSError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/api/v1/git/repos/{name}/tags")
    def create_git_tag(
        name: str,
        payload: GitTagCreateRequest,
        actor: ActorDep,
    ) -> dict[str, str]:
        _require_editor_role(store, actor, "create tags")
        repo = _repo_under_root(name)
        try:
            tag = GitService().create_tag(repo, payload.name, payload.ref, payload.message)
        except (GitServiceError, OSError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"tag": tag}

    @app.delete("/api/v1/git/repos/{name}/tags/{tag:path}")
    def delete_git_tag(name: str, tag: str, actor: ActorDep) -> dict[str, Any]:
        _require_editor_role(store, actor, "delete tags")
        repo = _repo_under_root(name)
        try:
            GitService().delete_tag(repo, tag)
        except (GitServiceError, OSError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"tag": tag, "deleted": True}

    @app.post("/api/v1/git/import")
    def import_git_repo(payload: GitImportRequest, actor: ActorDep) -> dict[str, Any]:
        if store.role_of(actor) != "admin":
            raise PermissionDenied("only an admin can import repositories")
        root = _repo_root()
        allow_local = os.environ.get("TIANXUAN_IMPORT_ALLOW_LOCAL", "0").strip() == "1"
        allowed_hosts = tuple(
            item.strip() for item in os.environ.get("TIANXUAN_IMPORT_ALLOWED_HOSTS", "").split(",") if item.strip()
        )
        fetch_lfs = os.environ.get("TIANXUAN_IMPORT_FETCH_LFS", "0").strip() == "1"
        try:
            return GitService().import_repo(  # type: ignore[no-any-return]
                root,
                payload.name,
                payload.source,
                allow_local=allow_local,
                allowed_hosts=allowed_hosts,
                fetch_lfs=fetch_lfs,
            )
        except (GitServiceError, OSError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/api/v1/git/import-jobs")
    def start_import_job(payload: GitImportRequest, actor: ActorDep) -> dict[str, Any]:
        if store.role_of(actor) != "admin":
            raise PermissionDenied("only an admin can import repositories")
        root = _repo_root()
        allow_local = os.environ.get("TIANXUAN_IMPORT_ALLOW_LOCAL", "0").strip() == "1"
        allowed_hosts = tuple(
            item.strip() for item in os.environ.get("TIANXUAN_IMPORT_ALLOWED_HOSTS", "").split(",") if item.strip()
        )
        fetch_lfs = os.environ.get("TIANXUAN_IMPORT_FETCH_LFS", "0").strip() == "1"
        job = store.create_import_job(actor, payload.name, payload.source)
        arguments = (store, job["id"], root, payload.name, payload.source, allow_local, allowed_hosts, fetch_lfs)
        if os.environ.get("TIANXUAN_IMPORT_JOBS_INLINE", "0").strip() == "1":
            _run_import_job(*arguments)
        else:
            threading.Thread(target=_run_import_job, args=arguments, daemon=True).start()
        return store.get_import_job(actor, job["id"])  # type: ignore[no-any-return]

    @app.get("/api/v1/git/import-jobs")
    def list_import_jobs(
        actor: ActorDep,
        limit: int = Query(default=20, ge=1, le=100),
    ) -> dict[str, list[dict[str, Any]]]:
        return {"jobs": store.list_import_jobs(actor, limit)}

    @app.get("/api/v1/git/import-jobs/{job_id}")
    def get_import_job(job_id: str, actor: ActorDep) -> dict[str, Any]:
        return store.get_import_job(actor, job_id)  # type: ignore[no-any-return]

    @app.get("/api/v1/git/repos/{name}/file")
    def repo_file(name: str, actor: ActorDep, path: str, branch: str = "main") -> dict[str, Any]:
        store.role_of(actor)
        service = GitService()
        repo = _repo_under_root(name)
        head = service.log(repo, branch, 1)[0]["sha"]
        parent = str(Path(path).parent).replace("\\", "/")
        entries = service.list_tree(repo, head, "" if parent == "." else parent)
        entry = next((item for item in entries if item["path"] == path), None)
        if entry is None:
            raise HTTPException(404, "tracked file not found")
        if entry["mode"] not in {"100644", "100755"} or entry["size"] is None or entry["size"] > 1_000_000:
            raise HTTPException(413, "only regular text files up to 1 MB can be edited")
        content = service.read_file(repo, head, path)
        if "\0" in content or "\ufffd" in content:
            raise HTTPException(415, "binary files cannot be edited as text")
        return {**entry, "content": content, "branch": branch}

    @app.post("/api/v1/git/repos/{name}/file")
    def write_repo_file(name: str, payload: RepoFileWriteRequest, actor: ActorDep) -> dict[str, Any]:
        if store.role_of(actor) == "viewer":
            raise PermissionDenied("viewer cannot edit repository files")
        current = repo_file(name, actor, payload.path, payload.branch)
        if current["sha"] != payload.expected_blob:
            raise HTTPException(409, "file changed; reload before editing")
        # Each edit goes to a fresh branch. It cannot overwrite another user's
        # branch or the deployment baseline, even if the source advances.
        import uuid

        service = GitService()
        repo = _repo_under_root(name)
        head = service.log(repo, payload.branch, 1)[0]["sha"]
        # Re-read at the selected immutable commit before creating the branch.
        if service.read_file(repo, head, payload.path) != current["content"]:
            raise HTTPException(409, "branch advanced; reload before editing")
        target = f"web/{actor}/{uuid.uuid4().hex[:12]}"
        try:
            ensure_branch_mutation_allowed(
                target, _policy_patterns(app), actor_role=store.role_of(actor), operation="create"
            )
        except PolicyError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        service.branch(repo, target, head)
        member = next(user for user in store.list_members(actor) if user["id"] == actor)
        sha = service.commit(
            repo, target, payload.message, {payload.path: payload.content}, member["name"] or actor, member["email"]
        )
        return {"commit": sha, "branch": target, "path": payload.path}

    # ---------- 多宝：合入队列 ----------

    if merge_queue is not None:

        def exact_request_view(item: dict[str, Any]) -> dict[str, Any]:
            evidence = item["evidence"]
            return {
                "id": item["id"],
                "source": item["source"],
                "target": item["target"],
                **evidence["exact_request"],
                "check_state": item["check_state"],
                "checks": [
                    {"command": check["command"], "exit_code": check["exit_code"]}
                    for check in evidence.get("checks", [])
                ],
            }

        @app.post("/api/v1/git/repos/{name}/merge-requests")
        def create_exact_request(name: str, payload: ExactMergeRequest, actor: PrivateActorDep) -> dict[str, Any]:
            if store.role_of(actor) == "viewer":
                raise PermissionDenied("viewer cannot enqueue merge candidates")
            repo = _repo_under_root(name)
            try:
                item = merge_queue.enqueue(
                    actor, str(repo), payload.source, payload.target, candidate=payload.candidate
                )
            except PolicyError as error:
                raise HTTPException(status_code=403, detail=str(error)) from error
            except (GitServiceError, ValueError, OSError) as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            return exact_request_view(item)

        @app.get("/api/v1/git/repos/{name}/merge-requests/{item_id}")
        def read_exact_request(name: str, item_id: str, actor: PrivateActorDep) -> dict[str, Any]:
            repo = _repo_under_root(name)
            try:
                item = merge_queue.get(item_id)
            except KeyError as error:
                raise HTTPException(status_code=404, detail="merge request not found") from error
            if (
                item["repo"] != str(repo)
                or "exact_request" not in item["evidence"]
                or store.actor_context(item["created_by"])["tenant"] != store.actor_context(actor)["tenant"]
            ):
                raise HTTPException(status_code=404, detail="merge request not found")
            return exact_request_view(item)

        @app.post("/api/v1/merge-queue")
        def enqueue_merge(payload: MergeQueueCreateRequest, actor: ActorDep) -> dict[str, Any]:
            if store.role_of(actor) == "viewer":
                raise PermissionDenied("viewer cannot enqueue merge candidates")
            repo = _repo_under_root(payload.repo)
            try:
                return merge_queue.enqueue(  # type: ignore[no-any-return]
                    actor,
                    str(repo),
                    payload.source,
                    payload.target,
                    payload.title,
                    payload.priority,
                    pr_number=payload.pr_number,
                    issue_ref=payload.issue_ref,
                )
            except PolicyError as error:
                raise HTTPException(status_code=403, detail=str(error)) from error
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error

        def _require_queue_item_owner(item_id: str, actor: str, action: str) -> None:
            try:
                item = merge_queue.get(item_id)
            except KeyError as error:
                raise HTTPException(status_code=404, detail="merge queue item not found") from error
            if store.role_of(actor) != "admin" and item.get("created_by") != actor:
                raise PermissionDenied(f"only the creator or an admin can {action} merge candidates")

        @app.get("/api/v1/merge-queue")
        def list_merge_queue(
            actor: ActorDep,
            status: str | None = Query(default=None),
            limit: int = Query(default=50, ge=1, le=200),
            offset: int = Query(default=0, ge=0),
        ) -> dict[str, Any]:
            try:
                return {
                    "items": merge_queue.list_items(status, limit, offset),
                    "total": merge_queue.count_items(status),
                }
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error

        @app.post("/api/v1/merge-queue/process")
        def process_merge_queue(
            actor: ActorDep,
            limit: int = Query(default=1, ge=1, le=20),
        ) -> dict[str, list[dict[str, Any]]]:
            if store.role_of(actor) == "viewer":
                raise PermissionDenied("viewer cannot process merge queue")
            return {"processed": merge_queue.process_batch(limit)}

        @app.get("/api/v1/merge-queue/workers")
        def merge_queue_workers(actor: ActorDep) -> dict[str, list[dict[str, Any]]]:
            return {"workers": merge_queue.list_workers()}

        @app.get("/api/v1/merge-queue/status")
        def merge_queue_status(actor: ActorDep) -> dict[str, Any]:
            return {
                "worker": merge_queue.worker_running,
                "queued": merge_queue.count_items("queued"),
                "total": merge_queue.count_items(),
            }

        @app.get("/api/v1/merge-queue/{item_id}")
        def get_merge_queue_item(item_id: str, actor: ActorDep) -> dict[str, Any]:
            try:
                return merge_queue.get(item_id)  # type: ignore[no-any-return]
            except KeyError as error:
                raise HTTPException(status_code=404, detail="merge queue item not found") from error

        @app.post("/api/v1/merge-queue/{item_id}/retry")
        def retry_merge(item_id: str, actor: ActorDep) -> dict[str, Any]:
            _require_queue_item_owner(item_id, actor, "retry")
            try:
                return merge_queue.retry(item_id)  # type: ignore[no-any-return]
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error

        @app.post("/api/v1/merge-queue/{item_id}/cancel")
        def cancel_merge_queue_item(item_id: str, actor: ActorDep) -> dict[str, Any]:
            _require_queue_item_owner(item_id, actor, "cancel")
            try:
                return merge_queue.cancel(item_id)  # type: ignore[no-any-return]
            except KeyError as error:
                raise HTTPException(status_code=404, detail="merge queue item not found") from error
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error

    # ---------- 文曲：评论 ----------

    @app.post("/api/v1/docs/{doc_id}/comments")
    def create_comment(doc_id: str, payload: CommentCreateRequest, actor: ActorDep) -> dict[str, Any]:
        return store.add_comment(actor, doc_id, payload.body, payload.parent_id)  # type: ignore[no-any-return]

    @app.get("/api/v1/docs/{doc_id}/comments")
    def list_comments(doc_id: str, actor: ActorDep) -> dict[str, list[dict[str, Any]]]:
        return {"comments": store.list_comments(actor, doc_id)}

    @app.patch("/api/v1/comments/{comment_id}")
    def resolve_comment(comment_id: str, payload: CommentResolveRequest, actor: ActorDep) -> dict[str, Any]:
        return store.resolve_comment(actor, comment_id, payload.resolved)  # type: ignore[no-any-return]

    # ---------- 文曲：实时协同 ----------

    @app.websocket("/api/v1/ws/merge-queue")
    async def merge_queue_room(websocket: WebSocket) -> None:
        actor = getattr(websocket.state, "verified_actor", None) or _websocket_actor(
            store, websocket.query_params, allow_header=not native_only
        )
        if actor is None:
            await websocket.close(code=4401)
            return
        if merge_queue is None:
            await websocket.close(code=4404)
            return
        try:
            store.role_of(actor)
        except NotFound:
            await websocket.close(code=4401)
            return
        await websocket.accept()
        signature = ""
        try:
            while True:
                items = merge_queue.list_items(limit=100)
                current = json.dumps(items, ensure_ascii=False, sort_keys=True, default=str)
                if current != signature:
                    await websocket.send_json({"type": "snapshot", "items": items})
                    signature = current
                await asyncio.sleep(1.0)
        except (WebSocketDisconnect, RuntimeError):
            return

    @app.websocket("/api/v1/ws/docs/{doc_id}")
    async def doc_room(websocket: WebSocket, doc_id: str) -> None:
        actor = getattr(websocket.state, "verified_actor", None) or _websocket_actor(
            store, websocket.query_params, allow_header=not native_only
        )
        if actor is None:
            await websocket.close(code=4401)
            return
        try:
            document = store.get_doc_shared(actor, doc_id)
        except NotFound:
            await websocket.close(code=4404)
            return
        except PermissionDenied:
            await websocket.close(code=4403)
            return
        await websocket.accept()
        rooms.join(doc_id, websocket, actor)
        try:
            await websocket.send_json({"type": "snapshot", "doc": document})
            await rooms.broadcast(doc_id, {"type": "presence", "actors": rooms.actors(doc_id)})
            while True:
                message = await websocket.receive_json()
                try:
                    store.get_doc_shared(actor, doc_id)
                except (NotFound, PermissionDenied):
                    await websocket.close(code=4403)
                    break
                kind = message.get("type")
                if kind == "ping":
                    await websocket.send_json({"type": "pong"})
                elif kind == "update":
                    try:
                        updated = store.update_doc(
                            actor,
                            doc_id,
                            str(message.get("body_md", "")),
                            int(message.get("expected_version", 0)),
                        )
                    except (NotFound, VersionConflict, TianxuanError) as error:
                        await websocket.send_json({
                            "type": "error",
                            "code": type(error).__name__,
                            "message": str(error),
                        })
                        continue
                    await rooms.broadcast(doc_id, {"type": "updated", "doc": updated, "actor": actor})
                else:
                    await websocket.send_json({
                        "type": "error",
                        "code": "unknown_message",
                        "message": f"unsupported type: {kind}",
                    })
        except WebSocketDisconnect:
            pass
        finally:
            rooms.leave(doc_id, websocket)
            if rooms.actors(doc_id):
                await rooms.broadcast(doc_id, {"type": "presence", "actors": rooms.actors(doc_id)})

    if native_only:
        excluded = (
            "/api/v1/git/",
            "/api/v1/gitea/",
            "/api/v1/repos",
            "/api/v1/repo-links",
            "/api/v1/webhooks/",
            "/api/v1/merge-queue",
            "/api/v1/ws/merge-queue",
        )
        app.router.routes[:] = [
            route
            for route in app.router.routes
            if not getattr(route, "path", "").startswith(excluded)
            and getattr(route, "path", "")
            not in {"/api/v1/requirements/{request_id}/commit", "/api/v1/requirements/{request_id}/git-file"}
        ]

    @app.post("/api/v1/tools")
    def call_tool(payload: ToolCallRequest, actor: ActorDep) -> dict[str, Any]:
        document_tools = {"doc.read", "doc.list", "doc.search", "doc.create", "doc.update", "doc.patch", "doc.restore"}
        from issue_flow import TOOLS as FLOW_TOOLS

        available_tools = (
            document_tools
            | FLOW_TOOLS
            | {
                "requirement.create",
                "requirement.plan",
                "issue.create",
                "issue.transition",
                "issue.list",
            }
        )
        migration_tools = {"migration.entry", "migration.status", "migration.start"}
        if payload.name not in available_tools | migration_tools | HISTORY_TOOLS:
            raise HTTPException(status_code=400, detail="unknown tool")
        public_workspace = os.environ.get("TIANXUAN_AUTH_MODE") == "accounts" and store.actor_context(actor)[
            "tenant"
        ] != os.environ.get("TIANXUAN_TENANT_ID")
        if public_workspace and payload.name not in document_tools:
            raise HTTPException(status_code=403, detail="this workspace is limited to document tools")
        try:
            if payload.name in HISTORY_TOOLS:
                return cast(dict[str, Any], history_tool(actor, payload.name, payload.payload, payload.call_id))
            if payload.name in migration_tools:
                return cast(dict[str, Any], migration_tool(actor, payload.name, payload.payload, payload.call_id))
            result = cast(
                dict[str, Any], store.dispatch_tool(actor, payload.name, payload.payload, call_id=payload.call_id)
            )
            if payload.name in {"doc.update", "doc.patch", "doc.restore"}:
                return notify_document_change(result)
            return result
        except (TypeError, KeyError) as error:
            raise HTTPException(status_code=422, detail="invalid tool arguments") from error

    @app.get("/api/v1/capabilities")
    def capabilities() -> dict[str, Any]:
        installation = native_entry.installation.verify() if native_entry is not None else None
        return {
            "mode": "native" if native_only else "git",
            "documents": True,
            "requirements": True,
            "issues": True,
            "models": gateway is not None,
            "native_candidates": native_store is not None,
            "native_execution": {
                "enabled": installation is not None,
                "mode": installation["mode"] if installation else "unconfigured",
                "execution_nodes": native_entry.execution_nodes if native_entry else None,
                "entry_api": "/api/v1/native/entry" if native_entry else None,
                "context_tools": bool(native_entry and native_entry.runtime_installation is not None),
            },
            "git": not native_only,
        }

    return app
