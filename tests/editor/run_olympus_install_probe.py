"""Verify installed editor location discovery with no workspace environment override."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--godot', type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='olympus-install-') as temporary:
        folder = Path(temporary)
        (folder / 'project.godot').write_text('[application]\nconfig/name="Installation probe"\n', encoding='utf-8')
        shutil.copyfile(ROOT / 'tests/editor/olympus_install_probe.gd', folder / 'probe.gd')
        env = dict(os.environ, OLYMPUS_EXPECTED_WORKSPACE=str(ROOT))
        env.pop('OLYMPUS_WORKSPACE', None)
        env.pop('OLYMPUS_PYTHON', None)
        env.pop('OLYMPUS_NODE', None)
        for name in ('APPDATA', 'LOCALAPPDATA', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME'):
            directory = folder / name
            directory.mkdir()
            env[name] = str(directory)
        result = subprocess.run([str(args.godot.resolve()), '--headless', '--editor', '--path', str(folder), '--script', 'res://probe.gd'],
                                cwd=folder, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
        if result.returncode or 'OLYMPUS_INSTALLED_WORKSPACE_DISCOVERY_OK' not in result.stdout:
            print(result.stdout[-5000:])
            print(result.stderr[-5000:])
            return 1
        print('Installed editor found workspace from executable ancestors; isolated settings, unrelated cwd, no workspace override.')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
