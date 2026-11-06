import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {repositoryWorker, advance} from './session.mjs';

test('real verifier process and durable terminal match without native host callbacks', async t => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(),'repository-worker-'));
  t.after(() => fs.rmSync(dir,{recursive:true,force:true}));
  const config = {python:process.env.GONGGONG_PYTHON || (process.platform === 'win32' ? 'python' : 'python3'),
    workers:{test:{kind:'framework-integrity'}}};
  const a = {ticket:'test',key:'a'.repeat(64),model:{id:'framework-integrity'}};
  const worker = repositoryWorker(config,dir);
  const receipt = await worker.launch(a);
  assert.equal(await worker.outcome(receipt),'completed');
  assert.equal(receipt.observedModel,null);
  const event = {type:'execution.finished',reference:receipt.reference + ':exited'};
  const restored = repositoryWorker(config,dir);
  assert.equal(await restored.verifyTerminal(receipt,event,a),true);
  assert.equal(await restored.verifyTerminal({...receipt,workerId:'different'},event,a),false);
  assert.equal(await restored.verifyTerminal(receipt,{...event,reference:'stale'},a),false);
});

test('verified exit re-reads only deferred work; unknown exit retains occupancy', async () => {
  const config = {event:{type:'user.requested',reference:'request'},requests:[{ticket:'one'},{ticket:'two'}]};
  const observed = [];
  const host = {
    async run(event, pending) {
      observed.push([event.type,pending.map(r=>r.ticket)]);
      const first = pending[0].ticket;
      return {results:[{ticket:first,key:first,receipt:{reference:first},state:'running'}],
        deferred:pending.slice(1).map(r=>({...r,reason:'capacity'}))};
    },
    async reconcile(event,key) {
      assert.equal(event.reference, key + ':exited');
      assert.equal(key,'one');
      return {state:'released'};
    },
  };
  const result = await advance(config,host,{outcome:async r=>r.reference === 'one' ? 'completed' : 'unknown'});
  assert.deepEqual(observed,[['user.requested',['one','two']],['execution.finished',['two']]]);
  assert.deepEqual(result.results.map(r=>r.state),['released','reconcile_required']);
});

test('a faster worker frees its slot while the first worker is still busy', async () => {
  const names = ['slow','fast','waiting'];
  const config = {event:{type:'user.requested',reference:'test'},requests:names.map(ticket=>({ticket}))};
  let freeSlow;
  const slow = new Promise(resolve=>{freeSlow = resolve;});
  const host = {
    async run(event, requests) {
      if (requests[0].ticket === 'waiting') {
        assert.equal(event.reference,'fast:exited');
        freeSlow('completed');
      }
      return {results:requests.slice(0,2).map(({ticket})=>({ticket,key:ticket,receipt:{reference:ticket},state:'running'})),
        deferred:requests.slice(2)};
    },
    async reconcile() {return {state:'released'};},
  };
  const worker = {outcome:async receipt=>receipt.reference === 'slow' ? slow : 'completed'};
  const {results} = await advance(config,host,worker);
  assert.deepEqual(results.map(r=>r.ticket).sort(),names.sort());
});
