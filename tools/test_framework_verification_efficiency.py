"""Formal-mode equivalence on explicit synthetic permits, never production approvals."""
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class FrameworkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'framework'
        shutil.copytree(ROOT / 'framework', self.root, ignore=shutil.ignore_patterns('__pycache__'))
        self.manifest = json.loads((self.root/'framework-manifest.json').read_text(encoding='utf-8'))
        for agent in self.manifest['agents']:
            path = self.root / agent['admission_pass']
            permit = json.loads(path.read_text(encoding='utf-8'))
            permit['status'] = 'approved'
            permit['review'].update(gonggong_framework='pass', applicable_validation='pass',
                evaluator_id='fixture-reviewer', independence='independent_subagent_review', evidence_refs=['README.md'])
            permit['review']['concision']['status'] = 'pass'
            permit['review']['yuanheng'] = dict.fromkeys(permit['review']['yuanheng'], 'pass')
            permit['approval'].update(approver_id='fixture-approver', authority_ref='synthetic-test-only',
                decision_evidence_ref='README.md', approved_at='2026-01-01T00:00:00Z',
                valid_until_or_task_end='bound_candidate_only', expires_at=None)
            self.write(path, permit)
        self.reseal()
        self.verify = runpy.run_path(str(self.root/'tools/verify_framework.py'))['verify']
        baseline = {'__name__': 'baseline'}
        source = subprocess.check_output(['git', '-C', str(ROOT), 'show', 'HEAD:framework/tools/verify_framework.py'])
        exec(compile(source, 'baseline_verify', 'exec'), baseline)
        self.baseline = baseline['verify']

    def write(self, path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

    def reseal(self):
        inventory = runpy.run_path(str(self.root/'tools/package_integrity.py'))['inventory'](self.root)
        self.write(self.root/'package-lock.json', {'schema_version': 1, 'path_base': 'framework_root', 'files': inventory})

    def test_formal_equivalence_and_one_child(self):
        expected = self.baseline(self.root)
        with patch('subprocess.run', wraps=subprocess.run) as run:
            actual = self.verify(self.root)
        self.assertEqual(actual, expected)
        self.assertEqual(run.call_count, 1)

    def test_expiry_rechecked_every_call(self):
        self.verify(self.root)
        path = self.root / self.manifest['agents'][0]['admission_pass']
        permit = json.loads(path.read_text(encoding='utf-8'))
        permit['approval']['expires_at'] = '2026-01-02T00:00:00Z'
        self.write(path, permit)
        self.reseal()
        for verify in (self.baseline, self.verify):
            with self.assertRaisesRegex(ValueError, 'expired'):
                verify(self.root)

    def test_foundation_and_unlisted_file_rejected(self):
        (self.root/'unexpected.txt').write_text('drift')
        with self.assertRaisesRegex(ValueError, 'drift'):
            self.verify(self.root)
        (self.root/'unexpected.txt').unlink()
        (self.root/'FOUNDATION.md').write_text('changed')
        self.reseal()
        with self.assertRaisesRegex(ValueError, 'Frozen foundation changed'):
            self.verify(self.root)

    def test_pending_permit_never_formal(self):
        path = self.root / self.manifest['agents'][0]['admission_pass']
        permit = json.loads(path.read_text(encoding='utf-8'))
        permit['status'] = 'pending_approval'
        self.write(path, permit)
        self.reseal()
        with self.assertRaisesRegex(ValueError, 'Invalid admission'):
            self.verify(self.root)
        self.assertEqual(self.verify(self.root, candidate=True)['mode'], 'candidate')


if __name__ == '__main__':
    unittest.main()
