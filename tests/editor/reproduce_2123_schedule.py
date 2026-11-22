"""Target the first real startup child of this harness only (macOS acceptance workflow)."""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def processes():
    output = subprocess.check_output(["ps", "-axww", "-o", "pid=,ppid=,command="], text=True)
    rows = (line.strip().split(None, 2) for line in output.splitlines())
    return {int(pid): (int(parent), command) for pid, parent, command in rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", required=True)
    parser.add_argument("--app", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--expect-old-race", action="store_true")
    args = parser.parse_args()
    command = [sys.executable, args.script, "--app", args.app, "--manifest", args.manifest, "--report", args.report]
    evidence = {}
    with (
        args.report.with_suffix(".log").open("wb") as log,
        subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT) as harness,
    ):
        deadline = time.monotonic() + 100
        while harness.poll() is None and time.monotonic() < deadline:
            rows = processes()
            editors = {
                pid
                for pid, (ppid, cmd) in rows.items()
                if ppid == harness.pid and "Candidate.app/Contents/MacOS/Godot --editor" in cmd
            }
            children = [
                (pid, ppid, cmd)
                for pid, (ppid, cmd) in rows.items()
                if ppid in editors and "gonggong-validation-" in cmd and "/Godot --headless --editor" in cmd
            ]
            if children:
                if len(children) != 1:
                    raise RuntimeError("Ambiguous isolated probe")
                pid, ppid, cmd = children[0]
                os.kill(pid, signal.SIGSTOP)
                start = time.monotonic()
                evidence = {"editor_pid": ppid, "child_pid": pid, "command": cmd, "requested_delay_seconds": 38}
                try:
                    while time.monotonic() - start < 38 and processes().get(pid) == (ppid, cmd):
                        time.sleep(0.1)
                finally:
                    evidence["elapsed_seconds"] = round(time.monotonic() - start, 3)
                    evidence["alive_before_resume"] = processes().get(pid) == (ppid, cmd)
                    if evidence["alive_before_resume"]:
                        os.kill(pid, signal.SIGCONT)
                break
            time.sleep(0.1)
        code = harness.wait(timeout=1100)
    evidence["harness_exit_code"] = code
    args.report.with_suffix(".schedule.json").write_text(json.dumps(evidence, indent=2))
    assert "child_pid" in evidence, evidence
    result = json.loads(args.report.read_bytes())
    cold = result["cases"]["cold"]
    if args.expect_old_race:
        assert code != 0 and not evidence["alive_before_resume"], evidence
        assert cold == {"exit_code": 0, "new_receipts": [], "observations": []}, cold
    else:
        assert code == 0 and result["state"] == "passed" and evidence["alive_before_resume"], evidence
        assert len(cold["new_receipts"]) == 1 and len(result["cases"]) == 11, result


if __name__ == "__main__":
    main()
