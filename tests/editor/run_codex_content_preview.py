"""Real, isolated editor check for Issue 652. Only invoke after the new binary is ready."""

import argparse
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(args):
    root = args.worktree.resolve()
    editor = root / "bin/godot.windows.editor.x86_64.console.exe"
    engine = root / "bin/godot.windows.editor.x86_64.exe"
    assert editor.is_file() and engine.is_file()
    run_dir = Path(tempfile.mkdtemp(prefix="gg652-proof-"))
    report = {
        "issue": 652,
        "engine_sha256": sha(engine),
        "utc": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
    }
    print("Live evidence:", run_dir, flush=True)
    try:
        with tempfile.TemporaryDirectory(prefix="gg652-live-", ignore_cleanup_errors=True) as tmp:
            project = Path(tmp)
            (project / "project.godot").write_text(
                '[application]\nconfig/name="Issue 652 isolated read batch"\n', encoding="utf-8"
            )
            shutil.copyfile(HERE / "codex_content_preview.gd", project / "gate.gd")
            src = project / "sources"
            src.mkdir()
            paths = [src / f"source_{n}_{secrets.token_hex(3)}.gd" for n in range(1, 10)]
            values = [secrets.token_hex(12) for _ in paths]
            for path, value in zip(paths, values):
                path.write_text(f'extends RefCounted\nconst VALUE := "{value}"\n', encoding="utf-8")
            before = {p.name: sha(p) for p in paths}
            report["source_sha256"] = before
            env = dict(os.environ)
            env.setdefault("GH_CONFIG_DIR", str(Path(env["APPDATA"]) / "GitHub CLI"))
            for key in ["APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME"]:
                isolated = project / key
                isolated.mkdir()
                env[key] = str(isolated)
            env.update(
                TS_WORKSPACE=str(root),
                TS_MODEL=args.model,
                TS_PYTHON=str(args.python.resolve()),
                TS_CODEX=shutil.which("codex.exe") or "",
                TS_NODE=shutil.which("node") or "",
                TS_BRIDGE=str(root / "tools/codebuddy_cli/godot_bridge.js"),
                TS_PROOF=json.dumps({"paths": [p.as_posix() for p in paths], "values_list": values}),
            )
            assert env["TS_CODEX"] and env["TS_NODE"] and args.python.is_file()
            env["GONGGONG_RUNTIME_CONFIG"] = str(project / "runtime.json")
            stderr_log = run_dir / "editor.log"
            with stderr_log.open("wb") as log:
                result = subprocess.run(
                    [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://gate.gd"],
                    cwd=root,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=1350,
                )
            report["returncode"] = result.returncode
            text = stderr_log.read_text(encoding="utf-8", errors="replace")
            report["rounds"] = [
                json.loads(line.partition("READBATCH_ROUND ")[2])
                for line in text.splitlines()
                if line.startswith("READBATCH_ROUND ")
            ]
            assert (
                result.returncode == 0
                and "PREVIEW_VISIBLE " in text
                and "PREVIEW_FINAL " in text
                and "PREVIEW_CANCEL_FOLLOWUP_OK" in text
            ), "see isolated editor log"
            assert before == {p.name: sha(p) for p in paths}, "source mutation"
            report["preview"] = [
                line
                for line in text.splitlines()
                if line.startswith(("PREVIEW_VISIBLE ", "PREVIEW_FINAL ", "PREVIEW_CANCEL_"))
            ]
            report["status"] = "passed"
    finally:
        (run_dir / "receipt.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree", type=Path, default=Path("D:/GongGong-work/tianshu-safe-preview"))
    parser.add_argument("--python", type=Path, default=Path("D:/GongGong/project/runtime/python/python.exe"))
    parser.add_argument("--model", default="gpt-6.1-sol")
    run(parser.parse_args())
