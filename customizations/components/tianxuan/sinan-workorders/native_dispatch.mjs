// Thin installed node adapter: model selection and event planning remain Sinan's.
import {dispatchEvent} from '../../../platforms/process-management/yuanheng-local/sinan/dispatch.mjs';
import {pathToFileURL} from 'node:url';

export async function dispatchNative(event, requests, service, launch) {
  let catalog;
  const host = {
    // Server reserve performs atomic capacity/source comparison; no network lock.
    withLock: fn => fn(),
    inspect: async () => {
      const board = await service('inspect', {});
      catalog = board.environment.catalog;
      return board;
    },
    revalidate: a => service('revalidate', {assignment: a}),
    reserve: (a, e) => service('reserve', {assignment: a, event: e}),
    startSource: a => service('start', {assignment: a}),
    launch,
    ack: (a, receipt) => service('ack', {assignment: a, receipt}),
    record: value => service('record', value),
  };
  const batch = await dispatchEvent(event, requests, host);
  const byTicket = new Map(requests.map(request => [request.ticket, request]));
  for (const item of batch.deferred) {
    if (item.reason !== 'required_model_or_capabilities_unavailable') continue;
    const request = byTicket.get(item.ticket);
    // Native contracts pin the installed profile before dispatch.
    const model = catalog.find(entry => entry.id === request.model);
    item.model = request.model;
    if (model?.localStatus) item.localStatus = model.localStatus;
    item.modelAvailable = model?.available === true && model.targets.includes(request.target ?? 'agent');
    item.requiredCapabilities = request.capabilities;
    item.missingCapabilities = request.capabilities.filter(capability => !model?.capabilities.includes(capability));
  }
  return batch;
}

export function httpService(base, token, {executeTimeoutMs = 120000} = {}) {
  const url = new URL(base);
  if (url.protocol !== 'https:' && !(url.protocol === 'http:' && ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname))) throw Error('TLS or loopback required');
  return async (operation, value) => {
    const response = await fetch(new URL(`/api/v1/native/workflow/${operation}`, url), {
      method: 'POST', headers: {'content-type': 'application/json', authorization: `Bearer ${token}`},
      body: JSON.stringify(value), signal: AbortSignal.timeout(['await-terminal', 'integration-await'].includes(operation) ? 86500000 : operation === 'execute' ? executeTimeoutMs : 120000), redirect: 'error',
    });
    const chunks = []; let bytes = 0;
    for await (const chunk of response.body) {
      bytes += chunk.length;
      if (bytes > 8 * 1024 * 1024) throw Error('Native response exceeds limit');
      chunks.push(chunk);
    }
    const reply = JSON.parse(Buffer.concat(chunks).toString('utf8'));
    if (!response.ok) throw Error(`Native service returned ${response.status}: ${reply.detail ?? 'operation failed'}`);
    return reply;
  };
}

export async function driveNative(service, initial = {type: 'user.requested', reference: 'native-cli'}) {
  const watched = new Set(), continuousEvents = new Set();
  const checked = new Set(), integrated = new Set(), groupErrors = new Set();
  const verifiedStages = new Set();
  const attempted = new Set(), finished = new Set(), pending = new Set(), rejectedEvents = new Set();
  const result = {results: [], deliveries: [], deferred: [], errors: []};
  let coordinator = Promise.resolve();
  let delivering = 0, deliveryCapacity = 1;
  const track = work => {
    const observed = work.catch(error => result.errors.push({stage: 'dispatch', reason: String(error.message ?? error)}));
    pending.add(observed);
    observed.finally(() => pending.delete(observed));
  };
  const observe = async key => {
    // One reconnect after an ambiguous observer reply; never replay execute.
    try {return await service('await-terminal', {key});}
    catch {return service('await-terminal', {key});}
  };
  const delivery = async (key, contribution = false) => {
    if (finished.has(key) || delivering >= deliveryCapacity) return;
    finished.add(key);
    delivering++;
    try {
      if (contribution) {
        if (!checked.has(key)) {
          checked.add(key);
          await service('integration-contribution', {key});
        }
      } else result.deliveries.push({key, ...await service('finish', {key})});
    }
    catch (error) {result.errors.push({key, stage: 'finish', reason: String(error.message ?? error)});}
    finally {delivering--;}
    await signal({type: 'execution.finished', reference: key});
  };
  const integrate = async original => {
    integrated.add(original);
    let key = original;
    try {
      const row = await service('integration-status', {key});
      if (row.acceptance) return;
      let merged = await service('integration-execute', {key});
      if (merged.state === 'conflicts_pending') {
        // Durable resolver intent prevents duplicate effects across restarts.
        try {key = await service('integration-resolve', {key});}
        catch {key = await service('integration-reconcile', {key});}
        merged = await service('integration-execute', {key});
      }
      if (merged.state === 'conflicts_pending') throw Error('Integration remains conflicted');
      result.deliveries.push({key, ...await service('integration-finish', {key})});
    } catch (error) {result.errors.push({key, stage: 'integration', reason: String(error.message ?? error)});}
    await signal({type: 'execution.finished', reference: original});
  };
  const signal = event => {
    // Serialize only event inspection/planning. Long workers/reviews remain outside.
    coordinator = coordinator.then(async () => {
      try {
        const advanced = await service('advance', {exclude: [...rejectedEvents]});
        for (const error of advanced.errors ?? []) {
          rejectedEvents.add(error.event);
          result.errors.push({stage: 'advance', ...error});
        }
      } catch (error) {result.errors.push({stage: 'advance', reason: String(error.message ?? error)});}
      const board = await service('inspect', {});
      deliveryCapacity = Math.max(1, board.environment.capacity);
      for (const active of board.environment.active ?? []) {
        if (!active.terminalObservable || attempted.has(active.ticket) || watched.has(active.ticket)) continue;
        watched.add(active.ticket);
        track(observe(active.ticket).then(() => signal({type: 'execution.finished', reference: active.ticket})));
      }
      for (const error of board.integrations?.errors ?? []) {
        const id = JSON.stringify(error);
        if (!groupErrors.has(id)) {groupErrors.add(id); result.errors.push({stage: 'integration-discovery', ...error});}
      }
      for (const lane of board.integrations?.continuous ?? []) {
        if (continuousEvents.has(lane.event)) continue;
        continuousEvents.add(lane.event);
        track((async () => {
          const request = {key: lane.key, event: lane.event};
          let receipt;
          try {receipt = await service('integration-continue', request);}
          catch {receipt = await service('integration-await', request);}
          if (receipt.state === 'publisher_busy') receipt = await service('integration-await', request);
          result.deliveries.push(receipt);
          if (receipt.state === 'held') result.errors.push({stage: 'integration', key: lane.key, reason: receipt.error});
          await signal({type: 'execution.finished', reference: lane.event});
        })());
      }
      for (const group of board.integrations?.ready ?? []) if (!integrated.has(group.key)) track(integrate(group.key));
      for (const key of board.stage_checks ?? []) {
        if (delivering >= deliveryCapacity) break;
        if (verifiedStages.has(key)) continue;
        verifiedStages.add(key);
        delivering++;
        track((async () => {
          try {
            const receipt = await service('verify-stage', {key});
            (result.stages ??= []).push(receipt);
          } catch (error) {result.errors.push({key, stage: 'verify-stage', reason: String(error.message ?? error)});}
          finally {delivering--;}
          await signal({type: 'execution.finished', reference: key});
        })());
      }
      for (const key of [...(board.produced ?? []), ...(board.contributions ?? [])]) if (!finished.has(key)) track(delivery(key, (board.contributions ?? []).includes(key)));
      const requests = board.requests.filter(request => !attempted.has(request.ticket));
      if (!requests.length) return;
      // dispatchEvent owns Sinan model selection and durable server reservations.
      // Its batch Promise is tracked, never awaited by the coordinator.
      track(dispatchNative(event, requests, service, async assignment => {
        attempted.add(assignment.ticket);
        try {
          let terminal;
          try {terminal = await service('execute', {key: assignment.ticket});}
          catch {terminal = await observe(assignment.ticket);}
          if (['reserved', 'running', 'held'].includes(terminal.state)) terminal = await observe(assignment.ticket);
          // The terminal frees production capacity before potentially slow review.
          await signal({type: 'execution.finished', reference: assignment.ticket});
          if (!['produced', 'accepted', 'stage-reached', 'stage-unmet'].includes(terminal.state)) throw Error('Worker not successfully terminal');
          if (terminal.id !== assignment.ticket || terminal.worker_ref !== 'native-worker:' + terminal.id) throw Error('Worker receipt does not match the assigned execution');
          return {workerId: terminal.id, reference: terminal.id, worker_ref: terminal.worker_ref, model: assignment.model.id, target: assignment.target};
        } catch (error) {
          await signal({type: 'execution.failed', reference: assignment.ticket});
          throw error;
        }
      }).then(batch => {
        result.results.push(...batch.results);
        result.deferred = batch.deferred;
        for (const item of batch.results) attempted.add(item.ticket);
      }));
    }).catch(error => result.errors.push({stage: 'coordinate', reason: String(error.message ?? error)}));
    return coordinator;
  };
  await signal(initial);
  // Wait only for real operation settlements; no timer/retry or whole-batch gate.
  while (pending.size) {
    await Promise.race(pending);
    await coordinator;
  }
  return result;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const service = httpService(process.env.NATIVE_SERVICE_URL, process.env.NATIVE_SERVICE_TOKEN);
  const result = await driveNative(service);
  process.stdout.write(JSON.stringify(result) + '\n');
}
