import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {pathToFileURL, fileURLToPath} from 'node:url';
import {githubRuntime} from './github_runtime.mjs';

const python = process.env.GONGGONG_PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
function fixture(t) {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'github-js-')));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  const api = path.join(root,'api');
  fs.writeFileSync(api, `const fs=require('node:fs');const mode=process.argv[2];
    if(mode==='hang')setTimeout(()=>{},10000);
    else if(mode==='secret'){console.error('fixture-token-secret HTTP 403');process.exitCode=1;}
    else if(mode==='network'){console.error('fixture-token-secret connection refused');process.exitCode=1;}
    else if(mode==='invalid')console.log('fixture-token-secret');
    else console.log(JSON.stringify({selected:process.env.GONGGONG_GH,args:process.argv.slice(2)}));`);
  const env = {...process.env,GONGGONG_GH:process.execPath};
  return {root,env,config:{workspace:root,python}};
}
function alias(directory, name) {
  fs.mkdirSync(directory,{recursive:true});
  const file=path.join(directory,name + (process.platform==='win32'?'.exe':''));
  if(process.platform==='win32')fs.copyFileSync(process.execPath,file);
  else fs.symlinkSync(process.execPath,file);
  return file;
}

test('real Python discovery honors environment with GUI PATH; config wins without mutating caller',async t=>{
  const f=fixture(t), env={...f.env,PATH:process.platform==='win32'?process.env.SystemRoot+'/System32':'/usr/bin:/bin'};
  const runtime=await githubRuntime(f.config,{env});
  assert.equal(runtime.gh,process.execPath);
  assert.equal((await runtime.json(['api','read'])).selected,process.execPath);
  const alternate=alias(path.join(f.root,'cli with spaces'),'selected');
  const selected=await githubRuntime({...f.config,gh:alternate},{env});
  assert.equal((await selected.json(['api','read'])).selected,alternate);
  assert.equal(env.GONGGONG_GH,process.execPath);
  assert.notEqual(selected.env,env);
  assert.equal(Object.isFrozen(selected.env),true);
  const replaced=await githubRuntime({...f.config,gh:process.execPath},{env});
  assert.equal(replaced.gh,process.execPath);
  assert.equal(selected.gh,alternate);
});

test('explicit empty/null/invalid/unexecutable choices fail closed instead of falling back',async t=>{
  const f=fixture(t);
  for(const gh of ['',null,undefined,7,false,path.join(f.root,'missing'),f.root]) {
    await assert.rejects(githubRuntime({...f.config,gh},{env:f.env}),/GITHUB_RUNTIME/);
  }
  for(const value of ['',null,undefined])await assert.rejects(githubRuntime(f.config,{env:{...f.env,GONGGONG_GH:value}}),/GITHUB_RUNTIME/);
  if(process.platform!=='win32'){
    const file=path.join(f.root,'not-executable');fs.writeFileSync(file,'private placeholder');
    await assert.rejects(githubRuntime({...f.config,gh:file},{env:f.env}),/not executable/);
  }
});

test('exact command names resolve only the supplied PATH, including missing PATH',async t=>{
  const f=fixture(t),dir=path.join(f.root,'exact path'),file=alias(dir,'selected-cli');
  const runtime=await githubRuntime({...f.config,gh:'selected-cli'},{env:{...f.env,PATH:dir}});
  assert.equal(runtime.gh,file);
  await assert.rejects(githubRuntime({...f.config,gh:'missing-cli'},{env:{...f.env,PATH:dir}}),/GITHUB_RUNTIME/);
  const env={...f.env};delete env.PATH;
  await assert.rejects(githubRuntime({...f.config,gh:'selected-cli'},{env}),/GITHUB_RUNTIME/);
});

test('request transport bounds hangs, sanitizes HTTP/network/JSON errors and keeps unknown-write readback',async t=>{
  const f=fixture(t),runtime=await githubRuntime(f.config,{env:f.env,timeoutMs:100});
  const started=Date.now();
  await assert.rejects(runtime.text(['api','hang']),error=>/GITHUB_TIMEOUT/.test(error.message)&&/read remote state/.test(error.message)&&!error.message.includes('fixture-token-secret'));
  assert.ok(Date.now()-started<5000);
  const errors=await githubRuntime(f.config,{env:f.env});
  for(const [mode,code] of [['secret','GITHUB_HTTP_403'],['network','GITHUB_NETWORK'],['invalid','GITHUB_RESPONSE']]){
    await assert.rejects(errors.json(['api',mode]),error=>error.message.includes(code)&&!error.message.includes('fixture-token-secret')&&/read remote state/.test(error.message));
  }
  for(const timeoutMs of [0,Infinity,120001])await assert.rejects(githubRuntime(f.config,{env:f.env,timeoutMs}),/timeout/);
  await assert.rejects(githubRuntime({...f.config,python:path.join(f.root,'missing-secret-python')},{env:f.env}),error=>/GITHUB_RUNTIME/.test(error.message)&&!error.message.includes('missing-secret-python'));
});

test('git-archived bridge relocates with Python dependency; target project cannot provide tools',async t=>{
  const f=fixture(t),source=path.join(f.root,'archive source'),installed=path.join(f.root,'relocated installation');
  const relative='customizations/components/issue-workorders';
  fs.mkdirSync(path.join(source,relative),{recursive:true});
  for(const name of ['github_runtime.mjs','github_runtime.py','github_runtime_bridge.py'])fs.copyFileSync(fileURLToPath(new URL(name,import.meta.url)),path.join(source,relative,name));
  const git=(...args)=>execFileSync('git',['-C',source,...args],{env:{...process.env,GIT_AUTHOR_NAME:'Fixture',GIT_AUTHOR_EMAIL:'fixture@example.invalid',GIT_COMMITTER_NAME:'Fixture',GIT_COMMITTER_EMAIL:'fixture@example.invalid'}});
  git('init','-q');git('add','.');git('commit','-qm','isolated package');
  fs.mkdirSync(installed);
  execFileSync(python,['-I','-c','import io,sys,tarfile; tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read())).extractall(sys.argv[1], filter="data")',installed],{input:git('archive','HEAD')});
  const {githubRuntime:relocated}=await import(pathToFileURL(path.join(installed,relative,'github_runtime.mjs')));
  const marker=path.join(f.root,'malicious-executed');
  fs.mkdirSync(path.join(f.root,relative),{recursive:true});
  for(const name of ['github_runtime.py','github_runtime_bridge.py','sitecustomize.py'])fs.writeFileSync(path.join(f.root,name),`open(${JSON.stringify(marker)},'w').write('executed')`);
  fs.writeFileSync(path.join(f.root,relative,'github_runtime.py'),`open(${JSON.stringify(marker)},'w').write('executed')`);
  const installedGh=alias(path.join(installed,'project/runtime/gh/bin'),'gh');
  alias(path.join(f.root,'project/runtime/gh/bin'),'gh');
  const env={...f.env,PYTHONPATH:f.root};delete env.GONGGONG_GH;
  const runtime=await relocated(f.config,{env});
  assert.equal(runtime.gh,installedGh);
  assert.equal((await runtime.json(['api','read'])).selected,installedGh);
  assert.equal(fs.existsSync(marker),false);
  fs.unlinkSync(path.join(installed,relative,'github_runtime.py'));
  await assert.rejects(relocated(f.config,{env}),/installed host bridge failed/);
  assert.equal(fs.existsSync(marker),false);
});
