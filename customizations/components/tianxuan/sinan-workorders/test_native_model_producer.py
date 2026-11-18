"""Deterministic installed process through NativeWorkflow and NativeIntegration."""

# pytest fixture imported for registration and injected by name.
# ruff: noqa: F811
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# isort: off
import native_model_producer as producer
import evaluate
import pytest
import runner
from native_proposal_adapter import host_for
from test_native_workflow import fixture, reserve, task  # noqa: F401
# isort: on

PROBE = """import sys,json,hashlib,time
p=json.load(sys.stdin); r=p['request']; time.sleep(.2)
if r['request_id'] != 'evaluation':
 assert 'Runtime governing context:' in r['context'] and 'fixed proposal' in r['context'] and 'Return only JSON' in r['context']
 assert 'native_binding' not in r['context']
def d(v): return hashlib.sha256(json.dumps(v,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()
files=[{'path':n,'content':n.split('/')[0]+' produced'} for n in r['write_allowlist']]
v={'request_id':r['request_id'],'input_digest':d(r),'summary':'deterministic installed probe','files':files}
c={'cachedInputTokens':0,'inputTokens':5,'outputTokens':3,'reasoningOutputTokens':1,'totalTokens':8}
usage={'thread_id':'known-thread','turn_id':r['request_id'],'observed_model':'probe','raw':{'last':c,'total':c},'status':'observed','source':'thread/tokenUsage/updated','normalized_usage':None}
unknown=r['acceptance']=='unknown'
print(json.dumps({'request_id':r['request_id'],'input_digest':d(r),'config_digest':p['installed']['config_digest'],'requested_model':p['installed']['model'],'execution_authority':False,'status':'unknown' if unknown else 'proposed','proposal':None if unknown else v,'output_digest':None if unknown else d(v),'usage':usage,'elapsed_ms':200}))
"""
SCHEMA = {
    "type": "object",
    "properties": {
        "request_id": {"type": "string"},
        "input_digest": {"type": "string"},
        "summary": {"type": "string"},
        "files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
        },
    },
    "required": ["request_id", "input_digest", "summary", "files"],
}


def installed(tmp, monkeypatch):
    monkeypatch.setenv("GONGGONG_HOST_KEY", "isolated-producer-test-authority-key")
    monkeypatch.setenv("PYTHONUTF8", "1")
    monkeypatch.setenv("PATH", str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"])
    probe = tmp / "probe.py"
    probe.write_text(PROBE, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "PYTHONUTF8"}}
    native = dict(
        node=sys.executable,
        entry=str(probe),
        python=sys.executable,
        model="probe",
        reasoning_effort=None,
        env=env,
        timeout=10,
    )
    p = dict(
        id="native",
        protocol="codex-native-proposal",
        model="probe",
        native_installation=native,
        timeout_seconds=10,
        max_context_bytes=1000000,
        output_token_limit="unsupported",
        response_bytes=524288,
        validation_probe=str(probe),
        validation_probe_sha256=hashlib.sha256(probe.read_bytes()).hexdigest(),
    )
    p["installation_digest"] = host_for(p).configuration()[1]
    request = dict(request_id="evaluation", task="fixed", context="{}", write_allowlist=["a/output"], acceptance="pass")
    report = evaluate.evaluate(
        p,
        [
            dict(
                id="proposal",
                task_type="native",
                messages=[dict(role="user", content=runner.canonical({"input": {"native_request": request}}))],
                schema=SCHEMA,
            )
        ],
        "synthetic",
    )
    assert report["passed_task_types"] == ["native"]
    f = tmp / "evaluation.json"
    f.write_text(runner.canonical(report), encoding="utf-8")
    p["evaluation"] = {
        **{k: report[k] for k in ["profile_digest", "scope", "passed_task_types"]},
        "evidence_ref": str(f),
        "evidence_sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
    }
    return p, env


def framework(tmp):
    # Existing framework test uses synthetic review passes; copied only into this
    # test-owned install. No frozen source or real approval is changed.
    import runpy
    import shutil

    root = tmp / "framework"
    shutil.copytree(producer.ROOT / "framework", root, ignore=shutil.ignore_patterns("__pycache__"))
    manifest = runner.read(root / "framework-manifest.json")
    (root / "reviews/fixture.txt").write_text("Synthetic only", encoding="utf-8")
    fp = runpy.run_path(str(root / "tools/verify_framework.py"))["fingerprint"]
    for a in manifest["agents"]:
        p = runner.read(root / "templates/review-pass.json")
        d, files = fp(root, a["candidate_files"])
        p.update(template=False, status="approved", event="agent_definition_change", phase="local_definition_release")
        p["subject"] = {
            "id": a["id"],
            "version_or_digest": {"version": a["version"], "candidate_digest": d, "candidate_files": files},
            "scope": ["local_agent_definition_only"],
        }
        p["review"] = {
            "gonggong_framework": "pass",
            "concision": {"status": "pass"},
            "applicable_validation": "pass",
            "independence": "independent_subagent_review",
            "evaluator_id": "synthetic-reviewer",
            "yuanheng": {k: "pass" for k in ["purpose", "truth", "economy", "authority", "adaptation", "continuity"]},
            "evidence_refs": ["reviews/fixture.txt"],
        }
        p["approval"] = {
            "approver_id": "synthetic-approver",
            "authority_ref": "test-only",
            "decision_evidence_ref": "reviews/fixture.txt",
            "approved_at": runner.now(),
            "valid_until_or_task_end": "bound_candidate_only",
            "expires_at": None,
        }
        (root / a["admission_pass"]).write_text(json.dumps(p), encoding="utf-8")
    inv = runpy.run_path(str(root / "tools/package_integrity.py"))["inventory"](root)
    (root / "package-lock.json").write_text(
        json.dumps({"schema_version": 1, "path_base": "framework_root", "files": inv}), encoding="utf-8"
    )
    return root


def prepare(f, monkeypatch):
    w, actor, tenant, req, initial, tmp = f
    p, env = installed(tmp, monkeypatch)
    root = framework(tmp)
    registry = tmp / "registry"
    registry.mkdir()
    w.worker.profiles["local"] = dict(
        argv=[sys.executable, "-B", "-X", "utf8", str(Path(producer.__file__)), "--registry", str(registry)],
        env={**env, "GONGGONG_HOST_KEY": os.environ["GONGGONG_HOST_KEY"]},
        timeout=60,
        log_bytes=20000,
    )
    return p, root, registry


def admit(f, p, root, registry, module, acceptance="pass", joint=False):
    w, actor, tenant, req, initial, tmp = f
    if joint:
        issue = w.domain.create_issue(actor, module, requirement_id=req["id"], acceptance="passed check")
        key = w.authorize_task(
            actor,
            issue["id"],
            selected={module: initial[module]},
            writes={module: "*"},
            dependencies={},
            profile="local",
            product="joint",
            checks=["check"],
            mandate="test",
            delivery_mode="contribution",
        )
    else:
        key, _ = task(f, module)
    contract = json.loads(w.status(actor, key)["task"])
    files = {}
    for m, rev in contract["selected"].items():
        # Match exact NativeWorkspace materialization, including requirement.
        staging = tmp / ("input-" + key)
    w.worker.workspace.materialize(tenant, contract["selected"], staging)
    files = producer.snapshot(staging)
    request = dict(
        request_id=key,
        task=runner.canonical(contract["source"]["definition"]),
        context=runner.canonical(files),
        write_allowlist=[module + "/output"],
        acceptance=acceptance,
    )
    t = dict(
        id=key,
        tenant_id=tenant,
        project_id="test",
        agent_id="yanshi",
        outcome="native production",
        authority_ref="synthetic",
        retention="test",
        mode="single",
        validation_only=True,
        work_items=[dict(id="1486", kind="feature", relation="tests", certainty="confirmed")],
        input=producer.prepare_inputs(
            contract, key, w.worker.root / key / "work", files, request["write_allowlist"], acceptance
        ),
        steps=[dict(id="proposal", kind="native", instruction="fixed proposal", output="json", schema=SCHEMA)],
    )
    central = dict(state_dir=str(tmp / "budgets"), max_calls=10, max_concurrent=2, authority_ref="synthetic-central")
    payload = dict(
        task=t,
        profiles=[p],
        limits=dict(max_calls=1, max_output_tokens=None, output_token_limit="unsupported"),
        central_budget=central,
        state_dir=str(Path(central["state_dir"]) / "tasks" / runner.jid_for(t)),
        runtime_sha256=runner.runtime_digest(),
        framework_sha256=hashlib.sha256((root / "framework-manifest.json").read_bytes()).hexdigest(),
        authority_ref="synthetic",
        expires_at=time.time() + 600,
    )
    grant = dict(payload=payload, signature=runner.signature(payload))
    producer.register(registry, key, grant, root)
    return key, grant


def test_proposal_preserves_exact_utf8_newlines(fixture, monkeypatch):
    content = "first\nsecond\r\nthird\r末行"
    probe = PROBE.replace(
        "v={'request_id'",
        "files=[{'path':n,'content':" + repr(content) + "} for n in r['write_allowlist']]\nv={'request_id'",
        1,
    )
    monkeypatch.setattr(sys.modules[__name__], "PROBE", probe)
    profile, root, registry = prepare(fixture, monkeypatch)
    key, _ = admit(fixture, profile, root, registry, "a")
    reserve(fixture, key)
    w, actor, *_ = fixture
    result = w.execute(actor, key)
    assert result["state"] == "produced"
    assert w.worker.process_closed(json.loads(w.status(actor, key)["task"]), key)
    expected = content.encode("utf-8")
    assert (w.worker.root / key / "work/a/output").read_bytes() == expected
    assert result["intake"]["inputs"]["a"]["edits"]["output"] == hashlib.sha256(expected).hexdigest()


def test_complete_parallel_native_chain(fixture, monkeypatch):
    w, actor, *_ = fixture
    p, root, registry = prepare(fixture, monkeypatch)
    w.principals = lambda a, i, role: {
        "producer": actor,
        "integrator": actor,
        "checker": actor,
        "reviewer": "reviewer",
        "publisher": "publisher",
    }[role]
    keys = [admit(fixture, p, root, registry, m, joint=True)[0] for m in "ab"]
    for key in keys:
        reserve(fixture, key)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda key: w.execute(actor, key), keys))
    for key, result in zip(keys, results):
        assert result["state"] == "produced", (w.worker.root / key / "process.log").read_text(encoding="utf-8")
        assert w.worker.process_closed(json.loads(w.status(actor, key)["task"]), key)
        assert json.loads(w.status(actor, key)["terminal"])["usage"] is None
    from native_candidates import NativeCandidates
    from native_integration import NativeIntegration

    spec = dict(
        tasks=keys,
        product="joint",
        channel="stable",
        base={m: fixture[4][m] for m in "ab"},
        expected=None,
        checks=["check"],
        request_id="native-model-producer-20261118",
        issue_url="https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1486",
    )
    integration = NativeIntegration(w, NativeCandidates(w.worker.store, lambda *a: True), lambda *a: spec)

    def review(operator, contract, candidate):
        return all(
            w.worker.store.read(fixture[2], m, candidate["modules"][m], "output") == (m + " produced").encode("utf-8")
            for m in "ab"
        )

    w.review_candidate = review
    for key in keys:
        assert integration.check_contribution(actor, key)["state"] == "contribution_checked"
    plan = integration.authorize(actor, "native-joint")
    w.release.configure(
        fixture[2],
        "publisher",
        "joint",
        dict(checks={"check": w.runner.context("check", "0" * 64)}, review_max_age_seconds=3600),
    )
    integration.execute(actor, plan)
    receipt = integration.finish(actor, plan)
    assert integration.finish(actor, plan) == receipt
    assert w.domain.sync_progress(fixture[3]["id"], actor=actor)["percent"] == 100
    for key in keys:
        assert w.execute(actor, key)["state"] == "accepted"


def test_failed_usage_unknown_no_replay(fixture, monkeypatch):
    w, actor, *_ = fixture
    p, root, registry = prepare(fixture, monkeypatch)
    key, g = admit(fixture, p, root, registry, "a", "unknown")
    reserve(fixture, key)
    result = w.execute(actor, key)
    assert result["state"] != "produced"
    state = Path(g["payload"]["state_dir"])
    with runner.connect(state) as db:
        events = runner.events(db, runner.jid_for(g["payload"]["task"]))
    end = next(e for e in events if e["kind"] == "call_end")["data"]
    assert end["protocol_evidence"]["usage"]["raw"]["last"]["outputTokens"] == 3
    with pytest.raises(ValueError, match="reconciliation"):
        runner.run(g, root, state)
    with runner.connect(state) as db:
        assert sum(e["kind"] == "call_start" for e in runner.events(db, runner.jid_for(g["payload"]["task"]))) == 1


@pytest.mark.parametrize(
    "case",
    [
        "old-runtime",
        "stale-installation",
        "stale-evaluation",
        "token-limit",
        "production-probe",
        "directory-reset",
        "registry-rebind",
        "authority-key",
    ],
)
def test_admission_boundaries(fixture, monkeypatch, case):
    import copy

    w, actor, *_ = fixture
    p, root, registry = prepare(fixture, monkeypatch)
    key, g = admit(fixture, p, root, registry, "a")
    bad = copy.deepcopy(g)
    if case == "old-runtime":
        bad["payload"]["runtime_sha256"] = "0" * 64
    elif case == "stale-installation":
        bad["payload"]["profiles"][0]["installation_digest"] = "0" * 64
    elif case == "stale-evaluation":
        bad["payload"]["profiles"][0]["evaluation"]["profile_digest"] = "0" * 64
    elif case == "token-limit":
        bad["payload"]["limits"]["max_output_tokens"] = 512
    elif case == "production-probe":
        bad["payload"]["task"]["validation_only"] = False
    elif case == "directory-reset":
        bad["payload"]["state_dir"] = str(fixture[-1] / "reset")
    elif case == "registry-rebind":
        bad["payload"]["expires_at"] += 10
    elif case == "authority-key":
        bad["payload"]["profiles"][0]["native_installation"]["env"]["GONGGONG_HOST_KEY"] = os.environ[
            "GONGGONG_HOST_KEY"
        ]
    bad["signature"] = runner.signature(bad["payload"])
    with pytest.raises(ValueError):
        if case == "directory-reset":
            runner.run(bad, root, Path(bad["payload"]["state_dir"]))
        else:
            producer.register(registry, key, bad, root)


@pytest.mark.parametrize("paths", [["../escape"], ["a/output", "a/missing/output"]])
def test_escape_and_partial_apply_never_accept(fixture, monkeypatch, paths):
    w, actor, *_ = fixture
    p, root, registry = prepare(fixture, monkeypatch)
    key, g = admit(fixture, p, root, registry, "a")
    # A second host-owned registry is used only by this isolated adversarial
    # fixture; the production register API deliberately forbids rebinding.
    new = fixture[-1] / "adversarial"
    new.mkdir()
    inp = g["payload"]["task"]["input"]
    inp["native_request"]["write_allowlist"] = paths
    inp["native_binding"]["write_allowlist"] = paths
    g["signature"] = runner.signature(g["payload"])
    producer.register(new, key, g, root)
    # Keep the originally authorized worker installation: replace registry
    # bytes in the fixture to model an independently signed hostile mandate.
    (registry / (key + ".json")).write_bytes((new / (key + ".json")).read_bytes())
    reserve(fixture, key)
    result = w.execute(actor, key)
    assert result["state"] == "failed"
    terminal = json.loads(w.status(actor, key)["terminal"])
    assert terminal.get("candidate") is None
    assert not (w.worker.root / key / "escape").exists()


def test_central_reservations_do_not_reset_or_share_task_lock(tmp_path):
    from task_budget import reservation

    central = dict(state_dir=str(tmp_path / "budget"), max_calls=2, max_concurrent=2, authority_ref="admitted")

    def grant(name):
        t = dict(id=name, tenant_id="tenant")
        return {
            "payload": dict(
                task=t,
                central_budget=central,
                limits={"max_calls": 1},
                profiles=[{"protocol": "codex-native-proposal"}],
                state_dir=str(Path(central["state_dir"]) / "tasks" / runner.jid_for(t)),
            )
        }

    a, b, c = map(grant, "abc")
    with reservation(a, Path(a["payload"]["state_dir"])):
        with reservation(b, Path(b["payload"]["state_dir"])):
            with pytest.raises(ValueError):
                with reservation(c, Path(c["payload"]["state_dir"])):
                    pass
    with pytest.raises(ValueError, match="budget exhausted"):
        with reservation(c, Path(c["payload"]["state_dir"])):
            pass
    a["payload"]["limits"]["max_calls"] = 2
    with pytest.raises(ValueError, match="reset"):
        with reservation(a, Path(a["payload"]["state_dir"])):
            pass


def test_context_overflow_never_starts_process(tmp_path, monkeypatch):
    import native_proposal_adapter as adapter
    from native_proposal_adapter import call_native

    p, _ = installed(tmp_path, monkeypatch)
    host = host_for(p)
    host.helper.run_owned = lambda *a, **kw: pytest.fail("oversized request dispatched")
    monkeypatch.setattr(adapter, "validate_profile", lambda profile: host)
    request = dict(
        request_id="overflow", task="fixed", context="x" * 131072, write_allowlist=["a/output"], acceptance="pass"
    )
    with pytest.raises(ValueError, match="too large"):
        call_native(
            p,
            [
                dict(role="system", content="governance"),
                dict(role="user", content=runner.canonical({"input": {"native_request": request}})),
            ],
            None,
        )
