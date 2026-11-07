'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { spawn, execFile } = require('node:child_process');
const { randomUUID } = require('node:crypto');

function bashExecutable(env = process.env, platform = process.platform) {
    if (platform !== 'win32') return '/bin/bash';
    const candidates = [env.CODEBUDDY_GIT_BASH_PATH, path.resolve(__dirname, "../../project/runtime/git-bash/bin/bash.exe"), path.join(env.ProgramFiles || 'C:/Program Files', 'Git/bin/bash.exe'), path.join(env.LOCALAPPDATA || '', 'Programs/Git/bin/bash.exe')];
    for (const directory of (env.PATH || '').split(path.delimiter)) {
        if (/git[\\/]cmd$/i.test(directory)) candidates.push(path.resolve(directory, '../bin/bash.exe'));
    }
    const executable = candidates.find(candidate => candidate && path.isAbsolute(candidate) && fs.existsSync(candidate));
    if (!executable) throw new Error('Git Bash is unavailable; configure CODEBUDDY_GIT_BASH_PATH. No command was executed.');
    return executable;
}

function terminalArguments(params, workspace) {
    if (!params || typeof params.command !== 'string' || !params.command.trim() || params.command.includes('\0') || params.command.length > 12000 || (params.args !== undefined && (!Array.isArray(params.args) || params.args.length))) throw new Error('Invalid Bash command; pass a complete command string without separate args.');
    if (params.env !== undefined && (!Array.isArray(params.env) || params.env.length)) throw new Error('Terminal environment overrides are not supported.');
    const cwd = params.cwd ?? workspace.workspace_root ?? workspace.project_root;
    if (typeof cwd !== 'string' || !path.isAbsolute(cwd) || cwd.includes('\0') || !fs.statSync(cwd).isDirectory()) throw new Error('An existing absolute terminal working directory is required.');
    const outputByteLimit = params.outputByteLimit ?? 32000;
    if (!Number.isSafeInteger(outputByteLimit) || outputByteLimit < 1 || outputByteLimit > 256 * 1024) throw new Error('Invalid terminal output limit.');
    return { command: params.command, cwd: fs.realpathSync(cwd), outputByteLimit, timeout_seconds: 3600, shell: 'bash' };
}

// Reserved terminal requests are dispatched to Godot, never evaluated by a shell.
function hostActionRequest(command) {
    if (!command.trim().startsWith('godot-host-action')) return null;
    const text = command.trim();
    const plain = /^godot-host-action (read_logs|get_parent_context|get_editor_state|build_engine|restart_engine|rollback_engine)$/.exec(text);
    if (plain) return { name: plain[1], arguments: {} };
    const action = /^godot-host-action (editor_action|route_engine_message) ([\s\S]{2,32768})$/.exec(text);
    if (action) {
        let args;
        try { args = JSON.parse(action[2]); } catch (_) { throw new Error('Godot host action requires one valid JSON object.'); }
        if (!args || typeof args !== 'object' || Array.isArray(args)) throw new Error('Godot host action requires one valid JSON object.');
        return { name: action[1], arguments: args };
    }
    throw new Error('Invalid Godot host action. Shell operators and other arguments are forbidden.');
}

function hostActionName(command) { return hostActionRequest(command)?.name ?? null; }

function redactOutput(text, env) {
    for (const [name, value] of Object.entries(env)) {
        if (/(?:key|token|secret|password|credential)/i.test(name) && typeof value === 'string' && value.length >= 6) text = text.split(value).join('[REDACTED]');
    }
    return text.replace(/((?:authorization\s*:\s*bearer|api[_-]?key|access[_-]?token|password|secret)\s*[=:]?\s*)[^\s"']+/gi, '$1[REDACTED]');
}

// Only expose numeric progress and fixed stage names, never arbitrary command output.
function createBuildProgress() {
    const partial = { stdout: '', stderr: '' };
    let state = { stage: 'running', units: 0 };
    const line = text => {
        text = text.replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, '').trim();
        let match;
        if ((match = /^\[godot-build-progress\] (\d+)\|(\d+)$/.exec(text))) {
            const completed = Number(match[1]), total = Number(match[2]);
            if (Number.isSafeInteger(completed) && Number.isSafeInteger(total) && completed >= 0 && total >= 0) {
                state = { ...state, completed, total, source: 'estimated', ...(total > 0 ? { percent: Math.min(99, Math.floor(completed * 100 / total)) } : { percent: undefined }) };
            }
        } else if ((match = /^\[header-docs-progress\] [^|\r\n]+\|(\d+)\|(\d+)\|/.exec(text))) {
            const completed = Number(match[1]), total = Number(match[2]);
            if (Number.isSafeInteger(completed) && Number.isSafeInteger(total) && total > 0 && completed <= total) state = { ...state, stage: 'documenting', completed, total, percent: Math.floor(completed * 100 / total), source: 'reported' };
        } else if ((match = /^\[\s*(\d+)\s*\/\s*(\d+)\s*\]/.exec(text))) {
            const completed = Number(match[1]), total = Number(match[2]);
            if (Number.isSafeInteger(completed) && Number.isSafeInteger(total) && total > 0 && completed <= total) state = { ...state, stage: 'building', completed, total, percent: Math.floor(completed * 100 / total), source: 'reported' };
        } else if ((match = /^\[\s*(\d{1,3})%\]/.exec(text)) && Number(match[1]) <= 100) {
            state = { ...state, stage: 'building', percent: Number(match[1]), source: 'reported', completed: undefined, total: undefined };
        }
        if (/^(?:Compiling |Building (?:C|CXX) object )/.test(text)) state = { ...state, stage: 'compiling', units: state.units + 1 };
        else if (/^(?:Linking |Generating .*\.lib)/.test(text)) state = { ...state, stage: 'linking' };
        else if (/^scons: Reading SConscript files/.test(text)) state = { ...state, stage: 'scanning' };
    };
    return {
        append(bytes, stream = 'stdout') {
            const text = partial[stream] + bytes.toString('utf8');
            const lines = text.split(/[\r\n]/);
            partial[stream] = lines.pop().slice(-4096);
            for (const text of lines) line(text);
        },
        snapshot() { return { ...state }; },
    };
}

function createTerminals({ approve, validate, hostAction, stateChanged = () => {}, finished = () => {}, progress = () => {}, env = process.env, timeoutMs = 3600000, progressIntervalMs = 1000 }) {
    const terminals = new Map();
    let closed = false;
    const get = params => {
        validate(params);
        const terminal = terminals.get(params.terminalId);
        if (!terminal) throw new Error('Unknown or released Godot terminal.');
        return terminal;
    };
    const kill = async terminal => {
        if (terminal.status) return;
        if (process.platform === 'win32') {
            await new Promise((resolve, reject) => execFile(path.join(env.SystemRoot || 'C:/Windows', 'System32/taskkill.exe'), ['/PID', String(terminal.child.pid), '/T', '/F'], { windowsHide: true }, error => {
                if (error && !terminal.status) reject(new Error('Could not terminate terminal process tree.')); else resolve();
            }));
        } else {
            try { process.kill(-terminal.child.pid, 'SIGKILL'); } catch (error) { if (error.code !== 'ESRCH') throw error; }
        }
        await terminal.exit;
    };
    return {
        get running() { return [...terminals.values()].filter(terminal => !terminal.status).length; },
        async create(params, workspace) {
            validate(params);
            if (closed || terminals.size >= 8) throw new Error('Godot terminal capacity exceeded or session closed.');
            const args = terminalArguments(params, workspace);
            const request = hostActionRequest(args.command);
            if (request) {
                if (!hostAction) throw new Error('Godot host action is unavailable. No shell command was executed.');
                const result = await hostAction(request.name, request.arguments, args.command);
                validate(params);
                if (closed || terminals.size >= 8) throw new Error('Godot terminal session closed or capacity exceeded.');
                if (!result || typeof result.ok !== 'boolean') throw new Error('Godot did not confirm the host action result.');
                const id = 'godot_host_terminal_' + randomUUID();
                const status = { exitCode: result.ok ? 0 : 1, _meta: { timed_out: false, start_failed: false } };
                const bytes = Buffer.from(JSON.stringify(result));
                // Log and parent-context snapshots are bounded by Godot. Keep
                // the JSON envelope intact even for escaped or non-ASCII text.
                const outputByteLimit = ['read_logs', 'get_parent_context', 'get_editor_state', 'editor_action', 'route_engine_message'].includes(request.name) ? 256 * 1024 : args.outputByteLimit;
                const terminal = { status, exit: Promise.resolve(status), output: bytes.subarray(Math.max(0, bytes.length - outputByteLimit)), truncated: bytes.length > outputByteLimit };
                terminals.set(id, terminal);
                finished({ terminalId: id, exit_status: status, timed_out: false, output_truncated: terminal.truncated, output: redactOutput(terminal.output.toString('utf8'), env) });
                return { terminalId: id };
            }
            const executable = bashExecutable(env);
            const approved = await approve(args);
            validate(params);
            if (closed || approved?.approved !== true) throw new Error('User rejected command. No command was executed. Do not retry or bypass the rejection.');
            if (terminals.size >= 8) throw new Error('Godot terminal capacity exceeded. No command was executed.');
            const id = 'godot_terminal_' + randomUUID();
            const restricted = process.platform === 'darwin' && workspace.command_profile;
            if (restricted && (typeof approved.command_profile !== 'string' || !approved.command_profile)) throw new Error('Godot did not refresh candidate command protection. No command was executed.');
            const child = spawn(restricted ? '/usr/bin/sandbox-exec' : executable, [...(restricted ? ['-p', approved.command_profile, executable] : []), '--noprofile', '--norc', '-c', args.command], { cwd: args.cwd, env: { ...env, CHERE_INVOKING: '1', GODOT_AI_CHAT_PROGRESS: '1' }, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true, detached: process.platform !== 'win32' });
            const terminal = { child, output: Buffer.alloc(0), truncated: false, status: null, timedOut: false, timer: null, progressTimer: null, started: Date.now(), lastOutput: Date.now(), bytes: 0, build: createBuildProgress() };
            terminals.set(id, terminal);
            const report = () => progress({ terminal_id: id, elapsed_ms: Date.now() - terminal.started, idle_ms: Date.now() - terminal.lastOutput, output_bytes: terminal.bytes, running: [...terminals.values()].filter(item => !item.status).length, ...terminal.build.snapshot() });
            terminal.exit = new Promise(resolve => {
                const append = (bytes, stream) => {
                    terminal.lastOutput = Date.now();
                    terminal.bytes += bytes.length;
                    terminal.build.append(bytes, stream);
                    terminal.output = Buffer.concat([terminal.output, bytes]);
                    if (terminal.output.length > args.outputByteLimit) { terminal.truncated = true; terminal.output = terminal.output.subarray(terminal.output.length - args.outputByteLimit); }
                };
                child.stdout.on('data', bytes => append(bytes, 'stdout'));
                child.stderr.on('data', bytes => append(bytes, 'stderr'));
                child.once('error', () => { terminal.startFailed = true; });
                child.once('close', (exitCode, signal) => {
                    clearTimeout(terminal.timer);
                    clearInterval(terminal.progressTimer);
                    terminal.build.append(Buffer.from('\n'), 'stdout');
                    terminal.build.append(Buffer.from('\n'), 'stderr');
                    terminal.status = { ...(Number.isInteger(exitCode) && !terminal.startFailed ? { exitCode } : {}), ...(signal ? { signal } : {}), _meta: { timed_out: terminal.timedOut, start_failed: !!terminal.startFailed } };
                    report();
                    stateChanged();
                    finished({ terminalId: id, exit_status: terminal.status, timed_out: terminal.timedOut, output_truncated: terminal.truncated, output: redactOutput(terminal.output.toString('utf8'), env) });
                    resolve(terminal.status);
                });
            });
            terminal.timer = setTimeout(() => { terminal.timedOut = true; kill(terminal).catch(() => child.kill()); }, timeoutMs);
            terminal.timer.unref();
            terminal.progressTimer = setInterval(report, progressIntervalMs);
            terminal.progressTimer.unref();
            report();
            stateChanged();
            return { terminalId: id };
        },
        output(params) {
            const terminal = get(params);
            return { output: redactOutput(terminal.output.toString('utf8'), env), truncated: terminal.truncated, ...(terminal.status ? { exitStatus: terminal.status } : {}) };
        },
        wait(params) { return get(params).exit; },
        async kill(params) { await kill(get(params)); return {}; },
        async release(params) { const terminal = get(params); await kill(terminal); terminals.delete(params.terminalId); return {}; },
        async reset() { await Promise.all([...terminals.values()].map(kill)); terminals.clear(); },
        async close() {
            closed = true;
            const results = await Promise.allSettled([...terminals].map(async ([id, terminal]) => { await kill(terminal); terminals.delete(id); }));
            if (results.some(result => result.status === 'rejected')) throw new Error('Terminal process-tree cleanup failed; unconfirmed processes remain tracked.');
        },
    };
}

module.exports = { bashExecutable, terminalArguments, hostActionName, hostActionRequest, createTerminals, redactOutput };
