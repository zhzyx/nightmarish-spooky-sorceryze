"""Exercise output commit failures on the signed-stage HTTP workflow with a real local producer."""

import hashlib
import json

import pytest
import test_native_stage_admission
from test_native_stage_stop import PREVIEW, install_preview, signed

fixture = test_native_stage_admission.fixture
host = test_native_stage_admission.host


@pytest.mark.parametrize("table", ["native_candidate_receipts", "native_worker_terminals_v2", "native_worker_closed"])
def test_stage_waits_for_durable_output(host, table, record_property):
    h = host
    issue = install_preview(h)
    key = signed(h, issue)
    assert h.reserve(key).raise_for_status().json() is True
    store = h.workflow.worker.store
    with store._connection(write=True) as db:
        db.execute(
            f"CREATE TRIGGER reject_output BEFORE INSERT ON {table} "
            "BEGIN SELECT RAISE(ABORT,'fixture write failure'); END"
        )
    response = h.api("execute", key=key)
    assert response.status_code == 409
    with store._connection() as db:
        closure = json.loads(
            db.execute("SELECT payload FROM native_worker_process_closures WHERE execution=?", (key,)).fetchone()[0]
        )
        assert closure["exit_code"] == 0 and closure["reasons"] == []
        spool = db.execute("SELECT digest FROM native_worker_closed WHERE execution=?", (key,)).fetchone()
        assert (spool is None) == (table == "native_worker_closed")
        partial_intake = db.execute(
            "SELECT result FROM native_candidate_receipts WHERE request_key=?", ("worker-" + key,)
        ).fetchone()
        assert (partial_intake is not None) == (table == "native_worker_terminals_v2")
        assert db.execute("SELECT 1 FROM native_worker_terminals_v2 WHERE execution=?", (key,)).fetchone() is None

    pending = h.api("reconcile", key=key).raise_for_status().json()
    assert pending["state"] == "closed-unresolved" and pending["terminal"] is None and pending["acceptance"] is None
    assert h.detail(issue)["execution_progress"] == pending["progress"]
    assert pending["progress"]["candidate"] is None
    assert h.api("inspect").json()["stage_checks"] == []
    assert h.api("verify-stage", key=key).status_code == h.api("check", key=key).status_code == 409
    wait = h.api("await-terminal", key=key)
    assert wait.status_code == 409 and "output receipt" in wait.json()["detail"]
    launches = h.observations()
    assert len(launches) == 1 and launches[0]["execution"] == key

    # A changed working file must never become the source for recovery.
    workspace = h.workflow.worker.root / key / "work"
    (workspace / "a" / "preview.svg").write_bytes(b"late edit")
    with store._connection(write=True) as db:
        db.execute("DROP TRIGGER reject_output")
    restored = h.api("reconcile", key=key).raise_for_status().json()
    observation = dict(
        execution=key,
        failed_table=table,
        execute_status=response.status_code,
        physical_closure=closure,
        output_spool_sha256=spool[0] if spool else None,
        pending_state=pending["state"],
        pending_candidate=pending["progress"]["candidate"],
        await_detail=wait.json()["detail"],
        recovery_state=restored["state"],
    )
    if spool is None:
        assert restored == pending
        assert h.api("verify-stage", key=key).status_code == 409
    else:
        assert restored["state"] == "produced" and restored["acceptance"] is None
        terminal = json.loads(restored["terminal"])
        if partial_intake:
            assert terminal["intake"] == json.loads(partial_intake[0])
        assert terminal["intake"]["request_key"] == "worker-" + key
        assert h.api("await-terminal", key=key).raise_for_status().json()["terminal"] == restored["terminal"]
        assert h.api("inspect").json()["stage_checks"] == [key]
        stage = h.api("verify-stage", key=key).raise_for_status().json()
        assert stage["state"] == "stage-reached" and stage["checks"]["check"]["outcome"] == "passed"
        assert stage["candidate"] == terminal["candidate"] and stage["modules"] == terminal["modules"]
        artifact = store.read(restored["tenant"], "a", stage["modules"]["a"], "preview.svg")
        assert artifact == PREVIEW.encode()
        assert h.api("verify-stage", key=key).raise_for_status().json() == stage
        observation.update(
            intake=terminal["intake"]["id"],
            stage=stage,
            artifact_sha256=hashlib.sha256(artifact).hexdigest(),
        )
    assert h.observations() == launches
    observation.update(launch_count=len(launches), steps=h.detail(issue)["execution_progress"]["events"])
    record_property("observation", json.dumps(observation))
