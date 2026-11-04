'use strict';
// Offline Codex protocol fixture. Never invokes a provider or executes a proposed action.
const fs = require('node:fs');
const path = require('node:path');
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
        const result = messages.slice(latest).findLast(message => message.role === 'tool');
        if (result) {
            fs.writeFileSync(path.join(process.env.SEMANTIC_WIRE_DIR, name + '.json'), JSON.stringify(result));
            answer = { content: 'Checked ' + name, actions: [] };
        } else {
            answer = { content: '', actions: [{ name: name === 'open_scene' ? 'editor_action' : 'get_editor_state', arguments: JSON.stringify(name === 'open_scene' ? { action: 'open_scene', target: 'res://fixture.tscn' } : {}) }] };
        }
    }
    process.stdout.write(JSON.stringify({ type: 'item.completed', item: { type: 'agent_message', text: JSON.stringify(answer) } }) + '\n');
    process.stdout.write(JSON.stringify({ type: 'turn.completed', usage: {} }) + '\n');
});
