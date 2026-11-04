import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {OperatorRuntime} from './operator.mjs';
import {NativeToolBridge} from './native-bridge.mjs';
import {issueSnapshot} from '../issue-workorders/github_source.mjs';
function setup(t) {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'sinan-operator-'));
  t.after(()=>{assert.ok(root.startsWith(path.join(os.tmpdir(),'sinan-operator-')));fs.rmSync(root,{recursive:true,force:true});});
  const issue={number:1,html_url:'https://github.com/test/repo/issues/1',title:'work',state:'open',updated_at:'2026-11-05T00:00:00Z',body:'<!-- gonggong-request:work -->',labels:['workspace:gonggong','type:development','status:in-progress'].map(name=>({name})),assignees:[]};
  const binding={number:1,requestId:'work'};
  const options={root:path.join(root,'sources'),repository:'test/repo',bindings:[binding],readIssue:async()=>issue,allowedCategories:['type:development'],operator:'actual-fixture-operator',catalog:[],capacity:2,authorityRef:'fixture-only',authorize:async()=>true,report:async()=>{},verifyWorker:async()=>true};
  const a={ticket:'github:test/repo#1',key:'a'.repeat(64),sourceSnapshot:issueSnapshot('test/repo',binding,issue,options.allowedCategories).sourceSnapshot,model:{id:'model'},target:'agent',reads:[],writes:[]};
  return {root,issue,options,a,runtime:new OperatorRuntime(options)};
}
test('two independent processes cannot claim the same source',async t=>{
  const f=setup(t),module=new URL('./operator.mjs',import.meta.url).href;
  const code=`import {OperatorRuntime} from ${JSON.stringify(module)};const o=${JSON.stringify({...f.options,readIssue:undefined,authorize:undefined,report:undefined,verifyWorker:undefined})};o.readIssue=async()=>(${JSON.stringify(f.issue)});o.authorize=async()=>true;o.report=async()=>{};o.verifyWorker=async()=>true;try{await new OperatorRuntime(o).compareAndStart(${JSON.stringify(f.a)});console.log('claimed')}catch(e){console.log('rejected')}`;
  const run=()=>new Promise((resolve,reject)=>{const c=spawn(process.execPath,['--input-type=module','-'],{windowsHide:true});let s='',err='';c.stdout.on('data',d=>s+=d);c.stderr.on('data',d=>err+=d);c.on('error',reject);c.on('close',code=>code?reject(Error(err)):resolve(s.trim()));c.stdin.end(code);});
  assert.deepEqual((await Promise.all([run(),run()])).sort(),['claimed','rejected']);
  assert.equal(new OperatorRuntime(f.options).active().length,1);
});
test('stale source is refused under claim lock and before native launch',async t=>{
  const f=setup(t);f.issue.title='changed';
  await assert.rejects(f.runtime.compareAndStart(f.a),/revision/);assert.equal(f.runtime.active().length,0);
  f.issue.title='work';await f.runtime.compareAndStart(f.a);f.issue.title='changed again';
  await assert.rejects(f.runtime.beforeLaunch(f.a),/changed before/);
});
test('worker, reservation and terminal receipt must match exactly',async t=>{
  const f=setup(t),receipt={workerId:'real-worker',reference:'native:receipt',model:'model',target:'agent'};
  await f.runtime.compareAndStart(f.a);await f.runtime.ack(f.a,receipt);
  const event={type:'execution.finished',reference:'actual-terminal'};
  assert.equal(await f.runtime.verifyTerminal(f.a,event,{...receipt,workerId:'other'}),false);
  assert.equal(await f.runtime.verifyTerminal(f.a,event,receipt),true);assert.equal(f.runtime.active().length,0);
  await assert.rejects(f.runtime.compareAndStart(f.a),/claimed/);
});
test('verified never-launched can release, but any native intent remains unknown',async t=>{
  const f=setup(t),bridge=new NativeToolBridge(path.join(f.root,'native'),'fixture-only');
  t.after(()=>bridge.close());
  await f.runtime.compareAndStart(f.a);
  assert.equal(await f.runtime.verifyNeverLaunched(f.a,{},bridge.root),true);
  const b={...f.a,key:'b'.repeat(64)};await f.runtime.compareAndStart(b);
  const pending=bridge.request('spawn_agent',{task_name:'worker'},{assignmentKey:b.key});
  const id=fs.readdirSync(bridge.root).find(n=>n.endsWith('.request.json')).split('.')[0];
  bridge.take(id);
  assert.equal(await f.runtime.verifyNeverLaunched(b,{},bridge.root),false);
  bridge.respond(id,{task_name:'worker'},'fixture-native-return');await pending;
});
test('native bridge persists intent, binds receipt and refuses issuing twice',async t=>{
  const f=setup(t),b=new NativeToolBridge(path.join(f.root,'native'),'fixture-only');
  t.after(()=>b.close());
  const pending=b.request('spawn_agent',{task_name:'worker',model:'model'},{assignmentKey:f.a.key});
  const id=fs.readdirSync(b.root).find(n=>n.endsWith('.request.json')).split('.')[0];
  assert.equal(b.take(id).args.model,'model');assert.throws(()=>b.take(id),/EEXIST/);
  b.respond(id,{task_name:'worker'},'fixture-native-return');assert.equal((await pending).task_name,'worker');
});
test('dependency closure without host acceptance proof is not readiness',async t=>{
  const f=setup(t);assert.equal(await f.runtime.assess({key:f.a.ticket,dependsOn:['dependency']},f.a.sourceSnapshot,{}),false);
});

test('launch intent and never-launched verification share the source lock',async t=>{
  const f=setup(t),bridge=new NativeToolBridge(path.join(f.root,'native'),'fixture-only');
  await f.runtime.compareAndStart(f.a);
  let entered,release;const started=new Promise(r=>entered=r),wait=new Promise(r=>release=r);
  f.runtime.readIssue=async()=>{entered();await wait;return f.issue;};
  const launch=f.runtime.beforeLaunch(f.a);await started;
  await assert.rejects(f.runtime.verifyNeverLaunched(f.a,{},bridge.root),/EEXIST/);
  release();await launch;
  assert.equal(await f.runtime.verifyNeverLaunched(f.a,{},bridge.root),false);
});

test('a verified unstarted terminal prevents a delayed original launch',async t=>{
  const f=setup(t),bridge=new NativeToolBridge(path.join(f.root,'native'),'fixture-only');
  await f.runtime.compareAndStart(f.a);await f.runtime.verifyNeverLaunched(f.a,{},bridge.root);
  await assert.rejects(f.runtime.beforeLaunch(f.a),/terminal/);
});
