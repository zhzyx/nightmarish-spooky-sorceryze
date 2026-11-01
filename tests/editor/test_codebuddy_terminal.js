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

test('Terminal validates commands, cwd and unsupported args/env before approval', t => {
    const { directory, workspace } = fixture(t);
    const base = { sessionId: 'test', command: 'printf ok' };
    assert.equal(terminalArguments(base, workspace).cwd, fs.realpathSync(directory));
    for (const changes of [{ command: '' }, { command: 'bad\0command' }, { command: 'x'.repeat(12001) }, { args: ['ignored'] }, { env: [{ name: 'SECRET', value: 'ignored' }] }, { cwd: 'relative' }, { outputByteLimit: 0 }, { outputByteLimit: 300000 }]) assert.throws(() => terminalArguments({ ...base, ...changes }, workspace));
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
