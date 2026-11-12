"""Silent native root/subdirectory binding probe; no provider or Issue publication."""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time
from contextlib import nullcontext
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--godot", type=Path, required=True)
parser.add_argument("--report", type=Path, required=True)
args = parser.parse_args()
host = Path(__file__).resolve().parents[2]
private = host / "data-collection/outbox/game-workspace-native"
private.mkdir(parents=True, exist_ok=True)
editor = private / args.godot.name
shutil.copy2(args.godot, editor)
(private / "_sc_").touch()
(private / "editor_data").mkdir(exist_ok=True)
package = args.godot.parent / "tianshu-ui.json"
if package.exists():
    shutil.copy2(package, private / package.name)
env = {k: v for k, v in os.environ.items() if not k.startswith("GONGGONG_")}
env.update(PYTHONUTF8="1", GONGGONG_TEST_PYTHON=os.environ.get("GONGGONG_TEST_PYTHON", ""))
results = []
with nullcontext(tempfile.mkdtemp(prefix="gonggong-game-binding-")) as folder:
    repo = Path(folder).resolve()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    for name in ("", "game"):
        project = repo / name
        project.mkdir(exist_ok=True)
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Game binding probe"\n', encoding="utf-8"
        )
        receipt = private / ("subdirectory.json" if name else "root.json")
        env.update(GAME_WORKSPACE_EXPECTED=str(repo), GAME_WORKSPACE_REPORT=str(receipt))
        result = subprocess.run(
            [
                str(editor),
                "--headless",
                "--editor",
                "--path",
                str(project),
                "--script",
                str(host / "tests/editor/game_workspace_binding.gd"),
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
        )
        (private / ("subdirectory.log" if name else "root.log")).write_text(
            result.stdout + result.stderr, encoding="utf-8"
        )
        observed = json.loads(receipt.read_text(encoding="utf-8")) if receipt.exists() else {"ok": False}
        # Retain fixture files and wait for owned editor/board helpers, never delete live data.
        env.update(GAME_PROBE_EDITOR=str(editor.resolve()), GAME_PROBE_ROOT=str(repo))
        remaining = []
        deadline = time.monotonic() + 20
        if os.name == "nt":
            query = "@(Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq $env:GAME_PROBE_EDITOR -or ($_.Name -match '^python' -and $_.CommandLine -like ('*' + $env:GAME_PROBE_ROOT + '*')) } | Select-Object ProcessId,Name) | ConvertTo-Json -Compress"
            while True:
                checked = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", query], env=env, capture_output=True, text=True, timeout=10
                )
                remaining = (
                    json.loads(checked.stdout)
                    if checked.returncode == 0 and checked.stdout.strip()
                    else ([] if checked.returncode == 0 else [{"state": "unknown"}])
                )
                if not remaining or time.monotonic() >= deadline:
                    break
                time.sleep(0.25)
        observed.update(
            case="subdirectory" if name else "root",
            exit_code=result.returncode,
            quiescent=not remaining,
            remaining_owned_processes=remaining,
        )
        observed["ok"] = observed["ok"] and not remaining
        results.append(observed)
args.report.write_text(
    json.dumps(
        {"ok": all(r["ok"] and r["exit_code"] == 0 for r in results), "cases": results, "provider_execution": False},
        indent=2,
    ),
    encoding="utf-8",
)
raise SystemExit(0 if all(r["ok"] and r["exit_code"] == 0 for r in results) else 1)
