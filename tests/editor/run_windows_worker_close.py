"""Exercise the native Windows editor EXIT_TREE with two live, isolated process trees."""

import argparse
import ctypes
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).resolve()
RUNNER = ROOT / "tools/godot_parallel/runner.mjs"
REQUEST = "gonggong-ai-workbench-plan1-r03"
HIDDEN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def read(file):
    return json.loads(file.read_text(encoding="utf8"))


def write(file, value):
    scratch = file.with_suffix(".writing")
    scratch.write_text(json.dumps(value, indent=2) + "\n", encoding="utf8")
    scratch.replace(file)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cmd(*args, cwd=ROOT):
    return subprocess.check_output(args, cwd=cwd, text=True, encoding="utf8", creationflags=HIDDEN).strip()


def wait_until(check, description, seconds=25):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(0.05)
    raise RuntimeError(description)


def fixture(role, folder, token, parent_mode):
    record = {"role": role, "pid": os.getpid(), "ppid": os.getppid(), "probe_id": token}
    if role == "worker":
        prompt = sys.stdin.read()
        if token not in prompt:
            raise RuntimeError("Worker received unexpected assignment")
        output = read(next((folder / "project/data-collection/outbox").glob("*.result.json")))["workers"][0]
        record.update(execution_id=output["execution_id"], worker_id=output["worker_id"])
        parent_mode = output["execution_id"]
    if role in {"control", "worker"}:
        child_role = "descendant" if role == "worker" else "control-child"
        child = subprocess.Popen(
            [sys.executable, SCRIPT, "--fixture", child_role, folder, token, parent_mode],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=HIDDEN,
        )
        record["child_pid"] = child.pid
    else:
        record["execution_id"] = parent_mode
    write(folder / (role + ".ready"), record)
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline and not (folder / "finish").exists():
        if role == "control-child" and (folder / "challenge").exists() and not (folder / "answer").exists():
            write(folder / "answer", {**record, "challenge": read(folder / "challenge"), "at": timestamp()})
        time.sleep(0.05)
    if role in {"control", "worker"}:
        child.wait(timeout=8)


class ProcessHandle:
    """Hold a handle to the original process object across exit and PID reuse."""

    def __init__(self, pid):
        self.pid = pid
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        self.kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        self.kernel.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
        self.handle = self.kernel.OpenProcess(0x00100000 | 0x1000, False, pid)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())

    def state(self, milliseconds=0):
        result = self.kernel.WaitForSingleObject(self.handle, milliseconds)
        if result == 0:
            return "exited"
        if result == 258:
            return "alive"
        raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        self.kernel.CloseHandle(self.handle)

    def identity(self):
        times = [wintypes.FILETIME() for _ in range(4)]
        if not self.kernel.GetProcessTimes(self.handle, *(ctypes.byref(value) for value in times)):
            raise ctypes.WinError(ctypes.get_last_error())
        created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        return {
            "pid": self.pid,
            "probe_process_pid": os.getpid(),
            "handle_value": hex(self.handle),
            "creation_filetime": str(created),
        }


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def project(folder, fixture_issue):
    source = folder / "project"
    source.mkdir()
    cmd("git", "init", "-q", "-b", "main", cwd=source)
    cmd("git", "config", "core.autocrlf", "false", cwd=source)
    for name in ["work-items.json", ".github/labels.json", "gonggong-diting-data/dataset.json"]:
        dst = source / name
        dst.parent.mkdir(exist_ok=True, parents=True)
        shutil.copyfile(ROOT / name, dst)
    if fixture_issue:
        settings = source / "work-items.json"
        write(settings, {**read(settings), "repository": "example/r03-private-fixture"})
    (source / "design-docs").mkdir()
    (source / "design-docs" / (REQUEST + ".md")).write_text(
        "# R03\n\n## 设计定版确认\nWindows close test\n\n## 生产工单\n1. Exercise " + folder.name + "\n",
        encoding="utf8",
    )
    cmd("git", "add", "--all", cwd=source)
    cmd(
        "git",
        "-c",
        "user.name=Windows process fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-qm",
        "Isolated process probe inputs",
        cwd=source,
    )
    repo = read(source / "work-items.json")["repository"]
    cmd("git", "remote", "add", "origin", "https://github.com/" + repo + ".git", cwd=source)
    # The real intake reads remote Issue metadata. This private fixture has no push destination.
    cmd("git", "remote", "set-url", "--push", "origin", str(folder / "no-push"), cwd=source)
    worker = folder / "worker"
    cmd("git", "worktree", "add", "-q", "-b", "probe", str(worker), cwd=source)
    return source, worker


def reservations(source, result):
    outbox = source / "data-collection/outbox"
    claims = {}
    for kind in ("capacity", "resource", "ticket"):
        matches = sorted(outbox.glob("parallel-" + kind + "-*.json"))
        assert len(matches) <= 1
        claims[kind] = {"count": len(matches)}
        if matches:
            saved = read(matches[0])
            claims[kind]["sha256"] = digest(matches[0])
            claims[kind].update({
                k: saved[k] for k in ("requestId", "order", "state", "execution_id", "worker_id") if k in saved
            })
            if "output" in saved:
                claims[kind]["references_this_output"] = Path(saved["output"]).resolve() == result.resolve()
    return {"output_running": Path(str(result) + ".running").exists(), "claims": claims}


def checked_ref(value):
    path = Path(value["path"])
    assert digest(path) == value["sha256"]
    return read(path)


def trial(folder, editor, mode, fixture_issue):
    from editor_test_isolation import copy_editor

    source, worktree = project(folder, fixture_issue)
    token = folder.name
    config = folder / "config.json"
    owner = "r03-" + token
    worker_python = sys._base_executable  # avoid the Windows venv redirector in PID assertions
    write(
        config,
        {
            "authorityRef": "codex-user:20261122-plan1-afterk03-r03",
            "capacity": 1,
            "nativeWorkspaceWrite": True,
            "python": sys.executable,
            "workerCommand": {
                "executable": worker_python,
                "args": [str(SCRIPT), "--fixture", "worker", str(folder), token, "{model}"],
            },
            "models": [
                {
                    "id": "local-fixture",
                    "available": True,
                    "targets": ["agent"],
                    "capabilities": ["coding"],
                    "preference": 1,
                }
            ],
            "jobs": [
                {"order": 1, "worktree": str(worktree), "workerId": owner, "capabilities": ["coding"], "dependsOn": []}
            ],
        },
    )
    installation = folder / "installation"
    installation.mkdir()
    binary = copy_editor(editor, installation / "bin")
    # The installed editor locates tools next to its own SConstruct. Delegate in the
    # same Node process so Godot owns the actual candidate runner PID and Job.
    (installation / "SConstruct").touch()
    entry = installation / "tools/godot_parallel/runner.mjs"
    entry.parent.mkdir(parents=True)
    entry.write_text(
        "process.argv[1] = " + json.dumps(str(RUNNER)) + "; await import(" + json.dumps(RUNNER.as_uri()) + ");"
    )
    (source / "project.godot").write_text('config_version=5\n[application]\nconfig/name="R03"\n')
    history = source / ".godot/editor/ai_chat_history.json"
    history.parent.mkdir(parents=True)
    write(
        history,
        {
            "version": 1,
            "active_agent": 0,
            "next_agent": 1,
            "scheduled_tasks": [],
            "sub_agent_spawned": {},
            "agents": [
                {
                    "id": 0,
                    "conversation_id": uuid.uuid4().hex,
                    "title": "R03 fixture owner",
                    "backend": 0,
                    "model": "fixture",
                    "cli_model": "",
                    "codex_model": "",
                    "draft": "",
                    "draft_images": [],
                    "messages": [],
                    "transcript": [],
                    "queued_messages": [],
                    "queue_paused": False,
                }
            ],
        },
    )
    shutil.copyfile(SCRIPT.with_name("windows_worker_close.gd"), source / "probe.gd")
    env = dict(
        os.environ,
        R03_NODE=shutil.which("node"),
        R03_PYTHON=sys.executable,
        R03_CONFIG=str(config),
        R03_DIR=str(folder),
        GONGGONG_KUAFU_LOCAL_ONLY="1",
        PYTHONUTF8="1",
        PYTHONDONTWRITEBYTECODE="1",
    )
    # Keep the host's gh read-only intake available while isolating all editor settings.
    if "GH_CONFIG_DIR" not in env:
        env["GH_CONFIG_DIR"] = str(Path(env["APPDATA"]) / "GitHub CLI")
    for name in (
        "APPDATA",
        "LOCALAPPDATA",
        "HOME",
        "USERPROFILE",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
    ):
        directory = folder / name
        directory.mkdir()
        env[name] = str(directory)
    if fixture_issue:
        from run_design_batch import fixture_program

        repo = read(source / "work-items.json")["repository"]
        issue = {
            "number": 1775,
            "html_url": f"https://github.com/{repo}/issues/1775",
            "state": "open",
            "updated_at": "2026-11-22T13:21:35Z",
            "body": f"<!-- gonggong-request:{REQUEST} -->",
            "labels": [{"name": label} for label in ("type:development", "status:in-progress", "workspace:gonggong")],
        }
        env["GONGGONG_GH"] = str(
            fixture_program(
                folder / "fixture-gh",
                "import json, sys\nassert sys.argv[1:] == "
                + repr(["api", f"repos/{repo}/issues/1775"])
                + "\nprint(json.dumps("
                + repr(issue)
                + "))\n",
            )
        )
    control = subprocess.Popen(
        [worker_python, SCRIPT, "--fixture", "control", folder, token, "control-" + token],
        stdin=subprocess.DEVNULL,
        creationflags=HIDDEN,
    )
    handles = {}
    engine = None
    try:
        outbox = source / "data-collection/outbox"
        with (folder / "editor.log").open("wb") as log:
            engine = subprocess.Popen(
                [
                    binary,
                    "--headless",
                    "--audio-driver",
                    "Dummy",
                    "--editor",
                    "--path",
                    source,
                    "--script",
                    "res://probe.gd",
                ],
                creationflags=HIDDEN,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                env=env,
            )
        roles = ("worker", "descendant", "control", "control-child")

        def ready():
            if engine.poll() is not None:
                raise RuntimeError("Editor exited before workers were ready")
            return all((folder / (role + ".ready")).exists() for role in roles)

        wait_until(ready, "Native dispatch did not start both trees", 85)
        (result,) = outbox.glob("*.result.json")
        (live,) = read(result)["workers"]
        reg = checked_ref(live["registration"])
        assert reg["worker_id"] == live["worker_id"] == owner and reg["execution_id"] == live["execution_id"]
        assert reg["request_id"] == REQUEST and reg["issue_number"] == 1775
        assert digest(Path(reg["dispatch_request"]["path"])) == reg["dispatch_request"]["sha256"]
        assert reg["editor_runtime"]["sha256"] == digest(binary)
        rows = {role: read(folder / (role + ".ready")) for role in roles}
        assert all(row["probe_id"] == token and row["role"] == role for role, row in rows.items())
        assert rows["worker"]["pid"] == live["pid"] and rows["worker"]["execution_id"] == reg["execution_id"]
        assert (
            rows["descendant"]["ppid"] == rows["worker"]["pid"]
            and rows["descendant"]["execution_id"] == live["execution_id"]
        )
        assert rows["control"]["pid"] == control.pid and rows["control-child"]["ppid"] == control.pid
        for role, row in rows.items():
            handles[role] = ProcessHandle(row["pid"])
        before = {k: h.state() for k, h in handles.items()}
        assert set(before.values()) == {"alive"}
        claims_before = reservations(source, result)
        assert all(v["count"] == 1 for v in claims_before["claims"].values()) and claims_before["output_running"]
        if mode == "foreign-claim":
            (slot,) = outbox.glob("parallel-capacity-*.json")
            write(slot, {**read(slot), "owner": "foreign-" + token})
            foreign_sha256 = digest(slot)
        if mode == "registration-drift":
            registration_path = Path(live["registration"]["path"])
            write(registration_path, {**reg, "worker_id": "changed-registration"})
        (folder / "close-editor").touch(exist_ok=False)
        assert engine.wait(timeout=40) == 0
        assert "R03_NORMAL_EDITOR_QUIT" in (folder / "editor.log").read_text(encoding="utf8", errors="replace")
        marker = Path(str(result) + ".quiesce")
        assert marker.read_text().strip() == str(engine.pid)
        after = {k: h.state() for k, h in handles.items()}
        assert after == {"worker": "exited", "descendant": "exited", "control": "alive", "control-child": "alive"}
        challenge = str(uuid.uuid4())
        write(folder / "challenge", challenge)
        wait_until(lambda: (folder / "answer").exists(), "Control did not respond after editor exit")
        answer = read(folder / "answer")
        assert answer["pid"] == rows["control-child"]["pid"] and answer["challenge"] == challenge
        (final,) = read(result)["workers"]
        terminal = {}
        if mode == "registration-drift":
            assert "terminal_receipt" not in final and "registration" in final["terminal_error"].lower()
            assert final["state"] == "reconcile_required" and not final["transport_completed"]
        else:
            terminal = checked_ref(final["terminal_receipt"])
            assert terminal["windows_shutdown"] == final["windows_shutdown"]
            assert (
                terminal["windows_shutdown"]["active_processes"] == 0
                and terminal["windows_shutdown"]["action"] == "editor_close"
            )
            assert terminal["registration"] == live["registration"] and terminal["pid"] == live["pid"]
            assert terminal["execution_id"] == live["execution_id"] and terminal["worker_id"] == owner
            assert (
                terminal["cancel_requested"]
                and not terminal["transport_completed"]
                and terminal["business_accepted"] is None
            )
            assert terminal["reporting"]["state"] == "recorded_file"
        claims_after = reservations(source, result)
        assert not claims_after["output_running"] and claims_after["claims"]["ticket"]["count"] == 1
        remaining = 0 if mode == "normal" else 1
        for kind in ("capacity", "resource"):
            assert claims_after["claims"][kind]["count"] == remaining
        if mode == "foreign-claim":
            assert digest(slot) == foreign_sha256 and final["reason"] == "Shutdown claim ownership changed"
        elif mode == "normal":
            ticket = read(next(outbox.glob("parallel-ticket-*.json")))
            assert ticket["terminal_receipt"] == final["terminal_receipt"]
        return dict(
            mode=mode,
            editor_pid=engine.pid,
            editor_exit=engine.returncode,
            registration_sha256=live["registration"]["sha256"],
            terminal_sha256=final.get("terminal_receipt", {}).get("sha256"),
            terminal_error=final.get("terminal_error"),
            execution_id=live["execution_id"],
            worker_id=owner,
            windows_job_terminal=final["windows_shutdown"],
            reporting=final["reporting"]["state"],
            business_accepted=terminal.get("business_accepted"),
            transport_completed=final["transport_completed"],
            handles={k: h.identity() for k, h in handles.items()},
            ready=rows,
            before=before,
            after=after,
            control_answer=answer,
            reservations_before=claims_before,
            reservations_after=claims_after,
            observed_at=timestamp(),
        )
    except Exception:
        print((folder / "editor.log").read_text(encoding="utf8", errors="replace")[-5000:], file=sys.stderr)
        for path in (source / "data-collection/outbox").glob("*.result.json"):
            print(path.read_text(encoding="utf8")[-3000:], file=sys.stderr)
        raise
    finally:
        (folder / "finish").touch()
        (folder / "close-editor").touch()
        if engine and engine.poll() is None:
            engine.wait(timeout=95)
        control.wait(timeout=12)
        for handle in handles.values():
            handle.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True, help="GUI executable, started headless")
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument(
        "--fixture-issue",
        action="store_true",
        help="Use an isolated fictional repository and Issue transport for post-closure regression",
    )
    args = parser.parse_args()
    if os.name != "nt" or args.godot.name.endswith(".console.exe") or args.receipt.exists():
        parser.error("Run on Windows with the actual editor .exe and a new receipt path")
    os.environ.pop("GONGGONG_WORKSPACE", None)
    cases = []
    for mode in ("normal", "foreign-claim", "registration-drift"):
        with tempfile.TemporaryDirectory(prefix="r03-close-") as temp:
            cases.append(trial(Path(temp).resolve(), args.godot, mode, args.fixture_issue))
    files = [
        SCRIPT,
        SCRIPT.with_name("windows_worker_close.gd"),
        RUNNER,
        RUNNER.with_name("windows_worker.py"),
        ROOT / "tools/editor_provenance_process.py",
        ROOT / "editor/docks/ai_chat_dock.cpp",
    ]
    write(
        args.receipt,
        dict(
            issue_number=1775,
            request_id=REQUEST,
            base_commit=cmd("git", "rev-parse", "HEAD"),
            platform=platform.platform(),
            node=cmd("node", "--version"),
            python=platform.python_version(),
            native_sha256=digest(args.godot),
            source_sha256={p.relative_to(ROOT).as_posix(): digest(p) for p in files},
            issue_transport="private fixture" if args.fixture_issue else "live GitHub intake",
            tests=cases,
        ),
    )
    print("Windows editor close and independent control passed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--fixture":
        fixture(sys.argv[2], Path(sys.argv[3]), sys.argv[4], sys.argv[5])
    else:
        main()
