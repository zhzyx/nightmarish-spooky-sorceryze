"""Read published history at a pinned native revision. The disposable index contains summaries and blob pointers."""

import hashlib
import io
import json
import re
import sqlite3
from collections import Counter
from contextlib import closing, contextmanager
from pathlib import Path

from importer import BLOCK_SIZE, NativeStore, canonical, digest
from migration_status import _connect, _exists, _status

ATTACHMENT_LIMIT = 8 * 1024 * 1024
SUMMARY = "r.source_id,r.kind,r.title,r.number,r.path"
COMMENT_KINDS = ("issue_comment", "review_comment", "commit_comment", "review")


def _blob(db, tenant, sha, limit=None):
    if limit is not None:
        size = db.execute(
            "SELECT length(content) FROM native_blobs WHERE tenant=? AND digest=?", (tenant, sha)
        ).fetchone()
        if not size or size[0] > limit:
            raise ValueError("Archive block unavailable or exceeds size limit")
    row = db.execute("SELECT content FROM native_blobs WHERE tenant=? AND digest=?", (tenant, sha)).fetchone()
    if row is None or digest(row[0]) != sha:
        raise ValueError("Native object integrity failure")
    return row[0]


@contextmanager
def _published(database, tenant, project, revision):
    with closing(_connect(database, "ro")) as db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN")
        status = _status(db, tenant, project) if _exists(db, "migration_publications") else None
        if not status or status["revision"] != revision:
            raise LookupError("Publication or revision unavailable")
        catalog = json.loads(_blob(db, tenant, status["catalog_sha256"]))
        yield db, catalog


def _comment_owners(kind, content, source):
    """Return structural parents from provider fields, independently of Markdown cross-references."""
    prefix = f"github:{source}/"
    api = re.escape(f"https://api.github.com/repos/{source}/")
    web = re.escape(f"https://github.com/{source}/")
    owners = set()
    if kind == "commit_comment":
        oid = content.get("commit_id") or ""
        if re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", oid):
            owners.add(prefix + "commit/" + oid)
    elif kind == "issue_comment":
        match = re.fullmatch(api + r"issues/([0-9]+)", content.get("issue_url") or "", re.I)
        if match:
            # GitHub uses the issue URL for both ordinary issues and PR conversations.
            owners.update(prefix + role + "/" + match[1] for role in ("issue", "pull"))
    elif kind in ("review", "review_comment"):
        match = re.fullmatch(api + r"pulls/([0-9]+)", content.get("pull_request_url") or "", re.I)
        if not match:
            match = re.fullmatch(web + r"pull/([0-9]+)(?:/files)?(?:#[^/]*)?", content.get("url") or "", re.I)
        if match:
            owners.add(prefix + "pull/" + match[1])
        if kind == "review_comment":
            for field, role in (("pull_request_review_id", "review"), ("in_reply_to_id", "review_comment")):
                identifier = str(content.get(field))
                if identifier.isascii() and identifier.isdecimal():
                    owners.add(prefix + role + "/" + identifier)
    return owners


def _build(index, db, tenant, catalog, database, project, revision):
    index.execute(
        "CREATE TABLE records(source_id TEXT PRIMARY KEY, kind TEXT, title TEXT, number INTEGER, path TEXT, blob TEXT)"
    )
    index.execute(
        "CREATE TABLE edges(target TEXT, source_id TEXT, owned INTEGER, PRIMARY KEY(target, source_id)) WITHOUT ROWID"
    )
    checksum = hashlib.sha256()
    counts = Counter()
    documents = {}
    for batch in catalog["record_batches"]:
        objects = NativeStore._revision(db, tenant, batch["module"], batch["revision"])["objects"]
        for name in batch["order"]:
            sha = objects[name]
            line = _blob(db, tenant, sha)
            row = json.loads(line)
            sid, kind, content = row["source_id"], row["kind"], row["content"]
            if (
                digest(sid.encode()) != name
                or row["mode"] != "record_only"
                or digest(canonical(content)) != row["sha256"]
            ):
                raise ValueError("Invalid archive record")
            checksum.update(line)
            counts[kind] += 1
            path = content.get("path") or ""
            if kind == "requirement" and path.lower().endswith((".md", ".markdown")) and content.get("blob"):
                documents[path] = content["blob"]
            title = content.get("title") or path or sid
            index.execute(
                "INSERT INTO records VALUES(?,?,?,?,?,?)",
                (sid, kind, title[:512], content.get("number"), path[:2048], sha),
            )
            owners = _comment_owners(kind, content, catalog["report"]["source"])
            index.executemany(
                "INSERT INTO edges VALUES(?,?,?)", ((target, sid, target in owners) for target in set(row["relations"]))
            )
    if checksum.hexdigest() != catalog["report"]["records_sha256"] or dict(counts) != catalog["report"]["counts"]:
        raise ValueError("Inventory stream does not match published catalog")
    report = catalog["report"]
    if documents and f"github:{report['source']}/history.bundle" in catalog["binaries"]:
        from history_git import requirement_titles

        titles = requirement_titles(database, tenant, project, revision, report["revision"], documents)
        index.executemany(
            "UPDATE records SET title=? WHERE kind='requirement' AND path=?",
            ((title[:512], path) for path, title in titles.items()),
        )
    index.execute("CREATE INDEX records_kind ON records(kind,source_id)")
    index.execute("CREATE INDEX records_number ON records(number)")


@contextmanager
def _index(database, tenant, project, revision, db, catalog):
    base = Path(database).resolve()
    folder = base.with_name(base.name + ".history-index")
    folder.mkdir(mode=0o700, exist_ok=True)
    path = folder / (digest(canonical([3, tenant, project, revision])) + ".sqlite")
    if path.is_file():
        with closing(_connect(path, "ro")) as index:
            if _exists(index, "records"):
                index.row_factory = sqlite3.Row
                yield index
                return
    with closing(sqlite3.connect(path, timeout=120)) as index:
        index.execute("BEGIN IMMEDIATE")
        if not _exists(index, "records"):
            _build(index, db, tenant, catalog, database, project, revision)
        index.commit()
        index.execute("PRAGMA query_only=ON")
        index.row_factory = sqlite3.Row
        yield index


def _page(offset, limit):
    if type(offset) is not int or type(limit) is not int or not 0 <= offset < 2**63 or not 1 <= limit <= 100:
        raise ValueError("Expected nonnegative offset and page size 1..100")


def search_records(database, tenant, project, revision, query="", kind=None, offset=0, limit=50):
    _page(offset, limit)
    if not isinstance(query, str) or len(query) > 512:
        raise ValueError("Invalid history search")
    with (
        _published(database, tenant, project, revision) as (db, catalog),
        _index(database, tenant, project, revision, db, catalog) as index,
    ):
        filters = []
        params = []
        if kind:
            filters.append("r.kind=?")
            params.append(kind)
        value = query.strip()
        number = value.removeprefix("#")
        if number.isascii() and number.isdecimal() and len(number) <= 18:
            filters.append("r.number=?")
            params.append(int(number))
        elif value:
            filters.append(
                "(instr(lower(r.title),lower(?)) OR instr(lower(r.path),lower(?)) OR instr(lower(r.source_id),lower(?)))"
            )
            params.extend([value, value, value])
        table = " FROM records r" + (" WHERE " + " AND ".join(filters) if filters else "")
        total = index.execute("SELECT count(*)" + table, params).fetchone()[0]
        rows = index.execute(
            "SELECT " + SUMMARY + table + " ORDER BY r.source_id LIMIT ? OFFSET ?", [*params, limit, offset]
        )
        return dict(items=[dict(r) for r in rows], total=total, offset=offset, limit=limit, revision=revision)


def _bounded_record(raw, budget):
    row = json.loads(raw)
    if len(raw) <= budget:
        return row
    content = row["content"]
    # Expose a bounded preview, retaining the digest of the full archived content.
    preview = {k: content[k] for k in ("number", "state") if k in content}
    for k in ("title", "path", "body"):
        if isinstance(content.get(k), str):
            preview[k] = content[k].encode()[: budget // 4].decode("utf8", errors="ignore")
    return dict(
        source_id=row["source_id"],
        kind=row["kind"],
        mode=row["mode"],
        sha256=row["sha256"],
        content=preview,
        relations=row["relations"][:32],
        truncated=True,
    )


def record_detail(database, tenant, project, revision, source_id, offset=0, limit=50):
    _page(offset, limit)
    with (
        _published(database, tenant, project, revision) as (db, catalog),
        _index(database, tenant, project, revision, db, catalog) as index,
    ):
        row = index.execute("SELECT blob FROM records WHERE source_id=?", (source_id,)).fetchone()
        if not row:
            raise LookupError("Record unavailable")
        record = _bounded_record(_blob(db, tenant, row[0]), 64 * 1024)
        table = " FROM edges e JOIN records r ON r.source_id=e.source_id WHERE e.target=?"

        def related(comments):
            sql = table + (" AND e.owned=1" if comments else "")
            params = [source_id]
            total = index.execute("SELECT count(*)" + sql, params).fetchone()[0]
            cols = "r.blob" if comments else SUMMARY
            rows = index.execute(
                "SELECT " + cols + sql + " ORDER BY r.source_id LIMIT ? OFFSET ?", [*params, limit, offset]
            )
            items = [_bounded_record(_blob(db, tenant, r[0]), 4096) if comments else dict(r) for r in rows]
            return dict(items=items, total=total, offset=offset, limit=limit)

        return dict(record=record, comments=related(True), reverse=related(False), revision=revision)


def _copy_binary(db, tenant, catalog, source_id, output, max_bytes=None):
    binary = catalog["binaries"].get(source_id)
    if binary is None:
        raise LookupError("Binary unavailable")
    checksum = hashlib.sha256()
    size = 0
    for block in binary["blocks"]:
        sha = NativeStore._revision(db, tenant, block["module"], block["revision"])["objects"]["bytes"]
        limit = BLOCK_SIZE if max_bytes is None else min(BLOCK_SIZE, max_bytes - size)
        data = _blob(db, tenant, sha, limit)
        output.write(data)
        size += len(data)
        checksum.update(data)
    if checksum.hexdigest() != binary["sha256"]:
        raise ValueError("Archive binary checksum mismatch")
    return {"sha256": binary["sha256"], "size": size}


def export_binary(database, tenant, project, revision, source_id, destination):
    """Host-owned new path in a private directory. A failed export removes only its own partial file."""
    with _published(database, tenant, project, revision) as (db, catalog):
        path = Path(destination)
        stream = path.open("xb")
        try:
            with stream:
                return _copy_binary(db, tenant, catalog, source_id, stream)
        except BaseException:
            path.unlink(missing_ok=True)
            raise


def read_attachment(database, tenant, project, revision, source_id, max_bytes=ATTACHMENT_LIMIT):
    if type(max_bytes) is not int or not 0 <= max_bytes <= ATTACHMENT_LIMIT:
        raise ValueError("Invalid attachment limit")
    with (
        _published(database, tenant, project, revision) as (db, catalog),
        _index(database, tenant, project, revision, db, catalog) as index,
    ):
        if not index.execute("SELECT 1 FROM records WHERE source_id=? AND kind='attachment'", (source_id,)).fetchone():
            raise LookupError("Attachment unavailable")
        stream = io.BytesIO()
        _copy_binary(db, tenant, catalog, source_id, stream, max_bytes)
        return stream.getvalue()


def read_body(database, tenant, project, revision, source_id, offset=0, limit=16384):
    """Return an exact slice of the original issue, pull or comment text, measured in Unicode code points."""
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 16384:
        raise ValueError("Expected a nonnegative character offset and limit 1..16384")
    with (
        _published(database, tenant, project, revision) as (db, catalog),
        _index(database, tenant, project, revision, db, catalog) as index,
    ):
        hit = index.execute("SELECT kind,blob FROM records WHERE source_id=?", (source_id,)).fetchone()
        if not hit:
            raise LookupError("Record unavailable")
        if hit["kind"] not in ("issue", "pull", "pull_issue_projection", *COMMENT_KINDS):
            raise ValueError("This record has no conversation body")
        row = json.loads(_blob(db, tenant, hit["blob"]))
        body = row["content"].get("body")
        if body is None:
            body = ""
        if not isinstance(body, str):
            raise ValueError("Invalid archived body")
        end = min(offset + limit, len(body))
        return dict(
            source_id=source_id, text=body[offset:end], total=len(body), next_offset=end if end < len(body) else None
        )
