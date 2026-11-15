// DeepSeek Harness dispatch host candidate.
//
// This module is an explicit host binding, not a source of identity or permission.
// The calling harness supplies the authoritative source callbacks and its native
// subagent callback; this adapter only maps plan assignments onto that surface and
// persists reservations before any side effect.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {dispatchEvent} from '../../../customizations/platforms/process-management/yuanheng-local/sinan/dispatch.mjs';

const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const nonempty = value => typeof value === 'string' && !!value.trim();

function persistNew(file, value) {
  const fd = fs.openSync(file, 'wx', 0o600);
  try {
    fs.writeFileSync(fd, JSON.stringify(value) + '\n');
    fs.fsyncSync(fd);
  } finally {
    fs.closeSync(fd);
  }
}

const SOURCE_CALLBACKS = ['inspect', 'revalidate', 'startSource', 'ack', 'report', 'verifyTerminal'];

/** Handoff text: target, authority, acceptance and resource scope only. */
export function handoff(assignment) {
  return [
    `工单：${assignment.ticket}`,
    `目标：${assignment.outcome}`,
    `责任人：${assignment.owner}`,
    `授权引用：${assignment.authorityRef}`,
    `验收：${assignment.acceptance}`,
    `上下文引用：${JSON.stringify(assignment.contextRefs)}`,
    `来源版本：${JSON.stringify(assignment.sourceSnapshot)}`,
    `允许读取：${JSON.stringify(assignment.reads)}`,
    `允许写入：${JSON.stringify(assignment.writes)}`,
    '遵循工作区与元衡治理，仅执行本工单及本次交接范围；不得扩大写入范围。',
    '提交实际产物与验证证据，不把产出当作业务验收。',
    '连续执行：读取事实 → 执行 → 验证 → 核对剩余验收 → 继续下一已授权步骤。',
    '回合结束、计划或阶段性成功不等于业务完成；结束前按本次交接的验收逐项核对真实证据。',
    '只读、暂停、预算、工具审批和用户保留决定继续有效。',
  ].join('\n');
}

/** Host descriptor uses the shared host protocol v1 shape. */
export function harnessHostDescriptor(overrides = {}) {
  return {protocol_version: 1, host: {id: 'deepseek-harness', kind: 'cli'}, ...overrides};
}

export class HarnessDispatchHost {
  constructor({stateRoot, source, native, policy}) {
    if (!path.isAbsolute(stateRoot)) throw Error('stateRoot must be absolute');
    for (const method of SOURCE_CALLBACKS) {
      if (typeof source?.[method] !== 'function') throw Error(`Missing authoritative source callback: ${method}`);
    }
    if (typeof (native?.spawnAgent ?? native?.spawn_agent) !== 'function') {
      throw Error('Harness native subagent callback required');
    }
    if (!policy || !nonempty(policy.operator)) throw Error('Host operator reference required');
    this.root = stateRoot;
    this.source = source;
    this.native = native;
    this.policy = policy;
    fs.mkdirSync(stateRoot, {recursive: true});
    for (const directory of ['reservations', 'records', 'released']) {
      fs.mkdirSync(path.join(stateRoot, directory), {recursive: true});
    }
    this.sourceTail = Promise.resolve();
  }

  async withLock(fn) {
    const file = path.join(this.root, 'coordination.lock');
    // Never steal a lock on elapsed time: its owner must be reconciled first.
    const fd = fs.openSync(file, 'wx', 0o600);
    try {
      fs.writeFileSync(fd, JSON.stringify({pid: process.pid}));
      fs.fsyncSync(fd);
      return await fn();
    } finally {
      fs.closeSync(fd);
      fs.unlinkSync(file);
    }
  }

  activeReservations() {
    return fs
      .readdirSync(path.join(this.root, 'reservations'))
      .filter(name => name.endsWith('.json'))
      .filter(name => !fs.existsSync(path.join(this.root, 'released', name)))
      .map(name => read(path.join(this.root, 'reservations', name)).assignment);
  }

  async inspect(event) {
    const value = await this.source.inspect(event);
    const active = new Map(value.environment.active.map(item => [item.ticket, item]));
    for (const reservation of this.activeReservations()) {
      active.set(reservation.ticket, active.get(reservation.ticket) ?? reservation);
    }
    // The harness has no native chat-thread tool; chat creation stays unauthorized.
    return {
      ...value,
      environment: {...value.environment, active: [...active.values()], chatCreationAuthorized: false},
    };
  }

  async revalidate(assignment) {
    if (assignment.target !== 'agent') return false;
    return (await this.source.revalidate(assignment)) === true;
  }

  async reserve(assignment, event) {
    if (!/^[a-f0-9]{64}$/.test(assignment.key)) throw Error('Invalid reservation key');
    if (this.activeReservations().some(item => item.ticket === assignment.ticket)) return false;
    const file = path.join(this.root, 'reservations', `${assignment.key}.json`);
    if (fs.existsSync(file)) return false;
    persistNew(file, {assignment, event, state: 'reserved', operator: this.policy.operator});
    return true;
  }

  async startSource(assignment) {
    const next = this.sourceTail.then(() => this.source.startSource(assignment));
    this.sourceTail = next.catch(() => {});
    return await next;
  }

  async launch(assignment) {
    if (assignment.target !== 'agent') throw Error('Harness adapter dispatches agent targets only');
    const spawn = this.native.spawnAgent ?? this.native.spawn_agent;
    const raw = await spawn(
      {task_name: `sinan_${hash(assignment.key).slice(0, 16)}`, prompt: handoff(assignment), model: assignment.model?.id},
      {assignmentKey: assignment.key, ticket: assignment.ticket},
    );
    const value = raw?.structuredContent ?? raw;
    if (raw?.isError) throw Error('Native subagent rejected launch');
    const workerId = value?.agent_id ?? value?.agentId ?? value?.task_name;
    if (!nonempty(workerId)) throw Error('Native launch receipt missing worker identity; reconcile before retry');
    const receipt = {
      workerId,
      reference: `agent:${workerId}`,
      target: 'agent',
      model: assignment.model?.id,
      requestedModel: assignment.model?.id ?? null,
      observedModel: value.model ?? null,
      modelEvidence: value.model ? 'native_receipt' : 'request_accepted_not_observed',
    };
    // Persist immediately: a later ack/report failure must not lose worker identity.
    persistNew(path.join(this.root, 'records', `${crypto.randomUUID()}.json`), {
      assignment,
      state: 'launch_received',
      receipt,
    });
    return receipt;
  }

  async ack(assignment, receipt) {
    return await this.source.ack(assignment, receipt);
  }

  async record(value) {
    persistNew(path.join(this.root, 'records', `${crypto.randomUUID()}.json`), value);
    await this.source.report(value);
  }

  async run(event, requests) {
    return await dispatchEvent(event, requests, this);
  }

  async reconcile(event, key, receipt) {
    if (
      !['execution.finished', 'execution.failed'].includes(event?.type) ||
      !nonempty(event.reference) ||
      !/^[a-f0-9]{64}$/.test(key)
    ) {
      throw Error('Actual terminal event required');
    }
    return await this.withLock(async () => {
      const reserved = read(path.join(this.root, 'reservations', `${key}.json`));
      const file = path.join(this.root, 'released', `${key}.json`);
      if (fs.existsSync(file)) {
        return {state: 'already_reconciled', key};
      }
      if ((await this.source.verifyTerminal(reserved.assignment, event, receipt)) !== true) {
        throw Error('Terminal receipt not authenticated');
      }
      await this.record({assignment: reserved.assignment, event, receipt, state: 'terminal_verified'});
      persistNew(file, {key, event, receipt, state: 'released_after_terminal_verification'});
      return {state: 'released', key};
    });
  }
}
