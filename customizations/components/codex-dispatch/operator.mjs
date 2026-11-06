// One explicit event in one bound local installation; no daemon or remote CAS.
import fs from 'node:fs';
import path from 'node:path';
import {execFile,spawn} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import {GitHubIssueSource,issueSnapshot,readIssueWithDependencies} from '../issue-workorders/github_source.mjs';
import {CodexDispatchHost} from './adapter.mjs';
import {NativeToolBridge,create,digest} from './native-bridge.mjs';
const exec=promisify(execFile), read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const command=async(file,args,cwd)=>JSON.parse((await exec(file,args,{cwd,windowsHide:true,maxBuffer:4*1024*1024})).stdout);
export class OperatorRuntime {
  constructor({root,repository,bindings,readIssue,allowedCategories,operator,catalog,capacity,authorityRef,authorize,report,verifyWorker,acceptedDependency,chatCreationAuthorized=false,verifyWriteAccess}) {
    if(!path.isAbsolute(root)||!operator||!authorityRef||typeof authorize!=='function'||typeof report!=='function'||typeof verifyWorker!=='function')throw Error('Actual operator host binding required');
    Object.assign(this,{root,repository,bindings,readIssue,allowedCategories,operator,catalog,capacity,authorityRef,checkAuthority:authorize,report,verifyWorker,acceptedDependency,chatCreationAuthorized,verifyWriteAccess});
    fs.mkdirSync(root,{recursive:true});
  }
  file(ticket,suffix='claim',key='') {return path.join(this.root,digest(ticket)+(key?'-'+key:'')+'.'+suffix+'.json');}
  active() {return fs.readdirSync(this.root).filter(n=>n.endsWith('.claim.json')).map(n=>read(path.join(this.root,n))).filter(c=>!fs.existsSync(this.file(c.assignment.ticket,'terminal',c.assignment.key))).map(c=>c.assignment);}
  async environment() {return {active:this.active(),catalog:this.catalog,capacity:this.capacity,chatCreationAuthorized:this.chatCreationAuthorized};}
  async assess(item,sourceSnapshot,event) {
    if(await this.checkAuthority({ticket:item.key,sourceSnapshot,event})!==true)return false;
    for(const dependency of item.dependsOn)if(!this.acceptedDependency||await this.acceptedDependency(dependency)!==true)return false;
    return true;
  }
  async authorize(a,current) {
    if (await this.checkAuthority(a)!==true || !await this.assess(current.item,current.sourceSnapshot,{type:'ticket.changed',reference:this.authorityRef})) return false;
    if (this.verifyWriteAccess) await this.verifyWriteAccess();
    return true;
  }
  async compareAndStart(a) {
    const lock=this.file(a.ticket,'lock');create(lock,{operator:this.operator,key:a.key});
    try {
      if(this.active().some(x=>x.ticket===a.ticket)||fs.existsSync(this.file(a.ticket,'claim',a.key)))throw Error('Source already claimed; reconcile original worker');
      const binding=this.bindings.find(b=>`github:${this.repository}#${b.number}`===a.ticket);
      if(!binding)throw Error('Unbound ticket');
      const current=issueSnapshot(this.repository,binding,await this.readIssue(this.repository,binding.number),this.allowedCategories);
      if(JSON.stringify(current.sourceSnapshot)!==JSON.stringify(a.sourceSnapshot)||current.item.status!=='status:in-progress'||current.item.lifecycle!=='open'||!await this.authorize(a,current))throw Error('Source revision changed or authority revoked');
      const claim={assignment:a,operator:this.operator,authorityRef:this.authorityRef};
      create(this.file(a.ticket,'claim',a.key),claim);
      return {key:a.key,ticket:a.ticket,sourceSha256:a.sourceSnapshot.sha256,reference:`local-source-claim:${digest(a.ticket)}:${a.key}`};
    } finally {fs.unlinkSync(lock);}
  }
  async beforeLaunch(a) {
    const lock=this.file(a.ticket,'lock');create(lock,{key:a.key,stage:'before_launch'});
    try {
      const c=read(this.file(a.ticket,'claim',a.key));
      if(c.assignment.key!==a.key||fs.existsSync(this.file(a.ticket,'terminal',a.key)))throw Error('Claim already terminal');
      if (c.operator !== this.operator) await this.verifyClaimOwner?.(a);
      const binding=this.bindings.find(b=>`github:${this.repository}#${b.number}`===a.ticket);
      const current=issueSnapshot(this.repository,binding,await this.readIssue(this.repository,binding.number),this.allowedCategories);
      if(JSON.stringify(current.sourceSnapshot)!==JSON.stringify(a.sourceSnapshot)||!await this.authorize(a,current))throw Error('Source changed before native launch');
      // This conservative intent excludes concurrent never-launched release.
      create(this.file(a.ticket,'launch-intent',a.key),{key:a.key,authorityRef:this.authorityRef});
    } finally {fs.unlinkSync(lock);}
  }
  async ack(a,receipt) {
    await this.verifyClaimOwner?.(a);
    const c=read(this.file(a.ticket,'claim',a.key));
    if(c.assignment.key!==a.key||!receipt.workerId||receipt.model!==a.model.id||receipt.target!==a.target)return false;
    const file=this.file(a.ticket,'worker',a.key);
    if(fs.existsSync(file))return JSON.stringify(read(file))===JSON.stringify({key:a.key,receipt});
    create(file,{key:a.key,receipt});return true;
  }
  async verifyTerminal(a,event,receipt) {
    await this.verifyClaimOwner?.(a);
    const worker=read(this.file(a.ticket,'worker',a.key));
    if(worker.key!==a.key||worker.receipt.workerId!==receipt.workerId||JSON.stringify(worker.receipt)!==JSON.stringify(receipt)||await this.verifyWorker(receipt,event,a)!==true)return false;
    const terminal=this.file(a.ticket,'terminal',a.key);
    if(!fs.existsSync(terminal))create(terminal,{key:a.key,workerId:receipt.workerId,event});
    return true;
  }
  async verifyNeverLaunched(a,event,nativeRoot) {
    await this.verifyClaimOwner?.(a);
    const lock=this.file(a.ticket,'lock');create(lock,{key:a.key,stage:'verify_never_launched'});
    try {
      if(await this.checkAuthority(a)!==true||['worker','launch-intent'].some(s=>fs.existsSync(this.file(a.ticket,s,a.key))))return false;
      if(fs.readdirSync(nativeRoot).filter(n=>n.endsWith('.request.json')).some(n=>read(path.join(nativeRoot,n)).context?.assignmentKey===a.key))return false;
      const terminal=this.file(a.ticket,'terminal',a.key);
      if(!fs.existsSync(terminal))create(terminal,{key:a.key,event,state:'never_launched_verified'});
      return true;
    } finally {fs.unlinkSync(lock);}
  }
}
export async function operatorStateRoot(workspace) {
  const gitCommon=(await exec('git',['rev-parse','--git-common-dir'],{cwd:workspace})).stdout.trim();
  const common=fs.realpathSync(path.resolve(workspace,gitCommon));
  return path.join(path.dirname(common),'data-collection/receipts/codex-dispatch');
}
export async function openSession(config,ports={}) {
  const workspace=fs.realpathSync(config.workspace);
  const root=await operatorStateRoot(workspace);
  const api=async endpoint=>command(config.gh??'gh',['api',endpoint],workspace);
  const settings=read(path.join(workspace,'work-items.json'));
  if(settings.repository!==config.repository||settings.tenant_id!=='gonggong-workspace')throw Error('Repository/tenant binding mismatch');
  const [owner, name] = config.repository.split('/');
  const viewerQuery = 'query($owner:String!,$name:String!){viewer{login} repository(owner:$owner,name:$name){nameWithOwner viewerPermission}}';
  async function verifyAccess(requireWrite) {
    const response = await command(config.gh ?? 'gh', ['api','graphql','-f','query=' + viewerQuery,
      '-f','owner=' + owner,'-f','name=' + name], workspace);
    const {viewer,repository} = response.data;
    if (viewer?.login !== config.operator || repository?.nameWithOwner !== config.repository) throw Error('Authenticated operator or repository changed');
    if (requireWrite && !['WRITE','MAINTAIN','ADMIN'].includes(repository.viewerPermission)) throw Error('Current operator write permission required');
  }
  const resume = ['reconcile','setup','release-unstarted'].includes(config.action);
  await verifyAccess(!resume);
  const categories=read(path.join(workspace,'.github/labels.json')).map(l=>l.name);
  const readIssue=async(repo,n)=>{
    const issue = await readIssueWithDependencies(api, repo, n);
    if (ports.validateIssue) await ports.validateIssue(issue);
    return issue;
  };
  // A host port must attest real terminal events; no file or model text self-attests.
  const verifyWorker=ports.worker?.verifyTerminal??ports.verifyWorker??(async(receipt,event,a)=>{
    const result=await bridge.request('verify_worker',{receipt,event},{assignmentKey:a.key,ticket:a.ticket});
    return result?.workerId===receipt.workerId&&result.reference===event.reference&&
      (event.type==='execution.finished'?result.state==='completed':['failed','interrupted'].includes(result.state));
  });
  const runtime=new OperatorRuntime({root:path.join(root,'sources'),repository:config.repository,bindings:config.bindings,readIssue,allowedCategories:categories,operator:config.operator,catalog:config.catalog,capacity:config.capacity,authorityRef:config.authorityRef,
    verifyWriteAccess:()=>verifyAccess(true),
    authorize:async a=>{
      if(!config.requests.some(r=>r.ticket===a.ticket&&r.authorityRef===config.authorityRef))return false;
      await exec(config.python,['-X','utf8',path.join(workspace,'framework/tools/verify_framework.py')],{cwd:workspace,windowsHide:true});return true;
    },report:ports.report??(async record=>{
      const binding=config.bindings.find(b=>`github:${config.repository}#${b.number}`===record.assignment?.ticket);
      if(!binding)throw Error('Reporting assignment binding missing');
      return await new Promise((resolve,reject)=>{
        const child=spawn(config.python,[fileURLToPath(new URL('./report.py',import.meta.url)),workspace],{cwd:workspace,windowsHide:true,stdio:['pipe','pipe','pipe']});
        let output='',error='';child.stdout.on('data',d=>output+=d);child.stderr.on('data',d=>error+=d);
        child.on('error',reject);child.on('close',code=>{if(code!==0)return reject(Error('Diting reporting failed: '+error));try{const receipt=JSON.parse(output);if(receipt.ok!==true||receipt.state!=='recorded_file')throw Error('No reporting receipt');resolve(receipt);}catch(e){reject(e);}});
        child.stdin.on('error',reject);child.stdin.end(JSON.stringify({requestId:binding.requestId,issue:binding.number,record,backend:ports.worker ? 'repository' : 'codex'}));
      });
    }),verifyWorker,acceptedDependency:ports.acceptedDependency,chatCreationAuthorized:config.chatCreationAuthorized===true});
  const source=new GitHubIssueSource({repository:config.repository,bindings:config.bindings,readIssue,allowedCategories:categories,runtime});
  const bridge=new NativeToolBridge(path.join(root,'native'),config.authorityRef);
  runtime.verifyClaimOwner = async a => {
    if (!/^[0-9a-f]{64}$/.test(a.key)) throw Error('Invalid reservation key');
    const claimPath = runtime.file(a.ticket,'claim',a.key);
    const reservationPath = path.join(root,'dispatch','reservations',a.key + '.json');
    const owners = new Set();
    for (const file of [claimPath,reservationPath]) {
      if (!fs.existsSync(file)) continue;
      const saved = read(file);
      if (saved.assignment?.key !== a.key || saved.assignment.ticket !== a.ticket) throw Error('Recovery binding changed');
      if (saved.operator) owners.add(saved.operator);
    }
    if (owners.size > 1) throw Error('Conflicting recovery ownership; reconcile the handoff');
    const [owner] = owners;
    const handoff = !owner || owner !== config.operator;
    await verifyAccess(handoff);
    if (handoff && await ports.verifyRecoveryHandoff?.(a,owner ?? null,config.operator) !== true) {
      throw Error('An authenticated handoff for this claim is required');
    }
  };
  source.verifyClaimOwner=runtime.verifyClaimOwner;
  source.verifyNeverLaunched=(a,event)=>runtime.verifyNeverLaunched(a,event,bridge.root);
  source.verifySetup=async(a,event,pending,receipt)=>{
    await runtime.verifyClaimOwner(a);
    if (ports.verifySetup) return ports.verifySetup(a,event,pending,receipt);
    const result=await bridge.request('verify_setup',{event,pending,receipt},{assignmentKey:a.key,ticket:a.ticket});
    return result?.clientThreadId===pending.workerId&&result.threadId===receipt.workerId&&result.reference===event.reference;
  };
  const host=new CodexDispatchHost({stateRoot:path.join(root,'dispatch'),source,native:ports.worker ? {launchAgent:ports.worker.launch} : bridge.native(),policy:{localResources:true,operator:config.operator,defaultChatModel:config.defaultChatModel,inheritedAgentModel:config.inheritedAgentModel,chatCreationAuthorized:config.chatCreationAuthorized===true,threadTarget:config.threadTarget,explicitChatModels:config.explicitChatModels}});
  if (ports.worker?.revalidate) {
    const revalidate = host.revalidate.bind(host);
    host.revalidate = async a => await revalidate(a) && await ports.worker.revalidate(a);
  }
  if (resume) {
    // A verified receipt may be reconciled after revocation. Backfilling a slot starts new work.
    const run = host.run.bind(host);
    host.run = async (event, requests) => {
      if (requests.length) await verifyAccess(true);
      return run(event, requests);
    };
  }
  const launch=host.launch.bind(host);host.launch=async a=>{if (ports.beforeLaunch) await ports.beforeLaunch(a);await runtime.beforeLaunch(a);return launch(a);};
  return {host,bridge,runtime};
}
