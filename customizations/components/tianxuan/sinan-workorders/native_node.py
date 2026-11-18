"""Outbound node using independent content cache and durable execution journal.

Installed producer shares this OS identity and must be trusted. The journal and
token must never be supplied as model context. Unknown intent is never relaunched.
"""

from __future__ import annotations

import json
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "duobao"))
from native_store import NativeStoreError, _digest, _json


class NativeNode:
    def __init__(self, worker, url, token, *, capacity=1, disk_bytes=268435456):
        if not url.startswith("https://") and not url.startswith("http://127.0.0.1:"):
            raise NativeStoreError("Verified HTTPS required outside loopback")
        self.worker, self.url, self.token = worker, url.rstrip("/"), token
        self.disk_bytes = disk_bytes
        self.pool = ThreadPoolExecutor(capacity)
        self.active = {}
        self.capacity = capacity
        self.futures = []
        self.pending = set()
        with worker.store._connection(write=True) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_node_intents(execution TEXT PRIMARY KEY,task TEXT NOT NULL,state TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_node_cursor(id INTEGER PRIMARY KEY CHECK(id=1),cursor INTEGER NOT NULL)"
            )
            db.execute("INSERT OR IGNORE INTO native_node_cursor VALUES(1,0)")
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_node_received(execution TEXT PRIMARY KEY,cancelled INTEGER NOT NULL DEFAULT 0)"
            )

    def request(self, path, value=None, *, binary=False):
        data = None if value is None else _json(value).encode()
        request = urllib.request.Request(
            self.url + "/native-nodes" + path,
            data=data,
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=35) as response:
            content = response.read(9 * 1024 * 1024 + 1)
        if len(content) > 9 * 1024 * 1024:
            raise NativeStoreError("Response quota")
        return content if binary else json.loads(content)

    def prepare(self, execution):
        manifest = self.request("/execution/" + execution)
        if manifest["package"] != _digest(Path(__file__).read_bytes()):
            raise NativeStoreError("Node package differs from admitted package")
        if manifest["execution"] != execution:
            raise NativeStoreError("Exact assignment digest mismatch")
        if manifest.get("cancelled"):
            return None, True
        task = manifest["task"]
        if manifest["execution"] != execution or _digest(_json(task).encode()) != execution:
            raise NativeStoreError("Exact assignment digest mismatch")
        if self.worker.installation(task["profile"]) != task["installation"]:
            raise NativeStoreError("Local installation differs from admitted installation")
        if manifest.get("cancelled"):
            return task, True
        if sum(p.stat().st_size for p in self.worker.root.rglob("*") if p.is_file()) > self.disk_bytes:
            raise NativeStoreError("Node disk quota")
        tenant = task["tenant"]
        for module, state in manifest["states"].items():
            encoded = _json(state)
            revision = manifest["revisions"][module]
            if _digest(encoded.encode()) != revision:
                raise NativeStoreError("Revision digest mismatch")
            for digest in state["objects"].values():
                with self.worker.store._connection() as db:
                    exists = db.execute(
                        "SELECT content FROM native_blobs WHERE tenant=? AND digest=?", (tenant, digest)
                    ).fetchone()
                if exists and _digest(bytes(exists["content"])) == digest:
                    continue
                blob = self.request("/execution/" + execution + "/blob/" + digest, binary=True)
                if _digest(blob) != digest or len(blob) > self.worker.workspace.limits.file_bytes:
                    raise NativeStoreError("Blob integrity/quota failure")
                with self.worker.store._connection(write=True) as db:
                    used = db.execute("SELECT COALESCE(sum(length(content)),0) FROM native_blobs").fetchone()[0]
                    if used + len(blob) > self.disk_bytes:
                        raise NativeStoreError("Node cache quota")
                    db.execute("INSERT OR REPLACE INTO native_blobs VALUES(?,?,?)", (tenant, digest, blob))
            with self.worker.store._connection(write=True) as db:
                db.execute(
                    "INSERT OR IGNORE INTO native_revisions VALUES(?,?,?,?)", (tenant, revision, module, encoded)
                )
        self.worker.workspace.sources(tenant, task["selected"])
        return task, False

    def send_closed(self, execution):
        with self.worker.store._connection() as db:
            physical = db.execute(
                "SELECT * FROM native_worker_process_closures WHERE execution=?", (execution,)
            ).fetchone()
            output = db.execute("SELECT * FROM native_worker_closed WHERE execution=?", (execution,)).fetchone()
        if physical is None:
            return False
        task = json.loads(physical["task"])
        if _digest(_json(task).encode()) != execution:
            raise NativeStoreError("Journal task digest mismatch")
        self.worker._history(task, physical, output)
        self.request(
            "/execution/" + execution + "/receipt",
            {
                "execution": execution,
                "physical": json.loads(physical["payload"]),
                "output": None if output is None else json.loads(output["payload"]),
            },
        )
        with self.worker.store._connection(write=True) as db:
            db.execute("UPDATE native_node_intents SET state='acknowledged' WHERE execution=?", (execution,))
        return True

    def execute(self, execution, cancel):
        try:
            with self.worker.store._connection() as db:
                intent = db.execute("SELECT * FROM native_node_intents WHERE execution=?", (execution,)).fetchone()
            if intent is not None:
                self.send_closed(execution)  # Unknown stays owned, never execute again.
                return
            task, cancelled = self.prepare(execution)
            if task is None:
                self.withdraw(execution)
                return
            no_launch = cancelled or cancel.is_set()
            with self.worker.store._connection(write=True) as db:
                db.execute("INSERT INTO native_node_intents VALUES(?,?,'intent')", (execution, _json(task)))
                if no_launch:
                    transcript = _digest(b"")
                    for table, payload in (
                        (
                            "native_worker_process_closures",
                            {"exit_code": None, "reasons": ["cancelled-before-launch"], "transcript": transcript},
                        ),
                        (
                            "native_worker_closed",
                            {"changes": [], "exit_code": None, "transcript": transcript, "cancelled": True},
                        ),
                    ):
                        encoded = _json(payload)
                        db.execute(
                            f"INSERT INTO {table} VALUES(?,?,?,?)",
                            (execution, _json(task), encoded, _digest(encoded.encode())),
                        )
            if no_launch:
                self.send_closed(execution)
                return
            try:
                self.worker.run(task, execution, cancel)
            finally:
                self.send_closed(execution)
        finally:
            self.active.pop(execution, None)

    def withdraw(self, execution):
        # Only absence of durable launch intent proves this node never launched.
        # Unknown intents retain ownership; real closures replay their own bytes.
        with self.worker.store._connection() as db:
            intent = db.execute("SELECT 1 FROM native_node_intents WHERE execution=?", (execution,)).fetchone()
        if intent:
            self.send_closed(execution)
            return
        self.request(
            "/execution/" + execution + "/receipt",
            {
                "execution": execution,
                "physical": {"exit_code": None, "reasons": ["cancelled-before-launch"], "transcript": _digest(b"")},
                "output": None,
            },
        )
        with self.worker.store._connection(write=True) as db:
            db.execute("UPDATE native_node_received SET cancelled=2 WHERE execution=?", (execution,))

    def schedule(self, execution, cancelled=False):
        if execution in self.active:
            return True
        if len(self.active) >= self.capacity:
            return False
        cancel = threading.Event()
        if cancelled:
            cancel.set()
        self.active[execution] = cancel
        self.futures.append(self.pool.submit(self.execute, execution, cancel))
        return True

    def step(self):
        for future in list(self.futures):
            if future.done():
                self.futures.remove(future)
                future.result()
        self.resume_pending()
        with self.worker.store._connection() as db:
            cursor = db.execute("SELECT cursor FROM native_node_cursor WHERE id=1").fetchone()[0]
        for event in self.request("/events?cursor=" + str(cursor)):
            execution = event["execution"]
            if event["kind"] in {"cancel", "withdraw"}:
                with self.worker.store._connection(write=True) as db:
                    db.execute(
                        "UPDATE native_node_received SET cancelled=1 WHERE execution=? AND cancelled!=2", (execution,)
                    )
                if execution in self.active:
                    self.active[execution].set()
                elif event["kind"] == "withdraw":
                    self.withdraw(execution)
            elif execution not in self.active:
                if len(self.active) >= self.capacity:
                    return  # Cursor remains pending; no unbounded executor queue.
                with self.worker.store._connection(write=True) as db:
                    db.execute("INSERT OR IGNORE INTO native_node_received(execution) VALUES(?)", (execution,))
                self.schedule(execution)
            with self.worker.store._connection(write=True) as db:
                db.execute("UPDATE native_node_cursor SET cursor=? WHERE id=1", (event["cursor"],))

    def recover(self):
        # Startup only, not an idle scan. Receipt loss is retried, execution isn't.
        with self.worker.store._connection() as db:
            pending = list(
                db.execute(
                    "SELECT r.execution,r.cancelled FROM native_node_received r LEFT JOIN native_node_intents i ON r.execution=i.execution WHERE r.cancelled!=2 AND (i.state IS NULL OR i.state!='acknowledged')"
                )
            )
        self.pending.update(execution for execution, _ in pending if execution not in self.active)
        self.resume_pending()

    def resume_pending(self):
        for execution in list(self.pending):
            with self.worker.store._connection() as db:
                cancelled = db.execute(
                    "SELECT cancelled FROM native_node_received WHERE execution=?", (execution,)
                ).fetchone()[0]
            if cancelled == 2:
                self.pending.remove(execution)
            elif self.schedule(execution, cancelled):
                self.pending.remove(execution)
            else:
                break

    def serve(self):
        reconnect = True
        while True:
            try:
                if reconnect:
                    self.recover()
                    reconnect = False
                self.step()
            except urllib.error.HTTPError as error:
                if error.code not in {429, 500, 502, 503, 504}:
                    raise
                reconnect = True
                time.sleep(1)  # Transport failure backoff, never an idle task scan.
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                reconnect = True
                time.sleep(1)


def main():
    import argparse

    from native_store import NativeStore
    from native_worker import NativeWorker
    from native_workspace import Limits

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--once", action="store_true", help="Consume one event batch; validation only")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    worker = NativeWorker(
        NativeStore(Path(config["database"])),
        Path(config["root"]),
        config["profiles"],
        lambda *a: True,
        process_helper_path=config.get("process_helper"),
        authorize=lambda *a: True,
        limits=Limits(file_bytes=1048576, total_bytes=4194304, files=1000),
    )
    node = NativeNode(
        worker, config["server"], Path(config["token_file"]).read_text().strip(), capacity=config.get("capacity", 1)
    )
    if args.once:
        node.recover()
        node.step()
        node.pool.shutdown(wait=True)
        for future in node.futures:
            future.result()
    else:
        node.serve()


if __name__ == "__main__":
    main()
