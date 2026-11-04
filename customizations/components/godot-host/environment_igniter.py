"""Local environment igniter for the Godot host workspace.

Detects, deploys (pins) and rolls back the python/node/git runtimes the
GongGong bridge needs. The igniter never auto-installs: deployment only
records executable paths the user authorized or that were discovered in
fixed install locations, and makes them visible to bridge subprocesses by
writing a recovery state workspace under ``project/runtime/state/``.

State layout (all under the gitignored ``project/runtime/``):

- ``state/installed.json``   active deployment record + env manifest (atomic)
- ``state/deploy.log``       append-only install/rollback log
- ``state/recovery.md``      human-readable recovery entry (kept on rollback)
"""

import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

STATE_SCHEMA = 1
RUNTIME_DIR = "project/runtime"
STATE_DIR = "state"
INSTALLED = "installed.json"
DEPLOY_LOG = "deploy.log"
RECOVERY = "recovery.md"

# Install locations the igniter may deploy to. ``project-local`` is the default
# and keeps everything inside the workspace's gitignored runtime directory.
LOCATIONS = ("project-local", "user-level")


def runtime_root(root):
    return Path(root).resolve() / RUNTIME_DIR


def state_dir(root):
    return runtime_root(root) / STATE_DIR


def state_file(root):
    return state_dir(root) / INSTALLED


def _home():
    try:
        return Path.home()
    except RuntimeError:
        return None


def _is_file_executable(path):
    try:
        return path.is_file() and os.access(path, os.X_OK)
    except OSError:
        return False


def _sha256_file(path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _which(names, env):
    for name in names:
        found = shutil.which(name, path=env.get("PATH"))
        if found and _is_file_executable(Path(found)):
            return found
    return None


def _fixed_candidates(names, dirs):
    home = _home()
    for name in names:
        for directory in dirs:
            base = Path(directory)
            candidate = base / name
            if _is_file_executable(candidate):
                yield str(candidate)
            if home is not None:
                candidate = home / directory / name
                if _is_file_executable(candidate):
                    yield str(candidate)


def _runtime_candidates(root, relative_paths):
    for relative in relative_paths:
        candidate = runtime_root(root) / relative
        if _is_file_executable(candidate):
            yield str(candidate)


def discover_python(root, env):
    configured = env.get("GONGGONG_PYTHON")
    if configured and _is_file_executable(Path(configured)):
        return configured
    if _is_file_executable(Path(sys.executable)):
        return sys.executable
    for candidate in _runtime_candidates(root, ("python/python.exe", "python/bin/python3", "python/bin/python")):
        return candidate
    found = _which(("python3", "python"), env)
    if found:
        return found
    for candidate in _fixed_candidates(("python3", "python"), ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", ".local/bin")):
        return candidate
    return None


def discover_node(root, env):
    configured = env.get("GONGGONG_NODE")
    if configured and _is_file_executable(Path(configured)):
        return configured
    for candidate in _runtime_candidates(root, ("node/node.exe", "node/bin/node")):
        return candidate
    found = _which(("node",), env)
    if found:
        return found
    for candidate in _fixed_candidates(("node",), ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", ".local/bin", "n/bin")):
        return candidate
    return None


def discover_git(root, env):
    configured = env.get("GONGGONG_GIT")
    if configured and _is_file_executable(Path(configured)):
        return configured
    for candidate in _runtime_candidates(root, ("git/cmd/git.exe", "git/bin/git")):
        return candidate
    found = _which(("git",), env)
    if found:
        return found
    for candidate in _fixed_candidates(("git",), ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", ".local/bin")):
        return candidate
    return None


COMPONENTS = {
    "python": {
        "display": "Python",
        "discover": discover_python,
        "env_key": "GONGGONG_PYTHON",
        "evidence": ("--version",),
        "prepend_path": False,
    },
    "node": {
        "display": "Node.js",
        "discover": discover_node,
        "env_key": "GONGGONG_NODE",
        "evidence": ("--version",),
        "prepend_path": True,
    },
    "git": {
        "display": "Git",
        "discover": discover_git,
        "env_key": "GONGGONG_GIT",
        "evidence": ("--version",),
        "prepend_path": True,
    },
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _relative(root, path):
    """Return a workspace-relative path when possible, otherwise the absolute path."""
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(Path(path).resolve())


def component_status(root, env=None):
    env = env if env is not None else dict(os.environ)
    status = {}
    for component_id, definition in COMPONENTS.items():
        path = definition["discover"](root, env)
        status[component_id] = {
            "available": path is not None,
            "path": path,
            "sha256": _sha256_file(Path(path)) if path else None,
        }
    return status


def missing_components(root, env=None):
    return [component_id for component_id, item in component_status(root, env).items() if not item["available"]]


def read_state(root):
    path = state_file(root)
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(value, dict) or value.get("schema_version") != STATE_SCHEMA:
        return None
    return value


def _append_log(root, text):
    path = state_dir(root) / DEPLOY_LOG
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(_now() + " " + text + "\n")
    except OSError:
        pass


def write_state_atomic(root, data):
    directory = state_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / INSTALLED
    temporary = directory / (INSTALLED + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    os.replace(temporary, path)


def environment_check(root, env=None):
    env = env if env is not None else dict(os.environ)
    status = component_status(root, env)
    missing = [component_id for component_id, item in status.items() if not item["available"]]
    state = read_state(root)
    return {
        "ok": not missing,
        "environment_missing": missing,
        "components": status,
        "locations": list(LOCATIONS),
        "state": state,
        "recovery_status": recovery_status(root),
        "model_execution_started": False,
        "note": "Read-only environment detection; it never installs or grants permission.",
    }


def environment_deploy(root, selection, env=None):
    """Pin authorized component executables into the recovery state workspace."""
    env = env if env is not None else dict(os.environ)
    if not isinstance(selection, dict):
        raise ValueError("Environment deploy selection must be an object")
    components = selection.get("components")
    if not isinstance(components, list) or not components:
        raise ValueError("Select at least one component to deploy")
    if any(not isinstance(component, str) for component in components) or len(set(components)) != len(components):
        raise ValueError("Select each component only once using its component ID")
    unknown = [component for component in components if component not in COMPONENTS]
    if unknown:
        raise ValueError("Unknown component: " + ", ".join(unknown))
    location = selection.get("location", "project-local")
    if location not in LOCATIONS:
        raise ValueError("Unsupported install location: " + str(location))
    explicit = selection.get("paths") if isinstance(selection.get("paths"), dict) else {}
    status = component_status(root, env)
    deployed = []
    env_changes = {}
    for component_id in components:
        definition = COMPONENTS[component_id]
        path = explicit.get(component_id) if isinstance(explicit.get(component_id), str) else None
        if not path:
            path = status[component_id]["path"]
        if not path or not _is_file_executable(Path(path)):
            raise ValueError(
                "Cannot deploy " + component_id + ": no executable found and no explicit path provided. "
                "Install it yourself (for example with Homebrew) or provide its executable path; the igniter never auto-installs."
            )
        path = str(Path(path).resolve())
        if not os.access(path, os.X_OK):
            raise ValueError("Deploy path is not executable: " + path)
        deployed.append(
            {
                "id": component_id,
                "display": definition["display"],
                "path": _relative(root, path),
                "sha256": _sha256_file(Path(path)),
                "env_key": definition["env_key"],
                "evidence": list(definition["evidence"]),
            }
        )
        env_changes[definition["env_key"]] = path
        if definition["prepend_path"]:
            directories = env_changes.get("PATH", "").split(os.pathsep) if env_changes.get("PATH") else []
            if str(Path(path).parent) not in directories:
                directories.append(str(Path(path).parent))
            env_changes["PATH"] = os.pathsep.join(directories)
    record = {
        "schema_version": STATE_SCHEMA,
        "path_base": "workspace_root",
        "deployed_at": _now(),
        "location": location,
        "authorized": True,
        "components": deployed,
        "env_changes": env_changes,
        "recovery": "python3 tools/gonggong_bridge.py environment-rollback --workspace .",
    }
    write_state_atomic(root, record)
    _append_log(root, "deploy location=" + location + " components=" + ",".join(components))
    recovery = state_dir(root) / RECOVERY
    recovery.parent.mkdir(parents=True, exist_ok=True)
    with recovery.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(
            "# 环境部署恢复入口\n\n"
            "已部署组件：\n\n"
            + "".join("- " + item["display"] + " → `" + item["path"] + "`\n" for item in deployed)
            + "\n回退命令（在工作区根目录执行）：\n\n```\npython3 tools/gonggong_bridge.py environment-rollback --workspace .\n```\n\n"
            "日志：`project/runtime/state/deploy.log`\n"
        )
    return {
        "ok": True,
        "location": location,
        "components": deployed,
        "env_changes": env_changes,
        "state": record,
        "recovery": "project/runtime/state/" + RECOVERY,
    }


def environment_rollback(root, env=None):
    """Unpin the recorded deployment and restore the pre-deploy environment."""
    state = read_state(root)
    if state is None:
        return {
            "ok": False,
            "error": "No active deployment to roll back; recovery state workspace is empty.",
            "rolled_back": [],
        }
    rolled_back = [item["id"] for item in state.get("components", []) if isinstance(item, dict) and "id" in item]
    _append_log(root, "rollback components=" + ",".join(rolled_back))
    directory = state_dir(root)
    installed = directory / INSTALLED
    try:
        if installed.is_file():
            installed.unlink()
    except OSError as error:
        raise ValueError("Failed to clear deployment record: " + str(error)) from error
    # The recovery entry and log are intentionally preserved for audit and re-run.
    return {
        "ok": True,
        "rolled_back": rolled_back,
        "restored_env_keys": [item.get("env_key") for item in state.get("components", []) if isinstance(item, dict)],
        "recovery": "project/runtime/state/" + RECOVERY,
        "note": "Rollback unpins the recorded deployment; logs and the recovery entry are kept.",
    }


def recovery_status(root):
    """Validate persisted pins before a new bridge process restores them.

    Legacy schema-1 component paths also resolve against the workspace root.
    The manifest is local recovery evidence, not an authorization certificate.
    """
    state = read_state(root)
    if state is None:
        return {"ok": not state_file(root).exists(), "active": False, "env_changes": {},
                "error": "Invalid deployment record" if state_file(root).exists() else None}
    try:
        if state.get("path_base", "workspace_root") != "workspace_root" or state.get("authorized") is not True:
            raise ValueError("Invalid deployment metadata")
        components = state.get("components")
        if not isinstance(components, list) or not components:
            raise ValueError("Invalid deployment components")
        changes = {}
        directories = []
        seen = set()
        for item in components:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or item["id"] not in COMPONENTS or item["id"] in seen:
                raise ValueError("Invalid or duplicate deployment component")
            seen.add(item["id"])
            definition = COMPONENTS[item["id"]]
            if not isinstance(item.get("path"), str) or not item["path"]:
                raise ValueError("Invalid component path")
            path = (Path(root).resolve() / item["path"]).resolve()
            digest = _sha256_file(path)
            if not _is_file_executable(path) or digest is None or digest != item.get("sha256"):
                raise ValueError("Deployment component missing or changed: " + item["id"])
            changes[definition["env_key"]] = str(path)
            if definition["prepend_path"] and str(path.parent) not in directories:
                directories.append(str(path.parent))
        if directories:
            changes["PATH"] = os.pathsep.join(directories)
        return {"ok": True, "active": True, "env_changes": changes, "error": None}
    except (OSError, ValueError, TypeError) as error:
        return {"ok": False, "active": False, "env_changes": {}, "error": str(error)}


def apply_state(root, env):
    """Restore validated component pins, leaving invalid state for diagnosis."""
    recovery = recovery_status(root)
    if not recovery["ok"]:
        return env
    for key, value in recovery["env_changes"].items():
        if key == "PATH":
            directories = value.split(os.pathsep)
            directories.extend(p for p in env.get("PATH", "").split(os.pathsep) if p not in directories)
            env[key] = os.pathsep.join(directories)
        else:
            env[key] = value
    return env


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "deploy", "rollback"])
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--selection", type=Path)
    args = parser.parse_args()
    root = Path(args.workspace).resolve()
    if args.action == "check":
        print(json.dumps(environment_check(root), ensure_ascii=False, indent=2))
    elif args.action == "deploy":
        selection = json.loads(args.selection.read_text(encoding="utf-8")) if args.selection else {}
        print(json.dumps(environment_deploy(root, selection), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(environment_rollback(root), ensure_ascii=False, indent=2))
