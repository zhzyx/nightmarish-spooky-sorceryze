"""Trusted installed local producer. Ordinary files, not an OS sandbox."""

from __future__ import annotations

import json
import math
from pathlib import Path

from native_check_runner import _process_helper
from native_store import NativeStoreError, _digest, _json
from native_workspace import NativeWorkspace, absolute


class NativeWorker:
    def __init__(self, store, root, profiles, verify_installation, process_helper_path=None):
        if not callable(verify_installation):
            raise NativeStoreError("Installation verifier required")
        self.store = store
        self.root = absolute(root, missing=True)
        self.root.mkdir(parents=True, exist_ok=True)
        self.profiles = json.loads(_json(profiles))
        self.verify = verify_installation
        self.helper = _process_helper(process_helper_path)
        self.workspace = NativeWorkspace(store)
        with store._connection(write=True) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_worker_terminals (execution TEXT PRIMARY KEY, task TEXT NOT NULL, terminal TEXT NOT NULL)"
            )
        for spec in self.profiles.values():
            if set(spec) != {"argv", "env", "timeout", "log_bytes"}:
                raise NativeStoreError("Invalid trusted producer profile")
            if (
                not isinstance(spec["argv"], list)
                or not spec["argv"]
                or not all(isinstance(a, str) and a for a in spec["argv"])
            ):
                raise NativeStoreError("Absolute installed executable required")
            executable = absolute(spec["argv"][0])
            if not executable.is_file() or executable.suffix.lower() in {".cmd", ".bat"}:
                raise NativeStoreError("Direct executable required")
            if (
                type(spec["timeout"]) not in {int, float}
                or not math.isfinite(spec["timeout"])
                or not 0 < spec["timeout"] <= 86400
                or type(spec["log_bytes"]) is not int
                or not 0 < spec["log_bytes"] <= 900000
            ):
                raise NativeStoreError("Invalid process budget")
            if not isinstance(spec["env"], dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in spec["env"].items()
            ):
                raise NativeStoreError("Explicit fixed environment required")

    def installation(self, profile):
        spec = self.profiles[profile]
        if self.verify(profile, json.loads(_json(spec))) is not True:
            raise NativeStoreError("Producer installation rejected")
        return _digest(
            _json({
                "profile": spec,
                "executable": _digest(Path(spec["argv"][0]).read_bytes()),
                "helper": self.helper.implementation_fingerprint(),
                "worker": _digest(Path(__file__).read_bytes()),
            }).encode()
        )

    def run(self, task, execution, cancel=None):
        spec = self.profiles[task["profile"]]
        if self.installation(task["profile"]) != task["installation"]:
            raise NativeStoreError("Authorized installation changed")
        if self.verify(task["profile"], json.loads(_json(spec))) is not True:
            raise NativeStoreError("Producer installation rejected")
        folder = self.root / execution
        folder.mkdir()  # Existing intent is never blindly relaunched.
        work = folder / "work"
        tenant, actor = task["tenant"], task["producer"]
        self.workspace.materialize(tenant, task["selected"], work)
        context = folder / "context.json"
        context.write_text(_json(task["source"]["definition"]), encoding="utf-8")
        env = {**spec["env"], "NATIVE_WORKSPACE": str(work), "NATIVE_CONTEXT": str(context)}
        reasons = []
        with (folder / "process.log").open("w+b") as log:
            code = self.helper.run_owned(
                spec["argv"],
                stdout=log,
                env=env,
                limit=spec["log_bytes"],
                timeout=spec["timeout"],
                active=lambda: cancel is None or not cancel.is_set(),
                fail=reasons.append,
                cwd=work,
            )
            log.flush()
            log.seek(0)
            digest = _digest(log.read())
        if code != 0 or reasons or (cancel is not None and cancel.is_set()):
            return self._terminal(
                task, execution, {"state": "failed", "exit_code": code, "reasons": reasons, "transcript": digest}
            )
        if self.verify(task["profile"], json.loads(_json(spec))) is not True:
            raise NativeStoreError("Producer installation changed")
        changes = self.workspace.collect(tenant, task["selected"], work)
        for change in changes:
            allowed = task["writes"].get(change["module"], [])
            if allowed != "*" and any(name not in allowed for name in change["edits"]):
                raise NativeStoreError("Producer changed objects outside mandate")
            if change["module"].startswith("requirement-"):
                raise NativeStoreError("Requirement source is immutable")
        revisions = dict(task["selected"])
        if changes:
            revisions.update(self.store.submit(tenant, actor, "worker-" + execution, changes)["revisions"])
        candidate = self.store.compose(tenant, revisions)["id"]
        return self._terminal(
            task,
            execution,
            {
                "state": "produced",
                "exit_code": code,
                "transcript": digest,
                "candidate": candidate,
                "modules": revisions,
                "usage": None,
                "provider_model": None,
            },
        )

    def _terminal(self, task, execution, terminal):
        with self.store._connection(write=True) as db:
            db.execute(
                "INSERT INTO native_worker_terminals VALUES (?,?,?)",
                (execution, _digest(_json(task).encode()), _json(terminal)),
            )
        return terminal

    def reconcile(self, task, execution):
        """Only host-recorded terminal after owned process close; never a PID claim."""
        with self.store._connection() as db:
            row = db.execute(
                "SELECT task,terminal FROM native_worker_terminals WHERE execution=?", (execution,)
            ).fetchone()
        if row is None:
            return None
        if row["task"] != _digest(_json(task).encode()):
            raise NativeStoreError("Worker terminal contract mismatch")
        return json.loads(row["terminal"])
