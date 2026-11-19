"""Publish verified native catalog receipts to an explicitly selected tenant/project."""

import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from importer import canonical, digest


def _now():
    return datetime.now(timezone.utc).isoformat()


def _connect(database, mode):
    path = Path(database).resolve()
    return sqlite3.connect(path.as_uri() + "?mode=" + mode, uri=True, timeout=30)


def _catalog(db, tenant, module, revision):
    row = db.execute(
        "SELECT payload FROM native_revisions WHERE tenant=? AND module=? AND id=?", (tenant, module, revision)
    ).fetchone()
    if not row or digest(row[0].encode()) != revision:
        raise ValueError("Unavailable or invalid native catalog revision")
    objects = json.loads(row[0])["objects"]
    if set(objects) != {"catalog.json"} or module != "migration-" + digest(canonical(objects)):
        raise ValueError("Invalid history catalog identity")
    sha = objects["catalog.json"]
    blob = db.execute("SELECT content FROM native_blobs WHERE tenant=? AND digest=?", (tenant, sha)).fetchone()
    if not blob or digest(blob[0]) != sha:
        raise ValueError("Invalid history catalog checksum")
    catalog = json.loads(blob[0])
    report = catalog["report"]
    if catalog["version"] != 1 or report["historical_policy"] != "record_only":
        raise ValueError("Unsupported catalog policy")
    return dict(
        source=report["source"],
        source_revision=report["revision"],
        records_sha256=report["records_sha256"],
        counts=report["counts"],
        binary_count=len(catalog["binaries"]),
        catalog_sha256=sha,
        module=module,
        revision=revision,
        historical_policy="record_only",
    )


def _exists(db, table):
    return bool(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())


def prepare_import(database, tenant, module):
    """Record ownership of timing before the first catalog commit, including interrupted imports."""
    with closing(_connect(database, "rw")) as db, db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "CREATE TABLE IF NOT EXISTS migration_import_times (tenant TEXT, module TEXT, revision TEXT,"
            " imported_at TEXT, PRIMARY KEY(tenant,module,revision))"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS migration_pending_times (tenant TEXT, module TEXT, PRIMARY KEY(tenant,module))"
        )
        if not db.execute("SELECT 1 FROM native_heads WHERE tenant=? AND module=?", (tenant, module)).fetchone():
            db.execute("INSERT OR IGNORE INTO migration_pending_times VALUES(?,?)", (tenant, module))


def stamp_import(database, tenant, module, revision):
    with closing(_connect(database, "rw")) as db, db:
        db.execute("BEGIN IMMEDIATE")
        registered = db.execute(
            "DELETE FROM migration_pending_times WHERE tenant=? AND module=?", (tenant, module)
        ).rowcount
        if registered:
            db.execute(
                "INSERT OR IGNORE INTO migration_import_times VALUES(?,?,?,?)", (tenant, module, revision, _now())
            )


def publish_import(database, tenant, project, actor, module, revision):
    """A trusted operator grants this project visibility of a verified catalog."""
    if not all(isinstance(i, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", i) for i in (tenant, actor)):
        raise ValueError("Invalid publication identity")
    segment = r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}"
    if not isinstance(project, str) or not re.fullmatch(segment + "(?:/" + segment + ")?", project):
        raise ValueError("Invalid publication project")
    with closing(_connect(database, "rw")) as db, db:
        _catalog(db, tenant, module, revision)
        db.execute(
            "CREATE TABLE IF NOT EXISTS migration_publications (id INTEGER PRIMARY KEY, tenant TEXT,"
            " project TEXT, module TEXT, revision TEXT, actor TEXT, published_at TEXT,"
            " UNIQUE(tenant,project,module,revision))"
        )
        db.execute(
            "INSERT OR IGNORE INTO migration_publications(tenant,project,module,revision,actor,published_at)"
            " VALUES(?,?,?,?,?,?)",
            (tenant, project, module, revision, actor, _now()),
        )
        return _status(db, tenant, project, module, revision)


def read_import_status(database, tenant, project):
    """Authenticated host supplies visibility scope. Read only the latest project-bound catalog."""
    with closing(_connect(database, "ro")) as db:
        db.execute("BEGIN")
        if not _exists(db, "migration_publications"):
            return None
        return _status(db, tenant, project)


def _status(db, tenant, project, module=None, revision=None):
    query = "SELECT module,revision,actor,published_at FROM migration_publications WHERE tenant=? AND project=?"
    params = [tenant, project]
    if module is not None:
        query += " AND module=? AND revision=?"
        params.extend((module, revision))
    row = db.execute(query + " ORDER BY id DESC LIMIT 1", params).fetchone()
    if not row:
        return None
    module, revision, actor, published = row
    result = _catalog(db, tenant, module, revision)
    imported = None
    if _exists(db, "migration_import_times"):
        imported = db.execute(
            "SELECT imported_at FROM migration_import_times WHERE tenant=? AND module=? AND revision=?",
            (tenant, module, revision),
        ).fetchone()
    return dict(
        result,
        tenant=tenant,
        project=project,
        published_by=actor,
        published_at=published,
        imported_at=imported[0] if imported else None,
    )
