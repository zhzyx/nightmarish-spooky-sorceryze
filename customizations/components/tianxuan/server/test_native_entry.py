"""Focused foundation tests; not normal-entry or live-model acceptance."""
# ruff: noqa: E402, I001

import asyncio
import builtins
import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
for folder in (HERE, HERE.parent / "duobao", HERE.parent / "sinan-workorders"):
    sys.path.insert(0, str(folder))

from native_execution_host import EntryConsumer, EntryLedger, SinanProcess
from native_installation import InstallationManifest, InstalledPlannerRuntime
from native_requirement_plan import RequirementPlanner, validate_plan
from native_store import NativeStoreError
from tianxuan_core import NotFound, Tianxuan, TransitionRejected


class EntryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.domain = Tianxuan(":memory:")
        self.ledger = EntryLedger(self.domain)
        self.actor = self.domain.register("first", "one@example.test", "password")["user_id"]
        self.other = self.domain.register("second", "two@example.test", "password")["user_id"]
        self.tokens = {actor: self.domain.issue_session(actor) for actor in (self.actor, self.other)}

    def tearDown(self):
        self.domain.db.close()

    def enqueue(self, call="request", actor=None):
        actor = actor or self.actor
        with self.ledger.transaction():
            requirement = self.domain.create_requirement(actor, call, "Title", "Outcome", "Scope", "Acceptance")
            key = self.ledger.enqueue(
                actor, requirement["id"], call, {"scopes": ["text"]}, credential=self.tokens[actor]
            )
        return key, requirement

    async def test_workspace_requires_installed_confirmation_reader(self):
        from unittest.mock import patch

        requirement = self.domain.create_requirement(
            self.actor, "workspace-" + "a" * 64, "Design", "Approved output", "scope", "checks"
        )
        with patch.dict(sys.modules, {"workspace_conversations": None}):
            with self.assertRaisesRegex(NativeStoreError, "approval reader"):
                with self.ledger.transaction():
                    self.ledger.enqueue(
                        self.actor,
                        requirement["id"],
                        "direct",
                        {"scopes": ["text"]},
                        credential=self.tokens[self.actor],
                    )
        self.assertFalse(self.ledger.pending())

    async def test_atomic_rollback_and_cross_tenant(self):
        with self.assertRaises(RuntimeError):
            with self.ledger.transaction():
                requirement = self.domain.create_requirement(
                    self.actor, "rollback", "Title", "Outcome", "Scope", "Acceptance"
                )
                self.ledger.enqueue(
                    self.actor, requirement["id"], "rollback", {"scopes": ["text"]}, credential=self.tokens[self.actor]
                )
                raise RuntimeError("crash before commit")
        self.assertEqual(self.ledger.pending(), [])
        key, requirement = self.enqueue()
        with self.assertRaises(Exception):
            with self.ledger.transaction():
                self.ledger.enqueue(self.other, requirement["id"], "foreign", {}, credential=self.tokens[self.other])
        self.assertEqual(len(self.ledger.pending()), 1)
        self.assertEqual(self.ledger.claim(key)["actor"], self.actor)
        self.assertIsNone(self.ledger.claim(key))

    async def test_original_credential_revocation_blocks_new_effect(self):
        key, _ = self.enqueue()
        self.assertTrue(self.ledger.authorize(key))
        self.domain.revoke_session(self.tokens[self.actor])
        with self.assertRaises(NativeStoreError):
            self.ledger.claim(key)
        self.assertEqual(len(self.ledger.pending()), 1)

    async def test_new_increment_reopens_only_aggregate_atomically(self):
        requirement = self.domain.create_requirement(self.actor, "increment", "Title", "Outcome", "Scope", "Acceptance")
        parent, child = self.domain.plan_tickets(
            self.actor,
            requirement["id"],
            [
                {
                    "title": "Earlier delivery",
                    "type": "task",
                    "acceptance": "Exact output",
                    "priority": "normal",
                    "body_md": "",
                }
            ],
        )
        for issue in (child, parent):
            for state in ("planned", "in-progress", "in-review", "done"):
                self.domain.transition_issue(self.actor, issue["id"], state)
        accepted_child = self.domain.get_issue(child["id"])
        self.assertEqual(self.domain.get_doc(requirement["id"])["progress"]["percent"], 100)

        def submit():
            return self.ledger.enqueue(
                self.actor,
                requirement["id"],
                "increment-entry",
                {"scopes": ["text"]},
                credential=self.tokens[self.actor],
            )

        with self.assertRaisesRegex(RuntimeError, "before commit"):
            with self.ledger.transaction():
                submit()
                self.assertEqual(self.domain.get_issue(parent["id"])["status"], "in-progress")
                raise RuntimeError("before commit")
        self.assertEqual(self.domain.get_issue(parent["id"])["status"], "done")
        self.assertEqual(self.domain.get_doc(requirement["id"])["progress"]["percent"], 100)
        self.assertFalse(self.ledger.pending())
        with self.assertRaises(NotFound):
            with self.ledger.transaction():
                self.ledger.enqueue(
                    self.other, requirement["id"], "foreign-increment", {}, credential=self.tokens[self.other]
                )
        with self.assertRaises(NativeStoreError):
            with self.ledger.transaction():
                self.ledger.enqueue(self.actor, requirement["id"], "invalid-credential", {}, credential="revoked")
        self.assertEqual(self.domain.get_issue(parent["id"])["status"], "done")

        with self.ledger.transaction():
            key = submit()
        self.assertEqual(self.domain.get_issue(parent["id"])["status"], "in-progress")
        self.assertLess(self.domain.get_doc(requirement["id"])["progress"]["percent"], 100)
        self.assertEqual(self.domain.get_issue(child["id"]), accepted_child)
        self.assertTrue(self.ledger.authorize(key))
        self.assertIsNone(self.ledger.pending()[0]["receipt"])
        before = self.domain.db.execute("SELECT COUNT(*) FROM events WHERE type='issue.transitioned'").fetchone()[0]
        with self.ledger.transaction():
            self.assertEqual(submit(), key)
        self.assertEqual(
            self.domain.db.execute("SELECT COUNT(*) FROM events WHERE type='issue.transitioned'").fetchone()[0], before
        )
        with self.assertRaises(TransitionRejected):
            self.domain.transition_issue(self.actor, child["id"], "in-progress")
        self.assertEqual(self.domain.get_issue(child["id"]), accepted_child)

    async def test_startup_commit_notify_gap_and_unknown_no_replay(self):
        key, _ = self.enqueue()
        calls = []
        done = asyncio.Event()

        async def consume(row):
            calls.append(row["id"])
            done.set()
            raise RuntimeError("external reply lost")

        consumer = EntryConsumer(self.ledger, consume)
        task = asyncio.create_task(consumer.run())
        await asyncio.wait_for(done.wait(), 2)
        consumer.stop()
        await task
        restarted = EntryConsumer(self.ledger, consume)
        task = asyncio.create_task(restarted.run())
        await asyncio.sleep(0)
        restarted.stop()
        await task
        self.assertEqual(calls, [key])
        self.assertEqual(self.ledger.pending(), [])

    async def test_event_arriving_while_consumer_busy(self):
        first, _ = self.enqueue()
        receipts = []
        done = asyncio.Event()

        async def consume(row):
            receipts.append(row["id"])
            if row["id"] == first:
                self.enqueue("second", self.other)
                consumer.notify()
            else:
                done.set()
            return {"delivery": "driver-returned"}

        consumer = EntryConsumer(self.ledger, consume)
        task = asyncio.create_task(consumer.run())
        await asyncio.wait_for(done.wait(), 2)
        consumer.stop()
        await task
        self.assertEqual(len(receipts), 2)
        self.assertFalse(self.ledger.pending())

    async def test_planner_persists_existing_issues_and_rechecks_withdrawal(self):
        key, _ = self.enqueue()
        row = self.ledger.claim(key)
        allow = True

        async def runtime(request):
            return {"source": request["source"], "tasks": [sample_task()]}

        planner = RequirementPlanner(
            self.domain,
            self.ledger,
            runtime,
            {"text": {"outputs": ["docs/result.txt"]}},
            {"small": ["text"]},
            lambda *args: allow,
        )
        tasks = await planner.propose(row)
        with self.ledger.transaction():
            receipt = planner.persist(row, tasks)
        self.assertEqual(len(self.domain.list_issues(self.actor)), 2)
        self.assertEqual(self.domain.list_issues(self.other), [])
        with self.ledger.transaction():
            self.assertEqual(planner.persist(row, tasks), receipt)
        allow = False
        with self.assertRaises(NativeStoreError):
            await planner.propose(row)

    async def test_committed_plan_survives_dispatch_gap_without_second_planner_call(self):
        key, _ = self.enqueue()
        row = self.ledger.claim(key)
        calls = []

        async def runtime(request):
            calls.append(request["entry"])
            return {"source": request["source"], "tasks": [sample_task()]}

        planner = RequirementPlanner(
            self.domain,
            self.ledger,
            runtime,
            {"text": {"outputs": ["docs/result.txt"]}},
            {"small": ["text"]},
            lambda *args: self.ledger.authorize(key),
        )
        tasks = await planner.propose(row)
        with self.ledger.transaction():
            issues = planner.persist(row, tasks)
            self.ledger.record_plan(key, {"tasks": tasks, "issues": issues})
        # Simulated crash after atomic Issue+plan commit, before task authorization.
        restarted = EntryLedger(self.domain)
        recovered = restarted.claim(key)
        self.assertEqual(recovered["state"], "planned")
        self.assertEqual(json.loads(recovered["receipt"])["issues"], issues)
        self.assertEqual(calls, [key])
        self.assertEqual(len(self.domain.list_issues(self.actor)), 2)

    async def test_production_admission_rejects_old_sessions_and_revoked_keys(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from native_entry_factory import OrdinaryEntry

        entry = object.__new__(OrdinaryEntry)
        entry.domain, entry.ledger = self.domain, self.ledger
        entry.installation = SimpleNamespace(spec={"mode": "production"})
        key, requirement = self.enqueue("old-session")
        tenant = self.domain.actor_context(self.actor)["tenant"]
        with patch.dict(os.environ, {"TIANXUAN_REQUIRE_KEYS": "1", "TIANXUAN_TENANT_ID": tenant}):
            with self.assertRaisesRegex(NativeStoreError, "tenant/key"):
                entry.entry_authority(key)
            access = self.domain.issue_access_key(self.actor, self.actor, "admitted")
            with self.ledger.transaction():
                admitted = self.ledger.enqueue(
                    self.actor, requirement["id"], "admitted", {"scopes": ["text"]}, credential=access["key"]
                )
            self.assertTrue(entry.entry_authority(admitted))
            self.domain.revoke_access_key(self.actor, access["id"])
            with self.assertRaises(NativeStoreError):
                entry.entry_authority(admitted)
        with patch.dict(os.environ, {"TIANXUAN_REQUIRE_KEYS": "0"}):
            with self.assertRaisesRegex(NativeStoreError, "strict administrator"):
                entry.validate_production({})

    async def test_held_planning_recovery_uses_only_readonly_port(self):
        key, _ = self.enqueue("recover-planner")
        self.ledger.claim(key)
        row = self.ledger.claim(key, recover=True)
        calls = []

        class Runtime:
            async def __call__(self, request):
                raise AssertionError("Unknown planning must never be repeated")

            async def recover(self, request):
                calls.append(request["entry"])
                return {"source": request["source"], "tasks": [sample_task()]}

        planner = RequirementPlanner(
            self.domain,
            self.ledger,
            Runtime(),
            {"text": {"outputs": ["docs/result.txt"]}},
            {"small": ["text"]},
            lambda *args: self.ledger.authorize(key),
        )
        tasks = await planner.propose(row, recover=True)
        self.assertEqual(calls, [key])
        self.assertEqual(tasks[0]["id"], "write")

    async def test_unrelated_arrival_completes_while_first_entry_waits(self):
        first, _ = self.enqueue("first-wait")
        started, release, second_done = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def consume(row):
            if row["id"] == first:
                started.set()
                await release.wait()
            else:
                second_done.set()
            return {"accepted": row["id"]}

        consumer = EntryConsumer(self.ledger, consume)
        running = asyncio.create_task(consumer.run())
        await asyncio.wait_for(started.wait(), 1)
        self.enqueue("independent", self.other)
        consumer.notify()
        await asyncio.wait_for(second_done.wait(), 1)
        release.set()
        consumer.stop()
        await running

    async def test_real_node_driver_closes_physical_process(self):
        node = os.environ.get("NATIVE_TEST_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Installed Node required")
        node = str(Path(node).resolve())
        operations = []

        async def dispatch(operation, value):
            operations.append(operation)
            if operation == "advance":
                return {"errors": []}
            if operation == "inspect":
                return {"environment": {"capacity": 1, "active": []}, "requests": []}
            self.fail(operation)

        driver = SinanProcess(
            [node, str(HERE.parent / "sinan-workorders/native_entry_driver.mjs")],
            {"SystemRoot": os.environ.get("SystemRoot", "C:/Windows")},
            dispatch,
        )
        result = await asyncio.wait_for(driver.run(), 10)
        self.assertEqual(driver.process.returncode, 0)
        self.assertFalse(result["errors"])
        self.assertEqual(operations, ["advance", "inspect"])

    async def test_driver_output_failure_closes_process_without_waiting_for_idle_exit(self):
        async def dispatch(operation, value):
            self.fail("No RPC expected")

        driver = SinanProcess(
            [
                sys.executable,
                "-B",
                "-c",
                "import sys,time; sys.stderr.write('x'*950000); sys.stderr.flush(); time.sleep(60)",
            ],
            {"SystemRoot": os.environ.get("SystemRoot", "C:/Windows")},
            dispatch,
        )
        with self.assertRaises(builtins.ExceptionGroup):
            await asyncio.wait_for(driver.run(), 10)
        self.assertIsNotNone(driver.process.returncode)


def sample_task():
    return {
        "id": "write",
        "title": "Write result",
        "body": "Produce scoped text",
        "acceptance": "Content accepted",
        "dependencies": [],
        "scope": "text",
        "complexity": "small",
        "outputs": ["docs/result.txt"],
    }


class PlanValidationTests(unittest.TestCase):
    def test_cycle_scope_and_revision_rejected(self):
        task = sample_task()
        scopes, complexity = {"text": {"outputs": ["docs/result.txt"]}}, {"small": ["text"]}
        self.assertEqual(
            validate_plan({"source": "fixed", "tasks": [task]}, "fixed", scopes, complexity)[0]["capabilities"],
            ["text"],
        )
        for field, value in (("dependencies", ["write"]), ("outputs", ["secrets/key"]), ("complexity", "unrated")):
            changed = copy.deepcopy(task)
            changed[field] = value
            with self.assertRaises(NativeStoreError):
                validate_plan({"source": "fixed", "tasks": [changed]}, "fixed", scopes, complexity)
        with self.assertRaises(NativeStoreError):
            validate_plan({"source": "old", "tasks": [task]}, "fixed", scopes, complexity)


class InstallationTests(unittest.IsolatedAsyncioTestCase):
    async def test_digest_withdrawal_and_owned_runtime_receipt(self):
        root = Path("D:/GongGong/data-collection/receipts/duobao-1382/native-production-entry-implementation-probes")
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            path = Path(folder)
            program = path / "installed_planner.py"
            program.write_text(
                "import json,sys,hashlib\nr=json.load(sys.stdin)\n"
                "assert 'GONGGONG_HOST_KEY' not in __import__('os').environ\n"
                "d=hashlib.sha256(json.dumps(r,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()\n"
                "print(json.dumps(dict(input_digest=d,source=r['source'],proposal={'source':r['source'],'tasks':[]},runtime_state='deterministic-test')))\n",
                encoding="utf-8",
            )
            python = str(Path(sys.executable).resolve())
            command = {
                "argv": [python, "-B", str(program)],
                "env": {"SystemRoot": os.environ.get("SystemRoot", "C:/Windows")},
            }
            spec = {
                "version": 1,
                "identity": "deterministic-test",
                "files": {
                    python: hashlib.sha256(Path(python).read_bytes()).hexdigest(),
                    str(program): hashlib.sha256(program.read_bytes()).hexdigest(),
                },
                "commands": {role: command for role in ("planner", "producer", "checker", "reviewer", "dispatcher")},
                "principals": {role: role for role in ("producer", "checker", "reviewer", "publisher")},
                "scopes": {"text": {"outputs": ["docs/result.txt"]}},
                "complexity": {"small": ["text"]},
                "catalog": [{"id": "test", "capabilities": ["text"]}],
            }
            manifest = path / "installation.json"
            manifest.write_text(json.dumps(spec), encoding="utf-8")
            digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
            with InstallationManifest(manifest, digest) as install:
                allowed = True
                runtime = InstalledPlannerRuntime(install, lambda request: allowed)
                self.assertEqual(await runtime({"source": "fixed"}), {"source": "fixed", "tasks": []})
                allowed = False
                with self.assertRaises(NativeStoreError):
                    await runtime({"source": "fixed"})
                if str(program) in install._cache:
                    with self.assertRaises(OSError):
                        program.write_text("changed", encoding="utf-8")
                    self.assertEqual(install.command("planner"), command)
                else:
                    program.write_text("changed", encoding="utf-8")
                    with self.assertRaises(NativeStoreError):
                        install.command("planner")
            # Managed replacement needs explicit shutdown and a new installation.
            program.write_text("changed", encoding="utf-8")
            with self.assertRaises(NativeStoreError):
                install.command("planner")
            with self.assertRaises(NativeStoreError):
                InstallationManifest(manifest, digest)


class RecoveryBoundaryTests(unittest.TestCase):
    def test_process_ownership_released_only_by_handle_close(self):
        from native_entry_factory import CoordinatorOwnership

        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "coordinator.lock"
            first = CoordinatorOwnership(path)
            try:
                with self.assertRaises(NativeStoreError):
                    CoordinatorOwnership(path)
            finally:
                first.close()
            second = CoordinatorOwnership(path)
            second.close()

    def test_signed_broker_readonly_recovery_never_replays_runtime(self):
        # Protocol fixture only: definition admission is stubbed, no model/provider.
        import sqlite3
        from unittest.mock import patch
        import native_entry_runtime as broker

        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ):
            root = Path(directory)
            (root / "framework-manifest.json").write_text("{}", encoding="utf-8")
            (root / "key").write_text("deterministic-test-key-material-only", encoding="utf-8")
            config = dict(
                node=sys.executable,
                python=sys.executable,
                framework=str(root),
                state=str(root / "state"),
                key_file=str(root / "key"),
                authority_ref="test-authority",
            )
            template = {
                "task": {"agent_id": "yanshi", "mode": "single", "steps": [{}]},
                "profiles": [{"protocol": "chat-completions"}],
            }
            request = dict(
                role="yanshi",
                entry="a" * 64,
                tenant="test",
                actor="actor",
                source="source",
                document={},
                scopes={},
                complexity={},
            )
            runtime_result = {
                "status": "completed",
                "result": {"outputs": {"proposal": {"source": "source", "tasks": []}}},
            }
            try:
                with (
                    patch.object(broker.runner, "validate_plan"),
                    patch.object(broker.runner, "context"),
                    patch.object(broker.runner, "run", return_value=runtime_result) as run,
                ):
                    receipt = broker.execute(config, template, request)
                    self.assertEqual(broker.execute(config, template, request, recover=True), receipt)
                    self.assertEqual(run.call_count, 1)
                    state = root / "state" / request["entry"]
                    (state / "entry-receipt.json").unlink()
                    intent = json.loads((state / "entry-intent.json").read_text())
                    grant = intent["grant"]
                    task = grant["payload"]["task"]
                    with sqlite3.connect(state / "runtime.sqlite") as db:
                        db.execute("CREATE TABLE jobs (id TEXT,task_hash TEXT,grant_hash TEXT,status TEXT,result TEXT)")
                        db.execute(
                            "INSERT INTO jobs VALUES (?,?,?,?,?)",
                            (
                                broker.runner.jid_for(task),
                                broker.runner.digest(task),
                                broker.runner.digest(grant),
                                "completed",
                                json.dumps(runtime_result["result"]),
                            ),
                        )
                    db.close()
                    self.assertEqual(broker.execute(config, template, request, recover=True), receipt)
                    self.assertEqual(run.call_count, 1)
                    (state / "entry-receipt.json").unlink()
                    with sqlite3.connect(state / "runtime.sqlite") as db:
                        db.execute("UPDATE jobs SET status='running'")
                    db.close()
                    with self.assertRaisesRegex(ValueError, "unknown"):
                        broker.execute(config, template, request, recover=True)
                    self.assertEqual(run.call_count, 1)
            finally:
                os.chdir(original_cwd)

    def test_review_rechecks_every_original_and_refuses_oversized_snapshot(self):
        from native_entry_review import IndependentReview
        from native_store import NativeStore

        domain = Tianxuan(":memory:")

        class Installed:
            def verify(self):
                return dict(identity="test-only", principals={"reviewer": "reviewer"})

        calls = []

        def authorize(actor, issue, action):
            calls.append(issue)
            if issue == "revoked":
                raise NativeStoreError("original credential revoked")
            return actor == "actor"

        try:
            review = IndependentReview(domain, None, Installed(), authorize)
            with self.assertRaisesRegex(NativeStoreError, "revoked"):
                review(
                    "actor",
                    {
                        "originals": [
                            {"contract": {"actor": "actor", "issue": "valid"}},
                            {"contract": {"actor": "actor", "issue": "revoked"}},
                        ]
                    },
                    {},
                )
            self.assertEqual(calls, ["valid", "revoked"])
            with tempfile.TemporaryDirectory() as folder:
                native = NativeStore(Path(folder) / "native.sqlite")
                selected = native.submit(
                    "tenant",
                    "actor",
                    "seed",
                    [dict(module="text", base=None, reads=None, edits={"output": b"x" * 80000})],
                )["revisions"]
                candidate = native.compose("tenant", selected)
                review = IndependentReview(domain, native, Installed(), authorize)
                task = dict(
                    actor="actor",
                    tenant="tenant",
                    issue="valid",
                    source={"definition": {"acceptance": "read all bytes"}},
                )
                with self.assertRaisesRegex(NativeStoreError, "has not been reviewed"):
                    review("actor", task, {"candidate": candidate["id"]})
                self.assertEqual(domain.db.execute("SELECT COUNT(*) FROM native_entry_reviews").fetchone()[0], 0)
        finally:
            domain.db.close()

    def test_semantic_receipt_requires_exact_content_and_original_criterion(self):
        import base64
        from native_entry_review import IndependentReview
        from native_store import _digest

        request = dict(
            source="candidate",
            complexity={"reviewer": "independent"},
            document={"source": {"definition": {"acceptance": "Exact original criterion"}}},
            scopes={"module/output": base64.b64encode(b"accepted").decode()},
        )
        receipt = dict(
            candidate="candidate",
            accepted=True,
            reviewer="independent",
            criteria="Exact original criterion",
            inspected={"module/output": _digest(b"accepted")},
            reason="Compared the exact content against original criterion",
        )
        IndependentReview.validate(receipt, request)
        for field, value in [
            ("accepted", False),
            ("criteria", "simplified"),
            ("reviewer", "producer"),
            ("candidate", "other"),
            ("inspected", {}),
            ("reason", ""),
        ]:
            with self.assertRaises(NativeStoreError):
                IndependentReview.validate({**receipt, field: value}, request)


if __name__ == "__main__":
    unittest.main()
