"""Read issue details through the compiled sidebar and compare with an independent Tianxuan connection."""

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
import threading
import time
from pathlib import Path
from unittest.mock import patch

import uvicorn
from editor_test_isolation import copy_editor
from run_unified_settings_native import sanitized_environment

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "customizations/components/tianxuan/server"))
from api import create_app  # noqa: E402
from native_store import NativeStore  # noqa: E402
from tianxuan_core import Tianxuan  # noqa: E402


def run_probe(
    base,
    binary,
    script,
    store,
    native,
    tenant,
    token,
    scope,
    variables,
    password,
    *,
    after_response=None,
    graphical=False,
    followup_scripts=(),
):
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        engine = copy_editor(binary, base / "engine")
    project = base / "project"
    project.mkdir()
    (project / "project.godot").write_text(
        'config_version=5\n[application]\nconfig/name="WorkbenchProbe"\n', encoding="utf-8"
    )
    shutil.copyfile(Path(__file__).with_name("workbench_issue_detail.gd"), project / "workbench_issue_detail.gd")
    modes = {
        "TIANXUAN_AUTH_MODE": "accounts",
        "TIANXUAN_TENANT_ID": tenant,
        "TIANXUAN_PUBLIC_ORIGIN": "https://fixture.invalid",
    }
    reads = []
    with patch.dict(os.environ, modes), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        api = create_app(store, native_store=native, native_only=True)

        @api.middleware("http")
        async def observe(request, call_next):
            response = await call_next(request)
            if after_response is not None:
                response = after_response(request, response)
            if request.url.path.startswith("/api/v1/issues/by-number/"):
                reads.append([request.url.path, request.query_params.get("project"), response.status_code])
            return response

        service = uvicorn.Server(uvicorn.Config(api, log_level="error", access_log=False))
        thread = threading.Thread(target=service.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 20
            while not service.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("Fixture failed to start")
                time.sleep(0.05)
            env = {k: v for k, v in sanitized_environment(base).items() if not k.startswith("TIANXUAN_")}
            env.update(
                TIANXUAN_API=f"http://127.0.0.1:{sock.getsockname()[1]}",
                TIANXUAN_PROJECT=scope,
                TIANXUAN_TOKEN=token,
                **variables,
            )
            reports = []
            for probe in (script, *followup_scripts):
                shutil.copyfile(Path(__file__).with_name(probe), project / "probe.gd")
                result = subprocess.run(
                    [
                        str(engine),
                        *(["--audio-driver", "Dummy"] if graphical else ["--headless"]),
                        "--editor",
                        "--path",
                        str(project),
                        "--script",
                        "res://probe.gd",
                    ],
                    env=env,
                    cwd=base,
                    capture_output=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=90,
                )
                output = result.stdout + result.stderr
                if (token and token in output) or password in output:
                    raise AssertionError("Credential in fixture diagnostics")
                markers = [
                    line.removeprefix("WORKBENCH_REPORT=")
                    for line in result.stdout.splitlines()
                    if line.startswith("WORKBENCH_REPORT=")
                ]
                if result.returncode or len(markers) != 1 or "SCRIPT ERROR" in output:
                    raise AssertionError(output[-5000:])
                reports.append(json.loads(markers[0]))
        finally:
            service.should_exit = True
            thread.join(timeout=10)
    return (reports if followup_scripts else reports[0]), reads


def exercise(base, binary):
    database = str(base / "domain.db")
    store = Tianxuan(database)
    scope = "studio/game"
    password = secrets.token_urlsafe(32)
    account = store.register("I02", "owner@example.invalid", password)
    owner = account["user_id"]
    viewer = store.add_member(owner, "reader@example.invalid", password, name="唐敏", role="viewer")["user_id"]
    assigned = store.create_issue(owner, "核对场景入口", project=scope)
    unassigned = store.create_issue(owner, "检查地图", project=scope)
    private_req = store.create_requirement(owner, "private", "Private", "why", "scope", "done")
    store.set_visibility(owner, private_req["id"], "private")
    hidden = store.create_issue(owner, "Private title", project=scope, requirement_id=private_req["id"])
    with store.db:
        store.db.execute("INSERT INTO issue_assignees VALUES (?,?)", (assigned["id"], viewer))
    store.transition_issue(owner, assigned["id"], "planned")
    numbers = [assigned["number"], unassigned["number"], hidden["number"], 99999]
    token = store.issue_session(viewer)
    try:
        records, reads = run_probe(
            base,
            binary,
            "workbench_issue_detail.gd",
            store,
            NativeStore(base / "native.db"),
            account["tenant_id"],
            token,
            scope,
            {"I02_NUMBERS": json.dumps(numbers)},
            password,
        )
    finally:
        store.db.close()
    assert len(records) == 4
    persisted = Tianxuan(database)
    try:
        for record, number, display_owner in zip(records[:2], numbers[:2], ["唐敏", "未分配"], strict=True):
            row = persisted.read_issue_number(viewer, scope, number)
            revision = persisted.issue_snapshot(viewer, row["id"])["revision"]
            expected = f"标题　{row['title']}\n负责人　{display_owner}\n状态　{row['status']}\n内容版本　{revision}"
            assert record["visible"] == expected and record["status"] == f"#{number}", record
            assert record["detail"] == persisted.read_issue_detail(viewer, scope, number)
    finally:
        persisted.db.close()
    assert [r["status"] for r in records[2:]] == ["没有权限查看此工单", "当前项目中不存在此编号的工单"]
    assert all(not r["detail"] and not r["visible"] for r in records[2:])
    reads = [read for read in reads if read[0].endswith("/detail")]
    assert reads == [
        [f"/api/v1/issues/by-number/{n}/detail", scope, code]
        for n, code in zip([*numbers, numbers[0]], [200, 200, 403, 404, 200], strict=True)
    ]
    with binary.open("rb") as stream:
        binary_digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {
        "engine_sha256": binary_digest,
        "observed_fields": [r["visible"] for r in records[:2]],
        "http_readback": reads,
        "error_feedback": [r["status"] for r in records[2:]],
        "checks": [
            "command palette opened sidebar",
            "assigned and unassigned compared to reopened database",
            "private and absent results cleared prior detail",
            "successful refresh after 404, logout cleared the visible record",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-i02-") as directory:
        report = exercise(Path(directory), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed I02 native issue detail checks")
