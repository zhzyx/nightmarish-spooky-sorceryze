import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {verifyDependencyPreflight} from './runner.mjs';

test('durable check is audit data with exact request/response linkage', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'dependency-preflight-'));
  try {
    const file = path.join(dir, 'check.json');
    const candidate = {root:dir, files_sha256:'abc', files:Array.from({length:2000}, (_, i) => ({path:`evidence/${i}.json`,sha256:'a'.repeat(64)}))};
    const bytes = JSON.stringify({schema_version:1, request_json:JSON.stringify({request_nonce:'actual', candidate}), response_json:JSON.stringify({ok:true, request_nonce:'actual', candidate_sha256:'abc'})});
    fs.writeFileSync(file, bytes);
    const source = {candidate_check:{path:file,sha256:crypto.createHash('sha256').update(bytes).digest('hex'),request_nonce:'actual'}, verified_response:{current_candidate:candidate,decision_sha256:'decision'},decision_sha256:'decision',decision:{verdict:'pass'}};
    verifyDependencyPreflight([source]);
    assert.throws(() => verifyDependencyPreflight([{...source,candidate_check:{...source.candidate_check,request_nonce:'other'}}]), /binding/);
    assert.throws(() => verifyDependencyPreflight([{...source,verified_response:{...source.verified_response,current_candidate:{...candidate,files_sha256:'stale'}}}]), /binding/);
    fs.appendFileSync(file, ' ');
    assert.throws(() => verifyDependencyPreflight([source]), /changed/);
    fs.unlinkSync(file);
    assert.throws(() => verifyDependencyPreflight([source]));
    assert.throws(() => verifyDependencyPreflight(Array(257).fill(source)), /size/);
  } finally { fs.rmSync(dir, {recursive:true,force:true}); }
});
