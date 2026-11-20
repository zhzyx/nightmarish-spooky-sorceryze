from pathlib import Path
from types import SimpleNamespace

import native_entry_runtime
import native_role_service
import pytest
from native_entry_factory import OrdinaryEntry
from native_role_service import client, launch, tree_sha256
from native_store import NativeStoreError


def _production_sources():
    component = Path(__file__).resolve().parents[1]
    sources = component / "sinan-workorders"
    files = [
        p for directory in (component / "server", component / "duobao", sources) for p in directory.glob("native_*.py")
    ]
    files.extend(sources.glob("native_*.mjs"))
    files.append(component.parents[2] / "tools/ainative/owned_process.py")
    return sources, dict.fromkeys(map(str, files))


def test_production_rejects_direct_planner(monkeypatch, tmp_path):
    monkeypatch.setenv("TIANXUAN_REQUIRE_KEYS", "1")
    monkeypatch.setenv("TIANXUAN_TENANT_ID", "test")
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://localhost")
    monkeypatch.setenv("TIANXUAN_LOCAL_VALIDATION_ROOT", str(tmp_path))
    sources, files = _production_sources()
    argv = [
        "python",
        "-B",
        "-X",
        "utf8",
        str(sources / "native_entry_runtime.py"),
        "--config",
        "unused",
        "--sha256",
        "unused",
    ]
    spec = {"mode": "production", "files": files, "commands": {"planner": {"argv": argv}}}
    with pytest.raises(NativeStoreError, match="requires authenticated operating-system role services"):
        OrdinaryEntry.validate_production(SimpleNamespace(root=tmp_path), spec)


@pytest.mark.parametrize("role", ["planner", "producer", "reviewer"])
@pytest.mark.parametrize("mismatch", ["path", "digest"])
def test_production_role_service_client_requires_broker_python(monkeypatch, tmp_path, role, mismatch):
    monkeypatch.setenv("TIANXUAN_REQUIRE_KEYS", "1")
    monkeypatch.setenv("TIANXUAN_TENANT_ID", "test")
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://localhost")
    sources, files = _production_sources()
    service = str(sources / "native_role_service.py")
    other_python = str(tmp_path / "other-python")
    python_sha256 = "a" * 64
    files[other_python] = python_sha256
    commands, clients, brokers = {}, {}, {}
    for number, name in enumerate(("planner", "producer", "reviewer"), start=1):
        python = str(tmp_path / f"{name}-python")
        client_file = str(tmp_path / f"{name}-client.json")
        broker_file = str(tmp_path / f"{name}-broker.json")
        checksum = str(number) * 64
        files.update({python: python_sha256, client_file: checksum, broker_file: checksum})
        clients[client_file, checksum] = dict(
            role=name,
            broker_file=broker_file,
            broker_sha256=checksum,
            service_sha256=checksum,
            peer_sha256=checksum,
            tree_sha256=checksum,
            service_identity=name,
            registry=str(tmp_path / "registry"),
            worker_root=str(tmp_path / "workers"),
        )
        brokers[broker_file, checksum] = (
            dict(python=python, python_sha256=python_sha256, state=name),
            dict(profiles=[{"id": "model"}], task={"agent_id": "yanshi" if name == "planner" else name, "role": name}),
        )
        commands[name] = dict(
            argv=[python, "-B", "-X", "utf8", service, "call", "--config", client_file, "--sha256", checksum]
        )
    monkeypatch.setattr(native_role_service, "config", lambda path, checksum: clients[path, checksum])
    monkeypatch.setattr(native_entry_runtime, "load_config", lambda path, checksum: brokers[path, checksum])
    spec = dict(
        mode="production",
        files=files,
        commands=commands,
        catalog=[{"id": "model", "available": True, "targets": ["agent"]}],
    )
    entry = SimpleNamespace(root=tmp_path)
    OrdinaryEntry.validate_production(entry, spec)

    if mismatch == "path":
        commands[role]["argv"][0] = other_python
    else:
        files[commands[role]["argv"][0]] = "b" * 64
    with pytest.raises(NativeStoreError, match="Role service client must use the verified broker Python"):
        OrdinaryEntry.validate_production(entry, spec)


def test_changed_tree_stops_before_broker_configuration(tmp_path):
    installed = tree_sha256()
    assert len(installed) == 64
    with pytest.raises(ValueError, match="execution tree changed"):
        launch({"tree_sha256": "0" * 64}, {}, None, tmp_path / "absent", "", [])


def test_producer_requires_installed_workspace_before_connect(monkeypatch, tmp_path):
    execution = "a" * 64
    work = tmp_path / "other" / execution / "work"
    monkeypatch.setenv("NATIVE_WORKSPACE", str(work))
    with pytest.raises(ValueError, match="producer workspace"):
        client({"role": "producer", "worker_root": str(Path(tmp_path, "installed"))}, False)
