"""Private same-process editor acceptance bridge, not a verdict authentication API.

The C++ completion owner retains the live reviewer/generation/criteria provenance.
This adapter independently rechecks current account authority and file bindings.
No disk receipt can reconstruct that live owner after a cold restart.
"""

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def current(bridge, root, request):
    """Read-only currentness check; this operation cannot accept or dispatch work."""
    nonce = request.get("request_nonce")
    if not isinstance(nonce, str) or not nonce or len(nonce) > 256:
        raise ValueError("Missing host request correlation")
    candidate = request.get("candidate")
    if not isinstance(candidate, dict) or Path(candidate["root"]).resolve() != Path(root).resolve():
        raise ValueError("Candidate differs from requested workspace")
    payload = json.dumps(candidate)
    if len(payload.encode("utf-8")) > 16 * 1024 * 1024:
        raise ValueError("Candidate manifest exceeds limit")
    installation = Path(__file__).resolve().parents[3]
    env = bridge.host_environment(root)
    node = env.get("GONGGONG_NODE") or shutil.which("node", path=env.get("PATH"))
    if not node:
        raise ValueError("Node host runtime unavailable")
    process = subprocess.run(
        [
            node,
            str(installation / "customizations/components/repository-dispatch/acceptance.mjs"),
            "current",
            str(root),
        ],
        cwd=installation,
        env=env,
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    checked = json.loads(process.stdout)
    if process.returncode or checked.get("ok") is not True:
        raise ValueError(checked.get("error", "Candidate check failed"))
    return {
        "ok": True,
        "request_nonce": nonce,
        "candidate_sha256": candidate["files_sha256"],
        "current_candidate": checked["current_candidate"],
    }


def execute(bridge, root, request, capture=False):
    nonce = request.get("request_nonce")
    if not isinstance(nonce, str) or not nonce or len(nonce) > 256:
        raise ValueError("Missing host request correlation")
    result = {"ok": False, "request_nonce": nonce}
    raw = request.get("decision_json")
    if not capture:
        if not isinstance(raw, str) or not 0 < len(raw.encode("utf-8")) <= 16 * 1024 * 1024:
            raise ValueError("Missing bounded host decision")
        result["decision_sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        live_path = request.get("host_liveness_path")
        if not isinstance(live_path, str) or not Path(live_path).is_absolute():
            raise ValueError("Missing native host liveness path")
        live = json.loads(Path(live_path).read_text(encoding="utf-8"))
        if live.get("active") is not True or live.get("request_nonce") != nonce:
            raise ValueError("Host generation cancelled or unknown")
    root = Path(root).resolve()
    env = bridge.host_environment(root)
    gh = bridge.find_gh(env, root)
    if not gh:
        raise ValueError("GitHub CLI unavailable")

    def api(endpoint):
        process = subprocess.run(
            [gh, "api", endpoint], cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", timeout=45
        )
        if process.returncode:
            raise ValueError("Current GitHub authority unavailable")
        return json.loads(process.stdout)

    settings = json.loads((root / "work-items.json").read_text(encoding="utf-8"))
    repository = settings["repository"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid configured repository")
    operator = api("user")["login"]
    permission = api(f"repos/{repository}/collaborators/{operator}/permission")
    if permission.get("permission") not in {"write", "maintain", "admin"} and permission.get("role_name") not in {
        "write",
        "maintain",
        "admin",
    }:
        raise ValueError("Current repository write permission required")
    # Always execute the installed reader, not a candidate-provided authority script.
    binding = dict(request, daqian_bound=True)
    bridge.issue_binding(root, binding, "gonggong-workspace")
    audit_policy = {
        "tenant_id": "gonggong-workspace",
        "request_id": request["request_id"],
        "source_ref": f"https://github.com/{repository}/issues/{request['issue_number']}",
    }
    installation = Path(__file__).resolve().parents[3]
    node = env.get("GONGGONG_NODE") or shutil.which("node", path=env.get("PATH"))
    if not node:
        raise ValueError("Node host runtime unavailable")
    config = request.get("host_dispatch_config") if not capture else None
    if config and (not isinstance(config, str) or not Path(config).is_absolute()):
        raise ValueError("Host dispatch configuration must be absolute")
    command = [
        node,
        str(installation / "customizations/components/repository-dispatch/acceptance.mjs"),
        "capture" if capture else "project" if config else "verify",
        str(root),
    ]
    if not capture:
        decision = json.loads(raw)
        if Path(decision["candidate"]["root"]).resolve() != root:
            raise ValueError("Decision candidate differs from bound workspace")
        if decision["candidate"].get("audit_policy") != audit_policy:
            raise ValueError("Candidate audit policy differs from current intake")
    payload = json.dumps(dict(request, operator=operator, gh=gh, python=sys.executable)) if config else raw
    process = subprocess.run(
        command,
        cwd=installation,
        env=env,
        input=json.dumps(audit_policy) if capture else payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    checked = json.loads(process.stdout)
    if process.returncode or checked.get("ok") is not True:
        raise ValueError(checked.get("error", "Acceptance candidate verification failed"))
    if not capture:
        live = json.loads(Path(live_path).read_text(encoding="utf-8"))
        if live.get("active") is not True or live.get("request_nonce") != nonce:
            raise ValueError("Host generation cancelled; preserve projection receipt for recovery")
    result.update(ok=True, operator=operator)
    if capture:
        result["candidate"] = checked["candidate"]
    else:
        result["candidate_sha256"] = decision["candidate"]["files_sha256"]
        result["current_candidate"] = checked["current_candidate"]
        result["projection"] = checked.get("projection", {"state": "not_configured"})
    return result
