"""Single coordinator, trusted enrolled nodes; no producer credentials on server.

The host must exclusively own the domain database and this adapter. Ordinary
same-user producers are trusted installed code, not hostile sandbox tenants.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import os
import threading
import time
from pathlib import Path

from native_candidates import NativeCandidates
from native_store import NativeStoreError, _digest, _json
from native_worker import OBSERVATION_PROTOCOL, NativeWorker
from native_workspace import Limits, NativeWorkspace, absolute
from tianxuan_core import PermissionDenied


class RemoteNativeWorker(NativeWorker):
    def __init__(self, store, root, profiles, *, authorize, nodes, single_coordinator=False):
        if single_coordinator is not True:
            raise NativeStoreError("Remote transport requires exclusive single coordinator")
        self.store, self.root = store, absolute(root, missing=True)
        self.root.mkdir(exist_ok=True)
        self.profiles = json.loads(_json(profiles))
        self.nodes = json.loads(_json(nodes))  # Trusted installer input, never HTTP enrollment.
        self.workspace = NativeWorkspace(store, Limits(file_bytes=1048576, total_bytes=4194304, files=1000))
        self.intake = NativeCandidates(store, authorize, self.workspace.limits)
        self.condition = threading.Condition()
        self.workflow = None
        for profile in self.profiles.values():
            if (
                set(profile) - {"observation_protocol"} != {"timeout", "installation"}
                or ("observation_protocol" in profile and profile["observation_protocol"] != OBSERVATION_PROTOCOL)
                or not 0 < profile["timeout"] <= 86400
            ):
                raise NativeStoreError("Public profile descriptor required")
        for node in self.nodes.values():
            if set(node) != {"tenant", "token_sha256", "profiles", "capacity", "enabled", "package"}:
                raise NativeStoreError("Invalid installed node")
            if type(node["capacity"]) is not int or not 1 <= node["capacity"] <= 16:
                raise NativeStoreError("Invalid node capacity")
        with store._connection(write=True) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_worker_terminals_v2 (execution TEXT PRIMARY KEY, task TEXT NOT NULL, terminal TEXT NOT NULL)"
            )
            for table in ("native_worker_closed", "native_worker_process_closures"):
                db.execute(
                    f"CREATE TABLE IF NOT EXISTS {table} (execution TEXT PRIMARY KEY, task TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL)"
                )

    def bind(self, workflow):
        database = workflow.domain.db.execute("PRAGMA database_list").fetchone()[2]
        if not database:
            raise NativeStoreError("Durable domain database required")
        self.owner = Path(database + ".remote-owner").open("a+b")
        try:
            self.owner.seek(0)
            if not self.owner.read(1):
                self.owner.write(b"1")
                self.owner.flush()
            self.owner.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.owner.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self.owner.close()
            raise NativeStoreError("Another remote coordinator owns this domain database") from error
        self.workflow = workflow
        with workflow._transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_remote_assignments (execution TEXT PRIMARY KEY,node TEXT NOT NULL,package TEXT NOT NULL,task TEXT NOT NULL,cancelled INTEGER NOT NULL DEFAULT 0,closed INTEGER NOT NULL DEFAULT 0)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_remote_events (cursor INTEGER PRIMARY KEY AUTOINCREMENT,node TEXT NOT NULL,execution TEXT NOT NULL,kind TEXT NOT NULL)"
            )

    def close(self):
        self.owner.close()

    def installation(self, profile):
        return self.profiles[profile]["installation"]

    def _contract(self, task, execution):
        super()._contract(task, execution)
        with self.workflow.domain._connection_lock:
            try:
                self.workflow._valid(task["actor"], self.workflow._row(self.workflow.domain.db, execution))
            except PermissionDenied as error:
                raise NativeStoreError("Current task authority rejected") from error
            row = self.workflow.domain.db.execute(
                "SELECT cancelled FROM native_remote_assignments WHERE execution=?", (execution,)
            ).fetchone()
            if row is not None and row[0]:
                raise NativeStoreError("Cancelled remote content is not admissible")

    def authenticate(self, token):
        digest = _digest(token.encode())
        for name, spec in self.nodes.items():
            if spec["enabled"] and hmac.compare_digest(spec["token_sha256"], digest):
                return name
        raise NativeStoreError("Node authentication rejected")

    def reserve(self, db, task, execution):
        # Called inside the SAME transaction as global capacity and FIFO checks.
        name = self.available_node(db, task)
        if name is None:
            return False
        db.execute(
            "INSERT INTO native_remote_assignments(execution,node,package,task) VALUES (?,?,?,?)",
            (execution, name, self.nodes[name]["package"], _json(task)),
        )
        db.execute("INSERT INTO native_remote_events(node,execution,kind) VALUES (?,?,'offer')", (name, execution))
        return True

    def available_node(self, db, task):
        if db.execute("SELECT count(*) FROM native_remote_assignments").fetchone()[0] >= 4096:
            raise NativeStoreError("Remote ledger quota; archive acknowledged records before new admission")
        for name, node in sorted(self.nodes.items()):
            if not node["enabled"] or node["tenant"] != task["tenant"]:
                continue
            if node["profiles"].get(task["profile"]) != task["installation"]:
                continue
            held = db.execute(
                "SELECT count(*) FROM native_remote_assignments WHERE node=? AND closed=0", (name,)
            ).fetchone()[0]
            if held >= node["capacity"]:
                continue
            return name
        return None

    def _assignment(self, node, execution, *, content=False):
        with self.workflow._transaction() as db:
            row = db.execute(
                "SELECT * FROM native_remote_assignments WHERE execution=? AND node=?", (execution, node)
            ).fetchone()
            if row is None or not self.nodes[node]["enabled"]:
                raise NativeStoreError("Assignment unavailable")
            task = json.loads(row["task"])
            spec = self.nodes[node]
            if (
                task["tenant"] != spec["tenant"]
                or spec["profiles"].get(task["profile"]) != task["installation"]
                or spec["package"] != row["package"]
            ):
                raise NativeStoreError("Current node installation rejected")
            if content:
                self.workflow._valid(task["actor"], self.workflow._row(db, execution))
                self._contract(task, execution)
            return dict(row), task

    def run(self, task, execution, cancel=None):
        with self.condition:
            with self.workflow._transaction() as db:
                row = db.execute(
                    "SELECT node,task FROM native_remote_assignments WHERE execution=?", (execution,)
                ).fetchone()
                if row is None or row["task"] != _json(task):
                    raise NativeStoreError("Missing atomic remote reservation")
                if (
                    db.execute(
                        "SELECT 1 FROM native_remote_events WHERE execution=? AND kind='offer'", (execution,)
                    ).fetchone()
                    is None
                ):
                    db.execute(
                        "INSERT INTO native_remote_events(node,execution,kind) VALUES (?,?,'offer')",
                        (row["node"], execution),
                    )
            self.condition.notify_all()
        # execute returns promptly; receipt commit is the durable completion event.
        return None

    def cancel(self, execution):
        with self.condition:
            with self.workflow._transaction() as db:
                row = db.execute(
                    "SELECT node,cancelled FROM native_remote_assignments WHERE execution=?", (execution,)
                ).fetchone()
                if row is None:
                    raise NativeStoreError("Assignment unavailable")
                if row["cancelled"]:
                    return
                db.execute("UPDATE native_remote_assignments SET cancelled=1 WHERE execution=?", (execution,))
                db.execute(
                    "INSERT INTO native_remote_events(node,execution,kind) VALUES (?,?,'cancel')",
                    (row["node"], execution),
                )
            self.condition.notify_all()

    def events(self, token, cursor, timeout=25):
        if type(cursor) is not int or cursor < 0:
            raise NativeStoreError("Invalid cursor")
        # Read/register/read is serialized with commit + notify, including empty reads.
        with self.condition:
            node = self.authenticate(token)

            def read():
                self.authenticate(token)  # Revocation is checked again after wait.
                with self.workflow._transaction() as db:
                    return [
                        dict(r)
                        for r in db.execute(
                            "SELECT * FROM native_remote_events WHERE node=? AND cursor>? ORDER BY cursor LIMIT 16",
                            (node, cursor),
                        )
                    ]

            rows = read()
            if not rows:
                self.condition.wait(min(timeout, 25))
                rows = read()
            for row in rows:
                assignment, _ = self._assignment(node, row["execution"])
                if row["kind"] == "offer" and not assignment["cancelled"]:
                    try:
                        self._assignment(node, row["execution"], content=True)
                    except (PermissionDenied, NativeStoreError):
                        self.cancel(row["execution"])
                        row["kind"] = "withdraw"
                elif row["kind"] == "offer":
                    row["kind"] = "withdraw"
            return rows

    def manifest(self, node, execution):
        row, task = self._assignment(node, execution)
        if not row["cancelled"]:
            try:
                self._assignment(node, execution, content=True)
            except (PermissionDenied, NativeStoreError):
                self.cancel(execution)
                row["cancelled"] = True
        if row["cancelled"]:
            return {"execution": execution, "cancelled": True, "package": self.nodes[node]["package"]}
        revisions, states = self.workspace.sources(task["tenant"], task["selected"])
        return {
            "task": task,
            "execution": execution,
            "revisions": revisions,
            "states": states,
            "package": self.nodes[node]["package"],
        }

    def blob(self, node, execution, digest):
        _, task = self._assignment(node, execution, content=True)
        _, states = self.workspace.sources(task["tenant"], task["selected"])
        for module, state in states.items():
            for name, value in state["objects"].items():
                if value == digest:
                    return self.store.read(task["tenant"], module, task["selected"][module], name)
        raise NativeStoreError("Blob outside assignment")

    def receipt(self, node, execution, receipt):
        row, task = self._assignment(node, execution)
        if set(receipt) != {"execution", "physical", "output"} or receipt["execution"] != execution:
            raise NativeStoreError("Typed closure receipt required")
        records = []
        for payload in (receipt["physical"], receipt["output"]):
            if payload is None:
                records.append(None)
                continue
            encoded = _json(payload)
            records.append({"task": _json(task), "payload": encoded, "digest": _digest(encoded.encode())})
        self._history(task, *records)
        if records[0] is None:
            raise NativeStoreError("Physical closure required")
        output = receipt["output"]
        changes = [] if output is None else output["changes"]
        size = count = 0
        for change in changes:
            if change["base"] != task["selected"].get(change["module"]) or change["module"] not in task["writes"]:
                raise NativeStoreError("Output outside mandate")
            for name, value in change["edits"].items():
                allowed = task["writes"][change["module"]]
                if allowed != "*" and name not in allowed:
                    raise NativeStoreError("Output outside mandate")
                data = b"" if value is None else bytes.fromhex(value)
                size += len(data)
                count += 1
                if len(data) > self.workspace.limits.file_bytes:
                    raise NativeStoreError("Output file quota")
        if size > self.workspace.limits.total_bytes or count > self.workspace.limits.files:
            raise NativeStoreError("Output quota")
        with self.condition:
            with self.store._connection(write=True) as db:
                for table, record in zip(("native_worker_process_closures", "native_worker_closed"), records):
                    if record is None:
                        continue
                    old = db.execute(f"SELECT * FROM {table} WHERE execution=?", (execution,)).fetchone()
                    if old and any(old[k] != record[k] for k in record):
                        raise NativeStoreError("Conflicting receipt replay")
                    db.execute(
                        f"INSERT OR IGNORE INTO {table} VALUES (?,?,?,?)",
                        (execution, record["task"], record["payload"], record["digest"]),
                    )
            with self.workflow._transaction() as db:
                db.execute("UPDATE native_remote_assignments SET closed=1 WHERE execution=?", (execution,))
                db.execute("UPDATE native_tasks SET state='running' WHERE id=? AND state='reserved'", (execution,))
            self.condition.notify_all()
        # Intake has its own immutable replay key. A crash here resumes on replay.
        try:
            result = self.workflow.reconcile(task["actor"], execution)
            state = result["state"]
        except PermissionDenied:
            state = self.workflow._settle_physical(self, execution)
        return {"execution": execution, "physical_closed": True, "state": state}

    async def wait_terminal(self, actor, execution):
        def wait():
            deadline = time.monotonic() + 25
            with self.condition:
                row = self.workflow.status(actor, execution)
                task = json.loads(row["task"])
                while not self.process_closed(task, execution):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise NativeStoreError("Remote terminal pending; ownership retained")
                    self.condition.wait(remaining)
            return self.workflow.reconcile(actor, execution)

        return await asyncio.to_thread(wait)
