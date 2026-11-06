"""Check the offline distribution before running framework and data checks."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def check_framework_pointer(root):
    pointer = json.loads((root / "CURRENT_FRAMEWORK.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "framework/framework-manifest.json").read_text(encoding="utf-8"))
    foundation = json.loads((root / "framework/foundation.lock.json").read_text(encoding="utf-8"))
    expected = {
        "path_base": "this_file_directory",
        "root": "framework",
        "manifest": "framework-manifest.json",
        "version": manifest["version"],
        "status": manifest["status"],
        "foundation_version": foundation["version"],
    }
    for field, value in expected.items():
        if pointer.get(field) != value:
            raise ValueError(f"CURRENT_FRAMEWORK.json: {field} must match the registered framework ({value})")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--require-committed", action="store_true")
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    check_framework_pointer(root)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    commands = [
        [sys.executable, str(root / "tools/check_gonggong_distribution.py")],
        [sys.executable, str(root / "framework/tools/verify_framework.py")],
        [
            sys.executable,
            str(root / "framework/extensions/diting-files/diting_files.py"),
            "git-check",
            "--repo",
            str(root),
        ]
        + (["--require-committed"] if a.require_committed else []),
    ]
    results = []
    for command in commands:
        r = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=env)
        if r.returncode:
            raise ValueError(r.stderr.strip() or r.stdout.strip())
        results.append(json.loads(r.stdout))
    print(
        json.dumps(
            {
                "workspace": "GongGong",
                "checks": results[1:],
                "offline_distribution": results[0],
                "agent_admission": "approved_local_definition_host_mandate_required",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
