"""Reopen a signed business task after its editor's supervised worker tree has stopped."""

import argparse
import ctypes
import hashlib
import json
import os
import platform
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

import run_workbench_project_reopen as reopen

checks = reopen.checks
LEASE = {"X-Native-Worker-Lifetime": "editor-connection"}
ROUTE = "/api/v1/native/workflow/recover-project?project=studio"

# The editor's production startup code owns the recovery. This observer only
# verifies login and requests ordinary window closure when the witness is ready.
OBSERVER = """extends SceneTree

func _initialize() -> void:
    observe.call_deferred()

func observe() -> void:
    var marker := OS.get_environment("Q05_CLOSE")
    var end := Time.get_ticks_msec() + 90000
    while Time.get_ticks_msec() < end:
        var session := root.find_child("WorkbenchBusinessSession", true, false)
        if session and not session.get_identity().is_empty() and FileAccess.file_exists(marker):
            print("Q05_WINDOW=" + JSON.stringify({"pid": OS.get_process_id(), "display": DisplayServer.get_name()}))
            root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
            return
        await create_timer(0.05).timeout
    quit(1)
"""

# This installed deterministic producer has no external production effects.
# Each attempt must see the original inputs. The abandoned edit is never admitted.
PRODUCER = """import subprocess, sys, time
sync = pathlib.Path(os.environ["Q05_SYNC"])
draft = pathlib.Path("a/abandoned")
assert not draft.exists()
if not (sync / "release").exists():
    draft.write_text("uncollected partial output")
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(150)"])
    (sync / "started.tmp").write_text(json.dumps([os.getpid(), child.pid]))
    (sync / "started.tmp").replace(sync / "started")
    while not (sync / "release").exists():
        challenge = sync / "challenge"
        if challenge.exists():
            answer = challenge.read_text()
            (sync / "answer.tmp").write_text(answer)
            (sync / "answer.tmp").replace(sync / "answer")
        time.sleep(.025)
"""


CONTROL = """if grant["issue_id"] == os.environ["Q05_SIBLING"]:
    import sys, time
    sync = pathlib.Path(os.environ["Q05_SYNC"])
    (sync / "control.tmp").write_text(str(os.getpid()))
    (sync / "control.tmp").replace(sync / "control")
    while not (sync / "release-control").exists():
        time.sleep(.025)
    sys.exit(0)
"""


def wait(check, description, timeout=45):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = check()
        if value:
            return value
        time.sleep(0.025)
    raise TimeoutError(description)


def dead(pid):
    if os.name == "nt":
        from ctypes import wintypes

        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        api.OpenProcess.restype = wintypes.HANDLE
        api.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        api.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = api.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE only
        if not handle:
            return ctypes.get_last_error() == 87  # ERROR_INVALID_PARAMETER
        try:
            return api.WaitForSingleObject(handle, 0) == 0
        finally:
            api.CloseHandle(handle)
    try:
        os.getpgid(pid)
    except ProcessLookupError:
        return True
    state = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True)
    return state.returncode == 0 and state.stdout.lstrip().startswith("Z")


def connection(url, token):
    address = urlsplit(url)
    sock = socket.create_connection((address.hostname, address.port), timeout=5)
    try:
        sock.sendall(
            (
                f"POST {ROUTE} HTTP/1.1\r\nHost: {address.netloc}\r\nAuthorization: Bearer {token}\r\n"
                "X-Native-Worker-Lifetime: editor-connection\r\nContent-Type: application/json\r\n"
                "Content-Length: 2\r\n\r\n{}"
            ).encode("ascii")
        )
    except BaseException:
        sock.close()
        raise
    return sock


@contextmanager
def window(engine, project, url, token, marker):
    marker.unlink(missing_ok=True)
    result = {}
    env = {k: v for k, v in reopen.sanitized_environment(project).items() if not k.startswith("TIANXUAN_")} | {
        "TIANXUAN_API": url,
        "TIANXUAN_TOKEN": token,
        "TIANXUAN_PROJECT": "studio",
        "Q05_CLOSE": str(marker),
    }
    if sys.platform != "darwin":
        raise RuntimeError("The native Q05 fixture requires a macOS Cocoa editor")
    proc = subprocess.Popen(
        [
            engine,
            "--single-window",
            "--rendering-method",
            "gl_compatibility",
            "--editor",
            "--path",
            project,
            "--script",
            "res://probe.gd",
        ],
        cwd=project,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        yield result
        marker.touch()
        log = proc.communicate(timeout=40)[0].decode("utf-8", errors="replace")
        if token in log:
            raise AssertionError("Credential in editor diagnostic")
        rows = [
            json.loads(line.removeprefix("Q05_WINDOW=")) for line in log.splitlines() if line.startswith("Q05_WINDOW=")
        ]
        if proc.returncode != 0 or "SCRIPT ERROR" in log or len(rows) != 1:
            raise RuntimeError(log[-5000:])
        assert rows[0]["pid"] == proc.pid and rows[0]["display"].lower() == "macos", rows
        result.update(**rows[0], exit=proc.returncode)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)


def exercise(root, executable=None, restartable=True, revoke=False):
    # macOS TMPDIR may start with /var, a system alias for /private/var.
    # Pass the fixture's physical path to the local workspace admission checks.
    root = root.resolve(strict=True)
    sync = root / "sync"
    sync.mkdir()
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Q05"\n')
    (project / "probe.gd").write_text(OBSERVER, encoding="utf-8")
    engine = reopen.copy_editor(executable, root / "engine") if executable else None
    windows = []
    with ExitStack() as stack:
        fixture = stack.enter_context(contextmanager(checks.fixture.__wrapped__)(root))
        workflow, actor, tenant, *_ = fixture
        h = stack.enter_context(contextmanager(checks.host.__wrapped__)(fixture))
        issue = checks.install(h)
        spec = workflow.worker.profiles["local"]
        if restartable:
            spec["restart_checkpoint"] = "immutable-inputs"
        spec["timeout"] = 100
        sibling = h.issues[1]
        spec["env"].update(Q05_SYNC=str(sync), Q05_SIBLING=sibling["id"])
        script = Path(spec["argv"][1])
        text = script.read_text(encoding="utf-8")
        text = text.replace("with open(", CONTROL + "with open(")
        script.write_text(
            text.replace("pathlib.Path('a/preview.svg')", PRODUCER + "pathlib.Path('a/preview.svg')"), encoding="utf-8"
        )
        stack.enter_context(
            patch.dict(
                os.environ,
                TIANXUAN_AUTH_MODE="accounts",
                TIANXUAN_TENANT_ID=tenant,
                TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
            )
        )
        token = workflow.domain.issue_session(actor)
        url, http = stack.enter_context(reopen.receiver(h, token, sync / "response"))
        key = checks.stage.signed(h, issue)
        before = checks.snapshot(h, key)
        stack.callback((sync / "release-control").touch)
        stack.callback((sync / "release").touch)
        with ExitStack() as first:
            if engine:
                windows.append(first.enter_context(window(engine, project, url, token, sync / "close")))
            else:
                request = connection(url, token)
                first.callback(request.close)
            wait((sync / "started").exists, "worker and child start")
            leader, child = json.loads((sync / "started").read_text())
            running = checks.snapshot(h, key)
            assert running["state"] == "running" and running["authorization"] == before["authorization"]
            assert all(not dead(pid) for pid in (leader, child))
            pgids = None
            if os.name == "posix":
                with workflow._transaction(write=False) as db:
                    occupancy = db.execute(
                        "SELECT pgid,owner FROM native_local_occupancy WHERE task=?", (key,)
                    ).fetchone()
                pgids = [os.getpgid(pid) for pid in (leader, child)]
                assert pgids == [leader, leader] and occupancy["pgid"] == leader
                assert json.loads(occupancy["owner"])["pid"] == os.getpid()
            # Closing another connection for the same signed actor/project cannot
            # acquire or stop the live worker. It sees the occupied task.
            assert h.client.post(ROUTE, json={}, headers=LEASE).raise_for_status().json()["continued"] == 0
            # A second authenticated connection owns another real producer under
            # the same actor and project. Its module does not overlap this task.
            h.plan.update(selected={"b": fixture[4]["b"]}, writes={"b": ["preview.svg"]})
            control_key = checks.stage.signed(h, sibling)
            stack.callback(connection(url, token).close)
            wait((sync / "control").exists, "independent business worker")
            control_pid = int((sync / "control").read_text())
            assert control_pid not in {leader, child}
            assert checks.snapshot(h, control_key)["state"] == "running"
            challenge = secrets.token_hex(16)
            (sync / "challenge").write_text(challenge)
            wait(lambda: (sync / "answer").exists() and (sync / "answer").read_text() == challenge, "live nonce")
        # Generate the second challenge strictly after the editor process exited.
        close_observed = time.monotonic()
        after_close = secrets.token_hex(16)
        if engine:
            (sync / "challenge").write_text(after_close)
        expected = "editor-interrupted" if restartable else "failed"
        wait(lambda: checks.snapshot(h, key)["state"] == expected, "durable close receipt", timeout=8)
        wait(lambda: all(dead(pid) for pid in (leader, child)), "physical exit", timeout=5)
        physical_exit_ms = round((time.monotonic() - close_observed) * 1000)
        if not engine:
            # Closing a test socket returns before uvicorn receives its EOF.
            # The stopped service receipt is this mode's close acknowledgment.
            (sync / "challenge").write_text(after_close)
        assert (sync / "answer").read_text() != after_close and not dead(control_pid)
        assert checks.snapshot(h, control_key)["state"] == "running"
        stopped = checks.snapshot(h, key)
        assert stopped["authorization"] == before["authorization"] and stopped["candidate"] is None
        result = dict(
            platform=platform.platform(),
            mode="macOS Cocoa" if engine else "service socket",
            task=key,
            issue=issue["id"],
            before=before,
            stopped=stopped,
            service_pid=os.getpid(),
            producer_pid=leader,
            child_pid=child,
            pgids=pgids,
            closed_pids=[leader, child],
            physical_exit_readback_ms=physical_exit_ms,
            control_pid=control_pid,
            control_task=control_key,
            control_alive=True,
            answered_before_close=True,
            answered_after_close=False,
            editors=windows,
        )
        if revoke:
            h.confirm(issue, "revoked").raise_for_status()
        if not restartable or revoke:
            assert h.client.post(ROUTE, json={}, headers=LEASE).raise_for_status().json()["continued"] == 0
            assert len(h.observations()) == 1
            return result
        status = h.api("status", key=key).raise_for_status().json()
        (event,) = [e for e in status["progress"]["events"] if e["step"] == "process.interrupted"]
        archive = workflow.worker.root / event["details"]["archive"]
        assert (archive / "work/a/abandoned").read_text() == "uncollected partial output"
        (sync / "release").touch()
        if engine:
            with window(engine, project, url, token, sync / "close") as second:
                wait(lambda: checks.snapshot(h, key)["state"] == "stage-reached", "reopened Cocoa stage")
            windows.append(second)
            assert second["pid"] != windows[0]["pid"]
        else:
            assert h.client.post(ROUTE, json={}, headers=LEASE).raise_for_status().json()["continued"] == 1
        after = checks.snapshot(h, key)
        assert (
            after["authorization"] == before["authorization"] and after["input_revisions"] == before["input_revisions"]
        )
        assert after["state"] == after["stage_receipt"]["state"] == "stage-reached"
        assert after["pending_decision"] == {"task": key, "kind": "stage-confirmation"}
        counts = checks.count_processes(h)
        assert len(counts["workers"]) == 2 and counts["workers"][0] == leader != counts["workers"][1]
        assert len(counts["checkers"]) == 1 and not dead(control_pid)
        assert all(o["execution"] == key and o["grant"] == before["authorization"]["stage"] for o in h.observations())
        assert after["candidate"] == after["stage_receipt"]["candidate"]
        preview = workflow.worker.store.read(tenant, "a", after["artifact_revisions"]["a"], "preview.svg")
        assert preview.decode() == checks.stage.PREVIEW
        assert h.api("status", key=key).raise_for_status().json()["acceptance"] is None
        # Another reopen must not run the producer or checker a third time.
        assert h.client.post(ROUTE, json={}, headers=LEASE).raise_for_status().json()["continued"] == 0
        assert checks.count_processes(h) == counts
        result.update(
            after=after,
            processes=counts,
            interrupted=event["details"],
            http=http,
            preview_sha256=hashlib.sha256(preview).hexdigest(),
        )
        if executable:
            with executable.open("rb") as file:
                result["editor_sha256"] = hashlib.file_digest(file, "sha256").hexdigest()
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, help="Bare compiled candidate; omit for the service-only test")
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="q05-close-") as temp, patch.dict(os.environ, GONGGONG_WORKSPACE=""):
        result = exercise(Path(temp), args.godot.resolve(strict=True) if args.godot else None)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
