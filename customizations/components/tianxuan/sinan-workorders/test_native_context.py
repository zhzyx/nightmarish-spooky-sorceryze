"""Deterministic real process/Subscription probes. No model or provider calls."""

# pytest imports the fixture for registration and injects parameters by name.
# ruff: noqa: F811
import base64
import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path

import pytest
from native_context import NativeContext
from native_model_host import NativeModelHost
from native_store import NativeStore
from test_native_workflow import fixture  # noqa: F401

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "customizations/components/tianxuan/duobao"))
sys.path.insert(0, str(ROOT / "customizations/platforms/ai-access/host-http/runtime"))

NODE = os.environ.get("NATIVE_TEST_NODE") or shutil.which("node")


@pytest.fixture
def context(tmp_path):
    store = NativeStore(tmp_path / "objects.sqlite")
    r = store.submit(
        "tenant",
        "actor",
        "first",
        [
            {
                "module": "code",
                "base": None,
                "reads": None,
                "edits": {"large.txt": ("中" * 30000).encode(), "empty": b""},
                "dependencies": {},
            }
        ],
    )["revisions"]["code"]
    binding = dict(
        execution="a" * 64,
        tenant="tenant",
        actor="actor",
        producer="producer",
        source_digest="source",
        installation_digest="installed",
        selected={"code": r},
        limits=dict(response_bytes=16384, chunk_bytes=8192, total_bytes=8388608, max_reads=20),
    )
    permission = {"active": True}
    resolver = NativeContext(store, lambda b, m, r, op: permission["active"], binding, tmp_path / "ledger.sqlite")
    return resolver, permission


def read_args(c, name="large.txt", length=2):
    revision = c.binding["selected"]["code"]
    return dict(
        op="read",
        module="code",
        revision=revision,
        name=name,
        object_digest=c.store.revision("tenant", "code", revision)["objects"].get(name),
        offset=0,
        length=length,
        cursor=None,
        known_receipt=None,
    )


def test_ranges_namespace_absence_and_resume(context):
    c, _ = context
    m = c.resolve(dict(op="manifest", cursor=None))
    assert m["dependency_kind"] == "namespace" and m["complete"]
    args = read_args(c)
    first = c.resolve(args)
    assert base64.b64decode(first["content"]) == "中".encode()[:2]
    second = c.resolve({**args, "cursor": first["next_cursor"]})
    assert second["range"]["offset"] == 2 and not second["complete"]
    missing = c.resolve(read_args(c, "missing"))
    assert missing["dependency_kind"] == "absence" and missing["content"]["exists"] is False
    empty = c.resolve(read_args(c, "empty"))
    assert empty["complete"] and empty["range"]["returned_bytes"] == 0
    restored = NativeContext(c.store, c.authorize, c.binding, c.path)
    assert restored.receipt() == c.receipt() and c.receipt()["reads"] is None


@pytest.mark.parametrize("mutation", ["tenant", "range", "hash", "path", "cursor", "revoke"])
def test_fail_closed(context, mutation):
    c, permission = context
    args = read_args(c)
    if mutation == "tenant":
        with pytest.raises(ValueError):
            NativeContext(c.store, c.authorize, {**c.binding, "tenant": "other"}, c.path)
        return
    if mutation == "range":
        args["length"] = 8193
    if mutation == "hash":
        args["object_digest"] = "b" * 64
    if mutation == "path":
        args["name"] = "../escape"
    if mutation == "cursor":
        args["cursor"] = base64.urlsafe_b64encode(b"{}").decode()
    if mutation == "revoke":
        permission["active"] = False
    with pytest.raises((ValueError, KeyError)):
        c.resolve(args)
    assert not any(e["kind"] == "resolved" for e in c.events())


def test_unknown_read_is_not_replayed(context):
    c, _ = context
    c.emit("started", {"request_id": "crashed"})
    with pytest.raises(ValueError, match="Unknown"):
        c.resolve(dict(op="manifest", cursor=None))


FIXTURE = r"""
const fs=require('node:fs');
const {contextSession,digest}=require(HELPER);
const {Subscription}=require(SUBSCRIPTION);
let data=''; process.stdin.on('data',c=>data+=c); process.stdin.on('end',async()=>{
 const p=JSON.parse(data); let turns=0, threads=0;
 const rpc={close(){},async call(method,params){
  if(method==='thread/start'){threads++;return {thread:{id:'t',ephemeral:true},approvalPolicy:'never',modelProvider:'openai',model:p.installed.model,sandbox:{type:'readOnly',networkAccess:false}};}
  if(method!=='turn/start')throw Error('unexpected');
  // Assert the provider subset on the exact RPC schema, independently of wrapper preflight.
  const assert=require('node:assert/strict');
  assert.equal(params.outputSchema.type,'object'); assert.equal(params.outputSchema.anyOf,undefined);
  function providerSubset(node){
    if(!node || typeof node!=='object')return;
    if(node.type==='object'){
      assert.equal(node.additionalProperties,false);
      assert.deepEqual([...node.required].sort(),Object.keys(node.properties).sort());
    }
    for(const value of Object.values(node)){
      if(Array.isArray(value))value.forEach(providerSubset); else providerSubset(value);
    }
  }
  providerSubset(params.outputSchema);
  turns++; const id='turn-'+turns;
  if(turns===2 && p.installed.env.PROBE_MODE==='crash')process.exit(7);
  if(turns===2 && p.installed.env.PROBE_MODE==='flood')process.stdout.write('x'.repeat(600000));
  if(turns===2 && p.installed.env.PROBE_MODE==='late-stdout')process.stdout.write('x'.repeat(256));
  if(turns===2 && p.installed.env.PROBE_MODE==='late-stderr')process.stderr.write('x'.repeat(256));
  const parsed=JSON.parse(params.input[0].text);
  if(turns>1 && (parsed.messages.length!==2 || parsed.messages[0].role!=='assistant'))throw Error('history replay');
  const parsedContext=p.request.context.startsWith('{')?JSON.parse(p.request.context):null;
  const multi=parsedContext?.pair?parsedContext:null;
  let arguments={op:'manifest',cursor:null};
  if(multi && turns===2){const manifest=JSON.parse(parsed.messages.at(-1).content).tool_result;
    const {byte_length,encoding_hint,...source}=manifest.content.find(e=>e.name==='large.txt');arguments={op:'read',...source,offset:0,length:2,cursor:null,known_receipt:null};}
  if(multi && turns===3){const previous=JSON.parse(parsed.messages.at(-1).content).tool_result;
    const {tenant,...source}=previous.source;arguments={op:'read',...source,offset:0,length:2,cursor:previous.next_cursor,known_receipt:null};}
  if(multi && turns===4)arguments={op:'delta',...multi.pair,cursor:null};
  const action=turns<(multi?5:3)?{action:'tool',name:'native_context',arguments,value:null}:
   {action:'final',name:null,arguments:null,value:{request_id:p.request.request_id,input_digest:digest(p.request),summary:'done',files:p.request.write_allowlist.map(path=>({path,content:'context-consumed'}))}};
  const counters={cachedInputTokens:0,inputTokens:2,outputTokens:1,reasoningOutputTokens:0,totalTokens:3};
  rpc.notify({method:'thread/tokenUsage/updated',params:{threadId:'t',turnId:id,tokenUsage:{last:counters,total:{...counters,totalTokens:turns*3}}}});
  rpc.notify({method:'item/completed',params:{threadId:'t',turnId:id,item:{id:'m'+turns,type:'agentMessage',text:p.installed.env.PROBE_MODE==='malformed'?'private-invalid-json':p.installed.env.PROBE_MODE==='empty'?'':JSON.stringify(action)}}});
  rpc.notify({method:'turn/completed',params:{threadId:'t',turn:{id,status:p.installed.env.PROBE_MODE==='failed'?'failed':'completed',error:{message:'PRIVATE_ERROR_DO_NOT_RETAIN'}}}});
  return {turn:{id}};
 }};
 const session=new Subscription(rpc,'unused');session.account='test';session.identity=async()=> 'test';
 try {await contextSession(p,async()=>session);fs.writeFileSync(process.env.PROBE_COUNTS,JSON.stringify({turns,threads}));}
 catch(e){process.stderr.write(String(e));process.exitCode=2;}
});
"""


def make_host(tmp_path, mode="success"):
    if not NODE:
        pytest.skip("Installed Node required for real transport probe")
    probe = tmp_path / "probe.cjs"
    probe.write_text(
        FIXTURE.replace("HELPER", json.dumps(str(Path(__file__).with_name("native_model_proposal.cjs")))).replace(
            "SUBSCRIPTION", json.dumps(str(ROOT / "tools/codex_cli/subscription_session.js"))
        ),
        encoding="utf8",
    )
    profile = dict(
        node=str(Path(NODE).resolve()),
        entry=str(probe),
        python=sys.executable,
        model="test",
        reasoning_effort=None,
        env={
            **{k: v for k, v in os.environ.items() if k.upper() != "GONGGONG_HOST_KEY"},
            "PROBE_COUNTS": str(tmp_path / "counts.json"),
            "PROBE_MODE": mode,
        },
        timeout=10,
    )
    host = NativeModelHost(profile, lambda p: p == profile, ROOT / "tools/ainative/owned_process.py")
    configured = host.configuration()
    host.wrapper = probe
    host.configuration = lambda: configured
    return host


def exit_between_mailbox_check_and_poll(session, final_turn, monkeypatch):
    request = session.mailbox / f"{final_turn}.input.json"
    staged = request.with_suffix(".tmp")
    response = session.mailbox / f"{final_turn}.output.json"
    replace, exists = Path.replace, Path.exists

    def delay_request(path, target):
        if path == staged and target == request:
            return target
        return replace(path, target)

    def observe(path):
        present = exists(path)
        if path == response and not present and exists(staged):
            # Release the real final turn only after capturing the negative mailbox read.
            replace(staged, request)
            while session.command.poll() is None:
                assert time.monotonic() < session.deadline
                time.sleep(0.005)
            assert session.command.poll() == 0 and exists(response)
        return present

    monkeypatch.setattr(Path, "replace", delay_request)
    monkeypatch.setattr(Path, "exists", observe)


@pytest.mark.parametrize("delay_request", [False, True], ids=["normal", "exit-between-checks"])
def test_real_process_reuses_subscription_and_physically_closes(context, tmp_path, monkeypatch, delay_request):
    c, _ = context
    before = c.binding["selected"]["code"]
    after = c.store.submit(
        "tenant", "actor", "delta", [{"module": "code", "base": before, "reads": None, "edits": {"added": b"change"}}]
    )["revisions"]["code"]
    pair = dict(module="code", before=before, after=after)
    c = NativeContext(c.store, c.authorize, {**c.binding, "allowed_delta_pairs": [pair]}, tmp_path / "multi.sqlite")
    host = make_host(tmp_path)
    request = dict(
        request_id=c.binding["execution"],
        task="fixed",
        context=json.dumps({"pair": pair}),
        write_allowlist=[],
        acceptance="fixed",
    )
    session = host.context_session(request, c, 6)
    if delay_request:
        exit_between_mailbox_check_and_poll(session, 5, monkeypatch)
    messages = [{"role": "system", "content": "fixed host"}, {"role": "user", "content": "fixed task"}]
    receipts = []
    try:
        for index in range(5):
            c.delivery(index + 1, messages, "included_in_call")
            receipt = session.turn(messages)
            receipts.append(receipt)
            c.delivery(index + 1, messages, "transport_received")
            if receipt["status"] == "tool_requested":
                result = c.resolve(receipt["action"]["arguments"], index + 1)
                messages.extend([
                    {"role": "assistant", "content": json.dumps(receipt["action"], separators=(",", ":"))},
                    {"role": "user", "content": json.dumps({"tool_result": result})},
                ])
        assert receipts[-1]["process_tree_closed"]
        assert [r["mode"] for r in receipts] == ["bootstrap"] + ["incremental"] * 4
        assert all(r["inputTextBytes"] > 0 for r in receipts)
        assert [r["usage"]["raw"]["total"]["totalTokens"] for r in receipts] == [3, 6, 9, 12, 15]
    finally:
        session.close()
    assert json.loads((tmp_path / "counts.json").read_text()) == {"turns": 5, "threads": 1}
    assert c.events()[-1]["kind"] == "process_closed"
    assert c.receipt()["terminal"] == "final"


def test_authority_revoked_before_second_model_turn(context, tmp_path):
    c, permission = context
    host = make_host(tmp_path)
    request = dict(
        request_id=c.binding["execution"], task="fixed", context="fixed", write_allowlist=[], acceptance="fixed"
    )
    session = host.context_session(request, c, 4)
    try:
        session.turn([{"role": "user", "content": "first"}])
        permission["active"] = False
        with pytest.raises(ValueError, match="authority"):
            session.turn([{"role": "user", "content": "second"}])
    finally:
        session.close()
    assert session.command.process.returncode is not None


def test_actual_runner_loop_and_no_unknown_replay(context, tmp_path, monkeypatch):
    import hashlib
    import time

    import native_proposal_adapter as adapter
    import runner
    from test_native_model_producer import SCHEMA, framework

    c, _ = context
    host = make_host(tmp_path)
    monkeypatch.setenv("GONGGONG_HOST_KEY", "context-isolated-authority-key-1501")
    monkeypatch.setenv("PATH", str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("PYTHONUTF8", "1")
    monkeypatch.setattr(adapter, "host_for", lambda p: host)
    root = framework(tmp_path)
    profile = dict(
        id="probe",
        protocol="codex-native-proposal",
        model="test",
        native_installation=host.installed,
        installation_digest=host.configuration()[1],
        timeout_seconds=10,
        max_context_bytes=1000000,
        output_token_limit="unsupported",
        response_bytes=524288,
    )
    evaluation = dict(profile_digest=runner.digest(profile), scope="synthetic", passed_task_types=["native"])
    evidence = tmp_path / "evaluation.json"
    evidence.write_text(runner.canonical(evaluation), encoding="utf8")
    profile["evaluation"] = {
        **evaluation,
        "evidence_ref": str(evidence),
        "evidence_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
    }
    request = dict(
        request_id=c.binding["execution"], task="fixed", context="fixed", write_allowlist=[], acceptance="fixed"
    )
    task = dict(
        id=c.binding["execution"],
        tenant_id="tenant",
        project_id="test",
        agent_id="yanshi",
        outcome="context test",
        authority_ref="synthetic",
        retention="test",
        mode="autonomous",
        validation_only=True,
        work_items=[dict(id="1501", kind="feature", relation="tests", certainty="confirmed")],
        input={"native_request": request},
        steps=[
            dict(
                id="proposal",
                kind="native",
                instruction="read context",
                output="json",
                schema=SCHEMA,
                tools=["native_context"],
            )
        ],
    )
    central = dict(state_dir=str(tmp_path / "budgets"), max_calls=4, max_concurrent=1, authority_ref="synthetic")
    state = Path(central["state_dir"]) / "tasks" / runner.jid_for(task)
    payload = dict(
        task=task,
        profiles=[profile],
        limits=dict(max_calls=4, max_output_tokens=None, output_token_limit="unsupported"),
        central_budget=central,
        state_dir=str(state),
        runtime_sha256=runner.runtime_digest(),
        framework_sha256=hashlib.sha256((root / "framework-manifest.json").read_bytes()).hexdigest(),
        authority_ref="synthetic",
        expires_at=time.time() + 600,
    )
    grant = dict(payload=payload, signature=runner.signature(payload))
    result = runner.run(grant, root, state, context_resolver=c)
    assert result["status"] == "completed" and result["result"]["calls"] == 3
    assert json.loads((tmp_path / "counts.json").read_text()) == {"turns": 3, "threads": 1}
    assert sum(e["kind"] == "transport_received" for e in c.events()) == 3
    assert sum(e["kind"] == "resolved" for e in c.events()) == 2
    assert runner.run(grant, root, state, context_resolver=c)["replayed"] is True
    assert json.loads((tmp_path / "counts.json").read_text())["turns"] == 3


def test_delta_fixed_pairs_and_cumulative_budget(context, tmp_path):
    c, _ = context
    before = c.binding["selected"]["code"]
    after = c.store.submit(
        "tenant",
        "actor",
        "next",
        [{"module": "code", "base": before, "reads": None, "edits": {"empty": None, "new": b"new"}}],
    )["revisions"]["code"]
    pair = dict(module="code", before=before, after=after)
    binding = {
        **c.binding,
        "selected": {"code": after},
        "allowed_delta_pairs": [pair],
        "limits": {**c.limit, "max_reads": 1},
    }
    c = NativeContext(c.store, c.authorize, binding, tmp_path / "delta.sqlite")
    result = c.resolve(dict(op="delta", **pair, cursor=None))
    assert result["dependency_kind"] == "revision_metadata"
    assert [e["name"] for e in result["content"]] == ["empty", "new"]
    restored = NativeContext(c.store, c.authorize, binding, c.path)
    with pytest.raises(ValueError, match="budget"):
        restored.resolve(dict(op="delta", **pair, cursor=None))


@pytest.mark.parametrize("mode", ["crash", "flood", "late-stdout", "late-stderr"])
def test_real_process_unknown_turn_closes_without_replay(context, tmp_path, mode, monkeypatch):
    c, _ = context
    host = make_host(tmp_path, mode)
    release_reader = threading.Event()
    if mode.startswith("late-"):
        # Keep all 256 bytes in the real pipe until the host observes the mailbox.
        original_drain = host.helper.OwnedCommand._drain

        def delayed_drain(command, channel):
            release_reader.wait()
            original_drain(command, channel)

        monkeypatch.setattr(host.helper.OwnedCommand, "_drain", delayed_drain)
    session = host.context_session(
        dict(request_id=c.binding["execution"], task="fixed", context="fixed", write_allowlist=[], acceptance="fixed"),
        c,
        4,
    )
    messages = [{"role": "user", "content": "first"}]
    try:
        receipt = session.turn(messages)
        command = session.command
        if mode.startswith("late-"):
            for channel in command.channels:
                channel["remaining"] = 128
        messages.extend([
            {"role": "assistant", "content": json.dumps(receipt["action"], separators=(",", ":"))},
            {"role": "user", "content": "result"},
        ])
        with pytest.raises(ValueError):
            session.turn(messages)
        assert session.command is command and session.sequence == 2
        assert [e["data"]["sequence"] for e in c.events() if e["kind"] == "model_receipt"] == [1]
    finally:
        release_reader.set()
        session.close()
    assert session.command.process.returncode is not None
    assert c.receipt()["terminal"] == "incomplete"
    with pytest.raises(ValueError, match="cannot restart"):
        host.context_session(session.request, c, 4)


def test_real_domain_revocation_before_response(fixture, tmp_path):
    w, owner, tenant, req, initial, _ = fixture
    invite = w.domain.create_invite(owner, "context-reader@example.invalid", "editor")
    reader = w.domain.accept_invite(invite["code"], "password")["user_id"]

    def authority(binding, module, revision, operation):
        w.domain.get_doc_shared(reader, req["id"])
        return w.domain.actor_context(reader)["tenant"] == tenant and module == "a" and revision == initial["a"]

    binding = dict(
        execution="a" * 64,
        tenant=tenant,
        actor=reader,
        producer=reader,
        source_digest="source",
        installation_digest="installed",
        selected={"a": initial["a"]},
        limits=dict(response_bytes=16384, chunk_bytes=8192, total_bytes=8388608, max_reads=20),
    )
    c = NativeContext(w.worker.store, authority, binding, tmp_path / "authority.sqlite")
    assert c.resolve(dict(op="manifest", cursor=None))["complete"]
    original = c.storage().read_range

    def revoke_after_read(*args):
        data = original(*args)
        w.domain.set_visibility(owner, req["id"], "private")
        return data

    c.storage().read_range = revoke_after_read
    state = c.store.revision(tenant, "a", initial["a"])
    with pytest.raises(Exception):
        c.resolve(
            dict(
                op="read",
                module="a",
                revision=initial["a"],
                name="output",
                object_digest=state["objects"]["output"],
                offset=0,
                length=7,
                cursor=None,
                known_receipt=None,
            )
        )
    assert not any(e["kind"] == "resolved" and e["data"]["dependency_kind"] == "object" for e in c.events())


def test_real_worker_producer_context_pipeline(fixture, monkeypatch, tmp_path):
    import hashlib

    import native_model_producer as producer
    import native_proposal_adapter as adapter
    import runner
    from test_native_model_producer import admit, prepare
    from test_native_workflow import reserve

    w, actor, tenant, req, _, _ = fixture
    profile, root, old_registry = prepare(fixture, monkeypatch)
    host = make_host(tmp_path)
    profile.update(
        native_installation=host.installed,
        validation_probe=str(host.wrapper),
        validation_probe_sha256=hashlib.sha256(host.wrapper.read_bytes()).hexdigest(),
        model="test",
    )
    profile["installation_digest"] = adapter.host_for(profile).configuration()[1]
    evidence = dict(
        profile_digest=runner.digest({k: v for k, v in profile.items() if k != "evaluation"}),
        scope="synthetic",
        passed_task_types=["native"],
    )
    evidence_path = tmp_path / "context-evaluation.json"
    evidence_path.write_text(runner.canonical(evidence), encoding="utf8")
    profile["evaluation"] = {
        **evidence,
        "evidence_ref": str(evidence_path),
        "evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
    }
    registry = tmp_path / "context-registry"
    registry.mkdir()
    launch = tmp_path / "context-launch.py"
    launch.write_text(
        "\n".join([
            "import sys",
            "from pathlib import Path",
            "sys.path.insert(0, " + repr(str(Path(producer.__file__).parent)) + ")",
            "sys.path.insert(0, " + repr(str(Path(sys.modules[type(w.domain).__module__].__file__).parent)) + ")",
            "import native_model_producer as producer",
            "from native_context import NativeContext",
            "from native_store import NativeStore",
            "from tianxuan_core import Tianxuan",
            "store = NativeStore(" + repr(str(w.worker.store.database)) + ")",
            "domain = Tianxuan(" + repr(str(tmp_path / "domain.sqlite")) + ")",
            "def factory(binding, execution, workspace):",
            "    fixed = binding['installed_context']['binding']",
            "    def authority(b, module, revision, operation):",
            "        domain.get_doc_shared(" + repr(actor) + ", " + repr(req["id"]) + ")",
            "        return domain.actor_context("
            + repr(actor)
            + ")['tenant'] == b['tenant'] and b['selected'].get(module) == revision",
            "    return NativeContext(store, authority, fixed, " + repr(str(tmp_path / "pipeline.sqlite")) + ")",
            "producer.launch(" + repr(str(registry)) + ", context_factory=factory)",
        ]),
        encoding="utf8",
    )
    w.worker.profiles["local"]["argv"] = [sys.executable, "-B", "-X", "utf8", str(launch)]
    from native_observations import OBSERVATION_PROTOCOL

    w.worker.profiles["local"]["observation_protocol"] = OBSERVATION_PROTOCOL
    key, grant = admit(fixture, profile, root, old_registry, "a")
    contract = json.loads(w.status(actor, key)["task"])
    binding = dict(
        execution=key,
        tenant=tenant,
        actor=actor,
        producer=contract["producer"],
        source_digest=runner.digest(contract["source"]),
        installation_digest=profile["installation_digest"],
        selected=contract["selected"],
        limits=dict(response_bytes=16384, chunk_bytes=8192, total_bytes=8388608, max_reads=20),
    )
    inputs = producer.prepare_context_inputs(
        contract,
        key,
        w.worker.root / key / "work",
        {"selected": contract["selected"]},
        ["a/output"],
        "pass",
        {"binding": binding},
        materialized_files=producer.snapshot(tmp_path / ("input-" + key), large=True),
    )
    payload = grant["payload"]
    payload["task"].update(mode="autonomous", input=inputs)
    payload["task"]["steps"][0]["tools"] = ["native_context"]
    payload["limits"]["max_calls"] = 4
    grant["signature"] = runner.signature(payload)
    producer.register(registry, key, grant, root)
    w.worker.context_receipt_reader = lambda task, execution: NativeContext(
        w.worker.store, lambda *args: False, binding, tmp_path / "pipeline.sqlite"
    ).receipt()
    reserve(fixture, key)
    result = w.execute(actor, key)
    assert result["state"] == "produced", (w.worker.root / key / "process.log").read_text(encoding="utf8")
    assert result["context_receipt"]["terminal"] == "final"
    assert result["context_receipt"]["reads"] is None
    assert w.worker.store.read(tenant, "a", result["modules"]["a"], "output") == b"context-consumed"
    assert json.loads((tmp_path / "counts.json").read_text()) == {"threads": 1, "turns": 3}
    calls = result["model_calls"]
    assert [(c["call"], c["source"], c["usage"]["last"]["totalTokens"]) for c in calls] == [
        (1, "codex-cli", 3),
        (2, "codex-cli", 3),
        (3, "codex-cli", 3),
    ]
    assert [c["usage"]["total"]["totalTokens"] for c in calls] == [3, 6, 9]
    assert result["usage"] == calls[-1]["usage"]
    assert w.worker.reconcile(contract, key)["model_calls"] == calls


@pytest.mark.parametrize("received", [[2], [1, 3]])
def test_worker_preserves_received_call_numbers_after_unknown(fixture, received):
    from native_observations import OBSERVATION_PROTOCOL, valid_producer_calls
    from test_native_workflow import reserve, task

    workflow, actor, *_ = fixture
    calls = [
        dict(call=n, source="codex-cli", requested_model="selected", provider_model=None, usage=None) for n in received
    ]
    for invalid in ([0], [101], [1, 1], [3, 1], [True]):
        assert not valid_producer_calls([{**calls[0], "call": n} for n in invalid])
    profile = workflow.worker.profiles["local"]
    profile["observation_protocol"] = OBSERVATION_PROTOCOL
    profile["argv"] = [
        sys.executable,
        "-c",
        "import json, os, pathlib, sys;"
        "print(json.dumps(dict(execution=pathlib.Path(os.environ['NATIVE_WORKSPACE']).parent.name,"
        "proposal_applied=True, provider_model=None, usage=None, model_calls=json.loads(sys.argv[1]))))",
        json.dumps(calls),
    ]
    key, _ = task(fixture, "a")
    contract = json.loads(workflow.status(actor, key)["task"])
    reserve(fixture, key)
    produced = workflow.execute(actor, key)
    assert produced["model_calls"] == calls
    assert workflow.worker.reconcile(contract, key)["model_calls"] == calls


def test_effective_context_size_rejected_before_process(context, tmp_path, monkeypatch):
    import native_proposal_adapter as adapter
    from adapters import TransportUnknown

    c, _ = context
    host = make_host(tmp_path)
    monkeypatch.setattr(adapter, "validate_profile", lambda profile: host)
    transport = adapter.ContextTransport(c, 4)
    request = dict(
        request_id=c.binding["execution"], task="fixed", context="fixed", write_allowlist=[], acceptance="fixed"
    )
    messages = [
        {"role": "system", "content": "fixed"},
        {"role": "user", "content": json.dumps({"input": {"native_request": request}})},
    ]
    try:
        with pytest.raises(TransportUnknown):
            transport.call({"max_context_bytes": 64}, messages, None)
        assert transport.session.command is None
        assert not any(e["kind"] == "model_call_start" for e in c.events())
    finally:
        transport.close()


@pytest.mark.parametrize("boundary", ["read", "delta", "history"])
def test_historical_authority_all_boundaries(context, boundary):
    c, _ = context
    old = c.binding["selected"]["code"]
    new = c.store.submit("tenant", "actor", "next", [dict(module="code", base=old, reads=None, edits={"new": b"new"})])[
        "revisions"
    ]["code"]
    pair = dict(module="code", before=old, after=new)
    active = {old: True, new: True}
    c = NativeContext(
        c.store,
        lambda b, m, r, op: active[r],
        {**c.binding, "selected": {"code": new}, "allowed_delta_pairs": [pair]},
        str(Path(c.path).with_name("historical.sqlite")),
    )
    args = {**read_args(c), "revision": old}
    if boundary == "history":
        c.resolve(args)
        active[old] = False
        for op in ("model_turn", "apply_proposal", "tool_response"):
            with pytest.raises(ValueError, match="authority"):
                c.check(op)
        return
    if boundary == "read":
        original = c.storage().read_range

        def changed(*a):
            result = original(*a)
            active[old] = False
            return result

        c.storage().read_range = changed
    else:
        original = c._revision

        def changed(*a):
            result = original(*a)
            if a[-1] == new:
                active[old] = False
            return result

        c._revision = changed
        args = dict(op="delta", cursor=None, **pair)
    with pytest.raises(ValueError, match="authority"):
        c.resolve(args)
    assert not any(e["kind"] == "resolved" for e in c.events())


@pytest.mark.parametrize(
    "mode,reason,terminal",
    [
        ("failed", "terminal_failure", "failed"),
        ("empty", "missing_output", "completed"),
        ("malformed", "proposal_rejection", "completed"),
    ],
)
def test_real_process_bounded_failure_diagnostics(context, tmp_path, mode, reason, terminal):
    c, _ = context
    host = make_host(tmp_path, mode)
    request = dict(
        request_id=c.binding["execution"], task="fixed", context="fixed", write_allowlist=[], acceptance="fixed"
    )
    session = host.context_session(request, c, 3)
    try:
        with pytest.raises(ValueError, match="Unknown model turn; no replay"):
            session.turn([{"role": "user", "content": "fixed"}])
    finally:
        session.close()
    unknown = [e["data"] for e in c.events() if e["kind"] == "model_unknown"]
    assert len(unknown) == 1
    assert unknown[0]["diagnostic"]["reason"] == reason
    assert unknown[0]["diagnostic"]["terminal"] == terminal
    assert "private-invalid-json" not in json.dumps(unknown)
    assert "PRIVATE_ERROR_DO_NOT_RETAIN" not in json.dumps(unknown)
    assert c.events()[-1]["kind"] == "process_closed"
    assert len([e for e in c.events() if e["kind"] == "model_call_start"]) == 1
    with pytest.raises(ValueError, match="cannot restart"):
        host.context_session(request, c, 3)


def test_adapter_preserves_only_safe_diagnostic_from_real_child(context, tmp_path, monkeypatch):
    import native_proposal_adapter as adapter
    from adapters import TransportUnknown

    c, _ = context
    host = make_host(tmp_path, "failed")
    monkeypatch.setattr(adapter, "validate_profile", lambda profile: host)
    transport = adapter.ContextTransport(c, 2)
    request = dict(
        request_id=c.binding["execution"], task="fixed", context="fixed", write_allowlist=[], acceptance="fixed"
    )
    messages = [
        {"role": "system", "content": "fixed"},
        {"role": "user", "content": json.dumps({"input": {"native_request": request}})},
    ]
    try:
        with pytest.raises(TransportUnknown) as caught:
            transport.call({"max_context_bytes": 131072}, messages, None)
        assert caught.value.evidence["diagnostic"]["reason"] == "terminal_failure"
        assert caught.value.evidence["reason"] == "native_context_unavailable"
        assert "PRIVATE_ERROR_DO_NOT_RETAIN" not in json.dumps(caught.value.evidence)
    finally:
        transport.close()
    assert c.events()[-1]["kind"] == "process_closed"
