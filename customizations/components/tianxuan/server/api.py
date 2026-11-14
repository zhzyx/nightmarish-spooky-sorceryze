"""天璇 FastAPI 传输适配器。

本层只做 HTTP 映射：提取 actor 头、校验请求体、把领域异常翻译为状态码。
租户、版本、状态机等语义全部由 tianxuan_core.Tianxuan 负责，适配器不复制规则。

actor 约定：需要身份的端点从请求头 ``X-Actor`` 读取用户 ID（当前切片的临时身份，
真正的认证与授权在后续切片接入）。列表端点统一返回 ``{"<name>": [...]}`` 包装，
与领域层 AI 工具面的返回结构保持一致。
"""

from __future__ import annotations

import difflib
import os
from pathlib import Path
from typing import Annotated, Any

from duobao_bridge import GitService, GitServiceError
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from gateway import ModelGateway, create_model_router
from gitea_bridge import GiteaClient, GiteaError
from schemas import (
    CommentCreateRequest,
    CommentResolveRequest,
    DocCreateRequest,
    DocMergeRequest,
    DocPatchRequest,
    DocShareRequest,
    DocUpdateRequest,
    DocVisibilityRequest,
    InviteAcceptRequest,
    InviteCreateRequest,
    IssueCommentCreateRequest,
    IssueTransitionRequest,
    LoginRequest,
    MemberCreateRequest,
    MergeQueueCreateRequest,
    PullRequestCreateRequest,
    PullRequestMergeRequest,
    RegisterRequest,
    RepoCreateRequest,
    RequirementCommitRequest,
    RequirementCreateRequest,
    RoleUpdateRequest,
    TicketsRequest,
)
from tianxuan_core import (
    NotFound,
    PermissionDenied,
    StorageBusy,
    StorageError,
    Tianxuan,
    TianxuanError,
    TransitionRejected,
    VersionConflict,
)
from wenqu_bridge import build_ai_index, export_markdown, merge_offline
from wenqu_bridge import classify as classify_markdown
from wenqu_bridge import search as search_documents


def _require_actor(
    request: Request,
    x_actor: str | None = Header(default=None, alias="X-Actor"),
    authorization: str | None = Header(default=None),
) -> str:
    """读取 actor：优先 Bearer 会话 token，兼容临时 X-Actor。"""
    actor = (x_actor or "").strip()
    if not actor and authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token.strip():
            actor = request.app.state.store.user_for_token(token.strip()) or ""
    if not actor:
        raise HTTPException(status_code=400, detail="X-Actor header or Bearer token is required")
    return actor


ActorDep = Annotated[str, Depends(_require_actor)]


class DocRooms:
    """单进程文档房间：连接、成员与广播；跨进程 fan-out 由部署层负责。"""

    def __init__(self) -> None:
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
            try:
                await peer.send_json(payload)
            except (RuntimeError, WebSocketDisconnect):
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


def _gitea_client() -> GiteaClient:
    base_url = os.environ.get("TIANXUAN_GITEA_URL", "").strip()
    token = os.environ.get("TIANXUAN_GITEA_TOKEN", "").strip()
    if not base_url or not token:
        raise HTTPException(
            status_code=400,
            detail="TIANXUAN_GITEA_URL and TIANXUAN_GITEA_TOKEN are required",
        )
    return GiteaClient(base_url, token)


def _repo_under_root(name: str) -> Path:
    root = os.environ.get("TIANXUAN_REPO_ROOT", "").strip()
    if not root:
        raise HTTPException(status_code=400, detail="TIANXUAN_REPO_ROOT is not configured")
    root_path = Path(root).resolve()
    candidate = (root_path / name).resolve()
    if not candidate.is_relative_to(root_path):
        raise HTTPException(status_code=400, detail="repo escapes TIANXUAN_REPO_ROOT")
    return candidate


def create_app(store: Tianxuan, gateway: ModelGateway | None = None, merge_queue: Any | None = None) -> FastAPI:
    """为给定领域核心实例构建 HTTP 应用；可选的模型网关与多宝合入队列挂载到同一应用。"""
    app = FastAPI(title="Tianxuan API", version="0.1.0")
    app.state.store = store
    app.state.gateway = gateway
    app.state.merge_queue = merge_queue
    rooms = DocRooms()
    if gateway is not None:
        app.include_router(create_model_router(gateway))

    # ---------- 领域异常 -> HTTP 状态码 ----------
    # Starlette 按异常的 MRO 查找处理器，VersionConflict/TransitionRejected
    # 是 TianxuanError 的子类，注册更具体的类型即可得到 409 而不是 400。

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

    # ---------- 身份 ----------

    @app.post("/api/v1/auth/register")
    def register(payload: RegisterRequest) -> dict[str, str]:
        return store.register(payload.tenant_name, payload.email, payload.password, payload.name or "")  # type: ignore[no-any-return]

    @app.post("/api/v1/auth/login")
    def login(payload: LoginRequest) -> dict[str, str]:
        account = store.authenticate(payload.email, payload.password)
        if account is None:
            raise HTTPException(status_code=401, detail="invalid email or password")
        return account  # type: ignore[no-any-return]

    @app.post("/api/v1/auth/session")
    def create_session(payload: LoginRequest) -> dict[str, str]:
        account = store.authenticate(payload.email, payload.password)
        if account is None:
            raise HTTPException(status_code=401, detail="invalid email or password")
        token = store.issue_session(account["user_id"])
        return {**account, "token": token}  # type: ignore[no-any-return]

    @app.post("/api/v1/auth/logout")
    def logout(authorization: str | None = Header(default=None)) -> dict[str, bool]:
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise HTTPException(status_code=400, detail="Bearer token is required")
        return {"revoked": store.revoke_session(token.strip())}

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

    @app.patch("/api/v1/docs/{doc_id}")
    def update_doc(doc_id: str, payload: DocUpdateRequest, actor: ActorDep) -> dict[str, Any]:
        return store.update_doc(  # type: ignore[no-any-return]
            actor,
            doc_id,
            payload.body_md,
            payload.expected_version,
            title=payload.title,
            status=payload.status,
            call_id=payload.call_id,
        )

    # ---------- 偃师：需求与工单 ----------

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

    @app.get("/api/v1/issues")
    def list_issues(
        actor: ActorDep,
        status: str | None = Query(default=None),
        requirement_id: str | None = Query(default=None),
    ) -> dict[str, list[dict[str, Any]]]:
        issues = store.list_issues(actor, requirement_id)
        if status is not None:
            issues = [issue for issue in issues if issue["status"] == status]
        return {"issues": issues}

    @app.patch("/api/v1/issues/{issue_id}")
    def transition_issue(issue_id: str, payload: IssueTransitionRequest, actor: ActorDep) -> dict[str, Any]:
        return store.transition_issue(actor, issue_id, payload.to_status, call_id=payload.call_id)  # type: ignore[no-any-return]

    @app.post("/api/v1/issues/{issue_id}/comments")
    def create_issue_comment(issue_id: str, payload: IssueCommentCreateRequest, actor: ActorDep) -> dict[str, Any]:
        return store.add_issue_comment(actor, issue_id, payload.body)  # type: ignore[no-any-return]

    @app.get("/api/v1/issues/{issue_id}/comments")
    def list_issue_comments(issue_id: str, actor: ActorDep) -> dict[str, list[dict[str, Any]]]:
        return {"comments": store.list_issue_comments(actor, issue_id)}

    # ---------- 事件流 ----------

    @app.get("/api/v1/events")
    def list_events(actor: ActorDep, limit: int = Query(default=100, ge=1, le=500)) -> dict[str, list[dict[str, Any]]]:
        return {"events": store.events(actor, limit)}

    # ---------- 文曲：检索、导出、AI 视图、归类 ----------

    @app.get("/api/v1/search")
    def search_docs(
        actor: ActorDep,
        q: str = Query(min_length=1),
        limit: int = Query(default=20, ge=1, le=100),
    ) -> dict[str, list[dict[str, Any]]]:
        documents = [store.get_doc(row["id"]) for row in store.list_docs(actor)]
        by_id = {document["id"]: document for document in documents}
        results = []
        for item in search_documents(documents, q)[:limit]:
            document = by_id.get(item["id"], {})
            results.append({**item, "title": document.get("title", ""), "kind": document.get("kind", "doc")})
        return {"results": results}

    @app.get("/api/v1/docs/{doc_id}/export")
    def export_doc(doc_id: str, actor: ActorDep) -> dict[str, str]:
        document = store.get_doc_shared(actor, doc_id)
        return {"filename": f"{doc_id}.md", "markdown": export_markdown(document)}

    @app.get("/api/v1/docs/{doc_id}/ai-view")
    def ai_view(doc_id: str, actor: ActorDep) -> dict[str, Any]:
        store.get_doc_shared(actor, doc_id)
        return store.ai_view(doc_id)  # type: ignore[no-any-return]

    @app.post("/api/v1/docs/{doc_id}/classify")
    def classify_doc(doc_id: str, actor: ActorDep) -> dict[str, list[str]]:
        document = store.get_doc_shared(actor, doc_id)
        return {"tags": classify_markdown(document["body_md"])}

    # ---------- 文曲：离线草稿合并 ----------

    @app.post("/api/v1/docs/{doc_id}/merge")
    def merge_doc(doc_id: str, payload: DocMergeRequest, actor: ActorDep) -> Any:
        document = store.get_doc_shared(actor, doc_id, write=True)
        if document["version"] == payload.expected_version:
            updated = store.update_doc(actor, doc_id, payload.local_md, payload.expected_version)
            return {"status": "applied", "doc": updated}
        merged_md, conflicts = merge_offline(payload.base_md, payload.local_md, document["body_md"])
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
        return {"status": "merged", "doc": updated, "remote_version": document["version"]}

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

    @app.post("/api/v1/docs/{doc_id}/patch")
    def patch_doc(doc_id: str, payload: DocPatchRequest, actor: ActorDep) -> dict[str, Any]:
        document = store.get_doc_shared(actor, doc_id, write=True)
        if document["version"] != payload.expected_version:
            raise VersionConflict(
                f"version mismatch: expected {payload.expected_version}, current {document['version']}"
            )
        body = document["body_md"]
        for operation in payload.patches:
            if not operation.find:
                raise TianxuanError("patch find must not be empty")
            occurrences = body.count(operation.find)
            if occurrences == 0:
                raise TianxuanError(f"patch target not found: {operation.find!r}")
            if occurrences > 1:
                raise TianxuanError(f"patch target is ambiguous ({occurrences} matches): {operation.find!r}")
            body = body.replace(operation.find, operation.replace, 1)
        return store.update_doc(actor, doc_id, body, payload.expected_version)  # type: ignore[no-any-return]

    # ---------- 文曲：版本历史与差异 ----------

    @app.get("/api/v1/docs/{doc_id}/versions")
    def list_versions(doc_id: str, actor: ActorDep) -> dict[str, list[dict[str, Any]]]:
        store.get_doc_shared(actor, doc_id)
        return {"versions": store.versions(doc_id)}

    @app.get("/api/v1/docs/{doc_id}/versions/{version}")
    def get_version(doc_id: str, version: int, actor: ActorDep) -> dict[str, Any]:
        store.get_doc_shared(actor, doc_id)
        return store.version(doc_id, version)  # type: ignore[no-any-return]

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
        client = _gitea_client()
        try:
            with client:
                return {"repos": client.list_repos(owner, limit)}
        except GiteaError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/api/v1/repos")
    def create_repo(payload: RepoCreateRequest, actor: ActorDep) -> dict[str, Any]:
        client = _gitea_client()
        try:
            with client:
                return client.create_repo(  # type: ignore[no-any-return]
                    payload.name, payload.private, payload.default_branch
                )
        except GiteaError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/v1/repos/{owner}/{name}")
    def get_repo(owner: str, name: str, actor: ActorDep) -> dict[str, Any]:
        client = _gitea_client()
        try:
            with client:
                return client.get_repo(owner, name)  # type: ignore[no-any-return]
        except GiteaError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/v1/repos/{owner}/{name}/branches")
    def list_repo_branches(owner: str, name: str, actor: ActorDep) -> dict[str, list[dict[str, Any]]]:
        client = _gitea_client()
        try:
            with client:
                return {"branches": client.list_branches(owner, name)}
        except GiteaError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/v1/repos/{owner}/{name}/pulls")
    def list_repo_pulls(
        owner: str,
        name: str,
        actor: ActorDep,
        state: str = Query(default="open"),
    ) -> dict[str, list[dict[str, Any]]]:
        client = _gitea_client()
        try:
            with client:
                return {"pulls": client.list_pull_requests(owner, name, state)}
        except GiteaError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/api/v1/repos/{owner}/{name}/pulls")
    def create_repo_pull(
        owner: str,
        name: str,
        payload: PullRequestCreateRequest,
        actor: ActorDep,
    ) -> dict[str, Any]:
        client = _gitea_client()
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
        client = _gitea_client()
        try:
            with client:
                return client.merge_pull_request(  # type: ignore[no-any-return]
                    owner, name, number, payload.method
                )
        except GiteaError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    # ---------- 文曲：可见性与共享 ----------

    @app.patch("/api/v1/docs/{doc_id}/visibility")
    def set_visibility(doc_id: str, payload: DocVisibilityRequest, actor: ActorDep) -> dict[str, Any]:
        return store.set_visibility(actor, doc_id, payload.visibility)  # type: ignore[no-any-return]

    @app.post("/api/v1/docs/{doc_id}/shares")
    def share_doc(doc_id: str, payload: DocShareRequest, actor: ActorDep) -> dict[str, Any]:
        return store.share_doc(actor, doc_id, payload.user_id, payload.permission)  # type: ignore[no-any-return]

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

    # ---------- 多宝：合入队列 ----------

    if merge_queue is not None:

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
                )
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error

        @app.get("/api/v1/merge-queue")
        def list_merge_queue(
            actor: ActorDep,
            status: str | None = Query(default=None),
            limit: int = Query(default=50, ge=1, le=200),
        ) -> dict[str, list[dict[str, Any]]]:
            try:
                return {"items": merge_queue.list_items(status, limit)}
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

        @app.get("/api/v1/merge-queue/{item_id}")
        def get_merge_queue_item(item_id: str, actor: ActorDep) -> dict[str, Any]:
            try:
                return merge_queue.get(item_id)  # type: ignore[no-any-return]
            except KeyError as error:
                raise HTTPException(status_code=404, detail="merge queue item not found") from error

        @app.post("/api/v1/merge-queue/{item_id}/cancel")
        def cancel_merge_queue_item(item_id: str, actor: ActorDep) -> dict[str, Any]:
            if store.role_of(actor) == "viewer":
                raise PermissionDenied("viewer cannot cancel merge candidates")
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

    @app.websocket("/api/v1/ws/docs/{doc_id}")
    async def doc_room(websocket: WebSocket, doc_id: str) -> None:
        actor = websocket.query_params.get("actor", "").strip()
        if not actor:
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

    return app
