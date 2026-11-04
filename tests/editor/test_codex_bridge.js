'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const { argumentsFor, promptFor, completion } = require('../../tools/codex_cli/godot_bridge');
const input = {
    model: '', messages: [{ role: 'user', content: '你好' }],
    available_tools: [{ type: 'function', function: { name: 'read_file' } }],
    tool_context: { permission_enabled: true, tool_rounds: 0, max_tool_rounds: null },
};

test('Codex arguments preserve default model, isolate config and disable native execution', () => {
    const args = argumentsFor('', 'schema.json');
    assert(!args.includes('--model'));
    assert(args.includes('--ignore-user-config'));
    assert(args.includes('--ephemeral'));
    assert(args.includes('read-only'));
    assert(args.includes('features.shell_tool=false'));
    assert(args.includes('features.apply_patch_freeform=false'));
    assert(!args.some(arg => arg.includes('dangerously')));
    assert.equal(argumentsFor('custom/model', 'schema').at(-2), 'custom/model');
});

test('Godot context preserves Chinese, tool results and current permissions', () => {
    const prompt = promptFor(input);
    assert(prompt.includes('你好'));
    assert(prompt.includes('permission_enabled'));
    assert(prompt.includes('Never claim success'));
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
            { events: [{ type: 'turn.failed', error: { message: 'authentication required' } }], success: false, exitCode: 23, errorCode: 'AUTH_REQUIRED' },
            { events: [{ type: 'error', message: 'private-token-must-not-leak' }], success: false, exitCode: 17, errorCode: 'PROCESS_EXIT' },
            { events: [{ type: 'item.completed', item: { type: 'agent_message', text: '{"content":"unfinished","actions":[]}' } }], success: false },
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
            }
        }
    } finally {
        fs.rmSync(directory, { recursive: true, force: true });
    }
});
