"""Trusted local pre-commit check. This is not authorization or remote acceptance."""

import argparse
import hashlib
import json
import os
import re
import runpy
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import work_items

BATCH_PATH = Path(__file__).resolve().parents[3] / "framework/tools/git_batch.py"
BATCH_SOURCE = BATCH_PATH.read_bytes()
GATE_SOURCE = Path(__file__).read_bytes()
BATCH = runpy.run_path(str(BATCH_PATH))

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
    if "workspace:gonggong" not in names:
        raise ValueError("Issue must explicitly include workspace:gonggong")
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
        if args[:2] == ("diff", "--quiet") and result.returncode == 1:
            raise ValueError(
                "WORKTREE_UNSTAGED: working files differ from index; stage only this task in an isolated worktree. Framework admission has not run."
            )
        error = result.stderr.decode("utf-8", errors="replace").lower()
        if "permission denied" in error or "access is denied" in error:
            raise ValueError(
                "GIT_PERMISSION: " + args[0] + " denied; use the host-authorized execution channel, not a gate bypass"
            )
        if "index.lock" in error or "cannot lock ref" in error:
            raise ValueError(
                "GIT_LOCK: "
                + args[0]
                + " blocked; identify the owning operation before retrying; do not delete another worker's lock"
            )
        raise ValueError(
            "GIT_COMMAND: "
            + args[0]
            + " failed (exit "
            + str(result.returncode)
            + "); inspect the trusted command locally"
        )
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
    return issue


def check_collection(root):
    """Sources and receipts are deliverables, even when a local ignore hides them."""
    if git(root, "diff", "HEAD", "--no-renames", "--name-only", "--diff-filter=MDT", "--", "data-collection").strip():
        raise ValueError("Preserve collection sources and receipts; append corrections")
    folder = root / "data-collection"
    if folder.is_symlink() or (hasattr(folder, "is_junction") and folder.is_junction()):
        raise ValueError("Linked collection root is not supported")
    batch = BATCH
    index = batch["objects"](root, ":", ["data-collection"])
    tracked = batch["tracked"](root)
    private_paths = []
    for path in sorted(folder.rglob("*")):
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise ValueError("Linked collection paths are not supported")
        if not path.is_file():
            continue
        name = path.relative_to(root).as_posix()
        relative = path.relative_to(folder)
        # Raw host state is private; only explicit source/evidence files are deliverables.
        private = relative.parts[0] in {"inbox", "outbox", "receipts"} or (
            len(relative.parts) == 1
            and (
                relative.name.endswith(".local.json")
                or re.fullmatch(r".+\.sqlite(?:-wal|-shm|-journal)?", relative.name)
            )
        )
        if private:
            if os.fsencode(name) in tracked:
                raise ValueError("Host-private collection state must not enter Git: " + name)
            private_paths.append(os.fsencode(name))
            continue
        if index.get(os.fsencode(name)) != path.read_bytes():
            raise ValueError("Collection source/receipt must be staged with current bytes: " + name)

    if set(private_paths) - batch["ignored"](root, private_paths):
        raise ValueError("Host-private collection state must remain ignored")


def snapshot(root):
    """Bind HEAD, index and current tracked/nonignored content, including deletions."""
    digest = hashlib.sha256()
    for args in [
        ("rev-parse", "HEAD"),
        ("ls-files", "--stage", "-z"),
    ]:
        digest.update(git(root, *args))
    paths = set(git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard").split(b"\0")) - {b""}

    def content_hash(raw):
        path = root / os.fsdecode(raw)
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise ValueError("Linked working-tree paths are not supported by the local gate")
        if path.is_file():
            with path.open("rb") as stream:
                content = hashlib.sha256()
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    content.update(block)
                return content.digest()
        if path.exists():
            raise ValueError("Submodules/directories require their own reviewed delivery binding")
        return b"DELETED"

    ordered = sorted(paths)
    # Bounded parallel I/O; map preserves deterministic path order and propagates failures.
    with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 1)) as pool:
        for raw, value in zip(ordered, pool.map(content_hash, ordered)):
            digest.update(raw + b"\0")
            digest.update(value)
    return digest.hexdigest()


def environment(root):
    return os.environ.copy()


def check_history(root):
    batch = BATCH
    head = batch["objects"](root, "HEAD", ["gonggong-diting-data/events", "olympus-hermes-data/events"])
    for raw, original in head.items():
        name = os.fsdecode(raw)
        path = root / name
        if not path.is_file() or path.read_bytes() != original:
            raise ValueError("Diting history must remain immutable; append correction events")


def validate_command(command, root, env, name):
    try:
        result = subprocess.run(
            command, cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", timeout=300
        )
    except subprocess.TimeoutExpired:
        raise ValueError(
            "VALIDATOR_TIMEOUT: "
            + name
            + " exceeded 300 seconds; verify the worktree baseline and runtime; result is unknown"
        ) from None
    if result.returncode:
        # Do not echo subprocess output: it may contain local paths or credentials.
        raise ValueError(name + " failed; run the trusted validator locally for details")
    return json.loads(result.stdout)


def check_pr_evidence(root, issue, request_id, tenant, base_ref):
    """Mirror issue-association on the PR diff, using the candidate index bytes."""
    base = git(root, "merge-base", "HEAD", base_ref).decode().strip()
    names = git(root, "diff", "--cached", "--name-only", "--no-renames", "--diff-filter=ACMT", "-z", base, "--").split(
        b"\0"
    )
    matching_event = False
    matching_collection = False
    for raw in names:
        name = os.fsdecode(raw)
        event = name.startswith("gonggong-diting-data/events/" + tenant + "/")
        collection = name.startswith("data-collection/")
        if not name.endswith(".json") or not (event or collection):
            continue
        try:
            value = json.loads(git(root, "show", ":" + name))
        except (ValueError, UnicodeError):
            raise ValueError("PR_EVIDENCE_JSON: invalid candidate JSON at " + name) from None
        if not isinstance(value, dict):
            raise ValueError("PR_EVIDENCE_JSON: expected an object at " + name)
        if value.get("request_id") != request_id:
            continue
        if event and value.get("tenant_id") == tenant:
            matching_event = True
        if collection and (
            value.get("issue") == issue["url"]
            or value.get("issue_url") == issue["url"]
            or type(value.get("issue_number")) is int
            and value["issue_number"] == issue["number"]
        ):
            matching_collection = True
    if matching_event and not matching_collection:
        raise ValueError(
            "PR_EVIDENCE_BINDING: Recorded Diting event must be delivered with matching data-collection evidence; include request_id and issue_url/issue/issue_number in a JSON file changed in this PR"
        )
    return {"base_commit": base, "matching_event": matching_event, "matching_collection": matching_collection}


def gate(root, number, request_id, session=None, base_ref="origin/main"):
    if session is not None:
        session.check_runtime()
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
    association = check_pr_evidence(root, issue, request_id, tenant, base_ref)
    env = environment(root)
    framework = validate_command(
        [sys.executable, "-X", "utf8", str(root / "framework/tools/verify_framework.py")],
        root,
        env,
        "Formal GongGong verification",
    )
    if framework.get("mode") != "approved_file_integrity":
        raise ValueError("Formal GongGong verification required; candidate mode is insufficient")
    if session is None:
        validate_command(
            [
                sys.executable,
                "-X",
                "utf8",
                str(root / "framework/extensions/diting-files/diting_files.py"),
                "git-check",
                "--repo",
                str(root),
            ],
            root,
            env,
            "Diting Git history check",
        )
    else:
        session.check_diting(root)
    check_history(root)
    check_collection(root)
    events = []
    request_source_found = False
    issue_sources = {issue["url"], f"github:{repository}:issue:{number}"}
    tracked_events = set(git(root, "ls-files", "-z", "--", "gonggong-diting-data/events").split(b"\0"))
    for path in sorted((root / "gonggong-diting-data/events" / tenant / request_id).glob("*.json")):
        raw = path.read_bytes()
        value = json.loads(raw)
        if value.get("request_id") == request_id and value.get("tenant_id") == tenant:
            if os.fsencode(path.relative_to(root).as_posix()) not in tracked_events:
                raise ValueError("Request event must be staged")
            events.append({"path": path.relative_to(root).as_posix(), "sha256": hashlib.sha256(raw).hexdigest()})
            if value.get("kind") == "request" and value.get("source_ref") in issue_sources:
                request_source_found = True
    if not events:
        raise ValueError("No actual Diting events for this request")
    if not request_source_found:
        raise ValueError("No same-tenant request event with exact Issue source")
    if snapshot(root) != before or fetch() != issue:
        raise ValueError("Content or Issue changed during check; rerun before commit")
    if (
        association.get("base_commit")
        and git(root, "merge-base", "HEAD", base_ref).decode().strip() != association["base_commit"]
    ):
        raise ValueError("PR_BASE_CHANGED: target merge-base changed during verification; recheck the PR scope")
    return {
        "state": "local_checks_passed",
        "issue": issue,
        "request_id": request_id,
        "tenant_id": tenant,
        "content_sha256": before,
        "pr_evidence": association,
        "events": events,
        "framework_mode": framework["mode"],
        "host_authority_authenticated": False,
        "approval_granted": False,
        "diting_ingestion_confirmed": False,
        "remote_merge_verified": False,
        "scope": "Current local content and index only; rerun after any change. Business acceptance is separate.",
    }


class VerificationSession:
    """Optional explicit-request session; no background polling or disk success cache."""

    def __init__(self):
        self.binding = None
        self.module = None
        self.events = {}

    def check_runtime(self):
        if Path(__file__).read_bytes() != GATE_SOURCE or BATCH_PATH.read_bytes() != BATCH_SOURCE:
            self.events.clear()
            raise ValueError("Gate implementation changed; restart the verification session")

    def check_diting(self, root):
        validator = root / "framework/extensions/diting-files/diting_files.py"
        batch = root / "framework/tools/git_batch.py"
        binding = (str(root.resolve()), validator.read_bytes(), batch.read_bytes(), sys.version)
        if binding != self.binding:
            self.module = runpy.run_path(str(validator))
            self.events.clear()
            self.binding = binding
        try:
            return self.module["git_check"](root, cache=self.events)
        except Exception:
            self.events.clear()
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--issue", type=int)
    parser.add_argument("--request-id")
    parser.add_argument(
        "--session",
        action="store_true",
        help="Read explicit JSON requests from stdin; reuse only exact-byte event evidence in memory",
    )
    parser.add_argument("--intake-only", action="store_true")
    parser.add_argument("--tenant")
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Fetched PR target; compare merge-base to candidate index, including already committed PR changes",
    )
    args = parser.parse_args()
    if args.session:
        if args.intake_only or args.issue is not None or args.request_id is not None:
            parser.error("--session takes issue/request_id from each input line")
        session = VerificationSession()
        for line in sys.stdin:
            request = {}
            try:
                request = json.loads(line)
                result = gate(args.repo.resolve(), request["issue"], request["request_id"], session, args.base_ref)
                from kuafu_incident import observe_success

                observe_success(
                    args.repo.resolve(), request["issue"], request["request_id"], "validation", result, args.base_ref
                )
                print(json.dumps(result, ensure_ascii=False), flush=True)
            except Exception as error:
                session.events.clear()
                result = {"state": "failed", "error": str(error)}
                if isinstance(request, dict) and request.get("issue") and request.get("request_id"):
                    from kuafu_incident import notify_failure

                    result["kuafu"] = notify_failure(
                        args.repo.resolve(), request["issue"], request["request_id"], "validation", error, args.base_ref
                    )
                print(json.dumps(result), flush=True)
        return
    if args.issue is None or args.request_id is None:
        parser.error("--issue and --request-id are required")
    try:
        result = (
            intake(args.repo.resolve(), args.issue, args.request_id, args.tenant)
            if args.intake_only
            else gate(args.repo.resolve(), args.issue, args.request_id, base_ref=args.base_ref)
        )
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        from kuafu_incident import notify_failure

        notify_failure(
            args.repo.resolve(),
            args.issue,
            args.request_id,
            "intake" if args.intake_only else "validation",
            error,
            args.tenant if args.intake_only else args.base_ref,
        )
        raise
    from kuafu_incident import observe_success

    observe_success(
        args.repo.resolve(),
        args.issue,
        args.request_id,
        "intake" if args.intake_only else "validation",
        result,
        args.tenant if args.intake_only else args.base_ref,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        sys.exit(str(error))
