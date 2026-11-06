// Candidate source callbacks for Sinan's host adapter. No scheduler or launcher.
import crypto from 'node:crypto';
const hash = x => crypto.createHash('sha256').update(JSON.stringify(x)).digest('hex');
const nonempty = x => typeof x === 'string' && !!x.trim();
const events = new Set(['request.created', 'ticket.changed', 'dependency.changed', 'decision.recorded', 'execution.finished', 'execution.failed', 'user.requested', 'scope.changed']);
const methods = ['environment', 'assess', 'authorize', 'compareAndStart', 'ack', 'report', 'verifyTerminal'];

// Follow the provider's native dependency list whenever it exists. A partial
// list cannot establish readiness, even if all visible dependencies passed.
async function readDependencies(issue, readPage) {
  const total = issue.issue_dependencies_summary?.total_blocked_by;
  if (total === 0) return [];
  if (total !== undefined && (!Number.isSafeInteger(total) || total < 0)) throw Error('Invalid dependency count');
  const tickets = new Set();
  for (let page = 1; total === undefined || tickets.size < total; page++) {
    const rows = await readPage(page);
    if (total === undefined && Array.isArray(rows) && !rows.length) break;
    if (!Array.isArray(rows) || !rows.length) throw Error('Incomplete native dependency list');
    for (const row of rows) {
      const match = /^https:\/\/github\.com\/([\w.-]+\/[\w.-]+)\/issues\/([1-9][0-9]*)$/.exec(row.html_url);
      if (!match || row.number !== Number(match[2]) || row.pull_request) throw Error('Invalid dependency Issue');
      const ticket = 'github:' + match[1] + '#' + match[2];
      if (tickets.has(ticket)) throw Error('Native dependency list changed during read');
      tickets.add(ticket);
    }
    if (total === undefined && rows.length < 100) break;
  }
  if (total !== undefined && tickets.size !== total) throw Error('Native dependency count changed during read');
  return [...tickets].sort();
}

export async function readIssueWithDependencies(api, repository, number) {
  const url = `repos/${repository}/issues/${number}`;
  const issue = await api(url);
  issue.nativeDependencies = await readDependencies(issue,
    page => api(`${url}/dependencies/blocked_by?per_page=100&page=${page}`));
  return issue;
}

export function issueSnapshot(repository, binding, issue, allowedCategories) {
  const url = `https://github.com/${repository}/issues/${binding.number}`;
  if (issue.number !== binding.number || issue.html_url !== url || issue.pull_request) throw Error('Wrong Issue identity');
  const body = issue.body ?? '';
  const ids = new Set([...body.matchAll(/<!--\s*(?:gonggong|olympus)-request:([a-z0-9]+(?:-[a-z0-9]+)*)\s*-->/g)].map(x => x[1]));
  for (const x of body.matchAll(/^### 稳定需求 ID\s*\n+([a-z0-9]+(?:-[a-z0-9]+)*)[ \t]*(?=\r?$)/gm)) ids.add(x[1]);
  if (ids.size !== 1 || !ids.has(binding.requestId)) throw Error('Ambiguous request identity');
  const labels = issue.labels.map(x => x.name).sort();
  const statuses = labels.filter(x => x.startsWith('status:'));
  const categories = labels.filter(x => x.startsWith('type:'));
  if (!labels.includes('workspace:gonggong') || statuses.length !== 1 || categories.length !== 1 || !allowedCategories.includes(categories[0])) throw Error('Invalid Issue labels');
  if (!['open', 'closed'].includes(issue.state) || !nonempty(issue.updated_at)) throw Error('Missing authoritative revision');
  const status = statuses[0];
  if (!['planned', 'needs-decision', 'in-progress', 'in-review', 'blocked', 'done', 'cancelled'].some(x => status === `status:${x}`)) throw Error('Unknown status');
  const source = `github:${repository}#${binding.number}`;
  const dependencies = [...new Set([...body.matchAll(/<!--\s*gonggong-depends-on:#([1-9][0-9]*)\s*-->/g)].map(x => Number(x[1])))].sort((a,b) => a-b);
  const revision = {number: issue.number, state: issue.state, updated_at: issue.updated_at,
    body_sha256: hash(body), title: issue.title, labels, assignees: issue.assignees.map(x => x.login).sort(), dependencies};
  const native = issue.nativeDependencies ?? [];
  if (native.length !== (issue.issue_dependencies_summary?.total_blocked_by ?? native.length)) throw Error('Native dependency evidence missing');
  if (native.length) revision.nativeDependencies = native;
  const dependsOn = [...new Set([...dependencies.map(n => `github:${repository}#${n}`), ...native])];
  const sourceSnapshot = {source, provider: 'github_issues', authority: url, requestId: binding.requestId, sha256: hash(revision)};
  return {sourceSnapshot, item: {key: source, source, title: issue.title, status, lifecycle: issue.state,
    owner: revision.assignees, dependsOn,
    dispatchCandidate: false, acceptanceValid: false, requestId: binding.requestId}};
}

/** runtime is a trusted host execution service, never an Issue-body declaration.
 * compareAndStart MUST serialize claims across all operators bound to the same
 * execution installation, reread and bind the observed source revision under that
 * lock, and revalidate before native launch. This is not GitHub-global CAS;
 * multiple installations must share a claim service, not independent local locks.
 */
export class GitHubIssueSource {
  constructor({repository, bindings, readIssue, allowedCategories, runtime = null}) {
    if (!/^[\w.-]+\/[\w.-]+$/.test(repository) || typeof readIssue !== 'function' || !Array.isArray(bindings) || !bindings.length) throw Error('Explicit source binding required');
    const seen = new Set();
    for (const b of bindings) {
      if (!Number.isSafeInteger(b.number) || b.number < 1 || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(b.requestId) || seen.has(b.number)) throw Error('Invalid or duplicate binding');
      seen.add(b.number);
    }
    if (!Array.isArray(allowedCategories) || !allowedCategories.length || allowedCategories.some(x => !nonempty(x))) throw Error('Configured categories required');
    this.allowedCategories = [...allowedCategories];
    if (runtime && methods.some(m => typeof runtime[m] !== 'function')) throw Error('Incomplete execution host');
    this.repository = repository; this.bindings = structuredClone(bindings); this.readIssue = readIssue; this.runtime = runtime;
  }
  async read(binding) {return issueSnapshot(this.repository, binding, await this.readIssue(this.repository, binding.number), this.allowedCategories);}
  async inspect(event) {
    if (!events.has(event?.type) || !nonempty(event.reference)) throw Error('Actual business event required');
    const snapshot = {sourcesRegistered: this.bindings.length, sourcesRead: 0, scope: 'explicit_host_bindings_only', items: [], sourceSnapshots: [], followUps: [], diagnostics: [], ready: []};
    for (const binding of this.bindings) {
      try {
        const {item, sourceSnapshot} = await this.read(binding);
        snapshot.items.push(item); snapshot.sourceSnapshots.push(sourceSnapshot); snapshot.sourcesRead++;
      } catch (e) {snapshot.diagnostics.push({issue: binding.number, error: String(e.message)});}
    }
    // Source state is visible; readiness is never inferred from labels or closure.
    // Host planning must assess dependency evidence, authority and existing workers.
    const environment = this.runtime ? await this.runtime.environment(snapshot, event) : {catalog: [], active: [], capacity: 0};
    for (const item of snapshot.items) {
      const version = snapshot.sourceSnapshots.find(s => s.source === item.source);
      try {
      if (this.runtime && item.lifecycle === 'open' && item.status === 'status:in-progress' &&
          !environment.active.some(a => a.ticket === item.key) && await this.runtime.assess(item, version, event) === true) {
        item.dispatchCandidate = true; snapshot.ready.push(item.key);
      }
      } catch (e) {snapshot.diagnostics.push({ticket: item.key, stage: 'assessment', error: String(e.message)});}
      snapshot.followUps.push({key: `${item.key}:source-assessment`, ticket: item.key,
        owner: 'current_operator', issue: snapshot.sourceSnapshots.find(s => s.source === item.source).authority,
        status: 'proposed', execution: 'not_dispatched', nextAction: 'Verify dependencies, admission and execution-host binding before dispatch'});
    }
    return {snapshot, environment};
  }
  async revalidate(a) {
    if (!this.runtime) return false;
    const binding = this.bindings.find(b => `github:${this.repository}#${b.number}` === a.ticket);
    if (!binding) return false;
    const current = await this.read(binding);
    if (JSON.stringify(current.sourceSnapshot) !== JSON.stringify(a.sourceSnapshot) || current.item.lifecycle !== 'open' || current.item.status !== 'status:in-progress') return false;
    return await this.runtime.authorize(a, current) === true;
  }
  async startSource(a) {
    if (!await this.revalidate(a)) throw Error('Source changed or execution host not authorized');
    const receipt = await this.runtime.compareAndStart(a);
    if (!receipt || receipt.key !== a.key || receipt.ticket !== a.ticket || receipt.sourceSha256 !== a.sourceSnapshot.sha256 || !nonempty(receipt.reference)) throw Error('Unverified source start; reconcile before retry');
    return receipt;
  }
  async ack(a, receipt) {
    if (!this.runtime || !nonempty(receipt?.workerId) || !nonempty(receipt.reference) || receipt.model !== a.model.id || receipt.target !== a.target || receipt.setupPending === true) throw Error('Actual matching worker receipt required');
    if (await this.runtime.ack(a, receipt) !== true) throw Error('Acknowledgement unknown; reconcile before retry');
  }
  async report(record) {
    if (!this.runtime) throw Error('Shared Diting host binding required');
    return await this.runtime.report(record);
  }
  async verifyTerminal(a, event, receipt) {
    return !!this.runtime && ['execution.finished', 'execution.failed'].includes(event?.type) && nonempty(event.reference) && await this.runtime.verifyTerminal(a, event, receipt) === true;
  }
}
