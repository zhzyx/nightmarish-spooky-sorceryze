"""天璇领域核心（可独立验证的最小切片）。

覆盖：租户/注册登录、文曲 Markdown 文档与版本、偃师需求文档、
司南工单与状态机、事件流、AI 只读机器视图与工具入口。

持久化使用标准库 sqlite3，作为测试与嵌入式存储；
生产适配器（FastAPI + PostgreSQL）在后续切片接入，不改变本层语义。
"""

from __future__ import annotations

import hashlib
import inspect
import json
import re
import sqlite3
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from functools import wraps
from threading import RLock
from typing import Any, Concatenate, ParamSpec, TypeVar, cast

SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL, password_hash TEXT NOT NULL, salt TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'editor', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS invites (
  token_hash TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, email TEXT NOT NULL, role TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, accepted_at TEXT
);
CREATE TABLE IF NOT EXISTS doc_shares (
  doc_id TEXT NOT NULL, user_id TEXT NOT NULL, permission TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (doc_id, user_id)
);
CREATE TABLE IF NOT EXISTS spaces (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, name TEXT NOT NULL, slug TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS docs (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, space_id TEXT NOT NULL,
  title TEXT NOT NULL, body_md TEXT NOT NULL, lang TEXT NOT NULL DEFAULT 'zh',
  kind TEXT NOT NULL DEFAULT 'doc', request_id TEXT, tags TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'draft', progress TEXT NOT NULL DEFAULT '{}',
  visibility TEXT NOT NULL DEFAULT 'tenant',
  version INTEGER NOT NULL DEFAULT 1, created_by TEXT NOT NULL,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS doc_versions (
  id TEXT PRIMARY KEY, doc_id TEXT NOT NULL, version INTEGER NOT NULL,
  body_md TEXT NOT NULL, author TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS issues (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, parent_id TEXT, number INTEGER NOT NULL,
  type TEXT NOT NULL, status TEXT NOT NULL, priority TEXT NOT NULL DEFAULT 'normal',
  title TEXT NOT NULL, body_md TEXT NOT NULL DEFAULT '', acceptance TEXT NOT NULL DEFAULT '',
  requirement_id TEXT, created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tool_receipts (
  tenant_id TEXT NOT NULL, actor_id TEXT NOT NULL, tool TEXT NOT NULL,
  key_kind TEXT NOT NULL, call_id TEXT NOT NULL, payload_json TEXT NOT NULL,
  result_json TEXT NOT NULL, created_at TEXT NOT NULL,
  PRIMARY KEY (tenant_id, actor_id, tool, key_kind, call_id)
);
CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, type TEXT NOT NULL, actor TEXT NOT NULL,
  target TEXT NOT NULL, payload TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS comments (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, doc_id TEXT NOT NULL, parent_id TEXT,
  author TEXT NOT NULL, body TEXT NOT NULL, resolved INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL, resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_comments_doc ON comments(doc_id, created_at);
CREATE TABLE IF NOT EXISTS issue_comments (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, issue_id TEXT NOT NULL,
  author TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_issue_comments_issue ON issue_comments(issue_id, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_docs_request ON docs(tenant_id, request_id)
  WHERE request_id IS NOT NULL;
"""

ISSUE_TRANSITIONS = {
    "backlog": {"planned", "in-progress", "cancelled"},
    "planned": {"backlog", "in-progress", "cancelled"},
    "in-progress": {"in-review", "blocked", "cancelled"},
    "blocked": {"in-progress", "cancelled"},
    "in-review": {"done", "in-progress", "cancelled"},
    "done": set(),
    "cancelled": set(),
}


class TianxuanError(Exception):
    """Base error for the Tianxuan domain."""


class VersionConflict(TianxuanError):
    """Raised when a document update uses a stale version."""


class StorageError(TianxuanError):
    """A storage failure; details remain on the chained exception, never the API."""


class StorageBusy(StorageError):
    """A competing transaction prevented this attempt; retry with the same key."""


def _storage_error(error: sqlite3.Error) -> StorageError:
    code = getattr(error, "sqlite_errorcode", 0) & 0xFF
    if code in (5, 6) or (not code and str(error) in ("database is locked", "database table is locked")):
        return StorageBusy("storage busy; retry with the same call_id")
    return StorageError("storage operation failed")


class NotFound(TianxuanError):
    """Raised when an addressed object does not exist."""


class TransitionRejected(TianxuanError):
    """Raised when an issue transition is not allowed."""


class PermissionDenied(TianxuanError):
    """Raised when the actor's role does not allow the operation."""


class UnknownTool(TianxuanError):
    """Raised when an AI tool name is not registered."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def classify(text: str) -> list[str]:
    """AI 优先的轻量归类：规则先行，模型结果可覆盖。"""
    tags: set[str] = set()
    if re.search(r"需求|验收|acceptance|requirement", text, re.I):
        tags.add("requirement")
    if re.search(r"设计|架构|design|architecture", text, re.I):
        tags.add("design")
    if re.search(r"工单|缺陷|issue|ticket|bug", text, re.I):
        tags.add("ticket")
    if re.search(r"代码|提交|分支|commit|branch|pull request|\bpr\b", text, re.I):
        tags.add("code")
    if re.search(r"[\u4e00-\u9fff]", text):
        tags.add("zh")
    if re.search(r"[A-Za-z]{3,}", text):
        tags.add("en")
    return sorted(tags)


def machine_view(body_md: str) -> dict[str, Any]:
    """为 AI 读取优化的结构化视图：标题树、链接、摘要。"""
    headings = [
        {"level": len(hashes), "text": text.strip()} for hashes, text in re.findall(r"^(#{1,6})\s+(.*)$", body_md, re.M)
    ]
    links = sorted(set(re.findall(r"\[\[([^\]]+)\]\]", body_md)))
    summary = ""
    for line in body_md.splitlines():
        clean = line.strip()
        if clean and not clean.startswith(("#", "---", ">", "-", "*", "|", "`")):
            summary = clean
            break
    return {"headings": headings, "links": links, "summary": summary}


_P = ParamSpec("_P")
_R = TypeVar("_R")
_F = TypeVar("_F", bound=Callable[..., Any])


def _connection_call(method: Callable[Concatenate[Tianxuan, _P], _R]) -> Callable[Concatenate[Tianxuan, _P], _R]:
    """Own the shared connection until the outermost domain call finishes.

    Nested calls share one transaction. Reads do not issue BEGIN or acquire a
    database write lock; SQLite begins a transaction at the first mutation.
    Direct access to db/private helpers is outside this concurrency boundary.
    """

    @wraps(method)
    def call(self: Tianxuan, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        with self._connection_lock:
            outermost = self._call_depth == 0
            # A caller-owned transaction must neither be committed nor erased.
            savepoint = f"domain_{uuid.uuid4().hex}" if outermost and self.db.in_transaction else None
            if savepoint:
                self.db.execute(f"SAVEPOINT {savepoint}")
            self._call_depth += 1
            try:
                result = method(self, *args, **kwargs)
                if savepoint:
                    self.db.execute(f"RELEASE {savepoint}")
                elif outermost:
                    self.db.commit()
                return result
            except BaseException as error:
                if savepoint:
                    self.db.execute(f"ROLLBACK TO {savepoint}")
                    self.db.execute(f"RELEASE {savepoint}")
                elif outermost:
                    self.db.rollback()
                if isinstance(error, sqlite3.Error):
                    raise _storage_error(error) from error
                raise
            finally:
                self._call_depth -= 1

    return call


def _replayable(tool: str, *, legacy: bool = False) -> Callable[[_F], _F]:
    """Opt-in receipts for ordinary writes; requirements also retain legacy replay."""

    def decorate(method: _F) -> _F:
        signature = inspect.signature(method)

        @wraps(method)
        def call(self: Tianxuan, *args: Any, **kwargs: Any) -> Any:
            bound = signature.bind(self, *args, **kwargs)
            bound.apply_defaults()
            arguments = dict(bound.arguments)
            arguments.pop("self")
            actor = arguments.pop("actor")
            call_id = arguments.pop("call_id")
            if call_id is None and (self._receipt_depth or not legacy):
                return method(self, *args, **kwargs)
            payload = self._tool_payload(tool, arguments)
            return self._run_tool_once(
                actor,
                tool,
                payload,
                call_id,
                lambda: method(self, actor, **payload, call_id=call_id),
            )

        return cast(_F, call)

    return decorate


class Tianxuan:
    """单组织首版的领域服务；方法与 AI 工具一一可测。"""

    def __init__(self, db_path: str = ":memory:"):
        self._connection_lock = RLock()
        self._call_depth = 0
        self._receipt_depth = 0
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self._migrate_sessions()
        self._migrate_users()
        self._migrate_docs()
        self.db.commit()

    def _migrate_docs(self) -> None:
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(docs)")}
        if columns and "visibility" not in columns:
            self.db.execute("ALTER TABLE docs ADD COLUMN visibility TEXT NOT NULL DEFAULT 'tenant'")

    def _migrate_users(self) -> None:
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(users)")}
        if columns and "role" not in columns:
            self.db.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'editor'")

    def _migrate_sessions(self) -> None:
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(sessions)")}
        if columns and "token_hash" not in columns:
            self.db.execute("DROP TABLE sessions")
            self.db.execute(
                "CREATE TABLE sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, "
                "created_at TEXT NOT NULL, expires_at TEXT NOT NULL)"
            )

    # ---------- 租户与身份 ----------

    @_connection_call
    def register(self, tenant_name: str, email: str, password: str, name: str = "") -> dict[str, Any]:
        if not tenant_name.strip() or not email.strip() or not password:
            raise TianxuanError("tenant name, email and password are required")
        tenant_id = _id("ten")
        space_id = _id("spc")
        user_id = _id("usr")
        salt = uuid.uuid4().hex
        now = _now()
        slug = re.sub(r"[^a-z0-9]+", "-", tenant_name.lower()).strip("-") or uuid.uuid4().hex[:8]
        try:
            self.db.execute(
                "INSERT INTO tenants (id, name, slug, created_at) VALUES (?, ?, ?, ?)",
                (tenant_id, tenant_name, slug, now),
            )
            self.db.execute(
                "INSERT INTO spaces (id, tenant_id, name, slug, created_at) VALUES (?, ?, ?, ?, ?)",
                (space_id, tenant_id, "默认空间", "default", now),
            )
            self.db.execute(
                "INSERT INTO users (id, tenant_id, email, name, password_hash, salt, role, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'admin', ?)",
                (
                    user_id,
                    tenant_id,
                    email.lower(),
                    name or email.split("@")[0],
                    _hash_password(password, salt),
                    salt,
                    now,
                ),
            )
        except sqlite3.IntegrityError as error:
            raise TianxuanError(f"registration rejected: {error}") from error
        self._event(tenant_id, "user.registered", user_id, user_id, {"email": email.lower()})
        return {"tenant_id": tenant_id, "space_id": space_id, "user_id": user_id}

    @_connection_call
    def authenticate(self, email: str, password: str) -> dict[str, Any] | None:
        row = self.db.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
        if row is None:
            return None
        if _hash_password(password, row["salt"]) != row["password_hash"]:
            return None
        return {
            "user_id": row["id"],
            "tenant_id": row["tenant_id"],
            "email": row["email"],
            "name": row["name"],
            "role": row["role"],
        }

    @_connection_call
    def issue_session(self, user_id: str, ttl_seconds: int = 86_400) -> str:
        self._tenant_of(user_id)
        token = "txs_" + uuid.uuid4().hex + uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=ttl_seconds)
        self.db.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (
                _token_hash(token),
                user_id,
                now.isoformat(timespec="seconds"),
                expires.isoformat(timespec="seconds"),
            ),
        )
        return token

    @_connection_call
    def user_for_token(self, token: str) -> str | None:
        token_hash = _token_hash(token)
        row = self.db.execute("SELECT user_id, expires_at FROM sessions WHERE token_hash = ?", (token_hash,)).fetchone()
        if row is None:
            return None
        try:
            expires = datetime.fromisoformat(row["expires_at"])
        except ValueError:
            expires = datetime.now(timezone.utc)
        if expires <= datetime.now(timezone.utc):
            self.db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
            return None
        return str(row["user_id"])

    @_connection_call
    def revoke_session(self, token: str) -> bool:
        cursor = self.db.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
        return cursor.rowcount > 0

    @_connection_call
    def role_of(self, actor: str) -> str:
        row = self.db.execute("SELECT role FROM users WHERE id = ?", (actor,)).fetchone()
        if row is None:
            raise NotFound(f"user not found: {actor}")
        return str(row["role"])

    def _require_editor(self, actor: str) -> None:
        if self.role_of(actor) == "viewer":
            raise PermissionDenied("viewer cannot modify content")

    @_connection_call
    def list_members(self, actor: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT id, email, name, role FROM users WHERE tenant_id = ? ORDER BY created_at, id",
            (self._tenant_of(actor),),
        ).fetchall()
        return [dict(row) for row in rows]

    @_connection_call
    def add_member(self, actor: str, email: str, password: str, name: str = "", role: str = "editor") -> dict[str, Any]:
        if self.role_of(actor) != "admin":
            raise PermissionDenied("only admin can add members")
        if role not in {"admin", "editor", "viewer"}:
            raise TianxuanError("role must be admin, editor or viewer")
        if not email.strip() or not password:
            raise TianxuanError("email and password are required")
        tenant_id = self._tenant_of(actor)
        salt = uuid.uuid4().hex
        user_id = _id("usr")
        display_name = name or email.split("@")[0]
        try:
            self.db.execute(
                "INSERT INTO users (id, tenant_id, email, name, password_hash, salt, role, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    tenant_id,
                    email.lower(),
                    display_name,
                    _hash_password(password, salt),
                    salt,
                    role,
                    _now(),
                ),
            )
        except sqlite3.IntegrityError as error:
            raise TianxuanError(f"member rejected: {error}") from error
        self._event(tenant_id, "user.added", actor, user_id, {"role": role})
        return {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "email": email.lower(),
            "name": display_name,
            "role": role,
        }

    @_connection_call
    def set_role(self, actor: str, user_id: str, role: str) -> dict[str, Any]:
        if self.role_of(actor) != "admin":
            raise PermissionDenied("only admin can change roles")
        if role not in {"admin", "editor", "viewer"}:
            raise TianxuanError("role must be admin, editor or viewer")
        row = self.db.execute("SELECT tenant_id FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None or row["tenant_id"] != self._tenant_of(actor):
            raise NotFound(f"user not found: {user_id}")
        self.db.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
        self._event(self._tenant_of(actor), "user.role_changed", actor, user_id, {"role": role})
        return {"user_id": user_id, "role": role}

    @_connection_call
    def create_invite(self, actor: str, email: str, role: str = "editor", ttl_seconds: int = 604_800) -> dict[str, Any]:
        if self.role_of(actor) != "admin":
            raise PermissionDenied("only admin can invite members")
        if role not in {"admin", "editor", "viewer"}:
            raise TianxuanError("role must be admin, editor or viewer")
        if not email.strip():
            raise TianxuanError("email is required")
        code = "txi_" + uuid.uuid4().hex + uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=ttl_seconds)
        self.db.execute(
            "INSERT INTO invites (token_hash, tenant_id, email, role, created_by, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                _token_hash(code),
                self._tenant_of(actor),
                email.lower(),
                role,
                actor,
                now.isoformat(timespec="seconds"),
                expires.isoformat(timespec="seconds"),
            ),
        )
        return {
            "code": code,
            "email": email.lower(),
            "role": role,
            "expires_at": expires.isoformat(timespec="seconds"),
        }

    @_connection_call
    def accept_invite(self, code: str, password: str, name: str = "") -> dict[str, Any]:
        token_hash = _token_hash(code)
        row = self.db.execute("SELECT * FROM invites WHERE token_hash = ?", (token_hash,)).fetchone()
        if row is None or row["accepted_at"] is not None:
            raise TianxuanError("invite is invalid or already used")
        try:
            expires = datetime.fromisoformat(row["expires_at"])
        except ValueError as error:
            raise TianxuanError("invite has an invalid expiry") from error
        if expires <= datetime.now(timezone.utc):
            raise TianxuanError("invite has expired")
        if not password:
            raise TianxuanError("password is required")
        salt = uuid.uuid4().hex
        user_id = _id("usr")
        display_name = name or row["email"].split("@")[0]
        try:
            self.db.execute(
                "INSERT INTO users (id, tenant_id, email, name, password_hash, salt, role, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    row["tenant_id"],
                    row["email"],
                    display_name,
                    _hash_password(password, salt),
                    salt,
                    row["role"],
                    _now(),
                ),
            )
            self.db.execute(
                "UPDATE invites SET accepted_at = ? WHERE token_hash = ?",
                (_now(), token_hash),
            )
        except sqlite3.IntegrityError as error:
            raise TianxuanError("email is already registered") from error
        self._event(row["tenant_id"], "user.invited", row["created_by"], user_id, {"role": row["role"]})
        return {
            "user_id": user_id,
            "tenant_id": row["tenant_id"],
            "email": row["email"],
            "name": display_name,
            "role": row["role"],
        }

    # ---------- 文曲：文档 ----------
    @_connection_call
    @_replayable("doc.create", legacy=False)
    def create_doc(
        self,
        actor: str,
        title: str,
        body_md: str = "",
        lang: str = "zh",
        kind: str = "doc",
        request_id: str | None = None,
        space_id: str | None = None,
        *,
        call_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_editor(actor)
        tenant_id = self._tenant_of(actor)
        space_id = (
            space_id
            or self.db.execute(
                "SELECT id FROM spaces WHERE tenant_id = ? ORDER BY created_at LIMIT 1", (tenant_id,)
            ).fetchone()["id"]
        )
        self._require_tenant_object(actor, "spaces", space_id)
        doc_id = _id("doc")
        now = _now()
        tags = classify(f"{title}\n{body_md}")
        try:
            self.db.execute(
                "INSERT INTO docs (id, tenant_id, space_id, title, body_md, lang, kind, request_id, tags, "
                "status, progress, version, created_by, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', '{}', 1, ?, ?, ?)",
                (
                    doc_id,
                    tenant_id,
                    space_id,
                    title,
                    body_md,
                    lang,
                    kind,
                    request_id,
                    json.dumps(tags),
                    actor,
                    now,
                    now,
                ),
            )
        except sqlite3.IntegrityError as error:
            if str(error) == "UNIQUE constraint failed: docs.tenant_id, docs.request_id":
                raise VersionConflict("request_id already exists in this tenant") from error
            raise
        self._version(doc_id, 1, body_md, actor)
        self._event(tenant_id, "doc.created", actor, doc_id, {"title": title, "kind": kind})
        return self.get_doc(doc_id)

    @_connection_call
    @_replayable("doc.update", legacy=False)
    def update_doc(
        self,
        actor: str,
        doc_id: str,
        body_md: str,
        expected_version: int,
        title: str | None = None,
        status: str | None = None,
        *,
        call_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_editor(actor)
        doc = self._require_tenant_doc(actor, doc_id)
        if not self._can_write(actor, doc):
            raise PermissionDenied("no write access to document")
        if doc["version"] != expected_version:
            raise VersionConflict(f"expected version {expected_version}, found {doc['version']}")
        version = expected_version + 1
        now = _now()
        title = title if title is not None else doc["title"]
        status = status if status is not None else doc["status"]
        updated = self.db.execute(
            "UPDATE docs SET title = ?, body_md = ?, status = ?, tags = ?, version = ?, updated_at = ? "
            "WHERE id = ? AND version = ?",
            (
                title,
                body_md,
                status,
                json.dumps(classify(f"{title}\n{body_md}")),
                version,
                now,
                doc_id,
                expected_version,
            ),
        )
        if updated.rowcount != 1:
            current = self.get_doc(doc_id)
            raise VersionConflict(f"expected version {expected_version}, found {current['version']}")
        self._version(doc_id, version, body_md, actor)
        self._event(doc["tenant_id"], "doc.updated", actor, doc_id, {"version": version})
        return self.get_doc(doc_id)

    @_connection_call
    def get_doc(self, doc_id: str) -> dict[str, Any]:
        row = self.db.execute("SELECT * FROM docs WHERE id = ?", (doc_id,)).fetchone()
        if row is None:
            raise NotFound(f"doc not found: {doc_id}")
        doc = dict(row)
        doc["tags"] = json.loads(doc["tags"])
        doc["progress"] = json.loads(doc["progress"])
        return doc

    @_connection_call
    def list_docs(self, actor: str, kind: str | None = None) -> list[dict[str, Any]]:
        tenant_id = self._tenant_of(actor)
        sql = "SELECT id, title, kind, status, tags, version, updated_at FROM docs WHERE tenant_id = ?"
        args: list[str] = [tenant_id]
        if self.role_of(actor) != "admin":
            sql += (
                " AND (visibility = 'tenant' OR created_by = ?"
                " OR id IN (SELECT doc_id FROM doc_shares WHERE user_id = ?))"
            )
            args.extend([actor, actor])
        if kind:
            sql += " AND kind = ?"
            args.append(kind)
        rows = self.db.execute(sql + " ORDER BY updated_at DESC", args).fetchall()
        return [dict(row) | {"tags": json.loads(row["tags"])} for row in rows]

    def _is_admin(self, actor: str) -> bool:
        return self.role_of(actor) == "admin"

    def _can_read(self, actor: str, doc: dict[str, Any]) -> bool:
        if doc["created_by"] == actor or self._is_admin(actor):
            return True
        if doc["visibility"] == "tenant":
            return True
        row = self.db.execute(
            "SELECT 1 FROM doc_shares WHERE doc_id = ? AND user_id = ?", (doc["id"], actor)
        ).fetchone()
        return row is not None

    def _can_write(self, actor: str, doc: dict[str, Any]) -> bool:
        self._require_tenant_doc(actor, doc["id"])
        if doc["created_by"] == actor or self._is_admin(actor):
            return True
        row = self.db.execute(
            "SELECT permission FROM doc_shares WHERE doc_id = ? AND user_id = ?", (doc["id"], actor)
        ).fetchone()
        if row is not None and row["permission"] == "write":
            return True
        return doc["visibility"] == "tenant" and self.role_of(actor) != "viewer"

    @_connection_call
    def get_doc_shared(self, actor: str, doc_id: str, *, write: bool = False) -> dict[str, Any]:
        doc = self.get_doc(doc_id)
        allowed = self._can_write(actor, doc) if write else self._can_read(actor, doc)
        if not allowed:
            raise PermissionDenied(f"no access to document: {doc_id}")
        return doc

    @_connection_call
    def set_visibility(self, actor: str, doc_id: str, visibility: str) -> dict[str, Any]:
        if visibility not in {"tenant", "private"}:
            raise TianxuanError("visibility must be tenant or private")
        doc = self._require_tenant_doc(actor, doc_id)
        if doc["created_by"] != actor and not self._is_admin(actor):
            raise PermissionDenied("only the owner or an admin can change visibility")
        self.db.execute("UPDATE docs SET visibility = ?, updated_at = ? WHERE id = ?", (visibility, _now(), doc_id))
        self._event(doc["tenant_id"], "doc.visibility_changed", actor, doc_id, {"visibility": visibility})
        return self.get_doc(doc_id)

    @_connection_call
    def share_doc(self, actor: str, doc_id: str, user_id: str, permission: str = "read") -> dict[str, Any]:
        if permission not in {"read", "write"}:
            raise TianxuanError("permission must be read or write")
        doc = self._require_tenant_doc(actor, doc_id)
        if doc["created_by"] != actor and not self._is_admin(actor):
            raise PermissionDenied("only the owner or an admin can share")
        target = self.db.execute("SELECT tenant_id FROM users WHERE id = ?", (user_id,)).fetchone()
        if target is None or target["tenant_id"] != doc["tenant_id"]:
            raise NotFound(f"user not found: {user_id}")
        self.db.execute(
            "INSERT INTO doc_shares (doc_id, user_id, permission, created_by, created_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(doc_id, user_id) DO UPDATE SET permission = excluded.permission",
            (doc_id, user_id, permission, actor, _now()),
        )
        self._event(doc["tenant_id"], "doc.shared", actor, doc_id, {"user_id": user_id, "permission": permission})
        return {"doc_id": doc_id, "user_id": user_id, "permission": permission}

    @_connection_call
    def unshare_doc(self, actor: str, doc_id: str, user_id: str) -> dict[str, Any]:
        doc = self._require_tenant_doc(actor, doc_id)
        if doc["created_by"] != actor and not self._is_admin(actor):
            raise PermissionDenied("only the owner or an admin can unshare")
        self._require_tenant_object(actor, "users", user_id)
        self.db.execute("DELETE FROM doc_shares WHERE doc_id = ? AND user_id = ?", (doc_id, user_id))
        self._event(doc["tenant_id"], "doc.unshared", actor, doc_id, {"user_id": user_id})
        return {"doc_id": doc_id, "user_id": user_id, "removed": True}

    @_connection_call
    def list_shares(self, actor: str, doc_id: str) -> list[dict[str, Any]]:
        doc = self.get_doc(doc_id)
        if doc["created_by"] != actor and not self._is_admin(actor):
            raise PermissionDenied("only the owner or an admin can list shares")
        rows = self.db.execute(
            "SELECT user_id, permission, created_at FROM doc_shares WHERE doc_id = ? ORDER BY created_at", (doc_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def ai_view(self, doc_id: str) -> dict[str, Any]:
        doc = self.get_doc(doc_id)
        return {
            "id": doc["id"],
            "title": doc["title"],
            "kind": doc["kind"],
            "lang": doc["lang"],
            "request_id": doc["request_id"],
            "tags": doc["tags"],
            "version": doc["version"],
            "machine": machine_view(doc["body_md"]),
            "body_md": doc["body_md"],
        }

    def _version(self, doc_id: str, version: int, body_md: str, author: str) -> None:
        self.db.execute(
            "INSERT INTO doc_versions (id, doc_id, version, body_md, author, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (_id("ver"), doc_id, version, body_md, author, _now()),
        )

    @_connection_call
    def versions(self, doc_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT version, author, created_at FROM doc_versions WHERE doc_id = ? ORDER BY version", (doc_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    @_connection_call
    def version(self, doc_id: str, version: int) -> dict[str, Any]:
        row = self.db.execute(
            "SELECT version, body_md, author, created_at FROM doc_versions WHERE doc_id = ? AND version = ?",
            (doc_id, version),
        ).fetchone()
        if row is None:
            raise NotFound(f"version not found: {doc_id}@{version}")
        return dict(row)

    # ---------- 文曲：评论 ----------

    @_connection_call
    def add_comment(self, actor: str, doc_id: str, body: str, parent_id: str | None = None) -> dict[str, Any]:
        self._require_editor(actor)
        document = self._require_tenant_doc(actor, doc_id)
        if not self._can_read(actor, document):
            raise PermissionDenied(f"no access to document: {doc_id}")
        if not body.strip():
            raise TianxuanError("comment body is required")
        if parent_id is not None:
            self._require_tenant_object(actor, "comments", parent_id)
            parent = self.get_comment(parent_id)
            if parent["doc_id"] != doc_id:
                raise TianxuanError("parent comment belongs to another document")
        comment_id = _id("cmt")
        now = _now()
        self.db.execute(
            "INSERT INTO comments (id, tenant_id, doc_id, parent_id, author, body, resolved, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
            (comment_id, document["tenant_id"], doc_id, parent_id, actor, body, now),
        )
        self._event(document["tenant_id"], "comment.created", actor, comment_id, {"doc_id": doc_id})
        return self.get_comment(comment_id)

    @_connection_call
    def get_comment(self, comment_id: str) -> dict[str, Any]:
        row = self.db.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()
        if row is None:
            raise NotFound(f"comment not found: {comment_id}")
        comment = dict(row)
        comment["resolved"] = bool(comment["resolved"])
        return comment

    @_connection_call
    def list_comments(self, actor: str, doc_id: str) -> list[dict[str, Any]]:
        document = self.get_doc(doc_id)
        if not self._can_read(actor, document):
            raise PermissionDenied(f"no access to document: {doc_id}")
        rows = self.db.execute(
            "SELECT * FROM comments WHERE tenant_id = ? AND doc_id = ? ORDER BY created_at, id",
            (document["tenant_id"], doc_id),
        ).fetchall()
        return [dict(row) | {"resolved": bool(row["resolved"])} for row in rows]

    @_connection_call
    def resolve_comment(self, actor: str, comment_id: str, resolved: bool = True) -> dict[str, Any]:
        self._require_editor(actor)
        self._require_tenant_object(actor, "comments", comment_id)
        comment = self.get_comment(comment_id)
        document = self._require_tenant_doc(actor, comment["doc_id"])
        if not self._can_write(actor, document):
            raise PermissionDenied("no write access to document")
        now = _now()
        self.db.execute(
            "UPDATE comments SET resolved = ?, resolved_at = ? WHERE id = ?",
            (1 if resolved else 0, now if resolved else None, comment_id),
        )
        self._event(
            comment["tenant_id"],
            "comment.resolved" if resolved else "comment.reopened",
            actor,
            comment_id,
            {},
        )
        return self.get_comment(comment_id)

    # ---------- 偃师：需求文档 ----------

    @_connection_call
    @_replayable("requirement.create", legacy=True)
    def create_requirement(
        self,
        actor: str,
        request_id: str,
        title: str,
        outcome: str,
        scope: str,
        acceptance: str,
        lang: str = "zh",
        *,
        call_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_editor(actor)
        body = (
            "---\n"
            f"request_id: {request_id}\nkind: requirement\nlang: {lang}\n---\n\n"
            f"# {title}\n\n## 目标\n\n{outcome}\n\n## 范围\n\n{scope}\n\n## 验收\n\n{acceptance}\n"
        )
        existing = self.db.execute(
            "SELECT * FROM docs WHERE tenant_id = ? AND request_id = ?", (self._tenant_of(actor), request_id)
        ).fetchone()
        if existing is not None:
            self._require_tenant_doc(actor, existing["id"])
            self.get_doc_shared(actor, existing["id"], write=True)
            if existing["kind"] == "requirement" and existing["title"] == title and existing["body_md"] == body:
                return self.get_doc(existing["id"])
            raise VersionConflict(f"request_id already exists with different content: {request_id}")
        return self.create_doc(actor, title, body, lang=lang, kind="requirement", request_id=request_id)

    # ---------- 司南：工单 ----------

    @_connection_call
    @_replayable("issue.create", legacy=False)
    def create_issue(
        self,
        actor: str,
        title: str,
        type: str = "task",
        acceptance: str = "",
        priority: str = "normal",
        requirement_id: str | None = None,
        parent_id: str | None = None,
        body_md: str = "",
        *,
        call_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_editor(actor)
        tenant_id = self._tenant_of(actor)
        self._require_issue_references(actor, requirement_id, parent_id, write=True)
        number = self.db.execute(
            "SELECT COALESCE(MAX(number), 0) + 1 FROM issues WHERE tenant_id = ?", (tenant_id,)
        ).fetchone()[0]
        issue_id = _id("iss")
        now = _now()
        self.db.execute(
            "INSERT INTO issues (id, tenant_id, parent_id, number, type, status, priority, title, body_md, "
            "acceptance, requirement_id, created_by, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 'backlog', ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                issue_id,
                tenant_id,
                parent_id,
                number,
                type,
                priority,
                title,
                body_md,
                acceptance,
                requirement_id,
                actor,
                now,
                now,
            ),
        )
        self._event(tenant_id, "issue.created", actor, issue_id, {"number": number, "title": title})
        return self.get_issue(issue_id)

    @_connection_call
    def get_issue(self, issue_id: str) -> dict[str, Any]:
        row = self.db.execute("SELECT * FROM issues WHERE id = ?", (issue_id,)).fetchone()
        if row is None:
            raise NotFound(f"issue not found: {issue_id}")
        return dict(row)

    @_connection_call
    def list_issues(self, actor: str, requirement_id: str | None = None) -> list[dict[str, Any]]:
        tenant_id = self._tenant_of(actor)
        sql = "SELECT * FROM issues WHERE tenant_id = ?"
        args: list[str] = [tenant_id]
        if requirement_id:
            sql += " AND requirement_id = ?"
            args.append(requirement_id)
        rows = self.db.execute(sql + " ORDER BY number", args).fetchall()
        return [dict(row) for row in rows]

    # ---------- 司南：工单评论 ----------

    @_connection_call
    def add_issue_comment(self, actor: str, issue_id: str, body: str) -> dict[str, Any]:
        self._require_editor(actor)
        if not body.strip():
            raise TianxuanError("issue comment body is required")
        issue = self._require_tenant_issue(actor, issue_id, write=True)
        comment_id = _id("icmt")
        now = _now()
        self.db.execute(
            "INSERT INTO issue_comments (id, tenant_id, issue_id, author, body, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (comment_id, issue["tenant_id"], issue_id, actor, body, now),
        )
        self._event(issue["tenant_id"], "issue.comment_added", actor, comment_id, {"issue_id": issue_id})
        return self.get_issue_comment(comment_id)

    @_connection_call
    def get_issue_comment(self, comment_id: str) -> dict[str, Any]:
        row = self.db.execute("SELECT * FROM issue_comments WHERE id = ?", (comment_id,)).fetchone()
        if row is None:
            raise NotFound(f"issue comment not found: {comment_id}")
        return dict(row)

    @_connection_call
    def list_issue_comments(self, actor: str, issue_id: str) -> list[dict[str, Any]]:
        issue = self._require_tenant_issue(actor, issue_id)
        rows = self.db.execute(
            "SELECT * FROM issue_comments WHERE tenant_id = ? AND issue_id = ? ORDER BY created_at, id",
            (issue["tenant_id"], issue_id),
        ).fetchall()
        return [dict(row) for row in rows]

    def _require_tenant_object(self, actor: str, table: str, object_id: str) -> None:
        # Table names are fixed by internal callers, never supplied by API input.
        tenant_id = self._tenant_of(actor)
        row = self.db.execute(f"SELECT tenant_id FROM {table} WHERE id = ?", (object_id,)).fetchone()
        if row is None or row["tenant_id"] != tenant_id:
            raise NotFound(f"{table} object not found: {object_id}")

    def _require_tenant_doc(self, actor: str, doc_id: str) -> dict[str, Any]:
        self._require_tenant_object(actor, "docs", doc_id)
        doc = self.get_doc(doc_id)
        self._require_tenant_object(actor, "spaces", doc["space_id"])
        return doc

    def _require_requirement(self, actor: str, requirement_id: str, *, write: bool = False) -> dict[str, Any]:
        requirement = self._require_tenant_doc(actor, requirement_id)
        if requirement["kind"] != "requirement":
            raise TianxuanError("requirement reference must name a requirement document")
        self.get_doc_shared(actor, requirement_id, write=write)
        return requirement

    def _require_issue_references(
        self, actor: str, requirement_id: str | None, parent_id: str | None, *, write: bool = False
    ) -> None:
        if requirement_id is not None:
            self._require_requirement(actor, requirement_id, write=write)
        visited: set[str] = set()
        while parent_id is not None:
            if parent_id in visited:
                raise TianxuanError("parent issue references contain a cycle")
            visited.add(parent_id)
            self._require_tenant_object(actor, "issues", parent_id)
            parent = self.get_issue(parent_id)
            if parent["requirement_id"] is not None:
                self._require_requirement(actor, parent["requirement_id"], write=write)
            parent_id = parent["parent_id"]

    def _require_tenant_issue(self, actor: str, issue_id: str, *, write: bool = False) -> dict[str, Any]:
        self._require_tenant_object(actor, "issues", issue_id)
        issue = self.get_issue(issue_id)
        self._require_issue_references(actor, issue["requirement_id"], issue["parent_id"], write=write)
        return issue

    @_connection_call
    @_replayable("issue.transition", legacy=False)
    def transition_issue(
        self, actor: str, issue_id: str, to_status: str, *, call_id: str | None = None
    ) -> dict[str, Any]:
        self._require_editor(actor)
        issue = self._require_tenant_issue(actor, issue_id, write=True)
        current = issue["status"]
        if to_status not in ISSUE_TRANSITIONS.get(current, set()):
            raise TransitionRejected(f"{current} -> {to_status} is not allowed")
        self.db.execute("UPDATE issues SET status = ?, updated_at = ? WHERE id = ?", (to_status, _now(), issue_id))
        self._event(issue["tenant_id"], "issue.transitioned", actor, issue_id, {"from": current, "to": to_status})
        if issue["requirement_id"]:
            self.sync_progress(issue["requirement_id"], actor=actor)
        return self.get_issue(issue_id)

    @_connection_call
    @_replayable("requirement.plan", legacy=True)
    def plan_tickets(
        self, actor: str, requirement_id: str, tickets: list[dict[str, Any]], *, call_id: str | None = None
    ) -> list[dict[str, Any]]:
        self._require_editor(actor)
        requirement = self._require_requirement(actor, requirement_id, write=True)
        parent_row = self.db.execute(
            "SELECT * FROM issues WHERE tenant_id = ? AND requirement_id = ? AND type = 'requirement' "
            "ORDER BY number LIMIT 1",
            (requirement["tenant_id"], requirement_id),
        ).fetchone()
        if parent_row is None:
            parent = self.create_issue(
                actor,
                requirement["title"],
                type="requirement",
                acceptance="全部子工单验收通过",
                requirement_id=requirement_id,
                body_md=f"需求文档：[[{requirement_id}]]",
            )
        else:
            parent = dict(parent_row)
        # Legacy incremental plans reuse complete specifications, with multiplicity.
        # Explicit call IDs represent intentional operations: distinct IDs create
        # distinct children, including identically titled/spec'd tickets.
        existing_children = (
            [issue for issue in self.list_issues(actor, requirement_id) if issue["parent_id"] == parent["id"]]
            if call_id is None
            else []
        )
        changed = parent_row is None
        created = []
        fields = ("title", "type", "acceptance", "priority", "body_md")
        for ticket in tickets:
            existing = next(
                (issue for issue in existing_children if all(issue[field] == ticket[field] for field in fields)), None
            )
            if existing is not None:
                created.append(existing)
                existing_children.remove(existing)
                continue
            child = self.create_issue(
                actor,
                ticket["title"],
                type=ticket["type"],
                acceptance=ticket["acceptance"],
                priority=ticket["priority"],
                body_md=ticket["body_md"],
                requirement_id=requirement_id,
                parent_id=parent["id"],
            )
            created.append(child)
            changed = True
        if changed:
            self._event(
                requirement["tenant_id"], "requirement.planned", actor, requirement_id, {"issues": len(created) + 1}
            )
            self.sync_progress(requirement_id, actor=actor)
        return [parent, *created]

    @_connection_call
    def sync_progress(self, requirement_id: str, *, actor: str) -> dict[str, Any]:
        self._require_editor(actor)
        requirement = self._require_requirement(actor, requirement_id, write=True)
        issues = self.db.execute(
            "SELECT status FROM issues WHERE requirement_id = ? AND tenant_id = ?",
            (requirement_id, requirement["tenant_id"]),
        ).fetchall()
        total = len(issues)
        done = sum(1 for row in issues if row["status"] == "done")
        progress = {"total": total, "done": done, "percent": round((done / total) * 100) if total else 0}
        self.db.execute(
            "UPDATE docs SET progress = ?, updated_at = ? WHERE id = ?", (json.dumps(progress), _now(), requirement_id)
        )
        return progress

    # ---------- 事件与 AI 工具 ----------

    def _tenant_of(self, actor: str) -> str:
        row = self.db.execute("SELECT tenant_id FROM users WHERE id = ?", (actor,)).fetchone()
        if row is None:
            raise NotFound(f"actor not found: {actor}")
        return str(row["tenant_id"])

    def _event(self, tenant_id: str, type_: str, actor: str, target: str, payload: dict[str, Any]) -> None:
        self.db.execute(
            "INSERT INTO events (id, tenant_id, type, actor, target, payload, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_id("evt"), tenant_id, type_, actor, target, json.dumps(payload), _now()),
        )

    @_connection_call
    def events(self, actor: str, limit: int = 100) -> list[dict[str, Any]]:
        tenant_id = self._tenant_of(actor)
        rows = self.db.execute(
            "SELECT type, actor, target, payload, created_at FROM events WHERE tenant_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (tenant_id, limit),
        ).fetchall()
        return [dict(row) | {"payload": json.loads(row["payload"])} for row in rows]

    @staticmethod
    def _tool_payload(name: str, payload: dict[str, Any]) -> dict[str, Any]:
        payload = dict(payload)
        if name == "requirement.plan":
            defaults = {"title": "未命名工单", "type": "task", "acceptance": "", "priority": "normal", "body_md": ""}
            tickets = payload["tickets"]
            if not isinstance(tickets, list) or any(
                not isinstance(ticket, dict) or set(ticket) - set(defaults) for ticket in tickets
            ):
                raise TianxuanError("invalid ticket specification")
            payload["tickets"] = [defaults | ticket for ticket in tickets]
        try:
            # Strict JSON rejects non-finite floats and normalizes container types.
            normalized = json.loads(json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False))
            assert isinstance(normalized, dict)
            return normalized
        except (TypeError, ValueError) as error:
            raise TianxuanError("tool payload must be JSON") from error

    def _authorize_tool(self, actor: str, name: str, payload: dict[str, Any], result: Any = None) -> None:
        self._require_editor(actor)
        if name == "doc.create" and payload["space_id"] is not None:
            self._require_tenant_object(actor, "spaces", payload["space_id"])
        if name == "doc.update":
            self._require_tenant_doc(actor, payload["doc_id"])
            self.get_doc_shared(actor, payload["doc_id"], write=True)
        if name == "requirement.plan":
            self._require_requirement(actor, payload["requirement_id"], write=True)
        if name == "issue.create":
            self._require_issue_references(actor, payload["requirement_id"], payload["parent_id"], write=True)
        if name == "issue.transition":
            self._require_tenant_issue(actor, payload["issue_id"], write=True)
        if result is None:
            return
        if name in ("doc.create", "doc.update", "requirement.create"):
            self._require_tenant_doc(actor, result["id"])
            self.get_doc_shared(actor, result["id"], write=True)
        else:
            for issue in result if isinstance(result, list) else [result]:
                self._require_tenant_issue(actor, issue["id"], write=True)

    def _run_tool_once(
        self, actor: str, name: str, payload: dict[str, Any], call_id: str | None, action: Callable[[], Any]
    ) -> Any:
        if call_id is not None and (not isinstance(call_id, str) or not call_id.strip() or len(call_id) > 256):
            raise TianxuanError("call_id must be a nonempty string of at most 256 characters")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        key_kind = "explicit" if call_id is not None else "legacy-v1"
        key = call_id if call_id is not None else hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        # SQLite's writer lock serializes independent connections/processes BEFORE
        # checking the receipt or running read-modify-write business logic.
        if not self.db.in_transaction:
            self.db.execute("BEGIN IMMEDIATE")
        savepoint = f"receipt_{uuid.uuid4().hex}"
        self.db.execute(f"SAVEPOINT {savepoint}")
        self._receipt_depth += 1
        try:
            self.db.execute("UPDATE tool_receipts SET call_id = call_id WHERE 0")
            self._require_editor(actor)
            identity = (self._tenant_of(actor), actor, name, key_kind, key)
            receipt = self.db.execute(
                "SELECT payload_json, result_json FROM tool_receipts "
                "WHERE tenant_id = ? AND actor_id = ? AND tool = ? AND key_kind = ? AND call_id = ?",
                identity,
            ).fetchone()
            if receipt is not None:
                # Check result access even on conflicts: old receipts are never an
                # alternate path around current tenant, role or document ACL checks.
                result = json.loads(receipt["result_json"])
                self._authorize_tool(actor, name, json.loads(receipt["payload_json"]), result)
                if receipt["payload_json"] != encoded:
                    raise VersionConflict("call_id already used with different payload")
            else:
                self._authorize_tool(actor, name, payload)
                result = action()
                self._authorize_tool(actor, name, payload, result)
                self.db.execute(
                    "INSERT INTO tool_receipts "
                    "(tenant_id, actor_id, tool, key_kind, call_id, payload_json, result_json, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (*identity, encoded, json.dumps(result, ensure_ascii=False, allow_nan=False), _now()),
                )
            self.db.execute(f"RELEASE {savepoint}")
            return result
        except BaseException:
            self.db.execute(f"ROLLBACK TO {savepoint}")
            self.db.execute(f"RELEASE {savepoint}")
            raise
        finally:
            self._receipt_depth -= 1

    @_connection_call
    def dispatch_tool(
        self, actor: str, name: str, payload: dict[str, Any], *, call_id: str | None = None
    ) -> dict[str, Any]:
        writes: dict[str, Callable[..., Any]] = {
            "doc.create": self.create_doc,
            "doc.update": self.update_doc,
            "requirement.create": self.create_requirement,
            "requirement.plan": self.plan_tickets,
            "issue.create": self.create_issue,
            "issue.transition": self.transition_issue,
        }
        if name in writes:
            handler = writes[name]
            payload = dict(payload)
            if "call_id" in payload:
                embedded_key = payload.pop("call_id")
                if call_id is not None and embedded_key != call_id:
                    raise TianxuanError("conflicting call_id values")
                call_id = embedded_key
            # Bind the actual public signature: defaults canonicalize identically
            # across HTTP/Python/tool calls; unknown fields cannot silently vanish.
            try:
                bound = inspect.signature(handler).bind(actor, **payload, call_id=call_id)
                bound.apply_defaults()
            except TypeError as error:
                raise TianxuanError("invalid tool arguments") from error
            arguments = dict(bound.arguments)
            arguments.pop("actor")
            arguments.pop("call_id")
            normalized = self._tool_payload(name, arguments)
            raw_handler = inspect.unwrap(handler)
            result = self._run_tool_once(
                actor,
                name,
                normalized,
                call_id,
                lambda: raw_handler(self, actor, **normalized, call_id=call_id),
            )
            return {"issues": result} if name == "requirement.plan" else result
        if call_id is not None or "call_id" in payload:
            raise TianxuanError("call_id is only supported for mutating tools")
        if name == "doc.read":
            self._require_tenant_doc(actor, payload["doc_id"])
            self.get_doc_shared(actor, payload["doc_id"])
            return self.ai_view(payload["doc_id"])
        if name == "doc.list":
            return {"docs": self.list_docs(actor, payload.get("kind"))}
        if name == "issue.list":
            return {"issues": self.list_issues(actor, payload.get("requirement_id"))}
        raise UnknownTool(f"unknown tool: {name}")
