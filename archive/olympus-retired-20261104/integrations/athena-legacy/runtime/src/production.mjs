import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { route, stages } from './catalog.mjs';

const now = () => new Date().toISOString();
const hash = b => crypto.createHash('sha256').update(b).digest('hex');
const ensure = (test, message) => { if (!test) throw Error(message); };
export class Production {
  constructor(root) { this.root = path.resolve(root); this.dir = path.join(this.root, '.zeus'); }
  git(...args) { return execFileSync('git', ['-C', this.root, ...args], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim(); }
  read() { return JSON.parse(fs.readFileSync(path.join(this.dir, 'state.json'), 'utf8')); }
  task(s, id) { const t = s.tasks.find(t => t.id === id); ensure(t, `工单不存在: ${id}`); return t; }
  init(config = {}) {
    ensure(!fs.existsSync(this.dir), '项目已初始化');
    ensure(path.resolve(this.git('rev-parse', '--show-toplevel')) === this.root, '请在目标 Git 仓库根目录初始化');
    const every = config.checkpointEvery ?? 8, minutes = config.checkpointMinutes ?? 30;
    ensure(Number.isInteger(every) && every > 0 && Number.isFinite(minutes) && minutes > 0, '检查点阈值必须为正数，事件阈值为整数');
    fs.mkdirSync(this.dir);
    const s = { version: 1, ledgerId: crypto.randomUUID(), config: { engine: 'unconfigured', ...config, checkpointEvery: every, checkpointMinutes: minutes },
      plans: [], tasks: [], agents: [], events: [], checkpoints: [], improvements: [] };
    this.event(s, 'initialized', { config: s.config }); this.persist(s); return s;
  }
  event(s, type, data) { s.events.push({ seq: s.events.length + 1, time: now(), type, data }); }
  persist(s) {
    const file = path.join(this.dir, 'state.json');
    fs.writeFileSync(`${file}.tmp`, JSON.stringify(s, null, 2) + '\n'); fs.renameSync(`${file}.tmp`, file);
    fs.mkdirSync(path.join(this.dir, 'issues'), { recursive: true });
    fs.writeFileSync(path.join(this.dir, 'issues', '.gitkeep'), '');
    for (const t of s.tasks) fs.writeFileSync(path.join(this.dir, 'issues', `${t.id}.md`),
      `# ${t.id} ${t.title}\n\n状态：${t.status}\n\n` + '```json\n' + JSON.stringify(t, null, 2) + '\n```\n');
    // Commit only our ledger. Never sweep the user's staged changes into a commit.
    this.git('add', '--', '.zeus/state.json', '.zeus/issues');
    this.git('-c', 'user.name=Zeus', '-c', 'user.email=zeus@local.invalid', 'commit', '--only', '-m',
      `zeus: ${s.events.at(-1).type} #${s.events.length}`, '--', '.zeus/state.json', '.zeus/issues');
  }
  mutate(fn) {
    const lock = path.join(this.dir, 'writer.lock');
    let fd;
    try { fd = fs.openSync(lock, 'wx'); } catch { throw Error('账本有其他写入者或遗留锁；检查后再重试'); }
    try {
      ensure(!this.git('status', '--porcelain', '--', '.zeus/state.json', '.zeus/issues'), '账本存在未提交修改；先检查并恢复 Git 记录');
      const s = this.read(), result = fn(s);
      const last = s.checkpoints.at(-1);
      if (s.events.length - (last?.cursor || 0) >= s.config.checkpointEvery ||
        Date.now() - Date.parse(last?.time || s.events[0].time) >= s.config.checkpointMinutes * 60000)
        this.makeCheckpoint(s, '自动周期检查点；语义判断仍需宿主补充');
      this.persist(s); return result ?? s;
    } finally { fs.closeSync(fd); fs.unlinkSync(lock); }
  }
  addTask(s, input) {
    ensure(input.title && input.goal && Array.isArray(input.acceptance) && input.acceptance.length, '工单必须有标题、目标和验收标准');
    ensure(stages.some(x => x.id === input.stage), '无效阶段');
    for (const id of input.dependsOn || []) this.task(s, id);
    const t = { id: `YH-${String(s.tasks.length + 1).padStart(4, '0')}`, title: input.title, goal: input.goal,
      stage: input.stage, plan: input.plan || null, dependsOn: input.dependsOn || [], acceptance: input.acceptance,
      independentReview: !!input.independentReview, status: 'open', owner: null, artifacts: [], review: null, notes: [], created: now() };
    s.tasks.push(t); this.event(s, 'task_created', { task: t.id, reason: input.reason || '需求分解' }); return t;
  }
  plan(request) { return this.mutate(s => {
    const decisions = route(request), p = { id: `P-${s.plans.length + 1}`, request, decisions, tasks: [] };
    let previous = [];
    for (const d of decisions.filter(x => x.include)) {
      const t = this.addTask(s, { title: `${request.title} / ${d.name}`, goal: request.goal, stage: d.id,
        plan: p.id, dependsOn: previous, acceptance: d.acceptance, independentReview: d.id === 'evaluation' });
      p.tasks.push(t.id); previous = [t.id];
    }
    s.plans.push(p); this.event(s, 'plan_routed', { plan: p.id, decisions }); return p;
  }); }
  create(input) { return this.mutate(s => {
    const p = input.plan && s.plans.find(p => p.id === input.plan);
    ensure(!input.plan || p, '计划不存在');
    ensure(!p || !p.tasks.some(id => this.task(s,id).stage === 'retrospective' && this.task(s,id).status === 'done'), '已复盘计划不可追加；新建变更计划');
    const t = this.addTask(s, input);
    if (p) {
      // New production work must join the remaining acceptance gate.
      const gate = p.tasks.map(id => this.task(s,id)).find(x => x.stage === 'evaluation' && x.status !== 'done');
      ensure(gate && !t.dependsOn.includes(gate.id), '动态任务不能依赖评价；评价已通过时新建变更计划');
      const reaches = (id, target) => id === target || this.task(s,id).dependsOn.some(dep => reaches(dep, target));
      ensure(!t.dependsOn.some(id => reaches(id, gate.id)), '动态任务造成依赖环');
      gate.dependsOn.push(t.id); p.tasks.push(t.id);
      if (['running','review'].includes(gate.status)) {
        gate.status = 'blocked'; gate.blocker = `等待新增任务 ${t.id} 验收`;
        this.event(s,'evaluation_blocked',{task:gate.id,dependency:t.id});
      }
    }
    return t;
  }); }
  start(id, mandate) { return this.mutate(s => {
    const t = this.task(s,id); ensure(t.status === 'open', '只能启动 open 工单');
    ensure(t.dependsOn.every(d => this.task(s,d).status === 'done'), '前置工单尚未通过验收');
    ensure(mandate.owner && mandate.capability && mandate.authority && mandate.nextAction, '需要 owner、capability、authority、nextAction');
    const agent = { id: `A-${s.agents.length + 1}`, task: id, owner: mandate.owner, capability: mandate.capability,
      authority: mandate.authority, nextAction: mandate.nextAction, goal: t.goal, acceptance: t.acceptance,
      inputs: t.dependsOn.map(d => ({ task: d, artifacts: this.task(s,d).artifacts })),
      handoff: 'Attach evidence; request review; checkpoint before context reset.', lifecycle: 'delegated',
      execution: 'pending_host', created: now() };
    s.agents.push(agent); t.owner = mandate.owner; t.agent = agent.id; t.status = 'running';
    this.event(s, 'agent_delegated', agent); return agent;
  }); }
  record(id, note) { return this.mutate(s => {
    const t = this.task(s,id); ensure(['running','review','blocked'].includes(t.status), '只有活动工单可以记录过程');
    ensure(note.action && note.result && note.next, '过程记录需要 action、result、next；未知结果写 unknown');
    t.notes.push({ ...note, time: now() }); this.event(s, 'work_recorded', { task: id, ...note });
  }); }
  acknowledge(id, receipt) { return this.mutate(s => {
    const t = this.task(s,id), a = s.agents.find(a => a.id === t.agent);
    ensure(t.status === 'running' && a && receipt.host && receipt.runId, '需要运行中的任务以及真实宿主 host 和 runId');
    a.execution = 'host_acknowledged'; a.receipt = receipt;
    this.event(s,'host_acknowledged',{task:id,...receipt});
  }); }
  artifact(file) {
    ensure(typeof file === 'string' && !path.isAbsolute(file), '产物必须是项目内相对路径');
    const target = fs.realpathSync(path.resolve(this.root, file));
    const relative = path.relative(this.root, target);
    ensure(relative && !relative.startsWith('..') && !path.isAbsolute(relative) && !relative.split(path.sep).some(p => ['.git','.zeus'].includes(p)), '产物路径越界或指向账本');
    ensure(fs.statSync(target).isFile(), '产物必须是文件');
    return { path: relative.split(path.sep).join('/'), sha256: hash(fs.readFileSync(target)) };
  }
  submit(id, files) { return this.mutate(s => {
    const t = this.task(s,id); ensure(t.status === 'running', '只能提交运行中的工单');
    ensure(Array.isArray(files) && files.length, '必须提交实际证据文件');
    t.artifacts = files.map(f => this.artifact(f)); t.status = 'review';
    this.event(s, 'submitted', { task: id, artifacts: t.artifacts });
  }); }
  review(id, r) { return this.mutate(s => {
    const t = this.task(s,id); ensure(t.status === 'review', '工单未提交审核');
    ensure(r.reviewer && ['pass','fail'].includes(r.verdict) && r.reason, '审核需要 reviewer、verdict(pass/fail)、reason');
    ensure(!t.independentReview || r.reviewer !== t.owner, '此工单需要独立审核者');
    if (r.verdict === 'pass') {
      ensure(t.dependsOn.every(d => this.task(s,d).status === 'done'), '前置工单尚未通过验收');
      ensure(t.artifacts.every(a => this.artifact(a.path).sha256 === a.sha256), '证据已发生变化，请退回后重新提交');
      ensure(Array.isArray(r.criteria) && r.criteria.length === t.acceptance.length && r.criteria.every(x => x.met === true && t.artifacts.some(a => a.path === x.evidence)), '必须逐项引用已提交文件作为验收证据');
    }
    t.review = { ...r, time: now() }; t.status = r.verdict === 'pass' ? 'done' : 'running';
    if (t.status === 'done') s.agents.find(a => a.id === t.agent).lifecycle = 'retired';
    this.event(s, 'reviewed', { task: id, review: t.review });
  }); }
  block(id, reason) { return this.mutate(s => {
    const t = this.task(s,id); ensure(['running','review'].includes(t.status) && reason, '只能阻塞活动工单，必须说明原因');
    t.status = 'blocked'; t.blocker = reason; this.event(s, 'blocked', { task:id, reason });
  }); }
  unblock(id, reason) { return this.mutate(s => {
    const t = this.task(s,id); ensure(t.status === 'blocked' && reason, '需要解除阻塞的依据');
    ensure(t.dependsOn.every(d => this.task(s,d).status === 'done'), '阻塞依赖尚未完成');
    t.status = 'running'; delete t.blocker; this.event(s, 'unblocked', { task:id, reason });
  }); }
  makeCheckpoint(s, summary) {
    const checkpoint = { id: `CP-${s.checkpoints.length + 1}`, time: now(), cursor: s.events.length,
      summary, active: s.tasks.filter(t => t.status !== 'done').map(t => ({ id:t.id, goal:t.goal, status:t.status,
        owner:t.owner, dependencies:t.dependsOn, blocker:t.blocker || null, latest:t.notes.at(-1) || null })),
      evidence: s.tasks.filter(t => t.artifacts.length).map(t => ({ task:t.id, artifacts:t.artifacts })),
      constraints: 'Preserve upstream core, delegated authority and original evidence. Unknown stays unknown.' };
    s.checkpoints.push(checkpoint); this.event(s, 'checkpoint', { id:checkpoint.id, cursor:checkpoint.cursor }); return checkpoint;
  }
  checkpoint(summary) { ensure(summary, '需要摘要'); return this.mutate(s => this.makeCheckpoint(s, summary)); }
  resume(id) {
    const s = this.read(), t = this.task(s,id), last = s.checkpoints.at(-1);
    const compact = task => ({...task, notes:task.notes.slice(-3)});
    return { core: fs.readFileSync(new URL('../../../../upstream/zeus/core.md', import.meta.url), 'utf8'),
      template: fs.readFileSync(new URL('../../../../upstream/zeus/agents/zeus.md', import.meta.url), 'utf8'),
      config:s.config, task:compact(t), agent:s.agents.find(a => a.id === t.agent) || null,
      checkpoint:last ? {...last,active:last.active.filter(x => [id,...t.dependsOn].includes(x.id)),evidence:last.evidence.filter(x => [id,...t.dependsOn].includes(x.task))} : null,
      delta:s.events.filter(e => e.seq > (last?.cursor || 0) && (e.data.task === id || e.type === 'checkpoint')),
      inputs:t.dependsOn.map(d => compact(this.task(s,d))), instructions:'Read linked evidence before acting. Full history stays in .zeus/state.json. Write a checkpoint before context reset. Do not claim pending_host delegation executed.' };
  }
  bug(input) {
    ensure(input.repro && input.expected && input.actual && ['critical','high','medium','low'].includes(input.severity), 'Bug需要复现步骤、期望、实际及severity');
    return this.create({ ...input, stage:'integration', goal:JSON.stringify({ repro:input.repro, expected:input.expected, actual:input.actual, severity:input.severity }),
      acceptance:['修复前复现证据','修复后同场景回归证据与影响范围'], independentReview:true });
  }
  search(query) { ensure(query, '需要查询词'); return this.read().tasks.filter(t => JSON.stringify(t).toLowerCase().includes(query.toLowerCase())); }
  improve(input) { return this.mutate(s => {
    const t = this.task(s,input.task); ensure(t.stage === 'retrospective' && t.status === 'running', '改进须关联运行中的复盘工单');
    ensure(input.hypothesis && input.scope && input.metric && input.rollback && input.evidence?.length, '改进需要假设、范围、指标、回滚条件与证据');
    const item = { ...input, id:`IMP-${s.improvements.length+1}`, evidence:input.evidence.map(f => this.artifact(f)), status:'proposed' };
    s.improvements.push(item); this.event(s,'improvement_proposed',item); return item;
  }); }
  decideImprovement(id, decision) { return this.mutate(s => {
    const item = s.improvements.find(i => i.id === id); ensure(item, '改进不存在');
    ensure(['trial','adopted','reverted'].includes(decision.status) && decision.reason && decision.actor, '需要改进状态、依据与负责人');
    const transitions = { proposed:['trial','reverted'], trial:['adopted','reverted'], adopted:['reverted'], reverted:[] };
    ensure(transitions[item.status].includes(decision.status), '无效改进状态迁移');
    ensure(decision.status !== 'adopted' || decision.evidence?.length, '采纳需要试验结果文件');
    const evidence = (decision.evidence || []).map(f => this.artifact(f));
    item.status = decision.status; item.decisions ||= []; item.decisions.push({ ...decision, evidence, time:now() });
    this.event(s,'improvement_decided',{id,...decision,evidence});
  }); }
  report() {
    const s=this.read(); return '# 宙斯生产复盘\n\n' +
      `已验收 ${s.tasks.filter(t=>t.status==='done').length}/${s.tasks.length}；事件 ${s.events.length}；检查点 ${s.checkpoints.length}。\n\n` +
      '## 流程裁剪\n\n' + s.plans.map(p=>`### ${p.id} ${p.request.title}\n\n`+p.decisions.map(d=>`- ${d.name}：${d.include?'执行':'跳过'}；${d.reason}`).join('\n')).join('\n\n') +
      '\n\n## 工单与证据\n\n' + s.tasks.map(t=>`- ${t.id} ${t.title}：${t.status}；负责人 ${t.owner||'未分配'}；证据 ${t.artifacts.map(a=>a.path+' @ '+a.sha256).join(', ')||'尚无'}；结论 ${t.review?.reason||'待验收'}${t.blocker?'；阻塞 '+t.blocker:''}`).join('\n')+
      '\n\n## 改进实验\n\n'+JSON.stringify(s.improvements,null,2)+'\n\n未完成和未知事项不视为通过。实际引擎运行及模型调用由宿主提供。\n';
  }
}
