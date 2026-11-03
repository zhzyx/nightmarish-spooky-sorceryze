import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {local} from './admission.mjs';
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const dependencies=['contracts/hermes-reporting.json','tools/reporting.mjs','tools/hermes-report.py','agents/hermes/scripts/ledger.py','agents/hermes/scripts/telemetry.py','agents/hermes/references/data-contract.md','agents/hermes/references/telemetry.md'];
const read=(root,p)=>JSON.parse(fs.readFileSync(local(root,p),'utf8'));
export function checkProfile(root,ownerRoot,profilePath,expected){
  const p=read(ownerRoot,profilePath),policy=read(root,'contracts/hermes-reporting.json');
  if(p.schema_version!==1||p.required!==true||p.policy!=='contracts/hermes-reporting.json'||p.policy_id!==policy.policy_id||p.reporter!=='tools/hermes-report.py'||p.runtime_binding!=='host_required'||p.runtime_connected!==false)throw Error('Invalid reporting contract or false runtime claim');
  for(const k of ['kind','id','version','entry'])if(p.component?.[k]!==expected[k])throw Error('Reporting component mismatch: '+k);
  if(p.component.entry_sha256!==hash(local(ownerRoot,expected.entry)))throw Error('Reporting entry fingerprint stale');
  if(JSON.stringify(p.events)!==JSON.stringify(policy.events))throw Error('Reporting events missing or changed');
  if(!p.dependencies||JSON.stringify(Object.keys(p.dependencies).sort())!==JSON.stringify([...dependencies].sort()))throw Error('Reporting dependency set mismatch');
  for(const dep of dependencies)if(p.dependencies[dep]!==hash(local(root,dep)))throw Error('Reporting dependency stale: '+dep);
  return p;
}
export function checkAgentReporting(root,a){
  const meta=read(root,a.manifest);
  if(meta.reporting!==a.reporting)throw Error('Agent reporting path mismatch');
  return checkProfile(root,root,a.reporting,{kind:'agent',id:a.id,version:a.version,entry:a.entry});
}
export function checkFrameworkReporting(root){
  const m=read(root,'framework-manifest.json');
  const outputs=[];
  for(const a of m.agents)outputs.push(checkAgentReporting(root,a));
  const skills=[...m.skills,m.upstream_skill_reporting];
  if(!m.upstream_skill_reporting)throw Error('Upstream skill reporting adapter missing');
  for(const s of skills)outputs.push(checkProfile(root,root,s.reporting,{kind:'skill',id:s.name,version:s.version,entry:s.path}));
  return {profiles:outputs.length,configured:true,runtime_connected:false};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{
    const [mode,rootArg,ownerArg,...extra]=process.argv.slice(2);const root=fs.realpathSync(rootArg);
    if(extra.length)throw Error('Unexpected arguments');
    if(mode==='--all'&&!ownerArg)console.log(JSON.stringify(checkFrameworkReporting(root)));
    else if(mode==='--component'&&ownerArg){
      const owner=fs.realpathSync(ownerArg),meta=read(owner,'component.json');
      if(meta.state!=='candidate_pending_review'||meta.governance_root!=='zeus'||!['agent','skill'].includes(meta.kind))throw Error('Generated component must be governed and remain a review candidate');
      console.log(JSON.stringify(checkProfile(root,owner,meta.reporting,meta)));
    }else throw Error('Usage: reporting.mjs --all ROOT | --component ROOT COMPONENT-DIR');
  }catch(e){console.error(e.message);process.exitCode=1;}
}
