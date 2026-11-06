import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {reservationOperation, ticketOperation, withBlockerRouting} from './kuafu_dispatch.mjs';

const repository = JSON.parse(fs.readFileSync(new URL('../../../work-items.json', import.meta.url))).repository;
const ticket = n => `github:${repository}#${n}`;
const config = {repository, bindings:[{number:1,requestId:'one'},{number:2,requestId:'two'}],
  requests:[{ticket:ticket(1)},{ticket:ticket(2)}]};
const failure = async () => {throw Error('test failure');};

test('route proven per-ticket errors and blockers; preserve normal waits and successful peers', async () => {
  const received = [];
  const notify = (_,binding) => received.push(binding.number);
  const waits = ['not_ready','capacity','resource_conflict','already_in_flight','existing_reservation'];
  const result = {results:[{ticket:ticket(2),state:'running'}],
    deferred:[...waits.map(reason => ({ticket:ticket(2),reason})),{ticket:ticket(1),reason:'host_revalidation_failed'}]};
  assert.equal(await withBlockerRouting(config,async()=>result,notify), result);
  await assert.rejects(withBlockerRouting(config,()=>ticketOperation(ticket(2),failure),notify),/test failure/);
  await assert.rejects(withBlockerRouting(config,failure,notify),/test failure/);
  assert.deepEqual(received, [1,2]);
});

test('use only the failed reservation from the bound worktree and preserve the original failure', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(),'kuafu-dispatch-'));
  t.after(() => fs.rmSync(root,{recursive:true,force:true}));
  const git = (...args) => execFileSync('git',['-C',root,...args],{stdio:'pipe'});
  git('init','-q');
  git('remote','add','origin',`https://github.com/${repository}.git`);
  fs.writeFileSync(path.join(root,'work-items.json'),JSON.stringify({repository}));
  const key = 'a'.repeat(64);
  const dir = path.join(root,'data-collection/receipts/codex-dispatch/dispatch/reservations');
  fs.mkdirSync(dir,{recursive:true});
  fs.writeFileSync(path.join(dir,key+'.json'),JSON.stringify({assignment:{key,ticket:ticket(2)}}));
  const c = {...config,action:'reconcile',workspace:root,reservationKey:key};
  const received = [];
  const notify = (_,binding) => received.push(binding.number);
  await assert.rejects(withBlockerRouting(c,()=>reservationOperation(c,failure),notify),/test failure/);
  c.reservationKey = 'b'.repeat(64);
  await assert.rejects(withBlockerRouting(c,()=>reservationOperation(c,failure),notify),/test failure/);
  git('remote','set-url','origin','https://github.com/example/unrelated.git');
  c.reservationKey = key;
  await assert.rejects(withBlockerRouting(c,()=>reservationOperation(c,failure),notify),/test failure/);
  assert.deepEqual(received,[2]);
});

test('entry bootstrap with one known Issue keeps its identity on failure', async () => {
  const received = [];
  const bootstrap = {...config,requests:[{ticket:ticket(2)}]};
  await assert.rejects(withBlockerRouting(bootstrap,failure,(_,b)=>received.push(b.number)),/test failure/);
  assert.deepEqual(received,[2]);
});

test('actual Python capture binds the separate workspace and ignores its executable suggestion', async t => {
  const prior = process.env.GONGGONG_KUAFU_LOCAL_ONLY;
  process.env.GONGGONG_KUAFU_LOCAL_ONLY = '1';
  t.after(() => {
    if (prior === undefined) delete process.env.GONGGONG_KUAFU_LOCAL_ONLY;
    else process.env.GONGGONG_KUAFU_LOCAL_ONLY = prior;
  });
  const root = fs.mkdtempSync(path.join(os.tmpdir(),'kuafu-dispatch-capture-'));
  t.after(() => fs.rmSync(root,{recursive:true,force:true}));
  const git = (...args) => execFileSync('git',['-C',root,...args],{stdio:'pipe'});
  git('init','-q');
  git('remote','add','origin',`https://github.com/${repository}.git`);
  git('-c','user.name=test','-c','user.email=test@example.invalid','commit','--allow-empty','-qm','fixture');
  fs.mkdirSync(path.join(root,'.github'));
  fs.writeFileSync(path.join(root,'work-items.json'),JSON.stringify({repository}));
  fs.writeFileSync(path.join(root,'.github/labels.json'),'[]');
  const c = {...config,workspace:root,python:path.join(root,'bogus-python'),requests:[{ticket:ticket(2)}]};
  await assert.rejects(withBlockerRouting(c,failure), /test failure/);
  const incidents = path.join(root,'.git','gonggong-kuafu');
  const [entry] = fs.readdirSync(incidents);
  const record = JSON.parse(fs.readFileSync(path.join(incidents,entry,'detected.json')));
  assert.equal(record.issue,2);
  assert.equal(fs.realpathSync(record.worktree),fs.realpathSync(root));
  assert.equal(record.head,git('rev-parse','HEAD').toString().trim());
});
