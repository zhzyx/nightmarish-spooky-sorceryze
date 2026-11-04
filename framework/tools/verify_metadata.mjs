// Internal child of verify_framework.py. This output is neither a permit nor a formal verification result.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {local, assertAdmission} from './admission.mjs';
import {checkFrameworkReporting} from './reporting.mjs';

try {
  const [rootArg,mode,...extra]=process.argv.slice(2);
  if(extra.length||!['formal','candidate'].includes(mode))throw Error('Invalid metadata invocation');
  const root=fs.realpathSync(rootArg), hashes=JSON.parse(fs.readFileSync(0,'utf8'));
  const read=p=>JSON.parse(fs.readFileSync(local(root,p),'utf8'));
  const hashFile=p=>{
    const name=path.relative(root,p).split(path.sep).join('/'), value=hashes[name];
    if(!/^[a-f0-9]{64}$/.test(value??''))throw Error('Missing snapshot hash: '+name);
    return value;
  };
  const registry=read('framework-manifest.json'),lock=read('foundation.lock.json');
  for(const agent of registry.agents){
    const records=agent.candidate_files.map(p=>({path:p,sha256:hashFile(local(root,p))})).sort((a,b)=>a.path<b.path?-1:a.path>b.path?1:0);
    const digest=crypto.createHash('sha256').update(records.map(x=>x.path+'\0'+x.sha256+'\n').join('')).digest('hex');
    if(digest!==agent.candidate_digest)throw Error('Candidate content changed');
    if(mode==='formal')assertAdmission(root,registry,agent,lock,digest);
  }
  console.log(JSON.stringify({metadata_checked:true,...checkFrameworkReporting(root,hashFile)}));
} catch(error) {console.error(error.message);process.exitCode=1;}
