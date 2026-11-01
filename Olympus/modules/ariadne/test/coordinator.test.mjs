import {fileURLToPath} from 'node:url';
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {board,prepare,filterItems,labelRegistry} from '../coordinator.mjs';
const base=path.resolve(process.env.WORKORDER_TEST_ROOT||'work');fs.mkdirSync(base,{recursive:true});
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
function fixture(id,tasks,agents=[]) {const root=fs.mkdtempSync(path.join(base,'tickets-'));fs.mkdirSync(path.join(root,'.yuanheng'));fs.writeFileSync(path.join(root,'proof.txt'),'verified');const t=tasks.map(x=>({goal:'goal',title:x.id,acceptance:['criterion'],dependsOn:[],owner:'owner',...x,...(x.status==='done'?{artifacts:[{path:'proof.txt',sha256:hash('verified')}],review:{verdict:'pass',criteria:[{met:true,evidence:'proof.txt'}]}}:{})}));fs.writeFileSync(path.join(root,'.yuanheng','state.json'),JSON.stringify({ledgerId:id,tasks:t,agents,events:[]}));return root;}
const config=(a,b)=>({sources:[{id:'a',root:a},...(b?[{id:'b',root:b}]:[])],dependencies:[],coordination:[],adapter_cli:fileURLToPath(new URL('../coordinator.mjs',import.meta.url))});
test('same local ID remains distinct across ledgers and scanning never writes',()=>{const a=fixture('A',[{id:'YH-0001',status:'open'}]),b=fixture('B',[{id:'YH-0001',status:'open'}]);const before=fs.readFileSync(path.join(a,'.yuanheng','state.json'));assert.equal(board(config(a,b)).items.length,2);assert.deepEqual(fs.readFileSync(path.join(a,'.yuanheng','state.json')),before);});
test('cross-ledger hard dependency and evidence mutation affect readiness',()=>{const a=fixture('A',[{id:'1',status:'done'}]),b=fixture('B',[{id:'2',status:'open'}]),c=config(a,b);c.dependencies=[{ticket:'B::2',requires:'A::1',kind:'hard'}];assert.deepEqual(board(c).ready,['B::2']);fs.writeFileSync(path.join(a,'proof.txt'),'changed');assert.equal(board(c).ready.length,0);});
test('cycles block even records already marked done, and soft dependencies do not block',()=>{const a=fixture('A',[{id:'1',status:'done'},{id:'2',status:'done'},{id:'3',status:'open'}]);const c=config(a);c.dependencies=[{ticket:'A::1',requires:'A::2',kind:'hard'},{ticket:'A::2',requires:'A::1',kind:'hard'},{ticket:'A::3',requires:'A::1',kind:'soft'}];const s=board(c);assert.equal(s.items[0].acceptanceValid,false);assert.deepEqual(s.ready,['A::3']);});
test('missing dependencies and unreadable source block affected branch only',()=>{const a=fixture('A',[{id:'1',status:'open'},{id:'2',status:'open'}]),c=config(a);c.sources.push({id:'bad',root:path.join(a,'missing')});c.dependencies=[{ticket:'A::1',requires:'missing::1',kind:'hard'}];const s=board(c);assert.equal(s.diagnostics.length,1);assert.deepEqual(s.ready,['A::2']);});
test('pending user record is applied before downstream acceptance regardless of source order',()=>{const a=fixture('A',[{id:'2',status:'open',dependsOn:['1']},{id:'1',status:'done'}]),c=config(a);c.coordination=[{ticket:'A::1',pending_user:true}];assert.equal(board(c).ready.length,0);});
test('delegation is not execution; duplicate sources are diagnosed',()=>{const a=fixture('A',[{id:'1',status:'running',agent:'worker'}],[{id:'worker',execution:'pending_host'}]),c=config(a);c.sources.push({id:'alias',root:a});const s=board(c);assert.equal(s.items.length,1);assert.equal(s.diagnostics.length,1);assert.equal(s.items[0].coordinationState,'delegated_pending_host');});
test('prepare does not execute and rejects blocked start',()=>{const a=fixture('A',[{id:'1',status:'open',dependsOn:['missing']}]),c=config(a);assert.throws(()=>prepare(c,board(c),'a','start',['1','mandate.json']),/constraints/);const empty=fixture('E',[]),e=config(empty);const p=prepare(e,board(e),'a','task',['task.json']);assert.equal(p.execution,'not_executed');assert.equal(p.argv[2],empty);});
test('rejection can return a review to repair despite an invalid upstream dependency',()=>{const a=fixture('A',[{id:'1',status:'review',dependsOn:['missing']}]),c=config(a),file=path.join(a,'review.json');fs.writeFileSync(file,JSON.stringify({verdict:'fail'}));assert.equal(prepare(c,board(c),'a','review',['1',file]).execution,'not_executed');fs.writeFileSync(file,JSON.stringify({verdict:'pass'}));assert.throws(()=>prepare(c,board(c),'a','review',['1',file]),/constraints/);});
test('incomplete definitions never enter dispatch candidates',()=>{const a=fixture('A',[{id:'1',status:'open',goal:''}]);assert.equal(board(config(a)).ready.length,0);});
test('type, progress and judgment labels coexist and filters intersect',()=>{
 const a=fixture('A',[{id:'1',status:'running'},{id:'2',status:'open'}]),c=config(a);
 c.coordination=[{ticket:'A::1',type:'bug',tags:['登录'],assessment:{state:'pending',owner:'忒弥斯',reason:'需判断接口影响',blocking:false}}];
 const s=board(c);assert.deepEqual(filterItems(s,['type:bug','state:processing','decision:pending']).map(t=>t.key),['A::1']);
 assert.equal(s.items[1].labels.includes('state:planned'),true);assert.equal(s.items[1].type,'unclassified');
 assert.equal(s.items[0].pendingUser,false);assert.equal(s.items[0].problems.includes('pending_judgment'),false);
});
test('pending host is not processing and blocking judgment propagates only to hard dependents',()=>{
 const a=fixture('A',[{id:'1',status:'done'},{id:'2',status:'open',dependsOn:['1']},{id:'3',status:'open'},{id:'4',status:'running',agent:'worker'}],[{id:'worker',execution:'pending_host'}]),c=config(a);
 c.coordination=[{ticket:'A::1',assessment:{state:'pending',owner:'owner',reason:'需评估影响',blocking:true}}];
 const s=board(c);assert.deepEqual(s.ready,['A::3']);assert.equal(s.items[0].acceptanceValid,false);assert.ok(s.items[3].labels.includes('state:awaiting_host'));assert.ok(!s.items[3].labels.includes('state:processing'));
});
test('label edits persist with audit, preserve coordination fields and never write source',()=>{
 const a=fixture('A',[{id:'1',status:'open'}]),c=config(a),file=path.join(a,'registry.json'),source=path.join(a,'.yuanheng','state.json');
 c.coordination=[{ticket:'A::1',priority:0,pending_user:true}];fs.writeFileSync(file,JSON.stringify(c));const before=fs.readFileSync(source);
 labelRegistry(file,'A::1',{type:'bug',tags:['登录','登录'],actor:'operator',reason:'已确认缺陷'});
 const updated=JSON.parse(fs.readFileSync(file));assert.deepEqual(updated.coordination[0].tags,['登录']);assert.equal(updated.coordination[0].priority,0);assert.equal(updated.label_history.length,1);assert.deepEqual(fs.readFileSync(source),before);
 assert.ok(board(updated).items[0].labels.includes('decision:user'));
 labelRegistry(file,'A::1',{assessment:{state:'resolved',owner:'owner',reason:'已给出处理方案',reference:'decision-1'},tags:[],actor:'operator',reason:'更新分类'});
 assert.equal(JSON.parse(fs.readFileSync(file)).label_history.length,2);assert.ok(board(JSON.parse(fs.readFileSync(file))).items[0].labels.includes('decision:user'));
});
test('invalid or unavailable labels and concurrent edits leave configuration intact',()=>{
 const a=fixture('A',[{id:'1',status:'open'}]),file=path.join(a,'registry.json');fs.writeFileSync(file,JSON.stringify(config(a)));const before=fs.readFileSync(file);
 for(const change of [{type:''},{type:12},{type:'state:done'},{type:'research task'},{tags:['state:done']},{status:'done'},{assessment:{state:'pending',owner:'owner',reason:'why'}},{assessment:{state:'resolved',owner:'owner',reason:'why'}}])assert.throws(()=>labelRegistry(file,'A::1',{...change,actor:'operator',reason:'test'}));
 assert.throws(()=>labelRegistry(file,'A::missing',{type:'bug',actor:'operator',reason:'test'}),/unavailable/);
 fs.writeFileSync(file+'.lock','busy');assert.throws(()=>labelRegistry(file,'A::1',{type:'bug',actor:'operator',reason:'test'}),/EEXIST/);fs.unlinkSync(file+'.lock');assert.deepEqual(fs.readFileSync(file),before);
});
test('CLI persists labels and filters a real fixture through its public commands',()=>{
 const a=fixture('A',[{id:'1',status:'open'},{id:'2',status:'open'}]),file=path.join(a,'registry.json'),change=path.join(a,'change.json');fs.writeFileSync(file,JSON.stringify(config(a)));fs.writeFileSync(change,JSON.stringify({type:'bug',actor:'operator',reason:'confirmed'}));
 const run=(...args)=>{const r=spawnSync(process.execPath,[fileURLToPath(new URL('../coordinator.mjs',import.meta.url)),...args],{encoding:'utf8'});assert.equal(r.status,0,r.stderr);return JSON.parse(r.stdout);};
 assert.equal(run('label',file,'A::1',change).updated,true);assert.deepEqual(run('board',file,'type:bug','state:planned').items.map(t=>t.key),['A::1']);assert.deepEqual(run('ready',file,'type:bug'),['A::1']);
});
test('non-development and new business types persist and coordinate without Feature membership',()=>{
 const kinds=['research','operations','content','design','coordination','administration','采购'];
 const a=fixture('A',kinds.map((type,i)=>({id:String(i),title:type,goal:'完成对应业务成果',status:'open'}))),file=path.join(a,'registry.json');
 fs.writeFileSync(file,JSON.stringify(config(a)));
 for(const [i,type] of kinds.entries())labelRegistry(file,`A::${i}`,{type,actor:'业务主责',reason:'按实际工作分类'});
 const s=board(JSON.parse(fs.readFileSync(file)));assert.equal(s.ready.length,kinds.length);
 for(const [i,type] of kinds.entries()){const t=filterItems(s,[`type:${type}`,'state:planned'])[0];assert.equal(t.key,`A::${i}`);assert.deepEqual(t.featureRefs,[]);}
});
