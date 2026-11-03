"""Run Godot/GongGong acceptance with loopback model fixtures, never a real provider."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def inventory(folder):
    return {
        p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out = args.out.resolve()
    if args.out.is_relative_to((ROOT / "gonggong-diting-data").resolve()):
        parser.error("The acceptance report must not be written into the production Diting dataset")
    env = dict(
        os.environ,
        PYTHONUTF8="1",
        PYTHONDONTWRITEBYTECODE="1",
        GONGGONG_NODE=str(ROOT / "project/runtime/node/node.exe"),
        GONGGONG_PYTHON=sys.executable,
    )
    env.pop("GODOT_AI_API_KEY", None)
    env.pop("OPENAI_API_KEY", None)
    env.pop("PYTHONOPTIMIZE", None)
    env["PATH"] = os.pathsep.join([
        str(ROOT / "project/runtime/git/cmd"),
        str(ROOT / "project/runtime/node"),
        env.get("PATH", ""),
    ])
    editor = ROOT / "project/godot/bin/godot.windows.editor.x86_64.console.exe"
    engine = editor.with_name("godot.windows.editor.x86_64.exe")
    checks = [
        ("doctor", [sys.executable, "tools/gonggong_bridge.py", "doctor", "--workspace", "."]),
        ("bridge_unit", [sys.executable, "customizations/components/godot-host/test_bridge.py"]),
        ("distribution", [sys.executable, "tests/editor/test_gonggong_distribution.py"]),
        ("native_ai_chat", [str(editor), "--headless", "--test", "--test-case=[AIChat]*"]),
        ("installed_location", [sys.executable, "tests/editor/run_gonggong_install_probe.py", "--godot", str(editor)]),
    ]
    modes = ("admitted", "accepted", "rejected", "tool", "cancel", "recovery", "recovery_rejected", "recovery_cancel")
    checks += [
        (
            "native_" + mode,
            [sys.executable, "tests/editor/run_gonggong_chat_gate.py", "--godot", str(editor), "--mode", mode],
        )
        for mode in modes
    ]
    dataset_before = inventory(ROOT / "gonggong-diting-data")
    report = {
        "schema_version": 1,
        "verification": "simulated_model_end_to_end",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "external_model_service_tested": False,
        "model_transport": "loopback HTTP fixture only",
        "production_model_credentials_used": False,
        "editor": {
            "path": editor.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(editor.read_bytes()).hexdigest(),
        },
        "engine": {
            "path": engine.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(engine.read_bytes()).hexdigest(),
        },
        "checks": [],
        "limitations": [
            "Successful model replies are simulated, not provider certification.",
            "The admitted scenario uses real approved GongGong definitions and local package checks; other positive transport scenarios use isolated context fixtures.",
        ],
    }
    for name, command in checks:
        started = datetime.now(timezone.utc)
        try:
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=180)
            output = result.stdout.decode("utf-8", errors="replace")
            errors = result.stderr.decode("utf-8", errors="replace")
            item = {
                "name": name,
                "ok": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
                "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
            }
            if name == "doctor":
                diagnostic = json.loads(output)
                item.update(ok=item["ok"] and diagnostic["ok"], blocking_checks=diagnostic["blocking_checks"])
            elif name in ("bridge_unit", "distribution"):
                count = re.search(r"Ran (\d+) tests? in ", errors)
                item["tests_run"] = int(count[1]) if count else 0
                item["ok"] = (
                    item["ok"]
                    and item["tests_run"] >= (16 if name == "bridge_unit" else 4)
                    and bool(re.search(r"^OK\s*$", errors, re.MULTILINE))
                )
            elif name == "native_ai_chat":
                for label, minimum in (("test cases", 12), ("assertions", 107)):
                    counts = re.search(re.escape(label) + r":\s*(\d+)\s*\|\s*(\d+) passed\s*\|\s*(\d+) failed", output)
                    measured = (
                        {"total": int(counts[1]), "passed": int(counts[2]), "failed": int(counts[3])}
                        if counts
                        else {"total": 0, "passed": 0, "failed": 0}
                    )
                    item[label.replace(" ", "_")] = measured
                    item["ok"] = (
                        item["ok"]
                        and measured["total"] >= minimum
                        and measured["passed"] == measured["total"]
                        and measured["failed"] == 0
                    )
            elif name.startswith("native_") and name != "native_ai_chat" and result.returncode == 0:
                item["observed"] = next(
                    json.loads(line)
                    for line in reversed(output.splitlines())
                    if line.startswith("{") and ("native_page" in line or "model_requests" in line)
                )
        except (OSError, subprocess.TimeoutExpired, ValueError, StopIteration) as error:
            item = {"name": name, "ok": False, "error_kind": type(error).__name__}
        item["elapsed_seconds"] = round((datetime.now(timezone.utc) - started).total_seconds(), 3)
        report["checks"].append(item)
        print(json.dumps({"check": name, "ok": item["ok"]}), flush=True)
    report["production_dataset_unchanged"] = inventory(ROOT / "gonggong-diting-data") == dataset_before
    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    report["ok"] = all(item["ok"] for item in report["checks"]) and report["production_dataset_unchanged"]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
