import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';
import {Production} from './runtime/src/production.mjs';
import {route} from './runtime/src/catalog.mjs';
import {execFileSync as runMemory} from 'node:child_process';
const [rootArg,cmd,id,...args]=process.argv.slice(2);
const root=path.resolve(rootArg||'.'), p=new Production(root);
const fail=m=>{throw Error(m);};
const json=f=>JSON.parse(fs.readFileSync(f,'utf8').replace(/^\uFEFF/,''));
const save=(f,v)=>{fs.writeFileSync(f+'.tmp',JSON.stringify(v,null,2)+'\n');fs.renameSync(f+'.tmp',f);};
if(id && !/^[A-Za-z0-9_-]+$/.test(id)) fail('feature ID 仅使用字母、数字、下划线或短横线');
const dir=path.join(root,'features',id||'_'), state=path.join(dir,'feature.json');
const groups={direction:['blueprint.md','research.md','direction.md'],planning:['planning.md'],design:['gameplay.md','technical.md','production.json']};
const digest=f=>crypto.createHash('sha256').update(fs.readFileSync(path.join(dir,f))).digest('hex');
function validate(s,gate){
  const order=['direction','planning','design'];
  for(const g of order.slice(0,order.indexOf(gate)+1)) {
    const a=s.approvals[g]; if(!a) fail(`${g} 尚未确认`);
    for(const f of groups[g]) if(a.hashes[f]!==digest(f)) fail(`${f} 已变化，需重新评审并建立修订`);
  }
}
const safe=x=>String(x??'—').replace(/\|/g,'\\|').replace(/[\r\n]/g,' ');
function refresh(){
  const s=json(state), ledger=p.read(), plan=ledger.plans.find(x=>x.id===s.plan);
  const tasks=plan?plan.tasks.map(id=>ledger.tasks.find(t=>t.id===id)):[];
  let valid='尚未定版';try{validate(s,'design');valid='审批文件与定版一致';}catch(e){valid=e.message;}
  const rows=tasks.map(t=>`| [${t.id}](../../.yuanheng/issues/${t.id}.md) | ${safe(t.title)} | ${t.status} | ${safe(t.owner)} | ${t.dependsOn.join(', ')} | ${safe(t.blocker)} | ${safe(t.notes.at(-1)?.next)} | ${safe(t.review?.verdict)} | ${t.artifacts.map(a=>`[证据](../../${a.path.split('/').map(encodeURIComponent).join('/')})`).join(' ')} |`).join('\n');
  const featureStatus=!tasks.length?'待设计定版':tasks.every(t=>t.status==='done')?'已完成':tasks.some(t=>t.status==='blocked')?'推进中（有阻碍）':tasks.some(t=>t.status==='running')?'推进中':'待推进';
  const ownership=plan?.ownership||s.ownership||{primaryOwner:'未指定',supportingOwners:[]};
  const summary=`Feature 工单：${id}；状态：${featureStatus}；主要负责人：${safe(ownership.primaryOwner)}；协作负责人：${ownership.supportingOwners.map(x=>safe(x.name)+'（'+safe(x.responsibility)+'）').join('、')||'无'}。`;
  const text=`# 偃师 · ${safe(s.title)}\n\n${summary}\n\nFeature：${id}；执行计划：${s.plan||'未创建'}；${valid}。\n\n[蓝本](blueprint.md) · [调研](research.md) · [方向](direction.md) · [策划](planning.md) · [玩法设计](gameplay.md) · [技术设计](technical.md) · [审批记录](feature.json)\n\n已验收 ${tasks.filter(t=>t.status==='done').length}/${tasks.length}。来源：元衡事件 #${ledger.events.length}；账本时间 ${ledger.events.at(-1)?.time}。刷新模式：命令触发或前台 watch。\n\n| 工单 | 内容 | 状态 | 负责人 | 依赖 | 阻塞 | 下一步 | 审核 | 证据 |\n|---|---|---|---|---|---|---|---|---|\n${rows}\n\n创建工单后由真实宿主派工；pending_host 不代表已经执行。所有工单验收且评价、复盘完成后才完成 feature。\n`;
  const contextualText=text+'\n[跨 feature 关联索引](../mapping.md) · 压缩记忆：本目录 memory.json（登记后生成，执行前核对来源）\n';
  const target=path.join(dir,'index.md');if(!fs.existsSync(target)||fs.readFileSync(target,'utf8')!==contextualText)fs.writeFileSync(target,contextualText);
  const ticket=path.join(dir,'ticket.md');if(!fs.existsSync(ticket)||fs.readFileSync(ticket,'utf8')!==contextualText)fs.writeFileSync(ticket,contextualText);
  if(fs.existsSync(path.join(root,'features'))){
    try{runMemory(process.execPath,[fileURLToPath(new URL('./feature-memory.mjs',import.meta.url)),root,'refresh'],{stdio:'pipe'});}catch(e){console.error('关联索引刷新失败，请重跑 feature-memory refresh：'+(e.stderr?.toString()||e.message));}
  }
}
try {
  if(cmd==='init'){p.init({project:'Yanshi features'});}
  else if(cmd==='new'){
    if(!id||!args[0])fail('new FEATURE-ID 标题');p.read();
    fs.mkdirSync(dir,{recursive:true});if(fs.existsSync(state))fail('feature 已存在');
    save(state,{id,title:args[0],approvals:{},plan:null});
    for(const f of Object.values(groups).flat()) if(f!=='production.json')fs.writeFileSync(path.join(dir,f),'');
    save(path.join(dir,'production.json'),{title:args[0],goal:'',changes:['gameplay'],tasks:[]});refresh();
  } else if(cmd==='team'){
    const s=json(state), ownership=json(args[0]);
    if(typeof ownership.primaryOwner!=='string'||!ownership.primaryOwner.trim()||!Array.isArray(ownership.supportingOwners))fail('需要主要负责人和 supportingOwners 数组');
    const names=new Set([ownership.primaryOwner]);
    for(const x of ownership.supportingOwners){if(!x.name||!x.responsibility||names.has(x.name))fail('协作负责人须唯一且有职责，不能重复主要负责人');names.add(x.name);}
    if(s.plan)p.mutate(ledger=>{const plan=ledger.plans.find(x=>x.id===s.plan);plan.ownership=ownership;p.event(ledger,'feature_ownership_updated',{feature:id,ownership});});
    s.ownership=ownership;save(state,s);refresh();
  } else if(cmd==='approve'){
    const [gate,receiptFile]=args, s=json(state);if(!groups[gate])fail('无效审批阶段');
    if(gate==='planning')validate(s,'direction');if(gate==='design')validate(s,'planning');
    if(s.approvals[gate])fail('审批已存在；内容变化需建立新的 feature 修订，保留历史');
    const receipt=json(receiptFile);for(const k of ['actor','quote','source','time'])if(!receipt[k])fail(`缺少实际确认记录 ${k}`);
    for(const f of groups[gate])if(!fs.readFileSync(path.join(dir,f),'utf8').trim())fail(`${f} 为空`);
    if(gate==='design')route(json(path.join(dir,'production.json')));
    s.approvals[gate]={receipt,hashes:Object.fromEntries(groups[gate].map(f=>[f,digest(f)]))};save(state,s);refresh();
  } else if(cmd==='tickets'){
    const s=json(state);validate(s,'design');
    const request=json(path.join(dir,'production.json'));route(request);
    if(!s.ownership?.primaryOwner)fail('先用 team 指定 feature 主要负责人及协作负责人');
    // One locked ledger transaction creates the plan and all feature tasks.
    const marker=`yanshi:${id}`;
    const existing=p.read().plans.find(x=>x.request.yanshiFeature===marker);
    if(existing){s.plan=existing.id;save(state,s);refresh();}
    else{
      const extras=request.tasks||[];
      if(!Array.isArray(extras))fail('tasks 必须为数组');
      const plan=p.mutate(ledger=>{
        const decisions=route(request), plan={id:`P-${ledger.plans.length+1}`,request:{...request,yanshiFeature:marker,approval:s.approvals.design},ownership:s.ownership,decisions,tasks:[]};
        let previous=[];const keyed=new Map();
        const add=input=>{const t=p.addTask(ledger,{...input,plan:plan.id,dependsOn:input.dependsOn??previous});plan.tasks.push(t.id);previous=[t.id];return t;};
        const anchor=`features/${id}/index.md; gameplay.md; technical.md`;
        for(const d of decisions.filter(d=>d.include&&!['evaluation','retrospective'].includes(d.id)))add({title:`${request.title} / ${d.name}`,goal:request.goal+'；设计基线 '+anchor,stage:d.id,acceptance:d.acceptance});
        const baseDependencies=[...previous];
        for(const t of extras){
          if(['evaluation','retrospective'].includes(t.stage))fail('专属拆分使用制作阶段，评价与复盘由流程保留');
          if(!t.key||keyed.has(t.key)||!Array.isArray(t.dependsOn))fail('专属任务需要唯一 key 和 dependsOn 数组；空数组表示可并发');
          const deps=t.dependsOn.map(k=>{if(!keyed.has(k))fail('依赖必须引用前面已定义的任务 key');return keyed.get(k);});
          const created=add({...t,dependsOn:[...new Set([...baseDependencies,...deps])]});keyed.set(t.key,created.id);
        }
        if(extras.length)previous=[...new Set([...baseDependencies,...keyed.values()])];
        for(const d of decisions.filter(d=>['evaluation','retrospective'].includes(d.id)))add({title:`${request.title} / ${d.name}`,goal:request.goal+'；设计基线 '+anchor,stage:d.id,acceptance:d.acceptance,independentReview:d.id==='evaluation'});
        ledger.plans.push(plan);p.event(ledger,'yanshi_feature_planned',{feature:id,plan:plan.id});return plan;
      });s.plan=plan.id;save(state,s);refresh();
    }
  } else if(cmd==='refresh')refresh();
  else if(cmd==='watch'){refresh();setInterval(()=>{try{refresh();}catch(e){console.error(e.message);}},3000);}
  else if(cmd==='work'){
    const s=json(state);validate(s,'design');if(!s.plan)fail('先创建工单');
    const operation=args[0], ledger=p.read(), plan=ledger.plans.find(x=>x.id===s.plan);
    if(operation==='bug'){const bug=json(args[1]);if(bug.plan&&bug.plan!==s.plan)fail('缺陷不属于当前 feature');p.bug({...bug,plan:s.plan});refresh();process.exit(0);}
    if(!['start','ack','record','submit','review','block','unblock','checkpoint','resume','search','status','report'].includes(operation))fail('不支持的 feature 操作');
    if(['init','plan','task'].includes(operation))fail('新工单通过 tickets 或修订创建');
    if(['start','ack','record','submit','review','block','unblock','resume'].includes(operation)&&!plan.tasks.includes(args[1]))fail('工单不属于当前 feature');
    try{process.stdout.write(execFileSync(process.execPath,[fileURLToPath(new URL('./runtime/cli.mjs',import.meta.url)),'--root',root,...args],{encoding:'utf8'}));}finally{refresh();}
  } else fail('用法：node yanshi.mjs ROOT init | new ID 标题 | approve ID direction/planning/design receipt.json | tickets ID | refresh ID | watch ID | work ID COMMAND ...');
}catch(e){console.error(e.message);process.exitCode=1;}
