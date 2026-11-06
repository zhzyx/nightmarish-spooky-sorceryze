import {hostPython, reservationOperation, ticketOperation, withBlockerRouting} from '../issue-workorders/kuafu_dispatch.mjs';
// One real source event. The operator supplies signed plans only for model production.
import fs from 'node:fs';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {execFile, spawn} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import {issueSnapshot, readIssueWithDependencies} from '../issue-workorders/github_source.mjs';
import {openSession, operatorStateRoot} from '../codex-dispatch/operator.mjs';
import {create} from '../codex-dispatch/native-bridge.mjs';
import {board} from '../../../customizations/platforms/process-management/yuanheng-local/sinan/coordinator.mjs';

const exec = promisify(execFile);
const directory = path.dirname(fileURLToPath(import.meta.url));
const workspace = fs.realpathSync(path.resolve(directory, '../../..'));
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const check = 'framework-integrity';

export function repositoryWorker(config, receipts) {
  const terminal = key => path.join(receipts, key + '.repository-terminal.json');
  const exits = new Map();
  const plans = new Map();
  async function modelCommand(a, args) {
    return new Promise((resolve,reject) => {
      const child = spawn(config.python,['-X','utf8',path.join(directory,'worker.py'),config.workers[a.ticket].grant,...args],
        {cwd:workspace,windowsHide:true,stdio:['pipe','pipe','inherit']});
      let output = '';
      child.stdout.setEncoding('utf8').on('data', chunk => {output += chunk;});
      child.once('error',reject);
      child.stdin.on('error',reject);
      child.once('close',code => {
        if (code !== 0) return reject(Error('Framework plan or runtime receipt rejected'));
        try {resolve(JSON.parse(output));} catch (error) {reject(error);}
      });
      child.stdin.end(JSON.stringify(a));
    });
  }
  return {
    async revalidate(a) {
      if (config.workers[a.ticket].kind !== check) {
        const {binding} = await modelCommand(a,['--check']);
        plans.set(a.key, binding);
      }
      return true;
    },
    async launch(a) {
      const definition = config.workers[a.ticket];
      const verification = definition.kind === check;
      const script = verification ? path.join(workspace, 'framework/tools/verify_framework.py') : path.join(directory, 'worker.py');
      const args = verification ? [script] : [script, definition.grant, 'run', plans.get(a.key)];
      const child = spawn(config.python, ['-X', 'utf8', ...args], {cwd:workspace, windowsHide:true, stdio:['pipe','pipe','inherit']});
      const workerId = randomUUID();
      const reference = 'repository-worker:' + workerId;
      const receipt = {workerId, reference, target:'agent', model:a.model.id, requestedModel:null, observedModel:null,
        modelEvidence:verification ? 'no_model_used' : 'framework_profile', setupPending:false, planBinding:plans.get(a.key) ?? null};
      const started = new Promise((resolve, reject) => {
        child.once('error', reject);
        child.once('spawn', resolve);
      });
      let output = '', inputError;
      child.stdout.setEncoding('utf8').on('data', chunk => {output += chunk;});
      child.stdin.on('error', error => {inputError = error;});
      // Bind exit observation before waiting for spawn or reporting the start.
      const exited = new Promise(resolve => child.once('close', (code,signal) => {
        const data = (() => {try {return JSON.parse(output);} catch {return null;}})();
        let status = 'unknown';
        if (verification) {
          status = code === 0 && data?.mode === 'approved_file_integrity' ? 'completed' : 'failed';
        } else if (!inputError && code === 0 && data?.job) {
          if (data.status === 'completed' && data.submission) status = 'completed';
          if (data.status === 'cancelled') status = 'failed';
        }
        try {
          create(terminal(a.key), {key:a.key, receipt, pid:child.pid, code, signal, data, status, reference:reference + ':exited'});
          resolve(status);
        } catch {resolve('unknown');}
      }));
      exits.set(workerId, exited);
      await started;
      child.stdin.end(verification ? undefined : JSON.stringify(a));
      return receipt;
    },
    async outcome(receipt) {return await exits.get(receipt.workerId) ?? 'unknown';},
    async verifyTerminal(receipt, event, a) {
      if (!['execution.finished','execution.failed'].includes(event.type)) return false;
      const expected = event.type === 'execution.finished' ? 'completed' : 'failed';
      if (event.reference === receipt.reference + ':ledger' && receipt.planBinding) {
        const record = await modelCommand(a,['--inspect',receipt.planBinding]);
        return expected === 'completed' ? record.status === 'completed' && !!record.submission : record.status === 'cancelled';
      }
      const saved = read(terminal(a.key));
      return saved.status === expected && saved.reference === event.reference && saved.key === a.key &&
        JSON.stringify(saved.receipt) === JSON.stringify(receipt);
    },
  };
}

export async function runEvent(config) {
  if (fs.realpathSync(config.workspace) !== workspace) throw Error('Run the entry from the bound trusted checkout');
  if (config.action && config.action !== 'dispatch' && config.action !== 'reconcile') throw Error('Unsupported repository event action');
  const receipts = path.join(await operatorStateRoot(workspace), 'sources');
  const gh = config.gh || 'gh';
  const worker = repositoryWorker(config, receipts);
  const acceptedDependency = async ticket => {
    const source = config.dependencyRegistry;
    if (!source || !path.isAbsolute(source.path) || !source.tickets?.[ticket]) return false;
    return board(read(source.path),path.dirname(source.path)).items.some(i => i.key === source.tickets[ticket] && i.acceptanceValid);
  };
  const validateIssue = issue => {
    if (config.workers['github:'+config.repository+'#'+issue.number]?.kind === check &&
        !issue.labels.some(label=>label.name === 'type:test')) throw Error('Verification requires a dedicated type:test Issue');
  };
  const {host,runtime} = await openSession(config, {worker, acceptedDependency, validateIssue});
  async function intake() {
    if (config.action === 'reconcile') await runtime.verifyWriteAccess();
    for (const r of config.requests) {
      const w = config.workers[r.ticket];
      if (config.authorityRef !== r.authorityRef) throw Error('Request authority mismatch');
      if (r.target !== 'agent' || !w || !(w.kind === check && r.model === check && r.capabilities.length === 1 &&
          r.capabilities[0] === check || w.kind === 'framework-model' && r.model && r.model !== check && path.isAbsolute(w.grant))) throw Error('Invalid repository worker binding');
    }
    for (const b of config.bindings) {
      if (!config.requests.some(r=>r.ticket === 'github:'+config.repository+'#'+b.number)) continue;
      const ticket = 'github:' + config.repository + '#' + b.number;
      await ticketOperation(ticket, () => exec(config.python, [path.join(workspace,'customizations/components/issue-workorders/issue_gate.py'),
        '--repo',workspace,'--issue',String(b.number),'--request-id',b.requestId,'--tenant','gonggong-workspace','--intake-only'],
        {env:{...process.env, GONGGONG_GH:gh}}));
    }
  }
  return advance(config, host, worker, intake);
}

export async function advance(config, host, worker, intake) {
  let event = config.event;
  let pending = config.requests;
  let deferred = [];
  const results = [];
  const active = new Map();
  if (config.action === 'reconcile') {
    results.push(await reservationOperation(config, () => host.reconcile(event,config.reservationKey,config.workerReceipt)));
  }
  if (pending.length && intake) await intake();
  while (pending.length || active.size) {
    if (pending.length) {
      const batch = await host.run(event, pending);
      deferred = batch.deferred;
      for (const result of batch.results) {
        if (result.state === 'running') {
          active.set(result.key, worker.outcome(result.receipt).then(outcome => ({result,outcome})));
        } else results.push(result);
      }
      pending = [];
    }
    if (!active.size) break;
    const {result,outcome} = await Promise.race(active.values());
    active.delete(result.key);
    if (!['completed','failed'].includes(outcome)) {
      results.push({...result,state:'reconcile_required'});
      continue;
    }
    event = {type:outcome === 'completed' ? 'execution.finished' : 'execution.failed', reference:result.receipt.reference + ':exited'};
    const terminal = await ticketOperation(result.ticket, () => host.reconcile(event, result.key, result.receipt));
    results.push({...result, state:outcome === 'failed' ? 'failed' : terminal.state});
    const waiting = new Set(deferred.map(r => r.ticket));
    pending = config.requests.filter(r => waiting.has(r.ticket));
  }
  return {results,deferred};
}

async function issueConfig(number, requestId, grant) {
  if (!Number.isSafeInteger(number) || number < 1 || typeof requestId !== 'string' || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(requestId)) throw Error('Supply ISSUE and stable request ID');
  const {repository} = read(path.join(workspace,'work-items.json'));
  const python = hostPython();
  const gh = process.env.GONGGONG_GH || 'gh';
  const operator = (await exec(gh,['api','user','--jq','.login'])).stdout.trim();
  const ticket = 'github:' + repository + '#' + number;
  const authorityRef = 'explicit-verification:' + operator + ':' + ticket;
  const request = {ticket,target:'agent',model:check,capabilities:[check],owner:operator,outcome:'Verify the admitted framework',
    authorityRef,acceptance:'Framework integrity verifier exited successfully',contextRefs:[`https://github.com/${repository}/issues/${number}`],reads:[workspace],writes:[]};
  const config = {workspace,python,gh,repository,operator,authorityRef,bindings:[{number,requestId}],capacity:1,defaultChatModel:check,
    catalog:[{id:check,available:true,targets:['agent'],capabilities:[check]}],workers:{[ticket]:{kind:check}},
    requests:[request],event:{type:'user.requested',reference:authorityRef}};
  if (grant !== undefined) {
    if (!path.isAbsolute(grant)) throw Error('Supply an absolute private grant path');
    const {task,profiles,state_dir,authority_ref} = read(grant).payload;
    if (profiles.length !== 1 || !path.isAbsolute(state_dir)) throw Error('One evaluated profile and absolute runtime state required');
    const model = profiles[0].id;
    Object.assign(request, {model,capabilities:[...new Set(task.steps.map(step=>step.kind))],outcome:task.outcome,
      acceptance:'Signed framework candidate and Diting submission',authorityRef:authority_ref,writes:[state_dir]});
    Object.assign(config,{authorityRef:authority_ref,defaultChatModel:model,event:{type:'user.requested',reference:authority_ref},
      catalog:[{id:model,available:true,targets:['agent'],capabilities:profiles[0].evaluation.passed_task_types}],
      workers:{[ticket]:{kind:'framework-model',grant}}});
  }
  return config;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2);
  if (args.length === 3 && args[0] === 'inspect') {
    const c = await issueConfig(Number(args[1]),args[2]);
    const api = async endpoint => JSON.parse((await exec(c.gh, ['api', endpoint], {maxBuffer:4*1024*1024})).stdout);
    const issue = await readIssueWithDependencies(api, c.repository, c.bindings[0].number);
    console.log(JSON.stringify(issueSnapshot(c.repository,c.bindings[0],issue,read(path.join(workspace,'.github/labels.json')).map(l=>l.name))));
    process.exit(0);
  }
  let config;
  if (args.length === 3 && args[0] === 'verify' || args.length === 4 && args[0] === 'model') {
    const number = Number(args[1]);
    const repository = read(path.join(workspace,'work-items.json')).repository;
    const bootstrap = {workspace, repository, bindings:[{number,requestId:args[2]}],
      requests:[{ticket:'github:' + repository + '#' + number}]};
    config = await withBlockerRouting(bootstrap, () => issueConfig(number,args[2],args[3]));
  } else if (args.length === 1 && path.isAbsolute(args[0])) {
    config = read(args[0]);
  } else throw Error('Usage: session.mjs inspect|verify ISSUE REQUEST_ID | model ISSUE REQUEST_ID ABS_GRANT | ABS_CONFIG');
  const result = await withBlockerRouting(config, () => runEvent(config));
  console.log(JSON.stringify(result));
  if (!result.results.length || result.deferred.length || result.results.some(r=>!['released','already_reconciled'].includes(r.state))) process.exitCode = 1;
}
