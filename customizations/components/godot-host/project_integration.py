"""Installed adapter for the live native integration owner; never a JSON grant.

The caller retains actual independent completion provenance and pinned plans.
Cancellation leaves durable intent for conservative, explicit rollback.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path


def execute(bridge, root, request):
    action = request.get("action")
    if action not in {"plan", "apply", "rollback"}:
        raise ValueError("Unsupported project integration action")
    nonce = request.get("request_nonce")
    if not isinstance(nonce, str) or not 0 < len(nonce) <= 256:
        raise ValueError("Missing host request correlation")
    live_path = Path(request["host_liveness_path"])
    if not live_path.is_absolute():
        raise ValueError("Host liveness path must be absolute")
    live = json.loads(live_path.read_text(encoding="utf-8"))
    if live.get("active") is not True or live.get("request_nonce") != nonce:
        raise ValueError("Host generation cancelled or unknown")
    raw = request.get("decision_json")
    if not isinstance(raw, str) or not 0 < len(raw.encode("utf-8")) <= 16 * 1024 * 1024:
        raise ValueError("Missing bounded host decision")
    decision = json.loads(raw)
    if Path(decision["candidate"]["root"]).resolve() != Path(root).resolve():
        raise ValueError("Candidate differs from host selection")
    installation = Path(__file__).resolve().parents[3]
    if request.get("resolve_project_workspace") is True:
        # The native parent supplies the actually open project. Its repository
        # may be the primary checkout while the workflow owns another worktree.
        # Resolve from that project, never from a model-supplied destination.
        project = Path(request["project_root"])
        if not project.is_absolute() or not (project / "project.godot").is_file():
            raise ValueError("Actual open project required")
        project_env = bridge.host_environment(root)
        git = project_env.get("GONGGONG_GIT") or shutil.which("git", path=project_env.get("PATH"))
        if not git:
            raise ValueError("Git host runtime unavailable")
        resolved = subprocess.run(
            [git, "-C", str(project), "rev-parse", "--show-toplevel"],
            env=project_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        if resolved.returncode:
            raise ValueError("Open project repository unavailable")
        project_workspace = Path(resolved.stdout.strip()).resolve()
        request = dict(
            request,
            workspace_root=str(project_workspace),
            transaction_root=str(project_workspace / "data-collection/outbox/project-integration"),
        )
    # Current account/intake are independent of serialized verdict data.
    # Installed Node validateDecision permits only verified ledger-only commits.
    destination = Path(request["workspace_root"] if action == "rollback" else root).resolve()
    env = bridge.host_environment(destination)
    gh = bridge.find_gh(env, destination)
    if not gh:
        raise ValueError("GitHub CLI unavailable")
    repository = json.loads((destination / "work-items.json").read_text(encoding="utf-8"))["repository"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid configured repository")

    def api(endpoint):
        result = subprocess.run(
            [gh, "api", endpoint],
            cwd=destination,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=45,
        )
        if result.returncode:
            raise ValueError("Current GitHub authority unavailable")
        return json.loads(result.stdout)

    operator = api("user")["login"]
    permission = api(f"repos/{repository}/collaborators/{operator}/permission")
    if not any(permission.get(k) in {"write", "maintain", "admin"} for k in ("permission", "role_name")):
        raise ValueError("Current repository write permission required")
    bridge.issue_binding(destination, dict(request, daqian_bound=True), "gonggong-workspace")
    policy = decision["candidate"].get("audit_policy")
    if policy != {
        "tenant_id": "gonggong-workspace",
        "request_id": request["request_id"],
        "source_ref": f"https://github.com/{repository}/issues/{request['issue_number']}",
    }:
        raise ValueError("Current intake differs from original decision")
    env = bridge.host_environment(root)
    node = env.get("GONGGONG_NODE") or shutil.which("node", path=env.get("PATH"))
    if not node:
        raise ValueError("Node host runtime unavailable")
    process = subprocess.run(
        [node, str(installation / "tools/godot_parallel/integration.mjs")],
        cwd=installation,
        env=env,
        input=json.dumps(request),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    result = json.loads(process.stdout)
    if result.get("request_nonce") != nonce:
        raise ValueError("Integration response correlation mismatch")
    return result
