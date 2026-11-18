// Pipe-only transport. Scheduling, model selection and execution stay in Sinan.
import {createInterface} from 'node:readline';
import {driveNative} from './native_dispatch.mjs';

if (process.argv.includes('--multiplex')) {
  const jobs = new Map(), pending = new Map();
  let serial = 0, lastJob = 0;
  const input = createInterface({input: process.stdin});
  const send = message => {
    const data = JSON.stringify(message) + '\n';
    if (Buffer.byteLength(data) > 8 * 1024 * 1024) throw Error('Dispatcher packet bound exceeded');
    if (process.stdout.writableLength + Buffer.byteLength(data) > 16 * 1024 * 1024) throw Error('Dispatcher output buffer bound exceeded');
    process.stdout.write(data);
  };
  const fail = () => {
    // Lost transport cannot authorize a new driver or replay an existing effect.
    process.exitCode = 1;
    for (const waiter of pending.values()) waiter.reject(Error('Host pipe failed; no replay'));
    pending.clear();
    input.close();
    process.stdin.destroy();
  };
  input.on('line', line => {
    try {
      if (Buffer.byteLength(line) > 8 * 1024 * 1024) throw Error('Host packet bound exceeded');
      const message = JSON.parse(line);
      if (message.type === 'start') {
        if (Object.keys(message).sort().join() !== 'job,type' || !Number.isSafeInteger(message.job) || message.job <= lastJob || jobs.size >= 1024) throw Error('Invalid driver admission');
        lastJob = message.job;
        const job = {pending: 0};
        jobs.set(message.job, job);
        const service = (operation, value) => new Promise((resolve, reject) => {
          if (pending.size >= 4096 || process.exitCode) return reject(Error('Dispatcher unavailable'));
          const id = ++serial;
          job.pending++;
          pending.set(id, {resolve, reject, job: message.job});
          send({type: 'rpc', job: message.job, id, operation, value});
        });
        driveNative(service).then(value => {
          if (job.pending) throw Error('Driver retained unfinished requests');
          if (!process.exitCode) send({type: 'result', job: message.job, value});
          jobs.delete(message.job);
        }).catch(fail);
        return;
      }
      const waiter = pending.get(message.id);
      const keys = Object.keys(message).sort().join();
      if (message.type !== 'reply' || !waiter || waiter.job !== message.job || !['id,job,type,value', 'error,id,job,type'].includes(keys)) throw Error('Unknown RPC receipt');
      pending.delete(message.id);
      jobs.get(message.job).pending--;
      if ('error' in message) waiter.reject(Error(message.error));
      else waiter.resolve(message.value);
    } catch {
      fail();
    }
  });
  input.on('close', () => {
    if (jobs.size || pending.size) fail();
    else process.stdin.destroy();
  });

} else {
  let serial = 0;
  const pending = new Map();
  const input = createInterface({input: process.stdin});
  input.on('line', line => {
    const reply = JSON.parse(line);
    const waiter = pending.get(reply.id);
    if (!waiter) throw Error('Unknown RPC receipt');
    pending.delete(reply.id);
    if ('error' in reply) waiter.reject(Error(reply.error));
    else waiter.resolve(reply.value);
  });
  input.on('close', () => {
    for (const waiter of pending.values()) waiter.reject(Error('Host pipe closed; no replay'));
    pending.clear();
  });
  const service = (operation, value) => new Promise((resolve, reject) => {
    const id = ++serial;
    pending.set(id, {resolve, reject});
    process.stdout.write(JSON.stringify({id, operation, value}) + '\n');
  });
  try {
    const value = await driveNative(service);
    process.stdout.write(JSON.stringify({type: 'result', value}) + '\n');
  } finally {
    input.close();
    process.stdin.destroy();
}

}
