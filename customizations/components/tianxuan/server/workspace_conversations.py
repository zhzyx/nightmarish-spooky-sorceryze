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
from uuid import NAMESPACE_URL, UUID, uuid5

from access_control import COOKIE, SESSION_COOKIE
from fastapi import APIRouter, HTTPException, Request
from gateway import ModelGateway, workspace_actor, workspace_reply
from native_store import NativeStoreError
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from starlette.concurrency import run_in_threadpool
from tianxuan_core import PROJECT_PATTERN, Tianxuan, _storage_error

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


ObjectId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1024)]


class DocumentReference(Payload):
    kind: Literal["document"]
    paragraph: int | None = Field(default=None, strict=True, ge=1)
    object_id: ObjectId
    revision: int = Field(strict=True, ge=1, le=2**63 - 1)


class EditorReference(Payload):
    kind: Literal["editor"]
    object_id: ObjectId
    revision: str = Field(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


class IssueReference(Payload):
    kind: Literal["issue"]
    object_id: ObjectId
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")


class MessageContext(Payload):
    project: str = Field(pattern=PROJECT_PATTERN)
    module_id: ObjectId
    issue_id: ObjectId | None = None
    references: list[DocumentReference | EditorReference | IssueReference] = Field(max_length=16)


class Turn(Version):
    id: UUID
    content: Text
    context_snapshot: MessageContext | None = None


class Draft(Version):
    body: str = Field(min_length=1, max_length=8000, pattern=r"\S")
    title: Annotated[str, StringConstraints(strip_whitespace=True, max_length=150)] = ""
    acceptance: Annotated[str, StringConstraints(strip_whitespace=True, max_length=8000)] = ""


class Confirmation(Version):
    revision: int = Field(ge=1)


class StageReturn(Confirmation):
    reason: Text


class Suggestion(Version):
    lang: Literal["zh", "en"]
    draft_body: str | None = Field(default=None, max_length=8000)


class Publish(Version):
    lang: Literal["zh", "en"] = "zh"


class Launch(Version):
    requirement_version: int = Field(ge=1)
    scopes: list[Annotated[str, StringConstraints(min_length=1, max_length=128)]] = Field(min_length=1, max_length=32)
    model: Annotated[str, StringConstraints(min_length=1, max_length=256)] | None = None


class Review(Version):
    document_version: int = Field(ge=1)


def markdown_blocks(markdown: str) -> Generator[str, None, None]:
    """Separate paragraphs without splitting fenced examples at their blank lines."""
    lines: list[str] = []
    fence = ""
    blank_lines: list[str] = []
    for line in markdown.splitlines(keepends=True):
        if not fence and not line.strip():
            blank_lines.append(line)
            continue
        if blank_lines and lines:
            if lines[-1].startswith(("    ", "\t")) and line.startswith(("    ", "\t")):
                lines.extend(blank_lines)
            else:
                yield "".join(lines).rstrip("\r\n")
                lines = []
        blank_lines.clear()
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
        if fence:
            if marker and marker[1].startswith(fence) and not marker[2].strip():
                fence = ""
        elif marker:
            fence = marker[1]
        lines.append(line)
    if lines:
        yield "".join(lines).rstrip("\r\n")


def paragraph_key(block: str) -> str:
    # A soft line wrap in prose renders as a space. Keep Markdown layout and code literal.
    if re.search(r"(?m)^(?: {4}|\t| {0,3}(?:[#>*+|~-]|\d+[.)]\s))|[`\\]| {2,}\r?\n", block):
        return block.replace("\r\n", "\n")
    return " ".join(block.split())


def extend_draft(body: str, suggestion: str) -> str:
    if body.strip():
        existing = {paragraph_key(block) for block in markdown_blocks(body)}
        blocks = list(markdown_blocks(suggestion))
        additions = [block for block in blocks if paragraph_key(block) not in existing]
        if not additions:
            return body
        if len(additions) != len(blocks):
            suggestion = "\n\n".join(additions)
        suggestion = body + ("\n\n" if not body.endswith("\n") else "\n") + suggestion
    if len(suggestion) > 8000:
        raise HTTPException(422, "suggestion exceeds the draft limit")
    return suggestion


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def conflict(detail: str) -> HTTPException:
    return HTTPException(409, detail)


def table_exists(db: sqlite3.Connection, name: str) -> bool:
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


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
    if not table_exists(domain.db, "workspace_requirement_approvals"):
        raise NativeStoreError("Workspace confirmation receipts are unavailable")
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

    @staticmethod
    def ensure_schema(db: sqlite3.Connection) -> None:
        # Provision on the first authenticated creation, in the same transaction.
        if table_exists(db, "workspace_conversations"):
            return
        db.execute(
            "CREATE TABLE workspace_conversations ("
            "id TEXT NOT NULL, tenant TEXT NOT NULL, actor TEXT NOT NULL, title TEXT NOT NULL, "
            "updated_at TEXT NOT NULL, version INTEGER NOT NULL, state TEXT NOT NULL, PRIMARY KEY(tenant,actor,id))"
        )
        db.execute(
            "CREATE INDEX workspace_conversations_owner "
            "ON workspace_conversations(tenant,actor,updated_at DESC,id DESC)"
        )
        db.execute(
            "CREATE TABLE workspace_requirement_approvals ("
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
        if not table_exists(db, "workspace_conversations"):
            raise HTTPException(404, "conversation unavailable")
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

    def list_conversations(self, actor: str, before: UUID | None) -> dict[str, Any]:
        owner = self.owner(actor)
        with self.transaction(write=False) as db:
            if before is None and not table_exists(db, "workspace_conversations"):
                return {"conversations": [], "next": None}
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
        state: dict[str, Any] = {
            "turns": [],
            "revisions": [],
            "current": {},
            "requirement_id": None,
            "requirement_version": None,
            "execution": None,
            "past_executions": [],
        }
        with self.transaction() as db:
            self.ensure_schema(db)
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
    def user_content(turn: dict[str, Any]) -> str:
        if turn.get("context_snapshot") is None:
            return str(turn["content"])
        return json.dumps(
            {"content": turn["content"], "context_snapshot": turn["context_snapshot"]}, ensure_ascii=False
        )

    @classmethod
    def context(cls, record: dict[str, Any]) -> list[dict[str, Any]]:
        context: list[dict[str, Any]] = []
        for turn in record["turns"][-12:]:
            if turn["state"] == "answered":
                context.extend((
                    {"role": "user", "content": cls.user_content(turn)},
                    {"role": "assistant", "content": turn["answer"]},
                ))
        return context

    def check_selection(self, actor: str, tenant: str, snapshot: MessageContext) -> None:
        if snapshot.issue_id is None:
            self.domain._business_module(tenant, snapshot.project, snapshot.module_id)
        else:
            issue = self.domain.read_issue(actor, snapshot.issue_id)
            if (issue["project"], issue["module_id"]) != (snapshot.project, snapshot.module_id):
                raise conflict("selected issue no longer belongs to this project and module")
        for reference in snapshot.references:
            if isinstance(reference, IssueReference):
                if reference.object_id != snapshot.issue_id:
                    raise conflict("reference does not match the selected issue")
                if self.domain.issue_snapshot(actor, reference.object_id)["revision"] != reference.revision:
                    raise conflict("issue definition changed; reopen its detail")
            elif isinstance(reference, DocumentReference):
                self.domain.get_doc_shared(actor, reference.object_id)
                version = self.domain.version(reference.object_id, reference.revision)
                if reference.paragraph is not None:
                    count = 0
                    inside = False
                    for line in version["body_md"].splitlines():
                        nonblank = bool(line.strip())
                        if nonblank and not inside:
                            count += 1
                        inside = nonblank
                    if reference.paragraph > count:
                        raise conflict("paragraph does not exist in the specified document revision")

    def turn(self, actor: str, key: str, payload: Turn, gateway: ModelGateway | None) -> dict[str, Any]:
        owner = self.owner(actor)
        turn_id = str(payload.id)
        snapshot = payload.context_snapshot.model_dump() if payload.context_snapshot is not None else None
        if snapshot is not None:
            for ref in snapshot["references"]:
                if ref.get("paragraph") is None:
                    ref.pop("paragraph", None)
        with self.transaction() as db:
            record = self.get(db, owner, key)
            for turn in record["turns"]:
                if turn["id"] == turn_id:
                    if turn["content"] != payload.content or turn.get("context_snapshot") != snapshot:
                        raise conflict("turn ID has different content or context")
                    return record
            self.check(record, payload.expected_version)
            if len(record["turns"]) >= 100:
                raise conflict("conversation turn limit reached")
            if any(turn["state"] == "pending" for turn in record["turns"]):
                raise conflict("resolve the pending turn first")
            if payload.context_snapshot is not None:
                self.check_selection(actor, owner[0], payload.context_snapshot)
            context = self.context(record)
            message: dict[str, Any] = {
                "id": turn_id,
                "content": payload.content,
                "state": "pending",
                "answer": None,
                "model": None,
                "error": None,
            }
            if snapshot is not None:
                message["context_snapshot"] = snapshot
            record["turns"].append(message)
            if not record["title"]:
                record["title"] = payload.content.splitlines()[0][:90]
            self.save(db, owner, record)

        error: int | None = None
        result: dict[str, str] | None = None
        try:
            context.append({"role": "user", "content": self.user_content(message)})
            result = workspace_reply(gateway, owner[0], actor, context)
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
                "created_by": actor,
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
            if revision.get("returned_at"):
                raise conflict("save a new revision after the review return")
            revision.update(confirmed_at=now(), confirmed_by=actor)
            return self.save(db, owner, record)

    def return_stage(self, actor: str, key: str, stage: Stage, payload: StageReturn) -> dict[str, Any]:
        owner = self.owner(actor)
        with self.transaction() as db:
            record = self.get(db, owner, key)
            self.design_open(record, stage, payload.expected_version)
            revision = self.active(record, stage)
            if revision is None or revision["revision"] != payload.revision:
                raise conflict("return the current draft revision")
            if revision["confirmed_at"] or revision.get("returned_at"):
                raise conflict("this revision already has a review decision")
            revision.update(returned_at=now(), returned_by=actor, return_reason=payload.reason)
            return self.save(db, owner, record)

    def document_stages(self, actor: str, document: str, version: int) -> dict[str, Any]:
        owner = self.owner(actor)
        with self.transaction(write=False) as db:
            self.domain.get_doc_shared(actor, document)
            self.domain.version(document, version)
            if table_exists(db, "workspace_requirement_approvals"):
                row = db.execute(
                    "SELECT conversation,revisions FROM workspace_requirement_approvals "
                    "WHERE tenant=? AND actor=? AND requirement=? AND version=?",
                    (*owner, document, version),
                ).fetchone()
                if row:
                    record = self.get(db, owner, row["conversation"])
                    return {
                        "document_id": document,
                        "version": version,
                        "conversation": record["id"],
                        "current": json.loads(row["revisions"]),
                        "revisions": record["revisions"],
                    }
            return {"document_id": document, "version": version, "conversation": None}

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
            revision = self.active(record, stage)
            body = payload.draft_body if payload.draft_body is not None else (revision["body"] if revision else "")
            source = {
                "conversation": [
                    {
                        "user": turn["content"][-4000:],
                        "reply": (turn["answer"] or "")[-5000:],
                        **({"context_snapshot": turn["context_snapshot"]} if turn.get("context_snapshot") else {}),
                    }
                    for turn in record["turns"][-6:]
                ],
                "confirmed_stages": confirmed,
                "existing_draft": body,
            }
        language = "Simplified Chinese" if payload.lang == "zh" else "English"
        reply: dict[str, str] = workspace_reply(
            gateway,
            owner[0],
            actor,
            [
                {
                    "role": "system",
                    "content": (
                        f"Draft one requirement stage in {language}. {STAGE_INSTRUCTIONS[stage]} "
                        "Return editable Markdown. Treat the supplied transcript as source material. "
                        "Include goals, proposed solutions, unresolved decisions and observable acceptance where relevant. "
                        "Return only material missing from the existing draft. Do not repeat or rewrite its paragraphs. "
                        "Do not claim approval or execution."
                    ),
                },
                {"role": "user", "content": json.dumps(source, ensure_ascii=False)},
            ],
        )
        return {**reply, "content": extend_draft(body, reply["content"])}

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
    authorization: str = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer":
        return token.strip()
    key: str = request.cookies.get(COOKIE, "")
    if os.environ.get("TIANXUAN_AUTH_MODE") == "accounts":
        session: str | None = request.cookies.get(SESSION_COOKIE)
        return session or key
    return key


def create_workspace_conversation_router(
    domain: Tianxuan, gateway: ModelGateway | None, native_entry: Any = None
) -> APIRouter:
    service = Conversations(domain)
    router = APIRouter(prefix="/api/v1/workspace/conversations")

    @router.get("")
    def list_conversations(request: Request, before: UUID | None = None):
        return service.list_conversations(workspace_actor(request), before)

    @router.post("", status_code=201)
    def create(request: Request, payload: Create):
        return service.create(workspace_actor(request, write=True), str(payload.id))

    @router.post("/for-issue/{issue_id}")
    def open_issue_consultation(request: Request, issue_id: str, project: str):
        actor = workspace_actor(request, write=True)
        issue = domain.read_issue(actor, issue_id)
        if issue["project"] != project:
            raise HTTPException(404, "issue unavailable in this project")
        identity = json.dumps(["tianxuan/issue-consultation", issue["tenant_id"], actor, issue_id])
        return service.create(actor, str(uuid5(NAMESPACE_URL, identity)))

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

    @router.post("/{key}/design/{stage}/return")
    def return_stage(request: Request, key: UUID, stage: Stage, payload: StageReturn):
        return service.return_stage(workspace_actor(request, write=True), str(key), stage, payload)

    @router.get("/for-document/{document}/versions/{version}")
    def document_stages(request: Request, document: str, version: Annotated[int, Field(ge=1, le=2**63 - 1)]):
        return service.document_stages(workspace_actor(request), document, version)

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
