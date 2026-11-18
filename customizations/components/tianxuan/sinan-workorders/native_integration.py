"""Installed Heqi integration: immutable originals, one product, atomic fan-in.

Plans come only from the installed planner. Object merging never follows heads.
Unsupported dependency repins and conflicts fail closed; a new installed plan
can reuse original contributions after a product CAS loss.
"""

import json
import time
from contextlib import contextmanager

from native_store import Conflict, NativeStoreError, _digest, _json
from native_workflow import check_passed as passed
from native_workspace import tree_names


def digest(value):
    return _digest(_json(value).encode())


class NativeIntegration:
    def __init__(
        self,
        workflow,
        candidates,
        installed_plan,
        installed_resolver=None,
        review_receipt=None,
        installed_groups=None,
        installed_continuous=None,
    ):
        if not callable(installed_plan):
            raise NativeStoreError("Installed integration planner required")
        self.w, self.candidates, self.installed_plan = workflow, candidates, installed_plan
        self.installed_resolver = installed_resolver
        self.review_receipt = review_receipt
        self.installed_groups = installed_groups
        self.store, self.workspace = candidates.store, workflow.worker.workspace
        if (
            len({
                self.store.database.resolve(),
                self.workspace.store.database.resolve(),
                workflow.release.store.database.resolve(),
                workflow.runner.store.database.resolve(),
            })
            != 1
        ):
            raise NativeStoreError("Integration ports must share one authoritative native store")
        workflow.integration = self
        self.continuous = None
        with workflow._transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_integration_groups (actor TEXT NOT NULL, name TEXT NOT NULL, spec TEXT NOT NULL, plan TEXT, PRIMARY KEY(actor,name))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_integration_timings (plan TEXT NOT NULL, stage TEXT NOT NULL, started REAL NOT NULL, finished REAL NOT NULL)"
            )
            db.execute("CREATE TABLE IF NOT EXISTS native_contributions (task TEXT PRIMARY KEY, receipt TEXT NOT NULL)")
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_integrations (id TEXT PRIMARY KEY, plan TEXT NOT NULL, result TEXT, review_intent INTEGER NOT NULL DEFAULT 0, review TEXT, acceptance TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_integration_intents (plan TEXT NOT NULL, stage TEXT NOT NULL, result TEXT, PRIMARY KEY(plan,stage))"
            )
        # Release provenance is read inside its native transaction, never from
        # user supplied candidate authors or an unguarded domain callback.
        with self.store._connection(write=True) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_integration_authors (tenant TEXT NOT NULL, candidate TEXT NOT NULL, author TEXT NOT NULL, PRIMARY KEY(tenant,candidate,author))"
            )
        if installed_continuous is not None:
            from native_continuous import ContinuousIntegration

            self.continuous = ContinuousIntegration(self, installed_continuous)
            self.w.runner.history_provider = self.continuous
        previous = workflow.release.contributors

        def authors(db, tenant, candidate):
            rows = db.execute(
                "SELECT author FROM native_integration_authors WHERE tenant=? AND candidate=?", (tenant, candidate)
            ).fetchall()
            found = {r[0] for r in rows}
            return found | (previous(db, tenant, candidate) or set())

        workflow.release.contributors = authors

    def discover(self, actor):
        """Event-driven installed membership; freeze plans before producers finish."""
        result = dict(ready=[], errors=[])
        if self.continuous:
            result["continuous"] = self.continuous.ready(actor)
        if not callable(self.installed_groups):
            return result
        groups = self.installed_groups(actor)
        if not isinstance(groups, (list, tuple)) or len(groups) > 1024:
            raise NativeStoreError("Bounded installed group list required")
        for group in groups:
            try:
                if not isinstance(group, str) or not group or len(group) > 256:
                    raise NativeStoreError("Installed group identifier required")
                spec = json.loads(_json(self.installed_plan(actor, group)))
                with self.w._transaction() as db:
                    old = db.execute(
                        "SELECT * FROM native_integration_groups WHERE actor=? AND name=?", (actor, group)
                    ).fetchone()
                    if old and json.loads(old["spec"]) != spec:
                        raise NativeStoreError("Installed group changed; new fixed group required")
                    tasks = spec.get("tasks")
                    if not isinstance(tasks, list) or not tasks or len(set(tasks)) != len(tasks):
                        raise NativeStoreError("Unique installed contribution set required")
                    rows = [self.w._row(db, key) for key in tasks]
                    for row in rows:
                        self.w._read_allowed(actor, row)
                    db.execute(
                        "INSERT OR IGNORE INTO native_integration_groups VALUES (?,?,?,NULL)",
                        (actor, group, _json(spec)),
                    )
                    existing = old["plan"] if old else None
                    if not existing:
                        for row in rows:
                            self.w._valid(actor, row)
                        ready = all(
                            row["state"] == "produced"
                            and db.execute("SELECT 1 FROM native_contributions WHERE task=?", (row["id"],)).fetchone()
                            for row in rows
                        )
                    else:
                        ready = False
                if existing:
                    state = self.status(actor, existing)
                    if not state["acceptance"]:
                        result["ready"].append(dict(group=group, key=existing))
                elif ready:
                    key = self.authorize(actor, group)
                    result["ready"].append(dict(group=group, key=key))
            except Exception as error:
                result["errors"].append(dict(group=group, reason=str(error)))
        return result

    def _original(self, actor, key, *, accepted=False, historical=False):
        row = self.w._row(self.w.domain.db, key)
        task = json.loads(row["task"]) if historical else self.w._valid(actor, row)
        if digest(task) != key:
            raise NativeStoreError("Original task contract integrity failure")
        self.w._read_allowed(actor, row)
        if not historical:
            # A domain user delegates to an installed execution principal; the
            # latter need not (and must not implicitly) become a login account.
            self.w._valid(task["actor"], row)
            producer = (
                self.w.principals(task["actor"], task["issue"], "producer")
                if callable(self.w.principals)
                else task["actor"]
            )
            if producer != task["producer"]:
                raise NativeStoreError("Original producer installation changed")
        elif row["state"] != "accepted" or not row["acceptance"]:
            raise NativeStoreError("Historical accepted original required")
        if task.get("delivery_mode") != "contribution" or row["state"] not in (
            {"produced", "accepted"} if accepted else {"produced"}
        ):
            raise NativeStoreError("Original contribution terminal required")
        terminal = json.loads(row["terminal"] or "null")
        if not terminal or terminal["state"] != "produced":
            raise NativeStoreError("Authentic produced terminal required")
        intake = terminal.get("intake")
        origin = dict(
            source_ref="native-source:" + digest(task["source"]),
            worker_ref="native-worker:" + key,
            issue_url="native://" + task["tenant"] + "/issues/" + task["issue"],
        )
        receipt = None
        if intake is None:
            if (
                terminal.get("no_changes") is not True
                or terminal.get("origin") != origin
                or terminal.get("exit_code") != 0
                or not isinstance(terminal.get("transcript"), str)
                or len(terminal["transcript"]) != 64
            ):
                raise NativeStoreError("Explicit original no-change process terminal required")
        else:
            receipt = self.candidates.receipt_for(task["tenant"], actor, task["producer"], intake["request_key"])
            if receipt != intake or receipt["origin"] != origin:
                raise NativeStoreError("Original receipt source/execution binding mismatch")
        expected = dict(task["selected"])
        expected.update(receipt["revisions"] if receipt else {})
        # Validate actual original base and writable bounds, including deletions.
        for module, item in (receipt["inputs"] if receipt else {}).items():
            if item["base"] != task["selected"].get(module) or module not in task["writes"]:
                raise NativeStoreError("Contribution escaped original base or mandate")
            bounds = task["writes"][module]
            if bounds != "*" and set(item["edits"]) - set(bounds):
                raise NativeStoreError("Contribution escaped writable objects")
        modules, _ = self.workspace.sources(task["tenant"], expected)
        with self.store._connection() as db:
            for module in set(modules) | set(task["selected"]):
                self.candidates._allow(db, task["tenant"], task["producer"], module, "read")
                self.candidates._allow(db, task["tenant"], actor, module, "read")
            for module in receipt["inputs"] if receipt else ():
                self.candidates._allow(db, task["tenant"], task["producer"], module, "receive")
        if terminal["candidate"] != digest({"state": "candidate", "modules": modules}):
            raise NativeStoreError("Terminal does not bind original intake")
        return row, task, terminal, receipt

    def check_contribution(self, actor, key):
        with self.w._transaction():
            row, task, terminal, receipt = self._original(actor, key)
        facts = self.w.check(actor, key)  # Real installed subprocesses, outside locks.
        if any(not passed(self.w.runner, task["tenant"], terminal["candidate"], c, r) for c, r in facts.items()):
            raise NativeStoreError("Contribution checks failed")
        result = dict(
            state="contribution_checked",
            task=key,
            source=task["source"],
            terminal=digest(terminal),
            intake=receipt["id"] if receipt else None,
            evidence={c: r["evidence"] for c, r in facts.items()},
        )
        with self.w._transaction() as db:
            self._original(actor, key)
            old = db.execute("SELECT receipt FROM native_contributions WHERE task=?", (key,)).fetchone()
            if old and json.loads(old[0]) != result:
                raise Conflict("Contribution check receipt is immutable")
            db.execute("INSERT OR IGNORE INTO native_contributions VALUES (?,?)", (key, _json(result)))
        if self.continuous:
            self.continuous.enqueue(actor, key, automatic=True)
        return result

    def continue_lane(self, actor, key, event=None):
        if not self.continuous:
            raise NativeStoreError("Continuous integration installation required")
        return self.continuous.drive(actor, key, event)

    def authorize(self, actor, group):
        return self._authorize_spec(actor, group, self.installed_plan(actor, group))

    def _authorize_spec(self, actor, group, installed_spec):
        if not callable(self.w.principals):
            raise NativeStoreError("Admitted integration principals required")
        spec = json.loads(_json(installed_spec))
        if set(spec) - {"repins", "continuation"} != {
            "tasks",
            "product",
            "channel",
            "base",
            "expected",
            "checks",
            "request_id",
            "issue_url",
        }:
            raise NativeStoreError("Exact installed integration plan required")
        if not spec["tasks"] or len(set(spec["tasks"])) != len(spec["tasks"]) or not spec["checks"]:
            raise NativeStoreError("Unique complete contribution set and final checks required")
        originals = []
        with self.w._transaction() as db:
            frozen = db.execute(
                "SELECT spec FROM native_integration_groups WHERE actor=? AND name=?", (actor, group)
            ).fetchone()
            if frozen and json.loads(frozen[0]) != spec:
                raise NativeStoreError("Installed group changed; new fixed group required")
            for key in sorted(spec["tasks"]):
                row, task, terminal, intake = self._original(actor, key)
                self.w._allow(actor, row["issue"], "authorize")
                checked = db.execute("SELECT receipt FROM native_contributions WHERE task=?", (key,)).fetchone()
                if not checked or task["product"] != spec["product"]:
                    raise NativeStoreError("Checked same-product contributions required")
                originals.append(
                    dict(
                        task=key,
                        contract=task,
                        terminal=digest(terminal),
                        intake=intake["id"] if intake else None,
                        checked=json.loads(checked[0]),
                    )
                )
            tenants = {o["contract"]["tenant"] for o in originals}
            if len(tenants) != 1:
                raise NativeStoreError("Same tenant required")
            tenant = next(iter(tenants))
            base, _ = self.workspace.sources(tenant, spec["base"])
            repins = spec.get("repins", {})
            if not isinstance(repins, dict) or set(repins) - set(base):
                raise NativeStoreError("Repin consumers must be in fixed product base")
            for module, pins in repins.items():
                if (
                    not isinstance(pins, dict)
                    or not pins
                    or set(pins) - set(base)
                    or any(v != "@integrated" for v in pins.values())
                ):
                    raise NativeStoreError("Explicit integrated dependency targets required")
            self.w._inputs_allowed(actor, base)
            required = {c for o in originals for c in o["contract"]["checks"]}
            if not required.issubset(spec["checks"]):
                raise NativeStoreError("Final checks omit original criteria")
            if not any(self.w.runner.cache._policy(c)["reads"] is None for c in spec["checks"]):
                raise NativeStoreError("Joint check covering complete product and criterion manifest required")
            plan = dict(
                **spec,
                tenant=tenant,
                originals=originals,
                actor=actor,
                group=group,
                contexts={c: self.w.runner.context(c, "0" * 64) for c in spec["checks"]},
                principals={
                    role: self.w.principals(actor, originals[0]["contract"]["issue"], role)
                    for role in ("integrator", "checker", "reviewer", "publisher")
                },
            )
            plan["base"] = base
            key = digest(plan)
            db.execute("INSERT OR IGNORE INTO native_integrations(id,plan) VALUES (?,?)", (key, _json(plan)))
            db.execute("UPDATE native_integration_groups SET plan=? WHERE actor=? AND name=?", (key, actor, group))
        return key

    def _load(self, actor, key, *, accepted=False):
        row = self.w.domain.db.execute("SELECT * FROM native_integrations WHERE id=?", (key,)).fetchone()
        if row is None:
            raise NativeStoreError("Integration unavailable")
        plan = json.loads(row["plan"])
        if digest(plan) != key:
            raise NativeStoreError("Integration plan integrity failure")
        historical = accepted and bool(row["acceptance"])
        for original in plan["originals"]:
            original_row, task, terminal, intake = self._original(
                actor, original["task"], accepted=accepted, historical=historical
            )
            if (
                task != original["contract"]
                or digest(terminal) != original["terminal"]
                or (intake["id"] if intake else None) != original["intake"]
                or (historical and original_row["acceptance"] != row["acceptance"])
            ):
                raise NativeStoreError("Original contribution changed")
        if historical:
            selected = json.loads(row["acceptance"])
            result = json.loads(row["result"] or "null")
            verified = self.w.release.historical(
                plan["tenant"], actor, plan["product"], plan["channel"], selected["id"]
            )
            if (
                verified != selected
                or not result
                or result["plan"] != key
                or result["candidate"] != selected["candidate"]
                or result["modules"] != selected["modules"]
                or selected["request"]["request_key"] != "integration-publish-" + key
            ):
                raise NativeStoreError("Historical integration publication changed")
            # Read already accepted facts under current source/release authority.
            # Do not re-authorize old execution, reset issues, or emit new events.
            return dict(row), plan
        if plan.get("continuation"):
            if not self.continuous:
                raise NativeStoreError("Continuous installation removed")
            policy = self.continuous.validate(actor, plan["continuation"])
            self.continuous.require_continuous(actor, plan["tasks"], policy["coordinator"])
        if plan["contexts"] != {c: self.w.runner.context(c, "0" * 64) for c in plan["checks"]}:
            raise NativeStoreError("Final check installation changed")
        if plan["principals"] != {
            role: self.w.principals(actor, plan["originals"][0]["contract"]["issue"], role)
            for role in plan["principals"]
        }:
            raise NativeStoreError("Independent integration principal installation changed")
        self.w._inputs_allowed(actor, plan["base"])
        with self.store._connection() as native_db:
            for module in plan["base"]:
                self.candidates._allow(native_db, plan["tenant"], actor, module, "read")
                self.candidates._allow(native_db, plan["tenant"], plan["principals"]["integrator"], module, "receive")
            if row["result"]:
                for module in json.loads(row["result"])["modules"]:
                    self.candidates._allow(native_db, plan["tenant"], actor, module, "read")
                    self.candidates._allow(
                        native_db, plan["tenant"], plan["principals"]["integrator"], module, "receive"
                    )
        if plan.get("resolution"):
            resolution = plan["resolution"]
            receipt = self.candidates.receipt_for(plan["tenant"], actor, resolution["actor"], resolution["request_key"])
            if receipt != resolution:
                raise NativeStoreError("Installed resolution receipt changed")
            with self.store._connection() as native_db:
                for module in resolution["inputs"]:
                    self.candidates._allow(native_db, plan["tenant"], resolution["actor"], module, "receive")
        return dict(row), plan

    def status(self, actor, key):
        with self.w._transaction():
            row, _ = self._load(actor, key, accepted=True)
            return row

    def execute(self, actor, key):
        with self.w._transaction() as db:
            row, plan = self._load(actor, key)
            if row["result"]:
                return json.loads(row["result"])
            db.execute("INSERT OR IGNORE INTO native_integration_intents VALUES (?,'execute',NULL)", (key,))
        tenant = plan["tenant"]
        _, base = self.workspace.sources(tenant, plan["base"])
        trees = {m: dict(s["objects"]) for m, s in base.items()}
        changes_by_path = {}
        conflicts = []
        for original in plan["originals"]:
            task = original["contract"]
            terminal = json.loads(self.w.status(actor, original["task"])["terminal"])
            if terminal["intake"] is None:
                continue
            receipt = self.candidates.receipt_for(tenant, actor, task["producer"], terminal["intake"]["request_key"])
            for module, item in receipt["inputs"].items():
                old = self.store.revision(tenant, module, item["base"])
                new = self.store.revision(tenant, module, receipt["revisions"][module])
                if (
                    module not in base
                    or old["dependencies"] != new["dependencies"]
                    or new["dependencies"] != base[module]["dependencies"]
                ):
                    conflicts.append(
                        dict(
                            module=module, task=original["task"], reason="explicit dependency/base resolution required"
                        )
                    )
                    continue
                for path in sorted(set(old["objects"]) | set(new["objects"])):
                    before, after = old["objects"].get(path), new["objects"].get(path)
                    if before == after:
                        continue
                    slot = (module, path)
                    pinned = base[module]["objects"].get(path)
                    if (pinned not in (before, after)) or (slot in changes_by_path and changes_by_path[slot] != after):
                        conflicts.append(
                            dict(
                                module=module,
                                path=path,
                                base=before,
                                product=pinned,
                                contribution=after,
                                task=original["task"],
                            )
                        )
                    changes_by_path[slot] = after
                    if after is None:
                        trees[module].pop(path, None)
                    else:
                        trees[module][path] = after
        if conflicts and plan.get("resolution"):
            resolution = plan["resolution"]
            if digest(conflicts) != plan["conflicts"]:
                raise NativeStoreError("Resolution conflict preconditions changed")
            required = {(c["module"], c["path"]) for c in conflicts if "path" in c}
            supplied = {(m, p) for m, item in resolution["inputs"].items() for p in item["edits"]}
            if any("path" not in conflict for conflict in conflicts) or supplied != required:
                raise NativeStoreError("Exact object conflict resolution required; dependency repins unsupported")
            for module, item in resolution["inputs"].items():
                state = self.store.revision(tenant, module, resolution["revisions"][module])
                if item["base"] != plan["base"][module] or state["dependencies"] != base[module]["dependencies"]:
                    raise NativeStoreError("Resolution changed pinned base or dependencies")
                for path in item["edits"]:
                    if path in state["objects"]:
                        trees[module][path] = state["objects"][path]
                    else:
                        trees[module].pop(path, None)
            conflicts = []
        if conflicts:
            with self.w._transaction() as db:
                self._load(actor, key)
                db.execute(
                    "UPDATE native_integration_intents SET result=? WHERE plan=? AND stage='execute'",
                    (_json(dict(state="conflicts_pending", conflicts=conflicts)), key),
                )
            return dict(state="conflicts_pending", plan=key, conflicts=conflicts)
        for tree in trees.values():
            tree_names(tree)
        changes = []
        changed = {m for m, tree in trees.items() if tree != base[m]["objects"]} | set(plan.get("repins", {}))
        for module, tree in trees.items():
            old = base[module]["objects"]
            edits = {}
            for path in sorted(set(old) | set(tree)):
                if old.get(path) != tree.get(path):
                    if path not in tree:
                        edits[path] = None
                    else:
                        with self.store._connection() as db:
                            content = db.execute(
                                "SELECT content FROM native_blobs WHERE tenant=? AND digest=?", (tenant, tree[path])
                            ).fetchone()
                        if not content or _digest(bytes(content[0])) != tree[path]:
                            raise NativeStoreError("Integration blob integrity failure")
                        edits[path] = bytes(content[0])
            if module in changed:
                dependencies = dict(base[module]["dependencies"])
                for dependency in plan.get("repins", {}).get(module, {}):
                    dependencies[dependency] = "@batch" if dependency in changed else plan["base"][dependency]
                changes.append(
                    dict(
                        module=module,
                        base=plan["base"][module],
                        reads=None,
                        edits=edits,
                        dependencies=dependencies,
                    )
                )
        integrator = self.w.principals(actor, plan["originals"][0]["contract"]["issue"], "integrator")
        selected = dict(plan["base"])
        intake = None
        if changes:
            intake = self.candidates.receive(
                tenant,
                integrator,
                "integration-" + key,
                changes,
                dict(source_ref=key, worker_ref="heqi-" + key, issue_url=plan["issue_url"]),
            )
            selected.update(intake["revisions"])
        # The exact original requirement/criterion union is a real immutable
        # check input, so a final check cannot reuse an unrelated coverage claim.
        manifest_module = "integration-" + key
        if manifest_module in selected:
            raise NativeStoreError("Reserved integration manifest collision")
        manifest = self.candidates.receive(
            tenant,
            integrator,
            "manifest-" + key,
            [dict(module=manifest_module, base=None, reads=None, edits={"integration.json": _json(plan).encode()})],
            dict(source_ref=key, worker_ref="heqi-" + key, issue_url=plan["issue_url"]),
        )
        selected.update(manifest["revisions"])
        candidate = self.store.compose(tenant, selected)
        authors = sorted({o["contract"]["producer"] for o in plan["originals"]} | {integrator})
        if plan.get("resolution"):
            authors = sorted(set(authors) | {plan["resolution"]["actor"]})
        result = dict(
            state="integrated",
            plan=key,
            candidate=candidate["id"],
            modules=candidate["modules"],
            authors=authors,
            intake=intake,
        )
        with self.store._connection(write=True) as native_db:
            with self.w._transaction() as db:
                self._load(actor, key)
                for author in authors:
                    native_db.execute(
                        "INSERT OR IGNORE INTO native_integration_authors VALUES (?,?,?)",
                        (tenant, candidate["id"], author),
                    )
                native_db.commit()  # Provenance precedes recoverable domain result.
                db.execute("UPDATE native_integrations SET result=? WHERE id=?", (_json(result), key))
                db.execute(
                    "UPDATE native_integration_intents SET result=? WHERE plan=? AND stage='execute'",
                    (_json(result), key),
                )
        return result

    def resolve(self, actor, key):
        """Installed resolver runs once outside locks; unknown outcome stays held.

        The resolver returns a real NativeCandidates receipt, never executable
        client text. Its request key is the supplied stable resolution intent.
        """
        if not callable(self.installed_resolver):
            raise NativeStoreError("Admitted conflict resolver unavailable")
        pending = self.execute(actor, key)
        if pending["state"] != "conflicts_pending":
            raise NativeStoreError("Unresolved conflict required")
        with self.w._transaction() as db:
            _, plan = self._load(actor, key)
            old = db.execute(
                "SELECT result FROM native_integration_intents WHERE plan=? AND stage='resolve'", (key,)
            ).fetchone()
            if old:
                if old[0]:
                    return json.loads(old[0])["plan"]
                raise NativeStoreError("Resolver outcome unknown; authenticated reconciliation required")
            db.execute("INSERT INTO native_integration_intents VALUES (?,'resolve',NULL)", (key,))
        principal = self.w.principals(actor, plan["originals"][0]["contract"]["issue"], "resolver")
        receipt = self.installed_resolver(actor, plan, pending, "resolution-" + key)
        verified = self.candidates.receipt_for(plan["tenant"], actor, principal, "resolution-" + key)
        if verified != receipt:
            raise NativeStoreError("Resolver must return exact installed-principal receipt")
        successor = dict(plan, previous=key, conflicts=digest(pending["conflicts"]), resolution=receipt)
        successor_id = digest(successor)
        with self.w._transaction() as db:
            self._load(actor, key)
            db.execute(
                "INSERT OR IGNORE INTO native_integrations(id,plan) VALUES (?,?)", (successor_id, _json(successor))
            )
            db.execute(
                "UPDATE native_integration_intents SET result=? WHERE plan=? AND stage='resolve'",
                (_json(dict(plan=successor_id)), key),
            )
        return successor_id

    def reconcile(self, actor, key):
        """Recover only real installed-principal receipts; never rerun resolver."""
        with self.w._transaction() as db:
            row, plan = self._load(actor, key, accepted=True)
            pending = db.execute(
                "SELECT result FROM native_integration_intents WHERE plan=? AND stage='resolve'", (key,)
            ).fetchone()
        if pending is not None:
            if pending[0]:
                return json.loads(pending[0])["plan"]
            principal = self.w.principals(actor, plan["originals"][0]["contract"]["issue"], "resolver")
            receipt = self.candidates.receipt_for(plan["tenant"], actor, principal, "resolution-" + key)
            conflicts = self.execute(actor, key)
            if conflicts["state"] != "conflicts_pending" or receipt["origin"]["source_ref"] != key:
                raise NativeStoreError("Exact unresolved source receipt required")
            successor = dict(plan, previous=key, conflicts=digest(conflicts["conflicts"]), resolution=receipt)
            successor_id = digest(successor)
            with self.w._transaction() as db:
                self._load(actor, key)
                db.execute(
                    "INSERT OR IGNORE INTO native_integrations(id,plan) VALUES (?,?)", (successor_id, _json(successor))
                )
                db.execute(
                    "UPDATE native_integration_intents SET result=? WHERE plan=? AND stage='resolve'",
                    (_json(dict(plan=successor_id)), key),
                )
            return successor_id
        return self.finish(actor, key)

    @contextmanager
    def _guard(self, actor, key, native_db):
        with self.w._transaction():
            _, plan = self._load(actor, key, accepted=True)
            for original in plan["originals"]:
                self.w._allow(actor, original["contract"]["issue"], "publish")
            _, policy = self.w.release._policy(native_db, plan["tenant"], plan["product"])
            if policy["checks"] != plan["contexts"]:
                raise NativeStoreError("Exact joint check policy required")
            if plan.get("continuation"):
                result = json.loads(
                    self.w.domain.db.execute("SELECT result FROM native_integrations WHERE id=?", (key,)).fetchone()[0]
                )
                for check in plan["checks"]:
                    self.continuous.prepare(
                        plan["tenant"], plan["principals"]["checker"], result["candidate"], check, materialize=False
                    )
            yield

    def _timing(self, key, stage, started):
        with self.w._transaction() as db:
            db.execute("INSERT INTO native_integration_timings VALUES (?,?,?,?)", (key, stage, started, time.time()))

    def finish(self, actor, key):
        row = self.status(actor, key)
        if row["acceptance"]:
            return json.loads(row["acceptance"])
        plan = json.loads(row["plan"])
        result = json.loads(row["result"] or "null")
        if not result:
            result = self.execute(actor, key)
        if result["state"] != "integrated":
            return result
        issue = plan["originals"][0]["contract"]["issue"]
        reviewer = self.w.principals(actor, issue, "reviewer")
        publisher = self.w.principals(actor, issue, "publisher")
        # Recovery uses request identity, including publication committed before
        # the domain acceptance transaction, independent of latest channel head.
        with self.store._connection() as db:
            saved = db.execute(
                "SELECT record FROM native_release_requests WHERE tenant=? AND actor=? AND request_key=?",
                (plan["tenant"], publisher, "integration-publish-" + key),
            ).fetchone()
        if saved:
            return self.complete(actor, key, saved[0])
        if reviewer in result["authors"] or not callable(self.w.review_candidate):
            raise NativeStoreError("Independent installed reviewer required")
        if row["review"]:
            review = json.loads(row["review"])
        else:
            with self.store._connection() as db:
                saved_review = db.execute(
                    "SELECT record FROM native_release_requests WHERE tenant=? AND actor=? AND request_key=?",
                    (plan["tenant"], reviewer, "integration-review-" + key),
                ).fetchone()
                recovered_review = (
                    self.w.release._valid_review(db, plan["tenant"], saved_review[0]) if saved_review else None
                )
            if recovered_review:
                with self.w._transaction() as db:
                    self._load(actor, key)
                    db.execute("UPDATE native_integrations SET review=? WHERE id=?", (_json(recovered_review), key))
                return self.finish(actor, key)
            checker = self.w.principals(actor, issue, "checker")
            check_started = time.time()
            facts = {
                c: self.w.runner.execute(
                    plan["tenant"], checker, "integration-" + key + "-" + c, result["candidate"], c
                )
                for c in plan["checks"]
            }
            self._timing(key, "checks", check_started)
            if any(not passed(self.w.runner, plan["tenant"], result["candidate"], c, f) for c, f in facts.items()):
                raise NativeStoreError("Joint product checks failed")
            with self.w._transaction() as db:
                current, _ = self._load(actor, key)
                recovering = bool(current["review_intent"])
                db.execute("UPDATE native_integrations SET review_intent=1 WHERE id=?", (key,))
            if recovering:
                receipt = self.review_receipt(actor, plan, result, reviewer) if callable(self.review_receipt) else None
                if (
                    not isinstance(receipt, dict)
                    or not receipt.get("id")
                    or receipt.get("plan") != key
                    or receipt.get("candidate") != result["candidate"]
                    or receipt.get("reviewer") != reviewer
                    or receipt.get("decision") != "accepted"
                ):
                    raise NativeStoreError("Review outcome unknown; authenticated reconciliation required")
                with self.w._transaction() as db:
                    self._load(actor, key)
                    db.execute(
                        "INSERT OR IGNORE INTO native_integration_intents VALUES (?,'review-receipt',?)",
                        (key, _json(receipt)),
                    )
            elif self.w.review_candidate(actor, plan, result) is not True:
                raise NativeStoreError("Joint independent review rejected")
            with self.w._transaction():
                self._load(actor, key)
            review = self.w.release.approve(
                plan["tenant"],
                reviewer,
                "integration-review-" + key,
                plan["product"],
                result["candidate"],
                {c: f["evidence"] for c, f in facts.items()},
                "Independent installed review of exact integration plan " + key,
            )
            with self.w._transaction() as db:
                db.execute("UPDATE native_integrations SET review=? WHERE id=?", (_json(review), key))
        publish_started = time.time()
        published = self.w.release.publish(
            plan["tenant"],
            publisher,
            "integration-publish-" + key,
            plan["product"],
            plan["channel"],
            review["id"],
            plan["expected"],
            guard=lambda db: self._guard(actor, key, db),
        )
        self._timing(key, "publish", publish_started)
        return self.complete(actor, key, published["id"])

    def complete(self, actor, key, release_id):
        with self.store._connection(write=True) as native_db:
            with self.w._transaction() as db:
                row, plan = self._load(actor, key, accepted=True)
                selected = self.w.release._validated_selection(
                    native_db, plan["tenant"], actor, plan["product"], plan["channel"], release_id
                )
                result = json.loads(row["result"] or "null")
                if (
                    not result
                    or selected["candidate"] != result["candidate"]
                    or selected["request"]["request_key"] != "integration-publish-" + key
                ):
                    raise NativeStoreError("Exact integration publication required")
                _, policy = self.w.release._policy(native_db, plan["tenant"], plan["product"])
                if policy["checks"] != plan["contexts"]:
                    raise NativeStoreError("Exact joint check policy required")
                acceptance = _json(selected)
                if row["acceptance"]:
                    if row["acceptance"] != acceptance:
                        raise Conflict("Integration acceptance changed")
                    return selected
                for original in plan["originals"]:
                    task = original["contract"]
                    self.w._allow(actor, task["issue"], "accept")
                    current = self.w._row(db, original["task"])
                    if current["state"] != "produced":
                        raise NativeStoreError("Frozen group already consumed")
                for original in plan["originals"]:
                    task, task_id = original["contract"], original["task"]
                    db.execute(
                        "UPDATE native_tasks SET state='accepted',acceptance=? WHERE id=?", (acceptance, task_id)
                    )
                    db.execute(
                        "UPDATE native_managed_issues SET acceptance=? WHERE issue_id=?", (acceptance, task["issue"])
                    )
                    db.execute("UPDATE issues SET status='done' WHERE id=?", (task["issue"],))
                    self.w.domain._event(
                        plan["tenant"],
                        "native.accepted",
                        actor,
                        task["issue"],
                        dict(task=task_id, integration=key, release=release_id),
                    )
                    requirement = task["source"]["definition"]["requirement_id"]
                    if requirement:
                        self.w.domain.sync_progress(requirement, actor=actor)
                    db.execute(
                        "INSERT INTO native_outbox VALUES (?,?,?)",
                        (task_id, plan["tenant"], _json(dict(type="dependency.changed", reference=task_id))),
                    )
                db.execute("UPDATE native_integrations SET acceptance=? WHERE id=?", (acceptance, key))
        return selected
