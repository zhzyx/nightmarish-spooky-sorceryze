'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { createInterface } = require('node:readline');
const { once } = require('node:events');

async function main() {
    const root = path.resolve(__dirname, '../..');
    const directory = fs.mkdtempSync(path.join(root, 'ai_cli_probe_'));
    const bridge = path.join(root, 'tools/codebuddy_cli/godot_bridge.js');
    const entry = path.join(root, 'tools/codebuddy_cli/node_modules/@tencent-ai/codebuddy-code/bin/codebuddy');
    const child = spawn(process.execPath, [bridge, 'session', entry], { stdio: ['pipe', 'pipe', 'ignore'], windowsHide: true });
    const lines = createInterface({ input: child.stdout })[Symbol.asyncIterator]();
    const timer = setTimeout(() => child.kill(), 125000);
    const send = async (text, number) => {
        const file = path.join(directory, number + '.json');
        fs.writeFileSync(file, JSON.stringify({ messages: [{ role: 'user', content: text }], model: process.env.CODEBUDDY_PROBE_MODEL || '', agent_id: 'account_probe', available_tools: [], tool_definitions: [{ type: 'function', function: { name: 'read_file', description: 'Godot file tool', parameters: { type: 'object', properties: { path: { type: 'string' } }, required: ['path'] } } }], tool_context: { permission_enabled: false, tool_rounds: 0, max_tool_rounds: null } }));
        child.stdin.write(JSON.stringify({ path: file }) + '\n');
        for (;;) {
            const line = await lines.next();
            if (line.done) throw new Error('CLI exited before returning a reply');
            const response = JSON.parse(line.value);
            if (response.event === 'progress') continue;
            if (response.error) throw new Error(response.error.message);
            const message = response.choices?.[0]?.message;
            if (!message || message.tool_calls?.length) throw new Error('Expected a text completion');
            return response;
        }
    };
    try {
        const first = await send('这是一条连接验证消息。请记住验证词 CODEBUDDY_ACCOUNT_OK，并且只回复这个词，不要调用工具。', 1);
        const second = await send('只回复上一条消息让你记住的验证词，不要调用工具。', 2);
        if (!first.choices[0].message.content.includes('CODEBUDDY_ACCOUNT_OK') || !second.choices[0].message.content.includes('CODEBUDDY_ACCOUNT_OK') || first.transport.session_id !== second.transport.session_id) throw new Error('Native session did not preserve the previous user context');
        console.log('CODEBUDDY_ACCOUNT_OK: real ACP model replies retained context in one native session. Cloud persistence and IDE history sharing are not asserted.');
    } finally {
        clearTimeout(timer);
        child.stdin.end();
        if (child.exitCode === null) await once(child, 'close');
        fs.rmSync(directory, { recursive: true, force: true });
    }
}

main().catch(error => { console.error('CODEBUDDY_ACCOUNT_NOT_VERIFIED:', error.message); process.exitCode = 1; });
