"""Event driven native workflow; host installation supplies all privileged ports.

SQLite reservations are short. Workers/checks/release run after domain locks end.
Unknown intent survives restart and requires an authenticated owner receipt.
"""

from __future__ import annotations

import asyncio
import json
import time
from concurrent.futures import Future
from contextlib import contextmanager

from native_store import NativeStoreError, _digest, _json
from tianxuan_core import PermissionDenied


class StageAuthorizationChanged(NativeStoreError):
    """A design task no longer has the stage authority used for dispatch."""


def check_passed(runner, tenant, candidate, check, fact):
    """A cached result has no process outcome; validate its actual evidence."""
    if fact.get("outcome") == "passed":
        return True
    if fact.get("state") != "cached":
        return False
    hit = runner.cache.lookup(tenant, candidate, check, **runner.context(check, candidate))
    return hit is not None and hit["evidence"]["id"] == fact.get("evidence")


class NativeWorkflow:
    def __init__(
        self,
        domain,
        worker,
        runner,
        release,
        authorize,
        capacity=2,
        catalog=None,
        principals=None,
        review_candidate=None,
        installed_plan=None,
        next_issues=None,
        installed_target=None,
    ):
        if not callable(authorize) or type(capacity) is not int or not 1 <= capacity <= 1024:
            raise NativeStoreError("Trusted authority and positive capacity required")
        self.domain, self.worker, self.runner, self.release = domain, worker, runner, release
        self.authorize, self.capacity = authorize, capacity
        self.principals, self.review_candidate, self.installed_plan = principals, review_candidate, installed_plan
        self._executions = {}  # Exact local coordinator ownership; never inferred from a PID.
        self.next_issues = next_issues
        self.installed_target = installed_target
        self.catalog = json.loads(_json(catalog or []))
        self.domain.db.create_function("native_workflow_version", 0, lambda: 2)
        with self._transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_tasks (id TEXT PRIMARY KEY, tenant TEXT NOT NULL, "
                "issue TEXT UNIQUE NOT NULL, task TEXT NOT NULL, state TEXT NOT NULL, "
                "ready_at REAL NOT NULL, assignment TEXT, terminal TEXT, acceptance TEXT)"
            )
            # One writer transaction: preserve exact old task rows and worker states.
            db.execute("CREATE TABLE IF NOT EXISTS native_active_tasks (issue TEXT PRIMARY KEY, task TEXT NOT NULL)")
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_task_revisions (task TEXT PRIMARY KEY, previous TEXT, actor TEXT NOT NULL)"
            )
            indexes = db.execute("PRAGMA index_list(native_tasks)").fetchall()
            if any(
                i["unique"] and [c["name"] for c in db.execute("PRAGMA index_info(" + i["name"] + ")")] == ["issue"]
                for i in indexes
            ):
                db.execute("ALTER TABLE native_tasks RENAME TO native_tasks_v1")
                db.execute(
                    "CREATE TABLE native_tasks (id TEXT PRIMARY KEY, tenant TEXT NOT NULL, issue TEXT NOT NULL, "
                    "task TEXT NOT NULL, state TEXT NOT NULL, ready_at REAL NOT NULL, assignment TEXT, terminal TEXT, acceptance TEXT)"
                )
                db.execute("INSERT INTO native_tasks SELECT * FROM native_tasks_v1")
                db.execute("INSERT INTO native_active_tasks SELECT issue,id FROM native_tasks_v1")
                for row in db.execute("SELECT id,task FROM native_tasks_v1").fetchall():
                    db.execute(
                        "INSERT INTO native_task_revisions VALUES (?,NULL,?)",
                        (row["id"], json.loads(row["task"])["actor"]),
                    )
                db.execute("DROP TABLE native_tasks_v1")
            # Old installations cannot mutate versioned task rows silently.
            for action in ("INSERT", "UPDATE", "DELETE"):
                db.execute(
                    "CREATE TRIGGER IF NOT EXISTS native_tasks_v2_"
                    + action
                    + " BEFORE "
                    + action
                    + " ON native_tasks BEGIN SELECT CASE WHEN native_workflow_version()!=2 "
                    "THEN RAISE(ABORT,'native workflow v2 required') END; END"
                )
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_outbox (id TEXT PRIMARY KEY, tenant TEXT NOT NULL, "
                "payload TEXT NOT NULL)"
            )
            db.execute("CREATE TABLE IF NOT EXISTS native_outbox_consumed (id TEXT PRIMARY KEY)")
            db.execute("CREATE TABLE IF NOT EXISTS native_workflow_reviews (task TEXT PRIMARY KEY, receipt TEXT)")
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_workflow_targets (task TEXT PRIMARY KEY, target TEXT NOT NULL)"
            )
            db.execute("CREATE INDEX IF NOT EXISTS native_tasks_ready ON native_tasks(tenant,state,ready_at,id)")

    @contextmanager
    def _transaction(self):
        with self.domain._connection_lock:
            db = self.domain.db
            if db.in_transaction:
                raise NativeStoreError("Workflow requires independent transaction")
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def _allow(self, actor, issue, action):
        source = self.domain.issue_snapshot(actor, issue, write=action != "read")
        if self.authorize(actor, issue, action) is not True:
            raise PermissionDenied("Native workflow authority denied")
        if action in {"authorize", "execute", "check"}:
            authority = self._stage_authority(actor, issue, source["revision"])
            if authority is not None:
                definition = {**source["definition"], "stage_authorization": authority}
                return {"definition": definition, "revision": _digest(_json(definition).encode())}
        return source

    def _stage_authority(self, actor, issue, issue_revision):
        # Membership is independent of source visibility. A private design or a
        # missing confirmation must never take the ordinary issue path.
        with self.domain._connection_lock:
            record = self.domain.db.execute(
                "SELECT i.project,i.number FROM design_task_sources s JOIN issues i ON i.id=s.issue_id "
                "WHERE s.issue_id=?",
                (issue,),
            ).fetchone()
            if record is None:
                return None
            detail = self.domain.read_issue_detail(actor, record["project"], record["number"])
        source = detail["design_source"]
        if not source:
            raise PermissionDenied("Signed task source unavailable")
        target = detail["task_target"]
        confirmation = detail.get("task_confirmation")
        if not target or target["status"] != "defined" or not confirmation or confirmation["status"] != "confirmed":
            raise StageAuthorizationChanged("Current task stage confirmation required")
        responsible = detail["assignee"]["id"] if detail["assignee"] else detail["created_by"]
        binding = {
            "issue_id": issue,
            "issue_revision": issue_revision,
            "document_id": source["document_id"],
            "version": source["version"],
            "target_revision": target["revision"],
            "stage": target["stage"],
            "responsible_user": responsible,
            "confirmed_by": responsible,
        }
        if (
            any(confirmation.get(name) != value for name, value in binding.items())
            or any(target[name] != binding[name] for name in ("issue_id", "document_id", "version"))
            or not target["criteria"]
            or not confirmation["revision"]
        ):
            raise StageAuthorizationChanged("Task stage confirmation changed")
        return {**binding, "confirmation_revision": confirmation["revision"], "criteria": target["criteria"]}

    def _row(self, db, key):
        row = db.execute("SELECT * FROM native_tasks WHERE id=?", (key,)).fetchone()
        if row is None:
            raise NativeStoreError("Native task unavailable")
        return dict(row)

    def status(self, actor, key):
        with self._transaction() as db:
            row = self._row(db, key)
            self._read_allowed(actor, row)
            return row

    def _read_allowed(self, actor, row):
        self._allow(actor, row["issue"], "read")
        task = json.loads(row["task"])
        # A historical contract keeps its original text even if the issue is
        # reassociated. Current issue visibility cannot authorize that history.
        for requirement in task["source"]["definition"]["requirements"]:
            self.domain.get_doc_shared(actor, requirement["id"])
        authority = task["source"]["definition"].get("stage_authorization")
        if authority:
            self.domain.get_doc_shared(actor, authority["document_id"])
        self._inputs_allowed(actor, task["selected"])

    def authorize_task(
        self,
        actor,
        issue,
        *,
        selected,
        writes,
        dependencies,
        profile,
        product,
        checks,
        mandate,
        capabilities=None,
        expected=None,
        delivery_mode="standalone",
        stage=None,
    ):
        source = self._allow(actor, issue, "authorize")
        if stage != source["definition"].get("stage_authorization", {}).get("stage"):
            raise NativeStoreError("Installed plan stage must match the confirmed target")
        if delivery_mode not in {"standalone", "contribution"}:
            raise NativeStoreError("Unsupported delivery mode")
        if not mandate or not checks or profile not in self.worker.profiles:
            raise NativeStoreError("Installed profile, checks and mandate required")
        tenant = source["definition"]["tenant_id"]
        revisions, _ = self.worker.workspace.sources(tenant, selected)
        self._inputs_allowed(actor, revisions)
        if not isinstance(writes, dict) or not writes or set(writes) - revisions.keys():
            raise NativeStoreError("Writable scope must be inside fixed inputs")
        if any(module.startswith("requirement-") for module in writes):
            raise NativeStoreError("Requirement source cannot be writable")
        if any(
            value != "*" and (not isinstance(value, list) or not all(isinstance(x, str) for x in value))
            for value in writes.values()
        ):
            raise NativeStoreError("Invalid writable objects")
        installation = self.worker.installation(profile)
        capabilities = [] if capabilities is None else capabilities
        if (
            not isinstance(capabilities, list)
            or len(capabilities) > 32
            or not all(isinstance(c, str) and c for c in capabilities)
        ):
            raise NativeStoreError("Invalid required capabilities")
        producer = self.principals(actor, issue, "producer") if self.principals else actor
        task = dict(
            actor=actor,
            producer=producer,
            tenant=tenant,
            issue=issue,
            source=source,
            selected=revisions,
            writes=writes,
            installation=installation,
            capabilities=capabilities,
            check_contexts={check: self.runner.context(check, "0" * 64) for check in checks},
            dependencies=dependencies,
            profile=profile,
            product=product,
            checks=checks,
            mandate=mandate,
            delivery_mode=delivery_mode,
            **({"previous": expected} if expected is not None else {}),
        )
        key = _digest(_json(task).encode())
        with self._transaction() as db:
            if self._allow(actor, issue, "authorize") != source:
                raise NativeStoreError("Source changed")
            for dependency, acceptance in dependencies.items():
                row = self._row(db, dependency)
                self._read_allowed(actor, row)
                if row["tenant"] != tenant or row["acceptance"] != acceptance or not acceptance:
                    raise NativeStoreError("Dependency lacks exact accepted output")
                accepted = json.loads(acceptance)
                if any(revisions.get(m) != r for m, r in accepted["modules"].items()):
                    raise NativeStoreError("Dependency output must be pinned")
            old = db.execute("SELECT task FROM native_active_tasks WHERE issue=?", (issue,)).fetchone()
            if db.execute("SELECT 1 FROM native_tasks WHERE id=?", (key,)).fetchone():
                return key  # Stable replay never reactivates an older definition.
            if (old["task"] if old else None) != expected:
                raise NativeStoreError("Managed definition already bound; explicit revision required (active changed)")
            stage_authority = source["definition"].get("stage_authorization")
            if expected and stage_authority:
                previous_task = json.loads(self._row(db, expected)["task"])
                if previous_task["source"]["definition"].get("stage_authorization") == stage_authority:
                    if {k: v for k, v in previous_task.items() if k != "previous"} == {
                        k: v for k, v in task.items() if k != "previous"
                    }:
                        return expected
                    raise NativeStoreError("A different installed contract requires a new stage confirmation")
            if expected is not None and not old:
                raise NativeStoreError("No active definition to replace")
            if expected is None and self.domain.get_issue(issue)["status"] in {"done", "cancelled"}:
                raise NativeStoreError("Terminal issue cannot be newly managed")
            db.execute(
                "INSERT INTO native_tasks VALUES (?,?,?,?,?,?,NULL,NULL,NULL)",
                (key, tenant, issue, _json(task), "ready", time.time()),
            )
            db.execute(
                "INSERT INTO native_active_tasks VALUES (?,?) ON CONFLICT(issue) DO UPDATE SET task=excluded.task",
                (issue, key),
            )
            if expected is not None:
                if stage_authority and not callable(getattr(self.worker, "reserve", None)):
                    # A local ticket that never entered running has no physical
                    # owner. Its superseding revision must be able to reserve.
                    db.execute(
                        "UPDATE native_tasks SET state='superseded' WHERE id=? AND state='reserved'", (expected,)
                    )
                # Legacy publishers do not know the active map and can publish
                # without writing native_tasks. Retire settled unaccepted work
                # so their existing produced-state guard also fails closed.
                # Real/unknown occupancy and historical acceptance stay intact.
                db.execute(
                    "UPDATE native_tasks SET state='superseded' WHERE id=? AND state IN ('ready','produced','failed','stopped','closed-unresolved')",
                    (expected,),
                )
            db.execute("INSERT INTO native_task_revisions VALUES (?,?,?)", (key, expected, actor))
            db.execute(
                "INSERT INTO native_managed_issues VALUES (?,?,NULL) ON CONFLICT(issue_id) DO UPDATE SET definition=excluded.definition,acceptance=NULL",
                (issue, source["revision"]),
            )
            db.execute("UPDATE issues SET status='planned' WHERE id=?", (issue,))
            self.domain._event(tenant, "native.authorized", actor, issue, {"task": key, "previous": expected})
            requirement = source["definition"]["requirement_id"]
            if requirement:
                self.domain.sync_progress(requirement, actor=actor)
        return key

    def _valid(self, actor, row):
        active = self.domain.db.execute(
            "SELECT task FROM native_active_tasks WHERE issue=?", (row["issue"],)
        ).fetchone()
        if not active or active[0] != row["id"]:
            raise NativeStoreError("Task definition superseded")
        task = json.loads(row["task"])
        self._inputs_allowed(actor, task["selected"])
        source = self._allow(actor, row["issue"], "execute")
        if source != task["source"]:
            if source["definition"].get("stage_authorization") != task["source"]["definition"].get(
                "stage_authorization"
            ):
                raise StageAuthorizationChanged("Task stage confirmation changed")
            raise NativeStoreError("Task definition changed")
        if self.domain.get_issue(row["issue"])["status"] in {"cancelled", "blocked"}:
            raise NativeStoreError("Issue execution is stopped")
        for dependency, acceptance in task["dependencies"].items():
            other = self._row(self.domain.db, dependency)
            self._read_allowed(actor, other)
            if other["acceptance"] != acceptance or other["state"] != "accepted":
                raise NativeStoreError("Dependency acceptance changed")
        return task

    def _inputs_allowed(self, actor, revisions):
        # authorize_task stores the complete exact closure, not just caller roots.
        for module in revisions:
            if module.startswith("requirement-"):
                self.domain.require_native_module_read(actor, module)

    def _schedulable(self, task, target="agent"):
        return target == "agent" and any(
            model.get("id") == task["profile"]
            and model.get("available") is True
            and target in model.get("targets", [])
            and all(c in model.get("capabilities", []) for c in task["capabilities"])
            for model in self.catalog
        )

    def inspect(self, actor):
        with self._transaction() as db:
            tenant = self.domain.actor_context(actor)["tenant"]
            rows = db.execute(
                "SELECT * FROM native_tasks WHERE tenant=? AND state='ready' ORDER BY ready_at,id LIMIT 1024", (tenant,)
            ).fetchall()
            items, ready, sources, active, requests = [], [], [], [], []
            held = db.execute(
                "SELECT * FROM native_tasks WHERE state IN ('reserved','running','held') ORDER BY id LIMIT 1024"
            ).fetchall()
            for index, held_row in enumerate(held):
                visible = held_row["tenant"] == tenant
                if visible:
                    try:
                        self._read_allowed(actor, held_row)
                    except PermissionDenied:
                        visible = False
                active.append({
                    "ticket": held_row["id"] if visible else "occupied-slot-" + str(index),
                    **({"terminalObservable": True} if visible and held_row["state"] != "reserved" else {}),
                    "reads": [],
                    "writes": [str(self.worker.root / held_row["id"])] if visible else [],
                })
            for row in rows:
                try:
                    task = self._valid(actor, row)
                except (PermissionDenied, NativeStoreError):
                    continue
                key = row["id"]
                resource = str(self.worker.root / key)
                source = {"source": key, "revision": task["source"]["revision"]}
                sources.append(source)
                items.append({"key": key, "source": key, "dispatchCandidate": row["state"] == "ready"})
                if row["state"] == "ready":
                    ready.append(key)
                requests.append(
                    dict(
                        ticket=key,
                        outcome=task["source"]["definition"]["title"],
                        owner=actor,
                        acceptance=task["source"]["definition"]["acceptance"] or "all criteria",
                        authorityRef=task["mandate"],
                        capabilities=task["capabilities"],
                        contextRefs=[],
                        reads=[],
                        writes=[resource],
                        model=task["profile"],
                    )
                )
            return dict(
                snapshot=dict(items=items, ready=ready, sourceSnapshots=sources),
                environment=dict(catalog=self.catalog, active=active, capacity=self.capacity),
                requests=requests,
                produced=self._produced_visible(actor, tenant),
            )

    def _produced_visible(self, actor, tenant):
        keys = []
        for row in self.domain.db.execute(
            "SELECT * FROM native_tasks WHERE tenant=? AND state='produced' ORDER BY ready_at,id LIMIT 1024", (tenant,)
        ).fetchall():
            try:
                self._valid(actor, row)
            except (PermissionDenied, NativeStoreError):
                continue
            keys.append(row["id"])
        return keys

    def reserve(self, actor, assignment):
        self._dependencies_current(actor, assignment["ticket"])
        with self._transaction() as db:
            row = self._row(db, assignment["ticket"])
            task = self._valid(actor, row)
            if row["state"] != "ready":
                return False
            if not self._schedulable(task, assignment.get("target", "agent")):
                return False
            held = db.execute(
                "SELECT count(*) FROM native_tasks WHERE state IN ('reserved','running','held')"
            ).fetchone()[0]
            if held >= self.capacity:
                return False
            earlier = db.execute(
                "SELECT * FROM native_tasks WHERE tenant=? AND state='ready' "
                "AND (ready_at < ? OR (ready_at=? AND id<?)) ORDER BY ready_at,id",
                (row["tenant"], row["ready_at"], row["ready_at"], row["id"]),
            ).fetchall()
            for waiting in earlier:
                try:
                    waiting_task = self._valid(actor, waiting)
                except (PermissionDenied, NativeStoreError):
                    continue
                if not self._schedulable(waiting_task):
                    continue
                available_node = getattr(self.worker, "available_node", None)
                if available_node is not None and available_node(db, waiting_task) is None:
                    continue
                return False  # Durable FIFO, including competing dispatcher processes.
            expected = {"source": row["id"], "revision": task["source"]["revision"]}
            if assignment["sourceSnapshot"] != expected or assignment["model"]["id"] != task["profile"]:
                raise NativeStoreError("Untrusted assignment")
            reserve_worker = getattr(self.worker, "reserve", None)
            if reserve_worker is not None and not reserve_worker(db, task, row["id"]):
                return False
            db.execute(
                "UPDATE native_tasks SET state='reserved',assignment=? WHERE id=?", (_json(assignment), row["id"])
            )
            callback = getattr(self, "on_state_change", None)
            if callback is not None:
                callback()
            return True

    async def await_terminal(self, actor, key):
        remote_wait = getattr(self.worker, "wait_terminal", None)
        if remote_wait is not None:
            return await remote_wait(actor, key)
        # Registration and execution ownership use the same domain lock. A
        # completed execution is recovered from durable state, not cached events.
        with self.domain._connection_lock:
            row = self.status(actor, key)
            owned = self._executions.get(key)
        if owned is not None:
            event, deadline = owned
            try:
                await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(event)), max(0, deadline - time.monotonic()))
            except TimeoutError:
                raise NativeStoreError("Terminal observer deadline exceeded; physical state remains unknown") from None
        row = self.reconcile(actor, key)
        if row["state"] in {"reserved", "running", "held", "closed-unresolved"}:
            raise NativeStoreError("Terminal event ownership unavailable; physical state remains unknown")
        with self._transaction() as db:
            row = self._row(db, key)
            self._valid(actor, row)
        return row

    def execute(self, actor, key):
        with self.domain._connection_lock:
            row = self.status(actor, key)
            if key in self._executions or row["state"] != "reserved":
                return row
            task = json.loads(row["task"])
            event = Future()
            deadline = time.monotonic() + self.worker.profiles[task["profile"]]["timeout"] + 60
            self._executions[key] = (event, deadline)
        try:
            return self._execute_owned(actor, key)
        finally:
            with self.domain._connection_lock:
                self._executions.pop(key, None)
                event.set_result(None)
            callback = getattr(self, "on_state_change", None)
            if callback is not None:
                callback()

    def _execute_owned(self, actor, key):
        self._dependencies_current(actor, key)
        stale = None
        with self._transaction() as db:
            row = self._row(db, key)
            try:
                task = self._valid(actor, row)
            except StageAuthorizationChanged as error:
                # A local reservation precedes all process intent. Remote adapters
                # can own a physical reservation and retain their own settlement.
                if row["state"] != "reserved" or callable(getattr(self.worker, "reserve", None)):
                    raise
                db.execute("UPDATE native_tasks SET state='stopped' WHERE id=?", (key,))
                self.domain._event(row["tenant"], "native.stage-denied", actor, row["issue"], {"task": key})
                stale = error
            if row["state"] != "reserved":
                return row  # Unknown/running never retried.
            if stale is None:
                db.execute("UPDATE native_tasks SET state='running' WHERE id=?", (key,))
                db.execute("UPDATE issues SET status='in-progress' WHERE id=?", (row["issue"],))
                self.domain._event(task["tenant"], "native.started", actor, row["issue"], {"task": key})
        if stale is not None:
            raise stale
        try:
            terminal = self.worker.run(task, key)
            if terminal is None:
                return self.status(actor, key)
        except BaseException:
            with self._transaction() as db:
                db.execute("UPDATE native_tasks SET state='held' WHERE id=?", (key,))
            raise
        with self._transaction() as db:
            current = self._row(db, key)
            try:
                self._valid(actor, current)
                state = terminal["state"]
            except (PermissionDenied, NativeStoreError):
                state = "stopped"
            db.execute("UPDATE native_tasks SET state=?,terminal=? WHERE id=?", (state, _json(terminal), key))
            if state != "stopped":
                db.execute(
                    "UPDATE issues SET status=? WHERE id=?",
                    ("in-review" if terminal["state"] == "produced" else "blocked", row["issue"]),
                )
            self.domain._event(task["tenant"], "native.terminal", actor, row["issue"], {"task": key, "state": state})
        return {**terminal, "state": state}

    def _dependencies_current(self, actor, key):
        row = self.status(actor, key)
        task = json.loads(row["task"])
        for dependency, acceptance in task["dependencies"].items():
            upstream = self.status(actor, dependency)
            accepted = json.loads(acceptance)
            if upstream["acceptance"] != acceptance or upstream["state"] != "accepted":
                raise NativeStoreError("Dependency acceptance changed")
            request = accepted["request"]
            current = self.release.historical(
                task["tenant"], actor, request["product"], request["channel"], accepted["id"]
            )
            if current != accepted:
                raise NativeStoreError("Dependency historical release invalid")

    def _settle_physical(self, worker, key):
        """Installed adapter only: release ownership, without reading/admitting output.

        No actor identity substitution and no task/issue content returned. The
        persisted exact physical record, not a timeout, is the release evidence.
        """
        if worker is not self.worker:
            raise NativeStoreError("Physical settlement requires installed worker")
        with self._transaction() as db:
            row = self._row(db, key)
            task = json.loads(row["task"])
            if not worker.process_closed(task, key):
                raise NativeStoreError("Physical closure required")
            if row["state"] in {"reserved", "running", "held", "closed-unresolved"}:
                db.execute("UPDATE native_tasks SET state='stopped' WHERE id=?", (key,))
                return "stopped"
            return row["state"]

    def reconcile(self, actor, key):
        row = self.status(actor, key)
        self._allow(actor, row["issue"], "reconcile")
        if row["state"] not in {"running", "held", "closed-unresolved"}:
            return row
        task = json.loads(row["task"])
        failure = None
        try:
            terminal = self.worker.reconcile(task, key)
        except NativeStoreError as error:
            # Current producer authority can reject content after the physical
            # process closed. The coordinator may settle capacity, never approve
            # that content or impersonate the producer to recover it.
            terminal, failure = None, str(error)
        if terminal is None and not self.worker.process_closed(task, key):
            if failure is not None:
                raise NativeStoreError(failure)
            return row  # No expiry, PID takeover or automatic relaunch.
        with self._transaction() as db:
            current = self._row(db, key)
            self._read_allowed(actor, current)
            self._allow(actor, current["issue"], "reconcile")
            try:
                self._valid(actor, current)
                state = terminal["state"] if terminal is not None else "closed-unresolved"
            except (PermissionDenied, NativeStoreError):
                state = "stopped"
            if current["state"] in {"running", "held", "closed-unresolved"}:
                db.execute(
                    "UPDATE native_tasks SET state=?,terminal=? WHERE id=?",
                    (state, _json(terminal) if terminal is not None else None, key),
                )
                if state in {"produced", "failed"}:
                    db.execute(
                        "UPDATE issues SET status=? WHERE id=?",
                        ("in-review" if state == "produced" else "blocked", current["issue"]),
                    )
                if current["state"] != state:
                    self.domain._event(
                        task["tenant"],
                        "native.reconciled",
                        actor,
                        current["issue"],
                        {"task": key, "state": state, "content_error": failure},
                    )
        return self.status(actor, key)

    def advance(self, actor, *, isolate=False, exclude=()):
        """Consume actual acceptance events. Installed graph resolver supplies issues.

        Authorizing a dependent uses pinned accepted outputs returned by the installed
        plan. Failed consumption is replayable; no background scans or model polling.
        """
        if not callable(self.next_issues):
            return {"authorized": [], "errors": []} if isolate else []
        with self._transaction() as db:
            tenant = self.domain.actor_context(actor)["tenant"]
            events = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM native_outbox WHERE tenant=? "
                    "AND id NOT IN (SELECT id FROM native_outbox_consumed) ORDER BY rowid",
                    (tenant,),
                ).fetchall()
            ]
        results, errors = [], []
        for event in events:
            if event["id"] in exclude:
                continue
            try:
                self.status(actor, event["id"])
            except PermissionDenied:
                continue  # Preserve private pending events without exposing identifiers.
            try:
                issues = self.next_issues(actor, json.loads(event["payload"]))
                if not isinstance(issues, list) or len(issues) > 1024 or not all(isinstance(i, str) for i in issues):
                    raise NativeStoreError("Invalid installed dependency event response")
                results.extend(self.authorize_installed(actor, issue) for issue in issues)
                with self._transaction() as db:
                    db.execute("INSERT OR IGNORE INTO native_outbox_consumed VALUES (?)", (event["id"],))
            except Exception as error:
                if not isolate:
                    raise
                errors.append({"event": event["id"], "reason": type(error).__name__})
        return {"authorized": results, "errors": errors} if isolate else results

    def check(self, actor, key):
        self._dependencies_current(actor, key)
        row = self.status(actor, key)
        task = self._valid(actor, row)
        if self._allow(actor, row["issue"], "check") != task["source"]:
            raise NativeStoreError("Task definition changed")
        if row["state"] != "produced":
            raise NativeStoreError("Confirmed producer terminal required")
        candidate = json.loads(row["terminal"])["candidate"]
        if task["check_contexts"] != {check: self.runner.context(check, candidate) for check in task["checks"]}:
            raise NativeStoreError("Authorized check installation changed")
        checker = self.principals(actor, task["issue"], "checker") if self.principals else actor
        return {
            check: self.runner.execute(task["tenant"], checker, key + "-" + check, candidate, check)
            for check in task["checks"]
        }

    def authorize_installed(self, actor, issue, *, expected=None):
        self._allow(actor, issue, "authorize")
        if not callable(self.installed_plan):
            raise NativeStoreError("No admitted native plan installed")
        plan = self.installed_plan(actor, issue)
        return self.authorize_task(actor, issue, expected=expected, **plan)

    def review(self, actor, key):
        self._dependencies_current(actor, key)
        row = self.status(actor, key)
        task = self._valid(actor, row)
        if task.get("delivery_mode") == "contribution":
            raise NativeStoreError("Contribution requires joint integration review")
        self._allow(actor, row["issue"], "review")
        if not callable(self.principals) or not callable(self.review_candidate):
            raise NativeStoreError("Independent review installation unavailable")
        if row["state"] != "produced":
            raise NativeStoreError("Producer terminal required")
        terminal = json.loads(row["terminal"])
        reviewer = self.principals(actor, row["issue"], "reviewer")
        if reviewer == task["producer"]:
            raise NativeStoreError("Independent execution principal required")
        with self.release.store._connection() as native_db:
            previous = native_db.execute(
                "SELECT record FROM native_release_requests WHERE tenant=? AND actor=? AND request_key=?",
                (task["tenant"], reviewer, "review-" + key),
            ).fetchone()
            if previous:
                return self.release._valid_review(native_db, task["tenant"], previous["record"])
        facts = self.check(actor, key)
        if any(
            not check_passed(self.runner, task["tenant"], terminal["candidate"], check, fact)
            for check, fact in facts.items()
        ):
            raise NativeStoreError("Required content checks failed; independent review not started")
        with self._transaction() as db:
            recovering = db.execute("SELECT 1 FROM native_workflow_reviews WHERE task=?", (key,)).fetchone() is not None
            if not recovering:
                db.execute("INSERT INTO native_workflow_reviews VALUES (?,NULL)", (key,))
        review = getattr(self.review_candidate, "reconcile", None) if recovering else self.review_candidate
        if not callable(review):
            raise NativeStoreError("Review outcome unknown; trusted reconciliation required")
        if review(actor, task, terminal) is not True:
            raise NativeStoreError("Independent candidate review not accepted")
        self._dependencies_current(actor, key)
        self._valid(actor, self.status(actor, key))
        receipt = self.release.approve(
            task["tenant"],
            reviewer,
            "review-" + key,
            task["product"],
            terminal["candidate"],
            {c: r["evidence"] for c, r in facts.items()},
            "Trusted independent execution accepted exact task candidate",
        )
        with self._transaction() as db:
            db.execute("UPDATE native_workflow_reviews SET receipt=? WHERE task=?", (_json(receipt), key))
        return receipt

    def finish(self, actor, key):
        """Installed delivery target only; a replay never silently rebases publication."""
        row = self.status(actor, key)
        if json.loads(row["task"]).get("delivery_mode") == "contribution":
            if not hasattr(self, "integration"):
                raise NativeStoreError("Integration installation unavailable")
            return self.integration.check_contribution(actor, key)
        self._allow(actor, row["issue"], "publish")
        self._valid(actor, row)
        if row["state"] == "accepted":
            return {"state": "accepted", "acceptance": json.loads(row["acceptance"])}
        if row["state"] != "produced" or not callable(self.installed_target):
            raise NativeStoreError("Produced candidate and admitted delivery target required")
        with self._transaction() as db:
            saved = db.execute("SELECT target FROM native_workflow_targets WHERE task=?", (key,)).fetchone()
        if saved:
            target = json.loads(saved["target"])
        else:
            target = self.installed_target(actor, json.loads(row["task"]))
            if (
                not isinstance(target, dict)
                or set(target) != {"channel", "expected"}
                or not isinstance(target["channel"], str)
                or not target["channel"]
                or len(target["channel"]) > 256
                or (target["expected"] is not None and not isinstance(target["expected"], str))
            ):
                raise NativeStoreError("Invalid installed delivery target")
            with self._transaction() as db:
                db.execute("INSERT OR IGNORE INTO native_workflow_targets VALUES (?,?)", (key, _json(target)))
                target = json.loads(
                    db.execute("SELECT target FROM native_workflow_targets WHERE task=?", (key,)).fetchone()[0]
                )
        self.publish(actor, key, target["channel"], target["expected"])
        accepted = self.complete(actor, key, target["channel"])
        return {"state": "accepted", "acceptance": accepted}

    def publish(self, actor, key, channel, expected):
        self._dependencies_current(actor, key)
        row = self.status(actor, key)
        task = self._valid(actor, row)
        self._allow(actor, row["issue"], "publish")
        if not callable(self.principals):
            raise NativeStoreError("Publisher installation unavailable")
        review = self.review(actor, key)
        publisher = self.principals(actor, row["issue"], "publisher")
        return self.release.publish(
            task["tenant"],
            publisher,
            "publish-" + key,
            task["product"],
            channel,
            review["id"],
            expected,
            guard=lambda native_db: self._publication_guard(actor, key, native_db),
        )

    @contextmanager
    def _publication_guard(self, actor, key, native_db):
        # Native writer first, domain writer second, matching complete().
        # Held through native commit, including other coordinator processes.
        with self._transaction() as db:
            row = self._row(db, key)
            task = self._valid(actor, row)
            self._allow(actor, row["issue"], "publish")
            if row["state"] != "produced":
                raise NativeStoreError("Confirmed producer terminal required")
            for acceptance in task["dependencies"].values():
                accepted = json.loads(acceptance)
                request = accepted["request"]
                if (
                    self.release.historical(
                        task["tenant"], actor, request["product"], request["channel"], accepted["id"]
                    )
                    != accepted
                ):
                    raise NativeStoreError("Dependency historical release invalid")
            _, policy = self.release._policy(native_db, task["tenant"], task["product"])
            if policy["checks"] != task["check_contexts"]:
                raise NativeStoreError("Release does not cover exact task criteria")
            yield

    def complete(self, actor, key, channel):
        # Serialize only the short local acceptance write against native review
        # revocation/policy/channel changes. No worker/check/network is inside.
        # Native writer guard precedes domain lock consistently; commits remain
        # separate, and a crash replays release readback rather than publication.
        with self.release.store._connection(write=True):
            return self._complete_guarded(actor, key, channel)

    def _complete_guarded(self, actor, key, channel):
        self._dependencies_current(actor, key)
        row = self.status(actor, key)
        task = json.loads(row["task"])
        if task.get("delivery_mode") == "contribution":
            raise NativeStoreError("Contribution requires atomic integration acceptance")
        if row["state"] == "accepted":
            with self._transaction() as db:
                self._valid(actor, self._row(db, key))
                self._allow(actor, row["issue"], "accept")
            accepted = json.loads(row["acceptance"])
            request = accepted["request"]
            if (
                channel != request["channel"]
                or self.release.historical(task["tenant"], actor, request["product"], channel, accepted["id"])
                != accepted
            ):
                raise NativeStoreError("Acceptance changed")
            return accepted
        # NativeRelease readback verifies current approval, contributor independence,
        # checks and policy. Caller cannot supply acceptance facts.
        selected = self.release.selected(task["tenant"], actor, task["product"], channel)
        terminal = json.loads(row["terminal"] or "null")
        if (
            not terminal
            or terminal["state"] != "produced"
            or not selected
            or selected["candidate"] != terminal["candidate"]
        ):
            raise NativeStoreError("Exact independent release required")
        with self.release.store._connection() as native_db:
            _, policy = self.release._policy(native_db, task["tenant"], task["product"])
            if policy["checks"] != task["check_contexts"]:
                raise NativeStoreError("Release does not cover exact task criteria")
        acceptance = _json(selected)
        with self._transaction() as db:
            row = self._row(db, key)
            self._valid(actor, row)
            self._allow(actor, row["issue"], "accept")
            if row["state"] == "accepted":
                if row["acceptance"] != acceptance:
                    raise NativeStoreError("Acceptance changed")
                return selected
            if row["state"] != "produced":
                raise NativeStoreError("Producer terminal required")
            db.execute("UPDATE native_tasks SET state='accepted',acceptance=? WHERE id=?", (acceptance, key))
            db.execute("UPDATE native_managed_issues SET acceptance=? WHERE issue_id=?", (acceptance, row["issue"]))
            db.execute("UPDATE issues SET status='done' WHERE id=?", (row["issue"],))
            self.domain._event(
                task["tenant"], "native.accepted", actor, row["issue"], {"task": key, "release": selected["id"]}
            )
            requirement = task["source"]["definition"]["requirement_id"]
            if requirement:
                self.domain.sync_progress(requirement, actor=actor)
            db.execute(
                "INSERT INTO native_outbox VALUES (?,?,?)",
                (key, task["tenant"], _json({"type": "dependency.changed", "reference": key})),
            )
        return selected
