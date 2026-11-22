"""Read back the native catalog, match two signed items and exercise credential loss/recovery."""

import json
import os
import shutil
import sys
from pathlib import Path

import native_entry_runtime  # noqa: F401 -- installs the host runtime adapter path
import pytest
import test_native_stage_admission
from native_entry_factory import installed_profile
from native_local_profiles import codex_login, codex_models, producer_catalog
from test_native_issue_capabilities import classify, dispatch

fixture = test_native_stage_admission.fixture
host = test_native_stage_admission.host


def cli_environment():
    return {k: v for k, v in os.environ.items() if k.upper() in {"WINDIR", "SYSTEMROOT", "PATH", "USERPROFILE", "HOME"}}


def test_signed_local_catalog(host, record_property):
    from native_proposal_adapter import installed_profile as cli_profile

    w, folder = host.workflow, host.calls.parent
    node = shutil.which("node")
    assert node
    cli = folder / "login.mjs"
    cli.write_text(
        "import fs from 'node:fs'; import path from 'node:path';\n"
        "if (process.argv.slice(2).join(' ') === 'debug models') {\n"
        "  const slug = path.basename(process.env.CODEX_HOME) + '-model';\n"
        "  const visibility = fs.existsSync(path.join(process.env.CODEX_HOME, 'hidden')) ? 'hide' : 'list';\n"
        "  console.log(JSON.stringify({models:[{slug,visibility}]})); process.exit(0);\n"
        "}\n"
        "if (process.argv.slice(2).join(' ') !== 'login status') process.exit(3);\n"
        "const ok = fs.existsSync(path.join(process.env.CODEX_HOME, 'signed-in'));\n"
        "console.error(ok ? 'Logged in using ChatGPT' : 'Not logged in'); process.exit(ok ? 0 : 1);\n",
        encoding="utf-8",
    )
    roles = ["coding", "animation"]
    profiles = []
    for role in roles:
        home = folder / role
        home.mkdir()
        (home / "signed-in").touch()
        model = role + "-model"
        profiles.append(
            cli_profile(
                role,
                dict(
                    node=node,
                    entry=str(cli),
                    python=sys.executable,
                    timeout=10,
                    model=model,
                    reasoning_effort=None,
                    env={**cli_environment(), "CODEX_HOME": str(home)},
                ),
            )
        )
        w.worker.profiles[role] = w.worker.profiles["local"]
    template = dict(task={"agent_id": "yanshi"}, profiles=profiles)
    w.observe_catalog = lambda: producer_catalog(template, {})
    w.catalog = [dict(id=role, available=True, capabilities=[role], targets=["agent"]) for role in roles]

    def plan(actor, issue):
        required = w.domain.issue_snapshot(actor, issue)["definition"]["required_capabilities"]
        profile = installed_profile(w.installed_catalog(), [], required, None)
        return {**host.plan, "profile": profile}

    w.installed_plan = plan
    tickets = []
    for role, issue in zip(roles, host.issues, strict=True):
        classify(host, issue, ["capability:" + role]).raise_for_status()
        host.target(issue)
        host.confirm(issue).raise_for_status()
        tickets.append(host.api("authorize", issue=issue["id"]).raise_for_status().json())

    def catalog():
        return host.api("inspect").raise_for_status().json()["environment"]["catalog"]

    def row(ticket):
        return host.api("status", key=ticket).raise_for_status().json()

    ready = catalog()
    assert [entry["localStatus"] for entry in ready] == [
        dict(agent="yanshi", requestedModel=role + "-model", status="ready") for role in roles
    ]
    original = cli.read_bytes()
    cli.write_bytes(original + b"\n// replaced installation")
    assert all(m["localStatus"]["status"] == "installation_unconfirmed" for m in catalog())
    cli.write_bytes(original)
    assert catalog() == ready
    hidden = folder / "animation" / "hidden"
    hidden.touch()
    assert catalog()[1]["localStatus"]["status"] == "model_missing"
    hidden.unlink()
    (folder / "animation" / "signed-in").unlink()
    partial = catalog()
    assert [entry["available"] for entry in partial] == [True, False]
    assert all(entry["configured"] for entry in partial)
    assert installed_profile(partial, [], ["animation"], None) == "animation"
    first = dispatch(host)
    assert [r["receipt"]["model"] for r in first["results"]] == ["coding"]
    (gap,) = first["deferred"]
    assert gap["ticket"] == tickets[1] and gap["requiredCapabilities"] == ["animation"]
    assert gap["missingCapabilities"] == [] and gap["localStatus"]["status"] == "credential_missing"
    assert row(tickets[1])["state"] == "ready" and not row(tickets[1])["assignment"]

    restored = folder / "animation" / "signed-in"
    restored.touch()
    task = json.loads(row(tickets[1])["task"])
    assignment = dict(
        ticket=tickets[1],
        sourceSnapshot=dict(source=tickets[1], revision=task["source"]["revision"]),
        model={"id": "animation", "localStatus": {"status": "caller_value"}},
    )
    assert host.api("reserve", assignment=assignment, event="restored").json() is True
    assert json.loads(row(tickets[1])["assignment"])["model"]["localStatus"] == ready[1]["localStatus"]
    restored.unlink()
    assert host.api("execute", key=tickets[1]).raise_for_status().json()["state"] == "ready"
    assert [o["execution"] for o in host.observations()] == tickets[:1]
    assert host.api("reserve", assignment=assignment, event="withdrawn").json() is False
    restored.touch()
    second = dispatch(host)
    assert [r["receipt"]["model"] for r in second["results"]] == ["animation"] and second["deferred"] == []
    assert [o["execution"] for o in host.observations()] == tickets
    receipts = []
    for ticket, role in zip(tickets, roles, strict=True):
        current = row(ticket)
        selected = json.loads(current["assignment"])["model"]
        assert current["state"] == "produced" and selected["capabilities"] == [role]
        assert selected["localStatus"] == dict(agent="yanshi", requestedModel=role + "-model", status="ready")
        receipts.append(dict(ticket=ticket, selected=selected, candidate=json.loads(current["terminal"])["candidate"]))
    record_property("local_catalog", json.dumps(dict(ready=ready, gap=gap, selected=receipts, physical_calls=2)))


def test_installed_codex_login(host, tmp_path, record_property):
    from native_proposal_adapter import installed_profile as cli_profile

    cli = shutil.which("codex")
    if not cli or Path(cli).suffix.lower() in {".cmd", ".bat", ".ps1"}:
        pytest.skip("Direct installed Codex CLI required for the host login check")
    env = cli_environment()
    if os.environ.get("CODEX_HOME"):
        env["CODEX_HOME"] = os.environ["CODEX_HOME"]
    installed = dict(entry=cli, env=env)
    account = codex_login(installed)
    models = codex_models(installed) if account == "ready" else None
    empty = codex_login({**installed, "env": {**env, "CODEX_HOME": str(tmp_path)}})
    assert account in {"ready", "credential_missing", "credential_unconfirmed"}
    assert empty == "credential_missing"
    matches = []
    if models and len(models) >= 2:
        w = host.workflow
        selections = list(zip(["coding", "animation"], sorted(models)[:2], strict=True))
        w.catalog = [dict(id=model, available=True, targets=["agent"], capabilities=[cap]) for cap, model in selections]
        profiles = [
            cli_profile(
                model,
                {
                    **installed,
                    "python": sys.executable,
                    "node": shutil.which("node"),
                    "model": model,
                    "reasoning_effort": None,
                    "timeout": 10,
                },
            )
            for _, model in selections
        ]
        w.observe_catalog = lambda: producer_catalog(dict(profiles=profiles, task={"agent_id": "yanshi"}), {})
        catalog = host.api("inspect").raise_for_status().json()["environment"]["catalog"]
        for capability, model in selections:
            assert installed_profile(catalog, [], [capability], None) == model
            observed = next(entry for entry in catalog if entry["id"] == model)
            assert observed["available"] and observed["localStatus"]["status"] == "ready"
            matches.append(observed)
    record_property(
        "installed_cli",
        json.dumps(
            dict(
                host_login=account,
                isolated_empty_login=empty,
                visible_models=sorted(models) if models is not None else None,
                matched_sample=matches,
                model_calls=0,
            )
        ),
    )


def test_role_catalog_uses_producer_identity_without_execution(tmp_path, monkeypatch):
    import hashlib
    import socket
    import ssl
    from concurrent.futures import ThreadPoolExecutor

    import native_role_service as service
    from test_native_entry_context_backpressure import _TLS_CERT, _TLS_KEY

    cert, key = tmp_path / "public-test-cert.pem", tmp_path / "public-test-key.pem"
    cert.write_text(_TLS_CERT)
    key.write_text(_TLS_KEY)
    template = dict(
        task={"agent_id": "yanshi"},
        profiles=[
            dict(id="service", protocol="chat-completions", model="sample", api_key_env="S02_CALLER_ONLY_TEST_VAR")
        ],
    )
    monkeypatch.setenv("S02_CALLER_ONLY_TEST_VAR", "caller-fixture")
    monkeypatch.setattr(native_entry_runtime, "load_config", lambda *_: ({"python": sys.executable}, template))
    monkeypatch.setattr(sys, "pycache_prefix", sys.pycache_prefix)
    monkeypatch.setattr(sys, "path", list(sys.path))
    script = Path(service.__file__).with_name("native_entry_producer.py")
    with socket.create_server(("127.0.0.1", 0)) as listener:
        settings = dict(
            address="127.0.0.1",
            port=listener.getsockname()[1],
            role="producer",
            server_name="localhost",
            ca_file=str(cert),
            certificate_file=str(cert),
            private_key_file=str(key),
            peer_sha256=hashlib.sha256(ssl.PEM_cert_to_DER_cert(_TLS_CERT)).hexdigest(),
            service_sha256="a" * 64,
            broker_sha256="b" * 64,
            broker_file=str(tmp_path / "broker.json"),
            script_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
            tree_sha256=service.tree_sha256(),
            service_identity=service.identity(),
            identity=service.identity(),
        )
        ctx, _ = service.endpoint(settings, True)

        def receiver():
            sock, _ = listener.accept()
            with sock, ctx.wrap_socket(sock, server_side=True) as conn:
                service.peer(conn, settings["peer_sha256"])
                request = service.receive(conn, service.MAX_REQUEST)
                result = service.launch(settings, request, conn, None, settings["service_sha256"], [])
                service.send(conn, result, service.MAX_RESULT)

        with ThreadPoolExecutor(max_workers=1) as pool:
            accepted = pool.submit(receiver)
            observation = service.exchange(settings, False, {}, inspect_catalog=True)
            accepted.result(timeout=10)
        assert observation == {"service": dict(agent="yanshi", requestedModel="sample", status="credential_missing")}
        assert set(tmp_path.iterdir()) == {cert, key}
