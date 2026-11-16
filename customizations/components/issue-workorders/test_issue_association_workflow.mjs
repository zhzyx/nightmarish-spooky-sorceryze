import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const workflow = readFileSync(new URL('../../../.github/workflows/gonggong-issue-gate.yml', import.meta.url), 'utf8');
const code = workflow.split('          script: |\n')[1].split('\n').map(line => line.replace(/^            /, '')).join('\n');
const execute = new (Object.getPrototypeOf(async function () {}).constructor)('github', 'context', 'core', code);
function fixture() {
  const issue = { number: 1388, state: 'open', html_url: 'https://github.com/example/repo/issues/1388', body: '<!-- gonggong-request:collaborator-pr-unblock-20261117 -->', labels: ['workspace:gonggong', 'type:bug', 'status:in-progress'] };
  const pr = { number: 9, state: 'open', body: 'GongGong-Issue: #1388\nGongGong-Request: collaborator-pr-unblock-20261117\n', base: {sha: 'base'} };
  const files = [];
  const blobs = {};
  const github = {rest: {pulls: {get: async () => ({data: pr}), listFiles: {}}, issues: {get: async () => ({data: issue})}, repos: {getContent: async () => ({data: {content: Buffer.from(JSON.stringify([{name:'type:bug'}])).toString('base64')}})}, git: {getBlob: async ({file_sha}) => ({data: {encoding:'base64', content: Buffer.from(JSON.stringify(blobs[file_sha])).toString('base64')}})}}, paginate: async () => files};
  const core = {warning() {}, summary: { addRaw() { return this; }, async write() {} }};
  return {issue, pr, files, blobs, run: () => execute(github, {repo:{owner:'example',repo:'repo'},payload:{pull_request:{number:9}}}, core)};
}
test('read-only pull_request event without checkout, secrets or write privileges', () => {
  assert.match(workflow, /\n  pull_request:\n/);
  assert.doesNotMatch(workflow, /pull_request_target:|actions\/checkout|secrets\.|: write/);
});
test('valid association passes without requiring a named reviewer', async () => { await fixture().run(); });
test('missing identity fails', async () => { const f=fixture(); f.pr.body=''; await assert.rejects(f.run(), /Require one/); });
test('mismatched request fails', async () => { const f=fixture(); f.issue.body='<!-- gonggong-request:another -->'; await assert.rejects(f.run(), /identity/); });
test('closed issue fails', async () => { const f=fixture(); f.issue.state='closed'; await assert.rejects(f.run(), /open Issue/); });
test('inactive status fails', async () => { const f=fixture(); f.issue.labels[2]='status:done'; await assert.rejects(f.run(), /active status/); });
test('recorded event without collection fails, matching collection passes', async () => {
  const f=fixture();
  f.files.push({filename:'gonggong-diting-data/events/gonggong-workspace/test/event.json',sha:'event'});
  f.blobs.event={tenant_id:'gonggong-workspace',request_id:'collaborator-pr-unblock-20261117'};
  await assert.rejects(f.run(), /collection evidence/);
  f.files.push({filename:'data-collection/test.json',sha:'collection'});
  f.blobs.collection={request_id:'collaborator-pr-unblock-20261117',issue_number:1388};
  await f.run();
});
