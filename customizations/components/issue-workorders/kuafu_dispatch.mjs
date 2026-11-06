import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {operatorStateRoot} from '../codex-dispatch/operator.mjs';

const script = fileURLToPath(new URL('./kuafu_incident.py', import.meta.url));
const install = fileURLToPath(new URL('../../../', import.meta.url));
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const failures = new Set(['failed', 'validation_failed', 'reconcile_required']);
const blockingReasons = new Set(['host_revalidation_failed', 'source_snapshot_missing', 'unsupported_target',
  'chat_creation_not_authorized', 'required_model_or_capabilities_unavailable']);
const errorTickets = new WeakMap();

export function hostPython() {
  if (process.env.GONGGONG_PYTHON) return process.env.GONGGONG_PYTHON;
  if (process.platform !== 'win32') return 'python3';
  const probe = execFileSync('powershell.exe', ['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',
    path.join(install,'tools/run_issue_gate.ps1'), '-ProbeOnly'], {encoding:'utf8', windowsHide:true, timeout:30000});
  return JSON.parse(probe).python;
}

function boundWorkspace(config) {
  const root = fs.realpathSync(config.workspace);
  const git = (...args) => execFileSync('git',['-C', root, ...args], {encoding:'utf8', timeout:30000}).trim();
  const repository = read(path.join(install,'work-items.json')).repository;
  if (fs.realpathSync(git('rev-parse','--show-toplevel')) !== root || config.repository !== repository ||
      read(path.join(root,'work-items.json')).repository !== repository) throw Error('Workspace binding mismatch');
  const origin = git('remote','get-url','origin').replace(/\.git$/i, '').toLowerCase();
  if (!['https://github.com/', 'git@github.com:', 'ssh://git@github.com/'].some(prefix =>
      origin === prefix + repository.toLowerCase())) throw Error('Repository origin mismatch');
  return root;
}

function capture(config, binding, reason) {
  try {
    const workspace = boundWorkspace(config);
    const digest = createHash('sha256').update(String(reason)).digest('hex');
    // Only execute the install's toolchain. A rejected input may name an arbitrary executable.
    const output = execFileSync(hostPython(), [script, '--repo', workspace, 'detect', '--issue', String(binding.number),
      '--request-id', binding.requestId, '--action', 'dispatch', '--evidence', digest],
      {encoding:'utf8', timeout:30000, windowsHide:true});
    process.stderr.write(output);
  } catch {
    console.error(JSON.stringify({state:'kuafu_intake_unavailable', issue:binding.number, action:'dispatch'}));
  }
}

export async function ticketOperation(ticket, operation) {
  try {return await operation();}
  catch (error) {
    if (error instanceof Error) errorTickets.set(error, ticket);
    throw error;
  }
}

export async function reservationOperation(config, operation) {
  try {return await operation();}
  catch (error) {
    let ticket = null;
    try {
      if (/^[a-f0-9]{64}$/.test(config.reservationKey)) {
        const root = await operatorStateRoot(boundWorkspace(config));
        const {assignment} = read(path.join(root,'dispatch','reservations', config.reservationKey + '.json'));
        if (assignment.key === config.reservationKey) ticket = assignment.ticket;
      }
    } catch { /* No verified reservation mapping. */ }
    if (error instanceof Error) errorTickets.set(error, ticket);
    throw error;
  }
}

function errorTicket(config, error) {
  if (errorTickets.has(error)) return errorTickets.get(error);
  if (config.action && config.action !== 'dispatch') return null;
  const tickets = new Set((config.requests ?? []).map(r => r.ticket));
  return tickets.size === 1 ? [...tickets][0] : null;
}

export async function withBlockerRouting(config, operation, notify = capture) {
  const bindings = Array.isArray(config?.bindings) ? config.bindings : [];
  const bindingFor = ticket => {
    const found = bindings.filter(b => ticket === `github:${config.repository}#${b.number}`);
    return found.length === 1 ? found[0] : null;
  };
  let result;
  try {
    result = await operation();
  } catch (error) {
    let binding;
    try {binding = bindingFor(errorTicket(config, error));} catch { /* no authenticated ticket */ }
    if (binding) notify(config, binding, error.message);
    else console.error(JSON.stringify({state:'kuafu_dispatch_unattributed', action:'dispatch'}));
    throw error;
  }
  for (const item of [...(result?.results ?? []), ...(result?.deferred ?? [])]) {
    if (!failures.has(item.state) && !blockingReasons.has(item.reason)) continue;
    const binding = bindingFor(item.ticket);
    if (binding) notify(config, binding, item.reason ?? item.state);
  }
  return result;
}
