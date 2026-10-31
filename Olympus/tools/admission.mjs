import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
export function local(root,relative){
  if(typeof relative!=='string'||path.isAbsolute(relative)||/[\0\r\n]/.test(relative))throw Error('Invalid framework path');
  const absolute=fs.realpathSync(path.resolve(root,relative));
  const rel=path.relative(fs.realpathSync(root),absolute);
  if(rel.startsWith('..')||path.isAbsolute(rel))throw Error('Path escapes framework');
  return absolute;
}
function timestamp(value){
  if(typeof value!=='string'||!/^\d{4}-\d\d-\d\dT.+(?:Z|[+-]\d\d:\d\d)$/.test(value)||!Number.isFinite(Date.parse(value)))throw Error('Invalid approval timestamp');
  return Date.parse(value);
}
export function assertAdmission(root,registry,agent,lock,digest){
  const read=p=>JSON.parse(fs.readFileSync(local(root,p),'utf8'));
  const policy=read('contracts/admission-policy.json'),p=read(agent.admission_pass),a=p.approval,r=p.review;
  if(p.template!==false||p.status!=='approved'||p.event!==policy.event||p.phase!==policy.phase)throw Error('Invalid admission status, event or phase');
  if(p.subject?.id!==agent.id||p.subject.version_or_digest?.version!==agent.version||p.subject.version_or_digest?.candidate_digest!==digest)throw Error('Admission subject mismatch');
  if(!Array.isArray(p.subject.scope)||JSON.stringify([...p.subject.scope].sort())!==JSON.stringify([...policy.scope].sort()))throw Error('Admission scope mismatch');
  if(p.baseline?.foundation_sha256!==lock.sha256||p.baseline.foundation_version!==lock.version||p.baseline.zeus_version!==registry.zeus_version||p.baseline.policy_version!==registry.version)throw Error('Admission baseline mismatch');
  if(r?.olympus_framework!==policy.review_status||r?.concision?.status!==policy.review_status||r?.applicable_validation!==policy.review_status||r?.independence!==policy.review_independence)throw Error('Admission review incomplete');
  if(!r.evaluator_id||policy.zeus_principles.some(k=>r.zeus?.[k]!==policy.review_status))throw Error('Zeus review incomplete');
  if(!Array.isArray(r.evidence_refs)||!r.evidence_refs.length)throw Error('Review evidence missing');
  for(const ref of r.evidence_refs)local(root,ref);
  if(!a?.approver_id||!a?.authority_ref||!a?.decision_evidence_ref||a.approver_id===r.evaluator_id||a.revocation_ref||a.superseded_by)throw Error('Approval absent, self-issued or inactive');
  local(root,a.decision_evidence_ref);
  if(a.valid_until_or_task_end!==policy.validity||!Object.hasOwn(a,'expires_at'))throw Error('Approval validity missing or outside scope');
  const approved=timestamp(a.approved_at),now=Date.now();
  if(approved>now)throw Error('Approval is in the future');
  if(a.expires_at!==null){const expiry=timestamp(a.expires_at);if(expiry<=now||expiry<=approved)throw Error('Approval expired');}
  return true;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{
    const [rootArg,id,...extra]=process.argv.slice(2);if(!rootArg||!id||extra.length)throw Error('Usage: admission.mjs ROOT AGENT-ID');
    const root=fs.realpathSync(rootArg),read=p=>JSON.parse(fs.readFileSync(local(root,p),'utf8')),m=read('framework-manifest.json'),lock=read('foundation.lock.json');
    const matches=m.agents.filter(x=>x.id===id);if(matches.length!==1)throw Error('Agent not uniquely registered');const a=matches[0];
    const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
    const records=a.candidate_files.map(p=>({path:p,sha256:sha(fs.readFileSync(local(root,p)))})).sort((x,y)=>x.path<y.path?-1:x.path>y.path?1:0);
    const digest=sha(Buffer.from(records.map(x=>x.path+'\0'+x.sha256+'\n').join(''),'utf8'));
    if(digest!==a.candidate_digest)throw Error('Candidate content changed');
    assertAdmission(root,m,a,lock,digest);console.log('passed local admission record checks; host authority not authenticated');
  }catch(error){console.error(error.message);process.exitCode=1;}
}
