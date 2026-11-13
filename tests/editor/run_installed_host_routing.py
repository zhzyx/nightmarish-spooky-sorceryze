"""Exercise the editor's embedded routing methods with private, controlled helpers."""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

from editor_test_isolation import copy_editor

ROOT = Path(__file__).resolve().parents[2]
HOST = Path("customizations/components/godot-host/daqian")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "request_id": "installed-host-command-routing-20261113",
        "issue_number": 1017,
        "editor_sha256": digest(args.godot),
        "platform": platform.system(),
        "source_sha256": digest(ROOT / "editor/docks/daqian/workspace.gd"),
        "test_sha256": {p.name: digest(p) for p in [Path(__file__), ROOT / "tests/editor/installed_host_routing.gd"]},
    }
    base = Path(tempfile.mkdtemp(prefix="installed-host-routing-"))
    cleanup_verified = False
    try:
        editor = copy_editor(args.godot, base / "editor")
        (base / "project.godot").write_text('[application]\nconfig/name="Private installed host routing"\n')
        shutil.copyfile(ROOT / "tests/editor/installed_host_routing.gd", base / "test.gd")
        shutil.copyfile(ROOT / "editor/docks/daqian/workspace.gd", base / "expected-workspace.txt")
        (base / "fixture.json").write_text(
            json.dumps({"node": str(args.node.resolve()), "workflow_python": str(args.python.resolve())})
        )
        for label in ["installed-host", "project-data"]:
            entry = base / label / HOST
            entry.mkdir(parents=True)
            # Distinguishable implementations, with actual Python transport and request files.
            (entry / "graph_host.py").write_text(
                "import json,sys\nfrom pathlib import Path\na=sys.argv[1:]\n"
                "def value(k): return a[a.index(k)+1]\n"
                'request=json.loads(Path(value("--request")).read_text()) if "--request" in a else {}\n'
                f'result={{"implementation":{label!r},"args":a,"request":request}}\n'
                'Path(value("--result")).write_text(json.dumps(result))\n'
            )
        installed = base / "installed-host"
        for relative in [
            HOST / name
            for name in ["watch_progress.mjs", "debug_session.mjs", "execution.mjs", "worker.py", "model_api.py"]
        ] + [
            Path("customizations/platforms/process-management/yuanheng-local/sinan/dispatch.mjs"),
            Path("customizations/platforms/ai-access/daqian/http_protocols.py"),
        ]:
            target = installed / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        for name in ["watch_progress.mjs", "debug_session.mjs"]:
            (base / "project-data" / HOST / name).write_text(
                'process.stdout.write("PROJECT_HELPER_EXECUTED\\n"); process.stdin.resume();\n'
            )
        receipt_dir = base / "receipts" / "daqian-direct" / ("daqian-direct-" + "a" * 20)
        receipt_dir.mkdir(parents=True)
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith("GONGGONG_") and k not in {"OPENAI_API_KEY", "GODOT_AI_API_KEY"}
        }
        for key in ["HOME", "APPDATA", "LOCALAPPDATA", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME"]:
            (base / key).mkdir()
            env[key] = str(base / key)
        try:
            run = subprocess.run(
                [str(editor), "--headless", "--editor", "--path", str(base), "--script", "res://test.gd"],
                env=env,
                capture_output=True,
                text=True,
                timeout=90,
            )
            report.update(exit_code=run.returncode, stdout=run.stdout, stderr=run.stderr)
        except subprocess.TimeoutExpired as error:
            report.update(
                ok=False,
                error="editor_timeout",
                stdout=(error.stdout or b"").decode("utf-8", errors="replace"),
                stderr=(error.stderr or b"").decode("utf-8", errors="replace"),
                cleanup="Editor terminated by subprocess; detached helpers unverified. Private fixture retained for recovery.",
            )
            return 1
        result = base / "result.json"
        if result.exists():
            report["observed"] = json.loads(result.read_text())
            # Completion assertions cover the debug worker's terminal event;
            # the GDScript receipt separately verifies its direct helper PIDs.
            cleanup_verified = report["observed"].get("ok", False) and report["observed"].get(
                "helper_processes_quiet", False
            )
        report["ok"] = run.returncode == 0 and cleanup_verified
    finally:
        if cleanup_verified:
            shutil.rmtree(base)
        else:
            report["private_fixture_retained"] = str(base)
        report["private_fixture_removed"] = not base.exists()
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
