'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { spawn } = require('node:child_process');
const { once } = require('node:events');
const { createInterface } = require('node:readline');

const root = path.resolve(__dirname, '../..');
const definitions = [{ type: 'function', function: { name: 'read_file', description: 'Read a file through Godot', parameters: { type: 'object', properties: { path: { type: 'string' } }, required: ['path'] } } }];

async function bridge(t, url, agentId, options = {}) {
    const directory = fs.mkdtempSync(path.join(root, 'tests/editor/acp-test-'));
    const child = spawn(process.execPath, [path.join(root, 'tools/codebuddy_cli/godot_bridge.js'), 'session', options.entry || path.join(__dirname, 'mock_codebuddy_cli.js')], { cwd: root, env: { ...process.env, ...options.env, AI_CHAT_TEST_URL: url, GODOT_ACP_LOG_DIRECTORY: path.join(directory, 'logs') }, stdio: ['pipe', 'pipe', 'pipe'] });
    const closed = once(child, 'close');
    let stderr = '';
    child.stderr.on('data', chunk => { stderr += chunk; });
    const lines = createInterface({ input: child.stdout })[Symbol.asyncIterator]();
    let number = 0;
    t.after(async () => {
        child.stdin.end();
        await closed;
        fs.rmSync(directory, { recursive: true, force: true });
    });
    const submit = async (messages, rounds = 0, model = 'mock-model', legacyEncoding = false, expectError = false, reset = false) => {
        const file = path.join(directory, ++number + '.json');
        let body = JSON.stringify({ messages, model, agent_id: agentId, available_tools: options.tools || definitions, tool_definitions: options.tools || definitions, tool_context: { permission_enabled: true, tool_rounds: rounds, max_tool_rounds: null, ...options.context } });
        if (legacyEncoding) body = body.replace(/\\u001b/g, '\x1b').replace(/\\u000b/g, '\\v');
        fs.writeFileSync(file, body);
        child.stdin.write(JSON.stringify({ path: file, ...(reset ? { reset: true } : {}) }) + '\n');
        for (;;) {
            const next = await lines.next();
            assert(!next.done, stderr);
            const response = JSON.parse(next.value);
            if (response.error && expectError) return response;
            assert(!response.error, JSON.stringify(response));
            if (response.choices) { assert(!expectError, 'Oversized output was accepted'); return response; }
            assert(['progress', 'command_result'].includes(response.event), JSON.stringify(response));
        }
    };
    submit.closed = closed;
    submit.trace = () => fs.readdirSync(path.join(directory, 'logs')).flatMap(file => fs.readFileSync(path.join(directory, 'logs', file), 'utf8').trim().split('\n').map(line => JSON.parse(line)));
    return submit;
}

test('Local restore notices survive ACP bootstrap without general system messages or undone turns', () => {
    const { promptBlocks } = require('../../tools/codebuddy_cli/godot_acp');
    const notice = { role: 'system', godot_snapshot_restore: true, content: 'The user restored all recorded text files. Reread before editing.' };
    const blocks = promptBlocks({
        messages: [
            { role: 'system', content: 'PRIVATE_GENERAL_INSTRUCTIONS' },
            { role: 'user', content: 'case:snapshot_seed' },
            { role: 'assistant', content: 'SNAPSHOT_SEED_OK' },
            notice,
            { role: 'user', content: 'case:snapshot_follow' },
        ],
        tool_context: { permission_enabled: true },
    }, true);
    const history = JSON.parse(blocks.find(block => block.resource?.uri === 'godot://conversation/recovery').resource.text);
    assert.deepEqual(history.at(-1), notice);
    assert.equal(history.length, 3);
    assert.equal(blocks[0].text, 'case:snapshot_follow');
    assert(!JSON.stringify(blocks).includes('PRIVATE_GENERAL_INSTRUCTIONS'));
    assert(!JSON.stringify(blocks).includes('case:snapshot_multi'));
});

test('concurrent native reads retain their callback IDs across bounded host batches', { timeout: 15000 }, async t => {
    const submit = await bridge(t, '', 'parallel_reads');
    let response = await submit([{ role: 'user', content: 'case:nine_concurrent_reads' }]);
    const ids = new Set();
    for (const [round, count] of [[1, 8], [2, 1]]) {
        const message = response.choices[0].message;
        assert.equal(message.tool_calls.length, count);
        const results = message.tool_calls.map(call => {
            assert(!ids.has(call.id));
            ids.add(call.id);
            const file = path.basename(JSON.parse(call.function.arguments).path);
            const match = /^part-(\d+)\.txt$/.exec(file);
            assert(match);
            return { role: 'tool', tool_call_id: call.id, content: 'value-' + match[1], godot_file_success: true };
        });
        response = await submit([message, ...results.reverse()], round);
    }
    assert.equal(ids.size, 9);
    assert.equal(response.choices[0].message.content, 'ALL_NINE_OK');
});

test('ACP tasks process more than 64 MiB across tool yields and keep the session alive', { timeout: 30000 }, async t => {
    const submit = await bridge(t, '', 'large_protocol_agent');
    const proposal = await submit([{ role: 'user', content: 'case:protocol_flood' }]);
    const call = proposal.choices[0].message.tool_calls[0];
    assert.equal(call.function.name, 'read_file');
    const completed = await submit([proposal.choices[0].message, { role: 'tool', tool_call_id: call.id, content: 'FLOOD_READ_OK', godot_file_success: true }], 1);
    assert.equal(completed.choices[0].message.content, 'PROTOCOL_FLOOD_OK');
    const next = await submit([completed.choices[0].message, { role: 'user', content: 'case:protocol_flood_next' }]);
    assert.equal(next.choices[0].message.content, 'PROTOCOL_NEXT_OK');
    assert.equal(next.transport.session_id, completed.transport.session_id);
    const records = submit.trace();
    const final = records.find(item => item.event === 'host_completion_sent' && item.request === 1);
    assert(final.stdout_bytes > 64 * 1024 * 1024, 'Traffic must exceed both the former cumulative cap and the new live-buffer cap');
    assert(final.content_bytes < 1024);
    assert(!records.some(item => item.event === 'request_failed'));
    assert.equal(records.filter(item => item.event === 'model_prompt_sent').length, 2, 'Tool continuation must not resubmit a user task');
    assert(!JSON.stringify(records).includes('PRIVATE_PROTOCOL_PAYLOAD'));
});

for (const scenario of ['oversized_rpc', 'unterminated_rpc', 'body_flood']) {
    test('ACP retains safety limits and stops the child for ' + scenario, { timeout: 30000 }, async t => {
        const submit = await bridge(t, '', 'limit_agent');
        const response = await submit([{ role: 'user', content: 'case:' + scenario }], 0, 'mock-model', false, true);
        assert.equal(response.error.code, 'OUTPUT_LIMIT');
        const [code] = await submit.closed;
        assert.equal(code, 1, 'Bridge must stop after the safety violation');
        assert(submit.trace().some(item => item.event === 'cli_closed'), 'CLI child must be reaped');
        const failure = submit.trace().find(item => item.event === 'request_failed');
        assert.equal(failure.code, 'OUTPUT_LIMIT');
        if (scenario === 'body_flood') assert(failure.content_bytes > 2 * 1024 * 1024);
        else assert.equal(failure.content_bytes, 0);
    });
}

test('Restarted ACP sessions continue from a host result without re-submitting the original task', { timeout: 10000 }, async t => {
    const submit = await bridge(t, '', 'resumed_agent');
    const call = { id: 'completed-build', type: 'function', function: { name: 'build_engine', arguments: '{}' } };
    const response = await submit([{ role: 'user', content: 'case:original_task' }, { role: 'assistant', content: '', tool_calls: [call] }, { role: 'tool', tool_call_id: call.id, content: JSON.stringify({ ok: true, restarted: true }) }], 4);
    assert.equal(response.choices[0].message.content, 'HOST_ACTION_RESUMED_OK');
    assert.equal(response.transport.mode, 'bootstrap');
    assert.equal(response.transport.message_count, 3);
});

test('Delivery completion yields to the host and preserves its typed failure result', { timeout: 10000 }, async t => {
    const tools = ['run_command', 'complete_delivery'].map(name => ({ type: 'function', function: { name, parameters: { type: 'object' } } }));
    const submit = await bridge(t, '', 'delivery_agent', { tools });
    const user = { role: 'user', content: 'case:host_action_delivery' };
    const proposal = await submit([user]);
    const message = proposal.choices[0].message;
    assert.equal(message.tool_calls.length, 1);
    assert.equal(message.tool_calls[0].function.name, 'complete_delivery');
    assert.equal(JSON.parse(message.tool_calls[0].function.arguments).pr, 7);
    const response = await submit([{ role: 'tool', tool_call_id: message.tool_calls[0].id, content: JSON.stringify({ ok: false, delivery_finalization: { completion_verified: false } }) }], 1);
    assert.equal(response.choices[0].message.content, 'HOST_DELIVERY_RESULT_OK');
});

test('Legacy controls survive file results, recovery and subsequent messages without poisoning an agent', { timeout: 20000 }, async t => {
    const ansi = '\x1b[90mfirst_line\x1b[0m\v';
    const server = http.createServer(async (request, response) => {
        let text = '';
        for await (const chunk of request) text += chunk;
        const messages = JSON.parse(text).messages.filter(message => message.role !== 'system');
        const user = messages.filter(message => message.role === 'user').at(-1).content;
        const last = messages.at(-1);
        let message;
        if (user === 'case:read_controls' && last.role !== 'tool') {
            message = { role: 'assistant', content: '', tool_calls: [{ id: 'control-read', type: 'function', function: { name: 'read_file', arguments: JSON.stringify({ path: path.join(root, 'file.txt') }) } }] };
        } else {
            assert(messages.some(message => message.role === 'tool' && message.content === ansi), 'Recovery must retain the exact tool text');
            message = { role: 'assistant', content: user };
        }
        response.writeHead(200, { 'Content-Type': 'application/json' });
        response.end(JSON.stringify({ choices: [{ message }] }));
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    t.after(() => new Promise(resolve => server.close(resolve)));
    const url = `http://127.0.0.1:${server.address().port}`;
    const submit = await bridge(t, url, 'affected_agent');
    const user = { role: 'user', content: 'case:read_controls' };
    const proposal = await submit([user]);
    const assistant = proposal.choices[0].message;
    const result = { role: 'tool', tool_call_id: assistant.tool_calls[0].id, content: ansi, godot_file_success: true };
    const completed = await submit([assistant, result], 1, 'mock-model', true);
    assert.equal(completed.choices[0].message.content, user.content);
    const restarted = await bridge(t, url, 'affected_agent');
    const recovered = await restarted([user, assistant, result, completed.choices[0].message, { role: 'user', content: 'case:recovered' }], 0, 'mock-model', true);
    assert.equal(recovered.choices[0].message.content, 'case:recovered');
    const next = await restarted([recovered.choices[0].message, { role: 'user', content: 'case:next' }]);
    assert.equal(next.choices[0].message.content, 'case:next');
    assert.equal(next.transport.session_id, recovered.transport.session_id);
});

test('ACP sessions keep exact user text, native tools and per-agent memory', { timeout: 20000 }, async t => {
    const seen = [];
    const server = http.createServer(async (request, response) => {
        let text = '';
        for await (const chunk of request) text += chunk;
        const body = JSON.parse(text);
        seen.push(body);
        const messages = body.messages.filter(message => message.role !== 'system');
        const user = messages.filter(message => message.role === 'user').at(-1).content;
        const result = messages.at(-1);
        let message;
        if (user === 'case:read' && result.role !== 'tool') message = { role: 'assistant', content: '', tool_calls: [{ id: 'native-read', type: 'function', function: { name: 'read_file', arguments: JSON.stringify({ path: path.join(root, 'file.txt') }) } }] };
        else message = { role: 'assistant', content: user === 'case:read' ? 'READ:' + result.content : messages.filter(item => item.role === 'user').map(item => item.content).join('|') };
        response.writeHead(200, { 'Content-Type': 'application/json' });
        response.end(JSON.stringify({ choices: [{ message }] }));
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    t.after(() => new Promise(resolve => server.close(resolve)));
    const url = `http://127.0.0.1:${server.address().port}`;
    const a = await bridge(t, url, 'agent_a');
    const b = await bridge(t, url, 'agent_b');
    const first = await a([{ role: 'user', content: 'case:A_SECRET' }]);
    const other = await b([{ role: 'user', content: 'case:B_SECRET' }]);
    assert.notEqual(first.transport.session_id, other.transport.session_id);
    assert.equal(other.choices[0].message.content, 'case:B_SECRET');
    const next = await a([{ role: 'assistant', content: first.choices[0].message.content }, { role: 'user', content: 'case:A_NEXT' }], 0, 'mock-alternative');
    assert.equal(next.transport.session_id, first.transport.session_id);
    assert.equal(next.choices[0].message.content, 'case:A_SECRET|case:A_NEXT');
    const proposal = await a([{ role: 'user', content: 'case:read' }], 0, 'mock-alternative');
    const call = proposal.choices[0].message.tool_calls[0];
    const completed = await a([{ role: 'assistant', content: '', tool_calls: [call] }, { role: 'tool', tool_call_id: call.id, content: 'APPROVED_RESULT', godot_file_success: true }], 1, 'mock-alternative');
    assert.equal(completed.transport.session_id, first.transport.session_id);
    assert.equal(completed.choices[0].message.content, 'READ:APPROVED_RESULT');
    assert.equal(completed.transport.transmitted_bytes, 0, 'Tool results must not become another ACP user prompt');
    assert.equal(seen.at(-1).cli_transport.new_users, 0);
    assert.equal(seen.at(-1).messages.filter(message => message.role === 'user').length, 3);
    assert(seen.every(body => body.messages.filter(message => message.role === 'user').every(message => message.content.startsWith('case:'))));
});

test('ACP steering reset closes detached commands and isolates old prompt and pipe callbacks', { timeout: 15000 }, async t => {
    const directory = fs.mkdtempSync(path.join(root, 'tests/editor/acp-reset-'));
    const entry = path.join(directory, 'fixture.js');
    const pidFile = path.join(directory, 'terminal.pid');
    const worker = path.join(directory, 'worker.js');
    // Observe the OS process inside the shell on Windows as well as POSIX.
    fs.writeFileSync(worker, `
        const fs = require('node:fs');
        const file = process.env.AI_CHAT_TEST_PID_FILE;
        fs.writeFileSync(file + '.tmp', String(process.pid));
        fs.renameSync(file + '.tmp', file);
        setTimeout(() => {}, 60000);
    `);
    const sdk = require('node:url').pathToFileURL(path.join(root, 'tools/codebuddy_cli/node_modules/@agentclientprotocol/sdk/dist/acp.js')).href;
    fs.writeFileSync(entry, `
        const fs = require('node:fs');
        const { Readable, Writable } = require('node:stream');
        (async () => {
            const acp = await import(${JSON.stringify(sdk)});
            const sessionId = 'reset-fixture'; // Deliberately reused across CLI instances.
            let connection;
            connection = new acp.AgentSideConnection(() => ({
                initialize: async () => ({ protocolVersion: acp.PROTOCOL_VERSION, agentCapabilities: { promptCapabilities: { embeddedContext: true } } }),
                newSession: async () => ({ sessionId }),
                prompt: async params => {
                    const text = params.prompt[0].text;
                    if (text === 'case:steering_background') {
                        await connection.createTerminal({ sessionId, command: 'exec "$AI_CHAT_TEST_NODE" "$AI_CHAT_TEST_WORKER"' });
                        try { await connection.readTextFile({ sessionId, path: process.env.AI_CHAT_TEST_PID_FILE }); }
                        catch (_) {
                            await connection.sessionUpdate({ sessionId, update: { sessionUpdate: 'agent_message_chunk', content: { type: 'text', text: 'STALE_RESET_REPLY' } } });
                        }
                    } else {
                        const recovery = params.prompt.find(block => block.resource?.uri === 'godot://conversation/recovery');
                        if (text === 'case:steering_revised' && !recovery) throw Error('Missing paired host recovery');
                        await connection.sessionUpdate({ sessionId, update: { sessionUpdate: 'agent_message_chunk', content: { type: 'text', text: 'RESET_OK' } } });
                    }
                    return { stopReason: 'end_turn' };
                },
                cancel: async () => {},
            }), acp.ndJsonStream(Writable.toWeb(process.stdout), Readable.toWeb(process.stdin)));
        })().catch(() => { process.exitCode = 1; });
    `);
    const tools = [...definitions, { type: 'function', function: { name: 'run_command', parameters: { type: 'object' } } }];
    const submit = await bridge(t, '', 'steering-reset', { entry, tools, env: { AI_CHAT_TEST_PID_FILE: pidFile, AI_CHAT_TEST_NODE: process.execPath, AI_CHAT_TEST_WORKER: worker } });
    // Register after the bridge cleanup so its fixture remains until shutdown.
    t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
    const user = { role: 'user', content: 'case:steering_background' };
    const approval = await submit([user]);
    const command = approval.choices[0].message.tool_calls[0];
    assert.equal(command.function.name, 'run_command');
    const approved = { role: 'tool', tool_call_id: command.id, content: '{"approved":true}', godot_file_success: true };
    const proposal = await submit([approval.choices[0].message, approved], 1);
    const read = proposal.choices[0].message.tool_calls[0];
    assert.equal(read.function.name, 'read_file');
    const deadline = Date.now() + 2000;
    while (!fs.existsSync(pidFile) && Date.now() < deadline) await new Promise(resolve => setTimeout(resolve, 10));
    assert(fs.existsSync(pidFile));
    const terminalPid = Number(fs.readFileSync(pidFile, 'utf8').trim());
    process.kill(terminalPid, 0);
    const history = [user, approval.choices[0].message, approved, proposal.choices[0].message,
        { role: 'tool', tool_call_id: read.id, content: 'Skipped old proposal', godot_file_success: false },
        { role: 'user', content: 'case:steering_revised' }];
    const revised = await submit(history, 2, 'mock-model', false, false, true);
    assert.equal(revised.choices[0].message.content, 'RESET_OK');
    assert.equal(revised.transport.mode, 'bootstrap');
    assert.equal(revised.transport.session_id, proposal.transport.session_id, 'Fixture must reuse IDs to exercise process-generation isolation');
    assert.throws(() => process.kill(terminalPid, 0), { code: 'ESRCH' });
    const spawnRecords = submit.trace().filter(row => row.event === 'cli_spawned');
    assert.equal(spawnRecords.length, 2);
    assert.throws(() => process.kill(spawnRecords[0].child_pid, 0), { code: 'ESRCH' });
    const idle = await submit([...history, revised.choices[0].message, { role: 'user', content: 'case:steering_idle' }], 2, 'mock-model', false, false, true);
    assert.equal(idle.choices[0].message.content, 'RESET_OK');
    assert.equal(idle.transport.session_id, revised.transport.session_id);
    assert(!submit.trace().some(row => row.event === 'request_failed'));
});


test('CodeBuddy read-only session rejects writes, real shell and same-process capability escalation', { timeout: 30000 }, async t => {
    const options = { tools: [...definitions, { function: { name: 'get_parent_context' } }], context: { consultation_only: true, writes_allowed: false, execution_allowed: false } };
    const submit = await bridge(t, '', 'readonly_agent', options);
    const proposal = await submit([{ role: 'user', content: 'case:readonly_boundary' }]);
    const call = proposal.choices[0].message.tool_calls[0];
    assert.equal(call.function.name, 'get_parent_context');
    const done = await submit([proposal.choices[0].message, { role: 'tool', tool_call_id: call.id, content: JSON.stringify({ ok: true, role: 'readonly-parent' }) }], 1);
    assert.equal(done.choices[0].message.content, 'READONLY_BOUNDARY_OK');
    options.context = { consultation_only: false, writes_allowed: true, execution_allowed: true };
    const denied = await submit([{ role: 'user', content: 'case:readonly_escalation' }], 0, 'mock-model', false, true);
    assert.equal(denied.error.code, 'INVALID_REQUEST');
});


test('CodeBuddy production parent dispatches native delegate_review through the reserved facade', { timeout: 30000 }, async t => {
    const tools = [...definitions, ...['run_command', 'delegate_review'].map(name => ({ function: { name } }))];
    const submit = await bridge(t, '', 'readonly_parent_agent', { tools });
    const proposal = await submit([{ role: 'user', content: 'case:readonly_parent' }]);
    const call = proposal.choices[0].message.tool_calls[0];
    assert.equal(call.function.name, 'delegate_review');
    assert.deepEqual(JSON.parse(call.function.arguments), { prompt: 'case:readonly_boundary', title: 'CodeBuddy readonly boundary' });
    const done = await submit([proposal.choices[0].message, { role: 'tool', tool_call_id: call.id, content: JSON.stringify({ ok: true, status: 'scheduled' }) }], 1);
    assert.equal(done.choices[0].message.content, 'READONLY_PARENT_WAITING');
});


test('Read-only CodeBuddy discovery and script reads stay on typed host requests', { timeout: 30000 }, async t => {
    const tools = ['read_file', 'list_scripts', 'list_directory', 'read_script'].map(name => ({ function: { name } }));
    const submit = await bridge(t, '', 'readonly_reads_agent', { tools, context: { consultation_only: true, writes_allowed: false, execution_allowed: false } });
    let proposal = await submit([{ role: 'user', content: 'case:readonly_reads' }]);
    const expected = ['list_scripts', 'list_directory', 'read_script'];
    for (let i = 0; i < expected.length; i++) {
        const call = proposal.choices[0].message.tool_calls[0];
        assert.equal(call.function.name, expected[i]);
        const content = i === 0 ? JSON.stringify({ paths: ['res://review.gd'] }) : i === 1 ? JSON.stringify({ entries: [{ path: 'res://review.gd', directory: false }] }) : JSON.stringify({ content: 'extends Node', offset: 1 });
        proposal = await submit([proposal.choices[0].message, { role: 'tool', tool_call_id: call.id, content, godot_file_success: i === 2 }], i + 1);
    }
    assert.equal(proposal.choices[0].message.content, 'READONLY_HOST_READS_OK');
});


test('CodeBuddy production continuation returns the actual typed host receipt', { timeout: 30000 }, async t => {
    const tools = [...definitions, ...['run_command', 'production_control'].map(name => ({ function: { name } }))];
    const submit = await bridge(t, '', 'continuation_parent', { tools });
    const proposal = await submit([{ role: 'user', content: 'case:production_control' }]);
    const call = proposal.choices[0].message.tool_calls[0];
    assert.equal(call.function.name, 'production_control');
    assert.deepEqual(JSON.parse(call.function.arguments), { action: 'status' });
    const done = await submit([proposal.choices[0].message, { role: 'tool', tool_call_id: call.id, content: JSON.stringify({ ok: true, items: [] }) }], 1);
    assert.equal(done.choices[0].message.content, 'PRODUCTION_CONTROL_RECEIPT');
});
