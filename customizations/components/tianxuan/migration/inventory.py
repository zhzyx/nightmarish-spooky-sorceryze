"""Create a read-only historical inventory pinned to an explicit Git revision."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

UPLOAD = re.compile(
    r"https://(?:github\.com/(?:user-attachments/|[^/\s]+/[^/\s]+/(?:files|assets)/)|user-images\.githubusercontent\.com/)[^\s<>)\"\]]+"
)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def record_line(source_id, kind, content, relations):
    row = dict(
        source_id=source_id,
        kind=kind,
        content=content,
        relations=sorted(set(relations)),
        mode="record_only",
        sha256=hashlib.sha256(canonical(content)).hexdigest(),
    )
    return canonical(row) + b"\n"


def command(*args):
    if args[0] != "gh":
        return subprocess.check_output(args)
    env = {**os.environ, "GODEBUG": "http2client=0"}
    for attempt in range(4):
        try:
            return subprocess.check_output(args, env=env, stderr=subprocess.PIPE, timeout=90)
        except subprocess.CalledProcessError as exc:
            msg = exc.stderr.decode(errors="replace")
            if attempt == 3 or not any(
                t in msg.lower() for t in ("stream error", "timeout", "eof", "502", "503", "504", "reset", "429")
            ):
                raise RuntimeError(msg[:500]) from exc
        except subprocess.TimeoutExpired:
            if attempt == 3:
                raise
        time.sleep(2**attempt)


def collect(repo, source, revision, output):
    started_at = datetime.now(timezone.utc).isoformat()

    def git(*args):
        return command("git", "-C", str(repo), *args)

    sha = git("rev-parse", "--verify", revision + "^{commit}").decode().strip()
    if git("rev-parse", "--is-shallow-repository").strip() == b"true":
        raise ValueError("Full history requires a non-shallow checkout")
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", source):
        raise ValueError("Invalid GitHub repository")
    output.mkdir(parents=True, exist_ok=True)
    prefix = "github:" + source + "/"
    fetch_url = git("remote", "get-url", "origin").decode().strip().removesuffix(".git")
    if fetch_url.casefold() not in (f"https://github.com/{source}".casefold(), f"git@github.com:{source}".casefold()):
        raise ValueError("Git checkout and GitHub source differ")
    counts = Counter()
    seen = set()
    pull_numbers = set()
    issue_numbers = set()
    attachments = set()
    stream_hash = hashlib.sha256()
    stage = output / "records.jsonl.partial"
    with stage.open("wb") as stream:

        def record(kind, key, content, relations=()):
            source_id = prefix + kind + "/" + str(key)
            if source_id in seen:
                raise ValueError("Duplicate source in paginated inventory: " + source_id)
            seen.add(source_id)
            line = record_line(source_id, kind, content, relations)
            stream.write(line)
            stream_hash.update(line)
            counts[kind] += 1
            return source_id

        for line in git("rev-list", "--parents", "--topo-order", sha).decode().splitlines():
            commit, *parents = line.split()
            record(
                "commit",
                commit,
                {"oid": commit, "parents": parents},
                [prefix + "commit/" + parent for parent in parents],
            )
        for entry in git("ls-tree", "-r", "-z", sha, "--", "design-docs").split(b"\0"):
            if entry:
                header, path = entry.split(b"\t", 1)
                _, _, oid = header.decode().split()
                name = path.decode("utf-8")
                record("requirement", name, {"path": name, "blob": oid, "commit": sha}, [prefix + "commit/" + sha])
        endpoints = (
            ("issues?state=all&sort=created&direction=asc", "issue"),
            ("pulls?state=all&sort=created&direction=asc", "pull"),
            ("issues/comments", "issue_comment"),
            ("pulls/comments", "review_comment"),
            ("comments", "commit_comment"),
        )

        def pages(endpoint, refresh=False):
            join = "&" if "?" in endpoint else "?"
            for page in range(1, 1000000):
                url = "repos/" + source + "/" + endpoint + f"{join}per_page=100&page={page}"
                cache = output / ".pages" / hashlib.sha256((sha + url).encode()).hexdigest()
                if refresh or not cache.is_file():
                    data = command("gh", "api", url)
                    rows = json.loads(data)
                    cache.parent.mkdir(exist_ok=True)
                    temp = cache.with_suffix(".partial")
                    temp.write_bytes(data)
                    os.replace(temp, cache)
                else:
                    rows = json.loads(cache.read_bytes())
                yield from rows
                if len(rows) < 100:
                    return
            raise RuntimeError("GitHub pagination limit exceeded")

        def target(number):
            kind = "pull" if int(number) in pull_numbers else "issue"
            return prefix + kind + "/" + str(number)

        def body_links(row, links):
            body = row.get("body") or ""
            for match in re.finditer(r"(?<![\w/])(?:([\w.-]+/[\w.-]+))?#(\d+)\b", body):
                other, number = match.groups()
                if other and other.casefold() != source.casefold():
                    continue
                if int(number) in issue_numbers or int(number) in pull_numbers:
                    links.append(target(number))
            for url in UPLOAD.findall(body):
                key = hashlib.sha256(url.encode()).hexdigest()
                if url not in attachments:
                    attachments.add(url)
                    record("attachment", key, {"url": url})
                links.append(prefix + "attachment/" + key)

        def index_tickets(refresh=False):
            # All ticket numbers share the same namespace in GitHub.
            return {
                r["number"]: "pull" if "pull_request" in r else "issue"
                for r in pages("issues?state=all&sort=created&direction=asc", refresh)
            }

        checkpoint = output / ".pages" / "tickets.json"
        if checkpoint.is_file():
            bound = json.loads(checkpoint.read_bytes())
            if bound["source"] != source or bound["revision"] != sha:
                raise RuntimeError("Checkpoint belongs to another source")
            tickets = {int(k): v for k, v in bound["tickets"].items()}
        else:
            tickets = index_tickets()
            checkpoint.parent.mkdir(exist_ok=True)
            pending = checkpoint.with_suffix(".partial")
            pending.write_bytes(canonical(dict(source=source, revision=sha, tickets=tickets)))
            os.replace(pending, checkpoint)
        pull_numbers.update(k for k, v in tickets.items() if v == "pull")
        issue_numbers.update(k for k, v in tickets.items() if v == "issue")
        for endpoint, kind in endpoints:
            for row in pages(endpoint):
                if kind in ("issue", "pull") and row["number"] not in tickets:
                    continue
                parent_url = row.get("issue_url") or row.get("pull_request_url")
                if parent_url and int(parent_url.rsplit("/", 1)[1]) not in tickets:
                    continue
                if kind == "issue" and "pull_request" in row:
                    record("pull_issue_projection", row["number"], row, [target(row["number"])])
                    continue
                links = []
                for field in ("issue_url", "pull_request_url"):
                    if row.get(field):
                        route, number = row[field].rsplit("/", 2)[-2:]
                        if number.isdigit():
                            links.append(target(number))
                if row.get("commit_id"):
                    links.append(prefix + "commit/" + row["commit_id"])
                if row.get("in_reply_to_id"):
                    links.append(prefix + "review_comment/" + str(row["in_reply_to_id"]))
                if row.get("pull_request_review_id"):
                    links.append(prefix + "review/" + str(row["pull_request_review_id"]))
                body_links(row, links)
                record(kind, row.get("number", row["id"]), row, links)

        owner, name = source.split("/")
        query = """query($owner:String!, $name:String!, $cursor:String) {
          repository(owner:$owner,name:$name) {pullRequests(first:50,after:$cursor) {
          nodes {number reviews(first:100) {nodes {databaseId id url body state submittedAt
          author {login} commit {oid}} pageInfo {hasNextPage}}}
          pageInfo {hasNextPage endCursor}}}}"""
        cursor = None
        while True:
            args = ["gh", "api", "graphql", "-f", "query=" + query, "-f", "owner=" + owner, "-f", "name=" + name]
            if cursor:
                args.extend(["-f", "cursor=" + cursor])
            result = json.loads(command(*args))["data"]["repository"]["pullRequests"]
            for pr in result["nodes"]:
                number = pr["number"]
                if number not in tickets:
                    continue
                reviews = pr["reviews"]
                rows = pages(f"pulls/{number}/reviews") if reviews["pageInfo"]["hasNextPage"] else reviews["nodes"]
                for review in rows:
                    links = [target(number)]
                    review_oid = review.get("commit_id") or (review.get("commit") or {}).get("oid")
                    if review_oid:
                        links.append(prefix + "commit/" + review_oid)
                    body_links(review, links)
                    record("review", review.get("databaseId") or review["id"], review, links)
            if not result["pageInfo"]["hasNextPage"]:
                break
            cursor = result["pageInfo"]["endCursor"]
        observed = {key for key in seen if key.startswith((prefix + "issue/", prefix + "pull/"))}
        after = index_tickets(True)
        if observed != {target(number) for number in tickets} or any(after.get(n) != k for n, k in tickets.items()):
            raise RuntimeError("Issue/PR membership changed during enumeration. Refresh inventory.")

    digest = stream_hash.hexdigest()
    os.replace(stage, output / "records.base.jsonl")
    report = dict(
        source=source,
        revision=sha,
        counts=dict(counts),
        records_sha256=digest,
        collection_started=started_at,
        historical_policy="record_only",
        coverage="revision ancestry, design-docs tree, GitHub REST issues, pulls, issue and review and commit comments, referenced GitHub upload URLs",
    )
    temp = output / "report.json.partial"
    temp.write_bytes(canonical(report) + b"\n")
    os.replace(temp, output / "report.base.json")
    return report


def pull_commits(source):
    owner, name = source.split("/")
    fields = "nodes{commit{oid}} pageInfo{hasNextPage endCursor}"
    root = "repository(owner:$owner,name:$name)"
    query = (
        "query($owner:String!,$name:String!,$cursor:String){"
        + root
        + "{pullRequests(first:50,after:$cursor){nodes{number commits(first:100){"
        + fields
        + "}}pageInfo{hasNextPage endCursor}}}}"
    )
    more = (
        "query($owner:String!,$name:String!,$number:Int!,$cursor:String!){"
        + root
        + "{pullRequest(number:$number){commits(first:100,after:$cursor){"
        + fields
        + "}}}}"
    )
    args = ["gh", "api", "graphql", "-f", "owner=" + owner, "-f", "name=" + name]
    cursor = None
    commits = {}
    while True:
        page = ["-f", "cursor=" + cursor] if cursor else []
        result = json.loads(command(*args, "-f", "query=" + query, *page))
        connection = result["data"]["repository"]["pullRequests"]
        for pr in connection["nodes"]:
            rows = pr["commits"]
            ids = []
            while True:
                ids.extend(node["commit"]["oid"] for node in rows["nodes"])
                if not rows["pageInfo"]["hasNextPage"]:
                    break
                next_page = json.loads(
                    command(
                        *args,
                        "-f",
                        "query=" + more,
                        "-F",
                        "number=" + str(pr["number"]),
                        "-f",
                        "cursor=" + rows["pageInfo"]["endCursor"],
                    )
                )
                rows = next_page["data"]["repository"]["pullRequest"]["commits"]
            commits[pr["number"]] = ids
        if not connection["pageInfo"]["hasNextPage"]:
            return commits
        cursor = connection["pageInfo"]["endCursor"]


def document_uploads(repo, revision):
    pattern = r"github\.com/(user-attachments/|[^/ ]+/[^/ ]+/(files|assets)/)|user-images\.githubusercontent\.com/"
    result = subprocess.run(
        ["git", "-C", str(repo), "grep", "-Ilz", "-E", pattern, revision, "--", ":(glob)**/README*", "design-docs"],
        capture_output=True,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.decode(errors="replace"))
    for obj in result.stdout.decode().split("\0"):
        if obj:
            doc = command("git", "-C", str(repo), "show", obj).decode(errors="replace")
            for url in set(UPLOAD.findall(doc)):
                yield obj.split(":", 1)[1], url


def enrich(output, repo):
    """Resolve structured GitHub edges after a completed base enumeration."""
    report_file = output / "report.json"
    report = json.loads((output / "report.base.json").read_bytes())
    source = report["source"]
    owner, name = source.split("/")
    prefix = "github:" + source + "/"
    query = """query($owner:String!, $name:String!, $cursor:String) {
      repository(owner:$owner,name:$name) {issues(first:50,after:$cursor) {
      nodes {number parent {number repository{nameWithOwner}}
      blockedBy(first:100){nodes{number repository{nameWithOwner}} pageInfo{hasNextPage endCursor}}}
      pageInfo{endCursor hasNextPage}}}}"""
    edges = {}
    cursor = None
    while True:
        args = ["gh", "api", "graphql", "-f", "query=" + query, "-f", "owner=" + owner, "-f", "name=" + name]
        if cursor:
            args.extend(["-f", "cursor=" + cursor])
        result = json.loads(command(*args))["data"]["repository"]["issues"]
        for ticket in result["nodes"]:

            def ref(item):
                return f"github:{item['repository']['nameWithOwner']}/issue/{item['number']}"

            blockers = ticket["blockedBy"]
            dependencies = []
            while True:
                dependencies.extend(ref(item) for item in blockers["nodes"])
                if not blockers["pageInfo"]["hasNextPage"]:
                    break
                more = """query($owner:String!,$name:String!,$number:Int!,$cursor:String!) {
                  repository(owner:$owner,name:$name){issue(number:$number){
                  blockedBy(first:100,after:$cursor){nodes{number repository{nameWithOwner}}
                  pageInfo{hasNextPage endCursor}}}}}"""
                data = command(
                    "gh",
                    "api",
                    "graphql",
                    "-f",
                    "query=" + more,
                    "-f",
                    "owner=" + owner,
                    "-f",
                    "name=" + name,
                    "-F",
                    "number=" + str(ticket["number"]),
                    "-f",
                    "cursor=" + blockers["pageInfo"]["endCursor"],
                )
                blockers = json.loads(data)["data"]["repository"]["issue"]["blockedBy"]
            edges[ticket["number"]] = {
                "parent": ref(ticket["parent"]) if ticket["parent"] else None,
                "blocked_by": sorted(dependencies),
            }
        if not result["pageInfo"]["hasNextPage"]:
            break
        cursor = result["pageInfo"]["endCursor"]
    pr_commits = pull_commits(source)
    records = output / "records.jsonl"
    stage = output / "enriched.partial"
    docs = {}
    for path, url in document_uploads(repo, report["revision"]):
        docs.setdefault(url, []).append(path)
    known_uploads = set()
    counts = Counter()
    previous = hashlib.sha256()
    digest = hashlib.sha256()
    with (output / "records.base.jsonl").open("rb") as src, stage.open("wb") as dst:
        for line in src:
            previous.update(line)
            row = json.loads(line)
            content = row["content"]
            if row["kind"] == "attachment":
                known_uploads.add(content["url"])
            links = set(row["relations"])
            if row["kind"] == "requirement":
                for url, paths in docs.items():
                    if content["path"] in paths:
                        links.add(prefix + "attachment/" + hashlib.sha256(url.encode()).hexdigest())
            counts[row["kind"]] += 1
            if row["kind"] == "issue":
                edge = edges.pop(content["number"])
                content["migration_issue_relationships"] = edge
                links.update(edge["blocked_by"])
                if edge["parent"]:
                    links.add(edge["parent"])
            elif row["kind"] == "pull":
                commits = pr_commits.pop(content["number"])
                content["migration_commits"] = commits
                links.update(prefix + "commit/" + oid for oid in commits)
                for commit in (content.get("merge_commit_sha"), content["head"].get("sha"), content["base"].get("sha")):
                    if commit:
                        links.add(prefix + "commit/" + commit)
            links.discard(row["source_id"])
            row["relations"] = sorted(links)
            row["sha256"] = hashlib.sha256(canonical(content)).hexdigest()
            new_line = canonical(row) + b"\n"
            digest.update(new_line)
            dst.write(new_line)
        for url in sorted(docs.keys() - known_uploads):
            content = {"url": url}
            key = hashlib.sha256(url.encode()).hexdigest()
            row = dict(
                kind="attachment",
                source_id=prefix + "attachment/" + key,
                mode="record_only",
                relations=[prefix + "commit/" + report["revision"]],
                content=content,
                sha256=hashlib.sha256(canonical(content)).hexdigest(),
            )
            data = canonical(row) + b"\n"
            dst.write(data)
            digest.update(data)
            counts["attachment"] += 1
    if previous.hexdigest() != report["records_sha256"]:
        raise RuntimeError("Inventory membership or digest changed before enrichment")
    os.replace(stage, records)
    report["records_sha256"] = digest.hexdigest()
    report["coverage"] = (
        "pinned revision ancestry and design-docs tree; GitHub issues and PRs "
        "including issue projection; conversation, review and commit comments, "
        "review summaries, parent and blocker edges, PR commit membership, "
        "upload URLs from ticket, PR, review and comment bodies"
    )
    report["newer_tickets_outside_initial_membership"] = sorted(set(edges) | set(pr_commits))
    report["counts"] = dict(counts)
    report["collected_through"] = datetime.now(timezone.utc).isoformat()
    report["consistency"] = "Git revision immutable; GitHub paginated reads span a live collection window"
    report["document_upload_sources"] = docs
    report["document_upload_scan"] = "design-docs and README files in revision tree"
    report["attachment_scope"] = "GitHub-hosted upload URLs extracted from Markdown/HTML bodies"
    temp = output / "report.json.partial"
    temp.write_bytes(canonical(report) + b"\n")
    os.replace(temp, report_file)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--source", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--enrich-existing", action="store_true")
    args = parser.parse_args()
    if args.enrich_existing:
        existing = json.loads((args.output / "report.base.json").read_bytes())
        revision = (
            command("git", "-C", str(args.repo), "rev-parse", "--verify", args.revision + "^{commit}").decode().strip()
        )
        if existing["source"] != args.source or existing["revision"] != revision:
            raise ValueError("Existing inventory does not match source and revision")
    else:
        collect(args.repo, args.source, args.revision, args.output)
    print(json.dumps(enrich(args.output, args.repo), ensure_ascii=False))
