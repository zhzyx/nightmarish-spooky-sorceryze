import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {board,followUpTracking} from '../coordinator.mjs';
import {refresh} from '../refresh.mjs';

const fixtures=path.resolve(fileURLToPath(new URL('../../../../../../work/generic-tracking/',import.meta.url)));
function setup(t) {
  fs.mkdirSync(fixtures,{recursive:true});
  const root=fs.mkdtempSync(path.join(fixtures,'case-'));
  t.after(()=>{if(path.dirname(root)!==fixtures)throw Error('Cleanup outside fixtures');fs.rmSync(root,{recursive:true,force:true});});
  fs.mkdirSync(path.join(root,'source','.yuanheng'),{recursive:true});
  fs.mkdirSync(path.join(root,'docs'));
  fs.writeFileSync(path.join(root,'source','.yuanheng','state.json'),JSON.stringify({ledgerId:'local-design',tasks:[{id:'draft',title:'文档审阅',goal:'合并两份设计意见',acceptance:['两方必要修改均保留'],status:'open',owner:'local-author',dependsOn:[]}],agents:[],events:[]}));
  fs.writeFileSync(path.join(root,'docs','draft.md'),'No sync markers; actual document failure');
  const config={sources:[{id:'local',root:'source'},{id:'missing',root:'absent'}],coordination:[{ticket:'local-design::draft',pending_user:true}],document_sync:{path_base:'registry_directory',write_root:'docs',documents:[{path:'docs/draft.md',tickets:['local-design::draft']}]}};
  const registry=path.join(root,'registry.json');
  const save=()=>fs.writeFileSync(registry,JSON.stringify(config));save();
  return {root,config,registry,save};
}
test('no Git repository or Issue binding: tasks, source failures and document repair stay local',t=>{
  const f=setup(t);assert.equal(fs.existsSync(path.join(f.root,'.git')),false);
  const b=board(f.config,f.root);
  assert.ok(b.ready.includes('local-design::draft'));
  assert.ok(b.followUps.some(x=>x.key==='source:missing'));
  for(const x of b.followUps){assert.equal(x.issueAction,null);assert.equal(x.tracking,'source_work_item');assert.ok(x.workItemAction);}
  const r=refresh(f.registry,'user.requested','local-user-request');
  assert.equal(r.outcome,'partial');
  assert.ok(r.followUps.some(x=>x.key==='document:docs/draft.md'));
  for(const x of r.followUps)assert.equal(x.issueAction,null);
  assert.doesNotMatch(fs.readFileSync(path.join(f.root,'progress.md'),'utf8'),/Issue/);
  assert.ok(!r.externalAuthorityActions.some(x=>/Issue/.test(x.action)));
});
test('explicit Git integration retains Issue handoffs for tasks, source gaps and document repairs',t=>{
  const f=setup(t);
  f.config.issue_tracking={enabled:true,provider:'git-issue',authority_ref:'host/current-mandate'};
  f.config.coordination[0].issue_ref='https://example.invalid/issues/known-synthetic';f.save();
  const r=refresh(f.registry,'dependency.changed','fixture-only');
  assert.equal(r.execution,'not_dispatched');
  assert.ok(r.followUps.some(x=>x.issue===f.config.coordination[0].issue_ref));
  for(const x of r.followUps){assert.equal(x.tracking,'git-issue');assert.match(x.issueAction,/verify authority and read back/);}
  assert.ok(r.externalAuthorityActions.some(x=>/bound Git Issue/.test(x.action)));
});
test('historic Issue references and disabled integrations do not activate remote handoffs',()=>{
  const old={issue_ref:'historical-observation'};
  for(const config of [{},{issue_tracking:{enabled:false}}]){
    const x=followUpTracking(config,old);assert.equal(x.issue,'historical-observation');assert.equal(x.issueAction,null);
  }
});
test('malformed or incomplete bindings fail before suggesting Git operations',()=>{
  for(const issue_tracking of [true,{},null,{enabled:'true'},{enabled:true},{enabled:true,provider:'other',authority_ref:'x'},{enabled:true,provider:'git-issue',authority_ref:' '}])assert.throws(()=>board({sources:[],issue_tracking}),/issue_tracking|handoff/);
});

test('standalone process installation works without the optional issue provider', async t => {
  const {root,config,registry} = setup(t);
  const install = path.join(root,'standalone');
  fs.mkdirSync(install);
  for (const name of ['coordinator.mjs','refresh.mjs']) {
    fs.copyFileSync(fileURLToPath(new URL('../'+name,import.meta.url)),path.join(install,name));
  }
  const {board} = await import(pathToFileURL(path.join(install,'coordinator.mjs')));
  const {refresh} = await import(pathToFileURL(path.join(install,'refresh.mjs')));
  assert.ok(board(config,root).ready.includes('local-design::draft'));
  assert.equal(refresh(registry,'user.requested','standalone').outcome,'partial');
  assert.doesNotThrow(()=>board({...config,issue_tracking:{enabled:false}},root));
  assert.throws(()=>board({...config,issue_tracking:{enabled:true,provider:'git-issue',authority_ref:'fixture'}},root),{code:'MODULE_NOT_FOUND'});
});
