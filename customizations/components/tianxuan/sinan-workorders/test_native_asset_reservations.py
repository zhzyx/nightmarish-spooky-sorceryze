"""Exercise asset waiting and physical slot refill through the signed HTTP workflow."""

import asyncio
import json
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import test_native_stage_stop
from native_execution_host import SharedSinanProcess, WorkflowService
from native_workflow import NativeWorkflow
from test_native_stage_stop import PREVIEW, drive, install_preview, signed
from tianxuan_core import Tianxuan

fixture = test_native_stage_stop.fixture
host = test_native_stage_stop.host


def authorize(f, writes):
    workflow, actor, _, requirement, initial, _ = f
    issue = workflow.domain.create_issue(actor, "edit", requirement_id=requirement["id"], acceptance="checked")
    return workflow.authorize_task(
        actor,
        issue["id"],
        selected={module: initial[module] for module in writes},
        writes=writes,
        dependencies={},
        profile="local",
        product="fixture",
        checks=["check"],
        mandate="asset-test",
    )


def assignment(workflow, actor, key):
    revision = json.loads(workflow.status(actor, key)["task"])["source"]["revision"]
    return dict(ticket=key, sourceSnapshot=dict(source=key, revision=revision), model={"id": "local"})


@pytest.mark.parametrize(
    ("first", "waiting"),
    [("*", ["art/file"]), (["art/file"], "*"), (["Art/File"], ["art/file"]), (["art"], ["art/file"])],
)
def test_reserved_scope_survives_restart_and_stale_assignment(fixture, first, waiting):
    workflow, actor, *_, folder = fixture
    owner = authorize(fixture, {"a": first})
    blocked = authorize(fixture, {"a": waiting})
    free = authorize(fixture, {"b": ["art/file"]})
    assert workflow.reserve(actor, assignment(workflow, actor, owner))

    # Independent connection and coordinator, using the admitted contract even
    # when an outdated caller supplies a disjoint work directory.
    domain = Tianxuan(str(folder / "domain.sqlite"))
    try:
        other = NativeWorkflow(
            domain, workflow.worker, workflow.runner, workflow.release, workflow.authorize, catalog=workflow.catalog
        )
        assert not other.reserve(actor, {**assignment(other, actor, blocked), "writes": ["/other"]})
        assert other.reserve(actor, assignment(other, actor, free))
        assert json.loads(other.status(actor, free)["assignment"])["writes"] == [
            "/native-assets/" + domain.actor_context(actor)["tenant"] + "/b/art/file"
        ]
    finally:
        domain.db.close()


def test_hidden_holder_keeps_asset_without_disclosing_ticket(fixture):
    w, actor, *_ = fixture
    owner = authorize(fixture, {"a": "*"})
    assert w.reserve(actor, assignment(w, actor, owner))
    # Existing workflow scope remains enforced when the actor loses read access
    # to this issue. A separately visible peer must still see its own wait.
    waiting = authorize(fixture, {"a": ["output"]})
    holder_issue = w.status(actor, owner)["issue"]
    w.authorize = lambda user, issue, action: issue != holder_issue
    board = w.inspect(actor)
    assert board["snapshot"]["items"] == [
        {"key": waiting, "source": waiting, "dispatchCandidate": False, "waitReason": "resource_conflict"}
    ]
    assert board["environment"]["active"] == [{"ticket": "occupied-slot-0", "reads": [], "writes": []}]
    assert owner not in json.dumps(board)
    assert not w.reserve(actor, assignment(w, actor, waiting))


def test_signed_waiter_refills_released_asset_while_peer_runs(host, record_property):
    h = host
    w = h.workflow
    w.capacity = 3
    install_preview(h)
    h.doc = w.domain.create_doc(h.actor, "Asset changes", "First\n\nWaiter\n\nPeer")["id"]
    w.domain.design_signoff(h.actor, h.doc, 1, "Wait on the shared preview")
    names = ("first", "waiter", "peer")
    issues = w.domain.split_design(
        h.actor,
        h.doc,
        1,
        "studio",
        [dict(paragraph=i, title=name, module_id="default", acceptance="preview") for i, name in enumerate(names, 1)],
        "asset-work",
    )
    profile = w.worker.profiles["local"]
    probe = Path(profile["argv"][1])
    folder = probe.parent
    profile["timeout"] = 20
    profile["env"]["GATES"] = str(folder)
    probe.write_text(
        "import json, os, pathlib, time\n"
        "context = pathlib.Path(os.environ['NATIVE_CONTEXT'])\n"
        "name = json.loads(context.read_text(encoding='utf-8'))['title']\n"
        "gates = pathlib.Path(os.environ['GATES'])\n"
        "start = dict(pid=os.getpid(), execution=context.parent.name, started_ns=time.perf_counter_ns())\n"
        # Exclusive creation leaves a duplicate launch as a failing physical receipt.
        "with (gates / (name + '.start')).open('x') as f: json.dump(start, f)\n"
        "while not (gates / (name + '.release')).exists(): time.sleep(0.01)\n"
        "asset = 'peer.svg' if name == 'peer' else 'preview.svg'\n"
        f"(pathlib.Path('a') / asset).write_bytes({PREVIEW.encode()!r})\n"
        "(gates / (name + '.end')).write_text(str(time.perf_counter_ns()))\n",
        encoding="utf-8",
    )
    check = w.runner._registry["check"]["argv"]
    check[-1] = check[-1].replace(
        "pathlib.Path(os.environ['DUOBAO_INPUT'])/'a/preview.svg'",
        "next((pathlib.Path(os.environ['DUOBAO_INPUT'])/'a').glob('*.svg'))",
    )
    keys = {}
    for issue, name in zip(issues, names, strict=True):
        h.plan["writes"] = {"a": ["peer.svg" if name == "peer" else "preview.svg"]}
        keys[name] = signed(h, issue)

    with ThreadPoolExecutor(1) as pool:
        dispatch = pool.submit(drive, h)

        def wait_start(name):
            deadline = time.monotonic() + 14
            while not (folder / (name + ".start")).exists():
                if dispatch.done():
                    pytest.fail(str(dispatch.result()))
                assert time.monotonic() < deadline, f"{name} did not start"
                time.sleep(0.02)

        try:
            wait_start("first")
            wait_start("peer")
            assert not (folder / "waiter.start").exists()
            board = h.api("inspect").raise_for_status().json()
            (item,) = board["snapshot"]["items"]
            assert item == dict(
                key=keys["waiter"], source=keys["waiter"], dispatchCandidate=False, waitReason="resource_conflict"
            )
            active = board["environment"]["active"]
            assert {row["ticket"] for row in active} == {keys["first"], keys["peer"]}
            entry = WorkflowService(w, h.actor, lambda: None, [issues[1]["id"]])
            holders = entry.call("inspect", {})["environment"]["active"]
            assert [r["ticket"] for r in holders if r.get("terminalObservable")] == [keys["first"]]
            assert h.reserve(keys["waiter"]).raise_for_status().json() is False
            (folder / "first.release").touch()
            wait_start("waiter")
            after = h.api("inspect").raise_for_status().json()
            assert {r["ticket"] for r in after["environment"]["active"]} == {keys["waiter"], keys["peer"]}
            assert not (folder / "peer.end").exists()
        finally:
            for name in names:
                (folder / (name + ".release")).touch()
        result = dispatch.result()["result"]
    assert result["errors"] == result["deferred"] == []
    assert {row["ticket"] for row in result["results"]} == set(keys.values())
    assert h.api("inspect").json()["environment"]["active"] == []

    receipts = {}
    for issue, name in zip(issues, names, strict=True):
        current = h.api("status", key=keys[name]).raise_for_status().json()
        assert current["state"] == "stage-reached"
        terminal = json.loads(current["terminal"])
        assert terminal["exit_code"] == 0
        start = json.loads((folder / (name + ".start")).read_text())
        assert start["execution"] == keys[name]
        receipts[name] = dict(
            **start,
            ended_ns=int((folder / (name + ".end")).read_text()),
            issue=issue["id"],
            candidate=terminal["candidate"],
            state=current["state"],
            exit_code=terminal["exit_code"],
        )
    first, waiter, peer = (receipts[n] for n in names)
    assert len({r["pid"] for r in receipts.values()}) == 3
    assert max(first["started_ns"], peer["started_ns"]) < first["ended_ns"] <= waiter["started_ns"] < peer["ended_ns"]
    record_property(
        "observation",
        json.dumps(
            dict(
                workers=receipts,
                waiting=item,
                active=active,
                after_release=after["environment"]["active"],
                final_active=[],
                dispatcher_errors=result["errors"],
                deferred_at_exit=result["deferred"],
            )
        ),
    )


def test_scoped_entry_observes_external_holder_with_spare_capacity(host, record_property):
    h = host
    w = h.workflow
    install_preview(h)
    profile = w.worker.profiles["local"]
    probe = Path(profile["argv"][1])
    release = probe.parent / "release-preview"
    profile["timeout"] = 20
    profile["env"]["RELEASE_PREVIEW"] = str(release)
    with probe.open("a", encoding="utf-8") as script:
        script.write("import time\nwhile not pathlib.Path(os.environ['RELEASE_PREVIEW']).exists(): time.sleep(0.01)\n")
    first, waiter = (signed(h, issue) for issue in h.issues)
    assert h.reserve(first).raise_for_status().json()
    token = w.domain.issue_session(h.actor)

    def authorize_entry():
        assert w.domain.user_for_token(token) == h.actor

    service = WorkflowService(w, h.actor, authorize_entry, [h.issues[1]["id"]])

    async def refill():
        subscribed = asyncio.Event()
        node = shutil.which("node")
        assert node
        driver = SharedSinanProcess(
            [node, str(Path(__file__).with_name("native_entry_driver.mjs"))],
            {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR"}},
        )

        async def observe(operation, value):
            if operation == "await-terminal" and value["key"] == first:
                subscribed.set()
            return await service(operation, value)

        job = asyncio.create_task(driver.run(observe))
        try:
            await asyncio.wait_for(subscribed.wait(), 5)
            board = h.api("inspect").raise_for_status().json()
            assert len(board["environment"]["active"]) == 1 < board["environment"]["capacity"]
            assert board["snapshot"]["items"][0]["waitReason"] == "resource_conflict"
            assert [r["execution"] for r in h.observations()] == [first]
            release.touch()
            result = await asyncio.wait_for(job, 12)
        finally:
            release.touch(exist_ok=True)
            closed = await driver.close()
        assert closed["physical_terminal"] and closed["exit_code"] == 0
        assert result["deferred"] == result["errors"] == result["host_errors"] == []
        assert [r["ticket"] for r in result["results"]] == [waiter]
        return dict(
            holder=first,
            waiter=waiter,
            observed=board["snapshot"]["items"],
            result=result["stages"][0]["state"],
            dispatcher_exit=closed["exit_code"],
        )

    with ThreadPoolExecutor(1) as pool:
        execution = pool.submit(h.api, "execute", key=first)
        try:
            deadline = time.monotonic() + 8
            while not h.calls.exists() or not h.calls.read_bytes().endswith(b"\n"):
                assert time.monotonic() < deadline
                time.sleep(0.02)
            receipt = asyncio.run(refill())
        finally:
            release.touch(exist_ok=True)
        assert execution.result().raise_for_status().json()["state"] == "produced"
    assert receipt["result"] == "stage-reached"
    assert [r["execution"] for r in h.observations()] == [first, waiter]
    record_property("observation", json.dumps(receipt))
