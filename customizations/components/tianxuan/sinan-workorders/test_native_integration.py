"""Real candidate intake and subprocess checks; terminal adapter fixture only.

Physical worker/HTTP delivery is separately gated by #1461 acceptance.
"""

import json

# pytest imports this fixture as a registration, then injects it by argument.
# ruff: noqa: F811
import pytest
from native_candidates import NativeCandidates
from native_integration import NativeIntegration, digest
from native_store import NativeStoreError, _json
from test_native_workflow import fixture  # noqa: F401


def setup(f, edits=None, modules=("a", "a"), producer=None):
    w, actor, tenant, req, initial, _ = f
    producer = actor if producer is None else producer
    w.principals = lambda a, i, role: {
        "producer": producer,
        "integrator": actor,
        "checker": actor,
        "reviewer": "reviewer",
        "publisher": "publisher",
    }[role]
    candidates = NativeCandidates(w.worker.store, lambda *a: True)
    keys = []
    for index, delta in enumerate(edits or [{"left": b"L"}, {"right": b"R"}]):
        issue = w.domain.create_issue(actor, "joint-" + str(index), requirement_id=req["id"], acceptance="joint check")
        module = modules[index]
        key = w.authorize_task(
            actor,
            issue["id"],
            selected={module: initial[module]},
            writes={module: "*"},
            dependencies={},
            profile="local",
            product="joint",
            checks=["check"],
            mandate="test-integration",
            delivery_mode="contribution",
        )
        original = json.loads(w.status(actor, key)["task"])
        origin = dict(
            source_ref="native-source:" + digest(original["source"]),
            worker_ref="native-worker:" + key,
            issue_url="native://" + tenant + "/issues/" + issue["id"],
        )
        intake = (
            None
            if delta is None
            else candidates.receive(
                tenant,
                producer,
                key,
                [
                    dict(
                        module=module,
                        base=initial[module],
                        reads=None,
                        edits={"output": (module + " produced").encode(), **delta},
                    )
                ],
                origin,
            )
        )
        selected = {**original["selected"], **(intake["revisions"] if intake else {})}
        candidate = w.worker.store.compose(tenant, selected)
        terminal = dict(
            state="produced",
            candidate=candidate["id"],
            intake=intake,
            modules=candidate["modules"],
            origin=origin,
            no_changes=delta is None,
            exit_code=0,
            transcript="a" * 64,
        )
        with w._transaction() as db:
            db.execute("UPDATE native_tasks SET state='produced',terminal=? WHERE id=?", (_json(terminal), key))
        keys.append(key)
    w.review_candidate = lambda *args: True
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
    integration = NativeIntegration(w, candidates, lambda *args: spec)
    for key in keys:
        assert integration.check_contribution(actor, key)["state"] == "contribution_checked"
    plan = integration.authorize(actor, "same-product")
    w.release.configure(
        tenant,
        "publisher",
        "joint",
        dict(checks={"check": w.runner.context("check", "0" * 64)}, review_max_age_seconds=3600),
    )
    return integration, plan, keys, spec


def test_joint_release_preserves_originals_and_heads(fixture):
    w, actor, tenant, req, initial, _ = fixture
    integration, plan, keys, _ = setup(fixture)
    originals = [w.status(actor, k)["terminal"] for k in keys]
    merged = integration.execute(actor, plan)
    assert merged == integration.execute(actor, plan)
    revision = merged["modules"]["a"]
    assert w.worker.store.read(tenant, "a", revision, "left") == b"L"
    assert w.worker.store.read(tenant, "a", revision, "right") == b"R"
    with w.worker.store._connection() as db:
        assert (
            db.execute("SELECT revision FROM native_heads WHERE tenant=? AND module='a'", (tenant,)).fetchone()[0]
            == initial["a"]
        )
    for key in keys:
        with pytest.raises(NativeStoreError, match="joint integration"):
            w.review(actor, key)
    accepted = integration.finish(actor, plan)
    assert integration.finish(actor, plan) == accepted
    assert [w.status(actor, k)["terminal"] for k in keys] == originals
    assert all(json.loads(w.status(actor, k)["acceptance"])["id"] == accepted["id"] for k in keys)
    assert w.domain.sync_progress(req["id"], actor=actor)["done"] == 2
    with w.worker.store._connection() as db:
        assert db.execute("SELECT count(*) FROM native_release_events").fetchone()[0] == 1


def test_conflicting_edits_do_not_choose_last_writer(fixture):
    _, actor, *_ = fixture
    integration, plan, _, _ = setup(fixture, [{"same": b"A"}, {"same": b"B"}])
    result = integration.execute(actor, plan)
    assert result["state"] == "conflicts_pending"
    assert integration.status(actor, plan)["result"] is None


def test_source_change_blocks_entire_group(fixture):
    w, actor, _, _, _, _ = fixture
    integration, plan, keys, _ = setup(fixture)
    integration.execute(actor, plan)
    issue = w.status(actor, keys[1])["issue"]
    with w._transaction() as db:
        db.execute("UPDATE issues SET acceptance='changed' WHERE id=?", (issue,))
    with pytest.raises(NativeStoreError, match="definition changed"):
        integration.finish(actor, plan)
    assert all(w.status(actor, k)["state"] == "produced" for k in keys)


def test_fanin_fault_rolls_back_all_and_recovers_historical(fixture):
    w, actor, tenant, _, _, _ = fixture
    integration, plan, keys, _ = setup(fixture)
    original_event = w.domain._event

    def fail(*args, **kwargs):
        if args[1] == "native.accepted":
            raise RuntimeError("injected domain failure")
        return original_event(*args, **kwargs)

    w.domain._event = fail
    with pytest.raises(RuntimeError, match="injected"):
        integration.finish(actor, plan)
    assert all(w.status(actor, k)["state"] == "produced" for k in keys)
    selected = w.release.selected(tenant, actor, "joint", "stable")
    review = json.loads(integration.status(actor, plan)["review"])
    w.release.publish(tenant, "publisher", "later-release", "joint", "stable", review["id"], selected["id"])
    w.domain._event = original_event
    assert integration.finish(actor, plan)["id"] == selected["id"]


def test_receipt_reader_uses_own_authority(fixture):
    w, actor, tenant, _, _, _ = fixture
    integration, _, keys, _ = setup(fixture)
    integration.candidates.authorize = lambda db, t, a, m, op: a != "intruder"
    with pytest.raises(NativeStoreError, match="authorization denied"):
        integration.candidates.receipt_for(tenant, "intruder", actor, keys[0])


def test_all_original_checks_required(fixture):
    _, actor, *_ = fixture
    integration, _, _, spec = setup(fixture)
    spec["checks"] = ["missing"]
    with pytest.raises(NativeStoreError, match="omit original"):
        integration.authorize(actor, "same-product")


def test_installed_resolver_creates_successor_without_changing_originals(fixture):
    w, actor, tenant, _, initial, _ = fixture
    integration, plan, keys, _ = setup(fixture, [{"same": b"A"}, {"same": b"B"}])
    terminals = [w.status(actor, k)["terminal"] for k in keys]
    prior = w.principals
    w.principals = lambda a, i, role: "heqi-resolver" if role == "resolver" else prior(a, i, role)

    def resolve(a, installed, pending, request):
        assert not w.domain.db.in_transaction
        assert pending["conflicts"][0]["path"] == "same"
        return integration.candidates.receive(
            tenant,
            "heqi-resolver",
            request,
            [dict(module="a", base=initial["a"], reads=None, edits={"same": b"resolved"})],
            dict(source_ref=plan, worker_ref=request, issue_url=installed["issue_url"]),
        )

    integration.installed_resolver = resolve
    successor = integration.resolve(actor, plan)
    assert successor != plan
    assert integration.resolve(actor, plan) == successor
    result = integration.execute(actor, successor)
    assert w.worker.store.read(tenant, "a", result["modules"]["a"], "same") == b"resolved"
    assert "heqi-resolver" in result["authors"]
    assert [w.status(actor, k)["terminal"] for k in keys] == terminals
    w.principals = lambda a, i, role: "heqi-resolver" if role == "reviewer" else prior(a, i, role)
    with pytest.raises(NativeStoreError, match="Independent"):
        integration.finish(actor, successor)


def test_semantic_failure_only_in_joint_candidate_blocks_release(fixture):
    w, actor, tenant, *_ = fixture
    w.runner._registry["check"]["argv"][2] += "; assert not ((p/'a'/'left').exists() and (p/'a'/'right').exists())"
    integration, plan, keys, _ = setup(fixture)
    with pytest.raises(NativeStoreError, match="Joint product checks failed"):
        integration.finish(actor, plan)
    assert all(w.status(actor, key)["state"] == "produced" for key in keys)
    assert w.release.selected(tenant, actor, "joint", "stable") is None


def test_revoked_producer_authority_blocks_finalization(fixture):
    w, actor, _, _, _, _ = fixture
    integration, plan, keys, _ = setup(fixture)
    integration.execute(actor, plan)
    integration.candidates.authorize = lambda db, tenant, who, module, action: action != "receive"
    with pytest.raises(NativeStoreError, match="authorization denied"):
        integration.finish(actor, plan)
    assert all(w.status(actor, key)["state"] == "produced" for key in keys)


def test_cas_loser_successor_reuses_contributions(fixture):
    w, actor, tenant, _, _, _ = fixture
    integration, plan, keys, spec = setup(fixture)
    originals = [w.status(actor, k)["terminal"] for k in keys]
    first = integration.finish(actor, plan)
    # A separate group is checked against the same original base, then its
    # fixed expected release loses to the existing publication.
    other, loser, other_keys, other_spec = setup(fixture)
    from native_store import Conflict

    with pytest.raises(Conflict, match="Channel changed"):
        other.finish(actor, loser)
    other_spec["expected"] = first["id"]
    successor = other.authorize(actor, "same-product")
    assert successor != loser
    assert other.finish(actor, successor)["state"] == "content_selected"
    assert [w.status(actor, k)["terminal"] for k in keys] == originals
    assert all(w.status(actor, k)["state"] == "accepted" for k in other_keys)


def test_authenticated_http_installed_plan_only(fixture):
    from api import create_app
    from fastapi.testclient import TestClient

    w, actor, *_ = fixture
    _, plan, _, _ = setup(fixture)
    headers = {"Authorization": "Bearer " + w.domain.issue_session(actor)}
    with TestClient(create_app(w.domain, native_store=w.worker.store, native_only=True, native_workflow=w)) as client:
        route = "/api/v1/native/workflow/integration-"
        assert client.post(route + "status", json={"key": plan}).status_code == 401
        assert client.post(route + "execute", json={"key": plan, "actor": actor}, headers=headers).status_code == 422
        assert (
            client.post(route + "authorize", json={"group": "same-product", "tasks": []}, headers=headers).status_code
            == 422
        )
        assert client.post(route + "authorize", json={"group": "same-product"}, headers=headers).json() == plan
        assert client.post(route + "execute", json={"key": plan}, headers=headers).json()["state"] == "integrated"
        assert client.post(route + "finish", json={"key": plan}, headers=headers).json()["state"] == "content_selected"


def test_original_workflow_review_accepts_verified_cache_hit(fixture):
    from test_native_workflow import reserve, task

    w, actor, tenant, _, initial, _ = fixture
    first, _ = task(fixture, "a")
    reserve(fixture, first)
    w.execute(actor, first)
    w.check(actor, first)
    second, issue = task(fixture, "a")
    # A separate actual task has identical content; its durable terminal refers
    # to that content and the second check request must hit real EvidenceCache.
    terminal = w.status(actor, first)["terminal"]
    with w._transaction() as db:
        db.execute("UPDATE native_tasks SET state='produced',terminal=? WHERE id=?", (terminal, second))
    w.principals = lambda a, i, role: {"reviewer": "reviewer", "checker": actor}[role]
    w.review_candidate = lambda *args: True
    w.release.configure(
        tenant,
        "publisher",
        "a",
        dict(checks={"check": w.runner.context("check", "0" * 64)}, review_max_age_seconds=3600),
    )
    assert w.check(actor, second)["check"]["state"] == "cached"
    assert w.review(actor, second)["state"] == "independent_review"


def test_noop_contribution_has_no_fabricated_intake(fixture):
    w, actor, tenant, _, initial, _ = fixture
    initial.update(
        w.worker.store.submit(
            tenant,
            actor,
            "noop-base",
            [dict(module="a", base=initial["a"], reads=None, edits={"output": b"a produced"})],
        )["revisions"]
    )
    integration, plan, keys, _ = setup(fixture, [None, {"right": b"R"}])
    before = w.status(actor, keys[0])["terminal"]
    assert json.loads(before)["intake"] is None
    assert integration.finish(actor, plan)["state"] == "content_selected"
    assert w.status(actor, keys[0])["terminal"] == before


def test_explicit_dependency_repin_and_cycle_rejection(fixture):
    w, actor, tenant, _, initial, _ = fixture
    initial.update(
        w.worker.store.submit(
            tenant,
            actor,
            "dependency-base",
            [
                dict(module="b", base=initial["b"], reads=None, edits={"output": b"b produced"}),
                dict(
                    module="a",
                    base=initial["a"],
                    reads=None,
                    edits={"output": b"a produced"},
                    dependencies={"b": "@batch"},
                ),
            ],
        )["revisions"]
    )
    integration, plan, keys, spec = setup(fixture, [{"left": b"L"}, {"right": b"R"}], modules=("a", "b"))
    with pytest.raises(NativeStoreError, match="Incompatible"):
        integration.execute(actor, plan)
    spec["repins"] = {"a": {"b": "@integrated"}}
    successor = integration.authorize(actor, "same-product")
    merged = integration.execute(actor, successor)
    assert w.worker.store.revision(tenant, "a", merged["modules"]["a"])["dependencies"] == {"b": merged["modules"]["b"]}
    assert integration.finish(actor, successor)["state"] == "content_selected"


def test_explicit_dependency_cycle_rejected(fixture):
    w, actor, tenant, _, initial, _ = fixture
    initial.update(
        w.worker.store.submit(
            tenant,
            actor,
            "dependency-base",
            [
                dict(module="b", base=initial["b"], reads=None, edits={"output": b"b produced"}),
                dict(
                    module="a",
                    base=initial["a"],
                    reads=None,
                    edits={"output": b"a produced"},
                    dependencies={"b": "@batch"},
                ),
            ],
        )["revisions"]
    )
    integration, _, _, spec = setup(fixture, [{"left": b"L"}, {"right": b"R"}], modules=("a", "b"))
    spec["repins"] = {"a": {"b": "@integrated"}, "b": {"a": "@integrated"}}
    plan = integration.authorize(actor, "same-product")
    with pytest.raises(NativeStoreError, match="Cyclic"):
        integration.execute(actor, plan)


def test_resolver_lost_reply_recovers_real_receipt_without_relaunch(fixture):
    w, actor, tenant, _, initial, _ = fixture
    integration, plan, _, _ = setup(fixture, [{"same": b"A"}, {"same": b"B"}])
    prior = w.principals
    w.principals = lambda a, i, role: actor if role == "resolver" else prior(a, i, role)
    calls = []

    def resolve(a, installed, pending, request):
        calls.append(request)
        integration.candidates.receive(
            tenant,
            actor,
            request,
            [dict(module="a", base=initial["a"], reads=None, edits={"same": b"resolved"})],
            dict(source_ref=plan, worker_ref=request, issue_url=installed["issue_url"]),
        )
        raise RuntimeError("lost resolver reply")

    integration.installed_resolver = resolve
    with pytest.raises(RuntimeError, match="lost resolver"):
        integration.resolve(actor, plan)
    recovered = integration.reconcile(actor, plan)
    assert integration.execute(actor, recovered)["state"] == "integrated"
    assert len(calls) == 1


def test_review_unknown_requires_installed_exact_receipt(fixture):
    w, actor, _, _, _, _ = fixture
    integration, plan, _, _ = setup(fixture)
    calls = []

    def review(*args):
        calls.append(args)
        raise RuntimeError("lost review reply")

    w.review_candidate = review
    with pytest.raises(RuntimeError, match="lost review"):
        integration.finish(actor, plan)
    with pytest.raises(NativeStoreError, match="outcome unknown"):
        integration.reconcile(actor, plan)
    integration.review_receipt = lambda actor, p, result, reviewer: dict(
        id="installed-host-receipt", plan=plan, candidate=result["candidate"], reviewer=reviewer, decision="accepted"
    )
    assert integration.reconcile(actor, plan)["state"] == "content_selected"
    assert len(calls) == 1


@pytest.mark.parametrize("edits", [[{"Alias": b"A"}, {"alias": b"B"}], [{"parent": b"A"}, {"parent/child": b"B"}]])
def test_cross_contribution_portable_tree_collisions(fixture, edits):
    _, actor, *_ = fixture
    integration, plan, _, _ = setup(fixture, edits)
    with pytest.raises(NativeStoreError):
        integration.execute(actor, plan)


def test_cached_result_with_wrong_evidence_id_is_not_success(fixture):
    from native_workflow import check_passed

    w, actor, tenant, *_ = fixture
    integration, plan, keys, _ = setup(fixture)
    candidate = json.loads(w.status(actor, keys[0])["terminal"])["candidate"]
    assert not check_passed(w.runner, tenant, candidate, "check", {"state": "cached", "evidence": "0" * 64})


def test_distinct_installed_producer_is_not_a_domain_user(fixture):
    w, actor, *_ = fixture
    integration, plan, keys, _ = setup(fixture, producer="installed-producer")
    assert integration.finish(actor, plan)["state"] == "content_selected"
    assert all(json.loads(w.status(actor, key)["task"])["producer"] == "installed-producer" for key in keys)


def test_changed_installed_producer_cannot_reuse_contribution(fixture):
    w, actor, *_ = fixture
    integration, plan, _, _ = setup(fixture, producer="installed-producer")
    original = w.principals
    w.principals = lambda a, i, role: "replacement-producer" if role == "producer" else original(a, i, role)
    with pytest.raises(NativeStoreError, match="producer installation changed"):
        integration.finish(actor, plan)


def test_accepted_history_survives_task_replacement_without_new_work(fixture):
    w, actor, tenant, *_ = fixture
    integration, plan, keys, _ = setup(fixture)
    accepted = integration.finish(actor, plan)
    original = json.loads(w.status(actor, keys[0])["task"])
    replacement = w.authorize_task(
        actor,
        original["issue"],
        selected=original["selected"],
        writes=original["writes"],
        dependencies=original["dependencies"],
        profile=original["profile"],
        product=original["product"],
        checks=original["checks"],
        mandate="new-authorized-mandate",
        expected=keys[0],
        delivery_mode="contribution",
    )
    assert replacement != keys[0]
    before = list(w.domain.db.execute("SELECT * FROM native_outbox"))
    assert json.loads(integration.status(actor, plan)["acceptance"]) == accepted
    assert integration.finish(actor, plan) == accepted
    assert w.status(actor, replacement)["state"] == "ready"
    assert w.domain.get_issue(original["issue"])["status"] == "planned"
    assert list(w.domain.db.execute("SELECT * FROM native_outbox")) == before
    with w.worker.store._connection() as db:
        assert db.execute("SELECT count(*) FROM native_release_events").fetchone()[0] == 1
    with pytest.raises(NativeStoreError, match="superseded|Original contribution terminal required"):
        integration.execute(actor, plan)
    prior_authorize = integration.candidates.authorize
    integration.candidates.authorize = lambda db, t, a, m, op: a != actor
    with pytest.raises(NativeStoreError, match="authorization denied"):
        integration.status(actor, plan)
    integration.candidates.authorize = prior_authorize
    assert integration.finish(actor, plan) == accepted
    w.runner.cache.policies["check"] = dict(version="new-policy", reads=None, max_age_seconds=3600)
    with pytest.raises(NativeStoreError):
        integration.status(actor, plan)
