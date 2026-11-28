"""Fetch and verify the optional Windows x64 upscaling SDKs before running SCons."""

import argparse
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".cache/temporal-sdk"
MANIFEST = Path(__file__).with_name("upscaler_sdk.json")


def verified(path, size, digest):
    if not path.is_file() or path.stat().st_size != size:
        return False
    hasher = hashlib.sha1(f"blob {size}\0".encode())
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest() == digest


def download(job):
    url, target, size, digest = job
    if verified(target, size, digest):
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temp:
        staging = Path(temp.name)
    try:
        args = [
            "curl.exe",
            "--fail",
            "--silent",
            "--show-error",
            "--location",
            "--connect-timeout",
            "12",
            "--max-time",
            "360",
            "--retry",
            "3",
            "--retry-all-errors",
            "--output",
            str(staging),
            url,
        ]
        local_runtime = ROOT / "bin" / target.name
        if target.suffix == ".dll" and target != local_runtime and verified(local_runtime, size, digest):
            shutil.copyfile(local_runtime, staging)
        else:
            subprocess.run(args, check=True)
        if not verified(staging, size, digest):
            raise ValueError(f"Content differs from the pinned Git blob for {target}.")
        os.replace(staging, target)
    finally:
        staging.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        default=ROOT / "bin",
        help="Directory containing the Windows editor or exported game executable.",
    )
    runtime = parser.parse_args().runtime_dir.resolve()
    jobs = []
    notices = []
    for vendor, package in json.loads(MANIFEST.read_text(encoding="utf-8")).items():
        for path, info in package["files"].items():
            filename = Path(path).name
            target = runtime / filename if filename.endswith(".dll") else CACHE / vendor / path
            url = f"https://raw.githubusercontent.com/{package['repository']}/{package['commit']}/{path}"
            jobs.append((url, target, info["size"], info["blob"]))
            if filename.lower() in ("license.txt", "license.md"):
                notices.append((target, runtime / f"{vendor}-upscaler-{filename}"))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(download, jobs))
    for source, target in notices:
        shutil.copyfile(source, target)
    print(f"Verified {len(jobs)} SDK files. Rebuild the Windows x64 editor or export template.")


if __name__ == "__main__":
    main()
