"""Read the native editor's four-path configuration; no interpreter bootstrap."""

import contextlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

FIELDS = {
    "node": "GONGGONG_NODE",
    "workflow_python": "GONGGONG_PYTHON",
    "build_python": "GONGGONG_BUILD_PYTHON",
    "codex": "GONGGONG_CODEX",
}


def configuration_path(env=None):
    env = os.environ if env is None else env
    explicit = env.get("GONGGONG_RUNTIME_CONFIG", "").strip()
    if explicit and Path(explicit).is_absolute() and "://" not in explicit:
        return Path(explicit)
    if sys.platform == "darwin":
        directory = Path(env["HOME"]) / "Library/Application Support" if env.get("HOME") else None
    elif os.name == "nt":
        directory = Path(env["APPDATA"]) if env.get("APPDATA") else None
    else:
        xdg = env.get("XDG_CONFIG_HOME", "")
        directory = (
            Path(xdg) if xdg and Path(xdg).is_absolute() else Path(env["HOME"]) / ".config" if env.get("HOME") else None
        )
    if directory is None or not directory.is_absolute():
        raise ValueError("runtime_configuration_path_unavailable")
    return directory / "gonggong/config.json"


@contextlib.contextmanager
def locked(path, timeout=2.0):
    """Same stable lock file and first-byte range as the native C++ helper."""
    path = Path(str(path) + ".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt
        else:
            import fcntl
        deadline = time.monotonic() + timeout
        while True:
            try:
                if os.name == "nt":
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise ValueError("runtime_configuration_busy") from None
                time.sleep(0.01)
        try:
            if os.name == "nt" and stream.seek(0, 2) == 0:
                # Lock first: another native process may own byte zero in a
                # newly created empty file. Never write through its lock.
                stream.write(b"\0")
                stream.flush()
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def read_effective(path=None, env=None):
    env = os.environ if env is None else env
    path = Path(path) if path is not None else configuration_path(env)
    if not path.is_absolute():
        raise ValueError("runtime_configuration_path_unavailable")
    with locked(path):
        if path.exists():
            if path.stat().st_size > 64 * 1024:
                raise ValueError("runtime_configuration_unreadable")
            document = json.loads(path.read_text(encoding="utf-8"))
            if (
                type(document) is not dict
                or type(document.get("schema_version")) not in (int, float)
                or document["schema_version"] != 1
                or type(document.get("runtimes")) is not dict
            ):
                raise ValueError("runtime_configuration_version_unsupported")
            configured = document["runtimes"]
            if any(
                key not in FIELDS or type(value) is not str or len(value) > 32768 for key, value in configured.items()
            ):
                raise ValueError("runtime_configuration_invalid")
        else:
            configured = {}
    try:
        derived = json.loads(env.get("GONGGONG_RUNTIME_DERIVED_ENV", "{}"))
    except (TypeError, ValueError):
        derived = {}
    if type(derived) is not dict:
        derived = {}
    defaults = {}
    node = shutil.which("node.exe" if os.name == "nt" else "node", path=env.get("PATH", ""))
    if node and Path(node).is_absolute():
        defaults["node"] = node
    source = Path(__file__).resolve().parent.parent
    for field, relative in (
        ("build_python", ".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python"),
        ("workflow_python", "project/runtime/python/python.exe"),
    ):
        value = source / relative
        if value.is_file() and os.access(value, os.X_OK):
            defaults[field] = str(value)
    paths, sources = {}, {}
    for field, name in FIELDS.items():
        external = env.get(name, "").strip()
        if external and derived.get(field) != external:
            paths[field], sources[field] = external, "environment"
        else:
            paths[field] = configured.get(field, defaults.get(field, "")).strip()
            sources[field] = "configuration" if field in configured else "default" if field in defaults else "missing"
    snapshot = {
        "ok": True,
        "schema_version": 1,
        "config_path": str(path),
        "paths": paths,
        "sources": sources,
        "configured": configured,
    }
    snapshot["executables"] = {field: runtime_path(snapshot, field) for field in FIELDS}
    return snapshot


def runtime_path(snapshot, field):
    value = snapshot["paths"].get(field, "")
    return (
        value
        if value
        and Path(value).is_absolute()
        and "://" not in value
        and Path(value).is_file()
        and os.access(value, os.X_OK)
        else ""
    )


def child_environment(snapshot, env=None):
    output = dict(os.environ if env is None else env)
    output["GONGGONG_RUNTIME_CONFIG"] = snapshot["config_path"]
    derived = {}
    for field, name in FIELDS.items():
        external = snapshot["sources"][field] == "environment"
        value = snapshot["paths"][field] if external else runtime_path(snapshot, field)
        if value:
            output[name] = value
            if not external:
                derived[field] = value
        else:
            output.pop(name, None)
    output["GONGGONG_RUNTIME_DERIVED_ENV"] = json.dumps(derived, separators=(",", ":"))
    return output
