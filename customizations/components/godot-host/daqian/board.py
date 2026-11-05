"""Project existing GitHub Issue identities and dependency references into Godot UI data."""
import argparse
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from repository_access import AccessDenied, collaborator, configured_login, work_items


def source_plan(issue, request_id):
    """Project only explicit Yanshi clauses from this exact work order."""
    source = issue["html_url"]
    nodes = {"requirement": {"kind": "text", "title": "需求", "value": issue["title"]}}
    evidence = {"requirement": source}
    questions = {}
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
            if heading == "待确认":
                if value.startswith(("【图片】", "[图片]", "请提供截图", "请上传截图")):
                    kind, title = "image", "待补图片"
                    questions[identity] = {"kind":"image","prompt":value}
                elif value.startswith(("【选择】","[选择]")) and "|" in value:
                    prompt, *options = [v.strip() for v in value.split("|")]
                    questions[identity] = {"kind":"choice","prompt":prompt,"options":list(dict.fromkeys(v for v in options if v))}
                elif value.startswith(("【确认】","[确认]")):
                    questions[identity] = {"kind":"confirmation","prompt":value,"options":["同意本项","退回修改"]}
                else:
                    questions[identity] = {"kind":"text","prompt":value}
            nodes[identity] = {"kind": kind, "title": title, "value": "" if kind=="image" else value}
            evidence[identity] = source + " · " + heading
            # Scope clauses are planned tasks, not actual launches or approved gates.
            if kind == "task":
                edges.append({"from": "requirement", "to": identity, "kind": "data"})
    result={"plan":{"nodes":nodes,"edges":edges},"sources":evidence}
    if questions:
        result["questions"]=questions
    return result


def read_board(root, follows, actor=None):
    settings, _ = work_items.config(root)
    repo = settings["repository"]
    base = f"repos/{repo}/issues"
    actor = actor or collaborator(root)
    login = actor["login"]

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
        item["pending_count"] = len(item.get("questions",{})) if row["state"]=="open" else 0
        item["decision"] = item["decision"] or item["pending_count"]>0
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
    return {"repo": repo, "login": login, "user_id": actor["user_id"], "repo_id": actor["repo_id"], "issues": sorted(items.values(), key=lambda row: row["number"]),
            "verified_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--follow", nargs="*", type=int, default=[])
    parser.add_argument("--access-only",action="store_true")
    parser.add_argument("--expected-user",default="")
    args = parser.parse_args()
    try:
        if any(n <= 0 for n in args.follow):
            raise ValueError("工单编号必须为正整数")
        actor=collaborator(args.repo)
        if args.expected_user and actor["user_id"]!=args.expected_user:
            raise AccessDenied("当前登录账号已切换")
        if args.access_only:
            result={"access":actor}
        else:
            board=read_board(args.repo,args.follow,actor)
            if not os.environ.get("DAQIAN_PLAN_SSH_HOST"):
                import plan_store
                with plan_store.connect(args.repo.resolve()) as db:
                    for item in board["issues"]:
                        if item["closed"]:
                            continue
                        source={"issue":item["url"],"base":item["plan"],"sources":item["sources"],"source_revision":"projection",
                                "questions":item.get("questions",{}),"can_edit":False}
                        view=plan_store.snapshot(db,source)
                        ctx=view["context"]
                        count=len(ctx["questions"])-len(ctx["answers"])
                        item["pending_count"]=count
                        item["decision"]=count>0 or (item["status"]=="needs-decision" and not ctx["answers"])
            result={"board":board}
    except AccessDenied as error:
        result={"denied":True,"error":str(error)}
    except work_items.GitHubCommandError as error:
        reason=str(error)
        offline=reason.startswith(("GITHUB_NETWORK","GITHUB_TIMEOUT"))
        result={"denied":not offline,"offline_login":configured_login() if offline else "","error":reason}
    except (ValueError, OSError, KeyError) as error:
        result = {"denied":True,"error":"读取工单来源失败"}
    temporary = args.result.with_suffix(".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, args.result)


if __name__ == "__main__":
    main()
