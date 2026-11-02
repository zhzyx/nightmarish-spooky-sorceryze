import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import issue_gate as gate


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.issue = {'number': 6, 'html_url': 'https://github.com/test/repo/issues/6',
                      'state': 'open', 'labels': [{'name': 'type:development'}, {'name': 'status:in-progress'}],
                      'body': '<!-- olympus-request:req-6 -->', 'updated_at': '2026-11-02T01:00:00Z'}

    def check(self, value=None):
        return gate.check_issue(value or self.issue, 'test/repo', 6, 'req-6', {'type:development'})

    def test_real_issue_and_form_id(self):
        self.check()
        self.issue['body'] = '### 稳定需求 ID\r\n\r\nreq-6\r\n\r\n### 目标\r\nSome task'
        self.check()

    def test_invalid_issue(self):
        for mutation in ({'number': 7}, {'html_url': 'https://github.com/other/repo/issues/6'},
                         {'pull_request': {}}, {'state': 'closed'}, {'body': '<!-- olympus-request:req-7 -->'},
                         {'body': '<!-- olympus-request:req-6 -->\n<!-- olympus-request:req-7 -->'}):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.check({**self.issue, **mutation})

    def test_invalid_labels(self):
        for names in ([], ['type:development'], ['status:in-progress'],
                      ['type:unknown', 'status:in-progress'],
                      ['type:development', 'type:bug', 'status:in-progress'],
                      ['type:development', 'status:planned'],
                      ['type:development', 'status:done'],
                      ['type:development', 'status:in-progress', 'status:in-review']):
            with self.subTest(names=names), self.assertRaises(ValueError):
                self.check({**self.issue, 'labels': [{'name': n} for n in names]})

    def setup_gate(self, events=True):
        if events:
            directory = self.root / 'olympus-hermes-data/events/local/req-6'
            directory.mkdir(parents=True)
            (directory / 'event.json').write_text(json.dumps({'request_id': 'req-6', 'tenant_id': 'local', 'kind': 'request', 'source_ref': self.issue['html_url']}))
        for target, kwargs in (
            ('check_repository', {}), ('git', {'return_value': b''}), ('snapshot', {'return_value': 'digest'}),
            ('environment', {'return_value': {}}),
            ('work_items.config', {'return_value': ({'repository': 'test/repo', 'tenant_id': 'local'}, [{'name': 'type:development'}])}),
            ('work_items.gh', {'return_value': json.dumps(self.issue)})):
            p = patch('issue_gate.' + target, **kwargs)
            p.start()
            self.addCleanup(p.stop)

    def test_formal_gate_calls_existing_tools(self):
        self.setup_gate()
        with patch.object(gate, 'validate_command', side_effect=[{'mode': 'approved_file_integrity'}, {}, {}]) as run:
            result = gate.gate(self.root, 6, 'req-6')
        self.assertNotIn('--candidate', run.call_args_list[0].args[0])
        self.assertIn('validate', run.call_args_list[1].args[0])
        self.assertIn('git-check', run.call_args_list[2].args[0])
        self.assertNotIn('--require-committed', run.call_args_list[2].args[0])
        self.assertEqual(result['state'], 'local_checks_passed')
        self.assertFalse(result['approval_granted'])
        self.assertFalse(result['diting_ingestion_confirmed'])
        self.assertEqual(len(result['events']), 1)

    def test_missing_collection_fails(self):
        self.setup_gate(events=False)
        with patch.object(gate, 'validate_command', side_effect=[{'mode': 'approved_file_integrity'}, {}, {}]):
            with self.assertRaisesRegex(ValueError, 'No actual Hermes events'):
                gate.gate(self.root, 6, 'req-6')

    def test_formal_or_hermes_failure_fails(self):
        self.setup_gate()
        for outcome in ([ValueError('formal failure')], [{'mode': 'candidate'}],
                        [{'mode': 'approved_file_integrity'}, ValueError('Hermes failure')],
                        [{'mode': 'approved_file_integrity'}, {}, ValueError('deleted history')]):
            with self.subTest(outcome=outcome), patch.object(gate, 'validate_command', side_effect=outcome):
                with self.assertRaises(ValueError):
                    gate.gate(self.root, 6, 'req-6')

    def test_mutating_content_fails(self):
        self.setup_gate()
        with patch.object(gate, 'validate_command', side_effect=[{'mode': 'approved_file_integrity'}, {}, {}]), \
             patch.object(gate, 'snapshot', side_effect=['before', 'after']):
            with self.assertRaisesRegex(ValueError, 'changed during check'):
                gate.gate(self.root, 6, 'req-6')

    def test_unstaged_content_or_untracked_event_fails(self):
        self.setup_gate()
        for calls in ([ValueError('unstaged content')], [b'', b'', ValueError('event not staged')]):
            with self.subTest(calls=calls), patch.object(gate, 'git', side_effect=calls), \
                 patch.object(gate, 'validate_command', side_effect=[{'mode': 'approved_file_integrity'}, {}, {}]):
                with self.assertRaises(ValueError):
                    gate.gate(self.root, 6, 'req-6')

    def test_tenant_kind_and_exact_source_binding(self):
        self.setup_gate()
        path = self.root / 'olympus-hermes-data/events/local/req-6/event.json'
        original = json.loads(path.read_text())
        for mutation in ({'tenant_id': 'other'}, {'kind': 'step'},
                         {'source_ref': 'https://github.com/other/repo/issues/6'},
                         {'source_ref': 'github:test/repo:issue:60'}):
            path.write_text(json.dumps({**original, **mutation}))
            with self.subTest(mutation=mutation), patch.object(gate, 'validate_command', side_effect=[{'mode': 'approved_file_integrity'}, {}, {}]):
                with self.assertRaises(ValueError):
                    gate.gate(self.root, 6, 'req-6')
        path.write_text(json.dumps({**original, 'source_ref': 'github:test/repo:issue:6'}))
        with patch.object(gate, 'validate_command', side_effect=[{'mode': 'approved_file_integrity'}, {}, {}]):
            self.assertEqual(gate.gate(self.root, 6, 'req-6')['state'], 'local_checks_passed')

    def test_history_cannot_be_rewritten(self):
        path = self.root / 'olympus-hermes-data/events/local/old/event.json'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'changed')
        name = path.relative_to(self.root).as_posix().encode()
        with patch.object(gate, 'git', side_effect=[name + b'\0', b'original']):
            with self.assertRaisesRegex(ValueError, 'history must remain immutable'):
                gate.check_history(self.root)

    def test_issue_changed_during_validation_fails(self):
        self.setup_gate()
        updated = {**self.issue, 'updated_at': '2026-11-02T02:00:00Z'}
        with patch.object(gate.work_items, 'gh', side_effect=[json.dumps(self.issue), json.dumps(updated)]), \
             patch.object(gate, 'validate_command', side_effect=[{'mode': 'approved_file_integrity'}, {}, {}]):
            with self.assertRaisesRegex(ValueError, 'changed during check'):
                gate.gate(self.root, 6, 'req-6')

    def test_validator_errors_do_not_echo_credentials(self):
        with patch.object(gate.subprocess, 'run') as run:
            run.return_value.returncode = 1
            run.return_value.stderr = 'secret-token'
            with self.assertRaisesRegex(ValueError, '^Formal failed; run the trusted validator locally for details$'):
                gate.validate_command(['python'], self.root, {}, 'Formal')

    def test_other_origin_rejected(self):
        with patch.object(gate, 'git', side_effect=[str(self.root).encode(), b'git@github.com:other/repo.git']):
            with self.assertRaisesRegex(ValueError, 'origin must match'):
                gate.check_repository(self.root, 'test/repo')

    def test_source_resolves_relative_to_repo(self):
        (self.root / '.olympus-local.json').write_text('{"GONGGONG_FRAMEWORK_SOURCE":"approved/framework"}')
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(gate.environment(self.root)['GONGGONG_FRAMEWORK_SOURCE'], str((self.root / 'approved/framework').resolve()))
        with patch.dict(os.environ, {'GONGGONG_FRAMEWORK_SOURCE': 'host/framework'}, clear=True):
            self.assertEqual(gate.environment(self.root)['GONGGONG_FRAMEWORK_SOURCE'], str((self.root / 'host/framework').resolve()))


if __name__ == '__main__':
    unittest.main()
