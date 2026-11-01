"""Stage existing Windows Python/Node runtimes for an IDE-independent local install."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def stage_git(source, destination):
    source = source.resolve()
    if not (source / 'cmd/git.exe').is_file() or destination.exists():
        raise ValueError('Git home must contain cmd/git.exe and destination must be new')
    files = [p for p in source.rglob('*') if p.is_file()]
    if any(p.is_symlink() for p in files):
        raise ValueError('Linked Git inputs are not supported')
    records = []
    for original in files:
        target = destination / original.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        digest = hashlib.sha256(original.read_bytes()).hexdigest()
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError('Git copy checksum mismatch')
        records.append({'path': 'git/' + original.relative_to(source).as_posix(), 'sha256': digest})
    subprocess.run([str(destination / 'cmd/git.exe'), '--version'], check=True)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python-home', type=Path, required=True)
    parser.add_argument('--node', type=Path, required=True)
    parser.add_argument('--git-home', type=Path, help='Portable Git home containing cmd/git.exe; otherwise Git must be on PATH')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    destination = root / 'project/runtime'
    source = args.python_home.resolve()
    node = args.node.resolve()
    if not (source / 'python.exe').is_file() or not node.is_file():
        raise ValueError('Existing Python home and Node executable are required')
    if destination.exists():
        raise ValueError('Runtime destination already exists; preserve it and review an explicit upgrade')
    # Use the standard library; do not copy IDE packages, credentials or site customizations.
    selected = [p for p in source.iterdir() if p.is_file() and
                (p.name in ('python.exe', 'vcruntime140.dll', 'vcruntime140_1.dll', 'LICENSE.txt')
                 or (p.name.startswith('python') and p.suffix == '.dll'))]
    for folder in ('DLLs', 'Lib', 'tcl'):
        if (source / folder).is_dir():
            selected += [p for p in (source / folder).rglob('*') if p.is_file()
                         and not {'site-packages', '__pycache__'}.intersection(p.relative_to(source).parts)
                         and p.name not in ('sitecustomize.py', 'usercustomize.py')]
    if any(p.is_symlink() for p in selected):
        raise ValueError('Linked runtime inputs are not supported')
    files = []
    for original in selected + [node]:
        target = destination / ('node/node.exe' if original == node else 'python/' + original.relative_to(source).as_posix())
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        digest = hashlib.sha256(original.read_bytes()).hexdigest()
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError('Runtime copy checksum mismatch')
        files.append({'path': target.relative_to(destination).as_posix(), 'sha256': digest})
    subprocess.run([str(destination / 'python/python.exe'), '-I', '-c', 'import ssl,sqlite3,json,hashlib,subprocess; print("Python standard runtime ready")'], check=True)
    subprocess.run([str(destination / 'node/node.exe'), '--version'], check=True)
    if args.git_home:
        files += stage_git(args.git_home, destination / 'git')
    (destination / 'installed.local.json').write_text(json.dumps({'schema_version': 1, 'path_base': 'runtime_directory', 'files': files}, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'installed_files': len(files), 'path': 'project/runtime', 'site_packages_copied': False}))


if __name__ == '__main__':
    main()
