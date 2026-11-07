"""Project existing GitHub Issue identities and dependency references into Godot UI data."""

import argparse
import hashlib
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import board_delta
import progress
from repository_access import (
    AccessDenied,
    SessionChanged,
    collaborator,
    configured_login,
    session_actor,
    session_path,
    work_items,
)


def source_plan(issue, request_id):
    """Project only explicit Yanshi clauses from this exact work order."""
    source = issue["html_url"]
    nodes = {"requirement": {"kind": "text", "title": "需求", "value": issue["title"]}}
    evidence = {"requirement": source}
    if re.fullmatch(r"daqian-direct-[a-f0-9]{20}", request_id or ""):
        # A directly submitted requirement can itself contain example Yanshi headings.
        # Display the original as one input rather than generating clauses from those headings.
        body = (issue.get("body") or "").replace("\r\n", "\n")
        if "<!-- gonggong-intake:daqian-direct -->" in body:
            _, heading, original = body.partition("\n\n## 原始需求\n\n")
            original, suffix, _ = original.rpartition("\n\n<!-- gonggong-host-git:")
            if heading and suffix:
                nodes["requirement"]["value"] = original.removesuffix("\n")
        return {"plan": {"nodes": nodes, "edges": []}, "sources": evidence}
    questions = {}
    edges = []
    heading = ""
    clauses = {"范围": ("task", "预计任务"), "验收条件": ("join", "验收条件"), "待确认": ("question", "待确认")}
    for section in ("范围与验收", "范围和验收"):
        clauses[section] = ("task", "范围与验收")
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
                    questions[identity] = {"kind": "image", "prompt": value}
                elif value.startswith(("【选择】", "[选择]")) and "|" in value:
                    prompt, *options = [v.strip() for v in value.split("|")]
                    questions[identity] = {
                        "kind": "choice",
                        "prompt": prompt,
                        "options": list(dict.fromkeys(v for v in options if v)),
                    }
                elif value.startswith(("【确认】", "[确认]")):
                    questions[identity] = {"kind": "confirmation", "prompt": value, "options": ["同意本项", "退回修改"]}
                else:
                    questions[identity] = {"kind": "text", "prompt": value}
            nodes[identity] = {"kind": kind, "title": title, "value": "" if kind == "image" else value}
            evidence[identity] = source + " · " + heading
            # Scope clauses are planned tasks, not actual launches or approved gates.
            if kind == "task":
                edges.append({"from": "requirement", "to": identity, "kind": "data"})
    result = {"plan": {"nodes": nodes, "edges": edges}, "sources": evidence}
    if questions:
        result["questions"] = questions
    return result


def design_document(root, body):
    """Read the document named by the work-order envelope, or its published copy."""
    match = re.match(
        r"^<!-- (?:gonggong|olympus)-request:[a-z0-9-]+ -->\n\n需求文档：`(design-docs/[^`\n]+\.md)`\n\n",
        (body or "").replace("\r\n", "\n"),
    )
    if not match:
        return {}
    relative = match[1]
    parts = relative.split("/")
    if any(part in ("", ".", "..") or "\\" in part or ":" in part for part in parts):
        return {}
    try:
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve() / "design-docs"):
            return {}
        if path.is_file() and path.stat().st_size <= 512 * 1024:
            return {"path": relative, "markdown": path.read_text(encoding="utf-8"), "source": "工作区"}
    except (OSError, RuntimeError, UnicodeError):
        pass
    snapshot = match.string[match.end() :].rsplit("\n\n<!-- gonggong-host-git:", 1)[0]
    snapshot = snapshot.rsplit("\n\n执行授权来源（由调用宿主核实，不代替候选准入）：", 1)[0]
    return {"path": relative, "markdown": snapshot.rstrip(), "source": "工单发布版本"}


def project_row(root, receipts, actor, row):
    number = row["number"]
    repo = actor["repo"]
    labels = [label["name"] for label in row["labels"]]
    statuses = [v.removeprefix("status:") for v in labels if v.startswith("status:")]
    status = statuses[0] if len(statuses) == 1 else row["state"]
    markers = sorted(work_items.request_ids(row.get("body")))
    item = {
        "number": number,
        "title": row["title"],
        "status": status,
        "url": row["html_url"],
        "updated": row["updated_at"],
        "creator": (row.get("user") or {}).get("login") or "",
        "owners": [x["login"] for x in row["assignees"]],
        "request": markers[0] if len(markers) == 1 else "",
        "dependencies": [],
        "development": "type:development" in labels,
        "categories": sorted({v[5:] for v in labels if v.startswith("type:") and v[5:]}),
        "analyzed": (
            len(markers) == 1
            and re.fullmatch(r"requirement-[0-9a-f]{32}", markers[0]) is not None
            and bool(
                re.search(
                    r"^需求整理：Yanshi / ClarifyFeature；原始输入摘要：`" + markers[0][12:] + r"[0-9a-f]{32}`。$",
                    (row.get("body") or "").replace("\r\n", "\n"),
                    re.MULTILINE,
                )
            )
        ),
        "closed": row["state"] == "closed",
    }
    if item["request"] and not item["request"].startswith("daqian-direct-"):
        item["source_sha256"] = progress.issue_route.digest([item["url"], item["request"], item["updated"]])
    item["design_document"] = design_document(root, row.get("body")) if item["request"] else {}
    item["routing_receipt"] = progress.route_for_row(root, receipts, actor, row, item)
    item["workers"] = progress.workers_for_row(receipts, repo, row, item)
    item.update(source_plan(row, item["request"]))
    item["pending_count"] = len(item.get("questions", {})) if row["state"] == "open" else 0
    item["decision"] = item["pending_count"] > 0
    return item


def read_board(root, follows, actor=None, *, project=False, personal_history=False, sources=None):
    settings, _ = work_items.config(root)
    repo = settings["repository"]
    base = f"repos/{repo}/issues"
    actor = actor or collaborator(root)
    if actor["repo"] != repo:
        raise AccessDenied("已绑定的仓库已切换")
    login = actor["login"]

    def pages(url):
        raw = json.loads(work_items.gh("api", url, "--paginate", "--slurp"))
        return [item for page in raw for item in page]

    def local_number(row):
        if row.get("pull_request") or row.get("html_url") != f"https://github.com/{repo}/issues/{row['number']}":
            raise ValueError("来源工单与当前仓库不匹配")
        return row["number"]

    queue = {}
    state = "all" if personal_history else "open"
    urls = [f"{base}?{role}={login}&state={state}&per_page=100" for role in ("assignee", "creator")]
    if project:
        urls = [f"{base}?state=open&per_page=100"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        for rows in pool.map(pages, urls):
            for row in rows:
                if "pull_request" not in row:
                    queue[local_number(row)] = row
    for num in [] if project else follows:
        if num not in queue:
            row = json.loads(work_items.gh("api", f"{base}/{num}"))
            local_number(row)
            queue[num] = row
    receipts = progress.receipt_root(root)
    items = {}
    while queue:
        number, row = queue.popitem()
        if number in items:
            continue
        item = project_row(root, receipts, actor, row)
        if sources is not None:
            sources[number] = progress.dispatch_revision(row)
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
                if not project and key not in items:
                    queue[key] = dependency
    return {
        "repo": repo,
        "login": login,
        "user_id": actor["user_id"],
        "repo_id": actor["repo_id"],
        "issues": sorted(items.values(), key=lambda row: row["number"]),
        "verified_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def plan_summary(db, item):
    if item["closed"]:
        return {}
    import plan_store

    source = {
        "issue": item["url"],
        "base": item["plan"],
        "sources": item["sources"],
        "source_revision": "projection",
        "questions": item.get("questions", {}),
        "can_edit": False,
    }
    view = plan_store.snapshot(db, source)
    ctx = view["context"]
    can_answer = bool(item["request"]) and item["status"] in {"needs-decision", "in-progress", "in-review"}
    count = len(ctx["questions"]) - len(ctx["answers"]) if can_answer else 0
    return {
        "updated": item["updated"],
        "request": item["request"],
        "node_states": ctx["states"],
        "running_titles": [
            (node.get("value") or node["title"]).partition("\n")[0][:48] if node["kind"] == "task" else node["title"]
            for key, node in view["plan"]["nodes"].items()
            if ctx["states"].get(key) == "running"
        ],
        "pending_count": count,
        "decision": count > 0,
        "answered_count": len(ctx["answers"]),
    }


def publish(path, value):
    temporary = Path(str(path) + ".partial")
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--follow", nargs="*", type=int, default=[])
    parser.add_argument("--editor-session", default="")
    parser.add_argument("--end-session", action="store_true")
    parser.add_argument("--project", action="store_true")
    parser.add_argument("--personal-history", action="store_true")
    parser.add_argument("--access-only", action="store_true")
    parser.add_argument("--expected-user", default="")
    parser.add_argument("--delta", type=Path, help="Apply known issue changes to this editor session snapshot")
    args = parser.parse_args()
    try:
        if any(n <= 0 for n in args.follow):
            raise ValueError("工单编号必须为正整数")
        if args.end_session:
            session_path(args.editor_session).unlink(missing_ok=True)
            try:
                board_delta.cache_path(args.editor_session).unlink(missing_ok=True)
            except OSError:
                pass  # An exiting delta reader can still have the SQLite file open on Windows.
            return
        if args.result is None:
            parser.error("--result required")
        actor = session_actor(args.repo, args.editor_session, allow_login=args.access_only and not args.expected_user)
        if args.expected_user and actor["user_id"] != args.expected_user:
            raise AccessDenied("当前登录账号已切换")
        if args.access_only:
            result = {"access": actor}
        elif args.delta:
            if not args.editor_session or args.expected_user != actor["user_id"]:
                raise AccessDenied("增量读取必须绑定当前编辑器和账号")
            result = {"delta": board_delta.read_changes(args, actor)}
            if session_actor(args.repo, args.editor_session) != actor:
                raise AccessDenied("读取工单期间账号已切换")
        else:
            sources = {} if args.editor_session else None
            board = read_board(
                args.repo,
                args.follow,
                actor,
                project=args.project,
                personal_history=args.personal_history,
                sources=sources,
            )
            import plan_store

            remote = os.environ.get("DAQIAN_PLAN_SSH_HOST", "")
            if remote:
                import graph_host

                # The shared installation owns the answers. Its authenticated summary
                # covers custom plan questions as well as questions in the Issue.
                envelope = {
                    "action": "board-progress",
                    "repository": actor["repo"],
                    "repo_id": actor["repo_id"],
                    "expected_user": actor["user_id"],
                    "follow": args.follow,
                    "project": args.project,
                    "personal_history": args.personal_history,
                }
                try:
                    shared = graph_host.via_shared_host(remote, json.dumps(envelope).encode())
                except (ValueError, OSError):
                    shared = {}
                summaries = shared.get("summaries", {})
                for item in board["issues"]:
                    if item["closed"]:
                        continue
                    summary = summaries.get(item["url"], {})
                    if summary.get("updated") == item["updated"] and summary.get("request") == item["request"]:
                        item.update(summary)
                    else:
                        item.update(pending_count=0, decision=False, answers_unverified=True)
            else:
                with plan_store.connect(args.repo.resolve()) as db:
                    for item in board["issues"]:
                        item.update(plan_summary(db, item))
            if args.editor_session and session_actor(args.repo, args.editor_session) != actor:
                raise AccessDenied("读取工单期间 GitHub 账号已切换")
            import bridge

            receipts = progress.receipt_root(args.repo)
            node = bridge._igniter.discover_node(args.repo, bridge.host_environment(args.repo))
            result = {"board": board}
            if sources is not None and board_delta.seed(args, actor, sources, board["issues"]):
                result["delta_version"] = 1
            if receipts.is_dir() and node:
                result["watch"] = {"node": node, "directory": str(receipts)}
    except AccessDenied as error:
        if args.editor_session:
            session_path(args.editor_session).unlink(missing_ok=True)
        result = {"denied": True, "session_changed": isinstance(error, SessionChanged), "error": str(error)}
    except work_items.GitHubCommandError as error:
        if args.editor_session and error.http_status in (401, 403):
            session_path(args.editor_session).unlink(missing_ok=True)
        reason = str(error)
        offline = reason.startswith(("GITHUB_NETWORK", "GITHUB_TIMEOUT")) or error.http_status in (
            429,
            500,
            502,
            503,
            504,
        )
        result = {"denied": not offline, "offline_login": configured_login() if offline else "", "error": reason}
    except (ValueError, TypeError, OSError, KeyError):
        result = {"denied": True, "error": "读取工单来源失败"}
    publish(args.result, result)


if __name__ == "__main__":
    main()
