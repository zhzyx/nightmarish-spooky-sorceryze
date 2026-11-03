import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
const read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,''));
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');
const key=(ledger,id)=>`${ledger}::${id}`;
function validateLabels(m) {
  if(m.pending_user_blocking!==undefined&&typeof m.pending_user_blocking!=='boolean')throw Error('pending_user_blocking must be boolean');
  if(m.type!==undefined&&(typeof m.type!=='string'||!m.type.trim()||m.type!==m.type.trim()||m.type.length>80||/[\s:]/u.test(m.type)))throw Error('Type must be a nonempty identifier without whitespace or colon (max 80 characters)');
  if(m.tags!==undefined&&(!Array.isArray(m.tags)||m.tags.some(t=>typeof t!=='string'||!t.trim()||t!==t.trim()||t.includes(':')||t.length>80)))throw Error('Tags must be nonempty plain names without colon');
  if(m.assessment!==undefined) {
    const a=m.assessment;
    if(!a||!['pending','resolved','none'].includes(a.state))throw Error('Invalid assessment state');
    if(a.state!=='none'&&(!a.owner?.trim()||!a.reason?.trim()))throw Error('Assessment owner and reason are required');
    if(a.state==='pending'&&typeof a.blocking!=='boolean')throw Error('Pending assessment must declare blocking');
    if(a.state==='resolved'&&!a.reference?.trim())throw Error('Resolved assessment requires decision reference');
  }
}
export function filterItems(snapshot,labels=[]) {return snapshot.items.filter(t=>labels.every(l=>t.labels.includes(l)));}
export function labelRegistry(file,ticket,change) {
  if(!change.actor?.trim()||!change.reason?.trim())throw Error('Label change actor and reason are required');
  const fields=['type','tags','assessment'];
  if(Object.keys(change).some(k=>![...fields,'actor','reason'].includes(k))||!fields.some(k=>Object.hasOwn(change,k)))throw Error('Only type, tags and assessment can be labeled');
  validateLabels(change);
  const lock=file+'.lock',fd=fs.openSync(lock,'wx'),tmp=file+'.tmp-'+process.pid;
  try {
    const cfg=read(file),snapshot=board(cfg,path.dirname(path.resolve(file)));
    if(!snapshot.items.some(t=>t.key===ticket))throw Error('Ticket unavailable; labels were not changed');
    cfg.coordination??=[];let m=cfg.coordination.find(m=>m.ticket===ticket);
    if(!m){m={ticket};cfg.coordination.push(m);}
    const before=Object.fromEntries(fields.filter(k=>Object.hasOwn(m,k)).map(k=>[k,m[k]]));
    for(const k of fields)if(Object.hasOwn(change,k))m[k]=k==='tags'?[...new Set(change[k])]:change[k];
    (cfg.label_history??=[]).push({ticket,actor:change.actor,reason:change.reason,at:new Date().toISOString(),before,after:Object.fromEntries(fields.filter(k=>Object.hasOwn(m,k)).map(k=>[k,m[k]]))});
    board(cfg,path.dirname(path.resolve(file)));
    fs.writeFileSync(tmp,JSON.stringify(cfg,null,2)+'\n');fs.renameSync(tmp,file);
    return {ticket,updated:true,sourceLedgerWritten:false};
  } finally {if(fs.existsSync(tmp))fs.unlinkSync(tmp);fs.closeSync(fd);fs.unlinkSync(lock);}
}

export function followUpTracking(config, metadata={}) {
  const selected=config.issue_tracking;
  if(selected!==undefined && (!selected || typeof selected!=='object' || Array.isArray(selected) || typeof selected.enabled!=='boolean'))throw Error('issue_tracking requires explicit enabled boolean');
  const enabled=selected?.enabled===true;
  if(enabled && (selected.provider!=='git-issue' || typeof selected.authority_ref!=='string' || !selected.authority_ref.trim()))throw Error('Git Issue handoff requires provider and authority reference');
  return {
    issue:metadata.issue_ref||null,
    issueAction:enabled?'Find or create linked Issue through the bound git-issue integration; verify authority and read back before marking linked':null,
    workItemAction:'Link the problem at the task authoritative source; preserve evidence, responsibility and recovery event',
    tracking:enabled?'git-issue':'source_work_item'
  };
}

export function board(config,base=process.cwd()) {
  followUpTracking(config);
  const items=[], diagnostics=[], sourceSnapshots=[], ledgers=new Set(), aliases=new Set();
  for(const source of config.sources||[]) {
    if(!source.id||aliases.has(source.id))throw Error('Source aliases must be unique and nonempty');
    aliases.add(source.id);
    try {
      const root=fs.realpathSync(path.resolve(base,source.root));
      const file=path.join(root,'.yuanheng','state.json'), bytes=fs.readFileSync(file), s=JSON.parse(bytes.toString().replace(/^\uFEFF/,''));
      if(!s.ledgerId||!Array.isArray(s.tasks))throw Error('Invalid Zeus ledger');
      if(ledgers.has(s.ledgerId))throw Error('Duplicate ledger registration');
      const seen=new Set();
      for(const t of s.tasks){if(!t.id||seen.has(t.id))throw Error('Missing or duplicate ticket ID');seen.add(t.id);}
      const local=s.tasks.map(t=>{
        const problems=[];
        const definitionValid=typeof t.title==='string'&&!!t.title.trim()&&typeof t.goal==='string'&&!!t.goal.trim()&&Array.isArray(t.acceptance)&&t.acceptance.length>0;
        if(!definitionValid)problems.push('incomplete_definition');
        if(!['open','running','review','blocked','done'].includes(t.status))problems.push('unknown_source_state');
        let evidenceValid=false;
        if(t.status==='done') {
          evidenceValid=t.review?.verdict==='pass'&&Array.isArray(t.artifacts)&&t.artifacts.length>0&&Array.isArray(t.acceptance)&&Array.isArray(t.review.criteria)&&t.review.criteria.length===t.acceptance.length&&t.review.criteria.every(c=>c.met===true&&t.artifacts.some(a=>a.path===c.evidence));
          try { for(const a of t.artifacts||[]) {
            const actual=fs.realpathSync(path.resolve(root,a.path)),relative=path.relative(root,actual);
            if(!relative||relative==='..'||relative.startsWith('..'+path.sep)||path.isAbsolute(relative)||relative.split(path.sep).some(p=>['.git','.yuanheng'].includes(p)))throw Error('Invalid evidence path');
            if(digest(fs.readFileSync(actual))!==a.sha256)throw Error('Stale evidence');
          }}catch{evidenceValid=false;}
          if(!evidenceValid)problems.push('acceptance_evidence_invalid');
        }
        const assignment=(s.agents||[]).find(a=>a.id===t.agent);
        return {key:key(s.ledgerId,t.id),source:source.id,id:t.id,title:t.title,root,goal:t.goal,status:t.status,owner:t.owner||null,plan:t.plan||null,dependsOn:(t.dependsOn||[]).map(d=>key(s.ledgerId,d)),softDependencies:[],definitionValid,evidenceValid,execution:assignment?.execution||null,blocker:t.blocker||null,created:t.created||null,problems,snapshot:{ledgerId:s.ledgerId,eventCursor:s.events?.length??0,sha256:digest(bytes)}};
      });
      ledgers.add(s.ledgerId);items.push(...local);sourceSnapshots.push({source:source.id,root,ledgerId:s.ledgerId,eventCursor:s.events?.length??0,sha256:digest(bytes)});
    }catch(e){diagnostics.push({source:source.id,error:e.message});}
  }
  const byKey=new Map(items.map(t=>[t.key,t]));
  for(const edge of config.dependencies||[]) {
    if(!['hard','soft'].includes(edge.kind))throw Error('Dependency kind must be hard or soft');
    const t=byKey.get(edge.ticket);
    if(!t){diagnostics.push({ticket:edge.ticket,error:'Dependency consumer unavailable'});continue;}
    (edge.kind==='hard'?t.dependsOn:t.softDependencies).push(edge.requires);
  }
  const metadata=new Map();for(const m of config.coordination||[]){if(metadata.has(m.ticket))throw Error('Duplicate coordination record');metadata.set(m.ticket,m);if(!byKey.has(m.ticket))diagnostics.push({ticket:m.ticket,error:'Coordination target unavailable'});}
  for(const t of items){const m=metadata.get(t.key)||{};if(m.priority!==undefined&&(!Number.isInteger(m.priority)||m.priority<0||m.priority>3))throw Error('Priority must be 0..3');t.priority=m.priority??2;t.featureRefs=m.feature_refs||[];t.coordinator=m.coordinator||null;t.decisionRef=m.decision_ref||null;t.pendingUser=m.pending_user===true;t.decisionBlocking=t.pendingUser&&m.pending_user_blocking===true;}
  for(const t of items){const m=metadata.get(t.key)||{};validateLabels(m);t.type=m.type??'unclassified';t.tags=[...new Set(m.tags||[])];t.assessment=m.assessment??{state:'none'};t.judgmentBlocking=t.assessment.state==='pending'&&t.assessment.blocking;}
  const visited=new Set(),active=new Set(),stack=[],cyclic=new Set();
  function visit(k){if(active.has(k)){for(const n of stack.slice(stack.indexOf(k)))cyclic.add(n);return;}if(visited.has(k))return;active.add(k);stack.push(k);for(const d of byKey.get(k)?.dependsOn||[])if(byKey.has(d))visit(d);stack.pop();active.delete(k);visited.add(k);}
  for(const t of items)visit(t.key);
  const healthMemo=new Map();
  function accepted(k,checking=new Set()) {
    if(healthMemo.has(k))return healthMemo.get(k);
    const t=byKey.get(k);if(!t||checking.has(k)||cyclic.has(k))return false;
    checking.add(k);const valid=t.status==='done'&&t.definitionValid&&t.evidenceValid&&!t.decisionBlocking&&!t.judgmentBlocking&&!!t.owner&&t.dependsOn.every(d=>accepted(d,checking));checking.delete(k);healthMemo.set(k,valid);return valid;
  }
  for(const t of items) {
    t.dependsOn=[...new Set(t.dependsOn)];
    if(cyclic.has(t.key))t.problems.push('dependency_cycle');
    for(const d of t.dependsOn)if(!byKey.has(d))t.problems.push(`missing_dependency:${d}`);else if(!accepted(d))t.problems.push(`waiting_dependency:${d}`);
    if(t.pendingUser)t.problems.push('pending_user_decision');
    if(t.judgmentBlocking)t.problems.push('pending_judgment');
    if(!t.owner)t.problems.push('owner_unassigned');
    // Unassigned work remains a coordination candidate, but not an execution authorization.
    t.dispatchCandidate=t.status==='open'&&t.problems.every(p=>p==='owner_unassigned'||(p==='pending_user_decision'&&!t.decisionBlocking));
    t.coordinationState=t.dispatchCandidate?'dispatch_candidate':t.status==='running'&&t.execution==='pending_host'?'delegated_pending_host':t.problems.length?'needs_coordination':t.status;
    t.acceptanceValid=accepted(t.key);
    const progress=t.status==='running'&&t.execution==='pending_host'?'awaiting_host':({open:'planned',running:'processing',review:'review',blocked:'blocked',done:'done'}[t.status]||'unknown');
    t.labels=[`type:${t.type}`,`state:${progress}`,...t.tags.map(x=>`tag:${x}`)];
    if(t.pendingUser||t.assessment.state==='pending')t.labels.push('decision:pending');
    if(t.pendingUser)t.labels.push('decision:user');
    if(t.problems.length)t.labels.push('attention:required');
  }
  // Derived handoffs are not executed assignments or new authoritative tickets.
  const followUps=items.flatMap(t=>[...new Set([...t.problems,...(t.assessment.state==='pending'?['pending_judgment']:[]),...(t.status==='blocked'?['source_blocked']:[])])].map(problem=>({
    key:`${t.key}::${problem}`,ticket:t.key,problem,
    owner:problem==='pending_judgment'?t.assessment.owner:(t.coordinator||t.owner||'host_task_coordinator'),
    decisionOwner:problem==='pending_user_decision'?'user':null,
    ...followUpTracking(config,metadata.get(t.key)||{}),
    status:'proposed',execution:'not_dispatched',
    nextAction:'Investigate or repair within mandate; isolate affected operation and continue independent authorized work',
    resumeOn:'Actual evidence, decision, dependency, execution event or user request; no timer'
  })));
  for(const d of diagnostics)followUps.push({key:`source:${d.source||d.ticket}`,problem:d.error,owner:'host_task_coordinator',status:'proposed',execution:'not_dispatched',...followUpTracking(config),nextAction:'Repair source visibility; continue readable independent sources'});
  return {followUps,scope:'registered_sources_only' ,sourcesRegistered:(config.sources||[]).length,sourcesRead:ledgers.size,sourceSnapshots,diagnostics,items,ready:items.filter(t=>t.dispatchCandidate).sort((a,b)=>a.priority-b.priority||String(a.created||'').localeCompare(String(b.created||''))||a.key.localeCompare(b.key)).map(t=>t.key)};
}

export function prepare(config,snapshot,sourceId,command,args=[]) {
  const source=(config.sources||[]).find(s=>s.id===sourceId);if(!source)throw Error('Unknown source');
  const supported=['plan','task','start','ack','record','submit','review','block','unblock','checkpoint','resume','bug','search','improve','decide','report','status'];
  if(!supported.includes(command))throw Error('Unsupported source operation');
  if(snapshot.diagnostics.some(d=>d.source===sourceId))throw Error('Source unavailable');
  if(['start','unblock','review'].includes(command)) {
    const t=snapshot.items.find(t=>t.source===sourceId&&t.id===args[0]);if(!t)throw Error('Unknown ticket');
    let rejectReview=false;
    if(command==='review'){if(!args[1])throw Error('Review JSON is required');const r=read(path.resolve(args[1]));if(!['pass','fail'].includes(r.verdict))throw Error('Review verdict must be pass or fail');rejectReview=r.verdict==='fail';}
    if(!rejectReview&&t.problems.some(p=>p!=='owner_unassigned'&&!(p==='pending_user_decision'&&!t.decisionBlocking)))throw Error('Resolve coordination constraints before preparing this transition');
    if(command==='start'&&!t.dispatchCandidate)throw Error('Ticket is not a dispatch candidate');
  }
  if(!config.adapter_cli||!fs.existsSync(config.adapter_cli))throw Error('Real source CLI is required');
  const src=snapshot.sourceSnapshots.find(s=>s.source===sourceId);if(!src)throw Error('Source snapshot unavailable');
  return {execution:'not_executed',executable:process.execPath,argv:[config.adapter_cli,'--root',src.root,command,...args],requires:'Host authorization, fresh dependency checks and original CLI gates; this plan grants no permission',snapshots:snapshot.sourceSnapshots};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  try{const [cmd,file,...args]=process.argv.slice(2);if(!file||!['board','ready','prepare','label'].includes(cmd))throw Error('Usage: board|ready REGISTRY [LABEL...]; label REGISTRY TICKET CHANGE.json; prepare REGISTRY SOURCE COMMAND [ARGS...]');let result;if(cmd==='label'){if(args.length!==2)throw Error('Ticket and label change JSON are required');result=labelRegistry(file,args[0],read(args[1]));}else{const cfg=read(file),s=board(cfg,path.dirname(path.resolve(file)));if(cmd==='prepare')result=prepare(cfg,s,...args);else{const items=filterItems(s,args);result=cmd==='board'?{...s,items,ready:s.ready.filter(k=>items.some(t=>t.key===k)),filters:args}:s.ready.filter(k=>items.some(t=>t.key===k));}}console.log(JSON.stringify(result,null,2));}catch(e){console.error(e.message);process.exitCode=1;}
}
