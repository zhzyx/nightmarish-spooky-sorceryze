"""Run real settings controls in a temporary plain SceneTree, never an editor."""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", required=True)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="maliang-unified-settings-") as temporary:
        sandbox = Path(temporary)
        project = sandbox / "project"
        project.mkdir()
        shutil.copytree(source / "addons", project / "addons", ignore=shutil.ignore_patterns(".godot", "__pycache__"))
        shutil.copy2(source / "unified_settings_acceptance.gd", project)
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Isolated settings controls"\n', encoding="utf-8"
        )
        env = {
            key: os.environ[key]
            for key in os.environ
            if not any(
                part in key.upper()
                for part in (
                    "AINATIVE",
                    "GONGGONG",
                    "OPENAI",
                    "ANTHROPIC",
                    "CODEX",
                    "API_KEY",
                    "TOKEN",
                    "SECRET",
                    "CREDENTIAL",
                )
            )
        }
        env.update({
            "APPDATA": str(sandbox / "appdata"),
            "LOCALAPPDATA": str(sandbox / "localappdata"),
            "XDG_CONFIG_HOME": str(sandbox / "config"),
            "XDG_DATA_HOME": str(sandbox / "data"),
            "AINATIVE_SETTINGS_TEST_DIR": str(sandbox / "settings"),
            "AINATIVE_SETTINGS_REPORT": str(args.report.resolve()),
        })
        for key in ("APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
            Path(env[key]).mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [args.godot, "--headless", "--path", str(project), "--script", "res://unified_settings_acceptance.gd"],
            env=env,
            capture_output=True,
            text=True,
            timeout=90,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        log = result.stdout + result.stderr
        args.report.with_suffix(".log").write_text(log, encoding="utf-8")
        if result.returncode or "SCRIPT ERROR:" in log or not args.report.exists():
            raise SystemExit(log[-16000:])
        receipt = json.loads(args.report.read_text(encoding="utf-8"))
        if not receipt["ok"]:
            raise SystemExit(log[-16000:])
        print(json.dumps({"ok": True, "checks": len(receipt["checks"]), "report": str(args.report)}))


if __name__ == "__main__":
    main()
