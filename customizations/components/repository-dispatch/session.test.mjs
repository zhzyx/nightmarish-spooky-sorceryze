import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {repositoryWorker, advance} from './session.mjs';

test('backfill intake failure preserves the original verified release', async () => {
  const events = [];
  const host = {reconcile:async()=>{events.push('released');return {state:'released'};},
    run:async()=>assert.fail('work started after failed intake')};
  const intake = async()=>{events.push('intake');throw Error('backfill issue closed');};
  const config = {requests:[{ticket:'backfill'}],event:{type:'execution.finished',reference:'actual'}};
  await assert.rejects(advance({...config,action:'reconcile'},host,{},intake),/issue closed/);
  assert.deepEqual(events,['released','intake']);
  events.length = 0;
  await assert.rejects(advance(config,host,{},intake),/issue closed/);
  assert.deepEqual(events,['intake']);
});

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

test('real bootstrap and intake share selected CLI in an isolated installed dispatch checkout',async t=>{
  const {execFileSync}=await import('node:child_process');
  const {fileURLToPath,pathToFileURL}=await import('node:url');
  const dir=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'dispatch-install-')));
  t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const source=fileURLToPath(new URL('../../../',import.meta.url));
  const copied=new Set();
  function copyModule(relative) {
    if(copied.has(relative))return;
    copied.add(relative);
    const content=fs.readFileSync(path.join(source,relative),'utf8');
    fs.mkdirSync(path.dirname(path.join(dir,relative)),{recursive:true});
    fs.writeFileSync(path.join(dir,relative),content);
    for(const [,specifier] of content.matchAll(/from\s+['"]([^'"]+)['"]/g))if(specifier.startsWith('.'))copyModule(path.normalize(path.join(path.dirname(relative),specifier)));
  }
  const entry='customizations/components/repository-dispatch/session.mjs';copyModule(entry);
  for(const name of ['github_runtime.py','github_runtime_bridge.py'])fs.copyFileSync(path.join(source,'customizations/components/issue-workorders',name),path.join(dir,'customizations/components/issue-workorders',name));
  execFileSync('git',['init','-q',dir]);
  fs.mkdirSync(path.join(dir,'.github'));
  fs.writeFileSync(path.join(dir,'.github/labels.json'),JSON.stringify([{name:'type:test'}]));
  fs.writeFileSync(path.join(dir,'work-items.json'),JSON.stringify({repository:'test/repo',tenant_id:'gonggong-workspace'}));
  const issue={number:1,issue_dependencies_summary:{total_blocked_by:0},html_url:'https://github.com/test/repo/issues/1',title:'closed fixture',state:'closed',updated_at:'2026-11-05T00:00:00Z',body:'<!-- gonggong-request:fixture -->',labels:['workspace:gonggong','type:test','status:done'].map(name=>({name})),assignees:[]};
  fs.writeFileSync(path.join(dir,'api'),`const fs=require('node:fs');fs.appendFileSync('cli-log.jsonl',JSON.stringify({gh:process.env.GONGGONG_GH,args:process.argv.slice(2)})+'\\n');
    if(process.argv[2]==='user')console.log('operator');
    else if(process.argv[2]==='graphql')console.log(JSON.stringify({data:{viewer:{login:'operator'},repository:{nameWithOwner:'test/repo',viewerPermission:'WRITE'}}}));
    else console.log(${JSON.stringify(JSON.stringify(issue))});`);
  // Only this isolated host's gate is a transport probe. Production gate and
  // permissions/ownership behavior have their own real regression suites.
  fs.writeFileSync(path.join(dir,'customizations/components/issue-workorders/issue_gate.py'),`import json,os,pathlib\npathlib.Path('intake-env.json').write_text(json.dumps({'gh':os.environ['GONGGONG_GH']}))\n`);
  const python=process.env.GONGGONG_PYTHON || (process.platform==='win32'?'python':'python3');
  const env={...process.env,GONGGONG_GH:process.execPath,GONGGONG_PYTHON:python};
  const inspected=JSON.parse(execFileSync(process.execPath,[path.join(dir,entry),'inspect','1','fixture'],{cwd:dir,env,encoding:'utf8'}));
  assert.equal(inspected.item.key,'github:test/repo#1');
  const config={workspace:dir,python,gh:process.execPath,repository:'test/repo',operator:'operator',authorityRef:'fixture',capacity:1,defaultChatModel:'framework-integrity',
    catalog:[{id:'framework-integrity',available:true,targets:['agent'],capabilities:['framework-integrity']}],bindings:[{number:1,requestId:'fixture'}],
    requests:[{ticket:'github:test/repo#1',authorityRef:'fixture',owner:'operator',target:'agent',model:'framework-integrity',capabilities:['framework-integrity'],reads:[dir],writes:[],outcome:'fixture',acceptance:'fixture',contextRefs:[]}],
    workers:{'github:test/repo#1':{kind:'framework-integrity'}},event:{type:'user.requested',reference:'fixture'}};
  // runEvent inherits the test cwd, so use a child with the actual bound checkout.
  const code=`import {runEvent} from ${JSON.stringify(pathToFileURL(path.join(dir,entry)).href)};console.log(JSON.stringify(await runEvent(${JSON.stringify(config)})));`;
  const result=JSON.parse(execFileSync(process.execPath,['--input-type=module','-e',code],{cwd:dir,env:{...env,GONGGONG_GH:path.join(dir,'invalid-environment-choice')},encoding:'utf8'}));
  assert.equal(result.results.length,0);
  assert.equal(result.deferred.length,1);
  assert.equal(JSON.parse(fs.readFileSync(path.join(dir,'intake-env.json'))).gh,process.execPath);
  const logs=fs.readFileSync(path.join(dir,'cli-log.jsonl'),'utf8').trim().split('\n').map(JSON.parse);
  assert.ok(logs.some(row=>row.args[0]==='user'));
  assert.ok(logs.some(row=>row.args[0]==='graphql'));
  assert.ok(logs.every(row=>row.gh===process.execPath));
  assert.equal(fs.readdirSync(path.join(dir,'data-collection/receipts/codex-dispatch/sources')).some(name=>name.endsWith('.claim.json')),false);
});
