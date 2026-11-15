import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {HarnessDispatchHost, handoff, harnessHostDescriptor} from './adapter.mjs';

const KEY = 'a'.repeat(64);
const TERMINAL = {type: 'execution.finished', reference: 'event:terminal'};

function temporaryRoot(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'harness-dispatch-'));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  return root;
}

function source(overrides = {}) {
  return {
    async inspect() {
      return {snapshot: {items: [], ready: [], sourceSnapshots: []}, environment: {catalog: [], active: [], capacity: 2}};
    },
    async revalidate() {
      return true;
    },
    async startSource() {
      return {reference: 'source:start'};
    },
    async ack() {},
    async report() {},
    async verifyTerminal() {
      return true;
    },
    ...overrides,
  };
}

function assignment(overrides = {}) {
  return {
    ticket: 'github:owner/repo#1',
    key: KEY,
    target: 'agent',
    model: {id: 'deepseek-v4-pro', capabilities: ['code'], targets: ['agent']},
    outcome: 'Implement the accepted work order',
    owner: 'sinan',
    authorityRef: 'issue:1',
    acceptance: 'Measured evidence recorded',
    contextRefs: ['issue:1'],
    sourceSnapshot: {revision: 'abc'},
    reads: ['/workspace/repo'],
    writes: ['/workspace/repo/src'],
    ...overrides,
  };
}

function host(t, overrides = {}) {
  const stateRoot = overrides.stateRoot ?? path.join(temporaryRoot(t), 'state');
  return new HarnessDispatchHost({
    stateRoot,
    source: overrides.source ?? source(),
    native: overrides.native ?? {async spawnAgent() { return {agent_id: 'agent-1', model: 'deepseek-v4-pro'}; }},
    policy: overrides.policy ?? {operator: 'harness-session'},
  });
}

test('rejects a relative state root', (t) => {
  assert.throws(() => host(t, {stateRoot: path.join('relative', 'state')}), /stateRoot must be absolute/);
});

test('rejects missing authoritative source callbacks', (t) => {
  assert.throws(() => host(t, {source: {inspect() {}}}), /Missing authoritative source callback/);
});

test('rejects a missing native subagent callback', (t) => {
  assert.throws(() => host(t, {native: {}}), /Harness native subagent callback required/);
});

test('reserve persists once and is idempotent per ticket and key', async (t) => {
  const instance = host(t);
  const value = assignment();
  assert.equal(await instance.reserve(value, TERMINAL), true);
  assert.equal(await instance.reserve(value, TERMINAL), false);
  assert.equal(instance.activeReservations().length, 1);
  const stored = JSON.parse(fs.readFileSync(path.join(instance.root, 'reservations', `${KEY}.json`), 'utf8'));
  assert.equal(stored.state, 'reserved');
  assert.equal(stored.operator, 'harness-session');
});

test('launch maps the native subagent receipt and rejects missing identity', async (t) => {
  const instance = host(t);
  const receipt = await instance.launch(assignment());
  assert.deepEqual(
    {workerId: receipt.workerId, reference: receipt.reference, target: receipt.target, model: receipt.model},
    {workerId: 'agent-1', reference: 'agent:agent-1', target: 'agent', model: 'deepseek-v4-pro'},
  );
  assert.equal(receipt.observedModel, 'deepseek-v4-pro');

  const silent = host(t, {native: {async spawnAgent() { return {}; }}});
  await assert.rejects(() => silent.launch(assignment()), /missing worker identity/);
});

test('inspect merges active reservations and forbids chat creation', async (t) => {
  const instance = host(t);
  await instance.reserve(assignment(), TERMINAL);
  const board = await instance.inspect(TERMINAL);
  assert.equal(board.environment.chatCreationAuthorized, false);
  assert.deepEqual(board.environment.active.map(item => item.ticket), ['github:owner/repo#1']);
});

test('reconcile requires an actual terminal event', async (t) => {
  const instance = host(t);
  await instance.reserve(assignment(), TERMINAL);
  await assert.rejects(() => instance.reconcile({type: 'request.created', reference: 'x'}, KEY, {}), /terminal event/);
});

test('reconcile releases only after the source authenticates the terminal receipt', async (t) => {
  const instance = host(t, {source: source({async verifyTerminal() { return false; }})});
  await instance.reserve(assignment(), TERMINAL);
  await assert.rejects(() => instance.reconcile(TERMINAL, KEY, {}), /not authenticated/);

  const accepted = host(t);
  await accepted.reserve(assignment(), TERMINAL);
  assert.deepEqual(await accepted.reconcile(TERMINAL, KEY, {}), {state: 'released', key: KEY});
  assert.deepEqual(await accepted.reconcile(TERMINAL, KEY, {}), {state: 'already_reconciled', key: KEY});
});

test('handoff and host descriptor expose only scope and protocol facts', () => {
  const text = handoff(assignment());
  assert.match(text, /github:owner\/repo#1/);
  assert.match(text, /不得扩大写入范围/);
  assert.deepEqual(harnessHostDescriptor(), {protocol_version: 1, host: {id: 'deepseek-harness', kind: 'cli'}});
});
