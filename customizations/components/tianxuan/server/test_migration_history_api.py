"""Verify published history through authenticated Web and AI transports."""

import base64
import hashlib
import json
import os
import subprocess

from api import create_app
from fastapi.testclient import TestClient
from native_store import NativeStore
from tianxuan_core import Tianxuan


def test_published_history_transport(tmp_path):
    store = Tianxuan(":memory:")
    db = tmp_path / "history.sqlite"
    client = TestClient(create_app(store, native_store=NativeStore(db)))
    from importer import canonical, import_inventory
    from migration_status import publish_import

    actor = store.register("owners", "owner@test.invalid", "test-password")["user_id"]
    outsider = store.register("others", "other@test.invalid", "test-password")["user_id"]
    tenant = store.actor_context(actor)["tenant"]
    sid = "github:sample/repo/attachment/123"
    content = {"url": "https://github.com/user-attachments/assets/sample"}
    data = (
        canonical(
            dict(
                kind="attachment",
                source_id=sid,
                mode="record_only",
                relations=[],
                content=content,
                sha256=hashlib.sha256(canonical(content)).hexdigest(),
            )
        )
        + b"\n"
    )
    (tmp_path / "records.jsonl").write_bytes(data)
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            dict(
                source="sample/repo",
                revision="sample",
                counts={"attachment": 1},
                records_sha256=hashlib.sha256(data).hexdigest(),
                historical_policy="record_only",
            )
        )
    )
    payload = bytes(range(256)) * 225
    file = tmp_path / "original.bin"
    file.write_bytes(payload)
    receipt = import_inventory(report, db, tenant, actor, artifacts={sid: (file, hashlib.sha256(payload).hexdigest())})
    publish_import(db, tenant, "example", actor, receipt["module"], receipt["revision"])
    options = {"project": "example", "source_id": sid}
    base = "/api/v1/migration/history/"
    headers = {"X-Actor": actor}

    def tool(name, args, who=actor):
        return client.post(
            "/api/v1/tools", headers={"X-Actor": who}, json={"name": "migration.history." + name, "payload": args}
        )

    assert client.get(base + "attachment", params=options, headers=headers).content == payload
    first = tool("attachment", options).json()
    second = tool("attachment", {**options, "byte_offset": first["next_offset"]}).json()
    assert base64.b64decode(first["data"]) + base64.b64decode(second["data"]) == payload
    args = {"project": "example", "kind": "attachment"}
    assert client.get(base + "search", params=args, headers=headers).json() == tool("search", args).json()
    assert client.get(base + "attachment", params=options, headers={"X-Actor": outsider}).status_code == 404
    assert tool("attachment", options, outsider).status_code == 404
    assert client.get(base + "detail", params={**options, "revision": "0" * 64}, headers=headers).status_code == 404
    assert store.list_issues(actor) == []


def test_published_merge_mapping(tmp_path):
    store = Tianxuan(":memory:")
    db = tmp_path / "history.sqlite"
    client = TestClient(create_app(store, native_store=NativeStore(db)))
    from importer import import_inventory
    from migration_status import publish_import

    actor = store.register("owners", "owner@test.invalid", "test-password")["user_id"]
    tenant = store.actor_context(actor)["tenant"]
    work = tmp_path / "source"
    work.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="Source Author",
        GIT_AUTHOR_EMAIL="author@example.invalid",
        GIT_AUTHOR_DATE="2026-11-18T09:15:30+05:30",
        GIT_COMMITTER_NAME="Merge Operator",
        GIT_COMMITTER_EMAIL="merge@example.invalid",
        GIT_COMMITTER_DATE="2026-11-19T07:00:00-04:00",
    )

    def git(*args):
        return subprocess.check_output(["git", "-C", str(work), *args], env=env).decode().strip()

    git("init", "-q", "-b", "main", "--object-format=sha1")
    (work / "base").write_bytes(b"root\n")
    git("add", "base")
    root = git("commit-tree", git("write-tree"), "-m", "root")
    (work / "left").write_bytes(b"left\n")
    git("add", "left")
    left = git("commit-tree", git("write-tree"), "-p", root, "-m", "left")
    git("read-tree", root)
    (work / "right").write_bytes(b"right\n")
    git("add", "right")
    right = git("commit-tree", git("write-tree"), "-p", root, "-m", "right")
    git("add", "left")
    tree = git("write-tree")
    merge = git("commit-tree", tree, "-p", left, "-p", right, "-m", "merge")
    git("update-ref", "refs/heads/main", merge)
    bundle = tmp_path / "history.bundle"
    git("bundle", "create", str(bundle), "--all")
    (tmp_path / "records.jsonl").write_bytes(b"")
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            dict(
                source="sample/repo",
                revision=merge,
                counts={},
                records_sha256=hashlib.sha256(b"").hexdigest(),
                historical_policy="record_only",
            )
        )
    )
    receipt = import_inventory(
        report,
        db,
        tenant,
        actor,
        artifacts={
            "github:sample/repo/history.bundle": (bundle, hashlib.sha256(bundle.read_bytes()).hexdigest()),
        },
    )
    publish_import(db, tenant, "demo", actor, receipt["module"], receipt["revision"])
    base = "/api/v1/migration/history/commit"
    headers = {"X-Actor": actor}
    query = {"project": "demo", "revision": receipt["revision"], "commit": merge}
    response = client.get(base, headers=headers, params=query)
    assert response.status_code == 200
    assert response.json() == {
        "source_id": f"github:sample/repo/commit/{merge}",
        "oid": merge,
        "parents": [left, right],
        "tree": tree,
        "author": {"name": "Source Author", "email": "author@example.invalid", "time": "2026-11-18T09:15:30+05:30"},
        "committer": {"name": "Merge Operator", "email": "merge@example.invalid", "time": "2026-11-19T07:00:00-04:00"},
        "tenant": tenant,
        "project": "demo",
        "module": receipt["module"],
        "revision": receipt["revision"],
    }
    tool = client.post("/api/v1/tools", headers=headers, json={"name": "migration.history.commit", "payload": query})
    assert tool.status_code == 200 and tool.json() == response.json()
    for oid, parents in ((left, [root]), (right, [root]), (root, [])):
        record = client.get(base, headers=headers, params={**query, "commit": oid}).json()
        assert record["oid"] == oid and record["parents"] == parents
    for param, value, code in (("commit", "main", 422), ("commit", tree, 422), ("revision", "0" * 64, 404)):
        assert client.get(base, headers=headers, params={**query, param: value}).status_code == code
    outsider = store.register("others", "other@test.invalid", "test-password")["user_id"]
    assert client.get(base, headers={"X-Actor": outsider}, params=query).status_code == 404
