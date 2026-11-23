"""Real authenticated ASGI repository route tests with native and domain DBs."""

import hashlib
import sqlite3

import pytest
from api import create_app
from fastapi.testclient import TestClient
from native_repository import NativeRepository
from native_repository_api import create_native_repository_router, domain_authority
from native_store import NativeStore
from tianxuan_core import Tianxuan

P = "/api/v1/native/repos/gonggong"


def test_production_key_middleware_preserves_verified_identity(tmp_path, monkeypatch):
    domain = Tianxuan(str(tmp_path / "strict-domain.sqlite"))
    owner = domain.register("strict", "owner@example.invalid", "password123")["user_id"]
    monkeypatch.setenv("TIANXUAN_REQUIRE_KEYS", "1")
    monkeypatch.setenv("TIANXUAN_TENANT_ID", domain.actor_context(owner)["tenant"])
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://testserver")
    key = domain.issue_access_key(owner, owner, "fixture")["key"]
    repository = NativeRepository(NativeStore(tmp_path / "strict-native.sqlite"), domain_authority(domain))
    with TestClient(create_app(domain, native_repository=repository)) as client:
        headers = {"Authorization": "Bearer " + key}
        assert client.post(P + "/bootstrap", headers=headers, json={"request_key": "init"}).status_code == 200
        result = client.get(P + "/identity", headers={**headers, "X-Actor": "forged"})
        assert result.status_code == 200 and result.json()["actor"] == owner
        assert client.get(P + "/identity", headers={"X-Actor": owner}).status_code == 401
    domain.db.close()


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.delenv("TIANXUAN_REQUIRE_KEYS", raising=False)
    domain = Tianxuan(str(tmp_path / "domain.db"))
    native = NativeStore(tmp_path / "repository.db")
    repository = NativeRepository(native, domain_authority(domain))
    app = create_app(domain, native_store=native, native_only=True)
    app.include_router(create_native_repository_router(repository))
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={"tenant_name": "RepoOrg", "email": "owner@example.invalid", "password": "password123"},
        )
        assert response.status_code == 200, response.text
        owner = response.json()["user_id"]
        reviewer = domain.add_member(owner, "reviewer@example.invalid", "password123")["user_id"]
        viewer = domain.add_member(owner, "viewer@example.invalid", "password123", role="viewer")["user_id"]
        headers = {
            name: {"Authorization": "Bearer " + domain.issue_session(actor)}
            for name, actor in {"owner": owner, "reviewer": reviewer, "viewer": viewer}.items()
        }
        issue = domain.create_issue(owner, "Native repository acceptance", acceptance="exact reviewed native revision")
        yield client, domain, repository, owner, reviewer, headers, issue["id"]
    domain.db.close()


def prepare(setup):
    client, _, _, _, _, headers, issue = setup
    h = headers["owner"]
    response = client.post(P + "/bootstrap", headers=h, json={"request_key": "init"})
    assert response.status_code == 200, response.text
    response = client.post(
        P + "/branches", headers=h, json={"request_key": "branch", "branch": "codex/task", "revision": None}
    )
    assert response.status_code == 200, response.text
    content = b"ordinary source file"
    digest = hashlib.sha256(content).hexdigest()
    assert client.put(P + "/objects/" + digest, headers=h, content=content).status_code == 200
    response = client.post(
        P + "/commits",
        headers=h,
        json={
            "request_key": "commit",
            "branch": "codex/task",
            "expected": None,
            "manifest": {"README.txt": digest},
            "message": "first",
        },
    )
    assert response.status_code == 200, response.text
    revision = response.json()["revision"]
    response = client.post(
        P + "/candidates",
        headers=h,
        json={
            "request_key": "candidate",
            "source": "codex/task",
            "target": "main",
            "revision": revision,
            "expected": None,
            "issue_id": issue,
        },
    )
    assert response.status_code == 200, response.text
    return response.json(), digest


def approve(setup, candidate):
    client, _, _, _, _, h, _ = setup
    path = P + "/candidates/" + candidate["id"]
    checks = client.post(path + "/checks", headers=h["owner"], json={"request_key": "checks"})
    assert checks.status_code == 200 and checks.json()["state"] == "checked", checks.text
    assert client.post(path + "/checks", headers=h["owner"], json={"request_key": "checks"}).json() == checks.json()
    observed = client.get(path + "/checks", headers=h["reviewer"])
    assert observed.status_code == 200 and observed.json()["state"] == "checked", observed.text
    assert candidate["revision"] in observed.json()["checks"]["repository-integrity"]["log"]
    review = client.post(
        path + "/reviews",
        headers=h["reviewer"],
        json={"request_key": "review", "note": "Reviewed exact immutable candidate"},
    )
    assert review.status_code == 200, review.text
    return review.json()["id"]


def test_authenticated_complete_flow_and_issue_replay(setup):
    client, domain, _, owner, _, h, issue = setup
    candidate, digest = prepare(setup)
    assert client.get(P + "/objects/" + digest, headers=h["viewer"]).content == b"ordinary source file"
    assert client.get(P + "/branches/codex/task", headers=h["owner"]).json()["revision"] == candidate["revision"]
    review = approve(setup, candidate)
    path = P + "/candidates/" + candidate["id"] + "/merge"
    payload = {"request_key": "merge", "review": review}
    response = client.post(path, headers=h["owner"], json=payload)
    assert response.status_code == 200, response.text
    assert response.json() == client.post(path, headers=h["owner"], json=payload).json()
    assert len(domain.list_issue_comments(owner, issue)) == 1
    assert client.get(P + "/branches/main", headers=h["viewer"]).json()["revision"] == candidate["revision"]


def test_permission_fail_closed_and_forged_inputs(setup):
    client, domain, _, owner, reviewer, h, _ = setup
    assert client.get(P + "/branches").status_code == 401
    assert client.get(P + "/branches", headers={"X-Actor": owner}).status_code in {401, 422}
    assert client.post(P + "/bootstrap", headers=h["reviewer"], json={"request_key": "init"}).status_code == 403
    candidate, _ = prepare(setup)
    path = P + "/candidates/" + candidate["id"]
    assert client.get(P + "/branches?tenant=forged", headers=h["owner"]).status_code == 422
    assert client.get(P + "/branches", headers={**h["owner"], "X-Actor": reviewer}).status_code == 422
    assert client.post(path + "/checks", headers=h["viewer"], json={"request_key": "denied"}).status_code == 403
    assert (
        client.post(
            path + "/checks", headers=h["owner"], json={"request_key": "forged", "outcome": "passed"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            P + "/commits",
            headers=h["owner"],
            json={"request_key": "bypass", "branch": "main", "expected": None, "manifest": {}, "message": "bypass"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            path + "/reviews", headers=h["reviewer"], json={"request_key": "early", "note": "review"}
        ).status_code
        == 422
    )
    review = approve(setup, candidate)
    assert (
        client.post(path + "/reviews", headers=h["owner"], json={"request_key": "self", "note": "review"}).status_code
        == 422
    )
    domain.db.execute("UPDATE users SET role='viewer' WHERE id=?", (reviewer,))
    assert (
        client.post(path + "/merge", headers=h["owner"], json={"request_key": "denied", "review": review}).status_code
        == 422
    )
    assert client.get(P + "/branches/main", headers=h["owner"]).json()["revision"] is None
    domain.revoke_session(h["owner"]["Authorization"].split()[1])
    assert client.get(P + "/branches", headers=h["owner"]).status_code == 401


def test_upload_limits_errors_and_foreign_tenant(setup, monkeypatch):
    import native_repository_api

    client, _, repository, _, _, h, _ = setup
    _, digest = prepare(setup)
    monkeypatch.setattr(native_repository_api, "MAX_OBJECT", 2)
    assert client.put(P + "/objects/" + digest, headers=h["owner"], content=b"large").status_code == 413
    other = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "Other", "email": "other@example.invalid", "password": "password123"},
    ).json()
    domain = setup[1]
    foreign = {"Authorization": "Bearer " + domain.issue_session(other["user_id"])}
    assert client.get(P + "/objects/" + digest, headers=foreign).status_code == 422

    def busy(*args):
        error = sqlite3.OperationalError("secret/local/path")
        error.sqlite_errorcode = sqlite3.SQLITE_BUSY
        raise error

    monkeypatch.setattr(repository, "branches", busy)
    result = client.get(P + "/branches", headers=h["owner"])
    assert result.status_code == 503 and result.headers["retry-after"] == "1"
    assert "secret" not in result.text


def test_post_commit_comment_failure_recovers_without_second_merge(setup, monkeypatch):
    client, domain, repository, owner, _, h, issue = setup
    candidate, _ = prepare(setup)
    review = approve(setup, candidate)
    original = domain.add_issue_comment

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("simulated domain failure")

    monkeypatch.setattr(domain, "add_issue_comment", fail)
    path = P + "/candidates/" + candidate["id"] + "/merge"
    payload = {"request_key": "merge", "review": review}
    assert client.post(path, headers=h["owner"], json=payload).status_code == 500
    assert client.get(P + "/branches/main", headers=h["owner"]).json()["revision"] == candidate["revision"]
    issue_type = domain.issue_snapshot(owner, issue)["definition"]["type"]
    domain.set_issue_classification(
        owner, issue, "workspace", issue_type, ["capability:changed-after-publication"], issue_type, []
    )
    monkeypatch.setattr(domain, "add_issue_comment", original)
    assert client.post(path, headers=h["owner"], json=payload).status_code == 200
    with repository.store._connection() as db:
        assert db.execute("SELECT count(*) FROM native_release_events").fetchone()[0] == 1


def test_changed_issue_invalidates_previously_reviewed_candidate(setup):
    client, domain, _, owner, _, h, issue = setup
    candidate, _ = prepare(setup)
    review = approve(setup, candidate)
    assert candidate["issue_revision"] == domain.issue_snapshot(owner, issue)["revision"]
    issue_type = domain.issue_snapshot(owner, issue)["definition"]["type"]
    domain.set_issue_classification(
        owner, issue, "workspace", issue_type, ["capability:new-required-validation"], issue_type, []
    )
    response = client.post(
        P + "/candidates/" + candidate["id"] + "/merge",
        headers=h["owner"],
        json={"request_key": "merge-changed", "review": review},
    )
    assert response.status_code == 409
    assert client.get(P + "/branches/main", headers=h["owner"]).json()["revision"] is None
