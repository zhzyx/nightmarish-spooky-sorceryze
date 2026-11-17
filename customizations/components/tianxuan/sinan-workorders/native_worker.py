"""Trusted installed local producer. Ordinary files, not an OS sandbox."""

from __future__ import annotations

import json
import math
from pathlib import Path

from native_candidates import NativeCandidates
from native_check_runner import _process_helper
from native_store import NativeStoreError, _digest, _json
from native_workspace import Limits, NativeWorkspace, absolute


class NativeWorker:
    def __init__(
        self, store, root, profiles, verify_installation, process_helper_path=None, *, authorize=None, limits=None
    ):
        if not callable(verify_installation):
            raise NativeStoreError("Installation verifier required")
        limits = limits or Limits(file_bytes=2 * 1024 * 1024, total_bytes=8 * 1024 * 1024)
        self.intake = NativeCandidates(store, authorize, limits)
        self.store = store
        self.root = absolute(root, missing=True)
        self.root.mkdir(parents=True, exist_ok=True)
        self.profiles = json.loads(_json(profiles))
        self.verify = verify_installation
        self.helper = _process_helper(process_helper_path)
        self.workspace = NativeWorkspace(store, limits)
        with store._connection(write=True) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_worker_terminals_v2 (execution TEXT PRIMARY KEY, task TEXT NOT NULL, terminal TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_worker_closed (execution TEXT PRIMARY KEY, task TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_worker_process_closures (execution TEXT PRIMARY KEY, task TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL)"
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
        task = json.loads(_json(task))
        self._contract(task, execution)
        recovered = self.reconcile(task, execution)
        if recovered is not None:
            return recovered
        spec = self.profiles[task["profile"]]
        if self.installation(task["profile"]) != task["installation"]:
            raise NativeStoreError("Authorized installation changed")
        if self.verify(task["profile"], json.loads(_json(spec))) is not True:
            raise NativeStoreError("Producer installation rejected")
        folder = self.root / execution
        folder.mkdir()  # Existing intent is never blindly relaunched.
        work = folder / "work"
        tenant = task["tenant"]
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
        physical = _json({"exit_code": code, "reasons": reasons, "transcript": digest})
        with self.store._connection(write=True) as db:
            db.execute(
                "INSERT INTO native_worker_process_closures VALUES (?,?,?,?)",
                (execution, _json(task), physical, _digest(physical.encode())),
            )
        if code != 0 or reasons or (cancel is not None and cancel.is_set()):
            self._close_output(task, execution, [], code, digest, cancel)
            return self.reconcile(task, execution)
        if self.verify(task["profile"], json.loads(_json(spec))) is not True:
            raise NativeStoreError("Producer installation changed")
        changes = self.workspace.collect(tenant, task["selected"], work)
        for change in changes:
            allowed = task["writes"].get(change["module"], [])
            if allowed != "*" and any(name not in allowed for name in change["edits"]):
                raise NativeStoreError("Producer changed objects outside mandate")
            if change["module"].startswith("requirement-"):
                raise NativeStoreError("Requirement source is immutable")
        # Only owned process closure + flushed transcript + bounded collection can
        # create this host database record. Workspace files never confer recovery.
        encoded = [{**c, "edits": {n: None if b is None else b.hex() for n, b in c["edits"].items()}} for c in changes]
        self._close_output(task, execution, encoded, code, digest, cancel)
        return self.reconcile(task, execution)

    def _close_output(self, task, execution, changes, code, transcript, cancel):
        with self.store._connection(write=True) as db:
            # Linearization point: cancellation observed here wins over output.
            # After this immutable decision, recovery never consults a live event.
            cancelled = cancel is not None and cancel.is_set()
            payload = _json({
                "changes": [] if cancelled else changes,
                "exit_code": code,
                "transcript": transcript,
                "cancelled": cancelled,
            })
            db.execute(
                "INSERT INTO native_worker_closed VALUES (?,?,?,?)",
                (execution, _json(task), payload, _digest(payload.encode())),
            )

    def _contract(self, task, execution):
        if execution != _digest(_json(task).encode()):
            raise NativeStoreError("Worker execution contract mismatch")
        with self.store._connection() as db:
            for module in task["selected"]:
                self.intake._allow(db, task["tenant"], task["producer"], module, "read")
            for module in task["writes"]:
                self.intake._allow(db, task["tenant"], task["producer"], module, "receive")

    def _origin(self, task, execution):
        return {
            "source_ref": "native-source:" + _digest(_json(task["source"]).encode()),
            "worker_ref": "native-worker:" + execution,
            "issue_url": "native://" + task["tenant"] + "/issues/" + task["issue"],
        }

    def _terminal(self, task, execution, terminal):
        with self.store._connection(write=True) as db:
            for module in task["selected"]:
                self.intake._allow(db, task["tenant"], task["producer"], module, "read")
            for module in task["writes"]:
                self.intake._allow(db, task["tenant"], task["producer"], module, "receive")
            db.execute(
                "INSERT OR IGNORE INTO native_worker_terminals_v2 VALUES (?,?,?)",
                (execution, _json(task), _json(terminal)),
            )
            row = db.execute(
                "SELECT task,terminal FROM native_worker_terminals_v2 WHERE execution=?", (execution,)
            ).fetchone()
            if row["task"] != _json(task) or row["terminal"] != _json(terminal):
                raise NativeStoreError("Worker terminal integrity failure")
        return terminal

    def process_closed(self, task, execution):
        """Trusted coordinator-only physical observation; grants no content access.

        Caller must authorize its own coordination role before using this port.
        Producer withdrawal does not erase authentic historical process closure.
        """
        if execution != _digest(_json(task).encode()):
            raise NativeStoreError("Worker execution contract mismatch")
        with self.store._connection() as db:
            row = db.execute("SELECT * FROM native_worker_process_closures WHERE execution=?", (execution,)).fetchone()
            spool = db.execute("SELECT * FROM native_worker_closed WHERE execution=?", (execution,)).fetchone()
        self._history(task, row, spool)
        return row is not None

    def _history(self, task, physical, closed):
        records = []
        for record in (physical, closed):
            if record is None:
                records.append(None)
                continue
            if record["task"] != _json(task) or record["digest"] != _digest(record["payload"].encode()):
                raise NativeStoreError("Worker closure integrity failure")
            try:
                records.append(json.loads(record["payload"]))
            except (ValueError, TypeError) as exc:
                raise NativeStoreError("Worker closure integrity failure") from exc
        process, output = records
        if physical is not None and (
            not isinstance(process, dict)
            or set(process) != {"exit_code", "reasons", "transcript"}
            or (process["exit_code"] is not None and type(process["exit_code"]) is not int)
            or not isinstance(process["reasons"], list)
            or not all(isinstance(reason, str) for reason in process["reasons"])
            or not isinstance(process["transcript"], str)
            or len(process["transcript"]) != 64
        ):
            raise NativeStoreError("Worker physical closure integrity failure")
        if closed is not None and (
            process is None
            or not isinstance(output, dict)
            or set(output)
            not in (
                {"changes", "exit_code", "transcript"},
                {"changes", "exit_code", "transcript", "cancelled"},
            )
            or type(output.get("cancelled", False)) is not bool
            or not isinstance(output["changes"], list)
            or (output["exit_code"] is not None and type(output["exit_code"]) is not int)
            or output["exit_code"] != process["exit_code"]
            or output["transcript"] != process["transcript"]
            or (
                (output.get("cancelled", False) or process["exit_code"] != 0 or process["reasons"])
                and output["changes"]
            )
        ):
            raise NativeStoreError("Worker output closure integrity failure")
        return process, output

    def reconcile(self, task, execution):
        """Replay only host-owned closed output; a live/unknown process stays unknown."""
        task = json.loads(_json(task))
        self._contract(task, execution)
        with self.store._connection() as db:
            row = db.execute(
                "SELECT task,terminal FROM native_worker_terminals_v2 WHERE execution=?", (execution,)
            ).fetchone()
            closed = db.execute("SELECT * FROM native_worker_closed WHERE execution=?", (execution,)).fetchone()
            physical = db.execute(
                "SELECT * FROM native_worker_process_closures WHERE execution=?", (execution,)
            ).fetchone()
        if row is not None and row["task"] != _json(task):
            raise NativeStoreError("Worker terminal contract mismatch")
        process, payload = self._history(task, physical, closed)
        if process is None:
            if row is not None:
                raise NativeStoreError("Missing owned process closure")
            return None
        if process["exit_code"] != 0 or process["reasons"] or (payload and payload.get("cancelled", False)):
            # Reconstruct, including all fields, then compare with the saved terminal.
            # An arbitrary terminal row can never establish a process outcome.
            return self._terminal(task, execution, {"state": "failed", **process})
        if payload is None:
            if row is not None:
                raise NativeStoreError("Missing owned output closure")
            return None
        changes = [
            {**c, "edits": {n: None if b is None else bytes.fromhex(b) for n, b in c["edits"].items()}}
            for c in payload["changes"]
        ]
        revisions = dict(task["selected"])
        receipt = None
        origin = self._origin(task, execution)
        if changes:
            receipt = self.intake.receive(task["tenant"], task["producer"], "worker-" + execution, changes, origin)
            revisions.update(receipt["revisions"])
        terminal = {
            "state": "produced",
            "exit_code": payload["exit_code"],
            "transcript": payload["transcript"],
            "candidate": self.store.compose(task["tenant"], revisions)["id"],
            "modules": revisions,
            "intake": receipt,
            "origin": origin,
            "no_changes": not changes,
            "usage": None,
            "provider_model": None,
        }
        return self._terminal(task, execution, terminal)
