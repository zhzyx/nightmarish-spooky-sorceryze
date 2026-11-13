import {fileDigest,captureCandidate,candidateCurrent,verifiedCurrentCandidate} from './acceptance-candidate.mjs';
export {captureCandidate} from './acceptance-candidate.mjs';
// Internal trusted-host adapter. A JSON verdict is data, never authority: the
// caller must bind an actual independent completion before invoking this module.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {Production} from '../../platforms/document-management/git-markdown/yanshi-legacy/runtime/src/production.mjs';
import {board} from '../../platforms/process-management/yuanheng-local/sinan/coordinator.mjs';

const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const check = (ok, why) => {if (!ok) throw Error(why);};
const read = file => JSON.parse(fs.readFileSync(file,'utf8'));

export function validateDecision(decision, allowLedgerCommits = false) {
  check(decision?.verdict === 'pass' && typeof decision.reason === 'string' && decision.reason.trim(), 'No passing independent verdict');
  check(/^[a-f0-9]{64}$/.test(decision.design_sha256), 'Missing design binding');
  const {producer,reviewer} = decision;
  const producerIdentity=typeof producer?.conversation_id==='string'&&producer.conversation_id || typeof producer?.execution_id==='string'&&producer.execution_id;
  check(producer?.worker_id && reviewer?.worker_id && producer.worker_id !== reviewer.worker_id && producerIdentity && typeof reviewer.conversation_id==='string'&&reviewer.conversation_id && producer.conversation_id !== reviewer.conversation_id, 'Independent worker binding required');
  for (const worker of [producer,reviewer]) {
    const receipt = worker.receipt;
    check(receipt && path.isAbsolute(receipt.path) && /^[a-f0-9]{64}$/.test(receipt.sha256), 'Missing terminal receipt');
    check(fileDigest(path.dirname(receipt.path),path.basename(receipt.path)) === receipt.sha256, 'Stale terminal receipt');
  }
  if(producer.execution_id) {
    const terminal=read(producer.receipt.path),registration=terminal.registration;
    check(terminal.schema_version===1&&terminal.execution_id===producer.execution_id&&terminal.worker_id===producer.worker_id&&terminal.transport_completed===true&&terminal.state==='review'&&terminal.exit_code===0&&terminal.cancel_requested===false&&Number.isSafeInteger(terminal.pid)&&terminal.pid>0&&!terminal.reporting_error&&terminal.reporting?.ok===true&&terminal.reporting?.state==='recorded_file','External producer terminal identity or outcome mismatch');
    check(registration&&path.isAbsolute(registration.path)&&fileDigest(path.dirname(registration.path),path.basename(registration.path))===registration.sha256,'External registration changed');
    const registered=read(registration.path),policy=decision.candidate.audit_policy;
    check(registered.schema_version===1&&registered.execution_id===producer.execution_id&&registered.worker_id===producer.worker_id&&registered.design_sha256===decision.design_sha256&&registered.issue_number===terminal.issue_number&&registered.request_id===terminal.request_id&&policy?.request_id===terminal.request_id&&policy.source_ref.endsWith('/issues/'+terminal.issue_number),'External registration source mismatch');
    check(registered.candidate.root===decision.candidate.root&&registered.candidate.branch===decision.candidate.branch&&terminal.candidate?.root===decision.candidate.root&&terminal.candidate.base_sha===registered.candidate.base_sha&&candidateCurrent({...terminal.candidate,audit_policy:policy},allowLedgerCommits),'External produced candidate changed');
  }
  check(candidateCurrent(decision.candidate,allowLedgerCommits), 'Stale candidate');
  check(Array.isArray(decision.criteria) && decision.criteria.length > 0 && new Set(decision.criteria.map(c=>c.id)).size === decision.criteria.length, 'Missing or duplicate criteria');
  for (const c of decision.criteria) {
    check(typeof c.id === 'string' && c.id && Array.isArray(c.evidence) && c.evidence.length, 'Missing criterion evidence');
    for (const e of c.evidence) check(/^[a-f0-9]{64}$/.test(e.sha256) && decision.candidate.files.some(f=>f.path === e.path && f.sha256 === e.sha256) && fileDigest(decision.candidate.root,e.path) === e.sha256, 'Stale or unbound evidence');
  }
  return true;
}

// Existing editor-runner jobs already identify worktrees and dependency keys.
// Resolve only a unique actual producer; never manufacture a ledger or owner.
export function parallelRegistry(config, decision, ticket) {
  check(Array.isArray(config.jobs), 'Invalid parallel runner configuration');
  if (!config.registry) {
    check(config.jobs.every(j=>Array.isArray(j.dependsOn)&&j.dependsOn.length===0),'Declared dependencies require registry');
    return null;
  }
  check(path.isAbsolute(config.registry),'Parallel registry must be absolute');
  const jobs=config.jobs.filter(j=>typeof j.worktree==='string'&&fs.realpathSync(j.worktree)===fs.realpathSync(decision.candidate.root));
  check(jobs.length===1,'Missing or ambiguous actual producer job');
  const references=new Set(config.jobs.flatMap(j=>j.dependsOn||[]));
  const items=board(read(config.registry),path.dirname(config.registry)).items.filter(i=>fs.realpathSync(i.root)===fs.realpathSync(decision.candidate.root)&&i.owner===decision.producer.worker_id&&
    (jobs[0].acceptanceTicket ? i.key===jobs[0].acceptanceTicket : references.has(i.key)));
  check(items.length===1,'Missing or ambiguous producer ledger mapping');
  return {path:config.registry,tickets:{[ticket]:items[0].key}};
}

// Called only by a trusted completion owner. Revalidation is synchronous so it
// remains inside Production's writer.lock, rather than a check-then-write race.
export async function projectAcceptance({decision,decisionSha256,decisionJson=JSON.stringify(decision),operator,registry,ticket,revalidate,resume,isLive}) {
  check(typeof revalidate === 'function' && typeof resume === 'function', 'Trusted host callbacks required');
  check(typeof isLive === 'function' && isLive() === true, 'Host generation cancelled or unknown');
  check(operator && /^[a-f0-9]{64}$/.test(decisionSha256), 'Missing host identity');
  check(sha(decisionJson) === decisionSha256 && JSON.stringify(JSON.parse(decisionJson)) === JSON.stringify(decision), 'Decision digest mismatch');
  check(registry && path.isAbsolute(registry.path) && registry.tickets?.[ticket], 'Missing registered ledger mapping');
  const key = registry.tickets[ticket];
  const snapshot = () => board(read(registry.path),path.dirname(registry.path));
  const item = snapshot().items.find(i=>i.key === key);
  check(item && fs.realpathSync(item.root) === fs.realpathSync(decision.candidate.root), 'Candidate/ledger mapping mismatch');
  const production = new Production(item.root);
  const current = production.task(production.read(),item.id);
  const binding = {decision_sha256:decisionSha256,operator,ticket,ledger_key:key,candidate:decision.candidate,
    producer_worker_id:decision.producer.worker_id,reviewer_worker_id:decision.reviewer.worker_id,
    terminal_receipts:[decision.producer.receipt,decision.reviewer.receipt]};
  const guard = (s,t) => {
    check(isLive() === true, 'Host generation cancelled or unknown');
    check(revalidate() === true, 'Current host authorization rejected');
    validateDecision(decision,t.status === 'done');
    check(`${s.ledgerId}::${t.id}` === key && t.owner === decision.producer.worker_id && t.independentReview, 'Ledger assignment changed');
    check(JSON.stringify(t.acceptance) === JSON.stringify(decision.criteria.map(c=>c.id)), 'Acceptance criteria changed');
    check(isLive() === true, 'Host generation cancelled during verification');
    return true;
  };
  if (current.review?.host_acceptance?.decision_sha256 === decisionSha256) {
    guard(production.read(),current);
  } else {
    production.review(item.id,{reviewer:decision.reviewer.worker_id,verdict:'pass',reason:decision.reason,
      criteria:decision.criteria.map(c=>({id:c.id,met:true,evidence:c.evidence[0].path})),host_acceptance:binding},guard,
      current.status==='running' ? [...new Set(decision.criteria.flatMap(c=>c.evidence.map(e=>e.path)))] : undefined);
  }
  check(snapshot().items.some(i=>i.key === key && i.acceptanceValid), 'Ledger acceptance projection rejected');
  check(isLive() === true, 'Host generation cancelled after ledger projection; recovery required');
  // Replaying after a dispatch failure reuses the existing review. The existing
  // dispatch reservation protocol provides startup idempotence.
  const dispatch = await resume({type:'ticket.changed',reference:'acceptance:'+decisionSha256});
  return {state:'accepted',ledger_key:key,decision_sha256:decisionSha256,dispatch};
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const [action,root] = process.argv.slice(2);
    if (action === 'capture') {const input=fs.readFileSync(0,'utf8');console.log(JSON.stringify({ok:true,candidate:captureCandidate(root,input ? JSON.parse(input) : undefined)}));}
    else if (action === 'current') {
      const candidate=JSON.parse(fs.readFileSync(0,'utf8'));
      check(fs.realpathSync(root)===fs.realpathSync(candidate.root),'Candidate differs from requested root');
      console.log(JSON.stringify({ok:true,current_candidate:verifiedCurrentCandidate(candidate)}));
    }
    else if (action === 'verify' || action === 'verify-finalization') {const decision=JSON.parse(fs.readFileSync(0,'utf8'));const ledger=action==='verify-finalization';validateDecision(decision,ledger);console.log(JSON.stringify({ok:true,current_candidate:verifiedCurrentCandidate(decision.candidate,ledger)}));}
    else if (action === 'project') {
      const input=JSON.parse(fs.readFileSync(0,'utf8'));
      const config=read(input.host_dispatch_config);
      const {runEvent}=await import('./session.mjs');
      const repository=read(path.join(root,'work-items.json')).repository;
      const parallel=Array.isArray(config.jobs);
      if(!parallel)check(config.repository===repository,'Dispatch repository mismatch');
      const ticket=`github:${repository}#${input.issue_number}`;
      const isLive=()=>{
        try {check(path.isAbsolute(input.host_liveness_path),'Missing live generation');const live=read(input.host_liveness_path);return live.active===true&&live.request_nonce===input.request_nonce;}
        catch {return false;}
      };
      const revalidate=()=>{
        const api=endpoint=>JSON.parse(execFileSync(input.gh,['api',endpoint],{encoding:'utf8',windowsHide:true,timeout:45000}));
        check(api('user').login===input.operator,'Operator changed');
        const permission=api(`repos/${repository}/collaborators/${input.operator}/permission`);
        check(['write','maintain','admin'].includes(permission.permission)||['write','maintain','admin'].includes(permission.role_name),'Repository permission revoked');
        execFileSync(input.python,['-E','-s','-X','utf8',path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../issue-workorders/issue_gate.py'),'--repo',root,'--issue',String(input.issue_number),'--request-id',input.request_id,'--tenant','gonggong-workspace','--intake-only'],{windowsHide:true,timeout:120000,stdio:'pipe'});
        return isLive();
      };
      const decision=JSON.parse(input.decision_json);
      const registry=parallel ? parallelRegistry(config,decision,ticket) : config.dependencyRegistry;
      let projection;
      if(parallel&&!registry) {
        check(isLive(),'Host generation cancelled or unknown');validateDecision(decision);
        projection={state:'not_configured',consumer:'parallel-runner'};
      } else projection=await projectAcceptance({decision,decisionJson:input.decision_json,decisionSha256:sha(input.decision_json),operator:input.operator,
        registry,ticket,revalidate,isLive,resume:parallel ? async event=>({state:'native_continuation_required',reference:event.reference}) : event=>runEvent({...config,dependencyRegistry:{...config.dependencyRegistry,requireHostAcceptance:true},requests:config.requests.filter(r=>r.ticket!==ticket),action:'dispatch',event},{isLive})});
      console.log(JSON.stringify({ok:true,projection,current_candidate:verifiedCurrentCandidate(decision.candidate,projection.state==='accepted')}));
    }
    else throw Error('Unsupported internal acceptance operation');
  } catch (error) {console.log(JSON.stringify({ok:false,error:error.message}));process.exitCode=1;}
}
