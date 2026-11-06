"""On-demand views over the configured repository. No mutation or background polling."""

import json
import re
import subprocess
from datetime import datetime, timezone
from math import ceil
from statistics import median
from urllib.parse import quote


def pages(gh, path):
    return [row for page in json.loads(gh("api", path, "--paginate", "--slurp")) for row in page]


def completed_revision(comments):
    """Read only complete Yanshi publications. A retry may interleave with another revision."""
    parts = {}
    complete = []
    ambiguous = set()
    for row in sorted(comments, key=lambda c: c["id"]):
        match = re.fullmatch(
            r"<!-- requirement-revision:([a-f0-9]{64})(?:-part-(\d{1,6}))? -->\n\n"
            r"Yanshi / ClarifyFeature 澄清更新(?:（(\d{1,6})/(\d{1,6})）)?\n\n(.*)",
            (row.get("body") or "").replace("\r\n", "\n"),
            re.S,
        )
        if not match or row.get("author_association") not in {"OWNER", "MEMBER", "COLLABORATOR"}:
            continue
        digest, marker_index, index, total, text = match.groups()
        index, total = int(index or 1), int(total or 1)
        if not 1 <= index <= total <= len(comments) or marker_index != (str(index) if index < total else None):
            continue
        key = (digest, row["user"]["login"], total)
        chunks = parts.setdefault(key, {})
        if index in chunks and chunks[index] != text:
            ambiguous.add(key)
        chunks[index] = text
        if index == total and len(chunks) == total:
            complete.append((key, "".join(chunks[i] for i in range(1, total + 1)), row))
    return next(((text, row) for key, text, row in reversed(complete) if key not in ambiguous), None)


def section(markdown, title):
    pattern = rf"^## {title}[ \t]*\n(.*?)(?=^#{{1,2}} |\Z)"
    found = re.search(pattern, markdown.replace("\r\n", "\n"), re.M | re.S)
    return found[1].split("<!--", 1)[0].strip() if found else ""


def design_extract(root, repository, path):
    # A Git blob pins the reader's source and cannot follow a worktree symlink.
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    blob = subprocess.run(["git", "-C", str(root), "show", f"{head}:{path}"], capture_output=True)
    if blob.returncode:
        return ["设计尚未进入当前检出版本，见工单发布正文。"]
    markdown = blob.stdout.decode("utf-8-sig")
    lines = [f"[设计原文 · {head[:8]}](https://github.com/{repository}/blob/{head}/{quote(path)})"]
    summary = section(markdown, "当前结论")
    if not summary:
        summary = "\n\n".join(line for line in markdown.splitlines() if line.startswith(("原始目标：", "当前结论：")))
    if summary:
        lines.extend(["", "## 设计内记录的结论", summary])
    return lines


def brief(gh, root, repository, number):
    base = f"repos/{repository}/issues/{number}"
    issue = json.loads(gh("api", base))
    if "pull_request" in issue or issue["number"] != number:
        raise ValueError("Expected the requested Issue")
    body = issue.get("body") or ""
    comments = pages(gh, base + "/comments?per_page=100") if issue["comments"] else []
    children = (
        pages(gh, base + "/sub_issues?per_page=100") if issue.get("sub_issues_summary", {}).get("total") != 0 else []
    )
    dependencies = (
        pages(gh, base + "/dependencies/blocked_by?per_page=100")
        if issue.get("issue_dependencies_summary", {}).get("total_blocked_by") != 0
        else []
    )
    revision = completed_revision(comments)
    url = issue["html_url"]
    source, reference = (revision[0], revision[1]["html_url"]) if revision else (body, url)
    statuses = [label["name"][7:] for label in issue["labels"] if label["name"].startswith("status:")]
    lines = [
        f"# #{number} {issue['title']}",
        "",
        f"工单状态：{issue['state_reason'] or issue['state']}。"
        + (" 标签：" + "、".join(statuses) + "。" if statuses else ""),
        "指派：" + ("、".join(a["login"] for a in issue["assignees"]) or "未指派"),
        f"[工单原文]({url})",
    ]
    path = re.match(
        r"^<!-- (?:gonggong|olympus)-request:[a-z0-9-]+ -->\n\n需求文档：`(design-docs/[^\n`]+\.md)`",
        body.replace("\r\n", "\n"),
    )
    if path and all(s not in ("", ".", "..") for s in path[1].split("/")) and "\\" not in path[1]:
        lines.extend(design_extract(root, repository, path[1]))
    conclusion = section(body, "当前结论")
    if conclusion:
        lines.extend(["", "## 工单正文记录的结论", conclusion])
    goal, separator, legacy_acceptance = source.partition("\n\n验收：\n") if revision else ("", "", "")
    if revision:
        lines.extend(["", f"[最近一次完整偃师澄清]({reference})", goal.split("\n## ", 1)[0].strip()])
    for heading in ("待确认", "验收条件", "范围"):
        value = section(source, heading)
        version = "澄清发布版本" if revision else "正文版本"
        if revision and separator:
            if heading == "验收条件":
                value = legacy_acceptance.strip()
            else:
                value = section(body, heading)
                version = "旧修订未提供本字段，以下为原正文"
        if value:
            lines.extend(["", f"## {heading}（{version}）", value])
    if dependencies:
        lines.extend(["", "## 登记的前置工单"])
        lines.extend(f"- [{r['title']}]({r['html_url']}) · {r['state']}" for r in dependencies)
    if children:
        lines.extend(["", "## 子项"])
        lines.extend(f"- [{c['title']}]({c['html_url']}) · {c['state_reason'] or c['state']}" for c in children)
    if comments:
        last = max(comments, key=lambda c: c["id"])
        lines.extend(["", f"[最新评论 · {last['created_at']}]({last['html_url']})"])
        if revision and last["id"] > revision[1]["id"]:
            lines.append("澄清发布后还有讨论，最新人工决定请回读评论。")
        lines.append((last.get("body") or "").split(" -->", 1)[-1].strip()[:400])
    return "\n".join(lines)


def recovery_receipts(comments, repository, released):
    receipts = []
    for comment in comments:
        if (
            comment["user"]["login"] != "github-actions[bot]"
            or datetime.fromisoformat(comment["created_at"]) < released
        ):
            continue
        body = (comment["body"] or "").replace("\r\n", "\n")
        if not body.startswith("<!-- kuafu-recovery:") or "\n```json\n" not in body:
            continue
        try:
            proof = json.loads(body.split("\n```json\n", 1)[1].removesuffix("\n```"))
        except ValueError:
            continue
        if (
            not isinstance(proof, dict)
            or comment["issue_url"] != f"https://api.github.com/repos/{repository}/issues/{proof.get('original_issue')}"
        ):
            continue
        state = proof.get("state")
        if state not in ("operation_reverified", "recovery_candidate") or not re.fullmatch(
            r"[0-9a-f]{40}", proof.get("old_candidate") or ""
        ):
            continue
        if state == "operation_reverified" and proof["old_candidate"] != proof.get("new_candidate"):
            continue
        if state == "operation_reverified" and ("old_pr_head" in proof or "new_pr_head" in proof):
            if not re.fullmatch(r"[0-9a-f]{40}", proof.get("old_pr_head") or "") or proof["old_pr_head"] != proof.get(
                "new_pr_head"
            ):
                continue
        receipts.append({
            "issue": proof["original_issue"],
            "state": state,
            "source": comment["html_url"],
            **{key: proof.get(key) for key in ("first_failure_at", "condition_observed_at", "reverified_at")},
        })
    return receipts


def turnaround(gh, repository, baseline, released):
    """Compare the same Issue categories, retaining the snapshot's original close timestamps."""
    if any(datetime.fromisoformat(row["closed_at"]) > released for row in baseline["closed_issues"]):
        raise ValueError("Release must follow the baseline observation")
    rows = pages(gh, f"repos/{repository}/issues?state=all&per_page=100")
    subjects = {r["number"]: r for r in rows if "pull_request" not in r}
    cohorts = {}
    missing = []
    for number, phase, end in [(r["issue"], "baseline", r["closed_at"]) for r in baseline["closed_issues"]] + [
        (r["number"], "after", r["closed_at"])
        for r in subjects.values()
        if r["state"] == "closed"
        and r["state_reason"] == "completed"
        and datetime.fromisoformat(r["created_at"]) >= released
    ]:
        if number not in subjects:
            missing.append(number)
            continue
        issue = subjects[number]
        categories = sorted(label["name"] for label in issue["labels"] if label["name"].startswith("type:"))
        key = categories[0] if len(categories) == 1 else "unknown"
        minutes = (datetime.fromisoformat(end) - datetime.fromisoformat(issue["created_at"])).total_seconds() / 60
        cohorts.setdefault(key, {"baseline": [], "after": []})[phase].append((minutes, number))
    result = {}
    for key, phases in sorted(cohorts.items()):
        result[key] = {}
        for phase, samples in phases.items():
            values = sorted(x[0] for x in samples)
            result[key][phase] = {
                "issues": sorted(x[1] for x in samples),
                "n": len(values),
                "median_minutes": round(median(values), 2) if values else None,
                "p90_minutes": round(values[ceil(0.9 * len(values)) - 1], 2) if values else None,
            }
    return {
        "repository": repository,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "released_at": released.isoformat(),
        "grouped_by_current_type": result,
        "unavailable_baseline_issues": missing,
        "public_recovery_receipts": recovery_receipts(
            pages(gh, f"repos/{repository}/issues/comments?per_page=100&since={quote(released.isoformat(), safe='')}"),
            repository,
            released,
        ),
        "substantive_concurrent_rework": None,
        "user_reading_seconds": None,
        "scope": "completed Issue wall time; after cohort starts at release",
    }
