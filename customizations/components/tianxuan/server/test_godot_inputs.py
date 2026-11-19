"""Consumer regression: importable project bytes are scoped to current approvals."""

import base64
import io
import json
import os
import socket
import struct
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path

import pytest
import uvicorn
from api import create_app
from fastapi.testclient import TestClient
from native_store import NativeStore
from tianxuan_core import Tianxuan

DATA = Path(__file__).resolve().parents[4] / "tests/data"
ASSETS = {"concept": (DATA / "images/icon.png").read_bytes(), "model": (DATA / "models/suzanne.glb").read_bytes()}
NAMES = {"concept": "nested/sketch.png", "model": "nested/hero.glb"}


@pytest.fixture
def studio(tmp_path):
    store = Tianxuan(str(tmp_path / "issues.db"))
    actor = store.register("studio", "owner@example.invalid", "secret")["user_id"]
    req = store.create_requirement(actor, "r", "Art", "Purpose", "Scope", "Accept")["id"]
    store.set_visibility(actor, req, "private")
    issue = store.create_issue(actor, "Art inputs", requirement_id=req)["id"]
    native = NativeStore(tmp_path / "assets.db")
    with TestClient(
        create_app(store, native_store=native), headers={"Authorization": "Bearer " + store.issue_session(actor)}
    ) as client:
        yield store, actor, client, issue, req
    store.db.close()


def publish(client, key, base=None):
    edits = {NAMES[kind]: base64.b64encode(data).decode() for kind, data in ASSETS.items()}
    edits["revision.txt"] = base64.b64encode(key.encode()).decode()
    response = client.post(
        "/api/v1/native/batches",
        json={"request_key": key, "changes": [dict(module="art", base=base, reads=None, edits=edits)]},
    )
    assert response.status_code == 200, response.text
    return response.json()["revisions"]["art"]


def command(client, issue, version, op, kind, revision, **changes):
    binding = dict(kind=kind, module="art", revision=revision, path=NAMES[kind])
    return client.post(
        f"/api/v1/issues/{issue}/work/{op}",
        json=dict(binding, expected_version=version, call_id=str(version), **changes),
    )


def success(response):
    assert response.status_code == 200, response.text


def rejected(response):
    assert 400 <= response.status_code < 500, response.text
    assert not zipfile.is_zipfile(io.BytesIO(response.content))
    assert all(data not in response.content for data in ASSETS.values())


def package(response):
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    assert "no-store" in response.headers["cache-control"]
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert archive.testzip() is None
        return {name: archive.read(name) for name in archive.namelist()}


def test_native_input_consumes_only_current_approved_complete_set(studio):
    store, actor, client, issue, _ = studio
    endpoint = f"/api/v1/issues/{issue}/work/godot-inputs"
    rejected(client.get(endpoint))
    # Legacy unbound planning operates independently.
    success(client.post(f"/api/v1/issues/{issue}/work/log", json=dict(minutes=8, expected_version=0, call_id="time")))
    rev = publish(client, "initial")
    success(command(client, issue, 1, "submit_asset", "concept", rev))
    rejected(client.get(endpoint))
    success(command(client, issue, 2, "decide", "concept", rev, decision="approved"))
    one = package(client.get(endpoint))
    assert one["assets/concept.png"] == ASSETS["concept"]
    assert "assets/model.glb" not in one
    success(command(client, issue, 3, "submit_asset", "model", rev))
    rejected(client.get(endpoint))
    success(command(client, issue, 4, "decide", "model", rev, decision="approved"))
    both = package(client.get(endpoint))
    assert "project.godot" in both
    assert both["assets/concept.png"] == ASSETS["concept"]
    model = both["assets/model.glb"]
    assert model == ASSETS["model"]
    assert struct.unpack_from("<4sII", model) == (b"glTF", 2, len(model))
    size = struct.unpack_from("<I", model, 12)[0]
    assert json.loads(model[20 : 20 + size])["meshes"]
    new = publish(client, "next", rev)
    assert package(client.get(endpoint)) == both
    success(command(client, issue, 5, "submit_asset", "model", new))
    rejected(client.get(endpoint))
    rejected(client.get(endpoint, params={"kind": "concept", "path": NAMES["concept"], "revision": rev}))
    success(command(client, issue, 6, "decide", "model", new, decision="changes_requested"))
    rejected(client.get(endpoint))
    assert store.get_issue(issue)["status"] == "backlog"


def test_no_cross_issue_override_or_stale_authority(studio):
    store, actor, client, issue, req = studio
    rev = publish(client, "private")
    success(command(client, issue, 0, "submit_asset", "concept", rev))
    rejected(command(client, issue, 1, "decide", "concept", rev, decision="approved", path="wrong.png"))
    success(command(client, issue, 1, "decide", "concept", rev, decision="approved"))
    endpoint = f"/api/v1/issues/{issue}/work/godot-inputs"
    assert package(client.get(endpoint))["assets/concept.png"] == ASSETS["concept"]
    other = store.create_issue(actor, "other")["id"]
    rejected(client.get(f"/api/v1/issues/{other}/work/godot-inputs", params={"issue_id": issue}))
    foreign = store.register("other", "a@other.invalid", "secret")["user_id"]
    rejected(client.get(endpoint, headers={"Authorization": "Bearer " + store.issue_session(foreign)}))
    invited = store.create_invite(actor, "reader@example.invalid", "viewer")
    reader = store.accept_invite(invited["code"], "secret")["user_id"]
    headers = {"Authorization": "Bearer " + store.issue_session(reader)}
    store.share_doc(actor, req, reader, "read")
    assert package(client.get(endpoint, headers=headers))["assets/concept.png"] == ASSETS["concept"]
    store.unshare_doc(actor, req, reader)
    rejected(client.get(endpoint, headers=headers))
    # Even if both persisted event digests agree, a different actual blob must fail the export.
    with store.work_native_store._connection(write=True) as db:
        db.execute("UPDATE native_blobs SET content=? WHERE content=?", (b"changed", ASSETS["concept"]))
    rejected(client.get(endpoint))


def test_cli_imports_with_real_godot_and_failure_keeps_destination_unpublished(studio, tmp_path):
    executable = os.environ.get("TIANXUAN_GODOT_EXECUTABLE")
    if not executable:
        pytest.skip("set TIANXUAN_GODOT_EXECUTABLE for the headless Godot integration test")
    store, actor, client, issue, _ = studio
    rev = publish(client, "godot")
    for i, kind in enumerate(ASSETS):
        success(command(client, issue, 2 * i, "submit_asset", kind, rev))
        success(command(client, issue, 2 * i + 1, "decide", kind, rev, decision="approved"))
    cli = Path(__file__).resolve().parents[1] / "duobao/native_workspace_cli.py"
    output = tmp_path / "imports"
    output.mkdir()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        retire_on_read = threading.Event()
        later = publish(client, "later", rev)

        async def app(scope, receive, send):
            await client.app(scope, receive, send)
            if scope["type"] == "http" and retire_on_read.is_set():
                retire_on_read.clear()
                store.dispatch_tool(
                    actor,
                    "work.submit_asset",
                    dict(
                        issue_id=issue,
                        kind="model",
                        module="art",
                        revision=later,
                        path=NAMES["model"],
                        expected_version=4,
                    ),
                    call_id="in-flight",
                )

        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started:
                assert thread.is_alive() and time.monotonic() < deadline
                time.sleep(0.02)
            profile = tmp_path / "godot-profile"
            profile.mkdir()
            env = os.environ | dict(
                APPDATA=str(profile),
                LOCALAPPDATA=str(profile),
                XDG_CONFIG_HOME=str(profile),
                XDG_CACHE_HOME=str(profile),
                XDG_DATA_HOME=str(profile),
                TIANXUAN_PUBLIC_ORIGIN=f"http://127.0.0.1:{sock.getsockname()[1]}",
                TIANXUAN_TOKEN=store.issue_session(actor),
            )

            def run(name, godot=executable):
                return subprocess.run(
                    [sys.executable, str(cli), "godot-import"],
                    input=json.dumps(dict(issue_id=issue, destination=str(output / name))),
                    text=True,
                    capture_output=True,
                    env=env | {"TIANXUAN_GODOT_EXECUTABLE": godot},
                    timeout=120,
                )

            # An unusable importer must leave neither a publish directory nor staging remnants.
            assert run("incomplete", sys.executable).returncode != 0
            assert not list(output.iterdir())
            result = run("accepted")
            assert result.returncode == 0, result.stdout + result.stderr
            dest = output / "accepted"
            for kind, ext in (("concept", "png"), ("model", "glb")):
                asset = dest / "assets" / f"{kind}.{ext}"
                assert asset.read_bytes() == ASSETS[kind]
                assert asset.with_suffix("." + ext + ".import").is_file()
            imported = dest / ".godot/imported"
            assert any(imported.glob("*.ctex")) and any(imported.glob("*.scn"))
            # Revoke the approval after the first GET has returned its bytes.
            retire_on_read.set()
            stale = run("in-flight")
            assert stale.returncode != 0 and "409" in stale.stdout, stale.stdout + stale.stderr
            assert not retire_on_read.is_set()
            assert list(output.iterdir()) == [dest]
            assert run("second").returncode != 0
            assert list(output.iterdir()) == [dest]
        finally:
            server.should_exit = True
            thread.join(10)
