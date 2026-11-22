"""Event driven native workflow; host installation supplies all privileged ports.

SQLite reservations are short. Workers/checks/release run after domain locks end.
Unknown intent survives restart and requires an authenticated owner receipt.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from concurrent.futures import Future
from contextlib import contextmanager, nullcontext
from pathlib import Path, PurePosixPath

from issue_flow import dependencies as issue_dependencies
from native_observations import model_observation
from native_store import NativeStoreError, _digest, _json, _object_name
from native_worker import worker_cancel_requested, worker_step_reporter
from native_workspace import portable
from tianxuan_core import PermissionDenied, StorageBusy, VersionConflict, _storage_error


class StageAuthorizationChanged(NativeStoreError):
    """A design task no longer has the stage authority used for dispatch."""


@contextmanager
def _worker_storage():
    """Keep storage faults on the workflow's recoverable error path."""
    try:
        yield
    except sqlite3.DatabaseError as error:
        raise NativeStoreError("Worker storage unavailable; reconcile the existing execution") from error


def write_resources(task, workspace):
    """Reserve planned shared assets or the producer's private contribution directory."""
    if not (task.get("shared_asset_writes") or task["source"]["definition"].get("stage_authorization")):
        return [workspace.as_posix()]
    resources = set()
    for module, scope in task["writes"].items():
        root = "/native-assets/" + task["tenant"] + "/" + module.casefold()
        if scope == "*":
            resources.add(root)
            continue
        try:
            resources.update(root + "/" + portable(name).casefold() for name in scope)
        except NativeStoreError:
            # Older admissions accepted arbitrary strings. Keep a conservative
            # claim for such a module until the original worker settles.
            resources.add(root)
    return sorted(resources)


class OccupiedWrites:
    """Index overlapping object paths and whole modules from one database snapshot."""

    def __init__(self, groups):
        self.paths = {PurePosixPath(path) for group in groups for path in group}
        self.parents = {parent for path in self.paths for parent in path.parents}

    def overlaps(self, resources):
        for resource in resources:
            path = PurePosixPath(resource)
            if path in self.paths or path in self.parents or not self.paths.isdisjoint(path.parents):
                return True
        return False


def execution_identity(key):
    # The pinned execution names its worker even across coordinator restarts.
    # This is the same address used by candidate intake, not a liveness claim.
    return {"id": key, "worker_ref": "native-worker:" + key}


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
        observe_catalog=None,
    ):
        if not callable(authorize) or type(capacity) is not int or not 1 <= capacity <= 1024:
            raise NativeStoreError("Trusted authority and positive capacity required")
        self.domain, self.worker, self.runner, self.release = domain, worker, runner, release
        self.authorize, self.capacity = authorize, capacity
        self.principals, self.review_candidate, self.installed_plan = principals, review_candidate, installed_plan
        self._executions = {}  # Exact local coordinator ownership; never inferred from a PID.
        self.next_issues = next_issues
        self.installed_target = installed_target
        self.observe_catalog = observe_catalog
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
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_edit_origins (task TEXT PRIMARY KEY, project TEXT NOT NULL, module_id TEXT NOT NULL)"
            )
            # Reinstall after the v1 table migration in this same writer transaction.
            db.execute("DROP TRIGGER IF EXISTS native_excludes_ordinary_flow")
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
            # Older domain stores exclude all issues with ordinary dependency edges.
            # Keep the exclusion for custom flows and legacy writers. Only this
            # transaction's active signed contract can take over its pinned edges.
            db.execute(
                "CREATE TRIGGER native_excludes_ordinary_flow BEFORE INSERT ON native_managed_issues "
                "WHEN EXISTS (SELECT 1 FROM issue_flows WHERE issue_id=NEW.issue_id AND definition IS NOT NULL) "
                "OR (EXISTS (SELECT 1 FROM issue_dependencies WHERE issue_id=NEW.issue_id) AND NOT EXISTS ("
                "SELECT 1 FROM native_active_tasks a JOIN native_tasks t ON t.id=a.task WHERE a.issue=NEW.issue_id "
                "AND json_extract(t.task,'$.source.revision')=NEW.definition "
                "AND json_type(t.task,'$.source.definition.stage_authorization')='object' "
                "AND json_type(t.task,'$.issue_prerequisites')='array')) "
                "BEGIN SELECT RAISE(ABORT,'ordinary workflow owns this issue'); END"
            )
            db.execute("CREATE TABLE IF NOT EXISTS native_outbox_consumed (id TEXT PRIMARY KEY)")
            db.execute("CREATE TABLE IF NOT EXISTS native_workflow_reviews (task TEXT PRIMARY KEY, receipt TEXT)")
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_workflow_targets (task TEXT PRIMARY KEY, target TEXT NOT NULL)"
            )
            db.execute("CREATE TABLE IF NOT EXISTS native_stage_results (task TEXT PRIMARY KEY, receipt TEXT NOT NULL)")
            db.execute("CREATE INDEX IF NOT EXISTS native_tasks_ready ON native_tasks(tenant,state,ready_at,id)")
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_task_progress ("
                "task TEXT NOT NULL, sequence INTEGER NOT NULL, state TEXT NOT NULL, step TEXT NOT NULL, "
                "details TEXT NOT NULL, receipt TEXT, recorded_at TEXT NOT NULL DEFAULT "
                "(strftime('%Y-%m-%dT%H:%M:%fZ','now')), PRIMARY KEY(task,sequence), UNIQUE(task,receipt))"
            )
            db.execute("CREATE TABLE IF NOT EXISTS native_run_controls (task TEXT PRIMARY KEY, intent TEXT NOT NULL)")
            # State changes can also originate in the remote adapter, stage
            # settlement or joint acceptance. Journal them in the same commit.
            for name, transition in (
                ("created", "AFTER INSERT ON native_tasks"),
                ("changed", "AFTER UPDATE OF state ON native_tasks WHEN NEW.state<>OLD.state"),
            ):
                db.execute(
                    f"CREATE TRIGGER IF NOT EXISTS native_progress_{name} {transition} BEGIN "
                    "INSERT INTO native_task_progress(task,sequence,state,step,details) "
                    "SELECT NEW.id,COALESCE(MAX(sequence),0)+1,NEW.state,'state',"
                    "CASE WHEN NEW.state IN ('produced','stage-reached','stage-unmet','accepted') THEN "
                    "json_object('candidate',json_extract(NEW.terminal,'$.candidate'),"
                    "'modules',json_extract(NEW.terminal,'$.modules')) ELSE '{}' END "
                    "FROM native_task_progress WHERE task=NEW.id; END"
                )
            # A pre-upgrade run has a known current state but no observed step history.
            db.execute(
                "INSERT INTO native_task_progress(task,sequence,state,step,details) "
                "SELECT id,1,state,'snapshot','{}' FROM native_tasks "
                "WHERE NOT EXISTS(SELECT 1 FROM native_task_progress WHERE task=native_tasks.id)"
            )

    @contextmanager
    def _transaction(self, *, write=True):
        with self.domain._connection_lock:
            db = self.domain.db
            if db.in_transaction:
                raise NativeStoreError("Workflow requires independent transaction")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
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
            try:
                authority = self.domain.task_stage_authority(actor, issue, source["revision"])
            except VersionConflict as exc:
                raise StageAuthorizationChanged(str(exc)) from exc
            if authority is not None:
                definition = {**source["definition"], "stage_authorization": authority}
                return {"definition": definition, "revision": _digest(_json(definition).encode())}
        return source

    def _row(self, db, key):
        row = db.execute("SELECT * FROM native_tasks WHERE id=?", (key,)).fetchone()
        if row is None:
            raise NativeStoreError("Native task unavailable")
        return {**row, **execution_identity(row["id"])}

    def status(self, actor, key):
        with self._transaction(write=False) as db:
            row = self._row(db, key)
            self._read_allowed(actor, row)
            task = json.loads(row["task"])
            row["progress"] = self._progress(db, row, task)
            if "stage_renewal" in task:
                row["stage_renewal"] = {"task": key, **task["stage_renewal"]}
            if task["source"]["definition"].get("stage_authorization"):
                saved = db.execute("SELECT receipt FROM native_stage_results WHERE task=?", (key,)).fetchone()
                if saved:
                    row["stage_result"] = json.loads(saved["receipt"])
                elif row["state"] == "produced":
                    row["stage_result"] = dict(
                        state="pending",
                        reason="awaiting_stage_check" if "stage_criteria" in task else "stage_criteria_check_unbound",
                    )
            return row

    def _progress(self, db, row, task):
        events = [
            {**event, "details": json.loads(event["details"])}
            for event in db.execute(
                "SELECT sequence,recorded_at,state,step,details FROM native_task_progress "
                "WHERE task=? ORDER BY sequence",
                (row["id"],),
            )
        ]
        grant = task["source"]["definition"].get("stage_authorization", {})
        terminal = json.loads(row["terminal"] or "{}")
        produced = row["state"] in {"produced", "stage-reached", "stage-unmet", "accepted"}
        observed = terminal if produced else {}
        if row["state"] == "failed":
            observed = terminal.get("observation", {})
        control = {}
        if not callable(getattr(self.worker, "reserve", None)):
            control["control"] = self._control_view(db, row, task, terminal, events[-1]["sequence"])
        return {
            **control,
            **execution_identity(row["id"]),
            "issue": row["issue"],
            "source_revision": task["source"]["revision"],
            "stage": grant.get("stage"),
            "state": row["state"],
            "candidate": terminal.get("candidate") if produced or row["state"] in {"paused", "cancelled"} else None,
            **model_observation(observed.get("provider_model"), observed.get("usage")),
            "events": events,
        }

    @staticmethod
    def _control_intent(db, key):
        result = db.execute("SELECT intent FROM native_run_controls WHERE task=?", (key,)).fetchone()
        return result[0] if result else None

    def _control_view(self, db, row, task, terminal, sequence):
        state = row["state"]
        intent = self._control_intent(db, row["id"])
        pending = state in {"running", "held", "closed-unresolved"}
        if intent and pending:
            state = {"pause": "pausing", "cancel": "canceling"}[intent]
        available = {
            "ready": ["pause", "cancel"],
            "reserved": ["pause", "cancel"],
            "running": ["pause", "cancel"],
            "pausing": ["cancel"],
            "paused": ["resume", "cancel"],
        }
        summaries = {
            "ready": "等待派发",
            "reserved": "已预约",
            "running": "工作者运行中",
            "pausing": "暂停已接收，等待当前工具完成",
            "canceling": "取消已接收，等待进程关闭",
            "paused": "已暂停",
            "cancelled": "已取消",
        }
        summary = summaries.get(state, state)
        if state == "paused":
            summary += "；原授权 " + task["mandate"] + "，来源修订 " + task["source"]["revision"]
            grant = task["source"]["definition"].get("stage_authorization")
            if grant:
                summary += (
                    "，确认人 " + grant["confirmed_by"] + "，阶段 " + grant["stage"] + "，验收条件 " + grant["criteria"]
                )
            if terminal:
                summary += "；工作者退出码 " + str(terminal.get("exit_code"))
                summary += "，输出记录 " + str(terminal.get("transcript"))
                if terminal.get("candidate"):
                    summary += "，已保存候选 " + terminal["candidate"]
            else:
                summary += "；尚未启动工作者"
        return dict(
            state=state,
            summary=summary,
            revision=sequence,
            actions=available.get(state, []),
        )

    def control_run(self, actor, operation, issue, key, expected, project=None):
        row = self.status(actor, key)
        task = json.loads(row["task"])
        if "control" not in row["progress"] or row["issue"] != issue or task["actor"] != actor:
            raise PermissionDenied("Current local run owner required")
        receipt = f"control.{operation}:{expected}"
        if operation == "resume":
            self._dependencies_current(actor, key)
            if row["state"] == "paused":
                self._valid(actor, row)
                self.worker.verify_pause_checkpoint(task, key, json.loads(row["terminal"] or "{}"))
        reviewed_state, reviewed_terminal = row["state"], row["terminal"]
        with self._transaction() as db:
            row = self._row(db, key)
            self._read_allowed(actor, row)
            self._allow(actor, issue, "control")
            current = db.execute("SELECT task FROM native_active_tasks WHERE issue=?", (issue,)).fetchone()
            if (
                not current
                or current[0] != key
                or (project is not None and self.domain.get_issue(issue)["project"] != project)
            ):
                raise NativeStoreError("Active issue run changed")
            replay = db.execute(
                "SELECT 1 FROM native_task_progress WHERE task=? AND receipt=?", (key, receipt)
            ).fetchone()
            if replay:
                return self._progress(db, row, task)
            progress = self._progress(db, row, task)
            control = progress["control"]
            if control["revision"] != expected or operation not in control["actions"]:
                raise NativeStoreError("Run changed; review current effects and authorization")
            state = row["state"]
            terminal = json.loads(row["terminal"] or "{}")
            if operation == "resume":
                self._valid(actor, row)
                if reviewed_state != "paused" or row["terminal"] != reviewed_terminal:
                    raise NativeStoreError("Reviewed worker checkpoint changed")
                if self.worker.installation(task["profile"]) != task["installation"]:
                    raise NativeStoreError("Original worker installation changed")
                # No process intent existed before a ready/reserved pause. A
                # drained worker can only continue its exact persisted terminal.
                state = terminal["state"] if terminal else "ready"
                db.execute("DELETE FROM native_run_controls WHERE task=?", (key,))
                if state == "produced":
                    db.execute("UPDATE issues SET status='in-review' WHERE id=?", (issue,))
            else:
                db.execute("INSERT OR REPLACE INTO native_run_controls VALUES (?,?)", (key, operation))
                if state not in {"running", "held", "closed-unresolved"}:
                    state = "paused" if operation == "pause" else "cancelled"
            db.execute("UPDATE native_tasks SET state=? WHERE id=?", (state, key))
            db.execute(
                "INSERT INTO native_task_progress(task,sequence,state,step,details,receipt) "
                "SELECT ?,MAX(sequence)+1,?,?,?,? FROM native_task_progress WHERE task=?",
                (
                    key,
                    state,
                    "control." + operation,
                    _json({"actor": actor, "reviewed_sequence": expected}),
                    receipt,
                    key,
                ),
            )
            result = self._progress(db, self._row(db, key), task)
        callback = getattr(self, "on_state_change", None)
        if callback:
            callback()
        return result

    def _control_settlement(self, db, key, state):
        intent = self._control_intent(db, key)
        if intent == "cancel" and state in {"produced", "failed"}:
            return "cancelled"
        if intent == "pause" and state == "produced":
            return "paused"
        return state

    def issue_detail(self, actor, project, number):
        # Resolve the issue revision, active execution and current visibility
        # in one SQLite snapshot, including when other coordinators are writing.
        with self._transaction(write=False) as db:
            detail = self.domain.read_issue_detail(actor, project, number)
            active = db.execute("SELECT task FROM native_active_tasks WHERE issue=?", (detail["id"],)).fetchone()
            progress = None
            actions = []
            if active:
                row = self._row(db, active["task"])
                try:
                    self._read_allowed(actor, row)
                except PermissionDenied:
                    pass  # The issue can be visible while the pinned design is private.
                else:
                    task = json.loads(row["task"])
                    progress = self._progress(db, row, task)
                    if actor == task["actor"] and self.domain.actor_context(actor)["role"] != "viewer":
                        actions = progress.get("control", {}).get("actions", [])
            return {**detail, "execution_progress": progress, "execution_control_actions": actions}

    def _record_step(self, key, step, details, receipt=None):
        """Installed tool receiver. An already observed receipt cannot advance a run."""
        with self._transaction() as db:
            self._append_step(db, key, step, details, receipt or step)

    @staticmethod
    def _append_step(db, key, step, details, receipt):
        encoded = _json(details)
        old = db.execute(
            "SELECT step,details FROM native_task_progress WHERE task=? AND receipt=?", (key, receipt)
        ).fetchone()
        if old:
            if (old["step"], old["details"]) != (step, encoded):
                raise NativeStoreError("Progress receipt rebound")
            return
        db.execute(
            "INSERT INTO native_task_progress(task,sequence,state,step,details,receipt) "
            "SELECT id,(SELECT COALESCE(MAX(sequence),0)+1 FROM native_task_progress WHERE task=?),state,?,?,? "
            "FROM native_tasks WHERE id=? AND state IN ('reserved','running','held','closed-unresolved')",
            (key, step, encoded, receipt, key),
        )

    def edit_baseline(self, actor, key, module, path):
        """Compare one writable object with the immutable revision selected at task admission."""
        _object_name(path)
        if not isinstance(module, str):
            raise NativeStoreError("Invalid edit module")
        with self._transaction() as db:
            row = self._row(db, key)
            self._read_allowed(actor, row)
            task = json.loads(row["task"])
            scope = task["writes"].get(module)
            if scope is None or (scope != "*" and path not in scope):
                raise PermissionDenied("Object outside this task's writable scope")
            origin = db.execute("SELECT project,module_id FROM native_edit_origins WHERE task=?", (key,)).fetchone()
            initial = task["selected"][module]
            tenant = row["tenant"]
        store = self.worker.store
        latest = store.head(tenant, module)
        initial_objects = store.revision(tenant, module, initial)["objects"]
        latest_objects = initial_objects if latest == initial else store.revision(tenant, module, latest)["objects"]
        return {
            "task": key,
            "project": origin["project"] if origin else None,
            "business_module": origin["module_id"] if origin else None,
            "module": module,
            "path": path,
            "initial": {"revision": initial, "sha256": initial_objects.get(path)},
            "latest": {"revision": latest, "sha256": latest_objects.get(path)},
        }

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

    def _issue_inputs(self, actor, issue):
        """Read the I04 graph under the domain lock, including its native release bindings."""
        bindings = {}
        prerequisites = issue_dependencies(self.domain, actor, issue)
        for prerequisite in prerequisites:
            if not prerequisite["accepted"]:
                raise NativeStoreError("Issue prerequisite has not been accepted")
            row = self.domain.db.execute(
                "SELECT t.* FROM native_active_tasks a JOIN native_tasks t ON t.id=a.task WHERE a.issue=?",
                (prerequisite["id"],),
            ).fetchone()
            if row is not None:
                self._read_allowed(actor, row)
                if row["state"] != "accepted" or not row["acceptance"]:
                    raise NativeStoreError("Issue prerequisite lacks exact accepted output")
                bindings[row["id"]] = row["acceptance"]
        return [p["id"] for p in prerequisites], bindings

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
        stage_criteria=None,
        shared_asset_writes=False,
        _renewal=None,
        _completion=None,
    ):
        source = self._allow(actor, issue, "authorize")
        authority = source["definition"].get("stage_authorization", {})
        if stage != authority.get("stage"):
            raise NativeStoreError("Installed plan stage must match the confirmed target")
        if stage_criteria is not None and stage_criteria != authority.get("criteria"):
            raise NativeStoreError("Installed stage checks must cover the confirmed criteria")
        if _renewal:
            if authority != _renewal["authorization"] or stage_criteria != authority["criteria"]:
                raise NativeStoreError("Stage renewal requires installed checks for the new signed criteria")
            selected = {**selected, **_renewal["from"]["modules"]}
        if delivery_mode not in {"standalone", "contribution"}:
            raise NativeStoreError("Unsupported delivery mode")
        if not isinstance(shared_asset_writes, bool):
            raise NativeStoreError("Shared asset scheduling requires a boolean")
        if not mandate or not checks or profile not in self.worker.profiles:
            raise NativeStoreError("Installed profile, checks and mandate required")
        tenant = source["definition"]["tenant_id"]
        with self.domain._connection_lock:
            prerequisites, issue_inputs = self._issue_inputs(actor, issue)
        if issue_inputs:
            selected, dependencies = dict(selected), dict(dependencies)
            for ticket, acceptance in issue_inputs.items():
                if dependencies.setdefault(ticket, acceptance) != acceptance:
                    raise NativeStoreError("Issue dependency acceptance changed")
                for module, revision in json.loads(acceptance)["modules"].items():
                    if selected.setdefault(module, revision) != revision:
                        raise NativeStoreError("Installed plan conflicts with accepted dependency output")
        if _completion is not None and _completion not in dependencies:
            return None  # A legacy resolver may enumerate other already-resolved branches.
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
        for scope in writes.values():
            if scope != "*":
                for name in scope:
                    portable(name)
        installation = self.worker.installation(profile)
        capabilities = [] if capabilities is None else capabilities
        if (
            not isinstance(capabilities, list)
            or len(capabilities) > 32
            or not all(isinstance(c, str) and c for c in capabilities)
        ):
            raise NativeStoreError("Invalid required capabilities")
        issue_capabilities = source["definition"].get("required_capabilities", [])
        if issue_capabilities:
            capabilities = capabilities + [c for c in issue_capabilities if c not in capabilities]
            if len(capabilities) > 32 or not all(c.strip() for c in issue_capabilities):
                raise NativeStoreError("Invalid required capabilities on issue")
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
            **({"issue_prerequisites": prerequisites} if prerequisites else {}),
            profile=profile,
            product=product,
            checks=checks,
            mandate=mandate,
            delivery_mode=delivery_mode,
            **({"shared_asset_writes": True} if shared_asset_writes and not authority else {}),
            **({"stage_criteria": stage_criteria} if stage_criteria is not None else {}),
            **({"stage_renewal": _renewal} if _renewal else {}),
            **({"previous": expected} if expected is not None else {}),
        )
        key = _digest(_json(task).encode())
        # Hold the native writer until admission commits, in the same lock order
        # as stage settlement. Evidence withdrawal cannot race the new decision.
        native_lock = self.runner.store._connection(write=True) if _renewal else nullcontext()
        with native_lock as native_db, self._transaction() as db:
            if self._allow(actor, issue, "authorize") != source or self._issue_inputs(actor, issue) != (
                prerequisites,
                issue_inputs,
            ):
                raise NativeStoreError("Source changed")
            if db.execute(
                "SELECT 1 FROM issue_flows WHERE issue_id=? AND definition IS NOT NULL", (issue,)
            ).fetchone() or (prerequisites and not authority):
                raise NativeStoreError("Ordinary workflow owns this issue")
            if (
                _completion is not None
                and not db.execute("SELECT 1 FROM native_active_tasks WHERE task=?", (_completion,)).fetchone()
            ):
                return None
            for dependency, acceptance in dependencies.items():
                row = self._row(db, dependency)
                self._read_allowed(actor, row)
                if (
                    row["tenant"] != tenant
                    or row["state"] != "accepted"
                    or row["acceptance"] != acceptance
                    or not acceptance
                ):
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
                previous_row = self._row(db, expected)
                previous_task = json.loads(previous_row["task"])
                previous_grant = previous_task["source"]["definition"].get("stage_authorization")
                if _renewal:
                    self._check_stage_basis(native_db, previous_row, previous_task, _renewal["from"])
                if previous_grant and previous_grant["stage"] != stage_authority["stage"]:
                    if previous_row["state"] == "stage-reached" and not _renewal:
                        raise NativeStoreError("Reached stage requires explicit renewal")
                    if previous_row["state"] == "stage-unmet":
                        raise NativeStoreError("Unmet stage cannot advance")
                if previous_grant == stage_authority:
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
                "INSERT INTO native_edit_origins(task,project,module_id) SELECT ?,project,module_id FROM issues WHERE id=?",
                (key, issue),
            )
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
        # Delivery and transport callbacks can validate on different threads.
        with self.domain._connection_lock:
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
            prerequisites, issue_inputs = self._issue_inputs(actor, row["issue"])
            if prerequisites != task.get("issue_prerequisites", []) or any(
                task["dependencies"].get(k) != v for k, v in issue_inputs.items()
            ):
                raise NativeStoreError("Issue dependency acceptance changed")
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

    def installed_catalog(self):
        if self.observe_catalog is None:
            # Direct local workers own their fixed argv. A configured descriptor
            # cannot make a missing executable eligible. Remote workers own their
            # installation checks on the enrolled node.
            catalog = []
            for model in self.catalog:
                profile = self.worker.profiles.get(model["id"])
                if not profile or ("argv" in profile and not Path(profile["argv"][0]).is_file()):
                    model = {
                        **model,
                        "configured": model.get("available") is True,
                        "available": False,
                        "localStatus": {"status": "installation_missing"},
                    }
                catalog.append(model)
            return catalog
        try:
            observed = self.observe_catalog()
        except (OSError, EOFError, ValueError, KeyError, NativeStoreError):
            observed = {}
        catalog = []
        for model in self.catalog:
            configured = model.get("available") is True
            status = observed.get(model["id"], {"status": "installation_unconfirmed"})
            available = configured and status["status"] in {"ready", "validation_probe"}
            catalog.append({**model, "configured": configured, "available": available, "localStatus": status})
        return catalog

    def _schedulable(self, task, catalog, target="agent"):
        return target == "agent" and any(
            model.get("id") == task["profile"]
            and model.get("available") is True
            and target in model.get("targets", [])
            and all(c in model.get("capabilities", []) for c in task["capabilities"])
            for model in catalog
        )

    @staticmethod
    def _held(db):
        return db.execute(
            "SELECT id,issue,task,tenant,state FROM native_tasks WHERE state IN ('reserved','running','held') ORDER BY id"
        ).fetchall()

    def inspect(self, actor):
        catalog = self.installed_catalog()
        with self._transaction() as db:
            tenant = self.domain.actor_context(actor)["tenant"]
            rows = db.execute(
                "SELECT * FROM native_tasks WHERE tenant=? AND state='ready' ORDER BY ready_at,id LIMIT 1024", (tenant,)
            ).fetchall()
            items, ready, sources, active, requests = [], [], [], [], []
            claims = []
            for index, held_row in enumerate(self._held(db)):
                writes = (
                    write_resources(json.loads(held_row["task"]), self.worker.root / held_row["id"])
                    if held_row["tenant"] == tenant
                    else []
                )
                claims.append(writes)
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
                    "writes": writes if visible else [],
                })
            occupied = OccupiedWrites(claims)
            for row in rows:
                try:
                    task = self._valid(actor, row)
                except (PermissionDenied, NativeStoreError):
                    continue
                key = row["id"]
                writes = write_resources(task, self.worker.root / key)
                waiting = occupied.overlaps(writes)
                source = {"source": key, "revision": task["source"]["revision"]}
                sources.append(source)
                items.append({
                    "key": key,
                    "source": key,
                    "dispatchCandidate": not waiting,
                    **({"waitReason": "resource_conflict"} if waiting else {}),
                })
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
                        writes=writes,
                        model=task["profile"],
                    )
                )
            return dict(
                snapshot=dict(items=items, ready=ready, sourceSnapshots=sources),
                environment=dict(catalog=catalog, active=active, capacity=self.capacity),
                requests=requests,
                produced=self._produced_visible(actor, tenant, stage=False),
                stage_checks=self._produced_visible(actor, tenant, stage=True),
            )

    def _produced_visible(self, actor, tenant, *, stage):
        keys = []
        binding = (
            "json_extract(task,'$.stage_criteria') IS NOT NULL"
            if stage
            else "json_extract(task,'$.source.definition.stage_authorization') IS NULL"
        )
        for row in self.domain.db.execute(
            f"SELECT * FROM native_tasks WHERE tenant=? AND state='produced' AND {binding} ORDER BY ready_at,id LIMIT 1024",
            (tenant,),
        ).fetchall():
            try:
                self._valid(actor, row)
            except (PermissionDenied, NativeStoreError):
                continue
            keys.append(row["id"])
        return keys

    def reserve(self, actor, assignment):
        self._dependencies_current(actor, assignment["ticket"])
        catalog = self.installed_catalog()
        with self._transaction() as db:
            row = self._row(db, assignment["ticket"])
            task = self._valid(actor, row)
            if row["state"] != "ready":
                return False
            if not self._schedulable(task, catalog, assignment.get("target", "agent")):
                return False
            held = self._held(db)
            if len(held) >= self.capacity:
                return False
            occupied = OccupiedWrites(
                write_resources(json.loads(other["task"]), self.worker.root / other["id"])
                for other in held
                if other["tenant"] == row["tenant"]
            )
            writes = write_resources(task, self.worker.root / row["id"])
            if occupied.overlaps(writes):
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
                if not self._schedulable(waiting_task, catalog) or occupied.overlaps(
                    write_resources(waiting_task, self.worker.root / waiting["id"])
                ):
                    continue
                available_node = getattr(self.worker, "available_node", None)
                if available_node is not None and available_node(db, waiting_task) is None:
                    continue
                return False  # Durable FIFO, including competing dispatcher processes.
            expected = {"source": row["id"], "revision": task["source"]["revision"]}
            if assignment["sourceSnapshot"] != expected or assignment["model"]["id"] != task["profile"]:
                raise NativeStoreError("Untrusted assignment")
            if self.observe_catalog is not None:
                model = next(m for m in catalog if m["id"] == task["profile"])
                assignment = {
                    **assignment,
                    "model": {
                        "id": model["id"],
                        "capabilities": task["capabilities"],
                        "reason": "installed_profile_and_required_capabilities",
                        "localStatus": model["localStatus"],
                    },
                }
            assignment = {**assignment, "reads": [], "writes": writes}
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
        if row["state"] == "closed-unresolved":
            raise NativeStoreError("Worker process closed; output receipt unresolved")
        if row["state"] in {"reserved", "running", "held"}:
            raise NativeStoreError("Terminal event ownership unavailable; physical state remains unknown")
        with self._transaction(write=False) as db:
            row = self._row(db, key)
            self._valid(actor, row)
        return row

    def execute_receipt(self, actor, key):
        retry_available = True
        while True:
            try:
                return {**self.execute(actor, key), **execution_identity(key)}
            except (sqlite3.OperationalError, StorageBusy) as error:
                if isinstance(error, sqlite3.OperationalError) and not isinstance(_storage_error(error), StorageBusy):
                    raise
                try:
                    observation = self._execution_fault(actor, key, "storage-busy", retry_available, record=True)
                except sqlite3.OperationalError as journal_error:
                    raise _storage_error(journal_error) from journal_error
                if observation["next_action"] != "retry-same-execution":
                    raise StorageBusy(observation["recovery_condition"]) from error
                retry_available = False

    def execution_readback(self, actor, key, *, issues=None):
        """An ambiguous transport response can only initiate a read of the original execution."""
        return self._execution_fault(actor, key, "response-unknown", False, record=False, issues=issues)

    def record_execution_fault(self, actor, key, *, issues=None):
        # Only the server constructs the audit payload from authorized durable state.
        try:
            return self._execution_fault(actor, key, "response-unknown", False, record=True, issues=issues)
        except sqlite3.OperationalError as error:
            raise _storage_error(error) from error

    def _execution_fault(self, actor, key, reason, allow_retry, *, record, issues=None):
        with self._transaction(write=record) as db:
            row = self._row(db, key)
            self._read_allowed(actor, row)
            if issues is not None and row["issue"] not in issues:
                raise NativeStoreError("Execution is outside this entry")
            self._allow(actor, row["issue"], "reconcile")
            state = row["state"]
            terminal = json.loads(row["terminal"] or "{}")
            action = "read-original-receipt"
            condition = "Observe the original worker or obtain its authoritative terminal receipt."
            external_reservation = callable(getattr(self.worker, "reserve", None))
            if state == "reserved" and key not in self._executions and allow_retry and not external_reservation:
                self._valid(actor, row)
                action = "retry-same-execution"
                condition = "The original reservation is current and the execution intent has not started."
            elif terminal:
                condition = "The original execution has a recorded terminal receipt."
            elif state == "reserved" and external_reservation:
                condition = "Read the original worker adapter's reservation and terminal receipt."
            elif state == "reserved" and reason == "storage-busy":
                condition = "Confirm storage is writable and recheck the original reservation before continuing."
            observation = {
                **execution_identity(key),
                "operation": "execute",
                "reason": reason,
                "state": state,
                "known_effects": {
                    "reservation_recorded": bool(row["assignment"]),
                    "exit_code": terminal.get("exit_code"),
                    "candidate": terminal.get("candidate"),
                },
                "next_action": action,
                "recovery_condition": condition,
            }
            if record:
                self.domain._event(row["tenant"], "native.execution-recovery", actor, row["issue"], observation)
            return observation

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
        catalog = self.installed_catalog() if self.observe_catalog is not None else None
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
            if stale is None and catalog is not None and not self._schedulable(task, catalog):
                # Local reservation only. No physical execution intent has been recorded.
                db.execute("UPDATE native_tasks SET state='ready',assignment=NULL WHERE id=?", (key,))
                return self._row(db, key)
            if stale is None:
                db.execute("UPDATE native_tasks SET state='running' WHERE id=?", (key,))
                db.execute("UPDATE issues SET status='in-progress' WHERE id=?", (row["issue"],))
                self.domain._event(task["tenant"], "native.started", actor, row["issue"], {"task": key})
        if stale is not None:
            raise stale
        try:
            # Read the exact durable run intent on the existing owned process
            # supervision loop, including requests accepted by another coordinator.
            def cancelled():
                with self.domain._connection_lock:
                    return self._control_intent(self.domain.db, key) == "cancel"

            cancellation = worker_cancel_requested.set(cancelled)
            reporter = worker_step_reporter.set(self._record_step)
            try:
                with _worker_storage():
                    terminal = self.worker.run(task, key)
            finally:
                worker_step_reporter.reset(reporter)
                worker_cancel_requested.reset(cancellation)
            if terminal is None:
                return self.status(actor, key)
        except BaseException:
            with self._transaction() as db:
                db.execute("UPDATE native_tasks SET state='held' WHERE id=? AND state='running'", (key,))
            raise
        with self._transaction() as db:
            current = self._row(db, key)
            if current["state"] not in {"running", "held", "closed-unresolved"}:
                if current["state"] == terminal["state"] and current["terminal"] == _json(terminal):
                    return terminal
                return current  # Concurrent reconciliation may already have settled the stage.
            try:
                self._valid(actor, current)
                state = terminal["state"]
            except (PermissionDenied, NativeStoreError):
                state = "stopped"
            self._terminal_progress(db, key, state, terminal)
            state = self._control_settlement(db, key, state)
            db.execute("UPDATE native_tasks SET state=?,terminal=? WHERE id=?", (state, _json(terminal), key))
            if state in {"produced", "failed"}:
                db.execute(
                    "UPDATE issues SET status=? WHERE id=?",
                    ("in-review" if terminal["state"] == "produced" else "blocked", row["issue"]),
                )
            self.domain._event(task["tenant"], "native.terminal", actor, row["issue"], {"task": key, "state": state})
        return {**terminal, "state": state}

    def _terminal_progress(self, db, key, state, terminal):
        if state not in {"produced", "failed"} or terminal is None:
            return
        if "transcript" in terminal:
            self._append_step(
                db, key, "process.closed", {k: terminal[k] for k in ("exit_code", "transcript")}, "process.closed"
            )
        if state == "produced":
            self._append_step(
                db, key, "candidate.compose", {k: terminal[k] for k in ("candidate", "modules")}, "candidate.compose"
            )

    def _dependencies_current(self, actor, key):
        row = self.status(actor, key)
        task = json.loads(row["task"])
        for dependency, acceptance in task["dependencies"].items():
            upstream = self.status(actor, dependency)
            accepted = json.loads(acceptance)
            if upstream["acceptance"] != acceptance or upstream["state"] != "accepted":
                raise NativeStoreError("Dependency acceptance changed")
            self._accepted_release(task["tenant"], actor, accepted)

    def _accepted_release(self, tenant, actor, accepted):
        request = accepted["request"]
        if self.release.historical(tenant, actor, request["product"], request["channel"], accepted["id"]) != accepted:
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
            with _worker_storage():
                terminal = self.worker.reconcile(task, key)
        except NativeStoreError as error:
            # Storage or content authorization can fail after the process exits.
            # Only the separate physical receipt can settle its capacity then.
            terminal, failure = None, str(error)
        if terminal is None:
            with _worker_storage():
                closed = self.worker.process_closed(task, key)
            if not closed:
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
                self._terminal_progress(db, key, state, terminal)
                if terminal is not None:
                    state = self._control_settlement(db, key, state)
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

    def advance(self, actor, *, isolate=False, exclude=(), completion=None, owned_issues=None):
        """Consume actual acceptance events. Installed graph resolver supplies issues.

        Authorizing a dependent uses pinned accepted outputs returned by the installed
        plan. Failed consumption is replayable; no background scans or model polling.
        """
        if not callable(self.next_issues) and not callable(self.installed_plan):
            return {"authorized": [], "errors": []} if isolate else []
        with self._transaction() as db:
            tenant = self.domain.actor_context(actor)["tenant"]
            events = [
                dict(r)
                for r in db.execute(
                    "SELECT o.*,t.issue FROM native_outbox o JOIN native_tasks t ON t.id=o.id WHERE o.tenant=? "
                    "AND EXISTS (SELECT 1 FROM native_active_tasks a WHERE a.issue=t.issue AND a.task=t.id) "
                    "AND (? IS NULL OR o.id=?) AND o.id NOT IN (SELECT id FROM native_outbox_consumed) ORDER BY o.rowid",
                    (tenant, completion, completion),
                ).fetchall()
            ]
        results, errors = [], []
        for event in events:
            if event["id"] in exclude or (owned_issues is not None and event["issue"] not in owned_issues):
                continue
            try:
                upstream = self.status(actor, event["id"])
            except PermissionDenied:
                continue  # Preserve private pending events without exposing identifiers.
            try:
                if upstream["state"] != "accepted" or not upstream["acceptance"]:
                    raise NativeStoreError("Dependency event lacks exact acceptance")
                issues = self.next_issues(actor, json.loads(event["payload"])) if self.next_issues else []
                if issues is None:
                    continue  # The installed entry owns this event in another dispatch context.
                if not isinstance(issues, list) or len(issues) > 1024 or not all(isinstance(i, str) for i in issues):
                    raise NativeStoreError("Invalid installed dependency event response")
                self._accepted_release(event["tenant"], actor, json.loads(upstream["acceptance"]))
                # A signed I04 successor can be installed independently of an entry planner.
                with self._transaction(write=False) as db:
                    signed = [
                        r[0]
                        for r in db.execute(
                            "SELECT d.issue_id FROM issue_dependencies d JOIN design_task_sources s "
                            "ON s.issue_id=d.issue_id LEFT JOIN native_active_tasks a ON a.issue=d.issue_id "
                            "LEFT JOIN issue_flows f ON f.issue_id=d.issue_id "
                            "WHERE d.dependency=? AND a.task IS NULL AND f.definition IS NULL ORDER BY d.issue_id",
                            (event["issue"],),
                        )
                    ]
                admitted = []
                inaccessible = False
                for issue in dict.fromkeys([*issues, *signed]):
                    if owned_issues is not None and issue not in owned_issues:
                        continue
                    if issue in signed:
                        try:
                            self._allow(actor, issue, "authorize")
                            with self.domain._connection_lock:
                                if not all(d["accepted"] for d in issue_dependencies(self.domain, actor, issue)):
                                    continue
                        except PermissionDenied:
                            inaccessible = True
                            continue
                        except StageAuthorizationChanged:
                            continue
                    ticket = self.authorize_installed(actor, issue, _completion=event["id"])
                    if ticket is not None:
                        admitted.append(ticket)
                if inaccessible:
                    # The active ticket protects work already admitted. A recipient
                    # with access can later consume the remaining private branch.
                    results.extend(admitted)
                    continue
                with self._transaction() as db:
                    if db.execute("INSERT OR IGNORE INTO native_outbox_consumed VALUES (?)", (event["id"],)).rowcount:
                        results.extend(admitted)
            except Exception as error:
                if not isolate:
                    raise
                errors.append({"event": event["id"], "reason": type(error).__name__})
        return {"authorized": results, "errors": errors} if isolate else results

    def check(self, actor, key):
        self._dependencies_current(actor, key)
        row = self.status(actor, key)
        task = self._valid(actor, row)
        return self._run_checks(actor, key, row, task)

    def _run_checks(self, actor, key, row, task):
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

    def verify_stage(self, actor, key):
        """Settle only the signed stage, using its installed checks on the physical candidate."""
        row = self.status(actor, key)
        task = self._valid(actor, row)
        grant = task["source"]["definition"].get("stage_authorization")
        if not grant or task.get("stage_criteria") != grant["criteria"]:
            raise NativeStoreError("Installed checks for the exact authorized criteria required")
        if row["state"] in {"stage-reached", "stage-unmet"}:
            return row["stage_result"]
        self._dependencies_current(actor, key)
        facts = self._run_checks(actor, key, row, task)
        terminal = json.loads(row["terminal"])
        candidate = terminal["candidate"]
        # Use the same native-writer then domain-writer order as release readback.
        # A revoked check or changed signature cannot race the recorded decision.
        with self.runner.store._connection(write=True) as native_db, self._transaction() as db:
            current = self._row(db, key)
            self._valid(actor, current)
            self._allow(actor, row["issue"], "check")
            if current["state"] in {"stage-reached", "stage-unmet"}:
                saved = db.execute("SELECT receipt FROM native_stage_results WHERE task=?", (key,)).fetchone()
                return json.loads(saved["receipt"])
            if current["state"] != "produced" or current["terminal"] != row["terminal"]:
                raise NativeStoreError("Stage candidate changed")
            # A produced candidate lives on its private branch until publication.
            # The writable source may still be at the admitted base across successive stages.
            origin = task
            while origin.get("stage_renewal"):
                previous = self._row(db, origin["stage_renewal"]["from"]["task"])
                origin = json.loads(previous["task"])
            for module in task["writes"]:
                head = native_db.execute(
                    "SELECT revision FROM native_heads WHERE tenant=? AND module=?", (row["tenant"], module)
                ).fetchone()
                if head is None or head["revision"] not in {
                    origin["selected"].get(module),
                    task["selected"][module],
                    terminal["modules"][module],
                }:
                    raise NativeStoreError("Stage check target revision has changed")
            checks = {}
            for name, fact in facts.items():
                if (
                    fact["state"] not in {"complete", "cached"}
                    or not fact.get("evidence")
                    or fact["candidate"] != candidate
                    or fact["context"] != task["check_contexts"][name]
                ):
                    raise NativeStoreError("Stage check outcome unresolved")
                passed = fact.get("outcome") != "failed"
                if passed:
                    current_evidence = self.runner.cache.lookup(
                        task["tenant"], candidate, name, **task["check_contexts"][name]
                    )
                    if current_evidence is None or current_evidence["evidence"]["id"] != fact["evidence"]:
                        raise NativeStoreError("Stage check evidence unavailable")
                checks[name] = dict(evidence=fact["evidence"], outcome="passed" if passed else "failed")
            reached = all(check["outcome"] == "passed" for check in checks.values())
            receipt = dict(
                task=key,
                authorization=grant,
                candidate=candidate,
                modules=terminal["modules"],
                checks=checks,
                state="stage-reached" if reached else "stage-unmet",
                reason="authorized_stage_criteria_met" if reached else "authorized_stage_check_failed",
            )
            db.execute("INSERT INTO native_stage_results VALUES (?,?)", (key, _json(receipt)))
            db.execute("UPDATE native_tasks SET state=? WHERE id=?", (receipt["state"], key))
            self.domain._event(task["tenant"], "native." + receipt["state"], actor, task["issue"], {"task": key})
        return receipt

    @staticmethod
    def require_delivery(task, row):
        if task["source"]["definition"].get("stage_authorization") and row["state"] != "accepted":
            raise NativeStoreError("Signed task is limited to its authorized stage")

    def authorize_installed(self, actor, issue, *, expected=None, _completion=None):
        self._allow(actor, issue, "authorize")
        if not callable(self.installed_plan):
            raise NativeStoreError("No admitted native plan installed")
        plan = self.installed_plan(actor, issue)
        return self.authorize_task(actor, issue, expected=expected, _completion=_completion, **plan)

    def renew_stage(self, actor, key, target_revision, confirmation_revision):
        """Use the reached ticket's immutable output as the next installed plan's baseline."""
        row = self.status(actor, key)
        result = row.get("stage_result")
        if row["state"] != "stage-reached" or not result or result["state"] != "stage-reached":
            raise NativeStoreError("Checked, reached predecessor required")
        issue = row["issue"]
        grant = self._allow(actor, issue, "authorize")["definition"].get("stage_authorization")
        previous = result["authorization"]
        if not grant or any(grant[k] != previous[k] for k in ("issue_id", "document_id", "version", "issue_revision")):
            raise NativeStoreError("Renewal must continue the same signed design and issue revision")
        if grant["confirmed_by"] != actor:
            raise PermissionDenied("Only the current confirmed responsible user may renew this stage")
        if (
            grant["target_revision"] != target_revision
            or grant["confirmation_revision"] != confirmation_revision
            or target_revision <= previous["target_revision"]
            or confirmation_revision <= previous["confirmation_revision"]
            or grant["stage"] == previous["stage"]
        ):
            raise NativeStoreError("Current confirmation of a new target stage required")
        renewal = {"from": result, "authorization": grant}
        # A lost response can be recovered after restart or installation changes.
        # Re-read the active ticket and current signature in the same transaction.
        with self._transaction() as db:
            self._read_allowed(actor, row)
            if self._allow(actor, issue, "authorize")["definition"].get("stage_authorization") != grant:
                raise NativeStoreError("Stage confirmation changed")
            active = db.execute("SELECT task FROM native_active_tasks WHERE issue=?", (issue,)).fetchone()
            if active and active["task"] != key:
                successor = self._row(db, active["task"])
                self._read_allowed(actor, successor)
                if json.loads(successor["task"]).get("stage_renewal") == renewal:
                    return {"task": successor["id"], **renewal}
                raise NativeStoreError("Predecessor is no longer the active stage")
        if not callable(self.installed_plan):
            raise NativeStoreError("No admitted native plan installed")
        plan = self.installed_plan(actor, issue)
        successor_key = self.authorize_task(actor, issue, expected=key, _renewal=renewal, **plan)
        return {"task": successor_key, **renewal}

    def _check_stage_basis(self, db, row, task, result):
        terminal = json.loads(row["terminal"])
        if (
            row["state"] != "stage-reached"
            or result["task"] != row["id"]
            or result["authorization"] != task["source"]["definition"]["stage_authorization"]
            or result["candidate"] != terminal["candidate"]
            or result["modules"] != terminal["modules"]
            or set(result["checks"]) != set(task["checks"])
        ):
            raise NativeStoreError("Reached stage receipt no longer matches its checked output")
        for name, check in result["checks"].items():
            evidence = self.runner.cache._evidence(db, row["tenant"], check["evidence"])
            withdrawn = db.execute(
                "SELECT 1 FROM native_check_revocations WHERE tenant=? AND evidence_id=?",
                (row["tenant"], evidence["id"]),
            ).fetchone()
            if withdrawn or evidence["outcome"] != "passed" or evidence["binding"]["check"] != name:
                raise NativeStoreError("Reached stage check evidence withdrawn or invalid")

    def review(self, actor, key):
        self._dependencies_current(actor, key)
        row = self.status(actor, key)
        task = self._valid(actor, row)
        self.require_delivery(task, row)
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
        task = json.loads(row["task"])
        self.require_delivery(task, row)
        if task.get("delivery_mode") == "contribution":
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
        self.require_delivery(task, row)
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
            self.require_delivery(task, row)
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
        self.require_delivery(task, row)
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
