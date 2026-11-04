// Explicit current-host tool transport. Files carry evidence, never authority.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
export const digest = value => crypto.createHash('sha256').update(JSON.stringify(value)).digest('hex');
const read = file => JSON.parse(fs.readFileSync(file,'utf8'));
export function create(file,value) {
  fs.mkdirSync(path.dirname(file),{recursive:true});
  const fd=fs.openSync(file,'wx',0o600);
  try {fs.writeFileSync(fd,JSON.stringify(value)+'\n');fs.fsyncSync(fd);} finally {fs.closeSync(fd);}
}
export class NativeToolBridge {
  constructor(root,authorityRef) {
    if(!path.isAbsolute(root)||!authorityRef)throw Error('Absolute private bridge root and actual authority required');
    this.root=root;this.authorityRef=authorityRef;this.watchers=new Set();fs.mkdirSync(root,{recursive:true});
  }
  request(tool,args,context={}) {
    if(!['spawn_agent','create_thread','verify_worker','verify_setup'].includes(tool))throw Error('Unsupported native tool');
    const id=crypto.randomUUID();
    const request={id,tool,args,argsDigest:digest(args),authorityRef:this.authorityRef,context};
    create(path.join(this.root,id+'.request.json'),request);
    return new Promise((resolve,reject)=>{
      const file=path.join(this.root,id+'.response.json');
      const check=()=>{
        if(!fs.existsSync(file))return;
        try {
          const response=read(file);
          if(response.id!==id||response.tool!==tool||response.argsDigest!==request.argsDigest)throw Error('Native response binding mismatch');
          watcher.close();this.watchers.delete(watcher);resolve(response.result);
        } catch(error){watcher.close();this.watchers.delete(watcher);reject(error);}
      };
      // Watch before checking; a response arriving in either interval is observed.
      const watcher=fs.watch(this.root,check);this.watchers.add(watcher);watcher.on('error',error=>{watcher.close();this.watchers.delete(watcher);reject(error);});check();
    });
  }
  native() {return Object.fromEntries(['spawn_agent','create_thread'].map(tool=>[tool,(args,context)=>this.request(tool,args,context)]));}
  close() {for(const watcher of this.watchers)watcher.close();this.watchers.clear();}
  take(id) {
    if(!/^[0-9a-f-]{36}$/.test(id))throw Error('Invalid request id');
    const request=read(path.join(this.root,id+'.request.json'));
    if(request.authorityRef!==this.authorityRef||digest(request.args)!==request.argsDigest)throw Error('Request binding changed');
    // Durable issued marker precedes the host's real call. Never issue twice.
    create(path.join(this.root,id+'.issued.json'),{id,argsDigest:request.argsDigest,authorityRef:this.authorityRef});
    return request;
  }
  respond(id,result,toolEvidenceRef) {
    if(!/^[0-9a-f-]{36}$/.test(id)||!toolEvidenceRef)throw Error('Actual native tool evidence required');
    const request=read(path.join(this.root,id+'.request.json'));
    const issued=read(path.join(this.root,id+'.issued.json'));
    if(issued.argsDigest!==request.argsDigest||issued.authorityRef!==this.authorityRef)throw Error('Issued request mismatch');
    const response={id,tool:request.tool,argsDigest:request.argsDigest,result,toolEvidenceRef};
    // Only a trusted host calls respond after the real tool returns. Atomic publish.
    const temporary=path.join(this.root,id+'.response.pending');create(temporary,response);
    fs.linkSync(temporary,path.join(this.root,id+'.response.json'));fs.unlinkSync(temporary);
  }
}
