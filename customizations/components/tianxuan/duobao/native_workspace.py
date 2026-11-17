"""Bounded filesystem adapter for NativeStore; trusted, single-writer local host.

The caller supplies authenticated tenant and exact sources on every operation.
Workspace metadata never grants authority. Received changes are not releases.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
import shutil
import stat
import tempfile
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from native_store import NativeStore, NativeStoreError, _digest, _json

MANIFEST = ".duobao-source.json"


@dataclass(frozen=True)
class Limits:
    modules: int = 128
    files: int = 10000
    entries: int = 20000
    file_bytes: int = 8 * 1024 * 1024
    total_bytes: int = 64 * 1024 * 1024
    request_bytes: int = 4 * 1024 * 1024
    page_items: int = 100
    page_bytes: int = 256 * 1024

    def __post_init__(self):
        for value in vars(self).values():
            if type(value) is not int or value < 1:
                raise NativeStoreError("Limits must be positive integers")
        # Host may lower budgets; cannot silently turn bounded interfaces unbounded.
        caps = (128, 10000, 20000, 8 * 1024 * 1024, 64 * 1024 * 1024, 4 * 1024 * 1024, 100, 256 * 1024)
        if any(v > c for v, c in zip(vars(self).values(), caps)):
            raise NativeStoreError("Limit exceeds supported hard ceiling")


def portable(name):
    if not isinstance(name, str) or not name or len(name) > 1024:
        raise NativeStoreError("Invalid portable path")
    for part in name.split("/"):
        stem = part.split(".")[0].rstrip(" ").upper()
        if (
            not part
            or part in {".", ".."}
            or part.endswith((" ", "."))
            or len(part) > 200
            or unicodedata.normalize("NFC", part) != part
            or any(ord(c) < 32 or c in '<>:"\\|?*~' for c in part)
            or stem in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
            or re.fullmatch(r"(?:COM|LPT)[0-9¹²³]", stem)
            or part.casefold() == ".git"
        ):
            raise NativeStoreError("Unsafe or aliased portable path: " + name)
    return name


def tree_names(names):
    seen = {}
    files = set(names)
    for name in files:
        portable(name)
        parts = name.split("/")
        for end in range(1, len(parts) + 1):
            prefix = "/".join(parts[:end])
            key = prefix.casefold()
            if key in seen and seen[key] != prefix:
                raise NativeStoreError("Case alias collision")
            seen[key] = prefix
            if end < len(parts) and prefix in files:
                raise NativeStoreError("File/directory collision")


def checked_stat(path):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise NativeStoreError("Links and reparse points are forbidden")
    if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
        raise NativeStoreError("Unknown filesystem entry type")
    return info


def absolute(path, *, missing=False):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise NativeStoreError("Explicit absolute path required")
    if os.name == "nt" and (len(path.drive) != 2 or path.drive[1] != ":"):
        raise NativeStoreError("Local drive path required; device and UNC namespaces are unsupported")
    # Check every ancestor without resolve(), which would hide links.
    for item in reversed((path, *path.parents)):
        if item == Path(item.anchor):
            checked_stat(item)
            continue
        portable(item.name)
        if missing and item == path and not os.path.lexists(item):
            continue
        checked_stat(item)
    return path


def _stage_identity(path):
    info = checked_stat(path)
    return info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)


def _capture_stage_owner(stage):
    # Capture immediately after creation, before filling or handing off the tree.
    absolute(stage)
    return tuple((path, _stage_identity(path)) for path in (stage, *stage.parents))


def _verify_stage_owner(stage, owner):
    absolute(stage)
    if tuple(path for path, _ in owner) != (stage, *stage.parents) or any(
        _stage_identity(path) != identity for path, identity in owner
    ):
        raise NativeStoreError("Prepared stage identity or ancestry changed")


def _rename_prepared(stage, destination, limits, owner):
    """Publish an owned bounded tree; tolerate brief Windows child-handle holds.

    This remains a trusted single-writer adapter. Windows rename never replaces
    an existing destination. Each retry revalidates the original owned tree and
    its ancestry; permanent denials retain the first OS exception.
    """
    _verify_stage_owner(stage, owner)
    if os.name != "nt":
        stage.rename(destination)
        return

    def metadata(info):
        # Reading can update access time on Windows; it is not content drift.
        return info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns

    def fingerprint():
        result = {}
        pending = [stage]
        total = files = 0
        while pending:
            path = pending.pop()
            info = checked_stat(path)
            if len(result) >= limits.entries + 1:
                raise NativeStoreError("Prepared tree entry limit exceeded")
            digest = None
            if stat.S_ISDIR(info.st_mode):
                with os.scandir(path) as entries:
                    for entry in entries:
                        pending.append(Path(entry.path))
                        if len(pending) + len(result) > limits.entries + 1:
                            raise NativeStoreError("Prepared tree entry limit exceeded")
            else:
                files += 1
                total += info.st_size
                # Workspace adds one bounded manifest to the source budgets.
                if (
                    files > limits.files + 1
                    or info.st_size > max(limits.file_bytes, limits.request_bytes)
                    or total > limits.total_bytes + limits.request_bytes
                ):
                    raise NativeStoreError("Prepared tree size limit exceeded")
                with path.open("rb") as stream:
                    data = stream.read(info.st_size + 1)
                if len(data) != info.st_size or metadata(checked_stat(path)) != metadata(info):
                    raise NativeStoreError("Prepared tree changed")
                digest = hashlib.sha256(data).hexdigest()
            result[path.relative_to(stage).as_posix()] = (*metadata(info), digest)
        return result

    prepared = fingerprint()
    _verify_stage_owner(stage, owner)
    absolute(destination, missing=True)
    if os.path.lexists(destination):
        raise NativeStoreError("Destination already exists")
    try:
        stage.rename(destination)
        return
    except OSError as original:
        if getattr(original, "winerror", None) not in (5, 32):
            raise
        deadline = time.monotonic() + 0.25
        for delay in (0.02, 0.04, 0.08):
            if time.monotonic() + delay >= deadline:
                break
            time.sleep(delay)
            try:
                _verify_stage_owner(stage, owner)
                absolute(destination, missing=True)
                if os.path.lexists(destination) or fingerprint() != prepared:
                    break
                _verify_stage_owner(stage, owner)
                if time.monotonic() >= deadline:
                    break
                stage.rename(destination)
                return
            except OSError as retry_error:
                if getattr(retry_error, "winerror", None) not in (5, 32):
                    break
            except NativeStoreError:
                break
        raise original


def _cleanup_owned_stage(stage, owner, error):
    # A failed retry may have observed replacement or a still-open child. Never
    # remove a replacement, traverse changed ancestry, or mask the first error.
    try:
        _verify_stage_owner(stage, owner)
        shutil.rmtree(stage)
    except (OSError, NativeStoreError) as cleanup_error:
        error.add_note("Prepared stage cleanup incomplete: " + str(cleanup_error))


class NativeWorkspace:
    def __init__(self, store: NativeStore, limits: Limits | None = None):
        self.store = store
        self.limits = limits or Limits()

    def _revision(self, tenant, module, revision):
        # Bound metadata before the underlying API decodes JSON.
        with self.store._connection() as db:
            row = db.execute(
                "SELECT length(CAST(payload AS BLOB)) FROM native_revisions WHERE tenant=? AND module=? AND id=?",
                (tenant, module, revision),
            ).fetchone()
        if row and row[0] > self.limits.request_bytes:
            raise NativeStoreError("Revision metadata exceeds limit")
        state = self.store.revision(tenant, module, revision)
        if len(state["objects"]) > self.limits.files:
            raise NativeStoreError("Object count exceeds limit")
        tree_names(state["objects"])
        return state

    def _size(self, tenant, digest):
        with self.store._connection() as db:
            row = db.execute(
                "SELECT length(content) FROM native_blobs WHERE tenant=? AND digest=?", (tenant, digest)
            ).fetchone()
        if row is None or row[0] > self.limits.file_bytes:
            raise NativeStoreError("Missing or oversized object")
        return row[0]

    def sources(self, tenant, selected):
        if not isinstance(selected, dict) or not selected or len(selected) > self.limits.modules:
            raise NativeStoreError("Expected bounded exact module selection")
        pending = list(selected.items())
        states, revisions = {}, {}
        count = size = 0
        entries = {MANIFEST}
        while pending:
            module, revision = pending.pop()
            portable(module)
            if module in revisions:
                if revisions[module] != revision:
                    raise NativeStoreError("Incompatible exact dependency revisions")
                continue
            if len(states) >= self.limits.modules:
                raise NativeStoreError("Module closure exceeds limit")
            state = self._revision(tenant, module, revision)
            states[module], revisions[module] = state, revision
            count += len(state["objects"])
            if count > self.limits.files:
                raise NativeStoreError("File count exceeds limit")
            for digest in state["objects"].values():
                size += self._size(tenant, digest)
                if size > self.limits.total_bytes:
                    raise NativeStoreError("Source bytes exceed limit")
            entries.add(module)
            for name in state["objects"]:
                parts = (module + "/" + name).split("/")
                entries.update("/".join(parts[:end]) for end in range(1, len(parts) + 1))
                if len(entries) > self.limits.entries:
                    raise NativeStoreError("Source tree entry count exceeds limit")
                # Verify even the old baseline when collecting: a mutable manifest
                # or damaged blob is not a substitute for authoritative bytes.
                self.store.read(tenant, module, revision, name)
            if len(state["dependencies"]) > self.limits.modules:
                raise NativeStoreError("Dependency count exceeds limit")
            pending.extend(state["dependencies"].items())
        tree_names(revisions)
        if len(entries) > self.limits.entries:
            raise NativeStoreError("Source tree entry count exceeds limit")
        if MANIFEST.casefold() in {m.casefold() for m in revisions}:
            raise NativeStoreError("Reserved module name")
        return revisions, states

    def materialize(self, tenant, selected, destination):
        destination = absolute(destination, missing=True)
        if os.path.lexists(destination):
            raise NativeStoreError("Destination already exists")
        revisions, states = self.sources(tenant, selected)
        manifest = {"schema": 1, "tenant": tenant, "state": "candidate", "modules": revisions}
        manifest["source_digest"] = _digest(_json(manifest).encode())
        stage = Path(tempfile.mkdtemp(prefix=".duobao-stage-", dir=destination.parent))
        owner = _capture_stage_owner(stage)
        try:
            for module, state in states.items():
                (stage / module).mkdir()
                for name in sorted(state["objects"]):
                    target = stage / module / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    data = self.store.read(tenant, module, revisions[module], name)
                    with target.open("xb") as stream:
                        stream.write(data)
            (stage / MANIFEST).write_text(_json(manifest), encoding="utf-8")
            if os.path.lexists(destination):
                raise NativeStoreError("Destination already exists")
            _rename_prepared(stage, destination, self.limits, owner)
        except BaseException as error:
            _cleanup_owned_stage(stage, owner, error)
            raise
        return manifest

    def collect(self, tenant, selected, workspace):
        workspace = absolute(workspace)
        revisions, states = self.sources(tenant, selected)
        found = {module: {} for module in revisions}
        entries = count = total = 0
        stack = [(workspace, "")]
        all_names = {}
        while stack:
            directory, prefix = stack.pop()
            with os.scandir(directory) as iterator:
                for entry in iterator:
                    entries += 1
                    if entries > self.limits.entries:
                        raise NativeStoreError("Scan entry count exceeds limit")
                    name = prefix + entry.name
                    portable(name)
                    key = name.casefold()
                    if key in all_names and all_names[key] != name:
                        raise NativeStoreError("Case alias collision")
                    all_names[key] = name
                    info = checked_stat(Path(entry.path))
                    if name == MANIFEST:
                        if not stat.S_ISREG(info.st_mode) or info.st_size > self.limits.request_bytes:
                            raise NativeStoreError("Invalid informational manifest")
                        continue  # Never read authority from mutable workspace metadata.
                    module, _, obj = name.partition("/")
                    if module not in revisions:
                        raise NativeStoreError("Unknown module in workspace")
                    if stat.S_ISDIR(info.st_mode):
                        stack.append((Path(entry.path), name + "/"))
                        continue
                    if not obj:
                        raise NativeStoreError("Expected module directory")
                    count += 1
                    total += info.st_size
                    if (
                        count > self.limits.files
                        or info.st_size > self.limits.file_bytes
                        or total > self.limits.total_bytes
                    ):
                        raise NativeStoreError("Workspace size exceeds limit")
                    with open(entry.path, "rb") as stream:
                        data = stream.read(self.limits.file_bytes + 1)
                    if len(data) != info.st_size:
                        raise NativeStoreError("Workspace changed while scanning")
                    found[module][obj] = data
        changes = []
        for module, state in states.items():
            edits = {name: data for name, data in found[module].items() if _digest(data) != state["objects"].get(name)}
            edits.update({name: None for name in state["objects"] if name not in found[module]})
            if edits:
                changes.append({
                    "module": module,
                    "base": revisions[module],
                    "reads": None,
                    "edits": edits,
                    "dependencies": dict(state["dependencies"]),
                })
        return changes

    def submit(self, tenant, actor, request_key, selected, workspace):
        changes = self.collect(tenant, selected, workspace)
        if not changes:
            return {"state": "unchanged", "revisions": {}}
        return self.store.submit(tenant, actor, request_key, changes)

    def delta(self, tenant, module, before, after, *, cursor=None):
        left = self._revision(tenant, module, before)
        right = self._revision(tenant, module, after)
        names = sorted(
            name
            for name in left["objects"].keys() | right["objects"].keys()
            if left["objects"].get(name) != right["objects"].get(name)
        )
        if len(names) > self.limits.files:
            raise NativeStoreError("Delta count exceeds limit")
        binding = _digest(_json([tenant, module, before, after, vars(self.limits)]).encode())
        offset = 0
        if cursor is not None:
            if not isinstance(cursor, str) or len(cursor) > 256:
                raise NativeStoreError("Invalid cursor")
            parts = cursor.split(":")
            if len(parts) != 2 or parts[0] != binding or not parts[1].isdigit():
                raise NativeStoreError("Cursor does not match exact inputs")
            offset = int(parts[1])
            if not 0 <= offset <= len(names):
                raise NativeStoreError("Cursor out of range")
        items, used = [], 0
        for name in names[offset : offset + self.limits.page_items]:
            old, new = left["objects"].get(name), right["objects"].get(name)
            item = {
                "name": name,
                "kind": "added" if old is None else "deleted" if new is None else "modified",
                "before": old,
                "after": new,
            }
            if new is not None:
                size = self._size(tenant, new)
                item.update(size=size, content_omitted=True)
                # Reserve JSON escaping/base64 overhead before fetching content.
                if size * 6 + len(_json(item).encode()) + 128 <= self.limits.page_bytes - used:
                    data = self.store.read(tenant, module, after, name)
                    try:
                        content = data.decode("utf-8")
                        encoding = "utf-8"
                        if "\x00" in content:
                            raise UnicodeError()
                    except UnicodeError:
                        content, encoding = base64.b64encode(data).decode("ascii"), "base64"
                    item.update(content=content, encoding=encoding, content_omitted=False)
            length = len(_json(item).encode())
            if used + length > self.limits.page_bytes:
                if not items:
                    raise NativeStoreError("Page budget too small for object summary")
                break
            used += length
            items.append(item)
        end = offset + len(items)
        return {
            "tenant": tenant,
            "module": module,
            "before": before,
            "after": after,
            "total_changes": len(names),
            "offset": offset,
            "items": items,
            "item_bytes": used,
            "truncated": end < len(names) or any(i.get("content_omitted") for i in items),
            "next_cursor": binding + ":" + str(end) if end < len(names) else None,
            "dependencies_before": left["dependencies"],
            "dependencies_after": right["dependencies"],
        }
