"""Signed issue capabilities cross the normal HTTP board and installed Sinan dispatcher."""

import json
import os
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

import test_native_stage_admission
import uvicorn
from native_entry_factory import installed_profile

fixture = test_native_stage_admission.fixture
host = test_native_stage_admission.host


def classify(h, issue, labels, headers=None):
    detail = h.detail(issue)
    return h.client.put(
        f"/api/v1/issues/{issue['id']}/classification",
        params={"project": "studio"},
        headers=headers,
        json=dict(type=detail["type"], expected_type=detail["type"], expected_labels=detail["labels"], labels=labels),
    )


def dispatch(h):
    # Expose the same authenticated ASGI app and call its ordinary Node HTTP adapter.
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    server = uvicorn.Server(uvicorn.Config(h.client.app, log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started
        adapter = Path(__file__).with_name("native_dispatch.mjs").resolve().as_uri()
        script = """
            const {httpService, dispatchNative} = await import(process.argv[1]);
            const service = httpService(process.env.TEST_URL, process.env.TEST_TOKEN);
            const board = await service('inspect', {});
            const batch = await dispatchNative({type:'user.requested', reference:'signed-capabilities'},
                board.requests, service, async assignment => {
                    const row = await service('execute', {key:assignment.ticket});
                    if (row.state !== 'produced') throw Error(row.state);
                    return {workerId:row.id, reference:row.id, model:assignment.model.id, target:assignment.target};
                });
            console.log(JSON.stringify(batch));
        """
        result = subprocess.run(
            [shutil.which("node"), "--input-type=module", "-e", script, adapter],
            env=dict(
                os.environ,
                TEST_URL=f"http://127.0.0.1:{listener.getsockname()[1]}",
                TEST_TOKEN=h.workflow.domain.issue_session(h.actor),
            ),
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return json.loads(result.stdout)
    finally:
        server.should_exit = True
        thread.join(10)
        listener.close()


def test_module_requests_match_or_report_missing_capability(host, record_property):
    h, w = host, host.workflow
    capabilities = ["coding", "animation"]
    modules = [
        w.domain.create_business_module(h.actor, "studio", name, call_id=name)["id"]
        for name in ("Movement", "Animation")
    ]
    items = [
        dict(paragraph=i + 1, title="Preview", module_id=module, acceptance="visible")
        for i, module in enumerate(modules)
    ]
    issues = w.domain.split_design(h.actor, h.doc, 1, "studio", items, "module-split")
    requirements = [["coding"], ["animation"], ["animation", "mesh-rigging"]]
    issues.append(w.domain.split_design(h.actor, h.doc, 1, "studio", [items[1]], "rig-split")[0])
    w.catalog = [dict(id=c, available=True, targets=["agent"], capabilities=["review", c]) for c in capabilities]
    probe = h.calls.parent / "capability_probe.py"
    probe.write_text(
        "import json, os, pathlib\n"
        "context = pathlib.Path(os.environ['NATIVE_CONTEXT'])\n"
        "definition = json.loads(context.read_text(encoding='utf-8'))\n"
        "module = os.environ['OUTPUT_MODULE']\n"
        "pathlib.Path(module, 'output').write_text(module, encoding='utf-8')\n"
        "(context.parent / 'observed.json').write_text(json.dumps(definition), encoding='utf-8')\n",
        encoding="utf-8",
    )
    paths = dict(zip(modules, ["a", "b"], strict=True))
    for profile, module in zip(capabilities, paths.values(), strict=True):
        local = w.worker.profiles["local"]
        w.worker.profiles[profile] = dict(
            local, argv=[local["argv"][0], str(probe)], env={**local["env"], "OUTPUT_MODULE": module}
        )

    def plan(actor, issue):
        required = w.domain.issue_snapshot(actor, issue)["definition"]["required_capabilities"]
        pinned = "animation" if issue == issues[2]["id"] else None
        source = next(item["design_source"] for item in issues if item["id"] == issue)
        module = paths[source["module_id"]]
        return dict(
            h.plan,
            capabilities=["review"],
            profile=installed_profile(w.catalog, ["review"], required, pinned),
            selected={module: w.worker.store.head(w.domain.actor_context(actor)["tenant"], module)},
            writes={module: ["output"]},
        )

    w.installed_plan = plan
    tickets = []
    for issue, required in zip(issues, requirements, strict=True):
        classify(h, issue, ["capability:" + c for c in required]).raise_for_status()
        h.target(issue)
        h.confirm(issue).raise_for_status()
        key = h.api("authorize", issue=issue["id"]).raise_for_status().json()
        tickets.append(key)
    board = h.api("inspect").raise_for_status().json()
    requests = {r["ticket"]: r for r in board["requests"]}
    batch = dispatch(h)
    assert [r["receipt"]["model"] for r in batch["results"]] == capabilities
    assert [r["ticket"] for r in batch["results"]] == tickets[:2]
    assert batch["deferred"] == [
        dict(
            ticket=tickets[2],
            model="animation",
            modelAvailable=True,
            requiredCapabilities=["review", "animation", "mesh-rigging"],
            missingCapabilities=["mesh-rigging"],
            reason="required_model_or_capabilities_unavailable",
        )
    ]
    observations = {
        path.parent.name: json.loads(path.read_text(encoding="utf-8")) for path in w.worker.root.glob("*/observed.json")
    }
    with w.worker.store._connection() as db:
        closures = {
            row["execution"]: json.loads(row["payload"])
            for row in db.execute("SELECT execution,payload FROM native_worker_process_closures")
        }
    assert set(observations) == set(closures) == set(tickets[:2])
    assert all(c["exit_code"] == 0 and not c["reasons"] for c in closures.values())
    receipts = []
    for issue, key, required in zip(issues, tickets, requirements, strict=True):
        row = h.api("status", key=key).raise_for_status().json()
        task = json.loads(row["task"])
        definition = task["source"]["definition"]
        assert definition["required_capabilities"] == required
        assert task["capabilities"] == requests[key]["capabilities"] == ["review", *required]
        assert task["writes"] == {paths[issue["design_source"]["module_id"]]: ["output"]}
        assert task["actor"] == task["producer"] == h.actor
        assert task["installation"] == w.worker.installation(task["profile"])
        assert requests[key]["model"] == task["profile"]
        assignment = json.loads(row["assignment"]) if row["assignment"] else None
        if key in observations:
            assert assignment["model"]["capabilities"] == task["capabilities"]
            assert observations[key] == definition
            assert row["state"] == "produced"
        else:
            assert row["state"] == "ready" and assignment is None and row["terminal"] is None
            assert not (w.worker.root / key).exists()
        receipts.append(
            dict(
                issue=issue["id"],
                module=issue["design_source"]["module_id"],
                ticket=key,
                stage=definition["stage_authorization"],
                source_revision=task["source"]["revision"],
                issue_capabilities=required,
                required=requests[key]["capabilities"],
                profile=task["profile"],
                installation=task["installation"],
                writes=task["writes"],
                matched=assignment["model"] if assignment else None,
                physical_closure=closures.get(key),
                state=row["state"],
                candidate=json.loads(row["terminal"])["candidate"] if row["terminal"] else None,
            )
        )
    record_property(
        "observation", json.dumps(dict(tickets=receipts, gap=batch["deferred"], physical_calls=len(closures)))
    )


def test_only_authorized_capability_edits_invalidate_signoff_and_reservation(host, record_property):
    h, issue = host, host.issues[0]
    original = h.detail(issue)["revision"]
    h.target(issue)
    h.confirm(issue).raise_for_status()
    classify(h, issue, ["ordinary"]).raise_for_status()
    assert h.detail(issue)["revision"] == original
    assert h.detail(issue)["task_confirmation"]["status"] == "confirmed"
    assert h.api("authorize", issue=issue["id"], capabilities=[]).status_code == 422
    key = h.api("authorize", issue=issue["id"]).raise_for_status().json()
    assert h.reserve(key).json() is True
    w = h.workflow
    viewer = w.domain.add_member(h.actor, "viewer@example.invalid", "fixture-pass", role="viewer")["user_id"]
    denied = classify(
        h, issue, ["capability:coding"], headers={"Authorization": "Bearer " + w.domain.issue_session(viewer)}
    )
    assert denied.status_code == 403
    assert h.detail(issue)["revision"] == original
    classify(h, issue, ["ordinary", "capability:coding"]).raise_for_status()
    changed = h.detail(issue)
    assert changed["revision"] != original and changed["task_confirmation"]["status"] == "pending"
    classify(h, issue, ["ordinary"]).raise_for_status()
    reverted = h.detail(issue)
    assert reverted["revision"] == original and reverted["task_confirmation"]["status"] == "pending"
    assert h.api("execute", key=key).status_code == 409
    assert h.api("status", key=key).json()["state"] == "stopped" and h.observations() == []
    assert h.api("revise", issue=issue["id"], expected=key).status_code == 409
    classify(h, issue, ["ordinary", "capability:coding"]).raise_for_status()
    h.confirm(issue).raise_for_status()
    new = h.api("revise", issue=issue["id"], expected=key).raise_for_status().json()
    assert new != key and h.api("inspect").json()["requests"][0]["capabilities"] == ["coding"]
    assert h.reserve(new).raise_for_status().json() is False
    record_property(
        "observation",
        json.dumps(
            dict(
                original=original,
                revised=changed["revision"],
                old_ticket=key,
                new_ticket=new,
                denied_edit=denied.status_code,
                old_state="stopped",
                missing_capability_reserved=False,
                reverted_definition=reverted["revision"],
                reverted_confirmation=reverted["task_confirmation"]["status"],
                physical_calls=len(h.observations()),
            )
        ),
    )
