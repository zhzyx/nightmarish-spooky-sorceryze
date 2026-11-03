import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
const types=new Set(['references','uses','extends','consumes','requires']);
const hash=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const read=file=>JSON.parse(fs.readFileSync(file,'utf8').replace(/^\uFEFF/,''));
const check=(ok,message)=>{if(!ok)throw Error(message);};
const validId=id=>typeof id==='string'&&/^[A-Za-z0-9_-]+$/.test(id);
const write=(file,value)=>{fs.writeFileSync(file+'.tmp',JSON.stringify(value,null,2)+'\n');fs.renameSync(file+'.tmp',file);};
function local(root,file){
  check(typeof file==='string'&&!path.isAbsolute(file),'来源必须是项目相对路径');
  const resolved=fs.realpathSync(path.resolve(root,file)),rel=path.relative(fs.realpathSync(root),resolved);
  check(rel&&!rel.startsWith('..')&&!path.isAbsolute(rel)&&!rel.split(path.sep).includes('.git'),'来源路径越界');
  check(fs.statSync(resolved).isFile(),'来源必须为文件');return resolved;
}
function locked(root,fn){
  const lock=path.join(root,'features','.mapping.lock');const fd=fs.openSync(lock,'wx');
  try{return fn();}finally{fs.closeSync(fd);fs.unlinkSync(lock);}
}
export function build(root){
  const ledger=read(path.join(root,'.zeus/state.json'));
  const features=[];
  for(const entry of fs.readdirSync(path.join(root,'features'),{withFileTypes:true})){
    if(!entry.isDirectory()||!validId(entry.name))continue;
    const dir=path.join(root,'features',entry.name),file=path.join(dir,'feature.json');if(!fs.existsSync(file))continue;
    const f=read(file),plan=ledger.plans.find(p=>p.id===f.plan),mf=path.join(dir,'memory.json');
    const memory=fs.existsSync(mf)?read(mf):null;
    const sources=(memory?.sources||[]).map(s=>{let state='missing';try{state=hash(local(root,s.path))===s.sha256?'current':'stale';}catch{}return {...s,state};});
    const capabilities=(memory?.capabilities||[]).map(c=>{
      const source=sources.find(s=>s.path===c.source),tasks=c.taskIds.map(id=>ledger.tasks.find(t=>t.id===id));
      const taskStates=tasks.map((t,i)=>({id:c.taskIds[i],status:t?.status||'missing',owner:t?.owner||null,blocker:t?.blocker||null}));
      const accepted=tasks.length>0&&tasks.every(t=>t&&plan?.tasks.includes(t.id)&&t.status==='done'&&t.review?.verdict==='pass'&&t.artifacts.length>0&&t.artifacts.every(a=>{try{return hash(local(root,a.path))===a.sha256;}catch{return false;}}));
      return {...c,availability:source?.state!=='current'?'stale':accepted?'verified':tasks.some(t=>t?.status==='blocked')?'blocked':'unverified',taskStates};
    });
    features.push({id:f.id,title:f.title,ownership:plan?.ownership||f.ownership||null,plan:f.plan,memory,sources,capabilities});
  }
  const edges=features.flatMap(f=>(f.memory?.relations||[]).map(r=>{
    const target=features.find(t=>t.id===r.toFeature),cap=target?.capabilities.find(c=>c.id===r.toCapability);
    return {fromFeature:f.id,...r,resolution:!target?'missing_feature':r.toCapability&&!cap?'missing_capability':'resolved',targetAvailability:cap?.availability||'unknown'};
  }));
  return {schemaVersion:1,ledgerId:ledger.ledgerId||null,ledgerEvent:ledger.events.length,ledgerTime:ledger.events.at(-1)?.time||null,features,edges};
}
export function refresh(root){
  const graph=build(root);write(path.join(root,'features/mapping.json'),graph);
  const safe=x=>String(x??'—').replace(/[\r\n|]/g,' ');
  const text='# Feature 关联索引\n\n派生于宙斯事件 #'+graph.ledgerEvent+'；账本时间 '+graph.ledgerTime+'。记忆仅供导航，执行前回查原文。\n\n'+graph.features.map(f=>`- [${safe(f.id)} ${safe(f.title)}](${encodeURIComponent(f.id)}/index.md)：主责 ${safe(f.ownership?.primaryOwner)}；记忆 ${f.memory?'已登记':'尚无'}；能力 ${f.capabilities.map(c=>safe(c.id)+'='+c.availability).join(', ')||'未登记'}`).join('\n')+'\n\n## 关联\n\n'+graph.edges.map(e=>`- ${safe(e.fromFeature)}:${safe(e.fromClause)} → ${safe(e.toFeature)}:${safe(e.toCapability)} [${e.type}] ${safe(e.reason)}；${e.resolution} / ${e.targetAvailability}`).join('\n')+'\n';
  const file=path.join(root,'features/mapping.md');if(!fs.existsSync(file)||fs.readFileSync(file,'utf8')!==text)fs.writeFileSync(file,text);
  return graph;
}
export function register(root,id,input){
  check(validId(id),'无效 feature ID');const dir=path.join(root,'features',id),f=read(path.join(dir,'feature.json'));
  check(typeof input.summary==='string'&&input.summary.trim()&&input.summary.length<=3000,'需要不超过3000字符的精简摘要');
  for(const k of ['sources','capabilities','relations'])check(Array.isArray(input[k]),k+' 必须为数组');
  const sources=input.sources.map(s=>({...s,sha256:hash(local(root,s.path))}));check(sources.length>0,'至少提供一个权威来源');
  const ledger=read(path.join(root,'.zeus/state.json')),plan=ledger.plans.find(p=>p.id===f.plan),seen=new Set();
  for(const c of input.capabilities){
    check(validId(c.id)&&!seen.has(c.id),'能力ID必须有效且唯一');seen.add(c.id);
    check(typeof c.contract==='string'&&c.contract.trim()&&sources.some(s=>s.path===c.source),'能力需要契约概述及已登记来源');
    check(Array.isArray(c.taskIds)&&c.taskIds.every(t=>plan?.tasks.includes(t)),'能力仅关联当前 feature 的工单');
  }
  for(const r of input.relations)check(types.has(r.type)&&validId(r.toFeature)&&typeof r.fromClause==='string'&&r.fromClause&&r.reason&&(!r.toCapability||validId(r.toCapability)),'关联缺少有效类型、条款、目标或理由');
  const memory={...input,featureId:id,sources,recordedAt:new Date().toISOString(),ledgerEvent:ledger.events.length};
  const current=path.join(dir,'memory.json');
  if(fs.existsSync(current)){const history=path.join(dir,'memory-history');fs.mkdirSync(history,{recursive:true});fs.copyFileSync(current,path.join(history,crypto.randomUUID()+'.json'));}
  write(current,memory);return refresh(root);
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{
    const [rootArg,command,id,input]=process.argv.slice(2),root=path.resolve(rootArg||'.');
    check(['refresh','register','query'].includes(command),'用法：feature-memory.mjs ROOT register ID input.json | refresh | query ID');
    const result=locked(root,()=>command==='register'?register(root,id,read(input)):refresh(root));
    if(command==='query'){
      const feature=result.features.find(f=>f.id===id);check(feature,'feature 不存在');
      const outgoing=result.edges.filter(e=>e.fromFeature===id),incoming=result.edges.filter(e=>e.toFeature===id);
      console.log(JSON.stringify({ledgerEvent:result.ledgerEvent,feature,outgoing,incoming,dependencies:result.features.filter(f=>outgoing.some(e=>e.toFeature===f.id)).map(({memory,...f})=>f)},null,2));
    }else console.log(JSON.stringify({features:result.features.length,edges:result.edges.length,ledgerEvent:result.ledgerEvent}));
  }catch(e){console.error(e.message);process.exitCode=1;}
}
