import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("bridge", Path(__file__).with_name("bridge.py"))
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class ChatGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "Olympus").mkdir()
        (self.root / "Olympus/framework-manifest.json").write_text(json.dumps({
            "version": "test", "agents": [{"id": "athena", "version": "test", "entry": "entry.md", "candidate_digest": "test"}]}))
        (self.root / 'Olympus/entry.md').write_text('Fixture only')
        self.request = {"request_id": "fixture", "outcome": "private fixture prompt",
                        "authority_ref": "isolated-test", "project": "fixture",
                        "tools_enabled": False, "file_changes_require_approval": True,
                        "execution_requires_approval": True}

    def process(self, ok, receipt_ok=True):
        def run(command, **kwargs):
            if command[1].endswith('agent-context.mjs'):
                mandate = json.loads(Path(command[-1]).read_text())
                self.assertFalse(mandate['tool_permission']['tools_enabled'])
                self.assertEqual(kwargs['env']['OLYMPUS_PYTHON'], bridge.sys.executable)
                return types.SimpleNamespace(returncode=0 if ok else 1, stdout="FRAMEWORK" if ok else "", stderr="admission blocked")
            event = json.loads(Path(command[-1]).read_text())
            self.assertNotIn(self.request['outcome'], json.dumps(event))
            self.assertEqual(event['payload']['context_accepted'], ok)
            return types.SimpleNamespace(returncode=0 if receipt_ok else 1, stdout='{"state":"recorded_file"}', stderr='receipt unavailable')
        return run

    def test_context_is_actual_loader_output(self):
        with patch.object(bridge.subprocess, 'run', side_effect=self.process(True)) as run:
            result = bridge.chat(self.root, self.request, 'test')
        self.assertTrue(result['ok'])
        self.assertEqual(result['context'], 'FRAMEWORK')
        self.assertEqual(run.call_count, 2)

    def test_admission_failure_cannot_send_context(self):
        with patch.object(bridge.subprocess, 'run', side_effect=self.process(False)):
            result = bridge.chat(self.root, self.request, 'test')
        self.assertFalse(result['ok'])
        self.assertEqual(result['context'], '')

    def test_receipt_failure_blocks_even_accepted_context(self):
        with patch.object(bridge.subprocess, 'run', side_effect=self.process(True, False)):
            result = bridge.chat(self.root, self.request, 'test')
        self.assertFalse(result['ok'])
        self.assertNotIn('context', result)

    def test_missing_host_permission_fails_before_launch(self):
        del self.request['tools_enabled']
        with patch.object(bridge.subprocess, 'run') as run:
            with self.assertRaises(ValueError):
                bridge.chat(self.root, self.request, 'test')
        run.assert_not_called()

    def test_local_upstream_locator_does_not_grant_admission(self):
        (self.root/'.olympus-local.json').write_text(json.dumps({'GONGGONG_FRAMEWORK_SOURCE':'fixture-source', 'force_approved':True}))
        env=bridge.host_environment(self.root)
        self.assertEqual(env['GONGGONG_FRAMEWORK_SOURCE'],str(self.root/'fixture-source'))
        self.assertNotIn('force_approved',env)

    def test_failed_receipt_is_retried_without_duplicate_identity(self):
        with patch.object(bridge.subprocess, 'run', side_effect=self.process(True, False)):
            self.assertFalse(bridge.chat(self.root, self.request, 'test')['ok'])
        pending=list((self.root/'.olympus-outbox/chat').glob('*.json'))
        self.assertEqual(len(pending),1)
        original=pending[0].read_bytes()
        with patch.object(bridge.subprocess, 'run', side_effect=self.process(True)):
            self.assertTrue(bridge.flush(self.root)['ok'])
        self.assertFalse(pending[0].exists())
        self.assertIn(b'event_id',original)

    def test_concurrent_flush_is_serialized(self):
        with patch.object(bridge.subprocess, 'run', side_effect=self.process(True, False)):
            self.assertFalse(bridge.chat(self.root, self.request, 'test')['ok'])
        def deliver(*args, **kwargs):
            time.sleep(0.15)
            return types.SimpleNamespace(returncode=0,stdout='{"state":"recorded_file"}',stderr='')
        with patch.object(bridge.subprocess,'run',side_effect=deliver) as run, ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:bridge.flush(self.root),range(2)))
        self.assertTrue(all(result['ok'] for result in results))
        self.assertEqual(run.call_count,1)


if __name__=='__main__':
    unittest.main()
