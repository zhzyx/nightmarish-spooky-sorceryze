import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {dispatchEvent} from '../../../framework/modules/sinan/dispatch.mjs';

const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
function persistNew(file, value) {
  const fd = fs.openSync(file, 'wx', 0o600);
  try {fs.writeFileSync(fd, JSON.stringify(value) + '\n'); fs.fsyncSync(fd);}
  finally {fs.closeSync(fd);}
}
function nonempty(value) {return typeof value === 'string' && !!value.trim();}
function handoff(a) {
  return `工单：${a.ticket}\n目标：${a.outcome}\n责任人：${a.owner}\n授权引用：${a.authorityRef}\n验收：${a.acceptance}\n` +
    `上下文引用：${JSON.stringify(a.contextRefs)}\n来源版本：${JSON.stringify(a.sourceSnapshot)}\n` +
    `允许读取：${JSON.stringify(a.reads)}\n允许写入：${JSON.stringify(a.writes)}\n` +
    '遵循工作区与元衡治理，仅执行本工单；不得扩大写入范围。提交实际产物与验证证据，不把产出当作业务验收。';
}

/** Explicit host binding only. Native tool callbacks must be supplied by the calling host. */
export class CodexDispatchHost {
  constructor({stateRoot, source, native, policy}) {
    if (!path.isAbsolute(stateRoot)) throw Error('stateRoot must be absolute');
    for (const method of ['inspect', 'revalidate', 'startSource', 'ack', 'report', 'verifyTerminal']) {
      if (typeof source?.[method] !== 'function') throw Error(`Missing authoritative source callback: ${method}`);
    }
    if (!policy || !nonempty(policy.defaultChatModel)) throw Error('Current default chat model required');
    if (policy.inheritedAgentModel !== undefined && !nonempty(policy.inheritedAgentModel)) {
      throw Error('Current inherited agent model required');
    }
    this.root = stateRoot; this.source = source; this.native = native; this.policy = policy;
    fs.mkdirSync(stateRoot, {recursive: true});
    for (const directory of ['reservations', 'records', 'released']) fs.mkdirSync(path.join(stateRoot, directory), {recursive: true});
    this.sourceTail = Promise.resolve();
  }
  async withLock(fn) {
    const file = path.join(this.root, 'coordination.lock');
    // Never steal a lock on elapsed time: its owner's status must be reconciled.
    const fd = fs.openSync(file, 'wx', 0o600);
    try {fs.writeFileSync(fd, JSON.stringify({pid: process.pid})); fs.fsyncSync(fd); return await fn();}
    finally {fs.closeSync(fd); fs.unlinkSync(file);}
  }
  activeReservations() {
    return fs.readdirSync(path.join(this.root, 'reservations')).filter(n => n.endsWith('.json'))
      .filter(n => !fs.existsSync(path.join(this.root, 'released', n)))
      .map(n => read(path.join(this.root, 'reservations', n)).assignment);
  }
  async inspect(event) {
    const value = await this.source.inspect(event);
    const active = new Map(value.environment.active.map(a => [a.ticket, a]));
    // Merge resource sets if a source and this adapter both report the same worker.
    for (const a of this.activeReservations()) {
      const old = active.get(a.ticket);
      active.set(a.ticket, old ? {...a, reads: [...new Set([...old.reads, ...a.reads])], writes: [...new Set([...old.writes, ...a.writes])]} : a);
    }
    const inherited = this.policy.inheritedAgentModel;
    const catalog = value.environment.catalog.map(model => inherited && model.id !== inherited && Array.isArray(model.targets)
      ? {...model, targets: model.targets.filter(target => target !== 'agent')}
      : model);
    return {...value, environment: {...value.environment, catalog, active: [...active.values()],
      chatCreationAuthorized: this.policy.chatCreationAuthorized === true && value.environment.chatCreationAuthorized === true}};
  }
  async revalidate(a) {
    if (a.target === 'agent' && typeof this.native.spawn_agent !== 'function') return false;
    if (a.target === 'chat') {
      if (typeof this.native.create_thread !== 'function' || this.policy.chatCreationAuthorized !== true || !this.policy.threadTarget) return false;
      const explicit = this.policy.explicitChatModels?.[a.ticket];
      if (a.model.id !== (explicit || this.policy.defaultChatModel)) return false;
    }
    return await this.source.revalidate(a) === true;
  }
  async reserve(a, event) {
    if (!/^[a-f0-9]{64}$/.test(a.key)) throw Error('Invalid reservation key');
    if (this.activeReservations().some(x => x.ticket === a.ticket)) return false;
    const file = path.join(this.root, 'reservations', `${a.key}.json`);
    if (fs.existsSync(file)) return false;
    persistNew(file, {assignment: a, event, state: 'reserved'});
    return true;
  }
  async startSource(a) {
    // Local serial source transactions; source callback also enforces distributed CAS.
    const next = this.sourceTail.then(() => this.source.startSource(a));
    this.sourceTail = next.catch(() => {});
    return await next;
  }
  async launch(a) {
    let args, raw;
    const inherited = a.target === 'agent' && this.policy.inheritedAgentModel !== undefined;
    if (a.target === 'agent') {
      args = {task_name: `sinan_${hash(a.key).slice(0, 16)}`, fork_turns: 'none', message: handoff(a)};
      if (!inherited) args.model = a.model.id;
      raw = await this.native.spawn_agent(args, {assignmentKey:a.key,ticket:a.ticket});
    } else {
      args = {title: a.outcome, prompt: handoff(a), target: this.policy.threadTarget};
      if (this.policy.explicitChatModels?.[a.ticket]) args.model = this.policy.explicitChatModels[a.ticket];
      raw = await this.native.create_thread(args, {assignmentKey:a.key,ticket:a.ticket});
    }
    const value = raw?.structuredContent ?? raw;
    if (raw?.isError) throw Error('Native tool rejected launch');
    const workerId = a.target === 'agent' ? (value?.agent_id ?? value?.task_name) : (value?.threadId ?? value?.clientThreadId);
    if (!nonempty(workerId)) throw Error('Native launch receipt missing worker identity; reconcile before retry');
    const receipt = {workerId, reference: `${a.target}:${workerId}`, target: a.target,
      model: a.model.id, requestedModel: args.model ?? null, observedModel: value.model ?? null,
      modelEvidence: value.model ? 'native_receipt' : args.model ? 'request_accepted_not_observed' : 'host_inheritance_not_observed',
      setupPending: !!value.clientThreadId && !value.threadId, hostId: value.hostId ?? null};
    // Persist immediately, so subsequent source ack/report failure cannot lose worker identity.
    try {
      persistNew(path.join(this.root, 'records', `${crypto.randomUUID()}.json`), {assignment: a, state: 'launch_received', receipt});
      if (value.model && value.model !== a.model.id) throw Error('Native receipt model mismatch; durable receipt retained');
    } catch (error) {
      error.receipt = receipt;
      throw error;
    }
    return receipt;
  }
  async ack(a, receipt) {return await this.source.ack(a, receipt);}
  async record(value) {
    persistNew(path.join(this.root, 'records', `${crypto.randomUUID()}.json`), value);
    await this.source.report(value);
  }
  async completeSetup(event,key,receipt) {
    if(event?.type!=='ticket.changed'||!nonempty(event.reference)||!/^[a-f0-9]{64}$/.test(key))throw Error('Actual setup event required');
    return this.withLock(async()=>{
      const a=read(path.join(this.root,'reservations',key+'.json')).assignment;
      if(fs.existsSync(path.join(this.root,'released',key+'.json')))return {state:'already_reconciled',key};
      const records=fs.readdirSync(path.join(this.root,'records')).filter(n=>n.endsWith('.json')).map(n=>read(path.join(this.root,'records',n)));
      if(records.some(r=>r.assignment?.key===key&&r.state==='running_after_verified_setup'&&JSON.stringify(r.receipt)===JSON.stringify(receipt)))return {state:'already_setup',key};
      const pending=records.find(r=>r.assignment?.key===key&&r.receipt?.setupPending===true)?.receipt;
      if(!pending||a.target!=='chat'||receipt?.target!=='chat'||receipt.setupPending!==false||receipt.model!==a.model.id||!nonempty(receipt.workerId)||!nonempty(receipt.reference))throw Error('Pending and ready chat receipts required');
      if(typeof this.source.verifySetup!=='function'||await this.source.verifySetup(a,event,pending,receipt)!==true)throw Error('Chat setup mapping not verified by host');
      await this.ack(a,receipt);await this.record({assignment:a,event,receipt,state:'running_after_verified_setup'});
      return receipt;
    });
  }
  async run(event, requests) {
    // Chat model overrides require an explicit user-selected model, per native tool policy.
    const prepared = requests.map(r => r.target !== 'chat' ? r : {...r,
      model: r.model ?? this.policy.explicitChatModels?.[r.ticket] ?? this.policy.defaultChatModel});
    return await dispatchEvent(event, prepared, this);
  }
  async reconcile(event, key, receipt) {
    if (!['execution.finished', 'execution.failed'].includes(event.type) || !nonempty(event.reference) || !/^[a-f0-9]{64}$/.test(key)) throw Error('Actual terminal event required');
    return await this.withLock(async () => {
      const reserved = read(path.join(this.root, 'reservations', `${key}.json`));
      const file = path.join(this.root, 'released', `${key}.json`);
      if (fs.existsSync(file)) return {state: 'already_reconciled', key};
      // Verification must match worker, reservation, revision and real terminal source state.
      if (await this.source.verifyTerminal(reserved.assignment, event, receipt) !== true) throw Error('Terminal receipt not authenticated');
      await this.record({assignment: reserved.assignment, event, receipt, state: 'terminal_verified'});
      persistNew(file, {key, event, receipt, state: 'released_after_terminal_verification'});
      return {state: 'released', key};
    });
  }
  async releaseUnstarted(event,key) {
    if(event?.type!=='execution.failed'||!nonempty(event.reference)||!/^[a-f0-9]{64}$/.test(key))throw Error('Actual never-launched verification event required');
    return this.withLock(async()=>{
      const reserved=read(path.join(this.root,'reservations',key+'.json'));
      if(typeof this.source.verifyNeverLaunched!=='function'||await this.source.verifyNeverLaunched(reserved.assignment,event)!==true)throw Error('Native outcome unknown; reservation retained');
      const file=path.join(this.root,'released',key+'.json');
      if(fs.existsSync(file))return {state:'already_reconciled',key};
      await this.record({assignment:reserved.assignment,event,state:'never_launched_verified'});
      persistNew(file,{key,event,state:'released_never_launched'});
      return {state:'released',key};
    });
  }
}
