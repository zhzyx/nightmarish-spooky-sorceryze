"""天璇 FastAPI 传输适配器。

本层只做 HTTP 映射：提取 actor 头、校验请求体、把领域异常翻译为状态码。
租户、版本、状态机等语义全部由 tianxuan_core.Tianxuan 负责，适配器不复制规则。

actor 约定：需要身份的端点从请求头 ``X-Actor`` 读取用户 ID（当前切片的临时身份，
真正的认证与授权在后续切片接入）。列表端点统一返回 ``{"<name>": [...]}`` 包装，
与领域层 AI 工具面的返回结构保持一致。
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from gateway import ModelGateway, create_model_router
from schemas import (
    CommentCreateRequest,
    CommentResolveRequest,
    DocCreateRequest,
    DocUpdateRequest,
    IssueTransitionRequest,
    LoginRequest,
    RegisterRequest,
    RequirementCreateRequest,
    TicketsRequest,
)
from tianxuan_core import NotFound, Tianxuan, TianxuanError, TransitionRejected, VersionConflict
from wenqu_bridge import classify as classify_markdown
from wenqu_bridge import export_markdown
from wenqu_bridge import search as search_documents


def _require_actor(x_actor: str | None = Header(default=None, alias="X-Actor")) -> str:
    """读取并规范化当前 actor；缺失时按客户端错误处理。"""
    actor = (x_actor or "").strip()
    if not actor:
        raise HTTPException(status_code=400, detail="X-Actor header is required")
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


def create_app(store: Tianxuan, gateway: ModelGateway | None = None) -> FastAPI:
    """为给定领域核心实例构建 HTTP 应用；可选的模型网关挂载到同一应用。"""
    app = FastAPI(title="Tianxuan API", version="0.1.0")
    app.state.store = store
    app.state.gateway = gateway
    rooms = DocRooms()
    if gateway is not None:
        app.include_router(create_model_router(gateway))

    # ---------- 领域异常 -> HTTP 状态码 ----------
    # Starlette 按异常的 MRO 查找处理器，VersionConflict/TransitionRejected
    # 是 TianxuanError 的子类，注册更具体的类型即可得到 409 而不是 400。

    @app.exception_handler(NotFound)
    def _not_found(_request: Request, exc: NotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(VersionConflict)
    def _version_conflict(_request: Request, exc: VersionConflict) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(TransitionRejected)
    def _transition_rejected(_request: Request, exc: TransitionRejected) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

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
        )

    @app.get("/api/v1/docs/{doc_id}")
    def get_doc(doc_id: str) -> dict[str, Any]:
        return store.get_doc(doc_id)  # type: ignore[no-any-return]

    @app.patch("/api/v1/docs/{doc_id}")
    def update_doc(doc_id: str, payload: DocUpdateRequest, actor: ActorDep) -> dict[str, Any]:
        return store.update_doc(  # type: ignore[no-any-return]
            actor,
            doc_id,
            payload.body_md,
            payload.expected_version,
            title=payload.title,
            status=payload.status,
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
        )

    @app.post("/api/v1/requirements/{doc_id}/tickets")
    def plan_tickets(doc_id: str, payload: TicketsRequest, actor: ActorDep) -> dict[str, list[dict[str, Any]]]:
        tickets = [ticket.model_dump() for ticket in payload.tickets]
        return {"issues": store.plan_tickets(actor, doc_id, tickets)}

    # ---------- 司南：工单 ----------

    @app.get("/api/v1/issues")
    def list_issues(
        actor: ActorDep, requirement_id: str | None = Query(default=None)
    ) -> dict[str, list[dict[str, Any]]]:
        return {"issues": store.list_issues(actor, requirement_id)}

    @app.patch("/api/v1/issues/{issue_id}")
    def transition_issue(issue_id: str, payload: IssueTransitionRequest, actor: ActorDep) -> dict[str, Any]:
        return store.transition_issue(actor, issue_id, payload.to_status)  # type: ignore[no-any-return]

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
        return {"results": search_documents(documents, q)[:limit]}

    @app.get("/api/v1/docs/{doc_id}/export")
    def export_doc(doc_id: str) -> dict[str, str]:
        document = store.get_doc(doc_id)
        return {"filename": f"{doc_id}.md", "markdown": export_markdown(document)}

    @app.get("/api/v1/docs/{doc_id}/ai-view")
    def ai_view(doc_id: str) -> dict[str, Any]:
        return store.ai_view(doc_id)  # type: ignore[no-any-return]

    @app.post("/api/v1/docs/{doc_id}/classify")
    def classify_doc(doc_id: str) -> dict[str, list[str]]:
        return {"tags": classify_markdown(store.get_doc(doc_id)["body_md"])}

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
            document = store.get_doc(doc_id)
        except NotFound:
            await websocket.close(code=4404)
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
