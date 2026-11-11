import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {execFileSync,spawn} from 'node:child_process';
import {createHash} from 'node:crypto';
import {integrate} from '../../tools/godot_parallel/integration.mjs';
import {captureCandidate} from '../../customizations/components/repository-dispatch/acceptance.mjs';
const sha=b=>createHash('sha256').update(b).digest('hex');
const integrationURL=pathToFileURL(path.resolve('tools/godot_parallel/integration.mjs')).href;
function ownership(f,changes={}) {
  fs.mkdirSync(f.request.transaction_root,{recursive:true});
  const store=fs.realpathSync(f.request.transaction_root),root=fs.realpathSync(f.root);
  const ref='refs/gonggong/project-integration/'+sha(store);
  const value={version:1,root,store,pid:process.pid,host:os.hostname(),nonce:'12345678-1234-1234-1234-123456789abc',state:'active',...changes};
  const oid=execFileSync('git',['-C',root,'hash-object','-w','--stdin'],{input:JSON.stringify(value),windowsHide:true,encoding:'utf8'}).trim();
  f.git('update-ref',ref,oid);return {ref,oid,value};
}
const waitFor=async predicate=>{const deadline=Date.now()+20000;while(!predicate()){assert.ok(Date.now()<deadline,'child synchronization timed out');await new Promise(r=>setTimeout(r,10));}};
function contender(t,f,name) {
  const prefix=path.join(f.dir,name);
  // Instrument only the process boundary around real Git CAS operations. All
  // contenders read the same stale generation before any is allowed to write.
  const code=`const fs=require('fs'),cp=require('child_process');
    const [url,request,prefix]=process.argv.slice(1),original=cp.execFileSync;
    const wait=file=>{const until=Date.now()+20000;while(!fs.existsSync(file)){if(Date.now()>until)throw Error('barrier timeout');Atomics.wait(new Int32Array(new SharedArrayBuffer(4)),0,0,10);}};
    let first=true;cp.execFileSync=function(command,args,options){
      if(args.includes('update-ref')&&first){first=false;fs.writeFileSync(prefix+'.ready','');wait(prefix+'.go');
        const result=original(command,args,options);fs.writeFileSync(prefix+'.acquired','');wait(prefix+'.finish');return result;}
      return original(command,args,options);
    };require('module').syncBuiltinESMExports();
    import(url).then(({integrate})=>{try{process.stdout.write(JSON.stringify(integrate(JSON.parse(request))));}catch(e){process.stdout.write(JSON.stringify({error:e.message}));}});`;
  const child=spawn(process.execPath,['-e',code,integrationURL,JSON.stringify(f.request),prefix],{windowsHide:true,stdio:['ignore','pipe','pipe']});
  child.stderr.resume();
  let output='';child.stdout.on('data',v=>output+=v);
  const done=new Promise((resolve,reject)=>{child.once('error',reject);child.once('close',()=>resolve(output));});
  t.after(async()=>{child.kill();await done;});
  return {child,prefix,done};
}
function fixture(t,options={}) {
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'integration-811-'));
  t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const root=path.join(dir,'target'),source=path.join(dir,'source');fs.mkdirSync(root);
  const git=(...args)=>execFileSync('git',['-C',root,...args],{windowsHide:true,stdio:'pipe',encoding:'utf8'}).trim();
  git('init','-b','main');git('config','user.name','Fixture');git('config','user.email','fixture@invalid');git('config','core.autocrlf','false');
  const put=(base,name,value)=>{const f=path.join(base,'game',name);fs.mkdirSync(path.dirname(f),{recursive:true});fs.writeFileSync(f,value);};
  put(root,'project.godot','config_version=5\n');put(root,'edit.txt','old');put(root,'delete.txt','delete');put(root,'user.txt','untouched');
  if(options.newlines){put(root,'edit.txt','old\n');put(root,'user.txt','untouched\n');put(root,'tracked.bin',Buffer.from([0,13,10,255,10]));}
  if(options.attributes)fs.writeFileSync(path.join(root,'.gitattributes'),options.attributes);
  git('add','.');git('commit','-m','baseline');
  if(options.autocrlf)git('config','core.autocrlf','true');
  if(options.newlines){for(const name of ['edit.txt','user.txt','project.godot'])fs.unlinkSync(path.join(root,'game',name));git('checkout','--','game/edit.txt','game/user.txt','game/project.godot');}
  git('worktree','add','-b','producer',source);
  const newText=options.newlines?'new\n':'new';
  put(source,'edit.txt',newText);put(source,'binary.bin',Buffer.from([0,1,255,128]));fs.unlinkSync(path.join(source,'game/delete.txt'));
  const receipt=name=>{const p=path.join(dir,name);fs.writeFileSync(p,name);return {path:p,sha256:sha(name)};};
  const decision={candidate:captureCandidate(source),verdict:'pass',reason:'controlled independent fixture',design_sha256:'d'.repeat(64),
    producer:{worker_id:'p',conversation_id:'p',receipt:receipt('producer')},reviewer:{worker_id:'r',conversation_id:'r',receipt:receipt('reviewer')},
    criteria:[{id:'files',met:true,evidence:[{path:'game/edit.txt',sha256:sha(newText)}]}]};
  const live=path.join(dir,'live.json');fs.writeFileSync(live,JSON.stringify({active:true,request_nonce:'nonce'}));
  const request={action:'plan',decision_json:JSON.stringify(decision),workspace_root:root,project_root:path.join(root,'game'),transaction_root:path.join(root,'data-collection/outbox/project-integration'),request_nonce:'nonce',host_liveness_path:live};
  const run=(action,plan,extra={})=>integrate({...request,action,...(plan?{plan_path:plan.plan_path,plan_sha256:plan.plan_sha256}:{}),...extra});
  return {root,source,dir,request,decision,run,put,git,live};
}
for(const kind of ['live','foreign','unknown','legacy'])test('writer preserves '+kind+' ownership',t=>{
  const f=fixture(t);
  if(kind==='legacy') {
    fs.mkdirSync(f.request.transaction_root,{recursive:true});const file=path.join(f.request.transaction_root,'writer.lock');
    fs.writeFileSync(file,JSON.stringify({pid:2147483647}));const before=fs.readFileSync(file);
    assert.throws(()=>f.run('plan'),/legacy/);assert.deepEqual(fs.readFileSync(file),before);return;
  }
  const owner=ownership(f,kind==='foreign'?{host:os.hostname()+'-foreign',pid:2147483647}:kind==='unknown'?{nonce:null}:{});
  assert.throws(()=>f.run('plan'),/writer/);assert.equal(f.git('rev-parse',owner.ref),owner.oid);
  assert.equal(fs.readFileSync(path.join(f.root,'game/edit.txt'),'utf8'),'old');
});

test('real concurrent stale recovery permits one owner and preserves it against a live contender',async t=>{
  const f=fixture(t),pid=Number(execFileSync(process.execPath,['-e','process.stdout.write(String(process.pid))'],{windowsHide:true}));
  assert.throws(()=>process.kill(pid,0),{code:'ESRCH'});const old=ownership(f,{pid});
  const children=[contender(t,f,'a'),contender(t,f,'b')];
  await waitFor(()=>children.every(c=>fs.existsSync(c.prefix+'.ready')));
  for(const c of children)fs.writeFileSync(c.prefix+'.go','');
  await waitFor(()=>children.some(c=>fs.existsSync(c.prefix+'.acquired')));
  const winner=children.find(c=>fs.existsSync(c.prefix+'.acquired')),loser=children.find(c=>c!==winner);
  assert.ok(JSON.parse(await loser.done).error);const active=f.git('rev-parse',old.ref);assert.notEqual(active,old.oid);
  assert.throws(()=>f.run('plan'),/still active/);assert.equal(f.git('rev-parse',old.ref),active);
  assert.equal(fs.existsSync(loser.prefix+'.acquired'),false);
  fs.writeFileSync(winner.prefix+'.finish','');assert.equal(JSON.parse(await winner.done).state,'planned');
  assert.equal(JSON.parse(f.git('cat-file','blob',f.git('rev-parse',old.ref))).state,'released');
  assert.equal(f.run('plan').state,'planned');
});

for(const phase of ['before','after'])test('real process death '+phase+' acquisition leaves recoverable ownership',async t=>{
  const f=fixture(t),c=contender(t,f,'crash');await waitFor(()=>fs.existsSync(c.prefix+'.ready'));
  if(phase==='after'){fs.writeFileSync(c.prefix+'.go','');await waitFor(()=>fs.existsSync(c.prefix+'.acquired'));assert.throws(()=>f.run('plan'),/still active/);}
  c.child.kill();await c.done;assert.equal(f.run('plan').state,'planned');
});

test('release cannot overwrite another ownership generation',async t=>{
  const f=fixture(t),c=contender(t,f,'release');await waitFor(()=>fs.existsSync(c.prefix+'.ready'));
  fs.writeFileSync(c.prefix+'.go','');await waitFor(()=>fs.existsSync(c.prefix+'.acquired'));
  const replacement=ownership(f);fs.writeFileSync(c.prefix+'.finish','');
  assert.ok(JSON.parse(await c.done).error);assert.equal(f.git('rev-parse',replacement.ref),replacement.oid);
});

test('real worktrees: binary addition, edit, deletion, user preservation, retries and rollback',t=>{
  const f=fixture(t);f.put(f.root,'user.txt','user unsaved on disk');
  const p=f.run('plan');assert.equal(p.changed_count,3);assert.equal(f.run('apply',p).state,'applied');
  assert.deepEqual(fs.readFileSync(path.join(f.root,'game/binary.bin')),Buffer.from([0,1,255,128]));
  assert.equal(fs.existsSync(path.join(f.root,'game/delete.txt')),false);assert.equal(f.run('apply',p).state,'applied');
  f.put(f.source,'edit.txt','source now drifted');assert.equal(f.run('rollback',p).state,'rolled_back');
  assert.equal(fs.readFileSync(path.join(f.root,'game/edit.txt'),'utf8'),'old');assert.equal(fs.readFileSync(path.join(f.root,'game/user.txt'),'utf8'),'user unsaved on disk');
  assert.equal(f.run('rollback',p).state,'rolled_back');assert.equal(fs.existsSync(path.join(f.root,'game/binary.bin')),false);
});
for(const kind of ['dirty','source','target','head','cancel','plan','receipt','self','failed','outside','store','symlink','hardlink'])test('reject '+kind,t=>{
  const f=fixture(t);
  if(kind==='dirty'){f.put(f.root,'edit.txt','user');assert.deepEqual(f.run('plan').conflicts,['edit.txt']);return;}
  if(kind==='self'){f.decision.reviewer.worker_id='p';assert.throws(()=>f.run('plan',null,{decision_json:JSON.stringify(f.decision)}),/Independent/);return;}
  if(kind==='failed'){f.decision.criteria[0].met=false;assert.throws(()=>f.run('plan',null,{decision_json:JSON.stringify(f.decision)}),/Failed/);return;}
  if(kind==='outside'){assert.throws(()=>f.run('plan',null,{project_root:f.dir}),/boundary/);return;}
  if(kind==='store'){assert.throws(()=>f.run('plan',null,{transaction_root:f.dir}),/transaction/);return;}
  const p=f.run('plan');
  if(kind==='source')f.put(f.source,'edit.txt','drift');
  if(kind==='target')f.put(f.root,'edit.txt','user');
  if(kind==='head')f.git('commit','--allow-empty','-m','drift');
  if(kind==='cancel')fs.writeFileSync(f.live,JSON.stringify({active:false,request_nonce:'nonce'}));
  if(kind==='plan')fs.appendFileSync(p.plan_path,' ');
  if(kind==='receipt')fs.appendFileSync(f.decision.reviewer.receipt.path,'changed');
  if(kind==='symlink') {fs.unlinkSync(path.join(f.root,'game/edit.txt'));try{fs.symlinkSync(path.join(f.root,'game/user.txt'),path.join(f.root,'game/edit.txt'));}catch(e){if(e.code==='EPERM'){t.skip('Host denies symlink creation');return;}throw e;}}
  if(kind==='hardlink'){fs.unlinkSync(path.join(f.root,'game/edit.txt'));fs.linkSync(path.join(f.root,'game/user.txt'),path.join(f.root,'game/edit.txt'));}
  assert.throws(()=>f.run('apply',p));assert.equal(fs.existsSync(path.join(f.root,'game/binary.bin')),false);
});
test('rollback refuses intervening user changes',t=>{const f=fixture(t),p=f.run('plan');f.run('apply',p);f.put(f.root,'edit.txt','user');const r=f.run('rollback',p);assert.equal(r.state,'conflict');assert.deepEqual(r.conflicts,['edit.txt']);assert.equal(fs.readFileSync(path.join(f.root,'game/edit.txt'),'utf8'),'user');});
test('conservative crash recovery rejects apply, rollback recognizes intent and bytes',t=>{
  const f=fixture(t),p=f.run('plan'),journal=p.plan_path+'.journal.json';
  const j=JSON.parse(fs.readFileSync(journal));j.state='applying';j.pending='edit.txt';j.attempted=['edit.txt'];fs.writeFileSync(journal,JSON.stringify(j));
  f.put(f.root,'edit.txt','new');assert.throws(()=>f.run('apply',p),/requires rollback/);assert.equal(f.run('rollback',p).state,'rolled_back');
  assert.equal(fs.readFileSync(path.join(f.root,'game/edit.txt'),'utf8'),'old');
});
test('cancelled generation rejects rollback and new generation may recover pinned plan',t=>{
  const f=fixture(t),p=f.run('plan');f.run('apply',p);fs.writeFileSync(f.live,JSON.stringify({active:false,request_nonce:'nonce'}));assert.throws(()=>f.run('rollback',p),/cancelled/);
  fs.writeFileSync(f.live,JSON.stringify({active:true,request_nonce:'next'}));assert.equal(f.run('rollback',p,{request_nonce:'next'}).state,'rolled_back');
});
test('plan excludes unchanged and identical already-integrated assets',t=>{const f=fixture(t);f.put(f.root,'edit.txt','new');assert.equal(f.run('plan').changed_count,2);});
test('directory junction escape is rejected without changing outside bytes',t=>{
  const f=fixture(t);f.put(f.source,'assets/asset.txt','new asset');f.decision.candidate=captureCandidate(f.source);f.request.decision_json=JSON.stringify(f.decision);
  const p=f.run('plan'),outside=path.join(f.dir,'outside');fs.mkdirSync(outside);
  fs.symlinkSync(outside,path.join(f.root,'game/assets'),process.platform==='win32'?'junction':'dir');
  assert.throws(()=>f.run('apply',p),/Linked/);assert.deepEqual(fs.readdirSync(outside),[]);
});
test('staged user edits and index changes after planning are rejected',t=>{
  const f=fixture(t);f.put(f.root,'edit.txt','staged');f.git('add','game/edit.txt');f.put(f.root,'edit.txt','old');
  assert.deepEqual(f.run('plan').conflicts,['edit.txt']);f.git('reset','HEAD','--','game/edit.txt');const p=f.run('plan');
  f.put(f.root,'edit.txt','staged');f.git('add','game/edit.txt');f.put(f.root,'edit.txt','old');assert.throws(()=>f.run('apply',p),/index changed/);
});
test('rollback of untouched plan preserves later user edit even if it matches candidate',t=>{
  const f=fixture(t),p=f.run('plan');f.put(f.root,'edit.txt','new');assert.equal(f.run('rollback',p).state,'conflict');
});

for(const style of ['autocrlf','attributes'])test(`real Git ${style}: clean CRLF target, exact source bytes and rollback`,t=>{
  const f=fixture(t,{newlines:true,autocrlf:style==='autocrlf',attributes:style==='attributes'?'*.txt text eol=crlf\n*.bin -text\n':null});
  const edit=path.join(f.root,'game/edit.txt'),binary=path.join(f.root,'game/tracked.bin');
  const before=fs.readFileSync(edit),binaryBefore=fs.readFileSync(binary);
  assert.equal(before.toString(),'old\r\n');
  f.put(f.source,'tracked.bin',Buffer.from([0,13,10,254,10]));
  f.decision.candidate=captureCandidate(f.source);f.request.decision_json=JSON.stringify(f.decision);
  const p=f.run('plan');assert.equal(p.changed_count,4);
  assert.equal(f.run('apply',p).state,'applied');assert.equal(fs.readFileSync(edit,'utf8'),'new\n');
  assert.deepEqual(fs.readFileSync(binary),Buffer.from([0,13,10,254,10]));
  assert.equal(f.run('rollback',p).state,'rolled_back');assert.deepEqual(fs.readFileSync(edit),before);assert.deepEqual(fs.readFileSync(binary),binaryBefore);
});

test('different source/target checkout newlines do not turn unchanged source into an edit',t=>{
  const f=fixture(t,{newlines:true,autocrlf:true});
  f.git('config','extensions.worktreeConfig','true');
  execFileSync('git',['-C',f.source,'config','--worktree','core.autocrlf','false'],{windowsHide:true});
  fs.unlinkSync(path.join(f.source,'game/user.txt'));
  fs.unlinkSync(path.join(f.source,'game/project.godot'));
  execFileSync('git',['-C',f.source,'checkout','--','game/user.txt','game/project.godot'],{windowsHide:true});
  assert.equal(fs.readFileSync(path.join(f.source,'game/user.txt'),'utf8'),'untouched\n');
  f.put(f.root,'user.txt','real user edit\r\n');
  f.decision.candidate=captureCandidate(f.source);f.request.decision_json=JSON.stringify(f.decision);
  const p=f.run('plan');assert.equal(p.changed_count,3);assert.equal(f.run('apply',p).state,'applied');
  assert.equal(fs.readFileSync(path.join(f.root,'game/user.txt'),'utf8'),'real user edit\r\n');
});

for(const kind of ['content','newline-only','binary','staged','index-drift'])test(`CRLF safeguards preserve ${kind}`,t=>{
  const f=fixture(t,{newlines:true,autocrlf:true});
  if(kind==='binary'){
    f.put(f.source,'tracked.bin',Buffer.from([0,13,10,254,10]));f.put(f.root,'tracked.bin',Buffer.from([0,10,255,10]));
    f.decision.candidate=captureCandidate(f.source);f.request.decision_json=JSON.stringify(f.decision);
    assert.deepEqual(f.run('plan').conflicts,['tracked.bin']);return;
  }
  if(kind==='content'||kind==='newline-only'){
    f.put(f.root,'edit.txt',kind==='content'?'user\r\n':'old\n');assert.deepEqual(f.run('plan').conflicts,['edit.txt']);return;
  }
  const p=kind==='index-drift'?f.run('plan'):null;
  f.put(f.root,'edit.txt','staged\r\n');f.git('add','game/edit.txt');f.put(f.root,'edit.txt','old\r\n');
  if(p)assert.throws(()=>f.run('apply',p),/index changed/);else assert.deepEqual(f.run('plan').conflicts,['edit.txt']);
});

test('baseline conversion disables configured smudge and process drivers',t=>{
  const f=fixture(t,{newlines:true,attributes:'*.txt text eol=crlf filter=untrusted\n'});
  // A failing driver proves neither command is invoked by baseline inspection.
  f.git('config','filter.untrusted.smudge','exit 73');f.git('config','filter.untrusted.process','exit 74');f.git('config','filter.untrusted.required','true');
  const p=f.run('plan');assert.equal(p.changed_count,3);assert.equal(f.run('apply',p).state,'applied');
  assert.equal(f.run('rollback',p).state,'rolled_back');
});

for(const changed of [false,true])test(`registered private snapshot preserves original dirty target; later edit=${changed}`,t=>{
  const f=fixture(t);
  const sourceGit=(...args)=>execFileSync('git',['-C',f.source,...args],{windowsHide:true,encoding:'utf8'}).trim();
  // A dangling commit-tree snapshot, as used by production setup; target HEAD
  // and its index stay unchanged while the original dirty bytes are captured.
  f.put(f.root,'edit.txt','original dirty user bytes');
  sourceGit('reset','--hard','HEAD');f.put(f.source,'edit.txt','original dirty user bytes');sourceGit('add','game/edit.txt');
  const base=sourceGit('commit-tree',sourceGit('write-tree'),'-p',f.git('rev-parse','HEAD'),'-m','private snapshot');
  sourceGit('reset','--hard',base);f.put(f.source,'edit.txt','new');
  const policy={tenant_id:'fixture',request_id:'snapshot-test',source_ref:'https://github.com/example/repo/issues/811'};
  f.decision.candidate=captureCandidate(f.source,policy);
  const candidate={...f.decision.candidate,base_sha:base};
  const writeReceipt=(name,value)=>{const file=path.join(f.dir,name),raw=JSON.stringify(value);fs.writeFileSync(file,raw);return {path:file,sha256:sha(raw)};};
  const registration=writeReceipt('registration.json',{schema_version:1,execution_id:'external',worker_id:'p',design_sha256:f.decision.design_sha256,issue_number:811,request_id:policy.request_id,candidate});
  f.decision.producer={worker_id:'p',execution_id:'external',receipt:writeReceipt('terminal.json',{schema_version:1,execution_id:'external',worker_id:'p',issue_number:811,request_id:policy.request_id,transport_completed:true,state:'review',exit_code:0,cancel_requested:false,pid:123,reporting:{ok:true,state:'recorded_file'},registration,candidate})};
  f.request.decision_json=JSON.stringify(f.decision);
  if(changed){f.put(f.root,'edit.txt','later user edit');assert.deepEqual(f.run('plan').conflicts,['edit.txt']);return;}
  const p=f.run('plan');assert.equal(JSON.parse(fs.readFileSync(p.plan_path)).base_sha,base);
  assert.equal(f.run('apply',p).state,'applied');assert.equal(fs.readFileSync(path.join(f.root,'game/edit.txt'),'utf8'),'new');
  assert.equal(f.run('rollback',p).state,'rolled_back');assert.equal(fs.readFileSync(path.join(f.root,'game/edit.txt'),'utf8'),'original dirty user bytes');
});
test('installed Python adapter rejects cancelled and mismatched selections before authority or writes',t=>{
  const f=fixture(t),adapter=path.resolve('customizations/components/godot-host/project_integration.py');
  const code=`import importlib.util,json,sys\nspec=importlib.util.spec_from_file_location('adapter',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\nr=json.loads(sys.argv[3])\ntry: m.execute(object(),sys.argv[2],r)\nexcept ValueError as e: print(str(e))\nelse: raise AssertionError('accepted')`;
  fs.writeFileSync(f.live,JSON.stringify({active:false,request_nonce:'nonce'}));
  const run=()=>execFileSync(process.env.GONGGONG_PYTHON||'py',['-X','utf8','-c',code,adapter,f.root,JSON.stringify(f.request)],{windowsHide:true,encoding:'utf8'});
  assert.match(run(),/cancelled/);fs.writeFileSync(f.live,JSON.stringify({active:true,request_nonce:'nonce'}));assert.match(run(),/selection/);
});
test('real concurrent cancellation during mutation leaves recoverable journal',async t=>{
  const f=fixture(t);for(let i=0;i<160;i++)f.put(f.source,`assets/${i}.txt`,'asset '+i);
  f.decision.candidate=captureCandidate(f.source);f.request.decision_json=JSON.stringify(f.decision);const p=f.run('plan');
  const code=`const fs=require('fs'),[journal,live]=process.argv.slice(1);const timer=setInterval(()=>{try{const j=JSON.parse(fs.readFileSync(journal));if(j.state==='applying'){fs.writeFileSync(live,JSON.stringify({active:false,request_nonce:'nonce'}));clearInterval(timer);process.exit(0);}}catch{}},1);process.stdout.write('ready');setTimeout(()=>process.exit(2),15000).unref();`;
  const child=spawn(process.execPath,['-e',code,p.plan_path+'.journal.json',f.live],{windowsHide:true,stdio:['ignore','pipe','pipe']});
  t.after(()=>child.kill());await new Promise((resolve,reject)=>{child.stdout.once('data',resolve);child.once('error',reject);});
  const result=f.run('apply',p);assert.equal(result.state,'reconcile_required');
  fs.writeFileSync(f.live,JSON.stringify({active:true,request_nonce:'nonce'}));assert.equal(f.run('rollback',p).state,'rolled_back');
  assert.equal(fs.readFileSync(path.join(f.root,'game/edit.txt'),'utf8'),'old');assert.equal(fs.existsSync(path.join(f.root,'game/binary.bin')),false);
});
