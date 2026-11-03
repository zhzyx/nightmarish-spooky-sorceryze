"""Check the installed distribution without consulting its external build source.

This is content integrity, not authentication or approval. Agent admission and
host permissions remain separate checks. Only the full rebuild creates a lock.
"""
import argparse
import hashlib
import json
import runpy
from pathlib import Path


def check(root):
    root = Path(root).resolve()
    inventory = runpy.run_path(str(root / 'sync/gonggong_sync.py'))['inventory']
    actual = inventory(root)
    lock = json.loads(actual['sync/runtime-lock.json'])
    if lock['schema_version'] != 1:
        raise ValueError('Unsupported runtime lock')
    manifest = json.loads(actual['framework-manifest.json'])
    for agent in manifest['agents']:
        agent.pop('candidate_digest', None)
    if manifest != lock['manifest']:
        raise ValueError('Runtime manifest changed; full rebuild required')
    allowed = {'sync/runtime-lock.json', 'framework-manifest.json',
               'sync/binding.json', 'sync/verification.json'}
    for agent in manifest['agents']:
        permit = agent['admission_pass']
        record = json.loads(actual[permit])
        allowed.add(permit)
        # Admission checks the approval, scope, subject and references later.
        # These are the only mutable evidence paths permitted in a release.
        refs = record.get('review', {}).get('evidence_refs', [])
        decision = (record.get('approval') or {}).get('decision_evidence_ref')
        for ref in [*refs, *([decision] if decision else [])]:
            if not isinstance(ref, str) or not ref.startswith('reviews/local-admission/') or '..' in ref.split('/') or '\\' in ref or ref not in actual:
                raise ValueError('Invalid local admission evidence')
            allowed.add(ref)
    wanted = lock['files']
    differences = sorted(p for p in set(actual) | set(wanted)
                         if p not in allowed and
                         (p not in actual or hashlib.sha256(actual[p]).hexdigest() != wanted.get(p)))
    if differences:
        raise ValueError('Local distribution drift: ' + ', '.join(differences[:20]))
    return {'local_integrity': True, 'external_source_required': False,
            'upstream_currentness_checked': False, 'host_authority_authenticated': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.root)))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, str(error) + '\n')
