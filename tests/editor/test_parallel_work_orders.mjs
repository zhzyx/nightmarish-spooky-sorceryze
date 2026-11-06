import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import crypto from 'node:crypto';
import {prepare,run as runHost} from '../../tools/godot_parallel/runner.mjs';
const run=(request,config,output)=>runHost(request,config,output,{report:async()=>({ok:true,state:'recorded_file',fixture:true})});
function fixture(t) {
  const base=fs.mkdtempSync(path.join(os.tmpdir(),'godot-parallel-'));
  t.after(()=>fs.rmSync(base,{recursive:true,force:true}));
  const root=path.join(base,'repo');fs.mkdirSync(root);
  const git=(...args)=>execFileSync('git',args,{cwd:root,stdio:'pipe'});
  git('init');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid');
  for (const file of ['customizations/components/issue-workorders/issue_gate.py','framework/tools/verify_framework.py']) {
    const p=path.join(root,file);fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,'process.exit(0)');
  }
  fs.writeFileSync(path.join(root,'CURRENT_FRAMEWORK.json'),'{}');fs.writeFileSync(path.join(root,'framework/package-lock.json'),'{}');
  git('add','.');git('commit','-m','Controlled fake host gate fixtures');
  const a=path.join(base,'a'),b=path.join(base,'b');
  git('worktree','add','-b','a',a);git('worktree','add','-b','b',b);
  const fake=path.join(base,'fake.mjs');
  fs.writeFileSync(fake,`import assert from 'node:assert/strict';
    import fs from 'node:fs';
    import path from 'node:path';
    import {setTimeout as delay} from 'node:timers/promises';
    assert.deepEqual(process.argv.slice(2), ['exec','--approve-for-me','--json','--ephemeral','--ignore-user-config','--model','fixture-model','-']);
    const base = ${JSON.stringify(base)};
    fs.writeFileSync(path.join(base,path.basename(process.cwd())+'.started'),'yes');
    const deadline = Date.now()+5000;
    while (!['a','b'].every(name=>fs.existsSync(path.join(base,name+'.started')))) {
      if (Date.now()>=deadline) throw Error('Second worker never started while first worker was alive');
      await delay(10);
    }
  `);
  const config={nativeWorkspaceWrite:true,authorityRef:'fixture-only',capacity:2,python:process.execPath,codex:fake,
    models:[{id:'fixture-model',targets:['agent'],available:true,capabilities:['coding']}],
    jobs:[{order:1,worktree:a,capabilities:['coding'],dependsOn:[]},{order:2,worktree:b,capabilities:['coding'],dependsOn:[]}]};
  const request={requestId:'fixture-request',issue:1,workspace:root,workers:[{id:1,order:1,prompt:'a'},{id:2,order:2,prompt:'b'}]};
  return {request,config,output:path.join(base,'receipt.json')};
}
test('real child processes overlap in isolated worktrees and retain exact model receipts',async t=>{
  const f=fixture(t);const r=await run(f.request,f.config,f.output);
  assert.deepEqual(r.workers.map(w=>w.state),['review','review'],r.workers.map(w=>w.reason).join('\n'));
  assert.ok(r.workers.every(w=>w.pid && w.workerBackend==='codex' && w.model==='fixture-model' && w.exitCode===0));
  const replay=await run(f.request,f.config,f.output);
  assert.deepEqual(replay.workers.map(w=>w.pid),r.workers.map(w=>w.pid));
  f.config.models=[];
  const unavailableReplay=await run(f.request,f.config,f.output);
  assert.deepEqual(unavailableReplay.workers.map(w=>[w.state,w.pid]),r.workers.map(w=>[w.state,w.pid]));
});
test('missing capability and shared workspace are rejected before launch',t=>{
  const f=fixture(t);f.config.jobs[0].capabilities=['vision'];
  assert.equal(prepare(f.request,f.config)[0].blocked,'blocked_model');
  f.config.jobs[0].capabilities=['coding'];f.config.jobs[1].worktree=f.config.jobs[0].worktree;
  assert.throws(()=>prepare(f.request,f.config),/Distinct/);
});
test('dependencies require actual acceptance and permission is explicit',t=>{
  const f=fixture(t);f.config.jobs[1].dependsOn=[1];
  assert.equal(prepare(f.request,f.config)[1].ready,false);
  f.config.nativeWorkspaceWrite=false;
  assert.throws(()=>prepare(f.request,f.config),/mandate/);
});

test('primary checkout and worktree subdirectories cannot impersonate workers',t=>{
  const f=fixture(t), primary=f.request.workspace;
  f.request.workspace=f.config.jobs[1].worktree;
  f.config.jobs[0].worktree=primary;
  assert.throws(()=>prepare(f.request,f.config),/primary/);
  const sub=path.join(f.request.workspace,'sub');fs.mkdirSync(sub);
  f.config.jobs[0].worktree=sub;
  assert.throws(()=>prepare(f.request,f.config),/subdirectories/);
});
test('model repair retries only the unstarted work order',async t=>{
  const f=fixture(t);fs.writeFileSync(f.config.codex,'console.log("fixture success")');
  f.config.jobs[0].capabilities=['vision'];
  let result=await run(f.request,f.config,f.output);
  assert.deepEqual(result.workers.map(w=>w.state),['blocked_model','review']);
  const secondPid=result.workers[1].pid;
  f.config.models[0].capabilities.push('vision');
  result=await run(f.request,f.config,f.output);
  assert.deepEqual(result.workers.map(w=>w.state),['review','review']);
  assert.equal(result.workers[1].pid,secondPid);
});
test('duplicate IDs and non-integer orders are rejected',t=>{
  const f=fixture(t);f.request.workers[1].id=1;
  assert.throws(()=>prepare(f.request,f.config),/duplicate/);
  f.request.workers[1].id=2;f.request.workers[1].order='../x';
  assert.throws(()=>prepare(f.request,f.config),/duplicate/);
});
test('missing durable reporting blocks model execution',async t=>{
  const f=fixture(t);
  const result=await runHost(f.request,f.config,f.output,{report:async()=>{throw Error('report offline');}});
  assert.ok(result.workers.every(w=>w.state==='blocked'&&!w.pid));
});
test('registered evidence unlocks dependency on a later explicit invocation',async t=>{
  const f=fixture(t);fs.writeFileSync(f.config.codex,'console.log("fixture success")');
  const base=path.dirname(f.output),source=path.join(base,'source');fs.mkdirSync(path.join(source,'.yuanheng'),{recursive:true});
  const task={id:'upstream',title:'upstream',goal:'goal',acceptance:['proof'],status:'open',owner:'reviewer',dependsOn:[]};
  const ledger=path.join(source,'.yuanheng/state.json');
  const save=()=>fs.writeFileSync(ledger,JSON.stringify({ledgerId:'ledger',tasks:[task],agents:[],events:[]}));save();
  f.config.registry=path.join(base,'registry.json');fs.writeFileSync(f.config.registry,JSON.stringify({sources:[{id:'source',root:'source'}]}));
  f.config.jobs[1].dependsOn=['ledger::upstream'];
  let result=await run(f.request,f.config,f.output);
  assert.equal(result.workers[1].state,'blocked_dependency');
  fs.writeFileSync(path.join(source,'proof.txt'),'proof');task.status='done';
  task.artifacts=[{path:'proof.txt',sha256:crypto.createHash('sha256').update('proof').digest('hex')}];
  task.review={verdict:'pass',criteria:[{met:true,evidence:'proof.txt'}]};save();
  result=await run(f.request,f.config,f.output);
  assert.equal(result.workers[1].state,'review');
});

function configureCommand(f) {
  const script = path.join(path.dirname(f.output), 'worker with spaces.mjs');
  fs.writeFileSync(script, `import fs from 'node:fs';
    const chunks = [];
    for await (const chunk of process.stdin) chunks.push(chunk);
    fs.writeFileSync('worker-result.json', JSON.stringify({
      args: process.argv.slice(2), cwd: process.cwd(), prompt: Buffer.concat(chunks).toString('utf8')
    }), {flag:'wx'});
  `);
  delete f.config.codex;
  f.config.workerCommand = {executable:process.execPath,args:[script,'--engine','{model}','a b;$HOME']};
}

test('command worker receives the selected model as one argument and bound prompt on stdin', async t => {
  const f = fixture(t);
  configureCommand(f);
  f.config.models[0].id = 'fixture-model/2';
  const events = [];
  const result = await runHost(f.request,f.config,f.output,{report: async event => {
    events.push(event);
    return {ok:true,state:'recorded_file'};
  }});
  for (const [index, worker] of result.workers.entries()) {
    assert.equal(worker.state,'review');
    assert.equal(worker.workerBackend,'command');
    assert.ok(worker.pid);
    const cwd = fs.realpathSync(f.config.jobs[index].worktree);
    const received = JSON.parse(fs.readFileSync(path.join(cwd,'worker-result.json'),'utf8'));
    assert.equal(received.cwd,cwd);
    assert.deepEqual(received.args,['--engine','fixture-model/2','a b;$HOME']);
    assert.match(received.prompt,/Do not merge, push, publish/);
    assert.ok(received.prompt.endsWith('\n'+f.request.workers[index].prompt));
  }
  assert.ok(events.length === 6 && events.every(event => event.workerBackend === 'command'));
  delete f.config.workerCommand;
  f.config.codex = path.join(path.dirname(f.output),'should-never-launch.mjs');
  const replay = await run(f.request,f.config,f.output);
  assert.deepEqual(replay.workers,result.workers);
});

test('command workers cannot bypass admission or use ambiguous model or executable configuration', async t => {
  const f = fixture(t);
  configureCommand(f);
  const command = f.config.workerCommand;
  for (const config of [
    {...f.config,codex:process.execPath},
    {...f.config,workerCommand:{...command,executable:'node'}},
    {...f.config,workerCommand:{...command,args:['--model']}},
    {...f.config,workerCommand:{...command,args:['{model}','{model}']}},
    {...f.config,workerCommand:null},
  ]) {
    assert.throws(() => prepare(f.request,config),/workerCommand/);
  }
  assert.throws(() => prepare(f.request,{...f.config,nativeWorkspaceWrite:false}),/mandate/);
  const gate = path.join(f.config.jobs[0].worktree,'customizations/components/issue-workorders/issue_gate.py');
  fs.writeFileSync(gate,'process.exit(1)');
  const result = await run(f.request,f.config,f.output);
  assert.equal(result.workers[0].state,'blocked');
  assert.equal(result.workers[0].pid,undefined);
  assert.equal(fs.existsSync(path.join(f.config.jobs[0].worktree,'worker-result.json')),false);
  assert.equal(result.workers[1].state,'review');
  fs.writeFileSync(gate,'process.exit(0)');
  const retry = await run(f.request,f.config,f.output);
  assert.deepEqual(retry.workers.map(w => w.state),['review','review']);
  assert.equal(retry.workers[1].pid,result.workers[1].pid);
});

test('child exit before prompt handoff retains an unknown work order',async t=>{
  const f=fixture(t);
  fs.writeFileSync(f.config.codex,'process.exit(0)');
  f.request.workers=f.request.workers.slice(0,1);
  const result=await runHost(f.request,f.config,f.output,{report:async record=>{
    if(record.state==='running') await new Promise(resolve=>setTimeout(resolve,400));
    return {ok:true,state:'recorded_file'};
  }});
  assert.equal(result.workers[0].state,'reconcile_required');
});
