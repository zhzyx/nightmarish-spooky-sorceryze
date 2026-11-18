'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {propose, UsageObserver, TimingObserver, requestSnapshot, digest} = require('./native_model_proposal.cjs');
const {Subscription} = require('../../../../tools/codex_cli/subscription_session.js');
const request = {request_id: '1480-test', task: 'Propose a text file', context: 'fixed input', write_allowlist: ['result.txt'], acceptance: 'content is hello'};
const installed = {model: 'requested-test', config_digest: 'a'.repeat(64)};
const breakdown = {cachedInputTokens: 2, inputTokens: 5, outputTokens: 3, reasoningOutputTokens: 1, totalTokens: 8};
const raw = {last: breakdown, total: {...breakdown, totalTokens: 80}, modelContextWindow: null};
function usage(value = raw, threadId = 'thread-1', turnId = 'turn-1') { return {method: 'thread/tokenUsage/updated', params: {threadId, turnId, tokenUsage: value}}; }
function fake(events = [], late = [], malformed = false, reject = false, turnStatus = 'completed') {
    let calls = [], closed = false;
    const rpc = {close() { closed = true; }, async call(method, params) {
        calls.push(method);
        if (method === 'thread/start') return {thread: {id: 'thread-1', ephemeral: true}, approvalPolicy: 'never', modelProvider: 'openai', model: 'requested-test', sandbox: {type: 'readOnly', networkAccess: false}};
        if (method !== 'turn/start') throw Error('unexpected call');
        for (const e of events) rpc.notify(e);
        if (reject) throw Error('disconnect');
        const p = {request_id: request.request_id, input_digest: digest(request), summary: 'proposed', files: [{path: 'result.txt', content: 'hello'}]};
        rpc.notify({method: 'item/completed', params: {threadId: 'thread-1', turnId: 'turn-1', item: {id: 'message-1', type: 'agentMessage', text: malformed ? '{}' : JSON.stringify(p)}}});
        rpc.notify({method: 'turn/completed', params: {threadId: 'thread-1', turn: {id: 'turn-1', status: turnStatus}}});
        if (late.length) setTimeout(() => late.forEach(e => rpc.notify(e)), 5);
        return {turn: {id: 'turn-1'}};
    }};
    const session = new Subscription(rpc, 'unused');
    session.account = 'test'; session.identity = async () => 'test';
    return {session, calls, closed: () => closed};
}
test('real Subscription early events retained, strict proposal bound, original notifications work', async () => {
    const f = fake([usage()]);
    const r = await propose(request, installed, async () => f.session);
    assert.equal(r.status, 'proposed'); assert.deepEqual(r.usage.raw, raw);
    assert.equal(r.usage.observed_model, 'requested-test'); assert.equal(r.execution_authority, false);
    assert.deepEqual(f.calls, ['thread/start', 'turn/start']); assert.equal(f.closed(), true);
    assert.equal(r.output_digest, digest(r.proposal));
});
test('late update replaces raw snapshot without summing', async () => {
    const latest = {...raw, last: {...breakdown, totalTokens: 9}};
    const f = fake([usage()], [usage(latest)]);
    const r = await propose(request, installed, async () => f.session);
    assert.deepEqual(r.usage.raw, latest); assert.equal(r.usage.updates, 2);
});
for (const [name, events] of Object.entries({duplicate: [usage(), usage()], wrong_thread: [usage(raw, 'other')], wrong_turn: [usage(raw, 'thread-1', 'other')], negative: [usage({...raw, last: {...breakdown, inputTokens: -1}})], wrong_type: [usage({...raw, total: {...breakdown, totalTokens: '8'}})], overflow: Array.from({length: 33}, () => usage())})) {
    test(name + ' fails usage closed', async () => {
        const f = fake(events); const r = await propose(request, installed, async () => f.session);
        assert.equal(r.usage.raw, null); assert.equal(r.usage.status, 'invalid'); assert.equal(f.calls.length, 2);
    });
}
test('missing usage remains unknown', async () => { const f = fake(); const r = await propose(request, installed, async () => f.session); assert.equal(r.usage.raw, null); assert.equal(r.usage.status, 'unknown'); });
test('unacknowledged turn never binds early usage or replays', async () => {
    const f = fake([usage()], [], false, true); const r = await propose(request, installed, async () => f.session);
    assert.equal(r.status, 'unknown'); assert.equal(r.usage.raw, null); assert.equal(r.usage.turn_id, null);
    assert.equal(r.usage.status, 'unknown'); assert.equal(f.calls.length, 2);
});
for (const kind of ['malformed', 'failed']) test(kind + ' proposal retains independently bound usage without authority', async () => {
    const f = fake([usage()], [], kind === 'malformed', false, kind === 'failed' ? 'failed' : 'completed');
    const r = await propose(request, installed, async () => f.session);
    assert.equal(r.status, 'unknown'); assert.equal(r.proposal, null); assert.equal(r.output_digest, null);
    assert.equal(r.execution_authority, false); assert.equal(r.usage.status, 'observed');
    assert.equal(r.usage.thread_id, 'thread-1'); assert.equal(r.usage.turn_id, 'turn-1');
    assert.deepEqual(r.usage.raw, raw); assert.equal(f.calls.length, 2);
});
test('failed proposal retains invalid usage classification', async () => {
    const f = fake([usage(raw, 'wrong')], [], true); const r = await propose(request, installed, async () => f.session);
    assert.equal(r.status, 'unknown'); assert.equal(r.usage.status, 'invalid'); assert.equal(r.usage.raw, null);
});
test('request configuration injection and duplicate paths rejected before start', async () => {
    for (const r of [{...request, env: {}}, {...request, write_allowlist: ['../escape']}, {...request, write_allowlist: ['a', 'a']}]) assert.throws(() => requestSnapshot(r));
});
test('callback preserved and restored including compaction signal', () => {
    const f = fake(); f.session.thread = 'thread-1'; const previous = f.session.rpc.notify;
    const observer = new UsageObserver(f.session.rpc);
    f.session.rpc.notify({method: 'thread/compacted', params: {threadId: 'thread-1'}});
    assert.equal(f.session.compacted, true); observer.detach(); assert.equal(f.session.rpc.notify, previous);
});
test('context compaction forces existing Subscription to rebuild', async () => {
    const f = fake();
    const input = {model: installed.model, available_tools: [], tool_context: {}, messages: [{role: 'user', content: 'fixed'}]};
    const first = await f.session.turn(input, 'scope', {}, JSON.stringify, () => {});
    assert.equal(first.rebuild, 'new_thread');
    f.session.rpc.notify({method: 'thread/compacted', params: {threadId: 'thread-1'}});
    const second = await f.session.turn(input, 'scope', {}, JSON.stringify, () => {});
    assert.equal(second.rebuild, 'context_compacted');
    assert.deepEqual(f.calls, ['thread/start', 'turn/start', 'thread/start', 'turn/start']);
});
test('strict output rejects wrong digest, duplicate paths, extra authority and outside path', () => {
    const {validateProposal} = require('./native_model_proposal.cjs');
    const valid = {request_id: request.request_id, input_digest: digest(request), summary: 'proposed', files: [{path: 'result.txt', content: 'hello'}]};
    for (const p of [{...valid, input_digest: 'wrong'}, {...valid, files: [...valid.files, ...valid.files]}, {...valid, approved: true}, {...valid, files: [{path: 'outside', content: 'hello'}]}]) assert.throws(() => validateProposal(JSON.stringify(p), request, digest(request)));
});

function timingFixture() {
    let clock = 1000;
    const calls = [], notifications = [];
    const rpc = {notify(packet) { notifications.push(packet); }, async call(method) {
        calls.push(method);
        return method === 'thread/start' ? {thread: {id: 't'}} : {turn: {id: 'u'}};
    }};
    const originalCall = rpc.call, originalNotify = rpc.notify;
    const observer = new TimingObserver(() => clock);
    observer.mark('session_ready'); observer.attach(rpc);
    return {observer, rpc, calls, notifications, originalCall, originalNotify,
        at(n) { clock = 1000 + n; }};
}
const delta = (turnId = 'u', value = 'text') => ({method: 'item/agentMessage/delta', params: {threadId: 't', turnId, delta: value}});
const completed = (status = 'completed') => ({method: 'turn/completed', params: {threadId: 't', turn: {id: 'u', status}}});
const messageCompleted = (id = 'message-1', turnId = 'u') => ({method: 'item/completed', params: {
    threadId: 't', turnId, item: {id, type: 'agentMessage', text: 'private marker'}
}});

test('replayed completed messages do not move last text, including before acknowledgement', async () => {
    for (const early of [false, true]) {
        const f = timingFixture(); await f.rpc.call('thread/start', {});
        const turn = f.rpc.call('turn/start', {threadId: 't'});
        if (!early) await turn;
        f.at(5); f.rpc.notify(messageCompleted('message-1', 'unrelated'));
        f.at(10); f.rpc.notify(messageCompleted());
        f.at(90); f.rpc.notify(messageCompleted());
        if (early) await turn;
        assert.equal(f.observer.value.marks.first_text, 10);
        assert.equal(f.observer.value.marks.last_text, 10);
        f.at(100); f.rpc.notify(completed());
        f.at(110); f.rpc.notify(messageCompleted('late'));
        assert.equal(f.observer.value.marks.last_text, 10);
        assert.equal(f.observer.value.marks.turn_completed, 100);
        assert.equal(JSON.stringify(f.observer.value).includes('private marker'), false);
        assert.equal(f.notifications.length, 5);
        assert.deepEqual(f.calls, ['thread/start', 'turn/start']);
        f.observer.detach(); assert.equal(f.observer.completedItems.size, 0);
        assert.equal(f.rpc.call, f.originalCall); assert.equal(f.rpc.notify, f.originalNotify);
    }
});

test('identical text deltas and distinct completed items remain distinct output', async () => {
    const f = timingFixture(); await f.rpc.call('thread/start', {}); await f.rpc.call('turn/start', {threadId: 't'});
    f.at(10); f.rpc.notify(delta()); f.at(20); f.rpc.notify(delta());
    assert.equal(f.observer.value.marks.last_text, 20);
    f.at(30); f.rpc.notify(messageCompleted('a')); f.at(40); f.rpc.notify(messageCompleted('b'));
    assert.equal(f.observer.value.marks.last_text, 40);
    f.at(50); f.rpc.notify(messageCompleted('a'));
    assert.equal(f.observer.value.marks.last_text, 40); f.observer.detach();
});

test('completed message identities are required and bounded with unknown overflow', async () => {
    const f = timingFixture(); await f.rpc.call('thread/start', {}); await f.rpc.call('turn/start', {threadId: 't'});
    for (const id of [null, '', 'x'.repeat(257)]) f.rpc.notify(messageCompleted(id));
    assert.equal(f.observer.value.marks.first_response, null);
    for (let i = 0; i < 256; i++) f.rpc.notify(messageCompleted(String(i)));
    assert.equal(f.observer.completedItems.size, 256);
    f.rpc.notify(messageCompleted('overflow')); f.rpc.notify(delta()); f.rpc.notify(completed());
    assert.equal(f.observer.completedItems.size, 0);
    for (const name of ['first_response', 'first_text', 'last_text', 'turn_completed']) assert.equal(f.observer.value.marks[name], null);
    f.observer.detach();
});

test('monotonic phase separation and terminal freeze without extra calls', async () => {
    const f = timingFixture();
    f.at(10); const thread = f.rpc.call('thread/start', {}); f.at(110); await thread;
    f.at(120); const turn = f.rpc.call('turn/start', {threadId: 't'}); f.at(130); await turn;
    f.at(200); f.rpc.notify({method: 'item/started', params: {threadId: 't', turnId: 'u', item: {id: 'i', type: 'reasoning'}}});
    f.at(500); f.rpc.notify(delta()); f.at(600); f.rpc.notify(delta('u', 'more'));
    f.at(900); f.rpc.notify(completed());
    f.at(950); f.rpc.notify(completed()); f.rpc.notify(delta());
    f.at(960); f.observer.mark('proposal_validated'); f.at(1000); f.observer.mark('receipt_ready');
    assert.deepEqual(f.observer.value, {version: 1, clock: 'monotonic', marks: {
        session_ready: 0, thread_start_sent: 10, thread_start_received: 110,
        turn_start_sent: 120, turn_start_received: 130, first_response: 200,
        first_text: 500, last_text: 600, turn_completed: 900, proposal_validated: 960, receipt_ready: 1000
    }, rpc: {thread_start_calls: 1, turn_start_calls: 1}});
    assert.deepEqual(f.calls, ['thread/start', 'turn/start']);
    assert.equal(f.notifications.length, 6);
    f.observer.detach(); assert.equal(f.rpc.call, f.originalCall); assert.equal(f.rpc.notify, f.originalNotify);
});

test('early notification timestamps bind only to acknowledged turn', async () => {
    const f = timingFixture(); await f.rpc.call('thread/start', {});
    f.at(10); const turn = f.rpc.call('turn/start', {threadId: 't'});
    f.at(11); f.rpc.notify(delta('unrelated'));
    f.at(20); f.rpc.notify(delta()); f.at(30); f.rpc.notify(completed()); f.at(40); await turn;
    const m = f.observer.value.marks;
    assert.equal(m.first_response, 20); assert.equal(m.first_text, 20);
    assert.equal(m.turn_completed, 30); assert.equal(m.turn_start_received, 40);
    assert.equal(f.observer.early.length, 0); f.observer.detach();
});

test('malformed and unrelated notifications cannot fabricate timing', async () => {
    const f = timingFixture(); await f.rpc.call('thread/start', {}); await f.rpc.call('turn/start', {threadId: 't'});
    for (const packet of [null, {}, {method: 'item/agentMessage/delta'}, delta('other'), delta('u', 42), delta('u', ''),
        {...delta(), id: 1}, {method: 'random', params: delta().params},
        {method: 'turn/completed', params: {threadId: 't', turnId: 'u', turn: {id: 'other', status: 'completed'}}},
        completed('inProgress'), {...delta(), params: {...delta().params, threadId: 'wrong'}},
        {method: 'item/completed', params: {threadId: 't', turnId: 'u', item: {type: 'agentMessage', text: 42}}}]) f.rpc.notify(packet);
    assert.equal(f.observer.value.marks.first_response, null);
    assert.equal(f.observer.value.marks.first_text, null);
    assert.equal(f.observer.value.marks.turn_completed, null); f.observer.detach();
});

test('early overflow discards ambiguous timings without retaining payloads', async () => {
    const f = timingFixture(); await f.rpc.call('thread/start', {});
    const turn = f.rpc.call('turn/start', {threadId: 't'});
    for (let i = 0; i < 257; i++) f.rpc.notify(delta('u', 'sensitive-payload'));
    assert.equal(f.observer.early.length, 0); await turn;
    assert.equal(f.observer.value.marks.first_response, null);
    f.rpc.notify(delta('u', 'late')); f.rpc.notify(completed());
    assert.equal(f.observer.value.marks.first_response, null);
    assert.equal(f.observer.value.marks.first_text, null);
    assert.equal(f.observer.value.marks.last_text, null);
    assert.equal(f.observer.value.marks.turn_completed, null);
    assert.equal(JSON.stringify(f.observer.value).includes('sensitive-payload'), false); f.observer.detach();
});

test('observer preserves original rejection and callback exception', async () => {
    const failure = Error('original');
    const rpc = {call() { throw failure; }, notify() { throw failure; }};
    const observer = new TimingObserver(); observer.attach(rpc);
    await assert.rejects(rpc.call('turn/start', {threadId: 't'}), e => e === failure);
    assert.throws(() => rpc.notify({}), e => e === failure);
    assert.equal(observer.value.marks.turn_start_received, null); observer.detach();
});

test('receipt timing accompanies proposed, failed and unacknowledged results and restores observers', async () => {
    for (const kind of ['proposed', 'failed', 'malformed', 'unacknowledged']) {
        const f = fake([usage()], [], kind === 'malformed', kind === 'unacknowledged', kind === 'failed' ? 'failed' : 'completed');
        const originalCall = f.session.rpc.call, originalNotify = f.session.rpc.notify;
        const r = await propose(request, installed, async () => f.session);
        assert.equal(r.status, kind === 'proposed' ? 'proposed' : 'unknown');
        assert.equal(r.timing.clock, 'monotonic'); assert.equal(r.timing.version, 1);
        assert.deepEqual(r.timing.rpc, {thread_start_calls: 1, turn_start_calls: 1});
        for (const value of Object.values(r.timing.marks)) assert.ok(value === null || Number.isInteger(value) && value >= 0 && value <= 86400000);
        assert.ok(r.timing.marks.receipt_ready >= r.timing.marks.session_ready);
        assert.equal(r.timing.marks.proposal_validated === null, kind !== 'proposed');
        assert.equal(r.timing.marks.turn_completed === null, kind === 'unacknowledged');
        assert.equal(f.closed(), true); assert.equal(f.session.rpc.call, originalCall); assert.equal(f.session.rpc.notify, originalNotify);
    }
});

test('startup failure produces unknown timing with no protocol calls', async () => {
    const r = await propose(request, installed, async () => { throw Error('start failed'); });
    assert.equal(r.status, 'unknown'); assert.equal(r.timing.marks.session_ready, null);
    assert.deepEqual(r.timing.rpc, {thread_start_calls: 0, turn_start_calls: 0});
    assert.ok(Number.isInteger(r.timing.marks.receipt_ready));
});

test('transport timeout after text stays unknown and closes without retry', async () => {
    let calls = 0, closed = 0;
    const rpc = {close() { closed++; this.onclose?.(); }, async call(method) {
        calls++;
        if (method === 'thread/start') return {thread: {id: 'thread-1', ephemeral: true}, approvalPolicy: 'never', modelProvider: 'openai', model: 'requested-test', sandbox: {type: 'readOnly', networkAccess: false}};
        queueMicrotask(() => {
            rpc.notify({method: 'item/agentMessage/delta', params: {threadId: 'thread-1', turnId: 'turn-1', delta: 'partial'}});
            rpc.close(); // Deterministic equivalent of Channel timeout/onclose, no wall-clock wait.
        });
        return {turn: {id: 'turn-1'}};
    }};
    const session = new Subscription(rpc, 'unused'); session.account = 'test'; session.identity = async () => 'test';
    const originalCall = rpc.call, originalNotify = rpc.notify;
    const r = await propose(request, installed, async () => session);
    assert.equal(r.status, 'unknown'); assert.equal(r.proposal, null);
    assert.ok(r.timing.marks.first_text !== null); assert.equal(r.timing.marks.turn_completed, null);
    assert.equal(r.timing.marks.proposal_validated, null); assert.equal(calls, 2); assert.ok(closed >= 1);
    assert.equal(rpc.call, originalCall); assert.equal(rpc.notify, originalNotify);
    assert.equal(session.onTurn, null); assert.equal(rpc.onclose, null);
});

test('out of range monotonic stamps remain unknown', () => {
    const f = timingFixture(); f.at(86400001); f.observer.mark('receipt_ready');
    assert.equal(f.observer.value.marks.receipt_ready, null); f.observer.detach();
});

test('duplicate RPC cannot be misreported as a single request', async () => {
    const f = timingFixture();
    await f.rpc.call('thread/start', {});
    await f.rpc.call('thread/start', {});
    assert.equal(f.calls.length, 2);
    assert.equal(f.observer.value.rpc.thread_start_calls, 2); // Rejected by the host's <=1 bound.
    f.observer.detach();
});


test('wire envelope requires inactive nulls and exact typed operation arguments', () => {
    const {validateAction} = require('./native_model_proposal.cjs');
    const valid = {action:'tool',name:'native_context',arguments:{op:'manifest',cursor:null},value:null};
    const check = x => validateAction(JSON.stringify(x),request,digest(request));
    assert.deepEqual(check(valid),{action:'tool',name:'native_context',arguments:valid.arguments});
    const read={op:'read',module:'code',revision:'r',name:'n',object_digest:'d',offset:0,length:1,cursor:null,known_receipt:null};
    const delta={op:'delta',module:'code',before:'a',after:'b',cursor:null};
    for(const args of [read,delta,{op:'manifest',cursor:'opaque'}]) assert.deepEqual(check({...valid,arguments:args}).arguments,args);
    for(const action of [{...valid,value:{}},{...valid,name:null},{action:'tool',name:'native_context',arguments:valid.arguments},
        {...valid,action:'final'}, {...valid,extra:true}]) assert.throws(()=>check(action));
    for(const args of [{op:'manifest'}, {op:'manifest',cursor:1}, {op:'manifest',cursor:null,module:'inactive'},
        {...read,offset:1.5},{...read,length:0},{...read,known_receipt:'unsupported'}, {...read,name:null},
        {...read,before:'inactive'},{...delta,after:null},{...delta,offset:0}]) assert.throws(()=>check({...valid,arguments:args}));
    const proposal={request_id:request.request_id,input_digest:digest(request),summary:'ok',files:[]};
    assert.deepEqual(check({action:'final',name:null,arguments:null,value:proposal}),{action:'final',value:proposal});
    assert.throws(()=>check({action:'final',name:'native_context',arguments:null,value:proposal}));
});

test('schema preflight rejects incompatible installed schema before startup', async () => {
    const {actionSchema,contextSession} = require('./native_model_proposal.cjs');
    const fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path');
    const mailbox=await fs.mkdtemp(path.join(os.tmpdir(),'schema-preflight-'));
    const binding='b'.repeat(64),messages=[{role:'user',content:'fixed'}];
    let starts=0;
    try {
        await fs.writeFile(path.join(mailbox,'1.input.json'),JSON.stringify({binding,sequence:1,messages,input_digest:digest(messages)}));
        actionSchema.additionalProperties=true;
        await contextSession({request,installed,mailbox,binding,max_calls:1},async()=>{starts++;throw Error('must not start');});
        const receipt=JSON.parse(await fs.readFile(path.join(mailbox,'1.output.json'),'utf8'));
        assert.equal(starts,0); assert.equal(receipt.status,'unknown');
        assert.deepEqual(receipt.diagnostic,{version:1,phase:'schema_preflight',terminal:'unknown',reason:'schema_preflight'});
    } finally {actionSchema.additionalProperties=false;await fs.rm(mailbox,{recursive:true,force:true});}
});

test('bounded diagnosis retains observed terminal or local phase only', async () => {
    for(const [mode,reason] of [['failed','terminal_failure'],['malformed','proposal_rejection'],['reject','unknown']]){
        const f=fake([],[],mode==='malformed',mode==='reject',mode==='failed'?'failed':'completed');
        const r=await propose(request,installed,async()=>f.session);
        assert.equal(r.diagnostic.reason,reason);
        assert.equal(JSON.stringify(r.diagnostic).includes('disconnect'),false);
    }
});
