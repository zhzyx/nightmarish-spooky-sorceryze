"""Durable entry intents and event-triggered supervision of the existing Sinan driver.

This ledger stores entry delivery only. Tasks, reservations, review and publication
remain owned by NativeWorkflow. A claimed external call without a receipt is held;
startup never replays it. The caller must own the domain transaction for enqueue.
"""

import asyncio
import contextvars
import json
import re
from contextlib import contextmanager
from datetime import datetime, timezone

from native_requirement_plan import requirement_digest
from native_store import NativeStoreError, _digest, _json
from native_workflow import OccupiedWrites
from tianxuan_core import _token_hash


def entry_key(tenant, actor, call_id):
    if not isinstance(call_id, str) or not 1 <= len(call_id) <= 128:
        raise NativeStoreError("Bounded idempotency key required")
    return _digest(_json([tenant, actor, call_id]).encode())


def workspace_approval(domain, actor, document):
    if not re.fullmatch(r"workspace-[0-9a-f]{64}", document.get("request_id") or ""):
        return None
    try:
        from workspace_conversations import require_workspace_approval
    except ModuleNotFoundError as error:
        if error.name != "workspace_conversations":
            raise
        raise NativeStoreError("Workspace approval reader is not installed") from None
    approval = require_workspace_approval(domain, actor, document["id"], document["version"])
    if not approval:
        raise NativeStoreError("Confirmed workspace design required")
    return approval


class EntryLedger:
    def __init__(self, domain):
        self.domain = domain
        with self.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_entry_intents ("
                "id TEXT PRIMARY KEY, tenant TEXT NOT NULL, actor TEXT NOT NULL, "
                "requirement TEXT NOT NULL, source TEXT NOT NULL, payload TEXT NOT NULL, "
                "state TEXT NOT NULL, receipt TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_entry_credentials ("
                "entry TEXT PRIMARY KEY, token_hash TEXT NOT NULL, access_key INTEGER NOT NULL)"
            )

    @contextmanager
    def transaction(self):
        with self.domain._connection_lock:
            db = self.domain.db
            if db.in_transaction:
                raise NativeStoreError("Entry transaction must be outermost")
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def enqueue(self, actor, requirement, call_id, choices, *, credential):
        """Call inside the transaction which creates/revises the requirement."""
        db = self.domain.db
        if not db.in_transaction:
            raise NativeStoreError("Entry enqueue requires the domain write transaction")
        self.domain._require_requirement(actor, requirement, write=True)
        document = self.domain.get_doc_shared(actor, requirement)
        tenant = self.domain.actor_context(actor)["tenant"]
        source = requirement_digest(document)
        key = entry_key(tenant, actor, call_id)
        if self.domain.user_for_token(credential) != actor:
            raise NativeStoreError("Current authenticated credential required")
        token_hash = _token_hash(credential)
        access_key = (
            db.execute("SELECT 1 FROM access_keys WHERE token_hash=? AND revoked_at IS NULL", (token_hash,)).fetchone()
            is not None
        )
        intent = dict(requirement=requirement, source=source, choices=choices)
        approval = workspace_approval(self.domain, actor, document)
        if approval is not None:
            intent["approval"] = approval
        payload = _json(intent)
        old = db.execute("SELECT * FROM native_entry_intents WHERE id=?", (key,)).fetchone()
        if old:
            if approval and "approval" not in json.loads(old["payload"]):
                raise NativeStoreError(
                    "Historical entry predates version approval; recover its status before a new call"
                )
            if old["payload"] != payload:
                raise NativeStoreError("Entry idempotency key rebound")
            self.authorize(key)
            return key
        db.execute(
            "INSERT INTO native_entry_intents VALUES (?,?,?,?,?,?, 'pending',NULL)",
            (key, tenant, actor, requirement, source, payload),
        )
        db.execute("INSERT INTO native_entry_credentials VALUES (?,?,?)", (key, token_hash, int(access_key)))
        # A new authorized increment extends the aggregate requirement, not the
        # immutable acceptance of earlier tasks. Do this in the enqueue transaction
        # so readers cannot see pending new work alongside a completed parent.
        parent = db.execute(
            "SELECT id,status FROM issues WHERE tenant_id=? AND requirement_id=? "
            "AND type='requirement' ORDER BY number LIMIT 1",
            (tenant, requirement),
        ).fetchone()
        if parent is not None and parent["status"] == "done":
            db.execute(
                "UPDATE issues SET status='in-progress',updated_at=? WHERE id=? AND status='done'",
                (datetime.now(timezone.utc).isoformat(), parent["id"]),
            )
            self.domain._event(
                tenant,
                "issue.transitioned",
                actor,
                parent["id"],
                {"from": "done", "to": "in-progress", "reason": "new_requirement_entry", "entry": key},
            )
        self.domain.sync_progress(requirement, actor=actor)
        return key

    def authorize(self, key):
        """Recheck the original irreversible credential reference, not actor alone."""
        with self.domain._connection_lock:
            row = self.domain.db.execute(
                "SELECT e.actor,e.requirement,c.token_hash,c.access_key,s.user_id,s.expires_at "
                "FROM native_entry_intents e JOIN native_entry_credentials c ON c.entry=e.id "
                "LEFT JOIN sessions s ON s.token_hash=c.token_hash WHERE e.id=?",
                (key,),
            ).fetchone()
            if row is None or row["user_id"] != row["actor"]:
                raise NativeStoreError("Entry credential withdrawn")
            expires = datetime.fromisoformat(row["expires_at"])
            if expires.tzinfo is None or expires <= datetime.now(timezone.utc):
                raise NativeStoreError("Entry credential expired")
            if (
                row["access_key"]
                and self.domain.db.execute(
                    "SELECT 1 FROM access_keys WHERE token_hash=? AND revoked_at IS NULL", (row["token_hash"],)
                ).fetchone()
                is None
            ):
                raise NativeStoreError("Entry access key withdrawn")
            self.domain._require_requirement(row["actor"], row["requirement"], write=True)
            intent = self.domain.db.execute(
                "SELECT source,payload FROM native_entry_intents WHERE id=?", (key,)
            ).fetchone()
            document = self.domain.get_doc_shared(row["actor"], row["requirement"])
            if requirement_digest(document) != intent["source"]:
                raise NativeStoreError("Entry source revision withdrawn")
            if workspace_approval(self.domain, row["actor"], document) != json.loads(intent["payload"]).get("approval"):
                raise NativeStoreError("Workspace approval changed")
            return True

    def pending(self, *, include_held=False):
        with self.transaction() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM native_entry_intents WHERE state IN ('pending','planned') OR (? AND state='held') ORDER BY rowid",
                    (int(include_held),),
                )
            ]

    def record_plan(self, key, receipt):
        """Persist proposal and Issue mapping in caller's domain transaction."""
        db = self.domain.db
        if not db.in_transaction:
            raise NativeStoreError("Planning receipt requires domain transaction")
        self.authorize(key)
        row = db.execute("SELECT state,receipt FROM native_entry_intents WHERE id=?", (key,)).fetchone()
        encoded = _json(receipt)
        if row is None or row["state"] not in {"held", "planned"}:
            raise NativeStoreError("Planning intent unavailable")
        if row["receipt"] is not None and row["receipt"] != encoded:
            raise NativeStoreError("Planning receipt cannot be rebound")
        db.execute("UPDATE native_entry_intents SET state='planned',receipt=? WHERE id=?", (encoded, key))

    def claim(self, key, *, recover=False):
        with self.transaction() as db:
            row = db.execute("SELECT * FROM native_entry_intents WHERE id=?", (key,)).fetchone()
            if row is None or row["state"] not in (
                {"pending", "planned", "held"} if recover else {"pending", "planned"}
            ):
                return None
            self.authorize(key)
            self.domain._require_requirement(row["actor"], row["requirement"], write=True)
            document = self.domain.get_doc_shared(row["actor"], row["requirement"])
            if requirement_digest(document) != row["source"]:
                raise NativeStoreError("Requirement changed; original intent cannot execute")
            if row["state"] == "pending":
                db.execute("UPDATE native_entry_intents SET state='held' WHERE id=?", (key,))
            return dict(row)

    def settle(self, key, receipt):
        with self.transaction() as db:
            row = db.execute("SELECT state,receipt FROM native_entry_intents WHERE id=?", (key,)).fetchone()
            if row is None or row["state"] not in {"held", "planned", "delivered"}:
                raise NativeStoreError("Entry is not claimed")
            encoded = _json(receipt)
            if row["state"] == "delivered" and row["receipt"] != encoded:
                raise NativeStoreError("Entry receipt cannot be rebound")
            db.execute("UPDATE native_entry_intents SET state='delivered',receipt=? WHERE id=?", (encoded, key))


class SinanProcess:
    """One finite driver with concurrent JSON-line RPC over inherited pipes.

    dispatch is the trusted actor-bound service adapter. Credentials and signer
    secrets never enter argv or the node environment. No HTTP listener is needed.
    """

    def __init__(self, argv, env, dispatch):
        self.argv, self.env, self.dispatch = tuple(argv), dict(env), dispatch
        self.process = None
        self.errors = []

    async def run(self):
        self.process = await asyncio.create_subprocess_exec(
            *self.argv,
            env=self.env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=8 * 1024 * 1024,
        )
        process = self.process
        write_lock = asyncio.Lock()
        result = None

        async def stderr():
            size = 0
            while chunk := await process.stderr.read(65536):
                size += len(chunk)
                if size > 900000:
                    raise NativeStoreError("Dispatcher stderr bound exceeded")

        async def reply(message):
            try:
                value = await self.dispatch(message["operation"], message["value"])
                answer = {"id": message["id"], "value": value}
            except Exception as error:
                self.errors.append({"operation": message["operation"], "error": str(error)})
                answer = {"id": message["id"], "error": str(error)}
            encoded = (_json(answer) + "\n").encode()
            if len(encoded) > 8 * 1024 * 1024:
                raise NativeStoreError("Dispatcher response bound exceeded")
            async with write_lock:
                process.stdin.write(encoded)
                await process.stdin.drain()

        try:
            async with asyncio.TaskGroup() as group:
                group.create_task(stderr())
                while line := await process.stdout.readline():
                    message = json.loads(line)
                    if message.get("type") == "result":
                        if result is not None:
                            raise NativeStoreError("Duplicate driver result")
                        result = message["value"]
                    else:
                        group.create_task(reply(message))
            code = await process.wait()
            if code != 0 or result is None:
                raise NativeStoreError("Driver closed without successful transport receipt")
            return result
        finally:
            if process.returncode is None:
                process.kill()
            await process.wait()


class SharedSinanProcess:
    """One installed Node process; independent, authority-bound logical drivers.

    No model credentials cross this pipe. Context is captured by the trusted
    caller, never selected by an incoming actor or tenant field. Broken transport
    is sticky for this coordinator lifetime; existing effects are not replayed.
    """

    MAX_JOBS = 1024
    MAX_RPC = 4096
    MAX_PACKET = 8 * 1024 * 1024
    MAX_BUFFER = 16 * 1024 * 1024

    def __init__(self, argv, env):
        self.argv, self.env = tuple(argv), dict(env)
        self.process = None
        self.jobs = {}
        self.replies = set()
        self.sends = set()
        self.serial = self.last_rpc = 0
        self.rpc_bytes = self.write_bytes = 0
        self.broken = None
        self.closing = False
        self.start_lock = asyncio.Lock()
        self.write_lock = asyncio.Lock()
        self.reader = self.stderr = None
        self.starting = None

    async def start(self):
        if self.closing or self.broken:
            raise NativeStoreError("Dispatcher unavailable; no automatic replay")
        if self.starting is None:
            self.starting = asyncio.create_task(self._start_process())
            self.starting.add_done_callback(lambda f: None if f.cancelled() else f.exception())
        await asyncio.shield(self.starting)

    async def _start_process(self):
        async with self.start_lock:
            if self.broken or self.closing:
                raise NativeStoreError("Dispatcher unavailable; no automatic replay")
            if self.process is not None:
                if self.process.returncode is not None:
                    raise NativeStoreError("Dispatcher exited; no automatic replay")
                return
            try:
                self.process = await asyncio.create_subprocess_exec(
                    *self.argv,
                    "--multiplex",
                    env=self.env,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    limit=self.MAX_PACKET,
                )
            except BaseException:
                self.broken = "Dispatcher start failed"
                raise
            self.reader = asyncio.create_task(self._read())
            self.stderr = asyncio.create_task(self._stderr())

    async def _send(self, message):
        data = (_json(message) + "\n").encode()
        if len(data) > self.MAX_PACKET:
            raise NativeStoreError("Dispatcher response bound exceeded")
        if self.write_bytes + len(data) > self.MAX_BUFFER:
            raise NativeStoreError("Dispatcher aggregate output bound exceeded")
        self.write_bytes += len(data)
        try:
            async with self.write_lock:
                self.process.stdin.write(data)
                await self.process.stdin.drain()
        finally:
            self.write_bytes -= len(data)

    async def run(self, dispatch):
        await self.start()
        if self.closing or self.broken:
            raise NativeStoreError("Dispatcher unavailable; no automatic replay")
        if len(self.jobs) >= self.MAX_JOBS:
            raise NativeStoreError("Dispatcher active context bound exceeded")
        self.serial += 1
        key = self.serial
        future = asyncio.get_running_loop().create_future()
        # Consume a detached caller's failure without suppressing awaited errors.
        future.add_done_callback(lambda f: None if f.cancelled() else f.exception())
        self.jobs[key] = dict(
            future=future,
            dispatch=dispatch,
            context=contextvars.copy_context(),
            errors=[],
            pending=0,
        )

        async def send_start():
            try:
                await self._send(dict(type="start", job=key))
            except BaseException:
                self._fail("Dispatcher send unknown; no replay")

        # Sending belongs to the durable logical driver, not its caller's await.
        # A detached caller cannot turn a queued pipe write into a global fault.
        sender = asyncio.create_task(send_start())
        self.sends.add(sender)
        sender.add_done_callback(self.sends.discard)
        await asyncio.shield(sender)
        # Caller cancellation never cancels another entry or fabricates closure.
        return await asyncio.shield(future)

    def _fail(self, reason):
        self.broken = self.broken or reason
        for job in self.jobs.values():
            if not job["future"].done():
                job["future"].set_exception(NativeStoreError(self.broken))
        self.jobs.clear()
        if self.process is not None and self.process.returncode is None:
            try:
                self.process.kill()
            except ProcessLookupError:
                pass

    async def _reply(self, key, rpc, operation, value, job, packet_bytes):
        settled = False
        try:
            try:
                value = await job["dispatch"](operation, value)
                answer = dict(type="reply", job=key, id=rpc, value=value)
            except Exception as error:
                if len(job["errors"]) < 128:
                    job["errors"].append(dict(operation=operation, error=str(error)))
                answer = dict(type="reply", job=key, id=rpc, error=str(error))
            # A completed side effect remains in the workflow's durable journal,
            # even when the pipe failed while that effect was running.
            if not self.broken:
                job["pending"] -= 1
                settled = True
                await self._send(answer)
        except Exception:
            self._fail("Dispatcher reply failed/unknown; no replay")
        finally:
            self.rpc_bytes -= packet_bytes
            if not settled:
                job["pending"] -= 1

    async def _read(self):
        try:
            while line := await self.process.stdout.readline():
                if len(line) > self.MAX_PACKET:
                    raise NativeStoreError("Dispatcher request bound exceeded")
                message = json.loads(line)
                if not isinstance(message, dict) or type(message.get("job")) is not int:
                    raise NativeStoreError("Invalid dispatcher envelope")
                key = message["job"]
                job = self.jobs.get(key)
                if job is None:
                    raise NativeStoreError("Unknown dispatcher context")
                if message.get("type") == "result":
                    if set(message) != {"type", "job", "value"} or job["pending"]:
                        raise NativeStoreError("Premature dispatcher terminal")
                    result = message["value"]
                    if not isinstance(result, dict):
                        raise NativeStoreError("Invalid dispatcher result")
                    result["host_errors"] = job["errors"]
                    result["transport"] = dict(
                        kind="shared-pipe",
                        pid=self.process.pid,
                        job=key,
                        logical_terminal=True,
                        physical_terminal=False,
                    )
                    del self.jobs[key]
                    job["future"].set_result(result)
                    continue
                if (
                    set(message) != {"type", "job", "id", "operation", "value"}
                    or message["type"] != "rpc"
                    or type(message["id"]) is not int
                    or message["id"] <= self.last_rpc
                    or not isinstance(message["operation"], str)
                    or not isinstance(message["value"], dict)
                    or len(self.replies) >= self.MAX_RPC
                    or self.rpc_bytes + len(line) > self.MAX_BUFFER
                ):
                    raise NativeStoreError("Invalid or unbounded dispatcher request")
                self.last_rpc = message["id"]
                job["pending"] += 1
                self.rpc_bytes += len(line)
                task = asyncio.create_task(
                    self._reply(key, message["id"], message["operation"], message["value"], job, len(line)),
                    context=job["context"].copy(),
                )
                self.replies.add(task)
                task.add_done_callback(self.replies.discard)
            code = await self.process.wait()
            if not self.closing or self.jobs or code != 0:
                raise NativeStoreError("Dispatcher closed/unknown; no replay")
        except BaseException as error:
            self._fail(str(error))
        finally:
            if self.broken and self.process.returncode is None:
                try:
                    self.process.kill()
                except ProcessLookupError:
                    pass
            await self.process.wait()

    async def _stderr(self):
        try:
            size = 0
            while chunk := await self.process.stderr.read(65536):
                size += len(chunk)
                if size > 900000:
                    raise NativeStoreError("Dispatcher stderr bound exceeded")
        except BaseException as error:
            self._fail(str(error))

    async def close(self):
        self.closing = True
        if self.starting is not None:
            try:
                await asyncio.shield(self.starting)
            except Exception:
                # A failed start already retained its failure; close any actual
                # process it produced, without launching a replacement.
                pass
        async with self.start_lock:
            self.closing = True
        if self.process is None:
            return dict(started=False, physical_terminal=True)
        if self.jobs:
            self._fail("Coordinator closed with outstanding contexts; no replay")
        elif self.process.returncode is None and not self.broken:
            self.process.stdin.close()
        await asyncio.gather(self.reader, self.stderr)
        if self.sends:
            await asyncio.gather(*list(self.sends))
        # Do not cancel worker threads with ongoing, durably tracked effects.
        if self.replies:
            await asyncio.gather(*list(self.replies))
        return dict(
            started=True,
            pid=self.process.pid,
            exit_code=self.process.returncode,
            physical_terminal=True,
            failure=self.broken,
        )


class WorkflowService:
    """Actor-bound pipe service, with the same native operations as the HTTP API.

    Entry authority is checked before every effect and after asynchronous waits.
    Models never receive this object or its dispatcher pipe.
    """

    def __init__(self, workflow, actor, authorize, issues=None):
        self.workflow, self.actor, self.authorize = workflow, actor, authorize
        self.issues = None if issues is None else frozenset(issues)

    async def __call__(self, operation, payload):
        self.authorize()
        workflow, actor = self.workflow, self.actor
        if operation == "await-terminal":
            result = await workflow.await_terminal(actor, payload["key"])
        elif operation == "integration-await":
            result = await workflow.integration.continuous.await_lane(actor, payload["key"], payload["event"])
        else:
            result = await asyncio.to_thread(self.call, operation, payload)
        self.authorize()
        return result

    def call(self, operation, payload):
        self.authorize()
        w, actor = self.workflow, self.actor
        if operation.startswith("integration-"):
            integration = getattr(w, "integration", None)
            if integration is None:
                raise NativeStoreError("Integration installation unavailable")
            method = operation.removeprefix("integration-")
            if method == "continue":
                return integration.continue_lane(actor, payload["key"], payload.get("event"))
            if method == "contribution":
                return integration.check_contribution(actor, payload["key"])
            if method not in {"status", "execute", "resolve", "reconcile", "finish", "authorize"}:
                raise NativeStoreError("Unsupported integration operation")
            return getattr(integration, method)(actor, payload["group" if method == "authorize" else "key"])
        if operation == "inspect":
            board = w.inspect(actor)
            owned = None
            if self.issues is not None:
                with w.domain._connection_lock:
                    owned = {
                        r["id"]
                        for r in w.domain.db.execute("SELECT id,issue FROM native_tasks")
                        if r["issue"] in self.issues
                    }
                board["requests"] = [r for r in board["requests"] if r["ticket"] in owned]
                board["produced"] = [k for k in board["produced"] if k in owned]
                board["stage_checks"] = [k for k in board["stage_checks"] if k in owned]
                board["snapshot"]["items"] = [r for r in board["snapshot"]["items"] if r["key"] in owned]
                board["snapshot"]["ready"] = [k for k in board["snapshot"]["ready"] if k in owned]
                waiting = {r["key"] for r in board["snapshot"]["items"] if r.get("waitReason") == "resource_conflict"}
                waiting_assets = OccupiedWrites(r["writes"] for r in board["requests"] if r["ticket"] in waiting)
                active = board["environment"]["active"]
                full = bool(board["requests"]) and len(active) >= board["environment"]["capacity"]
                for holder in active:
                    if holder["ticket"] not in owned and not full and not waiting_assets.overlaps(holder["writes"]):
                        holder.pop("terminalObservable", None)

            integration = getattr(w, "integration", None)
            if integration is not None:
                contributions = [
                    key
                    for key in board.get("produced", [])
                    if json.loads(w.status(actor, key)["task"]).get("delivery_mode") == "contribution"
                ]
                board["contributions"] = contributions
                board["produced"] = [key for key in board.get("produced", []) if key not in contributions]
                board["integrations"] = integration.discover(actor)
                if owned is not None:
                    with w.domain._connection_lock:
                        unfinished = any(
                            r["state"] != "accepted"
                            for r in w.domain.db.execute("SELECT id,state FROM native_tasks")
                            if r["id"] in owned
                        )
                    if not unfinished:
                        board["integrations"] = dict(ready=[], errors=[], continuous=[])

            return board
        if operation == "advance":
            return w.advance(actor, isolate=True, exclude=payload.get("exclude", []))
        if operation == "execute":
            return w.execute_receipt(actor, payload["key"])
        if operation in {"status", "check", "review", "reconcile", "finish"}:
            return getattr(w, operation)(actor, payload["key"])
        if operation == "verify-stage":
            return w.verify_stage(actor, payload["key"])
        if operation == "reserve":
            return w.reserve(actor, payload["assignment"])
        if operation not in {"revalidate", "start", "ack", "record"}:
            raise NativeStoreError("Unsupported dispatcher operation")
        assignment = payload.get("assignment")
        if not isinstance(assignment, dict) or "ticket" not in assignment:
            raise NativeStoreError("Exact dispatcher assignment required")
        row = w.status(actor, assignment["ticket"])
        if operation == "revalidate":
            return row["state"] == "ready"
        if operation == "start":
            return {"reference": row["id"]}
        return {"state": row["state"]}


class EntryConsumer:
    """Single installed coordinator: startup recovery plus real-event wakeups.

    notify must run on this loop after commit (call_soon_threadsafe from threads).
    Clearing before read and checking again after consumption closes idle races.
    No periodic polling; claimed unknown entries are deliberately not retried.
    """

    def __init__(self, ledger, consume, *, recover_unknown=False):
        self.ledger, self.consume = ledger, consume
        self.wakeup = asyncio.Event()
        self.stopping = False
        self.failures = []
        self.active = {}
        self.attempted = set()
        self.recover_unknown = recover_unknown

    def notify(self, key=None):
        if key is not None and key not in self.active:
            self.attempted.discard(key)
        self.wakeup.set()

    async def run(self):
        self.notify()

        async def consume(claimed):
            key = claimed["id"]
            try:
                receipt = await self.consume(claimed)
                self.ledger.settle(key, receipt)
                self.failures[:] = [failure for failure in self.failures if failure["id"] != key]
            except Exception as error:
                self.failures.append({"id": key, "error": str(error)})
            finally:
                self.active.pop(key, None)

        try:
            while not self.stopping:
                await self.wakeup.wait()
                self.wakeup.clear()
                for row in self.ledger.pending(include_held=self.recover_unknown):
                    key = row["id"]
                    if self.stopping:
                        break
                    if key in self.active or key in self.attempted:
                        continue
                    self.attempted.add(key)
                    try:
                        claimed = self.ledger.claim(key, recover=self.recover_unknown)
                        if claimed is not None:
                            self.active[key] = asyncio.create_task(consume(claimed))
                    except Exception as error:
                        self.failures.append({"id": key, "error": str(error)})
        finally:
            if self.active:
                await asyncio.gather(*list(self.active.values()))

    def stop(self):
        self.stopping = True
        self.notify()
