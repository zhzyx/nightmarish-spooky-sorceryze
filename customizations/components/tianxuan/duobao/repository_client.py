"""Authenticated ordinary-directory client for the server-owned native repository.

Configuration paths are relative to the explicit trusted configuration file.
Workspace markers never supply a network destination or credentials. No Git calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

MARKER = ".duobao-workspace.json"
MAX_OBJECT = 32 * 1024 * 1024
MAX_JSON = 32 * 1024 * 1024
EXCLUDED = {".git", ".duobao", ".godot", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}


def digest(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def safe_name(name):
    from native_workspace import portable

    portable(name)
    if name == MARKER or any(p in EXCLUDED for p in name.split("/")):
        raise ValueError("Repository object uses a local management path")
    return name


def ordinary(path):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError("Links and reparse points are not supported")
    if not stat.S_ISREG(info.st_mode) and not stat.S_ISDIR(info.st_mode):
        raise ValueError("Unsupported filesystem object")
    return info


def rooted(path):
    path = Path(os.path.abspath(path))
    for ancestor in (path, *path.parents):
        if ancestor.exists() or ancestor.is_symlink():
            ordinary(ancestor)
    return path


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    rooted(path.parent)
    fd, name = tempfile.mkstemp(prefix=".duobao-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Repository redirects are refused")


class Client:
    def __init__(self, config, token=None, authenticate=True):
        self.config_path = rooted(config)
        config = json.loads(self.config_path.read_text(encoding="utf-8-sig"))
        self.api = config["api"].rstrip("/")
        target = urllib.parse.urlsplit(self.api)
        if target.username or target.password or target.query or target.fragment:
            raise ValueError("Invalid repository service origin")
        if target.scheme != "https" and not (
            target.scheme == "http" and target.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError("Repository service requires HTTPS")
        self.repo = config.get("repository", "gonggong")
        if self.repo != "gonggong":
            raise ValueError("Unsupported repository")
        self.token = token or os.environ.get(config.get("token_env", "TIANXUAN_TOKEN"), "")
        if not self.token and config.get("credential_file"):
            credential = rooted(self.config_path.parent / config["credential_file"])
            self.token = json.loads(credential.read_text(encoding="utf-8-sig"))["token"]
        if authenticate and not self.token:
            raise ValueError("A current service-bound credential is required")
        self.binding = digest(canonical({"api": self.api, "repository": self.repo}))
        self.prefix = self.api + "/api/v1/native/repos/" + self.repo
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, path, value=None, raw=None):
        data = canonical(value) if value is not None else raw
        headers = {"Authorization": "Bearer " + self.token}
        if data is not None:
            headers["Content-Type"] = "application/json" if value is not None else "application/octet-stream"
        req = urllib.request.Request(self.prefix + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=180) as result:
                content = result.read((MAX_OBJECT if path.startswith("/objects/") else MAX_JSON) + 1)
                if len(content) > (MAX_OBJECT if path.startswith("/objects/") else MAX_JSON):
                    raise ValueError("Repository response exceeds its limit")
                if result.headers.get_content_type() == "application/octet-stream":
                    return content
                return json.loads(content)
        except urllib.error.HTTPError as error:
            # No credentials or transport URLs in diagnostics.
            raise ValueError(
                "Repository HTTP " + str(error.code) + ": " + error.read(2048).decode(errors="replace")
            ) from None

    def branch(self, name):
        return self.request("GET", "/branches/" + urllib.parse.quote(name, safe=""))

    def revision(self, revision):
        if revision is None:
            return {"objects": {}}
        value = self.request("GET", "/revisions/" + revision)
        if digest(canonical(value)) != revision:
            raise ValueError("Repository revision digest mismatch")
        return value


class Workspace:
    def __init__(self, client, root):
        self.client = client
        self.root = rooted(root)
        self.marker = self.root / MARKER
        ordinary(self.marker)
        self.state = json.loads(self.marker.read_text(encoding="utf-8"))
        if (
            self.state.get("schema") != 1
            or self.state.get("binding") != client.binding
            or self.state.get("repository") != client.repo
        ):
            raise ValueError("Workspace does not match the trusted service configuration")
        if self.state.get("tenant") != client.request("GET", "/identity")["tenant"]:
            raise ValueError("Workspace does not match the authenticated tenant")
        self.base = client.revision(self.state["revision"])

    def read(self, name):
        safe_name(name)
        path = rooted(self.root / name)
        info = ordinary(path)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_OBJECT:
            raise ValueError("Repository object exceeds its limit")
        with path.open("rb") as stream:
            data = stream.read(MAX_OBJECT + 1)
        if len(data) != info.st_size:
            raise ValueError("Workspace changed while reading")
        return data

    def scan(self):
        found = {}
        for directory, names, files in os.walk(self.root, followlinks=False):
            names[:] = [n for n in names if n not in EXCLUDED]
            for name in names:
                ordinary(Path(directory) / name)
            relative = Path(directory).relative_to(self.root).as_posix()
            if relative == "data-collection":
                names[:] = [n for n in names if n != "receipts"]
            for name in files:
                if Path(directory) == self.root and name in {MARKER, ".env"}:
                    continue
                path = (Path(directory) / name).relative_to(self.root).as_posix()
                safe_name(path)
                found[path] = digest(self.read(path))
                if len(found) > 100000:
                    raise ValueError("Workspace file count exceeds its limit")
        from native_workspace import tree_names

        tree_names(found)
        return found

    def status(self):
        current = self.scan()
        before = self.base["objects"]
        rows = [
            {
                "path": p,
                "status": "D" if p not in current else "A" if p not in before else "M",
                "digest": current.get(p),
            }
            for p in sorted(before.keys() | current.keys())
            if before.get(p) != current.get(p)
        ]
        return {
            "mode": "native-repository",
            "repository": self.client.repo,
            "branch": self.state["branch"],
            "base": self.state["revision"],
            "tree": digest(canonical(rows)),
            "files": rows,
        }

    def submit(self, key, message, paths=None):
        if self.state["branch"] == "main":
            raise ValueError("Create a task branch before submitting")
        pending = self.root / ".duobao" / ("pending-" + digest(key.encode()) + ".json")
        if pending.exists():
            saved = json.loads(pending.read_text(encoding="utf-8"))
            if (
                saved["message"] != message
                or saved["paths"] != paths
                or saved.get("binding") != self.client.binding
                or saved.get("tenant") != self.state["tenant"]
                or saved["payload"]["branch"] != self.state["branch"]
            ):
                raise ValueError("Request key is already bound to another submission")
            payload = saved["payload"]
        else:
            current = self.scan()
            manifest = dict(self.base["objects"]) if paths is not None else current
            for p in paths or []:
                safe_name(p)
                if p in current:
                    manifest[p] = current[p]
                else:
                    manifest.pop(p, None)
            if manifest == self.base["objects"]:
                return {"state": "unchanged", "revision": self.state["revision"]}
            identifiers = sorted(set(manifest.values()))
            missing = []
            for offset in range(0, len(identifiers), 512):
                missing.extend(
                    self.client.request("POST", "/objects/missing", {"digests": identifiers[offset : offset + 512]})[
                        "missing"
                    ]
                )
            source = {v: k for k, v in manifest.items()}
            for identity in missing:
                data = self.read(source[identity])
                if digest(data) != identity:
                    raise ValueError("Workspace changed; refresh before submitting")
                received = self.client.request("PUT", "/objects/" + identity, raw=data)
                if received["digest"] != identity:
                    raise ValueError("Object receipt mismatch")
            payload = {
                "request_key": key,
                "branch": self.state["branch"],
                "expected": self.state["revision"],
                "manifest": manifest,
                "message": message,
            }
            atomic_json(
                pending,
                {
                    "payload": payload,
                    "message": message,
                    "paths": paths,
                    "binding": self.client.binding,
                    "tenant": self.state["tenant"],
                },
            )
        receipt = self.client.request("POST", "/commits", payload)
        value = self.client.revision(receipt["revision"])
        if receipt["branch"] != payload["branch"] or value["objects"] != payload["manifest"]:
            raise ValueError("Submission receipt does not match the frozen request")
        if self.client.branch(payload["branch"])["revision"] != receipt["revision"]:
            raise ValueError("Historical receipt recovered; branch has advanced, keep the current workspace")
        self.state["revision"] = receipt["revision"]
        atomic_json(self.marker, self.state)
        # Keep the frozen request: replay after client/server restart is exact.
        return receipt


def initialize(client, root, branch, revision):
    root = rooted(root)
    if (root / MARKER).exists():
        raise ValueError("Workspace already has a native binding")
    client.revision(revision)
    atomic_json(
        root / MARKER,
        {
            "schema": 1,
            "binding": client.binding,
            "repository": client.repo,
            "branch": branch,
            "revision": revision,
            "tenant": client.request("GET", "/identity")["tenant"],
        },
    )


def main(arguments=None):
    p = argparse.ArgumentParser(description=__doc__)
    default_config = Path(os.environ.get("APPDATA", Path.home() / ".config")) / "GongGong" / "duobao.json"
    p.add_argument("--config", type=Path, default=default_config)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("route")
    head = sub.add_parser("head")
    head.add_argument("--branch", default="main")
    boot = sub.add_parser("bootstrap")
    boot.add_argument("--request-key", required=True)
    for name in ("bind", "status", "branch", "submit"):
        a = sub.add_parser(name)
        a.add_argument("--workspace", type=Path, required=True)
        if name in {"bind", "branch"}:
            a.add_argument("--branch", required=True)
        if name == "bind":
            a.add_argument("--revision")
        if name in {"branch", "submit"}:
            a.add_argument("--request-key", required=True)
        if name == "submit":
            a.add_argument("--message", required=True)
            a.add_argument("--path", action="append")
    cand = sub.add_parser("candidate")
    for flag in ("source", "revision", "issue-id", "request-key"):
        cand.add_argument("--" + flag, required=True)
    cand.add_argument("--expected")
    cand.add_argument("--target", default="main")
    for name in ("candidate-status", "check", "review", "deliver"):
        a = sub.add_parser(name)
        a.add_argument("--candidate", required=True)
        if name != "candidate-status":
            a.add_argument("--request-key", required=True)
        if name == "review":
            a.add_argument("--note", required=True)
        if name == "deliver":
            a.add_argument("--review", required=True)
    args = p.parse_args(arguments)
    try:
        c = Client(args.config)
        command = args.command
        if command == "route":
            result = {"mode": "native-repository", "api": c.api, "repository": c.repo}
        elif command == "head":
            result = c.branch(args.branch)
        elif command == "bootstrap":
            result = c.request("POST", "/bootstrap", {"request_key": args.request_key})
        elif command == "bind":
            revision = args.revision or c.branch(args.branch)["revision"]
            initialize(c, args.workspace, args.branch, revision)
            result = {"state": "bound", "revision": revision}
        elif command == "status":
            result = Workspace(c, args.workspace).status()
        elif command == "branch":
            w = Workspace(c, args.workspace)
            result = c.request(
                "POST",
                "/branches",
                {"branch": args.branch, "revision": w.state["revision"], "request_key": args.request_key},
            )
            w.state["branch"] = args.branch
            atomic_json(w.marker, w.state)
        elif command == "submit":
            result = Workspace(c, args.workspace).submit(args.request_key, args.message, args.path)
        elif command == "candidate":
            result = c.request(
                "POST",
                "/candidates",
                {
                    "source": args.source,
                    "target": args.target,
                    "revision": args.revision,
                    "expected": args.expected,
                    "issue_id": args.issue_id,
                    "request_key": args.request_key,
                },
            )
        else:
            route = "/candidates/" + urllib.parse.quote(args.candidate, safe="")
            if command == "candidate-status":
                result = c.request("GET", route)
            else:
                body = {"request_key": args.request_key}
                suffix = {"check": "checks", "review": "reviews", "deliver": "merge"}[command]
                if command == "review":
                    body["note"] = args.note
                if command == "deliver":
                    body["review"] = args.review
                result = c.request("POST", route + "/" + suffix, body)
        print(json.dumps({"ok": True, "data": result}, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, urllib.error.URLError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
