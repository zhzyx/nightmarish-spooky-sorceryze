#!/usr/bin/env node
import fs from 'node:fs';
import { Production } from './src/production.mjs';
const args=process.argv.slice(2);
const rootIndex=args.indexOf('--root');
const root=rootIndex<0?process.cwd():args.splice(rootIndex,2)[1];
const [command, first, second]=args;
const p=new Production(root);
const json=file=>JSON.parse(fs.readFileSync(file,'utf8').replace(/^\uFEFF/,''));
const help=`宙斯 Godot 生产基础框架
node cli.mjs [--root Git仓库根目录] COMMAND ...
init [config.json]             初始化 Git 工单账本
plan request.json             需求裁剪与工单分解
task task.json                生产中追加任务
start YH-ID mandate.json      按需生成宿主委托
ack YH-ID receipt.json        记录宿主执行回执
record YH-ID note.json        记录 action/result/next
submit YH-ID files.json       提交项目内证据路径数组
review YH-ID review.json      验收或退回
block/unblock YH-ID reason    阻塞/解除
checkpoint summary           保存上下文检查点
resume YH-ID                 输出新上下文恢复包
bug bug.json                 生成缺陷工单
search keyword               本地工单及缺陷检索
improve proposal.json         提出有证据的改进
decide IMP-ID decision.json   试验/采纳/回滚改进
report                       输出复盘 Markdown
status                       输出当前状态
远程发布通过项目实际授权的连接器接入；模型执行由宿主提供。`;
try {
  let result;
  switch(command) {
    case 'init':result=p.init(first?json(first):{engine:'Godot 4',project:'game'});break;
    case 'plan':result=p.plan(json(first));break;
    case 'task':result=p.create(json(first));break;
    case 'start':result=p.start(first,json(second));break;
    case 'ack':result=p.acknowledge(first,json(second));break;
    case 'record':result=p.record(first,json(second));break;
    case 'submit':result=p.submit(first,json(second));break;
    case 'review':result=p.review(first,json(second));break;
    case 'block':result=p.block(first,second);break;
    case 'unblock':result=p.unblock(first,second);break;
    case 'checkpoint':result=p.checkpoint(first);break;
    case 'resume':result=p.resume(first);break;
    case 'bug':result=p.bug(json(first));break;
    case 'search':result=p.search(first);break;
    case 'improve':result=p.improve(json(first));break;
    case 'decide':result=p.decideImprovement(first,json(second));break;
    case 'report':result=p.report();break;
    case 'status':{const s=p.read();result={config:s.config,tasks:s.tasks,events:s.events.length,checkpoint:s.checkpoints.at(-1)};break;}
    case undefined:case 'help':case '--help':result=help;break;
    default:throw Error(`未知命令 ${command}\n${help}`);
  }
  console.log(typeof result==='string'?result:JSON.stringify(result,null,2));
} catch(e) { console.error(e.message); process.exitCode=1; }
