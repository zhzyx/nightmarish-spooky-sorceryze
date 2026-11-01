"""Package one committed source snapshot with verified local Windows deliverables."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', default='HEAD')
    parser.add_argument('--editor-stage', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--build-root', type=Path, required=True, help='Actual original compiler source root, checked for accidental leakage')
    args = parser.parse_args()
    if args.out.exists() or args.manifest.exists():
        raise ValueError('Output files must be new')
    ref = subprocess.check_output(['git', 'rev-parse', args.ref + '^{commit}'], cwd=ROOT).decode().strip()
    tree = subprocess.check_output(['git', 'rev-parse', ref + '^{tree}'], cwd=ROOT).decode().strip()
    anchors = json.loads(subprocess.check_output(['git', 'show', ref + ':distribution/deliverables.json'], cwd=ROOT))
    files = {}
    forbidden = []
    for root in (ROOT, Path.home(), args.build_root.resolve()):
        for text in (str(root).replace('\\', '/'), str(root).replace('/', '\\')):
            forbidden += [text.lower().encode('utf-8'), text.lower().encode('utf-16-le')]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary, zipfile.ZipFile(args.out, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        source_zip = Path(temporary) / 'source.zip'
        subprocess.run(['git', 'archive', '--format=zip', '--output', str(source_zip), ref], cwd=ROOT, check=True)
        def add(name, data, origin, mode=0o100644):
            if name in files or name.startswith('/') or '..' in name.split('/'):
                raise ValueError('Duplicate or unsafe archive entry: ' + name)
            if any(prefix in data.lower() for prefix in forbidden):
                raise ValueError('Machine-specific path in deliverable: ' + name)
            entry = zipfile.ZipInfo(name, (2026, 11, 2, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            if mode not in (0o100644, 0o100755):
                raise ValueError('Unsupported source file mode: ' + name)
            entry.external_attr = mode << 16
            archive.writestr(entry, data)
            files[name] = {'sha256': digest(data), 'bytes': len(data), 'origin': origin, 'mode': oct(mode)}
        with zipfile.ZipFile(source_zip) as source:
            for entry in source.infolist():
                if not entry.is_dir():
                    mode = entry.external_attr >> 16
                    add(entry.filename, source.read(entry), 'git:' + ref, mode or 0o100644)
        runtime_raw = (ROOT / 'project/runtime/installed.local.json').read_bytes()
        if digest(runtime_raw) != anchors['runtime_inventory_sha256']:
            raise ValueError('Runtime inventory differs from reviewed inventory')
        runtime_manifest = json.loads(runtime_raw)
        for item in runtime_manifest['files']:
            data = (ROOT / 'project/runtime' / item['path']).read_bytes()
            if digest(data) != item['sha256']:
                raise ValueError('Installed runtime changed: ' + item['path'])
            add('project/runtime/' + item['path'], data, 'verified_local_runtime')
        add('project/runtime/installed.local.json', (ROOT / 'project/runtime/installed.local.json').read_bytes(), 'runtime_inventory')
        installed = json.loads((ROOT / 'project/godot/installed.local.json').read_text(encoding='utf-8-sig'))
        if {item['path'] for item in installed['files']} != set(anchors['editor']):
            raise ValueError('Editor installation file set differs from reviewed inventory')
        for item in installed['files']:
            data = (args.editor_stage / item['path']).read_bytes()
            if digest(data) != anchors['editor'][item['path']]:
                raise ValueError('Editor differs from reviewed artifact: ' + item['path'])
            item['sha256'], item['bytes'] = digest(data), len(data)
            add('project/godot/' + item['path'], data, 'reviewed_release_editor_derivative')
        add('project/godot/installed.local.json', (json.dumps(installed, indent=2) + '\n').encode(), 'release_installation_inventory')
        fallback = ROOT / 'project/godot/versions/godot-4.7.2'
        for name, expected in anchors['fallback'].items():
            path = fallback / name
            data = path.read_bytes()
            if digest(data) != expected:
                raise ValueError('Fallback differs from original installed artifact: ' + name)
            add(path.relative_to(ROOT).as_posix(), data, 'original_unmodified_godot_4.7.2')
        manifest = {'schema_version': 1, 'source_commit': ref, 'source_tree': tree,
                    'path_base': 'extracted_workspace_root', 'created_at': datetime.now(timezone.utc).isoformat(),
                    'model_validation': 'simulated_only', 'requires_valid_gonggong_source_binding': True,
                    'source_history_included': False, 'files': files}
        raw_manifest = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode()
        archive.writestr('bundle-manifest.json', raw_manifest)
    manifest['archive'] = {'name': args.out.name, 'bytes': args.out.stat().st_size,
                           'sha256': digest(args.out.read_bytes()), 'internal_manifest_sha256': digest(raw_manifest)}
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'source_commit': ref, 'files': len(files), 'archive': manifest['archive']}))


if __name__ == '__main__':
    main()
