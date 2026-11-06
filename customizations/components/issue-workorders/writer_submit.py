"""Issue a GitHub-signed submission for the staged tree using the current writer's account."""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import issue_gate
import work_items


def require(ok, message):
    if not ok:
        raise ValueError(message)


def git(repo, *args):
    return issue_gate.git(repo, *args).decode("utf-8").strip()


def authenticated_git(repo, *args):
    # Use the same logged-in CLI even in a fresh clone with no Git credential helper.
    helper = '!"$GONGGONG_GH" auth git-credential' if os.environ.get("GONGGONG_GH") else "!gh auth git-credential"
    return git(repo, "-c", "credential.helper=", "-c", "credential.helper=" + helper, *args)


def graphql(query, **variables):
    result = subprocess.run(
        [os.environ.get("GONGGONG_GH", "gh"), "api", "--hostname", "github.com", "graphql", "--input", "-"],
        input=json.dumps({"query": query, "variables": variables}),
        capture_output=True,
        encoding="utf-8",
        timeout=120,
    )
    if result.returncode:
        raise ValueError("GitHub request failed: " + result.stderr.strip()[:500] + "; retry to reconcile remote state")
    return json.loads(result.stdout)["data"]


def writer(repository):
    owner, name = repository.split("/")
    data = graphql(
        """query($owner:String!,$name:String!){
      viewer{login databaseId} repository(owner:$owner,name:$name){nameWithOwner viewerPermission}
    }""",
        owner=owner,
        name=name,
    )
    target = data["repository"]
    require(
        target
        and target["nameWithOwner"].lower() == repository.lower()
        and target["viewerPermission"] in {"WRITE", "MAINTAIN", "ADMIN"},
        "Repository write permission required",
    )
    actor = data["viewer"]
    require(
        re.fullmatch(r"[A-Za-z0-9-]+", actor["login"]) and type(actor["databaseId"]) is int,
        "Authenticated GitHub user required",
    )
    return actor


COMMIT_FIELDS = """oid message tree{oid} parents(first:2){nodes{oid}}
    author{user{login}} signature{isValid wasSignedByGitHub}"""


def remote_tip(repository, branch):
    owner, name = repository.split("/")
    data = graphql(
        """query($owner:String!,$name:String!,$ref:String!){
      repository(owner:$owner,name:$name){ref(qualifiedName:$ref){target{... on Commit{"""
        + COMMIT_FIELDS
        + "}}}}}",
        owner=owner,
        name=name,
        ref="refs/heads/" + branch,
    )
    ref = data["repository"]["ref"]
    return ref["target"] if ref else None


def verify_receipt(commit, actor, parent, tree, message):
    require(
        commit
        and commit["message"].rstrip() == message
        and commit["tree"]["oid"] == tree
        and commit["parents"]["nodes"] == [{"oid": parent}]
        and ((commit.get("author") or {}).get("user") or {}).get("login", "").lower() == actor.lower()
        and commit["signature"] == {"isValid": True, "wasSignedByGitHub": True},
        "Remote head is not the expected writer's signed receipt",
    )
    return commit["oid"]


def issue_receipt(repo, repository, actor, branch, parent, tree, message):
    tip = remote_tip(repository, branch)
    if tip is None:
        # Only create a new ref. A competing publisher can never be overwritten.
        ref = "refs/heads/" + branch
        authenticated_git(
            repo,
            "push",
            "--force-with-lease=" + ref + ":",
            "https://github.com/" + repository + ".git",
            parent + ":" + ref,
        )
        tip = remote_tip(repository, branch)
    if tip and tip["oid"] == parent:
        title, body = message.split("\n\n", 1)
        graphql(
            """mutation($input:CreateCommitOnBranchInput!){
          createCommitOnBranch(input:$input){commit{oid}}
        }""",
            input={
                "branch": {"repositoryNameWithOwner": repository, "branchName": branch},
                "expectedHeadOid": parent,
                "fileChanges": {"additions": [], "deletions": []},
                "message": {"headline": title, "body": body},
            },
        )
        tip = remote_tip(repository, branch)
    return verify_receipt(tip, actor, parent, tree, message)


def submit(repo, issue, request, title, notes):
    repository = work_items.config(repo)[0]["repository"]
    issue_gate.check_repository(repo, repository)
    actor = writer(repository)
    login = actor["login"]
    local_branch = git(repo, "symbolic-ref", "--short", "HEAD")
    require(local_branch != "main", "Use an isolated task branch")
    authenticated_git(repo, "fetch", "https://github.com/" + repository + ".git", "refs/heads/main")
    base = git(repo, "rev-parse", "FETCH_HEAD")
    head = git(repo, "rev-parse", "HEAD")
    tree = git(repo, "write-tree")
    require(git(repo, "merge-base", base, head) == base, "Integrate current main before signing")
    require(tree != git(repo, "rev-parse", base + "^{tree}"), "No changes relative to main")
    trailers = f"GongGong-Issue: #{issue}\nGongGong-Request: {request}"
    issue_gate.gate(repo, issue, request, base_ref=base)
    require(
        (local_branch, head, tree)
        == (git(repo, "symbolic-ref", "--short", "HEAD"), git(repo, "rev-parse", "HEAD"), git(repo, "write-tree")),
        "Staged candidate changed during gate",
    )
    if git(repo, "rev-parse", head + "^{tree}") != tree:
        email = f"{actor['databaseId']}+{login}@users.noreply.github.com"
        git(repo, "-c", "user.name=" + login, "-c", "user.email=" + email, "commit", "-m", title, "-m", trailers)
        candidate = git(repo, "rev-parse", "HEAD")
        require(git(repo, "show", "-s", "--format=%P", candidate) == head, "Unexpected commit parent")
    else:
        candidate = head
        require(
            git(repo, "show", "-s", "--format=%B", head).endswith(trailers),
            "Existing HEAD belongs to another work order; stage the intended change",
        )
    require(git(repo, "rev-parse", candidate + "^{tree}") == tree, "Committed tree differs from gated index")
    subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(repo / "framework/extensions/diting-files/diting_files.py"),
            "git-check",
            "--repo",
            str(repo),
            "--require-committed",
        ],
        check=True,
        timeout=300,
    )
    require(writer(repository) == actor, "GitHub identity changed")
    branch = f"codex/submit/{login}/{issue}/{candidate}"
    message = (
        f"Sign delivery for #{issue}\n\n{trailers}\nRepository: {repository}\n"
        f"Candidate: {candidate}\nTree: {tree}\nBase: {base}\nTarget: main\nWriter: {login}"
    )
    signed = issue_receipt(repo, repository, login, branch, candidate, tree, message)
    remote = "github.com/" + repository
    prs = json.loads(
        work_items.gh(
            "pr",
            "list",
            "-R",
            remote,
            "--state",
            "all",
            "--head",
            branch,
            "--base",
            "main",
            "--json",
            "url,headRefOid,isCrossRepository,state",
        )
    )
    matches = [p for p in prs if not p["isCrossRepository"]]
    if matches:
        require(
            len(matches) == 1 and matches[0]["headRefOid"] == signed and matches[0]["state"] != "CLOSED",
            "Existing PR conflicts with this signed candidate",
        )
        url = matches[0]["url"]
    else:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "body.md"
            path.write_text(f"{trailers}\n\n{notes.strip()}\n\n签发人 {login}，签发提交 {signed}。\n", encoding="utf-8")
            url = work_items.gh(
                "pr",
                "create",
                "-R",
                remote,
                "--base",
                "main",
                "--head",
                branch,
                "--title",
                title,
                "--body-file",
                str(path),
            )
    observed = json.loads(work_items.gh("pr", "view", url, "--json", "headRefOid,baseRefName,isCrossRepository"))
    require(
        observed == {"headRefOid": signed, "baseRefName": "main", "isCrossRepository": False},
        "Submitted PR no longer matches the signed candidate",
    )
    return {
        "repository": repository,
        "writer": login,
        "candidate": candidate,
        "tree": tree,
        "signed_commit": signed,
        "pull_request": url,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--notes-file", type=Path, required=True, help="PR scope, business checks and review evidence")
    args = parser.parse_args()
    try:
        notes = args.notes_file.read_text(encoding="utf-8-sig")
        require(
            args.title.strip()
            and "\n" not in args.title
            and notes.strip()
            and not re.search(r"^GongGong-(Issue|Request):", notes, re.M),
            "Provide a title and PR validation notes",
        )
        result = submit(args.repo.resolve(), args.issue, args.request_id, args.title, notes)
        from kuafu_incident import observe_success

        observe_success(args.repo.resolve(), args.issue, args.request_id, "delivery", result)
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        from kuafu_incident import notify_failure

        notify_failure(args.repo.resolve(), args.issue, args.request_id, "delivery", error)
        raise


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        sys.exit(str(exc))
