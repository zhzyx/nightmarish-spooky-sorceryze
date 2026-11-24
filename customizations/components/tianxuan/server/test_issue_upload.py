"""Check upload recovery, concurrent deduplication and current issue/source permissions."""

import base64
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from api import create_app
from fastapi.testclient import TestClient
from native_api import MAX_OBJECT
from native_store import NativeStore
from tianxuan_core import Tianxuan, VersionConflict


def test_private_upload_and_recovery(tmp_path, monkeypatch):
    database = str(tmp_path / "domain.db")
    store = Tianxuan(database)
    owner = store.register("I18", "owner@example.invalid", "password")["user_id"]
    reader = store.add_member(owner, "reader@example.invalid", "password", name="Reader", role="viewer")["user_id"]
    outsider = store.register("Elsewhere", "other@example.invalid", "password")["user_id"]
    headers = {actor: {"Authorization": "Bearer " + store.issue_session(actor)} for actor in (owner, reader, outsider)}
    req = store.create_requirement(owner, "private", "Private", "Why", "Scope", "Done")["id"]
    store.set_visibility(owner, req, "private")
    store.share_doc(owner, req, reader, "read")
    issue = store.create_issue(owner, "Asset", project="game", requirement_id=req)
    native = NativeStore(tmp_path / "native.db")
    route = f"/api/v1/issues/by-number/{issue['number']}/artifacts"
    options = {"headers": headers[owner], "params": {"project": "game"}}
    payload = {"name": "附件.dat", "content": ""}
    with TestClient(create_app(store, native_store=native)) as client:

        def interrupted(*args):
            raise VersionConflict("test process stopped before issue event")

        with monkeypatch.context() as phase:
            phase.setattr("issue_upload_api._bind", interrupted)
            assert client.post(route, json=payload, **options).status_code == 409
        assert client.get(route, **options).json() == {"artifacts": []}
        with native._connection() as db:
            assert db.execute("SELECT count(*) FROM native_revisions").fetchone()[0] == 1
        ref = client.post(route, json=payload, **options).json()
        assert ref["version"] == 1
        assert client.post(route, json=payload, **options).json() == ref
        raw = f"/api/v1/native/modules/{ref['module']}/revisions/{ref['revision']}/objects/{ref['path']}"
        assert client.get(raw, headers=headers[reader]).status_code == 200
        assert client.get(route + "/1", **options).content == b""
        assert client.post(route, json=payload, params=options["params"], headers=headers[reader]).status_code == 403
        assert client.post(route, json=payload, params=options["params"], headers=headers[outsider]).status_code == 404
        store.unshare_doc(owner, req, reader)
        assert client.get(raw, headers=headers[reader]).status_code == 403
        assert client.get(route + "/1", params=options["params"], headers=headers[reader]).status_code == 403
        for filename in ["../file", "dir/file", "dir\\file", ""]:
            assert client.post(route, json={**payload, "name": filename}, **options).status_code == 422
        large = base64.b64encode(bytes(MAX_OBJECT + 1)).decode("ascii")
        assert client.post(route, json={**payload, "content": large}, **options).status_code == 413
        assert client.post(route, json={**payload, "content": "?"}, **options).status_code == 422
        assert client.post(route, json={**payload, "module": "another"}, **options).status_code == 422
        with native._connection() as db:
            assert db.execute("SELECT count(*) FROM native_revisions").fetchone()[0] == 1
    store.db.close()


def test_concurrent_writers_get_one_reference(tmp_path):
    from issue_upload_api import _upload

    database = str(tmp_path / "domain.db")
    domain = Tianxuan(database)
    owner = domain.register("I18", "owner@example.invalid", "password")["user_id"]
    editor = domain.add_member(owner, "editor@example.invalid", "password", name="Editor", role="editor")["user_id"]
    issue = domain.create_issue(owner, "Parallel", project="game")
    native = NativeStore(tmp_path / "native.db")
    barrier = Barrier(2)

    def upload(actor):
        store = Tianxuan(database)
        storage = NativeStore(native.database)
        store.work_native_store = storage
        try:
            barrier.wait(timeout=10)
            return _upload(store, storage, actor, "game", issue["number"], "same.txt", b"shared")
        finally:
            store.db.close()

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(upload, (owner, editor)))
    assert results[0] == results[1] and results[0]["version"] == 1
    assert domain.db.execute("SELECT count(*) FROM issue_work_events").fetchone()[0] == 1
    with native._connection() as db:
        assert db.execute("SELECT count(*) FROM native_revisions").fetchone()[0] == 1
    other = domain.create_issue(owner, "Same file in another project", project="other")
    domain.work_native_store = native
    other_ref = _upload(domain, native, owner, "other", other["number"], "same.txt", b"shared")
    assert other_ref["version"] == 1 and other_ref["digest"] == results[0]["digest"]
    assert other_ref["module"] != results[0]["module"] and other_ref["revision"] != results[0]["revision"]
    domain.db.close()
