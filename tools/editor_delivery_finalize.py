"""Finish one host-bound signed delivery without reopening production intake."""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

INSTALLATION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INSTALLATION / "customizations/components/issue-workorders"))
sys.path.insert(0, str(INSTALLATION / "tools"))


def installed_module(name, relative):
    spec = importlib.util.spec_from_file_location(name, INSTALLATION / relative)
    if spec is None or spec.loader is None:
        raise ImportError("Installed delivery dependency is unavailable: " + relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


submission = installed_module("delivery_writer", "customizations/components/issue-workorders/writer_submit.py")
yanluo_progress = installed_module("delivery_progress", "customizations/components/issue-workorders/yanluo_progress.py")
_storage = installed_module(
    "delivery_storage", "customizations/platforms/data-collection/git-files/storage/diting_files.py"
)

_candidate = installed_module("delivery_candidate", "tools/editor_engine_candidate.py")
_activation = installed_module("delivery_activation", "tools/editor_candidate_activation.py")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def read_json(path):
    require(
        path.is_file() and not path.is_symlink() and path.stat().st_size <= 16 * 1024 * 1024, "Invalid delivery record"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def late_telemetry(root, binding):
    """Only canonical late events for this exact work order may remain uncommitted."""
    settings = json.loads((root / "work-items.json").read_text(encoding="utf-8"))
    tenant = settings.get("tenant_id")
    require(
        isinstance(tenant, str) and re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}", tenant), "Invalid work-order tenant"
    )
    raw = subprocess.check_output(
        ["git", "-C", str(root), "ls-files", "--others", "--exclude-standard", "-z"], timeout=120
    )
    names = [os.fsdecode(item) for item in raw.split(b"\0") if item]
    require(len(names) <= 4096, "Too many uncommitted delivery inputs")
    prefix = Path("gonggong-diting-data/events") / tenant / binding["request_id"]
    observed = []
    for name in names:
        relative = Path(name)
        require(
            relative.parent == prefix and relative.suffix == ".json", "Uncommitted production or design input remains"
        )
        path = root / relative
        require(not any(item.is_symlink() for item in (path, *path.parents)), "Linked delivery input is not allowed")
        value = read_json(path)
        normalized = _storage.event(value)
        require(
            type(value.get("schema_version")) is int
            and value.get("sha256") == normalized["sha256"]
            and value.get("tenant_id") == tenant
            and value.get("request_id") == binding["request_id"]
            and value.get("source_ref") == f"https://github.com/{binding['repository']}/issues/{binding['issue']}"
            and relative.name == value.get("event_id", "") + ".json",
            "Late event does not belong to this exact work order",
        )
        observed.append({"path": relative.as_posix(), "sha256": normalized["sha256"]})
    return {
        "count": len(observed),
        "manifest_sha256": hashlib.sha256(canonical(observed).encode()).hexdigest(),
        "git_committed": False,
        "scope": "Only events observed at finalizer start; later host events remain separate",
    }


def host_scope(root, request):
    require(
        request.get("schema_version") == 1 and type(request.get("schema_version")) is int,
        "Unsupported delivery request",
    )
    require(type(request.get("pr")) is int and request["pr"] > 0, "A real PR number is required")
    require(request.get("source_root") == str(root), "Host source root differs")
    for key in ("owner", "snapshot_id", "nonce"):
        value = request.get(key)
        require(
            isinstance(value, str) and 0 < len(value) <= 128 and not any(ord(c) < 32 for c in value),
            "Invalid host identity",
        )
    require(type(request.get("generation")) is int and request["generation"] >= 0, "Invalid host generation")
    for key in ("expected_candidate", "expected_signed_commit"):
        require(
            isinstance(request.get(key), str) and re.fullmatch(r"[a-f0-9]{40}", request[key]),
            "Exact candidate and signed head required",
        )
    binding = request.get("binding")
    require(isinstance(binding, dict), "Host candidate binding required")
    common, repository, origin = _candidate.identity(root)
    issue, request_id = binding.get("issue"), binding.get("request_id")
    require(
        type(issue) is int
        and issue > 0
        and isinstance(request_id, str)
        and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", request_id),
        "Invalid work-order binding",
    )
    digest = _candidate.candidate_digest(common, repository, issue, request_id, request["owner"])
    path = common / "gonggong-engine-candidates" / (digest + ".json")
    require(str(path) == binding.get("binding_path"), "Candidate journal differs from host binding")
    recorded = read_json(path)
    expected = {
        "version": 1,
        "owner": request["owner"],
        "issue": issue,
        "request_id": request_id,
        "common_dir": str(common),
        "repository": repository,
        "origin": origin,
        "source_root": str(root),
        "branch": binding.get("branch"),
        "base_sha": binding.get("base_sha"),
    }
    differing = [key for key, value in expected.items() if binding.get(key) != value]
    require(not differing, "Host candidate identity differs: " + ", ".join(differing))
    require(recorded.get("state") == "prepared", "Candidate preparation incomplete")
    _candidate.validate_source(root, recorded, expected)
    require(not submission.git(root, "diff", "--name-only", "HEAD", "--"), "Source changed after signed delivery")
    head = submission.git(root, "rev-parse", "HEAD")
    require(head == request["expected_candidate"], "Current source differs from expected candidate")
    return common, recorded, head, late_telemetry(root, recorded)


def verified_checks(repository, pr, signed):
    value = json.loads(
        submission.work_items.gh("pr", "view", str(pr), "-R", repository, "--json", "headRefOid,statusCheckRollup")
    )
    require(value.get("headRefOid") == signed, "PR head changed during completion")
    checks = value.get("statusCheckRollup")
    require(isinstance(checks, list) and checks, "CI readback is missing")
    summary = []
    for check in checks:
        if check.get("__typename") == "StatusContext":
            state = check.get("state")
            name = check.get("context", "")
            require(state == "SUCCESS", "CI is pending or failed")
        else:
            state = check.get("conclusion")
            name = check.get("name", "")
            require(check.get("status") == "COMPLETED" and state in {"SUCCESS", "SKIPPED"}, "CI is pending or failed")
        summary.append({"name": str(name)[:256], "state": state})
    return summary


def issue_readback(repository, number, request_id, known_types):
    value = json.loads(
        submission.work_items.gh(
            "issue", "view", str(number), "-R", repository, "--json", "number,url,state,stateReason,body,labels"
        )
    )
    require(
        value.get("number") == number
        and value.get("url", "").lower() == f"https://github.com/{repository}/issues/{number}".lower(),
        "Issue identity differs",
    )
    require(submission.work_items.request_ids(value.get("body")) == {request_id}, "Issue request identity differs")
    labels = [item["name"] for item in value.get("labels", [])]
    categories = [name for name in labels if name.startswith("type:")]
    require(
        "workspace:gonggong" in labels and len(categories) == 1 and categories[0] in known_types, "Issue scope differs"
    )
    return value, [name for name in labels if name.startswith("status:")]


def acceptance_declaration(value):
    require(isinstance(value, list) and 0 < len(value) <= 64, "The complete original acceptance checklist is required")
    for item in value:
        require(
            isinstance(item, dict) and set(item) == {"id", "module", "acceptance", "state", "evidence"},
            "Invalid acceptance declaration",
        )
        require(
            all(isinstance(item[key], str) and 0 < len(item[key]) <= 4096 for key in item),
            "Acceptance fields must be bounded text",
        )
    result = yanluo_progress.assess(value)
    require(result["complete"], "Remaining or unknown acceptance must keep the Issue open")
    return {
        "source": "authorized_worker_declaration",
        "items": value,
        "sha256": hashlib.sha256(canonical(value).encode()).hexdigest(),
    }


def compact_report(report):
    keys = (
        "repository",
        "issue",
        "request_id",
        "candidate",
        "signed_commit",
        "tree",
        "current_main",
        "merge_commit",
        "pull_request",
        "pr_state",
        "issue_receipt",
        "delivered_paths_differ",
    )
    return {key: report.get(key) for key in keys}


def publish_declaration(repository, scope, declaration):
    marker = "<!-- native-delivery:" + hashlib.sha256(canonical(scope).encode()).hexdigest() + " -->"
    pages = json.loads(
        submission.work_items.gh("api", f"repos/{repository}/issues/{scope['issue']}/comments", "--paginate", "--slurp")
    )
    require(
        isinstance(pages, list) and all(isinstance(page, list) for page in pages),
        "Issue comments could not be reconciled",
    )
    if any(marker in item.get("body", "") for page in pages for item in page):
        return
    body = (
        marker
        + "\n\nNative host delivery readback: signed candidate `"
        + scope["candidate"]
        + "`.\n\nAcceptance below is the responsible worker's explicit declaration, not inferred from process exit or CI.\n\n```json\n"
        + json.dumps(declaration, ensure_ascii=False, indent=2)
        + "\n```\n"
    )
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "acceptance.txt"
        path.write_text(body, encoding="utf-8")
        submission.work_items.gh("issue", "comment", str(scope["issue"]), "-R", repository, "--body-file", str(path))


def complete(root, request):
    root = Path(root).absolute()
    result = {
        "schema_version": 1,
        "kind": "native_delivery_finalization",
        "ok": False,
        "completion_verified": False,
        "mutations_may_have_started": False,
        "stage": "validation",
    }
    for key in ("owner", "snapshot_id", "generation", "nonce"):
        result[key] = request.get(key)
    binding = request.get("binding", {})
    result["issue"] = binding.get("issue") if isinstance(binding, dict) else None
    result["request_id"] = binding.get("request_id") if isinstance(binding, dict) else None
    result["source_root"] = str(root)
    diagnostic_folder = None
    try:
        common, binding, candidate, late = host_scope(root, request)
        result["late_telemetry_at_start"] = late
        repository = binding["repository"]
        known_types = {item["name"] for item in submission.work_items.config(root)[1]}
        submission.writer(repository)  # Re-read current collaborator write permission.
        report = submission.inspect_pr(root, repository, request["pr"])
        require(
            report.get("pr_state") == "MERGED" and report.get("delivered_paths_differ") == [],
            "Verified main delivery is required",
        )
        require(
            report.get("candidate") == candidate
            and report.get("issue") == binding["issue"]
            and report.get("request_id") == binding["request_id"],
            "PR does not belong to this host work order and candidate",
        )
        require(
            report.get("signed_commit") == request["expected_signed_commit"],
            "Signed head differs from approved completion",
        )
        require(
            submission.git(root, "merge-base", candidate, report["current_main"]) == candidate,
            "Candidate is not contained in main",
        )
        checks = verified_checks(repository, request["pr"], report["signed_commit"])
        declaration = acceptance_declaration(request.get("acceptance_items"))
        scope = {
            key: report[key] for key in ("repository", "issue", "request_id", "candidate", "signed_commit", "tree")
        }
        scope.update(owner=request["owner"], source_root=str(root), acceptance_sha256=declaration["sha256"])
        key = hashlib.sha256(
            canonical({key: value for key, value in scope.items() if key != "acceptance_sha256"}).encode()
        ).hexdigest()
        lock_key = hashlib.sha256(canonical([repository, binding["issue"], binding["request_id"]]).encode()).hexdigest()
        folder = common / "gonggong-delivery-finalization"
        require(not folder.is_symlink(), "Invalid delivery journal directory")
        folder.mkdir(mode=0o700, exist_ok=True)
        diagnostic_folder = folder / "attempts"
        require(not diagnostic_folder.is_symlink(), "Invalid delivery attempts directory")
        diagnostic_folder.mkdir(mode=0o700, exist_ok=True)
        with _candidate.binding_lock(folder / (lock_key + ".lock")):
            path = folder / (key + ".json")
            saved = read_json(path) if path.exists() else {"scope": scope, "prior_status": None}
            require(saved.get("scope") == scope, "Delivery journal identity differs")
            issue, statuses = issue_readback(repository, binding["issue"], binding["request_id"], known_types)
            if issue.get("state") == "CLOSED":
                require(
                    issue.get("stateReason") == "COMPLETED" and statuses == ["status:done"],
                    "Issue closed for another reason",
                )
            else:
                require(issue.get("state") == "OPEN", "Unknown Issue state")
                prior = saved.get("prior_status")
                require(
                    statuses == ["status:done"]
                    or (prior is None and statuses in (["status:in-progress"], ["status:in-review"]))
                    or (
                        prior in {"status:in-progress", "status:in-review"}
                        and (statuses == [prior] or set(statuses) == {prior, "status:done"})
                    ),
                    "Concurrent Issue status mutation",
                )
                if prior is None and len(statuses) == 1 and statuses[0] != "status:done":
                    saved["prior_status"] = statuses[0]
                _candidate.atomic_json(path, saved)
                result["stage"] = "completion_write"
                result["mutations_may_have_started"] = True
                publish_declaration(repository, scope, declaration)
                if "status:done" not in statuses:
                    submission.work_items.gh(
                        "issue", "edit", str(binding["issue"]), "-R", repository, "--add-label", "status:done"
                    )
                issue, statuses = issue_readback(repository, binding["issue"], binding["request_id"], known_types)
                prior = saved.get("prior_status")
                require(
                    statuses == ["status:done"] or (prior and set(statuses) == {prior, "status:done"}),
                    "Concurrent Issue status mutation",
                )
                if prior in statuses:
                    submission.work_items.gh(
                        "issue", "edit", str(binding["issue"]), "-R", repository, "--remove-label", prior
                    )
                issue, statuses = issue_readback(repository, binding["issue"], binding["request_id"], known_types)
                require(statuses == ["status:done"], "Completion label was not observed")
                if issue["state"] == "OPEN":
                    submission.work_items.gh(
                        "issue", "close", str(binding["issue"]), "-R", repository, "--reason", "completed"
                    )
            result["stage"] = "closure_readback"
            report = submission.inspect_pr(root, repository, request["pr"])
            receipt = report.get("issue_receipt", {})
            require(
                report.get("candidate") == candidate
                and report.get("signed_commit") == scope["signed_commit"]
                and report.get("delivered_paths_differ") == [],
                "Delivery changed during finalization",
            )
            require(
                receipt.get("state") == "CLOSED"
                and receipt.get("reason") == "COMPLETED"
                and receipt.get("labels", []).count("status:done") == 1
                and len([v for v in receipt["labels"] if v.startswith("status:")]) == 1,
                "Issue completion has not been verified",
            )
            result["host_facts"] = compact_report(report)
            result["ci"] = checks
            result["acceptance_declaration"] = declaration
            result["completion_verified"] = True
            result["stage"] = "activation"
            result["mutations_may_have_started"] = True
            submission.writer(repository)  # Revoked repository authority never authorizes an entry update.
            # Existing adapter verifies artifact/source/binding before any entry update.
            activation = _activation.after_delivery(root, report)
            result["engine_launch_activation"] = activation
            result["ok"] = activation.get("state") in {"activated", "not_applicable"}
            result["stage"] = "completed" if result["ok"] else "activation_pending"
            saved["last_receipt"] = result
            _candidate.atomic_json(path, saved)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as error:
        result["error"] = str(error)[:1000]
    if diagnostic_folder is not None:
        diagnostic = diagnostic_folder / (uuid.uuid4().hex + ".json")
        result["private_diagnostic_ref"] = str(diagnostic)
        try:
            _candidate.atomic_json(diagnostic, result)
        except OSError:
            result["private_diagnostic_write_failed"] = True
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    request = read_json(args.request)
    result = complete(args.source_root, request)
    _candidate.atomic_json(args.out, result)
    return 0 if result["completion_verified"] else 1


if __name__ == "__main__":
    sys.exit(main())
