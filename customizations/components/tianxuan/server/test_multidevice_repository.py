"""Same-account repository devices isolate replay, never authority or branch CAS."""

import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from api import create_app
from fastapi.testclient import TestClient
from native_repository import MODULE, NativeRepository
from native_repository_api import domain_authority
from native_store import Conflict, NativeStore, NativeStoreError, _digest, _json
from tianxuan_core import Tianxuan

P = "/api/v1/native/repos/gonggong"
D1 = {"device_id": "device-one", "credential_id": "credential-one"}
D2 = {"device_id": "device-two", "credential_id": "credential-two"}
ISSUE = "iss_" + "a" * 32


def parallel(function):
    barrier = Barrier(2)

    def call(index):
        barrier.wait(timeout=5)
        return function(index)

    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(call, range(2)))


@pytest.fixture
def devices(tmp_path, monkeypatch):
    monkeypatch.delenv("TIANXUAN_REQUIRE_KEYS", raising=False)
    domain = Tianxuan(str(tmp_path / "auth.db"))
    owner = domain.register("Devices", "owner@example.invalid", "password123")
    reviewer = domain.add_member(owner["user_id"], "review@example.invalid", "password123")["user_id"]
    repository = NativeRepository(NativeStore(tmp_path / "native.db"), domain_authority(domain))
    tokens = [domain.issue_session(actor) for actor in (owner["user_id"], owner["user_id"], reviewer, reviewer)]
    headers = [{"Authorization": "Bearer " + token} for token in tokens]
    contexts = [domain.device_context(token) for token in tokens]
    issue = domain.create_issue(owner["user_id"], "Device repository", acceptance="audited repository")
    with TestClient(create_app(domain, native_repository=repository)) as client:
        for h in headers[:2]:
            assert client.post(P + "/bootstrap", headers=h, json={"request_key": "init"}).status_code == 200
        yield client, domain, repository, owner, headers, contexts, issue["id"]
    domain.db.close()


def post(client, headers, path, body):
    response = client.post(P + path, headers=headers, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def commit_body(branch, manifest=None, expected=None):
    return {
        "request_key": "commit",
        "branch": branch,
        "expected": expected,
        "manifest": manifest or {},
        "message": "work",
    }


def prepare(devices):
    client, _, _, _, headers, _, issue = devices
    for i, h in enumerate(headers[:2]):
        post(client, h, "/branches", {"request_key": "branch", "branch": f"task/{i}", "revision": None})
    content = b"device source"
    digest = hashlib.sha256(content).hexdigest()
    assert client.put(P + "/objects/" + digest, headers=headers[0], content=content).status_code == 200
    commits = parallel(lambda i: post(client, headers[i], "/commits", commit_body(f"task/{i}", {"file.txt": digest})))
    candidates = [
        post(
            client,
            h,
            "/candidates",
            {
                "request_key": "candidate",
                "source": f"task/{i}",
                "target": "main",
                "revision": commits[i]["revision"],
                "expected": None,
                "issue_id": issue,
            },
        )
        for i, h in enumerate(headers[:2])
    ]
    return commits, candidates


def test_two_devices_same_keys_preserve_account_audit_and_restart(devices):
    client, _, repository, owner, headers, contexts, _ = devices
    commits, candidates = prepare(devices)
    assert commits[0]["revision"] != commits[1]["revision"]
    reopened = NativeRepository(NativeStore(repository.store.database), repository.authorize)
    for i, result in enumerate(commits):
        state = client.get(P + "/revisions/" + result["revision"], headers=headers[i]).json()
        assert state["author"] == state["actor"] == result["actor"] == owner["user_id"]
        assert state["objects"] == result["manifest"]
        for field in ("device_id", "credential_id"):
            assert state[field] == result[field] == contexts[i][field]
        for field in ("request_key", "branch", "expected"):
            assert state[field] == result[field]
        assert candidates[i]["revision"] == result["revision"]
        body = commit_body(f"task/{i}", result["manifest"])
        assert post(client, headers[i], "/commits", body) == result
        assert client.post(P + "/commits", headers=headers[i], json={**body, "message": "changed"}).status_code == 409
        with reopened.device_context(device_id=contexts[i]["device_id"], credential_id="rotated"):
            assert reopened.commit(owner["tenant_id"], owner["user_id"], "gonggong", **body) == result
    with repository.store._connection() as db:
        assert db.execute("SELECT count(*) FROM native_repo_requests").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM native_repo_device_requests").fetchone()[0] == 8


def test_http_competing_expected_revision_has_one_winner(devices):
    client, _, _, _, headers, contexts, _ = devices
    post(client, headers[0], "/branches", {"request_key": "branch", "branch": "shared", "revision": None})
    results = parallel(lambda i: client.post(P + "/commits", headers=headers[i], json=commit_body("shared")))
    assert sorted(r.status_code for r in results) == [200, 409]
    winner = next(i for i, r in enumerate(results) if r.status_code == 200)
    result = results[winner].json()
    assert result["device_id"] == contexts[winner]["device_id"]
    assert client.get(P + "/branches/shared", headers=headers[0]).json()["revision"] == result["revision"]


def test_device_headers_and_payload_cannot_select_identity(devices):
    client, _, _, owner, headers, contexts, _ = devices
    post(client, headers[0], "/branches", {"request_key": "branch", "branch": "task", "revision": None})
    forged = {**headers[0], "X-Device-Id": contexts[1]["device_id"], "X-Credential-Id": contexts[1]["credential_id"]}
    result = post(client, forged, "/commits", commit_body("task"))
    assert result["actor"] == owner["user_id"] and result["device_id"] == contexts[0]["device_id"]
    assert client.get(P + "/identity", headers={**forged, "X-Actor": "forged"}).status_code == 422
    assert client.post(P + "/commits", headers=headers[1], json=commit_body("task")).status_code == 409
    for field in ("device_id", "credential_id", "actor"):
        assert (
            client.post(P + "/commits", headers=headers[0], json={**commit_body("task"), field: "forged"}).status_code
            == 422
        )


def test_checks_reviews_merge_are_scoped_but_same_account_cannot_review_itself(devices):
    client, _, repository, _, headers, _, _ = devices
    commits, candidates = prepare(devices)
    paths = ["/candidates/" + c["id"] for c in candidates]
    # Same candidate and request key on two devices must create distinct check receipts.
    checks = [post(client, h, paths[0] + "/checks", {"request_key": "checks"}) for h in headers[:2]]
    assert checks[0]["evidence"] != checks[1]["evidence"]
    assert post(client, headers[1], paths[0] + "/checks", {"request_key": "checks"}) == checks[1]
    for h in headers[:2]:
        assert (
            client.post(
                P + paths[0] + "/reviews", headers=h, json={"request_key": "review", "note": "self"}
            ).status_code
            == 422
        )
    # Distinct devices of an actual independent reviewer may use the same key.
    reviews = [
        post(client, h, paths[0] + "/reviews", {"request_key": "review", "note": "independent"}) for h in headers[2:]
    ]
    assert reviews[0]["id"] != reviews[1]["id"]
    assert reviews[0]["request"]["actor"] == reviews[1]["request"]["actor"]
    payload = {"request_key": "merge", "review": reviews[1]["id"]}
    result = post(client, headers[0], paths[0] + "/merge", payload)
    assert result["revision"] == commits[0]["revision"]
    assert post(client, headers[0], paths[0] + "/merge", payload) == result
    # Other device cannot replay the first device's main update after CAS changed.
    assert client.post(P + paths[0] + "/merge", headers=headers[1], json=payload).status_code == 409
    assert repository._device.get() == (None, None)


def make_repository(tmp_path):
    return NativeRepository(NativeStore(tmp_path / "repository.db"), lambda tenant, actor, action: True)


def test_context_isolation_nested_restore_errors_and_store_cas(tmp_path):
    repository = make_repository(tmp_path)
    repository.bootstrap("tenant", "actor", "gonggong", "init")
    repository.create_branch("tenant", "actor", "gonggong", "branch", "shared", None)
    other = NativeRepository(repository.store, repository.authorize)
    with repository.device_context(**D1):
        assert other._device.get() == (None, None)
        with pytest.raises(RuntimeError), repository.device_context(**D2):
            raise RuntimeError("failed")
        assert repository._device.get() == tuple(D1.values())
    assert repository._device.get() == (None, None)

    def commit(index):
        with repository.device_context(**(D1, D2)[index]):
            try:
                return repository.commit("tenant", "actor", "gonggong", **commit_body("shared"))
            except Conflict:
                return None

    results = parallel(commit)
    assert sum(result is not None for result in results) == 1
    winner = next(result for result in results if result is not None)
    assert repository.branch("tenant", "actor", "gonggong", "shared")["revision"] == winner["revision"]
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(commit, 1).result() in (None, results[1])
        assert pool.submit(repository._device.get).result() == (None, None)


@pytest.mark.parametrize(
    "context", [{"device_id": "one"}, {"credential_id": "one"}, {"device_id": "", "credential_id": "one"}]
)
def test_partial_device_cannot_silently_enter_legacy_namespace(tmp_path, context):
    repository = make_repository(tmp_path)
    with pytest.raises(NativeStoreError), repository.device_context(**context):
        pytest.fail("invalid device was accepted")


def test_legacy_table_revision_and_approval_key_compatibility(tmp_path):
    database = tmp_path / "repository.db"
    request = {"operation": "branch", "repository": "gonggong", "branch": "historical", "revision": None}
    receipt = {"repository": "gonggong", "branch": "historical", "revision": None}
    with sqlite3.connect(database) as db:
        db.execute(
            "CREATE TABLE native_repo_requests (tenant TEXT, actor TEXT, request_key TEXT, digest TEXT, payload TEXT, PRIMARY KEY(tenant,actor,request_key))"
        )
        db.execute(
            "INSERT INTO native_repo_requests VALUES (?,?,?,?,?)",
            ("tenant", "actor", "branch", _digest(_json(request).encode()), _json(receipt)),
        )
    repository = make_repository(tmp_path)
    repository.bootstrap("tenant", "actor", "gonggong", "init")
    assert repository.create_branch("tenant", "actor", "gonggong", "branch", "historical", None) == receipt
    old_state = dict(
        module=MODULE,
        parent=None,
        objects={},
        dependencies={},
        repository="gonggong",
        author="actor",
        message="historical",
    )
    old_revision = _digest(_json(old_state).encode())
    with repository.store._connection(write=True) as db:
        db.execute("INSERT INTO native_revisions VALUES (?,?,?,?)", ("tenant", old_revision, MODULE, _json(old_state)))
        assert len(db.execute("PRAGMA table_info(native_repo_requests)").fetchall()) == 5
    assert repository.revision("tenant", "actor", "gonggong", old_revision) == old_state
    with repository.device_context(**D1):
        repository.create_branch("tenant", "actor", "gonggong", "branch", "device", old_revision)
    revision = repository.commit("tenant", "actor", "gonggong", "commit", "device", old_revision, {}, "legacy")
    candidate = repository.create_candidate(
        "tenant", "actor", "gonggong", "candidate", "device", "main", revision["revision"], None, ISSUE
    )
    checks = repository.run_checks("tenant", "actor", "gonggong", candidate["id"], "checks")
    review = repository.review("tenant", "reviewer", "gonggong", candidate["id"], "review", "independent")
    assert review["request"]["request_key"] == "repo-review-" + _digest(b"review")
    assert review == repository.review("tenant", "reviewer", "gonggong", candidate["id"], "review", "independent")
    result = repository.merge("tenant", "actor", "gonggong", candidate["id"], "merge", review["id"])
    reopened = make_repository(tmp_path)
    assert reopened.merge("tenant", "actor", "gonggong", candidate["id"], "merge", review["id"]) == result
    with repository.store._connection() as db:
        record = json.loads(
            db.execute("SELECT payload FROM native_repo_requests WHERE request_key='branch'").fetchone()[0]
        )
        assert record == receipt
        assert db.execute(
            "SELECT record FROM native_release_requests WHERE request_key=?", ("repo-merge-" + _digest(b"merge"),)
        ).fetchone()
        key = _digest(_json(["actor", "checks", candidate["id"], "repository-integrity"]).encode())
        assert (
            db.execute("SELECT evidence_id FROM native_check_requests WHERE request_key=?", (key,)).fetchone()[0]
            == checks["evidence"]["repository-integrity"]
        )


def test_audit_failure_rolls_back_commit_and_branch(tmp_path):
    repository = make_repository(tmp_path)
    repository.bootstrap("tenant", "actor", "gonggong", "init")
    repository.create_branch("tenant", "actor", "gonggong", "branch", "task", None)
    with repository.store._connection(write=True) as db:
        db.execute(
            "CREATE TRIGGER fail_audit BEFORE INSERT ON native_repo_device_requests BEGIN SELECT RAISE(ABORT,'audit unavailable'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="audit unavailable"), repository.device_context(**D1):
        repository.commit("tenant", "actor", "gonggong", **commit_body("task"))
    assert repository.branch("tenant", "actor", "gonggong", "task")["revision"] is None
    with repository.store._connection() as db:
        assert db.execute("SELECT count(*) FROM native_revisions").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM native_repo_device_requests").fetchone()[0] == 0
