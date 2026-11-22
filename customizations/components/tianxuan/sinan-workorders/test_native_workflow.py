"""Real ordinary-file producers and checks; no model quality claims."""

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import issue_lifecycle
import pytest
from native_check_runner import NativeCheckRunner
from native_evidence import EvidenceCache
from native_release import NativeRelease
from native_store import NativeStore, NativeStoreError
from native_worker import NativeWorker
from native_workflow import NativeWorkflow
from tianxuan_core import PermissionDenied, Tianxuan, TransitionRejected


@pytest.fixture
def fixture(tmp_path):
    domain = Tianxuan(str(tmp_path / "domain.sqlite"))
    actor = domain.register("native", "native@example.invalid", "password")["user_id"]
    tenant = domain.actor_context(actor)["tenant"]
    req = domain.create_requirement(actor, "native", "Native", "Outcome", "Scope", "Pass")
    native = NativeStore(tmp_path / "native.sqlite")
    initial = native.submit(
        tenant, actor, "initial", [dict(module=m, base=None, reads=None, edits={"output": b"initial"}) for m in "abc"]
    )["revisions"]
    env = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR"}}
    python = str(Path(sys.executable).resolve(strict=True))
    code = (
        "import pathlib,time,json,os; p=pathlib.Path.cwd(); started=time.time_ns(); time.sleep(.4); "
        "m=json.loads(pathlib.Path(os.environ['NATIVE_CONTEXT']).read_text(encoding='utf-8'))['title']; "
        "text=' '.join((p/x/'output').read_text() for x in 'ab') if m=='c' else m+' produced'; "
        "(p/m/'output').write_text(text); (p.parent/'interval.json').write_text(json.dumps([started,time.time_ns()]))"
    )
    worker = NativeWorker(
        native,
        tmp_path / "workers",
        {"local": dict(argv=[python, "-c", code], env=env, timeout=5, log_bytes=4096)},
        lambda *a: True,
        authorize=lambda db, t, a, m, action: (
            t == tenant
            and a in {actor, "execution-producer"}
            and (m in "abc" or m.startswith("requirement-"))
            and action in {"read", "receive"}
        ),
    )
    cache = EvidenceCache(native, {"check": dict(version="1", reads=None, max_age_seconds=3600)}, lambda *a: True)
    (tmp_path / "checks").mkdir()
    check_code = "import pathlib,os; p=pathlib.Path(os.environ['DUOBAO_INPUT']); files=list(p.glob('*/output')); assert files; assert all(f.read_text() == ('a produced b produced' if f.parent.name=='c' else f.parent.name+' produced') for f in files)"
    runner = NativeCheckRunner(
        cache,
        tmp_path / "checks",
        {
            "check": dict(
                argv=[python, "-c", check_code],
                env=env,
                toolchain="a" * 64,
                environment="b" * 64,
                timeout=5,
                log_bytes=4096,
            )
        },
        lambda *a: True,
        lambda *a: True,
    )
    release = NativeRelease(
        cache, lambda db, t, a, p, act: a in {actor, "reviewer", "publisher"}, lambda db, t, c: {actor}
    )
    workflow = NativeWorkflow(
        domain,
        worker,
        runner,
        release,
        lambda *a: True,
        catalog=[dict(id="local", available=True, targets=["agent"], capabilities=[])],
    )
    try:
        yield workflow, actor, tenant, req, initial, tmp_path
    finally:
        domain.db.close()


def task(f, module, selected=None, dependencies=None):
    workflow, actor, tenant, req, initial, _ = f
    issue = workflow.domain.create_issue(actor, module, requirement_id=req["id"], acceptance="passed check")
    key = workflow.authorize_task(
        actor,
        issue["id"],
        selected=selected or {module: initial[module]},
        writes={module: "*"},
        dependencies=dependencies or {},
        profile="local",
        product=module,
        checks=["check"],
        mandate="authorized-test",
    )
    return key, issue


def reserve(f, key):
    workflow, actor, *_ = f
    task = json.loads(workflow.status(actor, key)["task"])
    assert workflow.reserve(
        actor,
        dict(ticket=key, sourceSnapshot={"source": key, "revision": task["source"]["revision"]}, model={"id": "local"}),
    )


def accept(f, key):
    workflow, actor, tenant, *_ = f
    row = workflow.status(actor, key)
    task_data, terminal = json.loads(row["task"]), json.loads(row["terminal"])
    candidate = terminal["candidate"]
    facts = workflow.check(actor, key)
    product = task_data["product"]
    workflow.release.configure(
        tenant,
        "publisher",
        product,
        dict(checks={"check": workflow.runner.context("check", candidate)}, review_max_age_seconds=3600),
    )
    review = workflow.release.approve(
        tenant,
        "reviewer",
        "review-" + key,
        product,
        candidate,
        {"check": facts["check"]["evidence"]},
        "Read exact candidate",
    )
    workflow.release.publish(tenant, "publisher", "publish-" + key, product, "stable", review["id"], None)
    return workflow.complete(actor, key, "stable")


def test_actual_parallel_producers_completion_and_replay(fixture):
    w, actor, tenant, req, initial, _ = fixture
    a, ia = task(fixture, "a")
    b, ib = task(fixture, "b")
    reserve(fixture, a)
    reserve(fixture, b)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda key: w.execute(actor, key), [a, b]))
    intervals = [json.loads((w.worker.root / key / "interval.json").read_text()) for key in [a, b]]
    assert max(x[0] for x in intervals) < min(x[1] for x in intervals)
    assert all(r["state"] == "produced" for r in results)
    with pytest.raises(TransitionRejected):
        w.domain.transition_issue(actor, ia["id"], "done")
    with pytest.raises(NativeStoreError):
        w.complete(actor, a, "stable")
    aa, ab = accept(fixture, a), accept(fixture, b)
    assert w.complete(actor, a, "stable") == aa
    assert w.domain.sync_progress(req["id"], actor=actor)["done"] == 2
    assert w.execute(actor, a)["state"] == "accepted"
    assert w.worker.store.read(tenant, "a", aa["modules"]["a"], "output") == b"a produced"
    assert ab["state"] == "content_selected"
    selected = {**aa["modules"], **ab["modules"], "c": initial["c"]}
    ic = w.domain.create_issue(actor, "c", requirement_id=req["id"], acceptance="passed check")
    w.next_issues = lambda operator, event: [ic["id"]]
    w.installed_plan = lambda operator, issue: dict(
        selected=selected,
        writes={"c": "*"},
        dependencies={a: w.status(actor, a)["acceptance"], b: w.status(actor, b)["acceptance"]},
        profile="local",
        product="c",
        checks=["check"],
        mandate="authorized-test",
    )
    continued = w.advance(actor)
    assert len(set(continued)) == 1
    c = continued[0]
    assert w.advance(actor) == []
    reserve(fixture, c)
    assert w.execute(actor, c)["state"] == "produced"
    ac = accept(fixture, c)
    assert w.worker.store.read(tenant, "c", ac["modules"]["c"], "output") == b"a produced b produced"
    assert w.domain.sync_progress(req["id"], actor=actor)["percent"] == 100
    assert w.domain.get_issue(ic["id"])["status"] == "done"


def test_acl_and_stable_definition(fixture):
    w, owner, _, req, _, _ = fixture
    invite = w.domain.create_invite(owner, "other@example.invalid", "editor")
    other = w.domain.accept_invite(invite["code"], "password")["user_id"]
    _, issue = task(fixture, "a")
    before = w.domain.issue_snapshot(owner, issue["id"])
    w.domain.transition_issue(owner, issue["id"], "in-progress")
    assert w.domain.issue_snapshot(owner, issue["id"]) == before
    w.domain.set_visibility(owner, req["id"], "private")
    assert w.domain.list_issues(other) == []


def test_unknown_reservation_survives_restart(fixture):
    w, actor, *_ = fixture
    key, _ = task(fixture, "a")
    reserve(fixture, key)
    with w._transaction() as db:
        db.execute("UPDATE native_tasks SET state='held' WHERE id=?", (key,))
    restarted = NativeWorkflow(w.domain, w.worker, w.runner, w.release, w.authorize)
    assert restarted.execute(actor, key)["state"] == "held"
    assert restarted.inspect(actor)["environment"]["active"][0]["ticket"] == key


def test_actual_node_authenticated_http_dispatch(fixture):
    import uvicorn
    from api import create_app

    w, actor, tenant, req, initial, _ = fixture
    identities = {role: "execution-" + role for role in ["producer", "checker", "reviewer", "publisher"]}
    w.principals = lambda operator, issue, role: identities[role] if operator == actor else None
    w.release.authorize = lambda db, t, a, p, action: t == tenant and a in {actor, *identities.values()}
    w.release.contributors = lambda db, t, c: {identities["producer"]}
    reviewed = []

    def review(operator, contract, terminal):
        # Independent fixture reviewer actually reads the exact immutable output.
        with w.worker.store._connection() as db:
            candidate = json.loads(
                db.execute(
                    "SELECT payload FROM native_compositions WHERE tenant=? AND id=?", (tenant, terminal["candidate"])
                ).fetchone()[0]
            )
        for module in contract["writes"]:
            output = w.worker.store.read(tenant, module, candidate["modules"][module], "output")
            if output != (b"a produced b produced" if module == "c" else (module + " produced").encode()):
                return False
        reviewed.append(terminal["candidate"])
        return True

    w.review_candidate = review
    w.installed_target = lambda operator, contract: {"channel": "stable", "expected": None}
    for module in "abc":
        w.release.configure(
            tenant,
            identities["publisher"],
            module,
            dict(checks={"check": w.runner.context("check", "0" * 64)}, review_max_age_seconds=3600),
        )
    a, _ = task(fixture, "a")
    b, _ = task(fixture, "b")
    ic = w.domain.create_issue(actor, "c", requirement_id=req["id"], acceptance="passed check")
    w.next_issues = lambda operator, event: (
        [ic["id"]] if all(w.status(operator, k)["state"] == "accepted" for k in [a, b]) else []
    )

    def plan(operator, issue):
        assert issue == ic["id"]
        dependencies = {key: w.status(operator, key)["acceptance"] for key in [a, b]}
        selected = {"c": initial["c"]}
        for acceptance in dependencies.values():
            selected.update(json.loads(acceptance)["modules"])
        return dict(
            selected=selected,
            writes={"c": "*"},
            dependencies=dependencies,
            profile="local",
            product="c",
            checks=["check"],
            mandate="authorized-test",
        )

    w.installed_plan = plan
    app = create_app(w.domain, native_store=w.worker.store, native_only=True, native_workflow=w)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started
        node = shutil.which("node")
        assert node
        env = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR"}}
        env.update(
            PATH="", NATIVE_SERVICE_URL=f"http://127.0.0.1:{port}", NATIVE_SERVICE_TOKEN=w.domain.issue_session(actor)
        )
        process = subprocess.run(
            [node, str(Path(__file__).with_name("native_dispatch.mjs"))],
            env=env,
            capture_output=True,
            timeout=20,
            text=True,
        )
        assert process.returncode == 0, process.stderr
        dispatch = json.loads(process.stdout)
        assert len(dispatch["results"]) == 3, dispatch
        for item in dispatch["results"]:
            assert item["state"] == "running", (item.get("stage"), item.get("reason"))
        assert dispatch["errors"] == [], dispatch
        assert len(dispatch["deliveries"]) == 3
        assert all(w.status(actor, k)["state"] == "accepted" for k in [a, b])
        assert w.domain.get_issue(ic["id"])["status"] == "done"
        assert w.domain.sync_progress(req["id"], actor=actor)["percent"] == 100
        assert len(reviewed) == 3
        intervals = [json.loads((w.worker.root / key / "interval.json").read_text()) for key in [a, b]]
        assert max(x[0] for x in intervals) < min(x[1] for x in intervals)
        repeat = subprocess.run(
            [node, str(Path(__file__).with_name("native_dispatch.mjs"))],
            env=env,
            capture_output=True,
            timeout=20,
            text=True,
        )
        assert json.loads(repeat.stdout)["results"] == []
        assert json.loads(repeat.stdout)["deliveries"] == []
        assert len(reviewed) == 3
    finally:
        server.should_exit = True
        thread.join(10)
        listener.close()
    from fastapi.testclient import TestClient

    token = w.domain.issue_session(actor)
    headers = {"Authorization": "Bearer " + token}
    # Same interpreter/store: disable and restore only the optional host entry.
    with TestClient(create_app(w.domain, native_store=w.worker.store, native_only=True)) as client:
        assert client.post("/api/v1/native/workflow/status", json={"key": a}, headers=headers).status_code == 404
    with TestClient(create_app(w.domain, native_store=w.worker.store, native_only=True, native_workflow=w)) as client:
        assert (
            client.post("/api/v1/native/workflow/status", json={"key": a}, headers=headers).json()["state"]
            == "accepted"
        )


def test_bad_content_cannot_release(fixture):
    w, actor, tenant, *_ = fixture
    key, _ = task(fixture, "a")
    # Actual failed content check over immutable candidate, not a forged outcome.
    initial = json.loads(w.status(actor, key)["task"])["selected"]
    candidate = w.worker.store.compose(tenant, initial)["id"]
    result = w.runner.execute(tenant, actor, "bad-content", candidate, "check")
    assert result["outcome"] == "failed"
    w.release.configure(
        tenant,
        "publisher",
        "a",
        dict(checks={"check": w.runner.context("check", candidate)}, review_max_age_seconds=3600),
    )
    with pytest.raises(NativeStoreError):
        w.release.approve(
            tenant, "reviewer", "bad-review", "a", candidate, {"check": result["evidence"]}, "cannot accept"
        )


def test_installation_change_holds_without_launch(fixture):
    w, actor, *_ = fixture
    key, _ = task(fixture, "a")
    reserve(fixture, key)
    w.worker.profiles["local"]["argv"][-1] = "print('changed')"
    with pytest.raises(NativeStoreError, match="installation changed"):
        w.execute(actor, key)
    assert w.status(actor, key)["state"] == "held"
    assert not (w.worker.root / key).exists()


def test_release_before_domain_failure_replays_without_worker(fixture, monkeypatch):
    w, actor, _, req, *_ = fixture
    key, issue = task(fixture, "a")
    reserve(fixture, key)
    w.execute(actor, key)
    real = w.domain.sync_progress
    monkeypatch.setattr(
        w.domain, "sync_progress", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("injected domain failure"))
    )
    with pytest.raises(RuntimeError):
        accept(fixture, key)
    assert w.domain.get_issue(issue["id"])["status"] != "done"
    assert w.status(actor, key)["state"] == "produced"
    monkeypatch.setattr(w.domain, "sync_progress", real)
    w.complete(actor, key, "stable")
    assert w.domain.sync_progress(req["id"], actor=actor)["percent"] == 100
    assert w.domain.db.execute("SELECT count(*) FROM native_outbox WHERE id=?", (key,)).fetchone()[0] == 1


def test_private_link_and_ancestor_hidden_from_all_lists(fixture):
    w, owner, _, req, *_ = fixture
    invite = w.domain.create_invite(owner, "reader@example.invalid", "editor")
    reader = w.domain.accept_invite(invite["code"], "password")["user_id"]
    parent = w.domain.create_issue(owner, "private", requirement_id=req["id"])
    public = w.domain.create_requirement(owner, "public", "Public", "Outcome", "Scope", "Pass")
    child = w.domain.create_issue(owner, "child", parent_id=parent["id"], requirement_id=public["id"])
    w.domain.link_doc_issue(owner, public["id"], child["id"])
    w.domain.set_visibility(owner, req["id"], "private")
    assert w.domain.list_doc_issues(reader, public["id"]) == []
    assert w.domain.list_issues(reader) == []
    assert w.domain.requirement_snapshot(reader, public["id"])["issues"] == []


def test_single_operator_independent_execution_review_replay(fixture):
    w, actor, tenant, *_ = fixture
    identities = {role: "execution-" + role for role in ["producer", "checker", "reviewer", "publisher"]}
    w.principals = lambda operator, issue, role: identities[role] if operator == actor else None
    calls = []
    w.review_candidate = lambda operator, task, terminal: calls.append(terminal["candidate"]) is None
    w.release.authorize = lambda db, t, a, p, action: t == tenant and a in {actor, *identities.values()}
    w.release.contributors = lambda db, t, c: {identities["producer"]}
    key, _ = task(fixture, "a")
    reserve(fixture, key)
    result = w.execute(actor, key)
    w.release.configure(
        tenant,
        identities["publisher"],
        "a",
        dict(checks={"check": w.runner.context("check", result["candidate"])}, review_max_age_seconds=3600),
    )
    review = w.review(actor, key)
    assert w.review(actor, key) == review
    w.publish(actor, key, "stable", None)
    assert calls == [result["candidate"]]
    w.complete(actor, key, "stable")


def test_failed_check_does_not_consume_independent_review(fixture):
    w, actor, tenant, *_ = fixture
    w.principals = lambda operator, issue, role: "reviewer" if role == "reviewer" else actor
    calls = []
    w.review_candidate = lambda *args: calls.append(args) is None
    key, _ = task(fixture, "a")
    selected = json.loads(w.status(actor, key)["task"])["selected"]
    candidate = w.worker.store.compose(tenant, selected)["id"]
    with w._transaction() as db:
        db.execute(
            "UPDATE native_tasks SET state='produced',terminal=? WHERE id=?",
            (json.dumps({"state": "produced", "candidate": candidate}), key),
        )
    with pytest.raises(NativeStoreError, match="checks failed"):
        w.review(actor, key)
    assert calls == []
    assert w.domain.db.execute("SELECT count(*) FROM native_workflow_reviews").fetchone()[0] == 0


def test_finish_pins_target_and_recovers_after_progress_failure(fixture, monkeypatch):
    w, actor, tenant, *_ = fixture
    w.principals = lambda operator, issue, role: {"reviewer": "reviewer", "publisher": "publisher"}.get(role, actor)
    calls = []
    w.review_candidate = lambda *args: calls.append("review") is None
    w.installed_target = lambda *args: {"channel": "stable", "expected": None}
    key, _ = task(fixture, "a")
    reserve(fixture, key)
    terminal = w.execute(actor, key)
    w.release.configure(
        tenant,
        "publisher",
        "a",
        dict(checks={"check": w.runner.context("check", terminal["candidate"])}, review_max_age_seconds=3600),
    )
    sync = w.domain.sync_progress
    monkeypatch.setattr(
        w.domain, "sync_progress", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("progress fault"))
    )
    with pytest.raises(RuntimeError, match="progress fault"):
        w.finish(actor, key)
    w.installed_target = lambda *args: {"channel": "other", "expected": "changed"}
    monkeypatch.setattr(w.domain, "sync_progress", sync)
    assert w.finish(actor, key)["state"] == "accepted"
    assert calls == ["review"]
    saved = json.loads(
        w.domain.db.execute("SELECT target FROM native_workflow_targets WHERE task=?", (key,)).fetchone()[0]
    )
    assert saved == {"channel": "stable", "expected": None}


def test_authenticated_reconcile_durable_terminal_only(fixture):
    w, actor, *_ = fixture
    key, _ = task(fixture, "a")
    reserve(fixture, key)
    w.execute(actor, key)
    with w._transaction() as db:
        db.execute("UPDATE native_tasks SET state='held',terminal=NULL WHERE id=?", (key,))
    assert w.reconcile(actor, key)["state"] == "produced"
    with w._transaction() as db:
        db.execute("UPDATE native_tasks SET state='held',terminal=NULL WHERE id=?", (key,))
    with w.worker.store._connection(write=True) as db:
        db.execute("DELETE FROM native_worker_terminals_v2 WHERE execution=?", (key,))
        db.execute("DELETE FROM native_worker_closed WHERE execution=?", (key,))
    assert w.reconcile(actor, key)["state"] == "closed-unresolved"


def test_fifo_and_managed_done_tool_guard(fixture):
    w, actor, *_ = fixture
    a, issue = task(fixture, "a")
    b, _ = task(fixture, "b")
    task_b = json.loads(w.status(actor, b)["task"])
    assert not w.reserve(
        actor,
        dict(ticket=b, sourceSnapshot={"source": b, "revision": task_b["source"]["revision"]}, model={"id": "local"}),
    )
    reserve(fixture, a)
    reserve(fixture, b)
    with pytest.raises(TransitionRejected):
        w.domain.dispatch_tool(
            actor, "issue.transition", {"issue_id": issue["id"], "to_status": "done"}, call_id="bypass"
        )


def test_release_revoke_serializes_after_domain_acceptance(fixture, monkeypatch):
    w, actor, tenant, *_ = fixture
    key, issue = task(fixture, "a")
    reserve(fixture, key)
    w.execute(actor, key)
    complete = w._complete_guarded
    monkeypatch.setattr(w, "_complete_guarded", lambda *a: (_ for _ in ()).throw(RuntimeError("before domain")))
    with pytest.raises(RuntimeError):
        accept(fixture, key)
    monkeypatch.setattr(w, "_complete_guarded", complete)
    selected = w.release.selected(tenant, actor, "a", "stable")
    attempted, revoked = threading.Event(), threading.Event()
    errors = []

    def revoke():
        attempted.set()
        try:
            w.release.revoke(tenant, "publisher", "race-revoke", selected["request"]["review"], "withdraw")
            revoked.set()
        except Exception as error:
            errors.append(error)

    thread = threading.Thread(target=revoke)
    progress = w.domain.sync_progress

    def during_commit(*args, **kwargs):
        thread.start()
        assert attempted.wait(2)
        assert not revoked.wait(0.1)
        return progress(*args, **kwargs)

    monkeypatch.setattr(w.domain, "sync_progress", during_commit)
    w.complete(actor, key, "stable")
    thread.join(5)
    assert not errors
    assert revoked.is_set()
    assert w.domain.get_issue(issue["id"])["status"] == "done"
    # Historical completion remains; revoked acceptance cannot release new work.
    with pytest.raises(NativeStoreError):
        w.complete(actor, key, "stable")


def test_definition_change_and_replayed_manual_done_fail_closed(fixture):
    w, actor, *_ = fixture
    key, issue = task(fixture, "a")
    with w._transaction() as db:
        db.execute("UPDATE issues SET acceptance='changed criterion' WHERE id=?", (issue["id"],))
    task_data = json.loads(w.status(actor, key)["task"])
    with pytest.raises(NativeStoreError, match="definition changed"):
        w.reserve(
            actor,
            dict(
                ticket=key,
                sourceSnapshot={"source": key, "revision": task_data["source"]["revision"]},
                model={"id": "local"},
            ),
        )
    # A historical legacy receipt is not an authorization to close managed work.
    manual = w.domain.create_issue(actor, "manual")
    for state in ["planned", "in-progress", "in-review"]:
        w.domain.transition_issue(actor, manual["id"], state)
    evidence = w.domain.add_issue_comment(actor, manual["id"], "Manual deliverable reviewed")
    current = issue_lifecycle.read(w.domain, actor, manual["id"], manual["project"])
    issue_lifecycle.mutate(
        w.domain,
        actor,
        manual["id"],
        manual["project"],
        "accept",
        expected_version=current["version"],
        revision=current["revision"],
        comment=evidence["id"],
        call_id="manual-accept",
        asset_version=current["asset_version"],
    )
    w.domain.transition_issue(actor, manual["id"], "done", call_id="old-done")
    with w._transaction() as db:
        db.execute("INSERT INTO native_managed_issues VALUES (?,?,NULL)", (manual["id"], "host-bound-test"))
    with pytest.raises(TransitionRejected):
        w.domain.transition_issue(actor, manual["id"], "done", call_id="old-done")


def test_unavailable_head_and_server_capability_admission(fixture):
    w, actor, _, req, initial, _ = fixture
    issue = w.domain.create_issue(actor, "unavailable", requirement_id=req["id"])
    a = w.authorize_task(
        actor,
        issue["id"],
        selected={"a": initial["a"]},
        writes={"a": "*"},
        dependencies={},
        profile="local",
        product="a",
        checks=["check"],
        mandate="test",
        capabilities=["unavailable-capability"],
    )
    b, _ = task(fixture, "b")
    contract = json.loads(w.status(actor, a)["task"])
    assert not w.reserve(
        actor,
        dict(ticket=a, sourceSnapshot={"source": a, "revision": contract["source"]["revision"]}, model={"id": "local"}),
    )
    reserve(fixture, b)
    assert w.status(actor, a)["state"] == "ready"


def test_foreign_and_private_occupancy_is_anonymous(fixture):
    w, actor, _, req, *_ = fixture
    key, _ = task(fixture, "a")
    reserve(fixture, key)
    other = w.domain.register("other", "other@example.invalid", "password")["user_id"]
    invited = w.domain.create_invite(actor, "member@example.invalid", "editor")
    member = w.domain.accept_invite(invited["code"], "password")["user_id"]
    w.domain.set_visibility(actor, req["id"], "private")
    for reader in [other, member]:
        board = w.inspect(reader)
        assert len(board["environment"]["active"]) == 1
        assert board["requests"] == []
        assert key not in json.dumps(board) and str(w.worker.root) not in json.dumps(board)
        assert board["environment"]["active"][0]["writes"] == []


def test_cancel_during_real_production_preserves_business_stop(fixture):
    w, actor, *_ = fixture
    key, issue = task(fixture, "a")
    reserve(fixture, key)
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(w.execute, actor, key)
        deadline = time.monotonic() + 10
        while w.status(actor, key)["state"] != "running":
            assert time.monotonic() < deadline
            time.sleep(0.005)
        w.domain.transition_issue(actor, issue["id"], "cancelled")
        assert future.result(timeout=15)["state"] == "stopped"
    row = w.status(actor, key)
    assert json.loads(row["terminal"])["state"] == "produced"
    assert w.domain.get_issue(issue["id"])["status"] == "cancelled"
    with pytest.raises(NativeStoreError):
        w.check(actor, key)
    with pytest.raises(NativeStoreError):
        w.complete(actor, key, "stable")


def test_revoked_transitive_source_acl_prevents_materialization(fixture):
    w, owner, tenant, req, initial, _ = fixture
    invite = w.domain.create_invite(owner, "input-reader@example.invalid", "editor")
    reader = w.domain.accept_invite(invite["code"], "password")["user_id"]
    secret = w.domain.create_requirement(owner, "secret", "Secret", "Input", "Scope", "Pass")
    module = w.domain.bind_native_requirement(owner, secret["id"])
    w.domain.set_visibility(owner, secret["id"], "private")
    w.domain.share_doc(owner, secret["id"], reader, "read")
    revision = w.worker.store.submit(
        tenant,
        owner,
        "secret",
        [dict(module=module, base=None, reads=None, edits={"snapshot.json": b"private-canary"})],
    )["revisions"][module]
    linked = w.worker.store.submit(
        tenant,
        owner,
        "linked",
        [dict(module="a", base=initial["a"], reads=None, edits={}, dependencies={module: revision})],
    )["revisions"]["a"]
    issue = w.domain.create_issue(reader, "a", requirement_id=req["id"])
    plan = dict(
        selected={"a": linked},
        writes={"a": "*"},
        dependencies={},
        profile="local",
        product="a",
        checks=["check"],
        mandate="test",
    )
    key = w.authorize_task(reader, issue["id"], **plan)
    contract = json.loads(w.status(reader, key)["task"])
    assert module in contract["selected"]
    assignment = dict(
        ticket=key, sourceSnapshot={"source": key, "revision": contract["source"]["revision"]}, model={"id": "local"}
    )
    assert w.reserve(reader, assignment)
    w.domain.unshare_doc(owner, secret["id"], reader)
    with pytest.raises(PermissionDenied):
        w.execute(reader, key)
    with pytest.raises(PermissionDenied):
        w.authorize_task(reader, issue["id"], **plan)
    assert not (w.worker.root / key).exists()


def test_outbox_isolates_failed_branch(fixture):
    w, actor, *_ = fixture
    a, _ = task(fixture, "a")
    b, _ = task(fixture, "b")
    for key in [a, b]:
        reserve(fixture, key)
        w.execute(actor, key)
        accept(fixture, key)
    calls = []

    def resolver(operator, event):
        calls.append(event["reference"])
        if event["reference"] == a:
            raise RuntimeError("private resolver diagnostic")
        return []

    w.next_issues = resolver
    report = w.advance(actor, isolate=True)
    assert calls == [a, b]
    assert report == {"authorized": [], "errors": [{"event": a, "reason": "RuntimeError"}]}
    assert w.domain.db.execute("SELECT id FROM native_outbox_consumed").fetchone()[0] == b
    assert w.advance(actor, isolate=True, exclude=[a]) == {"authorized": [], "errors": []}
    assert calls == [a, b]


def test_review_cancellation_cannot_publish(fixture):
    w, actor, tenant, *_ = fixture
    key, issue = task(fixture, "a")
    reserve(fixture, key)
    terminal = w.execute(actor, key)
    w.principals = lambda operator, issue, role: "reviewer" if role == "reviewer" else "publisher"
    w.release.configure(
        tenant,
        "publisher",
        "a",
        dict(checks={"check": w.runner.context("check", terminal["candidate"])}, review_max_age_seconds=3600),
    )

    def review(*args):
        w.domain.transition_issue(actor, issue["id"], "cancelled")
        return True

    w.review_candidate = review
    with pytest.raises(NativeStoreError, match="stopped"):
        w.publish(actor, key, "stable", None)
    assert w.release.selected(tenant, actor, "a", "stable") is None


def test_publication_guard_covers_native_commit(fixture, monkeypatch):
    from contextlib import contextmanager

    w, actor, tenant, *_ = fixture
    key, issue = task(fixture, "a")
    reserve(fixture, key)
    terminal = w.execute(actor, key)
    w.principals = lambda operator, issue, role: "reviewer" if role == "reviewer" else "publisher"
    w.review_candidate = lambda *args: True
    w.release.configure(
        tenant,
        "publisher",
        "a",
        dict(checks={"check": w.runner.context("check", terminal["candidate"])}, review_max_age_seconds=3600),
    )
    original_guard = w._publication_guard
    observed = []

    @contextmanager
    def guard(operator, task_key, native_db):
        with original_guard(operator, task_key, native_db):
            yield
            # A separate connection must see selection before domain guard exits.
            observed.append(w.release.selected(tenant, actor, "a", "stable"))

    monkeypatch.setattr(w, "_publication_guard", guard)
    selected = w.publish(actor, key, "stable", None)
    assert observed == [selected]
    assert w.complete(actor, key, "stable") == selected


def test_publication_guard_rechecks_after_review_before_sql(fixture, monkeypatch):
    w, actor, tenant, *_ = fixture
    key, issue = task(fixture, "a")
    reserve(fixture, key)
    terminal = w.execute(actor, key)
    w.principals = lambda operator, issue, role: "reviewer" if role == "reviewer" else "publisher"
    w.review_candidate = lambda *args: True
    w.release.configure(
        tenant,
        "publisher",
        "a",
        dict(checks={"check": w.runner.context("check", terminal["candidate"])}, review_max_age_seconds=3600),
    )
    publish = w.release.publish

    def after_review(*args, **kwargs):
        w.domain.transition_issue(actor, issue["id"], "cancelled")
        return publish(*args, **kwargs)

    monkeypatch.setattr(w.release, "publish", after_review)
    with pytest.raises(NativeStoreError, match="stopped"):
        w.publish(actor, key, "stable", None)
    assert w.release.selected(tenant, actor, "a", "stable") is None


def test_actual_node_refills_before_unrelated_terminal(fixture):
    node = shutil.which("node")
    assert node
    script = r"""
import {driveNative} from './native_dispatch.mjs';
const states={A:'ready',B:'ready',C:'ready'}, trace=[];
let releaseA, startedC;
const gate=new Promise(resolve=>releaseA=resolve), c=new Promise(resolve=>startedC=resolve);
const service=async(op,value)=>{
 const key=value.key??value.assignment?.ticket;
 if(op==='advance')return {authorized:[],errors:[]};
 if(op==='inspect'){
  const ready=Object.keys(states).filter(k=>states[k]==='ready');
  return {snapshot:{items:ready.map(key=>({key,source:key,dispatchCandidate:true})),ready,sourceSnapshots:ready.map(source=>({source,revision:'v1'}))},
   environment:{capacity:2,catalog:[{id:'local',available:true,targets:['agent'],capabilities:[]}],active:Object.keys(states).filter(k=>states[k]==='running').map(ticket=>({ticket,reads:[],writes:['/work/'+ticket]}))},
   requests:ready.map(ticket=>({ticket,outcome:ticket,owner:'actor',acceptance:'pass',authorityRef:'test',capabilities:[],contextRefs:[],reads:[],writes:['/work/'+ticket],model:'local'})),
   produced:Object.keys(states).filter(k=>states[k]==='produced')};
 }
 if(op==='revalidate')return states[key]==='ready';
 if(op==='reserve'){if(states[key]!=='ready')return false;states[key]='running';return true;}
 if(op==='start')return {reference:key};
 if(op==='execute'){
  trace.push('start '+key);if(key==='A')await gate;if(key==='C')startedC();
  states[key]='produced';trace.push('terminal '+key);return {state:'produced',id:key,worker_ref:'native-worker:'+key};
 }
 if(op==='finish'){states[key]='accepted';trace.push('accepted '+key);return {state:'accepted'};}
 return {};
};
const running=driveNative(service);
let timer;
try {
 await Promise.race([c,new Promise((_,reject)=>timer=setTimeout(()=>reject(Error('C never started while A held')),5000))]);
 if(states.A!=='running')throw Error('A gate was not held');
} finally {clearTimeout(timer);releaseA();}
const result=await running;
if(result.errors.length||result.results.length!==3||Object.values(states).some(s=>s!=='accepted'))throw Error(JSON.stringify(result));
if(trace.indexOf('start C')>trace.indexOf('terminal A'))throw Error('batch barrier');
console.log(JSON.stringify({trace,result}));
"""
    process = subprocess.run(
        [node, "--input-type=module"],
        input=script,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent,
        timeout=20,
    )
    assert process.returncode == 0, process.stderr
    trace = json.loads(process.stdout)["trace"]
    assert trace.index("start C") < trace.index("terminal A")
