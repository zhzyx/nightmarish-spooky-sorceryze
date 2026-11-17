// Thin installed node adapter: model selection and event planning remain Sinan's.
import {dispatchEvent} from '../../../platforms/process-management/yuanheng-local/sinan/dispatch.mjs';
import {pathToFileURL} from 'node:url';

export async function dispatchNative(event, requests, service, launch) {
  const host = {
    // Server reserve performs atomic capacity/source comparison; no network lock.
    withLock: fn => fn(),
    inspect: () => service('inspect', {}),
    revalidate: a => service('revalidate', {assignment: a}),
    reserve: (a, e) => service('reserve', {assignment: a, event: e}),
    startSource: a => service('start', {assignment: a}),
    launch,
    ack: (a, receipt) => service('ack', {assignment: a, receipt}),
    record: value => service('record', value),
  };
  return dispatchEvent(event, requests, host);
}

export function httpService(base, token) {
  const url = new URL(base);
  if (url.protocol !== 'https:' && !(url.protocol === 'http:' && ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname))) throw Error('TLS or loopback required');
  return async (operation, value) => {
    const response = await fetch(new URL(`/api/v1/native/workflow/${operation}`, url), {
      method: 'POST', headers: {'content-type': 'application/json', authorization: `Bearer ${token}`},
      body: JSON.stringify(value), signal: AbortSignal.timeout(120000), redirect: 'error',
    });
    if (!response.ok) throw Error(`Native service returned ${response.status}`);
    const chunks = []; let bytes = 0;
    for await (const chunk of response.body) {
      bytes += chunk.length;
      if (bytes > 8 * 1024 * 1024) throw Error('Native response exceeds limit');
      chunks.push(chunk);
    }
    return JSON.parse(Buffer.concat(chunks).toString('utf8'));
  };
}

export async function driveNative(service, initial = {type: 'user.requested', reference: 'native-cli'}) {
  const attempted = new Set(), finished = new Set(), pending = new Set(), rejectedEvents = new Set();
  const result = {results: [], deliveries: [], deferred: [], errors: []};
  let coordinator = Promise.resolve();
  let delivering = 0, deliveryCapacity = 1;
  const track = work => {
    const observed = work.catch(error => result.errors.push({stage: 'dispatch', reason: String(error.message ?? error)}));
    pending.add(observed);
    observed.finally(() => pending.delete(observed));
  };
  const delivery = async key => {
    if (finished.has(key) || delivering >= deliveryCapacity) return;
    finished.add(key);
    delivering++;
    try {result.deliveries.push({key, ...await service('finish', {key})});}
    catch (error) {result.errors.push({key, stage: 'finish', reason: String(error.message ?? error)});}
    finally {delivering--;}
    await signal({type: 'execution.finished', reference: key});
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
      for (const key of board.produced ?? []) if (!finished.has(key)) track(delivery(key));
      const requests = board.requests.filter(request => !attempted.has(request.ticket));
      if (!requests.length) return;
      // dispatchEvent owns Sinan model selection and durable server reservations.
      // Its batch Promise is tracked, never awaited by the coordinator.
      track(dispatchNative(event, requests, service, async assignment => {
        attempted.add(assignment.ticket);
        try {
          const terminal = await service('execute', {key: assignment.ticket});
          // The terminal frees production capacity before potentially slow review.
          await signal({type: 'execution.finished', reference: assignment.ticket});
          if (!['produced', 'accepted'].includes(terminal.state)) throw Error('Worker not successfully terminal');
          await delivery(assignment.ticket);
          return {workerId: assignment.ticket, reference: assignment.ticket, model: assignment.model.id, target: assignment.target};
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
