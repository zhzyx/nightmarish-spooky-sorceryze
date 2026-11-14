'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const { Readable, Writable } = require('node:stream');
const { pathToFileURL } = require('node:url');
const path = require('node:path');

function pinnedReplacement(content, oldString, newString) {
    const source = fs.readFileSync(path.resolve(__dirname, '../../tools/codebuddy_cli/node_modules/@tencent-ai/codebuddy-code/dist/codebuddy-headless.js'), 'utf8');
    const match = source.match(/static applyTextReplacementWithLocation\([\s\S]*?return\{newContent:[\s\S]*?affectedLines:[\s\S]*?\}\}/);
    assert(match, 'Pinned ACP Edit matcher changed; update this regression before running it');
    const Matcher = new Function('return class { ' + match[0] + ' };')();
    return Matcher.applyTextReplacementWithLocation(content, [{ oldString, newString, replaceAll: false }]).newContent;
}

const catalog = [{ id: 'mock-model', name: 'Mock Model', description: 'Friendly description' }, { id: 'mock-alternative', name: 'Alternative' }];

async function main() {
    const args = process.argv.slice(2);
    assert.equal(process.env.CODEBUDDY_CODE_DISABLE_TERMINAL_TITLE, '1', 'Godot CLI started with automatic title inference enabled');
    for (const flag of ['--strict-mcp-config', '--no-session-persistence']) assert(args.includes(flag));
    assert(args.includes('--acp') ? ['', 'Read,Edit,Write,Glob,Grep,Bash,BashOutput,KillShell', 'Read,Bash'].includes(args[args.indexOf('--tools') + 1]) : args[args.indexOf('--tools') + 1] === '');
    assert.equal(args[args.indexOf('--setting-sources') + 1], '');
    assert.deepEqual(JSON.parse(args[args.indexOf('--mcp-config') + 1]), { mcpServers: {} });
    assert.equal(JSON.parse(args[args.indexOf('--settings') + 1]).disableAllHooks, true);
    assert.equal(args[args.indexOf('--permission-mode') + 1], 'default');
    assert(!args.includes('--dangerously-skip-permissions'));
    if (!args.includes('--acp')) assert(!fs.existsSync('project.godot'));
    if (args.includes('--acp')) {
        assert(!args.includes('--print'));
        assert(args.includes('--system-prompt'));
        assert(!args.includes('--allowedTools'));
        const acp = await import(pathToFileURL(path.resolve(__dirname, '../../tools/codebuddy_cli/node_modules/@agentclientprotocol/sdk/dist/acp.js')).href);
        let session;
        let connection;
        connection = new acp.AgentSideConnection(() => ({
            initialize: async params => {
                assert.deepEqual(params.clientCapabilities.fs, { readTextFile: true, writeTextFile: !['Read,Bash', ''].includes(args[args.indexOf('--tools') + 1]) });
                assert.equal(params.clientCapabilities.terminal, true);
                return { protocolVersion: acp.PROTOCOL_VERSION, agentCapabilities: { promptCapabilities: { embeddedContext: true, image: true } } };
            },
            newSession: async params => {
                assert(!session);
                assert.deepEqual(params.mcpServers, []);
                assert.equal(fs.realpathSync(params.cwd), fs.realpathSync(process.cwd()));
                session = { id: 'mock-' + process.pid, model: args[args.indexOf('--model') + 1] || 'mock-model', memory: [], prompts: 0 };
                session.tools = ['read_file', 'write_file'].map(name => ({ type: 'function', function: { name } }));
                return { sessionId: session.id, models: { currentModelId: session.model, availableModels: catalog.map(model => ({ modelId: model.id, name: model.name })) } };
            },
            extMethod: async (method, params) => {
                assert.equal(method, 'session/set_model');
                assert.equal(params.sessionId, session.id);
                session.model = params.modelId;
                return {};
            },
            prompt: async params => {
                assert.equal(params.sessionId, session.id);
                const text = params.prompt[0].type === 'text' ? params.prompt[0].text : '';
                const actionResult = params.prompt.find(block => block.resource?.uri === 'godot://host/action-result');
                assert(actionResult || text === '' || (text.startsWith('case:') || text.includes('case:readonly_boundary') || text.includes('current_host_design_batch')), 'User text acquired a bridge prefix');
                assert(!text.includes('CLI-native execution is disabled'));
                if (text === 'case:host_read_batch') {
                    const names = ['first.txt', 'literal.txt', 'absent.txt', 'last.txt'];
                    const reads = await Promise.allSettled(names.map(name => connection.readTextFile({
                        sessionId: session.id, path: path.join(process.env.BATCH_PROJECT, name),
                    })));
                    fs.writeFileSync(process.env.BATCH_WIRE, JSON.stringify(reads.map(read =>
                        read.status === 'fulfilled' ? { ok: true, content: read.value.content } : { ok: false, error: String(read.reason) })));
                    await connection.sessionUpdate({ sessionId: session.id, update: {
                        sessionUpdate: 'agent_message_chunk', content: { type: 'text', text: 'ACP_BATCH_COMPLETE' },
                    } });
                    return { stopReason: 'end_turn' };
                }
                const recovery = params.prompt.find(block => block.resource?.uri === 'godot://conversation/recovery');
                const blocks = params.prompt.filter(block => block.type === 'image');
                let imageIndex = 0;
                if (recovery) {
                    assert.equal(session.prompts, 0);
                    session.memory = JSON.parse(recovery.resource.text);
                    for (const record of session.memory) {
                        for (const image of record.images || []) {
                            const block = blocks[imageIndex++];
                            assert(block && block.mimeType === image.mime_type);
                            image.data = block.data;
                        }
                    }
                }
                const currentImages = blocks.slice(imageIndex).map(block => ({ name: 'attachment', mime_type: block.mimeType, data: block.data }));
                let state = JSON.parse(params.prompt.find(block => block.resource?.uri === 'godot://host/state').resource.text);
                const workspace = JSON.parse(params.prompt.find(block => block.resource?.uri === 'godot://host/workspace').resource.text);
                assert.equal(state.max_tool_rounds, null);
                assert.equal(state.remaining_tool_rounds, null);
                assert.equal(!!args[args.indexOf('--tools') + 1], state.permission_enabled);
                if (actionResult) {
                    assert(recovery, 'Restart requires the interrupted conversation snapshot');
                    assert(text.includes('Do not repeat the user task'));
                    assert.equal(session.memory.filter(message => message.role === 'user').length, 1);
                    const completed = JSON.parse(actionResult.resource.text);
                    assert.equal(completed.role, 'tool');
                    assert.equal(JSON.parse(completed.content).restarted, true);
                    assert(session.memory.at(-1).tool_calls.some(call => call.id === completed.tool_call_id));
                    await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'agent_message_chunk', content: { type: 'text', text: 'HOST_ACTION_RESUMED_OK' } } });
                    return { stopReason: 'end_turn' };
                }
                assert.notEqual(state.attach_editor_logs, true);
                assert(!text.includes('AI_CHAT_ON_DEMAND_LOG_SENTINEL'), 'Ordinary chat must not include editor Output');
                session.memory.push({ role: 'user', content: text, ...(currentImages.length ? { images: currentImages } : {}) });
                if (text === 'case:nine_concurrent_reads') {
                    const reads = Array.from({ length: 9 }, (_, index) => connection.readTextFile({
                        sessionId: session.id, path: path.join(workspace.project_root, 'part-' + index + '.txt')
                    }));
                    const results = await Promise.all(reads);
                    assert.deepEqual(results.map(result => result.content), Array.from({ length: 9 }, (_, i) => 'value-' + i));
                    await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'agent_message_chunk', content: { type: 'text', text: 'ALL_NINE_OK' } } });
                    return { stopReason: 'end_turn' };
                }
                if (text === 'case:protocol_flood') {
                    const payload = 'PRIVATE_PROTOCOL_PAYLOAD'.padEnd(256 * 1024, 'x');
                    await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'tool_call', toolCallId: 'flood-search', kind: 'search', status: 'in_progress', title: 'Grep' } });
                    for (let i = 0; i < 256; i++) {
                        await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'tool_call_update', toolCallId: 'flood-search', status: 'in_progress', content: [{ type: 'content', content: { type: 'text', text: payload } }] } });
                        if (i === 31) {
                            const result = await connection.readTextFile({ sessionId: session.id, path: path.join(workspace.project_root, 'file.txt') });
                            assert.equal(result.content, 'FLOOD_READ_OK');
                        }
                    }
                    await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'tool_call_update', toolCallId: 'flood-search', status: 'completed' } });
                    await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'agent_message_chunk', content: { type: 'text', text: 'PROTOCOL_FLOOD_OK' } } });
                    return { stopReason: 'end_turn' };
                }
                if (text === 'case:protocol_flood_next') {
                    await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'agent_message_chunk', content: { type: 'text', text: 'PROTOCOL_NEXT_OK' } } });
                    return { stopReason: 'end_turn' };
                }
                if (text === 'case:oversized_rpc') {
                    await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'agent_thought_chunk', content: { type: 'text', text: 'x'.repeat(16 * 1024 * 1024) } } });
                    return { stopReason: 'end_turn' };
                }
                if (text === 'case:unterminated_rpc') {
                    await new Promise(resolve => process.stdout.write(Buffer.alloc(16 * 1024 * 1024 + 1, 120), resolve));
                    return { stopReason: 'end_turn' };
                }
                if (text === 'case:body_flood') {
                    for (let i = 0; i < 33; i++) await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'agent_message_chunk', content: { type: 'text', text: 'x'.repeat(64 * 1024) } } });
                    return { stopReason: 'end_turn' };
                }
                if (text.startsWith('case:editor_logs')) {
                    assert.equal(state.execution_requires_approval, true);
                    const disabled = text === 'case:editor_logs_disabled';
                    try {
                        const terminal = await connection.createTerminal({ sessionId: session.id, command: 'godot-host-action read_logs', outputByteLimit: 256 * 1024 });
                        const status = await terminal.waitForExit();
                        const output = await terminal.currentOutput();
                        const result = JSON.parse(output.output);
                        assert.equal(status.exitCode, 0);
                        assert.equal(result.ok, true);
                        assert.equal(result.source, 'editor_output');
                        assert.equal(result.untrusted, true);
                        assert(result.logs.includes('AI_CHAT_ON_DEMAND_LOG_SENTINEL'));
                        assert(!result.logs.includes('LOG_TEST_PRIVATE_KEY'));
                        assert(result.logs.includes('[REDACTED]'));
                        assert(result.logs.length <= 32000);
                        await terminal.release();
                        assert(!disabled, 'Disabled local tools allowed editor log access');
                    } catch (error) {
                        if (!disabled) throw error;
                        assert.equal(state.permission_enabled, false);
                        assert(error.message.includes('disabled'));
                    }
                    await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'agent_message_chunk', content: { type: 'text', text: disabled ? 'NATIVE_LOGS_DISABLED_OK' : 'NATIVE_LOGS_ON_DEMAND_OK' } } });
                    return { stopReason: 'end_turn' };
                }
                if (text.includes('current_host_design_batch')) {
                    assert.equal(state.consultation_only, false);
                    const receipt = JSON.parse(text.slice(text.indexOf('{')));
                    assert.equal(receipt.source, 'current_host_design_batch');
                    assert.equal(receipt.read_only_review, true);
                    assert.equal(receipt.business_accepted, null);
                    const children = Object.values(receipt.children);
                    assert.equal(children.length, 1);
                    assert.equal(children[0].transport_completed, true);
                    assert.equal(children[0].child_report.text, 'READONLY_BOUNDARY_OK');
                    await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'agent_message_chunk', content: { type: 'text', text: 'READONLY_PARENT_RETURN_OK' } } });
                    return { stopReason: 'end_turn' };
                }
                if (text === 'case:production_control') {
                    const terminal = await connection.createTerminal({ sessionId: session.id, command: 'godot-host-action production_control ' + JSON.stringify({ action: 'status' }) });
                    const output = await terminal.currentOutput();
                    assert.equal(JSON.parse(output.output).ok, true);
                    await terminal.release();
                    await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'agent_message_chunk', content: { type: 'text', text: 'PRODUCTION_CONTROL_RECEIPT' } } });
                    return { stopReason: 'end_turn' };
                }
                if (text === 'case:readonly_parent') {
                    const terminal = await connection.createTerminal({ sessionId: session.id, command: 'godot-host-action delegate_review ' + JSON.stringify({ prompt: 'case:readonly_boundary', title: 'CodeBuddy readonly boundary' }) });
                    const output = await terminal.currentOutput();
                    assert.equal(JSON.parse(output.output).ok, true);
                    await terminal.release();
                    await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'agent_message_chunk', content: { type: 'text', text: 'READONLY_PARENT_WAITING' } } });
                    return { stopReason: 'end_turn' };
                }
                if (text === 'case:readonly_reads') {
                    assert.equal(args[args.indexOf('--tools') + 1], 'Read,Bash');
                    const requests = ['godot-host-action list_scripts', 'godot-host-action list_directory {"path":"res://"}', 'godot-host-action read_script {"path":"res://review.gd","offset":1,"limit":10}'];
                    for (const command of requests) {
                        const terminal = await connection.createTerminal({ sessionId: session.id, command });
                        const output = await terminal.currentOutput();
                        const result = JSON.parse(output.output);
                        assert.equal(result.ok, true);
                        await terminal.release();
                    }
                    await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'agent_message_chunk', content: { type: 'text', text: 'READONLY_HOST_READS_OK' } } });
                    return { stopReason: 'end_turn' };
                }
                if (text.includes('case:readonly_boundary')) {
                    assert.equal(state.consultation_only, true);
                    assert.equal(state.writes_allowed, false);
                    assert.equal(state.execution_allowed, false);
                    for (const kind of ['edit', 'delete', 'move', 'execute']) {
                        const permission = await connection.requestPermission({ sessionId: session.id, toolCall: { toolCallId: 'readonly-' + kind, kind, rawInput: { command: 'printf forbidden' } }, options: [{ optionId: 'allow', name: 'Allow once', kind: 'allow_once' }, { optionId: 'reject', name: 'Reject once', kind: 'reject_once' }] });
                        assert.equal(permission.outcome.optionId, 'reject');
                    }
                    await assert.rejects(connection.writeTextFile({ sessionId: session.id, path: path.join(process.cwd(), 'readonly-forbidden.txt'), content: 'forbidden' }));
                    for (const command of ['printf forbidden', 'godot-host-action build_engine', 'godot-host-action delegate_review {"prompt":"nested"}', 'godot-host-action read_file {"path":"res://x","command":"forbidden"}', 'godot-host-action get_parent_context; printf forbidden']) {
                        await assert.rejects(connection.createTerminal({ sessionId: session.id, command }));
                    }
                    const terminal = await connection.createTerminal({ sessionId: session.id, command: 'godot-host-action get_parent_context' });
                    const output = await terminal.currentOutput();
                    assert.equal(JSON.parse(output.output).ok, true);
                    await terminal.release();
                    await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'agent_message_chunk', content: { type: 'text', text: 'READONLY_BOUNDARY_OK' } } });
                    return { stopReason: 'end_turn' };
                }
                if (text.startsWith('case:host_action')) {
                    const denied = text === 'case:host_action_reject';
                    const delivery = text === 'case:host_action_delivery';
                    const command = delivery ? 'godot-host-action complete_delivery ' + JSON.stringify({ pr: 7, candidate: 'a'.repeat(40), signed_commit: 'b'.repeat(40), acceptance_items: [] }) : 'godot-host-action build_engine';
                    const terminal = await connection.createTerminal({ sessionId: session.id, command });
                    const status = await terminal.waitForExit();
                    const output = await terminal.currentOutput();
                    const result = JSON.parse(output.output);
                    assert.equal(result.ok, !denied && !delivery);
                    assert.equal(status.exitCode, denied || delivery ? 1 : 0);
                    await terminal.release();
                    await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'agent_message_chunk', content: { type: 'text', text: denied ? 'HOST_ACTION_REJECT_OK' : delivery ? 'HOST_DELIVERY_RESULT_OK' : 'HOST_ACTION_BUILD_OK' } } });
                    return { stopReason: 'end_turn' };
                }
                if (text.startsWith('case:win_cli_')) {
                    const kind = text.slice('case:win_cli_'.length);
                    assert.equal(workspace.provenance_guard_required, true);
                    assert.equal(state.execution_allowed, true);
                    const cwd = path.join(process.env.AI_CHAT_TEST_EXTERNAL, "工作 ' quoted");
                    fs.mkdirSync(cwd, { recursive: true });
                    const protectedFile = path.join(workspace.workspace_root, 'design-docs/windows-command-fixture.md');
                    const protectedBefore = fs.readFileSync(protectedFile, 'utf8');
                    const powershell = script => "'" + path.join(process.env.SystemRoot, 'System32/WindowsPowerShell/v1.0/powershell.exe').replaceAll('\\', '/') + "' -NoProfile -NonInteractive -EncodedCommand " + Buffer.from(script, 'utf16le').toString('base64');
                    let command = "printf 'short-ok\\n'; pwd -W";
                    if (kind === 'near') command = "printf 'near-ok\\n'\n#" + 'a'.repeat(4000);
                    if (kind === 'long') command = "printf '%s\\n' '中文 😀 '\"'\"'single'\"'\"' ` double \"'; printf '错误 stderr\\n' >&2; pwd -W; exit 7\n#" + 'a'.repeat(11000);
                    if (kind === 'source') command = powershell("Remove-Item -LiteralPath 'design-docs/windows-command-fixture.md'");
                    if (kind === 'failstart') command = 'godot-fixture-command-that-does-not-exist';
                    if (kind === 'limit') command = "printf 'must-not-run' > limit-executed.txt\n#" + 'a'.repeat(12000);
                    if (kind === 'reject') command = "printf forbidden > rejected.txt";
                    if (kind === 'cancel') {
                        const quote = value => value.replaceAll("'", "''");
                        const script = "[IO.File]::WriteAllText('" + quote(path.join(cwd, 'started')) + "', [string]$PID); Start-Sleep -Seconds 30; [IO.File]::WriteAllText('" + quote(path.join(cwd, 'unexpected')) + "', 'bad')";
                        command = powershell(script);
                    }
                    const terminalRequest = { sessionId: session.id, command, cwd: kind === 'source' ? workspace.workspace_root : cwd, outputByteLimit: 64000 };
                    if (kind === 'limit' || kind === 'reject') {
                        assert.equal(state.execution_requires_approval, kind === 'reject');
                        // Invalid terminal arguments and explicit host refusal have
                        // distinct ACP error envelopes.
                        await assert.rejects(connection.createTerminal(terminalRequest), error => kind === 'limit'
                            ? error.code === -32603
                            : error.code === -32000 && error.message.includes('User rejected'));
                        assert(!fs.existsSync(path.join(cwd, 'rejected.txt')));
                        assert(!fs.existsSync(path.join(cwd, 'limit-executed.txt')));
                    } else {
                        const terminal = await connection.createTerminal(terminalRequest);
                        const status = await terminal.waitForExit();
                        const output = await terminal.currentOutput();
                        assert.equal(output.exitStatus.exitCode, status.exitCode);
                        assert.equal(status._meta.timed_out, false);
                        if (kind === 'source') {
                            assert.notEqual(status.exitCode, 0);
                            assert(output.output.includes('provenance_violation'));
                            assert.equal(fs.readFileSync(protectedFile, 'utf8'), protectedBefore);
                        } else if (kind === 'long') {
                            assert.equal(status.exitCode, 7);
                            assert(output.output.includes('中文 😀 \'single\' ` double "') && output.output.includes('错误 stderr'));
                            assert(output.output.replaceAll('\\', '/').includes(cwd.replaceAll('\\', '/')));
                        } else if (kind === 'failstart') {
                            assert.equal(status.exitCode, 127);
                        } else {
                            assert.equal(status.exitCode, 0);
                            assert(output.output.includes(kind + '-ok'));
                        }
                        await terminal.release();
                    }
                    await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'agent_message_chunk', content: { type: 'text', text: 'WIN_CLI_' + kind.toUpperCase() + '_OK' } } });
                    return { stopReason: 'end_turn' };
                }
                if (text.startsWith('case:native_command')) {
                    assert.equal(state.execution_requires_approval !== false, text !== 'case:native_command_auto');
                    const denied = text === 'case:native_command_reject' || text === 'case:native_command_disabled';
                    let result;
                    try {
                        const command = denied ? 'printf forbidden > command_rejected.txt' : "printf 'BUILD_STDOUT_OK\\n'; printf 'BUILD_STDERR_OK\\n' >&2; exit 7";
                        const terminal = await connection.createTerminal({ sessionId: session.id, command, outputByteLimit: 32000 });
                        const status = await terminal.waitForExit();
                        const output = await terminal.currentOutput();
                        assert.equal(status.exitCode, 7);
                        assert(output.output.includes('BUILD_STDOUT_OK') && output.output.includes('BUILD_STDERR_OK'));
                        assert.equal(output.exitStatus.exitCode, 7);
                        await terminal.release();
                        assert(!denied, 'Denied command was executed');
                        result = 'NATIVE_COMMAND_EXIT_OK';
                    } catch (error) {
                        if (!denied) throw error;
                        assert(!fs.existsSync(path.join(workspace.project_root, 'command_rejected.txt')));
                        result = 'NATIVE_COMMAND_REJECT_OK';
                    }
                    await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'agent_message_chunk', content: { type: 'text', text: result } } });
                    return { stopReason: 'end_turn' };
                }
                let newUsers = 1;
                let newMessages = 1;
                for (;;) {
                    session.prompts++;
                    while (Buffer.byteLength(JSON.stringify(session.memory)) > 768 * 1024) {
                        const nextTurn = session.memory.findIndex((message, index) => index > 0 && message.role === 'user');
                        if (nextTurn < 0) break;
                        session.memory.splice(0, nextTurn);
                    }
                    const messages = [...session.memory, { role: 'system', content: 'Godot tool state (authoritative host metadata): ' + JSON.stringify(state) + '\n' }];
                    const response = await fetch(process.env.AI_CHAT_TEST_URL, {
                        method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer test-secret' },
                        body: JSON.stringify({ messages, cli_workspace: workspace, model: 'mock-model', ...(state.unavailable_reason === 'none' ? { tools: session.tools } : {}), cli_transport: { pid: process.pid, session_id: session.id, prompts: session.prompts, new_messages: newMessages, new_users: newUsers, prompt_bytes: newUsers ? Buffer.byteLength(JSON.stringify(params.prompt)) : 0, image_blocks: newUsers ? blocks.length : 0 } }),
                    });
                    const body = await response.text();
                    assert(response.ok, body);
                    const message = JSON.parse(body).choices[0].message;
                    session.memory.push(message);
                    if (text.includes('case:native_progress')) {
                        process.stderr.write('account-token=PRIVATE_STDERR_SENTINEL\n');
                        for (const piece of ['NATIVE_STREAM_', 'VISIBLE_', 'OK']) {
                            await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'agent_thought_chunk', content: { type: 'text', text: 'PRIVATE_THOUGHT_SENTINEL' } } });
                            await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'agent_message_chunk', content: { type: 'text', text: piece } } });
                            await new Promise(resolve => setTimeout(resolve, 350));
                        }
                        await new Promise(resolve => setTimeout(resolve, 800));
                        if (text === 'case:native_progress_error') throw new Error('mock failed PRIVATE_ERROR_SENTINEL');
                    } else if (message.content) {
                        await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'agent_message_chunk', content: { type: 'text', text: message.content } } });
                    }
                    const calls = message.tool_calls || [];
                    if (!calls.length) return { stopReason: 'end_turn' };
                    const editCalls = calls.filter(call => call.function.name === 'edit_native');
                    assert(editCalls.length === 0 || calls.length === 1, 'Native Edit regression must run sequential read and write');
                    const results = await Promise.all(calls.map(async call => {
                        const args = JSON.parse(call.function.arguments);
                        const filePath = args.path.startsWith('res://') ? path.join(process.env.AI_CHAT_TEST_PROJECT, args.path.slice(6)) : args.path;
                        let content;
                        try {
                            if (['read_file', 'write_file', 'edit_native', 'Glob', 'Grep'].includes(call.function.name)) {
                                const kind = ['Glob', 'Grep', 'read_file'].includes(call.function.name) ? 'read' : 'edit';
                                await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'tool_call', toolCallId: call.id, kind, status: 'pending', title: call.function.name } });
                                await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'tool_call_update', toolCallId: call.id, status: 'pending' } });
                                if (!session.permissionSafetyChecked) {
                                    session.permissionSafetyChecked = true;
                                    for (const denied of [{ sessionId: session.id, toolCall: { toolCallId: call.id, kind: 'fetch' } }, { sessionId: session.id, toolCall: { toolCallId: 'unseen-call', title: 'Read file' } }, { sessionId: session.id + '-other', toolCall: { toolCallId: call.id } }]) {
                                        const refusal = await connection.requestPermission({ ...denied, options: [{ optionId: 'allow', name: 'Allow once', kind: 'allow_once' }, { optionId: 'reject', name: 'Reject once', kind: 'reject_once' }] });
                                        assert.deepEqual(refusal.outcome, { outcome: 'selected', optionId: 'reject' });
                                    }
                                }
                                const permission = await connection.requestPermission({ sessionId: session.id, toolCall: { toolCallId: call.id }, options: [{ optionId: 'allow', name: 'Allow once', kind: 'allow_once' }, { optionId: 'reject', name: 'Reject once', kind: 'reject_once' }] });
                                assert.deepEqual(permission.outcome, { outcome: 'selected', optionId: 'allow' });
                            }
                            if (['Glob', 'Grep'].includes(call.function.name)) {
                                const rg = path.resolve(__dirname, '../../tools/codebuddy_cli/node_modules/@tencent-ai/codebuddy-code/vendor/ripgrep/x64-win32/rg.exe');
                                const command = call.function.name === 'Glob' ? ['--files', '--glob', args.pattern, '--', filePath] : ['--no-heading', '--line-number', '--glob', args.glob || '*', '-e', args.pattern, '--', filePath];
                                try { content = require('node:child_process').execFileSync(rg, command, { encoding: 'utf8', windowsHide: true, timeout: 10000, maxBuffer: 1024 * 1024 }); }
                                catch (error) { if (error.status !== 1) throw error; content = ''; }
                                await connection.sessionUpdate({ sessionId: session.id, update: { sessionUpdate: 'tool_call_update', toolCallId: call.id, status: 'completed' } });
                            } else if (call.function.name === 'read_file') {
                                const result = await connection.readTextFile({ sessionId: session.id, path: filePath, ...(args.offset != null ? { line: args.offset } : {}), ...(args.limit != null ? { limit: args.limit } : {}) });
                                content = result.content;
                            } else if (call.function.name === 'edit_native') {
                                const result = await connection.readTextFile({ sessionId: session.id, path: filePath });
                                const replacement = pinnedReplacement(result.content, args.old_string, args.new_string);
                                await connection.writeTextFile({ sessionId: session.id, path: filePath, content: replacement });
                                content = 'Applied approved script change';
                            } else if (call.function.name === 'write_file') {
                                await connection.writeTextFile({ sessionId: session.id, path: filePath, content: args.content });
                                content = 'Applied approved script change';
                            } else {
                                throw new Error('Native test attempted an unavailable tool: ' + call.function.name);
                            }
                        } catch (error) {
                            content = error.message.includes('User rejected') ? 'User rejected tool' : 'Error: ' + error.message;
                        }
                        return { role: 'tool', tool_call_id: call.id, content };
                    }));
                    if (calls.some(call => !['Glob', 'Grep'].includes(call.function.name))) state.tool_rounds += editCalls.length ? 2 : 1;
                    state.remaining_tool_rounds = null;
                    state.unavailable_reason = !state.permission_enabled ? 'permission_disabled' : 'none';
                    session.memory.push(...results);
                    newUsers = 0;
                    newMessages = calls.length + 1;
                }
            },
            cancel: async () => {},
        }), acp.ndJsonStream(Writable.toWeb(process.stdout), Readable.toWeb(process.stdin)));
        await connection.closed;
        return;
    }
    if (args.includes('--input-format')) {
        const lines = require('node:readline').createInterface({ input: process.stdin });
        for await (const line of lines) {
            const control = JSON.parse(line);
            assert.deepEqual(control.request, { subtype: 'initialize', hasPrompt: false });
            process.stdout.write(JSON.stringify({ type: 'control_response', response: { subtype: 'success', request_id: control.request_id, response: { models: catalog, account: { token: 'must-not-leak' } } } }) + '\n');
            return;
        }
        return;
    }
    let text = '';
    for await (const chunk of process.stdin) text += chunk;
    const request = JSON.parse(text);
    const response = await fetch(process.env.AI_CHAT_TEST_URL, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer test-secret' }, body: JSON.stringify({ messages: request.messages, model: request.model, ...(request.available_tools.length ? { tools: request.available_tools } : {}) }) });
    const message = (await response.json()).choices[0].message;
    const actions = (message.tool_calls || []).map(call => ({ name: call.function.name, arguments: JSON.parse(call.function.arguments) }));
    process.stdout.write(JSON.stringify({ type: 'result', subtype: 'success', result: JSON.stringify({ content: message.content, actions }) }));
}

if (require.main === module) main().catch(error => { console.error(error.message); process.exitCode = 1; });
module.exports = { pinnedReplacement };
