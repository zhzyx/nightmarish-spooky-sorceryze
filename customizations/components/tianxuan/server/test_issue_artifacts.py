"""I14 reads historical submissions independently of current approvals."""

import hashlib

from api import create_app
from fastapi.testclient import TestClient
from native_store import NativeStore
from tianxuan_core import Tianxuan


def test_selected_revisions_and_live_access(tmp_path):
    store = Tianxuan(str(tmp_path / "domain.db"))
    owner = store.register("Studio", "owner@example.invalid", "password")["user_id"]
    reader = store.add_member(owner, "reader@example.invalid", "password", name="Reader", role="viewer")["user_id"]
    outsider = store.register("Other", "other@example.invalid", "password")["user_id"]
    source = store.create_requirement(owner, "art", "Source", "Goal", "Scope", "Accept")["id"]
    module = store.bind_native_requirement(owner, source)
    gate = store.create_requirement(owner, "game", "Issue ancestor", "Goal", "Scope", "Accept")["id"]
    for req in (source, gate):
        store.set_visibility(owner, req, "private")
        store.share_doc(owner, req, reader, "read")
    parent = store.create_issue(owner, "Parent", project="studio/game", requirement_id=gate)
    issue = store.create_issue(owner, "Child", project="studio/game", parent_id=parent["id"])
    native = NativeStore(tmp_path / "native.db")
    tenant = store.actor_context(owner)["tenant"]
    tokens = {actor: {"Authorization": "Bearer " + store.issue_session(actor)} for actor in (owner, reader, outsider)}
    args = {"headers": tokens[reader], "params": {"project": issue["project"]}}
    url = f"/api/v1/issues/by-number/{issue['number']}/artifacts"
    work = f"/api/v1/issues/{issue['id']}/work"
    path = "art/hero.bin"
    with TestClient(create_app(store, native_store=native)) as client:
        assert client.get(url, **args).json() == {"artifacts": []}
        revisions = []
        for index, (kind, content) in enumerate([("concept", b"first\x00"), ("attachment", b"second\xff")]):
            revision = native.submit(
                tenant,
                owner,
                str(index),
                [dict(module=module, base=revisions[-1] if revisions else None, reads=None, edits={path: content})],
            )["revisions"][module]
            revisions.append(revision)
            ref = dict(kind=kind, module=module, revision=revision, path=path)
            payload = dict(ref, call_id=str(index), expected_version=index)
            posted = client.post(work + "/submit_asset", headers=tokens[owner], json=payload)
            assert posted.status_code == 200, posted.text
            assert client.post(work + "/submit_asset", headers=tokens[owner], json=payload).json() == posted.json()
        refs = client.get(url, **args).json()["artifacts"]
        assert [(r["version"], r["revision"]) for r in refs] == list(reversed(list(enumerate(revisions, 1))))
        for version, content in [(1, b"first\x00"), (2, b"second\xff")]:
            reply = client.get(f"{url}/{version}", **args)
            assert reply.status_code == 200 and reply.content == content
            assert "no-store" in reply.headers["cache-control"]
        assert client.get(url + "/3", **args).status_code == 404
        assert client.get(url + "/1", headers=tokens[reader], params={"project": "another"}).status_code == 404
        assert client.get(url + "/1", headers=tokens[outsider], params=args["params"]).status_code == 404
        assert client.get(url + "/1", params=args["params"]).status_code in (400, 401)
        store.unshare_doc(owner, source, reader)
        assert client.get(url, **args).json() == {"artifacts": []}
        assert client.get(url + "/1", **args).status_code == 403
        store.share_doc(owner, source, reader, "read")
        store.unshare_doc(owner, gate, reader)
        assert client.get(url, **args).status_code == client.get(url + "/1", **args).status_code == 403
        store.share_doc(owner, gate, reader, "read")
        with native._connection(write=True) as db:
            db.execute(
                "DELETE FROM native_blobs WHERE tenant=? AND digest=?",
                (tenant, hashlib.sha256(b"first\x00").hexdigest()),
            )
        assert client.get(url + "/1", **args).status_code == 409
        assert client.get(url + "/2", **args).content == b"second\xff"
    store.db.close()
