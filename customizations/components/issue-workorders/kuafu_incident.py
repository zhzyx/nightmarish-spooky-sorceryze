"""Durable handoff from a blocked host to the admitted Kuafu role. No scheduler."""

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import issue_gate
import work_items
from issue_events import event_lock, write_new


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], timeout=30)


def private_root(root):
    common = git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").decode().strip()
    return Path(common) / "gonggong-kuafu"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def operation_folder(root, issue, request, action, parameters=None):
    operation = [str(root.resolve()), issue, request, action, parameters]
    return private_root(root) / "operations" / sha(json.dumps(operation).encode())


def observe_success(root, issue, request, action, result, parameters=None):
    """Attach a real successful invocation to matching incidents; never close an Issue."""
    try:
        pending = operation_folder(root, issue, request, action, parameters)
        if not pending.is_dir():
            return
        for entry in pending.glob("*.pending"):
            key = entry.stem
            folder = private_root(root) / key
            with event_lock(folder / "incident.lock"):
                if not entry.exists():
                    continue
                detected = read(folder / "detected.json")
                head = git(root, "rev-parse", "HEAD").decode().strip()
                index = sha(git(root, "diff", "--cached", "--raw", "-z", "--no-abbrev", "HEAD"))
                state = (
                    "operation_reverified"
                    if (head, index) == (detected["head"], detected["index_delta_sha256"])
                    else "recovery_candidate"
                )
                outcome = {
                    "incident": key,
                    "state": state,
                    "head": head,
                    "index_delta_sha256": index,
                    "operation": action,
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                    "result_sha256": sha(json.dumps(result, sort_keys=True).encode()),
                }
                path = folder / ("recheck-" + sha(json.dumps(outcome).encode()) + ".json")
                write_new(path, outcome)
                entry.unlink()
                print(json.dumps(outcome), file=sys.stderr)
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        print(json.dumps({"state": "kuafu_recheck_receipt_unavailable", "reason": type(exc).__name__}), file=sys.stderr)


def capture(root, issue, request, action, observation, parameters=None):
    if type(issue) is not int or issue < 1 or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", request):
        raise ValueError("A bound Issue and stable request ID are required")
    identity = {
        "issue": issue,
        "request_id": request,
        "repository": work_items.config(root)[0]["repository"],
        "worktree": str(root.resolve()),
        "head": git(root, "rev-parse", "HEAD").decode().strip(),
        "index_delta_sha256": sha(git(root, "diff", "--cached", "--raw", "-z", "--no-abbrev", "HEAD")),
        "action": action,
        # Command output can contain credentials. Keep the original in the calling host.
        "observation_sha256": sha(observation.encode()),
    }
    if parameters is not None:
        identity["parameters"] = parameters
    key = sha(json.dumps(identity, sort_keys=True).encode())
    folder = private_root(root) / key
    with event_lock(folder / "incident.lock"):
        path = folder / "detected.json"
        if not path.exists():
            write_new(path, dict(identity, occurred_at=datetime.now(timezone.utc).isoformat()))
        pending = operation_folder(root, issue, request, action, parameters) / (key + ".pending")
        if not pending.exists():
            write_new(pending, {"incident": key})
    return {
        "incident": key,
        "state": "pending_kuafu_intake",
        "issue": issue,
        "action": action,
        "next_action": "The active host must invoke Kuafu now: receive, investigate, then assess with the actual worker and bug.",
    }


def send_to_kuafu(root, notice):
    """Trigger only an official main-branch receiver for a verified source; keep lost write receipts pending."""
    folder = private_root(root) / notice["incident"]
    record = read(folder / "detected.json")
    repository = record["repository"]
    if os.environ.get("GONGGONG_KUAFU_LOCAL_ONLY") == "1":
        return dict(notice, dispatch="local_only")
    try:
        issue_gate.check_repository(root, repository)
        with event_lock(folder / "dispatch.lock"):
            if (folder / "dispatch-receipt.json").exists():
                return dict(notice, dispatch=read(folder / "dispatch-receipt.json"))
            if (folder / "dispatch-intent.json").exists():
                actor = work_items.gh("api", "user", "--jq", ".login")
                expected = "kuafu-local-" + notice["incident"]
                path = f"repos/{repository}/actions/workflows/kuafu-blockers.yml/runs?event=workflow_dispatch&branch=main&actor={actor}&per_page=100"
                pages = json.loads(work_items.gh("api", path, "--paginate", "--slurp"))
                matches = [run for page in pages for run in page["workflow_runs"] if run["display_title"] == expected]
                if len(matches) == 1:
                    receipt = {"state": "dispatch_observed", "response": matches[0]["html_url"]}
                    write_new(folder / "dispatch-receipt.json", receipt)
                    return dict(notice, dispatch=receipt)
                return dict(notice, dispatch="unconfirmed_reconcile_before_retry")
            source = json.loads(work_items.gh("api", f"repos/{repository}/issues/{record['issue']}"))
            if (
                "pull_request" in source
                or source["state"] != "open"
                or work_items.request_ids(source["body"]) != {record["request_id"]}
                or "workspace:gonggong" not in {label["name"] for label in source["labels"]}
            ):
                return dict(notice, dispatch="source_binding_unconfirmed")
            if (
                work_items.gh("api", f"repos/{repository}/actions/workflows/kuafu-blockers.yml", "--jq", ".state")
                != "active"
            ):
                return dict(notice, dispatch="receiver_unavailable")
            inputs = {
                "incident": notice["incident"],
                "source_issue": str(record["issue"]),
                "request_id": record["request_id"],
                "head": record["head"],
                "action": record["action"],
            }
            write_new(folder / "dispatch-intent.json", inputs)
            fields = [arg for key, value in inputs.items() for arg in ("-f", key + "=" + value)]
            response = work_items.gh(
                "workflow", "run", "kuafu-blockers.yml", "--repo", repository, "--ref", "main", *fields
            )
            receipt = {"state": "dispatch_requested", "response": response}
            write_new(folder / "dispatch-receipt.json", receipt)
            return dict(notice, dispatch=receipt)
    except (OSError, KeyError, ValueError, TypeError, subprocess.SubprocessError) as error:
        return dict(
            notice,
            dispatch="unconfirmed_reconcile_before_retry"
            if (folder / "dispatch-intent.json").exists()
            else "pending_remote_intake",
            failure=type(error).__name__,
        )


def notify_failure(root, issue, request, action, error, parameters=None):
    try:
        notice = send_to_kuafu(root, capture(root, issue, request, action, str(error), parameters))
    except (OSError, KeyError, ValueError, TypeError, subprocess.SubprocessError) as capture_error:
        notice = {"state": "kuafu_intake_unavailable", "reason": type(capture_error).__name__}
    print(json.dumps(notice), file=sys.stderr)
    return notice


@contextmanager
def trusted_framework(root, repository):
    # Execute the registered main package, even when the defect is in the detecting tree.
    commit = work_items.gh("api", f"repos/{repository}/git/ref/heads/main", "--jq", ".object.sha")
    if not re.fullmatch("[0-9a-f]{40}", commit):
        raise ValueError("Missing authoritative main commit")
    present = subprocess.run(["git", "-C", str(root), "cat-file", "-e", commit + "^{commit}"], capture_output=True)
    if present.returncode:
        # Fetch only the authenticated object, without updating any working branch or FETCH_HEAD.
        git(
            root,
            "fetch",
            "--no-tags",
            "--no-write-fetch-head",
            "--no-auto-maintenance",
            "--refmap=",
            f"https://github.com/{repository}.git",
            commit,
        )
    archive = git(root, "archive", "--format=zip", commit, "framework")
    with tempfile.TemporaryDirectory() as directory, zipfile.ZipFile(io.BytesIO(archive)) as snapshot:
        snapshot.extractall(directory)
        yield Path(directory) / "framework"


def references_issue(body, repository, number):
    return bool(
        re.search(
            rf"(?<![\w/])#{number}(?!\d)|https://github\.com/{re.escape(repository)}/issues/{number}(?!\d)", body or ""
        )
    )


def issue_binding(root, record, bug):
    repository = work_items.config(root)[0]["repository"]
    if repository != record["repository"] or str(root.resolve()) != record["worktree"]:
        raise ValueError("Use the detecting repository and worktree")
    issue_gate.check_repository(root, repository)
    principal = json.loads(work_items.gh("repo", "view", "github.com/" + repository, "--json", "viewerPermission"))
    if principal["viewerPermission"] not in {"WRITE", "MAINTAIN", "ADMIN"}:
        raise ValueError("Authenticated repository writer required")
    actor = work_items.gh("api", "user", "--jq", ".login")
    source = json.loads(work_items.gh("api", f"repos/{repository}/issues/{record['issue']}"))
    target = source if bug == record["issue"] else json.loads(work_items.gh("api", f"repos/{repository}/issues/{bug}"))
    if "pull_request" in source or work_items.request_ids(source["body"]) != {record["request_id"]}:
        raise ValueError("Source Issue request binding changed")
    if "pull_request" in target or "type:bug" not in {label["name"] for label in target["labels"]}:
        raise ValueError("Link a real bug Issue before accepting the handoff")
    if bug != record["issue"]:
        # A typed bug in the same repository is insufficient evidence of this dependency.
        if not (
            references_issue(source["body"], repository, bug)
            or references_issue(target["body"], repository, record["issue"])
        ):
            raise ValueError("Link the original Issue and bug explicitly in an Issue body before intake")
    return actor, source["html_url"], target["html_url"]


def bind_context(framework, folder, record, args, identity):
    actor, source, bug = identity
    mandate = {
        "feature_id": record["request_id"],
        "outcome": "Diagnose and report the blocked operation",
        "authority_ref": args.authority,
        "operator": actor,
        "worker": args.worker,
        "source": source,
        "bug": bug,
    }
    file = folder / "mandate.json"
    if not file.exists():
        write_new(file, mandate)
    if read(file) != mandate:
        raise ValueError("Incident already bound to a different operator, worker or mandate; reconcile the handoff")
    context = subprocess.check_output(
        ["node", str(framework / "tools/agent-context.mjs"), "kuafu", str(file)],
        cwd=framework,
        env=dict(
            {
                k: v
                for k, v in os.environ.items()
                if k.upper() not in {"NODE_OPTIONS", "NODE_PATH", "PYTHONPATH", "PYTHONHOME"}
            },
            GONGGONG_PYTHON=sys.executable,
        ),
        timeout=120,
    )
    profile = read(framework / "agents/kuafu/reporting.json")["component"]
    binding = dict(
        mandate, context_sha256=sha(context), definition_sha256=profile["entry_sha256"], version=profile["version"]
    )
    receipt = folder / "received.json"
    if not receipt.exists():
        write_new(receipt, binding)
    if binding != read(receipt):
        raise ValueError("Kuafu context changed; reconcile the existing receipt")
    return context, binding


def publish(root, source, payload, receipt):
    """Publish one authenticated observation; on retry reconcile the original comment first."""
    repo = work_items.config(root)[0]["repository"]
    endpoint = f"repos/{repo}/issues/{source}/comments"
    marker = f"<!-- kuafu-assessment:{receipt['sha256']} -->"
    body = "\n".join([
        marker,
        f"夸父阻塞判断 · {payload['action']}",
        "",
        f"原工单 {payload['source_issue']} · 跟踪 {payload['bug']}",
        f"操作者 {payload['operator']} · 工作者 {payload['worker']}",
        f"证据 {payload['evidence']}",
        f"判断 {payload['diagnosis']}",
        f"下一步 {payload['next_action']}",
        "原操作复验：待原责任者回读。",
    ])

    def matches():
        pages = json.loads(work_items.gh("api", endpoint + "?per_page=100", "--paginate", "--slurp"))
        return [
            c
            for page in pages
            for c in page
            if c["user"]["login"] == payload["operator"] and c["body"].startswith(marker)
        ]

    existing = matches()
    if not existing:
        work_items.gh("api", endpoint, "--method", "POST", "--raw-field", "body=" + body)
        existing = matches()
    if len(existing) != 1 or existing[0]["body"] != body:
        raise ValueError("Kuafu timeline receipt ambiguous; inspect source Issue before retry")
    return existing[0]["html_url"]


def report(root, framework, folder, record, key, binding, args):
    # This is the authenticated handler's diagnosis, not proof of recovery.
    payload = {
        "incident": key,
        "source_issue": binding["source"],
        "bug": binding["bug"],
        "action": record["action"],
        "detection_head": record["head"],
        "context_sha256": binding["context_sha256"],
        "operator": binding["operator"],
        "worker": binding["worker"],
        "authority_ref": binding["authority_ref"],
        "evidence": args.evidence,
        "diagnosis": args.diagnosis,
        "next_action": args.next_action,
        "original_operation_reverified": False,
    }
    eid = "kuafu-" + sha(json.dumps(payload, sort_keys=True).encode())[:40]
    event = {
        "schema_version": 1,
        "event_id": eid,
        "tenant_id": work_items.config(root)[0]["tenant_id"],
        "request_id": record["request_id"],
        "kind": "quality_issue",
        "source_ref": binding["source"],
        "agent": {
            "id": "kuafu",
            "origin": "authenticated_host_role",
            "version": binding["version"],
            "definition_sha256": binding["definition_sha256"],
        },
        "evidence_refs": [],
        "payload": payload,
    }
    source_path = folder / (eid + ".json")
    if not source_path.exists():
        write_new(source_path, dict(event, occurred_at=datetime.now(timezone.utc).isoformat()))
    result = subprocess.check_output(
        [
            sys.executable,
            "-I",
            "-X",
            "utf8",
            str(root / "customizations/platforms/data-collection/git-files/storage/diting_files.py"),
            "record",
            "--repo",
            str(root),
            "--input",
            str(source_path),
        ],
        timeout=120,
    )
    receipt = json.loads(result)
    if receipt["state"] != "recorded_file":
        raise ValueError("Diting recording unconfirmed; retain the incident")
    stored_path = root / "gonggong-diting-data/events" / event["tenant_id"] / record["request_id"] / (eid + ".json")
    stored = read(stored_path)
    receipt["sha256"] = stored["sha256"]
    receipt["timeline"] = publish(root, record["issue"], payload, receipt)
    receipt["consumption"] = None
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=Path.cwd())
    commands = p.add_subparsers(dest="command", required=True)
    detect = commands.add_parser("detect")
    detect.add_argument("--issue", type=int, required=True)
    detect.add_argument("--request-id", required=True)
    detect.add_argument(
        "--action",
        required=True,
        choices=[
            "user-report",
            "dependency",
            "permission",
            "validation",
            "delivery",
            "dispatch",
            "unknown-receipt",
            "other",
        ],
    )
    detect.add_argument("--evidence", required=True, help="Reference to the observation, without credentials")
    for name in ("status", "forward"):
        child = commands.add_parser(name)
        child.add_argument("incident")
    for name in ("receive", "assess"):
        child = commands.add_parser(name)
        child.add_argument("incident")
        child.add_argument("--bug", type=int, required=True)
        child.add_argument("--worker", required=True)
        child.add_argument("--authority", required=True)
        if name == "assess":
            for field in ("evidence", "diagnosis", "next-action"):
                child.add_argument("--" + field, required=True)
    args = p.parse_args()
    root = args.repo.resolve()
    if args.command == "detect":
        print(json.dumps(send_to_kuafu(root, capture(root, args.issue, args.request_id, args.action, args.evidence))))
        return
    if not re.fullmatch("[0-9a-f]{64}", args.incident):
        raise ValueError("Invalid private incident key")
    folder = private_root(root) / args.incident
    record = read(folder / "detected.json")
    if args.command == "forward":
        if str(root.resolve()) != record["worktree"]:
            raise ValueError("Use original detecting worktree")
        print(json.dumps(send_to_kuafu(root, {"incident": args.incident, "state": "pending_kuafu_intake"})))
        return
    if args.command == "status":
        print(
            json.dumps({
                "incident": args.incident,
                "detected": record,
                "received": (folder / "received.json").exists(),
                "rechecks": [read(p) for p in sorted(folder.glob("recheck-*.json"))],
            })
        )
        return
    with event_lock(folder / "incident.lock"):
        if args.command == "assess" and not (folder / "received.json").is_file():
            raise ValueError("Receive and read the admitted Kuafu mandate first")
        identity = issue_binding(root, record, args.bug)
        with trusted_framework(root, record["repository"]) as framework:
            context, binding = bind_context(framework, folder, record, args, identity)
            if args.command == "receive":
                sys.stdout.buffer.write(context)
            else:
                print(json.dumps(report(root, framework, folder, record, args.incident, binding, args)))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        sys.exit(str(error))
