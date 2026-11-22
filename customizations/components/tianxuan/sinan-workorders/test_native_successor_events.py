"""Replay an observed physical completion against real signed I04 successors."""

import json
from pathlib import Path

import pytest
import test_native_stage_admission
from issue_lifecycle_test_support import accept_current_issue
from native_execution_host import WorkflowService
from test_native_stage_stop import drive
from test_native_workflow import accept, reserve, task
from test_native_workflow_revisions import replace

fixture = test_native_stage_admission.fixture
host = test_native_stage_admission.host


@pytest.mark.parametrize("accepted", [False, True])
def test_signed_successor_replays_exact_completion(host, fixture, accepted, record_property):
    h, w = host, host.workflow
    _, actor, _, requirement, initial, _ = fixture
    upstream = w.domain.create_issue(actor, "b", requirement_id=requirement["id"])
    profile = w.worker.profiles["local"]
    w.worker.profiles["prerequisite"] = {
        **profile,
        "argv": [profile["argv"][0], "-c", "from pathlib import Path; Path('b/output').write_text('b produced')"],
    }
    w.catalog.append({**w.catalog[0], "id": "prerequisite"})
    key = w.authorize_task(
        actor,
        upstream["id"],
        selected={"b": initial["b"]},
        writes={"b": "*"},
        dependencies={},
        profile="prerequisite",
        product="b",
        checks=["check"],
        mandate="upstream-test",
    )
    source = json.loads(w.status(actor, key)["task"])["source"]["revision"]
    assert (
        h
        .api(
            "reserve",
            event="upstream",
            assignment=dict(
                ticket=key,
                sourceSnapshot=dict(source=key, revision=source),
                model=dict(id="prerequisite"),
            ),
        )
        .raise_for_status()
        .json()
    )
    terminal = h.api("execute", key=key).raise_for_status().json()
    assert terminal["state"] == "produced" and terminal["id"] == key
    event = dict(type="execution.finished", reference=terminal["id"])

    successor, sibling = h.issues
    probe = Path(profile["argv"][1])
    probe.write_text(probe.read_text(encoding="utf-8").replace("fixture output", "a produced"), encoding="utf-8")
    criterion = "a/output contains a produced and b/output contains b produced"
    h.plan["stage_criteria"] = criterion
    for issue in (successor, sibling):
        path = f"/api/v1/issues/{issue['id']}/work/flow"
        version = h.client.get(path).raise_for_status().json()["version"]
        flow = (
            h.client
            .post(
                path + "/dependencies",
                json=dict(
                    dependencies=[upstream["id"]],
                    call_id=issue["id"],
                    expected_version=version,
                ),
            )
            .raise_for_status()
            .json()
        )
        assert flow["dependencies"] == [dict(id=upstream["id"], title="b", status="in-review", accepted=False)]
        h.target(issue, criteria=criterion)
    h.confirm(successor).raise_for_status()
    assert h.api("authorize", issue=successor["id"]).status_code == 409

    release = accept(fixture, key) if accepted else None
    if accepted:
        invite = w.domain.create_invite(actor, "observer@example.invalid", "editor")
        other = w.domain.accept_invite(invite["code"], "password")["user_id"]
        release_authority = w.release.authorize
        w.release.authorize = lambda db, tenant, operator, product, action: (
            (operator == other and action == "read") or release_authority(db, tenant, operator, product, action)
        )
        w.authorize = lambda operator, issue, action: operator != other or issue != successor["id"]
        assert w.advance(other, completion=key) == []
        assert not w.domain.db.execute("SELECT 1 FROM native_outbox_consumed WHERE id=?", (key,)).fetchone()
    # Neither a different completion nor a concurrent entry's recovery may drain this outbox.
    assert h.api("advance", completion="0" * 64).raise_for_status().json() == {"authorized": [], "errors": []}
    foreign = WorkflowService(w, actor, lambda: None, [sibling["id"]])
    assert foreign.call("advance", {}) == {"authorized": [], "errors": []}

    cumulative_starts, results = [], []
    for _ in range(3):  # Original plus two deliveries of the same event from a fresh Node receiver.
        run = drive(h, event)
        assert run["advances"][0]["completion"] == key
        results.append(run["result"])
        cumulative_starts.append(len(h.observations()))
    assert cumulative_starts == ([1, 1, 1] if accepted else [0, 0, 0]), results
    assert not h.detail(sibling)["execution_progress"]
    observed = h.detail(successor)["execution_progress"]
    if accepted:
        assert observed["state"] == "stage-reached"
        downstream = h.api("status", key=observed["id"]).raise_for_status().json()
        contract = json.loads(downstream["task"])
        assert json.loads(contract["dependencies"][key]) == release
        assert contract["selected"]["b"] == release["modules"]["b"]
        assert all(not result["errors"] and not result["deliveries"] for result in results)
        assert [len(result["results"]) for result in results] == [1, 0, 0]
        assert h.observations()[0]["execution"] == observed["id"]
    else:
        assert observed is None and w.status(actor, key)["acceptance"] is None
        assert all(not result["results"] and not result["deliveries"] for result in results)
        assert all(
            all(error["key"] == key and error["stage"] == "finish" for error in result["errors"]) for result in results
        )
    with w.worker.store._connection() as db:
        closed = {
            r["execution"]: json.loads(r["payload"])["exit_code"]
            for r in db.execute("SELECT execution,payload FROM native_worker_process_closures")
        }
    assert closed == ({key: 0, observed["id"]: 0} if accepted else {key: 0})
    consumed = w.domain.db.execute("SELECT count(*) FROM native_outbox_consumed WHERE id=?", (key,)).fetchone()[0]
    assert consumed == int(accepted)
    record_property(
        "observation",
        json.dumps(
            dict(
                event=event,
                upstream_candidate=json.loads(w.status(actor, key)["terminal"])["candidate"],
                release=release["id"] if release else None,
                cumulative_starts=cumulative_starts,
                consumed=consumed,
                physical_exits=closed,
                successor=observed,
                unsigned_sibling_starts=0,
                stage_result=downstream["stage_result"] if accepted else None,
            )
        ),
    )


def test_other_prerequisite_and_old_source(fixture):
    w, actor, _, req, initial, _ = fixture
    first, _ = task(fixture, "a")
    second, _ = task(fixture, "b")
    downstream = w.domain.create_issue(actor, "c", requirement_id=req["id"])
    for key in (first, second):
        reserve(fixture, key)
        assert w.execute(actor, key)["state"] == "produced"
    accepted = accept(fixture, first)

    def plan(operator, issue):
        assert issue == downstream["id"]
        receipts = {key: w.status(operator, key)["acceptance"] for key in (first, second)}
        return dict(
            selected={**accepted["modules"], "c": initial["c"]},
            writes={"c": "*"},
            dependencies=receipts,
            profile="local",
            product="c",
            checks=["check"],
            mandate="both inputs",
        )

    w.next_issues = lambda operator, event: [downstream["id"]]
    w.installed_plan = plan
    for _ in range(2):
        assert w.advance(actor, isolate=True, completion=first)["errors"] == [
            {"event": first, "reason": "NativeStoreError"}
        ]
        assert not w.inspect(actor)["requests"]
    new = replace(w, actor, first, mandate="revised source")
    assert w.advance(actor, isolate=True, completion=first) == {"authorized": [], "errors": []}
    assert [r["ticket"] for r in w.inspect(actor)["requests"]] == [new]
    assert not (w.worker.root / new).exists()


def test_custom_flow_retains_ownership(host):
    h, w = host, host.workflow
    prerequisite = w.domain.create_issue(h.actor, "upstream")
    successor = h.issues[0]
    path = f"/api/v1/issues/{successor['id']}/work/flow"
    original = h.client.get(path).raise_for_status().json()
    h.client.post(
        path + "/configure",
        json=dict(
            stages=original["stages"],
            edges=[{"from": "backlog", "to": "planned"}],
            expected_version=0,
            call_id="custom",
        ),
    ).raise_for_status()
    h.client.post(
        path + "/dependencies",
        json=dict(
            dependencies=[prerequisite["id"]],
            expected_version=1,
            call_id="dep",
        ),
    ).raise_for_status()
    for state in ("planned", "in-progress", "in-review", "done"):
        if state == "done":
            accept_current_issue(w.domain, h.actor, prerequisite["id"])
        w.domain.transition_issue(h.actor, prerequisite["id"], state)
    h.target(successor)
    h.confirm(successor).raise_for_status()
    reply = h.api("authorize", issue=successor["id"])
    assert reply.status_code == 409 and "Ordinary workflow owns" in reply.json()["detail"]
    assert h.client.get(path).json()["configured"] and not h.observations()
