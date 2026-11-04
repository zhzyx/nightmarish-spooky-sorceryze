"""Windows runtime bootstrap regression using an explicitly supplied existing runtime package."""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    script = ROOT / "tools/configure_gonggong_runtime.ps1"
    cases = []
    with tempfile.TemporaryDirectory(prefix="gonggong-setup-test-") as folder:
        root = Path(folder)
        (root / "CURRENT_FRAMEWORK.json").write_text("{}")
        (root / "tools").mkdir()
        doctor = root / "tools/gonggong_bridge.py"
        doctor.write_text(
            'import json,os\nassert all(os.path.isfile(os.environ[k]) for k in ["GONGGONG_PYTHON","GONGGONG_NODE","GONGGONG_GIT"])\nprint(json.dumps({"ok":True}))\n'
        )
        result = root / "result.json"

        def run(*extra, success=True):
            proc = subprocess.run(
                [
                    str(shell),
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "RemoteSigned",
                    "-File",
                    str(script),
                    "-Workspace",
                    str(root),
                    "-Out",
                    str(result),
                    *extra,
                ],
                capture_output=True,
                timeout=180,
            )
            assert result.exists(), proc.stderr.decode(errors="replace")
            value = json.loads(result.read_text(encoding="utf-8-sig"))
            assert (proc.returncode == 0) == success, (proc.stderr.decode(errors="replace"), value)
            assert value["ok"] == success, value
            return value

        value = run("-SourceRuntime", str(args.source.resolve()))
        assert all(Path(value[k]).is_file() for k in ["python", "node", "git"])
        assert len(value["changed"]) == 3
        receipt = value["receipt"]
        reused = run()
        assert reused["changed"] == []
        assert Path(reused["receipt"]).is_file()
        run("-Rollback", reused["receipt"])
        assert all(Path(value[k]).is_file() for k in ["python", "node", "git"])
        cases += [
            "deploy all three components with no destination Python",
            "existing runtimes reused without replacement; configuration-only rollback retains runtimes",
        ]
        run("-Rollback", receipt)
        assert not any((root / "project/runtime" / name).exists() for name in ["python", "node", "git"])
        run("-Rollback", receipt, success=False)
        cases += ["rollback retains recovery files", "repeated rollback rejected"]
        doctor.write_text("raise SystemExit(1)\n")
        failure = run("-SourceRuntime", str(args.source.resolve()), success=False)
        assert failure["rollback"] == "restored"
        assert not any((root / "project/runtime" / name).exists() for name in ["python", "node", "git"])
        cases += ["failed framework self-check restores pre-deployment files"]
        bad = root / "bad-source"
        (bad / "python").mkdir(parents=True)
        (bad / "python/python.exe").write_bytes(b"not executable")
        (bad / "installed.local.json").write_text(
            json.dumps({
                "schema_version": 1,
                "path_base": "runtime_directory",
                "files": [{"path": "python/python.exe", "sha256": "0" * 64}],
            })
        )
        failure = run("-SourceRuntime", str(bad), success=False)
        assert "checksum mismatch" in failure["error"], failure
        cases += ["tampered source rejected before execution"]
        launcher = root / "tools/launch_gonggong_editor.ps1"
        shutil.copyfile(ROOT / "tools/launch_gonggong_editor.ps1", launcher)
        editor = root / "project/godot/bin/godot.windows.editor.x86_64.exe"
        editor.parent.mkdir(parents=True)
        editor.write_bytes(b"probe-only; never executed")
        probe = subprocess.run(
            [
                str(shell),
                "-NoProfile",
                "-ExecutionPolicy",
                "RemoteSigned",
                "-File",
                str(launcher),
                "-Python",
                str(root / "missing-python.exe"),
                "-Node",
                str(root / "missing-node.exe"),
                "-Probe",
            ],
            capture_output=True,
            timeout=30,
        )
        assert probe.returncode == 0, probe.stderr.decode(errors="replace")
        assert b"Python" in probe.stdout and b"Node.js" in probe.stdout, probe.stdout
        cases += ["launcher permits editor ignition without Python or Node"]

    args.out.write_text(
        json.dumps(
            {
                "ok": True,
                "cases": cases,
                "source": "explicit existing package; no downloads",
                "global_environment_modified": False,
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps({"ok": True, "cases": len(cases)}))


if __name__ == "__main__":
    main()
