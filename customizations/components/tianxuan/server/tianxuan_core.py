"""天璇领域核心（可独立验证的最小切片）。

覆盖：租户/注册登录、文曲 Markdown 文档与版本、偃师需求文档、
司南工单与状态机、事件流、AI 只读机器视图与工具入口。

持久化使用标准库 sqlite3，作为测试与嵌入式存储；
生产适配器（FastAPI + PostgreSQL）在后续切片接入，不改变本层语义。
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

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
CREATE TABLE IF NOT EXISTS spaces (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, name TEXT NOT NULL, slug TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS docs (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, space_id TEXT NOT NULL,
  title TEXT NOT NULL, body_md TEXT NOT NULL, lang TEXT NOT NULL DEFAULT 'zh',
  kind TEXT NOT NULL DEFAULT 'doc', request_id TEXT, tags TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'draft', progress TEXT NOT NULL DEFAULT '{}',
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


class Tianxuan:
    """单组织首版的领域服务；方法与 AI 工具一一可测。"""

    def __init__(self, db_path: str = ":memory:"):
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self._migrate_sessions()
        self._migrate_users()
        self.db.commit()

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
            self.db.rollback()
            raise TianxuanError(f"registration rejected: {error}") from error
        self._event(tenant_id, "user.registered", user_id, user_id, {"email": email.lower()})
        self.db.commit()
        return {"tenant_id": tenant_id, "space_id": space_id, "user_id": user_id}

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

    def issue_session(self, user_id: str, ttl_seconds: int = 86_400) -> str:
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
        self.db.commit()
        return token

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
            self.db.commit()
            return None
        return str(row["user_id"])

    def revoke_session(self, token: str) -> bool:
        cursor = self.db.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
        self.db.commit()
        return cursor.rowcount > 0

    def role_of(self, actor: str) -> str:
        row = self.db.execute("SELECT role FROM users WHERE id = ?", (actor,)).fetchone()
        if row is None:
            raise NotFound(f"user not found: {actor}")
        return str(row["role"])

    def _require_editor(self, actor: str) -> None:
        if self.role_of(actor) == "viewer":
            raise PermissionDenied("viewer cannot modify content")

    def list_members(self, actor: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT id, email, name, role FROM users WHERE tenant_id = ? ORDER BY created_at, id",
            (self._tenant_of(actor),),
        ).fetchall()
        return [dict(row) for row in rows]

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
            self.db.rollback()
            raise TianxuanError(f"member rejected: {error}") from error
        self._event(tenant_id, "user.added", actor, user_id, {"role": role})
        self.db.commit()
        return {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "email": email.lower(),
            "name": display_name,
            "role": role,
        }

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
        self.db.commit()
        return {"user_id": user_id, "role": role}

    # ---------- 文曲：文档 ----------

    def create_doc(
        self,
        actor: str,
        title: str,
        body_md: str = "",
        lang: str = "zh",
        kind: str = "doc",
        request_id: str | None = None,
        space_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_editor(actor)
        tenant_id = self._tenant_of(actor)
        space_id = (
            space_id
            or self.db.execute(
                "SELECT id FROM spaces WHERE tenant_id = ? ORDER BY created_at LIMIT 1", (tenant_id,)
            ).fetchone()["id"]
        )
        doc_id = _id("doc")
        now = _now()
        tags = classify(f"{title}\n{body_md}")
        self.db.execute(
            "INSERT INTO docs (id, tenant_id, space_id, title, body_md, lang, kind, request_id, tags, "
            "status, progress, version, created_by, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', '{}', 1, ?, ?, ?)",
            (doc_id, tenant_id, space_id, title, body_md, lang, kind, request_id, json.dumps(tags), actor, now, now),
        )
        self._version(doc_id, 1, body_md, actor)
        self._event(tenant_id, "doc.created", actor, doc_id, {"title": title, "kind": kind})
        self.db.commit()
        return self.get_doc(doc_id)

    def update_doc(
        self,
        actor: str,
        doc_id: str,
        body_md: str,
        expected_version: int,
        title: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        self._require_editor(actor)
        doc = self.get_doc(doc_id)
        if doc["version"] != expected_version:
            raise VersionConflict(f"expected version {expected_version}, found {doc['version']}")
        version = expected_version + 1
        now = _now()
        title = title if title is not None else doc["title"]
        status = status if status is not None else doc["status"]
        self.db.execute(
            "UPDATE docs SET title = ?, body_md = ?, status = ?, tags = ?, version = ?, updated_at = ? WHERE id = ?",
            (title, body_md, status, json.dumps(classify(f"{title}\n{body_md}")), version, now, doc_id),
        )
        self._version(doc_id, version, body_md, actor)
        self._event(doc["tenant_id"], "doc.updated", actor, doc_id, {"version": version})
        self.db.commit()
        return self.get_doc(doc_id)

    def get_doc(self, doc_id: str) -> dict[str, Any]:
        row = self.db.execute("SELECT * FROM docs WHERE id = ?", (doc_id,)).fetchone()
        if row is None:
            raise NotFound(f"doc not found: {doc_id}")
        doc = dict(row)
        doc["tags"] = json.loads(doc["tags"])
        doc["progress"] = json.loads(doc["progress"])
        return doc

    def list_docs(self, actor: str, kind: str | None = None) -> list[dict[str, Any]]:
        tenant_id = self._tenant_of(actor)
        sql = "SELECT id, title, kind, status, tags, version, updated_at FROM docs WHERE tenant_id = ?"
        args: list[str] = [tenant_id]
        if kind:
            sql += " AND kind = ?"
            args.append(kind)
        rows = self.db.execute(sql + " ORDER BY updated_at DESC", args).fetchall()
        return [dict(row) | {"tags": json.loads(row["tags"])} for row in rows]

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

    def versions(self, doc_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT version, author, created_at FROM doc_versions WHERE doc_id = ? ORDER BY version", (doc_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def version(self, doc_id: str, version: int) -> dict[str, Any]:
        row = self.db.execute(
            "SELECT version, body_md, author, created_at FROM doc_versions WHERE doc_id = ? AND version = ?",
            (doc_id, version),
        ).fetchone()
        if row is None:
            raise NotFound(f"version not found: {doc_id}@{version}")
        return dict(row)

    # ---------- 文曲：评论 ----------

    def add_comment(self, actor: str, doc_id: str, body: str, parent_id: str | None = None) -> dict[str, Any]:
        self._require_editor(actor)
        document = self.get_doc(doc_id)
        if not body.strip():
            raise TianxuanError("comment body is required")
        if parent_id is not None:
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
        self.db.commit()
        return self.get_comment(comment_id)

    def get_comment(self, comment_id: str) -> dict[str, Any]:
        row = self.db.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()
        if row is None:
            raise NotFound(f"comment not found: {comment_id}")
        comment = dict(row)
        comment["resolved"] = bool(comment["resolved"])
        return comment

    def list_comments(self, actor: str, doc_id: str) -> list[dict[str, Any]]:
        document = self.get_doc(doc_id)
        rows = self.db.execute(
            "SELECT * FROM comments WHERE tenant_id = ? AND doc_id = ? ORDER BY created_at, id",
            (document["tenant_id"], doc_id),
        ).fetchall()
        return [dict(row) | {"resolved": bool(row["resolved"])} for row in rows]

    def resolve_comment(self, actor: str, comment_id: str, resolved: bool = True) -> dict[str, Any]:
        self._require_editor(actor)
        comment = self.get_comment(comment_id)
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
        self.db.commit()
        return self.get_comment(comment_id)

    # ---------- 偃师：需求文档 ----------

    def create_requirement(
        self, actor: str, request_id: str, title: str, outcome: str, scope: str, acceptance: str, lang: str = "zh"
    ) -> dict[str, Any]:
        body = (
            "---\n"
            f"request_id: {request_id}\nkind: requirement\nlang: {lang}\n---\n\n"
            f"# {title}\n\n## 目标\n\n{outcome}\n\n## 范围\n\n{scope}\n\n## 验收\n\n{acceptance}\n"
        )
        return self.create_doc(actor, title, body, lang=lang, kind="requirement", request_id=request_id)

    # ---------- 司南：工单 ----------

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
    ) -> dict[str, Any]:
        self._require_editor(actor)
        tenant_id = self._tenant_of(actor)
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
        self.db.commit()
        return self.get_issue(issue_id)

    def get_issue(self, issue_id: str) -> dict[str, Any]:
        row = self.db.execute("SELECT * FROM issues WHERE id = ?", (issue_id,)).fetchone()
        if row is None:
            raise NotFound(f"issue not found: {issue_id}")
        return dict(row)

    def list_issues(self, actor: str, requirement_id: str | None = None) -> list[dict[str, Any]]:
        tenant_id = self._tenant_of(actor)
        sql = "SELECT * FROM issues WHERE tenant_id = ?"
        args: list[str] = [tenant_id]
        if requirement_id:
            sql += " AND requirement_id = ?"
            args.append(requirement_id)
        rows = self.db.execute(sql + " ORDER BY number", args).fetchall()
        return [dict(row) for row in rows]

    def transition_issue(self, actor: str, issue_id: str, to_status: str) -> dict[str, Any]:
        self._require_editor(actor)
        issue = self.get_issue(issue_id)
        current = issue["status"]
        if to_status not in ISSUE_TRANSITIONS.get(current, set()):
            raise TransitionRejected(f"{current} -> {to_status} is not allowed")
        self.db.execute("UPDATE issues SET status = ?, updated_at = ? WHERE id = ?", (to_status, _now(), issue_id))
        self._event(issue["tenant_id"], "issue.transitioned", actor, issue_id, {"from": current, "to": to_status})
        self.db.commit()
        if issue["requirement_id"]:
            self.sync_progress(issue["requirement_id"])
        return self.get_issue(issue_id)

    def plan_tickets(self, actor: str, requirement_id: str, tickets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self._require_editor(actor)
        requirement = self.get_doc(requirement_id)
        if requirement["kind"] != "requirement":
            raise TianxuanError("tickets can only be planned from a requirement document")
        parent = self.create_issue(
            actor,
            requirement["title"],
            type="requirement",
            acceptance="全部子工单验收通过",
            requirement_id=requirement_id,
            body_md=f"需求文档：[[{requirement_id}]]",
        )
        created = []
        for ticket in tickets:
            created.append(
                self.create_issue(
                    actor,
                    ticket.get("title", "未命名工单"),
                    type=ticket.get("type", "task"),
                    acceptance=ticket.get("acceptance", ""),
                    priority=ticket.get("priority", "normal"),
                    requirement_id=requirement_id,
                    parent_id=parent["id"],
                )
            )
        self._event(
            requirement["tenant_id"], "requirement.planned", actor, requirement_id, {"issues": len(created) + 1}
        )
        self.db.commit()
        self.sync_progress(requirement_id)
        return [parent, *created]

    def sync_progress(self, requirement_id: str) -> dict[str, Any]:
        issues = self.db.execute("SELECT status FROM issues WHERE requirement_id = ?", (requirement_id,)).fetchall()
        total = len(issues)
        done = sum(1 for row in issues if row["status"] == "done")
        progress = {"total": total, "done": done, "percent": round((done / total) * 100) if total else 0}
        self.db.execute(
            "UPDATE docs SET progress = ?, updated_at = ? WHERE id = ?", (json.dumps(progress), _now(), requirement_id)
        )
        self.db.commit()
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

    def events(self, actor: str, limit: int = 100) -> list[dict[str, Any]]:
        tenant_id = self._tenant_of(actor)
        rows = self.db.execute(
            "SELECT type, actor, target, payload, created_at FROM events WHERE tenant_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (tenant_id, limit),
        ).fetchall()
        return [dict(row) | {"payload": json.loads(row["payload"])} for row in rows]

    def dispatch_tool(self, actor: str, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        tools = {
            "doc.create": lambda p: self.create_doc(
                actor, p.get("title", ""), p.get("body_md", ""), p.get("lang", "zh")
            ),
            "doc.update": lambda p: self.update_doc(actor, p["doc_id"], p["body_md"], p["expected_version"]),
            "doc.read": lambda p: self.ai_view(p["doc_id"]),
            "doc.list": lambda p: {"docs": self.list_docs(actor, p.get("kind"))},
            "requirement.create": lambda p: self.create_requirement(
                actor, p["request_id"], p["title"], p["outcome"], p["scope"], p["acceptance"]
            ),
            "requirement.plan": lambda p: {
                "issues": self.plan_tickets(actor, p["requirement_id"], p.get("tickets", []))
            },
            "issue.create": lambda p: self.create_issue(
                actor,
                p["title"],
                p.get("type", "task"),
                p.get("acceptance", ""),
                p.get("priority", "normal"),
                p.get("requirement_id"),
                p.get("parent_id"),
                p.get("body_md", ""),
            ),
            "issue.transition": lambda p: self.transition_issue(actor, p["issue_id"], p["to_status"]),
            "issue.list": lambda p: {"issues": self.list_issues(actor, p.get("requirement_id"))},
        }
        handler = tools.get(name)
        if handler is None:
            raise UnknownTool(f"unknown tool: {name}")
        return handler(payload)
