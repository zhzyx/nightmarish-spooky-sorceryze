"""Drive the installed dispatcher and verify the signed preview boundary over authenticated HTTP."""

import hashlib
import json
import os
import shutil
import socket
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import test_native_stage_admission
import uvicorn
from native_candidates import NativeCandidates
from native_execution_host import WorkflowService
from native_integration import NativeIntegration
from native_workflow import NativeWorkflow
from tianxuan_core import Tianxuan

fixture = test_native_stage_admission.fixture
host = test_native_stage_admission.host

CRITERION = "preview.svg shows one blue circle of radius 12"
PREVIEW = '<svg xmlns="http://www.w3.org/2000/svg"><circle cx="16" cy="16" r="12" fill="blue"/></svg>'


def install_preview(h, *, color="blue"):
    # Use the A03 signed local plan, with a concrete preview producer and
    # an independently installed content check that opens the immutable bytes.
    w = h.workflow
    profile = w.worker.profiles["local"]
    h.plan.update(writes={"a": ["preview.svg"]}, stage_criteria=CRITERION)
    preview = PREVIEW.replace("blue", color)
    probe = Path(profile["argv"][1])
    probe.write_text(
        "import json, os, pathlib\n"
        "context = pathlib.Path(os.environ['NATIVE_CONTEXT'])\n"
        "grant = json.loads(context.read_text(encoding='utf-8'))['stage_authorization']\n"
        "with open(os.environ['PROBE_CALLS'], 'a', encoding='utf-8') as calls:\n"
        "    print(json.dumps(dict(execution=context.parent.name, grant=grant)), file=calls)\n"
        f"pathlib.Path('a/preview.svg').write_bytes({preview.encode()!r})\n",
        encoding="utf-8",
    )
    spec = w.runner._registry["check"]
    spec["argv"] = [
        spec["argv"][0],
        "-c",
        "import os, pathlib, xml.etree.ElementTree as E; "
        "root=E.parse(pathlib.Path(os.environ['DUOBAO_INPUT'])/'a/preview.svg').getroot(); "
        "ns='{http://www.w3.org/2000/svg}'; circle,=list(root); "
        "assert root.tag==ns+'svg' and circle.tag==ns+'circle' and "
        "circle.get('fill')=='blue' and circle.get('r')=='12'",
    ]
    return h.issues[0]


def signed(h, issue):
    h.target(issue, criteria=CRITERION)
    h.confirm(issue).raise_for_status()
    return h.api("authorize", issue=issue["id"]).raise_for_status().json()


def drive(h):
    """Run the shipped Node dispatcher and count its actual HTTP requests."""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(h.client.app, log_level="error", ws="none"))
        thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started and time.monotonic() < deadline:
                time.sleep(0.01)
            assert server.started
            env = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR"}}
            env.update(
                DISPATCH=Path(__file__).with_name("native_dispatch.mjs").as_uri(),
                URL=f"http://127.0.0.1:{port}",
                TOKEN=h.workflow.domain.issue_session(h.actor),
            )
            process = subprocess.run(
                [
                    shutil.which("node"),
                    "--input-type=module",
                    "-e",
                    """
                    const {driveNative,httpService}=await import(process.env.DISPATCH);
                    const service=httpService(process.env.URL,process.env.TOKEN), calls=[];
                    const result=await driveNative((operation,payload)=>{
                      calls.push(operation); return service(operation,payload);
                    });
                    console.log(JSON.stringify({result,calls}));
                """,
                ],
                env=env,
                capture_output=True,
                text=True,
                check=True,
                timeout=25,
            )
            return json.loads(process.stdout)
        finally:
            server.should_exit = True
            thread.join(timeout=5)


@pytest.mark.parametrize("color,state", [("blue", "stage-reached"), ("red", "stage-unmet")])
def test_dispatch_stops_at_checked_preview(host, color, state, record_property):
    h = host
    w = h.workflow
    issue = install_preview(h, color=color)
    key = signed(h, issue)
    first = drive(h)
    second = drive(h)
    assert first["result"]["errors"] == second["result"]["errors"] == []
    assert first["result"]["deliveries"] == second["result"]["deliveries"] == []
    calls = first["calls"] + second["calls"]
    delivery = {
        op: calls.count(op)
        for op in (
            "finish",
            "review",
            "publish",
            "complete",
            "integration-contribution",
            "integration-finish",
        )
    }
    assert not any(delivery.values())
    assert calls.count("execute") == calls.count("verify-stage") == 1
    (launch,) = first["result"]["results"]
    assert launch["receipt"]["workerId"] == launch["receipt"]["reference"] == key
    assert launch["receipt"]["worker_ref"] == "native-worker:" + key
    row = h.api("status", key=key).raise_for_status().json()
    assert row["state"] == state and row["acceptance"] is None
    result = row["stage_result"]
    assert first["result"]["stages"] == [result]
    assert h.api("verify-stage", key=key).raise_for_status().json() == result
    assert h.api("inspect").json()["stage_checks"] == []
    task, terminal = json.loads(row["task"]), json.loads(row["terminal"])
    assert result["task"] == key and result["state"] == state
    assert result["candidate"] == terminal["candidate"] and result["modules"] == terminal["modules"]
    assert terminal["exit_code"] == 0 and terminal["state"] == "produced"
    assert h.observations() == [dict(execution=key, grant=result["authorization"])]
    assert result["authorization"] == task["source"]["definition"]["stage_authorization"]
    assert result["reason"] == ("authorized_stage_criteria_met" if color == "blue" else "authorized_stage_check_failed")
    check = w.runner.status(task["tenant"], h.actor, key + "-check")
    assert result["checks"]["check"] == dict(evidence=check["evidence"], outcome=check["outcome"])
    assert check["outcome"] == ("passed" if color == "blue" else "failed")
    assert check["candidate"] == result["candidate"]
    assert set(terminal["intake"]["inputs"]["a"]["edits"]) == {"preview.svg"}
    artifact = w.worker.store.read(task["tenant"], "a", result["modules"]["a"], "preview.svg")
    assert artifact.decode() == PREVIEW.replace("blue", color)
    for op, extra in [
        ("finish", {}),
        ("review", {}),
        ("publish", dict(channel="stable", expected=None)),
        ("complete", dict(channel="stable")),
    ]:
        assert "limited to its authorized stage" in h.api(op, key=key, **extra).json()["detail"]
    with w.domain._connection_lock:
        assert not w.domain.db.execute("SELECT * FROM native_outbox WHERE id=?", (key,)).fetchall()
    domain = Tianxuan(str(h.calls.parent / "domain.sqlite"))
    try:
        restored = NativeWorkflow(domain, w.worker, w.runner, w.release, w.authorize)
        assert restored.status(h.actor, key)["stage_result"] == result
    finally:
        domain.db.close()
    with w.worker.store._connection() as db:
        physical = db.execute("SELECT payload FROM native_worker_process_closures WHERE execution=?", (key,)).fetchall()
        assert len(physical) == 1
        closure = json.loads(physical[0]["payload"])
        assert closure["exit_code"] == 0 and not closure["reasons"]
    record_property(
        "observation",
        json.dumps(
            dict(
                physical_closure=closure,
                receiver=result,
                artifact=dict(path="a/preview.svg", svg=artifact.decode(), sha256=hashlib.sha256(artifact).hexdigest()),
                dispatch_calls=calls,
                delivery_calls=delivery,
                physical_producer_calls=len(h.observations()),
                check_exit=check["exit_code"],
                restarted_receipt_equal=True,
                outbox_events=0,
            )
        ),
    )


def test_unbound_and_mismatched_criteria(host):
    h = host
    issue = install_preview(h)
    h.target(issue, criteria=CRITERION)
    h.confirm(issue).raise_for_status()
    h.plan["stage_criteria"] = "some other criterion"
    assert h.api("authorize", issue=issue["id"]).status_code == 409
    del h.plan["stage_criteria"]
    key = h.api("authorize", issue=issue["id"]).raise_for_status().json()
    assert h.reserve(key).json() is True
    assert h.api("execute", key=key).json()["state"] == "produced"
    board = h.api("inspect").json()
    assert board["produced"] == board["stage_checks"] == []
    assert h.api("status", key=key).json()["stage_result"]["reason"] == "stage_criteria_check_unbound"
    assert h.api("verify-stage", key=key).status_code == h.api("finish", key=key).status_code == 409


def test_revocation_during_stage_check(host, monkeypatch):
    h = host
    issue = install_preview(h)
    key = signed(h, issue)
    assert h.reserve(key).json() is True
    assert h.api("execute", key=key).json()["state"] == "produced"
    original = h.workflow.runner.execute

    def revoke(*args):
        fact = original(*args)
        assert fact["outcome"] == "passed"
        h.confirm(issue, "revoked").raise_for_status()
        return fact

    monkeypatch.setattr(h.workflow.runner, "execute", revoke)
    assert h.api("verify-stage", key=key).status_code == 409
    assert h.api("status", key=key).json()["stage_result"]["state"] == "pending"
    assert h.api("inspect").json()["stage_checks"] == []
    assert h.api("publish", key=key, channel="stable", expected=None).status_code == 409


def test_revoked_evidence_and_contribution_never_release(host):
    h = host
    issue = install_preview(h)
    h.plan["delivery_mode"] = "contribution"
    key = signed(h, issue)
    w = h.workflow
    NativeIntegration(w, NativeCandidates(w.worker.store, lambda *args: True), lambda *args: {})
    assert h.reserve(key).json() is True
    assert h.api("execute", key=key).json()["state"] == "produced"
    assert h.api("inspect").json()["contributions"] == []
    assert WorkflowService(w, h.actor, lambda: True, [issue["id"]]).call("inspect", {})["stage_checks"] == [key]
    assert WorkflowService(w, h.actor, lambda: True, []).call("inspect", {})["stage_checks"] == []
    assert "limited to its authorized stage" in h.api("integration-contribution", key=key).json()["detail"]
    fact = h.api("check", key=key).raise_for_status().json()["check"]
    tenant = w.domain.actor_context(h.actor)["tenant"]
    w.runner.cache.revoke(tenant, h.actor, fact["evidence"], "fixture withdrawal")
    assert h.api("verify-stage", key=key).status_code == 409
    assert h.api("status", key=key).json()["stage_result"]["state"] == "pending"


def test_simultaneous_settlement_reuses_exact_check(host, monkeypatch):
    h = host
    key = signed(h, install_preview(h))
    assert h.reserve(key).json() is True
    assert h.api("execute", key=key).json()["state"] == "produced"
    assert h.api("check", key=key).json()["check"]["outcome"] == "passed"
    w = h.workflow
    barrier = threading.Barrier(2, timeout=10)
    original = w.runner.execute

    def checked(*args):
        fact = original(*args)
        barrier.wait()
        return fact

    monkeypatch.setattr(w.runner, "execute", checked)
    with ThreadPoolExecutor(2) as pool:
        receipts = list(pool.map(lambda _: h.api("verify-stage", key=key).raise_for_status().json(), range(2)))
    assert receipts[0] == receipts[1] == h.api("status", key=key).json()["stage_result"]
    events = [e for e in w.domain.events(h.actor) if e["type"] == "native.stage-reached"]
    assert len(events) == len(h.observations()) == 1
