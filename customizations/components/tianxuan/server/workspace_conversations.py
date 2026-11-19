"""Private workspace conversations and revision-bound requirement intake."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from access_control import COOKIE, SESSION_COOKIE
from fastapi import APIRouter, HTTPException, Request
from gateway import ModelGateway, workspace_actor, workspace_reply
from native_store import NativeStoreError
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from starlette.concurrency import run_in_threadpool
from tianxuan_core import Tianxuan, _storage_error

Stage = Literal["direction", "plan", "design"]
STAGES = ("direction", "plan", "design")
STAGE_INSTRUCTIONS = {
    "direction": "Summarize the goal, alternatives, tradeoffs, and unresolved direction decisions.",
    "plan": "Describe the user flow, planning scope, dependencies, and observable outcomes.",
    "design": "Describe implementation scope, constraints, behavior, and a testable design.",
}
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Create(Payload):
    id: UUID


class Version(Payload):
    expected_version: int = Field(ge=0)


class Turn(Version):
    id: UUID
    content: Text


class Draft(Version):
    body: Text
    title: Annotated[str, StringConstraints(strip_whitespace=True, max_length=150)] = ""
    acceptance: Annotated[str, StringConstraints(strip_whitespace=True, max_length=8000)] = ""


class Confirmation(Version):
    revision: int = Field(ge=1)


class Suggestion(Version):
    lang: Literal["zh", "en"]


class Publish(Version):
    lang: Literal["zh", "en"] = "zh"


class Launch(Version):
    requirement_version: int = Field(ge=1)
    scopes: list[Annotated[str, StringConstraints(min_length=1, max_length=128)]] = Field(min_length=1, max_length=32)
    model: Annotated[str, StringConstraints(min_length=1, max_length=256)] | None = None


class Review(Version):
    document_version: int = Field(ge=1)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def conflict(detail: str) -> HTTPException:
    return HTTPException(409, detail)


def require_workspace_approval(
    domain: Tianxuan, actor: str, requirement: str, expected_version: int | None = None
) -> dict[str, Any] | None:
    """Read an exact workspace approval under the caller's domain lock."""
    document = domain.get_doc_shared(actor, requirement, write=True)
    if not re.fullmatch(r"workspace-[a-f0-9]{64}", document.get("request_id") or ""):
        return None
    version = document["version"]
    tenant = domain.actor_context(actor)["tenant"]
    if expected_version is not None and version != expected_version:
        raise NativeStoreError("Saved requirement revision changed after design approval")
    row = domain.db.execute(
        "SELECT conversation,revisions FROM workspace_requirement_approvals "
        "WHERE tenant=? AND actor=? AND requirement=? AND version=?",
        (tenant, actor, requirement, version),
    ).fetchone()
    if row is None:
        raise NativeStoreError("Current requirement revision needs the workspace owner's confirmation")
    return dict(
        tenant=tenant,
        actor=actor,
        requirement=requirement,
        version=version,
        conversation=row["conversation"],
        revisions=json.loads(row["revisions"]),
    )


class Conversations:
    def __init__(self, domain: Tianxuan):
        self.domain = domain
        with self.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS workspace_conversations ("
                "id TEXT NOT NULL, tenant TEXT NOT NULL, actor TEXT NOT NULL, title TEXT NOT NULL, "
                "updated_at TEXT NOT NULL, version INTEGER NOT NULL, state TEXT NOT NULL, PRIMARY KEY(tenant,actor,id))"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS workspace_conversations_owner "
                "ON workspace_conversations(tenant,actor,updated_at DESC,id DESC)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS workspace_requirement_approvals ("
                "tenant TEXT NOT NULL, actor TEXT NOT NULL, requirement TEXT NOT NULL, version INTEGER NOT NULL, "
                "conversation TEXT NOT NULL, revisions TEXT NOT NULL, source TEXT NOT NULL, "
                "previous_version INTEGER, approved_at TEXT NOT NULL, PRIMARY KEY(tenant,actor,requirement,version))"
            )

    @contextmanager
    def transaction(self, *, write: bool = True) -> Generator[sqlite3.Connection, None, None]:
        with self.domain._connection_lock:
            db = self.domain.db
            try:
                db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            except sqlite3.Error as exc:
                raise _storage_error(exc) from exc
            try:
                yield db
                db.commit()
            except BaseException as exc:
                db.rollback()
                if isinstance(exc, sqlite3.Error):
                    raise _storage_error(exc) from exc
                raise

    def owner(self, actor: str) -> tuple[str, str]:
        return self.domain.actor_context(actor)["tenant"], actor

    def get(self, db: sqlite3.Connection, owner: tuple[str, str], key: str) -> dict[str, Any]:
        row = db.execute(
            "SELECT id,title,updated_at,version,state FROM workspace_conversations WHERE id=? AND tenant=? AND actor=?",
            (key, *owner),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "conversation unavailable")
        result = dict(row)
        state = json.loads(result.pop("state"))
        return {"requirement_version": None, "execution": None, "past_executions": [], **state, **result}

    def save(self, db: sqlite3.Connection, owner: tuple[str, str], record: dict[str, Any]) -> dict[str, Any]:
        record["version"] += 1
        record["updated_at"] = now()
        state = {
            name: record[name]
            for name in (
                "turns",
                "revisions",
                "current",
                "requirement_id",
                "requirement_version",
                "execution",
                "past_executions",
            )
        }
        db.execute(
            "UPDATE workspace_conversations SET title=?,updated_at=?,version=?,state=? WHERE id=? AND tenant=? AND actor=?",
            (
                record["title"],
                record["updated_at"],
                record["version"],
                json.dumps(state, ensure_ascii=False),
                record["id"],
                *owner,
            ),
        )
        return record

    def list(self, actor: str, before: UUID | None) -> dict[str, Any]:
        owner = self.owner(actor)
        with self.transaction(write=False) as db:
            where = "tenant=? AND actor=?"
            params: tuple[Any, ...] = owner
            if before:
                marker = self.get(db, owner, str(before))
                where += " AND (updated_at,id)<(?,?)"
                params += (marker["updated_at"], marker["id"])
            rows = db.execute(
                "SELECT id,title,updated_at FROM workspace_conversations WHERE "
                + where
                + " ORDER BY updated_at DESC,id DESC LIMIT 31",
                params,
            ).fetchall()
            return {
                "conversations": [dict(row) for row in rows[:30]],
                "next": rows[29]["id"] if len(rows) > 30 else None,
            }

    def create(self, actor: str, key: str) -> dict[str, Any]:
        owner = self.owner(actor)
        state = {
            "turns": [],
            "revisions": [],
            "current": {},
            "requirement_id": None,
            "requirement_version": None,
            "execution": None,
            "past_executions": [],
        }
        with self.transaction() as db:
            db.execute(
                "INSERT OR IGNORE INTO workspace_conversations VALUES (?,?,?,?,?,?,?)",
                (key, *owner, "", now(), 0, json.dumps(state)),
            )
            return self.get(db, owner, key)

    @staticmethod
    def check(record: dict[str, Any], version: int) -> None:
        if record["version"] != version:
            raise conflict("conversation changed; reload the latest version")

    @staticmethod
    def active(record: dict[str, Any], stage: str) -> dict[str, Any] | None:
        revision = record["current"].get(stage)
        return cast(dict[str, Any], record["revisions"][revision - 1]) if revision else None

    def design_open(self, record: dict[str, Any], stage: Stage, version: int) -> None:
        self.check(record, version)
        if record["requirement_id"]:
            raise conflict("requirement already saved")
        if not record["turns"]:
            raise conflict("start the conversation before drafting")
        for precursor in STAGES[: STAGES.index(stage)]:
            revision = self.active(record, precursor)
            if revision is None or revision["confirmed_at"] is None:
                raise conflict("confirm the preceding stage first")

    @staticmethod
    def context(record: dict[str, Any]) -> list[dict[str, Any]]:
        context = []
        for turn in record["turns"][-12:]:
            if turn["state"] == "answered":
                context.extend((
                    {"role": "user", "content": turn["content"]},
                    {"role": "assistant", "content": turn["answer"]},
                ))
        return context

    def turn(self, actor: str, key: str, payload: Turn, gateway: ModelGateway | None) -> dict[str, Any]:
        owner = self.owner(actor)
        turn_id = str(payload.id)
        with self.transaction() as db:
            record = self.get(db, owner, key)
            for turn in record["turns"]:
                if turn["id"] == turn_id:
                    if turn["content"] != payload.content:
                        raise conflict("turn ID has different content")
                    return record
            self.check(record, payload.expected_version)
            if len(record["turns"]) >= 100:
                raise conflict("conversation turn limit reached")
            if any(turn["state"] == "pending" for turn in record["turns"]):
                raise conflict("resolve the pending turn first")
            context = self.context(record)
            record["turns"].append({
                "id": turn_id,
                "content": payload.content,
                "state": "pending",
                "answer": None,
                "model": None,
                "error": None,
            })
            if not record["title"]:
                record["title"] = payload.content.splitlines()[0][:90]
            self.save(db, owner, record)

        error: int | None = None
        result: dict[str, str] | None = None
        try:
            result = workspace_reply(gateway, owner[0], actor, [*context, {"role": "user", "content": payload.content}])
        except HTTPException as exc:
            error = exc.status_code

        with self.transaction() as db:
            record = self.get(db, owner, key)
            current = next(turn for turn in record["turns"] if turn["id"] == turn_id)
            if current["state"] == "pending":
                if result:
                    current.update(state="answered", answer=result["content"], model=result["model"])
                else:
                    current.update(state="unanswered", error=error)
                self.save(db, owner, record)
            return record

    def stop_waiting(self, actor: str, key: str, turn_id: str, version: int) -> dict[str, Any]:
        owner = self.owner(actor)
        with self.transaction() as db:
            record = self.get(db, owner, key)
            self.check(record, version)
            turn = next((turn for turn in record["turns"] if turn["id"] == turn_id), None)
            if turn is None or turn["state"] != "pending":
                raise conflict("turn is no longer pending")
            turn.update(state="unanswered", error=None)
            return self.save(db, owner, record)

    def draft(self, actor: str, key: str, stage: Stage, payload: Draft) -> dict[str, Any]:
        owner = self.owner(actor)
        with self.transaction() as db:
            record = self.get(db, owner, key)
            self.design_open(record, stage, payload.expected_version)
            if len(record["revisions"]) >= 60:
                raise conflict("design revision limit reached")
            if stage == "design" and not (payload.title and payload.acceptance):
                raise HTTPException(422, "detailed design requires a title and acceptance criteria")
            revision = len(record["revisions"]) + 1
            record["revisions"].append({
                "revision": revision,
                "stage": stage,
                "body": payload.body,
                "title": payload.title,
                "acceptance": payload.acceptance,
                "created_at": now(),
                "confirmed_at": None,
                "confirmed_by": None,
            })
            for later in STAGES[STAGES.index(stage) + 1 :]:
                record["current"].pop(later, None)
            record["current"][stage] = revision
            return self.save(db, owner, record)

    def confirm(self, actor: str, key: str, stage: Stage, payload: Confirmation) -> dict[str, Any]:
        owner = self.owner(actor)
        with self.transaction() as db:
            record = self.get(db, owner, key)
            self.design_open(record, stage, payload.expected_version)
            revision = self.active(record, stage)
            if revision is None or revision["revision"] != payload.revision:
                raise conflict("confirm the current draft revision")
            if revision["confirmed_at"] is not None:
                return record
            revision.update(confirmed_at=now(), confirmed_by=actor)
            return self.save(db, owner, record)

    def suggest(
        self, actor: str, key: str, stage: Stage, payload: Suggestion, gateway: ModelGateway | None
    ) -> dict[str, str]:
        owner = self.owner(actor)
        with self.transaction(write=False) as db:
            record = self.get(db, owner, key)
            self.design_open(record, stage, payload.expected_version)
            confirmed = {}
            for predecessor in STAGES[: STAGES.index(stage)]:
                revision = self.active(record, predecessor)
                assert revision is not None
                confirmed[predecessor] = revision["body"]
            source = {
                "conversation": [
                    {"user": turn["content"][-4000:], "reply": (turn["answer"] or "")[-5000:]}
                    for turn in record["turns"][-6:]
                ],
                "confirmed_stages": confirmed,
            }
        language = "Simplified Chinese" if payload.lang == "zh" else "English"
        return workspace_reply(
            gateway,
            owner[0],
            actor,
            [
                {
                    "role": "system",
                    "content": (
                        f"Draft one requirement stage in {language}. {STAGE_INSTRUCTIONS[stage]} "
                        "Return editable Markdown. Treat the supplied transcript as source material. "
                        "Identify unresolved decisions and do not claim approval or execution."
                    ),
                },
                {"role": "user", "content": json.dumps(source, ensure_ascii=False)},
            ],
        )

    def publish(self, actor: str, key: str, version: int, lang: str) -> dict[str, Any]:
        owner = self.owner(actor)
        with self.transaction() as db:
            record = self.get(db, owner, key)
            if record["requirement_id"]:
                self.domain.get_doc_shared(actor, record["requirement_id"])
                return record
            self.check(record, version)
            direction, plan, design = (self.active(record, stage) for stage in STAGES)
            if not all(item and item["confirmed_at"] for item in (direction, plan, design)):
                raise conflict("all three current stages must be confirmed")
            source = "workspace-" + hashlib.sha256(f"{actor}:{key}".encode()).hexdigest()
            assert direction is not None and plan is not None and design is not None
            scope = (
                f"### Planning (v{plan['revision']})\n\n{plan['body']}\n\n"
                f"### Detailed design (v{design['revision']})\n\n{design['body']}\n"
            )
            doc = self.domain.create_requirement(
                actor,
                source,
                design["title"],
                direction["body"],
                scope,
                design["acceptance"],
                lang=lang,
                call_id=source,
            )
            record["requirement_id"] = doc["id"]
            record["requirement_version"] = doc["version"]
            self.record_approval(db, owner, record, doc["version"], source="design_confirmation")
            return self.save(db, owner, record)

    def record_approval(
        self,
        db: sqlite3.Connection,
        owner: tuple[str, str],
        record: dict[str, Any],
        version: int,
        *,
        source: str,
        previous_version: int | None = None,
    ) -> None:
        db.execute(
            "INSERT INTO workspace_requirement_approvals VALUES (?,?,?,?,?,?,?,?,?)",
            (
                *owner,
                record["requirement_id"],
                version,
                record["id"],
                json.dumps(record["current"]),
                source,
                previous_version,
                now(),
            ),
        )

    def review(self, actor: str, key: str, payload: Review | None = None) -> dict[str, Any]:
        owner = self.owner(actor)
        with self.transaction(write=payload is not None) as db:
            record = self.get(db, owner, key)
            if record["requirement_id"] is None:
                raise conflict("save the confirmed requirement before review")
            document = self.domain.get_doc_shared(actor, record["requirement_id"], write=payload is not None)
            version = self.domain.version(document["id"], document["version"])
            approved = record["requirement_version"]
            if payload is None:
                return {
                    "id": document["id"],
                    "title": document["title"],
                    "version": document["version"],
                    "body_md": version["body_md"],
                    "author": version["author"],
                    "created_at": version["created_at"],
                    "approved_version": approved,
                }
            if payload.document_version != document["version"]:
                raise conflict("document changed; read the current version before confirming")
            if approved == document["version"]:
                return record
            self.check(record, payload.expected_version)
            self.record_approval(
                db, owner, record, document["version"], source="document_reconfirmation", previous_version=approved
            )
            if record["execution"] is not None:
                record["past_executions"].append(record["execution"])
                record["execution"] = None
            record["requirement_version"] = document["version"]
            return self.save(db, owner, record)

    def launch(
        self, actor: str, key: str, payload: Launch, native_entry: Any, credential: str
    ) -> tuple[dict[str, Any], bool]:
        if native_entry is None or native_entry.domain is not self.domain:
            raise HTTPException(503, "native execution is not configured")
        owner = self.owner(actor)
        scopes = sorted(set(payload.scopes))
        if len(scopes) != len(payload.scopes):
            raise HTTPException(422, "select unique installed scopes")

        try:
            with self.transaction() as db:
                record = self.get(db, owner, key)
                requirement = record["requirement_id"]
                if not requirement:
                    raise conflict("save the confirmed requirement before launching")
                if payload.requirement_version != record["requirement_version"]:
                    raise conflict("launch request refers to a different approved requirement version")
                execution = record["execution"]
                if execution is not None:
                    self.domain.get_doc_shared(actor, requirement, write=True)
                    if execution["scopes"] != scopes or execution.get("model") != payload.model:
                        raise conflict("this approval already launched with different choices")
                    return record, False
                self.check(record, payload.expected_version)
                approval = require_workspace_approval(self.domain, actor, requirement, record["requirement_version"])
                if approval is None or approval["conversation"] != key:
                    raise conflict("requirement approval is unavailable")
                spec = native_entry.installation.verify()
                if any(scope not in spec["scopes"] for scope in scopes):
                    raise HTTPException(422, "select only installed scopes")
                if payload.model is not None and not any(
                    item["id"] == payload.model and item.get("available") is True for item in spec.get("catalog", [])
                ):
                    raise HTTPException(422, "select an available installed model profile")
                call_id = "workspace-" + hashlib.sha256(f"{actor}:{key}:{approval['version']}".encode()).hexdigest()
                dependencies = native_entry.validate_dependencies(actor, requirement, [])
                choices: dict[str, Any] = {"scopes": scopes, "dependencies": dependencies}
                if payload.model is not None:
                    choices["model"] = payload.model
                entry = native_entry.ledger.enqueue(actor, requirement, call_id, choices, credential=credential)
                record["execution"] = {
                    "entry": entry,
                    "scopes": scopes,
                    "model": payload.model,
                    "call_id": call_id,
                    "requirement_version": approval["version"],
                }
                return self.save(db, owner, record), True
        except NativeStoreError as exc:
            raise conflict(str(exc)) from None


def execution_credential(request: Request) -> str:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer":
        return token.strip()
    if os.environ.get("TIANXUAN_AUTH_MODE") == "accounts":
        return request.cookies.get(SESSION_COOKIE) or request.cookies.get(COOKIE, "")
    return request.cookies.get(COOKIE, "")


def create_workspace_conversation_router(
    domain: Tianxuan, gateway: ModelGateway | None, native_entry: Any = None
) -> APIRouter:
    service = Conversations(domain)
    router = APIRouter(prefix="/api/v1/workspace/conversations")

    @router.get("")
    def list_conversations(request: Request, before: UUID | None = None):
        return service.list(workspace_actor(request), before)

    @router.post("", status_code=201)
    def create(request: Request, payload: Create):
        return service.create(workspace_actor(request, write=True), str(payload.id))

    @router.get("/{key}")
    def get(request: Request, key: UUID):
        owner = service.owner(workspace_actor(request))
        with service.transaction(write=False) as db:
            return service.get(db, owner, str(key))

    @router.post("/{key}/turns")
    def turn(request: Request, key: UUID, payload: Turn):
        return service.turn(workspace_actor(request, write=True), str(key), payload, gateway)

    @router.post("/{key}/turns/{turn_id}/stop-waiting")
    def stop_waiting(request: Request, key: UUID, turn_id: UUID, payload: Version):
        return service.stop_waiting(
            workspace_actor(request, write=True), str(key), str(turn_id), payload.expected_version
        )

    @router.post("/{key}/design/{stage}/drafts")
    def draft(request: Request, key: UUID, stage: Stage, payload: Draft):
        return service.draft(workspace_actor(request, write=True), str(key), stage, payload)

    @router.post("/{key}/design/{stage}/confirm")
    def confirm(request: Request, key: UUID, stage: Stage, payload: Confirmation):
        return service.confirm(workspace_actor(request, write=True), str(key), stage, payload)

    @router.post("/{key}/design/{stage}/suggest")
    def suggest(request: Request, key: UUID, stage: Stage, payload: Suggestion):
        return service.suggest(workspace_actor(request, write=True), str(key), stage, payload, gateway)

    @router.post("/{key}/requirement")
    def publish(request: Request, key: UUID, payload: Publish):
        return service.publish(workspace_actor(request, write=True), str(key), payload.expected_version, payload.lang)

    @router.get("/{key}/requirement-review")
    def review(request: Request, key: UUID):
        return service.review(workspace_actor(request), str(key))

    @router.post("/{key}/requirement-review")
    def confirm_requirement(request: Request, key: UUID, payload: Review):
        return service.review(workspace_actor(request, write=True), str(key), payload)

    @router.post("/{key}/execution")
    async def launch(request: Request, key: UUID, payload: Launch):
        actor = await run_in_threadpool(workspace_actor, request, write=True)
        record, created = await run_in_threadpool(
            service.launch, actor, str(key), payload, native_entry, execution_credential(request)
        )
        if created:
            native_entry.consumer.notify(record["execution"]["entry"])
        return record

    return router
