"""Run or inspect a host-signed framework plan for one exact Sinan assignment."""

import hashlib
import hmac
import json
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FRAMEWORK = ROOT / "framework"
sys.path.insert(0, str(ROOT / "customizations/platforms/ai-access/host-http/runtime"))
import runner  # noqa: E402 - load the host runtime from its repository-owned location.


def resource(path):
    # Sinan normalizes Windows drive/UNC paths to lower-case forward slashes.
    resolved = path.resolve().as_posix()
    return resolved.lower() if sys.platform == "win32" else resolved


def execute(grant, assignment, action="run", original=None):
    payload = grant["payload"]
    state = Path(payload["state_dir"])
    if action == "--inspect":
        # Historical evidence may outlive its execution mandate. Only this read-only
        # branch accepts expiry; the ledger must still match the exact signed grant.
        if not hmac.compare_digest(runner.signature(payload), grant["signature"]):
            raise ValueError("Invalid historical grant signature")
        if payload.get("runtime_sha256") != runner.runtime_digest():
            raise ValueError("Historical runtime binding changed")
        if (
            payload["framework_sha256"]
            != hashlib.sha256((FRAMEWORK / "framework-manifest.json").read_bytes()).hexdigest()
        ):
            raise ValueError("Historical framework binding changed")
    else:
        runner.verify_grant(grant, FRAMEWORK, state)
    task = payload["task"]
    if not (
        payload["authority_ref"] == task["authority_ref"] == assignment["authorityRef"]
        and state.is_absolute()
        and resource(state) in assignment["writes"]
        and resource(FRAMEWORK.parent) in assignment["reads"]
        and task["tenant_id"] == "gonggong-workspace"
        and task["outcome"] == assignment["outcome"]
        and task.get("source_revision") == assignment["sourceSnapshot"]["sha256"]
        and any(link["id"] == assignment["ticket"] for link in task["work_items"])
        and {profile["id"] for profile in payload["profiles"]} == {assignment["model"]["id"]}
        and {step["kind"] for step in task["steps"]} == set(assignment["model"]["capabilities"])
        and task.get("validation_only", False) is False
    ):
        raise ValueError("Grant does not match this production assignment")
    # A renewal can change expiry without substituting a different job or budget.
    binding = runner.digest({k: v for k, v in payload.items() if k not in {"expires_at", "replaces_grant"}})
    if action == "--check":
        runner.validate_plan(payload)
        return {"binding": binding}
    if original != binding:
        raise ValueError("Original signed production plan changed")
    job = runner.jid_for(task)
    if action == "--inspect":
        uri = (state / "runtime.sqlite").resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as db:
            row = db.execute("SELECT task_hash,grant_hash,status,result FROM jobs WHERE id=?", (job,)).fetchone()
        if not row or row[0] != runner.digest(task) or row[1] != runner.digest(grant):
            raise ValueError("No matching runtime receipt")
        result = {"status": row[2], "result": json.loads(row[3]) if row[3] else None}
    elif action == "run":
        result = runner.run(grant, FRAMEWORK, state)
    else:
        raise ValueError("Unsupported worker operation")
    if result["status"] == "completed":
        return {"status": "completed", "submission": result["result"]["diting_submission_id"], "job": job}
    return {"status": result["status"], "job": job}


if __name__ == "__main__":
    os.environ["GONGGONG_PYTHON"] = sys.executable
    print(json.dumps(execute(runner.read(sys.argv[1]), json.load(sys.stdin), *sys.argv[2:])))
