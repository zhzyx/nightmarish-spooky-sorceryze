"""Reopen four real task states in a fresh service process without executing them."""

import json
import os
import subprocess
import sys
from contextlib import contextmanager

import test_native_stage_admission as admission
import test_native_stage_stop as stage
import test_native_workflow as native

fixture = native.fixture
host = admission.host


def test_reopen_four_states_and_isolate_owner(fixture, record_property):
    workflow, actor, tenant, requirement, initial, folder = fixture
    domain = workflow.domain

    def ordinary(module, project="studio"):
        issue = domain.create_issue(
            actor, module, requirement_id=requirement["id"], acceptance="exact", project=project
        )
        return workflow.authorize_task(
            actor,
            issue["id"],
            selected={module: initial[module]},
            writes={module: "*"},
            dependencies={},
            profile="local",
            product=module,
            checks=["check"],
            mandate="installed-test-plan",
        )

    accepted = ordinary("b")
    native.reserve(fixture, accepted)
    assert workflow.execute(actor, accepted)["state"] == "produced"
    native.accept(fixture, accepted)
    # The real c producer requires a and b; supplying only c makes it exit with failure.
    failed = ordinary("c")
    native.reserve(fixture, failed)
    assert workflow.execute(actor, failed)["state"] == "failed"
    with contextmanager(admission.host.__wrapped__)(fixture) as host:
        stage.install_preview(host)
        waiting = stage.signed(host, host.issues[0])
        assert host.reserve(waiting).raise_for_status().json()
        assert host.api("execute", key=waiting).raise_for_status().json()["state"] == "produced"
        assert host.api("verify-stage", key=waiting).raise_for_status().json()["state"] == "stage-reached"
        ready = stage.signed(host, host.issues[1])
        elsewhere = ordinary("a", project="elsewhere")
        owner_token = domain.issue_session(actor)
        invite = domain.create_invite(actor, "peer@example.invalid", "editor")
        peer = domain.accept_invite(invite["code"], "password")["user_id"]
        assert domain.actor_context(peer)["tenant"] == tenant
        peer_token = domain.issue_session(peer)
        # This peer can already see the shared task in the issue system.
        assert domain.issue_snapshot(peer, host.issues[1]["id"])
        expected = host.api("recovery", project="studio").raise_for_status().json()
    domain.db.close()
    code = """
import json, os, sys
from api import create_app
from fastapi.testclient import TestClient
from native_workflow import NativeWorkflow
from tianxuan_core import Tianxuan

owner, peer = json.load(sys.stdin)
domain = Tianxuan(sys.argv[1])
workflow = NativeWorkflow(domain, None, None, None, lambda *args: True)
with TestClient(create_app(domain, native_workflow=workflow)) as client:
    def read(token, project):
        return client.post('/api/v1/native/workflow/recovery', json={'project':project},
                           headers={'Authorization':'Bearer '+token}).raise_for_status().json()
    print(json.dumps({'pid':os.getpid(), 'owner':read(owner,'studio'), 'peer':read(peer,'studio'),
                      'other_project':read(owner,'elsewhere')}))
domain.db.close()
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(folder / "domain.sqlite")],
        input=json.dumps([owner_token, peer_token]),
        text=True,
        capture_output=True,
        timeout=30,
        env=dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path)),
    )
    assert result.returncode == 0, result.stderr
    reopened = json.loads(result.stdout)
    assert reopened["owner"] == expected and expected["next_cursor"] is None
    assert reopened["peer"] == {"items": [], "next_cursor": None}
    (other,) = reopened["other_project"]["items"]
    assert other["checkpoint"]["task"] == elsewhere and other["checkpoint"]["project"] == "elsewhere"
    outcomes = {i["checkpoint"]["task"]: i["category"] for i in expected["items"]}
    assert outcomes == {
        accepted: "completed",
        failed: "needs-attention",
        waiting: "awaiting-confirmation",
        ready: "resumable",
    }
    assert all(i["checkpoint"]["project"] == "studio" for i in expected["items"])
    assert len(host.observations()) == 1
    record_property("recovery_list", json.dumps({"original_pid": os.getpid(), **reopened}))


def test_visible_ready_task_with_withdrawn_execution_is_not_resumable(host):
    issue = stage.install_preview(host)
    key = stage.signed(host, issue)
    host.workflow.authorize = lambda actor, issue, action: action == "read"
    response = host.api("recovery", project="studio").raise_for_status().json()
    (item,) = response["items"]
    assert item["category"] == "needs-attention" and item["reason"] == "authorization-unavailable"
    assert item["checkpoint"]["task"] == key and item["checkpoint"]["state"] == "ready"
    assert host.observations() == []
