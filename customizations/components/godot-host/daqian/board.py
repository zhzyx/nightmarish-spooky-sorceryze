"""Project existing GitHub Issue identities and dependency references into Godot UI data."""
import argparse
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import shutil

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "issue-workorders"))
import work_items


# GUI-launched editors often have a smaller PATH than the user's terminal.
if not os.environ.get("GONGGONG_GH") and not shutil.which("gh"):
    if os.name == "nt":
        candidates = [Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "GitHub CLI" / "gh.exe"]
    else:
        candidates = [Path.home()/".local/bin/gh", Path("/opt/homebrew/bin/gh"), Path("/usr/local/bin/gh")]
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            os.environ["GONGGONG_GH"] = str(candidate)
            break

def source_plan(issue, request_id):
    """Project only explicit Yanshi clauses from this exact work order."""
    source = issue["html_url"]
    nodes = {"requirement": {"kind": "text", "title": "需求", "value": issue["title"]}}
    evidence = {"requirement": source}
    edges = []
    heading = ""
    clauses = {"范围": ("task", "预计任务"), "验收条件": ("join", "验收条件"), "待确认": ("question", "待确认")}
    for line in (issue.get("body") or "").splitlines():
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
        elif request_id and heading in clauses and line.startswith("- "):
            value = line[2:].strip()
            if not value or value in {"无", "暂无"}:
                continue
            kind, title = clauses[heading]
            identity = "s_" + hashlib.sha256((source + heading + value).encode()).hexdigest()[:24]
            if identity in nodes:
                continue
            nodes[identity] = {"kind": kind, "title": title, "value": value}
            evidence[identity] = source + " · " + heading
            # Scope clauses are planned tasks, not actual launches or approved gates.
            if kind == "task":
                edges.append({"from": "requirement", "to": identity, "kind": "data"})
    return {"plan": {"nodes": nodes, "edges": edges}, "sources": evidence}


def read_board(root, follows):
    settings, _ = work_items.config(root)
    repo = settings["repository"]
    base = f"repos/{repo}/issues"
    login = json.loads(work_items.gh("api", "user"))["login"]

    def pages(url):
        raw = json.loads(work_items.gh("api", url, "--paginate", "--slurp"))
        return [item for page in raw for item in page]

    def local_number(row):
        if row.get("pull_request") or row.get("html_url") != f"https://github.com/{repo}/issues/{row['number']}":
            raise ValueError("来源工单与当前仓库不匹配")
        return row["number"]

    assigned = pages(f"{base}?assignee={login}&state=open&per_page=100")
    queue = {local_number(row): row for row in assigned if "pull_request" not in row}
    for num in follows:
        if num not in queue:
            row = json.loads(work_items.gh("api", f"{base}/{num}"))
            local_number(row)
            if row["state"] == "open":
                queue[num] = row
    items = {}
    while queue:
        number, row = queue.popitem()
        if number in items:
            continue
        labels = [label["name"] for label in row["labels"]]
        statuses = [v.removeprefix("status:") for v in labels if v.startswith("status:")]
        status = statuses[0] if len(statuses) == 1 else row["state"]
        markers = sorted(work_items.request_ids(row.get("body")))
        item = {
            "number": number, "title": row["title"], "status": status, "url": row["html_url"],
            "updated": row["updated_at"], "owners": [x["login"] for x in row["assignees"]],
            "request": markers[0] if len(markers) == 1 else "", "dependencies": [],
            "decision": status == "needs-decision", "closed": row["state"] == "closed",
        }
        item.update(source_plan(row, item["request"]))
        items[number] = item
        # GitHub only returns a summary on some endpoint/API versions.
        summary = row.get("issue_dependencies_summary", {})
        if summary.get("total_blocked_by") == 0:
            continue
        for dependency in pages(f"{base}/{number}/dependencies/blocked_by?per_page=100"):
            url = dependency["html_url"]
            item["dependencies"].append(url)
            if dependency.get("repository_url") == f"https://api.github.com/repos/{repo}":
                key = local_number(dependency)
                if key not in items:
                    queue[key] = dependency
    return {"repo": repo, "login": login, "issues": sorted(items.values(), key=lambda row: row["number"]),
            "verified_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--follow", nargs="*", type=int, default=[])
    args = parser.parse_args()
    try:
        if any(n <= 0 for n in args.follow):
            raise ValueError("工单编号必须为正整数")
        result = {"board": read_board(args.repo, args.follow)}
    except (ValueError, OSError, KeyError) as error:
        result = {"error": str(error) if isinstance(error, work_items.GitHubCommandError) else "读取工单来源失败"}
    temporary = args.result.with_suffix(".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, args.result)


if __name__ == "__main__":
    main()
