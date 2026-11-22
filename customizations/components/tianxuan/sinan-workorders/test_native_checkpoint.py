"""Reopen genuine complete and torn domain journal images in new processes."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import test_native_stage_stop

fixture = test_native_stage_stop.fixture
host = test_native_stage_stop.host


def reopened(path, key, bearer):
    reader = """
import json, os, sys
from api import create_app
from fastapi.testclient import TestClient
from native_workflow import NativeWorkflow
from tianxuan_core import Tianxuan

path, key = sys.argv[1:]
domain = Tianxuan(path)
# Reading a checkpoint does not require a worker, checker or publisher.
workflow = NativeWorkflow(domain, None, None, None, lambda *args: True)
try:
    with TestClient(create_app(domain, native_workflow=workflow)) as client:
        response = client.post('/api/v1/native/workflow/checkpoint', json={'key': key},
                               headers={'Authorization': sys.stdin.read()})
        response.raise_for_status()
        print(json.dumps({'pid': os.getpid(), 'checkpoint': response.json()}))
finally:
    domain.db.close()
"""
    result = subprocess.run(
        [sys.executable, "-c", reader, str(path), key],
        env=dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path)),
        input=bearer,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_rebuild_and_partial_commit_frame(host, tmp_path, record_property):
    h = host
    issue = test_native_stage_stop.install_preview(h)
    key = test_native_stage_stop.signed(h, issue)
    db = h.workflow.domain.db
    path = Path(db.execute("PRAGMA database_list").fetchone()[2])
    assert db.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    db.execute("PRAGMA wal_autocheckpoint=0")
    assert h.reserve(key).raise_for_status().json()
    assert h.api("execute", key=key).raise_for_status().json()["state"] == "produced"
    before = h.api("checkpoint", key=key).raise_for_status().json()
    assert before["completed_steps"] == ["authorized", "reserved", "worker-terminal"]
    assert before["pending_decision"] == {"kind": "stage-check", "task": key}
    assert before["authorization"]["stage"]["criteria"] == test_native_stage_stop.CRITERION
    assert before["calls"]["worker"] == "native-worker:" + key
    assert before["target"]["writes"] == {"a": ["preview.svg"]}
    assert before["project"] == "studio"
    assert before["artifact_revisions"]["a"] != before["input_revisions"]["a"]
    assert before["stage_receipt"] is None
    # Freeze a physical baseline before the final transaction. The final WAL
    # frame marks that transaction committed only when the entire frame exists.
    assert db.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0] == 0
    baseline = path.read_bytes()
    receipt = h.api("verify-stage", key=key).raise_for_status().json()
    assert receipt["state"] == "stage-reached"
    after = h.api("checkpoint", key=key).raise_for_status().json()
    assert after["stage_receipt"] == receipt and after["artifact_revisions"] == receipt["modules"]
    assert after["completed_steps"] == before["completed_steps"] + ["stage-checked"]
    assert after["pending_decision"] == {"kind": "stage-confirmation", "task": key}
    assert after["authorization"] == before["authorization"] and after["target"] == before["target"]
    wal = Path(str(path) + "-wal").read_bytes()
    page_size = db.execute("PRAGMA page_size").fetchone()[0]
    frame_size = page_size + 24
    assert (len(wal) - 32) % frame_size == 0 and len(wal) >= 32 + frame_size
    assert int.from_bytes(wal[-frame_size + 4 : -frame_size + 8], "big") > 0
    assert path.read_bytes() == baseline
    bearer = h.client.headers["Authorization"]
    readers = []
    for name, image, expected in [("intact", wal, after), ("torn", wal[:-1], before)]:
        directory = tmp_path / name
        directory.mkdir()
        destination = directory / path.name
        shutil.copyfile(path, destination)
        Path(str(destination) + "-wal").write_bytes(image)
        observation = reopened(destination, key, bearer)
        assert observation["checkpoint"] == expected
        readers.append({"image": name, "wal_bytes": len(image), **observation})
    assert len(h.observations()) == 1
    other = h.workflow.domain.register("external", "external@example.invalid", "password")["user_id"]
    response = h.client.post(
        "/api/v1/native/workflow/checkpoint",
        json={"key": key},
        headers={"Authorization": "Bearer " + h.workflow.domain.issue_session(other)},
    )
    assert response.status_code in {403, 404}
    db.close()
    original = reopened(path, key, bearer)
    assert original["checkpoint"] == after
    readers.append({"image": "original-after-close", **original})
    record_property("recovery", json.dumps({"writer_pid": os.getpid(), "page_size": page_size, "readers": readers}))
