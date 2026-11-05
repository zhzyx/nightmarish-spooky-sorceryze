import assert from 'node:assert/strict';
import http from 'node:http';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';
import { dispatchGraph } from '../../customizations/components/godot-host/daqian/execution.mjs';

const worker = fileURLToPath(new URL('../../customizations/components/godot-host/daqian/worker.py',import.meta.url));
const python = process.env.GONGGONG_PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const image = {kind:'image',mime:'image/png',data:'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+kcy8AAAAASUVORK5CYII='};
const protocols = ['anthropic-messages','gemini-generate-content','responses','chat-completions'];
const activity = new Map();
let pending = 0;
let peak = 0;
const server = http.createServer(async (req,res) => {
  try {
    let input = '';
    for await (const chunk of req) input += chunk;
    const raw = JSON.parse(input);
    const protocol = req.url.split('/')[1];
    const start = performance.now();
    let encoded;
    let output;
    if (protocol === 'anthropic-messages') {
      assert.equal(req.headers['x-api-key'],'daqian-fixture');
      encoded = raw.messages[0].content[0].source.data;
      output = {id:'a',model:raw.model,stop_reason:'end_turn',content:[{type:'text',text:protocol}]};
    } else if (protocol === 'gemini-generate-content') {
      assert.equal(req.headers['x-goog-api-key'],'daqian-fixture');
      assert.equal(req.url.split('/')[2],'fixture');
      encoded = raw.contents[0].parts[0].inlineData.data;
      output = {responseId:'g',modelVersion:'fixture',candidates:[{finishReason:'STOP',content:{parts:[{text:protocol}]}}]};
    } else if (protocol === 'responses') {
      encoded = raw.input[0].content[0].image_url.split(',')[1];
      output = {id:'r',model:raw.model,status:'completed',output:[{type:'message',content:[{type:'output_text',text:protocol}]}]};
    } else {
      encoded = raw.messages[0].content[0].image_url.url.split(',')[1];
      output = {id:'c',model:raw.model,choices:[{finish_reason:'stop',message:{content:protocol}}]};
    }
    assert.equal(encoded,image.data);
    if (protocol==='responses' || protocol==='chat-completions') assert.equal(req.headers.authorization,'Bearer daqian-fixture');
    peak = Math.max(peak, ++pending);
    await delay(240);
    pending--;
    activity.set(protocol, {start,end:performance.now()});
    res.writeHead(200,{'content-type':'application/json'}).end(JSON.stringify(output));
  } catch (error) {
    res.writeHead(400).end('Invalid fixture transport');
    process.stderr.write(String(error));
  }
});
await new Promise((resolve,reject)=>server.once('error',reject).listen(0,'127.0.0.1',resolve));
const endpoint = 'http://127.0.0.1:' + server.address().port;
const running = new Map();
function launch(protocol) {
  const proc = spawn(python,[worker,'--fixture'],{stdio:['pipe','pipe','pipe']});
  const result = new Promise((resolve,reject)=>{
    let buffer='';
    proc.once('error',reject);
    proc.stdout.on('data',chunk=>buffer+=chunk);
    proc.once('close',(code,signal)=>{
      if (code!==0) return reject(new Error('fixture worker stopped: '+(signal||code)));
      try { resolve(JSON.parse(buffer)); } catch (error) { reject(error); }
    });
  });
  proc.stdin.end(JSON.stringify({text:'inspect input fixture',images:[image],profile:{model:'fixture',protocol,
    endpoint:endpoint+'/'+protocol+(protocol==='gemini-generate-content'?'/{model}':'')}}));
  running.set(protocol,proc);
  return {proc,result};
}

const graph = {nodes:{picture:{kind:'image'},a:{kind:'task',model:protocols[0]},b:{kind:'task',model:protocols[1]},merge:{kind:'join'}},
  edges:[{from:'picture',to:'a',kind:'data'},{from:'picture',to:'b',kind:'data'},{from:'a',to:'merge',kind:'data'},{from:'b',to:'merge',kind:'data'}]};
const outputs = new Map([['picture',image]]);
const ready = ['a','b'];
const receipts = [];
const tasks = new Map();
const catalog = protocols.map((id,preference)=>({id,available:true,targets:['agent'],capabilities:['text','image'],preference}));
const host = {
  isAccepted:(_issue,id)=>outputs.has(id),
  readOutput:(_issue,id)=>outputs.get(id),
  requiredCapabilities:()=>[],
  scoredCatalog:()=>catalog,
  assignment:(_issue,id)=>({ticket:id,owner:'fixture-agent-'+id,outcome:'inspect fixture image',acceptance:'validated transport receipt',
    authorityRef:'synthetic-loopback-only',contextRefs:['fixture-picture'],reads:[],writes:[]}),
  needsAttention:()=>assert.fail('unexpected missing fixture capability'),
  join:(_issue,id,inputs)=>outputs.set(id,inputs),
  sinanPorts:()=>({
    withLock:fn=>fn(),inspect:()=>({snapshot:{ready,items:ready.map(key=>({key,source:'fixture',dispatchCandidate:true})),sourceSnapshots:[{source:'fixture',revision:'one'}]},
      environment:{capacity:2,active:[],catalog}}),
    revalidate:()=>true,reserve:()=>true,startSource:a=>({reference:'fixture-source-'+a.ticket}),
    launch:a=>{
      const {proc,result} = launch(a.model.id);
      tasks.set(a.ticket,result.then(value=>outputs.set(a.ticket,{kind:'result',value:value.text})));
      return {workerId:String(proc.pid),reference:'fixture-process-'+proc.pid,target:'agent',model:a.model.id};
    },
    ack:(_a,receipt)=>receipts.push(receipt),record:()=>{}
  })
};
try {
  await dispatchGraph({type:'user.requested',reference:'fixture-start'},'test#1',graph,host);
  await Promise.all(tasks.values());
  assert.equal(new Set(receipts.map(r=>r.workerId)).size,2);
  assert.ok(peak>=2,'actual fixture HTTP request intervals must overlap');
  ready.length = 0;
  await dispatchGraph({type:'execution.finished',reference:'fixture-done'},'test#1',graph,host);
  assert.deepEqual(outputs.get('merge').map(x=>x.value),protocols.slice(0,2));
  for (const protocol of protocols.slice(2)) assert.equal((await launch(protocol).result).text,protocol);
  const first=launch(protocols[0]), second=launch(protocols[2]);
  const cancelled=assert.rejects(first.result);
  first.proc.kill();
  await cancelled;
  assert.equal((await second.result).text,protocols[2]);
  console.log(JSON.stringify({state:'passed',scope:'synthetic_loopback',protocols,distinctWorkers:2,peakRequests:peak,
    joined:outputs.get('merge'),cancelIsolated:true,liveProviderCalls:0}));
} finally {
  server.closeAllConnections();
  await new Promise(resolve=>server.close(resolve));
}
