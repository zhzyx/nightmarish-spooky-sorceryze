import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import os from 'node:os';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const digest = value => crypto.createHash('sha256').update(value).digest('hex');
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
function git(root, args, env = process.env) {
  const result = spawnSync('git', args, {cwd: root, env, encoding: 'utf8', windowsHide: true});
  if (result.status !== 0) throw Error(`Git ${args[0]} failed: ${result.stderr?.trim() || result.error?.message}`);
  return result.stdout.trim();
}
function write(file, value) {
  const temporary = file + '.' + crypto.randomUUID() + '.tmp';
  const fd = fs.openSync(temporary, 'wx', 0o600);
  try { fs.writeFileSync(fd, JSON.stringify(value)); fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
  fs.renameSync(temporary, file);
}
function dead(owner) {
  if (owner?.host !== os.hostname() || !Number.isSafeInteger(owner.pid) || owner.pid < 1) return false;
  try { process.kill(owner.pid, 0); return false; } catch (error) { return error.code === 'ESRCH'; }
}
// Git's compare-and-swap serializes stale-lock takeover, including simultaneous
// retries. A PID alone is never permission to reclaim a live or unknown owner.
function acquire(root, common, key, lock) {
  const ref = 'refs/gonggong/production-setup/' + key;
  const current = spawnSync('git', ['rev-parse', '--verify', '--quiet', ref], {cwd: root, encoding: 'utf8', windowsHide: true});
  if (![0, 1].includes(current.status)) throw Error('Cannot inspect preparation ownership');
  const old = current.status === 0 ? current.stdout.trim() : '0'.repeat(git(root, ['hash-object', '--stdin']).length);
  let previous, recorded;
  try {
    previous = current.status === 0 ? JSON.parse(git(root, ['cat-file', 'blob', old])) : null;
    recorded = fs.existsSync(lock) ? read(lock) : null;
    for (const value of [previous, recorded].filter(Boolean)) {
      if (value.version !== 1 || value.root !== root || value.common !== common || value.key !== key ||
          typeof value.nonce !== 'string' || !/^[\da-f-]{36}$/.test(value.nonce)) throw Error();
    }
    if (previous && !['active', 'released'].includes(previous.state)) throw Error();
    if (recorded && previous && ![previous.nonce, previous.inheritedLockNonce].includes(recorded.nonce)) throw Error();
    if (previous?.state === 'active' && !dead(previous)) throw Error();
    if (!previous && recorded && !dead(recorded)) throw Error();
  } catch { throw Error('Preparation is already active or has an unknown outcome; inspect its preparation receipt before retrying'); }
  const owner = {version: 1, root, common, key, pid: process.pid, host: os.hostname(), nonce: crypto.randomUUID(), state: 'active', inheritedLockNonce: recorded?.nonce};
  const object = value => {
    const result = spawnSync('git', ['hash-object', '-w', '--stdin'], {cwd: root, input: JSON.stringify(value), encoding: 'utf8', windowsHide: true});
    if (result.status !== 0) throw Error('Cannot persist preparation ownership');
    return result.stdout.trim();
  };
  const active = object(owner);
  git(root, ['update-ref', ref, active, old]);
  write(lock, owner);
  return {owner, release() {
    // Remove the advisory file while the authoritative lease is still held.
    if (fs.existsSync(lock) && read(lock).nonce === owner.nonce) fs.unlinkSync(lock);
    git(root, ['update-ref', ref, object({...owner, state: 'released'}), active]);
  }};
}
// Runs in a separate process: Git preparation must never block the editor loop.
export function prepare(request) {
  if (!path.isAbsolute(request.workspace) || !Number.isSafeInteger(request.issue) || request.issue < 1 ||
      !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(request.requestId)) throw Error('Invalid production Issue/workspace binding');
  if (!Number.isSafeInteger(request.capacity) || request.capacity < 1 || request.nativeWorkspaceWrite !== true)
    throw Error('Enable independent CLI execution and enter a positive integer capacity');
  if (typeof request.authorityRef !== 'string' || !request.authorityRef.trim()) throw Error('Explicit native execution authority is required');
  if (!request.model || !request.discoveredModels?.some(m => m.id === request.model))
    throw Error('Selected model is absent from the current discovered catalog; refresh models and select again');
  for (const field of ['python', 'executable']) {
    if (!path.isAbsolute(request[field] || '') || !fs.statSync(request[field]).isFile()) throw Error(`Configure a valid ${field} executable`);
  }
  if (!Array.isArray(request.orders) || !request.orders.length || new Set(request.orders).size !== request.orders.length ||
      request.orders.some(order => !Number.isSafeInteger(order) || order < 1)) throw Error('Invalid or duplicate production orders');
  const root = fs.realpathSync(request.workspace);
  if (fs.realpathSync(git(root, ['rev-parse', '--show-toplevel'])) !== root) throw Error('Workspace must be a repository root');
  const design = fs.readFileSync(path.join(root, 'design-docs', request.requestId + '.md'));
  if (digest(design) !== request.designSha256) throw Error('Confirmed design changed; reconfirm the design before continuing');
  const head = git(root, ['rev-parse', 'HEAD']);
  // Configuration is not an authentication receipt. Query the actual CLI before creating copies.
  if (request.backend !== 'codex' && request.backend !== 'codebuddy') throw Error('This connection has no parallel CLI adapter; ordinary serial chat remains available');
  if (request.backend === 'codex') {
    const login = spawnSync(/\.[cm]?js$/.test(request.executable) ? request.node : request.executable, [...(/\.[cm]?js$/.test(request.executable) ? [request.executable] : []), 'login', 'status'], {cwd: root, encoding: 'utf8', windowsHide: true, timeout: 15000});
    if (login.status !== 0) throw Error('CLI login status failed or timed out; reconnect the selected account and continue');
  }
  if (!path.isAbsolute(request.node || '') || !path.isAbsolute(request.modelBridge || '')) throw Error('Configure the existing CLI model discovery adapter');
  const entry = request.backend === 'codex' ? request.executable : request.cliEntry;
  const discovery = spawnSync(request.node, [request.modelBridge, 'models', entry], {cwd: root, encoding: 'utf8', windowsHide: true, timeout: 40000});
  if (discovery.status !== 0) throw Error('CLI model discovery failed; reconnect or refresh the selected connection before continuing');
  let liveModels;
  try { liveModels = JSON.parse(discovery.stdout).models; } catch { throw Error('CLI returned invalid model discovery data'); }
  if (!liveModels?.some(model => model.id === request.model)) throw Error('Selected model is no longer available in CLI discovery; refresh and select again');
  // Independent copies add a private directory prefix to existing repo paths.
  // Git for Windows otherwise rejects valid paths beyond MAX_PATH. Keep this
  // setting local to the authorized repository so workers and later verification
  // use the same support; do not change the user's global Git configuration.
  if (process.platform === 'win32') git(root, ['config', '--local', 'core.longpaths', 'true']);
  const common = fs.realpathSync(path.resolve(root, git(root, ['rev-parse', '--git-common-dir'])));
  const key = digest(JSON.stringify([request.issue, request.requestId, request.designSha256])).slice(0, 24);
  const directory = path.join(path.dirname(common), 'data-collection', 'outbox', 'production-setup-' + key);
  fs.mkdirSync(directory, {recursive: true});
  const lock = path.join(directory, 'preparing.lock');
  const lease = acquire(root, common, key, lock);
  try {
    // Pin working files without changing HEAD or the user's actual index. This
    // includes the editor's just-created design and work order source records.
    const index = path.join(directory, 'snapshot-' + crypto.randomUUID() + '.index');
    const env = {...process.env, GIT_INDEX_FILE: index};
    let tree;
    try {
      const stage = () => {
        const files = spawnSync('git', ['ls-files', '--cached', '--others', '--exclude-standard', '-z'], {cwd: root, env, encoding: 'utf8', windowsHide: true});
        if (files.status !== 0) throw Error('Cannot enumerate current production inputs');
        const names = [...new Set(files.stdout.split('\0').filter(name => name && !name.startsWith('data-collection/outbox/')))];
        if (!names.length) return;
        const added = spawnSync('git', ['add', '-A', '--pathspec-from-file=-', '--pathspec-file-nul'], {cwd: root, env: {...env, GIT_LITERAL_PATHSPECS: '1'}, input: names.join('\0') + '\0', encoding: 'utf8', windowsHide: true});
        if (added.status !== 0) throw Error('Cannot capture production inputs: ' + added.stderr);
      };
      git(root, ['read-tree', 'HEAD'], env);
      stage();
      tree = git(root, ['write-tree'], env);
      stage();
      if (git(root, ['write-tree'], env) !== tree || git(root, ['rev-parse', 'HEAD']) !== head)
        throw Error('Workspace changed while capturing production inputs; wait for the current writer and continue');
    } finally { fs.rmSync(index, {force: true}); }
    const designPath = 'design-docs/' + request.requestId + '.md';
    // Confirmation pins exact working bytes; the snapshot stores Git's clean
    // representation, which may differ for CRLF, encoding or configured filters.
    // Hash those confirmed bytes with the same path conversion used by git add.
    const capturedDesign = git(root, ['rev-parse', tree + ':' + designPath]);
    const confirmedBlob = spawnSync('git', ['hash-object', '--path=' + designPath, '--stdin'], {cwd: root, input: design, windowsHide: true});
    if (confirmedBlob.status !== 0 || confirmedBlob.stdout.toString('utf8').trim() !== capturedDesign ||
        digest(fs.readFileSync(path.join(root, designPath))) !== request.designSha256) throw Error('Design changed during snapshot; reconfirm before continuing');
    const receiptPath = path.join(directory, 'receipt.json');
    const receipt = fs.existsSync(receiptPath) ? read(receiptPath) : {head, tree, snapshot: git(root, ['commit-tree', tree, '-p', head, '-m', 'Private editor production snapshot ' + request.requestId]), designSha256: request.designSha256, jobs: []};
    if (git(root, ['rev-parse', receipt.snapshot + '^{tree}']) !== receipt.tree ||
        git(root, ['rev-parse', receipt.snapshot + '^']) !== receipt.head)
      throw Error('Preparation pinned snapshot changed; reconcile before continuing');
    const changedInputs = receipt.tree !== tree ? git(root, ['diff', '--name-only', receipt.tree, tree, '--', '.', ':(exclude)data-collection', ':(exclude)gonggong-diting-data']) : '';
    if (receipt.head !== head || changedInputs || receipt.designSha256 !== request.designSha256) throw Error('Preparation baseline changed; reconcile existing copies before preparing again');
    write(receiptPath, receipt);
    for (const order of request.orders) {
      const worktree = path.join(directory, 'order-' + order);
      const branch = 'codex/production-' + key + '-' + order;
      let job = receipt.jobs.find(j => j.order === order);
      if (!job) {
        if (fs.existsSync(worktree) || git(root, ['branch', '--list', branch])) throw Error(`Order ${order}: path or branch already exists without this preparation receipt`);
        job = {order, worktree, branch, common, snapshot: receipt.snapshot, owner: lease.owner, state: 'intent', capabilities: ['coding'], dependsOn: []};
        receipt.jobs.push(job); write(receiptPath, receipt);
      }
      if (job.worktree !== worktree || job.branch !== branch || !['intent', 'ready'].includes(job.state)) throw Error(`Order ${order}: preparation receipt identity changed; reconcile before continuing`);
      if (job.state === 'intent') {
        const exists = fs.existsSync(worktree);
        const branchExists = !!git(root, ['branch', '--list', branch]);
        if (job.owner?.nonce !== lease.owner.nonce && (!dead(job.owner) || job.owner.root !== root || job.owner.common !== common ||
            job.owner.key !== key || job.common !== common || job.snapshot !== receipt.snapshot))
          throw Error(`Order ${order}: interrupted preparation has unknown or live ownership`);
        if (exists || branchExists) {
          if (!exists || !branchExists || fs.realpathSync(git(worktree, ['rev-parse', '--show-toplevel'])) !== fs.realpathSync(worktree) ||
              fs.realpathSync(path.resolve(worktree, git(worktree, ['rev-parse', '--git-common-dir']))) !== common ||
              git(worktree, ['symbolic-ref', '--short', 'HEAD']) !== branch || git(worktree, ['rev-parse', 'HEAD']) !== receipt.snapshot ||
              git(worktree, ['status', '--porcelain', '--untracked-files=all', '--ignored']))
            throw Error(`Order ${order}: interrupted worktree identity or contents changed; preserve for reconciliation`);
        } else {
          // Persist intent before Git can create the branch or worktree.
          job.owner = lease.owner; write(receiptPath, receipt);
          git(root, ['worktree', 'add', '-b', branch, worktree, receipt.snapshot]);
        }
        // The runner binds the user's exact confirmation, not Git-normalized
        // bytes. Restore that representation only in this still-owned intent.
        // A resumed intent must contain either the expected checkout or those
        // already-restored bytes; preserve every other value for reconciliation.
        const workerDesign = path.join(worktree, designPath);
        const checkoutDesign = spawnSync('git', ['cat-file', '--filters', '--path=' + designPath, capturedDesign], {cwd: worktree, windowsHide: true});
        const actualDesign = fs.readFileSync(workerDesign);
        if (checkoutDesign.status !== 0 || (digest(actualDesign) !== request.designSha256 && !actualDesign.equals(checkoutDesign.stdout)))
          throw Error(`Order ${order}: interrupted design bytes changed; preserve for reconciliation`);
        if (digest(actualDesign) !== request.designSha256) {
          const stagedDesign = path.join(directory, 'design-' + crypto.randomUUID() + '.tmp');
          const fd = fs.openSync(stagedDesign, 'wx', 0o600);
          try { fs.writeFileSync(fd, design); fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
          fs.renameSync(stagedDesign, workerDesign);
        }
        job.state = 'ready'; write(receiptPath, receipt);
      }
      if (fs.realpathSync(git(worktree, ['rev-parse', '--show-toplevel'])) !== fs.realpathSync(worktree) ||
          fs.realpathSync(path.resolve(worktree, git(worktree, ['rev-parse', '--git-common-dir']))) !== common ||
          git(worktree, ['symbolic-ref', '--short', 'HEAD']) !== branch) throw Error(`Order ${order}: recorded worktree identity changed; reconcile its worker`);
    }
    const config = {nativeWorkspaceWrite: true, authorityRef: request.authorityRef, capacity: request.capacity, python: request.python,
      models: [{id: request.model, available: true, targets: ['agent'], capabilities: ['coding'], preference: 1}],
      jobs: receipt.jobs.map(({state, branch, common, snapshot, owner, ...job}) => job)};
    if (request.backend === 'codex') config.codex = request.executable;
    else config.workerCommand = {executable: request.executable, args: [request.cliEntry, '--print', '--output-format', 'json', '--model', '{model}', '--tools', 'Read,Glob,Grep,Edit,Write,Bash', '--allowedTools', 'Read,Glob,Grep,Edit,Write,Bash', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}', '--setting-sources', '', '--settings', '{"disableAllHooks":true,"enabledPlugins":{}}', '--no-session-persistence', '--permission-mode', 'default']};
    const configPath = path.join(directory, 'config.json');
    // Do not mutate a configuration already bound to a running worker's receipt.
    const versioned = configPath + '.' + digest(JSON.stringify(config)) + '.json';
    if (!fs.existsSync(versioned)) write(versioned, config);
    return {state: 'ready', config: versioned, receipt: receiptPath};
  } finally { lease.release(); }
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  let result;
  try { result = prepare(read(process.argv[2])); } catch (error) { result = {state: 'blocked', error: error.message}; }
  write(process.argv[3], result);
}
