"""Isolated, offline Git fixtures; no framework production state or global Git edits."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / 'tools' / 'check_delivery.py'
spec = importlib.util.spec_from_file_location('delivery', TOOL)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='olympus-delivery-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Isolated Test')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.repo / 'app.txt').write_bytes(b'candidate\n')
        self.git('add', 'app.txt')
        self.git('commit', '-qm', 'candidate')
        self.m = {
            'schema_version': 1, 'path_base': 'framework', 'stage': 'candidate',
            'delivery_kind': 'source', 'model_mode': 'none',
            'candidate': {'repository': 'repo', 'commit': self.git('rev-parse', 'HEAD'),
                          'tree': self.git('rev-parse', 'HEAD^{tree}')},
            'dependencies': [],
            'artifacts': [dict(self.ref('repo/app.txt'), id='source', role='source',
                               candidate_path='app.txt', distribution='repository checkout')],
            'validation': {}, 'collection': {'state': 'configured'}, 'publication': None}
        (self.root / 'binding.json').write_text('{"host":"fixture"}', encoding='utf-8')
        self.refresh()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.STDOUT).decode().strip()

    def ref(self, name):
        return {'path': name, 'sha256': gate.file_hash(self.root / name)}

    def report(self, kind, **extra):
        name = kind + '.json'
        data = dict(kind=kind, status='passed', candidate=copy.deepcopy(self.m['candidate']),
                    inputs_sha256=gate.inputs_digest(self.m), **extra)
        (self.root / name).write_text(json.dumps(data), encoding='utf-8')
        return self.ref(name)

    def refresh(self):
        kinds = ['source'] if self.m['delivery_kind'] == 'source' else ['build', 'install', 'start', 'business']
        self.m['validation'] = {k: self.report(k) for k in kinds}
        if self.m['model_mode'] != 'none':
            self.m['validation']['model'] = self.report('model', model_mode=self.m['model_mode'])
        self.m['collection']['configured'] = self.report('collection.configured', binding=self.ref('binding.json'))

    def result(self):
        return gate.check(self.m, self.root)

    def rejected(self, code):
        result = self.result()
        self.assertFalse(result['ok'], result)
        self.assertIn(code, [x['code'] for x in result['diagnostics']], result)
        return result

    def test_source_candidate_valid_without_publication(self):
        self.assertTrue(self.result()['ok'])

    def test_wrong_repository_even_with_identical_commit(self):
        subprocess.check_call(['git', 'clone', '-q', str(self.repo), str(self.root / 'other')])
        self.m['candidate']['repository'] = 'other'
        self.rejected('evidence_binding')

    def test_wrong_candidate_tree(self):
        old_tree = self.m['candidate']['tree']
        (self.repo / 'app.txt').write_bytes(b'new\n')
        self.git('add', 'app.txt')
        self.git('commit', '-qm', 'new candidate')
        self.m['candidate']['commit'] = self.git('rev-parse', 'HEAD')
        self.m['candidate']['tree'] = old_tree
        self.rejected('candidate_mismatch')

    def test_other_directory_source_rejected(self):
        (self.root / 'unrelated.txt').write_bytes(b'not candidate\n')
        self.m['artifacts'][0].update(self.ref('unrelated.txt'))
        self.refresh()
        self.rejected('source_mismatch')

    def test_source_cannot_replace_runnable(self):
        self.m['delivery_kind'] = 'runnable'
        self.refresh()
        self.rejected('runnable_missing')

    def test_dependency_drift_does_not_rewrite_baseline(self):
        dep = self.root / 'dependency.txt'
        dep.write_bytes(b'v1')
        self.m['dependencies'] = [dict(self.ref('dependency.txt'), version='1', affects=['source'])]
        self.refresh()
        before = copy.deepcopy(self.m)
        dep.write_bytes(b'v2')
        result = self.rejected('digest_mismatch')
        self.assertEqual(self.m, before)
        self.assertEqual(result['diagnostics'][0]['affected'], ['source'])

    def test_simulation_cannot_claim_real(self):
        self.m['model_mode'] = 'real'
        self.refresh()
        self.m['validation']['model'] = self.report('model', model_mode='simulated')
        self.rejected('model_boundary')

    def test_collection_claim_needs_receipts_and_matching_batch(self):
        self.m['collection']['state'] = 'delivered'
        self.rejected('schema')
        self.m['collection']['queued'] = self.report('collection.queued', batch_id='batch1')
        self.m['collection']['delivered'] = self.report('collection.delivered', batch_id='batch2', receipt_id='receipt')
        self.rejected('collection_batch')

    def test_consumed_requires_consumer_confirmation(self):
        self.m['collection'].update(state='consumed',
            queued=self.report('collection.queued', batch_id='batch1'),
            delivered=self.report('collection.delivered', batch_id='batch1', receipt_id='r1'),
            consumed=self.report('collection.consumed', batch_id='batch1', receipt_id='r1'))
        self.rejected('collection_consumption')

    def test_runnable_real_published_consistent_fixture(self):
        (self.root / 'package.bin').write_bytes(b'fixture package, not real runtime proof')
        self.m['artifacts'].append(dict(self.ref('package.bin'), id='package', role='runnable', distribution='fixture package'))
        self.m.update(delivery_kind='runnable', model_mode='real', stage='published')
        self.refresh()
        self.m['collection'].update(state='consumed',
            queued=self.report('collection.queued', batch_id='batch1'),
            delivered=self.report('collection.delivered', batch_id='batch1', receipt_id='r1'),
            consumed=self.report('collection.consumed', batch_id='batch1', receipt_id='r1', consumer='fixture'))
        self.m['publication'] = self.report('publication', remote='fixture://release', receipt_id='readback1')
        self.assertTrue(self.result()['ok'], self.result())
        self.assertIn('no authentication', self.result()['boundary'])

    def test_published_without_readback_rejected(self):
        self.m['stage'] = 'published'
        self.rejected('schema')

    def test_stale_release_receipt_rejected(self):
        self.m['stage'] = 'published'
        self.m['publication'] = self.report('publication', remote='fixture://release', receipt_id='r')
        p = self.root / 'publication.json'
        data = json.loads(p.read_text())
        data['candidate']['commit'] = '0' * 40
        p.write_text(json.dumps(data))
        self.m['publication'] = self.ref('publication.json')
        self.rejected('evidence_binding')

    def test_absolute_persisted_path_rejected(self):
        self.m['candidate']['repository'] = str(self.repo)
        self.rejected('path')

    def test_template_fails_cli_and_cli_is_cwd_independent(self):
        template = TOOL.parents[1] / 'templates' / 'delivery.json'
        result = subprocess.run([__import__('sys').executable, str(TOOL), 'templates/delivery.json'],
                                cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)['ok'])
        self.assertTrue(template.exists())
        (self.root / 'delivery.json').write_text(json.dumps(self.m), encoding='utf-8')
        result = subprocess.run([__import__('sys').executable, str(TOOL), '--framework-root', str(self.root), 'delivery.json'],
                                cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == '__main__':
    unittest.main()
