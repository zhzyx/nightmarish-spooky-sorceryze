import {test} from 'node:test';
import assert from 'node:assert/strict';
import {GitHubIssueSource, issueSnapshot} from './github_source.mjs';
const binding = {number: 9, requestId: 'test-request'};
const issue = () => ({number: 9, html_url: 'https://github.com/test/repo/issues/9', title: 'test', state: 'open', updated_at: '2026-11-05T00:00:00Z', body: '<!-- gonggong-request:test-request -->', labels: ['workspace:gonggong','type:development','status:in-progress'].map(name => ({name})), assignees: []});
const event = {type: 'user.requested', reference: 'synthetic-test'};
const runtime = () => ({environment: async () => ({active: [], capacity: 1, catalog: []}), assess: async () => true, authorize: async () => true, compareAndStart: async a => ({key:a.key,ticket:a.ticket,sourceSha256:a.sourceSnapshot.sha256,reference:'synthetic-start'}), ack: async () => true, report: async () => {}, verifyTerminal: async () => true});
function source(rt = null, readIssue = async () => issue()) {return new GitHubIssueSource({repository:'test/repo',allowedCategories:['type:development'],bindings:[binding],readIssue,runtime:rt});}
async function assignment(s) {const {snapshot} = await s.inspect(event);return {ticket:snapshot.items[0].key,key:'test-key',sourceSnapshot:snapshot.sourceSnapshots[0],model:{id:'test-model'},target:'agent'};}
test('read-only source is not a dispatcher or fake Yuanheng ledger', async () => {
  const s = source(); const {snapshot, environment} = await s.inspect(event);
  assert.equal(snapshot.sourcesRead,1); assert.deepEqual(snapshot.ready,[]); assert.equal(environment.capacity,0);
  assert.equal(snapshot.sourceSnapshots[0].ledgerId,undefined); assert.equal(await s.revalidate(await assignment(s)),false);
  await assert.rejects(s.startSource(await assignment(s)),/not authorized/);
});
test('wrong identity, ambiguity and workspace rejected', () => {
  for (const mutate of [v=>v.number=10,v=>v.pull_request={},v=>v.body+='<!-- gonggong-request:other -->',v=>v.labels.pop(),v=>v.labels.shift()]) {
    const v=issue();mutate(v);assert.throws(()=>issueSnapshot('test/repo',binding,v,['type:development']));
  }
});
test('dependencies only explicit and source version changes on reassignment', () => {
  const v=issue();v.body+=' see #10 <!-- gonggong-depends-on:#11 -->';
  const a=issueSnapshot('test/repo',binding,v,['type:development']);assert.deepEqual(a.item.dependsOn,['github:test/repo#11']);
  v.assignees=[{login:'new-owner'}];assert.notEqual(a.sourceSnapshot.sha256,issueSnapshot('test/repo',binding,v,['type:development']).sourceSnapshot.sha256);
});
test('one unavailable source does not hide readable independent source', async () => {
  const s=new GitHubIssueSource({repository:'test/repo',allowedCategories:['type:development'],bindings:[binding,{number:10,requestId:'other'}],readIssue:async (_,n)=>{if(n===10)throw Error('unavailable');return issue();}});
  const {snapshot}=await s.inspect(event);assert.equal(snapshot.sourcesRead,1);assert.equal(snapshot.diagnostics.length,1);
});
test('source revision drift prevents start before backend call', async () => {
  let v=issue(),starts=0;const rt=runtime();rt.compareAndStart=async()=>{starts++;};const s=source(rt,async()=>v);const a=await assignment(s);
  v=issue();v.title='changed';await assert.rejects(s.startSource(a));assert.equal(starts,0);
});
test('source start and ack require exact backend and worker receipts', async () => {
  const rt=runtime(),s=source(rt),a=await assignment(s);assert.equal((await s.startSource(a)).reference,'synthetic-start');
  rt.compareAndStart=async()=>({reference:'unbound'});await assert.rejects(s.startSource(a),/Unverified/);
  const receipt={workerId:'w',reference:'agent:w',model:'test-model',target:'agent'};await s.ack(a,receipt);
  await assert.rejects(s.ack(a,{...receipt,model:'wrong'}));await assert.rejects(s.ack(a,{...receipt,setupPending:true}));
  rt.ack=async()=>false;await assert.rejects(s.ack(a,receipt),/unknown/);
});
test('active workers cannot become ready; terminal status requires verification', async () => {
  const rt=runtime();rt.environment=async()=>({active:[{ticket:'github:test/repo#9'}],catalog:[],capacity:1});const s=source(rt);
  assert.deepEqual((await s.inspect(event)).snapshot.ready,[]);
  assert.equal(await s.verifyTerminal({},event,{}),false);rt.verifyTerminal=async()=>false;
  assert.equal(await s.verifyTerminal({},{type:'execution.finished',reference:'test'},{}),false);
  await assert.rejects(s.inspect({type:'timer',reference:'test'}));
});

test('unknown category rejected and local assessment failure isolated', async () => {
  const v=issue();v.labels[1].name='type:unknown';assert.throws(()=>issueSnapshot('test/repo',binding,v,['type:development']));
  const rt=runtime();rt.assess=async item=>{if(item.key.endsWith('#9'))throw Error('local evidence unavailable');return true;};
  const s=new GitHubIssueSource({repository:'test/repo',allowedCategories:['type:development'],bindings:[binding,{number:10,requestId:'test-request'}],runtime:rt,readIssue:async(_,n)=>({...issue(),number:n,html_url:`https://github.com/test/repo/issues/${n}`})});
  const {snapshot}=await s.inspect(event);assert.deepEqual(snapshot.ready,['github:test/repo#10']);assert.equal(snapshot.diagnostics[0].stage,'assessment');
});
