'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { spawn } = require('node:child_process');
const { terminalArguments, hostActionName, createTerminals, redactOutput } = require('../../tools/codebuddy_cli/godot_terminal');

function fixture(t, overrides = {}) {
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'godot-terminal-test-'));
    const manager = createTerminals({ approve: async () => ({ approved: true }), validate: params => assert.equal(params.sessionId, 'test'), ...overrides });
    t.after(async () => { await manager.close(); fs.rmSync(directory, { recursive: true, force: true }); });
    return { directory, manager, workspace: { project_root: directory } };
}

test('Semantic editor requests retain structured arguments and never reach the shell', async t => {
    const { hostActionRequest } = require('../../tools/codebuddy_cli/godot_terminal');
    assert.deepEqual(hostActionRequest('godot-host-action get_editor_state'), { name: 'get_editor_state', arguments: {} });
    const routed = { intent: 'engine_operation', request_id: 'new-page', operation: { action: 'set_text', target: 'editor.input', value: '你好' } };
    assert.deepEqual(hostActionRequest('godot-host-action route_engine_message ' + JSON.stringify(routed)), { name: 'route_engine_message', arguments: routed });
    assert.throws(() => hostActionRequest('godot-host-action route_engine_message {} && echo bypass'));
    const args = { action: 'start_guidance', steps: [{ target: 'project_settings', message: '窗口配置' }] };
    const command = 'godot-host-action editor_action ' + JSON.stringify(args);
    let received;
    const { manager, workspace } = fixture(t, {
        env: {},
        approve: () => { throw new Error('Semantic requests must not run through shell approval'); },
        hostAction: async (name, value) => { received = value; return { ok: true, action: name, status: 'preview' }; },
    });
    const terminal = await manager.create({ sessionId: 'test', command }, workspace);
    const params = { sessionId: 'test', terminalId: terminal.terminalId };
    assert.deepEqual(received, args);
    assert.equal((await manager.wait(params)).exitCode, 0);
    assert.equal(JSON.parse(manager.output(params).output).status, 'preview');
    for (const invalid of ['[]', 'null', '{}; exit 0', '{} && exit 0']) {
        assert.throws(() => hostActionRequest('godot-host-action editor_action ' + invalid));
    }
    await manager.release(params);
    const disabled = fixture(t, { validate: () => { throw new Error('permission disabled'); } });
    await assert.rejects(disabled.manager.create({ sessionId: 'test', command }, disabled.workspace), /permission disabled/);
});

test('Terminal validates commands, cwd and unsupported args/env before approval', t => {
    const { directory, workspace } = fixture(t);
    const base = { sessionId: 'test', command: 'printf ok' };
    assert.equal(terminalArguments(base, workspace).cwd, fs.realpathSync(directory));
    for (const changes of [{ command: '' }, { command: 'bad\0command' }, { command: 'x'.repeat(12001) }, { args: ['ignored'] }, { env: [{ name: 'SECRET', value: 'ignored' }] }, { cwd: 'relative' }, { outputByteLimit: 0 }, { outputByteLimit: 300000 }]) assert.throws(() => terminalArguments({ ...base, ...changes }, workspace));
});

test('Actual delivery terminals admit bounded UTF-8 host JSON while shell and UI limits remain unchanged', async t => {
    let hostCalls = 0;
    const { manager, workspace } = fixture(t, {
        env: {},
        approve: () => { throw new Error('Reserved delivery must not request shell approval or spawn'); },
        hostAction: async (name, args) => { hostCalls++; assert.equal(name, 'complete_delivery'); return { ok: false, evidence_bytes: Buffer.byteLength(args.evidence, 'utf8') }; },
    });
    const prefix = 'godot-host-action complete_delivery ';
    const overhead = Buffer.byteLength(JSON.stringify({ evidence: '' }), 'utf8');
    for (const evidence of ['中'.repeat(17000), 'x'.repeat(65536 - overhead)]) {
        const command = prefix + JSON.stringify({ evidence });
        assert(command.length > 12000);
        const terminal = await manager.create({ sessionId: 'test', command }, workspace);
        const params = { sessionId: 'test', terminalId: terminal.terminalId };
        assert.equal((await manager.wait(params)).exitCode, 1);
        assert.equal(JSON.parse(manager.output(params).output).evidence_bytes, Buffer.byteLength(evidence, 'utf8'));
        await manager.release(params);
    }
    for (const command of [prefix + JSON.stringify({ evidence: '中'.repeat(22000) }), prefix + JSON.stringify({ evidence: 'x'.repeat(65537 - overhead) }), prefix + '{} && echo forbidden', 'x'.repeat(12001), 'godot-host-action editor_action ' + JSON.stringify({ value: 'x'.repeat(13000) })]) {
        await assert.rejects(manager.create({ sessionId: 'test', command }, workspace));
    }
    assert.equal(hostCalls, 2);
    assert.equal(manager.running, 0);
});

test('No process starts while confirmation is pending or rejected', async t => {
    let resolve;
    const { directory, manager, workspace } = fixture(t, { approve: () => new Promise(done => { resolve = done; }) });
    const creation = manager.create({ sessionId: 'test', command: 'printf forbidden > forbidden.txt' }, workspace);
    assert.equal(manager.running, 0);
    assert(!fs.existsSync(path.join(directory, 'forbidden.txt')));
    resolve({ approved: false });
    await assert.rejects(creation, /rejected/);
    assert.equal(manager.running, 0);
    assert(!fs.existsSync(path.join(directory, 'forbidden.txt')));
});

test('Active work orders require the host guard and wait for its actual result', async t => {
    const missing = fixture(t);
    missing.workspace.provenance_guard_required = true;
    await assert.rejects(missing.manager.create({ sessionId: 'test', command: 'printf forbidden > missing.txt' }, missing.workspace), /did not provide/);
    assert(!fs.existsSync(path.join(missing.directory, 'missing.txt')));
    let guard;
    const run = fixture(t, { approve: async () => ({ approved: true, provenance_guard: guard }) });
    const worker = path.join(run.directory, 'guard.js');
    const binding = path.join(run.directory, 'binding.json');
    fs.writeFileSync(worker, "process.stderr.write('GONGGONG_PROVENANCE_GUARD {\\\"ok\\\":false}\\n');process.exit(76);\n");
    fs.writeFileSync(binding, '{}');
    guard = { protocol: 1, python: process.execPath, worker, binding };
    run.workspace.provenance_guard_required = true;
    const terminal = await run.manager.create({ sessionId: 'test', command: 'printf forbidden > blocked.txt' }, run.workspace);
    const params = { sessionId: 'test', terminalId: terminal.terminalId };
    assert.equal((await run.manager.wait(params)).exitCode, 76);
    assert(run.manager.output(params).output.includes('GONGGONG_PROVENANCE_GUARD'));
    assert(!fs.existsSync(path.join(run.directory, 'blocked.txt')));
    await run.manager.release(params);
});

test('Cancel waits for the active provenance worker to acknowledge its marker', async t => {
    let guard;
    const run = fixture(t, { approve: async () => ({ approved: true, provenance_guard: guard }) });
    const worker = path.join(run.directory, 'cancel-worker.js');
    const binding = path.join(run.directory, 'binding.json');
    const ready = path.join(run.directory, 'ready');
    fs.writeFileSync(binding, '{}');
    fs.writeFileSync(worker, `const fs=require('node:fs'); const args=process.argv; const marker=args[args.indexOf('--cancel-file')+1]; fs.writeFileSync(${JSON.stringify(ready)},'ready'); setInterval(()=>{if(fs.existsSync(marker)){process.stdout.write('cancel_verified');process.exit(143);}},20);`);
    guard = { protocol: 1, python: process.execPath, worker, binding };
    run.workspace.provenance_guard_required = true;
    const terminal = await run.manager.create({ sessionId: 'test', command: 'sleep 20' }, run.workspace);
    const params = { sessionId: 'test', terminalId: terminal.terminalId };
    for (let attempt = 0; attempt < 100 && !fs.existsSync(ready); attempt++) await new Promise(resolve => setTimeout(resolve, 20));
    assert(fs.existsSync(ready));
    await run.manager.kill(params);
    assert.equal((await run.manager.wait(params)).exitCode, 143);
    assert(run.manager.output(params).output.includes('cancel_verified'));
    await run.manager.release(params);
});

test('Cancel marker failures still terminate the worker and settle its result', async t => {
    let guard;
    const run = fixture(t, { approve: async () => ({ approved: true, provenance_guard: guard }) });
    const worker = path.join(run.directory, 'cancel-failure-worker.js');
    const binding = path.join(run.directory, 'binding.json');
    const ready = path.join(run.directory, 'ready');
    fs.writeFileSync(binding, '{}');
    fs.writeFileSync(worker, `const fs=require('node:fs'); fs.writeFileSync(${JSON.stringify(ready)},'ready'); setInterval(()=>{},1000);`);
    guard = { protocol: 1, python: process.execPath, worker, binding };
    run.workspace.provenance_guard_required = true;
    const terminal = await run.manager.create({ sessionId: 'test', command: 'sleep 20' }, run.workspace);
    const params = { sessionId: 'test', terminalId: terminal.terminalId };
    for (let attempt = 0; attempt < 100 && !fs.existsSync(ready); attempt++) await new Promise(resolve => setTimeout(resolve, 20));
    assert(fs.existsSync(ready));
    const write = fs.writeFileSync, remove = fs.rmSync;
    try {
        fs.writeFileSync = (file, ...args) => { if (String(file).includes('godot-provenance-cancel-')) throw new Error('injected marker write failure'); return write(file, ...args); };
        fs.rmSync = (file, ...args) => { if (String(file).includes('godot-provenance-cancel-')) throw new Error('injected marker cleanup failure'); return remove(file, ...args); };
        await run.manager.kill(params);
        const result = await run.manager.wait(params);
        assert.notEqual(result.exitCode, 0);
        assert.equal(result._meta.cancel_cleanup_failed, true);
    } finally {
        fs.writeFileSync = write;
        fs.rmSync = remove;
    }
    await run.manager.release(params);
});

test('Candidate commands use freshly approved protection and reject a missing refresh', { skip: process.platform !== 'darwin' }, async t => {
    const { directory, manager, workspace } = fixture(t, {
        approve: async () => ({ approved: true, command_profile: '(version 1)(allow default)(deny file-write* (subpath ' + JSON.stringify(fs.realpathSync(directory)) + '))' }),
    });
    workspace.command_profile = '(version 1)(allow default)';
    const terminal = await manager.create({ sessionId: 'test', command: 'printf forbidden > blocked.txt' }, workspace);
    const params = { sessionId: 'test', terminalId: terminal.terminalId };
    assert.notEqual((await manager.wait(params)).exitCode, 0);
    assert(!fs.existsSync(path.join(directory, 'blocked.txt')));
    await manager.release(params);
    const missing = fixture(t);
    missing.workspace.command_profile = '(version 1)(allow default)';
    await assert.rejects(missing.manager.create({ sessionId: 'test', command: 'printf forbidden > missing.txt' }, missing.workspace), /did not refresh candidate/);
    assert(!fs.existsSync(path.join(missing.directory, 'missing.txt')));
});

test('Reserved host actions never execute a shell and preserve success and refusal', async t => {
    for (const name of ['read_logs', 'build_engine', 'restart_engine', 'rollback_engine']) assert.equal(hostActionName('godot-host-action ' + name), name);
    assert.equal(hostActionName('printf ok'), null);
    for (const command of ['godot-host-action unknown', 'godot-host-action build_engine; exit 0', 'godot-host-action build_engine && exit 0', 'godot-host-action build_engine --restart']) assert.throws(() => hostActionName(command));
    let calls = 0;
    const { manager, workspace } = fixture(t, {
        env: { CODEBUDDY_GIT_BASH_PATH: 'missing' },
        approve: () => { throw new Error('Host actions must use host approval, not shell approval'); },
        hostAction: async name => ({ ok: ++calls === 1, action: name, restarted: false }),
    });
    for (const success of [true, false]) {
        const terminal = await manager.create({ sessionId: 'test', command: 'godot-host-action build_engine' }, workspace);
        const params = { sessionId: 'test', terminalId: terminal.terminalId };
        assert.equal((await manager.wait(params)).exitCode, success ? 0 : 1);
        assert.equal(JSON.parse(manager.output(params).output).ok, success);
        assert.equal(manager.running, 0);
        await manager.release(params);
    }
    assert.equal(calls, 2);
    const unavailable = fixture(t);
    await assert.rejects(unavailable.manager.create({ sessionId: 'test', command: 'godot-host-action build_engine' }, unavailable.workspace), /unavailable/);
});


test('On-demand editor logs are read-only host requests, not shell execution', async t => {
    const logs = 'LOG_SNAPSHOT\n' + '数据\n'.repeat(10000);
    const { manager, workspace } = fixture(t, {
        env: {},
        approve: () => { throw new Error('Reading editor logs must not request execution approval'); },
        hostAction: async name => {
            assert.equal(name, 'read_logs');
            return { ok: true, source: 'editor_output', untrusted: true, logs };
        },
    });
    const terminal = await manager.create({ sessionId: 'test', command: 'godot-host-action read_logs' }, workspace);
    const params = { sessionId: 'test', terminalId: terminal.terminalId };
    assert.equal((await manager.wait(params)).exitCode, 0);
    assert.equal(JSON.parse(manager.output(params).output).logs, logs);
    assert.equal(manager.output(params).truncated, false);
    assert.equal(manager.running, 0);
    await manager.release(params);
    assert.throws(() => hostActionName('godot-host-action read_logs; printf forbidden'));
});

test('Terminal returns true nonzero exit, combined output and bounded tail', async t => {
    const { manager, workspace } = fixture(t);
    const terminal = await manager.create({ sessionId: 'test', command: "printf 'stdout\\n'; printf 'stderr\\n' >&2; exit 7" }, workspace);
    const params = { sessionId: 'test', terminalId: terminal.terminalId };
    assert.equal((await manager.wait(params)).exitCode, 7);
    const result = manager.output(params);
    assert(result.output.includes('stdout') && result.output.includes('stderr'));
    assert.equal(result.exitStatus.exitCode, 7);
    await manager.release(params);
    assert.throws(() => manager.output(params), /released/);
    const tail = await manager.create({ sessionId: 'test', command: "printf '1234567890END'", outputByteLimit: 5 }, workspace);
    const tailParams = { sessionId: 'test', terminalId: tail.terminalId };
    await manager.wait(tailParams);
    assert.equal(manager.output(tailParams).output, '90END');
    assert.equal(manager.output(tailParams).truncated, true);
});

test('Terminal timeout kills execution and never reports success', { timeout: 10000 }, async t => {
    const { manager, workspace } = fixture(t, { timeoutMs: 300 });
    const terminal = await manager.create({ sessionId: 'test', command: 'sleep 20' }, workspace);
    const status = await manager.wait({ sessionId: 'test', terminalId: terminal.terminalId });
    assert.equal(status._meta.timed_out, true);
    assert.notEqual(status.exitCode, 0);
    assert.equal(manager.running, 0);
});

test('Release and reset terminate running commands and allow next turn', { timeout: 10000 }, async t => {
    const { manager, workspace } = fixture(t);
    const terminal = await manager.create({ sessionId: 'test', command: 'sleep 20' }, workspace);
    await manager.release({ sessionId: 'test', terminalId: terminal.terminalId });
    assert.equal(manager.running, 0);
    await manager.create({ sessionId: 'test', command: 'sleep 20' }, workspace);
    await manager.reset();
    assert.equal(manager.running, 0);
    const next = await manager.create({ sessionId: 'test', command: 'exit 0' }, workspace);
    assert.equal((await manager.wait({ sessionId: 'test', terminalId: next.terminalId })).exitCode, 0);
});

test('Terminal output masks known environment credentials', () => {
    assert.equal(redactOutput('prefix PRIVATE_SENTINEL suffix', { API_TOKEN: 'PRIVATE_SENTINEL' }), 'prefix [REDACTED] suffix');
    assert(!redactOutput('Authorization: Bearer PRIVATE_SENTINEL', {}).includes('PRIVATE_SENTINEL'));
});

test('Standard ACP terminal crosses the Godot approval bridge and honors denial/disabled permission', { timeout: 30000 }, async t => {
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'godot-terminal-acp-'));
    const child = spawn(process.execPath, [path.resolve(__dirname, '../../tools/codebuddy_cli/godot_bridge.js'), 'session', path.join(__dirname, 'mock_codebuddy_cli.js')], { env: { ...process.env, GODOT_ACP_LOG_DIRECTORY: path.join(directory, 'logs') }, stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true });
    t.after(() => { child.kill(); fs.rmSync(directory, { recursive: true, force: true }); });
    let partial = '';
    const packets = [];
    child.stdout.setEncoding('utf8');
    child.stdout.on('data', text => { partial += text; let newline; while ((newline = partial.indexOf('\n')) >= 0) { packets.push(JSON.parse(partial.slice(0, newline))); partial = partial.slice(newline + 1); } });
    let stderr = '';
    child.stderr.on('data', bytes => { stderr += bytes.toString(); });
    const wait = async condition => { const deadline = Date.now() + 10000; while (!condition() && Date.now() < deadline) await new Promise(resolve => setTimeout(resolve, 20)); assert(condition(), 'ACP timeout: ' + stderr + JSON.stringify(packets)); };
    let sequence = 0;
    const submit = (messages, rounds, enabled = true) => {
        const file = path.join(directory, String(++sequence) + '.json');
        fs.writeFileSync(file, JSON.stringify({ model: 'mock-model', project_root: directory, available_tools: enabled ? ['run_command', 'build_engine', 'restart_engine', 'rollback_engine'].map(name => ({ type: 'function', function: { name } })) : [], tool_context: { permission_enabled: enabled, tool_rounds: rounds, max_tool_rounds: null }, messages }));
        child.stdin.write(JSON.stringify({ path: file }) + '\n');
    };
    for (const [name, accepted] of [['native_command', true], ['native_command_reject', false], ['host_action', true], ['host_action_reject', false]]) {
        const host = name.startsWith('host_action');
        packets.length = 0;
        submit([{ role: 'user', content: 'case:' + name }], 0);
        await wait(() => packets.some(packet => packet.choices?.[0].message.tool_calls));
        const call = packets.find(packet => packet.choices?.[0].message.tool_calls).choices[0].message.tool_calls[0];
        assert.equal(call.function.name, host ? 'build_engine' : 'run_command');
        assert.deepEqual(host ? JSON.parse(call.function.arguments) : JSON.parse(call.function.arguments).shell, host ? {} : 'bash');
        assert(!packets.some(packet => packet.event === 'command_result'));
        const content = host ? JSON.stringify({ ok: accepted, built: accepted, restarted: false, ...(accepted ? {} : { error: 'User rejected self-update. Do not retry.' }) }) : accepted ? '{"approved":true}' : 'User rejected command';
        submit([{ role: 'tool', tool_call_id: call.id, content, ...(host ? {} : { godot_file_success: accepted }) }], 1);
        await wait(() => packets.some(packet => packet.choices && !packet.choices[0].message.tool_calls));
        assert(packets.find(packet => packet.choices && !packet.choices[0].message.tool_calls).choices[0].message.content.includes(host && accepted ? 'BUILD_OK' : accepted ? 'EXIT_OK' : 'REJECT_OK'));
        if (host || accepted) assert.equal(packets.find(packet => packet.event === 'command_result').result.exit_status.exitCode, host ? accepted ? 0 : 1 : 7);
        assert(!fs.existsSync(path.join(directory, 'command_rejected.txt')));
    }
    child.stdin.end();
    await new Promise(resolve => child.once('close', resolve));
    const disabled = createTerminals({ approve: async () => { throw new Error('Must not request confirmation'); }, validate: () => { throw new Error('permission disabled'); } });
    await assert.rejects(disabled.create({ sessionId: 'test', command: 'exit 0' }, { project_root: directory }), /disabled/);
    await disabled.close();
});
