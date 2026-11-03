#!/usr/bin/env python3
"""Read-only Git delivery consistency gate; never executes reports or approves release."""
import argparse
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
import subprocess
import sys


BOUNDARY = ('Local file/Git and supplied metadata consistency only; no authentication of '
            'remote identity, report authorship, execution, model service or collection behavior; '
            'not admission or release approval.')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


def inputs_digest(manifest):
    return digest({k: manifest[k] for k in ('dependencies', 'artifacts', 'model_mode')})


def file_hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class Invalid(Exception):
    pass


def check(manifest, framework):
    errors = []

    def fail(code, field, message, action):
        errors.append(dict(code=code, field=field, message=message, action=action))

    def require(ok, code, field, message, action='Correct the field and regenerate evidence for this candidate.'):
        if not ok:
            fail(code, field, message, action)
            raise Invalid()

    def path(value, field):
        require(isinstance(value, str) and bool(value.strip()) and '\\' not in value
                and not Path(value).is_absolute() and not PureWindowsPath(value).drive
                and not PureWindowsPath(value).is_absolute(), 'path', field,
                'Use a nonempty relative path with /, resolved against framework.')
        return (framework / value).resolve()

    def hashed(ref, field):
        require(isinstance(ref, dict), 'schema', field, 'Expected path/sha256 object.')
        p = path(ref.get('path'), field + '.path')
        require(isinstance(ref.get('sha256'), str) and re.fullmatch('[0-9a-f]{64}', ref['sha256']),
                'schema', field, 'Expected lowercase SHA256.')
        require(p.is_file(), 'missing_file', field, 'Referenced file is missing.', 'Provide the referenced file; do not substitute an unrelated output.')
        actual = file_hash(p)
        require(actual == ref['sha256'], 'digest_mismatch', field,
                'Recorded SHA256 differs from current file: ' + actual,
                'Block affected delivery; inspect drift and create a separately reviewed candidate. Do not rewrite the baseline.')
        return p

    def git(repo, *args):
        result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, check=False)
        require(result.returncode == 0, 'git', 'candidate',
                result.stderr.decode('utf-8', errors='replace').strip(),
                'Use the actual authorized Git repository and an existing commit; no global Git configuration is changed.')
        return result.stdout

    try:
        require(isinstance(manifest, dict), 'schema', '$', 'Expected JSON object.')
        require(manifest.get('schema_version') == 1 and manifest.get('path_base') == 'framework',
                'schema', '$', 'schema_version must be 1; path_base must be framework.')
        require(manifest.get('stage') in ('candidate', 'published'), 'schema', 'stage', 'Use candidate or published.')
        require(manifest.get('delivery_kind') in ('source', 'runnable'), 'schema', 'delivery_kind', 'Use source or runnable.')
        require(manifest.get('model_mode') in ('none', 'simulated', 'real'), 'schema', 'model_mode', 'Use none, simulated or real.')
        candidate = manifest.get('candidate')
        require(isinstance(candidate, dict) and set(candidate) == {'repository', 'commit', 'tree'},
                'schema', 'candidate', 'Expected repository, commit and tree only.')
        repo = path(candidate['repository'], 'candidate.repository')
        require(repo.is_dir(), 'repository', 'candidate.repository', 'Repository directory is missing.')
        top = Path(git(repo, 'rev-parse', '--show-toplevel').decode().strip()).resolve()
        require(repo == top, 'repository', 'candidate.repository', 'Path must be the actual Git worktree root.')
        for key in ('commit', 'tree'):
            require(isinstance(candidate[key], str) and re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}', candidate[key]),
                    'schema', 'candidate.' + key, 'Use a full Git object ID.')
        actual_commit = git(repo, 'rev-parse', '--verify', candidate['commit'] + '^{commit}').decode().strip()
        actual_tree = git(repo, 'rev-parse', '--verify', candidate['commit'] + '^{tree}').decode().strip()
        require(actual_commit == candidate['commit'] and actual_tree == candidate['tree'],
                'candidate_mismatch', 'candidate', 'Commit/tree do not identify the same candidate.')
        for key in ('dependencies', 'artifacts'):
            require(isinstance(manifest.get(key), list), 'schema', key, 'Expected list (dependencies may be empty).')
        require(bool(manifest['artifacts']), 'schema', 'artifacts', 'List at least one delivered artifact.')
        ids = set()
        for index, dependency in enumerate(manifest['dependencies']):
            field = 'dependencies[' + str(index) + ']'
            try:
                require(isinstance(dependency, dict) and isinstance(dependency.get('version'), str)
                        and bool(dependency['version'].strip()) and isinstance(dependency.get('affects'), list)
                        and bool(dependency['affects']) and all(isinstance(x, str) and x for x in dependency['affects']),
                        'schema', field, 'Dependency needs version, file path/SHA256 and nonempty affects list.')
                hashed(dependency, field)
            except Invalid:
                if isinstance(dependency, dict):
                    errors[-1]['affected'] = dependency.get('affects', [])
        for index, artifact in enumerate(manifest['artifacts']):
            field = 'artifacts[' + str(index) + ']'
            try:
                require(isinstance(artifact, dict) and isinstance(artifact.get('id'), str) and artifact['id']
                        and artifact['id'] not in ids, 'schema', field, 'Artifact needs a unique nonempty id.')
                ids.add(artifact['id'])
                require(artifact.get('role') in ('source', 'runnable'), 'schema', field, 'Artifact role must be source or runnable.')
                hashed(artifact, field)
                require(isinstance(artifact.get('distribution'), str) and bool(artifact['distribution'].strip()),
                        'schema', field, 'Describe how the recipient obtains this artifact.')
                if artifact['role'] == 'source':
                    source = artifact.get('candidate_path')
                    require(isinstance(source, str) and source and '\\' not in source
                            and not PureWindowsPath(source).drive and not source.startswith('/')
                            and '..' not in source.split('/'), 'schema', field, 'Source needs candidate_path relative to repository root.')
                    blob = git(repo, 'show', candidate['commit'] + ':' + source)
                    require(hashlib.sha256(blob).hexdigest() == artifact['sha256'], 'source_mismatch', field,
                            'Source artifact differs from the committed candidate.')
            except Invalid:
                pass
        if manifest['delivery_kind'] == 'runnable':
            require(any(a.get('role') == 'runnable' for a in manifest['artifacts'] if isinstance(a, dict)),
                    'runnable_missing', 'artifacts', 'Source files cannot replace the required runnable artifact.')
        else:
            require(any(a.get('role') == 'source' for a in manifest['artifacts'] if isinstance(a, dict)),
                    'source_missing', 'artifacts', 'Source delivery needs a committed source artifact.')
        fingerprint = inputs_digest(manifest)

        def evidence(ref, field, kind):
            p = hashed(ref, field)
            try:
                data = json.loads(p.read_text(encoding='utf-8-sig'))
            except (ValueError, UnicodeError):
                require(False, 'evidence_json', field, 'Evidence must be a JSON report.')
            require(isinstance(data, dict), 'evidence_json', field, 'Report must be an object.')
            require(data.get('candidate') == candidate and data.get('inputs_sha256') == fingerprint,
                    'evidence_binding', field, 'Report does not bind this exact repository, commit/tree and input snapshot.')
            require(data.get('kind') == kind and data.get('status') == 'passed',
                    'evidence_status', field, 'Report must record kind=' + kind + ' and status=passed.')
            return data

        validations = manifest.get('validation', {})
        require(isinstance(validations, dict), 'schema', 'validation', 'Expected map of validation evidence references.')
        required = ['source'] if manifest['delivery_kind'] == 'source' else ['build', 'install', 'start', 'business']
        if manifest['model_mode'] != 'none':
            required.append('model')
        for kind in required:
            try:
                report = evidence(validations.get(kind), 'validation.' + kind, kind)
                if kind == 'model':
                    require(report.get('model_mode') == manifest['model_mode'], 'model_boundary', 'validation.model',
                            'Simulation is not evidence of a real model service.')
            except Invalid:
                pass
        collection = manifest.get('collection')
        require(isinstance(collection, dict), 'schema', 'collection', 'Collection state and evidence are mandatory.')
        states = ['configured', 'queued', 'delivered', 'consumed']
        require(collection.get('state') in states, 'schema', 'collection.state', 'Use configured, queued, delivered or consumed.')
        batch = None
        receipt = None
        for state in states[:states.index(collection['state']) + 1]:
            try:
                report = evidence(collection.get(state), 'collection.' + state, 'collection.' + state)
                if state == 'configured':
                    require(isinstance(report.get('binding'), dict), 'collection_binding', 'collection.configured', 'Reference the existing host reporting binding as path/SHA256.')
                    hashed(report['binding'], 'collection.configured.binding')
                if state in ('queued', 'delivered', 'consumed'):
                    require(isinstance(report.get('batch_id'), str) and bool(report['batch_id']), 'collection_batch', 'collection.' + state, 'Nonempty batch_id required; an empty queue is not success.')
                    if state == 'queued':
                        batch = report['batch_id']
                    else:
                        require(report['batch_id'] == batch, 'collection_batch', 'collection.' + state, 'Receipt batch does not match queued batch.')
                if state == 'delivered':
                    receipt = report.get('receipt_id')
                    require(isinstance(receipt, str) and bool(receipt), 'collection_receipt', 'collection.delivered', 'Receiver receipt_id required.')
                if state == 'consumed':
                    require(report.get('receipt_id') == receipt and isinstance(report.get('consumer'), str)
                            and bool(report['consumer']), 'collection_consumption', 'collection.consumed', 'Consumer confirmation must reference the receiver receipt.')
            except Invalid:
                pass
        if manifest['stage'] == 'published':
            try:
                report = evidence(manifest.get('publication'), 'publication', 'publication')
                require(isinstance(report.get('remote'), str) and bool(report['remote']) and
                        isinstance(report.get('receipt_id'), str) and bool(report['receipt_id']),
                        'publication_receipt', 'publication', 'Remote destination and readback receipt_id required.')
            except Invalid:
                pass
    except Invalid:
        pass
    except (OSError, ValueError, TypeError, KeyError) as exc:
        fail('invalid_input', '$', str(exc), 'Repair the manifest or referenced local file; rerun this single check.')
    return {'ok': not errors, 'scope': 'local_consistency', 'boundary': BOUNDARY,
            'diagnostics': errors}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, epilog=BOUNDARY)
    parser.add_argument('manifest', help='Manifest path relative to --framework-root')
    parser.add_argument('--framework-root', type=Path, default=Path(__file__).resolve().parents[1],
                        help='Explicit resolution base; defaults to this tool framework directory, never cwd')
    parser.add_argument('--inputs-digest', action='store_true', help='Print input snapshot digest only; does NOT perform acceptance')
    args = parser.parse_args(argv)
    try:
        if Path(args.manifest).is_absolute() or PureWindowsPath(args.manifest).drive or '\\' in args.manifest:
            raise ValueError('Manifest path must be relative to framework root, with / separators.')
        manifest = json.loads((args.framework_root / args.manifest).read_text(encoding='utf-8-sig'))
        if args.inputs_digest:
            print(json.dumps({'inputs_sha256': inputs_digest(manifest), 'accepted': False}))
            return 0
        result = check(manifest, args.framework_root.resolve())
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result = {'ok': False, 'scope': 'local_consistency', 'boundary': BOUNDARY,
                  'diagnostics': [{'code': 'invalid_input', 'field': '$', 'message': str(exc),
                                   'action': 'Provide a valid manifest relative to the explicit framework root.'}]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
