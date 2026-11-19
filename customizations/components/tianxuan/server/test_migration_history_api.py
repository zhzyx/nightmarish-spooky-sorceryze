"""Verify published history through authenticated Web and AI transports."""

import base64
import hashlib
import json

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
