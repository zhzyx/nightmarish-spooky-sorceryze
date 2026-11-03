import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {refresh} from '../refresh.mjs';
import {board,prepare} from '../coordinator.mjs';
const workspace=fileURLToPath(new URL('../../../../',import.meta.url));
const fixtures=path.join(workspace,'work','ariadne-event-sync');
fs.mkdirSync(fixtures,{recursive:true});
function fixture(t) {
  const root=fs.mkdtempSync(path.join(fixtures,'test-'));
  t.after(()=>{if(path.dirname(root)!==fixtures)throw Error('Cleanup boundary mismatch');fs.rmSync(root,{recursive:true,force:true});});
  fs.mkdirSync(path.join(root,'source','.yuanheng'),{recursive:true});
  fs.mkdirSync(path.join(root,'docs'));
  const ledger=path.join(root,'source','.yuanheng','state.json');
  const registry=path.join(root,'registry.json');
  const document=path.join(root,'docs','requirement.md');
  fs.writeFileSync(document,'User intro\n<!-- ariadne:begin -->\nold view\n<!-- ariadne:end -->\nUser tail\n');
  const task=id=>({id,title:id,goal:'goal',acceptance:['proof'],status:'open',owner:'owner',dependsOn:[]});
  const state={ledgerId:'ledger',tasks:[task('child'),task('parent')],agents:[],events:[]};
  const config={sources:[{id:'source',root:'source'}],coordination:[{ticket:'ledger::child',type:'bug',tags:['release']}],document_sync:{path_base:'registry_directory',write_root:'docs',documents:[{path:'docs/requirement.md',tickets:['ledger::child','ledger::parent'],parent_tickets:['ledger::parent']}]}};
  const save=()=>{fs.writeFileSync(ledger,JSON.stringify(state));fs.writeFileSync(registry,JSON.stringify(config));};save();
  return {root,registry,document,ledger,state,config,save};
}

test('pending user decision is attention; explicit operation restriction stays local',t=>{
  const f=fixture(t);f.config.coordination[0].pending_user=true;f.save();
  let b=board(f.config,f.root);
  assert.ok(b.ready.includes('ledger::child'));
  assert.ok(b.items[0].labels.includes('decision:user'));
  assert.equal(b.followUps[0].execution,'not_dispatched');
  assert.equal(b.followUps[0].decisionOwner,'user');
  assert.equal(b.followUps[0].issue,null);
  f.config.adapter_cli=process.argv[1];
  assert.equal(prepare(f.config,b,'source','start',['child']).execution,'not_executed');
  f.config.coordination[0].pending_user_blocking=true;
  b=board(f.config,f.root);
  assert.ok(!b.ready.includes('ledger::child'));assert.ok(b.ready.includes('ledger::parent'));
  assert.throws(()=>prepare(f.config,b,'source','start',['child']),/constraints/);
  assert.equal(prepare(f.config,b,'source','record',['child']).execution,'not_executed');
});

test('blocked and judgment tasks retain repair handoffs; hard dependents remain excluded',t=>{
  const f=fixture(t);
  f.config.coordination[0].assessment={state:'pending',owner:'quality-owner',reason:'Check evidence',blocking:true};
  f.state.tasks[1].dependsOn=['child'];f.save();
  let b=board(f.config,f.root);
  assert.equal(b.ready.length,0);assert.equal(b.followUps.find(x=>x.problem==='pending_judgment').owner,'quality-owner');
  assert.ok(b.followUps.some(x=>x.problem==='waiting_dependency:ledger::child'));
  f.state.tasks[0].status='blocked';delete f.config.coordination[0].assessment;f.save();
  b=board(f.config,f.root);assert.ok(b.followUps.some(x=>x.problem==='source_blocked'));
  assert.deepEqual(b.followUps,board(f.config,f.root).followUps);
});
test('source planned -> processing -> accepted; preserves prose, parent and ledger; replay stable',t=>{
  const f=fixture(t);
  for(const [status,label] of [['open','planned'],['running','processing'],['done','done']]) {
    const child=f.state.tasks[0];child.status=status;
    if(status==='done') {
      fs.writeFileSync(path.join(f.root,'source','proof.txt'),'proof');
      child.artifacts=[{path:'proof.txt',sha256:crypto.createHash('sha256').update('proof').digest('hex')}];
      child.review={verdict:'pass',criteria:[{met:true,evidence:'proof.txt'}]};
    }
    f.save();const before=fs.readFileSync(f.ledger,'utf8');
    const result=refresh(f.registry,'ticket.changed','event:'+status);
    assert.equal(result.updated,true);assert.equal(fs.readFileSync(f.ledger,'utf8'),before);
    const doc=fs.readFileSync(f.document,'utf8');
    assert.match(doc,new RegExp('state:'+label));assert.match(doc,/type:bug/);assert.match(doc,/tag:release/);
    assert.match(doc,/ledger::parent \| parent \| open/);assert.match(doc,/子项完成不自动关闭父项/);
    assert.ok(doc.startsWith('User intro\n<!-- ariadne:begin -->'));assert.ok(doc.endsWith('<!-- ariadne:end -->\nUser tail\n'));
    refresh(f.registry,'ticket.changed','event:'+status);assert.equal(fs.readFileSync(f.document,'utf8'),doc);
    assert.equal(result.execution,'not_dispatched');assert.equal(result.authorityReconciliation,'not_performed');
  }
  assert.match(fs.readFileSync(f.document,'utf8'),/ledger::child \| child \| done.*\| 是 \|/);
});
test('unavailable sources and unknown ticket stay explicit',t=>{
  const f=fixture(t);f.config.sources.push({id:'missing',root:'not-present'});f.config.document_sync.documents[0].tickets.push('unknown::ticket');f.save();
  const r=refresh(f.registry,'source.changed','source-event');
  assert.equal(r.updated,true);assert.equal(r.sourceGaps.length,2);assert.match(fs.readFileSync(f.document,'utf8'),/unknown::ticket 来源未知/);
  assert.equal(r.externalAuthorityActions.every(a=>a.status==='not_executed'),true);
});
test('missing marker isolates one document and preserves other views',t=>{
  const f=fixture(t);fs.writeFileSync(f.document,'user-owned content');
  assert.equal(refresh(f.registry,'user.requested','manual').outcome,'partial');
  assert.equal(fs.existsSync(path.join(f.root,'progress.md')),true);assert.equal(fs.readFileSync(f.document,'utf8'),'user-owned content');
  const r=JSON.parse(fs.readFileSync(path.join(f.root,'sync-result.json'),'utf8'));
  assert.equal(r.localDocumentsSynced,false);assert.equal(r.localWriteFailures[0].stage,'document_preflight');assert.deepEqual(r.documents.map(d=>d.status),['synced','not_synced']);
});

test('missing document directory does not stop existing independent documents',t=>{
  const f=fixture(t);
  f.config.document_sync.documents.unshift({path:'docs/missing/a.md',tickets:['ledger::child']});f.save();
  const r=refresh(f.registry,'ticket.changed','missing-parent');
  assert.equal(r.outcome,'partial');
  assert.deepEqual(r.documents.map(d=>d.status),['synced','not_synced','synced']);
  assert.equal(fs.existsSync(path.join(f.root,'docs','missing')),false);
});
test('explicit boundary and protected output checks',t=>{
  const f=fixture(t);const original=fs.readFileSync(f.ledger,'utf8');
  for(const target of ['../outside.md','registry.json','source/.yuanheng/state.json','sync-result.json']) {
    f.config.document_sync.write_root='.';f.config.document_sync.documents[0].path=target;f.save();
    assert.throws(()=>refresh(f.registry,'scope.changed','scope'));
    assert.equal(fs.readFileSync(f.ledger,'utf8'),original);
  }
});
test('duplicate registration is rejected before any writes',t=>{
  const f=fixture(t);f.config.document_sync.documents.push({...f.config.document_sync.documents[0]});f.save();
  assert.throws(()=>refresh(f.registry,'ticket.changed','duplicate'),/Duplicate/);assert.equal(fs.existsSync(path.join(f.root,'progress.md')),false);
});
test('source hardlink and junction cannot be used as outputs',t=>{
  const f=fixture(t);
  fs.linkSync(f.ledger,path.join(f.root,'docs','alias.md'));f.config.document_sync.documents[0].path='docs/alias.md';f.save();
  assert.throws(()=>refresh(f.registry,'ticket.changed','alias'),/aliases/);
  fs.symlinkSync(path.join(f.root,'docs'),path.join(f.root,'linked'),'junction');f.config.document_sync.write_root='linked';f.config.document_sync.documents[0].path='linked/requirement.md';f.save();
  assert.throws(()=>refresh(f.registry,'ticket.changed','junction'),/Symlink/);
});
test('legacy API and new actual events work; timer and missing source reference rejected',t=>{
  const f=fixture(t);delete f.config.document_sync;f.save();
  for(const type of ['scope.changed','release.completed','source.changed','report.delivered'])assert.equal(refresh(f.registry,type,'real-event').updated,true);
  const before=fs.readFileSync(path.join(f.root,'sync-result.json'),'utf8');
  for(const type of ['timer','cron','heartbeat','time.elapsed'])assert.throws(()=>refresh(f.registry,type,'clock'),/time-based/);
  assert.throws(()=>refresh(f.registry,'user.requested',' '),/reference/);assert.equal(fs.readFileSync(path.join(f.root,'sync-result.json'),'utf8'),before);
});
test('concurrent invocation lock refuses before mutation',t=>{
  const f=fixture(t);fs.writeFileSync(path.join(f.root,'progress.lock'),'held');
  assert.throws(()=>refresh(f.registry,'ticket.changed','busy'),/EEXIST/);assert.equal(fs.existsSync(path.join(f.root,'progress.md')),false);assert.equal(fs.readFileSync(path.join(f.root,'progress.lock'),'utf8'),'held');
});

test('single-file write failure records partial completion and continues later docs',t=>{
  const f=fixture(t), second=path.join(f.root,'docs','delivery.md');
  fs.writeFileSync(second,'delivery\n<!-- ariadne:begin -->\nold\n<!-- ariadne:end -->\n');
  f.config.document_sync.documents.push({path:'docs/delivery.md',tickets:['ledger::child']});f.save();
  const original=fs.readFileSync(second,'utf8'), rename=fs.renameSync;
  try {
    fs.renameSync=(from,to)=>{if(to===f.document)throw Error('simulated local write failure');return rename(from,to);};
    assert.equal(refresh(f.registry,'release.completed','release-receipt').outcome,'partial');
  } finally {fs.renameSync=rename;}
  const r=JSON.parse(fs.readFileSync(path.join(f.root,'sync-result.json'),'utf8'));
  assert.deepEqual(r.documents.map(d=>d.status),['synced','not_synced','synced']);assert.equal(r.updated,false);
  assert.equal(r.localWriteFailures[0].path,'docs/requirement.md');assert.notEqual(fs.readFileSync(second,'utf8'),original);
  assert.ok(r.followUps.some(x=>x.key==='document:docs/requirement.md'));
  assert.equal(refresh(f.registry,'user.requested','repair').updated,true);
  assert.equal(fs.existsSync(path.join(f.root,'progress.lock')),false);
});
