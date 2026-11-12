import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import {spawn, spawnSync} from 'node:child_process';
import {once} from 'node:events';
import {setTimeout as delay} from 'node:timers/promises';
import {prepare} from '../../tools/godot_parallel/setup.mjs';
const git = (root, ...args) => {
  const r = spawnSync('git', args, {cwd: root, encoding: 'utf8', windowsHide: true});
  assert.equal(r.status, 0, r.stderr); return r.stdout.trim();
};
function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'production-setup-'));
  t.after(() => fs.rmSync(root, {recursive: true, force: true, maxRetries: 5}));
  git(root, 'init'); git(root, 'config', 'user.name', 'Fixture'); git(root, 'config', 'user.email', 'fixture@example.invalid');
  fs.mkdirSync(path.join(root, 'design-docs'));
  fs.writeFileSync(path.join(root, 'design-docs', 'fixture.md'), 'Confirmed design');
  fs.writeFileSync(path.join(root, '.gitignore'), '/data-collection/outbox/\n');
  const bridge = path.join(root, 'fixture-bridge.cjs');
  fs.writeFileSync(bridge, 'process.stdout.write(JSON.stringify({models:[{id:"fixture-model"}]}));');
  git(root, 'add', '.'); git(root, 'commit', '-m', 'fixture');
  return {workspace: root, issue: 810, requestId: 'fixture', capacity: 2, nativeWorkspaceWrite: true,
    model: 'fixture-model', discoveredModels: [{id: 'fixture-model'}], orders: [1, 2], python: process.execPath,
    executable: process.execPath, backend: 'codebuddy', cliEntry: bridge, modelBridge: bridge, node: process.execPath,
    authorityRef: 'fixture-only', designSha256: crypto.createHash('sha256').update('Confirmed design').digest('hex')};
}
test('real worktrees, immutable config, idempotency, changed capacity and preserved worker edits', t => {
  const request = fixture(t);
  const first = prepare(request); const config = JSON.parse(fs.readFileSync(first.config));
  assert.equal(config.jobs.length, 2); assert.notEqual(config.jobs[0].worktree, config.jobs[1].worktree);
  assert.equal(git(config.jobs[0].worktree, 'rev-parse', 'HEAD^{tree}'), git(request.workspace, 'rev-parse', 'HEAD^{tree}'));
  fs.writeFileSync(path.join(config.jobs[0].worktree, 'worker.txt'), 'Do not overwrite');
  assert.deepEqual(prepare(request), first);
  const changed = prepare({...request, capacity: 3}); assert.notEqual(changed.config, first.config);
  assert.equal(JSON.parse(fs.readFileSync(first.config)).capacity, 2);
  assert.equal(fs.readFileSync(path.join(config.jobs[0].worktree, 'worker.txt'), 'utf8'), 'Do not overwrite');
  assert.equal(git(request.workspace, 'worktree', 'list', '--porcelain').split('worktree ').length - 1, 3);
});
test('stale model fails before creating worktrees', t => {
  const request = fixture(t);
  assert.throws(() => prepare({...request, model: 'missing'}), /discovered catalog/);
  assert.throws(() => prepare({...request, model: 'retired', discoveredModels: [{id:'retired'}]}), /no longer available/);
  assert.equal(git(request.workspace, 'worktree', 'list', '--porcelain').split('worktree ').length - 1, 1);
});

for (const mode of ['autocrlf', 'attributes-crlf', 'lf-with-autocrlf']) {
  test('confirmed design preserves raw digest across Git newline conversion: ' + mode, t => {
    const request = fixture(t);
    git(request.workspace, 'config', 'core.autocrlf', mode === 'attributes-crlf' ? 'false' : 'true');
    if (mode === 'attributes-crlf') fs.writeFileSync(path.join(request.workspace, '.gitattributes'), '*.md text eol=crlf\n');
    const text = mode === 'lf-with-autocrlf' ? '# Confirmed\n\nCurrent design\n' : '# Confirmed\r\n\r\nCurrent design\r\n';
    const designPath = path.join(request.workspace, 'design-docs/fixture.md');
    fs.writeFileSync(designPath, text);
    request.designSha256 = crypto.createHash('sha256').update(text).digest('hex');
    const index = fs.readFileSync(path.join(request.workspace, '.git/index'));
    const head = git(request.workspace, 'rev-parse', 'HEAD');
    const result = prepare(request);
    const job = JSON.parse(fs.readFileSync(result.config)).jobs[0];
    assert.equal(git(job.worktree, 'show', 'HEAD:design-docs/fixture.md'), text.replaceAll('\r\n', '\n').trim());
    assert.equal(fs.readFileSync(path.join(job.worktree, 'design-docs/fixture.md'), 'utf8'), text);
    assert.equal(fs.readFileSync(designPath, 'utf8'), text);
    assert.deepEqual(fs.readFileSync(path.join(request.workspace, '.git/index')), index);
    assert.equal(git(request.workspace, 'rev-parse', 'HEAD'), head);
    assert.deepEqual(prepare(request), result);
    fs.appendFileSync(designPath, 'User edit');
    assert.throws(() => prepare(request), /Confirmed design changed/);
  });
}
test('duplicate order, invalid capacity and no native authorization fail closed', t => {
  const request = fixture(t);
  for (const patch of [{orders:[1,1]}, {capacity:0}, {capacity:1.5}, {nativeWorkspaceWrite:false}]) assert.throws(() => prepare({...request,...patch}));
});
test('unknown lock and altered checkout preserve ownership', t => {
  const request = fixture(t); const result = prepare(request);
  const lock = path.join(path.dirname(result.receipt), 'preparing.lock');
  fs.writeFileSync(lock, 'unknown'); assert.throws(() => prepare(request), /unknown outcome/);
  assert.equal(fs.readFileSync(lock, 'utf8'), 'unknown'); fs.unlinkSync(lock);
  const config = JSON.parse(fs.readFileSync(result.config));
  git(config.jobs[0].worktree, 'switch', '-c', 'other-owner');
  assert.throws(() => prepare(request), /identity changed/);
  assert.equal(git(config.jobs[0].worktree, 'branch', '--show-current'), 'other-owner');
});
test('host CLI returns durable error receipt without preparation', t => {
  const request = fixture(t); const directory = path.join(request.workspace, 'data-collection/outbox');
  fs.mkdirSync(directory, {recursive:true}); const input = path.join(directory, 'input.json'); const output = input+'.result';
  fs.writeFileSync(input, JSON.stringify({...request, capacity:0}));
  const result = spawnSync(process.execPath, ['tools/godot_parallel/setup.mjs', input, output], {encoding:'utf8', windowsHide:true});
  assert.equal(result.status,0,result.stderr); assert.equal(JSON.parse(fs.readFileSync(output)).state,'blocked');
});

test('Windows preparation enables repository-local long paths for workers and later verification', {skip: process.platform !== 'win32'}, t => {
  const request = fixture(t);
  git(request.workspace, 'config', '--local', 'core.longpaths', 'false');
  const relative = ['deep', 'a'.repeat(95), 'b'.repeat(95), 'input.txt'].join('/');
  const file = path.join(request.workspace, relative);
  fs.mkdirSync(path.dirname(file), {recursive: true});
  fs.writeFileSync(file, 'Long path user input');
  const head = git(request.workspace, 'rev-parse', 'HEAD');
  const index = fs.readFileSync(path.join(request.workspace, '.git/index'));
  const result = prepare(request);
  assert.equal(git(request.workspace, 'config', '--local', '--get', 'core.longpaths'), 'true');
  for (const job of JSON.parse(fs.readFileSync(result.config)).jobs) {
    assert.ok(path.join(job.worktree, relative).length > 260);
    assert.equal(fs.readFileSync(path.join(job.worktree, relative), 'utf8'), 'Long path user input');
    assert.equal(git(job.worktree, 'status', '--porcelain'), '');
  }
  assert.equal(git(request.workspace, 'rev-parse', 'HEAD'), head);
  assert.deepEqual(fs.readFileSync(path.join(request.workspace, '.git/index')), index);
});

test('normal editor uncommitted design and user files are pinned without touching source HEAD or index', t => {
  const request = fixture(t);
  const head = git(request.workspace, 'rev-parse', 'HEAD');
  const index = fs.readFileSync(path.join(request.workspace, '.git/index'));
  fs.writeFileSync(path.join(request.workspace, 'design-docs/fixture.md'), 'New current design');
  fs.writeFileSync(path.join(request.workspace, 'user.txt'), 'Keep user work');
  request.designSha256 = crypto.createHash('sha256').update('New current design').digest('hex');
  const result = prepare(request); const config = JSON.parse(fs.readFileSync(result.config));
  assert.equal(fs.readFileSync(path.join(config.jobs[0].worktree, 'design-docs/fixture.md'), 'utf8'), 'New current design');
  assert.equal(fs.readFileSync(path.join(config.jobs[0].worktree, 'user.txt'), 'utf8'), 'Keep user work');
  assert.equal(git(request.workspace, 'rev-parse', 'HEAD'), head);
  assert.deepEqual(fs.readFileSync(path.join(request.workspace, '.git/index')), index);
  assert.deepEqual(prepare(request), result);
  fs.writeFileSync(path.join(request.workspace, 'user.txt'), 'Later edits');
  assert.throws(() => prepare(request), /baseline changed/);
  assert.equal(fs.readFileSync(path.join(config.jobs[0].worktree, 'user.txt'), 'utf8'), 'Keep user work');
});

test('unowned target and failed login never overwrite or start a worker', t => {
  const request = fixture(t);
  assert.throws(() => prepare({...request, backend:'codex'}), /login status/);
  const key = crypto.createHash('sha256').update(JSON.stringify([request.issue, request.requestId, request.designSha256])).digest('hex').slice(0,24);
  const unknown = path.join(request.workspace, 'data-collection/outbox/production-setup-' + key, 'order-1');
  fs.mkdirSync(unknown, {recursive:true}); fs.writeFileSync(path.join(unknown, 'owner.txt'), 'unknown owner');
  assert.throws(() => prepare(request), /without this preparation receipt/);
  assert.equal(fs.readFileSync(path.join(unknown, 'owner.txt'), 'utf8'), 'unknown owner');
});

async function interrupted(t, request, phase) {
  const directory = path.join(request.workspace, 'data-collection/outbox');
  fs.mkdirSync(directory, {recursive: true});
  const marker = path.join(directory, 'phase.json');
  const input = path.join(directory, 'request.json');
  fs.writeFileSync(input, JSON.stringify(request));
  const script = `
    import fs from 'node:fs';
    const rename = fs.renameSync;
    fs.renameSync = function(from, to) {
      const value = JSON.parse(fs.readFileSync(from));
      const phase = ${JSON.stringify(phase)};
      const receipt = String(to).endsWith('receipt.json');
      const hit = (phase === 'lock' && String(to).endsWith('preparing.lock')) ||
        (phase === 'snapshot' && receipt && value.jobs.length === 0) ||
        (phase === 'intent' && receipt && value.jobs[0]?.state === 'intent') ||
        (phase === 'after-add' && receipt && value.jobs[0]?.state === 'ready') ||
        (phase === 'config' && String(to).includes('config.json.'));
      if (phase !== 'after-add' || !hit) rename(from, to);
      if (hit) {
        fs.writeFileSync(${JSON.stringify(marker)}, JSON.stringify({to, value}));
        Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0);
      }
      if (phase === 'after-add' && hit) rename(from, to);
    };
    const {prepare} = await import(${JSON.stringify(new URL('../../tools/godot_parallel/setup.mjs', import.meta.url).href)});
    prepare(JSON.parse(fs.readFileSync(${JSON.stringify(input)})));
  `;
  const child = spawn(process.execPath, ['--input-type=module', '-e', script], {windowsHide: true, stdio: ['ignore', 'pipe', 'pipe']});
  let errors = ''; child.stderr.on('data', chunk => errors += chunk);
  const exited = once(child, 'exit');
  t.after(() => { if (child.exitCode === null) child.kill('SIGKILL'); });
  const deadline = Date.now() + 20000;
  while (!fs.existsSync(marker) && child.exitCode === null && Date.now() < deadline) await delay(20);
  assert.ok(fs.existsSync(marker), `Child did not reach ${phase}: ${errors}`);
  return {child, exited, marker: JSON.parse(fs.readFileSync(marker)), async kill() { child.kill('SIGKILL'); await exited; }};
}

for (const phase of ['lock', 'snapshot', 'intent', 'after-add', 'config']) {
  test(`killed real setup at ${phase} resumes once with pinned inputs and no duplicate config/copies`, async t => {
    const request = fixture(t);
    fs.writeFileSync(path.join(request.workspace, 'user-current.txt'), 'uncommitted input');
    const head = git(request.workspace, 'rev-parse', 'HEAD');
    const index = fs.readFileSync(path.join(request.workspace, '.git/index'));
    const running = await interrupted(t, request, phase);
    assert.throws(() => prepare(request), /already active|unknown outcome/);
    await running.kill();
    const result = prepare(request);
    assert.deepEqual(prepare(request), result);
    assert.equal(git(request.workspace, 'worktree', 'list', '--porcelain').split('worktree ').length - 1, 3);
    const config = JSON.parse(fs.readFileSync(result.config));
    assert.equal(fs.readFileSync(path.join(config.jobs[0].worktree, 'user-current.txt'), 'utf8'), 'uncommitted input');
    assert.equal(fs.readdirSync(path.dirname(result.receipt)).filter(name => /^config\.json\..*\.json$/.test(name)).length, 1);
    assert.equal(git(request.workspace, 'rev-parse', 'HEAD'), head);
    assert.deepEqual(fs.readFileSync(path.join(request.workspace, '.git/index')), index);
  });
}

for (const drift of ['contents', 'ignored', 'branch', 'commit', 'common', 'snapshot', 'live-owner']) {
  test(`interrupted owned worktree rejects ${drift} drift without overwrite`, async t => {
    const request = fixture(t);
    const running = await interrupted(t, request, 'after-add'); await running.kill();
    const receiptPath = running.marker.to;
    const receipt = JSON.parse(fs.readFileSync(receiptPath));
    const job = receipt.jobs[0];
    if (drift === 'contents') fs.writeFileSync(path.join(job.worktree, 'foreign.txt'), 'preserve');
    if (drift === 'ignored') { fs.mkdirSync(path.join(job.worktree, 'data-collection/outbox'), {recursive:true}); fs.writeFileSync(path.join(job.worktree, 'data-collection/outbox/foreign.txt'), 'preserve'); }
    if (drift === 'branch') git(job.worktree, 'switch', '-c', 'foreign');
    if (drift === 'commit') git(job.worktree, 'commit', '--allow-empty', '-m', 'foreign');
    if (drift === 'common') job.common = job.worktree;
    if (drift === 'snapshot') job.snapshot = receipt.head;
    if (drift === 'live-owner') job.owner.pid = process.pid;
    fs.writeFileSync(receiptPath, JSON.stringify(receipt));
    const before = git(job.worktree, 'status', '--porcelain', '--ignored');
    assert.throws(() => prepare(request), /interrupted/);
    assert.equal(git(job.worktree, 'status', '--porcelain', '--ignored'), before);
    assert.equal(git(request.workspace, 'worktree', 'list', '--porcelain').split('worktree ').length - 1, 2);
  });
}

test('evidence-only source additions preserve the pinned snapshot and configuration', t => {
  const request = fixture(t); const first = prepare(request);
  fs.mkdirSync(path.join(request.workspace, 'gonggong-diting-data'), {recursive:true});
  fs.writeFileSync(path.join(request.workspace, 'gonggong-diting-data/receipt.json'), '{}');
  fs.writeFileSync(path.join(request.workspace, 'data-collection/evidence.json'), '{}');
  assert.deepEqual(prepare(request), first);
});

test('concurrent dead-owner retries have one authoritative lease and no duplicate worktrees', async t => {
  const request = fixture(t); const running = await interrupted(t, request, 'after-add'); await running.kill();
  const directory = path.join(request.workspace, 'data-collection/outbox');
  const input = path.join(directory, 'request.json');
  const script = new URL('../../tools/godot_parallel/setup.mjs', import.meta.url);
  const {fileURLToPath} = await import('node:url');
  const results = await Promise.all([1, 2].map(async id => {
    const output = path.join(directory, `result-${id}.json`);
    const child = spawn(process.execPath, [fileURLToPath(script), input, output], {windowsHide:true, stdio:'ignore'});
    const [code] = await once(child, 'exit'); assert.equal(code, 0);
    return JSON.parse(fs.readFileSync(output));
  }));
  assert.ok(results.some(result => result.state === 'ready'));
  const final = prepare(request);
  for (const result of results.filter(result => result.state === 'ready')) assert.deepEqual(result, final);
  assert.equal(git(request.workspace, 'worktree', 'list', '--porcelain').split('worktree ').length - 1, 3);
});
