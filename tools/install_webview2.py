#!/usr/bin/env python3
"""Acquire only pinned official WebView2 SDK files; never install the browser runtime."""

import argparse
import hashlib
import io
import json
import os
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPENDENCY = ROOT / "thirdparty" / "webview2"


def verify(data, expected, label):
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f"SHA-256 mismatch: {label}")


def reject_symlinks(path):
    path = Path(path).absolute()
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ValueError(f"Refusing symbolic-link dependency path: {component}")


def atomic_write(path, data):
    reject_symlinks(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".webview2-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def verify_installed():
    """Read-only SCons integration: returns verified SDK root, never downloads."""
    manifest = json.loads((DEPENDENCY / "manifest.json").read_text())
    destination = DEPENDENCY / "sdk"
    for name, digest in manifest["files"].items():
        target = destination / name
        reject_symlinks(target)
        if not target.is_file():
            raise FileNotFoundError("WebView2 SDK missing; run python tools/install_webview2.py")
        verify(target.read_bytes(), digest, name)
    return destination


def install(package=None):
    manifest = json.loads((DEPENDENCY / "manifest.json").read_text())
    destination = DEPENDENCY / "sdk"
    try:
        return verify_installed()
    except FileNotFoundError:
        pass
    # Existing corrupted files fail closed; remove the invalid SDK explicitly
    # before reacquisition rather than silently disguising tampering as repair.
    if package:
        data = Path(package).read_bytes()
    else:
        with urllib.request.urlopen(manifest["url"], timeout=90) as response:
            data = response.read()
    verify(data, manifest["sha256"], "NuGet package")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        files = {name: archive.read(name) for name in manifest["files"]}
        for name, content in files.items():
            verify(content, manifest["files"][name], name)
        for name, content in files.items():
            atomic_write(destination / name, content)
    return verify_installed()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, help="offline official .nupkg; same SHA-256 enforced")
    parser.add_argument("--arch", choices=("x86", "x64", "arm64"))
    parser.add_argument("--output-dir", type=Path, help="copy loader and license alongside editor executable")
    args = parser.parse_args()
    if bool(args.arch) != bool(args.output_dir):
        parser.error("--arch and --output-dir must be used together")
    sdk = install(args.package)
    if args.output_dir:
        atomic_write(
            args.output_dir / "WebView2Loader.dll",
            (sdk / "build/native" / args.arch / "WebView2Loader.dll").read_bytes(),
        )
        for name in ("LICENSE.txt", "NOTICE.txt"):
            atomic_write(args.output_dir / ("WebView2-" + name), (sdk / name).read_bytes())
    print(f"Verified WebView2 SDK: {sdk}")


if __name__ == "__main__":
    main()
