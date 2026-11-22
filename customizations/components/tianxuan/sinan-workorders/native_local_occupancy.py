"""Recover a local reservation only from its installed host and original run."""

import json
import os
import socket
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from native_store import NativeStoreError, _json
from tianxuan_core import NotFound, PermissionDenied


def _process(pid):
    # An inaccessible process or failed ps lookup cannot establish physical exit.
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return "gone"
    except PermissionError:
        return "unknown"
    try:
        observed = subprocess.run(
            ["/bin/ps", "-p", str(pid), "-o", "lstart=", "-o", "stat="],
            env={"LC_ALL": "C", "TZ": "UTC"},
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    fields = observed.stdout.split()
    if observed.returncode or len(fields) < 6:
        return "unknown"
    return "gone" if fields[-1].startswith("Z") else " ".join(fields[:-1])


@lru_cache(maxsize=1)
def _current(pid):
    birth = _process(pid)
    if birth in {"gone", "unknown"}:
        return None
    try:
        if sys.platform == "darwin":
            boot = subprocess.check_output(
                ["/usr/sbin/sysctl", "-n", "kern.bootsessionuuid"], text=True, timeout=3
            ).strip()
        elif sys.platform == "linux":
            boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip() + "/" + os.readlink("/proc/self/ns/pid")
        else:
            return None
    except (OSError, subprocess.SubprocessError):
        return None
    if not boot:
        return None
    return {"host": socket.gethostname(), "boot": boot, "pid": pid, "birth": birth}


def local_owner(workflow):
    if os.name != "posix" or workflow.worker is None or callable(getattr(workflow.worker, "reserve", None)):
        return None
    # External adapters own their reservation and physical closure protocol.
    if not getattr(workflow.worker, "records_local_process_group", False):
        return None
    identity = _current(os.getpid())
    return {**identity, "root": str(workflow.worker.root)} if identity else None


def remember(db, workflow, actor, key):
    owner = local_owner(workflow)
    if owner is not None:
        db.execute(
            "INSERT OR REPLACE INTO native_local_occupancy(task,actor,owner) VALUES (?,?,?)", (key, actor, _json(owner))
        )


def _orphan_state(row):
    if row["state"] == "reserved":
        return "reserved"
    pgid = row["pgid"]
    if pgid is None:
        return None  # Historical/ambiguous launch windows retain their occupancy.
    if type(pgid) is not int or pgid <= 1:
        raise NativeStoreError("Invalid local process receipt")
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        # Even without a recoverable output, the entire owned group has exited.
        return "closed-unresolved"
    except PermissionError:
        pass
    return None


def recover_local_occupancy(workflow, actor, project):
    current = local_owner(workflow)
    results = []
    with workflow._transaction() as db:
        workflow.domain._validate_project(project)
        tenant = workflow.domain.actor_context(actor)["tenant"]
        if current is None:
            return {"items": []}
        rows = db.execute(
            "SELECT t.*,o.owner,o.pgid FROM native_local_occupancy o JOIN native_tasks t ON t.id=o.task "
            "JOIN native_active_tasks a ON a.task=t.id AND a.issue=t.issue JOIN issues i ON i.id=t.issue "
            "JOIN native_edit_origins origin ON origin.task=t.id AND origin.project=i.project "
            "WHERE t.tenant=? AND origin.project=? AND o.actor=? AND t.state IN ('running','held','reserved')",
            (tenant, project, actor),
        ).fetchall()
        for row in rows:
            owner = json.loads(row["owner"])
            if any(owner.get(k) != current[k] for k in ("host", "boot", "root")):
                continue
            try:
                workflow._read_allowed(actor, row)
                task = workflow._valid(actor, row)
            except (NotFound, NativeStoreError, PermissionDenied):
                continue
            if task["actor"] != actor:
                continue
            key = row["id"]
            item = {"task": key, "worker_ref": "native-worker:" + key, "reclaimed": False, "state": row["state"]}
            results.append(item)
            if owner == current:
                continue
            birth = _process(owner["pid"])
            if birth == "unknown" or birth == owner["birth"]:
                continue
            state = _orphan_state(row)
            if state is None:
                continue
            db.execute("UPDATE native_local_occupancy SET owner=? WHERE task=?", (_json(current), key))
            db.execute("UPDATE native_tasks SET state=? WHERE id=?", (state, key))
            item.update(reclaimed=True, state=state)
            workflow.domain._event(tenant, "native.local-occupancy-recovered", actor, row["issue"], item)
    return {"items": results}
