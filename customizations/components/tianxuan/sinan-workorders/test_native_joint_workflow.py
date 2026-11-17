"""Physical joint production through authenticated HTTP and the actual Node pump."""

import json
import os
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest
from native_candidates import NativeCandidates
from native_integration import NativeIntegration
from native_store import NativeStoreError
from test_native_workflow import fixture  # noqa: F401

# pytest fixture registration is intentionally imported.
# ruff: noqa: F811


def install(f, shape=None):
    w, actor, tenant, req, initial, _ = f
    identities = {
        role: "execution-" + role for role in ("producer", "integrator", "checker", "reviewer", "publisher", "resolver")
    }
    w.principals = lambda a, i, role: identities[role]
    w.release.authorize = lambda db, t, a, p, op: t == tenant and a in {actor, *identities.values()}
    w.release.contributors = lambda *args: {identities["producer"]}
    w.worker.intake.authorize = lambda db, t, a, m, op: (
        t == tenant and a in {actor, identities["producer"]} and op in {"read", "receive"}
    )
    w.worker.profiles["local"]["argv"][-1] = """import pathlib,os,json,time
p=pathlib.Path.cwd(); start=time.time_ns(); time.sleep(.5)
title=json.loads(pathlib.Path(os.environ['NATIVE_CONTEXT']).read_text(encoding='utf-8'))['title']
if title == 'c':
    (p/'c'/'output').write_text((p/'a'/'left').read_text()+'|'+(p/'a'/'right').read_text())
else:
    (p/'a'/title).write_text({'left':'L','right':'R'}[title])
(p.parent/'interval.json').write_text(json.dumps([start,time.time_ns()]))
"""
    w.runner._registry["check"]["argv"][-1] = """import pathlib,os,json
p=pathlib.Path(os.environ['DUOBAO_INPUT'])
manifests=list(p.glob('integration-*/integration.json'))
if manifests:
    plan=json.loads(manifests[0].read_text(encoding='utf-8')); assert len(plan['originals']) == 2
    assert {o['contract']['source']['definition']['title'] for o in plan['originals']} == {'left','right'}
    assert all(o['contract']['checks'] == ['check'] for o in plan['originals'])
    assert (p/'a'/'left').read_text() == 'L'; assert (p/'a'/'right').read_text() == 'R'
else:
    assert any((p/'a'/n).exists() for n in ['left','right'])
if (p/'c').exists(): assert (p/'c'/'output').read_text() == 'L|R'
"""
    if shape is not None:
        code = w.worker.profiles["local"]["argv"][-1]
        if shape == "identical":
            code = code.replace(
                "(p/'a'/title).write_text({'left':'L','right':'R'}[title])", "(p/'a'/'shared').write_text('same')"
            )
        elif shape == "different":
            code = code.replace("p/'a'/title", "p/'a'/'shared'")
        else:
            code = code.replace("(p/'a'/title).write_text({'left':'L','right':'R'}[title])", "pass")
        w.worker.profiles["local"]["argv"][-1] = code
        w.runner._registry["check"]["argv"][-1] = (
            "import os,pathlib; assert (pathlib.Path(os.environ['DUOBAO_INPUT'])/'a'/'output').read_text() == 'initial'"
        )
    keys = []
    for title in ["left", "right"]:
        issue = w.domain.create_issue(actor, title, requirement_id=req["id"], acceptance=title + " present")
        keys.append(
            w.authorize_task(
                actor,
                issue["id"],
                selected={"a": initial["a"]},
                writes={"a": "*"},
                dependencies={},
                profile="local",
                product="joint",
                checks=["check"],
                mandate="physical-joint",
                delivery_mode="contribution",
            )
        )
    spec = dict(
        tasks=keys,
        product="joint",
        channel="stable",
        base={"a": initial["a"]},
        expected=None,
        checks=["check"],
        request_id="native-product-integration-20261118",
        issue_url="https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1466",
    )
    integration = NativeIntegration(
        w,
        NativeCandidates(w.worker.store, lambda *args: True),
        lambda *args: spec,
        installed_groups=lambda a: ["joint"],
    )
    reviewed = []

    def review(a, plan, result):
        modules = result["modules"]
        assert w.worker.store.read(tenant, "a", modules["a"], "left") == b"L"
        assert w.worker.store.read(tenant, "a", modules["a"], "right") == b"R"
        reviewed.append(result["candidate"])
        return True

    w.review_candidate = review
    w.installed_target = lambda *args: dict(channel="stable", expected=None)
    for product in ["joint", "c"]:
        w.release.configure(
            tenant,
            identities["publisher"],
            product,
            dict(checks={"check": w.runner.context("check", "0" * 64)}, review_max_age_seconds=3600),
        )
    downstream = w.domain.create_issue(actor, "c", requirement_id=req["id"], acceptance="union consumed")
    w.next_issues = lambda a, event: (
        [downstream["id"]] if all(w.status(a, k)["state"] == "accepted" for k in keys) else []
    )

    def downstream_plan(a, issue):
        dependencies = {k: w.status(a, k)["acceptance"] for k in keys}
        selected = {**json.loads(next(iter(dependencies.values())))["modules"], "c": initial["c"]}
        return dict(
            selected=selected,
            writes={"c": "*"},
            dependencies=dependencies,
            profile="local",
            product="c",
            checks=["check"],
            mandate="outbox-joint",
        )

    w.installed_plan = downstream_plan
    return integration, keys, spec, reviewed, downstream


@pytest.mark.parametrize("resume", [False, True, "lost-response"])
def test_real_joint_http_node_and_restart(fixture, resume):
    import uvicorn
    from api import create_app
    from fastapi.testclient import TestClient

    w, actor, tenant, req, _, _ = fixture
    integration, keys, spec, reviewed, downstream = install(fixture)
    if resume is True:
        from concurrent.futures import ThreadPoolExecutor

        from test_native_workflow import reserve

        for key in keys:
            reserve(fixture, key)
        with ThreadPoolExecutor(2) as pool:
            list(pool.map(lambda key: w.execute(actor, key), keys))
        for key in keys:
            integration.check_contribution(actor, key)
        ready = integration.discover(actor)["ready"]
        assert len(ready) == 1
        integration.execute(actor, ready[0]["key"])
    launches = []
    original_run = w.worker.run

    def counted_run(task, key):
        launches.append(key)
        return original_run(task, key)

    w.worker.run = counted_run
    observations = []
    original_observe = w.await_terminal

    async def counted_observe(a, key):
        observations.append(key)
        return await original_observe(a, key)

    w.await_terminal = counted_observe
    app = create_app(w.domain, native_store=w.worker.store, native_only=True, native_workflow=w)
    lost_observer_reply = []
    if resume == "lost-response":
        from fastapi.responses import JSONResponse

        @app.middleware("http")
        async def lose_first_observer_reply(request, call_next):
            response = await call_next(request)
            if request.url.path.endswith("/await-terminal") and not lost_observer_reply:
                lost_observer_reply.append(True)
                return JSONResponse({"detail": "injected lost terminal reply"}, status_code=503)
            return response

    token = w.domain.issue_session(actor)
    with TestClient(app) as client:
        assert client.post("/api/v1/native/workflow/inspect", json={}).status_code == 401
        assert (
            client.post(
                "/api/v1/native/workflow/integration-authorize",
                json={"group": "joint", "plan": spec},
                headers={"Authorization": "Bearer " + token},
            ).status_code
            == 422
        )
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
        env = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR"}}
        env.update(NATIVE_SERVICE_URL=f"http://127.0.0.1:{listener.getsockname()[1]}", NATIVE_SERVICE_TOKEN=token)

        def drive():
            adapter = Path(__file__).with_name("native_dispatch.mjs")
            command = [shutil.which("node"), str(adapter)]
            if resume == "lost-response":
                command = [
                    shutil.which("node"),
                    "--input-type=module",
                    "-e",
                    "import {driveNative,httpService} from " + json.dumps(adapter.as_uri()) + ";"
                    "const result=await driveNative(httpService(process.env.NATIVE_SERVICE_URL,"
                    "process.env.NATIVE_SERVICE_TOKEN,{executeTimeoutMs:200}));"
                    "console.log(JSON.stringify(result));",
                ]
            run = subprocess.run(
                command,
                env=env,
                capture_output=True,
                text=True,
                timeout=40,
            )
            assert run.returncode == 0, run.stderr
            return json.loads(run.stdout)

        result = drive()
        assert not result["errors"], result
        assert len(result["results"]) == (1 if resume is True else 3), result
        assert len(result["deliveries"]) == 2
        assert len(reviewed) == 2
        assert len(launches) == len(set(launches)) == (1 if resume is True else 3)
        if resume == "lost-response":
            assert set(keys) <= set(observations)
            assert lost_observer_reply == [True]
            assert len(observations) > len(set(observations))
        assert all(w.status(actor, k)["state"] == "accepted" for k in keys)
        intervals = [json.loads((w.worker.root / k / "interval.json").read_text()) for k in keys]
        assert max(x[0] for x in intervals) < min(x[1] for x in intervals)
        assert w.domain.get_issue(downstream["id"])["status"] == "done"
        assert w.domain.sync_progress(req["id"], actor=actor)["percent"] == 100
        with w.worker.store._connection() as db:
            assert db.execute("SELECT count(*) FROM native_release_events WHERE product='joint'").fetchone()[0] == 1
        replay = drive()
        assert replay["results"] == [] and replay["deliveries"] == [] and replay["errors"] == [], replay
        assert len(reviewed) == 2
    finally:
        server.should_exit = True
        thread.join(10)
        listener.close()


def test_fixed_group_discovery_detects_drift_and_no_early_acceptance(fixture):
    integration, keys, spec, _, _ = install(fixture)
    actor = fixture[1]
    assert integration.discover(actor) == {"ready": [], "errors": []}
    spec["expected"] = "0" * 64
    report = integration.discover(actor)
    assert report["ready"] == [] and "new fixed group" in report["errors"][0]["reason"]
    assert all(fixture[0].status(actor, k)["acceptance"] is None for k in keys)
    with pytest.raises(NativeStoreError, match="new fixed group"):
        integration.authorize(actor, "joint")


@pytest.mark.parametrize("mode", ["identical", "different", "no-op"])
def test_real_original_merge_shapes(fixture, mode):
    from concurrent.futures import ThreadPoolExecutor

    from test_native_workflow import reserve

    integration, keys, _, _, _ = install(fixture, mode)
    w, actor, *_ = fixture
    for key in keys:
        reserve(fixture, key)
    with ThreadPoolExecutor(2) as pool:
        terminals = list(pool.map(lambda key: w.execute(actor, key), keys))
    assert all(t["state"] == "produced" for t in terminals)
    for key in keys:
        integration.check_contribution(actor, key)
    plan = integration.discover(actor)["ready"][0]["key"]
    merged = integration.execute(actor, plan)
    if mode == "different":
        assert merged["state"] == "conflicts_pending"
        with pytest.raises(NativeStoreError, match="resolver unavailable"):
            integration.resolve(actor, plan)
    else:
        assert merged["state"] != "conflicts_pending"
        if mode == "identical":
            assert w.worker.store.read(fixture[2], "a", merged["modules"]["a"], "shared") == b"same"
        else:
            assert all(t["no_changes"] is True for t in terminals)
    assert all(w.status(actor, key)["acceptance"] is None for key in keys)
