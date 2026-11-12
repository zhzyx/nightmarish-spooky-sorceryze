import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {execFileSync, spawn} from 'node:child_process';
import {openSession, OperatorRuntime} from './operator.mjs';
import {NativeToolBridge} from './native-bridge.mjs';
import {issueSnapshot} from '../issue-workorders/github_source.mjs';
function setup(t) {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'sinan-operator-'));
  t.after(()=>{assert.ok(root.startsWith(path.join(os.tmpdir(),'sinan-operator-')));fs.rmSync(root,{recursive:true,force:true});});
  const issue={number:1,issue_dependencies_summary:{total_blocked_by:0},html_url:'https://github.com/test/repo/issues/1',title:'work',state:'open',updated_at:'2026-11-05T00:00:00Z',body:'<!-- gonggong-request:work -->',labels:['workspace:gonggong','type:development','status:in-progress'].map(name=>({name})),assignees:[]};
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

test('native session rechecks effective write permission and can reconcile an existing worker after revocation', async t => {
  const fixture = setup(t);
  const workspace = fixture.root;
  const operator = 'new-writer';
  const repository = fixture.options.repository;
  const save = (file, data) => fs.writeFileSync(path.join(workspace,file),JSON.stringify(data));
  execFileSync('git',['init','-q',workspace]);
  fs.mkdirSync(path.join(workspace,'.github'));
  save('.github/labels.json',[{name:'type:development'}]);
  save('work-items.json',{tenant_id:'gonggong-workspace',repository});
  save('issue.json',fixture.issue);
  fs.writeFileSync(path.join(workspace,'api'), `
    const fs = require('node:fs');
    if (process.argv[2] === 'graphql') {
      console.log(fs.readFileSync('viewer.json','utf8'));
    } else if (process.argv[2] === 'repos/test/repo/issues/1') {
      console.log(fs.readFileSync('issue.json','utf8'));
    } else process.exit(1);
  `);
  const setPermission = (permission,login=operator) => save('viewer.json',{data:{viewer:{login},
    repository:{nameWithOwner:repository,viewerPermission:permission}}});
  const config = {...fixture.options,workspace,operator,python:process.env.GONGGONG_PYTHON || (process.platform === 'win32' ? 'python' : 'python3'),gh:process.execPath,defaultChatModel:'model',
    requests:[{ticket:fixture.a.ticket,authorityRef:fixture.options.authorityRef}]};
  setPermission('READ');
  await assert.rejects(openSession(config),/write permission/);
  setPermission('WRITE');
  const {host,runtime,bridge} = await openSession(config);
  t.after(()=>bridge.close());
  runtime.checkAuthority = async () => true;
  fixture.a.target = 'chat';
  await host.reserve(fixture.a,{type:'request.created',reference:'fixture'});
  await runtime.compareAndStart(fixture.a);
  setPermission('READ');
  await assert.rejects(host.launch(fixture.a), /write permission/);
  assert.equal(fs.existsSync(runtime.file(fixture.a.ticket,'launch-intent',fixture.a.key)),false);
  assert.deepEqual(fs.readdirSync(bridge.root),[]);

  setPermission('WRITE');
  await runtime.beforeLaunch(fixture.a);
  const receipt = {workerId:'existing',reference:'chat:existing',model:'model',target:'chat',setupPending:false};
  await runtime.ack(fixture.a,receipt);
  const records = path.join(host.root,'records');
  fs.writeFileSync(path.join(records,'pending.json'), JSON.stringify({assignment:fixture.a,
    receipt:{...receipt,workerId:'pending',setupPending:true}}));
  const other = 'another-user';
  setPermission('READ',other);
  const foreign = await openSession({...config,operator:other,action:'reconcile'},{
    verifySetup:async()=>assert.fail('foreign setup verification reached'),
    verifyWorker:async()=>assert.fail('foreign terminal verification reached')});
  t.after(()=>foreign.bridge.close());
  const event = {type:'execution.finished',reference:'terminal'};
  await assert.rejects(foreign.host.reconcile(event,fixture.a.key,receipt), /write permission/);
  await assert.rejects(foreign.host.completeSetup({type:'ticket.changed',reference:'setup'},fixture.a.key,receipt),/write permission/);
  await assert.rejects(foreign.host.releaseUnstarted({type:'execution.failed',reference:'unstarted'},fixture.a.key),/write permission/);
  setPermission('WRITE',other);
  await assert.rejects(foreign.host.reconcile(event,fixture.a.key,receipt), /handoff/);
  assert.deepEqual(fs.readdirSync(records),['pending.json']);
  assert.deepEqual(fs.readdirSync(path.join(host.root,'released')),[]);
  assert.deepEqual(fs.readdirSync(foreign.bridge.root),[]);
  assert.equal(fs.existsSync(runtime.file(fixture.a.ticket,'terminal',fixture.a.key)),false);
  const legacy = {...fixture.a,key:'c'.repeat(64)};
  fs.writeFileSync(runtime.file(legacy.ticket,'claim',legacy.key),JSON.stringify({assignment:legacy}));
  await assert.rejects(foreign.runtime.verifyClaimOwner(legacy), /handoff/);
  const handoff = await openSession({...config,operator:other,action:'reconcile'},{
    verifyRecoveryHandoff:async(a,previous,actor)=> a.key === legacy.key && previous === null && actor === other});
  t.after(()=>handoff.bridge.close());
  await handoff.runtime.verifyClaimOwner(legacy);
  setPermission('READ',other);
  await assert.rejects(handoff.runtime.verifyClaimOwner(legacy), /write permission/);
  setPermission('READ');
  const resumed = await openSession({...config,action:'reconcile'},{verifyWorker:async()=>true});
  t.after(()=>resumed.bridge.close());
  assert.equal(await resumed.runtime.verifyTerminal(fixture.a,{type:'execution.finished',reference:'terminal'},receipt),true);
  await assert.rejects(resumed.host.run({type:'execution.finished',reference:'terminal'},config.requests),/write permission/);
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

test('GUI PATH environment selection reaches authenticated openSession and real installed reporting',async t=>{
  const f=setup(t), workspace=f.root;
  execFileSync('git',['init','-q',workspace]);
  fs.mkdirSync(path.join(workspace,'.github'));
  fs.writeFileSync(path.join(workspace,'.github/labels.json'),JSON.stringify([{name:'type:development'}]));
  fs.writeFileSync(path.join(workspace,'work-items.json'),JSON.stringify({tenant_id:'gonggong-workspace',repository:'test/repo'}));
  fs.writeFileSync(path.join(workspace,'api'),`console.log(JSON.stringify({data:{viewer:{login:'operator'},repository:{nameWithOwner:'test/repo',viewerPermission:'WRITE'}}}));`);
  fs.mkdirSync(path.join(workspace,'gonggong-diting-data'));
  fs.writeFileSync(path.join(workspace,'gonggong-diting-data/dataset.json'),JSON.stringify({schema_version:1,name:'gonggong-diting-data',origin_framework:'gonggong',dataset_id:'00000000-0000-4000-8000-000000000001'}));
  const malicious=path.join(workspace,'customizations/components/godot-host');fs.mkdirSync(malicious,{recursive:true});
  const marker=path.join(workspace,'project-code-executed');
  fs.writeFileSync(path.join(malicious,'bridge.py'),`open(${JSON.stringify(marker)},'w').write('bad')\nraise RuntimeError('target bridge executed')`);
  const python=execFileSync(process.env.GONGGONG_PYTHON || (process.platform==='win32'?'python':'python3'),
    ['-c','import sys; print(sys.executable)'],{encoding:'utf8'}).trim();
  const config={...f.options,workspace,operator:'operator',defaultChatModel:'model',python,requests:[]};
  const code=`import {openSession} from ${JSON.stringify(new URL('./operator.mjs',import.meta.url).href)};
    const c=${JSON.stringify(config)};const s=await openSession(c);
    try {const report=await s.runtime.report({state:'fixture',assignment:{ticket:'github:test/repo#1'}});
      console.log(JSON.stringify({gh:s.github.gh,report,active:s.runtime.active().length}));}finally{s.bridge.close();}`;
  // Child-only GUI-like PATH: never alter this test runner's or user's environment.
  const env={...process.env,GONGGONG_GH:process.execPath,PATH:process.platform==='win32'?path.dirname(execFileSync('where',['git'],{encoding:'utf8'}).trim().split('\r\n')[0])+';'+process.env.SystemRoot+'/System32':'/usr/bin:/bin'};
  const result=JSON.parse(execFileSync(process.execPath,['--input-type=module','-e',code],{cwd:workspace,env,encoding:'utf8'}));
  assert.equal(result.gh,process.execPath);
  assert.equal(result.report.ok,true);
  assert.equal(result.report.state,'recorded_file');
  assert.equal(result.report.receipts.length,1);
  assert.equal(result.active,0);
  assert.equal(fs.existsSync(marker),false);
});
