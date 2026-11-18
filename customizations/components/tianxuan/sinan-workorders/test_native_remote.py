"""Real HTTP, independent node process/database; deterministic producer only."""
# ruff: noqa: F811

import json
import os
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import uvicorn
from api import create_app
from native_node_api import mount_native_nodes
from native_remote_worker import RemoteNativeWorker
from native_store import _digest
from test_native_workflow import fixture, reserve, task  # noqa: F401


def test_real_http_separate_node_process(fixture, monkeypatch):
    w, actor, tenant, _, _, root = fixture
    local = w.worker
    token = "test-node-secret-with-adequate-length"
    installation = local.installation("local")
    remote = RemoteNativeWorker(
        local.store,
        root / "remote",
        {"local": {"timeout": 5, "installation": installation}},
        authorize=local.intake.authorize,
        nodes={
            "node-a": {
                "tenant": tenant,
                "token_sha256": _digest(token.encode()),
                "profiles": {"local": installation},
                "capacity": 1,
                "enabled": True,
                "package": _digest(Path(__file__).with_name("native_node.py").read_bytes()),
            }
        },
        single_coordinator=True,
    )
    w.worker = remote
    remote.bind(w)
    key, _ = task(fixture, "a")
    reserve(fixture, key)
    assert w.execute(actor, key)["state"] == "running"
    monkeypatch.setenv("TIANXUAN_REQUIRE_KEYS", "1")
    monkeypatch.setenv("TIANXUAN_TENANT_ID", tenant)
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://test.invalid")
    app = mount_native_nodes(
        create_app(w.domain, native_store=local.store, native_only=True, native_workflow=w), remote
    )
    sock = socket.socket()
    if os.name != "nt":
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    url = "http://127.0.0.1:" + str(port)
    try:
        assert httpx.get(url + "/api/v1/models", headers={"Authorization": "Bearer " + token}).status_code == 401
        assert (
            httpx.get(url + "/native-nodes/execution/" + key, headers={"Authorization": "Bearer wrong"}).status_code
            == 403
        )
        (root / "token").write_text(token)
        config = {
            "database": str(root / "node.sqlite"),
            "root": str(root / "node-work"),
            "profiles": local.profiles,
            "server": url,
            "token_file": str(root / "token"),
        }
        (root / "node.json").write_text(json.dumps(config))
        command = [
            sys.executable,
            str(Path(__file__).with_name("native_node.py")),
            "--config",
            str(root / "node.json"),
            "--once",
        ]
        completed = subprocess.run(command, capture_output=True, timeout=35)
        assert completed.returncode == 0, repr(completed.stderr)
        assert w.status(actor, key)["state"] == "produced"
        assert (root / "node.sqlite").exists()
        assert not (remote.root / key).exists()
        before = (root / "node-work" / key / "interval.json").read_bytes()
        # Identical closure transport replay cannot launch the producer twice.
        from native_node import NativeNode
        from native_store import NativeStore
        from native_worker import NativeWorker

        node_worker = NativeWorker(
            NativeStore(root / "node.sqlite"),
            root / "node-work",
            local.profiles,
            lambda *a: True,
            authorize=lambda *a: True,
        )
        node = NativeNode(node_worker, url, token)
        assert node.send_closed(key)
        assert (root / "node-work" / key / "interval.json").read_bytes() == before
        with node_worker.store._connection() as db:
            physical = json.loads(
                db.execute("SELECT payload FROM native_worker_process_closures WHERE execution=?", (key,)).fetchone()[0]
            )
            output = json.loads(
                db.execute("SELECT payload FROM native_worker_closed WHERE execution=?", (key,)).fetchone()[0]
            )
        physical["exit_code"] = 99
        assert (
            httpx.post(
                url + "/native-nodes/execution/" + key + "/receipt",
                headers={"Authorization": "Bearer " + token},
                json={"execution": key, "physical": physical, "output": output},
            ).status_code
            == 409
        )
        remote.nodes["node-b"] = {
            **remote.nodes["node-a"],
            "tenant": "different-org",
            "token_sha256": _digest(b"other-token"),
        }
        assert (
            httpx.get(
                url + "/native-nodes/execution/" + key, headers={"Authorization": "Bearer other-token"}
            ).status_code
            == 409
        )
        # Unknown ownership is retained independently of transport connection.
        second, _ = task(fixture, "b")
        reserve(fixture, second)
        second_task = json.loads(w.status(actor, second)["task"])
        with w._transaction() as db:
            assert remote.available_node(db, second_task) is None
        completed = subprocess.run(command, capture_output=True, timeout=35)
        assert completed.returncode == 0, repr(completed.stderr)
        assert w.status(actor, second)["state"] == "produced"
        assert w.check(actor, key)["check"]["outcome"] == "passed"
        assert w.check(actor, second)["check"]["outcome"] == "passed"
        from test_native_workflow import accept

        first_acceptance, second_acceptance = accept(fixture, key), accept(fixture, second)
        requirement, initial = fixture[3], fixture[4]
        joint_issue = w.domain.create_issue(actor, "c", requirement_id=requirement["id"], acceptance="passed check")
        w.next_issues = lambda operator, event: [joint_issue["id"]]
        w.installed_plan = lambda operator, issue: dict(
            selected={**first_acceptance["modules"], **second_acceptance["modules"], "c": initial["c"]},
            writes={"c": "*"},
            dependencies={key: w.status(actor, key)["acceptance"], second: w.status(actor, second)["acceptance"]},
            profile="local",
            product="c",
            checks=["check"],
            mandate="authorized-test",
        )
        continued = w.advance(actor)
        assert len(set(continued)) == 1
        joint = continued[0]
        assert w.advance(actor) == []
        reserve(fixture, joint)
        completed = subprocess.run(command, capture_output=True, timeout=35)
        assert completed.returncode == 0, repr(completed.stderr)
        joint_acceptance = accept(fixture, joint)
        assert local.store.read(tenant, "c", joint_acceptance["modules"]["c"], "output") == b"a produced b produced"
        revoked, _ = task(fixture, "a")
        reserve(fixture, revoked)
        revoked_node = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        original_authorizer = remote.intake.authorize
        try:
            deadline = time.monotonic() + 10
            while not (root / "node-work" / revoked / "work").exists() and time.monotonic() < deadline:
                time.sleep(0.005)
            assert (root / "node-work" / revoked / "work").exists()
            remote.intake.authorize = lambda *args: False
            _, stderr = revoked_node.communicate(timeout=15)
            assert revoked_node.returncode == 0, stderr
            assert w.status(actor, revoked)["state"] == "closed-unresolved"
            assert w.status(actor, revoked)["terminal"] is None
            with w._transaction() as db:
                assert (
                    db.execute("SELECT closed FROM native_remote_assignments WHERE execution=?", (revoked,)).fetchone()[
                        0
                    ]
                    == 1
                )
        finally:
            remote.intake.authorize = original_authorizer
            if revoked_node.poll() is None:
                revoked_node.terminate()
                revoked_node.communicate(timeout=10)
        never_started, _ = task(fixture, "a")
        reserve(fixture, never_started)
        remote.cancel(never_started)
        completed = subprocess.run(command, capture_output=True, timeout=35)
        assert completed.returncode == 0, repr(completed.stderr)
        assert w.status(actor, never_started)["state"] == "closed-unresolved"
        assert not (root / "node-work" / never_started).exists()

        # Install a real parent + sleeping descendant, then cancel via outbound event.
        local.profiles["local"]["argv"][-1] = (
            "import subprocess,sys,pathlib,time; "
            "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
            "(pathlib.Path.cwd().parent/'child.pid').write_text(str(child.pid)); time.sleep(60)"
        )
        installation = local.installation("local")
        remote.profiles["local"]["installation"] = installation
        remote.nodes["node-a"]["profiles"]["local"] = installation
        config["profiles"] = local.profiles
        (root / "node.json").write_text(json.dumps(config))
        running, _ = task(fixture, "a")
        reserve(fixture, running)
        process = subprocess.Popen(command[:-1], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            marker = root / "node-work" / running / "child.pid"
            deadline = time.monotonic() + 10
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            assert marker.exists()
            child_pid = int(marker.read_text())
            remote.cancel(running)
            deadline = time.monotonic() + 10
            while w.status(actor, running)["state"] in {"reserved", "running"} and time.monotonic() < deadline:
                time.sleep(0.02)
            assert w.status(actor, running)["state"] == "closed-unresolved"
            if os.name == "nt":
                import ctypes

                handle = ctypes.windll.kernel32.OpenProcess(0x100000, False, child_pid)
                if handle:
                    try:
                        assert ctypes.windll.kernel32.WaitForSingleObject(handle, 0) == 0
                    finally:
                        ctypes.windll.kernel32.CloseHandle(handle)
        finally:
            process.terminate()
            process.communicate(timeout=10)

        # Node restart with durable unknown launch intent must never relaunch.
        unknown, _ = task(fixture, "a")
        reserve(fixture, unknown)
        with node_worker.store._connection(write=True) as db:
            db.execute("INSERT INTO native_node_received(execution) VALUES(?)", (unknown,))
            db.execute(
                "INSERT INTO native_node_intents VALUES(?,?,'intent')", (unknown, w.status(actor, unknown)["task"])
            )
        completed = subprocess.run(command, capture_output=True, timeout=35)
        assert completed.returncode == 0, repr(completed.stderr)
        assert not (root / "node-work" / unknown).exists()
        assert w.status(actor, unknown)["state"] == "reserved"
        # Restart the HTTP coordinator in a distinct OS process over durable DBs.
        # A disconnected node may leave a real 25-second event wait. Prove that
        # restart waits for actual shutdown instead of treating join(5) as exit.
        waiting = threading.Event()
        condition_wait = remote.condition.wait

        def observed_wait(timeout=None):
            waiting.set()
            return condition_wait(timeout)

        monkeypatch.setattr(remote.condition, "wait", observed_wait)
        with w._transaction() as db:
            cursor = db.execute("SELECT COALESCE(MAX(cursor),0) FROM native_remote_events").fetchone()[0]
        with ThreadPoolExecutor(max_workers=1) as observers:
            pending = observers.submit(
                httpx.get,
                url + "/native-nodes/events?cursor=" + str(cursor),
                headers={"Authorization": "Bearer " + token},
                timeout=35,
            )
            assert waiting.wait(5)
            server.should_exit = True
            thread.join(35)
            assert not thread.is_alive(), "Coordinator shutdown incomplete; do not hand off its database"
            assert pending.result(timeout=5).status_code == 200
        with w._transaction() as db:
            db.execute("INSERT INTO native_remote_events(node,execution,kind) VALUES(?,?,'offer')", ("node-a", unknown))
        server_config = {"profiles": remote.profiles, "nodes": remote.nodes, "catalog": w.catalog}
        (root / "server.json").write_text(json.dumps(server_config))
        source = Path(__file__).resolve().parent
        script = (
            "import sys,json,pathlib; "
            f"sys.path[:0]={[str(source), str(source.parent / 'server'), str(source.parent / 'duobao')]!r}; "
            "from native_remote_worker import RemoteNativeWorker; from native_store import NativeStore; "
            "from native_workflow import NativeWorkflow; from tianxuan_core import Tianxuan; "
            "from api import create_app; from native_node_api import mount_native_nodes; import uvicorn; "
            f"root=pathlib.Path({str(root)!r}); config=json.loads((root/'server.json').read_text()); "
            "domain=Tianxuan(str(root/'domain.sqlite')); store=NativeStore(root/'native.sqlite'); "
            "worker=RemoteNativeWorker(store,root/'remote',config['profiles'],authorize=lambda *a:True,nodes=config['nodes'],single_coordinator=True); "
            "workflow=NativeWorkflow(domain,worker,None,None,lambda *a:True,catalog=config['catalog']); worker.bind(workflow); "
            "app=mount_native_nodes(create_app(domain,native_store=store,native_only=True,native_workflow=workflow),worker); "
            f"uvicorn.run(app,host='127.0.0.1',port={port},log_level='error')"
        )
        restarted = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if restarted.poll() is not None:
                    _, error = restarted.communicate(timeout=5)
                    raise AssertionError(f"Coordinator failed to start: {error!r}")
                try:
                    if httpx.get(url + "/api/v1/health").status_code == 200:
                        break
                except httpx.TransportError:
                    time.sleep(0.05)
            else:
                raise AssertionError("Replacement coordinator did not become ready")
            completed = subprocess.run(command, capture_output=True, timeout=35)
            assert completed.returncode == 0, repr(completed.stderr)
            assert not (root / "node-work" / unknown).exists()
            assert w.status(actor, unknown)["state"] == "reserved"
        finally:
            restarted.terminate()
            restarted.communicate(timeout=10)
        remote.nodes["node-a"]["enabled"] = False
        import pytest
        from native_store import NativeStoreError

        with pytest.raises(NativeStoreError):
            remote.authenticate(token)
    finally:
        server.should_exit = True
        thread.join(35)
        assert not thread.is_alive(), "Coordinator shutdown incomplete; do not hand off its database"
        sock.close()
