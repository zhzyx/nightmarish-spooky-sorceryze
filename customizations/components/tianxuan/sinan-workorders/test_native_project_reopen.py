"""Exercise the project reopen event against real signed workers and immutable stage checks."""

import hashlib
import json
from pathlib import Path

import pytest
import test_native_stage_stop as stage

fixture = stage.fixture
host = stage.host


def install(h):
    issue = stage.install_preview(h)
    # Both fixture processes append their own PID before doing any work.
    # A repeated physical start stays visible even if the receipt key is reused.
    profile = h.workflow.worker.profiles["local"]
    probe = Path(profile["argv"][1])
    producer = probe.read_text(encoding="utf-8")
    probe.write_text(producer.replace("dict(execution=", "dict(pid=os.getpid(), execution="), encoding="utf-8")
    checker = h.workflow.runner._registry["check"]
    journal = h.calls.parent / "check-starts.jsonl"
    checker["env"]["CHECK_STARTS"] = str(journal)
    checker["argv"][-1] = (
        "import json,os; "
        "f=open(os.environ['CHECK_STARTS'],'a',encoding='utf-8'); "
        "print(json.dumps({'pid':os.getpid()}),file=f); f.close(); " + checker["argv"][-1]
    )
    return issue


def reopen(h, project="studio", **kwargs):
    return h.client.post("/api/v1/native/workflow/recover-project", params={"project": project}, json={}, **kwargs)


def snapshot(h, key):
    return h.api("checkpoint", key=key).raise_for_status().json()


def count_processes(h):
    journal = h.calls.parent / "check-starts.jsonl"
    checks = [json.loads(line)["pid"] for line in journal.read_text().splitlines()] if journal.exists() else []
    return {"workers": [obs["pid"] for obs in h.observations()], "checkers": checks}


def verify_received(h, key, before):
    w = h.workflow
    after = snapshot(h, key)
    grant = after["authorization"]["stage"]
    assert after["authorization"] == before["authorization"] and after["target"] == before["target"]
    assert after["completed_steps"] == ["authorized", "reserved", "worker-terminal", "stage-checked"]
    assert after["state"] == after["stage_receipt"]["state"] == "stage-reached"
    receipt = after["stage_receipt"]
    assert receipt["task"] == key and receipt["authorization"] == grant
    assert receipt["candidate"] == after["candidate"] and receipt["modules"] == after["artifact_revisions"]
    assert after["pending_decision"] == {"kind": "stage-confirmation", "task": key}
    row = h.api("status", key=key).raise_for_status().json()
    terminal = json.loads(row["terminal"])
    assert terminal["exit_code"] == 0 and row["acceptance"] is None
    assert h.detail(h.issues[0])["task_confirmation"]["revision"] == grant["confirmation_revision"]
    assert w.domain.db.execute("SELECT COUNT(*) FROM native_outbox WHERE id=?", (key,)).fetchone()[0] == 0
    (worker,) = h.observations()
    assert worker["execution"] == key and worker["grant"] == grant and worker["pid"] > 0
    with w.worker.store._connection() as db:
        (closed,) = db.execute(
            "SELECT payload FROM native_worker_process_closures WHERE execution=?", (key,)
        ).fetchall()
    closure = json.loads(closed[0])
    assert closure["exit_code"] == 0 and not closure["reasons"]
    tenant = w.domain.actor_context(h.actor)["tenant"]
    check = w.runner.status(tenant, h.actor, key + "-check")
    assert receipt["checks"]["check"] == {"evidence": check["evidence"], "outcome": "passed"}
    assert check["exit_code"] == 0
    output = w.worker.store.read(tenant, "a", receipt["modules"]["a"], "preview.svg")
    assert output.decode() == stage.PREVIEW
    counts = count_processes(h)
    assert len(counts["workers"]) == len(counts["checkers"]) == 1 and counts["checkers"][0] != worker["pid"]
    return dict(
        before=before,
        after=after,
        processes=counts,
        physical_closure=closure,
        checker_exit=check["exit_code"],
        artifact_sha256=hashlib.sha256(output).hexdigest(),
    )


@pytest.mark.parametrize("boundary", ["ready", "reserved", "produced"])
def test_continue_from_each_confirmed_boundary(host, boundary, record_property):
    h = host
    issue = install(h)
    key = stage.signed(h, issue)
    if boundary in {"reserved", "produced"}:
        assert h.reserve(key).raise_for_status().json()
    if boundary == "produced":
        assert h.api("execute", key=key).raise_for_status().json()["state"] == "produced"
    before = snapshot(h, key)
    assert before["state"] == boundary
    launches = count_processes(h)
    original_grant = h.detail(issue)["task_confirmation"]
    assert reopen(h).raise_for_status().json() == dict(continued=1, errors=0, parked=0, deferred=0)
    result = verify_received(h, key, before)
    if boundary == "produced":
        assert launches["workers"] == result["processes"]["workers"]
        assert before["candidate"] == result["after"]["candidate"]
    assert reopen(h).raise_for_status().json() == dict(continued=0, errors=0, parked=0, deferred=0)
    assert snapshot(h, key) == result["after"] and count_processes(h) == result["processes"]
    assert h.detail(issue)["task_confirmation"] == original_grant
    record_property("reopen", json.dumps(result))


@pytest.mark.parametrize("control", ["pause", "cancel", "revoke"])
def test_reopen_respects_current_scope_and_controls(host, control):
    h = host
    issue = install(h)
    key = stage.signed(h, issue)
    domain = h.workflow.domain
    invite = domain.create_invite(h.actor, "peer@example.invalid", "editor")
    peer = domain.accept_invite(invite["code"], "password")["user_id"]
    assert domain.issue_snapshot(peer, issue["id"])
    token = domain.issue_session(peer)
    empty = dict(continued=0, errors=0, parked=0, deferred=0)
    assert reopen(h, headers={"Authorization": "Bearer " + token}).raise_for_status().json() == empty
    assert reopen(h, project="elsewhere").raise_for_status().json() == empty
    assert snapshot(h, key)["state"] == "ready"
    if control == "revoke":
        h.confirm(issue, "revoked").raise_for_status()
    else:
        revision = h.api("status", key=key).json()["progress"]["control"]["revision"]
        h.api(control, issue=issue["id"], key=key, expected=revision).raise_for_status()
    before = snapshot(h, key)
    assert reopen(h).raise_for_status().json() == empty
    assert snapshot(h, key) == before and count_processes(h) == {"workers": [], "checkers": []}


def test_reopen_settles_ordinary_pinned_publication(fixture):
    import test_native_workflow as native
    from api import create_app
    from fastapi.testclient import TestClient

    workflow, actor, tenant, *_ = fixture
    workflow.principals = lambda owner, issue, role: {"reviewer": "reviewer", "publisher": "publisher"}.get(role, actor)
    reviewed = []

    def review(operator, task, terminal):
        output = workflow.worker.store.read(tenant, "a", terminal["modules"]["a"], "output")
        assert output == b"a produced"
        reviewed.append(terminal["candidate"])
        return True

    workflow.review_candidate = review
    workflow.installed_target = lambda *args: {"channel": "stable", "expected": None}
    key, issue = native.task(fixture, "a")
    native.reserve(fixture, key)
    terminal = workflow.execute(actor, key)
    workflow.release.configure(
        tenant,
        "publisher",
        "a",
        dict(checks={"check": workflow.runner.context("check", terminal["candidate"])}, review_max_age_seconds=3600),
    )
    headers = {"Authorization": "Bearer " + workflow.domain.issue_session(actor)}
    with TestClient(create_app(workflow.domain, native_workflow=workflow), headers=headers) as client:

        def receive():
            return (
                client
                .post("/api/v1/native/workflow/recover-project", params={"project": issue["project"]}, json={})
                .raise_for_status()
                .json()
            )

        assert receive() == dict(continued=1, parked=0, errors=0, deferred=0)
        accepted = workflow.status(actor, key)
        assert (
            accepted["state"] == "accepted" and json.loads(accepted["acceptance"])["candidate"] == terminal["candidate"]
        )
        assert receive() == dict(continued=0, parked=0, errors=0, deferred=0)
        assert (
            reviewed == [terminal["candidate"]] and workflow.status(actor, key)["acceptance"] == accepted["acceptance"]
        )


def test_unmet_stage_stops_and_is_not_retried(host):
    h = host
    issue = stage.install_preview(h, color="red")
    key = stage.signed(h, issue)
    assert reopen(h).raise_for_status().json()["continued"] == 1
    failed = snapshot(h, key)
    assert failed["state"] == "stage-unmet" and failed["stage_receipt"]["checks"]["check"]["outcome"] == "failed"
    assert reopen(h).raise_for_status().json()["continued"] == 0
    assert snapshot(h, key) == failed and len(h.observations()) == 1
