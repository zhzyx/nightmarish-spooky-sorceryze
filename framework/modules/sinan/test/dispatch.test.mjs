import test from 'node:test';
import assert from 'node:assert/strict';
import {planDispatch, dispatchEvent, conflicts} from '../dispatch.mjs';

function fixture() {
  const requests = ['a', 'b', 'c'].map(ticket => ({ticket, capabilities: ['coding'], reads: [], writes: [`D:/repo/${ticket}`], outcome: ticket, owner: 'owner', acceptance: 'tested', authorityRef: 'mandate', contextRefs: []}));
  const snapshot = {items: requests.map(r => ({key: r.ticket, source: 'source', dispatchCandidate: true})), ready: ['a', 'b', 'c'], sourceSnapshots: [{source: 'source', version: 'v1'}]};
  const environment = {capacity: 2, active: [], catalog: [
    {id: 'reasoner', available: true, targets: ['agent', 'chat'], capabilities: ['coding', 'reasoning'], preference: 2},
    {id: 'worker', available: true, targets: ['agent'], capabilities: ['coding'], preference: 1}
  ]};
  return {requests, snapshot, environment};
}
test('independent tasks use capacity and capability-specific models', () => {
  const f = fixture(); f.requests[1].capabilities.push('reasoning');
  const p = planDispatch(f.snapshot, f.requests, f.environment);
  assert.deepEqual(p.assignments.map(a => a.model.id), ['worker', 'reasoner']);
  assert.equal(p.deferred[0].reason, 'capacity');
});
test('blocked task does not block independent work', () => {
  const f = fixture(); f.snapshot.ready = ['b', 'c'];
  const p = planDispatch(f.snapshot, f.requests, f.environment);
  assert.deepEqual(p.assignments.map(a => a.ticket), ['b', 'c']);
});
test('explicit unavailable model never silently falls back; chat requires authorization', () => {
  const f = fixture(); f.requests[0].model = 'missing'; f.requests[1].target = 'chat';
  let p = planDispatch(f.snapshot, f.requests, f.environment);
  assert.deepEqual(p.deferred.map(d => d.reason), ['required_model_or_capabilities_unavailable', 'chat_creation_not_authorized']);
  f.environment.chatCreationAuthorized = true;
  p = planDispatch(f.snapshot, f.requests, f.environment);
  assert.equal(p.assignments[0].model.id, 'reasoner');
});
test('Windows case and parent paths conflict, sibling prefix and read/read do not', () => {
  const f = fixture(); f.requests[0].writes = ['D:/REPO'];
  assert.equal(planDispatch(f.snapshot, f.requests, f.environment).assignments.length, 1);
  assert.equal(conflicts({reads: ['/x'], writes: []}, {reads: ['/x'], writes: []}), false);
  assert.equal(conflicts({reads: [], writes: ['/xy']}, {reads: ['/x'], writes: []}), false);
  assert.equal(conflicts({reads: [], writes: ['/']}, {reads: ['/x'], writes: []}), true);
});
test('source priority wins over request order and POSIX case stays distinct', () => {
  const f = fixture(); f.requests.reverse(); f.requests[0].writes = ['/Repo']; f.requests[1].writes = ['/repo'];
  f.snapshot.ready = ['c', 'b', 'a'];
  assert.deepEqual(planDispatch(f.snapshot, f.requests, f.environment).assignments.map(a => a.ticket), ['c', 'b']);
});
test('active reservations consume capacity and exclude duplicate tickets', () => {
  const f = fixture(); f.environment.active = [{ticket: 'a', reads: [], writes: ['D:/repo/a']}];
  const p = planDispatch(f.snapshot, f.requests, f.environment);
  assert.deepEqual(p.assignments.map(a => a.ticket), ['b']);
  assert.equal(p.deferred[0].reason, 'already_in_flight');
});
test('malformed resources and duplicate tickets are rejected', () => {
  const f = fixture(); f.requests[0].writes = ['relative'];
  assert.throws(() => planDispatch(f.snapshot, f.requests, f.environment), /absolute/);
  const g = fixture(); g.requests.push(g.requests[0]);
  assert.throws(() => planDispatch(g.snapshot, g.requests, g.environment), /Duplicate/);
});
function adapter(f) {
  const records = [], reservations = new Set();
  return {records, reservations, withLock: fn => fn(), inspect: async () => f,
    revalidate: async () => true,
    reserve: async a => {if (reservations.has(a.key)) return false; reservations.add(a.key); return true;},
    startSource: async () => ({reference: 'start'}),
    launch: async a => ({workerId: a.ticket, reference: 'receipt', model: a.model.id, target: a.target}),
    ack: async () => {}, record: async r => records.push(r)};
}
const event = {type: 'request.created', reference: 'request:1'};
test('two launches are in flight together before either finishes; replay is deduplicated', async () => {
  const f = fixture(), h = adapter(f), launched = [], releases = [];
  h.launch = a => {launched.push(a.ticket); return new Promise(resolve => releases.push(() => resolve({workerId: a.ticket, reference: 'r', model: a.model.id, target: a.target})));};
  const result = dispatchEvent(event, f.requests, h);
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(launched, ['a', 'b']);
  releases.forEach(r => r());
  assert.deepEqual((await result).results.map(r => r.state), ['running', 'running']);
  assert.equal((await dispatchEvent(event, f.requests, h)).results.length, 0);
});
test('unknown launch preserves reservation and independent task succeeds', async () => {
  const f = fixture(), h = adapter(f), launch = h.launch;
  h.launch = a => {if (a.ticket === 'a') throw Error('transport lost'); return launch(a);};
  const result = await dispatchEvent(event, f.requests, h);
  assert.deepEqual(result.results.map(r => r.state), ['reconcile_required', 'running']);
  assert.equal((await dispatchEvent(event, f.requests, h)).results.length, 0);
});
test('revalidation failure is local; completion event fills a released slot', async () => {
  const f = fixture(), h = adapter(f); h.revalidate = async a => a.ticket !== 'a';
  assert.deepEqual((await dispatchEvent(event, f.requests, h)).results.map(r => r.ticket), ['b', 'c']);
  h.reservations.clear(); // Actual completion reconciliation in this test adapter.
  f.snapshot.ready = ['c'];
  const next = await dispatchEvent({type: 'execution.finished', reference: 'receipt:b'}, f.requests, h);
  assert.deepEqual(next.results.map(r => r.ticket), ['c']);
});
test('receipt model mismatch and ack failure require reconciliation', async () => {
  const f = fixture(), h = adapter(f), launch = h.launch;
  h.launch = async a => ({...await launch(a), model: a.ticket === 'a' ? 'wrong' : a.model.id});
  h.ack = async () => {throw Error('ack unknown');};
  assert.deepEqual((await dispatchEvent(event, f.requests, h)).results.map(r => r.stage), ['launch', 'ack']);
  assert.equal(h.records[1].receipt.workerId, 'b');
  assert.equal(h.records[1].sourceReceipt.reference, 'start');
});
test('reservation uncertainty is local and preserves earlier reservations', async () => {
  const f = fixture(), h = adapter(f), reserve = h.reserve;
  f.environment.capacity = 3;
  h.reserve = async a => {if (a.ticket === 'b') throw Error('storage response lost'); return reserve(a);};
  const r = await dispatchEvent(event, f.requests, h);
  assert.deepEqual(r.results.map(r => [r.ticket, r.state]), [['b', 'reconcile_required'], ['a', 'running'], ['c', 'running']]);
});
test('revalidation exceptions permit independent work to fill the slot', async () => {
  const f = fixture(), h = adapter(f);
  h.revalidate = async a => {if (a.ticket === 'a') throw Error('source offline'); return true;};
  const r = await dispatchEvent(event, f.requests, h);
  assert.deepEqual(r.results.map(r => r.state), ['validation_failed', 'running', 'running']);
});
test('malformed deferred task is rejected before any reservation', async () => {
  const f = fixture(), h = adapter(f);
  h.revalidate = async a => a.ticket !== 'a';
  delete f.requests[2].acceptance;
  await assert.rejects(dispatchEvent(event, f.requests, h), /acceptance/);
  assert.equal(h.reservations.size, 0);
});
test('queued chat remains pending and failed receipt persistence retains worker identity', async () => {
  const f = fixture(), h = adapter(f), launch = h.launch;
  let acks = 0;
  h.ack = async () => {acks++;};
  h.launch = async a => {
    const receipt = {...await launch(a), setupPending: true};
    if (a.ticket === 'b') throw Object.assign(Error('disk full'), {receipt});
    return receipt;
  };
  const r = await dispatchEvent(event, f.requests, h);
  assert.equal(r.results[0].state, 'delegated_pending_host');
  assert.equal(r.results[1].receipt.workerId, 'b');
  assert.equal(r.results[1].state, 'reconcile_required');
  assert.equal(acks, 0);
});
test('timer events and incomplete host adapters cannot dispatch', async () => {
  const f = fixture();
  await assert.rejects(dispatchEvent({type: 'timer', reference: 'x'}, f.requests, adapter(f)), /Unsupported/);
  await assert.rejects(dispatchEvent(event, f.requests, {}), /Missing host/);
});
