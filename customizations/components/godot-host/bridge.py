"""Godot host adapter. Framework/data remain in their existing Git workspace."""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

_paths_spec = importlib.util.spec_from_file_location(
    "gonggong_workspace_paths", Path(__file__).with_name("workspace_paths.py")
)
if _paths_spec is None or _paths_spec.loader is None:
    raise ImportError("Cannot load workspace path resolver")
_paths_module = importlib.util.module_from_spec(_paths_spec)
_paths_spec.loader.exec_module(_paths_module)
framework_root = _paths_module.framework_root


@contextmanager
def outbox_lock(folder, deadline):
    """Serialize terminal-worker and next-chat flushes across processes."""
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / ".flush.lock").open("a+b") as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        while True:
            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise ValueError("Diting delivery busy; envelopes retained")
                time.sleep(0.05)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def flush(root):
    root = Path(root).resolve()
    deadline = time.monotonic() + 15
    with outbox_lock(root / ".gonggong-outbox/chat", deadline):
        return flush_locked(root, deadline)


def flush_locked(root, deadline):
    """Idempotent durable file outbox. Only delete an envelope after a real receipt."""
    root = Path(root).resolve()
    outbox = root / ".gonggong-outbox/chat"
    receipts = []
    for pending in sorted(outbox.glob("*.json")):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("Diting flush time budget reached; remaining envelopes retained")
        if pending.is_symlink():
            raise ValueError("Linked outbox entry is not allowed")
        recorded = subprocess.run(
            [
                sys.executable,
                str(root / "framework/extensions/diting-files/diting_files.py"),
                "record",
                "--repo",
                str(root),
                "--input",
                str(pending),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=remaining,
            env=host_environment(root),
        )
        if recorded.returncode:
            raise ValueError("Diting receipt failed; envelope retained: " + recorded.stderr.strip())
        receipts.append(json.loads(recorded.stdout))
        pending.unlink(missing_ok=True)
    return {"ok": True, "state": "recorded_file", "receipts": receipts, "git_committed": False}


def enqueue(root, event):
    outbox = root / ".gonggong-outbox/chat"
    outbox.mkdir(parents=True, exist_ok=True)
    pending = outbox / (event["event_id"] + ".json")
    temporary = pending.with_suffix(".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(pending)


def find_gh(env):
    """GUI-launched hosts often lack the user's shell PATH; never guess beyond fixed install locations."""
    configured = env.get("GONGGONG_GH")
    if configured:
        return configured if Path(configured).is_file() else None
    found = shutil.which("gh", path=env.get("PATH"))
    if found:
        return found
    try:
        home = Path.home()
    except RuntimeError:
        home = None
    candidates = [Path("/opt/homebrew/bin/gh"), Path("/usr/local/bin/gh")]
    if home is not None:
        candidates.insert(0, home / ".local/bin/gh")
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    candidates = [Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "GitHub CLI/gh.exe"]
    if home is not None:
        candidates += sorted((home / "Documents/Codex/tools/github-cli").glob("*/bin/gh.exe"), reverse=True)
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def host_environment(root):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", GONGGONG_PYTHON=sys.executable)
    gh = find_gh(env)
    if gh:
        env["GONGGONG_GH"] = gh
    node = env.get("GONGGONG_NODE")
    if not node and (root / "project/runtime/node/node.exe").is_file():
        node = str(root / "project/runtime/node/node.exe")
        env["GONGGONG_NODE"] = node
    if node and Path(node).is_file():
        # Framework subprocesses also invoke `node`; honor the host's runtime choice.
        env["PATH"] = str(Path(node).resolve().parent) + os.pathsep + env.get("PATH", "")
    git = env.get("GONGGONG_GIT") or root / "project/runtime/git/cmd/git.exe"
    if Path(git).is_file():
        env["PATH"] = str(Path(git).resolve().parent) + os.pathsep + env.get("PATH", "")
    return env


def request_identity(request):
    # Legacy Godot callers remain supported; protocol v1 requires explicit identity.
    if "protocol_version" not in request and "host" not in request:
        return {"id": "godot-editor", "kind": "engine"}, request.get("agent_id", "yanshi")
    if type(request.get("protocol_version")) is not int or request["protocol_version"] != 1:
        raise ValueError("Unsupported host protocol version")
    host = request.get("host")
    if not isinstance(host, dict) or host.get("kind") not in ("engine", "ide", "cli", "production-tool"):
        raise ValueError("Missing host descriptor or unsupported host kind")
    agent_id = request.get("agent_id")
    if any(
        not isinstance(v, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,95}", v) for v in (host.get("id"), agent_id)
    ):
        raise ValueError("Invalid host or agent identity")
    return {"id": host["id"], "kind": host["kind"]}, agent_id


def issue_binding(root, request, tenant):
    number = request.get("issue_number")
    request_id = request.get("request_id")
    if (
        type(number) is not int
        or number < 1
        or not isinstance(request_id, str)
        or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", request_id)
    ):
        raise ValueError("Before development, create/reuse a real Issue and bind issue_number and stable request_id")
    process = subprocess.run(
        [
            sys.executable,
            str(root / "customizations/components/issue-workorders/issue_gate.py"),
            "--repo",
            str(root),
            "--issue",
            str(number),
            "--request-id",
            request_id,
            "--tenant",
            tenant,
            "--intake-only",
        ],
        cwd=root,
        env=host_environment(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    if process.returncode:
        raise ValueError(
            "Issue intake rejected; verify GitHub access, repository, tenant, workspace label, active status and stable request ID"
        )
    return json.loads(process.stdout)


def chat(root, request, tenant):
    """Load framework context; never fall back to a model when checks reject it."""
    root = root.resolve()
    framework = framework_root(root)
    manifest = json.loads((framework / "framework-manifest.json").read_text(encoding="utf-8"))
    host, agent_id = request_identity(request)
    matches = [a for a in manifest["agents"] if a["id"] == agent_id]
    if len(matches) != 1:
        raise ValueError("Agent is not uniquely registered: " + agent_id)
    agent = matches[0]
    for field in ("request_id", "outcome", "authority_ref", "project"):
        if not isinstance(request.get(field), str) or not request[field].strip():
            raise ValueError("Missing host request: " + field)
    permission_fields = ("tools_enabled", "file_changes_require_approval", "execution_requires_approval")
    if any(type(request.get(field)) is not bool for field in permission_fields):
        raise ValueError("Missing host permission state")
    issue = issue_binding(root, request, tenant)
    flush(root)  # An earlier failed delivery blocks the next model/tool round.
    binding = {
        "tenant_id": tenant,
        "request_ref": request["request_id"],
        "source_ref": issue["url"],
        "agent_snapshot_ref": agent_id + "@" + agent["version"] + "#" + agent["candidate_digest"],
        "outbox_path": ".gonggong-outbox/chat",
        "sink_ref": "gonggong-diting-data",
        "path_base": "workspace_root",
        "authority_ref": request["authority_ref"],
        "agent": {
            "id": agent_id,
            "version": agent["version"],
            "origin": "gonggong-framework",
            "definition_sha256": hashlib.sha256((framework / agent["entry"]).read_bytes()).hexdigest(),
        },
    }
    mandate = {
        "feature_id": request["request_id"],
        "outcome": request["outcome"],
        "issue": issue,
        "delivery_requirements": {
            "required_git_deliverables": [
                "implementation",
                "design-docs",
                "data-collection sources, evidence and receipts",
                "gonggong-diting-data real events",
            ],
            "before_commit": "Review and sanitize actual sources, stage current bytes together, run the trusted Issue gate on final content",
            "after_commit": "Run Diting git-check --require-committed against HEAD; record push and merge separately",
            "preserve_originals": "Append corrections; do not submit credentials, local absolute source paths, caches or synthetic production facts",
        },
        "authority_ref": request["authority_ref"],
        "host": host["id"],
        "host_descriptor": host,
        "project": request["project"],
        "tool_permission": {k: request[k] for k in permission_fields},
        "reporting": binding,
    }
    env = host_environment(root)
    with tempfile.TemporaryDirectory() as temporary:
        mandate_file = Path(temporary) / "mandate.json"
        mandate_file.write_text(json.dumps(mandate, ensure_ascii=False), encoding="utf-8")
        try:
            process = subprocess.run(
                [
                    env.get("GONGGONG_NODE", "node"),
                    str(framework / "tools/agent-context.mjs"),
                    agent_id,
                    str(mandate_file),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            ok = process.returncode == 0 and bool(process.stdout.strip())
            result = {
                "ok": ok,
                "agent_execution_enabled": False,
                "context": process.stdout if ok else "",
                "error": "" if ok else process.stderr.strip() or "Framework returned no context",
            }
        except (OSError, subprocess.TimeoutExpired) as error:
            result = {"ok": False, "agent_execution_enabled": False, "context": "", "error": str(error)}
        event = {
            "schema_version": 1,
            "event_id": "host-context-" + uuid.uuid4().hex,
            "tenant_id": tenant,
            "request_id": request["request_id"],
            "kind": "request",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "source_ref": issue["url"],
            "agent": {
                "id": "gonggong-host-adapter",
                "version": "1.2.1",
                "definition_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "origin": "gonggong-host-adapter",
            },
            "payload": {
                "framework_version": manifest["version"],
                "requested_agent": agent_id,
                "host": host,
                "issue": issue,
                "candidate_digest": agent["candidate_digest"],
                "context_accepted": result["ok"],
                "outcome_sha256": hashlib.sha256(request["outcome"].encode()).hexdigest(),
                "input_tokens": None,
                "output_tokens": None,
                "reason": "Not measured; context assembly is not model execution",
            },
            "evidence_refs": [],
        }
        enqueue(root, event)
        try:
            result["receipt"] = flush(root)
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            return {"ok": False, "agent_execution_enabled": False, "error": str(error)}
        result["context_ready"] = result["ok"]
        result["model_execution_started"] = False
        if result["ok"]:
            result["reporting"] = binding
            result["admission_scope"] = "context_checked; model execution and reporting are host responsibilities"
        return result


def run(command, cwd):
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            env=host_environment(Path(cwd)),
        )
        return {
            "ok": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ok": False, "error": str(error)}


def diagnose(root):
    framework = framework_root(root)
    env = host_environment(root)
    node = env.get("GONGGONG_NODE", "node")
    checks = {"node_available": {"ok": shutil.which(node, path=env.get("PATH")) is not None}}
    checks["git_available"] = {"ok": shutil.which("git", path=env.get("PATH")) is not None}
    checks["candidate_integrity"] = run(
        [sys.executable, str(framework / "tools/verify_framework.py"), "--candidate"], root
    )
    checks["formal_framework_admission"] = run([sys.executable, str(framework / "tools/verify_framework.py")], root)
    manifest = json.loads((framework / "framework-manifest.json").read_text(encoding="utf-8"))
    for agent in manifest["agents"]:
        checks["local_admission:" + agent["id"]] = run(
            [node, str(framework / "tools/admission.mjs"), str(framework), agent["id"]], root
        )
    checks["diting_data"] = run(
        [sys.executable, str(framework / "extensions/diting-files/diting_files.py"), "validate", "--repo", str(root)],
        root,
    )
    return {
        "ok": all(c["ok"] for c in checks.values()),
        "checks": checks,
        "blocking_checks": [name for name, check in checks.items() if not check["ok"]],
        "model_execution_started": False,
        "host_authority_authenticated": False,
        "note": "Readiness diagnostics do not grant permission or test model credentials. Each chat still runs admission and requires a real Diting receipt.",
    }


def admission_record_status(framework, agent):
    try:
        value = json.loads((framework / agent["admission_pass"]).read_text(encoding="utf-8"))
        return value["status"] if isinstance(value.get("status"), str) else "invalid"
    except (FileNotFoundError, KeyError):
        return "missing"
    except (OSError, ValueError, TypeError, AttributeError):
        return "invalid_or_unavailable"


REQUEST_ID = r"[a-z0-9]+(?:-[a-z0-9]+)*"
STARTABLE_STATUSES = ("status:needs-decision", "status:planned")
ACTIVE_STATUSES = ("status:in-progress", "status:in-review")


def work_items_module(root):
    path = root / "customizations/components/issue-workorders/work_items.py"
    spec = importlib.util.spec_from_file_location("gonggong_work_items", path)
    if spec is None or spec.loader is None:
        raise ValueError("Issue work-order adapter is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def guide_fields(root, request):
    """Host-side Issue guide input; it is not a model request and grants no execution."""
    module = work_items_module(root)
    settings, labels = module.config(root)
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or len(request_id) > 80 or not re.fullmatch(REQUEST_ID, request_id):
        raise ValueError("Invalid stable request ID")
    fields = {"request_id": request_id}
    for name, limit in (("title", 120), ("category", 40), ("outcome", 16000)):
        value = request.get(name)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError("Missing or oversized Issue guide field: " + name)
        fields[name] = value.strip()
    if "\n" in fields["title"] or "\r" in fields["title"]:
        raise ValueError("Issue title must be a single line")
    if "type:" + fields["category"] not in {item["name"] for item in labels}:
        raise ValueError("Unknown task category")
    fields["document"] = "design-docs/" + request_id + ".md"
    return module, settings, fields


def requirement_document(fields):
    quoted = "\n".join("> " + line if line else ">" for line in fields["outcome"].splitlines())
    return (
        f"# {fields['title']}\n\n"
        f"<!-- gonggong-request:{fields['request_id']} -->\n\n"
        f"- 需求 ID：`{fields['request_id']}`\n"
        "- Issue：由 Godot 编辑器会话内工单引导创建，链接见远程 Issue\n"
        f"- 类别：`type:{fields['category']}`\n"
        "- 责任人：待实际指定\n\n"
        "## 原始需求与目标\n\n"
        "来源：Godot 编辑器 AI 聊天中因未绑定工单而暂停的用户消息，原文如下（创建远程 Issue 前已提示审查及脱敏）。\n\n"
        f"{quoted}\n\n"
        "## 范围与非目标\n\n待补充。\n\n"
        "## 验收标准\n\n- [ ] 待补充可核验的交付条件\n\n"
        "## 验证与采集证据\n\n尚未实施。引用实际文件、提交和事件，不填写估算用量。\n"
    )


def create_command(fields):
    return " ".join(
        shlex.quote(part)
        for part in (
            "python3",
            "customizations/components/issue-workorders/work_items.py",
            "--repo",
            ".",
            "issue",
            "--document",
            fields["document"],
            "--title",
            fields["title"],
            "--type",
            fields["category"],
            "--request-id",
            fields["request_id"],
            "--apply",
        )
    )


def gh_authenticated(gh, env):
    """Read-only `gh auth status`; logging in stays an interactive user action in a terminal."""
    try:
        result = subprocess.run(
            [gh, "auth", "status", "--hostname", "github.com"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def login_command(gh):
    return shlex.join([gh, "auth", "login", "--hostname", "github.com", "--git-protocol", "https", "--web"])


def gh_state(root):
    """Return (gh, error); error is gh_unavailable or gh_unauthenticated, never a remote side effect."""
    env = host_environment(root)
    gh = env.get("GONGGONG_GH")
    if not gh:
        return None, "gh_unavailable"
    os.environ["GONGGONG_GH"] = gh
    if not gh_authenticated(gh, env):
        return gh, "gh_unauthenticated"
    return gh, None


def issue_draft(root, request):
    """Write the requirement Markdown and preview the Issue; no remote side effects."""
    module, settings, fields = guide_fields(root, request)
    path = root / fields["document"]
    content = requirement_document(fields)
    if path.is_symlink():
        raise ValueError("Linked requirement document is not allowed")
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise ValueError("Requirement document already exists with different content: " + fields["document"])
        state = "document_existing"
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        state = "document_created"
    plan = module.issue(root, fields["document"], fields["title"], fields["category"], fields["request_id"], False)
    gh, gh_error = gh_state(root)
    return {
        "ok": True,
        "state": state,
        "document": fields["document"],
        "repository": plan["repository"],
        "title": plan["title"],
        "labels": plan["labels"],
        "request_id": fields["request_id"],
        "gh_available": gh is not None,
        "gh_authenticated": gh_error is None,
        "gh_login_command": login_command(gh) if gh else "",
        "remote_created": False,
    }


def issue_create(root, request):
    module, settings, fields = guide_fields(root, request)
    gh, gh_error = gh_state(root)
    if gh_error:
        return {
            "ok": False,
            "error": gh_error,
            "command": create_command(fields),
            "login_command": login_command(gh) if gh else "",
            "remote_created": False,
        }
    result = module.issue(root, fields["document"], fields["title"], fields["category"], fields["request_id"], True)
    issue_url = r"https://github\.com/" + re.escape(settings["repository"]) + r"/issues/([0-9]+)"
    match = re.fullmatch(issue_url, result["url"])
    if not match:
        raise ValueError("GitHub returned an unexpected Issue URL")
    return {"ok": True, "state": result["state"], "url": result["url"], "number": int(match.group(1))}


def issue_start(root, request):
    """Explicit user decision in the host: move an unstarted guide Issue to in-progress."""
    number = request.get("issue_number")
    request_id = request.get("request_id")
    valid_number = type(number) is int and number >= 1
    if not valid_number or not isinstance(request_id, str) or not re.fullmatch(REQUEST_ID, request_id):
        raise ValueError("Bind a real Issue number and its stable request ID first")
    module = work_items_module(root)
    settings, _ = module.config(root)
    gh, gh_error = gh_state(root)
    if gh_error:
        return {
            "ok": False,
            "error": gh_error,
            "login_command": login_command(gh) if gh else "",
            "remote_changed": False,
        }
    repository = settings["repository"]
    value = json.loads(module.gh("api", f"repos/{repository}/issues/{number}"))
    if value.get("number") != number or "pull_request" in value or value.get("state") != "open":
        raise ValueError("Issue must be an open Issue in the configured repository")
    if module.request_ids(value.get("body")) != {request_id}:
        raise ValueError("Issue stable request ID does not match unambiguously")
    names = [item["name"] for item in value.get("labels", [])]
    if "workspace:gonggong" not in names:
        raise ValueError("Issue must explicitly include workspace:gonggong")
    statuses = [name for name in names if name.startswith("status:")]
    if len(statuses) == 1 and statuses[0] in ACTIVE_STATUSES:
        return {"ok": True, "state": "already_active", "status": statuses[0], "remote_changed": False}
    if len(statuses) > 1 or (statuses and statuses[0] not in STARTABLE_STATUSES):
        raise ValueError("Issue status " + ", ".join(statuses) + " needs a decision on GitHub")
    arguments = ["issue", "edit", str(number), "--repo", repository, "--add-label", "status:in-progress"]
    if statuses:
        arguments += ["--remove-label", statuses[0]]
    module.gh(*arguments)
    return {
        "ok": True,
        "state": "started",
        "previous_status": statuses[0] if statuses else None,
        "status": "status:in-progress",
        "remote_changed": True,
    }


def issue_agent(root, request):
    from types import SimpleNamespace

    spec = importlib.util.spec_from_file_location(
        "gonggong_requirements", Path(__file__).with_name("requirements_agent.py")
    )
    if spec is None or spec.loader is None:
        raise ValueError("Requirements Agent adapter unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    api = SimpleNamespace(
        work_items_module=work_items_module,
        gh_state=gh_state,
        login_command=login_command,
        host_environment=host_environment,
        issue_start=issue_start,
        enqueue=enqueue,
        flush=flush,
        outbox_lock=outbox_lock,
    )
    return module.intake(root, request, api)


GUIDE_ACTIONS = {
    "issue-draft": issue_draft,
    "issue-create": issue_create,
    "issue-start": issue_start,
    "issue-agent": issue_agent,
}


def execute(workspace, action, tenant):
    root = Path(workspace).resolve()
    framework = framework_root(root)
    manifest = json.loads((framework / "framework-manifest.json").read_text(encoding="utf-8"))
    result = {
        "action": action,
        "framework_version": manifest["version"],
        "agent_execution_enabled": False,
        "admission": "Requires independent admission and authenticated host authority",
        "agents": [
            {
                "id": a["id"],
                "distribution_state": a["state"],
                "admission_record_status": admission_record_status(framework, a),
            }
            for a in manifest["agents"]
        ],
    }
    diting = str(framework / "extensions/diting-files/diting_files.py")
    if action == "status":
        result.update(
            ok=True,
            framework_status=manifest["status"],
            data_available=(root / "gonggong-diting-data/dataset.json").is_file(),
        )
    elif action == "doctor":
        result.update(diagnose(root))
    elif action == "check":
        result.update(run([sys.executable, str(framework / "tools/verify_framework.py"), "--candidate"], root))
    elif action == "validate":
        result.update(run([sys.executable, diting, "validate", "--repo", str(root)], root))
    elif action == "analyze":
        result.update(run([sys.executable, diting, "analyze", "--repo", str(root), "--tenant", tenant], root))
    else:
        raise ValueError("Unsupported action")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["status", "doctor", "check", "validate", "analyze", "chat", "flush", *GUIDE_ACTIONS]
    )
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--tenant", default="gonggong-workspace")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--request", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "chat":
            if args.request is None:
                raise ValueError("chat requires --request")
            result = chat(Path(args.workspace), json.loads(args.request.read_text(encoding="utf-8")), args.tenant)
        elif args.action in GUIDE_ACTIONS:
            if args.request is None:
                raise ValueError(args.action + " requires --request")
            request = json.loads(args.request.read_text(encoding="utf-8"))
            if not isinstance(request, dict):
                raise ValueError("Issue guide request must be an object")
            if args.action == "issue-agent":
                sys.stdin.reconfigure(encoding="utf-8")
                credentials = json.loads(sys.stdin.readline(8192))
                if set(credentials) != {"api_key"} or not isinstance(credentials["api_key"], str):
                    raise ValueError("Requirements credentials must use the private stdin pipe")
                request["_private_api_key"] = credentials["api_key"]
                request["_cancel_path"] = str(args.request)
            result = GUIDE_ACTIONS[args.action](Path(args.workspace).resolve(), request)
        elif args.action == "flush":
            result = flush(Path(args.workspace))
        else:
            result = execute(args.workspace, args.action, args.tenant)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        result = {"ok": False, "agent_execution_enabled": False, "error": str(error)}
    content = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        temporary = args.out.with_suffix(".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(args.out)
    else:
        print(content)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
