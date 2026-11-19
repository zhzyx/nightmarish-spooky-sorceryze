"""Operator-installed normal native entry; uses the existing workflow and Sinan."""

import asyncio
import json
import os
from contextvars import ContextVar
from functools import wraps
from pathlib import Path

from native_candidates import NativeCandidates
from native_check_runner import NativeCheckRunner
from native_entry_review import IndependentReview
from native_evidence import EvidenceCache
from native_execution_host import EntryConsumer, EntryLedger, SharedSinanProcess, WorkflowService
from native_installation import InstallationManifest, InstalledPlannerRuntime, require
from native_integration import NativeIntegration
from native_release import NativeRelease
from native_requirement_plan import RequirementPlanner
from native_store import NativeStoreError, _digest, _json
from native_worker import NativeWorker
from native_workflow import NativeWorkflow
from tianxuan_core import NotFound, PermissionDenied


def domain_locked(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self.domain._connection_lock:
            return method(self, *args, **kwargs)

    return call


class CoordinatorOwnership:
    """OS-released single-process ownership; a stale PID never authorizes takeover."""

    def __init__(self, path):
        self.file = Path(path).open("a+b")
        try:
            import os

            if os.fstat(self.file.fileno()).st_size == 0:
                self.file.write(b"0")
                self.file.flush()
            self.file.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            self.file.close()
            raise NativeStoreError("Native coordinator already owned") from None

    def close(self):
        self.file.close()


class OrdinaryEntry:
    def __init__(self, domain, native, manifest, digest, root, *, installed_worker=None, runtime_installation=None):
        self.runtime_installation = runtime_installation
        self.installation = InstallationManifest(manifest, digest)
        try:
            self._initialize(domain, native, root, installed_worker=installed_worker)
        except BaseException:
            self.installation.close()
            raise

    def _initialize(self, domain, native, root, *, installed_worker):
        self.domain, self.native = domain, native
        digest = self.installation.sha256
        self.execution_nodes = "local-only" if installed_worker is None else "trusted-existing-adapter"
        self.root = Path(root)
        require(self.root.is_absolute(), "Absolute installation state root required")
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger = EntryLedger(domain)
        with self.ledger.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_entry_catalogs (product TEXT PRIMARY KEY, origin TEXT NOT NULL)"
            )
        self.ownership = None
        self.product_locks = {}
        self.current_entry = ContextVar("native_entry", default=None)
        self.consumer = EntryConsumer(self.ledger, self.consume)
        self.background = None
        self.dependency_changed = asyncio.Event()
        self.event_loop = None
        self.event_generation = 0
        self.transports = {}
        self.dispatcher = None
        self.active_drivers = set()
        self.driver_closures = {}
        spec = self.installation.spec
        self.consumer.recover_unknown = spec.get("mode") == "production"
        require(
            spec["version"] == 2 and spec["mode"] in {"production", "deterministic-test"},
            "Explicit production or deterministic-test installation required",
        )
        if spec["mode"] == "production":
            self.validate_production(spec)
        self.principals = spec["principals"]
        self.principals = {**self.principals, "integrator": spec["principals"]["producer"] + "-integration"}
        for name in ("workers", "checks", "registry"):
            (self.root / name).mkdir(exist_ok=True)
        installation = self.installation
        factory = self

        class Worker(NativeWorker):
            def run(self, task, execution, cancel=None):
                class Cancel:
                    def is_set(self):
                        try:
                            factory.authorize(task["actor"], task["issue"], "execute")
                            return cancel is not None and cancel.is_set()
                        except Exception:
                            return True

                factory.authorize(task["actor"], task["issue"], "execute")
                contract = factory.root / "registry" / (execution + ".contract.json")
                encoded = _json(task)
                if contract.exists():
                    require(contract.read_text(encoding="utf-8") == encoded, "Producer contract rebound")
                else:
                    with contract.open("x", encoding="utf-8") as stream:
                        stream.write(encoded)
                        stream.flush()
                        import os

                        os.fsync(stream.fileno())
                return super().run(task, execution, Cancel())

        producer = {**spec["commands"]["producer"], "timeout": 600, "log_bytes": 900000}
        worker = Worker(
            native,
            self.root / "workers",
            {model["id"]: producer for model in spec["catalog"]},
            lambda *_: bool(installation.verify()),
            authorize=self.module_authority,
        )
        if self.runtime_installation is not None:
            runtime_spec = self.runtime_installation.verify()
            require(runtime_spec["installation"] == digest, "Runtime installation identity mismatch")
            if runtime_spec["remote"] is not None:
                from native_remote_worker import RemoteNativeWorker

                remote = runtime_spec["remote"]
                require(
                    installed_worker is None and set(remote) == {"profiles", "nodes"},
                    "Closed remote installation required",
                )

                class EntryRemoteWorker(RemoteNativeWorker):
                    def _contract(self, task, execution):
                        marker = factory.current_entry.set(task["mandate"])
                        try:
                            return super()._contract(task, execution)
                        finally:
                            factory.current_entry.reset(marker)

                    def reconcile(self, task, execution):
                        marker = factory.current_entry.set(task["mandate"])
                        try:
                            return super().reconcile(task, execution)
                        finally:
                            factory.current_entry.reset(marker)

                installed_worker = EntryRemoteWorker(
                    native,
                    self.root / "workers",
                    remote["profiles"],
                    authorize=self.module_authority,
                    nodes=remote["nodes"],
                    single_coordinator=True,
                )
                self.execution_nodes = "trusted-existing-adapter"
            from native_entry_context import EntryContexts

            self.contexts = EntryContexts(self, self.runtime_installation)
            worker.context_receipt_reader = self.contexts.receipt
        if installed_worker is not None:
            from native_remote_worker import RemoteNativeWorker

            require(
                isinstance(installed_worker, (NativeWorker, RemoteNativeWorker))
                and installed_worker.store.database.resolve() == native.database.resolve(),
                "Existing admitted worker adapter must share the exact native store",
            )
            worker = installed_worker
            if self.runtime_installation is not None:
                worker.context_receipt_reader = self.contexts.receipt
        cache = EvidenceCache(
            native, {"content": dict(version=digest, reads=None, max_age_seconds=3600)}, self.check_authority
        )

        class Checker(NativeCheckRunner):
            def execute(self, tenant, actor, key, candidate, check, cancel=None):
                class Cancel:
                    def is_set(self):
                        try:
                            factory.candidate_authority(tenant, candidate)
                            return cancel is not None and cancel.is_set()
                        except Exception:
                            return True

                factory.candidate_authority(tenant, candidate)
                return super().execute(tenant, actor, key, candidate, check, Cancel())

        runner = Checker(
            cache,
            self.root / "checks",
            {
                "content": {
                    **spec["commands"]["checker"],
                    "toolchain": digest,
                    "environment": _digest(_json(spec["commands"]["checker"]).encode()),
                    "timeout": 600,
                    "log_bytes": 900000,
                }
            },
            self.check_authority,
            lambda *_: bool(installation.verify()),
        )
        release = NativeRelease(cache, self.release_authority, lambda db, t, c: {self.principals["producer"]})
        review = IndependentReview(domain, native, installation, self.authorize)
        self.workflow = NativeWorkflow(
            domain,
            worker,
            runner,
            release,
            self.authorize,
            catalog=spec["catalog"],
            principals=lambda a, i, r: self.principals[r],
            review_candidate=review,
            installed_plan=self.plan,
            next_issues=self.next_issues,
            installed_target=lambda a, t: dict(channel="stable", expected=None),
        )
        NativeIntegration(
            self.workflow,
            NativeCandidates(native, self.module_authority),
            lambda *_: None,
            installed_continuous=self.continuous_policies,
            review_receipt=lambda actor, plan, result, reviewer: self.reconcile_review(
                review, actor, plan, result, reviewer
            ),
        )
        self.planner = RequirementPlanner(
            domain,
            self.ledger,
            InstalledPlannerRuntime(installation, lambda request: self.entry_authority(request["entry"])),
            spec["scopes"],
            spec["complexity"],
            self.requirement_authority,
        )

    def validate_production(self, spec):
        from native_entry_runtime import load_config

        require(
            os.environ.get("TIANXUAN_REQUIRE_KEYS") == "1"
            and os.environ.get("TIANXUAN_TENANT_ID")
            and os.environ.get("TIANXUAN_PUBLIC_ORIGIN", "").startswith("https://"),
            "Production execution requires strict administrator key and tenant admission",
        )

        templates = {}
        sources = Path(__file__).resolve().parent.parent / "sinan-workorders"
        component = sources.parent
        required = [
            *component.joinpath("server").glob("native_*.py"),
            *sources.glob("native_*.py"),
            *sources.glob("native_*.mjs"),
            *component.joinpath("duobao").glob("native_*.py"),
            component.parents[2] / "tools" / "ainative" / "owned_process.py",
        ]
        require(
            all(str(path) in spec["files"] for path in required),
            "Production installation must pin all native executable source inputs",
        )
        for role in ("planner", "producer", "reviewer"):
            argv = spec["commands"][role]["argv"]
            script = str(sources / ("native_entry_producer.py" if role == "producer" else "native_entry_runtime.py"))
            require(script in argv, "Production must use admitted existing runtime broker")
            require("--config" in argv and "--sha256" in argv, "Pinned broker configuration required")
            config, template = load_config(argv[argv.index("--config") + 1], argv[argv.index("--sha256") + 1])
            templates[role] = (config, template)
            if role == "producer":
                require(
                    "--registry" in argv and Path(argv[argv.index("--registry") + 1]) == self.root / "registry",
                    "Producer registry installation mismatch",
                )
        require(templates["planner"][1]["task"]["agent_id"] == "yanshi", "Admitted Yanshi required")
        require(
            templates["reviewer"][1]["task"].get("role") == "reviewer"
            and templates["reviewer"][1]["task"]["agent_id"] != templates["producer"][1]["task"]["agent_id"]
            and templates["reviewer"][0]["state"] != templates["producer"][0]["state"],
            "Independent admitted reviewer role and state required",
        )

    @staticmethod
    def reconcile_review(review, actor, plan, result, reviewer):
        require(review.reconcile(actor, plan, result) is True, "Review receipt unavailable")
        identity = _digest(_json(plan).encode())
        return dict(
            id=_digest(_json([identity, result["candidate"], reviewer]).encode()),
            plan=identity,
            candidate=result["candidate"],
            reviewer=reviewer,
            decision="accepted",
        )

    def entries(self):
        with self.domain._connection_lock:
            return [dict(r) for r in self.domain.db.execute("SELECT * FROM native_entry_intents")]

    def entry_authority(self, key):
        if self.installation.spec["mode"] == "production":
            with self.domain._connection_lock:
                row = self.domain.db.execute(
                    "SELECT e.tenant,c.access_key FROM native_entry_intents e JOIN native_entry_credentials c ON c.entry=e.id WHERE e.id=?",
                    (key,),
                ).fetchone()
            require(
                row is not None
                and row["access_key"]
                and os.environ.get("TIANXUAN_REQUIRE_KEYS") == "1"
                and row["tenant"] == os.environ.get("TIANXUAN_TENANT_ID"),
                "Original entry lacks current production tenant/key admission",
            )
        return self.ledger.authorize(key)

    def candidate_authority(self, tenant, candidate):
        with self.domain._connection_lock:
            originals = [
                json.loads(r[0])
                for r in self.domain.db.execute(
                    "SELECT task FROM native_tasks WHERE tenant=? AND state!='accepted' AND json_extract(terminal,'$.candidate')=? AND json_extract(task,'$.mandate')=?",
                    (tenant, candidate, self.current_entry.get()),
                )
            ]
            for row in self.domain.db.execute(
                "SELECT plan FROM native_integrations WHERE acceptance IS NULL AND json_extract(result,'$.candidate')=?",
                (candidate,),
            ):
                plan = json.loads(row[0])
                if plan["tenant"] == tenant:
                    originals.extend(original["contract"] for original in plan["originals"])
        require(originals, "Candidate has no entry authority")
        for task in originals:
            self.authorize(task["actor"], task["issue"], "check")
        return True

    def binding(self, issue):
        for row in self.entries():
            if row["receipt"]:
                receipt = json.loads(row["receipt"])
                if issue in receipt.get("mapping", {}).get("tasks", {}).values():
                    return row, receipt
        raise NativeStoreError("Issue has no installed entry authority")

    @staticmethod
    def product(row):
        return "entry-" + _digest(_json([row["tenant"], row["requirement"]]).encode())

    def requirement_authority(self, actor, requirement, action, entry):
        for row in self.entries():
            if row["id"] == entry and row["actor"] == actor and row["requirement"] == requirement:
                self.installation.verify()
                return self.entry_authority(row["id"])
        raise NativeStoreError("Requirement entry authority unavailable")

    def authorize(self, actor, issue, action):
        self.installation.verify()
        if self.runtime_installation is not None:
            self.runtime_installation.verify()
        with self.domain._connection_lock:
            row, _ = self.binding(issue)
            self.domain._require_requirement(actor, row["requirement"], write=action != "read")
            if action == "read":
                return True
            try:
                return self.entry_authority(row["id"])
            except NativeStoreError as error:
                raise PermissionDenied(str(error)) from None

    @domain_locked
    def module_authority(self, db, tenant, actor, module, action):
        self.installation.verify()
        require(action in {"read", "receive"}, "Producer authority denied")
        # Module callbacks authorize the installed data plane. Exact mutable task
        # authority is independently checked before/after every workflow effect.
        current = self.current_entry.get()
        for row in self.entries():
            if row["tenant"] != tenant or not row["receipt"]:
                continue
            receipt = json.loads(row["receipt"])
            known = module in receipt.get("catalog", receipt["selected"])
            if module.startswith("integration-"):
                with self.domain._connection_lock:
                    integration = self.domain.db.execute(
                        "SELECT plan FROM native_integrations WHERE id=?", (module.removeprefix("integration-"),)
                    ).fetchone()
                known = bool(integration and json.loads(integration[0])["product"] == self.product(row))
            if not known and not module.startswith("requirement-"):
                continue
            if actor in {self.principals["producer"], self.principals["integrator"]}:
                if current is None:
                    continue
                operation = next((e for e in self.entries() if e["id"] == current), None)
                if operation is None or self.product(operation) != self.product(row):
                    continue
                return self.entry_authority(current)
            if action == "read":
                try:
                    self.domain._require_requirement(actor, row["requirement"], write=False)
                    if module.startswith("requirement-"):
                        self.domain.require_native_module_read(actor, module)
                    return True
                except PermissionDenied:
                    continue
        self.last_denied = ("module", tenant, actor, module, action)
        return False

    def check_authority(self, tenant, actor, check, action):
        self.installation.verify()
        if actor != self.principals["checker"] or check != "content":
            return False
        for row in self.entries():
            if row["tenant"] == tenant:
                try:
                    if self.entry_authority(row["id"]):
                        return True
                except NativeStoreError:
                    continue
        return False

    @domain_locked
    def release_authority(self, db, tenant, actor, product, action):
        self.installation.verify()
        if action == "evidence:record":
            return self.check_authority(tenant, actor, product, "record")
        for row in self.entries():
            if row["tenant"] != tenant or product != self.product(row):
                continue
            if action == "read":
                try:
                    self.domain._require_requirement(actor, row["requirement"], write=False)
                    return True
                except PermissionDenied:
                    continue
            if row["id"] == self.current_entry.get():
                self.entry_authority(row["id"])
                return actor == (self.principals["reviewer"] if action == "approve" else self.principals["publisher"])
        self.last_denied = ("release", tenant, actor, product, action)
        return False

    def plan(self, actor, issue):
        row, receipt = self.binding(issue)
        self.authorize(actor, issue, "authorize")
        name = next(k for k, v in receipt["mapping"]["tasks"].items() if v == issue)
        task = next(t for t in receipt["tasks"] if t["id"] == name)
        used = {receipt["modules"][p.split("/", 1)[0]] for p in task["outputs"]}
        selected = {m: r for m, r in receipt["selected"].items() if m in used}
        dependencies = {}
        choices = json.loads(row["payload"])["choices"]
        for ref in choices.get("dependencies", []):
            previous = self.workflow.status(actor, ref["task"])
            require(
                previous["acceptance"] and _digest(previous["task"].encode()) == ref["contract"],
                "Cross-entry dependency is not accepted",
            )
            dependencies[previous["id"]] = previous["acceptance"]
            selected.update(json.loads(previous["acceptance"])["modules"])
        for dependency in task["dependencies"]:
            target = receipt["mapping"]["tasks"][dependency]
            with self.domain._connection_lock:
                previous = self.domain.db.execute(
                    "SELECT t.* FROM native_tasks t JOIN native_active_tasks a ON a.task=t.id WHERE a.issue=?",
                    (target,),
                ).fetchone()
            require(previous is not None and previous["acceptance"], "Dependency is not accepted")
            dependencies[previous["id"]] = previous["acceptance"]
            selected.update(json.loads(previous["acceptance"])["modules"])
        writes = {}
        for output in task["outputs"]:
            module, path = output.split("/", 1)
            module = receipt["modules"][module]
            writes.setdefault(module, []).append(path)
        models = [
            m
            for m in self.installation.spec["catalog"]
            if m.get("available") is True and set(task["capabilities"]) <= set(m.get("capabilities", []))
        ]
        if "model" in choices:
            models = [model for model in models if model["id"] == choices["model"]]
        require(models, "No admitted model capability")
        return dict(
            selected=selected,
            writes=writes,
            dependencies=dependencies,
            profile=models[0]["id"],
            product=self.product(row),
            checks=["content"],
            mandate=row["id"],
            capabilities=task["capabilities"],
            delivery_mode="contribution",
        )

    def continuous_policies(self, actor):
        policies = {}
        for row in self.entries():
            if not row["receipt"] or row["tenant"] != self.domain.actor_context(actor)["tenant"]:
                continue
            try:
                with self.domain._connection_lock:
                    self.domain._require_requirement(actor, row["requirement"], write=True)
            except Exception:
                continue
            product = self.product(row)
            if product in policies:
                continue
            policies[product] = dict(
                tenant=row["tenant"],
                coordinator=row["actor"],
                product=product,
                channel="stable",
                base=json.loads(row["receipt"]).get("catalog", json.loads(row["receipt"])["selected"]),
                checks=["content"],
                max_batch=32,
                history_refs=["first", "predecessor"],
                request_id=row["requirement"],
                issue_url="native://" + row["tenant"] + "/requirements/" + row["requirement"],
            )
            with self.domain._connection_lock:
                existing = self.domain.db.execute(
                    "SELECT policy FROM native_continuous_lanes WHERE json_extract(policy,'$.tenant')=? AND json_extract(policy,'$.product')=?",
                    (row["tenant"], product),
                ).fetchone()
            if existing:
                policies[product] = json.loads(existing[0])
        return list(policies.values())

    def task_references(self, key, actor):
        with self.domain._connection_lock:
            result = []
            for row in self.domain.db.execute(
                "SELECT * FROM native_tasks WHERE json_extract(task,'$.mandate')=?", (key,)
            ):
                try:
                    self.workflow._read_allowed(actor, row)
                except (NotFound, PermissionDenied):
                    continue
                contract = json.loads(row["task"])
                terminal = json.loads(row["terminal"]) if row["terminal"] else {}
                result.append(
                    dict(
                        observed_model=terminal.get("provider_model"),
                        usage=terminal.get("usage"),
                        task=row["id"],
                        state=row["state"],
                        issue_id=row["issue"],
                        title=contract["source"]["definition"]["title"],
                        selected_profile=contract["profile"],
                    )
                )
            return result

    def policy_reference(self, actor, requirement):
        tenant = self.domain.actor_context(actor)["tenant"]
        product = self.product(dict(tenant=tenant, requirement=requirement))
        with self.domain._connection_lock:
            row = self.domain.db.execute(
                "SELECT policy FROM native_continuous_lanes WHERE json_extract(policy,'$.tenant')=? AND json_extract(policy,'$.product')=?",
                (tenant, product),
            ).fetchone()
        return _digest(row[0].encode()) if row else None

    @domain_locked
    def handoff(self, actor, requirement, expected_policy):
        self.domain._require_requirement(actor, requirement, write=True)
        tenant = self.domain.actor_context(actor)["tenant"]
        product = self.product(dict(tenant=tenant, requirement=requirement))
        return self.workflow.integration.continuous.handoff(actor, tenant, product, "stable", expected_policy)

    def validate_dependencies(self, actor, requirement, references):
        require(
            isinstance(references, list)
            and len(references) <= 32
            and all(isinstance(r, str) for r in references)
            and len(references) == len(set(references)),
            "Bounded unique task dependency references required",
        )
        tenant = self.domain.actor_context(actor)["tenant"]
        result = []
        for key in references:
            row = self.workflow._row(self.domain.db, key)
            self.workflow._read_allowed(actor, row)
            task = json.loads(row["task"])
            require(
                task["tenant"] == tenant and task["source"]["definition"]["requirement_id"] == requirement,
                "Dependency must belong to the same shared requirement",
            )
            require(_digest(_json(task).encode()) == key, "Dependency contract changed")
            # Only existing immutable tasks may be referenced by a new entry:
            # no forward reference means no cycle can be introduced.
            result.append(dict(task=key, contract=_digest(_json(task).encode()), source=task["source"]))
        return result

    def notify_dependency_change(self):
        if self.event_loop is not None:
            self.event_loop.call_soon_threadsafe(self._event_received)

    def _event_received(self):
        self.event_generation += 1
        self.dependency_changed.set()

    async def await_dependencies(self, row):
        references = json.loads(row["payload"])["choices"].get("dependencies", [])
        while references:
            require(not self.consumer.stopping, "Dependency observer stopped; durable intent retained")
            self.dependency_changed.clear()
            self.entry_authority(row["id"])
            ready = True
            for ref in references:
                state = self.workflow.status(row["actor"], ref["task"])
                task = json.loads(state["task"])
                require(
                    _digest(_json(task).encode()) == ref["contract"] and task["source"] == ref["source"],
                    "Dependency immutable binding changed",
                )
                if not state["acceptance"]:
                    require(
                        state["state"] not in {"held", "stopped", "closed-unresolved"},
                        "Dependency outcome unavailable; original intent retained",
                    )
                    with self.domain._connection_lock:
                        self.workflow._valid(task["actor"], state)
                        blocked = self.domain.db.execute(
                            "SELECT 1 FROM native_continuous_queue WHERE task=? AND state='blocked'", (ref["task"],)
                        ).fetchone()
                    require(not blocked, "Dependency contribution blocked")
                    self.authorize(task["actor"], task["issue"], "dependency")
                    ready = False
            if ready:
                return
            await self.dependency_changed.wait()

    def next_issues(self, actor, event):
        result = []
        current = self.current_entry.get()
        for row in self.entries():
            if row["id"] != current or row["actor"] != actor or not row["receipt"]:
                continue
            for issue in json.loads(row["receipt"]).get("mapping", {}).get("tasks", {}).values():
                # Installation changes cannot rebind historical or in-flight
                # contracts. Existing tasks retain their exact authorization;
                # the workflow validates them when continuing their own work.
                with self.domain._connection_lock:
                    bound = self.domain.db.execute(
                        "SELECT 1 FROM native_active_tasks WHERE issue=?", (issue,)
                    ).fetchone()
                if bound:
                    continue
                try:
                    self.plan(actor, issue)
                    result.append(issue)
                except (NativeStoreError, PermissionDenied):
                    pass
        return result

    async def consume(self, row):
        token = self.current_entry.set(row["id"])
        try:
            return await self.consume_product(row)
        finally:
            self.recover_physical()
            self.current_entry.reset(token)
            self.notify_dependency_change()

    def recover_physical(self):
        with self.domain._connection_lock:
            rows = [
                dict(r)
                for r in self.domain.db.execute(
                    "SELECT id,task FROM native_tasks WHERE state IN ('running','held','closed-unresolved')"
                )
            ]
        for row in rows:
            task = json.loads(row["task"])
            try:
                self.authorize(task["actor"], task["issue"], "reconcile")
            except (NativeStoreError, PermissionDenied):
                # Existing host port proves physical closure; it cannot admit
                # output, impersonate the revoked actor, or release unknown work.
                try:
                    self.workflow._settle_physical(self.workflow.worker, row["id"])
                except NativeStoreError:
                    pass

    def seed_catalog(self, row, aliases):
        product = self.product(row)
        provenance = _digest(_json(self.installation.spec["scopes"]).encode())
        with self.ledger.transaction() as db:
            self.entry_authority(row["id"])
            proposed = dict(
                product=product,
                tenant=row["tenant"],
                requirement=row["requirement"],
                entry=row["id"],
                actor=row["actor"],
                source=row["source"],
                scope_provenance=provenance,
                modules=aliases,
                principal=self.principals["producer"],
            )
            db.execute("INSERT OR IGNORE INTO native_entry_catalogs VALUES (?,?)", (product, _json(proposed)))
            origin = json.loads(
                db.execute("SELECT origin FROM native_entry_catalogs WHERE product=?", (product,)).fetchone()[0]
            )
            require(
                origin["tenant"] == row["tenant"]
                and origin["requirement"] == row["requirement"]
                and origin["scope_provenance"] == provenance
                and origin["modules"] == aliases
                and origin["principal"] == self.principals["producer"],
                "Catalog reservation changed",
            )
        # The stable installed principal and reserved origin make the native
        # receipt recoverable across different members and a domain-write crash.
        self.entry_authority(row["id"])
        catalog = self.native.submit(
            row["tenant"],
            origin["principal"],
            "entry-seed-" + product,
            [dict(module=m, base=None, reads=None, edits={".entry": _json(origin).encode()}) for m in aliases.values()],
        )["revisions"]
        return catalog, origin

    async def consume_product(self, row):
        if row["receipt"]:
            receipt = json.loads(row["receipt"])
        else:
            tasks = await self.planner.propose(row, recover=row["state"] == "held")
            pinned = json.loads(row["payload"])["choices"].get("model")
            if pinned is not None:
                require(
                    any(
                        model["id"] == pinned
                        and model.get("available") is True
                        and "agent" in model.get("targets", [])
                        and all(set(task["capabilities"]) <= set(model.get("capabilities", [])) for task in tasks)
                        for model in self.installation.verify()["catalog"]
                    ),
                    "Selected model profile cannot execute the approved plan",
                )
            # The installed finite catalog is reserved once. Planning and all
            # physical worker/check/review waits occur outside this short lock.
            lock = self.product_locks.setdefault(self.product(row), asyncio.Lock())
            async with lock:
                all_modules = sorted({
                    p.split("/", 1)[0] for scope in self.installation.spec["scopes"].values() for p in scope["outputs"]
                })
                aliases = {m: self.product(row) + "-" + m for m in all_modules}
                previous = next(
                    (
                        json.loads(r["receipt"])
                        for r in self.entries()
                        if r["tenant"] == row["tenant"] and r["requirement"] == row["requirement"] and r["receipt"]
                    ),
                    None,
                )
                if previous:
                    require(
                        aliases == previous["modules"]
                        and previous.get("scope_provenance")
                        == _digest(_json(self.installation.spec["scopes"]).encode()),
                        "Installed product catalog changed; explicit migration required",
                    )
                    catalog = previous.get("catalog", previous["selected"])
                    seed_origin = previous.get("seed_origin")
                else:
                    catalog, seed_origin = self.seed_catalog(row, aliases)
                used = {aliases[p.split("/", 1)[0]] for t in tasks for p in t["outputs"]}
                selected = {m: r for m, r in catalog.items() if m in used}
                with self.ledger.transaction():
                    mapping = self.planner.persist(row, tasks)
                    receipt = dict(
                        tasks=tasks,
                        mapping=mapping,
                        selected=selected,
                        modules=aliases,
                        catalog=catalog,
                        seed_origin=seed_origin,
                        scope_provenance=_digest(_json(self.installation.spec["scopes"]).encode()),
                    )
                    self.ledger.record_plan(row["id"], receipt)
        await self.await_dependencies(row)
        for name, issue in receipt["mapping"]["tasks"].items():
            self.workflow.release.configure(
                row["tenant"],
                self.principals["publisher"],
                self.product(row),
                dict(
                    checks={"content": self.workflow.runner.context("content", "0" * 64)}, review_max_age_seconds=3600
                ),
            )
        for issue in self.next_issues(row["actor"], None):
            self.workflow.authorize_installed(row["actor"], issue)
        # Reconstruct recorded physical terminals before dispatching. Unknown
        # external execution remains occupied and is never converted to ready.
        with self.domain._connection_lock:
            recovering = [
                r[0]
                for r in self.domain.db.execute(
                    "SELECT id FROM native_tasks WHERE tenant=? AND state IN ('running','held','closed-unresolved')",
                    (row["tenant"],),
                )
            ]
        for key in recovering:
            try:
                self.workflow.reconcile(row["actor"], key)
            except (NativeStoreError, PermissionDenied):
                pass
        command = self.installation.command("dispatcher")
        service = WorkflowService(
            self.workflow, row["actor"], lambda: self.entry_authority(row["id"]), receipt["mapping"]["tasks"].values()
        )
        transports = self.transports.setdefault(row["id"], [])
        while True:
            observed = self.event_generation - self.driver_closures.get(row["id"], 0)
            self.dependency_changed.clear()
            if self.dispatcher is None:
                self.dispatcher = SharedSinanProcess(command["argv"], command["env"])
            self.active_drivers.add(row["id"])
            try:
                result = await self.dispatcher.run(service)
            finally:
                self.active_drivers.discard(row["id"])
            transports.append(result)
            with self.ledger.transaction():
                self.domain._event(
                    row["tenant"],
                    "native.entry.dispatch_completed",
                    row["actor"],
                    row["id"],
                    dict(entry=row["id"], transport=_digest(_json(result).encode())),
                )
            # Wake peers on logical driver completion; the shared Node remains
            # alive until coordinator shutdown. Exclude this entry's own
            # closure from its retry generation to avoid self-triggered replay.
            self.driver_closures[row["id"]] = self.driver_closures.get(row["id"], 0) + 1
            self._event_received()
            self.last_transport = result
            with self.domain._connection_lock:
                own = [
                    dict(r)
                    for r in self.domain.db.execute(
                        "SELECT id,state FROM native_tasks WHERE json_extract(task,'$.mandate')=?", (row["id"],)
                    )
                ]
                blocked = any(
                    self.domain.db.execute(
                        "SELECT 1 FROM native_continuous_queue WHERE task=? AND state='blocked'", (t["id"],)
                    ).fetchone()
                    for t in own
                )
                held = self.domain.db.execute(
                    "SELECT count(*) FROM native_tasks WHERE state IN ('reserved','running','held')"
                ).fetchone()[0]
                waiting_capacity = any(t["state"] == "ready" for t in own) and held >= self.workflow.capacity
                peers = {e["id"] for e in self.entries() if e["tenant"] == row["tenant"]} & self.active_drivers
                lane = _digest(_json([row["tenant"], self.product(row), "stable"]).encode())
                live = bool(
                    any(t["id"] in self.workflow._executions for t in own)
                    or (waiting_capacity and self.workflow._executions)
                    or lane in self.workflow.integration.continuous._lane_drivers
                    or peers - {row["id"]}
                )
            if own and all(t["state"] == "accepted" for t in own):
                break
            if (
                blocked
                or any(t["state"] in {"held", "stopped", "closed-unresolved"} for t in own)
                or self.consumer.stopping
            ):
                break
            # Another entry may have occupied the final slot between inspect and
            # reserve. A fresh driver consumes only recorded ready work after a
            # real terminal/acceptance event; unknown effects are never replayed.
            if self.event_generation - self.driver_closures.get(row["id"], 0) != observed:
                continue
            if not live:
                break
            await self.dependency_changed.wait()
            self.entry_authority(row["id"])
        receipt["transports"] = transports
        # Transport closure cannot erase the durable plan or imply acceptance.
        receipt["transport"] = result
        issues = [self.domain.get_issue(issue) for issue in receipt["mapping"]["tasks"].values()]
        parent = receipt["mapping"]["parent"]
        related = {
            issue
            for entry in self.entries()
            if entry["receipt"]
            for plan in [json.loads(entry["receipt"])]
            if plan["mapping"]["parent"] == parent
            for issue in plan["mapping"]["tasks"].values()
        }
        unplanned = any(
            entry["tenant"] == row["tenant"] and entry["requirement"] == row["requirement"] and not entry["receipt"]
            for entry in self.entries()
        )
        if not unplanned and all(self.domain.get_issue(issue)["status"] == "done" for issue in related):
            for state in ("planned", "in-progress", "in-review", "done"):
                current = self.domain.get_issue(parent)["status"]
                order = ["backlog", "planned", "in-progress", "in-review", "done"]
                if current in order and order.index(current) < order.index(state):
                    self.entry_authority(row["id"])
                    self.domain.transition_issue(row["actor"], parent, state)
        require(
            all(issue["status"] == "done" for issue in issues),
            "Native entry retains unfinished acceptance",
        )
        return receipt

    async def start(self):
        self.event_loop = asyncio.get_running_loop()
        self.workflow.integration.on_accepted = self.notify_dependency_change
        self.workflow.on_state_change = self.notify_dependency_change
        require(self.ownership is None, "Coordinator already started")
        try:
            self.ownership = CoordinatorOwnership(self.native.database.with_suffix(".coordinator.lock"))
            bind = getattr(self.workflow.worker, "bind", None)
            if bind is not None:
                bind(self.workflow)
            self.recover_physical()
            self.background = asyncio.create_task(self.consumer.run())
        except BaseException:
            if self.ownership:
                self.ownership.close()
                self.ownership = None
            self.installation.close()
            raise

    async def stop(self):
        self.consumer.stop()
        self.dependency_changed.set()
        if self.background:
            await self.background
        if self.dispatcher is not None:
            self.last_dispatcher_terminal = await self.dispatcher.close()
        close = getattr(self.workflow.worker, "close", None)
        if close is not None:
            close()
        if self.ownership:
            self.ownership.close()
            self.ownership = None
        self.installation.close()
