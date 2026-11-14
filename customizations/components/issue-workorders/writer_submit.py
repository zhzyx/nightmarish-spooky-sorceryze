"""Issue a GitHub-signed submission for the staged tree using the current writer's account."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import issue_gate
import submission_audit
import work_items


def require(ok: object, message: str) -> None:
    if not ok:
        raise ValueError(message)


def git(repo: Path, *args: str) -> str:
    raw: bytes = issue_gate.git(repo, *args)
    return raw.decode("utf-8").strip()


def authenticated_git(repo: Path, *args: str) -> str:
    # Use the same logged-in CLI even in a fresh clone with no Git credential helper.
    helper = work_items.github_runtime.credential_helper()
    return git(repo, "-c", "credential.helper=", "-c", "credential.helper=" + helper, *args)


def graphql(query: str, **variables: Any) -> Any:
    output = work_items.gh(
        "api",
        "--hostname",
        "github.com",
        "graphql",
        "--input",
        "-",
        input_value=json.dumps({"query": query, "variables": variables}),
    )
    return json.loads(output)["data"]


def writer(repository: str) -> dict[str, Any]:
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
    actor: dict[str, Any] = data["viewer"]
    require(
        re.fullmatch(r"[A-Za-z0-9-]+", actor["login"]) and type(actor["databaseId"]) is int,
        "Authenticated GitHub user required",
    )
    return actor


COMMIT_FIELDS = """oid message tree{oid} parents(first:2){nodes{oid}}
    author{user{login}} signature{isValid wasSignedByGitHub}"""


def remote_tip(repository: str, branch: str) -> dict[str, Any] | None:
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
    target: dict[str, Any] | None = ref["target"] if ref else None
    return target


def verify_receipt(commit: dict[str, Any] | None, actor: str, parent: str, tree: str, message: str) -> str:
    require(
        commit
        and commit["message"].rstrip() == message
        and commit["tree"]["oid"] == tree
        and commit["parents"]["nodes"] == [{"oid": parent}]
        and ((commit.get("author") or {}).get("user") or {}).get("login", "").lower() == actor.lower()
        and commit["signature"] == {"isValid": True, "wasSignedByGitHub": True},
        "Remote head is not the expected writer's signed receipt",
    )
    assert commit is not None
    return str(commit["oid"])


def issue_receipt(
    repo: Path,
    repository: str,
    actor: str,
    branch: str,
    parent: str,
    tree: str,
    message: str,
) -> str:
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


def changed_paths(repo: Path, before: str, after: str) -> list[str]:
    # Disable rename heuristics so both the removed and added paths are represented.
    raw = issue_gate.git(repo, "diff", "--no-renames", "--name-only", "-z", before, after, "--")
    return sorted(os.fsdecode(path) for path in raw.split(b"\0") if path)


def path_overlap(left: Iterable[str], right: Iterable[str]) -> list[str]:
    # A file replaced by a directory (or vice versa) also intersects a nested path.
    def prefixes(paths: Iterable[str]) -> set[str]:
        return {path[:i] for path in paths for i, char in enumerate(path) if char == "/"}

    right_set = set(right)
    directories = prefixes(right_set)
    return sorted(
        path for path in set(left) if path in right_set or path in directories or prefixes([path]) & right_set
    )


def _validate_read_paths(reads: Sequence[str] | None) -> list[str] | None:
    if reads is None:
        return None
    require(
        isinstance(reads, list)
        and all(
            isinstance(p, str)
            and bool(p)
            and not p.startswith("/")
            and "\\" not in p
            and not any(part in {"", ".", ".."} for part in p.split("/"))
            for p in reads
        ),
        "Read dependency paths must be repository-relative POSIX paths",
    )
    return sorted(set(reads))


def _tree_entries(repo: Path, tree_or_commit: str, paths: Sequence[str]) -> dict[str, tuple[str, str]]:
    if not paths:
        return {}
    raw = issue_gate.git(repo, "ls-tree", "-rz", tree_or_commit, "--", *paths)
    entries: dict[str, tuple[str, str]] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        meta, name = record.split(b"\t", 1)
        mode, _, oid = meta.split()
        entries[os.fsdecode(name)] = (mode.decode("ascii"), oid.decode("ascii"))
    return entries


def _merge_disjoint_tree(
    repo: Path,
    common: str,
    target_commit: str,
    source_commit: str,
    source_tree: str,
    writes: Sequence[str],
) -> str:
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "merge-tree",
            "--write-tree",
            "-z",
            f"--merge-base={common}",
            target_commit,
            source_commit,
        ],
        capture_output=True,
        timeout=120,
    )
    require(proc.returncode == 0, "Tree integration produced merge conflicts")
    merged_tree = proc.stdout.split(b"\0", 1)[0].decode("ascii").strip()
    require(re.fullmatch(r"[0-9a-f]{40}", merged_tree), "Invalid merged tree OID")
    require(
        changed_paths(repo, target_commit, merged_tree) == list(writes)
        and _tree_entries(repo, merged_tree, writes) == _tree_entries(repo, source_tree, writes),
        "Merged tree did not preserve exact candidate path deltas",
    )
    return merged_tree


def _diff_entries(repo: Path, before: str, after: str) -> list[tuple[str, bool]]:
    fields = issue_gate.git(repo, "diff", "--raw", "--no-renames", "-z", before, after, "--").split(b"\0")
    entries: list[tuple[str, bool]] = []
    for header, raw_path in zip(fields[::2], fields[1::2]):
        if not header or not raw_path:
            continue
        old, new, _, _, status = header[1:].split()
        entries.append((os.fsdecode(raw_path), status == b"M" and old == new == b"100644"))
    return entries


def _base_reviewed_host_inputs(repo: Path, base: str) -> frozenset[str]:
    try:
        entry = issue_gate.git(repo, "ls-tree", "-z", base, "--", "tools/native_host_inputs.json")
        if not entry:
            return frozenset()
        mode, kind, oid = entry.split(b"\t", 1)[0].split()
        if mode not in {b"100644", b"100755"} or kind != b"blob":
            return frozenset()
        policy = json.loads(issue_gate.git(repo, "cat-file", "blob", oid.decode("ascii")))
        if isinstance(policy, dict) and policy.get("schema_version") == 1 and isinstance(policy.get("inputs"), list):
            return frozenset(str(x) for x in policy["inputs"] if isinstance(x, str))
    except (ValueError, KeyError, OSError, subprocess.SubprocessError):
        pass
    return frozenset()


def handoff(repo: Path, base: str, tree: str, main: str) -> dict[str, Any]:
    diff_items = _diff_entries(repo, base, tree)
    writes = sorted(path for path, _ in diff_items)
    audit_profile = submission_audit.classify_submission_diff(diff_items, _base_reviewed_host_inputs(repo, base))
    upstream = changed_paths(repo, base, main) if main != base else []
    overlap = path_overlap(writes, upstream)
    advanced = main != base and git(repo, "merge-base", base, main) == base
    if main == base:
        action = "回读签发 head、main、CI 与验收，合入后继续逐项实测并办理关联工单关单回读。"
    elif not advanced:
        action = "目标历史与签发基线分离；核对目标和主线历史，重新整合、验证及签发。"
    elif overlap:
        action = "核对双方对重叠路径的修改意图，复验受影响条款；对整合后的候选重新门禁和签发。"
    else:
        action = "检查上游接口与依赖变化，可使用 --rebind-pr 或整合 main 后重新执行候选门禁与签发。"
    return {
        "base": base,
        "main_observed": main,
        "tree": tree,
        "write_paths": writes,
        "audit_profile": audit_profile,
        "base_advanced": advanced,
        "upstream_change_count": len(upstream),
        "overlapping_write_paths": overlap,
        "substantive_rework": None,
        "next_action": action,
    }


def pr_handoff(repository: str, report: Mapping[str, Any], candidate: str, signed: str, login: str) -> str:
    paths = report["write_paths"]
    listing = "\n".join("    " + json.dumps(path, ensure_ascii=True) for path in paths)
    if len(listing) > 6000:
        listing = f"[完整路径差异](https://github.com/{repository}/compare/{report['base']}...{signed}#files_bucket)"
    return (
        f"交接 · 发布者 {login} · 目标 main · 基线 `{report['base']}`\n"
        f"源候选 `{candidate}` · 已签 head `{signed}` · 内容树 `{report['tree']}`\n"
        f"相对签发基线写入 {len(paths)} 个仓库路径（含删除）：\n\n{listing}"
    )


def extract_pr_notes(body: str) -> str:
    """Recover user validation notes from a writer_submit-formatted PR body."""
    normalized = body.replace("\r\n", "\n").strip()
    normalized = re.sub(
        r"^GongGong-Issue:[ \t]*#[1-9][0-9]*[ \t]*\nGongGong-Request:[ \t]*[a-z0-9-]+[ \t]*\n+",
        "",
        normalized,
    )
    if normalized.startswith("交接 · 发布者 "):
        lines = normalized.split("\n")
        index = 0
        while index < len(lines) and index < 3:
            index += 1
        while index < len(lines) and not lines[index].strip():
            index += 1
        if index < len(lines) and lines[index].startswith("[完整路径差异]("):
            index += 1
        else:
            while index < len(lines) and lines[index].startswith('    "'):
                index += 1
        normalized = "\n".join(lines[index:]).strip()
    normalized = re.sub(r"\n*Rebound from #[1-9][0-9]* \([^\n]+\)\.\s*$", "", normalized).strip()
    return normalized or "Rebound signed candidate validation preserved from prior PR."


def matching_pr(repository: str, branch: str) -> dict[str, Any] | None:
    prs = json.loads(
        work_items.gh(
            "pr",
            "list",
            "-R",
            "github.com/" + repository,
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
    matches: list[dict[str, Any]] = [pr for pr in prs if not pr["isCrossRepository"]]
    require(len(matches) <= 1, "Multiple PRs for this candidate; reconcile before submission")
    return matches[0] if matches else None


def inspect_pr(repo: Path, repository: str, pr_number: int) -> dict[str, Any]:
    remote = "github.com/" + repository
    pr = json.loads(
        work_items.gh(
            "pr",
            "view",
            str(pr_number),
            "-R",
            remote,
            "--json",
            "url,headRefName,headRefOid,baseRefName,isCrossRepository,state,mergeCommit",
        )
    )
    branch = re.fullmatch(r"codex/submit/([A-Za-z0-9-]+)/([1-9][0-9]*)/([a-f0-9]{40})", pr["headRefName"])
    require(
        branch and pr["baseRefName"] == "main" and not pr["isCrossRepository"],
        "Expected a same-repository signed candidate for main",
    )
    assert branch is not None
    login, issue, candidate = branch.groups()
    url = "https://github.com/" + repository + ".git"
    authenticated_git(repo, "fetch", url, f"refs/pull/{pr_number}/head")
    signed = git(repo, "rev-parse", "FETCH_HEAD")
    require(signed == pr["headRefOid"], "PR head changed during readback")
    owner, name = repository.split("/")
    data = graphql(
        "query($owner:String!,$name:String!,$oid:GitObjectID!){repository(owner:$owner,name:$name){object(oid:$oid){... on Commit{"
        + COMMIT_FIELDS
        + "}}}}",
        owner=owner,
        name=name,
        oid=signed,
    )
    tip = data["repository"]["object"]
    # Use the signature envelope shared with older submissions, never trust mutable PR notes.
    require(tip and isinstance(tip.get("message"), str), "Signed commit unavailable")
    message = tip["message"].rstrip()
    body = re.fullmatch(
        rf"Sign delivery for #{issue}\n\nGongGong-Issue: #{issue}\nGongGong-Request: ([a-z0-9-]+)\n"
        rf"Repository: {re.escape(repository)}\nCandidate: {candidate}\nTree: ([0-9a-f]{{40}})\n"
        rf"Base: ([0-9a-f]{{40}})\nTarget: main\nWriter: {re.escape(login)}",
        message,
    )
    require(body, "Signed message does not bind this repository and candidate")
    assert body is not None
    request, tree, base = body.groups()
    require(verify_receipt(tip, login, candidate, tree, message) == signed, "Signed head mismatch")
    require(
        git(repo, "rev-parse", candidate + "^{tree}") == tree and git(repo, "merge-base", candidate, base) == base,
        "Signed tree or base differs from the source candidate",
    )
    authenticated_git(repo, "fetch", url, "refs/heads/main")
    main = git(repo, "rev-parse", "FETCH_HEAD")
    merge = (pr["mergeCommit"] or {}).get("oid")
    comparison: str | None = main
    if pr["state"] == "MERGED":
        require(merge and git(repo, "merge-base", main, merge) == merge, "Merged result requires main readback")
        assert isinstance(merge, str)
        parents = git(repo, "show", "-s", "--format=%P", merge).split()
        # Only a normal PR merge exposes the exact pre-merge target as its first parent.
        comparison = parents[0] if parents[1:] == [signed] else None
    report = handoff(repo, base, tree, comparison or base)
    if comparison is None:
        report.update(main_observed=None, base_advanced=None, upstream_change_count=None, overlapping_write_paths=None)
    report.update(
        current_main=main,
        pr_state=pr["state"],
        merge_commit=merge,
        issue=int(issue),
        request_id=request,
        writer=login,
        candidate=candidate,
        signed_commit=signed,
        pull_request=pr["url"],
        repository=repository,
    )
    if pr["state"] == "MERGED":
        assert isinstance(merge, str)
        landed_diff = set(changed_paths(repo, tree, merge))
        report["delivered_paths_differ"] = sorted(landed_diff.intersection(report["write_paths"]))
        receipt = json.loads(work_items.gh("issue", "view", issue, "-R", remote, "--json", "state,stateReason,labels"))
        labels = {label["name"] for label in receipt["labels"]}
        report["issue_receipt"] = {
            "state": receipt["state"],
            "reason": receipt["stateReason"],
            "labels": sorted(labels),
        }
        if receipt["state"] == "OPEN":
            action = "逐项执行可做的验收，修复后复验；通过后关闭对应 Issue 并回读。实际受阻或需人工判断时提醒责任人。"
        elif receipt["stateReason"] == "COMPLETED" and "status:done" in labels:
            action = "目标单已有完成回执，核对原验收证据及其余关联工单的结束回执。"
        else:
            action = "核对关闭原因、标签及尾项承接证据，沿原生命周期处理。"
        report["next_action"] = "已有 main 回执。" + action
    elif pr["state"] == "CLOSED":
        report["next_action"] = "核对旧 PR 的关闭原因及接替候选后再推进。"
    if comparison and comparison != base:
        report["upstream_diff"] = f"https://github.com/{repository}/compare/{base}..{comparison}"
    return report


def submit(
    repo: Path,
    issue: int,
    request: str,
    title: str,
    notes: str,
    *,
    auto_integrate: bool = False,
    reads: Sequence[str] | None = None,
    supersede_prior: bool = False,
) -> dict[str, Any]:
    checked_reads = _validate_read_paths(reads)
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
    common = git(repo, "merge-base", base, head)
    if common != base:
        branch = f"codex/submit/{login}/{issue}/{head}"
        previous = matching_pr(repository, branch)
        if previous and tree == git(repo, "rev-parse", head + "^{tree}"):
            report = inspect_pr(repo, repository, int(previous["url"].rsplit("/", 1)[1]))
            require(
                report["request_id"] == request and report["candidate"] == head, "Prior submission binding mismatch"
            )
            if report["pr_state"] == "MERGED":
                return report
        else:
            report = handoff(repo, common, tree, base)
            report.update(
                local_head=head,
                writer=login,
                prior_pr=previous,
                upstream_diff=f"https://github.com/{repository}/compare/{common}..{base}",
            )
        upstream_paths = changed_paths(repo, common, base)
        read_overlap = path_overlap(checked_reads, upstream_paths) if checked_reads is not None else []
        if read_overlap:
            report["overlapping_read_paths"] = read_overlap
        if (
            not auto_integrate
            or not report.get("base_advanced")
            or report.get("overlapping_write_paths")
            or read_overlap
        ):
            raise ValueError("Integrate current main before signing: " + json.dumps(report, ensure_ascii=True))
        # Refuse to rewrite a worktree with unstaged modifications.
        issue_gate.git(repo, "diff", "--quiet", "--no-ext-diff", "--ignore-submodules=none")
        stage_commit = git(
            repo,
            "-c",
            "user.name=" + login,
            "-c",
            f"user.email={actor['databaseId']}+{login}@users.noreply.github.com",
            "-c",
            "commit.gpgsign=false",
            "commit-tree",
            tree,
            "-p",
            common,
            "-m",
            "Stage candidate for zero-overlap main integration",
        )
        merged_tree = _merge_disjoint_tree(repo, common, base, stage_commit, tree, report["write_paths"])
        git(repo, "reset", "--soft", base)
        git(repo, "read-tree", "-u", "-m", merged_tree)
        head = git(repo, "rev-parse", "HEAD")
        tree = git(repo, "write-tree")
        require(head == base and tree == merged_tree, "Worktree integration state mismatch")
    report = handoff(repo, base, tree, base)
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
        git(
            repo,
            "-c",
            "user.name=" + login,
            "-c",
            "user.email=" + email,
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-m",
            title,
            "-m",
            trailers,
        )
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
            "-I",
            "-X",
            "utf8",
            str(issue_gate.INSTALLATION / "customizations/platforms/data-collection/git-files/storage/diting_files.py"),
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
    previous = matching_pr(repository, branch)
    if previous:
        require(
            previous["headRefOid"] == signed and previous["state"] != "CLOSED",
            "Existing PR conflicts with this signed candidate",
        )
        url = previous["url"]
    else:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "body.md"
            summary = pr_handoff(repository, report, candidate, signed, login)
            path.write_text(f"{trailers}\n\n{summary}\n\n{notes.strip()}\n", encoding="utf-8")
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
    observed = json.loads(
        work_items.gh("pr", "view", url, "--json", "headRefOid,baseRefName,isCrossRepository,baseRefOid,state")
    )
    observed_base = observed.pop("baseRefOid")
    state = observed.pop("state")
    require(
        observed == {"headRefOid": signed, "baseRefName": "main", "isCrossRepository": False},
        "Submitted PR no longer matches the signed candidate",
    )
    result_payload: dict[str, Any] = {
        "repository": repository,
        "writer": login,
        "candidate": candidate,
        "tree": tree,
        "signed_commit": signed,
        "pull_request": url,
        "handoff": report,
    }
    if observed_base != base or state != "OPEN":
        latest = inspect_pr(repo, repository, int(url.rsplit("/", 1)[1]))
        require(
            latest["pr_state"] == "MERGED" or (latest["pr_state"] == "OPEN" and latest["current_main"] == base),
            "PR handoff requires reconciliation: " + json.dumps(latest, ensure_ascii=True),
        )
        result_payload = latest
    if supersede_prior:
        pruned = prune_own_superseded(repo, issue=issue, request_id=request, actor_override=actor)
        result_payload["closed_superseded_prs"] = pruned["closed_prs"]
    return result_payload


def rebind_pr(
    repo: Path,
    pr_number: int,
    *,
    close_superseded: bool = False,
    reads: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Rebind a zero-overlap signed PR onto current main in a disposable worktree."""
    checked_reads = _validate_read_paths(reads)
    repository = work_items.config(repo)[0]["repository"]
    issue_gate.check_repository(repo, repository)
    actor = writer(repository)
    login = actor["login"]
    report = inspect_pr(repo, repository, pr_number)
    require(
        report["writer"].lower() == login.lower(),
        "Only the original authenticated writer may rebind this signed PR",
    )
    if report["pr_state"] == "MERGED":
        return {**report, "rebound": False}
    require(report["pr_state"] == "OPEN", "Cannot rebind a closed PR")
    if report["current_main"] == report["base"]:
        return {**report, "rebound": False}
    upstream_paths = changed_paths(repo, report["base"], report["current_main"])
    read_overlap = path_overlap(checked_reads, upstream_paths) if checked_reads is not None else []
    if read_overlap:
        report["overlapping_read_paths"] = read_overlap
    if not report["base_advanced"] or report["overlapping_write_paths"] or read_overlap:
        raise ValueError("Cannot auto-rebind overlapping or diverged PR: " + json.dumps(report, ensure_ascii=True))

    merged_tree = _merge_disjoint_tree(
        repo,
        report["base"],
        report["current_main"],
        report["candidate"],
        report["tree"],
        report["write_paths"],
    )
    remote = "github.com/" + repository
    pr_meta = json.loads(work_items.gh("pr", "view", str(pr_number), "-R", remote, "--json", "title,body"))
    title = pr_meta["title"].strip()
    prior_notes = extract_pr_notes(pr_meta.get("body") or "")
    rebound_notes = (
        f"{prior_notes}\n\n"
        f"Rebound from #{pr_number} (candidate `{report['candidate']}`, "
        f"base `{report['base']}` -> `{report['current_main']}`, overlapping_write_paths=[])."
    )

    with tempfile.TemporaryDirectory(prefix="gonggong-rebind-") as scratch:
        worktree = Path(scratch) / "wt"
        ephemeral_branch = f"rebind/{report['issue']}/{os.urandom(6).hex()}"
        git(repo, "worktree", "add", "--quiet", "--detach", str(worktree), report["current_main"])
        try:
            git(worktree, "switch", "--quiet", "-c", ephemeral_branch)
            git(worktree, "read-tree", "-u", "-m", merged_tree)
            result = submit(worktree, report["issue"], report["request_id"], title, rebound_notes)
        finally:
            subprocess.run(
                ["git", "-C", str(repo), "worktree", "remove", "--force", str(worktree)], capture_output=True
            )
            subprocess.run(["git", "-C", str(repo), "branch", "-D", ephemeral_branch], capture_output=True)

    result["issue"] = report["issue"]
    result["request_id"] = report["request_id"]
    result["rebound"] = True
    result["superseded_pr"] = report["pull_request"]
    result["superseded_closed"] = False
    if close_superseded and result.get("pull_request") != report["pull_request"]:
        work_items.gh(
            "pr",
            "close",
            str(pr_number),
            "-R",
            remote,
            "-c",
            f"Superseded by {result['pull_request']} after zero-overlap main advance (`{report['base']}` -> `{report['current_main']}`).",
        )
        result["superseded_closed"] = True
    return result


def queue_snapshot(repo: Path) -> dict[str, Any]:
    """Query all open signed PRs across accounts in one GraphQL call and plan merge waves."""
    repository = str(work_items.config(repo)[0]["repository"])
    issue_gate.check_repository(repo, repository)
    owner, name = repository.split("/", 1)
    url = "https://github.com/" + repository + ".git"
    authenticated_git(repo, "fetch", url, "refs/heads/main")
    main_sha = git(repo, "rev-parse", "FETCH_HEAD")

    query = (
        """query($owner:String!,$name:String!){
      repository(owner:$owner,name:$name){
        pullRequests(states:OPEN,baseRefName:"main",first:100,orderBy:{field:UPDATED_AT,direction:DESC}){
          nodes{
            number url title body isDraft headRefName headRefOid baseRefOid isCrossRepository mergeable updatedAt
            author { login }
            commits(last:1){
              nodes{
                commit{
                  """
        + COMMIT_FIELDS
        + """
                  statusCheckRollup{
                    contexts(first:100){
                      nodes{
                        __typename
                        ... on CheckRun { name status conclusion startedAt completedAt checkSuite { workflowRun { workflow { name } } } }
                        ... on StatusContext { context state }
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }"""
    )
    data = graphql(query, owner=owner, name=name)
    nodes = ((data.get("repository") or {}).get("pullRequests") or {}).get("nodes") or []

    valid_prs: list[tuple[dict[str, Any], str, str, int, str, str, str, str | None, list[dict[str, Any]]]] = []
    fetch_refs: list[str] = []
    for node in nodes:
        if not isinstance(node, dict) or node.get("isCrossRepository") or node.get("isDraft"):
            continue
        commit_nodes = ((node.get("commits") or {}).get("nodes")) or []
        if not commit_nodes or not isinstance(commit_nodes[-1].get("commit"), dict):
            continue
        tip = commit_nodes[-1]["commit"]
        head_oid = str(node.get("headRefOid") or "")
        if tip.get("oid") != head_oid:
            continue

        rollup_nodes = (((tip.get("statusCheckRollup") or {}).get("contexts") or {}).get("nodes")) or []
        checks: list[dict[str, Any]] = []
        for ctx in rollup_nodes:
            if not isinstance(ctx, dict):
                continue
            wf = (((ctx.get("checkSuite") or {}).get("workflowRun") or {}).get("workflow") or {}).get("name") or ""
            checks.append({**ctx, "workflowName": wf})

        branch_match = re.fullmatch(
            r"codex/submit/([A-Za-z0-9-]+)/([1-9][0-9]*)/([a-f0-9]{40})",
            str(node.get("headRefName") or ""),
        )
        if branch_match:
            login, issue_str, candidate = branch_match.groups()
            if not isinstance(tip.get("message"), str):
                continue
            message = tip["message"].rstrip()
            env_match = re.fullmatch(
                rf"Sign delivery for #{issue_str}\n\nGongGong-Issue: #{issue_str}\nGongGong-Request: ([a-z0-9-]+)\n"
                rf"Repository: {re.escape(repository)}\nCandidate: {candidate}\nTree: ([0-9a-f]{{40}})\n"
                rf"Base: ([0-9a-f]{{40}})\nTarget: main\nWriter: {re.escape(login)}",
                message,
            )
            if not env_match:
                continue
            request_id, tree, base = env_match.groups()
            try:
                verify_receipt(tip, login, candidate, tree, message)
            except ValueError:
                continue
            pr_num = int(node["number"])
            fetch_refs.append(f"+refs/pull/{pr_num}/head:refs/remotes/gonggong-queue/pr-{pr_num}")
            valid_prs.append((node, "signed", login, int(issue_str), request_id, candidate, tree, base, checks))
            continue

        body_text = str(node.get("body") or "")
        issue_matches = re.findall(r"^GongGong-Issue:[ \t]*#([1-9][0-9]*)[ \t]*\r?$", body_text, re.M)
        req_matches = re.findall(r"^GongGong-Request:[ \t]*([a-z0-9]+(?:-[a-z0-9]+)*)[ \t]*\r?$", body_text, re.M)
        author_login = str((node.get("author") or {}).get("login") or "")
        tree_oid = str((tip.get("tree") or {}).get("oid") or "")
        if len(issue_matches) == 1 and len(req_matches) == 1 and author_login and len(tree_oid) == 40:
            pr_num = int(node["number"])
            fetch_refs.append(f"+refs/pull/{pr_num}/head:refs/remotes/gonggong-queue/pr-{pr_num}")
            valid_prs.append((
                node,
                "pr_branch",
                author_login,
                int(issue_matches[0]),
                req_matches[0],
                head_oid,
                tree_oid,
                None,
                checks,
            ))

    if fetch_refs:
        authenticated_git(repo, "fetch", "--no-tags", url, *fetch_refs)

    submissions: list[dict[str, Any]] = []
    for node, sub_kind, login, issue_num, request_id, candidate, tree, pinned_base, checks in valid_prs:
        pr_num = int(node["number"])
        pr_ref = f"refs/remotes/gonggong-queue/pr-{pr_num}"
        resolved_base = pinned_base or git(repo, "merge-base", main_sha, pr_ref)
        report = handoff(repo, resolved_base, tree, main_sha)
        submissions.append({
            "number": pr_num,
            "submission_kind": sub_kind,
            "url": node["url"],
            "title": node["title"],
            "writer": login,
            "issue": issue_num,
            "request_id": request_id,
            "candidate": candidate,
            "signed_commit": node["headRefOid"] if sub_kind == "signed" else None,
            "tree": tree,
            "base": resolved_base,
            "base_advanced": report["base_advanced"],
            "write_paths": report["write_paths"],
            "overlapping_write_paths": report["overlapping_write_paths"],
            "audit_tier": report["audit_profile"]["tier"],
            "ci_state": submission_audit.summarize_ci_state(checks),
            "mergeable": node.get("mergeable") or "UNKNOWN",
            "updated_at": node.get("updatedAt") or "",
        })
    if fetch_refs:
        for item in valid_prs:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "update-ref",
                    "-d",
                    f"refs/remotes/gonggong-queue/pr-{int(item[0]['number'])}",
                ],
                capture_output=True,
            )
    return submission_audit.plan_submission_queue(submissions, main_sha)


def prune_own_superseded(
    repo: Path,
    *,
    issue: int | None = None,
    request_id: str | None = None,
    actor_override: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Close only the authenticated collaborator's own superseded duplicate open PRs."""
    repository = str(work_items.config(repo)[0]["repository"])
    issue_gate.check_repository(repo, repository)
    actor = dict(actor_override) if actor_override is not None else writer(repository)
    login = str(actor["login"])
    snapshot = queue_snapshot(repo)
    remote = "github.com/" + repository
    by_number = {int(item["number"]): item for item in snapshot["submissions"]}
    closed_prs: list[dict[str, Any]] = []
    for item in snapshot["superseded_prs"]:
        pr_num = int(item["pr"])
        full = by_number[pr_num]
        if str(full["writer"]).lower() != login.lower():
            continue
        if issue is not None and int(full["issue"]) != issue:
            continue
        if request_id is not None and str(full["request_id"]) != request_id:
            continue
        replacement = int(item["superseded_by"])
        work_items.gh(
            "pr",
            "close",
            str(pr_num),
            "-R",
            remote,
            "-c",
            f"Superseded by #{replacement} from the same writer (`{login}`) for #{full['issue']} (`{full['request_id']}`).",
        )
        closed_prs.append({"pr": pr_num, "superseded_by": replacement, "issue": full["issue"]})
    return {
        "repository": repository,
        "writer": login,
        "closed_prs": closed_prs,
        "remaining_ready_to_merge": snapshot["ready_to_merge"],
    }


def engine_launch_activation(repo: Path, report: Mapping[str, Any]) -> dict[str, Any]:
    # Run at the installed tools entry point, where native/managed dependencies
    # have normal script-directory imports. Never alter the writer's import
    # path/cache or interpret report fields as Python or shell source.
    tools = Path(__file__).resolve().parents[3] / "tools"
    result = subprocess.run(
        [
            sys.executable,
            "-E",
            "-s",
            "-B",
            "-X",
            "utf8",
            "-c",
            "import json, sys\n"
            "import editor_candidate_activation\n"
            "print(json.dumps(editor_candidate_activation.after_delivery(sys.argv[1], json.load(sys.stdin))))\n",
            str(repo),
        ],
        cwd=tools,
        input=json.dumps(report),
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    value: dict[str, Any] = json.loads(result.stdout)
    require(
        isinstance(value, dict)
        and value.get("state") in {"awaiting_main", "not_applicable", "pending", "activated"}
        and (value.get("state") != "activated" or value.get("ok") is True),
        "Invalid activation adapter result",
    )
    return value


def _load_reads_file(path: Path | None) -> list[str] | None:
    if path is None:
        return None
    loaded = json.loads(path.read_text(encoding="utf-8-sig"))
    require(isinstance(loaded, list), "--reads-file must contain a JSON array of relative POSIX paths")
    return _validate_read_paths(loaded)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--inspect-pr", type=int, help="Read signed PR handoff and compare to current main")
    parser.add_argument(
        "--queue",
        action="store_true",
        help="Inspect all open multi-account signed PRs in one GraphQL snapshot and plan merge waves",
    )
    parser.add_argument(
        "--prune-superseded",
        action="store_true",
        help="Close only the authenticated writer's own superseded duplicate open PRs",
    )
    parser.add_argument("--rebind-pr", type=int, help="Rebind an open zero-overlap signed PR onto current main")
    parser.add_argument(
        "--close-superseded",
        action="store_true",
        help="Close the old drifted PR once the rebound PR is created and verified (requires --rebind-pr)",
    )
    parser.add_argument(
        "--supersede-prior",
        action="store_true",
        help="After submitting a new signed PR, close older open PRs by the same writer for the same Issue/request",
    )
    parser.add_argument(
        "--auto-integrate",
        action="store_true",
        help="Automatically integrate current main before signing when write/read paths do not overlap",
    )
    parser.add_argument(
        "--reads-file",
        type=Path,
        help="Optional JSON array of repository-relative read dependency paths for overlap checks",
    )
    parser.add_argument("--issue", type=int)
    parser.add_argument("--request-id")
    parser.add_argument("--title")
    parser.add_argument("--notes-file", type=Path, help="PR scope, business checks and review evidence")
    args = parser.parse_args()
    if args.close_superseded and args.rebind_pr is None:
        parser.error("--close-superseded requires --rebind-pr")
    if args.queue:
        if (
            args.inspect_pr is not None
            or args.rebind_pr is not None
            or args.prune_superseded
            or args.supersede_prior
            or args.auto_integrate
            or any(
                value is not None
                for value in (args.reads_file, args.issue, args.request_id, args.title, args.notes_file)
            )
        ):
            parser.error("--queue takes no submission or mutation arguments")
        print(json.dumps(queue_snapshot(args.repo.resolve()), ensure_ascii=False))
        return
    if args.prune_superseded:
        if (
            args.inspect_pr is not None
            or args.rebind_pr is not None
            or args.supersede_prior
            or args.auto_integrate
            or any(value is not None for value in (args.reads_file, args.title, args.notes_file))
        ):
            parser.error("--prune-superseded accepts only optional --issue and --request-id filters")
        print(
            json.dumps(
                prune_own_superseded(args.repo.resolve(), issue=args.issue, request_id=args.request_id),
                ensure_ascii=False,
            )
        )
        return
    if args.inspect_pr is not None:
        if (
            args.inspect_pr < 1
            or any(
                value is not None
                for value in (args.rebind_pr, args.reads_file, args.issue, args.request_id, args.title, args.notes_file)
            )
            or args.auto_integrate
            or args.supersede_prior
        ):
            parser.error("--inspect-pr requires a positive PR number and no submission arguments")
        repo = args.repo.resolve()
        repository = work_items.config(repo)[0]["repository"]
        issue_gate.check_repository(repo, repository)
        report = inspect_pr(repo, repository, args.inspect_pr)
        # A verified merge/acceptance readback is the event that advances a
        # host-owned editor's stable startup entry. No timer or PR prose grants it.
        try:
            report["engine_launch_activation"] = engine_launch_activation(repo, report)
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            report["engine_launch_activation"] = {"state": "pending", "error": "activation_adapter_failed"}
        print(json.dumps(report, ensure_ascii=False))
        return
    if args.rebind_pr is not None:
        if (
            args.rebind_pr < 1
            or any(value is not None for value in (args.issue, args.request_id, args.title, args.notes_file))
            or args.auto_integrate
            or args.supersede_prior
        ):
            parser.error("--rebind-pr requires a positive PR number and no manual submission arguments")
        reads = _load_reads_file(args.reads_file)
        result = rebind_pr(
            args.repo.resolve(),
            args.rebind_pr,
            close_superseded=args.close_superseded,
            reads=reads,
        )
        if result.get("rebound"):
            from kuafu_incident import observe_success

            observe_success(args.repo.resolve(), result["issue"], result["request_id"], "delivery", result)
        print(json.dumps(result, ensure_ascii=False))
        return
    if not (args.issue and args.request_id and args.title and args.notes_file):
        parser.error("submission requires --issue, --request-id, --title and --notes-file")
    try:
        reads = _load_reads_file(args.reads_file)
        notes = args.notes_file.read_text(encoding="utf-8-sig")
        require(
            args.title.strip()
            and "\n" not in args.title
            and notes.strip()
            and not re.search(r"^GongGong-(Issue|Request):", notes, re.M),
            "Provide a title and PR validation notes",
        )
        result = submit(
            args.repo.resolve(),
            args.issue,
            args.request_id,
            args.title,
            notes,
            auto_integrate=args.auto_integrate,
            reads=reads,
            supersede_prior=args.supersede_prior,
        )
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
