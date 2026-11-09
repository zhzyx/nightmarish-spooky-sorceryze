'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const cp = require('node:child_process');
const {once} = require('node:events');
const {setTimeout: delay} = require('node:timers/promises');
const {Subscription} = require('../../tools/codex_cli/subscription_session');
const bridge = path.resolve(__dirname, '../../tools/codex_cli/godot_bridge.js');

test('only acknowledged history and unchanged scope can reuse a thread', async () => {
    const sent = [];
    let n = 0;
    const rpc = {
        call: async (method, p) => {
            if (method === 'thread/start')
                return {
                    thread: {id: String(++n), ephemeral: true},
                    model: p.model,
                    modelProvider: 'openai',
                    sandbox: {type: 'readOnly', networkAccess: false},
                    approvalPolicy: 'never'
                };
            sent.push(p);
            const id = 'turn-' + sent.length;
            setImmediate(() => {
                rpc.notify({
                    method: 'item/completed',
                    params: {threadId: p.threadId, turnId: id, item: {type: 'agentMessage', text: 'ok'}}
                });
                rpc.notify({method: 'turn/completed', params: {threadId: p.threadId, turn: {id, status: 'completed'}}});
            });
            return {turn: {id}};
        }
    };
    const s = new Subscription(rpc, 'unused');
    s.identity = async () => 'actor';
    s.account = 'actor';
    const input = {
        model: 'm',
        available_tools: [],
        tool_context: {},
        messages: [{role: 'system', content: 'mandate 1'}, {role: 'user', content: 'one'}]
    };
    const turn = (scope) => s.turn(input, scope, {}, JSON.stringify, () => {});
    assert.equal((await turn('A')).mode, 'bootstrap');
    s.accepted({role: 'assistant', content: 'ok'});
    input.messages[0].content = 'mandate 2';
    input.messages.push({role: 'assistant', content: 'ok'}, {role: 'user', content: 'two'});
    assert.equal((await turn('A')).mode, 'incremental');
    assert.match(sent.at(-1).input[0].text, /mandate 2/);
    input.messages.push({role: 'user', content: 'three'});
    assert.equal((await turn('B')).mode, 'bootstrap');
    input.messages[1].content = 'redacted';
    input.messages.push({role: 'user', content: 'four'});
    assert.equal((await turn('B')).mode, 'bootstrap');
    s.identity = async () => 'other';
    await assert.rejects(turn('B'));
    assert.equal(sent.length, 4);
});

for (const phase of ['app-server', 'exec'])
    test(
        'editor EOF terminates the Windows job during ' + phase,
        {skip: process.platform !== 'win32' || !process.env.GONGGONG_PYTHON}, async () => {
            const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'godot-codex-owner-'));
            const mock = path.join(dir, 'mock.js'), marker = path.join(dir, 'pid'), fn = path.join(dir, 'input.json');
            fs.writeFileSync(
                mock,
                'const fs=require(\'fs\');if(process.argv[2]===process.env.WAIT_PHASE){fs.writeFileSync(process.env.PID_FILE,String(process.pid));setInterval(()=>{},5000);}else process.exit(1);');
            fs.writeFileSync(
                fn,
                JSON.stringify({model: 'test', messages: [{role: 'user', content: 'fixture'}], available_tools: []}));
            const env = {...process.env, CODEX_HOME: dir, PID_FILE: marker, WAIT_PHASE: phase};
            for (const key of Object.keys(env))
                if (/^(openai_api_key|openai_base_url|codex_api_key)$/i.test(key)) delete env[key];
            const proc = cp.spawn(
                process.execPath, [bridge, 'session', mock, process.env.GONGGONG_PYTHON],
                {windowsHide: true, env, stdio: ['pipe', 'ignore', 'ignore']});
            const done = once(proc, 'close');
            try {
                proc.stdin.write(JSON.stringify({scope: 'a'.repeat(64), path: fn}) + '\n');
                const deadline = Date.now() + 25000;
                while (!fs.existsSync(marker) && Date.now() < deadline) await delay(50);
                const pid = Number(fs.readFileSync(marker, 'utf8'));
                assert.ok(pid > 0);
                proc.stdin.end();
                await Promise.race([
                    done, delay(6000, null, {ref: false}).then(() => {
                        throw Error('bridge still alive');
                    })
                ]);
                let dead = false;
                for (let n = 0; n < 40 && !dead; n++) {
                    try {
                        process.kill(pid, 0);
                        await delay(50);
                    } catch (e) {
                        dead = e.code === 'ESRCH';
                    }
                }
                assert.equal(dead, true);
            } finally {
                proc.kill();
                fs.rmSync(dir, {recursive: true, force: true, maxRetries: 5, retryDelay: 100});
            }
        });
