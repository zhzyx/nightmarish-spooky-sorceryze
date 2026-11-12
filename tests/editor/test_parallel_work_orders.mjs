import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {captureCandidate} from '../../customizations/components/repository-dispatch/acceptance-candidate.mjs';
import {prepare,run as runHost} from '../../tools/godot_parallel/runner.mjs';
const denied = new Set();
// Controlled host authority boundary, never a candidate-supplied executable.
const verify = (python,args,cwd) => {
  assert.ok(fs.existsSync(python), 'Host runtime missing');
  const installation=fileURLToPath(new URL('../../',import.meta.url));
  assert.ok(args[0].startsWith(installation), 'Only installed host code may verify');
  assert.ok(fs.existsSync(args[0]));
  if(args[0].endsWith('issue_gate.py')) {
    assert.equal(args[2],cwd);
    if(denied.has(cwd))throw Error('Controlled authority denied');
  } else assert.equal(fs.realpathSync(cwd),fs.realpathSync(installation));
};
const run=(request,config,output)=>runHost(request,config,output,{verify,report:async()=>({ok:true,state:'recorded_file',fixture:true})});

// Only Issue transport/reporting is controlled here. Both installed framework
// checks execute real Python; the worker marker proves admission precedes spawn.
for (const mutation of ['game', 'unchanged', 'file', 'pointer', 'lock', 'delete', 'committed-delete', 'base-only-delete']) {
  test(`installed runner candidate admission: ${mutation}`, async t => {
    const f = fixture(t, 1);
    const installation = fileURLToPath(new URL('../../', import.meta.url));
    const cwd = f.config.jobs[0].worktree;
    const base = path.dirname(f.output);
    const python = process.env.GONGGONG_PYTHON || execFileSync(process.platform === 'win32' ? 'py' : 'python3',
      ['-c', 'import sys; print(sys.executable)'], {encoding:'utf8'}).trim();
    f.config.python = python;
    const git = (...args) => execFileSync('git', args, {cwd, stdio:'pipe'});
    git('config', 'core.autocrlf', 'false');
    if (mutation !== 'game') {
      fs.cpSync(path.join(installation, 'framework'), path.join(cwd, 'framework'), {recursive:true});
      fs.copyFileSync(path.join(installation, 'CURRENT_FRAMEWORK.json'), path.join(cwd, 'CURRENT_FRAMEWORK.json'));
      git('add', 'framework', 'CURRENT_FRAMEWORK.json');
      git('commit', '-m', 'Exact installed framework fixture');
      if (mutation === 'file') fs.appendFileSync(path.join(cwd, 'framework/tools/verify_framework.py'),
        `\nfrom pathlib import Path\nPath(${JSON.stringify(path.join(base,'candidate-validator-ran')).replaceAll('\\\\','/')}).write_text('unsafe')\n`);
      if (mutation === 'pointer') fs.writeFileSync(path.join(cwd,'CURRENT_FRAMEWORK.json'), '{"root":"elsewhere"}');
      if (mutation === 'lock') fs.writeFileSync(path.join(cwd,'framework/package-lock.json'), '{}');
      if (mutation.includes('delete')) {
        if (mutation === 'base-only-delete') git('update-ref','refs/remotes/origin/main','HEAD');
        git('rm','-r','framework','CURRENT_FRAMEWORK.json');
        if (mutation === 'committed-delete') git('commit','-m','Remove framework');
        if (mutation === 'base-only-delete') {
          // HEAD has no framework ancestry, but the fetched target owns it.
          git('reset','--hard','HEAD~1');
        }
      }
    }
    const checks = [];
    const actualVerify = (executable, args, directory) => {
      verify(executable, args, directory);
      if (args.includes('--intake-only')) return;
      try {
        execFileSync(executable, args, {cwd:directory, encoding:'utf8', stdio:'pipe'});
        checks.push({candidate:args.includes('--candidate-framework-only'), ok:true});
      } catch (error) {
        checks.push({candidate:args.includes('--candidate-framework-only'), ok:false, status:error.status, stderr:String(error.stderr)});
        throw error;
      }
    };
    const result = await runHost(f.request,f.config,f.output,{verify:actualVerify,report:async()=>({ok:true,state:'recorded_file',fixture:true})});
    const worker = result.workers[0];
    const admitted = ['game','unchanged'].includes(mutation);
    assert.equal(worker.state,admitted?'review':'blocked',worker.reason);
    assert.equal(fs.existsSync(path.join(base,'a.started')),admitted);
    assert.equal(fs.existsSync(path.join(base,'candidate-validator-ran')),false);
    assert.equal(checks.filter(check=>check.candidate).length,1,'Actual installed candidate check must execute');
    const checked = checks.find(check=>check.candidate);
    assert.equal(checked.ok,admitted);
    if (!admitted) {
      assert.equal(checked.status,1);
      assert.match(checked.stderr,/Candidate framework (differs|binding differs)/);
      assert.equal(worker.pid,undefined);
      assert.equal(worker.registration,undefined);
      assert.equal(fs.existsSync(`${f.output}.1.log`),false);
    }
  });
}
function fixture(t, count=2) {
  const base=fs.mkdtempSync(path.join(os.tmpdir(),'godot-parallel-'));
  t.after(()=>fs.rmSync(base,{recursive:true,force:true,maxRetries:5,retryDelay:100}));
  const root=path.join(base,'repo');fs.mkdirSync(root);
  const git=(...args)=>execFileSync('git',args,{cwd:root,stdio:'pipe'});
  git('init');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid');
  fs.writeFileSync(path.join(root,'project.godot'),'config_version=5\n');
  git('add','.');git('commit','-m','Controlled fake host gate fixtures');
  const names=Array.from({length:count},(_,i)=>String.fromCharCode(97+i));
  const worktrees=names.map(name=>path.join(base,name));
  names.forEach((name,i)=>git('worktree','add','-b',name,worktrees[i]));
  const fake=path.join(base,'fake.mjs');
  fs.writeFileSync(fake,`import assert from 'node:assert/strict';
    import fs from 'node:fs';
    import path from 'node:path';
    import {setTimeout as delay} from 'node:timers/promises';
    assert.deepEqual(process.argv.slice(2), ['exec','--approve-for-me','--json','--ephemeral','--ignore-user-config','--model','fixture-model','-']);
    const base = ${JSON.stringify(base)};
    fs.writeFileSync(path.join(base,path.basename(process.cwd())+'.started'),'yes');
    const deadline = Date.now()+5000;
    while (!${JSON.stringify(names)}.every(name=>fs.existsSync(path.join(base,name+'.started')))) {
      if (Date.now()>=deadline) throw Error('Second worker never started while first worker was alive');
      await delay(10);
    }
  `);
  const config={nativeWorkspaceWrite:true,authorityRef:'fixture-only',capacity:count,python:process.execPath,codex:fake,
    models:[{id:'fixture-model',targets:['agent'],available:true,capabilities:['coding']}],
    jobs:worktrees.map((worktree,i)=>({order:i+1,worktree,capabilities:['coding'],dependsOn:[]}))};
  const request={requestId:'fixture-request',issue:1,workspace:root,workers:names.map((prompt,i)=>({id:i+1,order:i+1,prompt}))};
  return {request,config,output:path.join(base,'receipt.json')};
}

test('three authorized slots run three isolated workers concurrently',async t=>{
  const f=fixture(t,3);
  const result=await run(f.request,f.config,f.output);
  assert.deepEqual(result.workers.map(worker=>worker.state),['review','review','review']);
  assert.equal(new Set(result.workers.map(worker=>worker.pid)).size,3);
});

test('native host editor bytes reach the actual worker and immutable registration', async t => {
  const f = fixture(t, 1);
  const sha256 = crypto.createHash('sha256').update(fs.readFileSync(process.execPath)).digest('hex');
  f.request.editorRuntime = {executable:process.execPath, sha256};
  fs.writeFileSync(f.config.codex, `import fs from 'node:fs';
    let prompt=''; for await (const chunk of process.stdin) prompt+=chunk;
    fs.writeFileSync('observed-prompt.txt', prompt);
  `);
  const result = await run(f.request, f.config, f.output);
  assert.equal(result.workers[0].state, 'review', result.workers[0].reason);
  const prompt = fs.readFileSync(path.join(f.config.jobs[0].worktree, 'observed-prompt.txt'), 'utf8');
  const expected = {executable:fs.realpathSync(process.execPath), sha256};
  assert.ok(prompt.includes(JSON.stringify(expected)));
  assert.ok(prompt.includes('--headless --audio-driver Dummy'));
  const registration = JSON.parse(fs.readFileSync(result.workers[0].registration.path, 'utf8'));
  assert.deepEqual(registration.editor_runtime, expected);
});

test('editor runtime drift before launch blocks the actual worker', async t => {
  const f = fixture(t, 1);
  const executable = path.join(path.dirname(f.output), 'bound-editor');
  fs.writeFileSync(executable, 'original-host-editor');
  f.request.editorRuntime = {executable, sha256:crypto.createHash('sha256').update(fs.readFileSync(executable)).digest('hex')};
  const result = await runHost(f.request, f.config, f.output, {verify, report:async record => {
    if (record.state === 'prepared') fs.writeFileSync(executable, 'changed-host-editor');
    return {ok:true, state:'recorded_file', fixture:true};
  }});
  assert.equal(result.workers[0].state, 'blocked');
  assert.match(result.workers[0].reason, /editor runtime is missing or changed/);
  assert.equal(result.workers[0].pid, undefined);
  assert.equal(fs.existsSync(path.join(path.dirname(f.output), 'a.started')), false);
});

test('large valid capacity allocates only the ready workers',async t=>{
  const f=fixture(t);
  f.config.capacity=Number.MAX_SAFE_INTEGER;
  const result=await run(f.request,f.config,f.output);
  assert.deepEqual(result.workers.map(worker=>worker.state),['review','review']);
});

test('invalid host capacities are rejected before dispatch',t=>{
  const f=fixture(t);
  for(const capacity of [0,-1,1.5,Infinity,Number.MAX_SAFE_INTEGER+1]) {
    assert.throws(()=>prepare(f.request,{...f.config,capacity}),/capacity/);
  }
});
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

test('real worker registration and immutable terminal bind identity, candidate bytes and replay',async t=>{
  const f=fixture(t);configureCommand(f);
  f.config.jobs[0].workerId='actual-ledger-assignment';
  const result=await run(f.request,f.config,f.output);
  for(const [index,worker] of result.workers.entries()) {
    assert.equal(worker.state,'review');assert.equal(worker.transport_completed,true);
    const registrationBytes=fs.readFileSync(worker.registration.path);
    const terminalBytes=fs.readFileSync(worker.terminal_receipt.path);
    assert.equal(crypto.createHash('sha256').update(registrationBytes).digest('hex'),worker.registration.sha256);
    assert.equal(crypto.createHash('sha256').update(terminalBytes).digest('hex'),worker.terminal_receipt.sha256);
    const registration=JSON.parse(registrationBytes),terminal=JSON.parse(terminalBytes);
    assert.equal(registration.candidate.root,fs.realpathSync(f.config.jobs[index].worktree));
    assert.equal(registration.execution_id,worker.execution_id);
    assert.equal(terminal.execution_id,registration.execution_id);
    assert.equal(terminal.pid,worker.pid);assert.equal(terminal.business_accepted,null);
    assert.equal(terminal.transport_completed,true);assert.equal(terminal.exit_code,0);
    assert.ok(terminal.candidate.files.some(item=>item.path==='worker-result.json'&&item.sha256));
    assert.equal(terminal.candidate.files_sha256,crypto.createHash('sha256').update(JSON.stringify(terminal.candidate.files)).digest('hex'));
    assert.equal(Object.hasOwn(terminal,'conversation_id'),false);
  }
  assert.equal(result.workers[0].worker_id,'actual-ledger-assignment');
  const replay=await run(f.request,f.config,f.output);
  assert.deepEqual(replay.workers,result.workers);
  fs.appendFileSync(result.workers[0].terminal_receipt.path,' ');
  const tampered=await run(f.request,f.config,f.output);
  assert.equal(tampered.workers[0].state,'reconcile_required');
  assert.match(tampered.workers[0].reason,/terminal receipt changed/);
  assert.equal(tampered.workers[0].pid,result.workers[0].pid);
});

test('failed process retains a false transport result and original execution receipt',async t=>{
  const f=fixture(t);fs.writeFileSync(f.config.codex,'process.exit(7)');
  const result=await run(f.request,f.config,f.output);
  for(const worker of result.workers) {
    assert.equal(worker.state,'reconcile_required');assert.equal(worker.transport_completed,false);
    const terminal=JSON.parse(fs.readFileSync(worker.terminal_receipt.path));
    assert.equal(terminal.transport_completed,false);assert.equal(terminal.exit_code,7);
  }
});

test('changed configured worker identity never adopts a prior successful execution',async t=>{
  const f=fixture(t);configureCommand(f);
  const result=await run(f.request,f.config,f.output);
  f.config.jobs[0].workerId='a-different-owner';
  const replay=await run(f.request,f.config,f.output);
  assert.equal(replay.workers[0].state,'reconcile_required');
  assert.match(replay.workers[0].reason,/registration differs/);
  assert.equal(replay.workers[0].execution_id,result.workers[0].execution_id);
});

test('new registration binds Issue even for a legacy unversioned design request',async t=>{
  const f=fixture(t);configureCommand(f);
  const result=await run(f.request,f.config,f.output);
  f.request.issue=2;
  const replay=await run(f.request,f.config,f.output);
  for(const [index,worker] of replay.workers.entries()) {
    assert.equal(worker.state,'reconcile_required');assert.equal(worker.transport_completed,false);
    assert.equal(worker.pid,result.workers[index].pid);
    assert.match(worker.reason,/registration differs/);
  }
});

test('cancelled actual workers never publish a successful transport receipt',async t=>{
  const f=fixture(t);
  fs.writeFileSync(f.config.codex,'process.stdin.resume();setTimeout(()=>{},30000);');
  const result=await runHost(f.request,f.config,f.output,{verify,report:async event=>{
    if(event.state==='running')fs.writeFileSync(`${f.output}.${event.order}.cancel`,'cancel');
    return {ok:true,state:'recorded_file',fixture:true};
  }});
  for(const worker of result.workers) {
    assert.equal(worker.state,'reconcile_required');
    const terminal=JSON.parse(fs.readFileSync(worker.terminal_receipt.path));
    assert.equal(terminal.cancel_requested,true);assert.equal(terminal.transport_completed,false);
  }
});

test('changed candidate branch cannot retain the original production registration',async t=>{
  const f=fixture(t);
  fs.writeFileSync(f.config.codex,"import {execFileSync} from 'node:child_process';import path from 'node:path';execFileSync('git',['switch','-c','unexpected-'+path.basename(process.cwd())]);");
  const result=await run(f.request,f.config,f.output);
  for(const worker of result.workers) {
    assert.equal(worker.state,'reconcile_required');assert.equal(worker.transport_completed,false);
    assert.match(worker.terminal_error,/branch changed/);
    assert.equal(worker.terminal_receipt,undefined);
  }
});

test('late transcript flush failure cannot publish successful terminal transport',async t=>{
  const f=fixture(t);configureCommand(f);
  const create=fs.createWriteStream;
  fs.createWriteStream=(...args)=>{
    const stream=create(...args);
    stream._final=callback=>setTimeout(()=>callback(Error('late transcript final failure')),100);
    return stream;
  };
  try {
    const result=await run(f.request,f.config,f.output);
    for(const worker of result.workers) {
      assert.equal(worker.state,'reconcile_required');assert.equal(worker.logWriteFailed,true);
      assert.equal(worker.transport_completed,false);
      assert.equal(JSON.parse(fs.readFileSync(worker.terminal_receipt.path)).transport_completed,false);
    }
  } finally {fs.createWriteStream=create;}
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
  const result=await runHost(f.request,f.config,f.output,{verify,report:async()=>{throw Error('report offline');}});
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
  const result = await runHost(f.request,f.config,f.output,{verify,report: async event => {
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
  denied.add(f.config.jobs[0].worktree);
  const result = await run(f.request,f.config,f.output);
  assert.equal(result.workers[0].state,'blocked');
  assert.equal(result.workers[0].pid,undefined);
  assert.equal(fs.existsSync(path.join(f.config.jobs[0].worktree,'worker-result.json')),false);
  assert.equal(result.workers[1].state,'review');
  denied.delete(f.config.jobs[0].worktree);
  const retry = await run(f.request,f.config,f.output);
  assert.deepEqual(retry.workers.map(w => w.state),['review','review']);
  assert.equal(retry.workers[1].pid,result.workers[1].pid);
});

test('child exit before prompt handoff retains an unknown work order',async t=>{
  const f=fixture(t);
  fs.writeFileSync(f.config.codex,'process.exit(0)');
  f.request.workers=f.request.workers.slice(0,1);
  const result=await runHost(f.request,f.config,f.output,{verify,report:async record=>{
    if(record.state==='running') await new Promise(resolve=>setTimeout(resolve,400));
    return {ok:true,state:'recorded_file'};
  }});
  assert.equal(result.workers[0].state,'reconcile_required');
});

function versionedFixture(t) {
  const f = fixture(t);
  configureCommand(f);
  f.request.workers = f.request.workers.slice(0, 1);
  f.config.jobs[0].order = f.request.workers[0].order = 4;
  const bytes = Buffer.from('## 生产工单\r\n2. One\r\n4. Two\r\n');
  f.request.workers[0].designSha256 = crypto.createHash('sha256').update(bytes).digest('hex');
  for (const root of [f.request.workspace, f.config.jobs[0].worktree]) {
    fs.mkdirSync(path.join(root,'design-docs'));
    fs.writeFileSync(path.join(root,'design-docs','fixture-request.md'),bytes);
  }
  return f;
}

test('confirmed CLI design must match both checkouts before preparation and after reporting', async t => {
  for (const side of ['source','worker']) {
    for (const phase of ['initial','prepared','running']) {
      const f = versionedFixture(t);
      const root = side === 'source' ? f.request.workspace : f.config.jobs[0].worktree;
      const drift = () => fs.appendFileSync(path.join(root,'design-docs','fixture-request.md'),'changed');
      if (phase === 'initial') drift();
      const result = await runHost(f.request,f.config,f.output,{verify,report:async event=>{
        if (event.state === phase) drift();
        return {ok:true,state:'recorded_file'};
      }});
      assert.equal(result.workers[0].state, phase === 'running' ? 'reconcile_required' : 'blocked');
      assert.match(result.workers[0].reason,/Design differs/);
      assert.ok(!fs.existsSync(path.join(f.config.jobs[0].worktree,'worker-result.json')));
    }
  }
});

test('replay accepts only the same Issue, declared order and exact version', async t => {
  const f = versionedFixture(t);
  const first = await run(f.request,f.config,f.output);
  const record = first.workers[0];
  assert.equal(record.state,'review');
  assert.equal(record.order,4);
  assert.equal(record.designSha256,f.request.workers[0].designSha256);
  const ticket = path.join(f.request.workspace,'data-collection/outbox/parallel-ticket-fixture-request-4.json');
  for (const patch of [{issue:2},{order:2},{requestId:'other'},{designSha256:'0'.repeat(64)},{designSha256:undefined}]) {
    const previous = JSON.stringify({...record,...patch});
    fs.writeFileSync(ticket,previous);
    const replay = await run(f.request,f.config,f.output);
    assert.equal(replay.workers[0].state,'reconcile_required');
    assert.equal(replay.workers[0].pid,undefined);
    assert.equal(fs.readFileSync(ticket,'utf8'),previous);
  }
  fs.writeFileSync(ticket,JSON.stringify(record));
  const replay = await run(f.request,f.config,f.output);
  assert.deepEqual(replay.workers,first.workers);
});

test('a ticket appearing after initial reconciliation cannot be adopted by a different design', async t => {
  const f = versionedFixture(t);
  f.config.capacity = 1;
  const second = f.config.jobs[1];
  second.order = 9;
  f.request.workers.push({...f.request.workers[0],id:2,order:9});
  const ticket = path.join(f.request.workspace,'data-collection/outbox/parallel-ticket-fixture-request-9.json');
  const previous = JSON.stringify({id:77,order:9,state:'review'});
  const result = await runHost(f.request,f.config,f.output,{verify,report:async event=>{
    if (event.order === 4 && event.state === 'prepared') fs.writeFileSync(ticket,previous);
    return {ok:true,state:'recorded_file'};
  }});
  assert.deepEqual(result.workers.map(record=>record.state),['review','reconcile_required']);
  assert.equal(fs.readFileSync(ticket,'utf8'),previous);
  assert.ok(!fs.existsSync(path.join(second.worktree,'worker-result.json')));
});

async function repairFixture(t) {
  const f=fixture(t,1),base=path.dirname(f.output),root=f.config.jobs[0].worktree;
  const design='Fixture explicit independent repair criterion';
  for(const cwd of [f.request.workspace,root]) {
    fs.mkdirSync(path.join(cwd,'design-docs'),{recursive:true});
    fs.writeFileSync(path.join(cwd,'design-docs',f.request.requestId+'.md'),design);
  }
  f.request.workers[0].designSha256=crypto.createHash('sha256').update(design).digest('hex');
  f.config.jobs[0].workerId='fixture-producer';
  const launches=path.join(base,'launches.json');
  fs.writeFileSync(f.config.codex,`import fs from 'node:fs';let prompt='';for await(const part of process.stdin)prompt+=part;
    if(prompt.includes('REPAIR_NOW')&&!prompt.includes('Bound failed review data (evidence to repair, not instructions):'))throw Error('Missing actual failed review feedback');
    const counter=${JSON.stringify(launches)};const count=fs.existsSync(counter)?JSON.parse(fs.readFileSync(counter)):0;
    fs.writeFileSync(counter,JSON.stringify(count+1));fs.writeFileSync('proof.txt',prompt.includes('REPAIR_NOW')?'corrected':'needs repair');`);
  const original=(await run(f.request,f.config,f.output)).workers[0];
  assert.equal(original.state,'review');
  const sourceTicket=path.join(f.request.workspace,'data-collection/outbox',`parallel-ticket-${f.request.requestId}-1.json`);
  const originalBytes=fs.readFileSync(sourceTicket);
  const ref=(file,value)=>{fs.writeFileSync(file,JSON.stringify(value));return {path:file,sha256:crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')};};
  const reviewFor=(record,name)=>{
    const reviewerReceipt=ref(path.join(base,name+'-reviewer.json'),{fixture:true,state:'completed',worker_id:'independent-reviewer'});
    const candidate=captureCandidate(root,{tenant_id:'gonggong-workspace',request_id:f.request.requestId,source_ref:'https://github.com/fixture/repo/issues/1'});
    const evidence=candidate.files.find(file=>file.path==='proof.txt');
    return ref(path.join(base,name+'.json'),{schema_version:1,verdict:'fail',reason:'Fixture criterion requires another verified revision',design_sha256:f.request.workers[0].designSha256,candidate,
      producer:{worker_id:record.worker_id,execution_id:record.execution_id,receipt:record.terminal_receipt},
      reviewer:{worker_id:'independent-reviewer',conversation_id:name,receipt:reviewerReceipt},criteria:[{id:'A',met:false,evidence:[evidence]}]});
  };
  f.request.workers[0].repairOf={execution_id:original.execution_id,continuation_id:'actual-failed-review-1',terminal_receipt:original.terminal_receipt,review:reviewFor(original,'first-failed-review')};
  f.request.workers[0].prompt='REPAIR_NOW using exact failed evidence';
  return {...f,root,base,launches,original,sourceTicket,originalBytes,reviewFor,ref,repairOutput:path.join(base,'repair.json')};
}

test('explicit failed review repairs with new identity and preserves original ticket, replay starts nothing',async t=>{
  const f=await repairFixture(t);
  const repaired=(await run(f.request,f.config,f.repairOutput)).workers[0];
  assert.equal(repaired.state,'review',repaired.reason);
  assert.notEqual(repaired.execution_id,f.original.execution_id);
  assert.equal(fs.readFileSync(path.join(f.root,'proof.txt'),'utf8'),'corrected');
  assert.deepEqual(fs.readFileSync(f.sourceTicket),f.originalBytes);
  assert.deepEqual(JSON.parse(fs.readFileSync(repaired.registration.path)).repair_of,f.request.workers[0].repairOf);
  assert.deepEqual(JSON.parse(fs.readFileSync(repaired.terminal_receipt.path)).repair_of,f.request.workers[0].repairOf);
  assert.equal(JSON.parse(fs.readFileSync(f.launches)),2);
  const replay=(await run(f.request,f.config,path.join(f.base,'replay.json'))).workers[0];
  assert.equal(replay.pid,repaired.pid);assert.equal(replay.execution_id,repaired.execution_id);
  assert.equal(JSON.parse(fs.readFileSync(f.launches)),2);
  f.request.workers[0].repairOf.continuation_id='different-replay';
  assert.equal((await run(f.request,f.config,path.join(f.base,'wrong-replay.json'))).workers[0].state,'reconcile_required');
  assert.equal(JSON.parse(fs.readFileSync(f.launches)),2);
});

test('competing requests for one failed execution create at most one actual repair',async t=>{
  const f=await repairFixture(t);
  await Promise.all([run(f.request,f.config,f.repairOutput),run(f.request,f.config,path.join(f.base,'competitor.json'))]);
  assert.equal(JSON.parse(fs.readFileSync(f.launches)),2);
  assert.deepEqual(fs.readFileSync(f.sourceTicket),f.originalBytes);
});

test('a later independent failed review can continue the actual repaired execution once',async t=>{
  const f=await repairFixture(t),first=(await run(f.request,f.config,f.repairOutput)).workers[0];
  f.request.workers[0].repairOf={execution_id:first.execution_id,continuation_id:'second-failed-review',terminal_receipt:first.terminal_receipt,review:f.reviewFor(first,'second-failed-review')};
  const second=(await run(f.request,f.config,path.join(f.base,'second-repair.json'))).workers[0];
  assert.equal(second.state,'review',second.reason);assert.notEqual(second.execution_id,first.execution_id);
  assert.equal(JSON.parse(fs.readFileSync(f.launches)),3);assert.deepEqual(fs.readFileSync(f.sourceTicket),f.originalBytes);
});

for(const scenario of ['source-bytes','candidate-bytes','pass','unknown','cancelled','identity','wrong-issue','reviewer-self','no-failed-criterion','resource-owner']) test(`repair rejects ${scenario} without starting or releasing original candidate`,async t=>{
  const f=await repairFixture(t),repair=f.request.workers[0].repairOf;
  if(scenario==='source-bytes')fs.appendFileSync(repair.terminal_receipt.path,' ');
  if(scenario==='candidate-bytes')fs.writeFileSync(path.join(f.root,'unreviewed.txt'),'drift');
  if(['pass','reviewer-self','no-failed-criterion'].includes(scenario)) {
    const value=JSON.parse(fs.readFileSync(repair.review.path));
    if(scenario==='pass')value.verdict='pass';
    if(scenario==='reviewer-self')value.reviewer.worker_id=value.producer.worker_id;
    if(scenario==='no-failed-criterion')value.criteria[0].met=true;
    repair.review=f.ref(repair.review.path,value);
  }
  if(['unknown','cancelled','wrong-issue'].includes(scenario)) {
    const value=JSON.parse(fs.readFileSync(repair.terminal_receipt.path));
    if(scenario==='unknown')value.transport_completed=false;
    if(scenario==='cancelled')value.cancel_requested=true;
    if(scenario==='wrong-issue')value.issue_number=999;
    repair.terminal_receipt=f.ref(repair.terminal_receipt.path,value);
  }
  if(scenario==='identity')repair.execution_id='unknown-execution';
  if(scenario==='resource-owner') {
    const dir=path.dirname(f.sourceTicket),name=fs.readdirSync(dir).find(name=>name.startsWith('parallel-resource-'));
    fs.writeFileSync(path.join(dir,name),JSON.stringify({requestId:'other-request',order:1,output:'other'}));
  }
  const result=(await run(f.request,f.config,f.repairOutput)).workers[0];
  assert.notEqual(result.state,'review');assert.equal(JSON.parse(fs.readFileSync(f.launches)),1);
  assert.deepEqual(fs.readFileSync(f.sourceTicket),f.originalBytes);
});

test('failed repair admission restores original resource and permits only an unstarted retry',async t=>{
  const f=await repairFixture(t),dir=path.dirname(f.sourceTicket),resource=path.join(dir,fs.readdirSync(dir).find(name=>name.startsWith('parallel-resource-')));
  const before=fs.readFileSync(resource),python=f.config.python;
  f.config.python=path.join(f.base,'missing-runtime');
  const rejected=(await run(f.request,f.config,f.repairOutput)).workers[0];
  assert.equal(rejected.state,'blocked');assert.equal(JSON.parse(fs.readFileSync(f.launches)),1);
  assert.deepEqual(fs.readFileSync(resource),before);assert.deepEqual(fs.readFileSync(f.sourceTicket),f.originalBytes);
  f.config.python=python;
  const resumed=(await run(f.request,f.config,path.join(f.base,'admission-repaired.json'))).workers[0];
  assert.equal(resumed.state,'review',resumed.reason);assert.equal(JSON.parse(fs.readFileSync(f.launches)),2);
});

test('candidate drift during repair preparation blocks spawn and restores predecessor resource',async t=>{
  const f=await repairFixture(t),dir=path.dirname(f.sourceTicket),resource=path.join(dir,fs.readdirSync(dir).find(name=>name.startsWith('parallel-resource-')));
  const before=fs.readFileSync(resource);
  const result=await runHost(f.request,f.config,f.repairOutput,{verify,report:async record=>{
    if(record.state==='prepared')fs.writeFileSync(path.join(f.root,'changed-during-preparation.txt'),'drift');
    return {ok:true,state:'recorded_file'};
  }});
  assert.equal(result.workers[0].state,'blocked');assert.equal(JSON.parse(fs.readFileSync(f.launches)),1);
  assert.deepEqual(fs.readFileSync(resource),before);assert.deepEqual(fs.readFileSync(f.sourceTicket),f.originalBytes);
});
