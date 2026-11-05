'use strict';
// Offline Codex protocol fixture. Never invokes a provider or executes a proposed action.
const fs = require('node:fs');
const path = require('node:path');
const { createHash } = require('node:crypto');
let text = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { text += chunk; });
process.stdin.on('end', () => {
    const input = JSON.parse(text.slice(text.indexOf('\n') + 1));
    const messages = input.messages;
    let answer;
    if (messages[0].content.includes('Requirements intake only')) {
        const value = JSON.parse(messages.at(-1).content);
        answer = { content: JSON.stringify({ decision: 'continue', title: 'Semantic fixture', category: 'development', goal: value.request, scope: ['isolated semantic test'], acceptance: ['expected test behavior'], questions: [] }), actions: [] };
    } else {
        const latest = messages.findLastIndex(message => message.role === 'user');
        const name = messages[latest].content;
        const guidance = process.env.SEMANTIC_GUIDANCE === '1';
        const result = messages.slice(latest).findLast(message => message.role === 'tool');
        if (result) {
            const file = guidance ? createHash('sha256').update(name).digest('hex') : name;
            fs.writeFileSync(path.join(process.env.SEMANTIC_WIRE_DIR, file + '.json'), JSON.stringify(result));
            if (guidance) fs.writeFileSync(path.join(__dirname, 'project', 'last-result.json'), result.content);
            answer = { content: 'Checked ' + name, actions: [] };
        } else {
            answer = { content: '', actions: [{ name: guidance || name === 'open_scene' ? 'editor_action' : 'get_editor_state', arguments: guidance ? name : JSON.stringify(name === 'open_scene' ? { action: 'open_scene', target: 'res://fixture.tscn' } : {}) }] };
            if (guidance && process.env.SEMANTIC_ROUTING === '1') {
                const operation = JSON.parse(name);
                if (!['find_targets', 'describe_target'].includes(operation.action)) {
                    answer.actions = [{ name: 'route_engine_message', arguments: JSON.stringify({ intent: 'engine_operation', request_id: 'codex-' + latest, source: 'mock-codex', operation }) }];
                }
            }
        }
    }
    process.stdout.write(JSON.stringify({ type: 'item.completed', item: { type: 'agent_message', text: JSON.stringify(answer) } }) + '\n');
    process.stdout.write(JSON.stringify({ type: 'turn.completed', usage: {} }) + '\n');
});
