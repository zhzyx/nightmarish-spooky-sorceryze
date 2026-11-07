"""Package the built-in workbench's runtime scripts beside a new scene.

Only the manifest beside this installed tool is trusted. Ordinary project scenes
and scripts outside that exact deployment retain their original bytes. Runtime
files are durable before the caller atomically exposes the scene with publish_new.
"""

import hashlib
import json
import os
import re
import shutil
from contextlib import contextmanager
from pathlib import Path

_RESOURCE = re.compile(rb"(?m)^\[ext_resource\s+[^\r\n]*\]\r?$")
_TYPE = re.compile(rb'(?:^|\s)type=("(?:[^"\\]|\\.)*")')
_PATH = re.compile(rb'(?:^|\s)path=("(?:[^"\\]|\\.)*")')
_UID = re.compile(rb'\s+uid="(?:[^"\\]|\\.)*"')
_FILENAME = re.compile(r"[a-z][a-z0-9_]*\.gd\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")


def _script_reference(header, scripts):
    kind = _TYPE.search(header)
    path = _PATH.search(header)
    if kind is None or path is None or kind[1] != b'"Script"':
        return None
    decoded = json.loads(path[1].decode("utf-8"))
    value = Path(os.path.normpath(decoded))
    if value.is_absolute() and value.parent.resolve() == scripts.resolve():
        return value.name
    return None


def _runtime_snapshot(root, referenced):
    manifest_path = root / "manifest.json"
    scripts = root / "scripts"
    if manifest_path.is_symlink() or scripts.is_symlink():
        raise ValueError("Built-in runtime deployment must contain regular files")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("runtime_files") if isinstance(manifest, dict) else None
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != 1
        or not isinstance(files, dict)
        or not files
    ):
        raise ValueError("Invalid built-in runtime manifest")
    if not referenced.issubset(files):
        raise ValueError("Built-in scene references an unregistered runtime script")
    snapshot = {}
    for name, digest in sorted(files.items()):
        if (
            not isinstance(name, str)
            or not _FILENAME.fullmatch(name)
            or not isinstance(digest, str)
            or not _HASH.fullmatch(digest)
        ):
            raise ValueError("Invalid built-in runtime file record")
        source = scripts / name
        if source.is_symlink() or not source.is_file():
            raise ValueError("Built-in runtime script is missing or linked")
        payload = source.read_bytes()
        if hashlib.sha256(payload).hexdigest() != digest:
            raise ValueError("Built-in runtime script differs from its manifest")
        snapshot[name] = payload
    revision = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return snapshot, revision


def _write_file(path, payload):
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _remove_owned(directory, identity):
    try:
        current = directory.stat(follow_symlinks=False)
    except FileNotFoundError:
        return
    if (current.st_dev, current.st_ino) == identity:
        shutil.rmtree(directory)


@contextmanager
def prepare_scene(data, target):
    """Yield portable scene bytes; retain dependencies only on successful exit.

    The caller must publish the yielded bytes before leaving the context. The
    original stage, source asset hashes and other metadata are never rewritten.
    An existing runtime directory is never reused or changed, including a partial
    earlier publication: choose a new version name instead.
    """
    root = Path(__file__).resolve().parent.parent
    scripts = root / "scripts"
    if not (root / "manifest.json").is_file():
        yield data
        return
    references = {
        name for match in _RESOURCE.finditer(data) if (name := _script_reference(match[0], scripts)) is not None
    }
    if not references:
        yield data
        return
    snapshot, revision = _runtime_snapshot(root, references)
    target = Path(target)
    if os.path.lexists(target):
        raise FileExistsError("Choose a new character version filename")
    # Bound the directory name even for a long UTF-8 scene filename.
    version = hashlib.sha256(target.name.encode("utf-8")).hexdigest()[:8]
    directory = target.with_name(target.stem[:40] + ".ainative-" + revision[:16] + "-" + version)
    directory.mkdir()
    created = directory.stat(follow_symlinks=False)
    identity = (created.st_dev, created.st_ino)
    try:
        for name, payload in snapshot.items():
            _write_file(directory / name, payload)

        def rewrite(match):
            header = match[0]
            name = _script_reference(header, scripts)
            if name is None:
                return header
            value = _PATH.search(header)
            relative = directory.name + "/" + name
            encoded = json.dumps(relative, ensure_ascii=False).encode("utf-8")
            header = header[: value.start(1)] + encoded + header[value.end(1) :]
            # A UID from the editor's script cache must not redirect the new path.
            return _UID.sub(b"", header)

        yield _RESOURCE.sub(rewrite, data)
    except BaseException:
        _remove_owned(directory, identity)
        raise
