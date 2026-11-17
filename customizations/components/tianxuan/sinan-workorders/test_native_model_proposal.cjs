'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {propose, UsageObserver, requestSnapshot, digest} = require('./native_model_proposal.cjs');
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
        rpc.notify({method: 'item/completed', params: {threadId: 'thread-1', turnId: 'turn-1', item: {type: 'agentMessage', text: malformed ? '{}' : JSON.stringify(p)}}});
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
