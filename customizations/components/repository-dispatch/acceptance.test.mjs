import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {execFileSync,spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {Production} from '../../platforms/document-management/git-markdown/yanshi-legacy/runtime/src/production.mjs';
import {board} from '../../platforms/process-management/yuanheng-local/sinan/coordinator.mjs';
import {captureCandidate,validateDecision,projectAcceptance,parallelRegistry} from './acceptance.mjs';
import {dispatchEvent} from '../../platforms/process-management/yuanheng-local/sinan/dispatch.mjs';
const digest = v=>createHash('sha256').update(v).digest('hex');
function fixture(t, submitted=true) {
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'acceptance-776-'));
  t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const root=path.join(dir,'repo');fs.mkdirSync(root);
  const git=(...args)=>execFileSync('git',['-C',root,...args],{stdio:'pipe',encoding:'utf8'}).trim();
  git('init','-b','main');git('config','user.name','Fixture');git('config','user.email','fixture@invalid');
  fs.writeFileSync(path.join(root,'evidence.txt'),'actual fixture output');git('add','.');git('commit','-m','fixture');
  const p=new Production(root);p.init({checkpointEvery:100});
  const a=p.create({title:'A',goal:'A',stage:'integration',acceptance:['criterion'],independentReview:true});
  p.start(a.id,{owner:'producer',capability:'test',authority:'fixture',nextAction:'test'});
  p.acknowledge(a.id,{host:'controlled-fixture',runId:'actual-fixture'});if(submitted)p.submit(a.id,['evidence.txt']);
  const state=p.read(),key=`${state.ledgerId}::${a.id}`;
  const registry=path.join(dir,'registry.json');fs.writeFileSync(registry,JSON.stringify({sources:[{id:'source',root}]}));
  const receipt=(name)=>{const file=path.join(dir,name);fs.writeFileSync(file,name);return {path:file,sha256:digest(name)};};
  const decision={candidate:captureCandidate(root),producer:{worker_id:'producer',conversation_id:'p',receipt:receipt('producer')},
    reviewer:{worker_id:'reviewer',conversation_id:'r',receipt:receipt('reviewer')},criteria:[{id:'criterion',evidence:[{path:'evidence.txt',sha256:digest('actual fixture output')}]}],verdict:'pass',reason:'fixture verified',design_sha256:'d'.repeat(64)};
  const input={decision,decisionSha256:digest(JSON.stringify(decision)),operator:'fixture-operator',registry:{path:registry,tickets:{ticket:key}},ticket:'ticket',revalidate:()=>true,isLive:()=>true};
  return {dir,root,p,a,key,registry,decision,input,git};
}
test('real ledger review and derived board acceptance resume once using reservation idempotence',async t=>{
  const f=fixture(t);let starts=0;const references=new Set();
  const resume=async event=>{assert.equal(event.type,'ticket.changed');if(!references.has(event.reference)){references.add(event.reference);starts++;}return {started:starts};};
  const result=await projectAcceptance({...f.input,resume});assert.equal(result.state,'accepted');
  const count=f.p.read().events.filter(e=>e.type==='reviewed').length;
  assert.equal(board(JSON.parse(fs.readFileSync(f.registry)),f.dir).items[0].acceptanceValid,true);
  assert.equal(board(JSON.parse(fs.readFileSync(f.registry)),f.dir).items[0].hostAcceptanceVerified,true);
  await projectAcceptance({...f.input,resume});assert.equal(starts,1);assert.equal(f.p.read().events.filter(e=>e.type==='reviewed').length,count);
  fs.writeFileSync(path.join(f.root,'new-production.txt'),'new');
  assert.equal(board(JSON.parse(fs.readFileSync(f.registry)),f.dir).items[0].acceptanceValid,false);
});
test('dispatch failure retries from committed review without a second review',async t=>{
  const f=fixture(t);await assert.rejects(projectAcceptance({...f.input,resume:async()=>{throw Error('dispatch unavailable');}}),/dispatch unavailable/);
  assert.equal(f.p.read().tasks[0].status,'done');
  await projectAcceptance({...f.input,resume:async()=>({resumed:true})});
  assert.equal(f.p.read().events.filter(e=>e.type==='reviewed').length,1);
});
for(const scenario of ['self','unknown','stale','permission','criteria','lock','receipt']) test(`reject ${scenario} without accepting or releasing`,async t=>{
  const f=fixture(t);let called=0;
  if(scenario==='self')f.decision.reviewer.worker_id='producer';
  if(scenario==='unknown')f.decision.verdict='unknown';
  if(scenario==='stale')fs.writeFileSync(path.join(f.root,'evidence.txt'),'changed');
  if(scenario==='permission')f.input.revalidate=()=>false;
  if(scenario==='criteria')f.decision.criteria[0].id='other';
  if(scenario==='lock')fs.writeFileSync(path.join(f.root,'.yuanheng/writer.lock'),'busy');
  if(scenario==='receipt')fs.writeFileSync(f.decision.reviewer.receipt.path,'changed');
  f.input.decisionSha256=digest(JSON.stringify(f.decision));
  await assert.rejects(projectAcceptance({...f.input,resume:async()=>{called++;}}));
  assert.equal(called,0);assert.equal(f.p.read().tasks[0].status,'review');
});
test('complete candidate includes new files and deletions, rejects HEAD change',t=>{
  const f=fixture(t);assert.equal(validateDecision(f.decision),true);
  f.git('commit','--allow-empty','-m','changed head');assert.throws(()=>validateDecision(f.decision),/Stale candidate/);
});
test('completion event releases real dependent process through dispatchEvent with no manual action',async t=>{
  const f=fixture(t);
  const b=f.p.create({title:'B',goal:'dependent',stage:'integration',acceptance:['B ran'],dependsOn:[f.a.id]});
  f.decision.candidate=captureCandidate(f.root);f.input.decisionSha256=digest(JSON.stringify(f.decision));
  const key=`${f.p.read().ledgerId}::${b.id}`,held=[];let launches=0;
  const inspect=()=>board(JSON.parse(fs.readFileSync(f.registry)),f.dir);
  const requests=[{ticket:key,owner:'fixture',outcome:'B',acceptance:'B ran',authorityRef:'controlled-fixture',capabilities:['test'],contextRefs:[],reads:[f.root],writes:[]}];
  const host={withLock:async fn=>fn(),inspect:async()=>({snapshot:inspect(),environment:{active:held,capacity:1,catalog:[{id:'fixture',available:true,targets:['agent'],capabilities:['test']}]}}),
    revalidate:async()=>true,reserve:async a=>{held.push(a);return true;},
    startSource:async()=>{f.p.start(b.id,{owner:'B-worker',capability:'test',authority:'controlled-fixture',nextAction:'run'});return {reference:'fixture-start'};},
    launch:async a=>{const output=execFileSync(process.execPath,['-e','process.stdout.write("B completed")'],{encoding:'utf8',windowsHide:true});assert.equal(output,'B completed');launches++;return {workerId:'actual-process',reference:'fixture-exit',model:a.model.id,target:a.target};},
    ack:async()=>{},record:async record=>fs.writeFileSync(path.join(f.dir,'dispatch.json'),JSON.stringify(record))};
  const before=await dispatchEvent({type:'user.requested',reference:'fixture'},requests,host);assert.equal(before.deferred[0].reason,'not_ready');assert.equal(launches,0);
  const resume=event=>dispatchEvent(event,requests,host);
  await projectAcceptance({...f.input,resume});assert.equal(launches,1);
  await projectAcceptance({...f.input,resume});assert.equal(launches,1);
});
test('ordinary review JSON cannot claim host acceptance',t=>{
  const f=fixture(t);
  assert.throws(()=>f.p.review(f.a.id,{reviewer:'self-reported',verdict:'pass',reason:'untrusted',criteria:[{met:true,evidence:'evidence.txt'}],host_acceptance:{decision_sha256:'a'.repeat(64)}}),/可信回调/);
  f.p.review(f.a.id,{reviewer:'legacy-human',verdict:'pass',reason:'legacy',criteria:[{met:true,evidence:'evidence.txt'}]});
  const item=board(JSON.parse(fs.readFileSync(f.registry)),f.dir).items[0];
  assert.equal(item.acceptanceValid,true);assert.equal(item.hostAcceptanceVerified,false);
});
test('replay rejects unrelated empty HEAD change after a ledger acceptance',async t=>{
  const f=fixture(t);await projectAcceptance({...f.input,resume:async()=>({ok:true})});
  f.git('commit','--allow-empty','-m','unrelated');
  await assert.rejects(projectAcceptance({...f.input,resume:async()=>assert.fail('stale replay released')}),/Stale candidate/);
  assert.equal(board(JSON.parse(fs.readFileSync(f.registry)),f.dir).items[0].acceptanceValid,false);
});
test('actual cancellation after ledger commit preserves review and never starts dependent work',async t=>{
  const f=fixture(t),live=path.join(f.dir,'native.live');fs.writeFileSync(live,'active');
  const original=Production.prototype.persist;
  Production.prototype.persist=function(s){original.call(this,s);execFileSync(process.execPath,['-e','require("fs").unlinkSync(process.argv[1])',live],{windowsHide:true});};
  try {
    await assert.rejects(projectAcceptance({...f.input,isLive:()=>fs.existsSync(live),resume:async()=>assert.fail('cancelled B launched')}),/cancelled after ledger/);
    assert.equal(f.p.read().tasks[0].status,'done');
  } finally {Production.prototype.persist=original;}
});
const sorted=value=>value&&typeof value==='object'?(Array.isArray(value)?value.map(sorted):Object.fromEntries(Object.keys(value).sort().map(k=>[k,sorted(value[k])]))):value;
function audit(root,policy,id='host-context-'+'a'.repeat(32),change={}) {
  const e={schema_version:1,event_id:id,tenant_id:policy.tenant_id,request_id:policy.request_id,source_ref:policy.source_ref,kind:'request',occurred_at:'2026-11-11T00:00:00Z',
    agent:{id:'gonggong-host-adapter',version:'1.2.1',origin:'gonggong-host-adapter',definition_sha256:'a'.repeat(64)},payload:{issue:{url:policy.source_ref},context_accepted:true},evidence_refs:[],...change};
  e.sha256=digest(JSON.stringify(sorted(e)));
  const file=path.join(root,'gonggong-diting-data/events',policy.tenant_id,policy.request_id,id+'.json');fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(e));return file;
}
for(const scenario of ['new','old_changed','wrong_request','code','malformed','tracked','evidence']) test(`host audit policy ${scenario}`,t=>{
  const f=fixture(t),policy={tenant_id:'gonggong-workspace',request_id:'fixture',source_ref:'https://github.com/fixture/repo/issues/776'};
  const old=audit(f.root,policy,'host-context-'+'b'.repeat(32));
  f.decision.candidate=captureCandidate(f.root,policy);
  const added=audit(f.root,policy);
  if(scenario==='old_changed')fs.appendFileSync(old,' ');
  if(scenario==='wrong_request')audit(f.root,policy,undefined,{request_id:'another'});
  if(scenario==='code')fs.writeFileSync(path.join(f.root,'added.js'),'new code');
  if(scenario==='malformed')fs.writeFileSync(added,'{}');
  if(scenario==='tracked')f.git('add','gonggong-diting-data');
  if(scenario==='evidence')f.decision.criteria[0].evidence=[{path:path.relative(f.root,added).replaceAll('\\','/'),sha256:digest(fs.readFileSync(added))}];
  if(scenario==='new')assert.equal(validateDecision(f.decision),true);
  else assert.throws(()=>validateDecision(f.decision));
});
test('actual running ledger submits verified terminal evidence and reviews in one commit',async t=>{
  const f=fixture(t,false),before=Number(f.git('rev-list','--count','HEAD'));
  f.decision.candidate.audit_policy={tenant_id:'gonggong-workspace',request_id:'fixture',source_ref:'https://github.com/fixture/repo/issues/776'};
  delete f.decision.producer.conversation_id;f.decision.producer.execution_id='parallel:actual-worker:pid:start';
  const registration={schema_version:1,execution_id:f.decision.producer.execution_id,worker_id:'producer',design_sha256:f.decision.design_sha256,issue_number:776,request_id:'fixture',candidate:{root:f.root,branch:f.decision.candidate.branch,base_sha:f.decision.candidate.head}};
  const registrationPath=path.join(f.dir,'registration.json');fs.writeFileSync(registrationPath,JSON.stringify(registration));
  const processResult=spawnSync(process.execPath,['-e','process.exit(0)'],{windowsHide:true});
  const terminal={schema_version:1,execution_id:registration.execution_id,worker_id:'producer',issue_number:776,request_id:'fixture',registration:{path:registrationPath,sha256:digest(fs.readFileSync(registrationPath))},candidate:{...f.decision.candidate,base_sha:f.decision.candidate.head},pid:processResult.pid,exit_code:processResult.status,state:'review',transport_completed:true,cancel_requested:false,reporting:{ok:true,state:'recorded_file'},reporting_error:null};
  fs.writeFileSync(f.decision.producer.receipt.path,JSON.stringify(terminal));f.decision.producer.receipt.sha256=digest(fs.readFileSync(f.decision.producer.receipt.path));
  f.input.decisionSha256=digest(JSON.stringify(f.decision));
  const config={registry:f.registry,jobs:[{order:1,worktree:f.root,dependsOn:[]},{order:2,worktree:f.dir,dependsOn:[f.key]}]};
  f.input.registry=parallelRegistry(config,f.decision,'ticket');
  const result=await projectAcceptance({...f.input,resume:async event=>({state:'native_continuation_required',reference:event.reference})});
  assert.equal(result.dispatch.state,'native_continuation_required');
  assert.equal(Number(f.git('rev-list','--count','HEAD')),before+1);
  assert.deepEqual(f.p.read().events.slice(-2).map(e=>e.type),['submitted','reviewed']);
  assert.equal(f.p.read().tasks[0].status,'done');
  assert.throws(()=>parallelRegistry({...config,jobs:[config.jobs[0]]},f.decision,'ticket'),/mapping/);
  assert.throws(()=>parallelRegistry({...config,registry:null},f.decision,'ticket'),/require registry/);
  terminal.worker_id='forged';fs.writeFileSync(f.decision.producer.receipt.path,JSON.stringify(terminal));
  f.decision.producer.receipt.sha256=digest(fs.readFileSync(f.decision.producer.receipt.path));
  assert.throws(()=>validateDecision(f.decision,true),/identity or outcome mismatch/);
  assert.equal(board(JSON.parse(fs.readFileSync(f.registry)),f.dir).items[0].acceptanceValid,false);
});
