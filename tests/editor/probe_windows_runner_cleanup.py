"""Measure Windows worker cancellation and runner termination using isolated Git project data.

Run on Windows with the repository Python, Git, an authenticated read-only Issue intake,
Node on PATH, and the runner's lockfile-pinned Job Object dependency installed.
The probe uses the production CLI, admission checks and Diting adapter. Its only
worker command is this bounded local process fixture. No editor or model is started.
"""

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
REQUEST = "gonggong-ai-workbench-plan1"
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
        output = read(folder / "result.json")["workers"][0]
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


def project(folder):
    source = folder / "project"
    source.mkdir()
    cmd("git", "init", "-q", "-b", "main", cwd=source)
    cmd("git", "config", "core.autocrlf", "false", cwd=source)
    for name in ["work-items.json", ".github/labels.json", "gonggong-diting-data/dataset.json"]:
        dst = source / name
        dst.parent.mkdir(exist_ok=True, parents=True)
        shutil.copyfile(ROOT / name, dst)
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


def trial(folder, mode):
    source, worker = project(folder)
    token = str(uuid.uuid4())
    owner = "afterk03-win-probe-" + token
    roles = ("worker", "descendant", "control", "control-child")
    config, dispatch, result = (folder / name for name in ("config.json", "request.json", "result.json"))
    write(
        config,
        {
            "authorityRef": "codex-user:20261122-plan1-afterk03-win-probe",
            "capacity": 1,
            "nativeWorkspaceWrite": True,
            "python": sys.executable,
            "workerCommand": {
                "executable": sys.executable,
                "args": [str(SCRIPT), "--fixture", "worker", str(folder), token, "{model}"],
            },
            "models": [
                {
                    "id": "local-probe",
                    "available": True,
                    "targets": ["agent"],
                    "capabilities": ["coding"],
                    "preference": 1,
                }
            ],
            "jobs": [
                {"order": 1, "worktree": str(worker), "workerId": owner, "capabilities": ["coding"], "dependsOn": []}
            ],
        },
    )
    write(
        dispatch,
        {
            "workspace": str(source),
            "issue": 1709,
            "requestId": REQUEST,
            "batchId": token,
            "config": str(config),
            "workers": [{"id": 1, "order": 1, "prompt": token}],
        },
    )
    environment = dict(os.environ, PYTHONUTF8="1", GONGGONG_KUAFU_LOCAL_ONLY="1", PYTHONDONTWRITEBYTECODE="1")
    control = subprocess.Popen(
        [sys.executable, SCRIPT, "--fixture", "control", folder, token, "control-" + token],
        stdin=subprocess.DEVNULL,
        creationflags=HIDDEN,
        env=environment,
    )
    handles = {}
    runner = None
    try:
        with (folder / "stderr.log").open("wb") as log:
            runner = subprocess.Popen(
                [shutil.which("node"), RUNNER, dispatch, result, digest(dispatch)],
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                creationflags=HIDDEN,
                env=environment,
            )

        def ready():
            if runner.poll() is not None:
                error = (folder / "stderr.log").read_text(encoding="utf8")
                outcome = read(result)["workers"][0] if result.exists() else {}
                raise RuntimeError(
                    f"Runner exited before readiness: {runner.returncode}, {outcome.get('state')}, "
                    f"{outcome.get('reason')}, {outcome.get('reportingError')}, {error}"
                )
            return all((folder / (r + ".ready")).exists() for r in roles)

        wait_until(ready, "Both trees must reach readiness", 60)
        rows = {role: read(folder / (role + ".ready")) for role in roles}
        for role, row in rows.items():
            assert row["probe_id"] == token and row["role"] == role
            handles[role] = ProcessHandle(row["pid"])
        live = read(result)["workers"][0]
        execution = live["execution_id"]
        reg = live["registration"]
        assert digest(Path(reg["path"])) == reg["sha256"]
        registration = read(Path(reg["path"]))
        assert registration["batch_id"] == token and registration["worker_id"] == live["worker_id"] == owner
        assert registration["execution_id"] == rows["worker"]["execution_id"] == execution
        assert registration["issue_number"] == 1709 and registration["request_id"] == REQUEST
        assert registration["dispatch_request"]["sha256"] == digest(dispatch)
        assert rows["worker"]["ppid"] == runner.pid and rows["worker"]["pid"] == live["pid"]
        assert rows["descendant"]["pid"] == rows["worker"]["child_pid"]
        assert rows["descendant"]["ppid"] == live["pid"] and rows["descendant"]["execution_id"] == execution
        assert rows["control"]["pid"] == control.pid and rows["control-child"]["ppid"] == control.pid
        assert rows["control"]["child_pid"] == rows["control-child"]["pid"]
        before = {role: handle.state() for role, handle in handles.items()}
        assert set(before.values()) == {"alive"}
        identities = {role: handle.identity() for role, handle in handles.items()}
        claims_before = reservations(source, result)
        assert all(v["count"] == 1 for v in claims_before["claims"].values())
        assert claims_before["claims"]["ticket"]["execution_id"] == execution
        triggered = timestamp()
        if mode == "cancel":
            (folder / "result.json.1.cancel").touch(exist_ok=False)
        else:
            runner.terminate()
        runner_exit = runner.wait(timeout=25)
        after = {
            role: handle.state(2500 if role in ("worker", "descendant") else 0) for role, handle in handles.items()
        }
        challenge = str(uuid.uuid4())
        write(folder / "challenge", challenge)
        wait_until(lambda: (folder / "answer").exists(), "Independent child did not answer after action", 5)
        answer = read(folder / "answer")
        assert answer["challenge"] == challenge and answer["pid"] == rows["control-child"]["pid"]
        assert answer["probe_id"] == token and answer["execution_id"] == "control-" + token
        final = read(result)["workers"][0]
        claims_after = reservations(source, result)
        terminal = None
        if "terminal_receipt" in final:
            ref = final["terminal_receipt"]
            assert digest(Path(ref["path"])) == ref["sha256"]
            data = read(Path(ref["path"]))
            assert data["execution_id"] == execution and data["worker_id"] == owner and data["pid"] == live["pid"]
            terminal = {
                k: data[k]
                for k in (
                    "execution_id",
                    "worker_id",
                    "pid",
                    "exit_code",
                    "cancel_requested",
                    "transport_completed",
                    "business_accepted",
                    "state",
                )
            }
            terminal["raw_sha256"] = ref["sha256"]
        return {
            "action": mode,
            "probe_id": token,
            "runner_pid": runner.pid,
            "runner_exit": runner_exit,
            "ready": rows,
            "registration_sha256": reg["sha256"],
            "actions_started_utc": triggered,
            "process_handles": identities,
            "before": before,
            "after_runner_exit": after,
            "result_record": final["state"],
            "terminal": terminal,
            "reservations_before": claims_before,
            "reservations_after": claims_after,
            "control_kind": "independent local process, no runner reservations",
            "control_challenge_file_sha256": digest(folder / "challenge"),
            "control_answer": answer,
            "control_answer_file_sha256": digest(folder / "answer"),
            "observed_at": timestamp(),
        }
    finally:
        (folder / "finish").touch()
        if runner and runner.poll() is None:
            runner.terminate()
            runner.wait(timeout=10)
        control.wait(timeout=10)
        for role, handle in handles.items():
            try:
                if handle.state(8000) != "exited":
                    raise RuntimeError("Fixture process remains active: " + role)
            finally:
                handle.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True, help="New sanitized local JSON receipt")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("Windows required")
    if args.receipt.exists():
        parser.error("Choose a new receipt file")
    evidence = {
        "source_issue": 1709,
        "source_head": cmd("git", "rev-parse", "HEAD"),
        "entry_point": "tools/godot_parallel/runner.mjs",
        "probe_sha256": digest(SCRIPT),
        "observations": "WaitForSingleObject on original handles: WAIT_TIMEOUT=alive, WAIT_OBJECT_0=exited",
        "platform": platform.platform(),
        "node": cmd("node", "--version"),
        "python": platform.python_version(),
        "runner_sha256": digest(RUNNER),
        "job_object_sha256": digest(
            ROOT / "tools/codebuddy_cli/node_modules/@tencent-ai/codebuddy-code/bin/native/win32-x64/job-object.node"
        ),
        "trials": [],
    }
    for mode in ("cancel", "terminate-runner"):
        with tempfile.TemporaryDirectory(prefix="gg-win-process-") as tmp:
            evidence["trials"].append(trial(Path(tmp), mode))
    write(args.receipt, evidence)
    for trial_data in evidence["trials"]:
        assert trial_data["after_runner_exit"] == {
            "worker": "exited",
            "descendant": "exited",
            "control": "alive",
            "control-child": "alive",
        }
        if trial_data["action"] == "cancel":
            assert trial_data["terminal"]["cancel_requested"] and not trial_data["terminal"]["transport_completed"]
    print("Both owned process trees exited and the independent control answered in each trial.")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--fixture"]:
        fixture(sys.argv[2], Path(sys.argv[3]), sys.argv[4], sys.argv[5])
    else:
        main()
