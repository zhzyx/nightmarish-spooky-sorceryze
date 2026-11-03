"""Verify GongGong package admission and requirement data delivery."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--require-committed", action="store_true")
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    commands = [
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
                "checks": results,
                "agent_admission": "approved_local_definition_host_mandate_required",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
