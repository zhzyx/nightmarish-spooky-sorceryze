'use strict';
const test=require('node:test'), assert=require('node:assert/strict');
const {contentPreview:p}=require('../../tools/codex_cli/content_preview');
test('only first root content is previewed, with chunked escapes and action isolation',()=>{
 const raw=JSON.stringify({content:'中文 "quote"\n😀',actions:[{name:'run_command',arguments:'SECRET'}]});
 for(let i=0;i<=raw.length;i++) assert.ok(!p(raw.slice(0,i)).includes('SECRET'));
 assert.equal(p(raw),'中文 "quote"\n😀');
 assert.equal(p('{"actions":[{"content":"SECRET"}],"content":"safe"}'),'');
 assert.equal(p('{"content":"safe", "actions":"SECRET"}'),'safe');
 assert.equal(p('{"content":"bad\\q'), '');
 assert.equal(p(JSON.stringify({content:'a'.repeat(10000)})).length,2048);
});

test('incremental parser stops after content or cap and throttles intermediate updates',()=>{
 const {ContentPreview}=require('../../tools/codex_cli/content_preview');
 const parser=new ContentPreview();
 assert.equal(parser.feed('{"content":"one'),'one');
 assert.equal(parser.feed(' two'),'');
 assert.equal(parser.feed('","actions":["SECRET"]}'),'one two');
 assert.equal(parser.feed('SECRET'),'');
 const capped=new ContentPreview(); capped.feed('{"content":"'+'a'.repeat(3000));
 assert.equal(capped.text.length,2048); assert.equal(capped.feed('SECRET'),'');
 const escape=new ContentPreview(); escape.feed('{"content":"\\uD83D');
 assert.equal(escape.text,''); escape.feed('\\uDE00"}'); assert.equal(escape.text,'😀');
});

test('actions-first oversized prefix stops within a single chunk',()=>{
 const {ContentPreview}=require('../../tools/codex_cli/content_preview'); const p=new ContentPreview();
 assert.equal(p.feed('{"actions":['+'x'.repeat(32000)), '');
 assert.equal(p.done,true); assert.ok(p.prefix.length<=257);
 assert.equal(p.feed('x'.repeat(32000)), ''); assert.ok(p.prefix.length<=257);
});
