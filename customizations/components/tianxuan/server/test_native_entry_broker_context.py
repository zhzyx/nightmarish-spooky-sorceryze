"""Actual new signing bridge with an evaluated deterministic installed proposal process.

Synthetic framework admission is restricted to the owned fixture installation.
No actual model, provider, network listener or production configuration is used.
"""

# ruff: noqa: F811
import hashlib
import json
import os
import shutil
import socket
import sys
import threading
import time
from contextvars import ContextVar
from pathlib import Path
from types import SimpleNamespace

import native_entry_producer as bridge
import pytest
import runner
import uvicorn
from fastapi import FastAPI
from native_entry_context import EntryContexts, mount_entry_runtime
from test_native_entry_context import policy
from test_native_model_producer import SCHEMA, framework, installed
from test_native_workflow import fixture, reserve  # noqa: F401


def test_actual_broker_context_http(fixture, monkeypatch, broker_rpc):
    w, actor, tenant, requirement, initial, tmp = fixture
    profile, environment = installed(tmp, monkeypatch)
    from native_proposal_adapter import host_for
    from test_native_context import make_host

    host = make_host(tmp)
    profile.update(
        native_installation=host.installed,
        validation_probe=str(host.wrapper),
        validation_probe_sha256=hashlib.sha256(host.wrapper.read_bytes()).hexdigest(),
        model="test",
    )
    profile["installation_digest"] = host_for(profile).configuration()[1]
    evidence = dict(
        profile_digest=runner.digest({k: v for k, v in profile.items() if k != "evaluation"}),
        scope="synthetic",
        passed_task_types=["native"],
    )
    evidence_path = tmp / "context-evaluation.json"
    evidence_path.write_text(runner.canonical(evidence), encoding="utf-8")
    profile["evaluation"] = {
        **evidence,
        "evidence_ref": str(evidence_path),
        "evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
    }
    framework_root = framework(tmp)
    registry = tmp / "entry-registry"
    registry.mkdir()
    key_file = tmp / "signing-key"
    key_file.write_text(os.environ["GONGGONG_HOST_KEY"], encoding="utf-8")
    node_path = os.environ.get("NATIVE_TEST_NODE") or shutil.which("node")
    if not node_path:
        pytest.skip("Installed Node required")
    node = Path(node_path)
    central = dict(
        state_dir=str(tmp / "entry-budget"), max_calls=10, max_concurrent=2, authority_ref="synthetic-central"
    )
    template = dict(
        task=dict(
            id="template",
            tenant_id="template",
            project_id="test",
            agent_id="yanshi",
            outcome="finite native production",
            authority_ref="synthetic",
            retention="test",
            mode="autonomous",
            validation_only=True,
            work_items=["test-only"],
            input={},
            steps=[
                dict(
                    id="proposal",
                    kind="native",
                    instruction="fixed proposal",
                    output="json",
                    schema=SCHEMA,
                    tools=["native_context"],
                )
            ],
        ),
        profiles=[profile],
        limits=dict(max_calls=4, max_output_tokens=None, output_token_limit="unsupported"),
        central_budget=central,
    )
    template_path = tmp / "template.json"
    template_path.write_text(runner.canonical(template), encoding="utf-8")
    config = dict(
        template=str(template_path),
        template_sha256=hashlib.sha256(template_path.read_bytes()).hexdigest(),
        framework=str(framework_root),
        framework_sha256=hashlib.sha256((framework_root / "framework-manifest.json").read_bytes()).hexdigest(),
        runtime_sha256=runner.runtime_digest(),
        node=str(node),
        node_sha256=hashlib.sha256(node.read_bytes()).hexdigest(),
        python=sys.executable,
        python_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
        state=central["state_dir"],
        key_file=str(key_file),
        authority_ref="synthetic",
        context_transport=broker_rpc[0],
    )
    config_path = tmp / "broker.json"
    config_path.write_text(runner.canonical(config), encoding="utf-8")
    w.worker.profiles["local"] = dict(
        argv=[
            sys.executable,
            "-B",
            "-X",
            "utf8",
            str(Path(bridge.__file__)),
            "--config",
            str(config_path),
            "--sha256",
            hashlib.sha256(config_path.read_bytes()).hexdigest(),
            "--registry",
            str(registry),
        ],
        env={k: v for k, v in environment.items() if k.upper() in {"SYSTEMROOT", "WINDIR"}},
        timeout=60,
        log_bytes=20000,
    )
    local_worker = w.worker
    if broker_rpc[2]:
        import native_node
        from native_remote_worker import RemoteNativeWorker

        remote_spec = dict(
            profiles={"local": dict(timeout=60, installation=local_worker.installation("local"))},
            nodes={
                "node-a": dict(
                    tenant=tenant,
                    token_sha256=hashlib.sha256(b"local-secret").hexdigest(),
                    profiles={"local": local_worker.installation("local")},
                    capacity=1,
                    enabled=True,
                    package=hashlib.sha256(Path(native_node.__file__).read_bytes()).hexdigest(),
                )
            },
        )
        entry = broker_rpc[1]
        spec = json.loads(entry.runtime_installation.path.read_text())
        spec["remote"] = remote_spec
        entry.runtime_installation.path.write_text(json.dumps(spec))
        entry.runtime_installation.sha256 = hashlib.sha256(entry.runtime_installation.path.read_bytes()).hexdigest()
        w.worker = RemoteNativeWorker(
            local_worker.store,
            tmp / "remote",
            remote_spec["profiles"],
            authorize=local_worker.intake.authorize,
            nodes=remote_spec["nodes"],
            single_coordinator=True,
        )
        w.worker.bind(w)
        w.worker.context_receipt_reader = entry.contexts.receipt
        from native_store import NativeStore
        from native_worker import NativeWorker

        local_worker = NativeWorker(
            NativeStore(tmp / "node.sqlite"),
            tmp / "node-work",
            local_worker.profiles,
            lambda *args: True,
            authorize=lambda *args: True,
            contract_registry=registry,
        )
    issue = w.domain.create_issue(actor, "a", requirement_id=requirement["id"], acceptance="passed check")
    key = w.authorize_task(
        actor,
        issue["id"],
        selected={"a": initial["a"]},
        writes={"a": ["output"]},
        dependencies={},
        profile="local",
        product="a",
        checks=["check"],
        mandate="synthetic",
    )
    contract = json.loads(w.status(actor, key)["task"])
    (registry / (key + ".contract.json")).write_text(runner.canonical(contract), encoding="utf-8")
    reserve(fixture, key)
    result = w.execute(actor, key)
    if broker_rpc[2]:
        from native_node import NativeNode

        node_client = NativeNode(local_worker, broker_rpc[0]["server"], "local-secret")
        try:
            node_client.execute(key, threading.Event())
            assert w.reconcile(actor, key)["state"] == "produced"
            result = w.worker.reconcile(contract, key)
        finally:
            node_client.pool.shutdown(wait=True)
    assert result["state"] == "produced", (
        result,
        (local_worker.root / key / "process.log").read_text(encoding="utf-8"),
    )
    assert result["context_receipt"]["terminal"] == "final"
    assert result["context_receipt"]["reads"] is None
    assert w.worker.process_closed(contract, key)
    assert (local_worker.root / key / "work/a/output").read_bytes() == b"context-consumed"
    registration = runner.read(registry / (key + ".json"))
    grant = registration["grant"]
    assert grant["signature"] == runner.signature(grant["payload"])
    assert grant["payload"]["state_dir"] == str(
        Path(central["state_dir"]) / "tasks" / runner.jid_for(grant["payload"]["task"])
    )
    assert grant["payload"]["task"]["input"]["native_binding"]["definition"] == contract["source"]["definition"]
    assert "GONGGONG_HOST_KEY" not in local_worker.profiles["local"]["env"]
    if broker_rpc[2]:
        assert set(w.worker.profiles["local"]) == {"timeout", "installation"}


@pytest.fixture(params=[False, True])
def broker_rpc(fixture, request):
    w, actor, tenant, req, initial, root = fixture
    installed = policy(root)
    spec = json.loads(installed.path.read_text())
    spec["context"]["full_bytes"] = 0
    installed.path.write_text(json.dumps(spec))
    installed.sha256 = hashlib.sha256(installed.path.read_bytes()).hexdigest()
    entry = SimpleNamespace(
        root=root,
        native=w.worker.store,
        domain=w.domain,
        workflow=w,
        installation=SimpleNamespace(sha256="installed", verify=lambda: True),
        runtime_installation=installed,
        current_entry=ContextVar("test-entry", default=None),
        entry_authority=lambda mandate: True,
        module_authority=lambda *args: True,
    )
    entry.contexts = EntryContexts(entry, installed)
    w.worker.context_receipt_reader = entry.contexts.receipt
    from native_node_api import mount_native_nodes

    class CurrentWorker:
        def close(self):
            if hasattr(w.worker, "owner"):
                w.worker.close()

        def __getattr__(self, name):
            return getattr(w.worker, name)

    app = mount_entry_runtime(mount_native_nodes(FastAPI(), CurrentWorker()), entry)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", timeout_graceful_shutdown=3))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started
    token = root / "context-token"
    token.write_text("local-secret")
    try:
        yield (
            dict(server="http://127.0.0.1:" + str(sock.getsockname()[1]), token_file=str(token)),
            entry,
            request.param,
        )
    finally:
        server.should_exit = True
        thread.join(10)
        sock.close()
        assert not thread.is_alive()
