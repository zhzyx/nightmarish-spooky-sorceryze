'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const { argumentsFor, promptFor, completion, validateRequest } = require('../../tools/codex_cli/godot_bridge');
const input = {
    model: '', messages: [{ role: 'user', content: '你好' }],
    available_tools: [{ type: 'function', function: { name: 'read_file' } }],
    tool_context: { permission_enabled: true, tool_rounds: 0, max_tool_rounds: null },
};

test('consultation distinguishes malformed tools, version skew and disallowed writes', () => {
    const tool_context = { ...input.tool_context, consultation_only: true, writes_allowed: false, execution_allowed: false };
    for (const [tool, code] of [[null, 'INVALID_REQUEST'], [{ function: { name: 'future_read_tool' } }, 'UNSUPPORTED_HOST_TOOL'],
        [{ function: { name: 'write_file' } }, 'INVALID_REQUEST']]) {
        assert.throws(() => validateRequest({ ...input, tool_context, available_tools: [tool] }), { bridgeCode: code });
    }
});

const typedTool = {
    type: 'function', function: { name: 'run_command', parameters: {
        type: 'object', additionalProperties: false, required: ['command'], properties: {
            command: { type: 'string' }, cwd: { type: 'string' },
            timeout_seconds: { type: 'integer', minimum: 1, maximum: 3600 },
        },
    } },
};

test('output schema constrains active tools and typed arguments, retaining dynamic fallback', () => {
    const { outputSchemaFor } = require('../../tools/codex_cli/action_schema');
    const { SCHEMA } = require('../../tools/codex_cli/godot_bridge');
    const dynamic = { type: 'function', function: { name: 'editor_action', parameters: {
        type: 'object', properties: { action: { type: 'string' }, value: {} },
        required: ['action'], additionalProperties: false,
    } } };
    const schema = outputSchemaFor({ available_tools: [typedTool, dynamic] }, SCHEMA);
    const [typed, fallback] = schema.properties.actions.items.anyOf;
    assert.deepEqual(typed.properties.name.enum, ['run_command']);
    assert.equal(typed.properties.arguments.type, 'object');
    assert.deepEqual(typed.properties.arguments.required, ['command', 'cwd', 'timeout_seconds']);
    assert.deepEqual(typed.properties.arguments.properties.cwd.anyOf, [{ type: 'string' }, { type: 'null' }]);
    assert.equal(fallback.properties.arguments.type, 'string');
    assert.equal(outputSchemaFor({ available_tools: [] }, SCHEMA).properties.actions.maxItems, 0);
    assert.equal(typedTool.function.parameters.properties.cwd.type, 'string');
    assert.deepEqual(typedTool.function.parameters.required, ['command']);
});

test('typed commands avoid double encoding and preserve optional host defaults', () => {
    const configured = { ...input, available_tools: [typedTool] };
    const command = 'python3 - <<\'PY\'\nprint("中文 \\\\ \\\"quoted\\\"")\nPY';
    const wire = JSON.stringify({ content: '继续', actions: [{ name: 'run_command',
        arguments: { command, cwd: null, timeout_seconds: null } }] });
    const calls = completion(wire, configured).choices[0].message.tool_calls;
    assert.deepEqual(JSON.parse(calls[0].function.arguments), { command });
    const legacy = JSON.stringify({ content: '', actions: [{ name: 'run_command', arguments: JSON.stringify({ command }) }] });
    assert.deepEqual(JSON.parse(completion(legacy, configured).choices[0].message.tool_calls[0].function.arguments), { command });
    const fenced = completion('```json\n' + wire + '\n```', configured);
    assert.equal(fenced.choices[0].message.tool_calls.length, 1);
    assert.throws(() => completion('Here is the result:\n' + wire, configured));
});

test('required nulls and invalid batches are rejected without partial calls', () => {
    const configured = { ...input, available_tools: [typedTool] };
    for (const args of [null, [], { command: null }, {}, { command: 'ok', unknown: true },
        { command: 'ok', timeout_seconds: 0 }, { command: 'ok', timeout_seconds: '20' }]) {
        assert.throws(() => completion(JSON.stringify({ content: '', actions: [
            { name: 'run_command', arguments: { command: 'valid first action' } },
            { name: 'run_command', arguments: args },
        ] }), configured));
    }
    assert.throws(() => completion(JSON.stringify({ content: '', actions: [
        { name: 'run_command', arguments: { command: 'ok' } },
        { name: 'write_file', arguments: '{}' },
    ] }), configured));
    assert.throws(() => completion(JSON.stringify({ content: 1, actions: [] }), configured));
    assert.throws(() => completion(JSON.stringify({ content: '', actions: Array(9).fill({ name: 'run_command', arguments: '{}' }) }), configured));
    const nullable = { ...typedTool, function: { ...typedTool.function, parameters: {
        type: 'object', additionalProperties: false, required: ['command'],
        properties: { command: { type: ['string', 'null'] } },
    } } };
    const preserved = completion(JSON.stringify({ content: '', actions: [{ name: 'run_command', arguments: { command: null } }] }),
        { ...input, available_tools: [nullable] });
    assert.deepEqual(JSON.parse(preserved.choices[0].message.tool_calls[0].function.arguments), { command: null });
});

test('Codex arguments preserve default model, isolate config and disable native execution', () => {
    const args = argumentsFor('', 'schema.json');
    assert(!args.includes('--model'));
    assert(args.includes('--ignore-user-config'));
    assert(args.includes('--ephemeral'));
    assert(args.includes('read-only'));
    assert(args.includes('features.shell_tool=false'));
    assert(args.includes('approval_policy="never"'));
    assert(args.includes('features.apply_patch_freeform=false'));
    assert(!args.some(arg => arg.includes('dangerously')));
    assert.equal(argumentsFor('custom/model', 'schema').at(-2), 'custom/model');
});

test('consultation preserves host mode and rejects write capabilities before subprocess launch', () => {
    const consultation = { ...input, tool_context: { ...input.tool_context,
        consultation_only: true, writes_allowed: false, execution_allowed: false } };
    assert.equal(validateRequest(consultation).tool_context.consultation_only, true);
    for (const name of ['write_file', 'write_script', 'run_command', 'build_engine', 'restart_engine',
        'rollback_engine', 'complete_delivery', 'run_test', 'check_script', 'delegate_review']) {
        const broadened = { ...consultation, available_tools: [{ type: 'function', function: { name } }] };
        assert.throws(() => validateRequest(broadened));
        assert.throws(() => completion(JSON.stringify({ content: '', actions: [{ name, arguments: '{}' }] }), broadened));
    }
    const parentRead = { ...consultation, available_tools: [{ type: 'function', function: { name: 'get_parent_context' } }] };
    assert.equal(validateRequest(parentRead).tool_context.consultation_only, true);
    assert.equal(completion(JSON.stringify({ content: '', actions: [{ name: 'get_parent_context', arguments: '{}' }] }), parentRead)
        .choices[0].message.tool_calls[0].function.name, 'get_parent_context');
    assert.throws(() => validateRequest({ ...consultation, tool_context: { ...consultation.tool_context, writes_allowed: true } }));
    assert.equal(completion('{"content":"read","actions":[{"name":"read_file","arguments":"{}"}]}', consultation).choices[0].finish_reason, 'tool_calls');
});

test('Godot context preserves Chinese, tool results and current permissions', () => {
    const prompt = promptFor(input);
    assert(prompt.includes('你好'));
    assert(prompt.includes('permission_enabled'));
    assert(prompt.includes('Never claim success'));
    assert(prompt.includes('route_engine_message') && prompt.includes('planning_required'));
});

test('consultation accepts semantic editor state but refuses editor actions', () => {
    const names = ['read_file', 'read_script', 'read_logs', 'list_scripts', 'list_directory', 'get_editor_state'];
    const consultation = { ...input,
        available_tools: names.map(name => ({ type: 'function', function: { name } })),
        tool_context: { ...input.tool_context, consultation_only: true, writes_allowed: false, execution_allowed: false } };
    const validated = validateRequest(consultation);
    const state = JSON.stringify({ content: '', actions: [{ name: 'get_editor_state', arguments: '{"scope":"selection"}' }] });
    assert.equal(completion(state, validated).choices[0].message.tool_calls[0].function.name, 'get_editor_state');
    const broadened = { ...consultation, available_tools: [...consultation.available_tools,
        { type: 'function', function: { name: 'editor_action' } }] };
    assert.throws(() => validateRequest(broadened));
    assert.throws(() => completion(JSON.stringify({ content: '', actions: [{ name: 'editor_action', arguments: '{}' }] }), broadened));
});

test('structured proposals are translated to host tool calls', () => {
    const result = completion(JSON.stringify({
        content: '读取文件', actions: [{ name: 'read_file', arguments: '{"path":"res://main.gd"}' }],
    }), input);
    const message = result.choices[0].message;
    assert.equal(message.content, '读取文件');
    assert.deepEqual(JSON.parse(message.tool_calls[0].function.arguments), { path: 'res://main.gd' });
    assert.equal(result.choices[0].finish_reason, 'tool_calls');
});

test('malformed, unavailable and disabled actions never reach the host', () => {
    for (const action of [
        { name: 'run_command', arguments: '{}' },
        { name: 'read_file', arguments: 'bad json' },
        { name: 'read_file', arguments: '[]' },
    ]) {
        assert.throws(() => completion(JSON.stringify({ content: '', actions: [action] }), input));
    }
    assert.throws(() => completion('not JSON', input));
    assert.throws(() => completion(JSON.stringify({ content: '', actions: [
        { name: 'read_file', arguments: '{}' },
    ] }), { ...input, available_tools: [] }));
});

test('ordinary chat returns a final assistant message', () => {
    const result = completion('{"content":"你好！","actions":[]}', { ...input, available_tools: [] });
    assert.equal(result.choices[0].message.content, '你好！');
    assert.equal(result.choices[0].finish_reason, 'stop');
});

test('Codex subprocess handles UTF-8 JSONL, failed turns and missing completion without leaking stderr', () => {
    const fs = require('node:fs');
    const os = require('node:os');
    const path = require('node:path');
    const { spawnSync } = require('node:child_process');
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'godot-codex-test-'));
    try {
        const entry = path.join(directory, 'mock.js');
        const request = path.join(directory, 'request.json');
        fs.writeFileSync(request, JSON.stringify(input));
        const cases = [
            { events: [
                { type: 'thread.started', thread_id: 'mock' },
                { type: 'item.completed', item: { type: 'agent_message', text: '{"content":"中文回复","actions":[]}' } },
                { type: 'turn.completed', usage: {} },
            ], success: true },
            { events: [
                { type: 'error', message: 'Reconnecting... 2/5 (request timed out)' },
                { type: 'item.completed', item: { type: 'agent_message', text: '{"content":"中文回复","actions":[]}' } },
                { type: 'turn.completed', usage: {} },
            ], success: true },
            { events: [{ type: 'error', message: "Codex ran out of room in the model's context window." },
                { type: 'turn.failed', error: { message: 'Turn failed' } }], success: false, exitCode: 1, errorCode: 'CONTEXT_LIMIT' },
            { events: [{ type: 'turn.failed', error: { code: 'context_length_exceeded' } }], success: false, exitCode: 1, errorCode: 'CONTEXT_LIMIT' },
            { events: [{ type: 'turn.failed', error: { message: 'authentication required' } }], success: false, exitCode: 23, errorCode: 'AUTH_REQUIRED' },
            { events: [{ type: 'error', message: 'private-token-must-not-leak' }], success: false, exitCode: 17, errorCode: 'PROCESS_EXIT' },
            { events: [{ type: 'item.completed', item: { type: 'agent_message', text: '{"content":"unfinished","actions":[]}' } }], success: false },
            { events: [
                { type: 'item.completed', item: { type: 'agent_message', text: '{"content":"private-model-text","actions":[{"name":"read_file","arguments":"private-command-invalid-json"}]}' } },
                { type: 'turn.completed' },
            ], success: false, errorCode: 'INVALID_ACTION', exitCode: undefined, validationReason: 'argument_json' },
        ];
        for (const scenario of cases) {
            const wire = scenario.events.map(event => JSON.stringify(event)).join('\n');
            fs.writeFileSync(entry, `process.stdin.resume(); process.stdin.on('end', () => {
                process.stderr.write('private-token-must-not-leak');
                const bytes = Buffer.from(${JSON.stringify(wire)});
                for (let i = 0; i < bytes.length; i++) process.stdout.write(bytes.subarray(i, i + 1));
                process.exitCode = ${scenario.exitCode || 0};
            });`);
            const result = spawnSync(process.execPath, [path.resolve(__dirname, '../../tools/codex_cli/godot_bridge.js'), 'chat', entry, request],
                { encoding: 'utf8', timeout: 10000 });
            assert(!result.error, String(result.error));
            assert(!result.stdout.includes('private-token'));
            const packet = JSON.parse(result.stdout);
            if (scenario.success) {
                assert.equal(result.status, 0, result.stdout);
                assert.equal(packet.choices[0].message.content, '中文回复');
            } else {
                assert.equal(result.status, 1);
                assert(packet.error.code);
                if (scenario.errorCode) {
                    assert.equal(packet.error.code, scenario.errorCode);
                    assert.equal(packet.error.exit_code, scenario.exitCode);
                }
                if (scenario.validationReason) {
                    assert.equal(packet.error.validation_reason, scenario.validationReason);
                    assert.equal(packet.error.action_index, 0);
                    const retained = fs.readFileSync(request + '.failure.json', 'utf8');
                    assert(!retained.includes('private-model-text'));
                    assert(!retained.includes('private-command'));
                    assert.equal(JSON.parse(retained).validation_reason, 'argument_json');
                }
            }
        }
    } finally {
        fs.rmSync(directory, { recursive: true, force: true });
    }
});

// Semantic control uses the same host-proposal transport as existing tools.
test('semantic actions are discoverable and disabled permissions reject them', () => {
    const { validateInput } = require('../../tools/codebuddy_cli/godot_bridge');
    for (const name of ['get_editor_state', 'editor_action']) {
        const configured = { ...input, available_tools: [{ type: 'function', function: { name } }] };
        validateInput(configured);
        const envelope = JSON.stringify({ content: '', actions: [{ name, arguments: '{"action":"highlight","target":"scene_tree"}' }] });
        const result = completion(envelope, configured);
        assert.equal(result.choices[0].message.tool_calls[0].function.name, name);
        assert.throws(() => completion(envelope, { ...configured, available_tools: [] }));
    }
});

test('delivery completion remains an explicit host proposal with its exact typed scope', () => {
    const args = { pr: 7, candidate: 'a'.repeat(40), signed_commit: 'b'.repeat(40), acceptance_items: [{ id: 'one', state: 'done' }] };
    const configured = { ...input, available_tools: [{ type: 'function', function: { name: 'complete_delivery', parameters: {
        type: 'object', properties: { pr: { type: 'integer' }, candidate: { type: 'string' }, signed_commit: { type: 'string' }, acceptance_items: { type: 'array' } },
        required: ['pr', 'candidate', 'signed_commit', 'acceptance_items'],
    } } }] };
    const envelope = JSON.stringify({ content: '', actions: [{ name: 'complete_delivery', arguments: args }] });
    const result = completion(envelope, configured);
    assert.equal(result.choices[0].finish_reason, 'tool_calls');
    const call = result.choices[0].message.tool_calls[0];
    assert.equal(call.function.name, 'complete_delivery');
    assert.deepEqual(JSON.parse(call.function.arguments), args);
    assert.throws(() => completion(envelope, { ...configured, available_tools: [] }));
});

test('images reach the CLI as private attachments with message references and are cleaned up', () => {
    const fs = require('node:fs');
    const os = require('node:os');
    const path = require('node:path');
    const { spawnSync } = require('node:child_process');
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'godot-images-test-'));
    const data = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aRZkAAAAASUVORK5CYII=';
    try {
        const entry = path.join(directory, 'mock.js');
        const request = path.join(directory, 'request.json');
        const observed = path.join(directory, 'observed.json');
        fs.writeFileSync(request, JSON.stringify({ ...input, messages: [
            { role: 'user', content: '看图', images: [{ name: '截图.png', mime_type: 'image/png', data }] },
            { role: 'user', content: '请继续' },
        ] }));
        for (const fail of [false, true]) {
            fs.writeFileSync(entry, `const fs = require('node:fs'); let prompt = '';
                process.stdin.on('data', chunk => prompt += chunk);
                process.stdin.on('end', () => {
                    const index = process.argv.indexOf('--image');
                    const file = process.argv[index + 1];
                    const bytes = fs.readFileSync(file).toString('base64');
                    fs.writeFileSync(${JSON.stringify(observed)}, JSON.stringify({ file, bytes, prompt }));
                    process.stdout.write(JSON.stringify(${fail
                        ? "{ type: 'turn.failed', error: { message: 'authentication required' } }"
                        : "{ type: 'item.completed', item: { type: 'agent_message', text: '{\"content\":\"已读取\",\"actions\":[]}' } }"}) + '\\n');
                    process.stdout.write(JSON.stringify({ type: 'turn.completed' }) + '\\n');
                });`);
            const result = spawnSync(process.execPath, [path.resolve(__dirname, '../../tools/codex_cli/godot_bridge.js'), 'chat', entry, request],
                { encoding: 'utf8', timeout: 10000 });
            assert.equal(result.status, fail ? 1 : 0, result.stdout + result.stderr);
            const captured = JSON.parse(fs.readFileSync(observed));
            assert.equal(captured.bytes, data);
            assert(!captured.prompt.includes(data));
            assert(captured.prompt.includes('"attachment":1'));
            assert(captured.prompt.includes('截图.png'));
            assert(!fs.existsSync(captured.file));
            assert(!fs.existsSync(path.dirname(captured.file)));
        }
    } finally {
        fs.rmSync(directory, { recursive: true, force: true });
    }
});

test('cancelling a pending image request removes private attachments', async () => {
    const fs = require('node:fs');
    const os = require('node:os');
    const path = require('node:path');
    const { spawn } = require('node:child_process');
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'godot-cancel-test-'));
    let child;
    try {
        const entry = path.join(directory, 'mock.js');
        const observed = path.join(directory, 'observed.json');
        const request = path.join(directory, 'request.json');
        fs.writeFileSync(entry, `const fs = require('node:fs');
            fs.writeFileSync(${JSON.stringify(observed)}, JSON.stringify(process.argv[process.argv.indexOf('--image') + 1]));
            process.stdin.resume(); setInterval(() => {}, 1000);`);
        fs.writeFileSync(request, JSON.stringify({ ...input, messages: [{ role: 'user', content: '看图', images: [{
            name: '截图.png', mime_type: 'image/png',
            data: 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aRZkAAAAASUVORK5CYII=',
        }] }] }));
        child = spawn(process.execPath, [path.resolve(__dirname, '../../tools/codex_cli/godot_bridge.js'), 'chat', entry, request], { stdio: 'ignore' });
        const closed = new Promise(resolve => child.once('close', resolve));
        for (let i = 0; i < 200 && !fs.existsSync(observed); i++) await new Promise(resolve => setTimeout(resolve, 10));
        assert(fs.existsSync(observed));
        const file = JSON.parse(fs.readFileSync(observed));
        assert(fs.existsSync(file));
        child.kill('SIGTERM');
        await closed;
        // Windows closes the pipe on forced termination. The independent listener
        // can finish removing private files after the process handle signals.
        for (let i = 0; i < 200 && fs.existsSync(path.dirname(file)); i++) await new Promise(resolve => setTimeout(resolve, 10));
        assert(!fs.existsSync(path.dirname(file)));
    } finally {
        if (child && child.exitCode === null) child.kill();
        fs.rmSync(directory, { recursive: true, force: true });
    }
});
