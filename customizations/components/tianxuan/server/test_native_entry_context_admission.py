"""End-to-end loopback admission, including physical executor residency."""

import asyncio
import json
import time
from contextlib import ExitStack

import httpx
from test_native_entry_context import live_context  # noqa: F401
from test_native_workflow import fixture  # noqa: F401

# ruff: noqa: F811


def post(client, c, method="check", timeout=40):
    args = [{"op": "manifest", "cursor": None}] if method == "resolve" else []
    return client.post(
        c.url + "/native-context/" + c.execution,
        headers={"Authorization": "Bearer " + c.token},
        json={"method": method, "args": args},
        timeout=timeout,
    )


def test_real_http_72_request_bound(live_context):
    e, c, _, _ = live_context

    async def burst():
        async with httpx.AsyncClient(limits=httpx.Limits(max_connections=90)) as client:
            pending = [asyncio.create_task(post(client, c)) for _ in range(72)]
            for _ in range(300):
                if sum(p.done() for p in pending) >= 40 and e.contexts._waiters == 32:
                    break
                await asyncio.sleep(0.01)
            completed = [p.result() for p in pending if p.done()]
            assert len(completed) == 40
            assert all(r.status_code == 503 and r.json()["detail"]["status"] == "not_started" for r in completed)
            assert e.contexts._waiters == 32
            print("HTTP_BOUND", json.dumps({"requests": 72, "rejected": 40, "waiters": 32}))
            stack.close()
            responses = await asyncio.gather(*pending)
            assert sum(r.status_code == 200 for r in responses) == 32

    with ExitStack() as stack:
        for n in range(16):
            stack.enter_context(e.contexts._lease("occupied-" + str(n)))
        asyncio.run(burst())


def test_original_35_second_http_timeout_negative(live_context):
    e, c, _, _ = live_context

    async def race():
        async with httpx.AsyncClient(limits=httpx.Limits(max_connections=90)) as client:
            blockers = [asyncio.create_task(post(client, c)) for _ in range(28)]
            while e.contexts._waiters < 28:
                await asyncio.sleep(0.01)
            start = time.monotonic()
            response = await post(client, c, "resolve", timeout=35)
            elapsed = time.monotonic() - start
            assert response.status_code == 503 and elapsed < 35
            assert response.json()["detail"]["status"] == "not_started"
            assert not e.contexts.context(c.execution).events()
            stack.close()
            await asyncio.gather(*blockers)
            await asyncio.sleep(0.2)
            assert not e.contexts.context(c.execution).events()
            print("ORIGINAL_TIMEOUT_NEGATIVE", round(elapsed, 2), response.status_code, "no started events")

    with ExitStack() as stack:
        for n in range(16):
            stack.enter_context(e.contexts._lease("occupied-" + str(n)))
        asyncio.run(race())


def test_delayed_executor_keeps_occupancy_and_never_starts(live_context, monkeypatch):
    from concurrent.futures.thread import _WorkItem

    e, c, _, _ = live_context
    e.contexts.wait_seconds = 0.15
    original = _WorkItem.run

    def delayed(self):
        # Actual dedicated executor work is held before invoking the callable.
        time.sleep(1)
        original(self)

    monkeypatch.setattr(_WorkItem, "run", delayed)

    async def probe():
        async with httpx.AsyncClient(limits=httpx.Limits(max_connections=90)) as client:
            results = await asyncio.gather(*(post(client, c, "resolve") for _ in range(32)))
            assert all(r.status_code == 503 for r in results)
            second = await post(client, c)
            assert second.status_code == 503
            assert not e.contexts.context(c.execution).events()
            await asyncio.sleep(1.2)
            assert not e.contexts.context(c.execution).events()
            monkeypatch.setattr(_WorkItem, "run", original)
            e.contexts.wait_seconds = 30
            assert (await post(client, c)).status_code == 200

    asyncio.run(probe())


def test_disconnected_waiter_never_starts(live_context):
    e, c, _, _ = live_context

    async def probe():
        from urllib.parse import urlsplit

        target = urlsplit(c.url)
        reader, writer = await asyncio.open_connection(target.hostname, target.port)
        body = json.dumps({"method": "resolve", "args": [{"op": "manifest", "cursor": None}]}).encode()
        headers = (
            f"POST /native-context/{c.execution} HTTP/1.1\r\nHost: localhost\r\n"
            f"Authorization: Bearer {c.token}\r\nContent-Length: {len(body)}\r\n\r\n"
        ).encode()
        writer.write(headers + body)
        await writer.drain()
        for _ in range(300):
            if e.contexts._waiters == 1:
                break
            await asyncio.sleep(0.01)
        assert e.contexts._waiters == 1
        writer.close()
        await writer.wait_closed()
        for _ in range(300):
            if e.contexts._waiters == 0:
                break
            await asyncio.sleep(0.01)
        assert e.contexts._waiters == 0
        stack.close()
        await asyncio.sleep(0.1)
        assert not e.contexts.context(c.execution).events()

    with ExitStack() as stack:
        for n in range(16):
            stack.enter_context(e.contexts._lease("occupied-" + str(n)))
        asyncio.run(probe())


def test_inflight_disconnect_preserves_physical_lease(live_context, monkeypatch):
    import threading

    from native_context import NativeContext

    e, c, _, _ = live_context
    entered, release = threading.Event(), threading.Event()
    original = NativeContext.resolve

    def held(self, *args):
        entered.set()
        assert release.wait(5)
        return original(self, *args)

    monkeypatch.setattr(NativeContext, "resolve", held)

    async def probe():
        async with httpx.AsyncClient() as client:
            pending = asyncio.create_task(post(client, c, "resolve", timeout=0.15))
            try:
                await pending
            except httpx.ReadTimeout:
                pass
            else:
                raise AssertionError("Expected actual transport disconnect")
            assert entered.is_set()
            await asyncio.sleep(0.1)
            assert e.contexts._contexts[c.execution]["busy"]
            release.set()
            for _ in range(200):
                if not e.contexts._contexts[c.execution]["busy"]:
                    break
                await asyncio.sleep(0.01)
            assert not e.contexts._contexts[c.execution]["busy"]
            assert [x["kind"] for x in e.contexts.context(c.execution).events()] == ["started", "resolved"]

    try:
        asyncio.run(probe())
    finally:
        release.set()


def test_body_limit_and_typed_not_started(live_context):
    import pytest
    from native_entry_context_client import ContextNotStarted

    e, c, _, _ = live_context

    async def probe():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                c.url + "/native-context/" + c.execution,
                headers={"Authorization": "Bearer " + c.token},
                content=b"x" * 262145,
            )
            assert response.status_code == 413

    asyncio.run(probe())
    e.contexts.wait_seconds = 0.05
    with e.contexts._lease(c.execution):
        with pytest.raises(ContextNotStarted):
            c.resolve({"op": "manifest", "cursor": None})
    assert not e.contexts.context(c.execution).events()


def test_waiting_authority_revoked_before_capacity_release(live_context):
    e, c, active, _ = live_context

    async def probe():
        async with httpx.AsyncClient() as client:
            pending = asyncio.create_task(post(client, c, "resolve"))
            for _ in range(300):
                if e.contexts._waiters == 1:
                    break
                await asyncio.sleep(0.01)
            assert e.contexts._waiters == 1
            active["allow"] = False
            assert (await asyncio.wait_for(pending, 3)).status_code == 409
            assert e.contexts._waiters == 0
            active["allow"] = True
            assert not e.contexts.context(c.execution).events()

    with ExitStack() as stack:
        for n in range(16):
            stack.enter_context(e.contexts._lease("occupied-" + str(n)))
        asyncio.run(probe())


def test_slow_body_uses_same_deadline(live_context):
    from urllib.parse import urlsplit

    e, c, _, _ = live_context
    e.contexts.wait_seconds = 0.1

    async def probe():
        target = urlsplit(c.url)
        reader, writer = await asyncio.open_connection(target.hostname, target.port)
        writer.write(
            (
                f"POST /native-context/{c.execution} HTTP/1.1\r\nHost: localhost\r\n"
                f"Authorization: Bearer {c.token}\r\nContent-Length: 100\r\n\r\n" + "{"
            ).encode()
        )
        await writer.drain()
        response = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 3)
        body = await asyncio.wait_for(reader.readexactly(63), 3)
        assert b"503" in response and b"not_started" in body
        writer.close()
        await writer.wait_closed()
        assert not e.contexts.context(c.execution).events()

    asyncio.run(probe())
