import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const check = (ok, why) => {if (!ok) throw Error(why);};
const git = (root, ...args) => execFileSync(process.env.GONGGONG_GIT || 'git', ['-C', root, ...args], {encoding:'utf8',maxBuffer:32*1024*1024,windowsHide:true});

export function fileDigest(root, relative) {
  check(typeof relative === 'string' && relative && !path.isAbsolute(relative) && !relative.split(/[\\/]/).some(p => ['..','.git','.yuanheng',''].includes(p)), 'Invalid evidence path');
  const target = path.resolve(root,relative);
  for (let current = target; ; current = path.dirname(current)) {
    try {check(!fs.lstatSync(current).isSymbolicLink(), 'Linked candidate/evidence');}
    catch (error) {if (error.code !== 'ENOENT') throw error;}
    if (current === path.parse(current).root) break;
  }
  if (!fs.existsSync(target)) return null;
  check(fs.statSync(target).isFile(), 'Candidate is not a regular file');
  return sha(fs.readFileSync(target));
}

export function captureCandidate(root, auditPolicy) {
  root = fs.realpathSync(root);
  check(fs.realpathSync(git(root,'rev-parse','--show-toplevel').trim()) === root, 'Candidate must be repository root');
  const paths = [...new Set(git(root,'ls-files','--cached','--others','--exclude-standard','-z').split('\0').filter(p => p && !p.startsWith('.yuanheng/'))) ].sort();
  const files = paths.map(p => ({path:p,sha256:fileDigest(root,p)}));
  return {root,branch:git(root,'symbolic-ref','--short','HEAD').trim(),head:git(root,'rev-parse','HEAD').trim(),files_sha256:sha(JSON.stringify(files)),files,...(auditPolicy ? {audit_policy:auditPolicy} : {})};
}

const canonical = value => JSON.stringify(value && typeof value === 'object' ? Array.isArray(value) ? value.map(v=>JSON.parse(canonical(v))) : Object.fromEntries(Object.keys(value).sort().map(k=>[k,JSON.parse(canonical(value[k]))])) : value);
function newHostAudit(root, file, policy, tracked) {
  if (!policy || !/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}$/.test(policy.tenant_id) || !/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}$/.test(policy.request_id) || tracked.has(file.path)) return false;
  const prefix=`gonggong-diting-data/events/${policy.tenant_id}/${policy.request_id}/`;
  if (!file.path.startsWith(prefix) || !/^(host-context-[a-f0-9]{32}|godot-event-[0-9]+-[0-9]+)\.json$/.test(file.path.slice(prefix.length)) || file.sha256 === null) return false;
  const e=JSON.parse(fs.readFileSync(path.join(root,file.path),'utf8'));
  const required=['schema_version','event_id','tenant_id','request_id','kind','occurred_at','source_ref','agent','payload','evidence_refs','sha256'];
  if (!required.every(k=>Object.hasOwn(e,k)) || Object.keys(e).some(k=>!required.includes(k)&&k!=='supersedes') || e.schema_version!==1 || e.tenant_id!==policy.tenant_id || e.request_id!==policy.request_id || e.source_ref!==policy.source_ref || file.path!==prefix+e.event_id+'.json') return false;
  if (!['request','step','message','direction_error','correction','quality_issue','rework','handoff','coverage','request_end','analysis'].includes(e.kind) || !/(Z|[+-][0-9]{2}:[0-9]{2})$/.test(e.occurred_at) || !Number.isFinite(Date.parse(e.occurred_at)) || !Array.isArray(e.evidence_refs) || new Set(e.evidence_refs).size!==e.evidence_refs.length || e.evidence_refs.some(r=>typeof r!=='string'||!/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}$/.test(r)) || (e.supersedes!==undefined && (typeof e.supersedes!=='string'||!/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}$/.test(e.supersedes)))) return false;
  if (!e.agent || Object.keys(e.agent).sort().join(',')!=='definition_sha256,id,origin,version' || Object.values(e.agent).some(v=>typeof v!=='string'||!v.trim()) || !/^[a-f0-9]{64}$/.test(e.agent.definition_sha256) || !e.payload || Array.isArray(e.payload) || typeof e.payload!=='object') return false;
  if (e.event_id.startsWith('host-context-')) {
    if(e.kind!=='request'||e.agent.id!=='gonggong-host-adapter'||e.agent.origin!=='gonggong-host-adapter'||e.payload.issue?.url!==policy.source_ref||typeof e.payload.context_accepted!=='boolean')return false;
  } else if (e.payload.binding?.request_ref!==policy.request_id || e.payload.binding?.tenant_id!==policy.tenant_id || e.payload.binding?.source_ref!==policy.source_ref || typeof e.payload.phase!=='string'||typeof e.payload.status!=='string') return false;
  const body={...e};delete body.sha256;
  return /^[a-f0-9]{64}$/.test(e.sha256) && sha(canonical(body))===e.sha256;
}

function candidateMatches(candidate, actual, allowLedgerCommits = false) {
  try {
    if (actual.root !== candidate.root || actual.branch !== candidate.branch || sha(JSON.stringify(candidate.files))!==candidate.files_sha256) return false;
    const old=new Map(candidate.files.map(f=>[f.path,f.sha256]));
    const current=new Map(actual.files.map(f=>[f.path,f.sha256]));
    if(old.size!==candidate.files.length || candidate.files.some(f=>!current.has(f.path)||current.get(f.path)!==f.sha256))return false;
    const tracked=new Set(git(candidate.root,'ls-files','--cached','-z').split('\0'));
    if(actual.files.some(f=>!old.has(f.path)&&!newHostAudit(candidate.root,f,candidate.audit_policy,tracked)))return false;
    if (actual.head === candidate.head) return true;
    if (!allowLedgerCommits) return false;
    git(candidate.root,'merge-base','--is-ancestor',candidate.head,actual.head);
    // Ledger review itself creates a commit. Every intervening commit must only
    // change the ledger; an unrelated commit and revert is still stale.
    const commits=git(candidate.root,'rev-list',candidate.head+'..'+actual.head).trim().split('\n');
    return commits.every(commit=>{
      const changed=git(candidate.root,'diff-tree','--no-commit-id','--name-only','-r',commit).trim().split('\n').filter(Boolean);
      return changed.length>0 && changed.every(p=>p === '.yuanheng/state.json' || p.startsWith('.yuanheng/issues/'));
    });
  } catch {return false;}
}

export function verifiedCurrentCandidate(candidate, allowLedgerCommits = false) {
  const actual=captureCandidate(candidate.root,candidate.audit_policy);
  check(candidateMatches(candidate,actual,allowLedgerCommits),'Stale candidate');
  return actual;
}

export function candidateCurrent(candidate, allowLedgerCommits = false) {
  try {verifiedCurrentCandidate(candidate,allowLedgerCommits);return true;}
  catch {return false;}
}

export function terminalReceiptsCurrent(receipts) {
  try {return Array.isArray(receipts)&&receipts.length===2&&receipts.every(r=>path.isAbsolute(r.path)&&/^[a-f0-9]{64}$/.test(r.sha256)&&fileDigest(path.dirname(r.path),path.basename(r.path))===r.sha256);}
  catch {return false;}
}
