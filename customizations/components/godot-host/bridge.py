"""Godot host adapter. Framework/data remain in their existing Git workspace."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


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
                    raise ValueError("Hermes delivery busy; envelopes retained")
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
    with outbox_lock(root / ".olympus-outbox/chat", deadline):
        return flush_locked(root, deadline)


def flush_locked(root, deadline):
    """Idempotent durable file outbox. Only delete an envelope after a real receipt."""
    root = Path(root).resolve()
    outbox = root / ".olympus-outbox/chat"
    receipts = []
    for pending in sorted(outbox.glob("*.json")):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("Hermes flush time budget reached; remaining envelopes retained")
        if pending.is_symlink():
            raise ValueError("Linked outbox entry is not allowed")
        recorded = subprocess.run(
            [
                sys.executable,
                str(root / "Olympus/extensions/hermes-files/hermes_files.py"),
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
            raise ValueError("Hermes receipt failed; envelope retained: " + recorded.stderr.strip())
        receipts.append(json.loads(recorded.stdout))
        pending.unlink(missing_ok=True)
    return {"ok": True, "state": "recorded_file", "receipts": receipts, "git_committed": False}


def enqueue(root, event):
    outbox = root / ".olympus-outbox/chat"
    outbox.mkdir(parents=True, exist_ok=True)
    pending = outbox / (event["event_id"] + ".json")
    temporary = pending.with_suffix(".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(pending)


def host_environment(root):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", OLYMPUS_PYTHON=sys.executable)
    node = env.get("OLYMPUS_NODE")
    if not node and (root / "project/runtime/node/node.exe").is_file():
        node = str(root / "project/runtime/node/node.exe")
        env["OLYMPUS_NODE"] = node
    if node and Path(node).is_file():
        # Framework subprocesses also invoke `node`; honor the host's runtime choice.
        env["PATH"] = str(Path(node).resolve().parent) + os.pathsep + env.get("PATH", "")
    git = env.get("OLYMPUS_GIT") or root / "project/runtime/git/cmd/git.exe"
    if Path(git).is_file():
        env["PATH"] = str(Path(git).resolve().parent) + os.pathsep + env.get("PATH", "")
    config = root / ".olympus-local.json"
    if config.is_file():
        local = json.loads(config.read_text(encoding="utf-8-sig"))
        for name in (
            "GONGGONG_FRAMEWORK_SOURCE",
            "GONGGONG_SINAN_FRAMEWORK_SOURCE",
            "GONGGONG_SINAN_IMPLEMENTATION_SOURCE",
        ):
            if name in local:
                env[name] = str((root / local[name]).resolve())
    return env


def request_identity(request):
    # Legacy Godot callers remain supported; protocol v1 requires explicit identity.
    if "protocol_version" not in request and "host" not in request:
        return {"id": "godot-editor", "kind": "engine"}, request.get("agent_id", "athena")
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


def checked_issue_binding(root, request, tenant):
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


def issue_binding(root, request, tenant):
    """An Issue mismatch is advisory; it must not prevent host development."""
    try:
        value = checked_issue_binding(root, request, tenant)
        return {**value, "state": "verified"}
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired):
        return {
            "state": "needs-reconciliation",
            "url": None,
            "warning": "Issue 关联缺失、不符或暂时无法核实；本轮继续，请创建/复用真实工单并纠正关联。",
            "next_action": "Reconcile the real Issue association and retain a correction receipt; never present an unverified Issue URL as verified",
        }


def chat(root, request, tenant):
    """Load framework context; never fall back to a model when checks reject it."""
    root = root.resolve()
    framework = root / "Olympus"
    manifest = json.loads((framework / "framework-manifest.json").read_text(encoding="utf-8"))
    host, agent_id = request_identity(request)
    matches = [a for a in manifest["agents"] if a["id"] == agent_id]
    if len(matches) != 1:
        raise ValueError("Agent is not uniquely registered: " + agent_id)
    agent = matches[0]
    request = dict(request)
    if not isinstance(request.get("request_id"), str) or not re.fullmatch(
        r"[a-z0-9]+(?:-[a-z0-9]+)*", request["request_id"]
    ):
        identity = json.dumps([host, tenant, request.get("authority_ref"), request.get("outcome")], sort_keys=True)
        request["request_id"] = "pending-issue-" + hashlib.sha256(identity.encode()).hexdigest()[:32]
    for field in ("request_id", "outcome", "authority_ref", "project"):
        if not isinstance(request.get(field), str) or not request[field].strip():
            raise ValueError("Missing host request: " + field)
    permission_fields = ("tools_enabled", "file_changes_require_approval", "execution_requires_approval")
    if any(type(request.get(field)) is not bool for field in permission_fields):
        raise ValueError("Missing host permission state")
    issue = issue_binding(root, request, tenant)
    source_ref = issue.get("url") or host["id"] + ":ai-chat:issue-unverified"
    flush(root)  # An earlier failed delivery blocks the next model/tool round.
    binding = {
        "tenant_id": tenant,
        "request_ref": request["request_id"],
        "source_ref": source_ref,
        "agent_snapshot_ref": agent_id + "@" + agent["version"] + "#" + agent["candidate_digest"],
        "outbox_path": ".olympus-outbox/chat",
        "sink_ref": "olympus-hermes-data",
        "path_base": "workspace_root",
        "authority_ref": request["authority_ref"],
        "agent": {
            "id": agent_id,
            "version": agent["version"],
            "origin": "olympus-framework",
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
                "olympus-hermes-data real events",
            ],
            "before_commit": "Review and sanitize actual sources, stage current bytes together, run the trusted Issue gate on final content",
            "after_commit": "Run Hermes git-check --require-committed against HEAD; record push and merge separately",
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
                    env.get("OLYMPUS_NODE", "node"),
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
            "source_ref": source_ref,
            "agent": {
                "id": "olympus-host-adapter",
                "version": "1.1.0",
                "definition_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "origin": "olympus-host-adapter",
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
        result["issue_intake"] = issue
        result["warning"] = issue.get("warning", "")
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
    framework = root / "Olympus"
    env = host_environment(root)
    node = env.get("OLYMPUS_NODE", "node")
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
    checks["hermes_data"] = run(
        [sys.executable, str(framework / "extensions/hermes-files/hermes_files.py"), "validate", "--repo", str(root)],
        root,
    )
    return {
        "ok": all(c["ok"] for c in checks.values()),
        "checks": checks,
        "blocking_checks": [name for name, check in checks.items() if not check["ok"]],
        "model_execution_started": False,
        "host_authority_authenticated": False,
        "note": "Readiness diagnostics do not grant permission or test model credentials. Each chat still runs admission and requires a real Hermes receipt.",
    }


def admission_record_status(framework, agent):
    try:
        value = json.loads((framework / agent["admission_pass"]).read_text(encoding="utf-8"))
        return value["status"] if isinstance(value.get("status"), str) else "invalid"
    except (FileNotFoundError, KeyError):
        return "missing"
    except (OSError, ValueError, TypeError, AttributeError):
        return "invalid_or_unavailable"


def execute(workspace, action, tenant):
    root = Path(workspace).resolve()
    framework = root / "Olympus"
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
    hermes = str(framework / "extensions/hermes-files/hermes_files.py")
    if action == "status":
        result.update(
            ok=True,
            framework_status=manifest["status"],
            data_available=(root / "olympus-hermes-data/dataset.json").is_file(),
        )
    elif action == "doctor":
        result.update(diagnose(root))
    elif action == "check":
        result.update(run([sys.executable, str(framework / "tools/verify_framework.py"), "--candidate"], root))
    elif action == "validate":
        result.update(run([sys.executable, hermes, "validate", "--repo", str(root)], root))
    elif action == "analyze":
        result.update(run([sys.executable, hermes, "analyze", "--repo", str(root), "--tenant", tenant], root))
    else:
        raise ValueError("Unsupported action")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["status", "doctor", "check", "validate", "analyze", "chat", "flush"])
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--tenant", default="olympus-workspace")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--request", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "chat":
            if args.request is None:
                raise ValueError("chat requires --request")
            result = chat(Path(args.workspace), json.loads(args.request.read_text(encoding="utf-8")), args.tenant)
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
