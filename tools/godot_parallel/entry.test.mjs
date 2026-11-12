import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath, pathToFileURL} from 'node:url';

const installation = fileURLToPath(new URL('../../', import.meta.url));
const run = args => spawnSync(process.execPath, args, {encoding:'utf8',timeout:15000,windowsHide:true});
test('linked CLI entry actually validates input; module import does not dispatch', () => {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'parallel entry space-'));
  try {
    const linked = path.join(folder, 'linked installation');
    fs.symlinkSync(installation, linked, process.platform === 'win32' ? 'junction' : 'dir');
    const direct = path.join(installation, 'tools/godot_parallel/runner.mjs');
    const alias = path.join(linked, 'tools/godot_parallel/runner.mjs');
    const missing = path.join(folder, 'missing request.json');
    for (const args of [[direct,missing], [alias,missing], ['--preserve-symlinks-main',alias,missing]]) {
      const result = run(args);
      assert.equal(result.error, undefined);
      assert.equal(result.status, 1, 'CLI must enter input validation, never silently exit zero');
      // Windows without the native Job addon still fails explicitly before input validation.
      assert.match(result.stderr, process.platform === 'win32' ? /ENOENT|MODULE_NOT_FOUND|Cannot find module|Process tree boundary/ : /ENOENT/);
    }
    const imported = run(['--input-type=module','-e',`await import(${JSON.stringify(pathToFileURL(alias).href)});console.log('IMPORTED_WITHOUT_DISPATCH');`]);
    assert.equal(imported.status, 0, imported.stderr);
    assert.equal(imported.stdout.trim(), 'IMPORTED_WITHOUT_DISPATCH');
    assert.equal(imported.stderr, '');
    assert.deepEqual(fs.readdirSync(folder), ['linked installation']);
  } finally {fs.rmSync(folder,{recursive:true,force:true});}
});
