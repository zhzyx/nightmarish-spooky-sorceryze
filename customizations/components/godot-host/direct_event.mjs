// Consume the verified GitHub readback. This event has no worker requests or execution runtime.
import fs from 'node:fs';
import {GitHubIssueSource} from '../issue-workorders/github_source.mjs';
import {planDispatch} from '../../../customizations/platforms/process-management/yuanheng-local/sinan/dispatch.mjs';

const {result, issue, repository, allowedCategories} = JSON.parse(fs.readFileSync(0, 'utf8'));
const binding = {number: result.number, requestId: result.request_id};
const event = {type: 'request.created', reference: result.url};
const source = new GitHubIssueSource({repository, bindings: [binding], allowedCategories, readIssue: async () => issue});
const {snapshot, environment} = await source.inspect(event);
const [item] = snapshot.items;
const [sourceSnapshot] = snapshot.sourceSnapshots;
if (snapshot.sourcesRead !== 1 || snapshot.diagnostics.length || sourceSnapshot.authority !== result.url ||
    item.lifecycle !== 'open' || item.status !== 'status:' + result.status || issue.updated_at !== result.revision) {
  throw Error('Sinan could not reconcile this event with the verified GitHub Issue revision');
}
const {execution} = planDispatch(snapshot, [], environment);
console.log(JSON.stringify({event, sourceSnapshot, revision: issue.updated_at, status: item.status,
  scope: snapshot.scope, sourcesRead: snapshot.sourcesRead, sourcesRegistered: snapshot.sourcesRegistered,
  ready: item.dispatchCandidate, execution}));
