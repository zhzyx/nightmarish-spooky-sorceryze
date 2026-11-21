"""Link a real I02 issue to a tagged native revision, move the tag and reopen from G11."""

import argparse
import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from unittest.mock import patch

from editor_test_isolation import copy_editor
from run_unified_settings_native import sanitized_environment
from run_workbench_duobao_branches import ROOT, SERVER, Tianxuan
from run_workbench_duobao_native_commit import NativeStore, NativeWorkspace


def exercise(base, binary):
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        editor = copy_editor(binary, base / "engine")
    domain = Tianxuan(str(base / "domain.db"))
    account = domain.register("G12", "g12@example.invalid", secrets.token_urlsafe(32))
    tenant, actor = account["tenant_id"], account["user_id"]
    scope = "studio/game"
    issue = domain.create_issue(actor, "核对地图提交", project=scope)
    token = domain.issue_session(actor)
    domain.db.close()
    native = NativeStore(base / "native.db")
    seed = native.submit(
        tenant,
        actor,
        "seed",
        [
            {
                "module": "game",
                "base": None,
                "reads": None,
                "edits": {"project.godot": b'config_version=5\n[application]\nconfig/name="G12"\n', "map.txt": b"old"},
            }
        ],
    )["revisions"]["game"]
    checkout = base / "materialized"
    NativeWorkspace(native).materialize(tenant, {"game": seed}, checkout)
    project = checkout / "game"
    (base / "SConstruct").touch()
    host = base / SERVER
    host.mkdir(parents=True)
    for name in ("tianshu_bridge.py", "selected_commit.py", "native_workcopy_commit.py"):
        shutil.copyfile(ROOT / SERVER / name, host / name)
    (host.parent / "duobao").mkdir()
    for name in ("native_store.py", "native_workspace.py"):
        shutil.copyfile(ROOT / SERVER.parent / "duobao" / name, host.parent / "duobao" / name)
    environment = {k: v for k, v in sanitized_environment(base).items() if not k.startswith("TIANXUAN_")}
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    environment.update(
        TIANXUAN_AUTH_MODE="accounts",
        TIANXUAN_TENANT_ID=tenant,
        TIANXUAN_STORAGE_MODE="native",
        TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
        TIANXUAN_DB=str(base / "domain.db"),
        TIANXUAN_NATIVE_DB=str(native.database),
    )

    def request(method, path, data=None):
        req = urllib.request.Request(
            origin + path,
            method=method,
            data=json.dumps(data).encode() if data else None,
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as reply:
            return json.load(reply)

    tag_path = "/api/v1/native/modules/game/tags/review?project=studio%2Fgame"
    later = None
    reports = {}
    for phase in ("link", "restart"):
        with (base / "service.log").open("ab") as log:
            service = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "main:app",
                    "--app-dir",
                    str(ROOT / SERVER),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--no-access-log",
                ],
                cwd=base,
                env=environment,
                stdout=log,
                stderr=log,
            )
            try:
                end = time.monotonic() + 25
                while True:
                    try:
                        request("GET", "/api/v1/health")
                        break
                    except OSError:
                        if service.poll() is not None or time.monotonic() >= end:
                            raise RuntimeError((base / "service.log").read_text()[-2000:])
                        time.sleep(0.1)
                if phase == "link":
                    assert request("PUT", tag_path, {"revision": seed, "expected": None})["revision"] == seed
                else:
                    assert request("GET", tag_path)["revision"] == later
                run = subprocess.run(
                    [
                        str(editor),
                        "--headless",
                        "--editor",
                        "--path",
                        str(project),
                        "--script",
                        str(Path(__file__).with_name("workbench_issue_revisions.gd")),
                    ],
                    cwd=base,
                    env={
                        **environment,
                        "TIANXUAN_API": origin,
                        "TIANXUAN_PROJECT": scope,
                        "TIANXUAN_ACTOR": actor,
                        "TIANXUAN_TOKEN": token,
                        "G12_PYTHON": sys.executable,
                        "G12_PHASE": phase,
                        "G12_ISSUE": str(issue["number"]),
                        "G12_REVISION": seed,
                    },
                    capture_output=True,
                    text=True,
                    errors="replace",
                    timeout=120,
                )
                output = run.stdout + run.stderr
                assert token not in output
                markers = [line[11:] for line in run.stdout.splitlines() if line.startswith("G12_REPORT=")]
                if run.returncode or len(markers) != 1 or "SCRIPT ERROR" in output:
                    raise RuntimeError(output[-6000:])
                reports[phase] = json.loads(markers[0])
                if phase == "link":
                    later = native.submit(
                        tenant,
                        actor,
                        "advance",
                        [{"module": "game", "base": seed, "reads": None, "edits": {"map.txt": b"new"}}],
                    )["revisions"]["game"]
                    assert request("PUT", tag_path, {"revision": later, "expected": seed})["revision"] == later
            finally:
                service.terminate()
                service.wait(timeout=15)
    assert seed != later and native.read(tenant, "game", seed, "map.txt") == b"old"
    assert reports["link"]["forward_revision"] == reports["restart"]["forward_revision"]
    assert reports["restart"]["reverse_revision"] == reports["link"]["forward_revision"]
    assert reports["restart"]["reverse_button"] == f"#{issue['number']} {issue['title']}"
    assert issue["title"] in reports["restart"]["issue_detail"]
    with binary.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {
        "editor_sha256": digest,
        "project": scope,
        "issue_number": issue["number"],
        "module": "game",
        "tag": "review",
        "original_revision": seed,
        "new_tag_target": later,
        "views": reports,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-g12-") as directory:
        report = exercise(Path(directory).resolve(), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed native G12 issue and revision navigation before and after tag movement")
