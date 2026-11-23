"""Opt-in dual submission adapter. Git is a source here, never the native store.

Read only immutable Git objects, not working-directory bytes. Retain both receipts
on failure and replay the same native request after recovery. No main publication.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from repository_client import MAX_OBJECT, Client, atomic_json, canonical, digest


def configuration():
    configured = os.environ.get("GONGGONG_DUOBAO_CONFIG")
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            raise ValueError("GONGGONG_DUOBAO_CONFIG must be an absolute trusted host path")
        return path
    return Path(os.environ.get("APPDATA", Path.home() / ".config")) / "GongGong" / "duobao.json"


def run_git(root, *args):
    result = subprocess.run(
        [os.environ.get("GIT_EXECUTABLE") or "git", "-C", str(root), *args], capture_output=True, check=True
    )
    return result.stdout


def snapshot(root, commit):
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit):
        raise ValueError("An exact Git commit is required")
    tree = run_git(root, "rev-parse", commit + "^{tree}").decode().strip()
    entries = []
    for record in run_git(root, "ls-tree", "-r", "-z", commit).split(b"\0"):
        if not record:
            continue
        metadata, name = record.split(b"\t", 1)
        mode, kind, identity = metadata.decode("ascii").split()
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise ValueError("Source contains a link or submodule; explicit migration is required")
        entries.append((name.decode("utf-8"), identity, mode))
    return tree, entries


class Objects:
    def __init__(self, root):
        self.process = subprocess.Popen(
            [os.environ.get("GIT_EXECUTABLE") or "git", "-C", str(root), "cat-file", "--batch"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

    def read(self, identity):
        self.process.stdin.write(identity.encode() + b"\n")
        self.process.stdin.flush()
        header = self.process.stdout.readline().decode().split()
        if len(header) != 3 or header[:2] != [identity, "blob"]:
            raise ValueError("Source object is unavailable")
        size = int(header[2])
        if size > MAX_OBJECT:
            raise ValueError("Source object exceeds native upload limit")
        data = self.process.stdout.read(size)
        if len(data) != size or self.process.stdout.read(1) != b"\n":
            raise ValueError("Source object was truncated")
        actual = hashlib.new(
            "sha1" if len(identity) == 40 else "sha256", b"blob " + str(size).encode() + b"\0" + data
        ).hexdigest()
        if actual != identity:
            raise ValueError("Source object hash mismatch")
        return data

    def close(self):
        self.process.stdin.close()
        self.process.stdout.close()
        self.process.wait(timeout=20)


def mirror(root, commit, repository, *, config=None, client=None):
    root = Path(root).resolve()
    config = Path(config or configuration())
    settings = json.loads(config.read_text(encoding="utf-8-sig"))
    if settings.get("source_repository") != repository:
        raise ValueError("Dual submission source repository mismatch")
    client = client or Client(config)
    tree, entries = snapshot(root, commit)
    common = Path(run_git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").decode().strip())
    receipt_path = common / "gonggong-duobao" / (commit + ".json")
    pending = {
        "state": "pending",
        "git_repository": repository,
        "git_commit": commit,
        "git_tree": tree,
        "native_repository": client.repo,
        "binding": client.binding,
    }
    previous = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else None
    if previous is not None and any(previous.get(k) != v for k, v in pending.items() if k != "state"):
        raise ValueError("Existing native receipt is bound to another target or source")
    if previous is None:
        atomic_json(receipt_path, {**pending, "tenant": None})
    pending["tenant"] = client.request("GET", "/identity")["tenant"]
    if previous is not None and previous.get("tenant") is not None and previous["tenant"] != pending["tenant"]:
        raise ValueError("Existing native receipt is bound to another tenant")
    if previous is None or previous.get("state") != "received":
        atomic_json(receipt_path, pending)
    source = Objects(root)
    try:
        manifest, by_digest, blob_digests = {}, {}, {}
        for name, identity, _mode in entries:
            if identity not in blob_digests:
                blob_digests[identity] = digest(source.read(identity))
            content = blob_digests[identity]
            manifest[name] = content
            by_digest[content] = identity
        binding = {
            "git_repository": repository,
            "git_commit": commit,
            "git_tree": tree,
            "file_modes_sha256": digest(canonical({p: m for p, _oid, m in entries})),
        }
        branch = "git/" + commit

        def received():
            head = client.branch(branch)
            if head["revision"] is None:
                return None
            actual = client.revision(head["revision"])
            if (
                actual["objects"] != manifest
                or actual["parent"] is not None
                or json.loads(actual["message"]) != binding
            ):
                raise ValueError("Existing native branch differs from the immutable Git source")
            if previous and previous.get("state") == "received" and previous["native_revision"] != head["revision"]:
                raise ValueError("Received native revision has changed")
            return {
                **pending,
                "state": "received",
                "native_branch": branch,
                "native_revision": head["revision"],
                "manifest_sha256": digest(canonical(manifest)),
                "files": len(manifest),
                "native_publication": "not_requested",
            }

        known = {b["branch"] for b in client.request("GET", "/branches")["branches"]}
        if branch not in known:
            try:
                client.request(
                    "POST", "/branches", {"branch": branch, "revision": None, "request_key": "git-branch-" + commit}
                )
            except ValueError:
                # A concurrent authorized submitter may have created this exact ref.
                if branch not in {b["branch"] for b in client.request("GET", "/branches")["branches"]}:
                    raise
        result = received()
        if result is not None:
            atomic_json(receipt_path, result)
            return result
        if previous and previous.get("state") == "received":
            raise ValueError("Previously received native branch is now empty")
        identifiers = sorted(by_digest)
        for offset in range(0, len(identifiers), 512):
            missing = client.request("POST", "/objects/missing", {"digests": identifiers[offset : offset + 512]})[
                "missing"
            ]
            for identity in missing:
                data = source.read(by_digest[identity])
                uploaded = client.request("PUT", "/objects/" + identity, raw=data)
                if uploaded["digest"] != identity:
                    raise ValueError("Object receipt mismatch")
        try:
            client.request(
                "POST",
                "/commits",
                {
                    "branch": branch,
                    "expected": None,
                    "request_key": "git-commit-" + commit,
                    "manifest": manifest,
                    "message": json.dumps(binding, sort_keys=True),
                },
            )
        except ValueError:
            # Covers a lost response or another actor receiving the same content.
            if received() is None:
                raise
        result = received()
        if result is None:
            raise ValueError("Native commit has no verified receipt")
        atomic_json(receipt_path, result)
        return result
    except Exception:
        # A successful Git operation is retained. A retry reuses exact native keys.
        raise
    finally:
        source.close()


def automatic(root, commit, repository):
    path = configuration()
    if not path.exists():
        return {"state": "not_configured"}
    settings = json.loads(path.read_text(encoding="utf-8-sig"))
    if settings.get("dual_submit") is not True:
        return {"state": "disabled"}
    if settings.get("source_repository") != repository:
        return {"state": "not_selected"}
    return mirror(root, commit, repository, config=path)
