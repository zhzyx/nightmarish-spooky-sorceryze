"""Ordinary API entry with actual deterministic role subprocesses (no provider)."""

import hashlib
import importlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_native_entry_normal import HERE, PROGRAM

RESOLVER_PROGRAM = (
    PROGRAM
    .replace("('planner', 'reviewer')", "('planner', 'reviewer', 'resolver')")
    .replace(
        "tasks=[dict(id='result',title=r['document']['title'],body='Write deterministic accepted output',acceptance='output must equal deterministic accepted output',dependencies=[],scope='text',complexity='simple',outputs=['text/output'])]",
        "tasks=[dict(id=x.lower(),title=x,body='Preserve both A and B',acceptance='retain '+x,dependencies=[],scope='text',complexity='simple',outputs=['text/output']) for x in ['A','B']]",
    )
    .replace(
        " else:\n  data=",
        " elif role=='resolver':\n  pathlib.Path(__file__).with_suffix('.resolver-request').write_text(canonical(r))\n  proposal=dict(schema=1,plan=r['source'],conflicts_digest=r['document']['conflicts_digest'],edits=[dict(module=c['module'],path=c['path'],content_base64=base64.b64encode(b'AB').decode()) for c in r['document']['conflicts']],reason='Preserved both original contributions')\n else:\n  data=",
    )
    .replace("v==b'deterministic accepted output'", "v in (b'A',b'B',b'AB')")
    .replace(
        "(next(p.glob('*-text'))/'output').write_text('deterministic accepted output',encoding='utf-8')",
        "(next(p.glob('*-text'))/'output').write_text(json.loads(pathlib.Path(os.environ['NATIVE_CONTEXT']).read_text(encoding='utf-8'))['title'],encoding='utf-8')",
    )
    .replace("==b'deterministic accepted output'", "in (b'A',b'B',b'AB')")
)


@pytest.mark.parametrize(
    "window",
    [
        "signed",
        "signed-after-runtime",
        "normal",
        "no-conflict",
        "before-runtime",
        "during-runtime",
        "withdrawal",
        "unrelated",
        "after-runtime",
        "after-intake",
        "invalid-output",
    ],
)
def test_ordinary_installed_conflict(tmp_path, monkeypatch, window, request):
    signed = window.startswith("signed")
    if signed:
        signed_argv, signed_calls = request.getfixturevalue("signed_broker")
        from native_check_runner import _process_helper

        helper = _process_helper()
        original_owned = helper.run_owned

        def capture(*args, **kwargs):
            code = original_owned(*args, **kwargs)
            if code and kwargs.get("stderr"):
                kwargs["stderr"].seek(0)
                print(kwargs["stderr"].read().decode("utf-8", errors="replace"))
            return code

        monkeypatch.setattr(helper, "run_owned", capture)
    if window == "signed-after-runtime":
        window = "after-runtime"
    node = os.environ.get("NATIVE_TEST_NODE") or shutil.which("node")
    assert node, "Node required"
    root = tmp_path
    program = root / "roles.py"
    program_source = RESOLVER_PROGRAM.replace(
        " r=json.load(sys.stdin)",
        " r=json.load(sys.stdin)\n if role=='resolver' and '--recover' in sys.argv:\n  print(pathlib.Path(__file__).with_suffix('.resolver-receipt').read_text()); sys.exit(0)",
    )
    program_source = program_source.replace(
        " print(canonical(dict(input_digest=", " receipt=dict(input_digest="
    ).replace(
        "runtime_state='deterministic-test-installation')))",
        "runtime_state='deterministic-test-installation')\n if role=='resolver':\n  with pathlib.Path(__file__).with_suffix('.resolver-calls').open('a') as marker: marker.write('call\\n')\n  pathlib.Path(__file__).with_suffix('.resolver-receipt').write_text(canonical(receipt))\n print(canonical(receipt))",
    )
    if window == "no-conflict":
        program_source = program_source.replace("['title'],encoding='utf-8')", "['title'][0:0]+'A',encoding='utf-8')")
    if window == "during-runtime":
        program_source = program_source.replace(
            " elif role=='resolver':",
            " elif role=='resolver':\n  pathlib.Path(__file__).with_suffix('.resolver-calls').write_text('call\\n'); os._exit(7)",
        )
    if window in {"withdrawal", "unrelated"}:
        program_source = program_source.replace(
            " elif role=='resolver':",
            " elif role=='resolver':\n  import time\n  pathlib.Path(__file__).with_suffix('.resolver-wait').write_text('waiting'); time.sleep(2)",
        )
    if window == "invalid-output":
        program_source = program_source.replace("schema=1,plan=r['source']", "schema=1,plan='wrong'")
    program.write_text(program_source, encoding="utf-8", newline="\n")
    python = str(Path(sys.executable).resolve())
    node = str(Path(node).resolve())
    driver = str(HERE.parent / "sinan-workorders" / "native_entry_driver.mjs")
    environment = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR"}}
    files = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (python, node, str(program), driver)}
    commands = {
        r: dict(argv=[python, "-X", "utf8", str(program), r], env=environment)
        for r in ("planner", "producer", "checker", "reviewer", "resolver")
    }
    if signed:
        commands["resolver"]["argv"] = signed_argv
        for arg in signed_argv:
            if Path(arg).is_absolute() and Path(arg).is_file():
                files[arg] = hashlib.sha256(Path(arg).read_bytes()).hexdigest()
    commands["dispatcher"] = dict(argv=[node, driver], env=environment)
    spec = dict(
        version=3,
        mode="deterministic-test",
        identity="resolver-test",
        files=files,
        commands=commands,
        principals={r: "test-" + r for r in ("producer", "checker", "reviewer", "publisher", "resolver")},
        scopes={"text": {"outputs": ["text/output"]}},
        complexity={"simple": ["text"]},
        catalog=[dict(id="installed", available=True, targets=["agent"], capabilities=["text"])],
    )
    manifest = root / "installation.json"
    manifest.write_text(json.dumps(spec), encoding="utf-8", newline="\n")
    for k, v in dict(
        TIANXUAN_DB=str(root / "domain.sqlite"),
        TIANXUAN_NATIVE_DB=str(root / "native.sqlite"),
        TIANXUAN_STORAGE_MODE="native",
        TIANXUAN_NATIVE_INSTALLATION=str(manifest),
        TIANXUAN_NATIVE_INSTALLATION_SHA256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
        TIANXUAN_NATIVE_STATE=str(root / "state"),
    ).items():
        monkeypatch.setenv(k, v)
    sys.modules.pop("main", None)
    main = importlib.import_module("main")
    resolver = main._NATIVE_ENTRY.workflow.integration.installed_resolver
    if window in {"after-runtime", "after-intake"}:
        original_intake = resolver.intake

        def interrupt(*args):
            if window == "after-intake":
                original_intake(*args)
            raise RuntimeError("injected lost resolver reply")

        monkeypatch.setattr(resolver, "intake", interrupt)
    if window == "before-runtime":

        def interrupt(*args):
            raise RuntimeError("injected intent before runtime")

        monkeypatch.setattr(resolver, "run", interrupt)
    try:
        with TestClient(main.app) as client:
            account = dict(tenant_name="tenant", email="test@example.invalid", password="password123")
            assert client.post("/api/v1/auth/register", json=account).status_code == 200
            login = client.post("/api/v1/auth/session", json={k: account[k] for k in ("email", "password")}).json()
            headers = {"Authorization": "Bearer " + login["token"]}
            response = client.post(
                "/api/v1/requirements",
                headers=headers,
                json=dict(
                    request_id="resolution",
                    title="Preserve A and B",
                    outcome="AB",
                    scope="Text",
                    acceptance="Retain A and B",
                ),
            )
            assert response.status_code == 200, response.text
            requirement = response.json()["id"]
            response = client.post(
                "/api/v1/native/entry/execute",
                headers=headers,
                json=dict(requirement=requirement, call_id="execute", scopes=["text"]),
            )
            assert response.status_code == 200, response.text
            key = response.json()["entry"]
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if window in {"withdrawal", "unrelated"} and program.with_suffix(".resolver-wait").exists():
                    with main._STORE._connection_lock, main._STORE.db:
                        if window == "withdrawal":
                            main._STORE.db.execute(
                                "UPDATE issues SET acceptance='withdrawn' WHERE id IN (SELECT issue FROM native_tasks)"
                            )
                        else:
                            main._STORE.db.execute(
                                "UPDATE issues SET updated_at='unrelated-status-update' WHERE id IN (SELECT issue FROM native_tasks)"
                            )
                status = client.get("/api/v1/native/entry/" + key, headers=headers).json()
                if status["state"] == "delivered" or status["failures"]:
                    break
                time.sleep(0.05)
            if window in {
                "before-runtime",
                "during-runtime",
                "withdrawal",
                "after-runtime",
                "after-intake",
                "invalid-output",
            }:
                assert status["state"] != "delivered" and status["failures"], status
                assert (
                    main._STORE.db.execute(
                        "SELECT count(*) FROM native_continuous_batches WHERE state='held'"
                    ).fetchone()[0]
                    == 1
                )
                if window == "withdrawal":
                    assert not program.with_suffix(".resolver-calls").exists()
                    return
                integration = main._NATIVE_ENTRY.workflow.integration
                connection = main._STORE.db
                row = connection.execute("SELECT plan FROM native_integration_intents WHERE stage='resolve'").fetchone()
                assert row is not None
                actor = json.loads(
                    connection.execute("SELECT plan FROM native_integrations WHERE id=?", (row[0],)).fetchone()[0]
                )["actor"]
                if window in {"before-runtime", "during-runtime", "invalid-output"}:
                    for _ in range(2):
                        with pytest.raises(Exception):
                            integration.reconcile(actor, row[0])
                    assert (
                        not program.with_suffix(".resolver-calls").exists()
                        if window == "before-runtime"
                        else program.with_suffix(".resolver-calls").read_text().count("call") == 1
                    )
                    return
                original_grant = None
                if signed:
                    intent = next((root / "broker-state").rglob("entry-intent.json"))
                    original_grant = intent.read_bytes()
                    intent.with_name("entry-receipt.json").unlink()
                if signed:
                    # Stop every original physical owner, then reconstruct the
                    # complete coordinator from persisted domain/native state.
                    from native_entry_factory import OrdinaryEntry

                    client.portal.call(main._NATIVE_ENTRY.stop)
                    cold_factory = OrdinaryEntry(
                        main._STORE,
                        main._NATIVE_STORE,
                        str(manifest),
                        hashlib.sha256(manifest.read_bytes()).hexdigest(),
                        root / "state",
                    )
                    try:
                        client.portal.call(cold_factory.start)
                        until = time.monotonic() + 30
                        while time.monotonic() < until:
                            with main._STORE._connection_lock:
                                state = connection.execute(
                                    "SELECT state FROM native_entry_intents WHERE id=?", (key,)
                                ).fetchone()[0]
                            if state == "delivered":
                                break
                            time.sleep(0.05)
                        assert state == "delivered", state
                        assert intent.read_bytes() == original_grant
                        assert len(signed_calls) == 1
                    finally:
                        client.portal.call(cold_factory.stop)
                    return
                monkeypatch.setattr(resolver, "intake", original_intake)
                # Recreate the installed adapter: no in-memory result survives recovery.
                from native_entry_resolver import InstalledResolver

                cold = InstalledResolver(main._NATIVE_ENTRY)
                integration.installed_resolver = cold
                integration.resolver_recovery = cold.recover
                marker = main._NATIVE_ENTRY.current_entry.set(key)
                try:
                    successor = integration.reconcile(actor, row[0])
                    assert successor == integration.reconcile(actor, row[0])
                    lane = connection.execute("SELECT id FROM native_continuous_lanes").fetchone()[0]
                    result = integration.continue_lane(actor, lane)
                    assert result["state"] == "accepted", result
                finally:
                    main._NATIVE_ENTRY.current_entry.reset(marker)
                assert program.with_suffix(".resolver-calls").read_text().count("call") == 1
                if signed:
                    assert intent.read_bytes() == original_grant
                    assert len(signed_calls) == 1
                return
            assert status["state"] == "delivered", (
                json.dumps(status),
                getattr(main._NATIVE_ENTRY, "last_transport", None),
                getattr(main._NATIVE_ENTRY, "last_denied", None),
            )
            assert status["progress"]["percent"] == 100
            if window == "no-conflict":
                assert not program.with_suffix(".resolver-calls").exists()
                return
            assert program.with_suffix(".resolver-calls").read_text().count("call") == 1
            request = json.loads(program.with_suffix(".resolver-request").read_text())
            assert request["role"] == "heqi"
            originals = list(request["document"]["originals"])
            for history in request["document"]["accepted_history"]:
                if history["plan"]:
                    originals.extend(history["plan"]["originals"])
            assert {"retain A", "retain B"} <= {o["contract"]["source"]["definition"]["acceptance"] for o in originals}
            db = main._STORE.db
            assert (
                db.execute("SELECT count(*) FROM native_integration_intents WHERE stage='resolve'").fetchone()[0] == 1
            )
            assert db.execute("SELECT count(*) FROM native_tasks WHERE state='accepted'").fetchone()[0] == 2
            assert len(list((root / "state" / "workers").rglob("physical-producer-marker"))) == 2
    finally:
        main._STORE.db.close()
        sys.modules.pop("main", None)


@pytest.fixture
def signed_broker(tmp_path):
    """Owned loopback generic provider fixture; actual signer/runtime/Heqi admission."""
    import base64
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    sys.path.insert(0, str(HERE.parents[2] / "platforms/ai-access/host-http/runtime"))

    import evaluate
    import native_entry_runtime as broker
    import runner
    from test_native_model_producer import framework

    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            message = body["messages"][-1]["content"]
            if message == "evaluate":
                value = "ok"
            else:
                request = json.loads(message)["input"]
                calls.append(request)
                value = dict(
                    schema=1,
                    plan=request["source"],
                    conflicts_digest=request["document"]["conflicts_digest"],
                    edits=[
                        dict(module=m, path=p, content_base64=base64.b64encode(b"AB").decode())
                        for m, p in sorted({(c["module"], c["path"]) for c in request["document"]["conflicts"]})
                    ],
                    reason="Retain A and B",
                )
                (tmp_path / "roles.resolver-request").write_text(json.dumps(request), encoding="utf-8")
                with (tmp_path / "roles.resolver-calls").open("a") as stream:
                    stream.write("call\n")
            raw = json.dumps(
                dict(
                    text=json.dumps(dict(action="final", value=value)),
                    finish_reason="stop",
                    usage=dict(input_tokens=10, output_tokens=5),
                )
            ).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        profile = dict(
            id="fixture",
            protocol="gonggong-json",
            endpoint=f"http://127.0.0.1:{server.server_port}/fixture",
            model="deterministic",
            max_context_bytes=1000000,
        )
        report = evaluate.evaluate(
            profile,
            [
                dict(
                    id="resolver",
                    task_type="resolve",
                    messages=[dict(role="user", content="evaluate")],
                    schema={"type": "string"},
                    expected="ok",
                )
            ],
            "synthetic",
        )
        assert report["passed_task_types"] == ["resolve"]
        evidence = tmp_path / "evaluation.json"
        evidence.write_text(runner.canonical(report), encoding="utf-8", newline="\n")
        profile["evaluation"] = {
            **{k: report[k] for k in ("profile_digest", "scope", "passed_task_types")},
            "evidence_ref": str(evidence),
            "evidence_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
        }
        root = framework(tmp_path)
        template = dict(
            task=dict(
                id="fixture",
                tenant_id="fixture",
                project_id="test",
                agent_id="heqi",
                outcome="resolve original conflict",
                authority_ref="synthetic",
                retention="test",
                mode="single",
                validation_only=True,
                work_items=[dict(id="test-only", kind="feature", relation="tests", certainty="confirmed")],
                input={},
                steps=[
                    dict(
                        id="resolution",
                        kind="resolve",
                        instruction="Resolve exact conflicts preserving original acceptance",
                        output="json",
                        schema={
                            "type": "object",
                            "properties": {
                                "schema": {"type": "integer"},
                                "plan": {"type": "string"},
                                "conflicts_digest": {"type": "string"},
                                "reason": {"type": "string"},
                                "edits": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            k: {"type": "string"} for k in ("module", "path", "content_base64")
                                        },
                                    },
                                },
                            },
                        },
                    )
                ],
            ),
            profiles=[profile],
            limits=dict(max_calls=1, max_output_tokens=1024),
        )
        template_path = tmp_path / "template.json"
        template_path.write_text(runner.canonical(template), encoding="utf-8", newline="\n")
        key = tmp_path / "key"
        key.write_text("synthetic-test-only-signing-key-material-1526", encoding="utf-8", newline="\n")
        node = os.environ.get("NATIVE_TEST_NODE") or shutil.which("node")
        assert node, "Node required"
        node = str(Path(node).resolve())
        python = str(Path(sys.executable).resolve())
        config = dict(
            template=str(template_path),
            template_sha256=hashlib.sha256(template_path.read_bytes()).hexdigest(),
            framework=str(root),
            framework_sha256=hashlib.sha256((root / "framework-manifest.json").read_bytes()).hexdigest(),
            runtime_sha256=runner.runtime_digest(),
            node=node,
            node_sha256=hashlib.sha256(Path(node).read_bytes()).hexdigest(),
            python=python,
            python_sha256=hashlib.sha256(Path(python).read_bytes()).hexdigest(),
            state=str(tmp_path / "broker-state"),
            key_file=str(key),
            authority_ref="synthetic",
        )
        config_path = tmp_path / "broker.json"
        config_path.write_text(runner.canonical(config), encoding="utf-8", newline="\n")
        argv = [
            python,
            "-B",
            "-X",
            "utf8",
            str(Path(broker.__file__)),
            "--config",
            str(config_path),
            "--sha256",
            hashlib.sha256(config_path.read_bytes()).hexdigest(),
        ]
        yield argv, calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(10)
        assert not thread.is_alive()


@pytest.mark.parametrize(
    "change",
    [
        "wrong-plan",
        "wrong-conflicts",
        "extra-field",
        "missing-path",
        "duplicate-path",
        "extra-path",
        "traversal",
        "dependency",
        "bad-base64",
        "large-binary",
        "delete",
    ],
)
def test_closed_proposal(change):
    import base64
    from types import SimpleNamespace

    from native_entry_resolver import InstalledResolver
    from native_store import NativeStoreError

    received = []
    factory = SimpleNamespace(
        native=SimpleNamespace(revision=lambda *a: dict(dependencies={})),
        workflow=SimpleNamespace(
            integration=SimpleNamespace(
                candidates=SimpleNamespace(receive=lambda *a: received.append(a) or {"receipt": "exact"})
            )
        ),
    )
    resolver = InstalledResolver(factory)
    resolver.authorize = lambda *a: True
    plan = dict(
        tenant="tenant", principals={"resolver": "resolver"}, base={"module": "base"}, issue_url="native://test"
    )
    request = dict(
        source="source",
        document=dict(
            conflicts_digest="conflicts",
            conflicts=[dict(module="module", path="output")],
            request_key="resolution-source",
        ),
    )
    proposal = dict(
        schema=1,
        plan="source",
        conflicts_digest="conflicts",
        edits=[dict(module="module", path="output", content_base64=base64.b64encode(b"AB").decode())],
        reason="retain both",
    )
    if change == "wrong-plan":
        proposal["plan"] = "other"
    if change == "wrong-conflicts":
        proposal["conflicts_digest"] = "other"
    if change == "extra-field":
        proposal["principal"] = "attacker"
    if change == "missing-path":
        proposal["edits"] = []
    if change == "duplicate-path":
        proposal["edits"] *= 2
    if change == "extra-path":
        proposal["edits"][0]["path"] = "extra"
    if change == "traversal":
        proposal["edits"][0]["path"] = "../output"
    if change == "dependency":
        proposal["edits"][0]["dependencies"] = {}
    if change == "bad-base64":
        proposal["edits"][0]["content_base64"] = "!!!"
    if change == "large-binary":
        proposal["edits"][0]["content_base64"] = base64.b64encode(b"x" * 32769).decode()
    if change == "delete":
        proposal["edits"][0]["content_base64"] = None
        assert resolver.intake("actor", plan, request, proposal) == {"receipt": "exact"}
        assert received[0][3][0]["edits"] == {"output": None}
    else:
        with pytest.raises(NativeStoreError):
            resolver.intake("actor", plan, request, proposal)
        assert not received


def test_exact_input_bound_before_runtime():
    from contextlib import contextmanager
    from types import SimpleNamespace

    from native_entry_resolver import InstalledResolver
    from native_store import NativeStoreError, _digest, _json

    raw = b"x" * 32769
    blob = _digest(raw)

    class Cursor:
        def execute(self, *args):
            return self

        def fetchone(self):
            return (raw,)

    @contextmanager
    def connection():
        yield Cursor()

    factory = SimpleNamespace(
        native=SimpleNamespace(_connection=connection, revision=lambda *a: dict(objects={"output": blob}))
    )
    resolver = InstalledResolver(factory)
    resolver.authorize = lambda *a: True
    plan = dict(tenant="tenant", base={"module": "base"}, originals=[], resolver_binding={})
    key = _digest(_json(plan).encode())
    pending = dict(plan=key, conflicts=[dict(module="module", path="output")])
    with pytest.raises(NativeStoreError, match="small-input bound"):
        resolver.request("actor", plan, pending, "resolution-" + key)


@pytest.mark.parametrize("changed", [False, True])
def test_cas_reuses_resolution_without_provider(changed):
    from contextlib import nullcontext
    from types import SimpleNamespace

    from native_entry_resolver import InstalledResolver
    from native_store import NativeStoreError

    prior = dict(
        conflicts="old" if changed else "same",
        resolution=dict(inputs={"module": {"edits": {"output": "blob"}}}, revisions={"module": "resolved"}),
    )
    integration = SimpleNamespace(_load=lambda *a: (None, prior))
    factory = SimpleNamespace(
        workflow=SimpleNamespace(_transaction=nullcontext, integration=integration),
        native=SimpleNamespace(
            revision=lambda *a: dict(dependencies={}, objects={"output": "blob"}), read=lambda *a: b"AB"
        ),
    )
    resolver = InstalledResolver(factory)
    resolver.request = lambda *a: dict(source="new", document=dict(conflicts_digest="same"))
    resolver.intake = lambda actor, plan, request, proposal: proposal
    plan = dict(tenant="tenant", base={"module": "new-base"}, continuation={"previous_plan": "old-plan"})
    if changed:
        with pytest.raises(NativeStoreError, match="new explicit resolution authority"):
            resolver.run("actor", plan, {}, "new-key")
    else:
        result = resolver.run("actor", plan, {}, "new-key")
        assert result["edits"] == [dict(module="module", path="output", content_base64="QUI=")]
        assert result["plan"] == "new"
