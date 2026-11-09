"""Bind actual source inputs and an executable to a host-owned candidate."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from package_tianshu_ui import installed_package, verify_candidate_package

EXCLUDED_ROOTS = {
    ".git",
    "bin",
    ".godot",
    ".venv",
    "design-docs",
    "data-collection",
    "gonggong-diting-data",
    "olympus-hermes-data",
    "archive",
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def git_bytes(root, *args):
    return subprocess.check_output([os.environ.get("GONGGONG_GIT", "git"), "-C", str(root), *args], timeout=120)


def source_snapshot(root):
    root = Path(root).resolve()
    tracked_modes = {}
    for entry in git_bytes(root, "ls-files", "--stage", "-z").split(b"\0"):
        if entry:
            metadata, name = entry.split(b"\t", 1)
            mode, _, stage = metadata.split()
            if stage != b"0":
                raise ValueError("Unmerged source input: " + os.fsdecode(name))
            tracked_modes[name] = mode
    untracked = git_bytes(root, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
    inputs = {}
    for raw in sorted(tracked_modes.keys() | set(untracked)):
        if not raw:
            continue
        name = os.fsdecode(raw)
        parts = Path(name).parts
        if parts[0] in EXCLUDED_ROOTS or any(part in {"__pycache__", ".godot", ".venv"} for part in parts):
            continue
        path = root / name
        if path.is_symlink():
            inputs[name] = {"sha256": hashlib.sha256(os.readlink(path).encode()).hexdigest(), "mode": "120000"}
        elif not path.exists():
            inputs[name] = {"absent": True}
        elif path.is_file():
            executable = path.stat().st_mode & 0o111
            if os.name == "nt":
                executable = tracked_modes.get(raw) == b"100755"
            inputs[name] = {
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "mode": "100755" if executable else "100644",
            }
    return {"source_digest": hashlib.sha256(canonical(inputs)).hexdigest(), "source_inputs": inputs}


def artifact_manifest(root, artifact, binding, project, options, before, native_app=None):
    after = source_snapshot(root)
    if after != before:
        raise ValueError("candidate_source_changed_during_build")
    value = {
        "schema_version": 1,
        "binding": binding,
        "source_head": git_bytes(root, "rev-parse", "HEAD").decode().strip(),
        **after,
        "build_options": options,
        "project_root": str(Path(project).resolve()) if project else "",
        "executable": str(Path(artifact).resolve()),
        "artifact_sha256": hashlib.sha256(Path(artifact).read_bytes()).hexdigest(),
    }
    package = installed_package(artifact)
    if package.is_file():
        value["tianshu_ui_sha256"] = hashlib.sha256(package.read_bytes()).hexdigest()
    verify_candidate_package(value)
    path = Path(str(artifact) + ".candidate.json")
    if native_app is not None:
        from editor_native_app import descriptor, manifest_path, validate_native_app

        value["native_app"] = descriptor(root, native_app)
        path = manifest_path(native_app)
        # Signing must have finished before hashing and publishing the sidecar.
        # Validation reads the sealed locator, but never changes the App.
        validate_native_app(root, value, path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(canonical(value))
    temporary.replace(path)
    return str(path)


def verify_source(root, manifest):
    value = json.loads(Path(manifest).read_text(encoding="utf-8"))
    verify_candidate_package(value)
    actual = source_snapshot(root)
    # A deletion remains the same build input after Git stops tracking its name.
    for name, item in value.get("source_inputs", {}).items():
        if item == {"absent": True} and name not in actual["source_inputs"] and not os.path.lexists(Path(root) / name):
            actual["source_inputs"][name] = item
    actual["source_digest"] = hashlib.sha256(canonical(actual["source_inputs"])).hexdigest()
    if actual["source_digest"] != value.get("source_digest") or actual["source_inputs"] != value.get("source_inputs"):
        raise ValueError("candidate_source_changed_since_build")
    return {"ok": True, "source_digest": actual["source_digest"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(verify_source(args.root, args.manifest)))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({"ok": False, "error": str(error)}))
        sys.exit(1)
