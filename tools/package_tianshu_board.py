"""Deterministic, bounded legacy board compatibility package (tianshu-board-compat/1)."""

import argparse
import base64
import hashlib
import io
import json
import os
import tempfile
import zipfile
from pathlib import Path

ABI = "tianshu-board-compat/1"
SOURCE = Path(__file__).resolve().parents[1] / "customizations/components/godot-host/daqian"
NAMES = ("__main__.py", "board.py", "board_delta.py", "progress.py")
LIMIT = 4 * 1024 * 1024


def installed_package(executable):
    from package_tianshu_ui import installed_package as ui_package

    path = ui_package(executable)
    return path.with_name(path.name.replace("tianshu-ui", "tianshu-board"))


def archive_bytes(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name in NAMES:
            entry = zipfile.ZipInfo(name)
            entry.create_system = 0
            entry.compress_type = zipfile.ZIP_STORED
            archive.writestr(entry, entries[name])
    return stream.getvalue()


def validate(raw, pin=None):
    if not 0 < len(raw) <= LIMIT or (pin is not None and hashlib.sha256(raw).hexdigest() != pin):
        raise ValueError("board package size/pin mismatch")
    envelope = json.loads(raw)
    payload = envelope["payload"]
    if not isinstance(payload, str) or hashlib.sha256(payload.encode()).hexdigest() != envelope["sha256"]:
        raise ValueError("board payload digest")
    data = json.loads(payload)
    if data["abi"] != ABI or not isinstance(data["version"], str) or not data["version"].strip():
        raise ValueError("board ABI/version")
    bundle = base64.b64decode(data["bundle_base64"], validate=True)
    if (
        base64.b64encode(bundle).decode() != data["bundle_base64"]
        or hashlib.sha256(bundle).hexdigest() != data["bundle_sha256"]
    ):
        raise ValueError("board ZIP digest/encoding")
    if not isinstance(data["entries"], dict) or set(data["entries"]) != set(NAMES):
        raise ValueError("board entries")
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        infos = archive.infolist()
        if [entry.filename for entry in infos] != list(NAMES) or sum(
            entry.file_size for entry in infos
        ) > 16 * 1024 * 1024:
            raise ValueError("board ZIP entries/limit")
        if any(entry.compress_type != zipfile.ZIP_STORED for entry in infos):
            raise ValueError("board ZIP must be canonical stored format")
        entries = {name: archive.read(name) for name in NAMES}
    if archive_bytes(entries) != bundle:
        raise ValueError("noncanonical board ZIP")
    if any(hashlib.sha256(entries[name]).hexdigest() != data["entries"][name] for name in NAMES):
        raise ValueError("board entry digest")
    return data


def verify_candidate_package(manifest):
    expected = manifest.get("tianshu_board_sha256")
    if expected is None and "tools/package_tianshu_board.py" not in manifest.get("source_inputs", {}):
        return
    path = installed_package(manifest["executable"])
    if path.is_symlink() or not path.is_file() or path.stat().st_size > LIMIT:
        raise ValueError("candidate_tianshu_board_changed")
    validate(path.read_bytes(), expected or "missing")


def pack(source, version, output):
    entries = {
        name: (source / ("editor_board_entry.py" if name == "__main__.py" else name))
        .read_text(encoding="utf-8")
        .encode()
        for name in NAMES
    }
    bundle = archive_bytes(entries)
    payload = json.dumps(
        dict(
            abi=ABI,
            version=version,
            bundle_base64=base64.b64encode(bundle).decode(),
            bundle_sha256=hashlib.sha256(bundle).hexdigest(),
            entries={name: hashlib.sha256(value).hexdigest() for name, value in entries.items()},
        ),
        sort_keys=True,
    )
    raw = (json.dumps(dict(sha256=hashlib.sha256(payload.encode()).hexdigest(), payload=payload)) + "\n").encode()
    validate(raw)
    output.parent.mkdir(parents=True, exist_ok=True)
    stream = tempfile.NamedTemporaryFile(dir=output.parent, delete=False)
    temporary = Path(stream.name)
    try:
        with stream:
            stream.write(raw)
        temporary.chmod(0o644)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return hashlib.sha256(raw).hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--version", default="1")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(pack(args.source, args.version, args.output))
