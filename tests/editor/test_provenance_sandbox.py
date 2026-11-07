"""Actual macOS command policy checks in disposable Git worktrees."""

import importlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
fixtures = importlib.import_module("test_editor_provenance_guard")


@unittest.skipUnless(sys.platform == "darwin", "macOS policy acceptance")
class ProvenanceSandboxTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ProvenanceGuardTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def command(self, code):
        return self.fixture.command(code, profile="(version 1)(allow default)")

    def test_broad_stash_is_denied_without_losing_provenance(self):
        code = self.command(
            "import subprocess; raise SystemExit(subprocess.run(['git','stash','push','--include-untracked']).returncode)"
        )
        self.assertNotEqual(code, 0)
        for path, content in self.fixture.before.items():
            self.assertEqual(path.read_bytes(), content)

    def test_parent_rename_and_immutable_event_write_are_denied(self):
        self.assertNotEqual(self.command("from pathlib import Path; Path('design-docs').rename('moved-design')"), 0)
        self.assertFalse((self.fixture.root / "moved-design").exists())
        self.assertNotEqual(
            self.command(
                "from pathlib import Path; Path(" + repr(str(self.fixture.event_path)) + ").write_text('invalid')"
            ),
            0,
        )
        self.assertEqual(self.fixture.event_path.read_bytes(), self.fixture.before[self.fixture.event_path])

    def test_many_active_events_keep_each_policy_string_bounded(self):
        for index in range(80):
            event = fixtures.guard.events_module().event(self.fixture.event("active-long-event-" + str(index)))
            (self.fixture.event_path.parent / (event["event_id"] + ".json")).write_text(json.dumps(event))
        self.assertEqual(self.command("print('bounded profile accepted')"), 0)
        target = self.fixture.event_path.parent / "active-long-event-79.json"
        before = target.read_bytes()
        self.assertNotEqual(self.command("from pathlib import Path; Path(" + repr(str(target)) + ").unlink()"), 0)
        self.assertEqual(target.read_bytes(), before)

    def test_design_edit_new_evidence_and_selective_stash_still_work(self):
        code = self.command(
            "from pathlib import Path; import subprocess; "
            "p=Path('design-docs/active-test.md'); p.write_text(p.read_text()+'normal clarification\\n'); "
            "Path('data-collection/new-evidence.json').write_text('{\"request_id\":\"active-test\"}'); "
            "Path('source.txt').write_text('source update'); "
            "subprocess.run(['git','stash','push','--','source.txt'],check=True); "
            "subprocess.run(['git','stash','apply'],check=True)"
        )
        self.assertEqual(code, 0)
        self.assertIn("normal clarification", self.fixture.doc.read_text())
        self.assertEqual((self.fixture.root / "source.txt").read_text(), "source update")

    def test_real_canonical_pending_consumer_is_allowed(self):
        pending = self.fixture.pending()
        code = self.command(
            "import sys;sys.path.insert(0," + repr(str(ROOT / "tools")) + "); "
            "import editor_provenance_guard as g;from pathlib import Path; "
            "g.events_module().record(Path.cwd(),Path(" + repr(str(pending)) + ")); "
            "Path(" + repr(str(pending)) + ").unlink()"
        )
        self.assertEqual(code, 0)
        self.assertFalse(pending.exists())
        event = self.fixture.root / "gonggong-diting-data/events/fixture/active-test/pending-message.json"
        self.assertEqual(json.loads(event.read_text())["event_id"], "pending-message")

    def test_actual_native_terminal_guard_and_cancel(self):
        node = os.environ.get("GONGGONG_NODE") or shutil.which("node")
        self.assertTrue(node, "Pass GONGGONG_NODE for actual terminal acceptance")
        ready = self.fixture.folder / "terminal-ready"
        code = (
            "import os,time; from pathlib import Path; Path("
            + repr(str(ready))
            + ").write_text(str(os.getpid())); time.sleep(30)"
        )
        config = {
            "module": str(ROOT / "tools/codebuddy_cli/godot_terminal.js"),
            "guard": {
                "protocol": 1,
                "python": sys.executable,
                "worker": str(ROOT / "tools/editor_provenance_guard.py"),
                "binding": str(self.fixture.binding),
            },
            "workspace": {
                "workspace_root": str(self.fixture.root),
                "provenance_guard_required": True,
                "command_profile": "(version 1)(allow default)",
            },
            "ready": str(ready),
            "command": shlex.quote(sys.executable) + " -c " + shlex.quote(code),
        }
        script = r"""const fs = require('node:fs'); const assert = require('node:assert/strict');
const config=JSON.parse(process.argv[1]); const {createTerminals}=require(config.module);
const manager=createTerminals({approve:async()=>({approved:true,provenance_guard:config.guard,command_profile:config.workspace.command_profile}),validate:()=>{}});
async function run(command) { const {terminalId}=await manager.create({sessionId:'fixture',command},config.workspace); const p={sessionId:'fixture',terminalId}; const status=await manager.wait(p); await manager.release(p); return status; }
(async()=>{try {
 assert.notEqual((await run('git stash push --include-untracked')).exitCode,0);
 assert.equal((await run('printf source-update > source.txt && git stash push -- source.txt && git stash apply')).exitCode,0);
 const {terminalId}=await manager.create({sessionId:'fixture',command:config.command},config.workspace); const p={sessionId:'fixture',terminalId};
 for(let i=0;i<200 && !fs.existsSync(config.ready);i++) await new Promise(resolve=>setTimeout(resolve,20));
 assert(fs.existsSync(config.ready)); await manager.kill(p); const status=await manager.wait(p); assert.equal(status.exitCode,143); assert(!status.signal);
 await manager.release(p); console.log('actual_terminal_guard_and_cancel_passed');
}finally{await manager.close();}})().catch(error=>{console.error(error);process.exitCode=1;});
"""
        result = subprocess.run(
            [node, "-e", script, json.dumps(config)], cwd=self.fixture.root, capture_output=True, text=True, timeout=30
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("actual_terminal_guard_and_cancel_passed", result.stdout)
        self.assertEqual((self.fixture.root / "source.txt").read_text(), "source-update")
        for path, content in self.fixture.before.items():
            self.assertEqual(path.read_bytes(), content)


if __name__ == "__main__":
    unittest.main()
