// Explicit live-host repair lineage. These records authorize no acceptance;
// the editor binds an independent failure or explicitly classified missing-evidence review.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {candidateCurrent,fileDigest} from '../../customizations/components/repository-dispatch/acceptance-candidate.mjs';

const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const check = (ok, why) => {if (!ok) throw Error(why);};
const read = file => JSON.parse(fs.readFileSync(file,'utf8'));
function receipt(ref) {
  check(ref && path.isAbsolute(ref.path) && /^[a-f0-9]{64}$/.test(ref.sha256), 'Missing repair source receipt');
  check(fileDigest(path.dirname(ref.path),path.basename(ref.path))===ref.sha256, 'Repair source receipt changed');
  return read(ref.path);
}
export function repairIdentity(value) {
  check(value && typeof value.execution_id==='string' && /^[a-zA-Z0-9-]{1,128}$/.test(value.execution_id), 'Invalid predecessor execution');
  check(typeof value.continuation_id==='string' && /^[a-zA-Z0-9-]{1,128}$/.test(value.continuation_id), 'Invalid repair continuation');
  for (const ref of [value.terminal_receipt,value.review]) check(ref && typeof ref.path==='string' && path.isAbsolute(ref.path) && /^[a-f0-9]{64}$/.test(ref.sha256), 'Invalid repair receipt reference');
  check(value.mode===undefined || value.mode==='failed_review' || value.mode==='missing_execution_evidence', 'Invalid continuation mode');
  return {...(value.mode==='missing_execution_evidence'?{mode:value.mode}:{}),execution_id:value.execution_id,continuation_id:value.continuation_id,
    terminal_receipt:{path:value.terminal_receipt.path,sha256:value.terminal_receipt.sha256},review:{path:value.review.path,sha256:value.review.sha256}};
}
export function ticketPath(request,job) {
  const suffix=job.repairOf?'-repair-'+sha(job.repairOf.execution_id):'';
  return path.join(job.stateRoot,`parallel-ticket-${request.requestId}-${job.order}${suffix}.json`);
}
export function repairReceipts(repair) {
  const terminal=receipt(repair.terminal_receipt),review=receipt(repair.review);
  receipt(terminal.registration);
  receipt(review.reviewer?.receipt);
  return {terminal,review};
}
export function verifyRepair(request,job) {
  const repair=job.repairOf;
  const {terminal,review}=repairReceipts(repair);
  check(terminal.schema_version===1 && terminal.execution_id===repair.execution_id && terminal.issue_number===request.issue && terminal.request_id===request.requestId && terminal.transport_completed===true && terminal.state==='review' && terminal.exit_code===0 && terminal.cancel_requested===false && Number.isSafeInteger(terminal.pid) && terminal.pid>0 && !terminal.reporting_error && terminal.reporting?.ok===true && terminal.reporting?.state==='recorded_file', 'Predecessor transport is not a known completed execution');
  const registration=receipt(terminal.registration);
  check(registration.execution_id===terminal.execution_id && registration.worker_id===terminal.worker_id && registration.issue_number===request.issue && registration.request_id===request.requestId && registration.order===job.order && registration.editor_worker_id===job.id && registration.design_sha256===(job.designSha256??null) && registration.candidate?.root===job.cwd && registration.candidate.branch===terminal.candidate?.branch && registration.candidate.base_sha===terminal.candidate?.base_sha && (!job.workerId || job.workerId===terminal.worker_id), 'Predecessor registration differs from assignment');
  const producer=review.producer,reviewer=review.reviewer,policy=review.candidate?.audit_policy;
  const missing=repair.mode==='missing_execution_evidence';
  check((missing ? review.verdict==='unknown' && review.unknown_kind==='missing_execution_evidence' : review.verdict==='fail') && typeof review.reason==='string' && review.reason.trim() && review.design_sha256===registration.design_sha256, 'Continuation requires its bound failure or missing-evidence review');
  check(producer?.execution_id===terminal.execution_id && producer.worker_id===terminal.worker_id && producer.receipt?.path===repair.terminal_receipt.path && producer.receipt.sha256===repair.terminal_receipt.sha256 && reviewer?.worker_id && reviewer.worker_id!==producer.worker_id && typeof reviewer.conversation_id==='string' && reviewer.conversation_id, 'Independent repair reviewer binding missing');
  receipt(reviewer.receipt);
  check(review.candidate.root===job.cwd && policy?.request_id===request.requestId && typeof policy.source_ref==='string' && policy.source_ref.endsWith('/issues/'+request.issue) && candidateCurrent(review.candidate) && candidateCurrent({...terminal.candidate,audit_policy:policy}), 'Repair candidate changed');
  check(Array.isArray(review.criteria) && review.criteria.length && new Set(review.criteria.map(c=>c.id)).size===review.criteria.length && review.criteria.some(c=>missing ? c.met===null : c.met===false), 'No matching criterion to continue');
  if (missing) {
    check(Array.isArray(review.expected_criteria) && review.expected_criteria.length===review.criteria.length && new Set(review.expected_criteria.map(c=>c.id)).size===review.criteria.length && review.expected_criteria.every(c=>review.criteria.some(r=>r.id===c.id)), 'Incomplete original criteria coverage');
    check(review.review_files && Object.keys(review.review_files).length, 'Missing read provenance');
    for (const [file,hash] of Object.entries(review.review_files)) check(review.candidate.files.some(f=>f.path===file && f.sha256===hash) && fileDigest(job.cwd,file)===hash, 'Read provenance changed');
  }
  for (const criterion of review.criteria) {
    const unknown=missing && criterion.met===null && typeof criterion.missing_evidence==='string' && criterion.missing_evidence.trim();
    check(typeof criterion.id==='string' && criterion.id && (unknown || typeof criterion.met==='boolean') && Array.isArray(criterion.evidence) && (unknown || criterion.evidence.length), 'Incomplete continuation review evidence');
    for (const evidence of criterion.evidence) check((!missing || review.review_files[evidence.path]===evidence.sha256) && review.candidate.files.some(f=>f.path===evidence.path && f.sha256===evidence.sha256) && fileDigest(job.cwd,evidence.path)===evidence.sha256, 'Continuation review evidence changed');
  }
  const prefix=`parallel-ticket-${request.requestId}-${job.order}`;
  const names=fs.readdirSync(job.stateRoot).filter(name=>name===prefix+'.json' || new RegExp('^'+prefix+'-repair-[a-f0-9]{64}\\.json$').test(name));
  const previous=names.map(name=>read(path.join(job.stateRoot,name))).filter(record=>record.execution_id===repair.execution_id);
  check(previous.length===1 && previous[0].state==='review' && previous[0].transport_completed===true && previous[0].terminal_receipt?.path===repair.terminal_receipt.path && previous[0].terminal_receipt.sha256===repair.terminal_receipt.sha256 && previous[0].registration?.sha256===terminal.registration.sha256, 'Original terminal ticket missing or changed');
  return {terminal,registration,review};
}

export function previousResource(file,request,job,source) {
  const value=read(file);
  check(value.requestId===request.requestId && value.order===job.order && typeof value.output==='string' && path.resolve(`${value.output}.${job.id}.${source.terminal.execution_id}.registration.json`)===path.resolve(source.terminal.registration.path), 'Candidate resource belongs to another execution');
  return value;
}
