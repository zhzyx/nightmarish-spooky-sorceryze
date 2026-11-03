import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {local,assertAdmission} from './admission.mjs';
import {checkAgentReporting} from './reporting.mjs';
const ownRoot=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
export function buildContext(root,id,mandate){
  root=fs.realpathSync(root);
  execFileSync(process.env.GONGGONG_PYTHON || 'python', [path.join(root,'tools/package_integrity.py'),'--root',root], {stdio:'pipe'});
  const read=p=>JSON.parse(fs.readFileSync(local(root,p),'utf8'));
  const registry=read('framework-manifest.json');
  const matches=registry.agents.filter(a=>a.id===id);
  if(matches.length!==1)throw Error('Agent not uniquely registered');
  const a=matches[0],m=read(a.manifest),lock=read('foundation.lock.json');
  if(m.id!==a.id||m.version!==a.version||m.governance_root!=='yuanheng')throw Error('Agent metadata mismatch');
  if(sha(fs.readFileSync(local(root,'FOUNDATION.md')))!==lock.sha256)throw Error('Frozen foundation mismatch');
  if(!Array.isArray(a.candidate_files)||!a.candidate_files.length)throw Error('Candidate fingerprint missing');
  const records=a.candidate_files.map(p=>({path:p,sha256:sha(fs.readFileSync(local(root,p)))})).sort((x,y)=>x.path<y.path?-1:x.path>y.path?1:0);
  const digest=sha(Buffer.from(records.map(x=>x.path+'\0'+x.sha256+'\n').join(''),'utf8'));
  if(digest!==a.candidate_digest)throw Error('Candidate content changed');
  assertAdmission(root,registry,a,lock,digest);
  const reporting=checkAgentReporting(root,a);
  for(const field of ['feature_id','outcome','authority_ref'])if(typeof mandate[field]!=='string'||!mandate[field].trim())throw Error('Missing host mandate: '+field);
  const files=['upstream/yuanheng/core.md','upstream/yuanheng/agents/yuanheng.md','FOUNDATION.md',a.entry];
  return files.map(p=>fs.readFileSync(local(root,p),'utf8')).join('\n\n')+'\n\nDiting reporting: '+a.reporting+'; bind the current tenant/request/source/outbox/sink through the host before execution. Configuration is not delivery; require a committed receipt.\n'+'\nHost mandate (actual identity and permission must be authenticated by host):\n'+JSON.stringify(mandate)+'\n';
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{
    const [id,mandateFile,...extra]=process.argv.slice(2);
    if(!id||!mandateFile||extra.length)throw Error('Usage: node tools/agent-context.mjs AGENT-ID HOST-MANDATE.json; context only, no worker or permission grant');
    process.stdout.write(buildContext(ownRoot,id,JSON.parse(fs.readFileSync(path.resolve(mandateFile),'utf8'))));
  }catch(error){console.error(error.message);process.exitCode=1;}
}
