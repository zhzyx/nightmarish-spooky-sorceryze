"""Git object operations for reviewed, immutable merge-queue requests."""

import os
import subprocess
import tempfile
from pathlib import Path

from git_service import GitServiceError


def git(exe, repo, *args, data=None, env=None, check=True):
    result = subprocess.run([exe, "-C", str(repo), *args], input=data, capture_output=True, env=env, check=False)
    if check and result.returncode:
        raise GitServiceError(result.stderr.decode(errors="replace").strip() or "Git object operation failed")
    return result


def projection(exe, item):
    exact = item["evidence"]["exact_request"]
    merged = git(
        exe, item["repo"], "merge-tree", "--write-tree", "-z", exact["target_base"], exact["candidate"], check=False
    )
    if merged.returncode not in (0, 1):
        raise GitServiceError("Cannot read the exact merge tree")
    parts = iter(merged.stdout.split(b"\x00"))
    tree = next(parts).decode("ascii")
    conflicts = {}
    if merged.returncode:
        for entry in parts:
            if not entry:
                break
            metadata, path = entry.split(b"\t", 1)
            mode, oid, stage = metadata.decode("ascii").split()
            conflicts.setdefault(path.decode(), {})[int(stage)] = (mode, oid)
        if not conflicts:
            raise GitServiceError("Conflict has no selectable file stages")
    return tree, conflicts


def conflict_files(exe, item):
    _, conflicts = projection(exe, item)
    files = []
    remaining = 1_000_000
    for path, stages in conflicts.items():
        if len(files) >= 100:
            raise ValueError("Too many conflicts for an interactive text resolution")
        views = {}
        for key, stage in (("target", 2), ("source", 3)):
            entry = stages.get(stage)
            text = None
            if entry and entry[0] in ("100644", "100755"):
                size = int(git(exe, item["repo"], "cat-file", "-s", entry[1]).stdout)
                if size <= min(100_000, remaining):
                    content = git(exe, item["repo"], "cat-file", "blob", entry[1]).stdout
                    if b"\0" not in content:
                        try:
                            text = content.decode()
                        except UnicodeDecodeError:
                            pass
                    remaining -= size
            views[key] = {"oid": entry[1] if entry else None, "text": text}
        files.append({"path": path, **views})
    return files


def commit(exe, item, tree, parents, message):
    env = dict(
        os.environ,
        GIT_AUTHOR_NAME="Duobao Queue",
        GIT_COMMITTER_NAME="Duobao Queue",
        GIT_AUTHOR_EMAIL="duobao@gonggong.local",
        GIT_COMMITTER_EMAIL="duobao@gonggong.local",
        GIT_AUTHOR_DATE=item["created_at"],
        GIT_COMMITTER_DATE=item["created_at"],
    )
    args = [arg for parent in parents for arg in ("-p", parent)]
    return git(exe, item["repo"], "commit-tree", tree, *args, "-m", message, env=env).stdout.decode().strip()


def resolved_candidate(exe, item, resolutions, *, authorize):
    tree, conflicts = projection(exe, item)
    if not conflicts or set(conflicts) != set(resolutions):
        raise ValueError("Every conflicting path must have exactly one resolution")
    if len(resolutions) > 100 or sum(len(v.get("text", "").encode()) for v in resolutions.values()) > 1_000_000:
        raise ValueError("Interactive resolution exceeds its size limit")
    repo = item["repo"]
    exact = item["evidence"]["exact_request"]
    with tempfile.TemporaryDirectory(prefix="duobao-resolve-") as temp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(temp) / "index"))
        git(exe, repo, "read-tree", tree, env=env)
        updates = bytearray()
        for path, stages in conflicts.items():
            value = resolutions[path]
            side = value["choice"]
            if side in ("target", "source"):
                selected = stages.get(2 if side == "target" else 3)
            elif side == "text" and all(mode in ("100644", "100755") for mode, _ in stages.values()):
                modes = {s[0] for i, s in stages.items() if i in (2, 3)}
                if len(modes) != 1 or "text" not in value or "\0" in value["text"]:
                    raise ValueError("Choose a side for a mode or binary conflict")
                oid = (
                    git(exe, repo, "hash-object", "-w", "--stdin", data=value["text"].encode()).stdout.decode().strip()
                )
                selected = (modes.pop(), oid)
            else:
                raise ValueError("Invalid resolution")
            mode, oid = selected or ("0", "0" * len(tree))
            updates.extend(f"{mode} {oid}\t{path}\0".encode())
        git(exe, repo, "update-index", "-z", "--index-info", env=env, data=bytes(updates))
        ready = git(exe, repo, "write-tree", env=env).stdout.decode().strip()
    oid = commit(exe, item, ready, [exact["candidate"], exact["target_base"]], f"Resolve merge request {item['id']}")
    branch = "resolved/" + item["id"] + "/" + oid
    authorize(branch)
    ref = "refs/heads/" + branch
    pinned = f"verify refs/heads/{item['source']} {exact['candidate']}\nverify refs/heads/{item['target']} {exact['target_base']}\n"
    created = git(exe, repo, "update-ref", "--stdin", data=(pinned + f"create {ref} {oid}\n").encode(), check=False)
    if created.returncode:
        # Another request may already have created the same deterministic commit.
        git(exe, repo, "update-ref", "--stdin", data=(pinned + f"verify {ref} {oid}\n").encode())
    return branch, oid


def apply_checked(exe, item):
    repo = item["repo"]
    exact = item["evidence"]["exact_request"]
    candidate, base = exact["candidate"], exact["target_base"]
    marker = "refs/duobao/delivered/" + item["id"]
    prior = git(exe, repo, "rev-parse", "--verify", marker, check=False)
    if prior.returncode == 0:
        return prior.stdout.decode().strip()
    tree, conflicts = projection(exe, item)
    if conflicts or tree != item["evidence"].get("checked_tree"):
        raise ValueError("Rebuild and check the exact merge tree before delivery")
    if git(exe, repo, "merge-base", "--is-ancestor", base, candidate, check=False).returncode == 0:
        oid = candidate
    else:
        oid = commit(exe, item, tree, [base, candidate], f"Deliver merge request {item['id']}")
    transaction = (
        f"verify refs/heads/{item['source']} {candidate}\nupdate refs/heads/{item['target']} {oid} {base}\n"
        f"create {marker} {oid}\n"
    )
    git(exe, repo, "update-ref", "--stdin", data=transaction.encode())
    return oid
