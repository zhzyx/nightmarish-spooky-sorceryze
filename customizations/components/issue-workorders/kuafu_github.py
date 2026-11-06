"""Triage GitHub blocker events using only the trusted default-branch checkout."""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from work_items import ROOT, GitHubCommandError, gh, request_ids

FAILURES = {"failure", "startup_failure", "timed_out", "action_required"}
BOT = "github-actions[bot]"
OWN_WORKFLOW = ".github/workflows/kuafu-blockers.yml"


def number(value):
    if type(value) is not int or value < 1:
        raise ValueError("Expected a positive GitHub identifier")
    return value


class GitHub:
    def __init__(self, repo):
        self.repo = repo
        self.prefix = f"repos/{repo}/"

    def get(self, path):
        return json.loads(gh("api", (self.prefix + path).rstrip("/")))

    def pages(self, path, field=None):
        sep = "&" if "?" in path else "?"
        pages = json.loads(gh("api", self.prefix + path + sep + "per_page=100", "--paginate", "--slurp"))
        return [item for page in pages for item in (page[field] if field else page)]

    def post(self, path, body):
        # Read remote state on the next delivery if a write receipt is lost.
        result = subprocess.run(
            ["gh", "api", self.prefix + path, "--method", "POST", "--input", "-"],
            input=json.dumps(body),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        if result.returncode:
            raise RuntimeError(f"GitHub write to {path} was not confirmed; reconcile before retry")
        return json.loads(result.stdout)


def labels(issue):
    return {label["name"] for label in issue["labels"]}


def current_writer(api, login):
    if not isinstance(login, str) or not re.fullmatch(r"[A-Za-z0-9_-]+(?:\[bot\])?", login):
        return False
    try:
        access = api.get(f"collaborators/{login}/permission")
    except GitHubCommandError as exc:
        if exc.http_status == 404:
            return False
        raise
    return access["user"]["login"].casefold() == login.casefold() and access["permission"] in {
        "admin",
        "maintain",
        "write",
    }


def related_issue(api, run):
    # Use a unique provider-bound PR. A fork or an arbitrary PR body cannot direct writes.
    prs = run.get("pull_requests") or []
    if not prs and run["event"] in {"push", "pull_request"}:
        prs = api.pages("commits/" + run["head_sha"] + "/pulls")
    if len(prs) != 1:
        return None
    ref = prs[0]
    pr = api.get(f"pulls/{number(ref['number'])}")
    merged_push = (
        run["event"] == "push"
        and pr.get("merged") is True
        and pr.get("merge_commit_sha") == run["head_sha"]
        and pr["base"]["ref"] == run.get("head_branch")
    )
    if (
        pr["base"]["repo"]["full_name"] != api.repo
        or (pr["head"].get("repo") or {}).get("full_name") != api.repo
        or pr["head"]["sha"] != ref["head"]["sha"]
        or not re.fullmatch("[0-9a-f]{40}", pr["head"]["sha"])
        or (run["event"] != "pull_request_target" and pr["head"]["sha"] != run["head_sha"] and not merged_push)
    ):
        return None
    if not current_writer(api, (pr.get("user") or {}).get("login")):
        return None
    body = pr.get("body") or ""
    issues = re.findall(r"^GongGong-Issue:[ \t]*#([1-9][0-9]*)[ \t]*\r?$", body, re.M)
    requests = re.findall(r"^GongGong-Request:[ \t]*([a-z0-9]+(?:-[a-z0-9]+)*)[ \t]*\r?$", body, re.M)
    if len(issues) != 1 or len(requests) != 1:
        return None
    try:
        issue = api.get(f"issues/{int(issues[0])}")
    except GitHubCommandError as exc:
        if exc.http_status == 404:
            return None
        raise
    if (
        "pull_request" not in issue
        and "workspace:gonggong" in labels(issue)
        and request_ids(issue.get("body")) == set(requests)
    ):
        return {**issue, "verified_pr": number(pr["number"]), "verified_pr_head": pr["head"]["sha"]}
    return None


DISPATCH_ACTIONS = {
    "intake",
    "validation",
    "delivery",
    "dispatch",
    "user-report",
    "dependency",
    "permission",
    "unknown-receipt",
    "other",
}


def local_dispatch(api, event):
    inputs = event["inputs"]
    if (
        set(inputs) != {"source_issue", "request_id", "action", "incident", "head"}
        or not all(isinstance(v, str) for v in inputs.values())
        or not re.fullmatch(r"[1-9][0-9]{0,11}", inputs["source_issue"])
        or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", inputs["request_id"])
        or inputs["action"] not in DISPATCH_ACTIONS
        or not re.fullmatch("[0-9a-f]{64}", inputs["incident"])
        or not re.fullmatch("[0-9a-f]{40}", inputs["head"])
    ):
        raise ValueError("Invalid local incident handoff fields")
    branch = api.get("")["default_branch"]
    ref = f"refs/heads/{branch}"
    if (
        event["ref"] not in {branch, ref}
        or os.environ["GITHUB_REF"] != ref
        or os.environ["GITHUB_WORKFLOW_REF"] != f"{api.repo}/{OWN_WORKFLOW}@{ref}"
    ):
        raise ValueError("Local handoff requires the default-branch Kuafu workflow")
    actor = os.environ["GITHUB_ACTOR"]
    if actor.casefold() != event["sender"]["login"].casefold():
        raise ValueError("Handoff sender differs from the authenticated workflow actor")
    for login in {actor, os.environ["GITHUB_TRIGGERING_ACTOR"]}:
        if not current_writer(api, login):
            raise ValueError("Local handoff requires current repository write permission")
    n = int(inputs["source_issue"])
    issue = api.get(f"issues/{n}")
    if (
        issue["number"] != n
        or "pull_request" in issue
        or issue["state"] != "open"
        or "workspace:gonggong" not in labels(issue)
        or request_ids(issue.get("body")) != {inputs["request_id"]}
    ):
        raise ValueError("Local incident does not bind to the open workspace request")
    head = inputs["head"]
    try:
        remote_head = api.get(f"commits/{head}")["sha"]
        if remote_head != head:
            raise ValueError("Remote candidate identity mismatch")
    except GitHubCommandError as exc:
        if exc.http_status not in {404, 422}:
            raise
        remote_head = None
    incident = inputs["incident"]
    return (
        f"local-{n}-{incident}",
        {
            "source": f"https://github.com/{api.repo}/issues/{n}",
            "sender": actor,
            "host_attempt": f"https://github.com/{api.repo}/actions/runs/{int(os.environ['GITHUB_RUN_ID'])}/attempts/{int(os.environ['GITHUB_RUN_ATTEMPT'])}",
            "request_id": inputs["request_id"],
            "action": inputs["action"],
            "reported_head": head,
            "remote_head": remote_head,
            "local_incident": incident,
            "local_evidence_observed_by_runner": False,
            "diagnosis": "已核实协作者提交的本地阻塞交接和原工单。请按本地事件标识回读留存证据，再定向复验受影响操作。",
        },
        issue,
    )


def inspect_event(api, name, event):
    if event["repository"]["full_name"] != api.repo:
        raise ValueError("Unexpected event repository")
    if name == "workflow_dispatch":
        return local_dispatch(api, event)
    if name == "issues":
        if event["action"] != "labeled" or event["label"]["name"] != "status:blocked":
            return None
        n = number(event["issue"]["number"])
        issue = api.get(f"issues/{n}")
        if (
            "pull_request" in issue
            or issue["state"] != "open"
            or not {"workspace:gonggong", "status:blocked"} <= labels(issue)
        ):
            return None
        # The original webhook timestamp is stable on redelivery. A later re-block is a new occurrence.
        observed_at = datetime.fromisoformat(event["issue"]["updated_at"].replace("Z", "+00:00"))
        if observed_at.tzinfo is None:
            raise ValueError("Expected a timezone on the GitHub issue observation")
        return (
            f"issue-{n}-{int(observed_at.timestamp())}",
            {
                "source": f"https://github.com/{api.repo}/issues/{n}",
                "diagnosis": "原工单已标记阻塞，请原责任人回读阻塞说明并复现受影响动作。",
            },
            issue,
        )
    if name != "workflow_run" or event["action"] != "completed":
        return None
    observed = event["workflow_run"]
    if observed["conclusion"] not in FAILURES | {"success"}:
        return None
    rid, attempt = number(observed["id"]), number(observed["run_attempt"])
    path = f"actions/runs/{rid}/attempts/{attempt}"
    run = api.get(path)
    if (
        run["repository"]["full_name"] != api.repo
        or run["status"] != "completed"
        or any(run[k] != observed[k] for k in ("id", "run_attempt", "head_sha", "conclusion", "workflow_id"))
        or not re.fullmatch("[0-9a-f]{40}", run["head_sha"])
    ):
        raise ValueError("Run attempt does not match its completion event")
    workflow = run["path"].split("@", 1)[0]
    if workflow == OWN_WORKFLOW:
        return None
    source = f"https://github.com/{api.repo}/actions/runs/{rid}/attempts/{attempt}"
    issue = related_issue(api, run)
    if run["conclusion"] == "success":
        return ("recovery", run, issue) if issue else None
    jobs = []
    for job in api.pages(path + "/jobs", "jobs"):
        if job["conclusion"] in FAILURES:
            jid = number(job["id"])
            steps = [number(step["number"]) for step in job.get("steps", []) if step["conclusion"] in FAILURES]
            jobs.append({
                "url": f"https://github.com/{api.repo}/actions/runs/{rid}/job/{jid}",
                "conclusion": job["conclusion"],
                "failed_steps": steps,
            })
    if run["conclusion"] == "startup_failure":
        diagnosis = "工作流启动失败；核查该次运行的启动注释、配置、权限与依赖。"
    elif jobs:
        diagnosis = "运行有失败作业；从记录的作业及步骤编号回读首次失败日志，再定向复验。"
    else:
        diagnosis = "运行返回阻塞结论，但 API 未列出失败作业；核查该次运行注释。"
    report = {
        "source": source,
        "candidate": run["head_sha"],
        "conclusion": run["conclusion"],
        "failed_jobs": jobs,
        "diagnosis": diagnosis,
        "workflow_id": number(run["workflow_id"]),
        "pr": issue["verified_pr"] if issue else None,
        "pr_head": issue["verified_pr_head"] if issue else None,
    }
    return f"run-{rid}-attempt-{attempt}", report, issue


def job_coverage(before, after, conclusion):
    """Return concrete job IDs only when the original operation demonstrably ran."""
    good = [job for job in after if job["conclusion"] == "success"]
    if conclusion == "startup_failure" and not before and good:
        return [{"started_job": number(good[0]["id"])}]
    verified = []
    for old in before:
        if old["conclusion"] not in FAILURES:
            continue
        matching = [job for job in after if old.get("name") and job["name"] == old["name"]]
        if (
            sum(job.get("name") == old.get("name") for job in before) != 1
            or len(matching) != 1
            or matching[0]["conclusion"] != "success"
        ):
            return None
        new = matching[0]
        steps = []
        for step in old.get("steps", []):
            if step["conclusion"] not in FAILURES:
                continue
            same = [s for s in new.get("steps", []) if s["number"] == step["number"] and s["name"] == step["name"]]
            if len(same) != 1 or same[0]["conclusion"] != "success":
                return None
            steps.append(number(step["number"]))
        verified.append({"failed_job": number(old["id"]), "successful_job": number(new["id"]), "steps": steps})
    return verified or None


def prior_reports(api, issue):
    """Only examine bot-owned intake records linked from this specific business issue."""
    n = number(issue["number"])
    comments = api.pages(f"issues/{n}/comments")
    completed = {(c.get("body") or "").split("\n", 1)[0] for c in comments if c["user"]["login"] == BOT}
    for comment in comments:
        body = comment.get("body") or ""
        marker = re.match(r"<!-- kuafu-(notice|report):run-([1-9][0-9]*)-attempt-([1-9][0-9]*) -->\n", body)
        if comment["user"]["login"] != BOT or not marker:
            continue
        rid, attempt = map(int, marker.groups()[1:])
        if f"<!-- kuafu-recovery:run-{rid}-attempt-{attempt} -->" in completed:
            continue
        bug = n
        if marker[1] == "notice":
            link = re.match(r"夸父已将本次阻塞登记到 #([1-9][0-9]*)。", body[marker.end() :])
            if not link:
                continue
            bug = int(link[1])
            incident = api.get(f"issues/{bug}")
            body = incident.get("body") or ""
            if (
                incident["user"]["login"] != BOT
                or "pull_request" in incident
                or not body.startswith(f"<!-- gonggong-request:kuafu-run-{rid}-attempt-{attempt} -->\n")
            ):
                continue
        match = re.search(r"\n```json\n(\{.*\})\n```\Z", body, re.S)
        if match:
            try:
                report = json.loads(match[1])
            except ValueError:
                continue
            if isinstance(report, dict) and report.get("original_issue") == n:
                yield bug, rid, attempt, report


def reverify(api, run, issue):
    issue_number = number(issue["number"])
    success_path = f"actions/runs/{number(run['id'])}/attempts/{number(run['run_attempt'])}"
    jobs = None
    receipts = []
    for bug, rid, attempt, report in prior_reports(api, issue):
        if report.get("workflow_id") != run["workflow_id"] or report.get("pr") != issue["verified_pr"]:
            continue
        path = f"actions/runs/{rid}/attempts/{attempt}"
        old = api.get(path)
        if (
            old["repository"]["full_name"] != api.repo
            or old["id"] != rid
            or old["run_attempt"] != attempt
            or old["conclusion"] not in FAILURES
            or old["status"] != "completed"
            or old["conclusion"] != report.get("conclusion")
            or old["head_sha"] != report.get("candidate")
            or not re.fullmatch("[0-9a-f]{40}", old["head_sha"])
            or any(old[k] != run[k] for k in ("workflow_id", "path", "event", "head_branch"))
        ):
            continue
        if rid == run["id"]:
            if attempt >= run["run_attempt"] or old["head_sha"] != run["head_sha"]:
                continue
        elif old["updated_at"] >= run["run_started_at"]:
            continue
        old_pr_head = report.get("pr_head") or ""
        if not re.fullmatch("[0-9a-f]{40}", old_pr_head):
            continue
        different_head = old_pr_head != issue["verified_pr_head"] or old["head_sha"] != run["head_sha"]
        if different_head:
            pairs = {(old_pr_head, issue["verified_pr_head"]), (old["head_sha"], run["head_sha"])}
            if any(api.get(f"compare/{a}...{b}")["status"] != "ahead" for a, b in pairs if a != b):
                continue
        if jobs is None:
            jobs = api.pages(success_path + "/jobs", "jobs")
        coverage = job_coverage(api.pages(path + "/jobs", "jobs"), jobs, old["conclusion"])
        if not coverage:
            continue
        proof = {
            "original_issue": issue_number,
            "pr": issue["verified_pr"],
            "old_candidate": old["head_sha"],
            "new_candidate": run["head_sha"],
            "failure": f"https://github.com/{api.repo}/{path}",
            "success": f"https://github.com/{api.repo}/{success_path}",
            "jobs": coverage,
            "state": "recovery_candidate" if different_head else "operation_reverified",
        }
        marker = f"<!-- kuafu-recovery:run-{rid}-attempt-{attempt} -->"
        text = (
            "夸父定向复验。业务验收由原工单责任人继续。\n\n```json\n" + json.dumps(proof, ensure_ascii=False) + "\n```"
        )
        persisted = post_once(api, bug, marker, text)
        if bug != issue_number:
            post_once(api, issue_number, marker, persisted)
        receipts.append(json.loads(persisted.split("\n```json\n", 1)[1].removesuffix("\n```")))
    return {"reverification": receipts} if receipts else None


def load_context(key, report):
    framework = ROOT / json.loads((ROOT / "CURRENT_FRAMEWORK.json").read_text())["root"]
    mandate = {
        "feature_id": key,
        "outcome": "初判已验证阻塞、登记 bug 并通知可核实的原工单",
        "authority_ref": report["source"],
        "host_workflow": OWN_WORKFLOW,
    }
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "mandate.json"
        path.write_text(json.dumps(mandate), encoding="utf-8")
        context = subprocess.check_output(["node", str(framework / "tools/agent-context.mjs"), "kuafu", str(path)])
    return hashlib.sha256(context).hexdigest()


def post_once(api, n, marker, text):
    path = f"issues/{number(n)}/comments"
    prefix = marker + "\n"
    for comment in api.pages(path):
        body = comment.get("body") or ""
        if comment["user"]["login"] == BOT and body.startswith(prefix):
            return body[len(prefix) :]
    api.post(path, {"body": prefix + text})
    return text


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def record_evidence(directory, key, report):
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory / "diagnosis.json", report)
    settings = json.loads((ROOT / "work-items.json").read_text(encoding="utf-8"))
    framework = ROOT / json.loads((ROOT / "CURRENT_FRAMEWORK.json").read_text())["root"]
    request = "kuafu-" + key
    # Each real host invocation is a separate observation of the same incident.
    event_id = f"kuafu-host-{int(os.environ['GITHUB_RUN_ID'])}-{int(os.environ['GITHUB_RUN_ATTEMPT'])}"
    envelope = {
        "schema_version": 1,
        "event_id": event_id,
        "tenant_id": settings["tenant_id"],
        "request_id": request,
        "kind": "quality_issue",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "source_ref": report["source"],
        "agent": {
            "id": "kuafu-github-host",
            "version": "1",
            "definition_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "origin": "external-authorized-host",
        },
        "payload": report,
        "evidence_refs": [],
    }
    stored_path = ROOT / "gonggong-diting-data" / "events" / envelope["tenant_id"] / request / (event_id + ".json")
    if stored_path.is_file():
        # Replay the original observation timestamp; the adapter still compares the entire event.
        envelope["occurred_at"] = json.loads(stored_path.read_text(encoding="utf-8"))["occurred_at"]
    input_file = directory / "quality_issue.json"
    write_json(input_file, envelope)
    cli = framework / "extensions/diting-files/diting_files.py"
    process = subprocess.run(
        [sys.executable, str(cli), "record", "--repo", str(ROOT), "--input", str(input_file)],
        capture_output=True,
        encoding="utf-8",
    )
    if process.returncode:
        print("Diting recording failed: " + process.stderr.strip(), file=sys.stderr)
        receipt = {"state": "recording_unconfirmed"}
    else:
        receipt = json.loads(process.stdout)
        if receipt["state"] != "recorded_file":
            raise ValueError("Unexpected Diting recording result")
        if receipt.get("historical_read_only"):
            stored_path = ROOT / "olympus-hermes-data" / stored_path.relative_to(ROOT / "gonggong-diting-data")
        stored = json.loads(stored_path.read_text(encoding="utf-8"))
        receipt.update(path=str(stored_path), sha256=stored["sha256"])
        write_json(directory / "quality_issue.json", stored)
    write_json(directory / "record_receipt.json", receipt)
    return {"state": receipt["state"], "sha256": receipt.get("sha256"), "consumption": None}


def route(api, name, event, context=load_context, record=None):
    incident = inspect_event(api, name, event)
    if incident is None:
        return None
    key, report, issue = incident
    if key == "recovery":
        return reverify(api, report, issue)
    n = number(issue["number"]) if issue else None
    report.update(
        original_issue=n,
        context_sha256=context(key, report),
        host="github-actions/kuafu",
        root_cause=None,
        repair=None,
        verification=None,
        execution="deterministic_host_triage",
    )
    if record:
        report["diting"] = record(key, report)
    request = "kuafu-" + key
    marker = f"<!-- gonggong-request:{request} -->"
    text = "夸父阻塞初判\n\n" + report["diagnosis"] + "\n\n" + report["source"]
    # Machine-readable evidence never contains PR text, job names, logs, or attacker-supplied URLs.
    excerpt = dict(report)
    if "failed_jobs" in excerpt:
        excerpt["failed_job_count"] = len(report["failed_jobs"])
        excerpt["failed_jobs"] = [
            {**job, "failed_steps": job["failed_steps"][:50]} for job in report["failed_jobs"][:20]
        ]
    text += "\n\n```json\n" + json.dumps(excerpt, ensure_ascii=False, indent=2) + "\n```"
    if issue and issue["state"] == "open" and "type:bug" in labels(issue):
        bug = n
        post_once(api, bug, f"<!-- kuafu-report:{key} -->", text)
    else:
        matches = [
            i
            for i in api.pages("issues?state=all&creator=github-actions%5Bbot%5D")
            if "pull_request" not in i and i["user"]["login"] == BOT and marker in (i.get("body") or "")
        ]
        if len(matches) > 1:
            raise ValueError("Multiple incident bugs found; reconcile their identities")
        if matches:
            bug = number(matches[0]["number"])
        else:
            created = api.post(
                "issues",
                {
                    "title": f"夸父阻塞：{key}",
                    "body": marker + "\n\n" + text,
                    "labels": ["type:bug", "workspace:gonggong", "status:planned"],
                },
            )
            bug = number(created["number"])
        if n:
            post_once(
                api, n, f"<!-- kuafu-notice:{key} -->", f"夸父已将本次阻塞登记到 #{bug}。证据：{report['source']}"
            )
    return {**report, "incident_key": key, "bug_number": bug}


if __name__ == "__main__":
    settings = json.loads((ROOT / "work-items.json").read_text(encoding="utf-8"))
    repo = os.environ["GITHUB_REPOSITORY"]
    if repo != settings["repository"]:
        raise ValueError("Repository is outside the workspace binding")
    directory = Path(os.environ["RUNNER_TEMP"]) / "kuafu-evidence"
    directory.mkdir(exist_ok=True)
    write_json(
        directory / "host.json",
        {"workflow_run": f"https://github.com/{repo}/actions/runs/{os.environ['GITHUB_RUN_ID']}"},
    )
    outcome = route(
        GitHub(repo),
        os.environ["GITHUB_EVENT_NAME"],
        json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8")),
        record=lambda key, report: record_evidence(directory, key, report),
    )
    write_json(directory / "outcome.json", outcome)
    print(json.dumps(outcome, ensure_ascii=False))
    if outcome:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            print("has_evidence=true", file=output)
    if outcome and outcome.get("diting", {}).get("state") == "recording_unconfirmed":
        raise SystemExit("Incident tracked; Diting file recording still needs attention")
