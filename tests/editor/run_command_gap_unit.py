"""Run native command-gap regressions with a private editor and private test data."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from editor_test_isolation import copy_editor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    source = args.godot.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="command-gap-native-") as temporary:
        folder = Path(temporary)
        binary = copy_editor(source, folder / "editor")
        shutil.copytree(repo / "tests/data", folder / "tests/data")
        env = {key: value for key, value in os.environ.items() if not key.startswith("GONGGONG_")}
        result = subprocess.run(
            [str(binary), "--headless", "--test", "--test-case=*[Complex]*,*[Semantic]*,*Sub-agent*"],
            capture_output=True,
            env=env,
            cwd=folder,
            timeout=90,
        )
        output = (result.stdout + result.stderr).decode(errors="replace")
        report = {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "editor_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "output": output,
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2))
        print(output)
        if result.returncode:
            raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
