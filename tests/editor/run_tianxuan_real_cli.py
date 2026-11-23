"""Explicitly opt in to one real Codex request through the compiled native model host.

This is not a default CI test. It retains the caller's existing CLI authentication
source without inspecting or copying credentials. EditorPaths, project, working
directory and host bridge files are private. No business service is required.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

from editor_test_isolation import copy_editor

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def probe_passed(report):
    """Every observed provider, isolation and execution boundary is required."""
    editor_sha256 = report.get("editor_sha256", "")
    return (
        report.get("native", {}).get("ok") is True
        and report.get("exit_code") == 0
        and all(
            report.get("observed", {}).get(name) is True
            for name in ("installed_codex_process_seen", "read_only_sandbox", "no_approval_or_shell_tools")
        )
        and report.get("home_preserved") is True
        and report.get("codex_home_preserved") is True
        and len(editor_sha256) == 64
        and report.get("private_editor_sha256") == editor_sha256
        and report.get("script_error_seen") is False
    )


def watch_cli(process, cli, observed, stop):
    """Read only this test's descendants; retain no raw command line or environment."""
    while not stop.wait(0.1):
        pending = [process.pid]
        seen = set()
        while pending:
            parent = pending.pop()
            if parent in seen:
                continue
            seen.add(parent)
            children = subprocess.run(["pgrep", "-P", str(parent)], capture_output=True, text=True)
            for line in children.stdout.splitlines():
                if line.isdigit():
                    pending.append(int(line))
            if parent == process.pid:
                continue
            command = subprocess.run(
                ["ps", "-p", str(parent), "-o", "args="], capture_output=True, text=True
            ).stdout.strip()
            if command.startswith(str(cli) + " exec "):
                observed["installed_codex_process_seen"] = True
                observed["read_only_sandbox"] = "--sandbox read-only" in command
                observed["no_approval_or_shell_tools"] = all(
                    value in command
                    for value in (
                        'approval_policy="never"',
                        "features.shell_tool=false",
                        "features.apply_patch_freeform=false",
                    )
                )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--codex", required=True, type=Path)
    parser.add_argument("--node", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--allow-real-provider", action="store_true")
    args = parser.parse_args()
    if not args.allow_real_provider:
        parser.error("This optional probe requires explicit --allow-real-provider authorization")
    if sys.platform != "darwin":
        parser.error("This real-provider probe currently verifies the macOS installed CLI")
    binary, cli, node = (path.resolve(strict=True) for path in (args.godot, args.codex, args.node))
    for executable in (binary, cli, node):
        if not executable.is_file() or not os.access(executable, os.X_OK):
            parser.error("Each input must be an existing executable")
    report = {
        "ok": False,
        "provider": "real installed Codex CLI; no model mock",
        "editor_sha256": digest(binary),
        "codex_sha256": digest(cli),
        "node_sha256": digest(node),
        "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "authentication": "Inherited existing HOME/CODEX_HOME/provider environment; no credentials read, copied or written by the probe",
        "isolation": "Private self-contained editor and private empty project; actual source bridge files copied byte-for-byte; no workspace marker or business account",
        "observed": {},
    }
    with tempfile.TemporaryDirectory(prefix="tianxuan-real-cli-") as temporary:
        private = Path(temporary).resolve()
        with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
            editor = copy_editor(binary, private / "engine")
        # Preserve a real source layout, not an empty SConstruct or invented origin receipt.
        source_files = [ROOT / "SConstruct"]
        for name in ("codex_cli", "codebuddy_cli"):
            source_files.extend(
                path
                for path in (ROOT / "tools" / name).rglob("*")
                if path.is_file() and not {"node_modules", "__pycache__"}.intersection(path.parts)
            )
        manifest = {}
        for source in source_files:
            relative = source.relative_to(ROOT)
            target = private / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            actual = digest(target)
            if actual != digest(source):
                raise RuntimeError("Host source copy changed during isolation")
            manifest[relative.as_posix()] = actual
        report["host_source_files_sha256"] = manifest
        report["private_editor_sha256"] = digest(editor)
        project = private / "project"
        project.mkdir()
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Real Tianxuan CLI probe"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
        )
        shutil.copy2(Path(__file__).with_name("tianxuan_real_cli.gd"), project / "probe.gd")
        output = private / "result.json"
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.upper().startswith(("GONGGONG_", "TIANXUAN_", "AINATIVE_", "GODOT_AI_"))
        }
        environment.update(
            GONGGONG_WORKSPACE="",
            TIANXUAN_API="http://127.0.0.1:1",
            TX_REAL_CLI_OPT_IN="explicit",
            TX_REAL_CLI_ROOT=str(private),
            TX_REAL_CLI_RESULT=str(output),
            TX_REAL_CLI_NODE=str(node),
            TX_REAL_CLI_CODEX=str(cli),
            TX_REAL_CLI_WORKFLOW_PYTHON=str(Path(sys.executable).resolve()),
        )
        # Provider identity and auth discovery remain exactly as supplied by this user.
        report["home_preserved"] = environment.get("HOME") == os.environ.get("HOME")
        report["codex_home_preserved"] = environment.get("CODEX_HOME") == os.environ.get("CODEX_HOME")
        command = [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"]
        process = subprocess.Popen(
            command, cwd=project, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stop = threading.Event()
        watcher = threading.Thread(target=watch_cli, args=(process, cli, report["observed"], stop), daemon=True)
        watcher.start()
        started = time.monotonic()
        try:
            stdout, stderr = process.communicate(timeout=210)
            report["exit_code"] = process.returncode
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate(timeout=15)
            report["error"] = "Isolated real-provider editor exceeded the 210 second process deadline"
        finally:
            stop.set()
            watcher.join(timeout=10)
        report["elapsed_seconds"] = round(time.monotonic() - started, 2)
        if output.is_file():
            report["native"] = json.loads(output.read_text())
        else:
            report["error"] = "The private editor did not produce a native provider result"
        # Raw provider output/environment are intentionally not included in the public evidence.
        report["editor_output_sha256"] = hashlib.sha256(stdout + stderr).hexdigest()
        report["script_error_seen"] = b"SCRIPT ERROR:" in stderr
        report["ok"] = probe_passed(report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "report": str(args.out),
                "editor_sha256": report["editor_sha256"],
                "native": report.get("native", {}),
                "error": report.get("error", ""),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
