import fs from 'node:fs';
import path from 'node:path';
import {spawn, spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import crypto from 'node:crypto';
import {finished} from 'node:stream/promises';
import {selectModel} from '../../customizations/platforms/process-management/yuanheng-local/sinan/dispatch.mjs';
import {board} from '../../customizations/platforms/process-management/yuanheng-local/sinan/coordinator.mjs';
import {repairIdentity,ticketPath,verifyRepair,previousResource,repairReceipts} from './repair.mjs';

const read = p => JSON.parse(fs.readFileSync(p, 'utf8'));
const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
// Audit-only input from the live editor. This never replaces ledger readiness.
export function verifyDependencyPreflight(sources) {
  if (sources === undefined) return; // Older non-editor callers retain their contract.
  if (!Array.isArray(sources) || sources.length > 256 || Buffer.byteLength(JSON.stringify(sources)) > 64 * 1024 * 1024) throw Error('Invalid dependency preflight size');
  for (const source of sources) {
    const ref = source.candidate_check;
    if (!ref || !path.isAbsolute(ref.path) || fs.statSync(ref.path).size > 32 * 1024 * 1024) throw Error('Missing bounded dependency check');
    const bytes = fs.readFileSync(ref.path);
    if (digest(bytes) !== ref.sha256) throw Error('Dependency check changed');
    const record = JSON.parse(bytes);
    const request = JSON.parse(record.request_json), response = JSON.parse(record.response_json);
    if (record.schema_version !== 1 || response.ok !== true || request.request_nonce !== ref.request_nonce || response.request_nonce !== ref.request_nonce ||
        response.candidate_sha256 !== request.candidate.files_sha256 ||
        JSON.stringify(request.candidate) !== JSON.stringify(source.verified_response.current_candidate) ||
        source.verified_response.decision_sha256 !== source.decision_sha256 || source.decision.verdict !== 'pass') throw Error('Dependency check binding differs');
  }
}
function sidecar(file, value) {
  durable(file,value,true);
  return {path:file,sha256:digest(fs.readFileSync(file))};
}
function candidate(root, base) {
  const branch=command('git',['symbolic-ref','--short','HEAD'],root);
  const head=command('git',['rev-parse','HEAD'],root);
  const result=spawnSync('git',['ls-files','--cached','--others','--exclude-standard','-z'],{cwd:root,encoding:'utf8',windowsHide:true,maxBuffer:32*1024*1024});
  if(result.status!==0)throw Error('Cannot capture produced files');
  const names=[...new Set(result.stdout.split('\0').filter(p=>p&&!p.startsWith('.yuanheng/')))].sort();
  const files=names.map(relative=>{
    const file=path.resolve(root,relative);
    for(let current=file;current!==root;current=path.dirname(current)) {
      if(current===path.dirname(current))throw Error('Produced file escaped candidate');
      try {if(fs.lstatSync(current).isSymbolicLink())throw Error('Linked produced file');}
      catch(error){if(error.code!=='ENOENT')throw error;}
    }
    if(!fs.existsSync(file))return {path:relative,sha256:null};
    if(!fs.statSync(file).isFile())throw Error('Produced candidate is not a regular file');
    return {path:relative,sha256:digest(fs.readFileSync(file))};
  });
  return {root,branch,base_sha:base??head,head,files_sha256:digest(JSON.stringify(files)),files};
}
const inside = (a,b) => {
  if(process.platform==='win32'){a=a.toLowerCase();b=b.toLowerCase();}
  return a === b || a.startsWith(b + path.sep) || b.startsWith(a + path.sep);
};
const canonical = p => fs.realpathSync(p);
function durable(file,value,exclusive=false) {
  const fd=fs.openSync(file,exclusive?'wx':'w',0o600);
  try {fs.writeFileSync(fd,JSON.stringify(value));fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
}
function replaceResource(file,value) {
  const temporary=file+'.'+crypto.randomUUID()+'.tmp';
  durable(temporary,value,true);
  fs.renameSync(temporary,file);
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
// A versioned editor dispatch is approved for the exact bytes in both checkouts.
function verifyDesign(request, job) {
  if (!Object.hasOwn(job, 'designSha256')) return;
  const relative = path.join('design-docs', request.requestId + '.md');
  for (const root of [request.workspace, job.cwd]) {
    const file = path.join(root, relative);
    if (!inside(canonical(root), canonical(file)) || fs.statSync(file).size > 1024 * 1024 ||
        crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex') !== job.designSha256) {
      throw Error('Design differs from the confirmed version');
    }
  }
}

function editorRuntime(request) {
  // Older explicit CLI callers may have no Godot host. Never guess a runtime
  // from PATH or from a model response; native editor requests bind their own.
  if (!Object.hasOwn(request, 'editorRuntime')) return null;
  const runtime = request.editorRuntime;
  if (!runtime || typeof runtime.executable !== 'string' || !path.isAbsolute(runtime.executable) ||
      runtime.executable.includes('\0') || typeof runtime.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(runtime.sha256) ||
      !fs.statSync(runtime.executable).isFile() || digest(fs.readFileSync(runtime.executable)) !== runtime.sha256)
    throw Error('Current editor runtime is missing or changed; reconnect the editor before production');
  return {executable:fs.realpathSync(runtime.executable), sha256:runtime.sha256};
}

function restoreTicket(file, record, request, job) {
  try {
    const ticket = read(file);
    if (JSON.stringify(ticket.repair_of??null)!==JSON.stringify(job.repairOf??null)) throw Error('Existing repair ticket belongs to another continuation');
    if (job.repairOf) repairReceipts(job.repairOf);
    if (ticket.designSha256 !== record.designSha256 ||
        (record.designSha256 && (ticket.issue !== request.issue || ticket.requestId !== request.requestId || ticket.order !== record.order))) {
      throw Error('Existing ticket belongs to a different or unversioned design');
    }
    Object.assign(record, ticket, {id:record.id});
    if(ticket.registration) {
      const registration=read(ticket.registration.path);
      if(digest(fs.readFileSync(ticket.registration.path))!==ticket.registration.sha256 ||
          registration.candidate.root!==job.cwd || registration.execution_id!==ticket.execution_id ||
          registration.issue_number!==request.issue || registration.request_id!==request.requestId ||
          registration.order!==job.order || registration.editor_worker_id!==job.id ||
          registration.worker_id!==ticket.worker_id || (job.workerId && job.workerId!==ticket.worker_id)) {
        throw Error('Original worker registration differs from current assignment');
      }
      if(ticket.terminal_receipt && digest(fs.readFileSync(ticket.terminal_receipt.path))!==ticket.terminal_receipt.sha256)throw Error('Original terminal receipt changed');
    }
  } catch (error) {
    record.state = 'reconcile_required';
    record.transport_completed = false;
    record.reason = String(error.message);
  }
}

export function prepare(request, config) {
  if (config.nativeWorkspaceWrite !== true || !config.authorityRef || !Number.isSafeInteger(config.capacity) || config.capacity < 1) throw Error('Explicit native workspace-write mandate and positive safe integer capacity required');
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
    if (Object.hasOwn(worker, 'designSha256') && (typeof worker.designSha256 !== 'string' || !/^[0-9a-f]{64}$/.test(worker.designSha256))) throw Error('Invalid confirmed design digest');
    const job = config.jobs.find(j => j.order === worker.order);
    if (!job || typeof worker.prompt !== 'string' || !worker.prompt.trim() || !Array.isArray(job.capabilities) || !job.capabilities.length) throw Error('Each work order needs explicit capabilities and workspace');
    if(typeof job.worktree!=='string'||!path.isAbsolute(job.worktree))throw Error('Worktree must be absolute');
    if(Object.hasOwn(job,'workerId') && (typeof job.workerId!=='string'||!job.workerId.trim()||job.workerId.length>256))throw Error('Invalid host worker identity');
    const cwd = canonical(job.worktree);
    const top = canonical(command('git',['rev-parse','--show-toplevel'],cwd));
    const commonPath = command('git',['rev-parse','--git-common-dir'],cwd);
    if (!same(top,cwd) || !registered.some(r=>same(r,cwd)) || same(cwd,primary) ||
        !same(canonical(path.resolve(cwd,commonPath)),common) || same(cwd,source) || roots.some(r=>inside(cwd,r))) throw Error('Distinct registered worktrees of the same repository required; primary and subdirectories forbidden');
    roots.push(cwd);
    const model = selectModel(job.capabilities,config.models,'agent',job.model);
    if (!Array.isArray(job.dependsOn)) throw Error('Explicit dependencies required');
    const dependencyReady = job.dependsOn.every(d => accepted.includes(d));
    const repairOf=Object.hasOwn(worker,'repairOf')?repairIdentity(worker.repairOf):undefined;
    return {...worker,repairOf,cwd,model,launch,workerId:job.workerId,dependsOn:job.dependsOn,stateRoot:path.join(path.dirname(common),'data-collection/outbox'),ready:!!model&&dependencyReady,blocked:!model?'blocked_model':'blocked_dependency'};
  });
}
export async function run(request, config, output, runtime = {}) {
  const connector = runtime.report ?? ((record) => {
    const result=spawnSync(config.python,[fileURLToPath(new URL('./report.py',import.meta.url)),request.workspace],{input:JSON.stringify({requestId:request.requestId,issue:request.issue,...record}),encoding:'utf8',windowsHide:true});
    if(result.status!==0)throw Error('Shared Diting reporting failed; no success claimed');
    return JSON.parse(result.stdout);
  });
  const report=async (job,record)=>{
    const receipt=await connector({order:job.order,model:job.model.id,workerBackend:job.launch.backend,...(job.designSha256 ? {designSha256:job.designSha256} : {}),...record});
    if(receipt?.ok!==true || receipt.state!=='recorded_file')throw Error('No actual Diting file receipt');
    return receipt;
  };
  const verify = runtime.verify ?? command;
  const jobs = prepare(request,config);
  // Persistent exclusive intent is retained after crashes and unknown receipts.
  const reservation = output + '.running';
  durable(reservation,{requestId:request.requestId,authorityRef:config.authorityRef},true);
  const result = {requestId:request.requestId,batchId:request.batchId,workers:jobs.map(j=>({id:j.id,order:j.order,...(j.repairOf?{repair_of:j.repairOf}:{}),...(j.designSha256 ? {requestId:request.requestId,issue:request.issue,designSha256:j.designSha256} : {}),model:j.model?.id??null,state:j.ready?'reserved':j.blocked}))};
  // Reconciliation precedes current admission: an unavailable model cannot erase
  // an already-running/review worker's receipt or turn it into "never started".
  for(const job of jobs) {
    const existing=ticketPath(request,job);
    if(fs.existsSync(existing)) {
      restoreTicket(existing,result.workers.find(w=>w.id===job.id),request,job);
      job.existing=true;
    }
  }
  const save = () => {durable(output+'.tmp',result);fs.renameSync(output+'.tmp',output);};
  save();
  const pending = jobs.filter(j=>j.ready&&!j.existing);
  async function consume() {
    while (pending.length) {
      const job = pending.shift(), record = result.workers.find(r=>r.id===job.id);
      let resourceFile, ticketFile, slotFile, priorResource, resourceOwned=false, ticketOwned=false, launchAttempted=false;
      try {
        if (!job.dependsOn.every(d=>acceptedDependencies(config).includes(d))) {record.state='blocked_dependency';save();continue;}
        const locks = job.stateRoot;
        fs.mkdirSync(locks,{recursive:true});
        const resourceKey = crypto.createHash('sha256').update(process.platform==='win32'?job.cwd.toLowerCase():job.cwd).digest('hex');
        ticketFile=ticketPath(request,job);
        if (fs.existsSync(ticketFile)) {restoreTicket(ticketFile,record,request,job);continue;}
        verifyDesign(request, job);
        const repairSource=job.repairOf?verifyRepair(request,job):null;
        record.workerBackend=job.launch.backend;
        try {
          durable(ticketFile,{...record,state:'reconcile_required'},true);ticketOwned=true;
        } catch (error) {
          if (error.code !== 'EEXIST') throw error;
          restoreTicket(ticketFile,record,request,job);continue;
        }
        resourceFile=path.join(locks,`parallel-resource-${resourceKey}.json`);
        if (repairSource) {
          priorResource=previousResource(resourceFile,request,job,repairSource);
          replaceResource(resourceFile,{requestId:request.requestId,order:job.order,output,repair_of:job.repairOf});
        } else durable(resourceFile,{requestId:request.requestId,order:job.order,output},true);
        resourceOwned=true;
        for(let slot=0;slot<config.capacity;slot++) {
          const file=path.join(locks,`parallel-capacity-${slot}.json`);
          try {durable(file,{requestId:request.requestId,order:job.order},true);slotFile=file;break;}
          catch(error) {if(error.code!=='EEXIST')throw error;}
        }
        if(!slotFile) throw Error('Shared host capacity occupied');
        // Trusted installed code verifies the selected game data and live Issue authority.
        const installation = fileURLToPath(new URL('../../', import.meta.url));
        verify(config.python,[path.join(installation,'customizations/components/issue-workorders/issue_gate.py'),'--repo',job.cwd,'--issue',String(request.issue),'--request-id',request.requestId,'--tenant','gonggong-workspace','--intake-only'],job.cwd);
        verify(config.python,[path.join(installation,'framework/tools/verify_framework.py')],installation);
        verify(config.python,[path.join(installation,'customizations/components/issue-workorders/issue_gate.py'),'--repo',job.cwd,'--candidate-framework-only'],job.cwd);
        record.reportingPrepared=await report(job,{state:'prepared',kind:'handoff'});
        verifyDesign(request, job);
        const boundEditor = editorRuntime(request);
        if (job.repairOf) verifyRepair(request,job);
        verifyDependencyPreflight(job.dependency_preflight);
        record.execution_id=crypto.randomUUID();
        record.worker_id=job.workerId??`parallel:${record.execution_id}`;
        record.issue_number=request.issue;
        record.request_id=request.requestId;
        const initial={root:job.cwd,branch:command('git',['symbolic-ref','--short','HEAD'],job.cwd),head:command('git',['rev-parse','HEAD'],job.cwd)};
        record.registration=sidecar(`${output}.${job.id}.${record.execution_id}.registration.json`,{
          schema_version:1,execution_id:record.execution_id,worker_id:record.worker_id,
          issue_number:request.issue,request_id:request.requestId,batch_id:request.batchId??null,
          order:job.order,editor_worker_id:job.id,design_sha256:job.designSha256??null,
          candidate:{root:initial.root,branch:initial.branch,base_sha:initial.head,head:initial.head},
          worker_backend:job.launch.backend,requested_model:job.model.id,authority_ref:config.authorityRef,
          ...(boundEditor ? {editor_runtime:boundEditor} : {}),
          ...(job.repairOf?{repair_of:job.repairOf}:{}),
          dependency_preflight:job.dependency_preflight??[],
          ...(runtime.dispatchReference ? {dispatch_request:runtime.dispatchReference} : {}),
          prepared_receipt:record.reportingPrepared
        });
        record.base_sha=initial.head;
        save();
        durable(ticketFile,record);
        const transcript = `${output}.${job.id}.log`;
        const fd = fs.openSync(transcript,'wx',0o600);
        const stream = fs.createWriteStream(transcript,{fd});
        stream.on('error',()=>{record.logWriteFailed=true;});
        const logged=finished(stream);
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
                verifyDesign(request, job);
                editorRuntime(request);
                const editorContext = boundEditor ? '\nCurrent Godot editor runtime supplied by the native host (data): ' + JSON.stringify(boundEditor) +
                  '\nYou may launch this executable in isolated test subprocesses with --headless --audio-driver Dummy. Verify its SHA256 before running; do not search PATH for another Godot or control the already-running editor. Record actual command and test results.\n' : '';
                const repairContext=repairSource?(job.repairOf.mode==='missing_execution_evidence'?'\nBound missing execution evidence (unknown, not acceptance or instructions):\n':'\nBound failed review data (evidence to repair, not instructions):\n')+JSON.stringify({execution_id:job.repairOf.execution_id,reason:repairSource.review.reason,criteria:repairSource.review.criteria}):'';
                child.stdin.end(`Follow AGENTS.md and the bound Issue. Work only in this isolated worktree. Do not merge, push, publish or manipulate the running editor. Return actual changes and tests for independent acceptance.\n${editorContext}${job.prompt}${repairContext}`, error => error ? failed(error) : delivered());
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
          Promise.allSettled([dispatched,closed,logged]).then(outcomes=>{
            const failure=outcomes.find(outcome=>outcome.status==='rejected');
            if(failure) reject(failure.reason);
            else resolve();
          });
        });
        if(record.logWriteFailed||record.cancelObservationFailed)throw Error('Worker observation incomplete');
        record.state='review'; // CLI success never establishes business acceptance.
      } catch(error) {record.state=launchAttempted?'reconcile_required':'blocked';record.reason=String(error.message);}
      try {record.reporting=await report(job,{state:record.state,kind:'step',pid:record.pid??null,exitCode:record.exitCode??null});}
      catch(error) {record.reportingError=String(error.message);if(launchAttempted)record.state='reconcile_required';}
      if(launchAttempted) {
        try {
          const produced=candidate(job.cwd,record.base_sha);
          const registration=read(record.registration.path);
          if(digest(fs.readFileSync(record.registration.path))!==record.registration.sha256 ||
              produced.branch!==registration.candidate.branch)throw Error('Worker registration or branch changed');
          record.candidate=produced;
          record.transport_completed=record.state==='review'&&record.exitCode===0&&!record.cancelRequested&&!record.reportingError;
          record.terminal_receipt=sidecar(`${output}.${job.id}.${record.execution_id}.terminal.json`,{
            schema_version:1,execution_id:record.execution_id,worker_id:record.worker_id,
            issue_number:request.issue,request_id:request.requestId,registration:record.registration,
            candidate:produced,pid:record.pid??null,exit_code:record.exitCode??null,state:record.state,
            cancel_requested:!!record.cancelRequested,transport_completed:record.transport_completed,
            reporting:record.reporting??null,reporting_error:record.reportingError??null,
            ...(job.repairOf?{repair_of:job.repairOf}:{}),
            business_accepted:null
          });
        } catch(error) {
          record.state='reconcile_required';record.transport_completed=false;record.terminal_error=String(error.message);
          try {record.reporting=await report(job,{state:record.state,kind:'step',pid:record.pid??null,exitCode:record.exitCode??null});}
          catch(reportError) {record.reportingError=String(reportError.message);}
        }
      }
      if (ticketOwned) {
        if (!launchAttempted) {
          try {
            if(resourceOwned) {
              if(priorResource) replaceResource(resourceFile,priorResource);
              else fs.unlinkSync(resourceFile);
            }
            fs.unlinkSync(ticketFile);
          } catch(error) {
            record.state='reconcile_required';record.transport_completed=false;
            record.reason='Unstarted reservation rollback failed: '+error.message;
            durable(ticketFile,record);
          }
        }
        else durable(ticketFile,record);
      }
      if(slotFile && (!launchAttempted || record.state==='review'))fs.unlinkSync(slotFile);
      save();
    }
  }
  // Capacity belongs to the authorized host; allocate consumers only for work
  // actually ready in this event, even if the configured limit is much larger.
  const consumers = Math.min(config.capacity, pending.length);
  await Promise.all(Array.from({length:consumers},consume));
  save();
  fs.unlinkSync(reservation); // Crash leaves this marker; only actual completion releases it.
  return result;
}
// Node resolves module URLs through installation links; compare the actual files.
if (process.argv[1] && fs.existsSync(process.argv[1]) && fs.realpathSync(process.argv[1])===fs.realpathSync(fileURLToPath(import.meta.url))) {
  try {
    if (process.platform==='win32') {
      const {createRequire} = await import('node:module');
      const require = createRequire(import.meta.url);
      const job = require('../codebuddy_cli/node_modules/@tencent-ai/codebuddy-code/bin/native/win32-'+process.arch+'/job-object.node');
      if (!job.ensureKillOnCloseJob()) throw Error('Process tree boundary unavailable');
    }
    const bytes = fs.readFileSync(process.argv[2]);
    if (bytes.length > 64 * 1024 * 1024 || (process.argv[4] && digest(bytes) !== process.argv[4])) throw Error('Dispatch request changed or exceeds bound');
    const request=JSON.parse(bytes);
    await run(request,read(request.config),process.argv[3], {dispatchReference:{path:path.resolve(process.argv[2]),sha256:digest(bytes)}});
  } catch(error) {console.error(error.message);process.exitCode=1;}
}
