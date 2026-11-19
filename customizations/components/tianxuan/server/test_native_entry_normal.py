"""Normal main/ASGI test with explicitly deterministic installed role programs."""

import hashlib
import importlib
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

HERE = Path(__file__).resolve().parent
for folder in (HERE, HERE.parent / "duobao", HERE.parent / "sinan-workorders"):
    sys.path.insert(0, str(folder))

from native_model_host import executable_sha256  # noqa: E402

PROGRAM = r"""
import base64, hashlib, json, os, pathlib, sys
role = sys.argv[1]
def digest(value): return hashlib.sha256(value).hexdigest()
def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
if role in ('planner', 'reviewer'):
 r=json.load(sys.stdin)
 if role=='planner':
  proposal=dict(source=r['source'], tasks=[dict(id='result',title=r['document']['title'],body='Write deterministic accepted output',acceptance='output must equal deterministic accepted output',dependencies=[],scope='text',complexity='simple',outputs=['text/output'])])
 else:
  data={k:base64.b64decode(v) for k,v in r['scopes'].items()}
  assert any(k.endswith('/output') and v==b'deterministic accepted output' for k,v in data.items())
  proposal=dict(candidate=r['source'],accepted=True,reviewer=r['complexity']['reviewer'],criteria=r['document']['source']['definition']['acceptance'],inspected={k:digest(v) for k,v in data.items()},reason='Independently read exact output and compared with original criterion')
 print(canonical(dict(input_digest=digest(canonical(r).encode()),source=r['source'],proposal=proposal,runtime_state='deterministic-test-installation')))
elif role=='producer':
 p=pathlib.Path(os.environ['NATIVE_WORKSPACE']);
 if json.loads(pathlib.Path(os.environ['NATIVE_CONTEXT']).read_text(encoding='utf-8'))['title']=='Revoke':
  import time
  (p.parent/'revoke-wait').write_text('waiting'); time.sleep(30)
 (next(p.glob('*-text'))/'output').write_text('deterministic accepted output',encoding='utf-8')
 (p.parent/'physical-producer-marker').write_text('once')
elif role=='checker':
 p=pathlib.Path(os.environ['DUOBAO_INPUT']); assert next(p.glob('*-text/output')).read_bytes()==b'deterministic accepted output'
"""


class NormalEntryTests(unittest.TestCase):
    def test_main_two_users(self):
        node = os.environ.get("NATIVE_TEST_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Installed Node required")
        node = str(Path(node).resolve())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            program = root / "deterministic_installation.py"
            program.write_text(PROGRAM, encoding="utf-8")
            python = str(Path(sys.executable).resolve())
            driver = str(HERE.parent / "sinan-workorders" / "native_entry_driver.mjs")
            environment = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR"}}
            files = {p: executable_sha256(p) for p in (python, node, str(program), driver)}
            commands = {
                r: dict(argv=[python, "-X", "utf8", str(program), r], env=environment)
                for r in ("planner", "producer", "checker", "reviewer")
            }
            commands["dispatcher"] = dict(argv=[node, driver], env=environment)
            spec = dict(
                version=2,
                mode="deterministic-test",
                identity="deterministic-normal-entry-test",
                files=files,
                commands=commands,
                principals=dict(
                    producer="test-producer",
                    checker="test-checker",
                    reviewer="test-reviewer",
                    publisher="test-publisher",
                ),
                scopes={"text": {"outputs": ["text/output"]}},
                complexity={"simple": ["text"]},
                catalog=[dict(id="installed", available=True, targets=["agent"], capabilities=["text"])],
            )
            manifest = root / "installation.json"
            manifest.write_text(json.dumps(spec), encoding="utf-8")
            env = dict(
                TIANXUAN_DB=str(root / "domain.sqlite"),
                TIANXUAN_NATIVE_DB=str(root / "native.sqlite"),
                TIANXUAN_STORAGE_MODE="native",
                TIANXUAN_NATIVE_INSTALLATION=str(manifest),
                TIANXUAN_NATIVE_INSTALLATION_SHA256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                TIANXUAN_NATIVE_STATE=str(root / "state"),
            )
            with patch.dict(os.environ, env):
                sys.modules.pop("main", None)
                main = importlib.import_module("main")
                self.addCleanup(main._STORE.db.close)
                try:
                    with TestClient(main.app) as client:
                        capability = client.get("/api/v1/capabilities").json()["native_execution"]
                        self.assertEqual(capability["mode"], "deterministic-test")
                        self.assertEqual(capability["execution_nodes"], "local-only")
                        entries = []
                        requirements = []
                        for i in range(2):
                            account = dict(
                                tenant_name="tenant" + str(i),
                                email=f"person{i}@example.invalid",
                                password="password123",
                            )
                            response = client.post("/api/v1/auth/register", json=account)
                            self.assertEqual(response.status_code, 200, response.text)
                            login = client.post(
                                "/api/v1/auth/session", json={k: account[k] for k in ("email", "password")}
                            ).json()
                            headers = {"Authorization": "Bearer " + login["token"]}
                            response = client.post(
                                "/api/v1/requirements",
                                headers=headers,
                                json=dict(
                                    request_id="normal" + str(i),
                                    title="Normal entry",
                                    outcome="Output",
                                    scope="Text",
                                    acceptance="output must equal deterministic accepted output",
                                ),
                            )
                            self.assertEqual(response.status_code, 200, response.text)
                            requirement = response.json()["id"]
                            requirements.append(requirement)
                            response = client.post(
                                "/api/v1/native/entry/execute",
                                headers=headers,
                                json=dict(
                                    requirement=requirement,
                                    call_id="execute",
                                    scopes=["text"],
                                    **({"model": "installed"} if i else {}),
                                ),
                            )
                            self.assertEqual(response.status_code, 200, response.text)
                            key = response.json()["entry"]
                            recovered = client.post(
                                "/api/v1/native/entry/calls/status", headers=headers, json={"call_id": "execute"}
                            )
                            self.assertEqual(recovered.status_code, 200, recovered.text)
                            self.assertEqual(recovered.json()["entry"], key)
                            self.assertEqual(recovered.json()["requested_profile"], "installed" if i else None)
                            entries.append((key, headers))
                        deadline = time.monotonic() + 90
                        for key, headers in entries:
                            while time.monotonic() < deadline:
                                response = client.get("/api/v1/native/entry/" + key, headers=headers)
                                self.assertEqual(response.status_code, 200, response.text)
                                status = response.json()
                                if status["state"] == "delivered" or status["failures"]:
                                    break
                                time.sleep(0.05)
                            self.assertEqual(
                                status["state"],
                                "delivered",
                                (
                                    status,
                                    getattr(main._NATIVE_ENTRY, "last_transport", None),
                                    getattr(main._NATIVE_ENTRY, "last_denied", None),
                                ),
                            )
                            self.assertEqual(status["progress"]["percent"], 100)
                        self.assertEqual(
                            client.get("/api/v1/native/entry/" + entries[0][0], headers=entries[1][1]).status_code, 404
                        )
                        self.assertEqual(len(list((root / "state" / "workers").rglob("physical-producer-marker"))), 2)
                        owner = entries[0][1]
                        response = client.post(
                            "/api/v1/users",
                            headers=owner,
                            json=dict(email="colleague@example.invalid", password="password123", role="editor"),
                        )
                        self.assertEqual(response.status_code, 200, response.text)
                        colleague = response.json()["user_id"]
                        response = client.post(
                            "/api/v1/docs/" + requirements[0] + "/shares",
                            headers=owner,
                            json=dict(user_id=colleague, permission="write"),
                        )
                        self.assertEqual(response.status_code, 200, response.text)
                        login = client.post(
                            "/api/v1/auth/session", json=dict(email="colleague@example.invalid", password="password123")
                        ).json()
                        headers = {"Authorization": "Bearer " + login["token"]}
                        response = client.post(
                            "/api/v1/native/entry/execute",
                            headers=headers,
                            json=dict(requirement=requirements[0], call_id="collaborate", scopes=["text"]),
                        )
                        self.assertEqual(response.status_code, 200, response.text)
                        key = response.json()["entry"]
                        deadline = time.monotonic() + 90
                        while time.monotonic() < deadline:
                            response = client.get("/api/v1/native/entry/" + key, headers=headers)
                            self.assertEqual(response.status_code, 200, response.text)
                            status = response.json()
                            if status["state"] == "delivered" or status["failures"]:
                                break
                            time.sleep(0.05)
                        self.assertEqual(
                            status["state"],
                            "delivered",
                            (
                                status,
                                getattr(main._NATIVE_ENTRY, "last_transport", None),
                                getattr(main._NATIVE_ENTRY, "last_denied", None),
                            ),
                        )
                        self.assertEqual(len(list((root / "state" / "workers").rglob("physical-producer-marker"))), 3)
                        headers = entries[1][1]
                        response = client.post(
                            "/api/v1/requirements",
                            headers=headers,
                            json=dict(
                                request_id="revoke",
                                title="Revoke",
                                outcome="Output",
                                scope="Text",
                                acceptance="output must equal deterministic accepted output",
                            ),
                        )
                        requirement = response.json()["id"]
                        response = client.post(
                            "/api/v1/native/entry/execute",
                            headers=headers,
                            json=dict(requirement=requirement, call_id="revoke", scopes=["text"]),
                        )
                        key = response.json()["entry"]
                        deadline = time.monotonic() + 20
                        while time.monotonic() < deadline and not list(
                            (root / "state" / "workers").rglob("revoke-wait")
                        ):
                            time.sleep(0.05)
                        self.assertTrue(list((root / "state" / "workers").rglob("revoke-wait")))
                        self.assertTrue(client.post("/api/v1/auth/logout", headers=headers).json()["revoked"])
                        self.assertEqual(client.get("/api/v1/native/entry/" + key, headers=headers).status_code, 401)
                        new_session = client.post(
                            "/api/v1/auth/session", json={"email": "person1@example.invalid", "password": "password123"}
                        ).json()
                        renewed = {"Authorization": "Bearer " + new_session["token"]}
                        observed = client.get("/api/v1/native/entry/" + key, headers=renewed)
                        self.assertEqual(observed.status_code, 200, observed.text)
                        self.assertEqual(observed.json()["entry"], key)
                        deadline = time.monotonic() + 15
                        while time.monotonic() < deadline and not any(
                            f["id"] == key for f in main._NATIVE_ENTRY.consumer.failures
                        ):
                            time.sleep(0.05)
                        self.assertTrue(any(f["id"] == key for f in main._NATIVE_ENTRY.consumer.failures))
                        self.assertEqual(len(list((root / "state" / "workers").rglob("physical-producer-marker"))), 3)

                        for row in main._STORE.db.execute("SELECT id,task FROM native_tasks"):
                            self.assertTrue(
                                main._NATIVE_ENTRY.workflow.worker.process_closed(json.loads(row["task"]), row["id"])
                            )
                finally:
                    main._STORE.db.close()
                # A fresh normal main reload recovers durable ledgers without
                # replaying accepted producers or the revoked external intent.
                main = importlib.reload(main)
                try:
                    with TestClient(main.app):
                        time.sleep(0.1)
                        self.assertEqual(len(list((root / "state" / "workers").rglob("physical-producer-marker"))), 3)
                        self.assertFalse(main._NATIVE_ENTRY.workflow._executions)
                    # Strict deployment uses administrator provisioned keys;
                    # ordinary self-registration is intentionally forbidden.
                    owner = main._STORE.authenticate("person1@example.invalid", "password123")
                    access = main._STORE.issue_access_key(owner["user_id"], owner["user_id"], "strict-normal-test")
                    tenant = main._STORE.actor_context(owner["user_id"])["tenant"]
                finally:
                    main._STORE.db.close()
                with patch.dict(
                    os.environ,
                    dict(
                        TIANXUAN_REQUIRE_KEYS="1",
                        TIANXUAN_TENANT_ID=tenant,
                        TIANXUAN_PUBLIC_ORIGIN="https://testserver",
                    ),
                ):
                    main = importlib.reload(main)
                    try:
                        with TestClient(main.app, base_url="https://testserver") as client:
                            headers = {"Authorization": "Bearer " + access["key"]}
                            self.assertEqual(
                                client.post("/api/v1/auth/register", headers=headers, json={}).status_code, 403
                            )
                            response = client.post(
                                "/api/v1/requirements",
                                headers=headers,
                                json=dict(
                                    request_id="strict",
                                    title="Healthy strict entry",
                                    outcome="Output",
                                    scope="Text",
                                    acceptance="output must equal deterministic accepted output",
                                ),
                            )
                            self.assertEqual(response.status_code, 200, response.text)
                            requirement = response.json()["id"]
                            response = client.post(
                                "/api/v1/native/entry/execute",
                                headers=headers,
                                json=dict(requirement=requirement, call_id="strict", scopes=["text"]),
                            )
                            self.assertEqual(response.status_code, 200, response.text)
                            key = response.json()["entry"]
                            deadline = time.monotonic() + 90
                            while time.monotonic() < deadline:
                                response = client.get("/api/v1/native/entry/" + key, headers=headers)
                                self.assertEqual(response.status_code, 200, response.text)
                                status = response.json()
                                if status["state"] == "delivered" or status["failures"]:
                                    break
                                time.sleep(0.05)
                            self.assertEqual(
                                status["state"],
                                "delivered",
                                (status, getattr(main._NATIVE_ENTRY, "last_transport", None)),
                            )
                            self.assertEqual(
                                len(list((root / "state" / "workers").rglob("physical-producer-marker"))), 4
                            )
                    finally:
                        main._STORE.db.close()


if __name__ == "__main__":
    unittest.main()
