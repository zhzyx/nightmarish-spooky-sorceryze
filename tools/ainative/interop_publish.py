"""Atomic, no-overwrite publication of staged interop artifacts."""

import hashlib
import json
import struct
import sys
from contextlib import nullcontext
from pathlib import Path

from extensions import publish_new
from portable_scene import prepare_scene


def publish(staged, target):
    data = Path(staged).read_bytes()
    suffix = Path(target).suffix.lower()
    if suffix == ".tscn":
        if not data.startswith(b"[gd_scene"):
            raise ValueError("Expected packed Godot scene")
    elif suffix == ".glb":
        if (
            len(data) < 12
            or data[:4] != b"glTF"
            or int.from_bytes(data[4:8], "little") != 2
            or int.from_bytes(data[8:12], "little") != len(data)
        ):
            raise ValueError("Expected complete GLB v2")
        offset, chunks = 12, []
        while offset < len(data):
            if offset + 8 > len(data):
                raise ValueError("Truncated GLB chunk")
            size, kind = struct.unpack_from("<I4s", data, offset)
            offset += 8
            if size % 4 or offset + size > len(data):
                raise ValueError("Invalid GLB chunk length")
            chunks.append((kind, data[offset : offset + size]))
            offset += size
        if not chunks or chunks[0][0] != b"JSON":
            raise ValueError("GLB JSON chunk required")
        document = json.loads(chunks[0][1])
        if document.get("asset", {}).get("version") != "2.0":
            raise ValueError("glTF 2.0 asset required")
        for buffer in document.get("buffers", []):
            if (
                "uri" in buffer
                or len(chunks) != 2
                or chunks[1][0] != b"BIN\x00"
                or buffer.get("byteLength", 0) > len(chunks[1][1])
            ):
                raise ValueError("GLB buffer payload missing or external")
    elif suffix == ".json":
        profile = json.loads(data)
        if profile.get("schema_version") != 1 or not profile.get("revision") or not profile.get("bones"):
            raise ValueError("Expected versioned skeleton profile")
    else:
        raise ValueError("Expected .tscn, .glb or .json destination")
    with prepare_scene(data, target) if suffix == ".tscn" else nullcontext(data) as payload:

        class Encoded:
            def encode(self, _manifest):
                return payload

        revision = hashlib.sha256(payload).hexdigest()
        manifest = {
            "schema_version": 1,
            "artifacts": [
                {
                    "id": "interop-output",
                    "type": "character",
                    "revision": revision,
                    "payload": {"encoding": suffix[1:]},
                    "binding": {"level": "unbound"},
                }
            ],
        }
        return publish_new(Encoded(), manifest, target)


if __name__ == "__main__":
    try:
        print(json.dumps(publish(*sys.argv[1:])))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
