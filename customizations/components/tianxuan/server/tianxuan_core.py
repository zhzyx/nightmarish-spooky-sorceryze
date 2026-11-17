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
CREATE TABLE IF NOT EXISTS access_keys (
  id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, user_id TEXT NOT NULL,
  name TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, revoked_at TEXT
);
CREATE TABLE IF NOT EXISTS invites (
  token_hash TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, email TEXT NOT NULL, role TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, accepted_at TEXT
);
CREATE TABLE IF NOT EXISTS doc_shares (
  doc_id TEXT NOT NULL, user_id TEXT NOT NULL, permission TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT,
  PRIMARY KEY (doc_id, user_id)
);
CREATE TABLE IF NOT EXISTS doc_field_permissions (
  doc_id TEXT NOT NULL, field TEXT NOT NULL, min_role TEXT NOT NULL,
  updated_by TEXT NOT NULL, updated_at TEXT NOT NULL,
  PRIMARY KEY (doc_id, field)
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
CREATE TABLE IF NOT EXISTS doc_issue_links (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  doc_id TEXT NOT NULL, issue_id TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL,
  UNIQUE (tenant_id, doc_id, issue_id)
);
CREATE TABLE IF NOT EXISTS native_managed_issues (
  issue_id TEXT PRIMARY KEY, definition TEXT NOT NULL, acceptance TEXT
);
CREATE INDEX IF NOT EXISTS idx_doc_issue_links_issue ON doc_issue_links(tenant_id, issue_id);
CREATE TABLE IF NOT EXISTS import_jobs (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, actor TEXT NOT NULL,
  name TEXT NOT NULL, source TEXT NOT NULL,
  status TEXT NOT NULL, phase TEXT NOT NULL, message TEXT NOT NULL DEFAULT '',
  path TEXT, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_import_jobs_tenant ON import_jobs(tenant_id, created_at);
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
CREATE TABLE IF NOT EXISTS external_links (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  system TEXT NOT NULL, external_id TEXT NOT NULL,
  target_type TEXT NOT NULL, target_id TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL,
  UNIQUE (tenant_id, system, external_id, target_type, target_id)
);
CREATE INDEX IF NOT EXISTS idx_external_links_lookup
  ON external_links(tenant_id, system, external_id);
CREATE TABLE IF NOT EXISTS identity_links (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  provider TEXT NOT NULL, subject TEXT NOT NULL, user_id TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE (provider, subject)
);
CREATE INDEX IF NOT EXISTS idx_issue_comments_issue ON issue_comments(issue_id, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_docs_request ON docs(tenant_id, request_id)
  WHERE request_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS repo_links (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
  provider TEXT NOT NULL, owner TEXT NOT NULL, name TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL,
  UNIQUE (provider, owner, name)
);
CREATE INDEX IF NOT EXISTS idx_repo_links_tenant ON repo_links(tenant_id);
CREATE TABLE IF NOT EXISTS native_requirement_sources (
  tenant_id TEXT NOT NULL, module TEXT NOT NULL, doc_id TEXT NOT NULL,
  PRIMARY KEY (tenant_id, module), UNIQUE (tenant_id, doc_id)
);
"""

_FIELD_FIELDS = {"title", "body_md", "status", "visibility"}
_ROLE_RANK = {"viewer": 0, "editor": 1, "admin": 2}

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


def _normalize_expiry(value: str | None) -> str | None:
    """校验共享过期时间：None/空串表示不过期，否则必须是未来的 ISO-8601。"""
    if value is None or not str(value).strip():
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError as error:
        raise TianxuanError("expires_at must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    if parsed <= datetime.now(timezone.utc):
        raise TianxuanError("expires_at must be in the future")
    return parsed.astimezone(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


_REPO_PROVIDERS = frozenset({"gitea", "github"})
_REPO_SEGMENT_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _validate_repo_provider(value: str) -> str:
    if not isinstance(value, str):
        raise TianxuanError("repository provider must be a string")
    provider = value.strip().lower()
    if provider not in _REPO_PROVIDERS:
        raise TianxuanError(f"unsupported repository provider: {value!r}; expected one of gitea, github")
    return provider


def _validate_repo_segment(value: str, label: str) -> str:
    if not isinstance(value, str):
        raise TianxuanError(f"repository {label} must be a string")
    if not value or value != value.strip():
        raise TianxuanError(f"invalid repository {label}: {value!r}")
    if len(value) > 100:
        raise TianxuanError(f"repository {label} is too long: {value!r}")
    if _REPO_SEGMENT_CONTROL.search(value) or "/" in value or "\\" in value:
        raise TianxuanError(f"invalid repository {label}: {value!r}")
    return value


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
        self._migrate_doc_shares()
        self.db.commit()

    def _migrate_doc_shares(self) -> None:
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(doc_shares)")}
        if columns and "expires_at" not in columns:
            self.db.execute("ALTER TABLE doc_shares ADD COLUMN expires_at TEXT")

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
    def issue_access_key(self, actor: str, user_id: str, name: str, days: int = 90) -> dict[str, Any]:
        if self.role_of(actor) != "admin" or self._tenant_of(actor) != self._tenant_of(user_id):
            raise PermissionDenied("only a tenant administrator can issue access keys")
        if not name.strip() or len(name) > 100 or not 1 <= days <= 365:
            raise TianxuanError("key name and lifetime (1–365 days) are required")
        token = self.issue_session(user_id, days * 86400)
        key_id = _id("key")
        self.db.execute(
            "INSERT INTO access_keys VALUES (?, ?, ?, ?, ?, ?, NULL)",
            (key_id, _token_hash(token), user_id, name.strip(), actor, _now()),
        )
        self._event(self._tenant_of(actor), "access_key.issued", actor, key_id, {"user_id": user_id})
        return {"id": key_id, "key": token, "user_id": user_id, "name": name.strip(), "days": days}

    @_connection_call
    def user_for_access_key(self, token: str) -> str | None:
        row = self.db.execute(
            "SELECT user_id FROM access_keys WHERE token_hash = ? AND revoked_at IS NULL",
            (_token_hash(token),),
        ).fetchone()
        if row is None:
            return None
        actor = self.user_for_token(token)
        if actor is None:
            return None
        self.role_of(actor)
        return actor

    @_connection_call
    def list_access_keys(self, actor: str) -> list[dict[str, Any]]:
        if self.role_of(actor) != "admin":
            raise PermissionDenied("only admin can manage access keys")
        rows = self.db.execute(
            "SELECT k.id,k.user_id,k.name,k.created_at,k.revoked_at,s.expires_at "
            "FROM access_keys k JOIN users u ON u.id=k.user_id "
            "LEFT JOIN sessions s ON s.token_hash=k.token_hash WHERE u.tenant_id=? "
            "ORDER BY k.created_at,k.id",
            (self._tenant_of(actor),),
        ).fetchall()
        return [dict(row) for row in rows]

    @_connection_call
    def revoke_access_key(self, actor: str, key_id: str) -> bool:
        if self.role_of(actor) != "admin":
            raise PermissionDenied("only admin can revoke access keys")
        row = self.db.execute(
            "SELECT k.token_hash FROM access_keys k JOIN users u ON u.id=k.user_id WHERE k.id=? AND u.tenant_id=?",
            (key_id, self._tenant_of(actor)),
        ).fetchone()
        if row is None:
            raise NotFound("access key not found")
        self.db.execute("DELETE FROM sessions WHERE token_hash=?", (row["token_hash"],))
        self.db.execute("UPDATE access_keys SET revoked_at=? WHERE id=?", (_now(), key_id))
        self._event(self._tenant_of(actor), "access_key.revoked", actor, key_id, {})
        return True

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
        if body_md != doc["body_md"]:
            self._require_field_write(actor, doc, "body_md")
        if title is not None and title != doc["title"]:
            self._require_field_write(actor, doc, "title")
        if status is not None and status != doc["status"]:
            self._require_field_write(actor, doc, "status")
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
                " OR id IN (SELECT doc_id FROM doc_shares WHERE user_id = ?"
                " AND (expires_at IS NULL OR expires_at > ?)))"
            )
            args.extend([actor, actor, _now()])
        if kind:
            sql += " AND kind = ?"
            args.append(kind)
        rows = self.db.execute(sql + " ORDER BY updated_at DESC", args).fetchall()
        return [dict(row) | {"tags": json.loads(row["tags"])} for row in rows]

    def _is_admin(self, actor: str) -> bool:
        return self.role_of(actor) == "admin"

    def _can_read(self, actor: str, doc: dict[str, Any]) -> bool:
        self._require_tenant_doc(actor, doc["id"])
        if doc["created_by"] == actor or self._is_admin(actor):
            return True
        if doc["visibility"] == "tenant":
            return True
        row = self.db.execute(
            "SELECT 1 FROM doc_shares WHERE doc_id = ? AND user_id = ? AND (expires_at IS NULL OR expires_at > ?)",
            (doc["id"], actor, _now()),
        ).fetchone()
        return row is not None

    def _can_write(self, actor: str, doc: dict[str, Any]) -> bool:
        self._require_tenant_doc(actor, doc["id"])
        if doc["created_by"] == actor or self._is_admin(actor):
            return True
        row = self.db.execute(
            "SELECT permission FROM doc_shares WHERE doc_id = ? AND user_id = ?"
            " AND (expires_at IS NULL OR expires_at > ?)",
            (doc["id"], actor, _now()),
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
        if visibility != doc["visibility"]:
            self._require_field_write(actor, doc, "visibility")
        self.db.execute("UPDATE docs SET visibility = ?, updated_at = ? WHERE id = ?", (visibility, _now(), doc_id))
        self._event(doc["tenant_id"], "doc.visibility_changed", actor, doc_id, {"visibility": visibility})
        return self.get_doc(doc_id)

    @_connection_call
    def share_doc(
        self,
        actor: str,
        doc_id: str,
        user_id: str,
        permission: str = "read",
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        if permission not in {"read", "write"}:
            raise TianxuanError("permission must be read or write")
        expiry = _normalize_expiry(expires_at)
        doc = self._require_tenant_doc(actor, doc_id)
        if doc["created_by"] != actor and not self._is_admin(actor):
            raise PermissionDenied("only the owner or an admin can share")
        target = self.db.execute("SELECT tenant_id FROM users WHERE id = ?", (user_id,)).fetchone()
        if target is None or target["tenant_id"] != doc["tenant_id"]:
            raise NotFound(f"user not found: {user_id}")
        self.db.execute(
            "INSERT INTO doc_shares (doc_id, user_id, permission, created_by, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(doc_id, user_id) DO UPDATE SET permission = excluded.permission, "
            "expires_at = excluded.expires_at, created_at = excluded.created_at",
            (doc_id, user_id, permission, actor, _now(), expiry),
        )
        self._event(
            doc["tenant_id"],
            "doc.shared",
            actor,
            doc_id,
            {"user_id": user_id, "permission": permission, "expires_at": expiry},
        )
        return {"doc_id": doc_id, "user_id": user_id, "permission": permission, "expires_at": expiry}

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
            "SELECT user_id, permission, created_at, expires_at FROM doc_shares WHERE doc_id = ?"
            " AND (expires_at IS NULL OR expires_at > ?) ORDER BY created_at",
            (doc_id, _now()),
        ).fetchall()
        return [dict(row) for row in rows]

    # ---------- 文曲：文档字段级权限 ----------

    @_connection_call
    def set_doc_field_permission(
        self,
        actor: str,
        doc_id: str,
        field: str,
        min_role: str,
    ) -> dict[str, Any]:
        if field not in _FIELD_FIELDS:
            raise TianxuanError(f"unsupported field: {field}")
        if min_role not in _ROLE_RANK:
            raise TianxuanError("min_role must be viewer, editor or admin")
        doc = self._require_tenant_doc(actor, doc_id)
        if doc["created_by"] != actor and not self._is_admin(actor):
            raise PermissionDenied("only the owner or an admin can set field permissions")
        now = _now()
        self.db.execute(
            "INSERT INTO doc_field_permissions (doc_id, field, min_role, updated_by, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(doc_id, field) DO UPDATE SET min_role = excluded.min_role, "
            "updated_by = excluded.updated_by, updated_at = excluded.updated_at",
            (doc_id, field, min_role, actor, now),
        )
        self._event(
            doc["tenant_id"],
            "doc.field_permission_set",
            actor,
            doc_id,
            {"field": field, "min_role": min_role},
        )
        return {"doc_id": doc_id, "field": field, "min_role": min_role, "updated_at": now}

    @_connection_call
    def list_doc_field_permissions(self, actor: str, doc_id: str) -> list[dict[str, Any]]:
        doc = self.get_doc_shared(actor, doc_id, write=True)
        rows = self.db.execute(
            "SELECT field, min_role, updated_by, updated_at FROM doc_field_permissions WHERE doc_id = ? ORDER BY field",
            (doc["id"],),
        ).fetchall()
        return [dict(row) for row in rows]

    def _require_field_write(self, actor: str, doc: dict[str, Any], field: str) -> None:
        if self._is_admin(actor):
            return
        row = self.db.execute(
            "SELECT min_role FROM doc_field_permissions WHERE doc_id = ? AND field = ?",
            (doc["id"], field),
        ).fetchone()
        if row is None:
            return
        if _ROLE_RANK.get(self.role_of(actor), 0) < _ROLE_RANK.get(str(row["min_role"]), 0):
            raise PermissionDenied(f"{field} requires {row['min_role']} role")

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
        return self._visible_issues(actor, rows)

    def _visible_issues(self, actor: str, rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        visible = []
        for row in rows:
            try:
                self._require_tenant_issue(actor, row["id"])
            except (NotFound, PermissionDenied):
                continue
            visible.append(dict(row))
        return visible

    @_connection_call
    def issue_snapshot(self, actor: str, issue_id: str, *, write: bool = False) -> dict[str, Any]:
        if not self.db.in_transaction:
            self.db.execute("BEGIN")
        if write:
            self._require_editor(actor)
        issue = self._require_tenant_issue(actor, issue_id, write=write)
        fields = ("id", "tenant_id", "parent_id", "type", "title", "body_md", "acceptance", "requirement_id")
        definition = {key: issue[key] for key in fields}
        ancestors = []
        current: dict[str, Any] | None = issue
        while current:
            if current["requirement_id"]:
                doc = self.get_doc_shared(actor, current["requirement_id"], write=write)
                ancestors.append({key: doc[key] for key in ("id", "title", "body_md", "kind")})
            current = self.get_issue(current["parent_id"]) if current["parent_id"] else None
        definition["requirements"] = ancestors
        encoded = json.dumps(definition, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return {"definition": definition, "revision": hashlib.sha256(encoded.encode()).hexdigest()}

    @_connection_call
    def actor_context(self, actor: str) -> dict[str, str]:
        """Resolve identity fields together under the shared connection lock."""
        return {"actor": actor, "tenant": self._tenant_of(actor), "role": self.role_of(actor)}

    @_connection_call
    def bind_native_requirement(self, actor: str, doc_id: str) -> str:
        """Reserve a source-bound namespace before persisting native content.

        A later native write failure may leave an empty reservation. It never
        creates content, a successful receipt, or permission to read the source.
        """
        self._require_requirement(actor, doc_id, write=True)
        tenant = self._tenant_of(actor)
        module = "requirement-" + hashlib.sha256(doc_id.encode()).hexdigest()
        self.db.execute("INSERT OR IGNORE INTO native_requirement_sources VALUES (?,?,?)", (tenant, module, doc_id))
        row = self.db.execute(
            "SELECT doc_id FROM native_requirement_sources WHERE tenant_id=? AND module=?", (tenant, module)
        ).fetchone()
        if row is None or row["doc_id"] != doc_id:
            raise VersionConflict("native requirement binding conflict")
        return module

    @_connection_call
    def require_native_module_read(self, actor: str, module: str) -> None:
        """Use current source ACL, never a caller-authored native object binding."""
        tenant = self._tenant_of(actor)
        row = self.db.execute(
            "SELECT doc_id FROM native_requirement_sources WHERE tenant_id=? AND module=?", (tenant, module)
        ).fetchone()
        if row is None:
            raise PermissionDenied("native requirement source unavailable")
        self.get_doc_shared(actor, row["doc_id"])

    @_connection_call
    def requirement_snapshot(self, actor: str, doc_id: str) -> dict[str, Any]:
        """One deferred SQLite read transaction, including other connections' writes.

        The domain wrapper owns the shared connection and ends this transaction
        before serialization or native storage work. No writer reservation is taken.
        """
        if not self.db.in_transaction:
            self.db.execute("BEGIN")
        document = self.get_doc_shared(actor, doc_id)
        if document["kind"] != "requirement":
            raise TianxuanError("expected a requirement document")
        issues = {row["id"]: row for row in self.list_issues(actor, doc_id)}
        issues.update({row["id"]: row for row in self.list_doc_issues(actor, doc_id)})
        return {"document": document, "issues": sorted(issues.values(), key=lambda row: row["id"])}

    # ---------- 文曲/司南：文档 ↔ 工单关联 ----------

    @_connection_call
    def link_doc_issue(self, actor: str, doc_id: str, issue_id: str) -> dict[str, Any]:
        """把文档与工单双向关联；重复关联幂等返回已有记录。"""
        self._require_editor(actor)
        self.get_doc_shared(actor, doc_id, write=True)
        issue = self._require_tenant_issue(actor, issue_id)
        tenant_id = self._tenant_of(actor)
        existing = self.db.execute(
            "SELECT * FROM doc_issue_links WHERE tenant_id = ? AND doc_id = ? AND issue_id = ?",
            (tenant_id, doc_id, issue_id),
        ).fetchone()
        if existing is not None:
            return dict(existing)
        link_id = _id("dil")
        now = _now()
        try:
            self.db.execute(
                "INSERT INTO doc_issue_links (id, tenant_id, doc_id, issue_id, created_by, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (link_id, tenant_id, doc_id, issue["id"], actor, now),
            )
        except sqlite3.IntegrityError as error:
            row = self.db.execute(
                "SELECT * FROM doc_issue_links WHERE tenant_id = ? AND doc_id = ? AND issue_id = ?",
                (tenant_id, doc_id, issue_id),
            ).fetchone()
            if row is None:
                raise TianxuanError("failed to link document and issue") from error
            return dict(row)
        self._event(
            tenant_id,
            "doc.issue_linked",
            actor,
            f"{doc_id}:{issue['id']}",
            {"doc_id": doc_id, "issue_id": issue["id"]},
        )
        return {
            "id": link_id,
            "tenant_id": tenant_id,
            "doc_id": doc_id,
            "issue_id": issue["id"],
            "created_by": actor,
            "created_at": now,
        }

    @_connection_call
    def unlink_doc_issue(self, actor: str, doc_id: str, issue_id: str) -> dict[str, Any]:
        self._require_editor(actor)
        self.get_doc_shared(actor, doc_id, write=True)
        tenant_id = self._tenant_of(actor)
        row = self.db.execute(
            "SELECT id FROM doc_issue_links WHERE tenant_id = ? AND doc_id = ? AND issue_id = ?",
            (tenant_id, doc_id, issue_id),
        ).fetchone()
        if row is None:
            raise NotFound(f"document is not linked to issue: {issue_id}")
        self.db.execute("DELETE FROM doc_issue_links WHERE id = ?", (row["id"],))
        self._event(
            tenant_id,
            "doc.issue_unlinked",
            actor,
            f"{doc_id}:{issue_id}",
            {"doc_id": doc_id, "issue_id": issue_id},
        )
        return {"doc_id": doc_id, "issue_id": issue_id, "deleted": True}

    # ---------- 多宝：仓库导入任务 ----------

    @_connection_call
    def create_import_job(self, actor: str, name: str, source: str) -> dict[str, Any]:
        self._require_editor(actor)
        job_id = _id("imp")
        now = _now()
        self.db.execute(
            "INSERT INTO import_jobs (id, tenant_id, actor, name, source, status, phase, message, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'queued', 'queued', '', ?, ?)",
            (job_id, self._tenant_of(actor), actor, name, source, now, now),
        )
        self._event(self._tenant_of(actor), "repo.import_queued", actor, job_id, {"name": name})
        return self.get_import_job(actor, job_id)

    @_connection_call
    def update_import_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        phase: str | None = None,
        message: str | None = None,
        path: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        self.get_import_job_unscoped(job_id)
        fields: dict[str, Any] = {}
        if status is not None:
            fields["status"] = status
        if phase is not None:
            fields["phase"] = phase
        if message is not None:
            fields["message"] = message
        if path is not None:
            fields["path"] = path
        if error is not None:
            fields["error"] = error
        if fields:
            fields["updated_at"] = _now()
            assignments = ", ".join(f"{key} = ?" for key in fields)
            self.db.execute(
                f"UPDATE import_jobs SET {assignments} WHERE id = ?",
                (*fields.values(), job_id),
            )
        return self.get_import_job_unscoped(job_id)

    @_connection_call
    def get_import_job(self, actor: str, job_id: str) -> dict[str, Any]:
        job = self.get_import_job_unscoped(job_id)
        if job["tenant_id"] != self._tenant_of(actor):
            raise NotFound(f"import job not found: {job_id}")
        return job

    @_connection_call
    def get_import_job_unscoped(self, job_id: str) -> dict[str, Any]:
        row = self.db.execute("SELECT * FROM import_jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise NotFound(f"import job not found: {job_id}")
        return dict(row)

    @_connection_call
    def list_import_jobs(self, actor: str, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        rows = self.db.execute(
            "SELECT * FROM import_jobs WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ?",
            (self._tenant_of(actor), limit),
        ).fetchall()
        return [dict(row) for row in rows]

    @_connection_call
    def list_doc_issues(self, actor: str, doc_id: str) -> list[dict[str, Any]]:
        self.get_doc_shared(actor, doc_id)
        tenant_id = self._tenant_of(actor)
        rows = self.db.execute(
            "SELECT i.id, i.number, i.title, i.status, i.priority, i.type, i.requirement_id, i.updated_at "
            "FROM issues i JOIN doc_issue_links l ON l.issue_id = i.id AND l.tenant_id = i.tenant_id "
            "WHERE l.tenant_id = ? AND l.doc_id = ? ORDER BY i.number",
            (tenant_id, doc_id),
        ).fetchall()
        return self._visible_issues(actor, rows)

    @_connection_call
    def list_issue_docs(self, actor: str, issue_id: str) -> list[dict[str, Any]]:
        issue = self._require_tenant_issue(actor, issue_id)
        rows = self.db.execute(
            "SELECT doc_id FROM doc_issue_links WHERE tenant_id = ? AND issue_id = ? ORDER BY created_at, id",
            (issue["tenant_id"], issue_id),
        ).fetchall()
        documents: list[dict[str, Any]] = []
        for row in rows:
            try:
                document = self.get_doc_shared(actor, str(row["doc_id"]))
            except (NotFound, PermissionDenied):
                continue
            documents.append({
                "id": document["id"],
                "title": document["title"],
                "kind": document["kind"],
                "status": document["status"],
                "version": document["version"],
                "updated_at": document["updated_at"],
            })
        return documents

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
            "SELECT * FROM issue_comments WHERE tenant_id = ? AND issue_id = ? ORDER BY created_at, rowid",
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
        if (
            to_status == "done"
            and self.db.execute("SELECT 1 FROM native_managed_issues WHERE issue_id=?", (issue_id,)).fetchone()
        ):
            raise TransitionRejected("native managed completion requires trusted workflow acceptance")
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

    # ---------- 跨系统：天枢 ↔ 天璇 ----------

    def link_external(
        self,
        actor: str,
        system: str,
        external_id: str,
        target_type: str,
        target_id: str,
    ) -> dict[str, Any]:
        """把外部系统标识（如 Tianshu/GitHub Issue）绑定到天璇文档或工单。"""
        self._require_editor(actor)
        system = system.strip()
        external_id = external_id.strip()
        if not system or not external_id:
            raise TianxuanError("system and external_id are required")
        tenant_id = self._tenant_of(actor)
        if target_type == "doc":
            target = self.get_doc(target_id)
        elif target_type == "issue":
            target = self.get_issue(target_id)
        else:
            raise TianxuanError("target_type must be doc or issue")
        if target["tenant_id"] != tenant_id:
            raise NotFound(f"{target_type} not found: {target_id}")
        existing = self.db.execute(
            "SELECT * FROM external_links WHERE tenant_id = ? AND system = ? AND external_id = ? "
            "AND target_type = ? AND target_id = ?",
            (tenant_id, system, external_id, target_type, target_id),
        ).fetchone()
        if existing is not None:
            return dict(existing)
        link_id = _id("xln")
        now = _now()
        self.db.execute(
            "INSERT INTO external_links (id, tenant_id, system, external_id, target_type, target_id, "
            "created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (link_id, tenant_id, system, external_id, target_type, target_id, actor, now),
        )
        self._event(
            tenant_id,
            "external.linked",
            actor,
            link_id,
            {"system": system, "external_id": external_id, "target_type": target_type, "target_id": target_id},
        )
        row = self.db.execute("SELECT * FROM external_links WHERE id = ?", (link_id,)).fetchone()
        return dict(row)

    def external_targets(self, actor: str, system: str, external_id: str) -> list[dict[str, Any]]:
        tenant_id = self._tenant_of(actor)
        rows = self.db.execute(
            "SELECT * FROM external_links WHERE tenant_id = ? AND system = ? AND external_id = ? "
            "ORDER BY created_at, id",
            (tenant_id, system, external_id),
        ).fetchall()
        links: list[dict[str, Any]] = []
        for row in rows:
            link = dict(row)
            try:
                if link["target_type"] == "doc":
                    target = self.get_doc(link["target_id"])
                    link["target"] = {
                        "id": target["id"],
                        "type": "doc",
                        "title": target["title"],
                        "kind": target["kind"],
                        "version": target["version"],
                    }
                else:
                    target = self.get_issue(link["target_id"])
                    link["target"] = {
                        "id": target["id"],
                        "type": "issue",
                        "title": target["title"],
                        "status": target["status"],
                        "number": target["number"],
                    }
            except NotFound:
                link["target"] = None
            links.append(link)
        return links

    def external_links_for(self, actor: str, target_type: str, target_id: str) -> list[dict[str, Any]]:
        """返回绑定到某个文档/工单的外部系统标识。"""
        tenant_id = self._tenant_of(actor)
        if target_type == "doc":
            target = self.get_doc(target_id)
        elif target_type == "issue":
            target = self.get_issue(target_id)
        else:
            raise TianxuanError("target_type must be doc or issue")
        if target["tenant_id"] != tenant_id:
            raise NotFound(f"{target_type} not found: {target_id}")
        rows = self.db.execute(
            "SELECT * FROM external_links WHERE tenant_id = ? AND target_type = ? AND target_id = ? "
            "ORDER BY created_at, id",
            (tenant_id, target_type, target_id),
        ).fetchall()
        return [dict(row) for row in rows]

    def external_context(self, actor: str, system: str, external_id: str) -> dict[str, Any]:
        """返回外部标识在天璇内的文档、需求与工单，供天枢画布/对话读取。"""
        links = self.external_targets(actor, system, external_id)
        documents: dict[str, dict[str, Any]] = {}
        issues: dict[str, dict[str, Any]] = {}
        for link in links:
            target = link.get("target")
            if not isinstance(target, dict):
                continue
            try:
                if target["type"] == "doc":
                    document = self.get_doc(target["id"])
                    documents[document["id"]] = document
                    if document["kind"] == "requirement":
                        for issue in self.list_issues(actor, document["id"]):
                            issues[issue["id"]] = issue
                else:
                    issue = self.get_issue(target["id"])
                    issues[issue["id"]] = issue
            except NotFound:
                continue
        return {
            "system": system,
            "external_id": external_id,
            "links": links,
            "documents": list(documents.values()),
            "issues": list(issues.values()),
        }

    def create_requirement_from_external(
        self,
        actor: str,
        system: str,
        external_id: str,
        request_id: str,
        title: str,
        outcome: str,
        scope: str,
        acceptance: str,
        tickets: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """从天枢工单创建天璇需求与工单树，并建立外部绑定。"""
        requirement = self.create_requirement(actor, request_id, title, outcome, scope, acceptance)
        if tickets:
            self.plan_tickets(actor, requirement["id"], tickets)
        link = self.link_external(actor, system, external_id, "doc", requirement["id"])
        return {
            "requirement": requirement,
            "issues": self.list_issues(actor, requirement["id"]),
            "link": link,
        }

    # ---------- 跨系统：身份适配 ----------

    def link_identity(self, actor: str, provider: str, subject: str, user_id: str) -> dict[str, Any]:
        """管理员把外部身份（provider + subject）绑定到本地用户。"""
        if self.role_of(actor) != "admin":
            raise PermissionDenied("only admin can bind external identities")
        provider = provider.strip()
        subject = subject.strip()
        if not provider or not subject:
            raise TianxuanError("provider and subject are required")
        tenant_id = self._tenant_of(actor)
        user = self.db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None or user["tenant_id"] != tenant_id:
            raise NotFound(f"user not found: {user_id}")
        existing = self.db.execute(
            "SELECT * FROM identity_links WHERE provider = ? AND subject = ?",
            (provider, subject),
        ).fetchone()
        now = _now()
        if existing is not None:
            if existing["tenant_id"] != tenant_id:
                raise PermissionDenied("external identity is bound to another tenant")
            if existing["user_id"] != user_id:
                self.db.execute(
                    "UPDATE identity_links SET tenant_id = ?, user_id = ?, updated_at = ? WHERE id = ?",
                    (tenant_id, user_id, now, existing["id"]),
                )
                self._event(
                    tenant_id,
                    "identity.relinked",
                    actor,
                    existing["id"],
                    {"provider": provider, "subject": subject, "user_id": user_id},
                )
                self.db.commit()
            return self.get_identity_link(existing["id"])
        link_id = _id("idn")
        self.db.execute(
            "INSERT INTO identity_links (id, tenant_id, provider, subject, user_id, created_by, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (link_id, tenant_id, provider, subject, user_id, actor, now, now),
        )
        self._event(
            tenant_id,
            "identity.linked",
            actor,
            link_id,
            {"provider": provider, "subject": subject, "user_id": user_id},
        )
        self.db.commit()
        return self.get_identity_link(link_id)

    def get_identity_link(self, link_id: str) -> dict[str, Any]:
        row = self.db.execute("SELECT * FROM identity_links WHERE id = ?", (link_id,)).fetchone()
        if row is None:
            raise NotFound(f"identity link not found: {link_id}")
        return dict(row)

    def rebind_identity(self, actor: str, link_id: str, user_id: str) -> dict[str, Any]:
        if self.role_of(actor) != "admin":
            raise PermissionDenied("only admin can rebind external identities")
        tenant_id = self._tenant_of(actor)
        link = self.get_identity_link(link_id)
        if link["tenant_id"] != tenant_id:
            raise NotFound(f"identity link not found: {link_id}")
        user = self.db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None or user["tenant_id"] != tenant_id:
            raise NotFound(f"user not found: {user_id}")
        if link["user_id"] == user_id:
            return link
        now = _now()
        self.db.execute(
            "UPDATE identity_links SET user_id = ?, updated_at = ? WHERE id = ?",
            (user_id, now, link_id),
        )
        self._event(
            tenant_id,
            "identity.rebound",
            actor,
            link_id,
            {"provider": link["provider"], "subject": link["subject"], "user_id": user_id},
        )
        self.db.commit()
        return self.get_identity_link(link_id)

    def unlink_identity(self, actor: str, link_id: str) -> dict[str, Any]:
        if self.role_of(actor) != "admin":
            raise PermissionDenied("only admin can unbind external identities")
        tenant_id = self._tenant_of(actor)
        link = self.get_identity_link(link_id)
        if link["tenant_id"] != tenant_id:
            raise NotFound(f"identity link not found: {link_id}")
        self.db.execute("DELETE FROM identity_links WHERE id = ?", (link_id,))
        self._event(
            tenant_id,
            "identity.unlinked",
            actor,
            link_id,
            {"provider": link["provider"], "subject": link["subject"], "user_id": link["user_id"]},
        )
        self.db.commit()
        return {"deleted": link_id}

    def list_identity_links(
        self, actor: str, provider: str | None = None, subject: str | None = None
    ) -> list[dict[str, Any]]:
        if self.role_of(actor) != "admin":
            raise PermissionDenied("only admin can list external identities")
        tenant_id = self._tenant_of(actor)
        sql = "SELECT * FROM identity_links WHERE tenant_id = ?"
        args: list[Any] = [tenant_id]
        if provider:
            sql += " AND provider = ?"
            args.append(provider)
        if subject:
            sql += " AND subject = ?"
            args.append(subject)
        rows = self.db.execute(sql + " ORDER BY created_at, id", args).fetchall()
        return [dict(row) for row in rows]

    def resolve_identity(self, provider: str, subject: str) -> dict[str, Any]:
        """按适配器已校验的外部身份解析本地用户；不在此处校验凭据。"""
        row = self.db.execute(
            "SELECT il.*, u.email, u.name FROM identity_links il JOIN users u ON u.id = il.user_id "
            "WHERE il.provider = ? AND il.subject = ?",
            (provider.strip(), subject.strip()),
        ).fetchone()
        if row is None:
            raise NotFound(f"external identity is not linked: {provider}/{subject}")
        return dict(row)

    @_connection_call
    def identity_subject_for_user(self, user_id: str, provider: str) -> str:
        """返回用户绑定的外部身份 subject（如 Gitea 用户名）；未绑定抛 ``NotFound``。"""
        if not isinstance(provider, str) or not provider.strip():
            raise TianxuanError("provider must be a non-empty string")
        row = self.db.execute(
            "SELECT subject FROM identity_links WHERE provider = ? AND user_id = ? ORDER BY updated_at DESC LIMIT 1",
            (provider.strip(), user_id),
        ).fetchone()
        if row is None:
            raise NotFound(f"no {provider} identity linked to user: {user_id}")
        return str(row["subject"])

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
        role = self.role_of(actor)
        sql = "SELECT type, actor, target, payload, created_at FROM events WHERE tenant_id = ?"
        args: list[Any] = [tenant_id]
        if role != "admin":
            sql += " AND type NOT LIKE 'identity.%'"
        sql += " ORDER BY created_at DESC, rowid DESC LIMIT ?"
        args.append(max(1, min(int(limit), 500)))
        rows = self.db.execute(sql, args).fetchall()
        return [dict(row) | {"payload": json.loads(row["payload"])} for row in rows]

    def identity_events(self, actor: str, limit: int = 50, event_type: str | None = None) -> list[dict[str, Any]]:
        if self.role_of(actor) != "admin":
            raise PermissionDenied("only admin can read identity events")
        if event_type is not None and not event_type.startswith("identity."):
            raise ValueError(f"not an identity event type: {event_type}")
        tenant_id = self._tenant_of(actor)
        sql = (
            "SELECT type, actor, target, payload, created_at FROM events WHERE tenant_id = ? AND type LIKE 'identity.%'"
        )
        args: list[Any] = [tenant_id]
        if event_type:
            sql += " AND type = ?"
            args.append(event_type)
        sql += " ORDER BY created_at DESC, rowid DESC LIMIT ?"
        args.append(max(1, min(int(limit), 200)))
        rows = self.db.execute(sql, args).fetchall()
        return [dict(row) | {"payload": json.loads(row["payload"])} for row in rows]

    def prune_events(self, actor: str, older_than_days: int = 90, type_prefix: str | None = None) -> int:
        if self.role_of(actor) != "admin":
            raise PermissionDenied("only admin can prune events")
        tenant_id = self._tenant_of(actor)
        return self._delete_events(tenant_id, older_than_days, type_prefix)

    def prune_all_events(self, older_than_days: int = 90, type_prefix: str | None = None) -> int:
        return self._delete_events(None, older_than_days, type_prefix)

    # ------------------------------------------------------------------
    # 仓库绑定（webhook 与仓库元数据的租户映射）
    # ------------------------------------------------------------------
    @_connection_call
    def bind_repo(self, actor: str, provider: str, owner: str, name: str) -> dict[str, Any]:
        """把外部仓库绑定到当前租户；同一 ``provider/owner/name`` 全局唯一。"""
        if self.role_of(actor) != "admin":
            raise PermissionDenied("only admin can bind repositories")
        provider = _validate_repo_provider(provider)
        owner = _validate_repo_segment(owner, "owner")
        name = _validate_repo_segment(name, "name")
        tenant_id = self._tenant_of(actor)
        link_id = _id("repo")
        try:
            self.db.execute(
                "INSERT INTO repo_links (id, tenant_id, provider, owner, name, created_by, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (link_id, tenant_id, provider, owner, name, actor, _now()),
            )
        except sqlite3.IntegrityError as error:
            raise TianxuanError(f"repository is already linked: {provider}/{owner}/{name}") from error
        self._event(
            tenant_id,
            "repo.linked",
            actor,
            f"{provider}/{owner}/{name}",
            {"provider": provider, "owner": owner, "name": name},
        )
        return {
            "id": link_id,
            "tenant_id": tenant_id,
            "provider": provider,
            "owner": owner,
            "name": name,
            "created_by": actor,
        }

    @_connection_call
    def list_repo_links(self, actor: str) -> list[dict[str, Any]]:
        tenant_id = self._tenant_of(actor)
        rows = self.db.execute(
            "SELECT id, provider, owner, name, created_by, created_at FROM repo_links "
            "WHERE tenant_id = ? ORDER BY created_at, id",
            (tenant_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    @_connection_call
    def unbind_repo(self, actor: str, link_id: str) -> dict[str, Any]:
        if self.role_of(actor) != "admin":
            raise PermissionDenied("only admin can unbind repositories")
        tenant_id = self._tenant_of(actor)
        row = self.db.execute(
            "SELECT provider, owner, name FROM repo_links WHERE id = ? AND tenant_id = ?",
            (link_id, tenant_id),
        ).fetchone()
        if row is None:
            raise NotFound(f"repository link not found: {link_id}")
        target = f"{row['provider']}/{row['owner']}/{row['name']}"
        self.db.execute("DELETE FROM repo_links WHERE id = ? AND tenant_id = ?", (link_id, tenant_id))
        self._event(tenant_id, "repo.unlinked", actor, target, {"provider": row["provider"]})
        return {"id": link_id, "deleted": True}

    @_connection_call
    def tenant_for_repo(self, provider: str, owner: str, name: str) -> str | None:
        """供 webhook 解析仓库所属租户；未绑定返回 ``None``。"""
        provider = _validate_repo_provider(provider)
        owner = _validate_repo_segment(owner, "owner")
        name = _validate_repo_segment(name, "name")
        row = self.db.execute(
            "SELECT tenant_id FROM repo_links WHERE provider = ? AND owner = ? AND name = ?",
            (provider, owner, name),
        ).fetchone()
        return str(row["tenant_id"]) if row is not None else None

    @_connection_call
    def record_repo_event(self, tenant_id: str, event_type: str, target: str, payload: dict[str, Any]) -> None:
        """记录来自 Git 服务的仓库事件；webhook 已校验签名并由调用方解析租户。"""
        if not isinstance(event_type, str) or not event_type.startswith("repo."):
            raise TianxuanError(f"invalid repository event type: {event_type!r}")
        self._event(tenant_id, event_type, "gitea:webhook", target, payload)

    @_connection_call
    def record_actor_event(self, actor: str, event_type: str, target: str, payload: dict[str, Any]) -> None:
        """以操作者身份记录事件；供合入队列等宿主组件写入审计回执。"""
        if not isinstance(event_type, str) or not event_type:
            raise TianxuanError("event type must be a non-empty string")
        self._event(self._tenant_of(actor), event_type, actor, target, payload)

    @_connection_call
    def ping(self) -> bool:
        """轻量健康检查：确认数据库连接仍可读。"""
        row = self.db.execute("SELECT 1").fetchone()
        return row is not None

    def _delete_events(self, tenant_id: str | None, older_than_days: int, type_prefix: str | None) -> int:
        days = max(0.0, float(older_than_days))
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        sql = "DELETE FROM events WHERE created_at < ?"
        args: list[Any] = [cutoff]
        if tenant_id is not None:
            sql += " AND tenant_id = ?"
            args.append(tenant_id)
        if type_prefix:
            sql += " AND type LIKE ?"
            args.append(f"{type_prefix}%")
        with self.db:
            deleted = self.db.execute(sql, args).rowcount
        return int(deleted)

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
            if (
                payload["to_status"] == "done"
                and self.db.execute(
                    "SELECT 1 FROM native_managed_issues WHERE issue_id=?", (payload["issue_id"],)
                ).fetchone()
            ):
                raise TransitionRejected("native managed completion requires trusted workflow acceptance")
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
