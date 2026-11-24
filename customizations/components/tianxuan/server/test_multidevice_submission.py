"""Device-scoped idempotency with shared conflict checks and durable audit."""

import base64
import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from api import create_app
from fastapi.testclient import TestClient
from native_store import Conflict, NativeStore, NativeStoreError
from tianxuan_core import Tianxuan

P = "/api/v1/native"
D1 = {"device_id": "device-one", "credential_id": "credential-one"}
D2 = {"device_id": "device-two", "credential_id": "credential-two"}


def change(module="shared", *, base=None, reads=(), **edits):
    return {"module": module, "base": base, "reads": None if reads is None else list(reads), "edits": edits}


def batch(key="same", module="shared", base=None, value=b"content"):
    return {
        "request_key": key,
        "changes": [change(module, base=base, reads=None, file=base64.b64encode(value).decode())],
    }


def parallel(function):
    barrier = Barrier(2)

    def call(index):
        barrier.wait(timeout=5)
        return function(index)

    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(call, range(2)))


def test_disjoint_device_writes_merge_and_audit_actual_bases(tmp_path):
    store = NativeStore(tmp_path / "native.db")
    base = store.submit("tenant", "actor", "seed", [change(left=b"0", right=b"0")])["revisions"]["shared"]
    devices = (D1, D2)
    edits = ({"left": b"one"}, {"right": b"two"})
    changes = [[change(base=base, reads=[], **edit)] for edit in edits]
    results = parallel(lambda i: store.submit("tenant", "actor", "same", changes[i], **devices[i]))
    head = store.head("tenant", "shared")
    assert store.read("tenant", "shared", head, "left") == b"one"
    assert store.read("tenant", "shared", head, "right") == b"two"
    assert {r["changes"]["shared"]["applied_base"] for r in results} == {
        base,
        next(r["revisions"]["shared"] for r in results if r["revisions"]["shared"] != head),
    }
    reopened = NativeStore(store.database)
    for i, result in enumerate(results):
        assert result["actor"] == "actor" and result["request_key"] == "same"
        assert all(result[key] == value for key, value in devices[i].items())
        audit = result["changes"]["shared"]
        assert audit["base"] == base
        assert audit["revision"] == result["revisions"]["shared"]
        assert audit["writes"] == {name: hashlib.sha256(data).hexdigest() for name, data in edits[i].items()}
        assert reopened.batch_receipt("tenant", "actor", "same", **devices[i]) == result
        assert reopened.submit("tenant", "actor", "same", changes[i], **devices[i]) == result
    assert reopened.batch_receipt("tenant", "actor", "same") is None
    assert reopened.batch_receipt("tenant", "another", "same", **D1) is None
    assert reopened.batch_receipt("another", "actor", "same", **D1) is None


@pytest.mark.parametrize(
    "reads,edits", [([], {"file": b"collision"}), (["file"], {"other": b"read"}), (None, {"other": b"unknown"})]
)
def test_other_device_does_not_bypass_changed_inputs(tmp_path, reads, edits):
    store = NativeStore(tmp_path / "native.db")
    base = store.submit("tenant", "actor", "seed", [change(file=b"old")])["revisions"]["shared"]
    latest = store.submit("tenant", "actor", "same", [change(base=base, file=b"new")], **D1)
    with pytest.raises(Conflict):
        store.submit("tenant", "actor", "same", [change(base=base, reads=reads, **edits)], **D2)
    assert store.head("tenant", "shared") == latest["revisions"]["shared"]
    assert store.batch_receipt("tenant", "actor", "same", **D2) is None


def test_device_replay_and_rotation_retain_original_audit(tmp_path):
    store = NativeStore(tmp_path / "native.db")
    changes = [change(file=b"one")]
    results = parallel(lambda _: store.submit("tenant", "actor", "same", changes, **D1))
    assert results[0] == results[1]
    rotated = {**D1, "credential_id": "new-credential"}
    assert store.submit("tenant", "actor", "same", changes, **rotated) == results[0]
    assert store.batch_receipt("tenant", "actor", "same", **rotated) == results[0]
    with pytest.raises(Conflict):
        store.submit("tenant", "actor", "same", [change(file=b"different")], **rotated)
    with store._connection() as db:
        assert db.execute("SELECT count(*) FROM native_device_receipts").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM native_revisions").fetchone()[0] == 1


def test_additive_upgrade_preserves_historical_receipt_and_legacy_namespace(tmp_path):
    database = tmp_path / "native.db"
    historical = {"state": "received", "revisions": {}, "request_digest": "old"}
    with sqlite3.connect(database) as db:
        db.execute(
            "CREATE TABLE native_receipts (tenant TEXT, actor TEXT, request_key TEXT, request_digest TEXT, result TEXT, PRIMARY KEY (tenant,actor,request_key))"
        )
        db.execute(
            "INSERT INTO native_receipts VALUES (?,?,?,?,?)", ("tenant", "actor", "same", "old", json.dumps(historical))
        )
    store = NativeStore(database)
    assert store.batch_receipt("tenant", "actor", "same") == historical
    assert store.batch_receipt("tenant", "actor", "same", **D1) is None
    received = store.submit("tenant", "actor", "same", [change(file=b"device")], **D1)
    legacy = store.submit("tenant", "actor", "legacy", [change("legacy", file=b"legacy")])
    assert legacy["device_id"] is None and legacy["credential_id"] is None
    assert store.batch_receipt("tenant", "actor", "legacy", **D1) is None
    reopened = NativeStore(database)
    assert reopened.batch_receipt("tenant", "actor", "same", **D1) == received
    with sqlite3.connect(database) as db:
        assert len(db.execute("PRAGMA table_info(native_receipts)").fetchall()) == 5
        assert (
            json.loads(db.execute("SELECT result FROM native_receipts WHERE request_key='same'").fetchone()[0])
            == historical
        )


def test_audit_failure_rolls_back_revision_blobs_and_heads(tmp_path):
    store = NativeStore(tmp_path / "native.db")
    with store._connection(write=True) as db:
        db.execute(
            "CREATE TRIGGER fail_audit BEFORE INSERT ON native_device_receipts BEGIN SELECT RAISE(ABORT,'audit unavailable'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="audit unavailable"):
        store.submit("tenant", "actor", "same", [change(file=b"content")], **D1)
    with store._connection(write=True) as db:
        for table in ("native_blobs", "native_revisions", "native_heads", "native_device_receipts"):
            assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
        db.execute("DROP TRIGGER fail_audit")
    assert store.submit("tenant", "actor", "same", [change(file=b"retry")], **D1)["state"] == "received"


@pytest.mark.parametrize(
    "device", [{"device_id": "one"}, {"credential_id": "one"}, {"device_id": "", "credential_id": "one"}]
)
def test_incomplete_device_identity_never_falls_back_to_legacy(tmp_path, device):
    store = NativeStore(tmp_path / "native.db")
    with pytest.raises(NativeStoreError):
        store.submit("tenant", "actor", "same", [change(file=b"content")], **device)
    with pytest.raises(NativeStoreError):
        store.batch_receipt("tenant", "actor", "same", **device)


@pytest.fixture
def devices(tmp_path, monkeypatch):
    monkeypatch.delenv("TIANXUAN_REQUIRE_KEYS", raising=False)
    domain = Tianxuan(str(tmp_path / "auth.db"))
    native = NativeStore(tmp_path / "native.db")
    app = create_app(domain, native_store=native, native_only=True)
    with TestClient(app) as client:
        credentials = {"email": "device@example.invalid", "password": "password123"}
        registered = client.post("/api/v1/auth/register", json={"tenant_name": "Devices", **credentials})
        assert registered.status_code == 200
        owner = registered.json()
        sessions = [client.post("/api/v1/auth/session", json=credentials).json() for _ in range(3)]
        contexts = [domain.device_context(session["token"]) for session in sessions]
        assert len({context["device_id"] for context in contexts}) == 3
        headers = [{"Authorization": "Bearer " + session["token"]} for session in sessions]
        yield domain, native, client, owner, headers, contexts
    domain.db.close()


def test_http_two_devices_same_key_different_modules_are_independent(devices):
    domain, native, client, owner, headers, contexts = devices
    payloads = [batch(module="left", value=b"one"), batch(module="right", value=b"two")]
    results = parallel(lambda i: client.post(P + "/batches", headers=headers[i], json=payloads[i]))
    assert [r.status_code for r in results] == [200, 200]
    for i, response in enumerate(results):
        result = response.json()
        assert result["actor"] == owner["user_id"]
        assert result["device_id"] == contexts[i]["device_id"]
        assert result["credential_id"] == contexts[i]["credential_id"]
        assert headers[i]["Authorization"].split()[1] not in response.text
        assert client.get(P + "/batches/same", headers=headers[i]).json()["receipt"] == result
        assert client.post(P + "/batches", headers=headers[i], json=payloads[i]).json() == result
        assert client.post(P + "/batches", headers=headers[i], json=payloads[1 - i]).status_code == 409
    assert client.get(P + "/batches/same", headers=headers[2]).json()["receipt"] is None
    with TestClient(create_app(domain, native_store=NativeStore(native.database), native_only=True)) as restarted:
        for i, response in enumerate(results):
            assert restarted.get(P + "/batches/same", headers=headers[i]).json()["receipt"] == response.json()


def test_http_cross_device_competing_writes_return_one_409(devices):
    _, native, client, owner, headers, _ = devices
    seed = client.post(P + "/batches", headers=headers[0], json=batch(key="seed")).json()
    base = seed["revisions"]["shared"]
    results = parallel(
        lambda i: client.post(P + "/batches", headers=headers[i], json=batch(base=base, value=str(i).encode()))
    )
    assert sorted(r.status_code for r in results) == [200, 409]
    winner = next(i for i, result in enumerate(results) if result.status_code == 200)
    head = native.head(owner["tenant_id"], "shared")
    assert native.read(owner["tenant_id"], "shared", head, "file") == str(winner).encode()
    assert client.get(P + "/batches/same", headers=headers[1 - winner]).json()["receipt"] is None


def test_http_headers_and_payload_cannot_choose_another_device(devices):
    _, _, client, owner, headers, contexts = devices
    forged = {
        **headers[0],
        "X-Device-Id": contexts[1]["device_id"],
        "X-Credential-Id": contexts[1]["credential_id"],
        "X-Actor": "someone-else",
    }
    result = client.post(P + "/batches", headers=forged, json=batch())
    assert result.status_code == 200
    assert result.json()["actor"] == owner["user_id"]
    assert result.json()["device_id"] == contexts[0]["device_id"]
    assert (
        client.get(P + "/batches/same", headers={**headers[1], "X-Device-Id": contexts[0]["device_id"]}).json()[
            "receipt"
        ]
        is None
    )
    for field in ("device_id", "credential_id", "actor"):
        assert client.post(P + "/batches", headers=headers[0], json={**batch(), field: "forged"}).status_code == 422
    for reads in ([], ["file"]):
        payload = batch()
        payload["changes"][0]["reads"] = reads
        assert client.post(P + "/batches", headers=headers[0], json=payload).status_code == 422


def test_http_revocation_during_device_resolution_cannot_write_legacy_receipt(devices, monkeypatch):
    domain, native, client, owner, headers, _ = devices
    monkeypatch.setattr(domain, "device_context", lambda token: None)
    assert client.post(P + "/batches", headers=headers[0], json=batch()).status_code == 401
    assert native.head(owner["tenant_id"], "shared") is None
    assert native.batch_receipt(owner["tenant_id"], owner["user_id"], "same") is None


def test_legacy_host_without_device_resolver_retains_account_receipts(devices, monkeypatch):
    domain, native, client, owner, headers, _ = devices
    monkeypatch.setattr(domain, "device_context", None)
    result = client.post(P + "/batches", headers={**headers[0], "X-Device-Id": "forged"}, json=batch())
    assert result.status_code == 200
    assert result.json()["device_id"] is None
    assert client.get(P + "/batches/same", headers=headers[1]).json()["receipt"] == result.json()
    assert native.batch_receipt(owner["tenant_id"], owner["user_id"], "same") == result.json()


def test_requirement_snapshot_keys_are_device_scoped(devices):
    domain, native, client, owner, headers, contexts = devices
    docs = [
        domain.create_doc(owner["user_id"], name, "requirement", kind="requirement")["id"] for name in ("one", "two")
    ]
    results = []
    for i, doc in enumerate(docs):
        path = P + f"/requirements/{doc}"
        source = client.get(path + "/source", headers=headers[i]).json()["source_version"]
        payload = {"request_key": "same", "source_version": source, "base": None}
        response = client.post(path + "/snapshots", headers=headers[i], json=payload)
        assert response.status_code == 200, response.text
        assert client.post(path + "/snapshots", headers=headers[i], json=payload).json() == response.json()
        # Another device must perform its own conflict check, not replay ours.
        assert client.post(path + "/snapshots", headers=headers[2], json=payload).status_code == 409
        results.append(response.json())
    assert results[0]["module"] != results[1]["module"]
    key = "snapshot-" + hashlib.sha256(b"same").hexdigest()
    for i, result in enumerate(results):
        receipt = native.batch_receipt(owner["tenant_id"], owner["user_id"], key, **contexts[i])
        assert receipt["revisions"] == {result["module"]: result["revision"]}
