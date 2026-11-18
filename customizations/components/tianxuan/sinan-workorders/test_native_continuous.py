"""Continuous admission regression probes with actual native checks and SQLite."""

import pytest
from native_continuous import ContinuousIntegration, publisher_lock
from native_store import NativeStoreError
from test_native_integration import setup
from test_native_workflow import fixture  # noqa: F401

# ruff: noqa: F811


def continuous(f, edits=None, extra_base=None):
    w, actor, tenant, _, initial, _ = f
    policy = dict(
        tenant=tenant,
        coordinator=actor,
        product="joint",
        channel="stable",
        base={"a": initial["a"], **(extra_base or {})},
        checks=["check"],
        max_batch=1,
        history_refs=["first", "predecessor"],
        request_id="native-continuous-integration-20261118",
        issue_url="https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1488",
    )
    from native_candidates import NativeCandidates
    from native_integration import NativeIntegration

    NativeIntegration(
        w,
        NativeCandidates(w.worker.store, lambda *args: True),
        lambda *args: None,
        installed_continuous=lambda a: [policy],
    )
    i, _, keys, _ = setup(f, edits)
    i.continuous = ContinuousIntegration(i, lambda a: [policy])
    w.runner.history_provider = i.continuous
    for key in keys:
        i.continuous.enqueue(actor, key)
    return i, keys, policy, i.continuous.ready(actor)[0]["key"]


def test_continuous_distinct_modifications(fixture):
    w, actor, tenant, *_ = fixture
    i, keys, policy, lane = continuous(fixture)
    originals = [w.status(actor, k)["terminal"] for k in keys]
    assert i.continue_lane(actor, lane)["state"] == "accepted"
    assert w.status(actor, keys[1])["state"] == "produced"
    final = i.continue_lane(actor, lane)
    assert final["state"] == "accepted"
    selected = final["release"]
    rev = selected["modules"]["a"]
    assert w.worker.store.read(tenant, "a", rev, "left") == b"L"
    assert w.worker.store.read(tenant, "a", rev, "right") == b"R"
    assert len(selected["modules"]) == 2
    assert [w.status(actor, k)["terminal"] for k in keys] == originals
    assert i.continuous.ready(actor) == []


def test_conflict_isolated_and_later_task_continues(fixture):
    w, actor, *_ = fixture
    i, keys, policy, lane = continuous(fixture, [{"same": b"A"}, {"same": b"B"}])
    assert i.continue_lane(actor, lane)["state"] == "accepted"
    assert i.continue_lane(actor, lane)["state"] == "conflicts_pending"
    assert w.status(actor, keys[1])["state"] == "produced"
    other, _, fresh, _ = setup(fixture, [{"other": b"C"}], modules=("a",))
    i.continuous.enqueue(actor, fresh[0])
    assert i.continue_lane(actor, lane)["state"] == "accepted"


def test_external_cas_auto_successor(fixture):
    w, actor, tenant, *_ = fixture
    i, keys, policy, lane = continuous(fixture)
    # Freeze first, then a noncooperating legacy writer advances the channel.
    i.continuous.freeze(actor, lane, policy, [keys[0]])
    other, plan, _, _ = setup(fixture, [{"external": b"X"}], modules=("a",))
    other.finish(actor, plan)
    assert i.continue_lane(actor, lane)["state"] == "successor_ready"
    assert i.continue_lane(actor, lane)["state"] == "accepted"
    final = i.continue_lane(actor, lane)["release"]
    assert w.worker.store.read(tenant, "a", final["modules"]["a"], "external") == b"X"
    assert w.worker.store.read(tenant, "a", final["modules"]["a"], "left") == b"L"
    assert w.worker.store.read(tenant, "a", final["modules"]["a"], "right") == b"R"


def test_unknown_review_stays_held_without_replay(fixture):
    w, actor, *_ = fixture
    i, keys, policy, lane = continuous(fixture)
    calls = []

    def review(*args):
        calls.append(1)
        raise RuntimeError("lost review reply")

    w.review_candidate = review
    assert i.continue_lane(actor, lane)["state"] == "held"
    assert i.continuous.ready(actor) == []
    assert i.continue_lane(actor, lane)["state"] == "held"
    assert len(calls) == 1


def test_revoked_waiting_member_does_not_block_next(fixture):
    w, actor, *_ = fixture
    i, keys, policy, lane = continuous(fixture)
    issue = w.status(actor, keys[0])["issue"]
    with w._transaction() as db:
        db.execute("UPDATE issues SET acceptance='changed' WHERE id=?", (issue,))
    assert i.continue_lane(actor, lane)["state"] == "idle"
    assert i.continue_lane(actor, lane)["state"] == "accepted"


def test_nonblocking_lock_and_enqueue(fixture):
    w, actor, *_ = fixture
    i, keys, policy, lane = continuous(fixture)
    path = i.store.database.parent / "native-publish-locks" / (lane + ".lock")
    with publisher_lock(path) as acquired:
        assert acquired
        assert i.continue_lane(actor, lane)["state"] == "publisher_busy"
        assert i.continuous.enqueue(actor, keys[0]) == lane
    assert i.continue_lane(actor, lane)["state"] == "accepted"


def test_installation_drift_blocks(fixture):
    w, actor, *_ = fixture
    i, keys, policy, lane = continuous(fixture)
    policy["max_batch"] = 2
    with pytest.raises(NativeStoreError, match="installation changed"):
        i.continue_lane(actor, lane)


def test_restart_after_publish_before_domain_acceptance(fixture):
    w, actor, *_ = fixture
    i, keys, policy, lane = continuous(fixture)
    original = w.domain._event

    def fail(*args, **kwargs):
        if args[1] == "native.accepted":
            raise RuntimeError("domain interrupted")
        return original(*args, **kwargs)

    w.domain._event = fail
    assert i.continue_lane(actor, lane)["state"] == "held"
    w.domain._event = original
    i.continuous = ContinuousIntegration(i, lambda a: [policy])
    assert i.continue_lane(actor, lane)["state"] == "accepted"
    assert w.status(actor, keys[0])["state"] == "accepted"


def test_history_required_refs_are_bounded_and_tamper_rejected(fixture):
    w, actor, tenant, *_ = fixture
    i, keys, policy, lane = continuous(fixture)
    first = i.continue_lane(actor, lane)["release"]
    batch = i.continuous.freeze(actor, lane, policy, [keys[1]])
    row = w.domain.db.execute("SELECT plan FROM native_continuous_batches WHERE id=?", (batch,)).fetchone()
    merged = i.execute(actor, row[0])
    data = i.continuous.prepare(tenant, actor, merged["candidate"], "check")
    assert list(data["binding"]) == [first["id"]]
    from pathlib import Path

    path = Path(data["env"]["DUOBAO_HISTORY"]) / (first["id"] + ".json")
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(NativeStoreError, match="criteria input changed"):
        i.continuous.prepare(tenant, actor, merged["candidate"], "check")


def test_history_wrong_checker_rejected(fixture):
    w, actor, tenant, *_ = fixture
    i, keys, policy, lane = continuous(fixture)
    i.continue_lane(actor, lane)
    batch = i.continuous.freeze(actor, lane, policy, [keys[1]])
    row = w.domain.db.execute("SELECT plan FROM native_continuous_batches WHERE id=?", (batch,)).fetchone()
    merged = i.execute(actor, row[0])
    with pytest.raises(NativeStoreError, match="authority mismatch"):
        i.continuous.prepare(tenant, "wrong-checker", merged["candidate"], "check")


@pytest.mark.parametrize("lose_response", [False, True])
def test_real_node_event_entry_continues_multiple_batches(fixture, lose_response):
    import json
    import os
    import shutil
    import socket
    import subprocess
    import threading
    import time
    from pathlib import Path

    import uvicorn
    from api import create_app

    w, actor, *_ = fixture
    i, keys, policy, lane = continuous(fixture)
    if lose_response:
        w.review_candidate = lambda *args: time.sleep(0.8) or True
    app = create_app(w.domain, native_store=w.worker.store, native_only=True, native_workflow=w)
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
        env.update(
            NATIVE_SERVICE_URL=f"http://127.0.0.1:{listener.getsockname()[1]}",
            NATIVE_SERVICE_TOKEN=w.domain.issue_session(actor),
        )
        adapter = Path(__file__).with_name("native_dispatch.mjs")
        command = [shutil.which("node"), str(adapter)]
        if lose_response:
            script = (
                "import {driveNative,httpService} from "
                + json.dumps(adapter.as_uri())
                + ";const raw=httpService(process.env.NATIVE_SERVICE_URL,process.env.NATIVE_SERVICE_TOKEN);let lost=false;const wrapped=async(op,value)=>{const pending=raw(op,value);if(op==='integration-continue'&&!lost){lost=true;pending.catch(()=>{});await new Promise(r=>setTimeout(r,200));throw Error('injected response loss while server continues');}return pending;};console.log(JSON.stringify(await driveNative(wrapped)));"
            )
            command = [shutil.which("node"), "--input-type=module", "-e", script]
        run = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            timeout=45,
        )
        assert run.returncode == 0, run.stderr
        result = json.loads(run.stdout)
        assert not result["errors"], result
        assert all(w.status(actor, k)["state"] == "accepted" for k in keys)
    finally:
        server.should_exit = True
        thread.join(10)
        listener.close()


@pytest.mark.parametrize("pollution", ["write", "delete", "extra"])
def test_check_history_view_pollution_cannot_mutate_archive(fixture, pollution):
    from native_candidates import NativeCandidates
    from native_integration import NativeIntegration

    w, actor, tenant, _, initial, _ = fixture
    policy = dict(
        tenant=tenant,
        coordinator=actor,
        product="joint",
        channel="stable",
        base={"a": initial["a"]},
        checks=["check"],
        max_batch=1,
        history_refs=["first", "predecessor"],
        request_id="native-continuous-integration-20261118",
        issue_url="https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1488",
    )
    installed = NativeIntegration(
        w,
        NativeCandidates(w.worker.store, lambda *args: True),
        lambda *args: None,
        installed_continuous=lambda a: [policy],
    )
    w.runner._registry["check"]["argv"][-1] += (
        "\nfrom pathlib import Path\nh=Path(os.environ['DUOBAO_HISTORY']) if 'DUOBAO_HISTORY' in os.environ else None\nif h:\n for f in h.glob('*.json'): f.write_text('{}')"
    )
    if pollution == "delete":
        w.runner._registry["check"]["argv"][-1] = w.runner._registry["check"]["argv"][-1].replace(
            "f.write_text('{}')", "f.unlink()"
        )
    elif pollution == "extra":
        w.runner._registry["check"]["argv"][-1] = w.runner._registry["check"]["argv"][-1].replace(
            "f.write_text('{}')", "(h / 'extra.json').write_text('{}')"
        )
    i, _, keys, _ = setup(fixture)
    i.continuous = installed.continuous
    for key in keys:
        i.continuous.enqueue(actor, key)
    lane = i.continuous.ready(actor)[0]["key"]
    first = i.continue_lane(actor, lane)["release"]
    assert i.continue_lane(actor, lane)["state"] == "held"
    archive = next((w.worker.store.database.parent / "native-criteria-history").glob("*/*.json"))
    assert archive.read_text(encoding="utf-8") != "{}"
    assert first["id"] in archive.name
    active = w.domain.db.execute("SELECT active FROM native_continuous_lanes WHERE id=?", (lane,)).fetchone()[0]
    batch = w.domain.db.execute("SELECT plan FROM native_continuous_batches WHERE id=?", (active,)).fetchone()[0]
    assert (
        "Joint product checks failed"
        in w.domain.db.execute("SELECT error FROM native_continuous_batches WHERE id=?", (active,)).fetchone()[0]
    )
    with w.worker.store._connection() as db:
        run = db.execute(
            "SELECT payload FROM native_check_runs WHERE run_key=?", ("integration-" + batch + "-check",)
        ).fetchone()[0]
    assert '"state":"complete"' in run
    assert '"outcome":"failed"' in run
    assert "history_pollution" in run


def test_other_product_publishes_while_first_product_lock_is_held(fixture):
    from test_native_workflow import reserve

    w, actor, tenant, req, initial, _ = fixture
    i, keys, policy, lane = continuous(fixture)
    other = dict(policy, product="other", base={"b": initial["b"]})
    i.continuous.installed = lambda a: [policy, other]
    issue = w.domain.create_issue(actor, "b", requirement_id=req["id"], acceptance="b produced")
    key = w.authorize_task(
        actor,
        issue["id"],
        selected={"b": initial["b"]},
        writes={"b": "*"},
        dependencies={},
        profile="local",
        product="other",
        checks=["check"],
        mandate="other-product",
        delivery_mode="contribution",
    )
    reserve(fixture, key)
    w.execute(actor, key)
    i.check_contribution(actor, key)
    w.release.configure(
        tenant,
        "publisher",
        "other",
        dict(checks={"check": w.runner.context("check", "0" * 64)}, review_max_age_seconds=3600),
    )
    other_lane = next(x["key"] for x in i.continuous.ready(actor) if x["key"] != lane)
    with publisher_lock(i.store.database.parent / "native-publish-locks" / (lane + ".lock")) as acquired:
        assert acquired
        assert i.continue_lane(actor, other_lane)["state"] == "accepted"
        assert w.status(actor, keys[0])["state"] == "produced"


def test_two_real_members_share_installed_coordinator(fixture):
    from test_native_workflow import reserve

    w, actor, tenant, req, initial, path = fixture
    i, keys, policy, lane = continuous(fixture)
    member = w.domain.add_member(actor, "member@example.invalid", "password")["user_id"]
    w.worker.intake.authorize = lambda *args: True
    w.principals = lambda a, issue, role: (
        a
        if role == "producer"
        else {"integrator": actor, "checker": actor, "reviewer": "reviewer", "publisher": "publisher"}[role]
    )
    w.worker.profiles["local"]["argv"][-1] = (
        "import pathlib; p=pathlib.Path.cwd(); (p/'a'/'member').write_text('member'); (p/'a'/'output').write_text('a produced')"
    )
    issue = w.domain.create_issue(member, "member", requirement_id=req["id"], acceptance="member present")
    key = w.authorize_task(
        member,
        issue["id"],
        selected={"a": initial["a"]},
        writes={"a": "*"},
        dependencies={},
        profile="local",
        product="joint",
        checks=["check"],
        mandate="multi-member",
        delivery_mode="contribution",
    )
    reserve((w, member, tenant, req, initial, path), key)
    w.execute(member, key)
    i.check_contribution(member, key)
    assert i.continuous.ready(member)[0]["key"] == lane
    while i.continuous.ready(member):
        assert i.continue_lane(member, lane)["state"] == "accepted"
    assert all(w.status(actor, k)["state"] == "accepted" for k in [*keys, key])
    stranger = w.domain.register("other", "other@example.invalid", "password")["user_id"]
    with pytest.raises(NativeStoreError, match="same-tenant"):
        i.continuous.ready(stranger)
    with w._transaction() as db:
        db.execute("UPDATE users SET role='viewer' WHERE id=?", (actor,))
    with pytest.raises(NativeStoreError, match="same-tenant"):
        i.continue_lane(member, lane)


@pytest.mark.parametrize("failure", ["tamper", "revoke"])
def test_history_revalidated_between_review_and_publication(fixture, failure):
    w, actor, tenant, *_ = fixture
    i, keys, policy, lane = continuous(fixture)
    i.continue_lane(actor, lane)
    original = w.release.publish

    def tamper(*args, **kwargs):

        if failure == "tamper":
            views = w.worker.store.database.parent / "native-criteria-history" / "views"
            for path in views.glob("*/*.json"):
                path.write_text("{}", encoding="utf-8")
        else:
            old_issue = w.status(actor, keys[0])["issue"]
            w.authorize = lambda who, issue, action: issue != old_issue
        return original(*args, **kwargs)

    w.release.publish = tamper
    assert i.continue_lane(actor, lane)["state"] == "held"
    assert w.status(actor, keys[1])["state"] == "produced"
    with w.worker.store._connection() as db:
        assert db.execute("SELECT count(*) FROM native_release_events").fetchone()[0] == 1


def test_busy_observer_binds_actual_driver_and_restart_receipt(fixture):
    import asyncio
    import threading
    from concurrent.futures import ThreadPoolExecutor

    w, actor, tenant, *_ = fixture
    i, keys, policy, lane = continuous(fixture)
    entered, release = threading.Event(), threading.Event()

    def review(*args):
        entered.set()
        assert release.wait(10)
        return True

    w.review_candidate = review
    with ThreadPoolExecutor(1) as pool:
        running = pool.submit(i.continue_lane, actor, lane, "original-event")
        assert entered.wait(10)
        assert i.continue_lane(actor, lane, "follower-event")["state"] == "publisher_busy"
        release.set()
        observed = asyncio.run(i.continuous.await_lane(actor, lane, "follower-event"))
        assert observed == running.result()
    i.continuous = ContinuousIntegration(i, lambda a: [policy])
    assert asyncio.run(i.continuous.await_lane(actor, lane, "original-event")) == observed
    with w.worker.store._connection() as db:
        assert db.execute("SELECT count(*) FROM native_release_events").fetchone()[0] == 1


def test_restart_does_not_replay_unknown_driver(fixture):
    import asyncio

    from native_integration import digest

    w, actor, tenant, *_ = fixture
    i, keys, policy, lane = continuous(fixture)
    token = digest([lane, "unknown-event"])
    with w._transaction() as db:
        db.execute(
            "INSERT INTO native_continuous_drives VALUES (?,?,?,'running',NULL,NULL)", (token, lane, "unknown-event")
        )
    with pytest.raises(NativeStoreError, match="outcome unknown"):
        asyncio.run(i.continuous.await_lane(actor, lane, "unknown-event"))
    assert all(w.status(actor, k)["state"] == "produced" for k in keys)


@pytest.mark.parametrize("failure", ["changed", "revoked", "unknown-review"])
def test_frozen_member_invalidation_is_scope_bound(fixture, failure):
    w, actor, tenant, *_ = fixture
    i, keys, policy, lane = continuous(fixture)
    batch = i.continuous.freeze(actor, lane, policy, keys)
    issue = w.status(actor, keys[0])["issue"]
    if failure == "unknown-review":

        def unknown(*args):
            with w._transaction() as db:
                db.execute("UPDATE issues SET acceptance='changed' WHERE id=?", (issue,))
            raise RuntimeError("external reviewer response lost")

        w.review_candidate = unknown
        assert i.continue_lane(actor, lane)["state"] == "held"
        assert (
            w.domain.db.execute("SELECT active FROM native_continuous_lanes WHERE id=?", (lane,)).fetchone()[0] == batch
        )
        assert all(w.status(actor, k)["state"] == "produced" for k in keys)
        return
    if failure == "changed":
        with w._transaction() as db:
            db.execute("UPDATE issues SET acceptance='changed' WHERE id=?", (issue,))
    else:
        w.authorize = lambda who, key, action: key != issue or action == "read"
    assert i.continue_lane(actor, lane)["state"] == "invalid_members_isolated"
    assert i.continue_lane(actor, lane)["state"] == "accepted"
    assert w.status(actor, keys[0])["state"] == "produced"
    assert w.status(actor, keys[1])["state"] == "accepted"


def test_successor_preserves_deletion_and_business_manifest_prefix(fixture):
    w, actor, tenant, _, initial, _ = fixture
    initial["a"] = w.worker.store.submit(
        tenant, actor, "delete-base", [dict(module="a", base=initial["a"], reads=None, edits={"obsolete": b"old"})]
    )["revisions"]["a"]
    business = "integration-" + "f" * 64
    revision = w.worker.store.submit(
        tenant,
        actor,
        "business-prefix",
        [dict(module=business, base=None, reads=None, edits={"business.txt": b"keep"})],
    )["revisions"][business]
    i, keys, policy, lane = continuous(fixture, [{"obsolete": None}, {"right": b"R"}], extra_base={business: revision})
    assert i.continue_lane(actor, lane)["state"] == "accepted"
    final = i.continue_lane(actor, lane)["release"]
    assert final["modules"][business] == revision
    assert "obsolete" not in w.worker.store.revision(tenant, "a", final["modules"]["a"])["objects"]
    assert w.worker.store.read(tenant, "a", final["modules"]["a"], "right") == b"R"


@pytest.mark.parametrize("stage", ["enqueue", "freeze", "review", "publish", "persisted"])
def test_fixed_atomic_membership_never_splits(fixture, stage):
    w, actor, tenant, *_ = fixture
    i, keys, policy, lane = continuous(fixture)

    def install():
        return setattr(i, "installed_groups", lambda a: ["atomic-required"])

    if stage in {"enqueue", "freeze", "persisted"}:
        install()
        found = i.discover(actor)
        fixed = found["ready"][0]["key"]
        if stage == "persisted":
            i.installed_groups = lambda a: []
        if stage == "enqueue":
            with pytest.raises(NativeStoreError, match="Fixed group"):
                i.continuous.enqueue(actor, keys[0])
            assert i.check_contribution(actor, keys[0])["state"] == "contribution_checked"
        with pytest.raises(NativeStoreError, match="Fixed group"):
            i.continuous.freeze(actor, lane, policy, [keys[0]])
        assert i.continue_lane(actor, lane)["state"] == "idle"
        assert all(w.status(actor, key)["state"] == "produced" for key in keys)
        assert i.finish(actor, fixed)["candidate"]
        assert all(w.status(actor, key)["state"] == "accepted" for key in keys)
    else:
        if stage == "review":

            def review(*args):
                install()
                return True

            w.review_candidate = review
        else:
            publish = w.release.publish

            def late(*args, **kwargs):
                install()
                return publish(*args, **kwargs)

            w.release.publish = late
        assert i.continue_lane(actor, lane)["state"] == "held"
        assert all(w.status(actor, key)["state"] == "produced" for key in keys)
    with w.worker.store._connection() as db:
        assert db.execute("SELECT count(*) FROM native_release_events").fetchone()[0] == (
            1 if stage in {"enqueue", "freeze", "persisted"} else 0
        )


@pytest.mark.parametrize("damage", ["input", "archive", "view", "extra", "changed"])
@pytest.mark.parametrize("state", ["complete", "result", "running", "cached"])
def test_history_restart_never_recreates_or_relaunches(fixture, damage, state):
    import json
    from pathlib import Path

    from native_check_runner import NativeCheckRunner

    w, actor, tenant, *_ = fixture
    i, keys, policy, lane = continuous(fixture)
    assert i.continue_lane(actor, lane)["state"] == "accepted"
    assert i.continue_lane(actor, lane)["state"] == "accepted"
    with w.worker.store._connection() as db:
        rows = [dict(r) for r in db.execute("SELECT * FROM native_check_runs")]
    row = next(r for r in rows if json.loads(r["payload"]).get("history_binding"))
    value = json.loads(row["payload"])
    history = i.continuous.prepare(tenant, actor, value["candidate"], "check", materialize=False)
    view = Path(history["env"]["DUOBAO_HISTORY"])
    target = next(view.glob("*.json"))
    if damage == "archive":
        target = next(p for p in view.parent.parent.glob("*/*.json") if p.name == target.name)
    if damage in {"input", "archive", "view"}:
        target.unlink()
        if damage == "view":
            view.rmdir()
    elif damage == "extra":
        (view / "extra.json").write_text("{}")
    else:
        target.write_text("{}")
    with w.worker.store._connection(write=True) as db:
        value["state"] = state
        db.execute("UPDATE native_check_runs SET payload=? WHERE run_key=?", (json.dumps(value), row["run_key"]))
    runner = NativeCheckRunner(
        w.runner.cache, w.runner.root, w.runner._registry, w.runner.authorize, w.runner.verify_installation
    )
    runner.history_provider = i.continuous
    launches = []
    runner.helper.run_owned = lambda *a, **k: launches.append(1)
    for run_key in [row["run_key"], "cache-read-after-damage"]:
        with pytest.raises((OSError, NativeStoreError)):
            runner.execute(tenant, actor, run_key, value["candidate"], "check")
    assert launches == []
    if damage in {"input", "archive", "view"}:
        assert not target.exists()


@pytest.mark.parametrize("owner", ["caller", "original", "coordinator", "persisted-other"])
def test_fixed_membership_across_principals(fixture, owner):
    import json

    w, actor, tenant, *_ = fixture
    i, keys, policy, lane = continuous(fixture)
    member = w.domain.add_member(actor, "fixed-member@example.invalid", "password")["user_id"]
    # Queue can be submitted by another authorized same-tenant caller.
    i.continuous.enqueue(member, keys[0])
    who = member if owner == "caller" else actor
    if owner == "persisted-other":
        with w._transaction() as db:
            db.execute(
                "INSERT INTO native_integration_groups VALUES (?,?,?,NULL)",
                (member, "fixed", json.dumps(i.installed_plan(actor, "fixed"))),
            )
    else:
        i.installed_groups = lambda a: ["fixed"] if a == who else []
    with pytest.raises(NativeStoreError, match="Fixed group"):
        i.continuous.freeze(actor, lane, policy, [keys[0]])
    assert all(w.status(actor, key)["state"] == "produced" for key in keys)


def test_unrelated_fixed_members_do_not_disable_continuous(fixture):
    w, actor, *_ = fixture
    i, keys, policy, lane = continuous(fixture)
    original = i.installed_plan
    i.installed_groups = lambda a: ["unrelated"]
    i.installed_plan = lambda a, g: dict(original(a, g), tasks=["unrelated-task"], product="other")
    assert i.continue_lane(actor, lane)["state"] == "accepted"
    assert i.continue_lane(actor, lane)["state"] == "accepted"
