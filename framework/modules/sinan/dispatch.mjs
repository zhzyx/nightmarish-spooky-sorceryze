// Event-scoped dispatch. Source state, locks, identity and admission belong to the host.
import crypto from 'node:crypto';
import path from 'node:path';

const requiredString = (s, name) => {
  if (typeof s !== 'string' || !s.trim()) throw Error(`Missing ${name}`);
  return s;
};
const strings = (xs, name) => {
  if (!Array.isArray(xs) || xs.some(x => typeof x !== 'string' || !x.trim())) throw Error(`Invalid ${name}`);
  return xs;
};
const overlap = (a, b) => a === b || a.startsWith(b.endsWith('/') ? b : `${b}/`) || b.startsWith(a.endsWith('/') ? a : `${a}/`);
export function conflicts(a, b) {
  return a.writes.some(x => [...b.reads, ...b.writes].some(y => overlap(x, y))) ||
    b.writes.some(x => a.reads.some(y => overlap(x, y)));
}

// Host must resolve symlinks/junctions and workspace aliases before supplying resources.
function resources(task) {
  const normalize = xs => strings(xs, 'canonical resources').map(p => {
    if (!path.posix.isAbsolute(p) && !path.win32.isAbsolute(p)) throw Error('Resources must be absolute canonical paths');
    const normalized = p.replaceAll('\\', '/');
    if (normalized.split('/').includes('..') || normalized.split('/').includes('.')) throw Error('Resources must be normalized');
    const result = normalized.replace(/\/+$/, '') || '/';
    return /^[A-Za-z]:[\\/]|^\\\\/.test(p) ? result.toLowerCase() : result;
  });
  return {reads: normalize(task.reads), writes: normalize(task.writes)};
}

export function selectModel(requirements, catalog, target, requestedModel) {
  strings(requirements, 'capabilities');
  const eligible = catalog.filter(m => m.available === true && m.targets?.includes(target) &&
    requirements.every(c => m.capabilities?.includes(c)) && (!requestedModel || m.id === requestedModel));
  // preference is supplied by the host, never an invented price or quality score.
  eligible.sort((a, b) => (a.preference ?? Number.MAX_SAFE_INTEGER) - (b.preference ?? Number.MAX_SAFE_INTEGER) || a.id.localeCompare(b.id));
  if (!eligible.length) return null;
  return {id: eligible[0].id, reason: requestedModel ? 'explicit_model_and_required_capabilities' : 'required_capabilities_then_host_preference', capabilities: [...requirements]};
}

export function planDispatch(snapshot, requests, environment) {
  const {catalog, active, capacity} = environment;
  if (!Number.isInteger(capacity) || capacity < 0 || !Array.isArray(active) || !Array.isArray(catalog)) throw Error('Invalid host capacity/catalog/active workers');
  // Validate even deferred work before any caller can persist a reservation.
  for (const r of requests) {
    for (const field of ['ticket', 'outcome', 'owner', 'acceptance', 'authorityRef']) requiredString(r[field], field);
    strings(r.capabilities, 'capabilities');
    strings(r.contextRefs, 'context references');
    resources(r);
  }
  const ids = new Set();
  for (const model of catalog) {
    requiredString(model.id, 'model id');
    if (ids.has(model.id)) throw Error('Duplicate model id');
    ids.add(model.id);
    strings(model.capabilities, 'model capabilities');
    strings(model.targets, 'model targets');
    if (model.preference !== undefined && !Number.isFinite(model.preference)) throw Error('Invalid model preference');
  }
  const seen = new Set(), assignments = [], deferred = [];
  const held = active.map(t => ({...t, ...resources(t)}));
  const items = new Map(snapshot.items.map(t => [t.key, t]));
  const ordered = [...requests].sort((a, b) => {
    const rank = t => {const i = snapshot.ready.indexOf(t.ticket); return i < 0 ? Infinity : i;};
    return rank(a) - rank(b);
  });
  for (const request of ordered) {
    const ticket = requiredString(request.ticket, 'ticket');
    if (seen.has(ticket)) throw Error('Duplicate requested ticket');
    seen.add(ticket);
    const reject = reason => deferred.push({ticket, reason});
    const item = items.get(ticket);
    if (!item || !snapshot.ready.includes(ticket) || item.dispatchCandidate !== true) {reject('not_ready'); continue;}
    if (active.some(t => t.ticket === ticket)) {reject('already_in_flight'); continue;}
    const target = request.target ?? 'agent';
    if (!['chat', 'agent'].includes(target)) {reject('unsupported_target'); continue;}
    if (target === 'chat' && environment.chatCreationAuthorized !== true) {reject('chat_creation_not_authorized'); continue;}
    const source = snapshot.sourceSnapshots.find(s => s.source === item.source);
    if (!source) {reject('source_snapshot_missing'); continue;}
    const model = selectModel(request.capabilities, catalog, target, request.model);
    if (!model) {reject('required_model_or_capabilities_unavailable'); continue;}
    const io = resources(request);
    if (held.some(other => conflicts(io, other))) {reject('resource_conflict'); continue;}
    if (held.length >= capacity) {reject('capacity'); continue;}
    const assignment = {
      ticket, target, model, ...io,
      outcome: requiredString(request.outcome, 'outcome'),
      owner: requiredString(request.owner, 'owner'),
      authorityRef: requiredString(request.authorityRef, 'authority reference'),
      acceptance: requiredString(request.acceptance, 'acceptance'),
      contextRefs: strings(request.contextRefs, 'context references'),
      sourceSnapshot: structuredClone(source),
      execution: 'not_dispatched'
    };
    // Revision-specific idempotency, independent of event id and model choice.
    assignment.key = crypto.createHash('sha256').update(JSON.stringify([ticket, source])).digest('hex');
    assignments.push(assignment);
    held.push(assignment);
  }
  return {assignments, deferred, execution: 'not_dispatched'};
}

/**
 * Host contract: withLock serializes coordination across chats; inspect returns a fresh
 * board, catalog and all held reservations; reserve persists intent before side effects;
 * revalidate authenticates admission, mandate, source version, resources and capacity;
 * startSource invokes original CLI start, launch calls a real host, ack invokes original
 * CLI ack. record is durable and reports through shared Diting. Unknown outcomes retain
 * the reservation until an actual receipt reconciles them. No timers or retries here.
 */
export async function dispatchEvent(event, requests, host) {
  const events = ['request.created', 'ticket.changed', 'dependency.changed', 'decision.recorded',
    'execution.finished', 'execution.failed', 'user.requested', 'scope.changed'];
  if (!events.includes(event.type)) throw Error('Unsupported dispatch event');
  requiredString(event.reference, 'event reference');
  for (const method of ['withLock', 'inspect', 'reserve', 'revalidate', 'startSource', 'launch', 'ack', 'record']) {
    if (typeof host[method] !== 'function') throw Error(`Missing host adapter: ${method}`);
  }
  const reserved = await host.withLock(async () => {
    const {snapshot, environment} = await host.inspect(event);
    planDispatch(snapshot, requests, environment); // Validate the batch before reserving.
    const accepted = [], deferred = [], preparationResults = [];
    const current = {...environment, active: [...environment.active]};
    const rank = t => {const i = snapshot.ready.indexOf(t.ticket); return i < 0 ? Infinity : i;};
    for (const request of [...requests].sort((a, b) => rank(a) - rank(b))) {
      const plan = planDispatch(snapshot, [request], current);
      deferred.push(...plan.deferred);
      const assignment = plan.assignments[0];
      if (!assignment) continue;
      let stage = 'revalidate';
      try {
        if (await host.revalidate(assignment) !== true) {
          deferred.push({ticket: assignment.ticket, reason: 'host_revalidation_failed'});
          continue;
        }
        stage = 'reserve';
        if (await host.reserve(assignment, event) === true) accepted.push(assignment);
        else deferred.push({ticket: assignment.ticket, reason: 'existing_reservation'});
        // A pre-existing reservation also holds resources until host reconciliation.
        current.active.push(assignment);
      } catch (error) {
        if (stage === 'reserve') current.active.push(assignment);
        const result = {ticket: assignment.ticket, key: assignment.key, stage,
          state: stage === 'reserve' ? 'reconcile_required' : 'validation_failed', reason: String(error.message ?? error)};
        try {await host.record({assignment, event, ...result});}
        catch (recordError) {result.recordFailure = String(recordError.message ?? recordError);}
        preparationResults.push(result);
      }
    }
    return {assignments: accepted, deferred, preparationResults};
  });
  // Launch every independent assignment before awaiting their receipts.
  const results = await Promise.all(reserved.assignments.map(async assignment => {
    let stage = 'source_start';
    let sourceReceipt, receipt;
    try {
      sourceReceipt = await host.startSource(assignment);
      if (!sourceReceipt?.reference) throw Error('Missing source start receipt');
      stage = 'launch';
      receipt = await host.launch(assignment);
      if (!receipt?.workerId || !receipt?.reference || receipt.model !== assignment.model.id || receipt.target !== assignment.target) throw Error('Missing or mismatched host receipt');
      stage = 'ack';
      if (receipt.setupPending !== true) await host.ack(assignment, receipt);
      stage = 'record';
      const state = receipt.setupPending === true ? 'delegated_pending_host' : 'running';
      await host.record({assignment, event, state, sourceReceipt, receipt});
      return {ticket: assignment.ticket, key: assignment.key, state, receipt};
    } catch (error) {
      receipt ??= error.receipt;
      const result = {ticket: assignment.ticket, key: assignment.key, state: 'reconcile_required', stage, sourceReceipt, receipt, reason: String(error.message ?? error)};
      try {await host.record({assignment, event, ...result});}
      catch (recordError) {result.recordFailure = String(recordError.message ?? recordError);}
      return result;
    }
  }));
  return {event, results: [...reserved.preparationResults, ...results], deferred: reserved.deferred, execution: 'host_adapter_invoked'};
}
