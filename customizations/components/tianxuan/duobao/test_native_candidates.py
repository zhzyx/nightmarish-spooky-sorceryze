import base64
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from native_candidates import NativeCandidates
from native_store import Conflict, NativeStore, NativeStoreError
from native_workspace import Limits, NativeWorkspace

ORIGIN = {
    "source_ref": "frozen-input-1444",
    "worker_ref": "worker-one",
    "issue_url": "https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1451",
}


def change(base=None, data=b"output", module="m", **extra):
    return {"module": module, "base": base, "reads": None, "edits": {"file": data}, **extra}


@pytest.fixture
def env(tmp_path):
    store = NativeStore(tmp_path / "native.db")
    base = store.submit("t", "seed", "seed", [change(data=b"base")])["revisions"]["m"]
    return store, NativeCandidates(store, lambda *_: True), base


def snapshot(store):
    with store._connection() as db:
        return {
            row[0]: list(map(tuple, db.execute('SELECT * FROM "' + row[0] + '"')))
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }


def test_drift_replay_provenance_and_rollback(env, tmp_path):
    store, candidates, base = env
    head = store.submit("t", "other", "drift", [change(base, b"drift")])["revisions"]["m"]
    with pytest.raises(Conflict, match="Unknown read"):
        store.submit("t", "worker", "old-submit", [change(base)])
    result = candidates.receive("t", "worker", "one", [change(base)], ORIGIN)
    assert result["inputs"]["m"]["reads"] is None
    assert result["requires_final_composition_validation"] is True
    assert store.head("t", "m") == head
    assert store.revision("t", "m", result["revisions"]["m"])["parent"] == base
    assert candidates.receive("t", "worker", "one", [change(base)], ORIGIN) == result
    other = candidates.receive("t", "second", "one", [change(base)], {**ORIGIN, "worker_ref": "worker-two"})
    assert other["id"] != result["id"] and other["revisions"] == result["revisions"]
    with pytest.raises(Conflict):
        candidates.receive("t", "worker", "one", [change(base, b"different")], ORIGIN)
    recovered = NativeCandidates(NativeStore(store.database), lambda *_: True)
    assert recovered.receipt("t", "worker", "one") == result
    composition = store.compose("t", result["revisions"])
    NativeWorkspace(store).materialize("t", composition["modules"], tmp_path / "materialized")
    assert (tmp_path / "materialized/m/file").read_bytes() == b"output"
    # Rollback means disable candidate entry; existing interface still reads/writes.
    assert NativeStore(store.database).read("t", "m", base, "file") == b"base"
    assert store.submit("t", "old", "after-disable", [change(head, b"legacy")])["state"] == "received"


@pytest.mark.parametrize(
    "bad",
    [
        {"edits": {"../escape": b"x"}},
        {"edits": {"A": b"a", "a": b"b"}},
        {"edits": {"x": b"a", "x/y": b"b"}},
        {"edits": {"CON": b"x"}},
        {"dependencies": {"absent": "0" * 64}},
        {"dependencies": {"absent": "@batch"}},
        {"dependencies": {"m": "@batch"}},
        {"base": "0" * 64},
        {"reads": "unknown"},
    ],
)
def test_atomic_bad_input(env, bad):
    store, candidates, base = env
    before = snapshot(store)
    with pytest.raises(NativeStoreError):
        candidates.receive("t", "a", "bad", [change(module="first"), {**change(base), **bad}], ORIGIN)
    assert snapshot(store) == before


def test_authority_tenant_budgets_and_corruption(env):
    store, candidates, base = env
    before = snapshot(store)
    for decision in (False, 1, "yes", None):
        with pytest.raises(NativeStoreError, match="authorization"):
            NativeCandidates(store, lambda *_, d=decision: d).receive("t", "a", "denied", [change(base)], ORIGIN)
    with pytest.raises(NativeStoreError):
        candidates.receive("other", "a", "cross", [change(base)], ORIGIN)
    for limited, edits in [
        (Limits(file_bytes=1), {"f": b"xx"}),
        (Limits(files=1), {"a": b"x", "b": b"x"}),
        (Limits(total_bytes=1), {"a": b"x", "b": b"x"}),
        (Limits(entries=1), {"a/b": b"x"}),
    ]:
        with pytest.raises(NativeStoreError):
            NativeCandidates(store, lambda *_: True, limited).receive("t", "a", "limit", [change(edits=edits)], ORIGIN)
    assert snapshot(store) == before
    with store._connection(write=True) as db:
        db.execute("UPDATE native_blobs SET content=?", (b"corrupt",))
    before = snapshot(store)
    with pytest.raises(NativeStoreError, match="integrity"):
        candidates.receive("t", "a", "corrupt", [change(base)], ORIGIN)
    assert snapshot(store) == before


def test_batch_closure_cycle_and_authorization(env):
    store, candidates, base = env
    changes = [change(base, dependencies={"dep": "@batch"}), change(module="dep")]
    result = candidates.receive("t", "a", "batch", changes, ORIGIN)
    assert store.compose("t", {"m": result["revisions"]["m"]})["modules"] == result["revisions"]
    assert store.head("t", "dep") is None
    before = snapshot(store)
    with pytest.raises(NativeStoreError):
        candidates.receive(
            "t",
            "a",
            "cycle",
            [change(dependencies={"dep": "@batch"}), change(module="dep", dependencies={"m": "@batch"})],
            ORIGIN,
        )
    denied = NativeCandidates(store, lambda db, t, a, m, action: m != "dep")
    with pytest.raises(NativeStoreError, match="authorization"):
        denied.receive("t", "a", "denied-dep", [change(base, dependencies={"dep": result["revisions"]["dep"]})], ORIGIN)
    assert snapshot(store) == before


@pytest.mark.parametrize("removed_dependency", [False, True])
def test_replay_and_receipt_recheck_original_and_final_acl(env, removed_dependency):
    store, _, _ = env
    dep = store.submit("t", "seed", "dep", [change(module="dep")])["revisions"]["dep"]
    base = store.submit("t", "seed", "with-dep", [change(module="app", dependencies={"dep": dep})])["revisions"]["app"]
    denied = set()
    candidates = NativeCandidates(store, lambda db, t, a, m, action: (m, action) not in denied)
    changes = [change(base, module="app", **({"dependencies": {}} if removed_dependency else {}))]
    original = candidates.receive("t", "a", "acl", changes, ORIGIN)
    for module in ("app", "dep"):
        denied.add((module, "read"))
        before = snapshot(store)
        with pytest.raises(NativeStoreError, match="authorization"):
            candidates.receive("t", "a", "acl", changes, ORIGIN)
        with pytest.raises(NativeStoreError, match="authorization"):
            candidates.receipt("t", "a", "acl")
        assert snapshot(store) == before
        denied.clear()
    assert candidates.receipt("t", "a", "acl") == original
    assert candidates.receive("t", "a", "acl", changes, ORIGIN) == original


@pytest.mark.parametrize("field", ["origin", "tenant", "actor", "request_key", "request_digest", "id", "inputs"])
def test_corrupted_persisted_receipt_rejected_without_mutation(env, field):
    store, candidates, base = env
    changes = [change(base)]
    original = candidates.receive("t", "a", "corrupt", changes, ORIGIN)
    broken = json.loads(json.dumps(original))
    if field == "origin":
        broken[field]["worker_ref"] = "not-the-original-worker"
    elif field == "inputs":
        broken[field] = []
    else:
        broken[field] = "changed"
    with store._connection(write=True) as db:
        db.execute("UPDATE native_candidate_receipts SET result=?", (json.dumps(broken),))
    before = snapshot(store)
    with pytest.raises(NativeStoreError, match="integrity"):
        candidates.receive("t", "a", "corrupt", changes, ORIGIN)
    with pytest.raises(NativeStoreError, match="integrity"):
        candidates.receipt("t", "a", "corrupt")
    assert snapshot(store) == before


def test_actual_parallel_cli_no_git_restart(env, tmp_path):
    store, candidates, base = env
    cli = Path(__file__).with_name("native_candidates_cli.py")
    process_env = {**os.environ, "PATH": ""}
    procs = []
    for index, output in enumerate((b"same", b"same", b"distinct", b"fourth")):
        payload = [change(base, base64.b64encode(output).decode())]
        request = tmp_path / f"input{index}.json"
        request.write_text(json.dumps(payload))
        args = [
            sys.executable,
            str(cli),
            "--db",
            str(store.database),
            "--tenant",
            "t",
            "--actor",
            f"producer{index}",
            "--request-key",
            "run",
        ]
        procs.append((
            args,
            subprocess.Popen(
                args
                + [
                    "receive",
                    "--input",
                    str(request),
                    "--source-ref",
                    base,
                    "--worker-ref",
                    f"worker{index}",
                    "--issue-url",
                    ORIGIN["issue_url"],
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=process_env,
            ),
        ))
    # Shared head changes while independent processes are running.
    head = base
    for index in range(5):
        head = store.submit("t", "head-writer", f"advance{index}", [change(head, str(index).encode())])["revisions"][
            "m"
        ]
    results = []
    for args, proc in procs:
        out, err = proc.communicate(timeout=30)
        assert proc.returncode == 0, err + out
        result = json.loads(out)["data"]
        results.append(result)
        reread = subprocess.run(args + ["receipt"], capture_output=True, env=process_env, timeout=30)
        assert reread.returncode == 0
        assert json.loads(reread.stdout)["data"] == result
    assert len({r["id"] for r in results}) == 4
    assert len({r["revisions"]["m"] for r in results}) == 3
    assert store.head("t", "m") == head
    assert {r["origin"]["worker_ref"] for r in results} == {f"worker{i}" for i in range(4)}
    for index, result in enumerate(results):
        NativeWorkspace(store).materialize(
            "t", store.compose("t", result["revisions"])["modules"], tmp_path / f"recovered{index}"
        )


def test_database_failure_is_atomic_and_release_unchanged(env):
    from native_release import SCHEMA as RELEASE_SCHEMA

    store, candidates, base = env
    with store._connection() as db:
        db.executescript(RELEASE_SCHEMA)
        db.execute("INSERT INTO native_release_heads VALUES ('t','product','stable','original')")
        db.execute(
            "CREATE TRIGGER reject_receipt BEFORE INSERT ON native_candidate_receipts BEGIN SELECT RAISE(ABORT,'injected failure'); END"
        )
    before = snapshot(store)
    with pytest.raises(sqlite3.IntegrityError, match="injected failure"):
        candidates.receive("t", "a", "transaction", [change(base)], ORIGIN)
    assert snapshot(store) == before
    with store._connection() as db:
        db.execute("DROP TRIGGER reject_receipt")
    result = candidates.receive("t", "a", "transaction", [change(base)], ORIGIN)
    after = snapshot(store)
    for table in before:
        if table.startswith("native_release") or table == "native_heads":
            assert before[table] == after[table]
    assert result["state"] == "candidate_received"


def test_resource_metadata_and_cli_rejections(env, tmp_path):
    store, candidates, base = env
    cases = [
        (Limits(modules=1), [change(), change(module="n")]),
        (Limits(files=1), [change(reads=["a", "b"])]),
        (Limits(request_bytes=100), [change()]),
        (Limits(modules=1), [change(dependencies={"a": "0" * 64, "b": "0" * 64})]),
    ]
    before = snapshot(store)
    for limits, changes in cases:
        with pytest.raises(NativeStoreError):
            NativeCandidates(store, lambda *_: True, limits).receive("t", "a", "bounded", changes, ORIGIN)
    with pytest.raises(NativeStoreError):
        candidates.receipt("other", "a", "none")
    assert snapshot(store) == before
    cli = Path(__file__).with_name("native_candidates_cli.py")
    args = [
        sys.executable,
        str(cli),
        "--db",
        str(store.database),
        "--tenant",
        "t",
        "--actor",
        "a",
        "--request-key",
        "invalid",
        "receive",
        "--source-ref",
        base,
        "--worker-ref",
        "w",
        "--issue-url",
        ORIGIN["issue_url"],
    ]
    for raw in (b"[" * 2000, b" " * (Limits().request_bytes + 1), json.dumps([change(base, "!!bad!!")]).encode()):
        process = subprocess.run(args, input=raw, capture_output=True, timeout=30)
        assert process.returncode == 2
        assert json.loads(process.stdout)["ok"] is False
    assert snapshot(store) == before


def test_null_base_and_separate_request_namespace(env):
    store, candidates, base = env
    before_head = store.head("t", "m")
    result = candidates.receive("t", "seed", "seed", [change()], ORIGIN)
    assert store.revision("t", "m", result["revisions"]["m"])["parent"] is None
    assert store.head("t", "m") == before_head
    revoked = NativeCandidates(store, lambda *_: False)
    with pytest.raises(NativeStoreError, match="authorization"):
        revoked.receive("t", "seed", "seed", [change()], ORIGIN)
    with pytest.raises(NativeStoreError, match="authorization"):
        revoked.receipt("t", "seed", "seed")
