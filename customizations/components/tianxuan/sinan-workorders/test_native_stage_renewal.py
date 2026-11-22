"""Continue a checked preview through the authenticated host on its exact module revision."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
import test_native_stage_stop as preview
from api import create_app
from fastapi.testclient import TestClient
from native_workflow import NativeWorkflow
from test_native_issue_capabilities import classify
from tianxuan_core import Tianxuan

fixture = preview.fixture
host = preview.host

NEXT = "package contains the SHA-256 of the verified preview.svg"


def install_package(h):
    local = h.workflow.worker.profiles["local"]
    probe = h.calls.parent / "package.py"
    probe.write_text(
        "import hashlib, json, os, pathlib\n"
        "context = pathlib.Path(os.environ['NATIVE_CONTEXT'])\n"
        "grant = json.loads(context.read_text(encoding='utf-8'))['stage_authorization']\n"
        "digest = hashlib.sha256(pathlib.Path('a/preview.svg').read_bytes()).hexdigest()\n"
        "with open(os.environ['PROBE_CALLS'], 'a', encoding='utf-8') as log:\n"
        "    print(json.dumps(dict(execution=context.parent.name, grant=grant, input_sha256=digest)), file=log)\n"
        "pathlib.Path('a/package.sha256').write_bytes(digest.encode())\n",
        encoding="utf-8",
    )
    local["argv"] = [local["argv"][0], str(probe)]
    spec = h.workflow.runner._registry["check"]
    spec["argv"] = [
        spec["argv"][0],
        "-c",
        "import hashlib, os, pathlib; a=pathlib.Path(os.environ['DUOBAO_INPUT'])/'a'; "
        "assert (a/'package.sha256').read_text()==hashlib.sha256((a/'preview.svg').read_bytes()).hexdigest()",
    ]
    spec["toolchain"] = "c" * 64
    h.plan.update(stage="package", stage_criteria=NEXT, writes={"a": ["package.sha256"]})


def renew(h, key, grant):
    return h.api(
        "renew-stage", key=key, target_revision=grant["target_revision"], confirmation_revision=grant["revision"]
    )


def test_explicit_renewal_pins_preview_and_executes_only_next_stage(host, record_property):
    h, w = host, host.workflow
    issue = preview.install_preview(h)
    classify(h, issue, ["capability:art"]).raise_for_status()
    w.catalog[0]["capabilities"] = ["art"]
    key = preview.signed(h, issue)
    first = preview.drive(h)
    reached = h.api("status", key=key).raise_for_status().json()["stage_result"]
    assert first["result"]["stages"] == [reached] and reached["state"] == "stage-reached"
    assert renew(h, key, h.detail(issue)["task_confirmation"]).status_code == 409
    install_package(h)
    h.target(issue, "package", NEXT, revision=1)
    assert h.api("renew-stage", key=key, target_revision=2, confirmation_revision=1).status_code == 409
    grant = h.confirm(issue).raise_for_status().json()
    assert renew(h, key, {**grant, "revision": grant["revision"] - 1}).status_code == 409
    assert "explicit renewal" in h.api("revise", issue=issue["id"], expected=key).json()["detail"]
    idle = preview.drive(h)
    assert "execute" not in idle["calls"] and "verify-stage" not in idle["calls"]
    assert h.api("status", key=key).json()["stage_result"] == reached
    tenant = w.domain.actor_context(h.actor)["tenant"]
    artifact = w.worker.store.read(tenant, "a", reached["modules"]["a"], "preview.svg")
    digest = hashlib.sha256(artifact).hexdigest()
    assert artifact.decode() == preview.PREVIEW and len(h.observations()) == 1
    with ThreadPoolExecutor(2) as pool:
        receipts = list(pool.map(lambda _: renew(h, key, grant).raise_for_status().json(), range(2)))
    receipt = receipts[0]
    assert receipts[1] == receipt and receipt["from"] == reached
    successor = receipt["task"]
    assert successor != key and receipt["authorization"]["confirmed_by"] == h.actor
    task = json.loads(h.api("status", key=successor).json()["task"])
    assert task["previous"] == key and task["selected"]["a"] == reached["modules"]["a"] != h.plan["selected"]["a"]
    assert task["stage_renewal"] == {"from": reached, "authorization": receipt["authorization"]}
    assert task["capabilities"] == task["source"]["definition"]["required_capabilities"] == ["art"]
    w.catalog[0]["capabilities"] = []
    assert h.reserve(successor).json() is False
    assert len(h.observations()) == 1
    w.catalog[0]["capabilities"] = ["art"]
    second = preview.drive(h)
    for run in (first, second):
        assert run["calls"].count("execute") == run["calls"].count("verify-stage") == 1
    final = h.api("status", key=successor).raise_for_status().json()["stage_result"]
    assert second["result"]["stages"] == [final] and final["state"] == "stage-reached"
    assert final["candidate"] != reached["candidate"] and final["authorization"] == receipt["authorization"]
    assert digest == w.worker.store.read(tenant, "a", final["modules"]["a"], "package.sha256").decode()
    assert w.worker.store.read(tenant, "a", final["modules"]["a"], "preview.svg") == artifact
    # Fresh domain connection and coordinator, same durable workflow and native store.
    domain = Tianxuan(str(h.calls.parent / "domain.sqlite"))
    try:
        restored = NativeWorkflow(domain, w.worker, w.runner, w.release, w.authorize, catalog=w.catalog)
        with TestClient(
            create_app(domain, native_store=w.worker.store, native_workflow=restored), headers=h.client.headers
        ) as client:
            h.client = client
            assert renew(h, key, grant).raise_for_status().json() == receipt
            assert h.api("status", key=key).json()["stage_result"] == reached
            assert h.api("status", key=successor).json()["stage_result"] == final
            assert h.api("status", key=successor).json()["stage_renewal"] == receipt
            replay = preview.drive(h)
            assert "execute" not in replay["calls"] and "verify-stage" not in replay["calls"]
    finally:
        domain.db.close()
    observations = h.observations()
    assert [o["execution"] for o in observations] == [key, successor] and observations[1]["input_sha256"] == digest
    with w.worker.store._connection() as db:
        closures = {
            r["execution"]: json.loads(r["payload"])
            for r in db.execute("SELECT execution,payload FROM native_worker_process_closures")
        }
    assert set(closures) == {key, successor} and all(
        c["exit_code"] == 0 and not c["reasons"] for c in closures.values()
    )
    record_property(
        "observation",
        json.dumps(
            dict(
                receiver=receipt,
                next_result=final,
                physical_calls=observations,
                physical_closures=closures,
                preview_sha256=digest,
                package_contents=digest,
                dispatch=[r["calls"] for r in (first, idle, second, replay)],
                restarted_receipt_equal=True,
                capabilities=task["capabilities"],
            )
        ),
    )


@pytest.mark.parametrize("case", ["unmet", "criteria", "actor", "definition", "withdrawn"])
def test_invalid_renewal_preserves_preview(host, case):
    h = host
    issue = preview.install_preview(h, color="red" if case == "unmet" else "blue")
    key = preview.signed(h, issue)
    assert h.reserve(key).json() is True
    h.api("execute", key=key).raise_for_status()
    result = h.api("verify-stage", key=key).raise_for_status().json()
    if case == "withdrawn":
        tenant = h.workflow.domain.actor_context(h.actor)["tenant"]
        h.workflow.runner.cache.revoke(tenant, h.actor, result["checks"]["check"]["evidence"], "preview withdrawn")
    install_package(h)
    if case == "definition":
        classify(h, issue, ["capability:new"]).raise_for_status()
    h.target(issue, "package", NEXT, revision=1)
    grant = h.confirm(issue).raise_for_status().json()
    if case == "criteria":
        del h.plan["stage_criteria"]
    if case == "actor":
        other = h.workflow.domain.add_member(h.actor, "other@example.invalid", "fixture-pass")["user_id"]
        h.client.headers["Authorization"] = "Bearer " + h.workflow.domain.issue_session(other)
    assert renew(h, key, grant).status_code == (403 if case == "actor" else 409)
    assert h.api("status", key=key).json()["stage_result"] == result
    assert h.api("inspect").json()["snapshot"]["ready"] == [] and len(h.observations()) == 1


def test_revised_issue_can_rework_the_same_stage(host):
    h = host
    issue = preview.install_preview(h)
    key = preview.signed(h, issue)
    assert h.reserve(key).json() is True
    h.api("execute", key=key).raise_for_status()
    result = h.api("verify-stage", key=key).raise_for_status().json()
    classify(h, issue, ["capability:revised"]).raise_for_status()
    h.confirm(issue).raise_for_status()
    replacement = h.api("revise", issue=issue["id"], expected=key).raise_for_status().json()
    assert replacement != key and h.api("status", key=key).json()["stage_result"] == result
    task = json.loads(h.api("status", key=replacement).json()["task"])
    assert "stage_renewal" not in task and task["capabilities"] == ["revised"]
