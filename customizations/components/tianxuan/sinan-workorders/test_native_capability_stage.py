"""Exercise a signed preview with an unavailable and then an available local capability."""

import hashlib
import json

import test_native_stage_admission
from test_native_issue_capabilities import classify
from test_native_stage_stop import PREVIEW, drive, install_preview, signed

fixture = test_native_stage_admission.fixture
host = test_native_stage_admission.host


def test_capability_gates_checked_preview(host, record_property):
    workflow = host.workflow
    issue = install_preview(host)
    classify(host, issue, ["capability:animation"]).raise_for_status()
    ticket = signed(host, issue)
    unavailable = drive(host)
    deferred = unavailable["result"]["deferred"]
    assert len(deferred) == 1 and deferred[0]["ticket"] == ticket
    assert deferred[0]["missingCapabilities"] == ["animation"]
    assert host.observations() == []

    workflow.catalog = [dict(id="local", available=True, targets=["agent"], capabilities=["animation"])]
    completed, replay = drive(host), drive(host)
    calls = unavailable["calls"] + completed["calls"] + replay["calls"]
    assert calls.count("execute") == calls.count("verify-stage") == 1
    assert not {"review", "publish", "finish", "complete", "integration-finish"}.intersection(calls)
    (stage,) = completed["result"]["stages"]
    assert not replay["result"].get("stages")
    status = host.api("status", key=ticket).raise_for_status().json()
    assert status["stage_result"] == stage and stage["state"] == "stage-reached"
    assert host.observations() == [dict(execution=ticket, grant=stage["authorization"])]
    artifact = workflow.worker.store.read(status["tenant"], "a", stage["modules"]["a"], "preview.svg")
    assert artifact.decode() == PREVIEW
    record_property(
        "capability_stage",
        json.dumps(
            dict(
                ticket=ticket,
                missing=deferred[0]["missingCapabilities"],
                candidate=stage["candidate"],
                stage=stage["state"],
                process_count=calls.count("execute"),
                delivery_calls=0,
                artifact_sha256=hashlib.sha256(artifact).hexdigest(),
            )
        ),
    )
