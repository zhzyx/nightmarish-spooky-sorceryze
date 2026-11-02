"""Trusted local pre-commit check. This is not authorization or remote acceptance."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import work_items

ACTIVE = {"status:in-progress", "status:in-review"}
REQUEST = r"[a-z0-9]+(?:-[a-z0-9]+)*"


request_ids = work_items.request_ids


def check_issue(value, repository, number, request_id, types):
    expected = f"https://github.com/{repository}/issues/{number}"
    if (
        value.get("number") != number
        or value.get("html_url", "").lower() != expected.lower()
        or "pull_request" in value
    ):
        raise ValueError("Issue must be a real Issue in the configured repository")
    if value.get("state") != "open":
        raise ValueError("Issue is not open")
    names = [v["name"] for v in value.get("labels", [])]
    categories = [x for x in names if x.startswith("type:")]
    statuses = [x for x in names if x.startswith("status:")]
    if len(categories) != 1 or categories[0] not in types:
        raise ValueError("Issue requires exactly one known type label")
    if len(statuses) != 1 or statuses[0] not in ACTIVE:
        raise ValueError("Issue requires exactly one active status label")
    if request_ids(value.get("body")) != {request_id}:
        raise ValueError("Issue stable request ID does not match unambiguously")
    return {
        "url": expected,
        "number": number,
        "type": categories[0],
        "status": statuses[0],
        "updated_at": value.get("updated_at"),
    }


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=120)
    if result.returncode:
        raise ValueError("Git check failed: " + args[0])
    return result.stdout


def check_repository(root, repository):
    if Path(os.fsdecode(git(root, "rev-parse", "--show-toplevel")).strip()).resolve() != root:
        raise ValueError("--repo must be the Git repository root")
    origin = os.fsdecode(git(root, "remote", "get-url", "origin")).strip()
    allowed = {
        f"https://github.com/{repository}",
        f"https://github.com/{repository}.git",
        f"git@github.com:{repository}",
        f"git@github.com:{repository}.git",
        f"ssh://git@github.com/{repository}",
        f"ssh://git@github.com/{repository}.git",
    }
    if origin.lower() not in {v.lower() for v in allowed}:
        raise ValueError("Git origin must match the configured GitHub repository")


def intake(root, number, request_id, tenant):
    """Read the real work order before any host model/tool execution."""
    if type(number) is not int or number < 1 or not re.fullmatch(REQUEST, request_id):
        raise ValueError("Bind a real Issue number and its stable request ID before starting work")
    settings, labels = work_items.config(root)
    if tenant != settings.get("tenant_id"):
        raise ValueError("Host tenant must match work-items.json")
    check_repository(root, settings["repository"])
    value = json.loads(work_items.gh("api", f"repos/{settings['repository']}/issues/{number}"))
    issue = check_issue(value, settings["repository"], number, request_id, {v["name"] for v in labels})
    if "workspace:olympus" not in [v["name"] for v in value.get("labels", [])]:
        raise ValueError("Issue must explicitly include workspace:olympus")
    return issue


def check_collection(root):
    """Sources and receipts are deliverables, even when a local ignore hides them."""
    if git(root, "diff", "HEAD", "--name-only", "--diff-filter=D", "--", "data-collection").strip():
        raise ValueError("Preserve collection sources and receipts; append corrections")
    folder = root / "data-collection"
    if folder.is_symlink() or (hasattr(folder, "is_junction") and folder.is_junction()):
        raise ValueError("Linked collection root is not supported")
    for path in sorted(folder.rglob("*")):
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise ValueError("Linked collection paths are not supported")
        if not path.is_file():
            continue
        name = path.relative_to(root).as_posix()
        if git(root, "show", ":" + name) != path.read_bytes():
            raise ValueError("Collection source/receipt must be staged with current bytes: " + name)


def snapshot(root):
    """Bind HEAD, index and current tracked/nonignored content, including deletions."""
    digest = hashlib.sha256()
    for args in [
        ("rev-parse", "HEAD"),
        ("ls-files", "--stage", "-z"),
        ("diff", "--cached", "--binary", "--no-ext-diff"),
    ]:
        digest.update(git(root, *args))
    paths = set(git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard").split(b"\0")) - {b""}
    for raw in sorted(paths):
        path = root / os.fsdecode(raw)
        digest.update(raw + b"\0")
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise ValueError("Linked working-tree paths are not supported by the local gate")
        if path.is_file():
            digest.update(hashlib.sha256(path.read_bytes()).digest())
        elif path.exists():
            raise ValueError("Submodules/directories require their own reviewed delivery binding")
        else:
            digest.update(b"DELETED")
    return digest.hexdigest()


def environment(root):
    env = os.environ.copy()
    source = env.get("GONGGONG_FRAMEWORK_SOURCE")
    if not source:
        local = root / ".olympus-local.json"
        if local.exists():
            source = work_items.read(local).get("GONGGONG_FRAMEWORK_SOURCE")
    if source:
        env["GONGGONG_FRAMEWORK_SOURCE"] = str((root / source).resolve())
    return env


def check_history(root):
    paths = git(root, "ls-tree", "-r", "--name-only", "-z", "HEAD", "--", "olympus-hermes-data/events")
    for raw in paths.split(b"\0"):
        if not raw:
            continue
        name = os.fsdecode(raw)
        path = root / name
        if not path.is_file() or path.read_bytes() != git(root, "show", "HEAD:" + name):
            raise ValueError("Hermes history must remain immutable; append correction events")


def validate_command(command, root, env, name):
    result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", timeout=300)
    if result.returncode:
        # Do not echo subprocess output: it may contain local paths or credentials.
        raise ValueError(name + " failed; run the trusted validator locally for details")
    return json.loads(result.stdout)


def gate(root, number, request_id):
    if number < 1 or not re.fullmatch(REQUEST, request_id):
        raise ValueError("Positive Issue number and stable request ID required")
    settings, labels = work_items.config(root)
    repository = settings["repository"]
    tenant = settings.get("tenant_id")
    if not isinstance(tenant, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}", tenant):
        raise ValueError("Explicit repository tenant_id binding required")
    check_repository(root, repository)
    # The framework verifies working files; refuse a different version in the index.
    git(root, "diff", "--quiet", "--no-ext-diff", "--ignore-submodules=none")

    def fetch():
        return check_issue(
            json.loads(work_items.gh("api", f"repos/{repository}/issues/{number}")),
            repository,
            number,
            request_id,
            {v["name"] for v in labels},
        )

    issue = fetch()
    before = snapshot(root)
    env = environment(root)
    framework = validate_command(
        [sys.executable, "-X", "utf8", str(root / "Olympus/tools/verify_framework.py")],
        root,
        env,
        "Formal Olympus verification",
    )
    if framework.get("mode") != "approved_file_integrity":
        raise ValueError("Formal Olympus verification required; candidate mode is insufficient")
    validate_command(
        [
            sys.executable,
            "-X",
            "utf8",
            str(root / "Olympus/extensions/hermes-files/hermes_files.py"),
            "validate",
            "--repo",
            str(root),
        ],
        root,
        env,
        "Hermes validation",
    )
    validate_command(
        [
            sys.executable,
            "-X",
            "utf8",
            str(root / "Olympus/extensions/hermes-files/hermes_files.py"),
            "git-check",
            "--repo",
            str(root),
        ],
        root,
        env,
        "Hermes Git history check",
    )
    check_history(root)
    check_collection(root)
    events = []
    request_source_found = False
    issue_sources = {issue["url"], f"github:{repository}:issue:{number}"}
    for path in sorted((root / "olympus-hermes-data/events").rglob("*.json")):
        raw = path.read_bytes()
        value = json.loads(raw)
        if value.get("request_id") == request_id and value.get("tenant_id") == tenant:
            git(root, "ls-files", "--error-unmatch", "--", path.relative_to(root).as_posix())
            events.append({"path": path.relative_to(root).as_posix(), "sha256": hashlib.sha256(raw).hexdigest()})
            if value.get("kind") == "request" and value.get("source_ref") in issue_sources:
                request_source_found = True
    if not events:
        raise ValueError("No actual Hermes events for this request")
    if not request_source_found:
        raise ValueError("No same-tenant request event with exact Issue source")
    if snapshot(root) != before or fetch() != issue:
        raise ValueError("Content or Issue changed during check; rerun before commit")
    return {
        "state": "local_checks_passed",
        "issue": issue,
        "request_id": request_id,
        "tenant_id": tenant,
        "content_sha256": before,
        "events": events,
        "framework_mode": framework["mode"],
        "host_authority_authenticated": False,
        "approval_granted": False,
        "diting_ingestion_confirmed": False,
        "remote_merge_verified": False,
        "scope": "Current local content and index only; rerun after any change. Business acceptance is separate.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--intake-only", action="store_true")
    parser.add_argument("--tenant")
    args = parser.parse_args()
    result = (
        intake(args.repo.resolve(), args.issue, args.request_id, args.tenant)
        if args.intake_only
        else gate(args.repo.resolve(), args.issue, args.request_id)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        sys.exit(str(error))
