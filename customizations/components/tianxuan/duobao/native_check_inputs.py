"""Immutable, bounded check-only views from a frozen trusted evidence binding.

No producer manifest or candidate identity is exposed to the check. This is a
filesystem adapter for trusted commands, not a security sandbox.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from native_store import NativeStoreError, _digest, _json
from native_workspace import Limits, NativeWorkspace, absolute, checked_stat, portable, tree_names

CONTRACT = "native-check/2:cwd=output:scoped-input"


@dataclass(frozen=True)
class CheckInputView:
    # Immutable serialized facts: caller mutation cannot change the selected view.
    descriptor: str
    limits: Limits

    @classmethod
    def from_binding(cls, store, tenant, binding, limits=None):
        limits = limits or Limits()
        encoded = _json(binding)
        if len(encoded.encode()) > limits.request_bytes:
            raise NativeStoreError("Check binding metadata exceeds limit")
        frozen = json.loads(encoded)
        if _digest(_json(frozen["binding"]).encode()) != frozen["key"]:
            raise NativeStoreError("Check binding integrity failure")
        inputs = frozen["binding"]["inputs"]
        workspace = NativeWorkspace(store, limits)
        objects, pins = {}, {}
        for module, selection in inputs.items():
            portable(module)
            objects[module] = dict(selection["objects"])
            for dep, revision in selection["dependencies"].items():
                if dep in pins and pins[dep] != revision:
                    raise NativeStoreError("Incompatible exact dependency revisions")
                pins[dep] = revision
        if pins:
            revisions, states = workspace.sources(tenant, pins)
            for module, state in states.items():
                if module in inputs:
                    selection = inputs[module]
                    if (
                        selection["dependencies"] != state["dependencies"]
                        or selection.get("revision", revisions[module]) != revisions[module]
                        or any(state["objects"].get(n) != d for n, d in selection["objects"].items())
                    ):
                        raise NativeStoreError("Dependency conflicts with selected input")
                objects[module] = dict(state["objects"])
        tree_names(objects)
        if len(objects) > limits.modules:
            raise NativeStoreError("Module closure exceeds limit")
        entries = set(objects)
        count = total = 0
        for module, names in objects.items():
            tree_names(names)
            for name, digest in names.items():
                if digest is None:
                    continue
                count += 1
                total += workspace._size(tenant, digest)
                parts = (module + "/" + name).split("/")
                entries.update("/".join(parts[:end]) for end in range(1, len(parts) + 1))
                if count > limits.files or total > limits.total_bytes or len(entries) > limits.entries:
                    raise NativeStoreError("Check view resource limit exceeded")
        if len(entries) > limits.entries:
            raise NativeStoreError("Check view entry limit exceeded")
        return cls(_json(objects), limits)

    def materialize(self, store, tenant, destination):
        destination = absolute(destination, missing=True)
        if os.path.lexists(destination):
            raise NativeStoreError("Destination already exists")
        stage = Path(tempfile.mkdtemp(prefix=".duobao-check-stage-", dir=destination.parent))
        try:
            for module, names in json.loads(self.descriptor).items():
                (stage / module).mkdir()
                for name, digest in names.items():
                    if digest is None:
                        continue
                    with store._connection() as db:
                        row = db.execute(
                            "SELECT content FROM native_blobs WHERE tenant=? AND digest=? AND length(content)<=?",
                            (tenant, digest, self.limits.file_bytes),
                        ).fetchone()
                    if row is None or _digest(bytes(row[0])) != digest:
                        raise NativeStoreError("Check input integrity failure")
                    target = stage / module / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open("xb") as stream:
                        stream.write(bytes(row[0]))
            if os.path.lexists(destination):
                raise NativeStoreError("Destination already exists")
            stage.rename(destination)
        except BaseException:
            shutil.rmtree(stage)
            raise

    def snapshot(self, root):
        root = absolute(root)
        result = {}
        total = files = 0
        stack = [root]
        while stack:
            path = stack.pop()
            info = checked_stat(path)
            name = path.relative_to(root).as_posix()
            if name != ".":
                portable(name)
            if len(result) > self.limits.entries:
                raise NativeStoreError("Input entry limit exceeded")
            digest = None
            if stat.S_ISDIR(info.st_mode):
                with os.scandir(path) as entries:
                    for entry in entries:
                        stack.append(Path(entry.path))
                        if len(stack) + len(result) > self.limits.entries + 1:
                            raise NativeStoreError("Input entry limit exceeded")
            else:
                files += 1
                total += info.st_size
                if (
                    files > self.limits.files
                    or info.st_size > self.limits.file_bytes
                    or total > self.limits.total_bytes
                ):
                    raise NativeStoreError("Input size limit exceeded")
                with path.open("rb") as stream:
                    data = stream.read(self.limits.file_bytes + 1)
                if len(data) != info.st_size:
                    raise NativeStoreError("Input changed during snapshot")
                digest = _digest(data)
            result[name] = (stat.S_IFMT(info.st_mode), info.st_mtime_ns, info.st_ctime_ns, digest)
        return result
