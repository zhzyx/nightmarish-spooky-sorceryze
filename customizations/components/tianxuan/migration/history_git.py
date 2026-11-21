"""Read published Git history without a checkout, hooks, filters or archive programs."""

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import tempfile
from contextlib import closing, contextmanager
from pathlib import Path

from migration_status import read_import_status

MAX_FILE_SIZE = 1024 * 1024
OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")


def _git(repo, *args, data=None):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_TERMINAL_PROMPT="0",
        GIT_ALLOW_PROTOCOL="file",
        GIT_OPTIONAL_LOCKS="0",
    )
    result = subprocess.run(
        [
            "git",
            "--no-replace-objects",
            "--literal-pathspecs",
            "-c",
            "core.longpaths=true",
            "-c",
            "core.hooksPath=" + os.devnull,
            "-C",
            str(repo),
            *args,
        ],
        input=data,
        capture_output=True,
        env=env,
        timeout=300,
    )
    if result.returncode:
        raise ValueError("Archived Git operation failed: " + args[0])
    return result.stdout


def _publication(database, tenant, project, revision):
    status = read_import_status(database, tenant, project)
    if not status or status["revision"] != revision:
        raise LookupError("Git history catalog is not published for this project")
    return status


def _cache_root(database, tenant, project, revision, cache_dir):
    database = Path(database).resolve()
    root = Path(cache_dir) if cache_dir else database.parent / ".migration-history-cache"
    key = hashlib.sha256(json.dumps([str(database), tenant, project, revision]).encode()).hexdigest()
    root = root.resolve() / key
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


@contextmanager
def _cache_lock(root):
    with closing(sqlite3.connect(root / "initialization.lock", timeout=300)) as lock:
        lock.execute("BEGIN IMMEDIATE")
        yield
        lock.commit()


def _promote(database, tenant, project, revision, staged, mirror):
    _publication(database, tenant, project, revision)
    if mirror.exists():
        raise FileExistsError("History cache already exists")
    staged.rename(mirror)


def _mirror(database, tenant, project, revision, cache_dir):
    # Re-check project visibility on every access, including an existing cache.
    status = _publication(database, tenant, project, revision)
    root = _cache_root(database, tenant, project, revision, cache_dir)
    mirror = root / "archive.git"
    if mirror.is_dir():
        return mirror
    with _cache_lock(root):
        if not mirror.is_dir():
            from history_records import export_binary

            with tempfile.TemporaryDirectory(dir=root) as temp:
                stage = Path(temp)
                bundle = stage / "history.bundle"
                export_binary(database, tenant, project, revision, f"github:{status['source']}/history.bundle", bundle)
                staged = stage / "archive.git"
                _git(stage, "clone", "--mirror", "--template=", "--quiet", "--", str(bundle), str(staged))
                _git(staged, "bundle", "verify", str(bundle))
                _promote(database, tenant, project, revision, staged, mirror)
    return mirror


def _check_path(path):
    if (
        not isinstance(path, str)
        or len(path.encode("utf-8")) > 4096
        or any(part in {"", ".", ".."} for part in path.split("/"))
        or "\\" in path
        or ":" in path
        or any(ord(c) < 32 or ord(c) == 127 for c in path)
    ):
        raise ValueError("Expected a repository-relative literal file path")


def _check_oid(commit):
    if not isinstance(commit, str) or not OID.fullmatch(commit):
        raise ValueError("Expected a full lowercase Git commit ID")


def _check_commit(repo, commit):
    if (
        _git(repo, "cat-file", "-t", commit).strip() != b"commit"
        or not _git(repo, "for-each-ref", "--count=1", "--format=%(objectname)", "--contains", commit).strip()
    ):
        raise ValueError("Commit is outside archived history")


def commit_mapping(database, tenant, project, revision, commit, *, cache_dir=None):
    """Resolve one exact Git commit inside the project's published native catalog."""
    _check_oid(commit)
    repo = _mirror(database, tenant, project, revision, cache_dir)
    _check_commit(repo, commit)
    # No path filtering, traversal, mailmap substitution or display truncation.
    fields = (
        _git(
            repo,
            "show",
            "-s",
            "--no-notes",
            "--no-show-signature",
            "--encoding=UTF-8",
            "--format=format:%H%x00%T%x00%P%x00%an%x00%ae%x00%aI%x00%cn%x00%ce%x00%cI",
            commit,
            "--",
        )
        .decode("utf-8")
        .split("\0")
    )
    oid, tree, parents, author, author_email, authored_at, committer, committer_email, committed_at = fields
    if oid != commit:
        raise ValueError("Expected the complete archive object ID")
    status = _publication(database, tenant, project, revision)
    return {
        "source_id": f"github:{status['source']}/commit/{oid}",
        "tenant": tenant,
        "project": project,
        "module": status["module"],
        "revision": revision,
        "oid": oid,
        "tree": tree,
        "parents": parents.split(),
        "author": {"name": author, "email": author_email, "time": authored_at},
        "committer": {"name": committer, "email": committer_email, "time": committed_at},
    }


def list_branches(database, tenant, project, revision, *, offset=0, limit=20, cache_dir=None):
    """Page through full branch refs of the published bundle in Git refname order."""
    if type(offset) is not int or not 0 <= offset <= 10000000 or type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Invalid branch page")
    repo = _mirror(database, tenant, project, revision, cache_dir)
    records = _git(
        repo,
        "for-each-ref",
        "--sort=refname",
        f"--count={offset + limit + 1}",
        "--format=%(refname)%00%(objectname)",
        "refs/heads/",
    ).splitlines()
    items = []
    for record in records[offset : offset + limit]:
        ref, tip = record.split(b"\0", 1)
        items.append({"ref": ref.decode("utf-8"), "tip": tip.decode("ascii")})
    return {"items": items, "next_offset": offset + limit if len(records) > offset + limit else None}


def list_commits(database, tenant, project, revision, *, commit=None, path=None, offset=0, limit=50, cache_dir=None):
    if type(offset) is not int or offset < 0 or offset > 2**31 - 1 or type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Invalid history page")
    if path is not None:
        _check_path(path)
    if commit is not None:
        _check_oid(commit)
    repo = _mirror(database, tenant, project, revision, cache_dir)
    if commit is not None:
        _check_commit(repo, commit)
    args = [
        "log",
        "--topo-order",
        "--no-decorate",
        "--no-notes",
        "--no-show-signature",
        "--no-color",
        "-z",
        "--encoding=UTF-8",
        "--format=%H%x00%P%x00%<(256,trunc)%an%x00%aI%x00%<(512,trunc)%s",
        f"--skip={offset}",
        f"--max-count={limit + 1}",
        commit or "--all",
        "--",
    ]
    if path is not None:
        args.append(path)
    fields = _git(repo, *args).rstrip(b"\x00").decode("utf-8", errors="replace").split("\x00")
    items = []
    if fields != [""]:
        if len(fields) % 5:
            raise ValueError("Invalid archive commit metadata")
        for start in range(0, len(fields), 5):
            oid, parents, author, authored_at, subject = fields[start : start + 5]
            items.append(
                dict(
                    oid=oid,
                    parents=parents.split(),
                    author=author.rstrip(),
                    authored_at=authored_at,
                    subject=subject.rstrip(),
                )
            )
    return {"items": items[:limit], "next_offset": offset + limit if len(items) > limit else None}


def read_file(database, tenant, project, revision, commit, path, *, cache_dir=None):
    _check_oid(commit)
    _check_path(path)
    repo = _mirror(database, tenant, project, revision, cache_dir)
    _check_commit(repo, commit)
    entry = _git(repo, "ls-tree", "-z", "--full-tree", commit, "--", path)
    header, separator, name = entry.rstrip(b"\0").partition(b"\t")
    if not separator or name != path.encode("utf-8"):
        raise LookupError("File is absent from this commit")
    mode, kind, oid = header.decode("ascii").split()
    if mode not in {"100644", "100755"} or kind != "blob":
        raise ValueError("Only regular archived files can be read")
    size = int(_git(repo, "cat-file", "-s", oid))
    if size > MAX_FILE_SIZE:
        raise ValueError("Archived file exceeds 1 MiB")
    data = _git(repo, "cat-file", "blob", oid)
    if len(data) != size or b"\0" in data:
        raise ValueError("Expected an archived UTF-8 text file")
    return dict(commit=commit, path=path, blob=oid, size=size, text=data.decode("utf-8"))


def _heading(data):
    try:
        lines = data.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError:
        return None
    fence = ""
    previous = ""
    frontmatter = bool(lines and lines[0] == "---")
    for index, line in enumerate(lines):
        if frontmatter:
            if index and line in ("---", "..."):
                frontmatter = False
            continue
        if fence:
            if re.fullmatch(r" {0,3}" + fence[0] + "{" + str(len(fence)) + r",}[ \t]*", line):
                fence = ""
            continue
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if marker:
            fence = marker[1]
            previous = ""
            continue
        heading = re.fullmatch(r" {0,3}#[ \t]+(.+)", line)
        if heading:
            title = re.sub(r"[ \t]+#+[ \t]*$", "", heading[1]).strip()
            if title:
                return title[:512]
        if previous and re.fullmatch(r" {0,3}=+[ \t]*", line):
            return previous[:512]
        previous = "" if line.startswith(("    ", "\t")) else line.strip()
    return None


def requirement_titles(database, tenant, project, revision, commit, documents, *, cache_dir=None):
    """Read H1 titles for verified Markdown paths. Bound batch sizes on Windows and blob memory."""
    import io

    _check_oid(commit)
    repo = _mirror(database, tenant, project, revision, cache_dir)
    _check_commit(repo, commit)
    paths = []
    size = 0
    blobs = {}

    def locate(group):
        listed = _git(repo, "ls-tree", "-lz", "--full-tree", commit, "--", *group)
        found = set()
        for item in listed.split(b"\0"):
            if not item:
                continue
            header, path = item.split(b"\t", 1)
            name = path.decode("utf-8")
            mode, kind, oid, length = header.decode().split()
            if mode not in ("100644", "100755") or kind != "blob" or documents.get(name) != oid:
                raise ValueError("Requirement blob does not match commit and path")
            found.add(name)
            if int(length) <= MAX_FILE_SIZE:
                blobs.setdefault((oid, int(length)), []).append(name)
        if found != set(group):
            raise LookupError("Requirement is absent from this commit")

    for path, oid in documents.items():
        _check_path(path)
        if not path.lower().endswith((".md", ".markdown")):
            continue
        if not isinstance(oid, str) or not OID.fullmatch(oid):
            raise ValueError("Invalid requirement blob ID")
        path_size = len(path.encode("utf-8")) + 3
        if paths and size + path_size > 10000:
            locate(paths)
            paths, size = [], 0
        paths.append(path)
        size += path_size
    if paths:
        locate(paths)

    titles = {}

    def read_batch(batch):
        request = "".join(oid + "\n" for oid, n in batch).encode()
        with io.BytesIO(_git(repo, "cat-file", "--batch", data=request)) as contents:
            for oid, length in batch:
                if contents.readline().split() != [oid.encode(), b"blob", str(length).encode()]:
                    raise ValueError("Archived object differs from tree entry")
                title = _heading(contents.read(length))
                if contents.read(1) != b"\n":
                    raise ValueError("Invalid archive batch framing")
                if title:
                    titles.update((path, title) for path in blobs[(oid, length)])

    batch = []
    total = 0
    for key in blobs:
        if batch and (total + key[1] > 4 * MAX_FILE_SIZE or len(batch) >= 100):
            read_batch(batch)
            batch, total = [], 0
        batch.append(key)
        total += key[1]
    if batch:
        read_batch(batch)
    return titles
