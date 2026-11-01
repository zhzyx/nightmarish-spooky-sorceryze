"""Godot host adapter. Framework/data remain in their existing Git workspace."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def run(command, cwd):
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=120,
                                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"})
        return {"ok": result.returncode == 0, "exit_code": result.returncode,
                "stdout": result.stdout, "stderr": result.stderr}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ok": False, "error": str(error)}


def execute(workspace, action, tenant):
    root = Path(workspace).resolve()
    framework = root / "Olympus"
    manifest = json.loads((framework / "framework-manifest.json").read_text(encoding="utf-8"))
    result = {"action": action, "framework_version": manifest["version"],
              "agent_execution_enabled": False,
              "admission": "Requires independent admission and authenticated host authority",
              "agents": [{"id": a["id"], "state": a["state"]} for a in manifest["agents"]]}
    hermes = str(framework / "extensions/hermes-files/hermes_files.py")
    if action == "status":
        result.update(ok=True, framework_status=manifest["status"],
                      data_available=(root / "olympus-hermes-data/dataset.json").is_file())
    elif action == "check":
        result.update(run([sys.executable, str(framework / "tools/verify_framework.py"), "--candidate"], root))
    elif action == "validate":
        result.update(run([sys.executable, hermes, "validate", "--repo", str(root)], root))
    elif action == "analyze":
        result.update(run([sys.executable, hermes, "analyze", "--repo", str(root), "--tenant", tenant], root))
    else:
        raise ValueError("Unsupported action")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["status", "check", "validate", "analyze"])
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--tenant", default="olympus-workspace")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        result = execute(args.workspace, args.action, args.tenant)
    except (OSError, ValueError, KeyError, TypeError) as error:
        result = {"ok": False, "agent_execution_enabled": False, "error": str(error)}
    content = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        temporary = args.out.with_suffix(".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(args.out)
    else:
        print(content)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
