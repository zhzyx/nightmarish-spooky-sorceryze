import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {CodexDispatchHost} from './adapter.mjs';

const event = {type: 'request.created', reference: 'source:event'};
function setup(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'codex-dispatch-'));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  const requests = ['one','two','three'].map(ticket => ({ticket, outcome: ticket, owner:'owner', authorityRef:'mandate', acceptance:'test', contextRefs:['source:context'], capabilities:['coding'], reads:[], writes:[`D:/work/${ticket}`]}));
  const calls = [], reports = [];
  const source = {inspect: async () => ({snapshot:{items:requests.map(r => ({key:r.ticket, source:'s', dispatchCandidate:true})), ready:requests.map(r => r.ticket), sourceSnapshots:[{source:'s', version:1}]}, environment:{capacity:2, active:[], chatCreationAuthorized:true, catalog:[{id:'small', targets:['agent','chat'], capabilities:['coding'], available:true, preference:1},{id:'large',targets:['agent','chat'],capabilities:['coding','reasoning'],available:true,preference:2}]}}),
    revalidate:async () => true, startSource:async () => ({reference:'start'}), ack:async () => {}, report:async r => reports.push(r), verifyTerminal:async () => true};
  const native = {spawn_agent:async a => {calls.push(a); return {task_name:a.task_name};}, create_thread:async a => {calls.push(a); return {threadId:'chat-1',hostId:'local'};}};
  const policy = {defaultChatModel:'small',chatCreationAuthorized:true,threadTarget:{type:'projectless'}};
  const make = () => new CodexDispatchHost({stateRoot:root, source,native,policy});
  return {root,requests,calls,reports,source,native,policy,make};
}
test('actual callbacks receive capability selected models, isolated contexts and bounded handoff', async t => {
  const f = setup(t); f.requests[1].capabilities.push('reasoning');
  const result = await f.make().run(event,f.requests);
  assert.deepEqual(f.calls.map(c => c.model),['small','large']);
  assert.ok(f.calls.every(c => c.fork_turns === 'none' && c.message.includes('source:context')));
  assert.ok(result.results.every(r => r.receipt.observedModel === null));
});
test('agent and chat handoffs carry scoped continuation without changing authority or model', async t => {
  const f = setup(t);
  f.requests[1].target = 'chat';
  const result = await f.make().run(event, f.requests.slice(0, 2));
  assert.equal(result.results.length, 2);
  for (const args of f.calls) {
    const prompt = args.message ?? args.prompt;
    assert.ok(prompt.includes('读取事实 → 执行 → 验证 → 核对剩余验收'));
    assert.ok(prompt.includes('只读、暂停、预算、工具审批和用户保留决定继续有效'));
    assert.ok(prompt.includes('不接管父任务的交付权限'));
    assert.ok(prompt.includes('授权引用：mandate'));
    assert.ok(prompt.includes('验收：test'));
  }
  assert.equal(f.calls[0].fork_turns, 'none');
  assert.equal(f.calls[0].model, 'small');
  assert.equal(Object.hasOwn(f.calls[1], 'model'), false);
});
test('inherited agent model limits selection and leaves the native override unset', async t => {
  const f = setup(t);
  f.policy.inheritedAgentModel = 'large';
  f.requests[1].model = 'small';
  f.requests[2].target = 'chat';
  const result = await f.make().run(event, f.requests);
  assert.deepEqual(result.deferred, [{ticket:'two', reason:'required_model_or_capabilities_unavailable'}]);
  assert.equal(f.calls.length, 2);
  assert.ok(f.calls.every(args => !Object.hasOwn(args, 'model')));
  const agent = result.results.find(r => r.ticket === 'one').receipt;
  assert.equal(agent.model, 'large');
  assert.equal(agent.requestedModel, null);
  assert.equal(agent.observedModel, null);
  assert.equal(agent.modelEvidence, 'host_inheritance_not_observed');
  assert.equal(result.results.find(r => r.ticket === 'three').receipt.model, 'small');
});
test('inherited agent cannot borrow capabilities from another catalog entry', async t => {
  const f = setup(t);
  f.policy.inheritedAgentModel = 'small';
  f.requests[0].capabilities.push('reasoning');
  const result = await f.make().run(event, [f.requests[0]]);
  assert.equal(result.deferred[0].reason, 'required_model_or_capabilities_unavailable');
  assert.equal(f.calls.length, 0);
});
test('launches overlap, before either receipt is resolved', async t => {
  const f = setup(t), release = [];
  f.native.spawn_agent = a => {f.calls.push(a);return new Promise(resolve => release.push(() => resolve({task_name:a.task_name})));};
  const run = f.make().run(event,f.requests);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(f.calls.length,2); release.forEach(r => r()); await run;
});
test('restart retains unknown launch and prevents duplicate launch', async t => {
  const f=setup(t); f.native.spawn_agent=async a=>{f.calls.push(a);throw Error('lost response');};
  assert.ok((await f.make().run(event,f.requests)).results.every(r=>r.state==='reconcile_required'));
  assert.equal((await f.make().run(event,f.requests)).results.length,0);
  assert.equal(f.calls.length,2);
});
test('durable receipt survives ack failure; authenticated completion frees capacity', async t => {
  const f=setup(t), host=f.make(); f.source.ack=async()=>{throw Error('ack lost');};
  const r=await host.run(event,f.requests);
  assert.equal(r.results[0].receipt.observedModel,null);
  const active=host.activeReservations();
  f.source.verifyTerminal=async()=>false;
  await assert.rejects(host.reconcile({type:'execution.finished',reference:'done'},active[0].key,{}),/authenticated/);
  assert.equal(host.activeReservations().length,2);
  f.source.verifyTerminal=async()=>true;
  await host.reconcile({type:'execution.finished',reference:'done'},active[0].key,{workerId:r.results[0].receipt.workerId});
  f.requests.shift(); // source no longer lists the completed ticket as ready.
  f.source.ack=async()=>{};
  assert.equal((await host.run({type:'execution.finished',reference:'done'},f.requests)).results[0].ticket,'three');
});
test('chat uses configured default without overriding model; explicit exact model may override', async t=>{
  const f=setup(t);f.requests[0].target='chat';
  const first = await f.make().run(event,[f.requests[0]]);
  assert.equal(first.results[0].receipt.requestedModel, null);
  assert.equal(Object.hasOwn(f.calls[0],'model'),false);
  f.requests[1].target='chat';f.requests[1].model='large';f.policy.explicitChatModels={two:'large'};
  const second = await f.make().run(event,[f.requests[1]]);
  assert.equal(second.results[0].receipt.requestedModel, 'large');
  assert.equal(f.calls[1].model,'large');
});
test('chat creation and model override restrictions fail before source start', async t=>{
  const f=setup(t);f.requests[0].target='chat';f.requests[0].model='large';
  let starts=0;f.source.startSource=async()=>{starts++;return {reference:'start'};};
  const r=await f.make().run(event,[f.requests[0]]);
  assert.equal(r.deferred[0].reason,'host_revalidation_failed');assert.equal(starts,0);
  f.policy.chatCreationAuthorized=false;
  assert.equal((await f.make().run(event,[f.requests[0]])).deferred[0].reason,'chat_creation_not_authorized');
});
test('cross-chat lock refuses concurrent coordinator and never steals stale lock',async t=>{
  const f=setup(t), a=f.make(), b=f.make();
  await a.withLock(async()=>{await assert.rejects(b.withLock(async()=>{}),/EEXIST/);});
  fs.writeFileSync(path.join(f.root,'coordination.lock'),'{}');
  await assert.rejects(b.withLock(async()=>{}),/EEXIST/);
});
test('queued chat setup is not reported as ready thread',async t=>{
  const f=setup(t);f.requests[0].target='chat';f.native.create_thread=async()=>({clientThreadId:'pending',hostId:'local'});
  const r=await f.make().run(event,[f.requests[0]]);
  assert.equal(r.results[0].receipt.setupPending,true);
});
test('same ticket at different revisions gets distinct native task names',async t=>{
  const f=setup(t), h=f.make();
  const a={...f.requests[0],key:'a'.repeat(64),model:{id:'small'},target:'agent',sourceSnapshot:{source:'s',version:1}};
  await h.launch(a);
  await h.launch({...a,key:'b'.repeat(64),sourceSnapshot:{source:'s',version:2}});
  assert.notEqual(f.calls[0].task_name,f.calls[1].task_name);
});
test('receipt persistence failure preserves actual worker receipt on error',async t=>{
  const f=setup(t), h=f.make();
  const a={...f.requests[0],key:'a'.repeat(64),model:{id:'small'},target:'agent',sourceSnapshot:{source:'s',version:1}};
  const records=path.join(f.root,'records'), open=fs.openSync;
  t.mock.method(fs,'openSync',(file,...args)=>{
    if(String(file).startsWith(records+path.sep)) throw Error('simulated record storage failure');
    return open(file,...args);
  });
  await assert.rejects(h.launch(a),error=>{
    assert.equal(error.receipt.workerId,f.calls[0].task_name);
    assert.equal(error.receipt.requestedModel,'small');
    return true;
  });
});

test('queued setup requires authoritative mapping before source acknowledgement',async t=>{
  const f=setup(t);f.requests[0].target='chat';let ack=0;
  f.native.create_thread=async()=>({clientThreadId:'setup-1',hostId:'local'});
  f.source.ack=async()=>{ack++;};f.source.verifySetup=async()=>false;
  const h=f.make(),result=await h.run(event,[f.requests[0]]),r=result.results[0];
  const receipt={...r.receipt,workerId:'ready-1',reference:'chat:ready-1',setupPending:false};
  const ready={type:'ticket.changed',reference:'actual-setup-completed'};
  await assert.rejects(h.completeSetup(ready,r.key,receipt),/not verified/);assert.equal(ack,0);
  f.source.verifySetup=async(a,e,pending,final)=>pending.workerId==='setup-1'&&final.workerId==='ready-1';
  await h.completeSetup(ready,r.key,receipt);assert.equal(ack,1);
  const count=f.reports.length;
  assert.equal((await h.completeSetup(ready,r.key,receipt)).state,'already_setup');
  assert.equal(ack,1);assert.equal(f.reports.length,count);
  await h.reconcile({type:'execution.finished',reference:'actual-chat-terminal'},r.key,receipt);
  const terminalCount=f.reports.length;
  assert.equal((await h.completeSetup(ready,r.key,receipt)).state,'already_reconciled');
  assert.equal(ack,1);assert.equal(f.reports.length,terminalCount);
});

test('only explicit verified never-launched failure releases a reservation',async t=>{
  const f=setup(t);f.source.startSource=async()=>{throw Error('stale source');};
  const h=f.make(),result=await h.run(event,[f.requests[0]]),key=result.results[0].key;
  assert.equal(f.calls.length,0);const failed={type:'execution.failed',reference:'verified-source-refusal'};
  await assert.rejects(h.releaseUnstarted(failed,key),/unknown/);assert.equal(h.activeReservations().length,1);
  f.source.verifyNeverLaunched=async()=>true;
  await h.releaseUnstarted(failed,key);assert.equal(h.activeReservations().length,0);
});

test('aliases to a future output block readers until the original worker is verified terminal', async t => {
  const f = setup(t);
  f.policy.localResources = true;
  const shared = path.join(f.root, 'actual');
  const alias = path.join(f.root, 'alias');
  fs.mkdirSync(shared);
  fs.symlinkSync(shared, alias, 'junction');
  const [writer,reader,independent] = f.requests;
  writer.writes = [path.join(alias, 'new')];
  reader.reads = [path.join(shared, 'new', 'contract.txt')];
  reader.writes = [];
  independent.writes = [path.join(shared, 'independent')];
  const batch = await f.make().run(event, f.requests);
  assert.deepEqual(batch.results.map(row => row.ticket), [writer.ticket, independent.ticket]);
  assert.equal(batch.deferred[0].reason, 'resource_conflict');
  const started = batch.results[0];
  assert.equal(started.acceptance, writer.acceptance);
  assert.equal(started.owner, writer.owner);
  const restart = f.make();
  assert.equal((await restart.run(event, [reader])).deferred[0].reason, 'resource_conflict');
  await restart.reconcile({type:'execution.finished', reference:'verified'}, started.key, started.receipt);
  assert.equal((await restart.run(event, [reader])).results[0].state, 'running');
});

test('an unresolved requested path fails only that work order before reservation', async t => {
  const f = setup(t);
  f.policy.localResources = true;
  const [invalid, independent] = f.requests;
  const file = path.join(f.root, 'file');
  fs.writeFileSync(file, 'not a directory');
  invalid.writes = [path.join(file, 'child')];
  independent.writes = [path.join(f.root, 'other')];
  const host = f.make();
  const batch = await host.run(event, [invalid, independent]);
  assert.equal(batch.results.find(row => row.ticket === invalid.ticket).stage, 'resource_resolution');
  assert.equal(batch.results.find(row => row.ticket === independent.ticket).state, 'running');
  assert.deepEqual(host.activeReservations().map(row => row.ticket), [independent.ticket]);
});

test('a Windows drive root is refused for new work and retained in older reservations',
    {skip:process.platform !== 'win32'}, async t => {
  const f = setup(t);
  f.policy.localResources = true;
  const [writer, reader] = f.requests;
  const drive = path.parse(f.root).root;
  writer.writes = [drive];
  reader.reads = [f.root];
  reader.writes = [];
  const host = f.make();
  assert.equal((await host.run(event, [writer])).results[0].stage, 'resource_resolution');
  const old = {...writer, key:'c'.repeat(64), writes:[drive.slice(0, 2).toLowerCase()]};
  assert.equal(await host.reserve(old, event), true);
  assert.equal((await f.make().run(event, [reader])).deferred[0].reason, 'resource_conflict');
});

test('a persisted slash-normalized UNC share still blocks a child read',
    {skip:process.platform !== 'win32'}, async t => {
  const f = setup(t);
  f.policy.localResources = true;
  const [writer, reader] = f.requests;
  const share = '//fixture-server/share';
  const nativeShare = path.normalize(share + '/');
  // Only emulate access to the UNC filesystem; reservation and planning are real.
  const stat = fs.lstatSync;
  const realpath = fs.realpathSync.native;
  t.mock.method(fs, 'lstatSync', (file, ...args) => file.startsWith(nativeShare) ? {} : stat(file, ...args));
  t.mock.method(fs.realpathSync, 'native', (file, ...args) => file.startsWith(nativeShare) ? file : realpath(file, ...args));
  const host = f.make();
  assert.equal(await host.reserve({...writer, key:'d'.repeat(64), writes:[share+'/api']}, event), true);
  reader.reads = [share+'/api/interface'];
  reader.writes = [];
  assert.equal((await f.make().run(event, [reader])).deferred[0].reason, 'resource_conflict');
});
