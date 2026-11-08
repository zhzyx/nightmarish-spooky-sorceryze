'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { cliEnvironment, safeArguments, sessionArguments, modelArguments, normalizeModels, buildPrompt, validateInput, sessionInstructions, normalizeResult, classifyDiagnostics, serializeError } = require('../../tools/codebuddy_cli/godot_bridge');
const { workspacePaths, promptBlocks, fileArguments, parseHostJson, readResponse, createWaitBudget, progressUpdate, createTraceLog, rpcTrace, createToolKindState, createFileTextView, fileTextFormat, toolFailure, boundedRpcStream } = require('../../tools/codebuddy_cli/godot_acp');

test('Reserved delivery JSON never reaches a shell and retains the original UI action size limit', () => {
    const { hostActionRequest } = require('../../tools/codebuddy_cli/godot_terminal');
    const args = { pr: 7, candidate: 'a'.repeat(40), signed_commit: 'b'.repeat(40), acceptance_items: [{ evidence: '中'.repeat(17000) }] };
    assert.deepEqual(hostActionRequest('godot-host-action complete_delivery ' + JSON.stringify(args)), { name: 'complete_delivery', arguments: args });
    for (const text of ['{}; touch forbidden', '[]', '{} && true', '{"bad":', JSON.stringify({ evidence: 'x'.repeat(65536) })]) {
        assert.throws(() => hostActionRequest('godot-host-action complete_delivery ' + text));
    }
    assert.throws(() => hostActionRequest('godot-host-action editor_action ' + JSON.stringify({ evidence: 'x'.repeat(32768) })));
    assert(sessionInstructions().includes('godot-host-action complete_delivery'));
});

test('Godot CLI disables automatic title inference without mutating the parent environment', () => {
    const source = Object.freeze({ PATH: 'test-path', CODEBUDDY_CODE_DISABLE_TERMINAL_TITLE: '0', CODEBUDDY_STARTUP_PROFILE: 'old-profile' });
    const env = cliEnvironment(source);
    assert.equal(env.CODEBUDDY_CODE_DISABLE_TERMINAL_TITLE, '1');
    assert.equal(env.PATH, 'test-path');
    assert(!Object.hasOwn(env, 'CODEBUDDY_STARTUP_PROFILE'));
    assert.equal(source.CODEBUDDY_CODE_DISABLE_TERMINAL_TITLE, '0');
    assert.equal(source.CODEBUDDY_STARTUP_PROFILE, 'old-profile');
    assert.equal(cliEnvironment({}).CODEBUDDY_CODE_DISABLE_TERMINAL_TITLE, '1');
});

test('CLI tools, MCP, hooks and session persistence are disabled', () => {
    assert(sessionInstructions().includes('route_engine_message'));
    const args = safeArguments('gpt-6.1-sol');
    assert.equal(args[args.indexOf('--tools') + 1], '');
    assert.equal(args[args.indexOf('--setting-sources') + 1], '');
    assert.equal(args[args.indexOf('--permission-mode') + 1], 'default');
    assert(args.includes('--strict-mcp-config'));
    assert(args.includes('--no-session-persistence'));
    assert(!args.includes('--dangerously-skip-permissions'));
    assert.deepEqual(JSON.parse(args[args.indexOf('--mcp-config') + 1]), { mcpServers: {} });
    assert.equal(JSON.parse(args[args.indexOf('--settings') + 1]).disableAllHooks, true);
    assert.equal(args[args.indexOf('--model') + 1], 'gpt-6.1-sol');
    assert(!args.includes('--json-schema'));
});

test('Default model is not secretly replaced and metadata requests have no model prompt', () => {
    assert(!safeArguments().includes('--model'));
    assert.equal(safeArguments('custom-id').at(-1), 'custom-id');
    const args = modelArguments();
    assert.equal(args[args.indexOf('--input-format') + 1], 'stream-json');
    assert.equal(args[args.indexOf('--output-format') + 1], 'stream-json');
    assert(!args.includes('--model'));
    assert(args.includes('--no-session-persistence'));
});

test('Model metadata drops account credentials and unrelated protocol messages', () => {
    const requestId = 'models';
    const packet = { type: 'control_response', response: { subtype: 'success', request_id: requestId, response: { models: [{ id: 'real-id', name: 'Friendly name', apiKey: 'secret' }, { id: 'real-id' }, { id: 'bad\nID' }], account: { token: 'private-token' }, commands: ['private-command'] } } };
    assert.deepEqual(normalizeModels(packet, requestId), { models: [{ id: 'real-id', name: 'Friendly name', description: '' }] });
    assert.equal(normalizeModels(packet, 'other'), null);
    assert.equal(normalizeModels({ type: 'user' }, requestId), null);
    assert(!JSON.stringify(normalizeModels(packet, requestId)).includes('private'));
    assert.throws(() => normalizeModels({ type: 'control_response', response: { subtype: 'error', request_id: requestId, error: 'token=private' } }, requestId));
});

test('Godot action permission is distinct from disabled CLI-native execution', () => {
    const input = { model: 'test-model', messages: [{ role: 'assistant', content: 'Old claim: file tools are not available.' }], available_tools: [{ type: 'function', function: { name: 'read_file' } }], tool_context: { permission_enabled: true, tool_rounds: 2, max_tool_rounds: null } };
    const prompt = buildPrompt(input);
    assert(!prompt.includes('You have no tools'));
    assert(!prompt.includes('JSON action proposals'));
    const payload = JSON.parse(prompt);
    assert.deepEqual(payload.tool_context, { permission_enabled: true, tool_rounds: 2, max_tool_rounds: null, remaining_tool_rounds: null, unavailable_reason: 'none', consultation_only: false, writes_allowed: true, execution_allowed: true });
    assert(sessionInstructions().includes('authoritative permissions'));
    assert.deepEqual(payload.messages, input.messages);
});

test('Automatic file changes preserve host policy without enabling commands or disabled tools', () => {
    const base = { model: '', messages: [], available_tools: [{ type: 'function', function: { name: 'read_file' } }], tool_context: { permission_enabled: true, tool_rounds: 0, max_tool_rounds: null } };
    for (const required of [false, true]) {
        const input = { ...base, tool_context: { ...base.tool_context, file_changes_require_approval: required } };
        assert.equal(validateInput(input).tool_context.file_changes_require_approval, required);
    }
    assert.equal(validateInput({ ...base, available_tools: [], tool_context: { ...base.tool_context, permission_enabled: false, file_changes_require_approval: false } }).tool_context.file_changes_require_approval, true);
    assert.throws(() => validateInput({ ...base, tool_context: { ...base.tool_context, file_changes_require_approval: 'false' } }), { bridgeCode: 'INVALID_REQUEST' });
    assert(sessionInstructions().includes('execution_requires_approval is false'));
});

test('Automatic execution is an independent host opt-in and cannot enable disabled tools', () => {
    const base = { model: '', messages: [], available_tools: [{ type: 'function', function: { name: 'run_command' } }], tool_context: { permission_enabled: true, tool_rounds: 0, max_tool_rounds: null, file_changes_require_approval: true } };
    assert(!Object.hasOwn(validateInput(base).tool_context, 'execution_requires_approval'));
    for (const required of [false, true]) {
        const state = validateInput({ ...base, tool_context: { ...base.tool_context, execution_requires_approval: required } }).tool_context;
        assert.equal(state.execution_requires_approval, required);
        assert.equal(state.file_changes_require_approval, true);
    }
    assert.equal(validateInput({ ...base, available_tools: [], tool_context: { ...base.tool_context, permission_enabled: false, execution_requires_approval: false } }).tool_context.execution_requires_approval, true);
    assert.throws(() => validateInput({ ...base, tool_context: { ...base.tool_context, execution_requires_approval: 'false' } }), { bridgeCode: 'INVALID_REQUEST' });
    assert(!sessionArguments().includes('--dangerously-skip-permissions'));
});

test('Tool rounds remain unlimited and permission disabled still prevents local actions', () => {
    for (const enabled of [false, true]) {
        const tools = enabled ? [{ type: 'function', function: { name: 'read_file' } }] : [];
        const prompt = buildPrompt({ model: '', messages: [], available_tools: tools, tool_context: { permission_enabled: enabled, tool_rounds: 1000, max_tool_rounds: null } });
        const state = JSON.parse(prompt).tool_context;
        assert.equal(state.unavailable_reason, enabled ? 'none' : 'permission_disabled');
        assert.equal(state.max_tool_rounds, null);
        assert.equal(state.remaining_tool_rounds, null);
        assert.equal(state.permission_enabled, enabled);
    }
});

test('Inconsistent host permission or budget fails before starting the CLI', () => {
    const base = { model: '', messages: [], available_tools: [], tool_context: { permission_enabled: true, tool_rounds: 0, max_tool_rounds: null } };
    assert.throws(() => buildPrompt(base), { bridgeCode: 'INVALID_REQUEST' });
    assert.throws(() => buildPrompt({ ...base, tool_context: { permission_enabled: false, tool_rounds: -1, max_tool_rounds: null } }), { bridgeCode: 'INVALID_REQUEST' });
    assert.throws(() => buildPrompt({ ...base, tool_context: { permission_enabled: true, tool_rounds: 6, max_tool_rounds: null } }), { bridgeCode: 'INVALID_REQUEST' });
    assert.throws(() => buildPrompt({ ...base, available_tools: [{}], tool_context: { permission_enabled: false, tool_rounds: 0, max_tool_rounds: null } }), { bridgeCode: 'INVALID_REQUEST' });
});

test('Extra actions after the round budget receive a non-permission error', () => {
    const result = { structured_output: { content: '', actions: [{ name: 'read_file', arguments: { path: 'file.gd' } }] } };
    assert.throws(() => normalizeResult(result, false, 'round_limit_reached'), { bridgeCode: 'TOOL_ROUND_LIMIT_REACHED' });
    assert.throws(() => normalizeResult(result, false), { bridgeCode: 'TOOLS_DISABLED' });
    const summary = normalizeResult({ structured_output: { content: 'Budget exhausted, permission is still on.', actions: [] } }, false, 'round_limit_reached');
    assert.equal(summary.choices[0].message.content, 'Budget exhausted, permission is still on.');
});

test('Persistent sessions keep native isolation and never enable transcript persistence', () => {
    const args = sessionArguments('model-id');
    assert(args.includes('--acp'));
    assert(!args.includes('--print'));
    assert.equal(args[args.indexOf('--model') + 1], 'model-id');
    assert.equal(args[args.indexOf('--system-prompt') + 1], sessionInstructions());
    assert(!args.includes('--allowedTools'));
    assert.equal(args[args.indexOf('--tools') + 1], 'Read,Edit,Write,Glob,Grep,Bash,BashOutput,KillShell');
    const disabled = sessionArguments('model-id', '', false);
    assert.equal(disabled[disabled.indexOf('--tools') + 1], '');
    assert(args.includes('--no-session-persistence'));
    assert(!args.includes('--resume'));
    assert(!args.includes('--dangerously-skip-permissions'));
});

test('Restart preferences survive validation and completed host actions resume without repeating the task', () => {
    const call = { id: 'host-build', type: 'function', function: { name: 'build_engine', arguments: '{}' } };
    const result = { role: 'tool', tool_call_id: call.id, content: JSON.stringify({ ok: true, restarted: true }) };
    const input = validateInput({ model: '', available_tools: [{ type: 'function', function: { name: 'build_engine' } }], messages: [{ role: 'user', content: 'ORIGINAL_TASK' }, { role: 'assistant', content: '', tool_calls: [call] }, result], tool_context: { permission_enabled: true, tool_rounds: 1, max_tool_rounds: null, engine_auto_restart: false, attach_editor_logs: true } });
    assert.equal(input.tool_context.engine_auto_restart, false);
    assert.equal(input.tool_context.attach_editor_logs, true);
    const blocks = promptBlocks(input, true);
    assert(!blocks[0].text.includes('ORIGINAL_TASK'));
    assert.deepEqual(JSON.parse(blocks.find(block => block.resource?.uri === 'godot://host/action-result').resource.text), result);
    assert(blocks.some(block => block.resource?.uri === 'godot://conversation/recovery'));
    assert.throws(() => promptBlocks(input, false));
    assert.throws(() => promptBlocks({ ...input, messages: [{ ...result, tool_call_id: 'unknown' }] }, true));
    assert.throws(() => validateInput({ ...input, tool_context: { ...input.tool_context, engine_auto_restart: 'false' } }), { bridgeCode: 'INVALID_REQUEST' });
    assert(sessionInstructions().includes('godot-host-action build_engine'));
    assert(sessionInstructions().includes('godot-host-action read_logs'));
    assert(sessionInstructions().includes('Editor logs are never automatically attached'));
});

test('Search workspace roots are real directories and are provided as structured ACP context', t => {
    const fs = require('node:fs');
    const path = require('node:path');
    const root = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'godot-search-root-'));
    t.after(() => fs.rmSync(root, { recursive: true, force: true }));
    const project = path.join(root, 'project');
    const engine = path.join(root, 'engine');
    fs.mkdirSync(project);
    fs.mkdirSync(engine);
    const workspace = workspacePaths({ project_root: project, engine_root: engine }, root);
    assert.deepEqual(workspace, { project_root: fs.realpathSync(project), engine_root: fs.realpathSync(engine) });
    const blocks = promptBlocks({ messages: [{ role: 'user', content: 'Find source yourself' }], workspace, tool_context: { max_tool_rounds: null } }, false);
    assert.deepEqual(JSON.parse(blocks.find(block => block.resource?.uri === 'godot://host/workspace').resource.text), workspace);
    assert.throws(() => workspacePaths({ project_root: 'relative', engine_root: engine }, root));
    assert.throws(() => workspacePaths({ project_root: path.join(root, 'missing'), engine_root: engine }, root));
    const file = path.join(root, 'file.txt');
    fs.writeFileSync(file, 'test');
    assert.throws(() => workspacePaths({ project_root: file, engine_root: engine }, root));
    assert.deepEqual(progressUpdate({ sessionUpdate: 'tool_call', title: 'Grep', kind: 'read' }), { activity: 'searching', content_delta: '' });
});

test('Native Glob/Grep permission classification matches the pinned CLI implementation', () => {
    const fs = require('node:fs');
    const source = fs.readFileSync(require('node:path').resolve(__dirname, '../../tools/codebuddy_cli/node_modules/@tencent-ai/codebuddy-code/dist/codebuddy-headless.js'), 'utf8');
    const match = source.match(/static inferToolKind\([\s\S]*?"other"\}/);
    assert(match, 'Pinned tool classification changed; verify before updating this regression');
    const Utils = new Function('return class {' + match[0] + '};')();
    for (const name of ['Glob', 'Grep', 'Read']) assert.equal(Utils.inferToolKind(name), 'read');
    assert.equal(Utils.inferToolKind('Edit'), 'edit');
    const state = createToolKindState();
    state.begin('search-session');
    state.update({ sessionId: 'search-session', update: { sessionUpdate: 'tool_call', toolCallId: 'grep-call', kind: Utils.inferToolKind('Grep') } });
    assert.equal(state.resolve('search-session', { toolCallId: 'grep-call' }).kind, 'read');
});

test('Legacy host JSON preserves control text while rejecting unrelated malformed JSON', () => {
    const controls = Array.from({ length: 32 }, (_, i) => String.fromCharCode(i)).join('');
    const value = { content: 'source:"\\path\\v\n' + controls + '中文', literal: '\\v', '\x1bkey': '\x1b[31mred\x1b[0m' };
    const encoded = JSON.stringify(value);
    assert.deepEqual(parseHostJson(encoded), value);
    const legacy = encoded.replace(/\\u00([0-9a-f]{2})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
    assert.throws(() => JSON.parse(legacy));
    assert.deepEqual(parseHostJson(legacy), value);
    assert.deepEqual(parseHostJson('{"content":"a\\vb","literal":"\\\\v"}'), { content: 'a\vb', literal: '\\v' });
    const ranged = '{"offset":1,"content":"\x1b[90mline\x1b[0m"}';
    assert.deepEqual(readResponse(ranged, { offset: 1 }), { content: '\x1b[90mline\x1b[0m' });
    for (const invalid of ['{"x":}', '{"x":"\\q"}', '{"x":"unterminated}', '{"x":1,}', '\x1b{"x":1}']) {
        assert.throws(() => parseHostJson(invalid), { bridgeCode: 'INVALID_REQUEST' });
    }
    assert(!serializeError({ bridgeCode: 'INVALID_REQUEST', message: 'PRIVATE_SOURCE' }).message.includes('PRIVATE_SOURCE'));
});

test('Native file requests validate absolute paths, ranges and complete write size', () => {
    const path = require('node:path').resolve('fixture.txt');
    assert.deepEqual(fileArguments({ path }, false), { path });
    assert.deepEqual(fileArguments({ path, line: 2, limit: 1 }, false), { path, offset: 2, limit: 1 });
    assert.deepEqual(fileArguments({ path, content: '中文\n' }, true), { path, content: '中文\n' });
    for (const params of [{ path: 'relative.txt' }, { path, line: 0 }, { path, line: 1.5 }, { path, limit: 501 }]) assert.throws(() => fileArguments(params, false));
    assert.throws(() => fileArguments({ path, content: '中'.repeat(90000) }, true));
    assert.deepEqual(readResponse('Error: this is actual file content', { path }), { content: 'Error: this is actual file content' });
    assert.deepEqual(readResponse(JSON.stringify({ offset: 2, content: 'line' }), { path, offset: 2 }), { content: 'line' });
    assert.throws(() => readResponse(JSON.stringify({ offset: 2, content: 'excerpt', context_excerpted: true }), { path, offset: 2 }));
    assert.throws(() => readResponse(JSON.stringify({ offset: 1, content: 'wrong range' }), { path, offset: 2 }));
});

test('Pinned native Edit matches the normalized view while disk CRLF and BOM are preserved', () => {
    const { pinnedReplacement } = require('./mock_codebuddy_cli');
    const path = require('node:path').resolve('eol_fixture.txt');
    const before = '\uFEFFheader\r\n\tvalue = 1\r\nfooter\r\n';
    const oldString = 'header\n\tvalue = 1';
    assert.throws(() => pinnedReplacement(before, oldString, 'header\n\tvalue = 2'), /old_string/);
    const view = createFileTextView();
    const read = view.read(before, { path });
    assert.equal(read.content, 'header\n\tvalue = 1\nfooter\n');
    const updated = pinnedReplacement(read.content, oldString, 'header\n\tvalue = 2');
    const written = view.write({ path, content: updated });
    assert.equal(written.content, '\uFEFFheader\r\n\tvalue = 2\r\nfooter\r\n');
    assert.deepEqual(fileTextFormat(written.content), { newline: 'crlf', bom: true, crlf_count: 3, lf_count: 0, cr_count: 0 });
    view.saved(written);
    assert.equal(view.read(written.content, { path }).content, updated);
    assert.throws(() => pinnedReplacement(read.content, 'header\n value = 1', 'changed'), /old_string/);
    const independent = createFileTextView();
    assert.equal(independent.write({ path, content: updated }).content, updated);
    const lfPath = path + '.lf';
    view.read('a\nb\n', { path: lfPath });
    assert.equal(view.write({ path: lfPath, content: 'a\r\nc\r\n' }).content, 'a\nc\n');
    const mixed = 'a\r\nb\nc\r';
    assert.equal(view.read(mixed, { path: path + '.mixed' }).content, mixed);
    const json = JSON.stringify({ content: 'real JSON source', offset: 1 });
    assert.equal(view.read(json, { path: path + '.json' }).content, json);
    view.clear();
    assert.equal(view.write({ path, content: updated }).content, updated);
});

test('Restored disk format respects byte limits and failed tool text is safely classified', () => {
    const path = require('node:path').resolve('limit.txt');
    const view = createFileTextView();
    view.read('a\r\n', { path });
    assert.throws(() => view.write({ path, content: '\n'.repeat(256 * 1024) }));
    const update = text => ({ sessionUpdate: 'tool_call_update', status: 'failed', content: [{ type: 'content', content: { type: 'text', text } }] });
    const failure = toolFailure(update('Edit error: The provided `old_string` does not appear in the file: "PRIVATE_SOURCE".\r\n\r\nNo edits were applied.'));
    assert.equal(failure.failure_cause, 'old_string_not_found');
    assert(!JSON.stringify(failure).includes('PRIVATE_SOURCE'));
    assert.equal(toolFailure(update('Edit error: The provided `old_string` is empty.\n\nNo edits were applied.')).failure_cause, 'empty_old_string');
    assert.equal(toolFailure(update('unrelated error')).failure_cause, 'unknown');
    assert.equal(toolFailure({ sessionUpdate: 'agent_thought_chunk', status: 'failed', content: [] }), null);
});

test('Native ACP user text is exact and old history is only an explicit recovery resource', () => {
    const input = validateInput({ model: 'model', messages: [{ role: 'user', content: 'OLD_TASK' }, { role: 'assistant', content: 'OLD_REPLY' }, { role: 'user', content: '新的问题\n原文保持不变' }], available_tools: [], tool_context: { permission_enabled: false, tool_rounds: 0, max_tool_rounds: null } });
    for (const initial of [true, false]) {
        const blocks = promptBlocks(input, initial);
        assert.deepEqual(blocks[0], { type: 'text', text: input.messages.at(-1).content });
        assert.equal(blocks.some(block => block.resource?.uri === 'godot://conversation/recovery'), initial);
        assert(!blocks[0].text.includes('Godot editor assistant'));
        assert(!JSON.stringify(blocks).includes('Output schema:'));
        if (!initial) assert(!JSON.stringify(blocks).includes('OLD_TASK'));
    }
    assert.throws(() => promptBlocks({ messages: [{ role: 'tool', content: 'RESULT' }] }, false));
});

test('Image attachments are native blocks, preserve order and are not retransmitted incrementally', () => {
    const data = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]).toString('base64');
    const image = { name: '截图.png', mime_type: 'image/png', data };
    const base = { model: '', available_tools: [], messages: [{ role: 'user', content: 'old', images: [image] }, { role: 'assistant', content: 'old reply' }, { role: 'user', content: 'new', images: [image, image] }] };
    const input = validateInput(base);
    assert.equal(promptBlocks(input, true).filter(block => block.type === 'image').length, 3);
    const recovery = promptBlocks(input, true).find(block => block.resource?.uri === 'godot://conversation/recovery');
    assert(!recovery.resource.text.includes(data));
    const incremental = promptBlocks(input, false);
    assert.deepEqual(incremental[0], { type: 'text', text: 'new' });
    assert.deepEqual(incremental.filter(block => block.type === 'image'), [image, image].map(item => ({ type: 'image', data: item.data, mimeType: item.mime_type })));
    assert.throws(() => promptBlocks(input, false, false), { bridgeCode: 'IMAGE_UNSUPPORTED' });
    assert.equal(promptBlocks(validateInput({ ...base, messages: [{ role: 'user', content: '', images: [image] }] }), false)[0].type, 'image');
    assert.equal(promptBlocks(validateInput({ ...base, messages: [...base.messages, { role: 'user', content: 'next' }] }), false).filter(block => block.type === 'image').length, 0);
    for (const images of [[{ ...image, data: 'bad!!' }], [{ ...image, mime_type: 'text/plain' }], Array(5).fill(image), [{ ...image, data: data + 'A'.repeat(256 * 1024) }]]) {
        assert.throws(() => validateInput({ ...base, messages: [{ role: 'user', content: '', images }] }), { bridgeCode: 'INVALID_REQUEST' });
    }
    assert.throws(() => validateInput({ ...base, messages: [{ role: 'assistant', content: '', images: [image] }] }), { bridgeCode: 'INVALID_REQUEST' });
    assert.equal(serializeError({ bridgeCode: 'IMAGE_UNSUPPORTED' }).code, 'IMAGE_UNSUPPORTED');
});

test('Malformed agent identifiers cannot select another session', () => {
    const input = { model: '', messages: [], available_tools: [] };
    for (const agent_id of ['../other', '', 'agent\nother', 3]) assert.throws(() => validateInput({ ...input, agent_id }), { bridgeCode: 'INVALID_REQUEST' });
    assert.equal(validateInput({ ...input, agent_id: 'agent_2' }).agent_id, 'agent_2');
});

test('Structured CLI result becomes a Godot chat completion', () => {
    const result = normalizeResult({ subtype: 'success', structured_output: { content: '你好', actions: [{ name: 'read_script', arguments: { path: 'res://player.gd' } }] } }, true);
    assert.equal(result.choices[0].message.content, '你好');
    const call = result.choices[0].message.tool_calls[0];
    assert.equal(call.function.name, 'read_script');
    assert.deepEqual(JSON.parse(call.function.arguments), { path: 'res://player.gd' });
});

test('Plain JSON output is accepted without inventing tool calls', () => {
    const result = normalizeResult({ result: JSON.stringify({ content: '完成', actions: [] }) }, false);
    assert.equal(result.choices[0].message.content, '完成');
    assert(!result.choices[0].message.tool_calls);
});

test('Official CLI JSON event arrays use the final result only', () => {
    const events = [
        { type: 'message', role: 'user', content: 'untrusted' },
        { type: 'message', role: 'assistant', content: 'intermediate' },
        { type: 'result', subtype: 'success', is_error: false, result: JSON.stringify({ content: 'CODEBUDDY_ACCOUNT_OK', actions: [] }) },
    ];
    assert.equal(normalizeResult(events, false).choices[0].message.content, 'CODEBUDDY_ACCOUNT_OK');
    assert.throws(() => normalizeResult(events.slice(0, 2), false));
    assert.throws(() => normalizeResult([...events, { type: 'result', is_error: true }], false));
});

test('Complete fenced JSON accepts CRLF, no language and uppercase JSON', () => {
    const body = JSON.stringify({ content: 'ok', actions: [] });
    for (const fenced of ['```json\n' + body + '\n```', '```JSON\r\n' + body + '\r\n```', '```\n' + body + '\n```']) {
        assert.equal(normalizeResult({ result: fenced }, false).choices[0].message.content, 'ok');
    }
    assert.throws(() => normalizeResult({ result: 'explanation\n```json\n' + body + '\n```' }, false), { bridgeCode: 'INVALID_RESPONSE' });
});

test('Permission updates inherit kind only for the same live tool and session', () => {
    const state = createToolKindState(2);
    const update = (id, kind, extra = {}, sessionId = 'session-a', type = 'tool_call') => state.update({ sessionId, update: { sessionUpdate: type, toolCallId: id, kind, ...extra } });
    state.begin('session-a');
    update('read-a', 'read');
    update('edit-a', 'edit');
    update('read-a', undefined, { status: 'pending' }, 'session-a', 'tool_call_update');
    assert.deepEqual(state.resolve('session-a', { toolCallId: 'read-a' }), { kind: 'read', kind_source: 'notification' });
    assert.equal(state.resolve('session-a', { toolCallId: 'read-a', kind: null }).kind, 'read');
    assert.equal(state.resolve('session-a', { toolCallId: 'edit-a' }).kind, 'edit');
    assert.equal(state.resolve('session-b', { toolCallId: 'read-a', kind: 'read' }).kind, 'missing');
    assert.equal(state.resolve('session-a', { toolCallId: 'unknown', title: 'Read', name: 'Read' }).kind, 'missing');
    assert.equal(state.resolve('session-a', { toolCallId: 'read-a', kind: 'execute' }).kind, 'execute');
    assert.equal(state.resolve('session-a', { kind: 'read' }).kind, 'missing');
    update('read-a', 'execute', {}, 'session-b');
    assert.equal(state.resolve('session-a', { toolCallId: 'read-a' }).kind, 'read');
    update('overflow', 'read');
    assert.equal(state.resolve('session-a', { toolCallId: 'overflow' }).kind, 'missing');
    update('read-a', 'execute', {}, 'session-a', 'tool_call_update');
    assert.equal(state.resolve('session-a', { toolCallId: 'read-a' }).kind, 'execute');
    update('read-a', undefined, { status: 'completed' }, 'session-a', 'tool_call_update');
    assert.equal(state.resolve('session-a', { toolCallId: 'read-a' }).kind, 'missing');
    update('edit-a', undefined);
    assert.equal(state.resolve('session-a', { toolCallId: 'edit-a' }).kind, 'missing');
    update('fresh', 'read');
    state.begin('session-a');
    assert.equal(state.resolve('session-a', { toolCallId: 'fresh' }).kind, 'missing');
    update('fresh', 'read');
    state.clear();
    assert.equal(state.resolve('session-a', { toolCallId: 'fresh' }).kind, 'missing');
});

test('Active model waits exceed 120 seconds, expire on inactivity and retain the hard cap across approvals', () => {
    let time = 0;
    const budget = createWaitBudget(() => time);
    budget.resume();
    time = 125000;
    assert.equal(budget.snapshot().expired, '');
    time = 299999;
    budget.touch();
    time = 599998;
    assert.equal(budget.snapshot().expired, '');
    time++;
    assert.equal(budget.snapshot().expired, 'idle');
    budget.pause();
    const spent = budget.snapshot().elapsed_ms;
    time += 3600000;
    assert.equal(budget.snapshot().elapsed_ms, spent);
    budget.resume();
    assert.equal(budget.snapshot().idle_ms, 0);
    while (budget.snapshot().elapsed_ms < 1800000) {
        time += Math.min(100000, 1800000 - budget.snapshot().elapsed_ms);
        budget.touch();
    }
    assert.equal(budget.snapshot().expired, 'hard');
    assert.equal(budget.snapshot().remaining_ms, 0);
});

test('Progress carries only public answer text and diagnostics are a strict whitelist', () => {
    const { safeDiagnostics } = require('../../tools/codebuddy_cli/godot_bridge');
    assert.deepEqual(progressUpdate({ sessionUpdate: 'agent_message_chunk', content: { type: 'text', text: '正文' } }), { activity: 'responding', content_delta: '正文' });
    for (const sessionUpdate of ['agent_thought_chunk', 'plan', 'tool_call', 'tool_call_update']) {
        assert(!JSON.stringify(progressUpdate({ sessionUpdate, content: { type: 'text', text: 'private' }, title: 'private' })).includes('private'));
    }
    assert.equal(progressUpdate({ sessionUpdate: 'config_option_update' }), null);
    const info = { elapsed_ms: 300000, idle_ms: 300000, stdout_bytes: 1024, stderr_bytes: 88, timeout_kind: 'idle', stage: 'analyzing', failure_hint: 'NETWORK_ERROR', stderr: 'private', token: 'private' };
    const failure = serializeError({ bridgeCode: 'TIMEOUT', diagnostics: info });
    assert.equal(failure.diagnostics.timeout_kind, 'idle');
    assert.equal(failure.diagnostics.failure_hint, 'NETWORK_ERROR');
    assert(!JSON.stringify(failure).includes('private'));
    assert.deepEqual(safeDiagnostics({ elapsed_ms: -1, stage: 'private', timeout_kind: 'private', failure_hint: 'private' }), {});
    assert.notEqual(serializeError({ bridgeCode: 'OUTPUT_LIMIT' }).message, failure.message);
});

test('RPC framing counts UTF-8 bytes, accepts boundary frames and rejects oversized complete/incomplete frames', async () => {
    const wire = Buffer.from(JSON.stringify({ text: '中文' }) + '\n');
    const events = [];
    const drain = async (chunks, maxMessageBytes) => {
        const tap = rpcTrace('incoming', (event) => events.push(event), { maxMessageBytes });
        const result = [];
        const reader = tap.readable.pipeTo(new WritableStream({ write(chunk) { result.push(Buffer.from(chunk)); } }));
        const writer = tap.writable.getWriter();
        const write = (async () => { for (const chunk of chunks) await writer.write(chunk); await writer.close(); })();
        await Promise.all([reader, write]);
        return Buffer.concat(result);
    };
    // Split inside a multi-byte character and carry the frame across chunks.
    assert((await drain([wire.subarray(0, 10), wire.subarray(10)], wire.length - 1)).equals(wire));
    await assert.rejects(drain([wire], wire.length - 2), { bridgeCode: 'OUTPUT_LIMIT' });
    await assert.rejects(drain([wire.subarray(0, -1)], wire.length - 2), { bridgeCode: 'OUTPUT_LIMIT' });
    const small = Buffer.from('{}\n');
    assert((await drain([Buffer.concat(Array(100).fill(small))], 2)).equals(Buffer.concat(Array(100).fill(small))), 'Limit is per frame, not per chunk');
    assert.equal(events.filter(event => event === 'rpc_line_limit').length, 2);
});

test('RPC buffer accounts only unconsumed bytes and preserves malformed/CRLF/trailing-frame handling', async () => {
    const acp = await import('../../tools/codebuddy_cli/node_modules/@agentclientprotocol/sdk/dist/acp.js');
    const packet = { jsonrpc: '2.0', id: 1, result: { text: '中文' } };
    const wire = Buffer.from(' \r\nnot-json\nnull\n' + JSON.stringify(packet) + '\r\n' + JSON.stringify(packet));
    const errors = [];
    const output = [];
    const stream = boundedRpcStream(acp, new WritableStream({ write(bytes) { output.push(Buffer.from(bytes)); } }), new ReadableStream({ start(controller) {
        controller.enqueue(wire.subarray(0, 35));
        controller.enqueue(wire.subarray(35));
        controller.close();
    } }), () => {}, error => errors.push(error), () => {}, { maxMessageBytes: 256, maxBufferedBytes: 4096 });
    const packets = [];
    await stream.readable.pipeTo(new WritableStream({ write(message) { packets.push(message); } }));
    assert.deepEqual(packets, [packet, packet]);
    assert.equal(stream.bufferedBytes, 0);
    assert.equal(errors.length, 0);
    assert(Buffer.concat(output).toString().includes('error'), 'SDK must still reject malformed JSON');
});

test('RPC buffer stops queued-data growth when its dispatcher is stalled', async () => {
    const acp = await import('../../tools/codebuddy_cli/node_modules/@agentclientprotocol/sdk/dist/acp.js');
    const wire = Buffer.from(JSON.stringify({ jsonrpc: '2.0', id: 1, result: { text: 'x'.repeat(256) } }) + '\n');
    let remaining = 1000;
    const source = new ReadableStream({ pull(controller) { if (remaining--) controller.enqueue(wire); else controller.close(); } });
    let resolveLimit;
    const reached = new Promise(resolve => { resolveLimit = resolve; });
    const stream = boundedRpcStream(acp, new WritableStream(), source, () => {}, resolveLimit, () => {}, { maxMessageBytes: 1024, maxBufferedBytes: 4096 });
    // Do not consume the decoded queue until the guard reports its limit.
    assert.equal((await reached).bridgeCode, 'OUTPUT_LIMIT');
    assert(remaining > 900, 'A stalled decoder must stop reading before all data is buffered');
    const reader = stream.readable.getReader();
    await assert.rejects(async () => { while (!(await reader.read()).done) {} }, { bridgeCode: 'OUTPUT_LIMIT' });
    assert.equal(stream.bufferedBytes, 0);
});

test('Persistent trace logs are bounded, redact payloads and never change RPC bytes', async t => {
    const fs = require('node:fs');
    const path = require('node:path');
    const directory = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'godot-acp-log-test-'));
    t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
    const log = createTraceLog(directory, 4096);
    log.write('permission_decided', { request: 1, decision: 'reject_once', kind: 'execute', content: 'PRIVATE_SENTINEL', stderr: 'PRIVATE_SENTINEL', path: 'PRIVATE_SENTINEL', token: 'PRIVATE_SENTINEL' });
    const wire = Buffer.from(JSON.stringify({ jsonrpc: '2.0', id: 'PRIVATE_SENTINEL', method: 'fs/read_text_file', params: { path: 'PRIVATE_SENTINEL', content: 'PRIVATE_SENTINEL' } }) + '\n');
    const tap = rpcTrace('incoming', (event, fields) => log.write(event, fields));
    const output = [];
    const drain = tap.readable.pipeTo(new WritableStream({ write(chunk) { output.push(Buffer.from(chunk)); } }));
    const writer = tap.writable.getWriter();
    await writer.write(wire.subarray(0, 21));
    await writer.write(wire.subarray(21));
    await writer.close();
    await drain;
    assert(Buffer.concat(output).equals(wire), 'Diagnostic tap changed CLI protocol bytes');
    let text = fs.readFileSync(log.file, 'utf8');
    assert(!text.includes('PRIVATE_SENTINEL'));
    const records = text.trim().split('\n').map(line => JSON.parse(line));
    assert.equal(records[0].decision, 'reject_once');
    assert.equal(records[1].method, 'fs/read_text_file');
    assert.match(records[1].rpc_id_hash, /^[a-f0-9]{16}$/);
    log.write('rpc_method', { method: 'PRIVATE_SENTINEL', update: 'PRIVATE_SENTINEL' });
    for (let index = 0; index < 1000; index++) log.write('wait_snapshot', { request: 1, elapsed_ms: index });
    assert(fs.statSync(log.file).size <= 4096);
    text = fs.readFileSync(log.file, 'utf8');
    assert(!text.includes('PRIVATE_SENTINEL'));
    assert.doesNotThrow(() => text.trim().split('\n').map(line => JSON.parse(line)));
    const occupied = path.join(directory, 'occupied');
    fs.writeFileSync(occupied, 'test');
    assert.doesNotThrow(() => createTraceLog(occupied).write('bridge_start'));
});

test('ACP stdout streams public text before completion and keeps diagnostics safe on failure', { timeout: 20000 }, async t => {
    const fs = require('node:fs');
    const path = require('node:path');
    const http = require('node:http');
    const { spawn } = require('node:child_process');
    const directory = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'godot-acp-stream-test-'));
    let requests = 0;
    const server = http.createServer((request, response) => {
        requests++;
        request.resume();
        response.writeHead(200, { 'Content-Type': 'application/json' });
        response.end(JSON.stringify({ choices: [{ message: { role: 'assistant', content: requests === 2 ? 'NATIVE_STREAM_NEXT_OK' : 'NATIVE_STREAM_VISIBLE_OK' }, finish_reason: 'stop' }] }));
    });
    let child;
    let closed;
    t.after(async () => {
        try {
            if (child) {
                // A failed ACP request may never consume EOF. The test timeout
                // does not bound after hooks, so force this owned child to exit.
                const killTimer = setTimeout(() => child.kill('SIGKILL'), 2000);
                try {
                    child.stdin.end();
                    await closed;
                } finally {
                    clearTimeout(killTimer);
                }
            }
        } finally {
            server.closeAllConnections();
            await new Promise(resolve => server.close(resolve));
            fs.rmSync(directory, { recursive: true, force: true });
        }
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    child = spawn(process.execPath, [path.resolve(__dirname, '../../tools/codebuddy_cli/godot_bridge.js'), 'session', path.join(__dirname, 'mock_codebuddy_cli.js')], { env: { ...process.env, AI_CHAT_TEST_URL: 'http://127.0.0.1:' + server.address().port, GODOT_ACP_LOG_DIRECTORY: path.join(directory, 'logs') }, stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true });
    closed = require('node:events').once(child, 'close');
    const packets = [];
    let raw = '';
    let pending = '';
    child.stdout.setEncoding('utf8');
    child.stdout.on('data', text => {
        raw += text;
        pending += text;
        let newline;
        while ((newline = pending.indexOf('\n')) >= 0) {
            packets.push(JSON.parse(pending.slice(0, newline)));
            pending = pending.slice(newline + 1);
        }
    });
    let stderr = '';
    child.stderr.on('data', bytes => { stderr += bytes.toString(); });
    const wait = async condition => {
        const deadline = Date.now() + 10000;
        while (!condition() && Date.now() < deadline) await new Promise(resolve => setTimeout(resolve, 20));
        assert(condition(), 'ACP stream condition timed out');
    };
    const submit = name => {
        const requestPath = path.join(directory, name + '.json');
        fs.writeFileSync(requestPath, JSON.stringify({ model: 'mock-model', available_tools: [], messages: [{ role: 'user', content: 'case:' + name }] }));
        child.stdin.write(JSON.stringify({ path: requestPath }) + '\n');
    };
    submit('native_progress');
    await wait(() => packets.filter(packet => packet.event === 'progress' && packet.content_delta).length >= 2);
    assert.equal(packets.filter(packet => packet.choices).length, 0);
    await wait(() => packets.some(packet => packet.choices));
    assert.equal(packets.filter(packet => packet.event === 'progress').map(packet => packet.content_delta).join(''), 'NATIVE_STREAM_VISIBLE_OK');
    assert.equal(packets.find(packet => packet.choices).choices[0].message.content, 'NATIVE_STREAM_VISIBLE_OK');
    submit('native_stream_next');
    await wait(() => packets.filter(packet => packet.choices).length === 2);
    const beforeError = packets.length;
    submit('native_progress_error');
    await wait(() => packets.some(packet => packet.error));
    assert.equal(requests, 3, 'Progress caused retries or additional model requests');
    assert.equal(packets.slice(beforeError).filter(packet => packet.event === 'progress').map(packet => packet.content_delta).join(''), 'NATIVE_STREAM_VISIBLE_OK');
    assert(packets.find(packet => packet.error).error.diagnostics.stderr_bytes > 0);
    assert(!raw.includes('PRIVATE_') && !stderr.includes('PRIVATE_'), 'Private thought or account diagnostics escaped the bridge');
    const files = fs.readdirSync(path.join(directory, 'logs'));
    assert.equal(files.length, 1);
    const trace = fs.readFileSync(path.join(directory, 'logs', files[0]), 'utf8');
    assert(!trace.includes('PRIVATE_') && !trace.includes('NATIVE_STREAM_'), 'Trace persisted private payload or reply text');
    const records = trace.trim().split('\n').map(line => JSON.parse(line));
    assert.equal(records.filter(record => record.event === 'user_request_received').length, 3);
    assert.equal(records.filter(record => record.event === 'model_prompt_sent').length, 3);
    assert(records.some(record => record.event === 'session_notification' && record.update === 'agent_thought_chunk'));
    const sent = records.find(record => record.event === 'rpc_method' && record.direction === 'outgoing' && record.method === 'session/prompt');
    assert(records.some(record => record.event === 'rpc_result' && record.direction === 'incoming' && record.rpc_id_hash === sent.rpc_id_hash));
    assert(records.some(record => record.event === 'request_failed' && record.stderr_bytes > 0 && record.read_count === 0));
});

test('Diagnostic classification does not conflate dependencies, format and login', () => {
    assert.equal(classifyDiagnostics("Cannot find module 'job-object.node' token=private"), 'NATIVE_COMPONENT_MISSING');
    assert.equal(classifyDiagnostics('Please login token=private'), 'AUTH_REQUIRED');
    assert.equal(classifyDiagnostics('Invalid model secret=private'), 'MODEL_UNAVAILABLE');
    assert.equal(classifyDiagnostics('fetch failed https://example.invalid/?token=private'), 'NETWORK_ERROR');
    assert.equal(classifyDiagnostics('arbitrary stderr secret=private'), 'PROCESS_EXIT');
    const error = Object.assign(new Error('token=private https://example.invalid'), { bridgeCode: 'NATIVE_COMPONENT_MISSING', exitCode: 1 });
    const serialized = serializeError(error);
    assert.equal(serialized.code, 'NATIVE_COMPONENT_MISSING');
    assert.equal(serialized.exit_code, 1);
    assert(!JSON.stringify(serialized).includes('private'));
    assert.equal(serializeError(new Error('token=private')).code, 'BRIDGE_ERROR');
    assert.throws(() => normalizeResult({ result: '{token=private' }, false), { bridgeCode: 'INVALID_RESPONSE' });
    assert.throws(() => normalizeResult({ is_error: true, errors: ['Invalid model token=private'] }, false), { bridgeCode: 'MODEL_UNAVAILABLE' });
});

test('Failed, malformed, excessive and forbidden actions are rejected', () => {
    assert.throws(() => normalizeResult({ is_error: true }, true));
    assert.throws(() => normalizeResult({ structured_output: { content: '', actions: [{ name: 'Bash', arguments: {} }] } }, true));
    assert.throws(() => normalizeResult({ structured_output: { content: '', actions: [{ name: 'write_script', arguments: {} }] } }, false));
    assert.throws(() => normalizeResult({ structured_output: { content: '', actions: Array(9).fill({ name: 'read_logs', arguments: {} }) } }, true));
    assert.throws(() => normalizeResult({ result: 'bad JSON' }, true));
});


test('Read-only CodeBuddy capability tuple is preserved and rejects contradictory or writable tools', () => {
    const request = { messages: [{ role: 'user', content: 'Review' }], model: '', available_tools: [{ function: { name: 'read_file' } }], tool_context: { permission_enabled: true, tool_rounds: 0, max_tool_rounds: null, consultation_only: true, writes_allowed: false, execution_allowed: false } };
    const validated = validateInput(request);
    assert.equal(validated.tool_context.consultation_only, true);
    assert.equal(validated.tool_context.writes_allowed, false);
    assert.equal(validated.tool_context.execution_allowed, false);
    assert.throws(() => validateInput({ ...request, tool_context: { ...request.tool_context, writes_allowed: true } }), { bridgeCode: 'INVALID_REQUEST' });
    assert.throws(() => validateInput({ ...request, available_tools: [{ function: { name: 'delegate_review' } }] }), { bridgeCode: 'INVALID_REQUEST' });
    const args = sessionArguments('', '', true, true);
    assert.equal(args[args.indexOf('--tools') + 1], 'Read,Bash');
    assert(!args[args.indexOf('--tools') + 1].includes('Write'));
    assert(!args[args.indexOf('--tools') + 1].includes('Glob'));
    assert(!args[args.indexOf('--tools') + 1].includes('Grep'));
});
