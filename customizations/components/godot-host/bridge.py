"""Godot host adapter. Framework/data remain in their existing Git workspace."""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import runpy
import shlex
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

_runtime_spec = importlib.util.spec_from_file_location(
    "gonggong_runtime_config", Path(__file__).resolve().parents[3] / "tools/gonggong_runtime_config.py"
)
if _runtime_spec is None or _runtime_spec.loader is None:
    raise ImportError("Cannot load runtime configuration reader")
_runtime = importlib.util.module_from_spec(_runtime_spec)
_runtime_spec.loader.exec_module(_runtime)

_igniter_spec = importlib.util.spec_from_file_location(
    "gonggong_environment_igniter", Path(__file__).with_name("environment_igniter.py")
)
if _igniter_spec is None or _igniter_spec.loader is None:
    raise ImportError("Cannot load environment igniter")
_igniter = importlib.util.module_from_spec(_igniter_spec)
_igniter_spec.loader.exec_module(_igniter)


RECEIPT_PROTOCOL = "gonggong-scoped-batch-receipts-v1"
RECEIPT_EXECUTION_SECONDS = 120
RECEIPT_LOCK_WAIT_SECONDS = RECEIPT_EXECUTION_SECONDS + 5


def storage_entry():
    # Execute only the installed host adapter. The selected project supplies data.
    installation = Path(__file__).resolve().parents[3]
    checker = runpy.run_path(str(installation / "tools/check_gonggong_distribution.py"))
    directory = checker["PLATFORM_PACKAGES"][0]
    lock = json.loads((installation / checker["REGISTRATION"]).read_text(encoding="utf-8"))
    checker["platform_inventory"](installation, directory, lock["platform_files"][directory])
    batch = "customizations/platforms/development/git/git_batch.py"
    if hashlib.sha256((installation / batch).read_bytes()).hexdigest() != lock["host_files"][batch]:
        raise ValueError("Git storage dependency differs from its registered version")
    return str(installation / directory / "diting_files.py")


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


def flush(root, scope=None):
    root = Path(root).resolve()
    deadline = time.monotonic() + RECEIPT_LOCK_WAIT_SECONDS
    with outbox_lock(root / ".gonggong-outbox/chat", deadline):
        return flush_locked(root, deadline, scope)


def scoped_pending(pending_files, scope):
    if set(scope) != {"tenant_id", "request_id", "source_ref"} or not all(
        isinstance(value, str) and value for value in scope.values()
    ):
        raise ValueError("Complete outbox request scope required")
    envelopes = {}
    selected = []
    for path in pending_files:
        if path.is_symlink():
            raise ValueError("Linked outbox entry is not allowed")
        envelope = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(envelope, dict):
            raise ValueError("Invalid outbox envelope")
        if any(
            not isinstance(envelope.get(key), str) or not envelope[key]
            for key in ("tenant_id", "event_id", "request_id", "source_ref")
        ):
            raise ValueError("Unattributed outbox envelope")
        identity = (envelope["tenant_id"], envelope["event_id"])
        envelopes.setdefault(identity, []).append((path, envelope))
        if all(envelope.get(key) == value for key, value in scope.items()):
            selected.append(identity)

    ordered = []
    visiting = set()
    visited = set()

    def visit(identity):
        if identity in visiting:
            raise ValueError("Cyclic outbox dependencies; envelopes retained")
        if identity in visited:
            return
        visiting.add(identity)
        if len(envelopes[identity]) != 1:
            raise ValueError("Duplicate outbox event identity")
        path, envelope = envelopes[identity][0]
        refs = list(envelope.get("evidence_refs", []))
        if "supersedes" in envelope:
            refs.append(envelope["supersedes"])
        for ref in refs:
            predecessor = (identity[0], ref)
            if predecessor in envelopes:
                visit(predecessor)
        visiting.remove(identity)
        visited.add(identity)
        ordered.append(path)

    for identity in selected:
        visit(identity)
    return ordered


def flush_locked(root, deadline, scope=None):
    """Idempotent durable file outbox. Only delete an envelope after a real receipt."""
    root = Path(root).resolve()
    outbox = root / ".gonggong-outbox/chat"
    pending_files = sorted(outbox.glob("*.json"))
    if scope is not None:
        pending_files = scoped_pending(pending_files, scope)
    if any(path.is_symlink() for path in pending_files):
        raise ValueError("Linked outbox entry is not allowed")
    if pending_files:
        recorded = subprocess.run(
            [sys.executable, "-I", storage_entry(), "record-batch", "--repo", str(root)],
            input=json.dumps([str(path) for path in pending_files]),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
            env=host_environment(root),
        )
        if recorded.returncode:
            raise ValueError("Diting batch receipt failed; envelopes retained: " + recorded.stderr.strip())
        result = json.loads(recorded.stdout)
        if result.get("ok") is not True or len(result.get("receipts", [])) != len(pending_files):
            raise ValueError("Incomplete Diting batch receipt; envelopes retained")
        for pending, receipt in zip(pending_files, result["receipts"]):
            envelope = json.loads(pending.read_text(encoding="utf-8"))
            body = {key: value for key, value in envelope.items() if key != "sha256"}
            digest = hashlib.sha256(
                json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            if (
                not isinstance(receipt, dict)
                or receipt.get("state") != "recorded_file"
                or receipt.get("tenant_id") != envelope.get("tenant_id")
                or receipt.get("event_id") != envelope.get("event_id")
                or receipt.get("sha256") != digest
            ):
                raise ValueError("Unmatched Diting batch receipt; envelopes retained")
        for pending in pending_files:
            pending.unlink(missing_ok=True)
        return {"ok": True, "state": "recorded_file", "receipts": result["receipts"], "git_committed": False}
    return {"ok": True, "state": "recorded_file", "receipts": [], "git_committed": False}


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


_github_spec = importlib.util.spec_from_file_location(
    "gonggong_github_runtime", Path(__file__).resolve().parents[1] / "issue-workorders/github_runtime.py"
)
if _github_spec is None or _github_spec.loader is None:
    raise ImportError("Cannot load installed GitHub runtime")
_github = importlib.util.module_from_spec(_github_spec)
_github_spec.loader.exec_module(_github)


def find_gh(env, root=None):
    """Compatibility probe; root selects project data, never an executable source."""
    try:
        return _github.resolve_gh(env)
    except _github.GitHubCommandError:
        return None


def host_environment(root):
    root = Path(__file__).resolve().parents[3]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    snapshot = _runtime.read_effective(env=env) if env.get("GONGGONG_RUNTIME_CONFIG") else None
    if snapshot is None:
        env["GONGGONG_PYTHON"] = sys.executable
    # A retired external source locator must not propagate to child processes.
    env.pop("GONGGONG_FRAMEWORK_SOURCE", None)
    # A deployed local environment (the configuration igniter) is honored before
    # the host's own runtime discovery, but never grants admission by itself.
    env = _igniter.apply_state(root, env)
    # Native callers pass their resolved scope, including self-contained tests.
    # Never let a deployed legacy environment hide a later field edit.
    if snapshot is not None:
        env = _runtime.child_environment(snapshot, env)
    gh = _github.resolve_gh(env) if "GONGGONG_GH" in env else find_gh(env, root)
    if gh:
        env["GONGGONG_GH"] = gh
    node = env.get("GONGGONG_NODE")
    if snapshot is None and not node and (root / "project/runtime/node/node.exe").is_file():
        node = str(root / "project/runtime/node/node.exe")
        env["GONGGONG_NODE"] = node
    if node and Path(node).is_file():
        # Framework subprocesses also invoke `node`; honor the host's runtime choice.
        env["PATH"] = str(Path(node).resolve().parent) + os.pathsep + env.get("PATH", "")
    git = env.get("GONGGONG_GIT") or root / "project/runtime/git/cmd/git.exe"
    if Path(git).is_file():
        env["PATH"] = str(Path(git).resolve().parent) + os.pathsep + env.get("PATH", "")
    return env


def governance_fingerprint(context, mandate):
    # The rendered framework must end with exactly the authenticated mandate. Its user
    # outcome is sent in full on this turn; all other fields/revisions invalidate reuse.
    prefix, separator, rendered = context.partition(
        "\nHost mandate (actual identity and permission must be authenticated by host):\n"
    )
    try:
        if separator and json.loads(rendered) == mandate:
            policy = [prefix, {key: value for key, value in mandate.items() if key != "outcome"}]
            return hashlib.sha256(json.dumps(policy, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    except ValueError:
        pass
    return hashlib.sha256(context.encode("utf-8")).hexdigest()


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


def worker_delegation(request, host, sponsor):
    if "delegation" not in request:
        return None
    delegation = request["delegation"]
    if (
        host != {"id": "godot-editor", "kind": "engine"}
        or request.get("protocol_version") != 1
        or sponsor != "sinan"
        or not isinstance(delegation, dict)
        or set(delegation)
        != {
            "source",
            "execution_role",
            "parent_conversation",
            "child_conversation",
            "issue_number",
            "request_id",
            "work_order",
            "scope_sha256",
            "authority_ref",
            "turn_scope_sha256",
        }
    ):
        raise ValueError("Invalid editor worker delegation")
    parent, child = (delegation[key] for key in ("parent_conversation", "child_conversation"))
    if (
        any(not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32}", value) for value in (parent, child))
        or parent == child
        or delegation["authority_ref"] != "godot-editor:user-chat:" + parent
        or delegation["authority_ref"] != request["authority_ref"]
        or type(delegation["issue_number"]) is not int
        or delegation["issue_number"] != request.get("issue_number")
        or delegation["request_id"] != request["request_id"]
        or delegation["execution_role"] != "implementation_worker"
        or delegation["source"] not in ("manual", "design")
        or type(delegation["work_order"]) is not int
        or not (
            1 <= delegation["work_order"] <= 999 if delegation["source"] == "design" else delegation["work_order"] == 0
        )
        or not isinstance(delegation["turn_scope_sha256"], str)
        or not re.fullmatch(r"[a-f0-9]{64}", delegation["turn_scope_sha256"])
        or not isinstance(delegation["scope_sha256"], str)
        or not re.fullmatch(r"(?:[a-f0-9]{64})?", delegation["scope_sha256"])
    ):
        raise ValueError("Editor worker delegation does not match the bound work order")
    return delegation


def intake_failure_reason(stderr):
    """Classify trusted gate output without reflecting arbitrary stderr in the UI."""
    reason = stderr.strip()
    lines = reason.splitlines()
    if len(lines) == 2:
        try:
            prefix = json.loads(lines[0])
        except (ValueError, TypeError):
            prefix = None
        if (
            isinstance(prefix, dict)
            and set(prefix) == {"incident", "state", "issue", "action", "next_action", "dispatch"}
            and isinstance(prefix["incident"], str)
            and re.fullmatch(r"[a-f0-9]{64}", prefix["incident"])
            and prefix["state"] == "pending_kuafu_intake"
            and type(prefix["issue"]) is int
            and prefix["issue"] > 0
            and prefix["action"] == "intake"
            and prefix["next_action"]
            == "The active host must invoke Kuafu now: receive, investigate, then assess with the actual worker and bug."
            and (isinstance(prefix["dispatch"], dict) or prefix["dispatch"] == "local_only")
        ):
            reason = lines[1].strip()
    match = re.match(r"GITHUB_(HTTP_\d{3}|NETWORK|TIMEOUT|RUNTIME|COMMAND)\b", reason)
    if match:
        code = "GITHUB_" + match[1]
        transient = code in {"GITHUB_NETWORK", "GITHUB_TIMEOUT", "GITHUB_HTTP_429"}
        transient = transient or bool(re.fullmatch(r"GITHUB_HTTP_5\d{2}", code))
        return code, transient, code
    binding_errors = {
        "Host tenant must match work-items.json",
        "Git origin must match the configured GitHub repository",
        "--repo must be the Git repository root",
        "Issue must be a real Issue in the configured repository",
        "Issue is not open",
        "Issue must explicitly include workspace:gonggong",
        "Issue requires exactly one known type label",
        "Issue requires exactly one active status label",
        "Issue stable request ID does not match unambiguously",
    }
    if reason in binding_errors:
        return "ISSUE_BINDING", False, reason
    return "INTAKE_LOCAL_FAILURE", False, "INTAKE_LOCAL_FAILURE (see private intake diagnostics)"


def record_intake_failure(root, request, tenant, attempt, code, stderr, returncode):
    # Private diagnostics are never a permission certificate or a model prompt.
    # Keep the original bounded gate error locally; expose only fixed reasons.
    try:
        directory = root / ".gonggong-outbox/intake-failures"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (uuid.uuid4().hex + ".json")
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(
                {
                    "occurred_at": datetime.now(timezone.utc).isoformat(),
                    "issue_number": request["issue_number"],
                    "request_id": request["request_id"],
                    "tenant": tenant,
                    "read_attempt": attempt,
                    "code": code,
                    "returncode": returncode,
                    "stderr": stderr[:8192],
                },
                stream,
                ensure_ascii=False,
            )
    except OSError:
        pass  # A diagnostic-write failure must never hide the original rejection.


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
    bound = request_id.startswith("daqian-direct-") or request.get("daqian_bound") is True
    # A candidate supplies repository data, never the reader trusted to attest its own actor.
    installation = Path(__file__).resolve().parents[3]
    command = [
        sys.executable,
        "-E",
        "-s",
        "-X",
        "utf8",
        str(installation / "customizations/components/issue-workorders/issue_gate.py"),
        "--repo",
        str(root),
        "--issue",
        str(number),
        "--request-id",
        request_id,
        "--tenant",
        tenant,
        "--intake-only",
    ]
    env = host_environment(root)
    if bound:
        command.append("--include-issue-source")
    deadline = time.monotonic() + 120
    for attempt in range(1, 3):
        try:
            process = subprocess.run(
                command,
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=max(0.001, deadline - time.monotonic()),
            )
            if process.returncode == 0:
                result = json.loads(process.stdout)
                if not bound:
                    result.pop("verified_issue_source", None)
                return result
            stderr, returncode = process.stderr or "", process.returncode
        except subprocess.TimeoutExpired:
            stderr, returncode = "GITHUB_TIMEOUT: intake read exceeded the time budget", None
        code, transient, reason = intake_failure_reason(stderr)
        record_intake_failure(root, request, tenant, attempt, code, stderr, returncode)
        # --intake-only performs reads. Never repeat model calls or writes, and
        # never treat a previous approval as a substitute for a successful read.
        if attempt == 1 and transient and time.monotonic() < deadline:
            continue
        raise ValueError("Issue intake rejected: " + reason + "; read attempts=" + str(attempt))


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
    delegation = worker_delegation(request, host, agent_id)
    direct = request["request_id"].startswith("daqian-direct-")
    issue = issue_binding(root, dict(request, daqian_bound=True), tenant)
    source = issue.pop("verified_issue_source", {})
    if direct or request.get("daqian_bound") is True:
        routing, api = direct_adapter()
        # Public READ access is not membership. For read-only/legacy bindings use the
        # explicit affiliation check, including its identity and pagination checks.
        principal = source.get("actor") or routing.direct_issue.publish_collaborator(root)
    receipt_scope = {"tenant_id": tenant, "request_id": request["request_id"], "source_ref": issue["url"]}
    flush(root, receipt_scope)  # Required predecessors in this request must have receipts.
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
    if delegation:
        # Sinan's admission covers coordination. Attribute actual steps to the
        # embedded host worker and bind its role contract to this bridge revision.
        worker_digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        binding["sponsor_agent_snapshot_ref"] = binding["agent_snapshot_ref"]
        binding["agent"] = {
            "id": "godot-editor-worker",
            "version": "1",
            "origin": "godot-editor",
            "definition_sha256": worker_digest,
        }
        binding["agent_snapshot_ref"] = "godot-editor-worker@1#" + worker_digest
        binding["delegation"] = delegation
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
        "execution_policy": {
            "scope": "Apply only within this task, current delegation and host tool permissions. Read-only scope, user cancellation, budgets, required approval and decisions reserved to the user remain binding.",
            "continue": "Read facts, execute, verify, check remaining acceptance, then take the next authorized step. When the goal, authority, tools and observable acceptance are clear, act without asking whether to continue. Use repository conventions for routine reversible implementation choices.",
            "clarify": "Read available sources before guessing or asking the user. Ask only for necessary input affecting correctness or authority that cannot be obtained with available tools. Name the affected step and continue independent authorized work.",
            "finish": "A model turn ending, worker exit, plan or successful intermediate step is not business acceptance. Before finishing, check each criterion in this delegation against actual evidence. Continue executable remaining work; report unresolved evidence honestly and do not assume a parent task's delivery authority.",
            "recover": "Inspect actual failures and use evidence to choose a bounded recovery. If the same failure has no new evidence, escalate through the existing blocker route; do not loop. Read back unknown side effects before retrying. Wait for actual external completion events instead of polling without change.",
        },
        "authority_ref": request["authority_ref"],
        "host": host["id"],
        "host_descriptor": host,
        "project": request["project"],
        "tool_permission": {k: request[k] for k in permission_fields},
        "reporting": binding,
    }
    if delegation:
        mandate["execution_role"] = (
            "You are the delegated implementation worker. Sinan provides coordination governance."
        )
    if direct:
        requirement = routing.chat_context(root, request, api, verified_source=source.get("row"), principal=principal)
        mandate["bound_requirement"] = requirement
        binding["actor"] = requirement["actor"]
        binding["source_sha256"] = requirement["source_sha256"]
    elif request.get("daqian_bound") is True:
        binding["actor"] = principal["user_id"]
        binding["source_sha256"] = routing.digest([issue["url"], request["request_id"], issue["updated_at"]])
    env = host_environment(root)
    environment_missing = _igniter.missing_components(root, env)
    node = env.get("GONGGONG_NODE", "" if env.get("GONGGONG_RUNTIME_CONFIG") else "node")
    if not node and "node" not in environment_missing:
        environment_missing.append("node")
    with tempfile.TemporaryDirectory() as temporary:
        mandate_file = Path(temporary) / "mandate.json"
        mandate_file.write_text(json.dumps(mandate, ensure_ascii=False), encoding="utf-8")
        try:
            if not node:
                raise ValueError("runtime_node_unavailable")
            process = subprocess.run(
                [
                    node,
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
                "governance_sha256": governance_fingerprint(process.stdout, mandate) if ok else "",
                "error": "" if ok else process.stderr.strip() or "Framework returned no context",
            }
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            result = {"ok": False, "agent_execution_enabled": False, "context": "", "error": str(error)}
        if not result["ok"] and environment_missing:
            # Environment gaps are a config problem, not a framework/admission/data
            # block; the editor turns this marker into the configuration igniter.
            result["environment_missing"] = environment_missing
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
        if delegation:
            event["payload"]["delegation"] = delegation
            event["payload"]["sponsor_agent_snapshot_ref"] = binding["sponsor_agent_snapshot_ref"]
        enqueue(root, event)
        try:
            result["receipt"] = flush(root, receipt_scope)
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            return {"ok": False, "agent_execution_enabled": False, "error": str(error)}
        result["context_ready"] = result["ok"]
        result["model_execution_started"] = False
        if result["ok"]:
            result["reporting"] = binding
            if source and not delegation:
                spec = importlib.util.spec_from_file_location(
                    "gonggong_parent_completion", Path(__file__).with_name("parent_completion.py")
                )
                parent_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(parent_module)
                result["parent_confirmation_source"] = parent_module.authority_snapshot(source)
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
    status = _igniter.component_status(root, env)
    checks = {}
    for component_id in ("python", "node", "git"):
        checks[component_id + "_available"] = {
            "ok": status[component_id]["available"],
            "path": status[component_id]["path"],
        }
    checks["candidate_integrity"] = run(
        [sys.executable, str(framework / "tools/verify_framework.py"), "--candidate"], root
    )
    checks["formal_framework_admission"] = run([sys.executable, str(framework / "tools/verify_framework.py")], root)
    manifest = json.loads((framework / "framework-manifest.json").read_text(encoding="utf-8"))
    node = env.get("GONGGONG_NODE", "" if env.get("GONGGONG_RUNTIME_CONFIG") else "node")
    for agent in manifest["agents"]:
        checks["local_admission:" + agent["id"]] = (
            run([node, str(framework / "tools/admission.mjs"), str(framework), agent["id"]], root)
            if node
            else {"ok": False, "error": "runtime_node_unavailable"}
        )
    checks["diting_data"] = run(
        [
            sys.executable,
            "-I",
            storage_entry(),
            "validate",
            "--repo",
            str(root),
        ],
        root,
    )
    environment_checks = {"python_available", "node_available", "git_available"}
    environment_missing = [
        component_id for component_id in ("python", "node", "git") if not status[component_id]["available"]
    ]
    return {
        "ok": all(c["ok"] for c in checks.values()),
        "checks": checks,
        "environment_missing": environment_missing,
        "blocking_checks": [
            name for name, check in checks.items() if name not in environment_checks and not check["ok"]
        ],
        "model_execution_started": False,
        "host_authority_authenticated": False,
        "note": "Readiness diagnostics do not grant permission or test model credentials. Each chat still runs admission and requires a real Diting receipt. Environment gaps are reported separately from framework/admission/data blocking checks.",
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
    path = Path(__file__).resolve().parents[3] / "customizations/components/issue-workorders/work_items.py"
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
    """Read authentication status; runtime/network failures retain their own reason."""
    try:
        _github.run_gh("auth", "status", "--hostname", "github.com", env=dict(env, GONGGONG_GH=gh), timeout=30)
    except _github.GitHubCommandError as error:
        if str(error).startswith("GITHUB_COMMAND:") or error.http_status == 401:
            return False
        raise
    return True


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
    key = request.get("request_id")
    if isinstance(key, str) and re.fullmatch(r"daqian-direct-[a-f0-9]{20}", key):
        routing, api = direct_adapter()
        with outbox_lock(routing.direct_issue.receipt_folder(root, key), time.monotonic() + 3):
            return _issue_start(root, request, routing, api)
    return _issue_start(root, request)


def _issue_start(root, request, routing=None, api=None):
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
    if request_id.startswith("daqian-direct-"):
        expected = request.get("expected_user")
        if (
            not isinstance(expected, str)
            or not re.fullmatch(r"[1-9][0-9]*", expected)
            or module.gh("api", "user", "--jq", ".id").strip() != expected
            or value.get("html_url") != f"https://github.com/{repository}/issues/{number}"
            or statuses not in (["status:planned"], ["status:in-progress"], ["status:in-review"])
        ):
            raise ValueError("请重新核对当前账号、工单来源及状态")
        if statuses == ["status:planned"] and (
            not value.get("updated_at") or request.get("expected_revision") != value["updated_at"]
        ):
            raise ValueError("工单已更新，请刷新天枢后重新确认开始")
        if statuses == ["status:planned"]:
            if routing is None:
                raise ValueError("Invalid direct Issue binding")
            try:
                routing.prepare_start(root, request, api)
            except routing.RoutingReceiptRequired as error:
                return {"ok": False, "error": str(error), "refresh_routing": True, "remote_changed": False}
        elif routing is not None:
            routing.chat_context(root, request, api)
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


def direct_adapter():
    from types import SimpleNamespace

    # tools/gonggong_bridge.py uses runpy, which retains the entry point's import path.
    directory = str(Path(__file__).resolve().parent)
    sys.path.insert(0, directory)
    try:
        import issue_route
    finally:
        sys.path.remove(directory)
    api = SimpleNamespace(
        guide_fields=guide_fields,
        gh_state=gh_state,
        outbox_lock=outbox_lock,
        host_environment=host_environment,
        work_items_module=work_items_module,
        enqueue=enqueue,
        flush=flush,
        discover_node=_igniter.discover_node,
    )
    return issue_route, api


def issue_direct(root, request):
    routing, api = direct_adapter()
    return routing.direct_issue.create(root, request, api)


def issue_route(root, request):
    routing, api = direct_adapter()
    return routing.route(root, request, api)


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
        direct_adapter=direct_adapter,
        enqueue=enqueue,
        flush=flush,
        outbox_lock=outbox_lock,
    )
    return module.intake(root, request, api)


def environment_check_action(root, request):
    return _igniter.environment_check(root, host_environment(root))


def environment_deploy_action(root, request):
    if not isinstance(request, dict):
        raise ValueError("environment-deploy requires a selection object")
    return _igniter.environment_deploy(root, request, host_environment(root))


def environment_rollback_action(root, request):
    return _igniter.environment_rollback(root, host_environment(root))


def acceptance_action(root, request, capture=False, current=False):
    spec = importlib.util.spec_from_file_location("gonggong_acceptance", Path(__file__).with_name("acceptance.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # The wrapper may execute this file with runpy rather than importing it.
    from types import SimpleNamespace

    host = SimpleNamespace(host_environment=host_environment, find_gh=find_gh, issue_binding=issue_binding)
    return module.current(host, root, request) if current else module.execute(host, root, request, capture)


def project_integration_action(root, request):
    spec = importlib.util.spec_from_file_location(
        "gonggong_project_integration", Path(__file__).with_name("project_integration.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from types import SimpleNamespace

    host = SimpleNamespace(host_environment=host_environment, find_gh=find_gh, issue_binding=issue_binding)
    try:
        return module.execute(host, root, request)
    except Exception as error:
        # Keep the native request correlation even when intake/runtime fails.
        # A missing child result cannot establish that no mutation happened.
        return {
            "ok": False,
            "request_nonce": request.get("request_nonce"),
            "state": "reconcile_required",
            "error": str(error),
        }


ENVIRONMENT_ACTIONS = {
    "environment-check": environment_check_action,
    "environment-deploy": environment_deploy_action,
    "environment-rollback": environment_rollback_action,
}


def parent_completion_action(root, request, delivery=False, readback=False):
    spec = importlib.util.spec_from_file_location(
        "gonggong_parent_completion", Path(__file__).with_name("parent_completion.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from types import SimpleNamespace

    host = SimpleNamespace(host_environment=host_environment, find_gh=find_gh, issue_binding=issue_binding)
    if readback:
        return module.readback_delivery(root, request)
    return module.finalize(host, root, request) if delivery else module.execute(host, root, request)


GUIDE_ACTIONS = {
    "parent-completion": parent_completion_action,
    "parent-delivery": lambda root, request: parent_completion_action(root, request, delivery=True),
    "parent-delivery-readback": lambda root, request: parent_completion_action(root, request, readback=True),
    "project-integration": project_integration_action,
    "acceptance-current": lambda root, request: acceptance_action(root, request, current=True),
    "acceptance-capture": lambda root, request: acceptance_action(root, request, True),
    "acceptance-verify": acceptance_action,
    "issue-draft": issue_draft,
    "issue-create": issue_create,
    "issue-start": issue_start,
    "issue-agent": issue_agent,
    "issue-direct": issue_direct,
    "issue-route": issue_route,
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
        result.update(run([sys.executable, "-I", storage_entry(), "validate", "--repo", str(root)], root))
    elif action == "analyze":
        result.update(
            run([sys.executable, "-I", storage_entry(), "analyze", "--repo", str(root), "--tenant", tenant], root)
        )
    else:
        raise ValueError("Unsupported action")
    return result


def publish_result(path, content):
    """Retry transport only; the completed action must never be replayed here."""
    temporary = path.with_suffix(".tmp")
    stage = "write"
    attempts = 0
    try:
        temporary.write_text(content, encoding="utf-8")
        stage = "replace"
        deadline = time.monotonic() + 1.0
        while True:
            attempts += 1
            try:
                temporary.replace(path)
                return True
            except OSError as error:
                # Access denied (5/EACCES) is not evidence of a transient lock.
                # winerror survives only on genuine Windows OS errors (or fixtures).
                if getattr(error, "winerror", None) not in (32, 33) or attempts >= 6:
                    raise
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise
                time.sleep(min(0.1, remaining))
    except OSError as error:
        # Do not print exception text or result contents: both can contain private
        # paths, credentials or user data. Keep the temporary bytes for diagnosis.
        diagnostic = {
            "status": "receipt_publication_failed",
            "stage": stage,
            "attempts": attempts,
            "errno": error.errno,
            "winerror": getattr(error, "winerror", None),
            "temporary_retained": temporary.is_file(),
        }
        sys.stderr.write(json.dumps(diagnostic, sort_keys=True) + "\n")
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=[
            "status",
            "doctor",
            "check",
            "validate",
            "analyze",
            "chat",
            "flush",
            *GUIDE_ACTIONS,
            *ENVIRONMENT_ACTIONS,
        ],
    )
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--tenant", default="gonggong-workspace")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--receipt-tenant")
    parser.add_argument("--receipt-request")
    parser.add_argument("--receipt-source")
    args = parser.parse_args()
    try:
        if args.action in {"issue-agent", "issue-route", "issue-draft"}:
            _paths_module.prepare_game_workspace(Path(args.workspace), work_items_module(Path(args.workspace)))
        if args.action == "chat":
            if args.request is None:
                raise ValueError("chat requires --request")
            result = chat(Path(args.workspace), json.loads(args.request.read_text(encoding="utf-8")), args.tenant)
        elif args.action in ENVIRONMENT_ACTIONS:
            request = {}
            if args.request is not None:
                request = json.loads(args.request.read_text(encoding="utf-8"))
            result = ENVIRONMENT_ACTIONS[args.action](Path(args.workspace).resolve(), request)
        elif args.action in GUIDE_ACTIONS:
            if args.request is None:
                raise ValueError(args.action + " requires --request")
            request = json.loads(args.request.read_text(encoding="utf-8"))
            if not isinstance(request, dict):
                raise ValueError("Issue guide request must be an object")
            if args.action in {"issue-agent", "issue-route"}:
                sys.stdin.reconfigure(encoding="utf-8")
                credentials = json.loads(sys.stdin.readline(8192))
                if set(credentials) != {"api_key"} or not isinstance(credentials["api_key"], str):
                    raise ValueError("Requirements credentials must use the private stdin pipe")
                request["_private_api_key"] = credentials["api_key"]
                request["_cancel_path"] = str(args.request)
            result = GUIDE_ACTIONS[args.action](Path(args.workspace).resolve(), request)
        elif args.action == "flush":
            scope = None
            if any((args.receipt_tenant, args.receipt_request, args.receipt_source)):
                scope = {
                    "tenant_id": args.receipt_tenant,
                    "request_id": args.receipt_request,
                    "source_ref": args.receipt_source,
                }
            result = flush(Path(args.workspace), scope)
        else:
            result = execute(args.workspace, args.action, args.tenant)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        result = {"ok": False, "agent_execution_enabled": False, "error": str(error)}
    if args.action == "issue-direct" and not result["ok"]:
        result.setdefault("reconcile_required", True)
    content = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        if not publish_result(args.out, content):
            return 2
    else:
        sys.stdout.buffer.write((content + "\n").encode("utf-8"))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
