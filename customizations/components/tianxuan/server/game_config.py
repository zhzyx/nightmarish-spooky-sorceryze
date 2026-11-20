"""Game configuration projection and live-consumer receipts on the Wenqu store."""

from __future__ import annotations

import time
from typing import Any

from game_config_schema import config_markdown, parse_config, replace_config
from tianxuan_core import NotFound, TianxuanError, _connection_call


def snapshot(doc: dict[str, Any]) -> dict[str, Any]:
    if doc["kind"] != "game_config":
        raise NotFound("game configuration project not found")
    try:
        features = parse_config(doc["body_md"])
    except ValueError as error:
        raise TianxuanError(str(error)) from error
    return {"id": doc["id"], "title": doc["title"], "version": doc["version"], "features": features}


@_connection_call
def read_project(store, actor: str, project_id: str) -> dict[str, Any]:
    return snapshot(store.get_doc_shared(actor, project_id))


@_connection_call
def list_projects(store, actor: str) -> list[dict[str, Any]]:
    result = []
    for row in store.list_docs(actor, kind="game_config"):
        project = read_project(store, actor, row["id"])
        result.append(
            {k: project[k] for k in ("id", "title", "version")}
            | {
                "feature_count": len(project["features"]),
                "entry_count": sum(len(f["entries"]) for f in project["features"]),
            }
        )
    return result


def create_project(store, actor: str, title: str, features) -> dict[str, Any]:
    try:
        body = config_markdown(features)
    except ValueError as error:
        raise TianxuanError(str(error)) from error
    return snapshot(store.create_doc(actor, title=title, body_md=body, kind="game_config"))


@_connection_call
def update_project(store, actor: str, project_id: str, title: str, features, expected_version: int):
    document = store.get_doc_shared(actor, project_id)
    snapshot(document)
    try:
        body = replace_config(document["body_md"], features)
    except ValueError as error:
        raise TianxuanError(str(error)) from error
    return snapshot(store.update_doc(actor, project_id, body, expected_version, title=title))


@_connection_call
def clients(store, actor: str, project_id: str) -> list[dict[str, Any]]:
    project = store.get_doc_shared(actor, project_id)
    if project["kind"] != "game_config":
        raise NotFound("game configuration project not found")
    result = []
    for row in store.db.execute(
        "SELECT * FROM game_config_clients WHERE doc_id=? AND last_seen>? ORDER BY name,id",
        (project_id, time.time() - 35),
    ).fetchall():
        # Recheck the consumer ACL too, so a revoked connection is never advertised as live.
        try:
            store.get_doc_shared(row["actor"], project_id)
        except (NotFound, TianxuanError):
            continue
        result.append({
            "id": row["id"],
            "name": row["name"],
            "version": row["version"],
            "status": row["status"] if row["reported_version"] == project["version"] else "pending",
            "error": row["error"] if row["reported_version"] == project["version"] else "",
            "last_seen": row["last_seen"],
        })
    return result


@_connection_call
def connect_client(store, actor: str, project_id: str, connection: str, name: str) -> None:
    read_project(store, actor, project_id)
    store.db.execute("DELETE FROM game_config_clients WHERE last_seen<?", (time.time() - 300,))
    store.db.execute(
        "INSERT INTO game_config_clients(id,doc_id,actor,name,last_seen) VALUES (?,?,?,?,?)",
        (connection, project_id, actor, name, time.time()),
    )


@_connection_call
def touch_client(store, connection: str) -> None:
    store.db.execute("UPDATE game_config_clients SET last_seen=? WHERE id=?", (time.time(), connection))


@_connection_call
def report_client(store, connection: str, version: int, status: str, error: str) -> None:
    store.db.execute(
        "UPDATE game_config_clients SET version=CASE WHEN ?='applied' THEN ? ELSE version END, "
        "reported_version=?,status=?,error=?,last_seen=? WHERE id=?",
        (status, version, version, status, error, time.time(), connection),
    )


@_connection_call
def disconnect_client(store, connection: str) -> None:
    store.db.execute("DELETE FROM game_config_clients WHERE id=?", (connection,))
