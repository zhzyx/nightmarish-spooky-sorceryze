import fs from 'node:fs';
import path from 'node:path';
import {spawn, spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import crypto from 'node:crypto';
import {selectModel} from '../../framework/modules/sinan/dispatch.mjs';
import {board} from '../../framework/modules/sinan/coordinator.mjs';

const read = p => JSON.parse(fs.readFileSync(p, 'utf8'));
const inside = (a,b) => {
  if(process.platform==='win32'){a=a.toLowerCase();b=b.toLowerCase();}
  return a === b || a.startsWith(b + path.sep) || b.startsWith(a + path.sep);
};
const canonical = p => fs.realpathSync(p);
function durable(file,value,exclusive=false) {
  const fd=fs.openSync(file,exclusive?'wx':'w',0o600);
  try {fs.writeFileSync(fd,JSON.stringify(value));fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
}
function command(executable, args, cwd) {
  const r = spawnSync(executable, args, {cwd, encoding:'utf8', windowsHide:true});
  if (r.status !== 0) throw Error(`Host check failed: ${path.basename(executable)}`);
  return r.stdout.trim();
}
function acceptedDependencies(config) {
  if (!config.registry) return [];
  if (!path.isAbsolute(config.registry)) throw Error('Registry must be absolute');
  return board(read(config.registry),path.dirname(config.registry)).items.filter(t=>t.acceptanceValid).map(t=>t.key);
}
function workerCommand(config) {
  const absolute = value => typeof value === 'string' && path.isAbsolute(value) && !value.includes('\0');
  if (Object.hasOwn(config, 'workerCommand')) {
    if (Object.hasOwn(config, 'codex')) throw Error('Configure only one of workerCommand and codex');
    const command = config.workerCommand;
    if (!absolute(command?.executable) || !Array.isArray(command.args) ||
        !command.args.every(arg => typeof arg === 'string' && !arg.includes('\0')) ||
        command.args.filter(arg => arg === '{model}').length !== 1) {
      throw Error('workerCommand requires an absolute executable and string args with one {model} argument');
    }
    return {backend: 'command', executable: command.executable, args: command.args};
  }
  if (!absolute(config.codex)) throw Error('Codex executable must use an absolute path');
  const args = ['exec','--approve-for-me','--json','--ephemeral','--ignore-user-config','--model','{model}','-'];
  return /\.[cm]?js$/.test(config.codex)
    ? {backend: 'codex', executable: process.execPath, args: [config.codex, ...args]}
    : {backend: 'codex', executable: config.codex, args};
}
export function prepare(request, config) {
  if (config.nativeWorkspaceWrite !== true || !config.authorityRef || !Number.isInteger(config.capacity) || config.capacity < 1 || config.capacity > 2) throw Error('Explicit native workspace-write mandate and capacity 1..2 required');
  if (![request.workspace,config.python].every(p=>typeof p==='string'&&path.isAbsolute(p))) throw Error('Workspace and executables must use absolute paths');
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(request.requestId) || !Number.isInteger(request.issue) || request.issue < 1) throw Error('Invalid Issue binding');
  const launch = workerCommand(config);
  const source = canonical(request.workspace), seen = new Set(), ids = new Set(), roots = [];
  const common = canonical(path.resolve(source,command('git',['rev-parse','--git-common-dir'],source)));
  const registered = command('git',['worktree','list','--porcelain'],source).split(/\r?\n/)
    .filter(line=>line.startsWith('worktree ')).map(line=>canonical(line.slice(9)));
  const primary = registered[0];
  const same = (a,b) => process.platform==='win32' ? a.toLowerCase()===b.toLowerCase() : a===b;
  const accepted = acceptedDependencies(config);
  return request.workers.map(worker => {
    if (!Number.isInteger(worker.id) || worker.id < 0 || ids.has(worker.id) || !Number.isInteger(worker.order) || worker.order < 1 || seen.has(worker.order)) throw Error('Invalid or duplicate work order'); seen.add(worker.order);ids.add(worker.id);
    const job = config.jobs.find(j => j.order === worker.order);
    if (!job || typeof worker.prompt !== 'string' || !worker.prompt.trim() || !Array.isArray(job.capabilities) || !job.capabilities.length) throw Error('Each work order needs explicit capabilities and workspace');
    if(typeof job.worktree!=='string'||!path.isAbsolute(job.worktree))throw Error('Worktree must be absolute');
    const cwd = canonical(job.worktree);
    const top = canonical(command('git',['rev-parse','--show-toplevel'],cwd));
    const commonPath = command('git',['rev-parse','--git-common-dir'],cwd);
    if (!same(top,cwd) || !registered.some(r=>same(r,cwd)) || same(cwd,primary) ||
        !same(canonical(path.resolve(cwd,commonPath)),common) || same(cwd,source) || roots.some(r=>inside(cwd,r))) throw Error('Distinct registered worktrees of the same repository required; primary and subdirectories forbidden');
    roots.push(cwd);
    const model = selectModel(job.capabilities,config.models,'agent',job.model);
    if (!Array.isArray(job.dependsOn)) throw Error('Explicit dependencies required');
    const dependencyReady = job.dependsOn.every(d => accepted.includes(d));
    return {...worker,cwd,model,launch,dependsOn:job.dependsOn,stateRoot:path.join(path.dirname(common),'data-collection/outbox'),ready:!!model&&dependencyReady,blocked:!model?'blocked_model':'blocked_dependency'};
  });
}
export async function run(request, config, output, runtime = {}) {
  const connector = runtime.report ?? ((record) => {
    const result=spawnSync(config.python,[fileURLToPath(new URL('./report.py',import.meta.url)),request.workspace],{input:JSON.stringify({requestId:request.requestId,issue:request.issue,...record}),encoding:'utf8',windowsHide:true});
    if(result.status!==0)throw Error('Shared Diting reporting failed; no success claimed');
    return JSON.parse(result.stdout);
  });
  const report=async (job,record)=>{
    const receipt=await connector({order:job.order,model:job.model.id,workerBackend:job.launch.backend,...record});
    if(receipt?.ok!==true || receipt.state!=='recorded_file')throw Error('No actual Diting file receipt');
    return receipt;
  };
  const jobs = prepare(request,config);
  // Persistent exclusive intent is retained after crashes and unknown receipts.
  const reservation = output + '.running';
  durable(reservation,{requestId:request.requestId,authorityRef:config.authorityRef},true);
  const result = {requestId:request.requestId,batchId:request.batchId,workers:jobs.map(j=>({id:j.id,order:j.order,model:j.model?.id??null,state:j.ready?'reserved':j.blocked}))};
  // Reconciliation precedes current admission: an unavailable model cannot erase
  // an already-running/review worker's receipt or turn it into "never started".
  for(const job of jobs) {
    const existing=path.join(job.stateRoot,`parallel-ticket-${request.requestId}-${job.order}.json`);
    if(fs.existsSync(existing)) {
      Object.assign(result.workers.find(w=>w.id===job.id),read(existing),{id:job.id});
      job.existing=true;
    }
  }
  const save = () => {durable(output+'.tmp',result);fs.renameSync(output+'.tmp',output);};
  save();
  const pending = jobs.filter(j=>j.ready&&!j.existing);
  async function consume() {
    while (pending.length) {
      const job = pending.shift(), record = result.workers.find(r=>r.id===job.id);
      let resourceFile, ticketFile, slotFile, resourceOwned=false, ticketOwned=false, launchAttempted=false;
      try {
        if (!job.dependsOn.every(d=>acceptedDependencies(config).includes(d))) {record.state='blocked_dependency';save();continue;}
        const locks = job.stateRoot;
        fs.mkdirSync(locks,{recursive:true});
        const resourceKey = crypto.createHash('sha256').update(process.platform==='win32'?job.cwd.toLowerCase():job.cwd).digest('hex');
        ticketFile=path.join(locks,`parallel-ticket-${request.requestId}-${job.order}.json`);
        if (fs.existsSync(ticketFile)) {Object.assign(record,read(ticketFile),{id:job.id});continue;}
        record.workerBackend=job.launch.backend;
        durable(ticketFile,{...record,state:'reconcile_required'},true);ticketOwned=true;
        resourceFile=path.join(locks,`parallel-resource-${resourceKey}.json`);
        durable(resourceFile,{requestId:request.requestId,order:job.order,output},true);resourceOwned=true;
        for(let slot=0;slot<config.capacity;slot++) {
          const file=path.join(locks,`parallel-capacity-${slot}.json`);
          try {durable(file,{requestId:request.requestId,order:job.order},true);slotFile=file;break;}
          catch(error) {if(error.code!=='EEXIST')throw error;}
        }
        if(!slotFile) throw Error('Shared host capacity occupied');
        for(const file of ['CURRENT_FRAMEWORK.json','framework/package-lock.json']) {
          if(!fs.readFileSync(path.join(request.workspace,file)).equals(fs.readFileSync(path.join(job.cwd,file)))) throw Error('Worker framework differs from dispatch candidate');
        }
        command(config.python,[path.join(job.cwd,'customizations/components/issue-workorders/issue_gate.py'),'--repo',job.cwd,'--issue',String(request.issue),'--request-id',request.requestId,'--tenant','gonggong-workspace','--intake-only'],job.cwd);
        command(config.python,[path.join(job.cwd,'framework/tools/verify_framework.py')],job.cwd);
        record.reportingPrepared=await report(job,{state:'prepared',kind:'handoff'});
        const transcript = `${output}.${job.id}.log`;
        const fd = fs.openSync(transcript,'wx',0o600);
        const stream = fs.createWriteStream(transcript,{fd});
        stream.on('error',()=>{record.logWriteFailed=true;});
        const args = job.launch.args.map(arg => arg === '{model}' ? job.model.id : arg);
        launchAttempted=true;
        await new Promise((resolve,reject)=> {
          const child = spawn(job.launch.executable,args,{cwd:job.cwd,windowsHide:true,stdio:['pipe','pipe','pipe']});
          const cancelPath = `${output}.${job.id}.cancel`;
          const cancel = () => {
            if (!fs.existsSync(cancelPath) || !child.pid || child.exitCode !== null) return;
            record.cancelRequested = true;
            if (process.platform === 'win32') spawnSync('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});
            else child.kill('SIGTERM');
          };
          const watcher = fs.watch(path.dirname(output),cancel);
          watcher.on('error',()=>{record.cancelObservationFailed=true;});
          const dispatched = new Promise((delivered, failed) => {
            child.once('error',failed);
            child.stdin.once('error',failed);
            child.once('spawn',async()=> {
              record.state='running';record.pid=child.pid;record.transcript=transcript;
              try {
                save();
                record.reportingStarted=await report(job,{order:job.order,model:job.model.id,state:'running',kind:'step',pid:child.pid});
                cancel();
                if (child.exitCode !== null || child.signalCode !== null || child.stdin.destroyed) throw Error('Worker exited before prompt handoff');
                child.stdin.end(`Follow AGENTS.md and the bound Issue. Work only in this isolated worktree. Do not merge, push, publish or manipulate the running editor. Return actual changes and tests for independent acceptance.\n${job.prompt}`, error => error ? failed(error) : delivered());
              } catch(error) {child.kill();failed(error);}
            });
          });
          child.stdout.pipe(stream,{end:false});child.stderr.pipe(stream,{end:false});
          const closed = new Promise((finished,failed) => {
            child.once('close',code=> {
              watcher.close();stream.end();record.exitCode=code;
              code===0&&!record.cancelRequested ? finished() : failed(Error('Worker exited without successful receipt'));
            });
          });
          Promise.all([dispatched,closed]).then(resolve,reject);
        });
        record.state='review'; // CLI success never establishes business acceptance.
      } catch(error) {record.state=launchAttempted?'reconcile_required':'blocked';record.reason=String(error.message);}
      try {record.reporting=await report(job,{state:record.state,kind:'step',pid:record.pid??null,exitCode:record.exitCode??null});}
      catch(error) {record.reportingError=String(error.message);if(launchAttempted)record.state='reconcile_required';}
      if (ticketOwned) {
        if (!launchAttempted) {fs.unlinkSync(ticketFile);if(resourceOwned)fs.unlinkSync(resourceFile);}
        else durable(ticketFile,record);
      }
      if(slotFile && (!launchAttempted || record.state==='review'))fs.unlinkSync(slotFile);
      save();
    }
  }
  await Promise.all(Array.from({length:config.capacity},consume));
  save();
  fs.unlinkSync(reservation); // Crash leaves this marker; only actual completion releases it.
  return result;
}
if (process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  try {
    if (process.platform==='win32') {
      const {createRequire} = await import('node:module');
      const require = createRequire(import.meta.url);
      const job = require('../codebuddy_cli/node_modules/@tencent-ai/codebuddy-code/bin/native/win32-'+process.arch+'/job-object.node');
      if (!job.ensureKillOnCloseJob()) throw Error('Process tree boundary unavailable');
    }
    const request=read(process.argv[2]);
    await run(request,read(request.config),process.argv[3]);
  } catch(error) {console.error(error.message);process.exitCode=1;}
}
