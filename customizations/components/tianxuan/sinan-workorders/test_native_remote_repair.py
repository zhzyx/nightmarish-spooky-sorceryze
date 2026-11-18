# ruff: noqa: F811
import json
import os
import sys
import time
from pathlib import Path

import pytest
from native_node import NativeNode
from native_remote_worker import RemoteNativeWorker
from native_store import NativeStore, NativeStoreError, _digest
from native_worker import NativeWorker
from test_native_workflow import fixture as fixture
from test_native_workflow import reserve, task
from tianxuan_core import PermissionDenied

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / p) for p in ["sinan-workorders", "server", "duobao"]]


def remote_fixture(f):
    w, actor, tenant, _, _, root = f
    local = w.worker
    installation = local.installation("local")
    remote = RemoteNativeWorker(
        local.store,
        root / "remote",
        {"local": {"timeout": 5, "installation": installation}},
        authorize=local.intake.authorize,
        nodes={
            "n": {
                "tenant": tenant,
                "token_sha256": _digest(b"token"),
                "profiles": {"local": installation},
                "capacity": 2,
                "enabled": True,
                "package": _digest((ROOT / "sinan-workorders/native_node.py").read_bytes()),
            }
        },
        single_coordinator=True,
    )
    w.worker = remote
    remote.bind(w)
    return remote, local


def test_failed_coordinator_binding_closes_handle_before_actual_handoff(fixture):
    remote, local = remote_fixture(fixture)
    replacement = RemoteNativeWorker(
        local.store,
        fixture[-1] / "replacement",
        remote.profiles,
        authorize=local.intake.authorize,
        nodes=remote.nodes,
        single_coordinator=True,
    )
    try:
        with pytest.raises(NativeStoreError, match="Another remote coordinator"):
            replacement.bind(fixture[0])
        assert replacement.owner.closed
        assert not remote.owner.closed
        remote.close()
        replacement.bind(fixture[0])
        assert not replacement.owner.closed
    finally:
        remote.close()
        if hasattr(replacement, "owner"):
            replacement.close()


def test_revoked_offer_withdraws_without_content_and_later_cancel_progresses(fixture):
    remote, local = remote_fixture(fixture)
    try:
        first, _ = task(fixture, "a")
        reserve(fixture, first)
        second, _ = task(fixture, "b")
        reserve(fixture, second)
        remote.cancel(second)
        old = remote.intake.authorize
        remote.intake.authorize = lambda db, t, a, m, action: m != "a" and old(db, t, a, m, action)
        rows = remote.events("token", 0, timeout=0)
        assert rows[0]["kind"] == "withdraw"
        assert all(set(row) == {"cursor", "node", "execution", "kind"} for row in rows)
        assert any(row["kind"] == "cancel" and row["execution"] == second for row in rows)
        manifest = remote.manifest("n", first)
        assert set(manifest) == {"execution", "cancelled", "package"}
        assert manifest["cancelled"]
        with pytest.raises((NativeStoreError, PermissionDenied)):
            remote.blob("n", first, "0" * 64)
        for _ in range(2):
            remote.events("token", rows[-1]["cursor"], timeout=0)
        # A distinct legitimate offer remains available while revocation persists.
        remote.receipt(
            "n",
            first,
            {
                "execution": first,
                "physical": {"exit_code": None, "reasons": ["cancelled-before-launch"], "transcript": _digest(b"")},
                "output": None,
            },
        )
        third, _ = task(fixture, "c")
        reserve(fixture, third)
        assert any(
            row["execution"] == third and row["kind"] == "offer"
            for row in remote.events("token", rows[-1]["cursor"], timeout=0)
        )
    finally:
        remote.close()


def test_recovery_is_cancellable_and_unknown_intent_never_launches(fixture):
    w, actor, tenant, _, _, root = fixture
    w.worker.profiles["local"]["argv"][-1] = (
        "import subprocess,sys,pathlib,time,os,json; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
        "(pathlib.Path.cwd().parent/'pids.json').write_text(json.dumps([os.getpid(),child.pid])); time.sleep(60)"
    )
    remote, local = remote_fixture(fixture)
    nodeworker = NativeWorker(
        NativeStore(root / "node.sqlite"), root / "node", local.profiles, lambda *a: True, authorize=lambda *a: True
    )
    node = NativeNode(nodeworker, "http://127.0.0.1:1", "token", capacity=2)

    def request(path, value=None, **kwargs):
        if path.startswith("/events"):
            return remote.events("token", int(path.split("=")[1]), timeout=0)
        execution = path.split("/")[2]
        if path.endswith("/receipt"):
            return remote.receipt("n", execution, value)
        if "/blob/" in path:
            return remote.blob("n", execution, path.split("/")[-1])
        return remote.manifest("n", execution)

    node.request = request
    try:
        key, _ = task(fixture, "a")
        reserve(fixture, key)
        unknown, _ = task(fixture, "b")
        reserve(fixture, unknown)
        unknown_task = w.status(actor, unknown)["task"]
        with nodeworker.store._connection(write=True) as db:
            db.executemany("INSERT INTO native_node_received VALUES (?,0)", [(key,), (unknown,)])
            db.execute("INSERT INTO native_node_intents VALUES (?, ?, ?)", (unknown, unknown_task, "intent"))
            db.execute("UPDATE native_node_cursor SET cursor=2")
        node.recover()
        marker = root / "node" / key / "pids.json"
        deadline = time.monotonic() + 10
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert marker.exists()
        assert key in node.active
        remote.cancel(key)
        while key in node.active and time.monotonic() < deadline:
            node.step()
            time.sleep(0.01)
        assert key not in node.active
        node.step()
        for future in node.futures:
            future.result(timeout=5)
        with nodeworker.store._connection() as db:
            output = json.loads(
                db.execute("SELECT payload FROM native_worker_closed WHERE execution=?", (key,)).fetchone()[0]
            )
            assert output["cancelled"]
            assert db.execute("SELECT cursor FROM native_node_cursor").fetchone()[0] > 2
        import ctypes

        for pid in json.loads(marker.read_text()):
            if os.name == "nt":
                handle = ctypes.windll.kernel32.OpenProcess(0x100000, False, pid)
                if handle:
                    try:
                        assert ctypes.windll.kernel32.WaitForSingleObject(handle, 0) == 0
                    finally:
                        ctypes.windll.kernel32.CloseHandle(handle)
            elif sys.platform.startswith("linux"):
                status = Path(f"/proc/{pid}/stat")
                if status.exists():
                    # A killed orphan can await container PID 1 reaping; it must
                    # already be a zombie, never an executing descendant.
                    assert status.read_text().rsplit(")", 1)[1].split()[0] == "Z"
        node.recover()
        node.pool.shutdown(wait=True)
        assert not (root / "node" / unknown).exists()
        assert w.status(actor, unknown)["state"] == "reserved"
    finally:
        for cancel in list(node.active.values()):
            cancel.set()
        node.pool.shutdown(wait=True)
        remote.close()


def test_revoked_actor_physical_settlement_releases_both_capacities(fixture):
    w, actor, *_ = fixture
    remote, local = remote_fixture(fixture)
    try:
        key, _ = task(fixture, "a")
        reserve(fixture, key)
        w.authorize = lambda *args: False
        receipt = {
            "execution": key,
            "physical": {"exit_code": 0, "reasons": [], "transcript": _digest(b"")},
            "output": None,
        }
        first = remote.receipt("n", key, receipt)
        assert first == {"execution": key, "physical_closed": True, "state": "stopped"}
        assert remote.receipt("n", key, receipt) == first
        with pytest.raises(PermissionDenied):
            w.status(actor, key)
        with w._transaction() as db:
            assert (
                db.execute("SELECT closed FROM native_remote_assignments WHERE execution=?", (key,)).fetchone()[0] == 1
            )
            assert (
                db.execute("SELECT count(*) FROM native_tasks WHERE state IN ('reserved','running','held')").fetchone()[
                    0
                ]
                == 0
            )
            assert db.execute("SELECT terminal FROM native_tasks WHERE id=?", (key,)).fetchone()[0] is None
        with local.store._connection() as db:
            assert db.execute("SELECT count(*) FROM native_worker_terminals_v2").fetchone()[0] == 0
            assert db.execute("SELECT count(*) FROM native_candidate_receipts").fetchone()[0] == 0
        remote.nodes["n"]["enabled"] = False
        with pytest.raises(NativeStoreError):
            remote.receipt("n", key, receipt)
    finally:
        remote.close()
