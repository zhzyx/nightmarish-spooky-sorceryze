"""GitHub Issue work orders and read-only Diting collection manifests."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def request_ids(body):
    pattern = r"[a-z0-9]+(?:-[a-z0-9]+)*"
    markers = re.findall(r"<!--\s*(?:gonggong|olympus)-request:(" + pattern + r")\s*-->", body or "")
    fields = re.findall(r"^### 稳定需求 ID\s*\n+(" + pattern + r")[ \t]*(?=\r?$)", body or "", re.M)
    return set(markers + fields)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class GitHubCommandError(ValueError):
    def __init__(self, status=None, reason=None):
        self.http_status = status
        super().__init__(
            reason
            or (
                "GITHUB_HTTP_" + str(status) + ": check repository access and API permissions"
                if status
                else "GITHUB_COMMAND: check local gh login and repository access"
            )
        )


def gh(*args):
    try:
        result = subprocess.run(
            [os.environ.get("GONGGONG_GH", "gh"), *args], capture_output=True, text=True, encoding="utf-8", timeout=120
        )
    except FileNotFoundError:
        raise GitHubCommandError(
            reason="GITHUB_RUNTIME: gh executable missing; set GONGGONG_GH to the authenticated host CLI"
        ) from None
    except subprocess.TimeoutExpired:
        raise GitHubCommandError(
            reason="GITHUB_TIMEOUT: request exceeded 120 seconds; read remote state before retrying a write"
        ) from None
    if result.returncode:
        match = re.search(r"\bHTTP (\d{3})\b", result.stderr or "")
        if not match and any(
            text in (result.stderr or "").lower()
            for text in (
                "error connecting",
                "connection was reset",
                "could not resolve",
                "network is unreachable",
                "connection refused",
                "i/o timeout",
            )
        ):
            raise GitHubCommandError(
                reason="GITHUB_NETWORK: connection unavailable; check host network permissions and connectivity; Issue state is unknown"
            )
        raise GitHubCommandError(int(match[1]) if match else None)
    return result.stdout.strip()


def config(root):
    value = read(root / "work-items.json")
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", value["repository"]):
        raise ValueError("Invalid GitHub repository")
    labels = read(root / ".github/labels.json")
    names = [item["name"] for item in labels]
    if len(set(names)) != len(names) or not all(re.fullmatch(r"type:[a-z-]+", x) for x in names):
        raise ValueError("Invalid or duplicate task labels")
    return value, labels


def labels(root, apply=False):
    settings, definitions = config(root)
    statuses = read(root / ".github/status-labels.json")
    expected = {
        "status:" + v for v in ("needs-decision", "planned", "in-progress", "blocked", "in-review", "done", "cancelled")
    }
    if len(statuses) != len(expected) or {v["name"] for v in statuses} != expected:
        raise ValueError("Invalid status label definitions")
    definitions = definitions + statuses
    if not apply:
        return {"state": "planned", "repository": settings["repository"], "labels": definitions}
    pages = json.loads(gh("api", "repos/" + settings["repository"] + "/labels?per_page=100", "--paginate", "--slurp"))
    existing = {item["name"] for page in pages for item in page}
    # Preserve pre-existing label colors and descriptions.
    for label in definitions:
        if label["name"] in existing:
            continue
        gh(
            "label",
            "create",
            label["name"],
            "--repo",
            settings["repository"],
            "--color",
            label["color"],
            "--description",
            label["description"],
        )
    return {"state": "labels_ensured", "count": len(definitions)}


def issue(root, document, title, category, request_id, apply=False, execution_authority_ref=None):
    # Trace the caller's existing mandate; this is not a governance grant.
    if execution_authority_ref is not None and (
        not isinstance(execution_authority_ref, str)
        or not execution_authority_ref.strip()
        or any(ord(c) < 32 for c in execution_authority_ref)
    ):
        raise ValueError("Execution authority reference must be nonempty single-line text")
    initial_status = "status:in-progress" if execution_authority_ref else "status:needs-decision"
    settings, definitions = config(root)
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", request_id):
        raise ValueError("Invalid stable request ID")
    label = "type:" + category
    if label not in {x["name"] for x in definitions}:
        raise ValueError("Unknown task category")
    doc = (root / document).resolve()
    doc.relative_to((root / "design-docs").resolve())
    if doc.suffix != ".md" or not doc.is_file():
        raise ValueError("A Markdown requirement in design-docs is required")
    marker = "<!-- gonggong-request:" + request_id + " -->"
    body = marker + "\n\n需求文档：`" + doc.relative_to(root).as_posix() + "`\n\n" + doc.read_text(encoding="utf-8")
    if execution_authority_ref:
        body += "\n\n执行授权来源（由调用宿主核实，不代替候选准入）：" + execution_authority_ref + "\n"
    plan = {
        "state": "planned",
        "repository": settings["repository"],
        "title": title,
        "labels": [label, initial_status, "workspace:gonggong"],
        "request_id": request_id,
        "body": body,
    }
    if not apply:
        return plan
    account = json.loads(gh("api", "user")).get("login")
    if not isinstance(account, str) or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", account):
        raise ValueError("Authenticated GitHub account login is required")
    body += "\n\n<!-- gonggong-host-git:" + account + " -->\n"
    # Query all pages and exact marker, including closed issues, to avoid recreating a request.
    pages = json.loads(
        gh("api", "repos/" + settings["repository"] + "/issues?state=all&per_page=100", "--paginate", "--slurp")
    )
    matches = [
        item
        for page in pages
        for item in page
        if "pull_request" not in item and request_id in request_ids(item.get("body"))
    ]
    if any(request_ids(item.get("body")) != {request_id} for item in matches):
        raise ValueError("Ambiguous remote request identity; resolve before continuing")
    if len(matches) > 1:
        raise ValueError("Duplicate remote request identity; resolve before continuing")
    if matches:
        existing = matches[0]
        owners = re.findall(r"<!--\s*gonggong-host-git:([A-Za-z0-9-]+)\s*-->", existing.get("body") or "")
        return {
            "state": "existing",
            "url": existing["html_url"],
            "host_git_account": owners[0] if len(set(owners)) == 1 else None,
            "host_identity_verified": False,
        }
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "issue.md"
        path.write_text(body, encoding="utf-8")
        url = gh(
            "issue",
            "create",
            "--repo",
            settings["repository"],
            "--title",
            title,
            "--label",
            label,
            "--label",
            initial_status,
            # Host intake only accepts explicitly labeled GongGong work.
            "--label",
            "workspace:gonggong",
            "--body-file",
            str(path),
        )
    return {"state": "created", "url": url, "host_git_account": account, "host_identity_verified": True}


def collect(root, request_id):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", request_id):
        raise ValueError("Invalid request ID")
    command = [
        sys.executable,
        "-X",
        "utf8",
        str(root / "framework/extensions/diting-files/diting_files.py"),
        "validate",
        "--repo",
        str(root),
    ]
    check = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=120)
    if check.returncode:
        raise ValueError("Diting validation failed; collection not published")
    settings, _ = config(root)
    issue_sources = set()
    events = []
    for path in sorted((root / "gonggong-diting-data/events").rglob("*.json")):
        raw = path.read_bytes()
        value = json.loads(raw)
        if value["request_id"] == request_id:
            if value.get("kind") == "request" and value.get("tenant_id") == settings.get("tenant_id"):
                source = value.get("source_ref", "")
                repository = re.escape(settings["repository"])
                match = re.fullmatch(r"https://github\.com/" + repository + r"/issues/([1-9][0-9]*)", source)
                alternate = re.fullmatch(r"github:" + repository + r":issue:([1-9][0-9]*)", source)
                if match or alternate:
                    issue_sources.add(int((match or alternate)[1]))
            events.append({
                "source": path.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "tenant_id": value["tenant_id"],
                "event_id": value["event_id"],
                "origin": value["agent"]["origin"],
            })
    if not events:
        raise ValueError("No actual events for request; refusing empty success")
    if len(issue_sources) > 1:
        raise ValueError("Ambiguous request Issue sources; collection not published")
    result = {
        "schema_version": 1,
        "kind": "source_index",
        "request_id": request_id,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "collector": "gonggong-local-file-indexer",
        "intended_reader": "diting",
        "diting_ingestion_confirmed": False,
        "events": events,
        "scope": "Validated local Diting events for this request; not a remote Issue snapshot",
    }
    if issue_sources:
        result["issue_number"] = next(iter(issue_sources))
        result["issue_url"] = f"https://github.com/{settings['repository']}/issues/{result['issue_number']}"
    directory = root / "data-collection/requests" / request_id
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / (str(uuid.uuid4()) + ".json")
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return {"state": "collected_file_index", "path": destination.relative_to(root).as_posix(), "events": len(events)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    label = sub.add_parser("labels")
    label.add_argument("--apply", action="store_true")
    create = sub.add_parser("issue")
    create.add_argument("--document", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--type", required=True)
    create.add_argument("--request-id", required=True)
    create.add_argument("--apply", action="store_true")
    create.add_argument("--execution-authority-ref", help="Existing user/host mandate verified by caller; not a grant")
    collection = sub.add_parser("collect")
    collection.add_argument("--request-id", required=True)
    args = parser.parse_args()
    root = args.repo.resolve()
    if args.command == "labels":
        result = labels(root, args.apply)
    elif args.command == "issue":
        result = issue(
            root, args.document, args.title, args.type, args.request_id, args.apply, args.execution_authority_ref
        )
    else:
        result = collect(root, args.request_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        sys.exit(str(error))
