"""Portable candidate, complete drift detection, and strict production boundary."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
FRAMEWORK = Path(os.environ.get('OLYMPUS_TEST_FRAMEWORK', ROOT / 'Olympus')).resolve()
sync = runpy.run_path(str(FRAMEWORK / 'sync/gonggong_sync.py'))


class DistributionTests(unittest.TestCase):
    def test_approved_overlay_is_validated_not_silently_ignored(self):
        # Synthetic permit only in an isolated checkout; never modifies a real approval.
        with tempfile.TemporaryDirectory(dir=ROOT / '.godot-integration-local', prefix='admission-fixture-') as temporary:
            isolated=Path(temporary)/'Olympus'
            binding=json.loads((FRAMEWORK/'sync/binding.json').read_text(encoding='utf-8'))
            sync['build'](FRAMEWORK/binding['source'], isolated)
            wanted=sync['inventory'](isolated)
            manifest=json.loads(wanted['framework-manifest.json'])
            agent=manifest['agents'][0]
            policy=json.loads(wanted['contracts/admission-policy.json'])
            lock=json.loads(wanted['foundation.lock.json'])
            permit=json.loads(wanted[agent['admission_pass']])
            ref='reviews/local-admission/isolated-test-only.md'
            (isolated/ref).parent.mkdir(parents=True)
            (isolated/ref).write_text('Synthetic isolated test evidence. No production authority.',encoding='utf-8')
            permit.update(status='approved',event=policy['event'],phase=policy['phase'])
            permit['subject']['scope']=policy['scope']
            permit['baseline']={'foundation_sha256':lock['sha256'],'foundation_version':lock['version'],
                                'zeus_version':manifest['zeus_version'],'policy_version':manifest['version']}
            permit['review']={'olympus_framework':'pass','concision':{'status':'pass'},'applicable_validation':'pass',
                              'independence':policy['review_independence'],'evaluator_id':'isolated-fixture-reviewer',
                              'evidence_refs':[ref],'zeus':dict.fromkeys(policy['zeus_principles'],'pass')}
            permit['approval']={'approver_id':'isolated-fixture-owner','authority_ref':'synthetic-test-only','decision_evidence_ref':ref,
                                'valid_until_or_task_end':policy['validity'],'approved_at':'2020-01-01T00:00:00Z','expires_at':None,
                                'revocation_ref':None,'superseded_by':None}
            target=isolated/agent['admission_pass']
            target.write_text(json.dumps(permit),encoding='utf-8')
            accepted=sync['admitted_overlays'](isolated,wanted,sync['inventory'](isolated))
            self.assertEqual(accepted,{agent['admission_pass'],ref})
            for field,value in [('approver_id','isolated-fixture-reviewer'),('expires_at','2020-01-02T00:00:00Z'),('revocation_ref','fixture-revoked')]:
                original=permit['approval'][field];permit['approval'][field]=value
                target.write_text(json.dumps(permit),encoding='utf-8')
                with self.assertRaises(ValueError):sync['admitted_overlays'](isolated,wanted,sync['inventory'](isolated))
                permit['approval'][field]=original
            permit['subject']['version_or_digest']['candidate_digest']='0'*64
            target.write_text(json.dumps(permit),encoding='utf-8')
            with self.assertRaises(ValueError):sync['admitted_overlays'](isolated,wanted,sync['inventory'](isolated))

    def test_candidate_and_formal_admission_are_separate(self):
        result = sync['check'](FRAMEWORK, candidate_source=True)
        self.assertTrue(result['full_parity'])
        self.assertFalse(result['source_admission_verified'])
        # A new distribution must never inherit live source/local approval.
        with tempfile.TemporaryDirectory(dir=ROOT / '.godot-integration-local', prefix='pending-test-') as temporary:
            isolated=Path(temporary)/'Olympus'
            binding=json.loads((FRAMEWORK/'sync/binding.json').read_text(encoding='utf-8'))
            sync['build'](FRAMEWORK/binding['source'], isolated)
            manifest = json.loads((isolated / 'framework-manifest.json').read_text(encoding='utf-8'))
            for agent in manifest['agents']:
                permit = json.loads((isolated / agent['admission_pass']).read_text(encoding='utf-8'))
                self.assertIsNone(permit['approval'])
                self.assertEqual(permit['status'], 'pending_independent_review')
            process = subprocess.run([sys.executable, str(isolated / 'tools/verify_framework.py')],
                                     capture_output=True, encoding='utf-8')
            self.assertNotEqual(process.returncode, 0)

    def test_relocation_and_full_source_drift(self):
        binding = json.loads((FRAMEWORK / 'sync/binding.json').read_text(encoding='utf-8'))
        source = sync['source_root'](FRAMEWORK / binding['source'])
        with tempfile.TemporaryDirectory(dir=ROOT / '.godot-integration-local', prefix='portable-test-') as temporary:
            base = Path(temporary)
            relocated = base / 'checkout/Olympus'
            clone = base / 'upstream/framework'
            shutil.copytree(FRAMEWORK, relocated, ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(source, clone, ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(source.parent / 'work/sinan-events-review', base / 'upstream/work/sinan-events-review')
            pointer = base / 'upstream/CURRENT_FRAMEWORK.json'
            pointer.write_text(json.dumps({'root': 'framework'}), encoding='utf-8')
            binding['source'] = Path(os.path.relpath(pointer, relocated)).as_posix()
            binding['sinan_source'] = {'framework': Path(os.path.relpath(clone, relocated)).as_posix()}
            (relocated / 'sync/binding.json').write_text(json.dumps(binding), encoding='utf-8')
            process = subprocess.run([sys.executable, str(relocated / 'tools/verify_framework.py'), '--candidate'],
                                     cwd=base, capture_output=True, encoding='utf-8')
            self.assertEqual(process.returncode, 0, process.stderr)
            extra = clone / 'unexpected.txt'
            extra.write_text('fixture mutation, never a production source')
            with self.assertRaisesRegex(ValueError, 'drift'):
                sync['check'](relocated, candidate_source=True)
            extra.unlink()
            target = clone / 'specs/work-order-management.md'
            original = target.read_bytes()
            target.write_bytes(original + b'\nfixture mutation\n')
            with self.assertRaises(ValueError):
                sync['check'](relocated, candidate_source=True)
            target.write_bytes(original)
            target.unlink()
            with self.assertRaises((ValueError, FileNotFoundError)):
                sync['check'](relocated, candidate_source=True)
            target.write_bytes(original)
            approval = clone / 'reviews/sinan/event-change-review.json'
            value = json.loads(approval.read_text(encoding='utf-8'))
            value['approval']['revocation_ref'] = 'isolated-test-revocation'
            approval.write_text(json.dumps(value), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'inactive'):
                sync['check'](relocated, candidate_source=True)
            with self.assertRaises(ValueError):
                sync['check'](relocated, source=str(base / 'absent-source'))

    def test_hermes_exemption_and_source_archive_scope(self):
        def hashes(root):
            return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
        self.assertEqual(hashes(FRAMEWORK / 'extensions/hermes-files'), hashes(ROOT / 'Olympus/extensions/hermes-files'))
        self.assertFalse((FRAMEWORK / 'source-history.zip').exists())
        self.assertFalse((FRAMEWORK / 'source-sinan-history.zip').exists())
        self.assertTrue((FRAMEWORK / 'source-evidence.json').is_file())
        self.assertFalse((FRAMEWORK / 'modules/ariadne/scheduler.json').exists())


if __name__ == '__main__':
    unittest.main()
