// The host supplies fresh source snapshots, admission checks, reservation, and real receipts.
// This adapter contributes graph dependencies and per-task evidence ranking to the existing Sinan dispatcher.
import { dispatchEvent, selectModel } from '../../../../customizations/platforms/process-management/yuanheng-local/sinan/dispatch.mjs';

export async function dispatchGraph(event, issue, graph, host) {
  const requests = [];
  const results = new Map();
  for (const [id, node] of Object.entries(graph.nodes)) {
    if (!['task', 'join'].includes(node.kind) || host.isAccepted(issue,id) || (host.isEligible && !host.isEligible(issue,id))) continue;
    const incoming = graph.edges.filter(e => e.to === id);
    if (incoming.some(e => !host.isAccepted(issue, e.from))) continue;
    const inputs = [];
    for (const e of incoming.filter(e => e.kind === 'data')) {
      inputs.push(await host.readOutput(issue, e.from));
    }
    if (node.kind === 'join') {
      if (!inputs.length) {
        await host.needsAttention(issue, id, '待取得上游结果或独立验收证据');
        continue;
      }
      // This is a data join. The host still validates the issue revision and its required inputs.
      await host.join(issue, id, inputs, event.reference);
      continue;
    }
    const capabilities = [...new Set(['text', ...host.requiredCapabilities(issue,id),
      ...inputs.filter(input => input.kind === 'image').map(() => 'image')])];
    const catalog = await host.scoredCatalog(issue, id, capabilities);
    const chosen = selectModel(capabilities, catalog, 'agent', node.model || undefined);
    if (!chosen) {
      await host.needsAttention(issue, id, '没有满足能力、评分证据和当前授权的模型');
      continue;
    }
    const binding = await host.assignment(issue, id, event);
    const request = {...binding, model: chosen.id, capabilities, target:'agent'};
    requests.push(request);
    results.set(request.ticket, {issue, id, inputs, model:chosen.id});
  }
  if (!requests.length) return {results:[], deferred:[]};
  // Factory owns all authoritative ports; the editor cannot approve its own launches.
  return dispatchEvent(event, requests, await host.sinanPorts(results));
}
