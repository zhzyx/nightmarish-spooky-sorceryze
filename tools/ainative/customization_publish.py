"""Publish an immutable assembled scene and its SHA-bound FaceBinding sidecar."""

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path


def publish_snapshot(data: bytes, destination: Path) -> None:
    """Expose validated bytes through a private inode, without a caller-owned alias."""
    fd, temporary = tempfile.mkstemp(prefix=".assembly-", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def publish(staged: str, target: str) -> None:
    source = Path(staged)
    destination = Path(target)
    sidecar = Path(str(source) + ".face-binding.json")
    final_sidecar = Path(str(destination) + ".face-binding.json")
    data = source.read_bytes()
    binding_data = sidecar.read_bytes()
    binding = json.loads(binding_data)
    if not data.startswith(b"[gd_scene") or binding["asset_sha256"] != hashlib.sha256(data).hexdigest():
        raise ValueError("Staged scene/FaceBinding mismatch")
    # The scene is the commit point: a reader never sees it before its sidecar.
    # Exclusive hardlinks fail closed on an existing destination or unsupported FS.
    publish_snapshot(binding_data, final_sidecar)
    try:
        publish_snapshot(data, destination)
    except OSError:
        final_sidecar.unlink()
        raise


if __name__ == "__main__":
    publish(*sys.argv[1:])
