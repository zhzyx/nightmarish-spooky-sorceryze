'use strict';
// Replay actual HTTP host tool results through the native Codex subprocess bridge.
// This verifies transport bytes, not a full native-editor session or a real provider.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const log = fs.readFileSync(process.argv[2], 'utf8');
assert(log.includes('SEMANTIC_MOCK_BOUNDS_OK'), 'Successful actual host fixture required');
const results = JSON.parse(log.split(/\r?\n/).find(line => line.startsWith('MOCK_RESULTS ')).slice(13));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'semantic-codex-wire-'));
try {
    for (const [name, content] of Object.entries(results)) {
        if (!name.startsWith('state_')) continue;
        const state = JSON.parse(content);
        assert.equal(state.ok, true);
        assert(Buffer.byteLength(content, 'utf8') <= 16 * 1024);
        const input = {
            model: 'offline-semantic',
            messages: [{ role: 'user', content: name }, { role: 'tool', content, tool_call_id: name }],
            available_tools: [{ type: 'function', function: { name: 'get_editor_state' } }],
            tool_context: { permission_enabled: true, tool_rounds: 1, max_tool_rounds: null },
        };
        const request = path.join(directory, 'request.json');
        fs.writeFileSync(request, JSON.stringify(input));
        const run = spawnSync(process.execPath, [path.resolve(__dirname, '../../tools/codex_cli/godot_bridge.js'), 'chat', path.join(__dirname, 'mock_codex_semantic.js'), request], {
            encoding: 'utf8', timeout: 10000, env: { ...process.env, SEMANTIC_WIRE_DIR: directory },
        });
        assert.equal(run.status, 0, run.stdout + run.stderr);
        assert.equal(JSON.parse(run.stdout).choices[0].message.content, 'Checked ' + name);
        const received = JSON.parse(fs.readFileSync(path.join(directory, name + '.json'), 'utf8'));
        assert.equal(received.content, content, 'Codex stdin tool result changed');
        assert.deepEqual(JSON.parse(received.content), state);
        console.log('CODEX_WIRE_BYTES', name, Buffer.byteLength(received.content, 'utf8'));
    }
    console.log('SEMANTIC_CODEX_WIRE_REPLAY_OK');
} finally {
    fs.rmSync(directory, { recursive: true, force: true });
}
