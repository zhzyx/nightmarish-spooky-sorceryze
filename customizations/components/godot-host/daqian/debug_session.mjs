// Explicit loopback-only fixture. It never writes back to GitHub or grants production execution.
import http from 'node:http';
import readline from 'node:readline';
import fs from 'node:fs';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {setTimeout as delay} from 'node:timers/promises';
import {dispatchGraph} from './execution.mjs';

const emit = event => process.stdout.write(JSON.stringify(event)+'\n');
const protocols = {'调试 · Claude':'anthropic-messages','调试 · Gemini':'gemini-generate-content','调试 · GPT':'responses','调试 · DeepSeek':'chat-completions'};
const worker = fileURLToPath(new URL('./worker.py',import.meta.url));
let graph, python, server, closed=false, revision=0, queue=Promise.resolve();
const nodes = new Map();
const active = new Map();
const history = new Map();
const data = new Map();
const accepted = id => nodes.get(id)==='completed';
const eligible = id => !nodes.has(id);
function state(id, value, fields={}) {
  nodes.set(id,value);
  emit({scope:'synthetic_loopback',id,state:value,at:Date.now(),...fields});
}
function fixtureEndpoint() {
  return http.createServer(async (req,res)=>{
    try {
      let count=0; const buffers=[];
      for await (const chunk of req) {
        count+=chunk.length;
        if (count>20*1024*1024) throw Error('fixture payload too large');
        buffers.push(chunk);
      }
      const input = JSON.parse(Buffer.concat(buffers).toString('utf8'));
      const mode=req.url.split('/')[1];
      let parts;
      if (mode==='anthropic-messages' || mode==='chat-completions') parts=input.messages[0].content;
      else if (mode==='gemini-generate-content') parts=input.contents[0].parts;
      else if (mode==='responses') parts=input.input[0].content;
      else throw Error('unknown fixture protocol');
      const images=(Array.isArray(parts)?parts:[]).filter(p=>p.type==='image'||p.type==='input_image'||p.type==='image_url'||p.inlineData);
      const dims=images.map(p=>{
        const encoded=p.source?.data ?? p.inlineData?.data ?? (p.image_url?.url??p.image_url??'').split(',')[1];
        const bytes=Buffer.from(encoded,'base64');
        if (bytes.length<24 || !bytes.subarray(0,8).equals(Buffer.from('89504e470d0a1a0a','hex'))) throw Error('fixture requires PNG input');
        return bytes.readUInt32BE(16)+'×'+bytes.readUInt32BE(20);
      });
      const text='协议调试完成 · '+mode+(dims.length?' · PNG '+dims.join(', '):'');
      const output=mode==='responses'?{status:'completed',output:[{type:'message',content:[{type:'output_text',text}]}]}:
        mode==='chat-completions'?{choices:[{finish_reason:'stop',message:{content:text}}]}:
        mode==='anthropic-messages'?{stop_reason:'end_turn',content:[{type:'text',text}]}:
        {candidates:[{finishReason:'STOP',content:{parts:[{text}]}}]};
      await delay(400);
      res.writeHead(200,{'Content-Type':'application/json'}).end(JSON.stringify(output));
    } catch { res.writeHead(400).end('Invalid fixture payload'); }
  });
}
const catalog=Object.keys(protocols).map((id,preference)=>({id,preference,available:true,capabilities:['text','image'],targets:['agent']}));
function wake(reason) {
  queue=queue.then(async()=>{
    if (closed || !graph) return;
    const event={type:reason,reference:'fixture-event-'+ ++revision};
    const host={
      isAccepted:(_issue,id)=>accepted(id),isEligible:(_issue,id)=>eligible(id),
      readOutput:(_issue,id)=>data.get(id),requiredCapabilities:()=>[],
      scoredCatalog:()=>catalog,assignment:(_issue,id)=>({ticket:id,owner:'调试 Agent '+id,outcome:graph.nodes[id].title,
        acceptance:'receive fixture result',authorityRef:'synthetic_loopback',contextRefs:[id],reads:[],writes:[]}),
      join:(_issue,id,inputs)=>{data.set(id,{kind:'result',value:inputs.map(x=>x.value).join('\n')});state(id,'completed',{result:data.get(id).value});},
      needsAttention:(_issue,id,why)=>state(id,'waiting',{reason:why}),
      sinanPorts:entries=>({
        withLock:fn=>fn(),inspect:()=>({snapshot:{ready:[...entries.keys()],items:[...entries.keys()].map(key=>({key,source:'local-fixture',dispatchCandidate:true})),
          sourceSnapshots:[{source:'local-fixture',revision}]}, environment:{catalog,capacity:2,active:[...active.keys()].map(ticket=>({ticket,reads:[],writes:[]}))}}),
        revalidate:a=>eligible(a.ticket), reserve:a=>{state(a.ticket,'reserved');return true;},
        startSource:a=>({reference:'fixture-source-'+a.key}),
        launch:a=>{
          const id=a.ticket, model=a.model.id;
          const proc=spawn(python,[worker,'--fixture'],{stdio:['pipe','pipe','pipe']});
          active.set(id,proc);
          const run=(history.get(id)??0)+1;
          history.set(id,run);
          let stdout='';
          proc.stdout.on('data',buf=>stdout+=buf);
          proc.on('error',()=>state(id,'failed',{run,reason:'无法启动 Python'}));
          proc.once('close',code=>{
            active.delete(id);
            if (closed) return;
            if (nodes.get(id)==='stopping') {
              state(id,'cancelled',{run,model});
            } else {
              let parsed;
              try { parsed=JSON.parse(stdout); } catch { parsed={}; }
              if (code===0 && parsed.text) {
                data.set(id,{kind:'result',value:parsed.text});
                state(id,'completed',{run,model,result:parsed.text});
              } else state(id,'failed',{run,model,reason:parsed.error??'调试进程异常结束'});
            }
            wake('execution.finished');
          });
          const ctx=entries.get(id);
          const images=ctx.inputs.filter(x=>x.kind==='image').map(x=>({mime:'image/png',data:x.value}));
          const text=[graph.nodes[id].value,...ctx.inputs.filter(x=>x.kind!=='image').map(x=>x.value)].filter(Boolean).join('\n');
          const protocol=protocols[model];
          proc.stdin.on('error',()=>{});
          proc.stdin.end(JSON.stringify({text,images,profile:{model,protocol,endpoint:'http://127.0.0.1:'+server.address().port+'/'+protocol+
            (protocol==='gemini-generate-content'?'/{model}':'')}}));
          return {workerId:String(proc.pid),model,target:'agent',reference:'fixture-process-'+proc.pid};
        },
        ack:(a,r)=>state(a.ticket,'running',{run:history.get(a.ticket),model:r.model,worker:r.workerId}),
        record:()=>{}
      })
    };
    await dispatchGraph(event,'local-fixture',graph,host);
    if (!active.size) emit({scope:'synthetic_loopback',idle:true});
  }).catch(error=>emit({error:String(error.message)}));
}
async function handle(cmd) {
  if(cmd.action==='start' && !graph) {
    graph=cmd.plan;
    python=cmd.python;
    server=fixtureEndpoint();
    await new Promise((resolve,reject)=>server.once('error',reject).listen(0,'127.0.0.1',resolve));
    for(const [id,n] of Object.entries(graph.nodes)) {
      if(['image','text'].includes(n.kind)) {
        data.set(id,{kind:n.kind,value:n.value});state(id,'completed');
      } else if(n.kind==='question') state(id,'waiting');
    }
    wake('user.requested');
  } else if(cmd.action==='answer' && graph?.nodes[cmd.id]?.kind==='question' && nodes.get(cmd.id)==='waiting') {
    data.set(cmd.id,{kind:'text',value:cmd.value});state(cmd.id,'completed');wake('decision.recorded');
  } else if(cmd.action==='cancel' && active.has(cmd.id)) {
    state(cmd.id,'stopping');active.get(cmd.id).kill();
  } else if(cmd.action==='retry' && ['failed','cancelled','waiting'].includes(nodes.get(cmd.id)) && graph.nodes[cmd.id].kind==='task') {
    if(cmd.model && !Object.hasOwn(protocols,cmd.model)) throw Error('调试型号无效');
    graph.nodes[cmd.id].model=cmd.model||'';nodes.delete(cmd.id);wake('user.requested');
  }
}
if (process.argv[2]) {
  const seed=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
  fs.unlinkSync(process.argv[2]);
  await handle(seed);
}
const input=readline.createInterface({input:process.stdin,crlfDelay:Infinity});
for await(const line of input) {
  try { await handle(JSON.parse(line)); } catch(error) {emit({error:String(error.message)});}
}
closed=true;
for(const proc of active.values()) proc.kill();
server?.closeAllConnections();
server?.close();
