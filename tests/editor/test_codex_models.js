'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { listModels, argumentsFor, validateRequest } = require('../../tools/codex_cli/godot_bridge');

async function fixture(source, callback) {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'codex-models-test-'));
    const entry = path.join(dir, 'codex');
    fs.writeFileSync(entry, '#!' + process.execPath + '\n' + source, { mode: 0o700 });
    try { await callback(entry); } finally { fs.rmSync(dir, { recursive: true, force: true }); }
}
const rpc = `require('node:readline').createInterface({input:process.stdin}).on('line', line => {
const p = JSON.parse(line); const reply = result => process.stdout.write(JSON.stringify({id:p.id,result})+'\\n');
if(p.method==='initialize') reply({});
else if(p.method==='initialized') {}
`;
test('model discovery handshakes, pages, filters hidden/duplicate models and returns actual efforts', async () => {
    await fixture(rpc + `else if(p.method==='model/list') {
if(!p.params.cursor) reply({data:[{id:'first',model:'wire-id',displayName:'模型',isDefault:true,supportedReasoningEfforts:[{reasoningEffort:'ultra'}]}],nextCursor:'page2'});
else reply({data:[{id:'first',model:'wire-id'},{id:'hidden',hidden:true},{id:'plain',supportedReasoningEfforts:[]}],nextCursor:null});
} else throw Error('unexpected method'); });`, async entry => {
        const result = await listModels(entry);
        assert.deepEqual(result.models.map(m => m.id), ['wire-id', 'plain']);
        assert.equal(result.models[0].name, '模型');
        assert.equal(result.models[0].is_default, true);
        assert.deepEqual(result.models[0].reasoning_efforts, ['ultra']);
        assert.deepEqual(result.models[1].reasoning_efforts, []);
    });
});
test('errors, invalid JSON, repeated cursors and silent timeout reject without leaking server text', async () => {
    for(const source of [rpc+`else if(p.method==='model/list') process.stdout.write(JSON.stringify({id:p.id,error:{message:'secret'}})+'\\n'); });`,
        `process.stdout.write('invalid\\n');setInterval(()=>{},1000);`,
        rpc+`else if(p.method==='model/list') reply({data:[],nextCursor:'same'}); });`]) {
        await fixture(source, async entry => assert.rejects(listModels(entry,{timeoutMs:200}), error => !error.message.includes('secret')));
    }
});
test('reasoning effort reaches Codex configuration, default omits it and invalid efforts reject', () => {
    for(const effort of ['medium','high','xhigh','max','ultra']) assert.ok(argumentsFor('model','schema',[],effort).includes('model_reasoning_effort="'+effort+'"'));
    assert.ok(!argumentsFor('model','schema').some(arg=>arg.startsWith('model_reasoning_effort=')));
    assert.throws(()=>argumentsFor('model','schema',[],'invalid'));
    assert.throws(()=>validateRequest({messages:[],available_tools:[],reasoning_effort:'invalid'}));
});
test('chat subprocess receives the selected effort after request validation', async () => {
    const { run } = require('../../tools/codex_cli/godot_bridge');
    await fixture(`let body=''; process.stdin.on('data',x=>body+=x); process.stdin.on('end',()=>{
        const args=process.argv.slice(2);
        if(!args.includes('model_reasoning_effort="high"') || !args.includes('fixture-model')) process.exit(23);
        process.stdout.write(JSON.stringify({type:'item.completed',item:{type:'agent_message',text:JSON.stringify({content:'ok',actions:[]})}})+'\\n');
        process.stdout.write(JSON.stringify({type:'turn.completed'})+'\\n');
    });`, async entry => {
        const request = path.join(path.dirname(entry),'request.json');
        fs.writeFileSync(request,JSON.stringify({model:'fixture-model',reasoning_effort:'high',messages:[{role:'user',content:'test'}],available_tools:[],tool_context:{permission_enabled:false,tool_rounds:0,max_tool_rounds:null}}));
        const result = await run(entry, request);
        assert.equal(result.choices[0].message.content,'ok');
    });
});
