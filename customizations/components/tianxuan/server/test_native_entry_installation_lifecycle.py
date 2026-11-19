"""An accepted task must not bind later independent work to its old installation."""

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
from native_model_host import executable_sha256
from test_native_entry_normal import PROGRAM


def test_installation_update_and_rollback_preserve_accepted_tasks(tmp_path, monkeypatch):
    node = os.environ.get("NATIVE_TEST_NODE") or shutil.which("node")
    if not node:
        pytest.skip("Installed Node required")
    node = str(Path(node).resolve())
    python = str(Path(sys.executable).resolve())
    driver = str(Path(__file__).parent.parent / "sinan-workorders" / "native_entry_driver.mjs")
    environment = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR"}}
    manifests = {}
    for version in ("v1", "v2"):
        program = tmp_path / (version + ".py")
        program.write_text(PROGRAM + "\n# installation " + version + "\n", encoding="utf-8")
        commands = {
            role: dict(argv=[python, "-X", "utf8", str(program), role], env=environment)
            for role in ("planner", "producer", "checker", "reviewer")
        }
        commands["dispatcher"] = dict(argv=[node, driver], env=environment)
        spec = dict(
            version=2,
            mode="deterministic-test",
            identity="lifecycle-" + version,
            files={p: executable_sha256(p) for p in (python, node, str(program), driver)},
            commands=commands,
            principals={role: "test-" + role for role in ("producer", "checker", "reviewer", "publisher")},
            scopes={"text": {"outputs": ["text/output"]}},
            complexity={"simple": ["text"]},
            catalog=[dict(id="installed", available=True, targets=["agent"], capabilities=["text"])],
        )
        manifest = tmp_path / (version + ".json")
        manifest.write_text(json.dumps(spec), encoding="utf-8")
        manifests[version] = manifest
    for key, value in dict(
        TIANXUAN_DB=str(tmp_path / "domain.sqlite"),
        TIANXUAN_NATIVE_DB=str(tmp_path / "native.sqlite"),
        TIANXUAN_STORAGE_MODE="native",
        TIANXUAN_NATIVE_STATE=str(tmp_path / "state"),
    ).items():
        monkeypatch.setenv(key, value)
    accepted = []
    task_snapshots = {}
    for number, version in enumerate(("v1", "v2", "v1"), 1):
        if number == 2:
            from native_entry_factory import OrdinaryEntry
            from native_store import NativeStore, NativeStoreError
            from tianxuan_core import Tianxuan

            incompatible = json.loads(manifests["v2"].read_text())
            incompatible["version"] = 999
            rejected_manifest = tmp_path / "incompatible.json"
            rejected_manifest.write_text(json.dumps(incompatible), encoding="utf-8")
            domain = Tianxuan(str(tmp_path / "domain.sqlite"))
            try:
                with pytest.raises(NativeStoreError):
                    OrdinaryEntry(
                        domain,
                        NativeStore(tmp_path / "native.sqlite"),
                        rejected_manifest,
                        hashlib.sha256(rejected_manifest.read_bytes()).hexdigest(),
                        tmp_path / "state",
                    )
                assert {
                    row["id"]: dict(row) for row in domain.db.execute("SELECT * FROM native_tasks")
                } == task_snapshots
                assert len(list((tmp_path / "state" / "workers").rglob("physical-producer-marker"))) == 1
            finally:
                domain.db.close()
        manifest = manifests[version]
        monkeypatch.setenv("TIANXUAN_NATIVE_INSTALLATION", str(manifest))
        monkeypatch.setenv("TIANXUAN_NATIVE_INSTALLATION_SHA256", hashlib.sha256(manifest.read_bytes()).hexdigest())
        sys.modules.pop("main", None)
        main = importlib.import_module("main")
        try:
            with TestClient(main.app) as client:
                account = dict(email="lifecycle@example.invalid", password="password123")
                if number == 1:
                    response = client.post("/api/v1/auth/register", json={**account, "tenant_name": "Lifecycle"})
                    assert response.status_code == 200, response.text
                login = client.post("/api/v1/auth/session", json=account)
                assert login.status_code == 200, login.text
                headers = {"Authorization": "Bearer " + login.json()["token"]}
                capability = client.get("/api/v1/native/entry/capabilities", headers=headers).json()
                assert capability["identity"] == "lifecycle-" + version
                for previous in accepted:
                    response = client.get("/api/v1/native/entry/" + previous["entry"], headers=headers)
                    assert response.status_code == 200, response.text
                    assert response.json() == previous
                for key, previous in task_snapshots.items():
                    row = main._STORE.db.execute("SELECT * FROM native_tasks WHERE id=?", (key,)).fetchone()
                    assert dict(row) == previous
                response = client.post(
                    "/api/v1/requirements",
                    headers=headers,
                    json=dict(
                        request_id="phase-" + str(number),
                        title="Phase " + str(number),
                        outcome="Output",
                        scope="Text",
                        acceptance="output must equal deterministic accepted output",
                    ),
                )
                assert response.status_code == 200, response.text
                response = client.post(
                    "/api/v1/native/entry/execute",
                    headers=headers,
                    json=dict(requirement=response.json()["id"], call_id="phase-" + str(number), scopes=["text"]),
                )
                assert response.status_code == 200, response.text
                key = response.json()["entry"]
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    response = client.get("/api/v1/native/entry/" + key, headers=headers)
                    assert response.status_code == 200, response.text
                    status = response.json()
                    if status["state"] == "delivered" or status["failures"]:
                        break
                    time.sleep(0.05)
                assert status["state"] == "delivered", status
                assert status["progress"]["percent"] == 100
                accepted.append(status)
                for previous_key, previous in task_snapshots.items():
                    row = main._STORE.db.execute("SELECT * FROM native_tasks WHERE id=?", (previous_key,)).fetchone()
                    assert dict(row) == previous
                task_snapshots = {row["id"]: dict(row) for row in main._STORE.db.execute("SELECT * FROM native_tasks")}
                assert len(task_snapshots) == number
            assert main._NATIVE_ENTRY.last_dispatcher_terminal["exit_code"] == 0
            assert len(list((tmp_path / "state" / "workers").rglob("physical-producer-marker"))) == number
        finally:
            main._STORE.db.close()
            sys.modules.pop("main", None)
