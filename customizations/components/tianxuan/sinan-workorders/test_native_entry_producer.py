"""Actual new signing bridge with an evaluated deterministic installed proposal process.

Synthetic framework admission is restricted to the owned fixture installation.
No actual model, provider, network listener or production configuration is used.
"""

# ruff: noqa: F811
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import native_entry_producer as bridge
import pytest
import runner
from native_model_host import executable_sha256
from test_native_model_producer import SCHEMA, framework, installed
from test_native_workflow import fixture, reserve  # noqa: F401


def test_actual_broker_signs_exact_finite_task_and_uses_central_budget(fixture, monkeypatch):
    node_path = os.environ.get("NATIVE_TEST_NODE") or shutil.which("node")
    if not node_path:
        pytest.skip("Installed Node required")
    node = Path(node_path).resolve()
    w, actor, tenant, requirement, initial, tmp = fixture
    profile, environment = installed(tmp, monkeypatch)
    framework_root = framework(tmp)
    registry = tmp / "entry-registry"
    registry.mkdir()
    key_file = tmp / "signing-key"
    key_file.write_text(os.environ["GONGGONG_HOST_KEY"], encoding="utf-8")
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
            mode="single",
            validation_only=True,
            work_items=["test-only"],
            input={},
            steps=[dict(id="proposal", kind="native", instruction="fixed proposal", output="json", schema=SCHEMA)],
        ),
        profiles=[profile],
        limits=dict(max_calls=1, max_output_tokens=None, output_token_limit="unsupported"),
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
        node_sha256=executable_sha256(node),
        python=sys.executable,
        python_sha256=executable_sha256(sys.executable),
        state=central["state_dir"],
        key_file=str(key_file),
        authority_ref="synthetic",
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
    assert result["state"] == "produced", (result, (w.worker.root / key / "process.log").read_text(encoding="utf-8"))
    assert w.worker.process_closed(contract, key)
    assert (w.worker.root / key / "work/a/output").read_bytes() == b"a produced"
    registration = runner.read(registry / (key + ".json"))
    grant = registration["grant"]
    assert grant["signature"] == runner.signature(grant["payload"])
    assert grant["payload"]["state_dir"] == str(
        Path(central["state_dir"]) / "tasks" / runner.jid_for(grant["payload"]["task"])
    )
    assert grant["payload"]["task"]["input"]["native_binding"]["definition"] == contract["source"]["definition"]
    assert "GONGGONG_HOST_KEY" not in w.worker.profiles["local"]["env"]
