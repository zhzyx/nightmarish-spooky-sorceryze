"""Installed, event-driven FIFO admission using existing native integration ports.

The OS lock is a nonblocking publisher lock, never a producer/intake lock.
Durable intents in NativeIntegration/CheckRunner remain authoritative after death.
"""

import asyncio
import json
import os
import time
import uuid
from concurrent.futures import Future
from contextlib import contextmanager
from functools import wraps
from pathlib import Path

from native_store import Conflict, NativeStoreError, _json
from tianxuan_core import PermissionDenied


def digest(value):
    from native_integration import digest as checksum

    return checksum(value)


@contextmanager
def publisher_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.seek(0)
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        locked = False
        try:
            if os.name == "nt":
                import msvcrt

                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    locked = True
                except OSError:
                    pass
            else:
                import fcntl

                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked = True
                except BlockingIOError:
                    pass
            yield locked
        finally:
            if locked:
                handle.seek(0)
                if os.name == "nt":
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle, fcntl.LOCK_UN)


def domain_locked(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self.w.domain._connection_lock:
            return method(self, *args, **kwargs)

    return call


class ContinuousIntegration:
    def __init__(self, integration, installed):
        if not callable(installed):
            raise NativeStoreError("Installed continuous policy required")
        self.i, self.w, self.installed = integration, integration.w, installed
        self._drivers = {}
        self._lane_drivers = {}
        with self.w._transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_continuous_callers (task TEXT NOT NULL, actor TEXT NOT NULL, PRIMARY KEY(task,actor))"
            )
            db.execute("CREATE TABLE IF NOT EXISTS native_history_inputs (path TEXT PRIMARY KEY)")
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_continuous_drives (id TEXT PRIMARY KEY, lane TEXT NOT NULL, event TEXT NOT NULL, state TEXT NOT NULL, result TEXT, owner TEXT)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS native_integration_candidate_idx ON native_integrations(json_extract(result, '$.candidate'))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_continuous_lanes (id TEXT PRIMARY KEY, actor TEXT NOT NULL, policy TEXT NOT NULL, active TEXT, generation INTEGER NOT NULL DEFAULT 0)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_continuous_queue (seq INTEGER PRIMARY KEY AUTOINCREMENT, lane TEXT NOT NULL, task TEXT UNIQUE NOT NULL, state TEXT NOT NULL, received REAL NOT NULL, batch TEXT, error TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_continuous_batches (id TEXT PRIMARY KEY, lane TEXT NOT NULL, tasks TEXT NOT NULL, plan TEXT, state TEXT NOT NULL, previous TEXT, created REAL NOT NULL, result TEXT, error TEXT, metrics TEXT)"
            )

            db.execute(
                "CREATE INDEX IF NOT EXISTS native_continuous_queue_order ON native_continuous_queue(lane,state,seq)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS native_continuous_batch_order ON native_continuous_batches(lane,state,created)"
            )

    def fingerprint(self):
        return dict(
            source=digest(Path(__file__).read_text(encoding="utf-8")),
            root=str(self.i.store.database.resolve()),
            max_history=32,
        )

    def _initial_input(self, path, materialize):
        if not materialize:
            return False
        with self.w._transaction() as db:
            return db.execute("INSERT OR IGNORE INTO native_history_inputs VALUES (?)", (str(path),)).rowcount == 1

    @domain_locked
    def prepare(self, tenant, checker, candidate, check, *, materialize=True):
        if self.w.runner.cache._policy(check)["reads"] is not None:
            return dict(env={}, binding={})
        # Bounded history channel, separate from the active product composition.
        # Every file is written once; subsequent uses validate the exact bytes.
        rows = self.w.domain.db.execute(
            "SELECT plan,result FROM native_integrations WHERE json_extract(result, '$.candidate')=? LIMIT 1",
            (candidate,),
        ).fetchall()
        plans = [json.loads(r["plan"]) for r in rows if json.loads(r["result"])["candidate"] == candidate]
        if not plans or not plans[0].get("continuation"):
            return dict(env={}, binding={})
        plan = plans[0]
        if tenant != plan["tenant"] or checker != plan["principals"]["checker"] or check not in plan["checks"]:
            raise NativeStoreError("History checker authority mismatch")
        actor = plan["actor"]
        self.validate(actor, plan["continuation"])
        references = plan["continuation"]["required_history"]
        directory = (
            Path(self.i.store.database).resolve().parent
            / "native-criteria-history"
            / digest([tenant, plan["product"], plan["channel"]])
        )
        if materialize:
            directory.mkdir(parents=True, exist_ok=True)
        if directory.is_symlink() or directory.resolve() != directory:
            raise NativeStoreError("History root must not redirect")
        view = directory.parent / "views" / digest([tenant, candidate, check])
        create_view = self._initial_input(view, materialize)
        if create_view:
            view.mkdir(parents=True, exist_ok=True)
        if view.is_symlink() or view.resolve() != view:
            raise NativeStoreError("History input view must not redirect")
        bindings = {}
        if len(references) > 32:
            raise NativeStoreError("Required history exceeds installed check capacity")
        for previous in references:
            record = self.history(actor, tenant, plan["product"], plan["channel"], previous)
            content = _json(record).encode()
            path = directory / (previous + ".json")
            if path.is_symlink():
                raise NativeStoreError("History file must not redirect")
            if self._initial_input(path, materialize) and not path.exists():
                with path.open("xb") as stream:
                    stream.write(content)
            if path.read_bytes() != content:
                raise NativeStoreError("Historical criteria bytes changed")
            target = view / path.name
            if create_view and not target.exists():
                with target.open("xb") as stream:
                    stream.write(content)
            if target.is_symlink() or target.read_bytes() != content:
                raise NativeStoreError("Historical criteria input changed")
            bindings[previous] = digest(record)

        if {p.name for p in view.iterdir()} != {ref + ".json" for ref in references}:
            raise NativeStoreError("Undeclared historical criteria input")
        return dict(env={"DUOBAO_HISTORY": str(view)}, binding=bindings)

    @domain_locked
    def fixed_owner(self, actor, key, coordinator=None):
        task = json.loads(self.w._row(self.w.domain.db, key)["task"])
        # Persisted membership remains authoritative across installation changes.
        specs = [json.loads(r[0]) for r in self.w.domain.db.execute("SELECT spec FROM native_integration_groups")]
        if callable(self.i.installed_groups):
            callers = {
                r[0]
                for r in self.w.domain.db.execute("SELECT actor FROM native_continuous_callers WHERE task=?", (key,))
            }
            for who in ({actor, task["actor"], coordinator} | callers) - {None}:
                groups = self.i.installed_groups(who)
                if not isinstance(groups, (list, tuple)) or len(groups) > 1024:
                    raise NativeStoreError("Bounded installed group list required")
                specs.extend(self.i.installed_plan(who, group) for group in groups)
        return any(key in spec.get("tasks", []) for spec in specs)

    def require_continuous(self, actor, tasks, coordinator):
        if any(self.fixed_owner(actor, key, coordinator) for key in tasks):
            raise NativeStoreError("Fixed group owns continuous contribution")

    def policies(self, actor):
        values = self.installed(actor)
        if not isinstance(values, list) or len(values) > 128:
            raise NativeStoreError("Bounded installed continuous policies required")
        found = {}
        for p in values:
            if (
                set(p)
                != {
                    "tenant",
                    "coordinator",
                    "product",
                    "channel",
                    "base",
                    "checks",
                    "max_batch",
                    "request_id",
                    "issue_url",
                    "history_refs",
                }
                or type(p["max_batch"]) is not int
                or not 1 <= p["max_batch"] <= 32
            ):
                raise NativeStoreError("Exact bounded continuous policy required")
            if (
                not isinstance(p["history_refs"], list)
                or not p["history_refs"]
                or len(p["history_refs"]) > 32
                or any(
                    not isinstance(ref, str)
                    or (
                        ref not in {"first", "predecessor"}
                        and (len(ref) != 64 or any(c not in "0123456789abcdef" for c in ref))
                    )
                    for ref in p["history_refs"]
                )
            ):
                raise NativeStoreError("Explicit bounded installed history references required")
            for who in (actor, p["coordinator"]):
                identity = self.w.domain.actor_context(who)
                if identity["tenant"] != p["tenant"] or identity["role"] not in {"admin", "editor"}:
                    raise NativeStoreError("Current same-tenant publishing delegation required")
            key = digest([p["tenant"], p["product"], p["channel"]])
            if key in found:
                raise NativeStoreError("One installed publisher per product channel required")
            found[key] = json.loads(_json(p))
        return found

    def validate(self, actor, binding):
        p = self.policies(actor).get(binding["lane"])
        if p is None or digest(p) != binding["policy"]:
            raise NativeStoreError("Continuous installation changed")
        return p

    @domain_locked
    def enqueue(self, actor, key, *, automatic=False):
        _, task, _, _ = self.i._original(actor, key)
        matches = [
            (k, p)
            for k, p in self.policies(actor).items()
            if p["tenant"] == task["tenant"] and p["product"] == task["product"]
        ]
        if automatic and (not matches or self.fixed_owner(actor, key, matches[0][1]["coordinator"])):
            return None
        if len(matches) != 1:
            raise NativeStoreError("Exactly one installed contribution destination required")
        lane, policy = matches[0]
        coordinator = policy["coordinator"]
        self.require_continuous(actor, [key], coordinator)
        self.i._original(coordinator, key)
        self.w._allow(coordinator, task["issue"], "authorize")
        with self.w._transaction() as db:
            db.execute("INSERT OR IGNORE INTO native_continuous_callers VALUES (?,?)", (key, actor))
            old = db.execute("SELECT * FROM native_continuous_lanes WHERE id=?", (lane,)).fetchone()
            if old and (old["actor"] != coordinator or old["policy"] != _json(policy)):
                raise NativeStoreError("Installed lane owner or policy changed")
            db.execute(
                "INSERT OR IGNORE INTO native_continuous_lanes(id,actor,policy) VALUES (?,?,?)",
                (lane, coordinator, _json(policy)),
            )
            db.execute(
                "INSERT OR IGNORE INTO native_continuous_queue(lane,task,state,received) VALUES (?,?,'ready',?)",
                (lane, key, time.time()),
            )
        return lane

    def ready(self, actor):
        result = []
        with self.w._transaction() as db:
            for lane, policy in self.policies(actor).items():
                row = db.execute(
                    "SELECT * FROM native_continuous_lanes WHERE id=? AND actor=?", (lane, policy["coordinator"])
                ).fetchone()
                if not row:
                    continue
                self.validate(actor, {"lane": lane, "policy": digest(json.loads(row["policy"]))})
                active = (
                    db.execute("SELECT * FROM native_continuous_batches WHERE id=?", (row["active"],)).fetchone()
                    if row["active"]
                    else None
                )
                if active and active["state"] == "held":
                    continue
                pending = db.execute(
                    "SELECT seq FROM native_continuous_queue WHERE lane=? AND state='ready' ORDER BY seq LIMIT 1",
                    (lane,),
                ).fetchone()
                if active or pending:
                    result.append(
                        dict(
                            key=lane, event=f"{lane}:{row['generation']}:{active['plan'] if active else pending['seq']}"
                        )
                    )
        return result

    @domain_locked
    def history(self, actor, tenant, product, channel, release_id):
        """Authenticated immutable criteria resolver for installed check/review hosts."""
        selected = self.w.release.historical(tenant, actor, product, channel, release_id)
        request = selected["request"]["request_key"]
        if not request.startswith("integration-publish-"):
            return dict(selection=selected, plan=None)
        key = request.removeprefix("integration-publish-")
        row = (
            self.i._load(actor, key, accepted=True)[0] if self.w.domain.db.in_transaction else self.i.status(actor, key)
        )
        if json.loads(row["acceptance"] or "null") != selected:
            raise NativeStoreError("Historical integration acceptance required")
        return dict(selection=selected, plan=json.loads(row["plan"]))

    @domain_locked
    def base(self, actor, p):
        selected = self.w.release.selected(p["tenant"], actor, p["product"], p["channel"])
        if selected is None:
            return dict(p["base"]), None
        modules = dict(selected["modules"])
        history = self.history(actor, p["tenant"], p["product"], p["channel"], selected["id"])
        plan = history["plan"]
        if plan:
            manifest = "integration-" + digest(plan)
            # Only the exact manifest of this validated selected integration.
            if manifest not in modules:
                raise NativeStoreError("Historical manifest missing")
            revision = self.i.store.revision(p["tenant"], manifest, modules[manifest])
            if self.i.store.read(p["tenant"], manifest, modules[manifest], "integration.json") != _json(plan).encode():
                raise NativeStoreError("Historical manifest mismatch")
            if set(revision["objects"]) != {"integration.json"} or revision["dependencies"]:
                raise NativeStoreError("Historical manifest contains business inputs")
            for module, rev in modules.items():
                if module != manifest and manifest in self.i.store.revision(p["tenant"], module, rev)["dependencies"]:
                    raise NativeStoreError("Business dependency on historical manifest")
            del modules[manifest]
        return modules, selected["id"]

    @domain_locked
    def freeze(self, actor, lane, policy, tasks, previous=None):
        self.require_continuous(actor, tasks, policy["coordinator"])
        base, expected = self.base(actor, policy)
        refs = []
        for ref in policy["history_refs"]:
            if ref == "predecessor":
                ref = expected
            elif ref == "first":
                first = self.w.domain.db.execute(
                    "SELECT result FROM native_continuous_batches WHERE lane=? AND state='accepted' ORDER BY created LIMIT 1",
                    (lane,),
                ).fetchone()
                ref = json.loads(first[0])["id"] if first else None
            if ref and ref not in refs:
                self.history(actor, policy["tenant"], policy["product"], policy["channel"], ref)
                refs.append(ref)
        binding = dict(
            lane=lane, policy=digest(policy), predecessor=expected, previous_plan=previous, required_history=refs
        )
        spec = {k: policy[k] for k in ("product", "channel", "checks", "request_id", "issue_url")}
        spec.update(tasks=tasks, base=base, expected=expected, continuation=binding)
        plan = self.i._authorize_spec(actor, "continuous-" + digest(spec), spec)
        batch = digest([lane, tasks, plan])
        with self.w._transaction() as db:
            db.execute(
                "INSERT OR IGNORE INTO native_continuous_batches VALUES (?,?,?,?,? ,?,?,NULL,NULL,NULL)",
                (batch, lane, _json(tasks), plan, "ready", previous, time.time()),
            )
            db.execute("UPDATE native_continuous_lanes SET active=?,generation=generation+1 WHERE id=?", (batch, lane))
            for task in tasks:
                db.execute("UPDATE native_continuous_queue SET state='active',batch=? WHERE task=?", (batch, task))
        return batch

    def drive(self, actor, lane, event=None):
        if lane not in self.policies(actor):
            raise NativeStoreError("Installed lane unavailable")
        event = event or ("direct-" + uuid.uuid4().hex)
        token = digest([lane, event])
        with self.w.domain._connection_lock:
            with self.w._transaction() as db:
                old = db.execute("SELECT * FROM native_continuous_drives WHERE id=?", (token,)).fetchone()
                if old:
                    if old["state"] == "complete":
                        return json.loads(old["result"])
                    return dict(state="publisher_busy", lane=lane, event=event)
                owner = self._lane_drivers.get(lane)
                db.execute(
                    "INSERT INTO native_continuous_drives VALUES (?,?,?,'running',NULL,?)", (token, lane, event, owner)
                )
            if owner:
                return dict(state="publisher_busy", lane=lane, event=event)
            future = Future()
            self._drivers[token] = future
            self._lane_drivers[lane] = token
        try:
            result = self._drive(actor, lane)
            with self.w._transaction() as db:
                db.execute(
                    "UPDATE native_continuous_drives SET state='complete',result=? WHERE id=?", (_json(result), token)
                )
            return result
        except BaseException as exc:
            with self.w._transaction() as db:
                db.execute(
                    "UPDATE native_continuous_drives SET state='unknown',result=? WHERE id=?",
                    (_json(dict(error=str(exc))), token),
                )
            raise
        finally:
            with self.w.domain._connection_lock:
                self._lane_drivers.pop(lane, None)
                self._drivers.pop(token, None)
                future.set_result(None)

    async def await_lane(self, actor, lane, event):
        if lane not in self.policies(actor):
            raise NativeStoreError("Installed lane unavailable")
        token = digest([lane, event])
        with self.w.domain._connection_lock:
            row = self.w.domain.db.execute("SELECT * FROM native_continuous_drives WHERE id=?", (token,)).fetchone()
            if row is None:
                raise NativeStoreError("Publisher event not received; execution remains unknown")
            owner = row["owner"] or token
            owned = self._drivers.get(owner)
        if owned is not None:
            try:
                await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(owned)), 86400)
            except TimeoutError:
                raise NativeStoreError("Publisher observer deadline exceeded; original intent retained") from None
        if lane not in self.policies(actor):
            raise NativeStoreError("Publishing delegation revoked")
        with self.w.domain._connection_lock:
            current = self.w.domain.db.execute("SELECT * FROM native_continuous_drives WHERE id=?", (owner,)).fetchone()
        if current is None or current["state"] != "complete":
            raise NativeStoreError("Publisher physical ownership unavailable; outcome unknown")
        result = json.loads(current["result"])
        if result.get("state") == "publisher_busy":
            raise NativeStoreError("External publisher ownership unavailable; outcome unknown")
        return result

    def _drive(self, actor, lane):
        policy = self.policies(actor).get(lane)
        if policy is None:
            raise NativeStoreError("Installed lane unavailable")
        actor = policy["coordinator"]
        path = Path(self.i.store.database).parent / "native-publish-locks" / (lane + ".lock")
        with publisher_lock(path) as acquired:
            if not acquired:
                return dict(state="publisher_busy", lane=lane)
            with self.w._transaction() as db:
                row = db.execute(
                    "SELECT * FROM native_continuous_lanes WHERE id=? AND actor=?", (lane, actor)
                ).fetchone()
                if not row:
                    raise NativeStoreError("Lane unavailable")
                self.validate(actor, dict(lane=lane, policy=digest(json.loads(row["policy"]))))
                active = row["active"]
                rows = (
                    db.execute(
                        "SELECT * FROM native_continuous_queue WHERE lane=? AND state='ready' ORDER BY seq LIMIT ?",
                        (lane, policy["max_batch"]),
                    ).fetchall()
                    if not active
                    else []
                )
            tasks = []
            for row in rows:
                try:
                    with self.w._transaction():
                        self.i._original(actor, row["task"])
                        self.require_continuous(actor, [row["task"]], policy["coordinator"])
                    tasks.append(row["task"])
                except Exception as exc:
                    with self.w._transaction() as db:
                        db.execute(
                            "UPDATE native_continuous_queue SET state='blocked',error=? WHERE task=?",
                            (str(exc), row["task"]),
                        )
            if not active:
                if not tasks:
                    return dict(state="idle", lane=lane)
                active = self.freeze(actor, lane, policy, tasks)
            with self.w.domain._connection_lock:
                batch = dict(
                    self.w.domain.db.execute("SELECT * FROM native_continuous_batches WHERE id=?", (active,)).fetchone()
                )
            plan = batch["plan"]
            started = time.time()
            try:
                result = self.i.reconcile(actor, plan)
                if result.get("state") == "conflicts_pending":
                    bad = {c.get("task") for c in result["conflicts"]}
                    # Dependency conflicts lacking an exact member bind the batch.
                    if None in bad:
                        bad = set(json.loads(batch["tasks"]))
                    with self.w._transaction() as db:
                        for task in json.loads(batch["tasks"]):
                            db.execute(
                                "UPDATE native_continuous_queue SET state=?,error=? WHERE task=?",
                                ("blocked" if task in bad else "ready", _json(result) if task in bad else None, task),
                            )
                        db.execute(
                            "UPDATE native_continuous_batches SET state='conflicted',result=? WHERE id=?",
                            (_json(result), active),
                        )
                        db.execute(
                            "UPDATE native_continuous_lanes SET active=NULL,generation=generation+1 WHERE id=?", (lane,)
                        )
                    return result
            except Conflict as exc:
                # Native finish already read back its publication request. Only a
                # known failed CAS permits successor; all other failures hold.
                if "Channel changed" not in str(exc):
                    return self.hold(active, exc)
                current = self.i.status(actor, plan)
                if not current["review"]:
                    return self.hold(active, exc)
                try:
                    successor = self.freeze(actor, lane, policy, json.loads(batch["tasks"]), previous=plan)
                except Exception as failure:
                    return self.hold(active, failure)
                with self.w._transaction() as db:
                    db.execute(
                        "UPDATE native_continuous_batches SET state='superseded',error=? WHERE id=?", (str(exc), active)
                    )
                return dict(state="successor_ready", batch=successor, previous=plan)
            except Exception as exc:
                isolated = self.isolate_invalid(actor, batch)
                return isolated if isolated is not None else self.hold(active, exc)
            with self.w.domain._connection_lock:
                oldest_received = min(
                    r[0]
                    for r in self.w.domain.db.execute(
                        "SELECT received FROM native_continuous_queue WHERE batch=?", (active,)
                    )
                )
            metrics = dict(
                started=started,
                finished=time.time(),
                elapsed_seconds=time.time() - started,
                queue_seconds=started - oldest_received,
            )
            with self.w._transaction() as db:
                db.execute(
                    "UPDATE native_continuous_batches SET state='accepted',result=?,metrics=? WHERE id=?",
                    (_json(result), _json(metrics), active),
                )
                db.execute("UPDATE native_continuous_queue SET state='accepted' WHERE batch=?", (active,))
                db.execute("UPDATE native_continuous_lanes SET active=NULL,generation=generation+1 WHERE id=?", (lane,))
            return dict(state="accepted", batch=active, release=result, metrics=metrics)

    def isolate_invalid(self, actor, batch):
        """Split independent invalid members only after ruling out unknown effects."""
        with self.w._transaction() as db:
            row = db.execute("SELECT * FROM native_integrations WHERE id=?", (batch["plan"],)).fetchone()
            plan = json.loads(row["plan"])
            if digest(plan) != batch["plan"]:
                return None
            invalid = {}
            for key in json.loads(batch["tasks"]):
                try:
                    self.i._original(actor, key)
                except (NativeStoreError, PermissionDenied) as error:
                    # Only original validity is being classified; never interpret
                    # a failed external call as permission to replay that call.
                    invalid[key] = str(error)
            if not invalid or row["acceptance"] or (row["review_intent"] and not row["review"]):
                return None
            unknown = db.execute(
                "SELECT 1 FROM native_integration_intents WHERE plan=? AND result IS NULL LIMIT 1", (batch["plan"],)
            ).fetchone()
            if unknown:
                return None
            with self.i.store._connection() as native:
                published = native.execute(
                    "SELECT 1 FROM native_release_requests WHERE tenant=? AND actor=? AND request_key=?",
                    (plan["tenant"], plan["principals"]["publisher"], "integration-publish-" + batch["plan"]),
                ).fetchone()
                if published:
                    return None
                for check in plan["checks"]:
                    run = native.execute(
                        "SELECT payload FROM native_check_runs WHERE tenant=? AND run_key=?",
                        (plan["tenant"], "integration-" + batch["plan"] + "-" + check),
                    ).fetchone()
                    if run and json.loads(run[0])["state"] not in {"complete", "cached", "result"}:
                        return None
            for key in json.loads(batch["tasks"]):
                db.execute(
                    "UPDATE native_continuous_queue SET state=?,batch=NULL,error=? WHERE task=?",
                    ("blocked" if key in invalid else "ready", invalid.get(key), key),
                )
            result = dict(state="invalid_members_isolated", batch=batch["id"], invalid=invalid)
            db.execute(
                "UPDATE native_continuous_batches SET state='invalidated',error=? WHERE id=?",
                (_json(result), batch["id"]),
            )
            db.execute(
                "UPDATE native_continuous_lanes SET active=NULL,generation=generation+1 WHERE id=? AND active=?",
                (batch["lane"], batch["id"]),
            )
            return result

    def hold(self, batch, error):
        with self.w._transaction() as db:
            db.execute(
                "UPDATE native_continuous_batches SET state='held',error=? WHERE id=?",
                (f"{type(error).__name__}: {error}", batch),
            )
        return dict(state="held", batch=batch, error=str(error))
