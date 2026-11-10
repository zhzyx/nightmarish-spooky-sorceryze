"""Build the Windows editor and validate this checkout's AIChat runtime."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

from editor_native_cache import build_or_reuse
from editor_source_manifest import git_bytes, source_snapshot


def build(root, jobs, use_mingw=False, cache_path=None, cache_limit=8):
    if jobs < 1 or cache_limit <= 0:
        raise ValueError("Jobs and the SCons object cache limit must be positive")
    env = dict(os.environ, MSYSTEM="")
    options = dict(
        platform="windows",
        target="editor",
        arch="x86_64",
        dev_build="no",
        precision="single",
        module_mono_enabled="no",
        ninja="no",
        extra_suffix="",
        tests="yes",
        accesskit="no",
        d3d12="no",
        angle="no",
    )
    if use_mingw:
        options["use_mingw"] = "yes"
    if cache_path:
        options.update(cache_path=str(Path(cache_path).resolve()), cache_limit=str(cache_limit))
    command = [sys.executable, "-m", "SCons", *(f"{k}={v}" for k, v in options.items()), f"-j{jobs}"]
    binary = root / "bin/godot.windows.editor.x86_64.exe"
    head = git_bytes(root, "rev-parse", "HEAD").decode().strip()
    clean_source = not git_bytes(root, "status", "--porcelain", "--untracked-files=all").strip()
    source = source_snapshot(root)["source_digest"]

    def compile_editor():
        subprocess.run(command, cwd=root, env=env, check=True)

    native = build_or_reuse(root, options, binary, compile_editor, env=env)
    package = root / "bin/tianshu-ui.json"
    subprocess.run([sys.executable, "tools/package_tianshu_ui.py", "--output", str(package)], cwd=root, check=True)
    console = binary.with_suffix(".console.exe")
    subprocess.run([console, "--headless", "--test", "--test-case=[AIChat]*"], cwd=root, check=True)
    if (
        source_snapshot(root)["source_digest"] != source
        or git_bytes(root, "rev-parse", "HEAD").decode().strip() != head
    ):
        raise RuntimeError("Worktree changed during build or validation")
    receipt = dict(
        worktree=str(root),
        revision=head,
        source_digest=source,
        clean_source=clean_source,
        console_sha256=hashlib.sha256(console.read_bytes()).hexdigest(),
        native=native,
        tianshu_sha256=hashlib.sha256(package.read_bytes()).hexdigest(),
        aichat="passed",
    )
    folder = root / "bin/gonggong-build-receipts"
    folder.mkdir(exist_ok=True)
    path = folder / (uuid.uuid4().hex + ".json")
    path.with_suffix(".tmp").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    path.with_suffix(".tmp").replace(path)
    print(path)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--use-mingw", action="store_true")
    parser.add_argument("--cache-path", type=Path)
    parser.add_argument("--cache-limit", type=int, default=8, help="SCons object cache limit in GiB")
    args = parser.parse_args()
    build(Path(__file__).resolve().parents[1], args.jobs, args.use_mingw, args.cache_path, args.cache_limit)
