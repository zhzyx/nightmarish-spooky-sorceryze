// Private trusted-native-host adapter. JSON is evidence, never authorization.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {createHash, randomUUID} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {validateDecision} from '../../customizations/components/repository-dispatch/acceptance.mjs';

const MAX_BYTES=64*1024*1024, MAX_FILES=512;
const sha=b=>createHash('sha256').update(b).digest('hex');
const check=(v,m)=>{if(!v)throw Error(m);};
const git=(root,...args)=>execFileSync(process.env.GONGGONG_GIT||'git',['-C',root,...args],{windowsHide:true,maxBuffer:MAX_BYTES,timeout:60000});
const textGit=(root,...args)=>git(root,...args).toString('utf8').trim();
function checkoutBlob(root,name,oid) {
  // Ask Git for its built-in checkout conversions (EOL, ident, encoding),
  // using this worktree's attributes. Never run an external smudge/process
  // driver: a custom-filtered baseline may conservatively conflict instead.
  // Disable every configured driver, not merely the currently selected one:
  // changing a source-controlled attribute cannot select another executable.
  const drivers=new Set(git(root,'config','--null','--list').toString('utf8').split('\0').map(entry=>entry.split('\n')[0].match(/^filter\.(.+)\.(smudge|process|required)$/)?.[1]).filter(Boolean));
  const args=[];
  for(const driver of drivers) {
    check(!/[\x00-\x1f]/.test(driver),'Invalid Git filter name');
    args.push('-c',`filter.${driver}.smudge=`,'-c',`filter.${driver}.process=`,'-c',`filter.${driver}.required=false`);
  }
  return git(root,...args,'cat-file','--filters',`--path=${name}`,oid);
}
function safeAbsolute(file) {
  check(typeof file==='string'&&path.isAbsolute(file),'Absolute host path required');
  for(let p=path.resolve(file);;p=path.dirname(p)) {
    try {check(!fs.lstatSync(p).isSymbolicLink(),'Linked path rejected: '+p);}catch(e){if(e.code!=='ENOENT')throw e;}
    if(p===path.dirname(p))break;
  }
  return path.resolve(file);
}
function inside(root,file) {
  const rel=path.relative(root,file);
  check(rel&&!path.isAbsolute(rel)&&rel!=='..'&&!rel.startsWith('..'+path.sep),'Path outside boundary');
  return rel;
}
function target(root,rel) {
  check(typeof rel==='string'&&rel&&!path.isAbsolute(rel)&&!rel.includes('\\')&&!rel.split('/').some(p=>!p||['.','..','.git','.godot','.yuanheng'].includes(p)||/[<>:"|?*\x00-\x1f]/.test(p)||/[. ]$/.test(p)||/^(con|prn|aux|nul|com[0-9]|lpt[0-9])(\.|$)/i.test(p)),'Invalid project path');
  const file=path.resolve(root,rel);inside(root,file);return safeAbsolute(file);
}
function bytes(file) {
  safeAbsolute(file);
  try {const s=fs.lstatSync(file);check(s.isFile()&&s.nlink===1,'Nonregular or hardlinked file');check(s.size<=MAX_BYTES,'File exceeds limit');return fs.readFileSync(file);}catch(e){if(e.code==='ENOENT')return null;throw e;}
}
const hash=b=>b===null?null:sha(b);
const encode=b=>b===null?null:b.toString('base64');
const decode=b=>b===null?null:Buffer.from(b,'base64');
const indexState=(root,project,files)=>sha(git(root,'ls-files','--stage','-z','--',...files.map(f=>path.relative(root,path.join(project,f.path)).replaceAll('\\','/'))));
function durable(file,content) {
  safeAbsolute(file);const tmp=file+'.'+randomUUID()+'.tmp';
  const fd=fs.openSync(tmp,'wx',0o600);
  try {fs.writeFileSync(fd,content);fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
  fs.renameSync(tmp,file);
}
function live(r) {
  check(typeof r.request_nonce==='string'&&r.request_nonce.length>0&&r.request_nonce.length<=256,'Missing request nonce');
  const v=JSON.parse(fs.readFileSync(safeAbsolute(r.host_liveness_path),'utf8'));
  check(v.active===true&&v.request_nonce===r.request_nonce,'Host generation cancelled or unknown');
}
function binding(r) {
  live(r);
  const workspace=safeAbsolute(r.workspace_root),project=safeAbsolute(r.project_root),store=safeAbsolute(r.transaction_root);
  check(fs.realpathSync(workspace)===fs.realpathSync(textGit(workspace,'rev-parse','--show-toplevel')),'Destination must be repository root');
  check(project===workspace||inside(workspace,project),'Project outside workspace');
  check(bytes(path.join(project,'project.godot'))!==null,'Open Godot project required');
  check(store===path.join(workspace,'data-collection','outbox','project-integration'),'Unexpected host transaction directory');
  fs.mkdirSync(store,{recursive:true});safeAbsolute(store);
  return {workspace,project,store};
}
function receipt(r,p,file,state,extra={}) {
  return {ok:['planned','applied','rolled_back'].includes(state),request_nonce:r.request_nonce,state,plan_path:file,plan_sha256:sha(fs.readFileSync(file)),changed_count:p.files.length,changed_files:p.files.map(f=>f.path),...extra};
}
function withLock(workspace,store,fn) {
  // The old PID-only file cannot prove host identity. Preserve it for explicit
  // reconciliation; never unlink a lock based on a stale read.
  const legacy=path.join(store,'writer.lock');safeAbsolute(legacy);
  check(!fs.existsSync(legacy),'Unknown legacy integration writer lock');
  const root=fs.realpathSync(workspace),directory=fs.realpathSync(store);
  const ref='refs/gonggong/project-integration/'+sha(directory);
  const old=textGit(root,'for-each-ref','--format=%(objectname)',ref);
  if(old) {
    let owner;try {owner=JSON.parse(textGit(root,'cat-file','blob',old));}catch {throw Error('Unknown integration writer ownership');}
    check(owner?.version===1&&owner.root===root&&owner.store===directory&&
      typeof owner.nonce==='string'&&/^[a-f0-9-]{36}$/.test(owner.nonce)&&
      typeof owner.host==='string'&&Number.isSafeInteger(owner.pid)&&owner.pid>0&&
      ['active','released'].includes(owner.state),'Unknown integration writer ownership');
    if(owner.state==='active') {
      let dead=false;
      if(owner.host===os.hostname())try {process.kill(owner.pid,0);}catch(e){dead=e.code==='ESRCH';}
      check(dead,'Integration writer still active or unknown');
    }
  }
  const owner={version:1,root,store:directory,pid:process.pid,host:os.hostname(),nonce:randomUUID(),state:'active'};
  const object=value=>execFileSync(process.env.GONGGONG_GIT||'git',['-C',root,'hash-object','-w','--stdin'],
    {input:JSON.stringify(value),windowsHide:true,timeout:60000}).toString('utf8').trim();
  const active=object(owner);
  // Publish a complete immutable owner in one CAS. Losing recovery contenders
  // cannot replace the winner, even if both observed the same dead process.
  git(root,'update-ref',ref,active,old||'0'.repeat(active.length));
  try{return fn();}finally{
    // Release only our exact generation. Crashes on either side leave either
    // the previous generation or a fully identifiable recoverable owner.
    git(root,'update-ref',ref,object({...owner,state:'released'}),active);
  }
}
export function integrate(r) {
  const b=binding(r);
  return withLock(b.workspace,b.store,()=>{
    if(r.action==='plan')return plan(r,b);
    check(['apply','rollback'].includes(r.action),'Unknown integration action');
    const file=safeAbsolute(r.plan_path);check(path.dirname(file)===b.store&&/^[a-f0-9]{64}\.plan\.json$/.test(path.basename(file)),'Invalid plan location');
    check(fs.statSync(file).isFile()&&fs.statSync(file).size<=MAX_BYTES*3,'Invalid plan file');
    const raw=fs.readFileSync(file);check(sha(raw)===r.plan_sha256,'Pinned plan changed');
    const p=JSON.parse(raw);check(p.schema_version===1&&p.workspace_root===b.workspace&&p.project_root===b.project&&p.decision_sha256===sha(r.decision_json),'Plan binding changed');
    check(Array.isArray(p.files)&&p.files.length<=MAX_FILES,'Invalid file manifest');
    const journal=file+'.journal.json';safeAbsolute(journal);const j=JSON.parse(fs.readFileSync(journal,'utf8'));
    check(j.plan_sha256===r.plan_sha256,'Journal binding changed');
    if(r.action==='apply') {
      validateDecision(JSON.parse(r.decision_json),true);live(r);
      check(textGit(b.workspace,'rev-parse','HEAD')===p.target_head,'Target HEAD changed');
      check(indexState(b.workspace,b.project,p.files)===p.target_index,'Target index changed');
      if(j.state==='applied') {for(const f of p.files)check(hash(bytes(target(b.project,f.path)))===f.after_sha256,'Applied target changed: '+f.path);return receipt(r,p,file,j.state);}
      check(j.state==='planned','Interrupted transaction requires rollback');
      for(const f of p.files)check(hash(bytes(target(b.project,f.path)))===f.before_sha256,'Target drift: '+f.path);
    } else if(j.state==='rolled_back') {
      for(const f of p.files)check(hash(bytes(target(b.project,f.path)))===f.before_sha256,'Restored target changed: '+f.path);
      return receipt(r,p,file,j.state);
    }
    // A crash between intent and completion is reconciled from exact before/after
    // bytes. Unknown values are user edits and are never overwritten.
    const conflicts=[];
    if(r.action==='rollback')for(const f of p.files) {
      const current=hash(bytes(target(b.project,f.path)));
      if(current!==f.before_sha256&&(!j.attempted?.includes(f.path)||current!==f.after_sha256))conflicts.push(f.path);
    }
    if(conflicts.length)return receipt(r,p,file,'conflict',{conflicts});
    j.state=r.action==='apply'?'applying':'rolling_back';durable(journal,JSON.stringify(j));
    try {
      for(const f of (r.action==='apply'?p.files:[...p.files].reverse())) {
        live(r);const dest=target(b.project,f.path),before=r.action==='apply'?f.before_sha256:f.after_sha256;
        const content=decode(r.action==='apply'?f.after:f.before),desired=hash(content),current=hash(bytes(dest));
        check(desired===(r.action==='apply'?f.after_sha256:f.before_sha256),'Corrupt backup');
        if(current===desired)continue;
        check(current===before,'Concurrent target change: '+f.path);
        j.pending=f.path;j.attempted=[...new Set([...(j.attempted||[]),f.path])];durable(journal,JSON.stringify(j));live(r);
        check(hash(bytes(dest))===before,'Concurrent target change: '+f.path);
        if(content===null)fs.unlinkSync(dest);
        else {fs.mkdirSync(path.dirname(dest),{recursive:true});safeAbsolute(dest);durable(dest,content);fs.chmodSync(dest,r.action==='apply'?f.after_mode:f.before_mode);}
        j.completed=f.path;delete j.pending;durable(journal,JSON.stringify(j));
      }
      if(r.action==='apply')validateDecision(JSON.parse(r.decision_json),true);
      live(r);j.state=r.action==='apply'?'applied':'rolled_back';durable(journal,JSON.stringify(j));
      return receipt(r,p,file,j.state);
    }catch(e){j.state='reconcile_required';j.error=e.message;durable(journal,JSON.stringify(j));return receipt(r,p,file,j.state,{error:e.message});}
  });
}
function plan(r,b) {
  const d=JSON.parse(r.decision_json);validateDecision(d,true);live(r);
  check(d.criteria.every(c=>c.met!==false),'Failed criterion');
  const source=safeAbsolute(d.candidate.root);check(source!==b.workspace,'Source must be isolated');
  check(fs.realpathSync(textGit(source,'rev-parse','--path-format=absolute','--git-common-dir'))===fs.realpathSync(textGit(b.workspace,'rev-parse','--path-format=absolute','--git-common-dir')),'Different Git repository');
  const projectRel=path.relative(b.workspace,b.project).replaceAll('\\','/'),prefix=projectRel?projectRel+'/':'';
  const sourceProject=projectRel?target(source,projectRel):source;
  check(bytes(path.join(sourceProject,'project.godot'))!==null,'Candidate project missing');
  const head=textGit(b.workspace,'rev-parse','HEAD');
  let base=textGit(b.workspace,'merge-base',head,d.candidate.head);
  if(d.producer.execution_id) {
    // External workers start from a private snapshot which can include the
    // user's original uncommitted files. The validated registration pins it.
    const terminalRaw=bytes(safeAbsolute(d.producer.receipt.path));
    check(hash(terminalRaw)===d.producer.receipt.sha256,'Stale terminal receipt');
    const terminal=JSON.parse(terminalRaw),registrationRaw=bytes(safeAbsolute(terminal.registration.path));
    check(hash(registrationRaw)===terminal.registration.sha256,'External registration changed');
    base=JSON.parse(registrationRaw).candidate.base_sha;
    check(typeof base==='string'&&/^[a-f0-9]{40,64}$/.test(base),'Invalid snapshot base');
    check(textGit(source,'merge-base',base,d.candidate.head)===base,'Snapshot is not candidate ancestor');
  }
  const entries=git(b.workspace,'ls-tree','-r','-z',base).toString('utf8').split('\0').filter(Boolean);
  const baseline=new Map(entries.map(e=>{const [meta,name]=e.split('\t');return [name,meta.split(' ')];}));
  const candidates=new Map(d.candidate.files.map(f=>[f.path,f]));
  const names=[...new Set([...baseline.keys(),...candidates.keys()])].filter(n=>n.startsWith(prefix)).sort();
  const staged=new Set(git(b.workspace,'diff','--cached','--name-only','-z').toString('utf8').split('\0'));
  const files=[],conflicts=[];let total=0;
  for(const name of names) {
    const rel=name.slice(prefix.length);const old=baseline.get(name),candidate=candidates.get(name);
    // Host caches are never production assets.
    if(rel.split('/').some(s=>['.godot','.git','.yuanheng'].includes(s))||rel.startsWith('data-collection/outbox/'))continue;
    const src=target(sourceProject,rel),dest=target(b.project,rel);
    check(!old||['100644','100755'].includes(old[0]),'Unsupported Git entry: '+name);
    const original=old?checkoutBlob(b.workspace,name,old[2]):null;
    const sourceOriginal=old?checkoutBlob(source,name,old[2]):null;
    const after=candidate?bytes(src):null;
    check(!candidate||hash(after)===candidate.sha256,'Source drift: '+name);
    if(hash(sourceOriginal)===hash(after))continue;
    const before=bytes(dest);
    if(hash(before)===hash(after))continue;
    if(hash(before)!==hash(original)||staged.has(name)){conflicts.push(rel);continue;}
    total+=(before?.length||0)+(after?.length||0);check(total<=MAX_BYTES,'Transaction bytes exceed limit');
    files.push({path:rel,before:encode(before),after:encode(after),before_sha256:hash(before),after_sha256:hash(after),before_mode:before===null?null:fs.statSync(dest).mode&0o777,after_mode:after===null?null:fs.statSync(src).mode&0o777});check(files.length<=MAX_FILES,'Transaction file count exceeds limit');
  }
  if(conflicts.length)return {ok:false,request_nonce:r.request_nonce,state:'conflict',conflicts,error:'Dirty target conflicts',changed_files:[],changed_count:0};
  validateDecision(d,true);live(r);
  const p={schema_version:1,workspace_root:b.workspace,project_root:b.project,source_root:source,base_sha:base,target_head:head,target_index:indexState(b.workspace,b.project,files),decision_sha256:sha(r.decision_json),files};
  const raw=JSON.stringify(p),file=path.join(b.store,sha(raw)+'.plan.json'),journal=file+'.journal.json';
  if(fs.existsSync(file)){check(sha(fs.readFileSync(file))===sha(raw),'Existing plan corrupt');check(fs.existsSync(journal),'Missing transaction journal');}
  else {durable(file,raw);durable(journal,JSON.stringify({plan_sha256:sha(raw),state:'planned'}));}
  return receipt(r,p,file,JSON.parse(fs.readFileSync(journal,'utf8')).state);
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  let r;
  try {const raw=fs.readFileSync(0);check(raw.length<=32*1024*1024,'Request exceeds limit');r=JSON.parse(raw);console.log(JSON.stringify(integrate(r)));}
  catch(e){console.log(JSON.stringify({ok:false,request_nonce:r?.request_nonce,state:'rejected',error:e.message}));process.exitCode=1;}
}
