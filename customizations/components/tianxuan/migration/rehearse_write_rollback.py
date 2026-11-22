"""Exercise the Git-backed Duobao write route and restore the original entry in a disposable replica."""

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path

from routing import tenant_entry

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "duobao"))
from git_service import GitService


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def refs(repo):
    rows = git(repo, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads", "refs/tags")
    return dict(row.split() for row in rows.splitlines())


def rehearse(directory):
    source = directory / "original.git"
    subprocess.run(["git", "init", "--quiet", "--bare", "--initial-branch=main", str(source)], check=True)
    service = GitService(shutil.which("git"))
    author = ("Rehearsal", "rehearsal@example.invalid")
    base = service.commit(source, "main", "Baseline", {"project.txt": "baseline\n"}, *author)
    git(source, "update-ref", "refs/heads/topic", base)
    git(source, "update-ref", "refs/tags/baseline", base)
    target = directory / "duobao.git"
    subprocess.run(["git", "clone", "--quiet", "--mirror", str(source), str(target)], check=True)

    def route(new_entry=None):
        with closing(sqlite3.connect(directory / "routing.sqlite")) as database, database:
            return tenant_entry(database, "rehearsal", "workbench", entry=new_entry)

    initial = {"route": route(), "original": refs(source), "duobao": refs(target)}
    assert initial["route"] == "existing" and initial["original"] == initial["duobao"]
    checkpoint = directory / "before.json"
    checkpoint.write_text(json.dumps(initial), encoding="utf-8")
    route("tianxuan")
    assert route() == "tianxuan"
    changes = {}
    for branch in ("main", "topic"):
        changes[branch] = service.commit(target, branch, "Write during cutover", {branch + ".txt": branch}, *author)
    saved = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert refs(source) == saved["original"]
    advanced = refs(target)
    for branch, head in changes.items():
        ref = "refs/heads/" + branch
        git(target, "merge-base", "--is-ancestor", saved["duobao"][ref], head)
        assert advanced[ref] == head
    # Only fast-forwards are accepted. The two destination refs change together.
    git(target, "push", "--atomic", str(source), *(f"refs/heads/{b}:refs/heads/{b}" for b in changes))
    recovered = refs(source)
    assert recovered == advanced
    route(saved["route"])
    assert route() == "existing"
    for branch in changes:
        assert git(source, "show", branch + ":" + branch + ".txt") == branch
    # Demonstrate a new write using the original Git remote after restoring the route.
    client = directory / "original-client"
    subprocess.run(["git", "clone", "--quiet", str(source), str(client)], check=True)
    (client / "after.txt").write_text("original entry\n", encoding="utf-8")
    git(client, "add", "after.txt")
    git(
        client,
        "-c",
        "user.name=" + author[0],
        "-c",
        "user.email=" + author[1],
        "-c",
        "commit.gpgsign=false",
        "commit",
        "--quiet",
        "-m",
        "Write after rollback",
    )
    git(client, "push", "--quiet", "origin", "main")
    final = refs(source)
    assert git(source, "rev-parse", "main^") == changes["main"]
    assert final["refs/heads/topic"] == changes["topic"] and refs(target) == advanced
    git(source, "fsck", "--full", "--no-dangling")
    return {
        "before": saved,
        "cutover_commits": changes,
        "recovered_refs": recovered,
        "final_route": route(),
        "after_original_write": final,
    }


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="duobao-rollback-") as directory:
        print(json.dumps(rehearse(Path(directory)), indent=2))
