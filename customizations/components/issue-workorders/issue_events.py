"""Explicit, single-event GitHub intake for the GongGong workspace; no scheduler."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from work_items import gh, request_ids


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path, value, staging=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".issue-pending-", dir=staging or path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)  # Atomic publication, never overwrites an observation.
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextmanager
def event_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if not path.stat().st_size:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    # Keep the inode: deleting it would let competing processes lock different files.


def remote_event(repository, number, event_id):
    pages = json.loads(gh("api", f"repos/{repository}/issues/{number}/events?per_page=100", "--paginate", "--slurp"))
    matches = [event for page in pages for event in page if event.get("id") == event_id]
    if len(matches) != 1:
        raise ValueError("Exactly one actual event on the specified Issue is required")
    issue = json.loads(gh("api", f"repos/{repository}/issues/{number}"))
    if (
        issue.get("number") != number
        or "pull_request" in issue
        or issue.get("html_url") != f"https://github.com/{repository}/issues/{number}"
    ):
        raise ValueError("Remote Issue identity mismatch")
    return matches[0], issue


def mapping(issue, request_id, allowed_types):
    labels = [item["name"] for item in issue["labels"]]
    if "workspace:gonggong" not in labels:
        raise ValueError("This intake only handles explicitly labeled GongGong work")
    if request_ids(issue.get("body")) != {request_id}:
        raise ValueError("Remote request identity is missing or ambiguous")
    types = [label for label in labels if label.startswith("type:")]
    statuses = [label for label in labels if label.startswith("status:")]
    if len(types) != 1 or len(statuses) != 1:
        raise ValueError("Exactly one type and status label required")
    if types[0] not in allowed_types:
        raise ValueError("Unknown task category")
    if statuses[0] not in {
        "status:" + state
        for state in ("needs-decision", "planned", "in-progress", "blocked", "in-review", "done", "cancelled")
    }:
        raise ValueError("Unknown workflow status")
    # Only explicit machine-readable relations are dependencies. Ordinary #links
    # in prose are references, never an instruction to dispatch or close work.
    dependencies = sorted(
        set(int(n) for n in re.findall(r"<!--\s*gonggong-depends-on:#([1-9][0-9]*)\s*-->", issue.get("body") or ""))
    )
    body = issue.get("body") or ""
    host_markers = re.findall(r"<!--\s*gonggong-host-git:([A-Za-z0-9-]+)\s*-->", body)
    host_fields = re.findall(r"^### 宿主 GitHub 账号\s*\n+([A-Za-z0-9-]+)[ \t]*(?=\r?$)", body, re.M)
    host_accounts = set(host_markers + host_fields)
    if len(host_accounts) > 1:
        raise ValueError("Conflicting host GitHub account identities")
    return {
        "lifecycle": issue["state"],
        "category": types[0],
        "status": statuses[0],
        "assignees": sorted(a["login"] for a in issue["assignees"]),
        "host_git_account": next(iter(host_accounts), None),
        "host_account_source": "issue_body_claim_unverified" if host_accounts else "legacy_issue_unknown",
        "dependencies": dependencies,
        "dependency_coverage": "explicit_markers_only",
        "decision_required": statuses[0] == "status:needs-decision",
        "coordination": "associate_only_no_dispatch",
        "parent_auto_close": False,
        "processed_workspace": "gonggong",
        "other_workspace_processed": False,
    }


def intake(root, number, event_id, host_id, tenant, request_id, definition):
    root = root.resolve()
    settings = read(root / "work-items.json")
    repository = settings["repository"]
    if tenant != settings["tenant_id"]:
        raise ValueError("Tenant must match the workspace configuration")
    allowed_types = {label["name"] for label in read(root / ".github/labels.json")}
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repository):
        raise ValueError("Invalid repository")
    for value in (host_id, tenant, request_id):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}", value):
            raise ValueError("Invalid host, tenant or request identity")
    if number < 1 or event_id < 1:
        raise ValueError("Positive Issue and real event ID required")
    definition = (root / definition).resolve()
    definition.relative_to(root)
    definition_hash = hashlib.sha256(definition.read_bytes()).hexdigest()
    identity = {"repository": repository, "issue": number, "event_id": event_id}
    key = digest(identity)
    folder = root / "data-collection/issue-events" / key
    folder.resolve().relative_to(root)
    binding = {"host_id": host_id, "tenant_id": tenant, "request_id": request_id, "definition_sha256": definition_hash}
    lock = root / ".gonggong-outbox/issue-events" / (key + ".lock")
    lock.resolve().relative_to(root)
    with event_lock(lock):
        envelope_path = folder / "envelope.json"
        if envelope_path.exists():
            envelope = read(envelope_path)
            if envelope["payload"]["binding"] != binding or envelope["payload"]["remote_identity"] != identity:
                raise ValueError("An existing event has a different binding; refusing reattribution")
        else:
            event, issue = remote_event(repository, number, event_id)
            state = mapping(issue, request_id, allowed_types)
            payload = {
                "remote_identity": identity,
                "binding": binding,
                "mapping": state,
                "remote_event": {name: event.get(name) for name in ("id", "node_id", "event", "created_at")},
                "remote_event_actor_login": (event.get("actor") or {}).get("login"),
                "revision_marker": {
                    "key": key,
                    "issue_updated_at": issue["updated_at"],
                    "issue_body_sha256": hashlib.sha256((issue.get("body") or "").encode()).hexdigest(),
                    "recognition": "observed_event_and_current_issue_snapshot; no_atomic_remote_update_claim",
                },
                "issue_updated_at": issue["updated_at"],
                "issue_body_sha256": hashlib.sha256((issue.get("body") or "").encode()).hexdigest(),
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "snapshot_scope": "Issue state at explicit read time, not reconstructed historical state",
                "input_tokens": None,
                "output_tokens": None,
                "usage_reason": "Not measured",
                "sinan_source_registered": False,
                "diting_consumption_confirmed": False,
                "host_authority_authenticated": False,
            }
            envelope = {
                "schema_version": 1,
                "event_id": "github-" + key,
                "tenant_id": tenant,
                "request_id": request_id,
                "kind": "step",
                "occurred_at": payload["observed_at"],
                "source_ref": f"github:{repository}:issue:{number}:event:{event_id}",
                "agent": {
                    "id": host_id,
                    "version": "not-reported-by-host",
                    "definition_sha256": definition_hash,
                    "origin": "explicit-github-issue-event-intake",
                },
                "payload": payload,
                "evidence_refs": [],
            }
            write_new(envelope_path, envelope, lock.parent)
        expected_fields = {
            "schema_version": 1,
            "event_id": "github-" + key,
            "tenant_id": tenant,
            "request_id": request_id,
            "kind": "step",
            "source_ref": f"github:{repository}:issue:{number}:event:{event_id}",
        }
        if any(envelope.get(name) != expected for name, expected in expected_fields.items()):
            raise ValueError("Persisted envelope identity does not match the requested event")
        expected_agent = {
            "id": host_id,
            "version": "not-reported-by-host",
            "definition_sha256": definition_hash,
            "origin": "explicit-github-issue-event-intake",
        }
        if envelope.get("agent") != expected_agent or envelope["payload"]["remote_event"]["id"] != event_id:
            raise ValueError("Persisted envelope host or source identity mismatch")
        result_path = folder / "receipt.json"
        value = {
            "schema_version": 1,
            "remote_identity": identity,
            "envelope_sha256": hashlib.sha256(envelope_path.read_bytes()).hexdigest(),
            "state": "recorded_file",
            "diting_event_id": envelope["event_id"],
            "git_committed": False,
            "diting_consumption_confirmed": False,
            "coordination": "associate_only_no_dispatch",
        }
        if result_path.exists() and read(result_path) != value:
            raise ValueError("Stored receipt does not match the persisted envelope")
        # Reuse the canonical immutable store, including its collision and graph checks.
        result = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                str(root / "framework/extensions/diting-files/diting_files.py"),
                "record",
                "--repo",
                str(root),
                "--input",
                str(envelope_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        if result.returncode:
            raise ValueError("Diting record failed; retained envelope permits explicit retry")
        receipt = json.loads(result.stdout)
        if receipt.get("state") != "recorded_file":
            raise ValueError("Expected an actual file receipt")
        if not result_path.exists():
            write_new(result_path, value, lock.parent)
        return {
            **value,
            "idempotent": bool(receipt.get("idempotent")),
            "receipt": result_path.relative_to(root).as_posix(),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--event-id", type=int, required=True)
    parser.add_argument("--host-id", required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--host-definition", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                intake(
                    args.repo,
                    args.issue,
                    args.event_id,
                    args.host_id,
                    args.tenant,
                    args.request_id,
                    args.host_definition,
                ),
                ensure_ascii=False,
            )
        )
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
