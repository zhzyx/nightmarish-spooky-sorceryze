"""Verify a trusted release archive digest and extract its exact file inventory."""
import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
import zipfile


def sha_file(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def editor_files(installed, revision):
    gui = 'bin/godot.windows.editor.x86_64.exe'
    console = 'bin/godot.windows.editor.x86_64.console.exe'
    if (installed.get('schema_version') != 2 or installed.get('main_revision') != revision
            or installed.get('default_editor') != gui or installed.get('console_editor') not in (gui, console)):
        raise ValueError('Release requires the verified installation of the exact source revision')
    records = {}
    for item in installed['files']:
        name = item['path']
        if (name not in (gui, installed['console_editor'], 'bin/tianshu-ui.json')
                and not re.fullmatch(r'bin/[\w.-]+\.dll', name, re.ASCII)):
            raise ValueError('Unexpected installed runtime component: ' + name)
        if name in records or not re.fullmatch('[a-fA-F0-9]{64}', item['sha256']):
            raise ValueError('Invalid installed runtime inventory')
        records[name] = item
    if not {gui, installed['console_editor'], 'bin/tianshu-ui.json'} <= records.keys():
        raise ValueError('Incomplete installed editor inventory')
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--extract', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if sha_file(args.archive) != args.sha256.lower():
        raise ValueError('Release archive checksum mismatch')
    destination = args.extract.resolve()
    report = args.report.resolve()
    if report == args.archive.resolve() or report.is_relative_to(destination):
        raise ValueError('Report must be outside the extracted tree and must not overwrite the archive')
    if report.exists():
        raise ValueError('Report must be a new file')
    if destination.exists():
        raise ValueError('Extract into a new directory to preserve existing work')
    with zipfile.ZipFile(args.archive) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)) or any(entry.is_dir() for entry in entries):
            raise ValueError('Duplicate or unexpected directory entry')
        manifest = json.loads(archive.read('bundle-manifest.json'))
        if set(names) != set(manifest['files']) | {'bundle-manifest.json'}:
            raise ValueError('Archive inventory differs from manifest')
        if manifest.get('schema_version') == 2:
            inventory = json.loads(archive.read('project/godot/installed.local.json'))
            records = editor_files(inventory, manifest['source_commit'])
            managed = {'project/godot/' + path for path in records}
            for name in names:
                if name.startswith('project/godot/') and (name.lower().endswith(('.exe', '.dll'))
                        or name.startswith('project/godot/bin/')) and name not in managed:
                    raise ValueError('Unexpected bundled editor file: ' + name)
            for name, record in records.items():
                entry = manifest['files']['project/godot/' + name]
                if entry['sha256'] != record['sha256'] or entry['bytes'] != record['bytes']:
                    raise ValueError('Bundled editor differs from verified installation: ' + name)
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in entry.filename or ':' in entry.filename:
                raise ValueError('Unsafe archive path')
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Symbolic link entries are not allowed')
            (destination / entry.filename).resolve().relative_to(destination)
        destination.mkdir(parents=True)
        for entry in entries:
            target = destination / entry.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as source, target.open('xb') as output:
                while block := source.read(1024 * 1024):
                    output.write(block)
            if entry.filename != 'bundle-manifest.json':
                expected = manifest['files'][entry.filename]
                if target.stat().st_size != expected['bytes'] or sha_file(target) != expected['sha256']:
                    raise ValueError('Extracted file mismatch: ' + entry.filename)
                target.chmod(int(expected['mode'], 8) & 0o777)
    result = {'archive_sha256': args.sha256.lower(), 'files_verified': len(manifest['files']),
              'source_commit': manifest['source_commit'], 'source_tree': manifest['source_tree'],
              'all_files_match': True, 'extracted_to_new_directory': True}
    args.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
