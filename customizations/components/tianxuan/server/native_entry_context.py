"""Pinned installer policy and live execution-bound context service."""

import hashlib
import hmac
import json
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path

from native_context import NativeContext
from native_installation import require
from native_store import _digest, _json


class ContextAdmissionBusy(ValueError):
    """No operation has started; bounded service capacity is temporarily occupied."""


class RequestAdmission:
    """One HTTP receipt deadline; cancellation only prevents unstarted work."""

    def __init__(self, deadline):
        self.deadline = deadline
        self.cancelled = threading.Event()
        self.started = False
        self.lock = threading.Lock()

    def check(self):
        with self.lock:
            self._check()

    def _check(self):
        if self.cancelled.is_set() or time.monotonic() >= self.deadline:
            raise ContextAdmissionBusy("Context request expired before execution")

    def begin(self):
        with self.lock:
            self._check()
            self.started = True

    def abort(self):
        with self.lock:
            if self.started:
                return False
            self.cancelled.set()
            return True


class RuntimeInstallation:
    def __init__(self, path, sha256):
        self.path = Path(path)
        require(self.path.is_absolute() and not self.path.is_symlink(), "Absolute runtime installation required")
        self.sha256 = sha256
        spec = self.verify()
        require(
            set(spec) == {"version", "installation", "remote", "context"} and spec["version"] == 1,
            "Closed runtime installation required",
        )
        context = spec["context"]
        require(set(context) == {"local_token_sha256", "full_bytes", "limits"}, "Closed context policy required")
        require(
            type(context["full_bytes"]) is int and 0 <= context["full_bytes"] <= 60000,
            "Bounded full-context threshold required",
        )

    def verify(self):
        raw = self.path.read_bytes()
        require(
            not self.path.is_symlink() and hashlib.sha256(raw).hexdigest() == self.sha256,
            "Runtime installation changed",
        )
        return json.loads(raw)


class EntryContexts:
    def __init__(self, entry, installation):
        self.entry, self.installation = entry, installation
        self.root = entry.root / "contexts"
        self.root.mkdir(exist_ok=True)
        # Bounds count retained metadata, not RSS. Storage retains no blob bodies.
        self.capacity = 16
        self.max_waiters = 32
        self.wait_seconds = 30
        self._condition = threading.Condition()
        self._contexts = OrderedDict()
        self._waiters = 0

    @contextmanager
    def _lease(self, execution, guard=None):
        deadline = time.monotonic() + self.wait_seconds
        with self._condition:
            if self._waiters >= self.max_waiters:
                raise ContextAdmissionBusy("Context admission wait budget exceeded")
            self._waiters += 1
            try:
                while True:
                    if guard is not None:
                        # Never hold the lease lock while consulting live authority.
                        self._condition.release()
                        try:
                            guard()
                        finally:
                            self._condition.acquire()
                    slot = self._contexts.get(execution)
                    if slot is not None and not slot["busy"]:
                        break
                    if slot is None:
                        if len(self._contexts) >= self.capacity:
                            idle = next((k for k, v in self._contexts.items() if not v["busy"]), None)
                            if idle is not None:
                                del self._contexts[idle]  # Never delete durable ledger/worker state.
                        if len(self._contexts) < self.capacity:
                            slot = {"busy": False, "context": None}
                            self._contexts[execution] = slot
                            break
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ContextAdmissionBusy("Context admission timed out before execution")
                    self._condition.wait(min(remaining, 0.05))
                slot["busy"] = True
                self._contexts.move_to_end(execution)
            finally:
                self._waiters -= 1
        try:
            yield slot
        finally:
            with self._condition:
                slot["busy"] = False
                self._condition.notify_all()

    def context(self, execution, token=None, existing=None):
        with self.entry.domain._connection_lock:
            binding, authorize = self._authority(execution, token)
        if existing is not None:
            require(existing.binding == binding, "Original context binding changed")
            existing.authorize = authorize
            return existing
        return NativeContext(self.entry.native, authorize, binding, self.root / (execution + ".sqlite"))

    def _authority(self, execution, token):
        e = self.entry
        spec = self.installation.verify()
        require(spec["installation"] == e.installation.sha256, "Runtime belongs to another installation")
        e.installation.verify()
        row = e.workflow._row(e.domain.db, execution)
        task = json.loads(row["task"])
        require(_digest(_json(task).encode()) == execution, "Exact context execution required")
        require(row["state"] in {"reserved", "running", "produced", "accepted"}, "Context task is not live")
        e.workflow._valid(task["actor"], row)
        e.entry_authority(task["mandate"])
        worker = e.workflow.worker
        if spec["remote"] is not None:
            if token is not None:
                node = worker.authenticate(token)
            else:
                assignment = e.domain.db.execute(
                    "SELECT node FROM native_remote_assignments WHERE execution=?", (execution,)
                ).fetchone()
                require(assignment is not None, "Context assignment missing")
                node = assignment[0]
            worker._assignment(node, execution, content=True)
        elif token is not None:
            require(
                hmac.compare_digest(_digest(token.encode()), spec["context"]["local_token_sha256"]),
                "Local context authentication rejected",
            )
        binding = dict(
            execution=execution,
            tenant=task["tenant"],
            actor=task["actor"],
            producer=task["producer"],
            source_digest=_digest(_json(task["source"]).encode()),
            installation_digest=task["installation"],
            selected=task["selected"],
            limits=spec["context"]["limits"],
        )

        def authorize(bound, module, revision, operation):
            # Live authority is never cached with immutable source metadata.
            with e.domain._connection_lock:
                self.installation.verify()
                e.installation.verify()
                current = e.workflow._row(e.domain.db, execution)
                require(current["task"] == row["task"], "Original context task changed")
                require(current["state"] in {"reserved", "running", "produced", "accepted"}, "Context task is not live")
                e.entry_authority(task["mandate"])
                e.workflow._valid(task["actor"], current)
                if spec["remote"] is not None:
                    if token is not None:
                        require(worker.authenticate(token) == node, "Context node changed")
                    worker._assignment(node, execution, content=True)
                require(bound == binding and binding["selected"].get(module) == revision, "Context revision changed")
                marker = e.current_entry.set(task["mandate"])
                try:
                    with e.native._connection() as db:
                        return e.module_authority(db, task["tenant"], task["producer"], module, "read") is True
                finally:
                    e.current_entry.reset(marker)

        return binding, authorize

    def _open(self, execution):
        with self.entry.native._connection() as db:
            require(
                db.execute("SELECT 1 FROM native_worker_process_closures WHERE execution=?", (execution,)).fetchone()
                is None,
                "Physically closed context cannot accept further operations",
            )

    def call(self, execution, token, method, args, admission=None):
        def guard():
            if admission is not None:
                admission.check()
            with self.entry.domain._connection_lock:
                self._authority(execution, token)

        guard()
        with self._lease(execution, guard) as slot:
            c = self.context(execution, token, slot["context"])
            slot["context"] = c
            self._open(execution)
            c.check("rpc")
            require(isinstance(args, list), "Context argument list required")
            require(method in {"binding", "check", "resolve", "delivery", "emit", "events"}, "Context operation denied")
            if admission is not None:
                admission.check()
            if method == "binding":
                if admission is not None:
                    admission.begin()
                require(not args, "Binding takes no arguments")
                value = {"binding": c.binding, "full_bytes": self.installation.verify()["context"]["full_bytes"]}
                c.check("rpc_completed")
                self._open(execution)
                return value
            if method == "emit":
                require(
                    len(args) == 2
                    and args[0]
                    in {"model_receipt", "unknown", "model_unknown", "model_process_closed", "model_call_start"},
                    "Host closure cannot be supplied by producer",
                )
            c.ledger_budget(262144 if method == "events" else 8388608)
            if admission is not None:
                admission.check()
                admission.begin()
            value = getattr(c, method)(*args)
            c.check("rpc_completed")
            self._open(execution)
            c.ledger_budget()
            if method == "resolve":
                self.entry.workflow._record_step(
                    execution,
                    "context." + args[0]["op"],
                    {"result_id": value["result_id"], "response_sha256": value["response_sha256"]},
                    "context:" + value["result_id"],
                )
            return value

    def receipt(self, task, execution):
        if not (self.root / (execution + ".sqlite")).exists():
            return None
        with self._lease(execution) as slot:
            c = self.context(execution, existing=slot["context"])
            slot["context"] = c
            if not c.events():
                return None
            with self.entry.native._connection() as db:
                physical = db.execute(
                    "SELECT * FROM native_worker_process_closures WHERE execution=?", (execution,)
                ).fetchone()
                output = db.execute("SELECT * FROM native_worker_closed WHERE execution=?", (execution,)).fetchone()
            require(physical is not None, "Physical context closure missing")
            self.entry.workflow.worker._history(task, physical, output)
            payload = json.loads(physical["payload"])
            events = c.events()
            if not events or events[-1]["kind"] != "process_closed":
                c.check("completion")
                c.emit("process_closed", {"exit_code": payload["exit_code"], "physical": True})
            return c.receipt()


def mount_entry_runtime(app, entry):
    import asyncio
    from contextlib import asynccontextmanager

    from fastapi import FastAPI, HTTPException, Request
    from native_node_api import mount_native_nodes
    from native_store import NativeStoreError
    from starlette.applications import Starlette
    from starlette.routing import Mount
    from tianxuan_core import PermissionDenied

    user_app = app
    if entry.runtime_installation.verify()["remote"] is not None:
        app = mount_native_nodes(app, entry.workflow.worker)
    rpc = FastAPI()

    # This bounds concurrent RPC residency, not the number of workflow tasks.
    # Admission precedes body collection and every executor submission.
    from concurrent.futures import ThreadPoolExecutor

    executor = ThreadPoolExecutor(max_workers=32, thread_name_prefix="native-context")
    occupied = 0

    @rpc.post("/{execution}")
    async def call(execution: str, request: Request):
        nonlocal occupied
        admission = RequestAdmission(time.monotonic() + entry.contexts.wait_seconds)
        if occupied >= 32:
            raise HTTPException(503, {"status": "not_started", "reason": "context_capacity"})
        occupied += 1
        future = None
        disconnect = None

        def released(done):
            nonlocal occupied
            occupied -= 1
            # Retrieve abandoned exceptions without treating an unknown as success.
            if done is not None and not done.cancelled():
                done.exception()

        async def read_body():
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > 262144:
                    raise HTTPException(413, "Context request budget exceeded")
                body.extend(chunk)
            return body

        try:
            auth = request.headers.get("authorization", "")
            if not auth.startswith("Bearer "):
                raise HTTPException(401, "Context bearer required")
            try:
                body = await asyncio.wait_for(read_body(), max(0.001, admission.deadline - time.monotonic()))
            except TimeoutError:
                raise ContextAdmissionBusy("Context body deadline exceeded") from None
            value = json.loads(body)
            del body
            require(set(value) == {"method", "args"}, "Closed context RPC required")
            admission.check()
            future = asyncio.get_running_loop().run_in_executor(
                executor, entry.contexts.call, execution, auth[7:], value["method"], value["args"], admission
            )
            # Shield the physical worker: cancellation must not release its slot.
            future.add_done_callback(released)

            async def watch_disconnect():
                while True:
                    message = await request.receive()
                    if message["type"] == "http.disconnect":
                        return

            disconnect = asyncio.create_task(watch_disconnect())
            while not future.done():
                await asyncio.wait({future, disconnect}, timeout=0.05)
                if (disconnect.done() or time.monotonic() >= admission.deadline) and admission.abort():
                    raise ContextAdmissionBusy("Context request expired before execution")
                if disconnect.done():
                    return await asyncio.shield(future)
            return future.result()
        except ContextAdmissionBusy:
            raise HTTPException(503, {"status": "not_started", "reason": "context_capacity"}) from None
        except (ValueError, TypeError, KeyError, NativeStoreError, PermissionDenied):
            raise HTTPException(409, "Context request rejected") from None
        finally:
            admission.abort()
            if disconnect is not None:
                disconnect.cancel()
            if future is None:
                released(None)

    @asynccontextmanager
    async def lifespan(application):
        try:
            async with user_app.router.lifespan_context(user_app):
                yield
        finally:
            # Join every dedicated worker, including cancelled HTTP handlers.
            executor.shutdown(wait=True, cancel_futures=False)

    return Starlette(routes=[Mount("/native-context", rpc), Mount("/", app)], lifespan=lifespan)
