"""Version replacement and pinned dependency regressions with actual workers."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
import test_native_workflow
from native_store import NativeStoreError
from native_workflow import NativeWorkflow
from test_native_workflow import accept, reserve, task
from tianxuan_core import PermissionDenied

fixture = test_native_workflow.fixture


def replace(w, actor, key, **changes):
    old = json.loads(w.status(actor, key)["task"])
    fields = {
        k: old[k]
        for k in ("selected", "writes", "dependencies", "profile", "product", "checks", "mandate", "capabilities")
    }
    fields.update(changes)
    return w.authorize_task(actor, old["issue"], expected=key, **fields)


@pytest.mark.parametrize("source", ["original", "ancestor", "selected"])
def test_historical_source_read_checks_current_original_acl(fixture, source):
    w, owner, tenant, req, initial, _ = fixture
    invite = w.domain.create_invite(owner, "reader@example.invalid", "editor")
    reader = w.domain.accept_invite(invite["code"], "password")["user_id"]
    selected = {"a": initial["a"]}
    if source == "selected":
        original = w.domain.create_requirement(owner, "extra", "Original", "Secret", "Scope", "Pass")
        module = w.domain.bind_native_requirement(owner, original["id"])
        selected.update(
            w.worker.store.submit(
                tenant, owner, "extra", [dict(module=module, base=None, reads=None, edits={"text": b"secret"})]
            )["revisions"]
        )
    else:
        original = req
    old, issue = task(fixture, "a", selected)
    if source == "ancestor":
        parent = w.domain.create_issue(owner, "Parent", requirement_id=req["id"])
        with w._transaction() as db:
            db.execute("UPDATE issues SET requirement_id=NULL,parent_id=? WHERE id=?", (parent["id"], issue["id"]))
        old = replace(w, owner, old)
    reserve(fixture, old)
    before = w.status(reader, old)
    public = w.domain.create_requirement(owner, "public", "Public", "Public", "Scope", "Pass")
    # A privileged host migration can reparent an issue; no public mutation API
    # currently exposes this operation. History must still retain its own ACL.
    with w._transaction() as db:
        db.execute("UPDATE issues SET requirement_id=?,parent_id=NULL WHERE id=?", (public["id"], issue["id"]))
    new = replace(w, owner, old, selected={"a": initial["a"]})
    w.domain.set_visibility(owner, original["id"], "private")
    with pytest.raises(PermissionDenied):
        w.status(reader, old)
    assert w.status(owner, old) == before
    assert w.status(reader, new)["state"] == "ready"
    active = w.inspect(reader)["environment"]["active"]
    assert active == [{"ticket": "occupied-slot-0", "reads": [], "writes": []}]
    w.domain.set_visibility(owner, original["id"], "tenant")
    assert w.status(reader, old) == before


def test_revision_cas_idempotence_and_old_occupancy(fixture):
    w, actor, *_ = fixture
    old, issue = task(fixture, "a")
    reserve(fixture, old)
    before = w.status(actor, old)
    new = replace(w, actor, old, mandate="new mandate")
    assert replace(w, actor, old, mandate="new mandate") == new
    assert w.status(actor, old) == before
    with pytest.raises(NativeStoreError, match="active changed"):
        replace(w, actor, old, mandate="different replacement")
    with pytest.raises(NativeStoreError, match="superseded"):
        w.execute(actor, old)
    assert w.inspect(actor)["environment"]["active"][0]["ticket"] == old
    assert w.domain.get_issue(issue["id"])["status"] == "planned"
    latest = replace(w, actor, new, mandate="third")
    assert replace(w, actor, old, mandate="new mandate") == new
    assert (
        w.domain.db.execute("SELECT task FROM native_active_tasks WHERE issue=?", (issue["id"],)).fetchone()[0]
        == latest
    )


def test_actual_late_terminal_and_reconcile_do_not_close_new_definition(fixture):
    w, actor, *_ = fixture
    old, issue = task(fixture, "a")
    reserve(fixture, old)
    import threading

    entered = threading.Event()
    proceed = threading.Event()
    real_run = w.worker.run

    def run(*args):
        entered.set()
        assert proceed.wait(10)
        return real_run(*args)

    w.worker.run = run
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(w.execute, actor, old)
        assert entered.wait(10)
        new = replace(w, actor, old)
        assert w.status(actor, old)["state"] == "running"
        proceed.set()
        assert future.result()["state"] == "stopped"
    assert w.status(actor, new)["state"] == "ready"
    assert w.domain.get_issue(issue["id"])["status"] == "planned"
    # Simulate lost domain terminal commit; native worker retains its real receipt.
    with w._transaction() as db:
        db.execute("UPDATE native_tasks SET state='held',terminal=NULL WHERE id=?", (old,))
    assert w.reconcile(actor, old)["state"] == "stopped"
    assert not w.inspect(actor)["environment"]["active"]


def test_replaced_produced_candidate_cannot_publish_or_close(fixture):
    w, actor, tenant, *_ = fixture
    old, issue = task(fixture, "a")
    reserve(fixture, old)
    terminal = w.execute(actor, old)
    before = w.status(actor, old)
    new = replace(w, actor, old)
    retired = w.status(actor, old)
    assert retired["state"] == "superseded"
    assert retired["task"] == before["task"] and retired["terminal"] == before["terminal"]
    assert json.loads(retired["terminal"]) == terminal
    with pytest.raises(NativeStoreError):
        w.publish(actor, old, "stable", None)
    with pytest.raises(NativeStoreError):
        w.complete(actor, old, "stable")
    assert w.status(actor, new)["state"] == "ready"
    assert w.domain.get_issue(issue["id"])["status"] == "planned"


def test_historical_acceptance_survives_channel_and_active_definition_changes(fixture):
    w, actor, tenant, _, initial, _ = fixture
    old, _ = task(fixture, "a")
    reserve(fixture, old)
    w.execute(actor, old)
    accepted = accept(fixture, old)
    w.release.publish(tenant, "publisher", "reselect", "a", "stable", accepted["request"]["review"], accepted["id"])
    newer = replace(w, actor, old)
    assert w.status(actor, old)["state"] == "accepted"
    # Do not schedule new upstream for this fixed version consumer.
    with w._transaction() as db:
        db.execute("UPDATE native_tasks SET ready_at=ready_at+100 WHERE id=?", (newer,))
    downstream, _ = task(
        fixture,
        "c",
        {**accepted["modules"], "c": initial["c"]},
        {old: json.dumps(accepted, sort_keys=True, separators=(",", ":"), ensure_ascii=False)},
    )
    reserve(fixture, downstream)
    w.release.revoke(tenant, "publisher", "revoke-old", accepted["request"]["review"], "withdrawn")
    with pytest.raises(NativeStoreError, match="revoked"):
        w.execute(actor, downstream)


def test_persistent_old_schema_migration_and_old_writer_fail_closed(fixture):
    w, actor, *_ = fixture
    old, _ = task(fixture, "a")
    before = w.status(actor, old)
    db = w.domain.db
    with w._transaction():
        for action in ("INSERT", "UPDATE", "DELETE"):
            db.execute("DROP TRIGGER native_tasks_v2_" + action)
        db.execute("DROP TABLE native_active_tasks")
        db.execute("DROP TABLE native_task_revisions")
        db.execute("CREATE UNIQUE INDEX legacy_issue ON native_tasks(issue)")
    restored = NativeWorkflow(w.domain, w.worker, w.runner, w.release, w.authorize, catalog=w.catalog)
    assert restored.status(actor, old) == before
    new = replace(restored, actor, old)
    restarted = NativeWorkflow(w.domain, w.worker, w.runner, w.release, w.authorize, catalog=w.catalog)
    assert restarted.status(actor, new)["state"] == "ready"
    path = db.execute("PRAGMA database_list").fetchone()[2]
    with sqlite3.connect(path) as legacy:
        assert legacy.execute("SELECT count(*) FROM native_tasks").fetchone()[0] == 2
        with pytest.raises(sqlite3.OperationalError, match="native_workflow_version"):
            legacy.execute("UPDATE native_tasks SET state='running' WHERE id=?", (old,))


def test_authenticated_installed_revision_http(fixture):
    import socket
    import threading
    import time
    from contextlib import contextmanager

    import httpx
    import uvicorn
    from api import create_app

    @contextmanager
    def live_client(app):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started and time.monotonic() < deadline:
                time.sleep(0.01)
            assert server.started
            with httpx.Client(base_url=f"http://127.0.0.1:{listener.getsockname()[1]}") as client:
                yield client
        finally:
            server.should_exit = True
            thread.join(10)
            listener.close()

    w, actor, *_ = fixture
    old, issue = task(fixture, "a")
    data = json.loads(w.status(actor, old)["task"])
    w.installed_plan = lambda a, i: {
        k: data[k] for k in ("selected", "writes", "dependencies", "profile", "product", "checks", "mandate")
    }
    headers = {"Authorization": "Bearer " + w.domain.issue_session(actor)}
    with live_client(create_app(w.domain, native_store=w.worker.store, native_only=True, native_workflow=w)) as client:
        url = "/api/v1/native/workflow/revise"
        body = {"issue": issue["id"], "expected": old}
        assert client.post(url, json=body).status_code == 401
        result = client.post(url, json=body, headers=headers)
        assert result.status_code == 200, result.text
        assert result.json() != old
        assert client.post(url, json=body, headers=headers).json() == result.json()
        assert client.post(url, json={**body, "actor": actor}, headers=headers).status_code == 422
        stranger = w.domain.register("foreign", "foreign@example.invalid", "password")["user_id"]
        foreign = {"Authorization": "Bearer " + w.domain.issue_session(stranger)}
        assert client.post(url, json=body, headers=foreign).status_code in {403, 404}


def test_migration_failure_rolls_back_all_ddl(fixture):
    w, actor, *_ = fixture
    old, _ = task(fixture, "a")
    db = w.domain.db
    with w._transaction():
        for action in ("INSERT", "UPDATE", "DELETE"):
            db.execute("DROP TRIGGER native_tasks_v2_" + action)
        db.execute("DROP TABLE native_active_tasks")
        db.execute("DROP TABLE native_task_revisions")
        db.execute("CREATE UNIQUE INDEX legacy_issue ON native_tasks(issue)")
    before = w.status(actor, old)
    db.set_authorizer(
        lambda op, name, *args: (
            sqlite3.SQLITE_DENY if op == sqlite3.SQLITE_DROP_TABLE and name == "native_tasks_v1" else sqlite3.SQLITE_OK
        )
    )
    try:
        with pytest.raises(sqlite3.DatabaseError):
            NativeWorkflow(w.domain, w.worker, w.runner, w.release, w.authorize)
    finally:
        db.set_authorizer(None)
    assert w.status(actor, old) == before
    assert not db.execute("SELECT name FROM sqlite_master WHERE name='native_active_tasks'").fetchone()
    assert db.execute("SELECT name FROM sqlite_master WHERE name='legacy_issue'").fetchone()


def test_two_real_processes_compete_for_one_active_revision(fixture):
    import os
    import subprocess
    import sys

    w, actor, *_ = fixture
    old, _ = task(fixture, "a")
    data = json.loads(w.status(actor, old)["task"])
    path = w.domain.db.execute("PRAGMA database_list").fetchone()[2]
    code = """
import json,sys
from types import SimpleNamespace
from native_workflow import NativeWorkflow
from native_store import NativeStoreError
from tianxuan_core import Tianxuan
path,old,raw,mandate=sys.argv[1:]
t=json.loads(raw)
d=Tianxuan(path)
worker=SimpleNamespace(profiles={'local':{}},installation=lambda p:t['installation'],workspace=SimpleNamespace(sources=lambda tenant,selected:(selected,None)))
runner=SimpleNamespace(context=lambda check,candidate:t['check_contexts'][check])
w=NativeWorkflow(d,worker,runner,None,lambda *a:True)
plan={k:t[k] for k in ('selected','writes','dependencies','profile','product','checks')}
try:
 print(w.authorize_task(t['actor'],t['issue'],expected=old,mandate=mandate,**plan))
except NativeStoreError:
 sys.exit(3)
"""
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", code, path, old, json.dumps(data), value],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for value in ("first", "second")
    ]
    outputs = [p.communicate(timeout=30) for p in processes]
    assert sorted(p.returncode for p in processes) == [0, 3], outputs
    assert w.domain.db.execute("SELECT count(*) FROM native_tasks").fetchone()[0] == 2


@pytest.mark.parametrize("invalid", ["policy", "event", "authority", "integrity"])
def test_historical_release_rejects_invalid_original(fixture, invalid):
    w, actor, tenant, *_ = fixture
    old, _ = task(fixture, "a")
    reserve(fixture, old)
    w.execute(actor, old)
    accepted = accept(fixture, old)
    if invalid == "authority":
        w.release.authorize = lambda *args: False
    else:
        with w.release.store._connection(write=True) as db:
            if invalid == "event":
                db.execute("DELETE FROM native_release_events WHERE record=?", (accepted["id"],))
            elif invalid == "integrity":
                db.execute("UPDATE native_release_records SET payload='{}' WHERE id=?", (accepted["id"],))
            else:
                db.execute("DELETE FROM native_release_policy")
    with pytest.raises(NativeStoreError):
        w.release.historical(tenant, actor, "a", "stable", accepted["id"])


@pytest.mark.parametrize("change", ["cancel", "authority", "definition"])
def test_late_real_terminal_after_logical_stop_reconciles(fixture, change):
    w, actor, *_ = fixture
    key, issue = task(fixture, "a")
    reserve(fixture, key)
    # Produce an actual trusted receipt, then recover a lost domain commit.
    assert w.execute(actor, key)["state"] == "produced"
    with w._transaction() as db:
        db.execute("UPDATE native_tasks SET state='held',terminal=NULL WHERE id=?", (key,))
        if change == "definition":
            db.execute("UPDATE issues SET title='changed' WHERE id=?", (issue["id"],))
    if change == "cancel":
        w.domain.transition_issue(actor, issue["id"], "cancelled")
    if change == "authority":
        w.authorize = lambda a, i, action: action != "execute"
    assert w.reconcile(actor, key)["state"] == "stopped"
    assert not w.inspect(actor)["environment"]["active"]
