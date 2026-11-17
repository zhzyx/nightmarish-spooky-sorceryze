"""Real process intake, crash recovery, authority and immutable provenance."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

# The imported fixture is intentionally injected by pytest.
# ruff: noqa: F811
from native_store import Conflict, NativeStoreError, _digest, _json
from native_worker import NativeWorker
from test_native_workflow import fixture, reserve, task  # noqa: F401


def contract(f, key):
    return json.loads(f[0].status(f[1], key)["task"])


@pytest.mark.parametrize("advance", [False, True])
@pytest.mark.parametrize("distinct", [False, True])
def test_same_module_parallel_and_unrelated_head(fixture, distinct, advance):
    w, actor, tenant, req, initial, _ = fixture
    code = w.worker.profiles["local"]["argv"][-1]
    if distinct:
        code = code.replace("m+' produced'", "str(p.parent)")
    w.worker.profiles["local"]["argv"][-1] = code
    keys = [task(fixture, "a")[0] for _ in range(2)]
    for key in keys:
        reserve(fixture, key)
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(w.execute, actor, key) for key in keys]
        advanced = initial["a"]
        if advance:
            advanced = w.worker.store.submit(
                tenant,
                actor,
                "third-party",
                [dict(module="a", base=initial["a"], reads=None, edits={"output": b"third"})],
            )["revisions"]["a"]
        results = [f.result() for f in futures]
    intervals = [json.loads((w.worker.root / key / "interval.json").read_text()) for key in keys]
    assert max(x[0] for x in intervals) < min(x[1] for x in intervals)
    assert all(r["state"] == "produced" for r in results)
    assert w.worker.store.head(tenant, "a") == advanced
    assert (results[0]["modules"] != results[1]["modules"]) == distinct
    assert results[0]["intake"]["id"] != results[1]["intake"]["id"]
    restarted = NativeWorker(
        w.worker.store, w.worker.root, w.worker.profiles, w.worker.verify, authorize=w.worker.intake.authorize
    )
    for key, result in zip(keys, results):
        assert result["intake"]["inputs"]["a"]["base"] == initial["a"]
        assert restarted.reconcile(contract(fixture, key), key) == result
        assert restarted.run(contract(fixture, key), key) == result
        assert result["origin"]["issue_url"].startswith("native://")
    if advance:
        with pytest.raises(Conflict):
            w.worker.store.submit(
                tenant,
                actor,
                "strict-still-strict",
                [dict(module="a", base=initial["a"], reads=None, edits={"output": b"stale"})],
            )


@pytest.mark.parametrize("point", ["receive", "compose", "terminal"])
def test_closed_output_recovers_without_producer(fixture, monkeypatch, point):
    w, actor, tenant, *_ = fixture
    key, _ = task(fixture, "a")
    reserve(fixture, key)
    owner, method = {
        "receive": (w.worker.intake, "receive"),
        "compose": (w.worker.store, "compose"),
        "terminal": (w.worker, "_terminal"),
    }[point]
    original = getattr(owner, method)

    def crash(*args, **kwargs):
        raise RuntimeError("injected after process close")

    monkeypatch.setattr(owner, method, crash)
    with pytest.raises(RuntimeError):
        w.execute(actor, key)
    interval = (w.worker.root / key / "interval.json").read_bytes()
    monkeypatch.setattr(owner, method, original)
    monkeypatch.setattr(w.worker.helper, "run_owned", crash)
    # Mutable output is never recollected after the owned closed spool exists.
    (w.worker.root / key / "work/a/output").write_text("forged later")
    result = w.worker.reconcile(contract(fixture, key), key)
    assert result["state"] == "produced"
    assert w.worker.store.read(tenant, "a", result["modules"]["a"], "output") == b"a produced"
    assert (w.worker.root / key / "interval.json").read_bytes() == interval


def test_authority_withdrawal_receipt_tamper_and_task_replay(fixture):
    w, actor, tenant, *_ = fixture
    key, _ = task(fixture, "a")
    reserve(fixture, key)
    w.execute(actor, key)
    original = w.worker.intake.authorize
    w.worker.intake.authorize = lambda *a: False
    assert w.worker.process_closed(contract(fixture, key), key) is True
    with pytest.raises(NativeStoreError, match="authorization"):
        w.worker.reconcile(contract(fixture, key), key)
    w.worker.intake.authorize = original
    forged = contract(fixture, key)
    forged["producer"] = "imposter"
    with pytest.raises(NativeStoreError, match="contract"):
        w.worker.reconcile(forged, key)
    other, _ = task(fixture, "a")
    assert w.worker.reconcile(contract(fixture, other), other) is None
    with w.worker.store._connection(write=True) as db:
        db.execute("UPDATE native_candidate_receipts SET result='{}'")
    with pytest.raises(NativeStoreError, match="integrity"):
        w.worker.reconcile(contract(fixture, key), key)


def test_no_changes_and_unknown_are_distinct(fixture):
    w, actor, *_ = fixture
    w.worker.profiles["local"]["argv"][-1] = "pass"
    key, _ = task(fixture, "a")
    data = contract(fixture, key)
    assert w.worker.reconcile(data, key) is None
    assert w.worker.process_closed(data, key) is False
    reserve(fixture, key)
    result = w.execute(actor, key)
    assert result["no_changes"] is True and result["intake"] is None
    assert result["origin"]["worker_ref"] == "native-worker:" + key
    assert w.worker.reconcile(data, key) == result


@pytest.mark.parametrize("mode", ["scope", "requirement", "unknown-module"])
def test_invalid_collection_never_produced(fixture, mode):
    w, actor, tenant, *_ = fixture
    w.worker.profiles["local"]["argv"][-1] = "from pathlib import Path; Path('a/forbidden').write_text('bad')"
    key, _ = task(fixture, "a")
    data = contract(fixture, key)
    data["writes"] = {"a": ["output"]}
    if mode == "requirement":
        revision = w.worker.store.submit(
            tenant,
            actor,
            "req",
            [dict(module="requirement-test", base=None, reads=None, edits={"output": b"immutable"})],
        )["revisions"]
        data["selected"].update(revision)
        data["writes"] = {"requirement-test": "*"}
        w.worker.profiles["local"]["argv"][-1] = (
            "from pathlib import Path; Path('requirement-test/output').write_text('bad')"
        )
    elif mode == "unknown-module":
        w.worker.profiles["local"]["argv"][-1] = (
            "from pathlib import Path; Path('alien').mkdir(); Path('alien/o').write_text('bad')"
        )
    data["installation"] = w.worker.installation("local")
    execution = _digest(_json(data).encode())
    with pytest.raises(NativeStoreError):
        w.worker.run(data, execution)
    assert w.worker.reconcile(data, execution) is None


def test_missing_authority_fails_closed(fixture):
    worker = fixture[0].worker
    with pytest.raises(NativeStoreError, match="authority"):
        NativeWorker(worker.store, worker.root, worker.profiles, worker.verify)


@pytest.mark.parametrize("code", ["raise SystemExit(7)", "import time; time.sleep(2)"])
def test_physical_failure_or_cancel_survives_withdrawal(fixture, code):
    import threading

    w, actor, *_ = fixture
    w.worker.profiles["local"]["argv"][-1] = code
    key, _ = task(fixture, "a")
    data = contract(fixture, key)
    cancelled = threading.Event()
    if "sleep" in code:
        cancelled.set()
    result = w.worker.run(data, key, cancelled)
    assert result["state"] == "failed"
    w.worker.intake.authorize = lambda *a: False
    assert w.worker.process_closed(data, key) is True
    with pytest.raises(NativeStoreError):
        w.worker.reconcile(data, key)
    forged = {**data, "producer": "forged"}
    with pytest.raises(NativeStoreError):
        w.worker.process_closed(forged, key)
    with w.worker.store._connection(write=True) as db:
        db.execute("UPDATE native_worker_process_closures SET payload='{}'")
    with pytest.raises(NativeStoreError, match="integrity"):
        w.worker.process_closed(data, key)


def test_physical_probe_rejects_corrupt_spool_without_writes(fixture):
    w, actor, *_ = fixture
    key, _ = task(fixture, "a")
    reserve(fixture, key)
    w.execute(actor, key)
    data = contract(fixture, key)

    def snapshot():
        with w.worker.store._connection() as db:
            return list(db.iterdump())

    before = snapshot()
    assert w.worker.process_closed(data, key) is True
    assert snapshot() == before
    with w.worker.store._connection(write=True) as db:
        db.execute("UPDATE native_worker_closed SET payload='{}'")
    corrupted = snapshot()
    with pytest.raises(NativeStoreError, match="integrity"):
        w.worker.process_closed(data, key)
    assert snapshot() == corrupted


@pytest.mark.parametrize("mode", ["produced", "no-change", "failed", "cancelled"])
def test_separate_process_recovery(fixture, monkeypatch, mode):
    import subprocess
    import sys
    import threading

    w = fixture[0]
    if mode == "failed":
        w.worker.profiles["local"]["argv"][-1] = "raise SystemExit(7)"
    elif mode == "no-change":
        w.worker.profiles["local"]["argv"][-1] = "pass"
    key, _ = task(fixture, "a")
    data = contract(fixture, key)
    cancel = threading.Event()
    if mode == "cancelled":
        collect = w.worker.workspace.collect

        def late_cancel(*args):
            changes = collect(*args)
            cancel.set()
            return changes

        monkeypatch.setattr(w.worker.workspace, "collect", late_cancel)
    original = w.worker._terminal
    monkeypatch.setattr(w.worker, "_terminal", lambda *a: (_ for _ in ()).throw(RuntimeError("crash")))
    with pytest.raises(RuntimeError, match="crash"):
        w.worker.run(data, key, cancel)
    monkeypatch.setattr(w.worker, "_terminal", original)
    script = """
import json,sys
sys.path[:0] = json.loads(sys.argv[1])
from native_store import NativeStore
from native_worker import NativeWorker
w = NativeWorker(NativeStore(sys.argv[2]), sys.argv[3], {}, lambda *a: True,
                 authorize=lambda *a: True)
w.helper.run_owned = lambda *a, **k: (_ for _ in ()).throw(AssertionError('relaunch'))
print(json.dumps(w.reconcile(json.loads(sys.argv[4]), sys.argv[5]), sort_keys=True))
"""
    command = [
        sys.executable,
        "-c",
        script,
        json.dumps(sys.path),
        str(fixture[-1] / "native.sqlite"),
        str(w.worker.root),
        _json(data),
        key,
    ]
    processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(4)]
    try:
        outputs = [process.communicate(timeout=20) for process in processes]
        assert all(process.returncode == 0 for process in processes), outputs
        results = [json.loads(stdout) for stdout, _ in outputs]
        assert all(result == results[0] for result in results)
        assert results[0]["state"] == ("failed" if mode in {"failed", "cancelled"} else "produced")
        assert w.worker.run(data, key) == results[0]
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)


@pytest.mark.parametrize("corruption", ["physical", "missing-physical", "failed-terminal", "missing-output"])
def test_history_rejects_corruption(fixture, corruption):
    w = fixture[0]
    if corruption == "failed-terminal":
        w.worker.profiles["local"]["argv"][-1] = "raise SystemExit(7)"
    key, _ = task(fixture, "a")
    data = contract(fixture, key)
    result = w.worker.run(data, key)
    with w.worker.store._connection(write=True) as db:
        if corruption == "physical":
            db.execute("UPDATE native_worker_process_closures SET payload='{}'")
        elif corruption == "missing-physical":
            db.execute("DELETE FROM native_worker_process_closures")
        elif corruption == "failed-terminal":
            assert result["exit_code"] == 7
            result["exit_code"] = 99
            db.execute("UPDATE native_worker_terminals_v2 SET terminal=?", (_json(result),))
        else:
            db.execute("DELETE FROM native_worker_closed")
            db.execute(
                "UPDATE native_worker_terminals_v2 SET terminal=?", (_json({"state": "failed", "exit_code": 99}),)
            )
    with pytest.raises(NativeStoreError):
        w.worker.reconcile(data, key)


@pytest.mark.parametrize("table", ["native_worker_process_closures", "native_worker_closed"])
def test_null_record_is_not_missing_history(fixture, table):
    w = fixture[0]
    key, _ = task(fixture, "a")
    data = contract(fixture, key)
    w.worker.run(data, key)
    with w.worker.store._connection(write=True) as db:
        db.execute(f"UPDATE {table} SET payload=?,digest=?", ("null", _digest(b"null")))
    with pytest.raises(NativeStoreError, match="integrity"):
        w.worker.reconcile(data, key)
    with pytest.raises(NativeStoreError, match="integrity"):
        w.worker.process_closed(data, key)
