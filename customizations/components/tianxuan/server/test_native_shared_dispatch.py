"""Real pipe/process tests: concurrency and authority context, without models."""

# ruff: noqa: E402, I001
import asyncio
import contextvars
import os
import shutil
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
for folder in (HERE, HERE.parent / "duobao", HERE.parent / "sinan-workorders"):
    sys.path.insert(0, str(folder))

from native_execution_host import SharedSinanProcess
from native_store import NativeStoreError

IDENTITY = contextvars.ContextVar("test_entry")
DRIVER = HERE.parent / "sinan-workorders" / "native_entry_driver.mjs"


def board():
    return dict(requests=[], produced=[], environment=dict(capacity=250, active=[]))


class SharedDispatchTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.node = os.environ.get("NATIVE_TEST_NODE") or shutil.which("node")
        if not self.node:
            self.skipTest("Installed Node required")
        self.node = str(Path(self.node).resolve())
        self.environment = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR"}}

    def pool(self, driver=DRIVER):
        pool = SharedSinanProcess([self.node, str(driver)], self.environment)
        self.addAsyncCleanup(pool.close)
        return pool

    async def test_250_contexts_reach_barrier_in_one_process(self):
        pool = self.pool()
        seen, pids = set(), set()
        release = asyncio.Event()

        async def job(number):
            IDENTITY.set(number)

            async def service(operation, value):
                self.assertEqual(IDENTITY.get(), number)
                self.assertEqual(await asyncio.to_thread(IDENTITY.get), number)
                if operation == "advance":
                    return {"errors": []}
                self.assertEqual(operation, "inspect")
                seen.add(number)
                if len(seen) == 250:
                    release.set()
                await release.wait()
                return board()

            result = await pool.run(service)
            pids.add(result["transport"]["pid"])
            self.assertFalse(result["errors"])
            self.assertFalse(result["host_errors"])
            self.assertFalse(result["transport"]["physical_terminal"])
            return result

        tasks = [asyncio.create_task(job(i)) for i in range(250)]
        await asyncio.wait_for(release.wait(), 20)
        self.assertEqual(len(pool.jobs), 250)
        results = await asyncio.wait_for(asyncio.gather(*tasks), 20)
        self.assertEqual(len(pids), 1)
        self.assertEqual(len({r["transport"]["job"] for r in results}), 250)
        terminal = await pool.close()
        self.assertEqual(terminal["exit_code"], 0)
        self.assertTrue(terminal["physical_terminal"])

    async def test_slow_and_cancelled_caller_does_not_hold_peer_or_replay(self):
        pool = self.pool()
        entered, release, completed = asyncio.Event(), asyncio.Event(), asyncio.Event()
        calls = []

        async def slow(operation, value):
            calls.append(operation)
            if operation == "advance":
                return {"errors": []}
            entered.set()
            await release.wait()
            completed.set()
            return board()

        async def fast(operation, value):
            return {"errors": []} if operation == "advance" else board()

        original = asyncio.create_task(pool.run(slow))
        await asyncio.wait_for(entered.wait(), 5)
        original.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await original
        peer = await asyncio.wait_for(pool.run(fast), 5)
        self.assertFalse(peer["errors"])
        self.assertFalse(completed.is_set())
        self.assertEqual(len(pool.jobs), 1)
        release.set()
        await asyncio.wait_for(completed.wait(), 5)
        # Await the actual internal terminal, not the detached caller.
        if pool.jobs:
            await asyncio.wait_for(asyncio.gather(*(j["future"] for j in pool.jobs.values())), 5)
        self.assertEqual(calls, ["advance", "inspect"])
        self.assertEqual((await pool.close())["exit_code"], 0)

    async def test_withdrawn_entry_errors_do_not_use_peer_authority(self):
        pool = self.pool()
        effects = []

        async def job(actor):
            IDENTITY.set(actor)

            async def service(operation, value):
                self.assertEqual(IDENTITY.get(), actor)
                if actor == "revoked":
                    raise NativeStoreError("Current entry authority withdrawn")
                effects.append(actor)
                return {"errors": []} if operation == "advance" else board()

            return await pool.run(service)

        rejected, accepted = await asyncio.gather(job("revoked"), job("current"))
        self.assertTrue(rejected["errors"])
        self.assertTrue(rejected["host_errors"])
        self.assertFalse(accepted["errors"])
        self.assertEqual(set(effects), {"current"})

    async def test_cancel_during_queued_send_does_not_kill_peer(self):
        pool = self.pool()
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []

        async def service(operation, value):
            calls.append(operation)
            if operation == "advance":
                return {"errors": []}
            entered.set()
            await release.wait()
            return board()

        peer = asyncio.create_task(pool.run(service))
        await asyncio.wait_for(entered.wait(), 5)
        pid = pool.process.pid
        async with pool.write_lock:
            caller = asyncio.create_task(pool.run(service))

            async def queued():
                while not pool.write_bytes:
                    await asyncio.sleep(0)

            await asyncio.wait_for(queued(), 5)
            self.assertEqual(len(pool.jobs), 2)
            caller.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await caller
            self.assertIsNone(pool.broken)
        release.set()
        self.assertFalse((await asyncio.wait_for(peer, 5))["errors"])
        if pool.jobs:
            await asyncio.wait_for(asyncio.gather(*(job["future"] for job in pool.jobs.values())), 5)
        self.assertEqual(calls.count("advance"), 2)
        self.assertEqual(calls.count("inspect"), 2)
        self.assertEqual(pool.process.pid, pid)
        terminal = await pool.close()
        self.assertEqual(terminal["exit_code"], 0)
        self.assertIsNone(terminal["failure"])

    async def test_cancel_first_caller_during_spawn_keeps_single_owned_start(self):
        pool = self.pool()
        entered, release = asyncio.Event(), asyncio.Event()
        spawn = asyncio.create_subprocess_exec
        spawned = []

        async def gated_spawn(*args, **kwargs):
            entered.set()
            await release.wait()
            process = await spawn(*args, **kwargs)
            spawned.append(process)
            return process

        async def service(operation, value):
            return {"errors": []} if operation == "advance" else board()

        with patch("native_execution_host.asyncio.create_subprocess_exec", side_effect=gated_spawn):
            caller = asyncio.create_task(pool.run(service))
            await asyncio.wait_for(entered.wait(), 5)
            caller.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await caller
            peer = asyncio.create_task(pool.run(service))
            release.set()
            self.assertFalse((await asyncio.wait_for(peer, 5))["errors"])
        self.assertEqual(len(spawned), 1)
        self.assertEqual((await pool.close())["exit_code"], 0)
        self.assertEqual(spawned[0].returncode, 0)

    async def test_unrecognized_context_breaks_transport_without_dispatch_or_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "wrong.mjs"
            script.write_text(
                "process.stdin.once('data', () => {process.stdout.write(JSON.stringify("
                "{type:'rpc',job:999,id:1,operation:'execute',value:{}})+'\\n');});",
                encoding="utf-8",
            )
            pool = self.pool(script)
            effects = []

            async def service(operation, value):
                effects.append(operation)

            with self.assertRaisesRegex(NativeStoreError, "Unknown dispatcher context"):
                await asyncio.wait_for(pool.run(service), 5)
            pid = pool.process.pid
            with self.assertRaisesRegex(NativeStoreError, "no automatic replay"):
                await pool.run(service)
            self.assertEqual(pool.process.pid, pid)
            self.assertEqual(effects, [])
            self.assertTrue((await pool.close())["physical_terminal"])

    async def test_exited_pipe_keeps_started_effect_and_never_replays_it(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "exit.mjs"
            script.write_text(
                "process.stdin.once('data', () => {process.stdout.write(JSON.stringify("
                "{type:'rpc',job:1,id:1,operation:'execute',value:{}})+'\\n', () => process.exit(2));});",
                encoding="utf-8",
            )
            pool = self.pool(script)
            entered, release = asyncio.Event(), asyncio.Event()
            effects = []

            async def service(operation, value):
                effects.append(operation)
                entered.set()
                await release.wait()
                return {"durably_recorded": True}

            task = asyncio.create_task(pool.run(service))
            await asyncio.wait_for(entered.wait(), 5)
            with self.assertRaisesRegex(NativeStoreError, "no replay"):
                await asyncio.wait_for(task, 5)
            closing = asyncio.create_task(pool.close())
            await asyncio.sleep(0)
            self.assertFalse(closing.done())
            release.set()
            terminal = await asyncio.wait_for(closing, 5)
            self.assertEqual(terminal["exit_code"], 2)
            self.assertEqual(effects, ["execute"])
            with self.assertRaises(NativeStoreError):
                await pool.run(service)
