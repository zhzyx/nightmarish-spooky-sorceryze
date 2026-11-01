"""Verify a trusted release archive digest and extract its exact file inventory."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile


def sha_file(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


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
