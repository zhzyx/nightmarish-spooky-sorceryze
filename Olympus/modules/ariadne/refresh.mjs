import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {board} from './coordinator.mjs';

const types = new Set(['request.created','ticket.changed','dependency.changed','decision.recorded','execution.finished','execution.failed','user.requested']);
const escape = value => String(value ?? '—').replace(/[\r\n]+/g, ' ').replace(/\|/g, '\\|').replace(/</g, '&lt;').replace(/>/g, '&gt;');
export function refresh(registryFile, type, reference) {
  if (!types.has(type)) throw Error('Only actual task events are supported; time-based triggers are prohibited');
  if (typeof reference !== 'string' || !reference.trim()) throw Error('Actual event source reference is required');
  const file = path.resolve(registryFile), base = path.dirname(file);
  const lock = path.join(base, 'progress.lock'), output = path.join(base, 'progress.md');
  const fd = fs.openSync(lock, 'wx'), temporary = output + '.tmp-' + process.pid;
  try {
    const config = JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));
    const snapshot = board(config, base);
    const lines = ['# 阿里阿德涅工单进度', '', `触发：${escape(type)}；来源：${escape(reference)}`, '',
      `覆盖：已登记来源 ${snapshot.sourcesRegistered} 个，成功读取 ${snapshot.sourcesRead} 个。未登记来源未知。`, '',
      '| 工单 | 标题 | 源状态 | 标签 | 责任人 | 阻塞或待处理 | 验收证据有效 |',
      '| --- | --- | --- | --- | --- | --- | --- |'];
    for (const t of snapshot.items) lines.push('| ' + [t.key,t.title,t.status,t.labels.join(', '),t.owner,[...t.problems,t.blocker ? JSON.stringify(t.blocker) : ''].filter(Boolean).join('; '),t.acceptanceValid ? '是' : '未通过或未验收'].map(escape).join(' | ') + ' |');
    if (!snapshot.items.length) lines.push('', '本次未读取到工单；不代表所有项目均无任务。');
    lines.push('', '就绪候选（实际派发前仍需宿主核验权限、容量、依赖及回执）：', ...snapshot.ready.map(k => '- ' + escape(k)));
    if (!snapshot.ready.length) lines.push('无；本次处理结束，不安排时间唤醒。');
    lines.push('', '来源版本：', ...snapshot.sourceSnapshots.map(s => `- ${escape(s.source)}：${escape(s.ledgerId)}，事件游标 ${s.eventCursor}，SHA256 ${s.sha256}`));
    if (snapshot.diagnostics.length) lines.push('', '读取缺口：', ...snapshot.diagnostics.map(d => '- ' + escape(JSON.stringify(d))));
    lines.push('', '此文档是来源视图，不改变源状态，不代表实际派发或赫尔墨斯落库成功。', '');
    fs.writeFileSync(temporary, lines.join('\n'));
    fs.renameSync(temporary, output);
    return {updated:true, document:path.basename(output), ready:snapshot.ready, sourcesRead:snapshot.sourcesRead,
      diagnostics:snapshot.diagnostics, execution:'not_dispatched', reporting:'host_binding_and_receipt_required'};
  } finally {
    if (fs.existsSync(temporary)) fs.unlinkSync(temporary);
    fs.closeSync(fd);fs.unlinkSync(lock);
  }
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const [type, reference, registry, ...extra] = process.argv.slice(2);
    if (extra.length) throw Error('Usage: refresh.mjs EVENT-TYPE SOURCE-REFERENCE [REGISTRY]');
    console.log(JSON.stringify(refresh(registry || fileURLToPath(new URL('./runtime/registry.json', import.meta.url)), type, reference), null, 2));
  } catch (error) { console.error(error.message);process.exitCode = 1; }
}
