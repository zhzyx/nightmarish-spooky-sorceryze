"""Selected-object commits for the module containing an open materialized Godot project."""

import base64
import difflib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import quote

# The installed workspace adapter owns the portable path and symlink rules.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "duobao"))
from native_store import _digest, _json  # noqa: E402
from native_workspace import Limits, absolute, checked_stat, portable, tree_names  # noqa: E402


class NativeProject:
    def __init__(self, project, marker, api, request, read_object):
        self.project = absolute(project)
        self.root = absolute(marker).parent
        if not (self.project / "project.godot").is_file():
            raise ValueError("请选择已物化的 Godot 项目")
        if marker.stat().st_size > Limits().request_bytes:
            raise ValueError("物化来源超限")
        manifest = json.loads(marker.read_bytes())
        if not isinstance(manifest, dict):
            raise ValueError("无效的物化来源清单")
        digest = manifest.pop("source_digest", None)
        if (
            digest != _digest(_json(manifest).encode())
            or manifest.get("schema") != 1
            or manifest.get("state") != "candidate"
            or not isinstance(manifest.get("modules"), dict)
        ):
            raise ValueError("物化来源无效，请重新物化")
        relative = self.project.relative_to(self.root)
        if not relative.parts:
            raise ValueError("请打开物化模块内的 Godot 工程")
        self.module = relative.parts[0]
        self.directory = self.root / self.module
        self.prefix = "/".join(relative.parts[1:])
        self.prefix = self.prefix + "/" if self.prefix else ""
        self.initial = manifest["modules"].get(self.module)
        if not isinstance(self.initial, str) or not re.fullmatch(r"[0-9a-f]{64}", self.initial):
            raise ValueError("当前工程没有确切物化修订")
        self.request = request
        self.read_object = read_object
        self.endpoint = "modules/" + quote(self.module, safe="") + "/"
        self.tenant = manifest["tenant"]
        head = request("GET", self.endpoint + "head")
        if head.get("tenant") != self.tenant:
            raise ValueError("登录租户与物化来源不匹配")
        binding = _digest(_json([api, self.tenant, self.module, digest]).encode())
        self.cursor = self.project / ".godot" / "editor" / ("duobao-g11-" + binding + ".json")
        self.base = self.current_base()
        self.state = self.revision(self.base)

    def current_base(self):
        if not os.path.lexists(self.cursor):
            return self.initial
        absolute(self.cursor)
        if self.cursor.stat().st_size > 256:
            raise ValueError("本地修订记录无效")
        cursor = json.loads(self.cursor.read_bytes())
        if not isinstance(cursor, dict) or not isinstance(cursor.get("revision"), str):
            raise ValueError("本地修订记录无效")
        return cursor["revision"]

    def revision(self, revision):
        if not re.fullmatch(r"[0-9a-f]{64}", revision):
            raise ValueError("物化修订无效")
        state = self.request("GET", self.endpoint + "revisions/" + revision)
        if state.get("module") != self.module or _digest(_json(state).encode()) != revision:
            raise ValueError("多宝修订摘要不匹配")
        tree_names(state["objects"])
        return state

    def file(self, name):
        portable(name)
        if not name.startswith(self.prefix) or name.removeprefix(self.prefix).split("/")[0] == ".godot":
            raise ValueError("路径超出当前物化项目")
        path = self.directory / name
        # A deletion may also remove an ancestor directory.
        for ancestor in (path, *path.parents):
            if os.path.lexists(ancestor):
                absolute(ancestor)
                break
        if not path.exists() or path.is_dir():
            return None
        info = checked_stat(path)
        if info.st_size > Limits().file_bytes:
            raise ValueError("物化文件超出读取上限")
        with path.open("rb") as stream:
            value = stream.read(info.st_size + 1)
        if len(value) != info.st_size:
            raise ValueError("文件在读取期间改变")
        return value

    def diff(self) -> dict[str, Any]:
        baseline = {
            name: digest
            for name, digest in self.state["objects"].items()
            if name.startswith(self.prefix) and name.removeprefix(self.prefix).split("/")[0] != ".godot"
        }
        pending = [self.project]
        current: dict[str, str] = {}
        entries = size = 0
        limits = Limits()
        while pending:
            for entry in os.scandir(pending.pop()):
                path = Path(entry.path)
                if path == self.project / ".godot":
                    continue
                name = portable(path.relative_to(self.directory).as_posix())
                info = checked_stat(path)
                entries += 1
                if entries > limits.entries:
                    raise ValueError("物化目录条目超限")
                if stat.S_ISDIR(info.st_mode):
                    pending.append(path)
                else:
                    size += info.st_size
                    if len(current) >= limits.files or size > limits.total_bytes:
                        raise ValueError("物化目录内容超限")
                    value = self.file(name)
                    if value is None:
                        raise ValueError("工作区已变化，请刷新差异")
                    current[name] = _digest(value)
        tree_names(current)
        rows = []
        for name in sorted(baseline.keys() | current.keys()):
            if baseline.get(name) != current.get(name):
                status = "D" if name not in current else "M" if name in baseline else "A"
                rows.append({"path": name, "status": status, "digest": current.get(name, "deleted")})
        return {
            "mode": "native",
            "branch": self.module,
            "base": self.base,
            "tree": _digest(_json(rows).encode()),
            "files": rows,
        }

    def preview(self, body) -> dict[str, Any]:
        if body["base"] != self.base:
            raise ValueError("项目修订已变化，请刷新")
        name = body["path"]
        current = self.file(name)
        if (_digest(current) if current is not None else "deleted") != body["digest"]:
            raise ValueError("文件已变化，请刷新差异")
        previous = b""
        if name in self.state["objects"]:
            path = self.endpoint + "revisions/" + self.base + "/objects/" + quote(name, safe="/")
            previous = self.read_object(path, Limits().file_bytes)
            if _digest(previous) != self.state["objects"][name]:
                raise ValueError("多宝原始内容摘要不符")
        after = current or b""
        try:
            if b"\0" in previous or b"\0" in after:
                return {"diff": f"二进制文件 · {len(previous)} → {len(after)} 字节"}
            before_lines = previous[:65536].decode().splitlines()
            after_lines = after[:65536].decode().splitlines()
        except UnicodeDecodeError:
            return {"diff": f"二进制文件 · {len(previous)} → {len(after)} 字节"}
        delta = difflib.unified_diff(before_lines, after_lines, fromfile=name, tofile=name, lineterm="")
        text = "\n".join(delta)
        truncated = max(len(previous), len(after), len(text)) > 65536
        return {"diff": text[:65536] + ("\n…（预览截断）" if truncated else "")}

    def submit(self, body) -> dict[str, Any]:
        paths = sorted(set(body["paths"]))
        if (
            not paths
            or len(paths) > 1024
            or not body["message"].strip()
            or body["branch"] != self.module
            or set(paths) != body["digests"].keys()
        ):
            raise ValueError("请选择当前模块的改动")
        base = body["base"]
        source = self.state if base == self.base else self.revision(base)
        expected = dict(source["objects"])
        for name in paths:
            portable(name)
            if not name.startswith(self.prefix) or name.removeprefix(self.prefix).split("/")[0] == ".godot":
                raise ValueError("所选路径超出项目")
            digest = body["digests"][name]
            if digest == "deleted" and name in expected:
                del expected[name]
            elif isinstance(digest, str) and re.fullmatch(r"[a-f0-9]{64}", digest) and expected.get(name) != digest:
                expected[name] = digest
            else:
                raise ValueError("所选文件与显示差异不符")
        key = "g11-" + _digest(_json([self.module, base, body["digests"], body["message"]]).encode())
        observed = self.request("GET", "batches/" + key)
        if observed.get("tenant") != self.tenant or observed.get("request_key") != key or "receipt" not in observed:
            raise ValueError("无法确认原生批次状态")
        result = observed["receipt"]
        if result is None:
            if base != self.base:
                raise ValueError("工作区修订已变化，请刷新")
            edits = {}
            total = 0
            for name in paths:
                value = self.file(name)
                if (_digest(value) if value is not None else "deleted") != body["digests"][name]:
                    raise ValueError("所选文件已变化，请刷新确认")
                if value is not None:
                    total += len(value)
                    if len(value) > 1024 * 1024 or total > 4 * 1024 * 1024:
                        raise ValueError("原生批次单文件上限 1 MiB，总内容上限 4 MiB")
                edits[name] = base64.b64encode(value).decode() if value is not None else None
            result = self.request(
                "POST",
                "batches",
                {"request_key": key, "changes": [{"module": self.module, "base": base, "reads": None, "edits": edits}]},
            )
        if result.get("state") != "received" or set(result.get("revisions", {})) != {self.module}:
            raise ValueError("原生批次回执不匹配")
        revision = result["revisions"][self.module]
        saved = self.revision(revision)
        if saved["parent"] != base or saved["objects"] != expected or saved["dependencies"] != source["dependencies"]:
            raise ValueError("原生批次的已接收修订与所选内容不符")
        self.advance(base, revision)
        return {"branch": self.module, "sha": revision, "request_key": key}

    def advance(self, base, revision):
        for directory in (self.cursor.parent.parent, self.cursor.parent):
            absolute(directory, missing=True)
            directory.mkdir(exist_ok=True)
            absolute(directory)
        with tempfile.NamedTemporaryFile(dir=self.cursor.parent, delete=False) as pending:
            pending.write(_json({"revision": revision}).encode())
            stage = Path(pending.name)
        try:
            lock_path = self.cursor.with_suffix(".lock")
            with lock_path.open("xb") as lock:
                try:
                    current = self.current_base()
                    if current == revision:
                        return
                    if current != base:
                        raise ValueError("本地修订已前移，请核对已接收的批次")
                    os.replace(stage, self.cursor)
                finally:
                    lock.close()
                    lock_path.unlink()
        finally:
            stage.unlink(missing_ok=True)
