"""Exercise both directions against exact revisions and current access rights."""

from contextlib import closing

from api import create_app
from fastapi.testclient import TestClient
from native_store import NativeStore
from tianxuan_core import Tianxuan

PREFIX = "/api/v1/native"
SCOPE = {"project": "studio/game"}


def test_revision_links_scope_replay_and_revoked_access(tmp_path):
    domain = Tianxuan(str(tmp_path / "issues.db"))
    native = NativeStore(tmp_path / "native.db")
    with closing(domain.db), TestClient(create_app(domain, native_store=native, native_only=True)) as client:
        owner = domain.register("team", "owner@example.invalid", "test-password")
        actor, tenant = owner["user_id"], owner["tenant_id"]
        viewer = domain.add_member(actor, "viewer@example.invalid", "test-password", role="viewer")
        other = domain.register("other", "other@example.invalid", "test-password")
        auth, reader, foreign = [
            {"Authorization": "Bearer " + domain.issue_session(u["user_id"])} for u in (owner, viewer, other)
        ]
        req = domain.create_requirement(actor, "source", "Source", "why", "scope", "done")
        module = domain.bind_native_requirement(actor, req["id"])
        baseline = native.submit(
            tenant, actor, "seed", [{"module": module, "base": None, "reads": None, "edits": {"a": b"one"}}]
        )["revisions"][module]
        later = native.submit(
            tenant, actor, "update", [{"module": module, "base": baseline, "reads": None, "edits": {"a": b"two"}}]
        )["revisions"][module]
        private = domain.create_requirement(actor, "issue", "Restricted issue", "why", "scope", "done")
        one, two = [
            domain.create_issue(actor, title, project=SCOPE["project"], requirement_id=origin)
            for title, origin in (("Visible", None), ("Private", private["id"]))
        ]
        first, second = [f"{PREFIX}/issues/{issue['id']}/revisions" for issue in (one, two)]
        context = f"{PREFIX}/modules/{module}/revisions/{baseline}/issue-context"
        tag = f"{PREFIX}/modules/{module}/tags/review"
        pin = {"module": module, "revision": baseline, "tag": "review"}

        def put(url, body, identity=auth, scope=SCOPE):
            return client.put(url, params=scope, headers=identity, json=body)

        def post(url, body, identity=auth, scope=SCOPE):
            return client.post(url, params=scope, headers=identity, json=body)

        def get(url, identity=auth, scope=SCOPE):
            return client.get(url, params=scope, headers=identity)

        assert put(tag, {"revision": baseline, "expected": None}).json()["revision"] == baseline
        for path in (first, second):
            assert post(path, pin).json() == pin
        assert put(tag, {"revision": later, "expected": None}).status_code == 409
        assert put(tag, {"revision": later, "expected": baseline}).json()["revision"] == later
        assert get(tag).json()["revision"] == later
        assert post(first, pin).json() == pin
        assert get(first).json()["links"] == [pin]
        stale = domain.create_issue(actor, "Stale", project=SCOPE["project"])
        assert post(f"{PREFIX}/issues/{stale['id']}/revisions", pin).status_code == 409
        assert get(context.replace(baseline, later)).json()["issues"] == []
        assert {issue["id"] for issue in get(context, reader).json()["issues"]} == {one["id"], two["id"]}
        assert post(first, pin, reader).status_code == 403
        assert put(tag, {"revision": baseline, "expected": later}, reader).status_code == 403
        assert post(first, {"module": module, "revision": "review"}).status_code == 422
        assert post(first, {"module": module, "revision": "e" * 64}).status_code == 422
        assert get(context, auth, {"project": "studio/other"}).json()["issues"] == []
        assert get(first, auth, {"project": "studio/other"}).status_code == 404
        assert get(first, foreign).status_code in (403, 404)
        assert get(context, foreign).status_code in (403, 404, 422)
        assert get(context, {}).status_code == 401
        domain.set_visibility(actor, private["id"], "private")
        assert [i["id"] for i in get(context, reader).json()["issues"]] == [one["id"]]
        assert get(second, reader).status_code == 403
        domain.set_visibility(actor, req["id"], "private")
        assert get(first, reader).json()["links"] == []
        assert get(context, reader).status_code == 403
        assert get(tag, reader).status_code == 403


def test_identical_native_content_in_two_tenants_does_not_join_issues(tmp_path):
    domain = Tianxuan(str(tmp_path / "issues.db"))
    native = NativeStore(tmp_path / "native.db")
    with closing(domain.db), TestClient(create_app(domain, native_store=native, native_only=True)) as client:
        records = []
        for org in ("alpha", "beta"):
            owner = domain.register(org, f"{org}@example.invalid", "test-password")
            actor = owner["user_id"]
            token = {"Authorization": "Bearer " + domain.issue_session(actor)}
            issue = domain.create_issue(actor, org, project=SCOPE["project"])
            revision = native.submit(
                owner["tenant_id"],
                actor,
                "seed",
                [{"module": "game", "base": None, "reads": None, "edits": {"a": b"1"}}],
            )["revisions"]["game"]
            records.append((token, issue, revision))
        assert records[0][2] == records[1][2]
        revision = records[0][2]
        context = f"{PREFIX}/modules/game/revisions/{revision}/issue-context"
        for token, issue, _ in records:
            path = f"{PREFIX}/issues/{issue['id']}/revisions"
            link = client.post(path, params=SCOPE, headers=token, json={"module": "game", "revision": revision})
            assert link.json() == {"module": "game", "revision": revision, "tag": None}
        for token, issue, _ in records:
            assert client.get(context, params=SCOPE, headers=token).json()["issues"] == [
                {key: issue[key] for key in ("id", "number", "title")}
            ]
