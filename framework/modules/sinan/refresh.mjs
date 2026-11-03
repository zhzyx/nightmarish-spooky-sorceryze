import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {board,followUpTracking} from './coordinator.mjs';

const types = new Set(['request.created','ticket.changed','dependency.changed','decision.recorded','execution.finished','execution.failed','user.requested','scope.changed','release.completed','source.changed','report.delivered']);
const BEGIN = '<!-- sinan:begin -->', END = '<!-- sinan:end -->';
const escape = value => String(value ?? '—').replace(/[\r\n]+/g, ' ').replace(/\|/g, '\\|').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const within = (root, target) => {const r=path.relative(root,target);return !r || (r!=='..'&&!r.startsWith('..'+path.sep)&&!path.isAbsolute(r));};
function noLinks(target) {
  let cursor=path.parse(target).root;
  for(const part of target.slice(cursor.length).split(path.sep).filter(Boolean)) {
    cursor=path.join(cursor,part);
    try {if(fs.lstatSync(cursor).isSymbolicLink())throw Error('Symlink/reparse path prohibited: '+target);} catch(e) {if(e.code!=='ENOENT')throw e;}
  }
}
function safeTarget(target, root, protectedFiles) {
  noLinks(target);
  // A missing document directory is a local I/O gap, not permission to create it.
  // Canonicalize its nearest existing ancestor while retaining lexical containment.
  let ancestor=path.dirname(target);
  while(!fs.existsSync(ancestor)&&path.dirname(ancestor)!==ancestor)ancestor=path.dirname(ancestor);
  const parent=fs.realpathSync(ancestor);
  if(!within(root,parent)||!within(root,target))throw Error('Target outside canonical write boundary: '+target);
  if(target.split(path.sep).some(p=>['.yuanheng','.git'].includes(p.toLowerCase())))throw Error('Protected ledger or repository path');
  for(const file of protectedFiles) {
    if(path.relative(file,target)==='')throw Error('Cannot overwrite registry or source ledger');
    if(fs.existsSync(file)&&fs.existsSync(target)) {
      const a=fs.statSync(file),b=fs.statSync(target);
      if(a.dev===b.dev&&a.ino===b.ino)throw Error('Target aliases registry or source ledger');
    }
  }
  if(fs.existsSync(target)&&!fs.statSync(target).isFile())throw Error('Target must be a regular file');
  return target;
}
function atomicWrite(target, content) {
  if(fs.existsSync(target)&&fs.readFileSync(target,'utf8')===content)return;
  const temp=target+'.tmp-'+crypto.randomUUID();
  try {fs.writeFileSync(temp,content,{flag:'wx'});fs.renameSync(temp,target);} finally {if(fs.existsSync(temp))fs.unlinkSync(temp);}
}
function nextStep(t,parent) {
  if(parent)return '待核验整体目标、验收与外部权威状态并对账；子项完成不自动关闭父项';
  if(t.problems.length)return '关联适用来源的工单并交责任方调查/修复；继续无关授权工作，仅限制受影响操作';
  return ({open:'由宿主核验授权与容量后派发',running:'等待真实执行回执',review:'由有权验收者核验成果',blocked:'由责任人解除阻塞',done:'核对交付、外部权威回读与采集回执'}[t.status]||'核验未知源状态');
}
function render(snapshot, type, reference, tickets, parents=[]) {
  const items=tickets?snapshot.items.filter(t=>tickets.includes(t.key)):snapshot.items;
  const lines=[`触发：${escape(type)}；来源：${escape(reference)}`, '',
    `覆盖：已登记来源 ${snapshot.sourcesRegistered} 个，成功读取 ${snapshot.sourcesRead} 个。未登记来源未知。`, '',
    '| 工单 | 标题 | 源状态 | 标签 | 责任人 | 阻塞或待处理 | 验收证据有效 | 依赖 | 下一步 |',
    '| --- | --- | --- | --- | --- | --- | --- | --- | --- |'];
  for(const t of items)lines.push('| '+[t.key,t.title,t.status,t.labels.join(', '),t.owner,[...t.problems,t.blocker?JSON.stringify(t.blocker):''].filter(Boolean).join('; '),t.acceptanceValid?'是':'未通过或未验收',`硬: ${t.dependsOn.join(', ')}; 软: ${t.softDependencies.join(', ')}`,nextStep(t,parents.includes(t.key))].map(escape).join(' | ')+' |');
  for(const ticket of tickets||[])if(!items.some(t=>t.key===ticket))lines.push('',`读取缺口：${escape(ticket)} 来源未知或不可读，待权威来源核验。`);
  if(!items.length)lines.push('','本次未读取到工单；不代表所有项目均无任务。');
  const ready=snapshot.ready.filter(k=>items.some(t=>t.key===k));
  lines.push('','就绪候选（实际派发前仍需宿主核验权限、容量、依赖及回执）：',...ready.map(k=>'- '+escape(k)));
  if(!ready.length)lines.push('无；本次处理结束，不安排时间唤醒。');
  const followUps=snapshot.followUps.filter(f=>!tickets||tickets.includes(f.ticket));
  if(followUps.length)lines.push('','问题处理候选（宿主关联适用来源工单并核验授权后派发）：',...followUps.map(f=>'- '+escape(`${f.key} | ${f.owner} | ${f.nextAction}`)));
  lines.push('','来源版本：' ,...snapshot.sourceSnapshots.map(s=>`- ${escape(s.source)}：${escape(s.ledgerId)}，事件游标 ${s.eventCursor}，SHA256 ${s.sha256}`));
  if(snapshot.diagnostics.length)lines.push('','读取缺口：',...snapshot.diagnostics.map(d=>'- '+escape(JSON.stringify(d))));
  lines.push('','此文档是来源视图，不改变源状态，不代表实际派发、权威工单关闭或谛听落库成功。');
  return lines.join('\n');
}
function replaceRegion(text, body) {
  if(text.split(BEGIN).length!==2||text.split(END).length!==2||text.indexOf(BEGIN)>text.indexOf(END))throw Error('Document requires one ordered sinan marker pair');
  return text.slice(0,text.indexOf(BEGIN)+BEGIN.length)+'\n'+body+'\n'+text.slice(text.indexOf(END));
}
export function refresh(registryFile, type, reference) {
  if(!types.has(type))throw Error('Only actual task events are supported; time-based triggers are prohibited');
  if(typeof reference!=='string'||!reference.trim())throw Error('Actual event source reference is required');
  const file=path.resolve(registryFile);noLinks(file);
  const base=fs.realpathSync(path.dirname(file));
  const config=JSON.parse(fs.readFileSync(file,'utf8').replace(/^\uFEFF/,''));
  const protectedFiles=[file,...(config.sources||[]).map(s=>path.resolve(base,s.root,'.yuanheng','state.json'))];
  // Fixed legacy outputs are implicit in the original API, additional documents require registration.
  const output=safeTarget(path.join(base,'progress.md'),base,protectedFiles);
  const resultFile=safeTarget(path.join(base,'sync-result.json'),base,protectedFiles);
  const lock=safeTarget(path.join(base,'progress.lock'),base,protectedFiles);
  const fd=fs.openSync(lock,'wx');
  const result={event:{type,reference},updated:false,document:'progress.md',documents:[],sourceGaps:[],externalAuthorityActions:[],localWriteFailures:[],execution:'not_dispatched',reporting:'host_binding_and_receipt_required',path_base:'registry_directory'};
  let failed;
  try {
    const snapshot=board(config,base);
    Object.assign(result,{followUps:snapshot.followUps,ready:snapshot.ready,sourcesRead:snapshot.sourcesRead,sourcesRegistered:snapshot.sourcesRegistered,scope:'registered_sources_only',sourceSnapshots:snapshot.sourceSnapshots.map(({root,...s})=>s),diagnostics:snapshot.diagnostics,sourceGaps:[...snapshot.diagnostics]});
    const sync=config.document_sync;
    const documents=sync?.documents??[];
    result.documents=[{path:'progress.md',status:'not_synced'},...(Array.isArray(documents)?documents:[]).map(d=>({path:d.path,status:'not_synced'}))];
    let root=base;
    if(sync) {
      if(sync.path_base!=='registry_directory'||typeof sync.write_root!=='string'||!!path.parse(sync.write_root).root||!Array.isArray(documents))throw Error('document_sync requires registry_directory, relative write_root and documents array');
      const declared=path.resolve(base,sync.write_root);noLinks(declared);root=fs.realpathSync(declared);
    }
    const targets=new Set([output,resultFile,lock,file].map(p=>process.platform==='win32'?p.toLowerCase():p));
    const writes=[{target:output,content:'# 司南工单进度\n\n'+render(snapshot,type,reference)+'\n',entry:result.documents[0],root:base}];
    for(const [index,d] of documents.entries()) {
      if(typeof d.path!=='string'||!d.path||!!path.parse(d.path).root||!Array.isArray(d.tickets)||!d.tickets.length||d.tickets.some(k=>typeof k!=='string'||!k.includes('::'))|| (d.parent_tickets!==undefined&&(!Array.isArray(d.parent_tickets)||d.parent_tickets.some(k=>!d.tickets.includes(k)))))throw Error('Invalid document registration');
      const target=safeTarget(path.resolve(base,d.path),root,protectedFiles);
      const identity=process.platform==='win32'?target.toLowerCase():target;
      if(targets.has(identity))throw Error('Duplicate or reserved document path');targets.add(identity);
      try {
        const original=fs.readFileSync(target,'utf8');
        writes.push({target,content:replaceRegion(original,render(snapshot,type,reference,d.tickets,d.parent_tickets)),original,root,entry:result.documents[index+1]});
      } catch(e) {
        result.documents[index+1].reason=e.message;
        result.localWriteFailures.push({path:d.path,stage:'document_preflight',error:e.message});
      }
      for(const ticket of d.tickets)if(!snapshot.items.some(t=>t.key===ticket)&&!result.sourceGaps.some(g=>g.ticket===ticket))result.sourceGaps.push({ticket,error:'Registered document ticket unavailable'});
      for(const ticket of d.parent_tickets||[])if(!result.externalAuthorityActions.some(a=>a.ticket===ticket))result.externalAuthorityActions.push({ticket,action:'Verify overall goal and acceptance; reconcile parent at authoritative source',status:'not_executed'});
    }
    result.externalAuthorityActions.push({action:config.issue_tracking?.enabled?'Verify bound Git Issue/release status and read back any authorized transition':'Verify task acceptance and delivery at the bound authoritative source',status:'not_executed'},{action:'Verify actual reporting binding and delivered/consumed receipts',status:'not_executed'});
    // All documents are checked before the first write. A multi-file transaction is deliberately not claimed.
    for(const w of writes) {
      try {
        safeTarget(w.target,w.root,protectedFiles);
        if(w.original!==undefined&&fs.readFileSync(w.target,'utf8')!==w.original)throw Error('Document changed since preflight');
        atomicWrite(w.target,w.content);w.entry.status='synced';
      }catch(e){w.entry.reason=e.message;result.localWriteFailures.push({path:w.entry.path,error:e.message});/* Continue independent document writes; preserve the failed entry. */}
    }
    for(const failure of result.localWriteFailures)result.followUps.push({key:`document:${failure.path}`,problem:failure.error,owner:'host_task_coordinator',status:'proposed',execution:'not_dispatched',...followUpTracking(config),nextAction:'Repair this document and replay on actual event; other documents continue'});
    result.updated=result.documents.every(d=>d.status==='synced');
    result.outcome=result.updated?'synced':'partial';
  }catch(e){failed=e;result.localWriteFailures.push({stage:'preflight',error:e.message});}
  finally {
    try {
      for(const d of result.documents)if(d.status==='not_synced'&&!d.reason)d.reason=failed?.message||'Not attempted';
      result.localDocumentsSynced=result.updated;
      result.authorityReconciliation='not_performed';
      safeTarget(resultFile,base,protectedFiles);atomicWrite(resultFile,JSON.stringify(result,null,2)+'\n');
    }catch(e){result.localWriteFailures.push({path:'sync-result.json',error:e.message});failed=e;}
    finally {fs.closeSync(fd);fs.unlinkSync(lock);}
  }
  if(failed){failed.syncResult=result;throw failed;}
  return result;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  try {
    const [type,reference,registry,...extra]=process.argv.slice(2);
    if(extra.length)throw Error('Usage: refresh.mjs EVENT-TYPE SOURCE-REFERENCE [REGISTRY]');
    console.log(JSON.stringify(refresh(registry||fileURLToPath(new URL('./runtime/registry.json',import.meta.url)),type,reference),null,2));
  }catch(error){console.error(error.message);if(error.syncResult)console.error(JSON.stringify(error.syncResult,null,2));process.exitCode=1;}
}


