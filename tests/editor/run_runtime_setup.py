"""Windows runtime bootstrap regression using an explicitly supplied existing runtime package."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from runtime_policy_fixture import copy_runtime_policy
from runtime_selector_fixture import native_selector

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
        shutil.copyfile(ROOT / "tools/configure_gonggong_runtime.ps1", root / "tools/configure_gonggong_runtime.ps1")
        shutil.copyfile(ROOT / "tools/run_gonggong_config_agent.ps1", root / "tools/run_gonggong_config_agent.ps1")
        shutil.copyfile(ROOT / "tools/check_gonggong_github.ps1", root / "tools/check_gonggong_github.ps1")
        shutil.copyfile(ROOT / "tools/install_gonggong_github_cli.ps1", root / "tools/install_gonggong_github_cli.ps1")
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
        doctor.write_text(
            'import json,os\nassert all(os.path.isfile(os.environ[k]) for k in ["GONGGONG_PYTHON","GONGGONG_NODE","GONGGONG_GIT"])\nprint(json.dumps({"ok":True}))\n'
        )
        copy_runtime_policy(ROOT, root)
        fake_codex, selector_marker = native_selector(
            root / "native-selector",
            {
                "python": args.source / "python/python.exe",
                "node": args.source / "node/node.exe",
                "git": args.source / "git/cmd/git.exe",
                "gh": sys.executable,
            },
        )
        agent_result = root / "agent-result.json"
        agent_env = dict(os.environ, GONGGONG_RUNTIME_SOURCE=str(args.source.resolve()), GONGGONG_GH=sys.executable)
        agent = subprocess.run(
            [
                str(shell),
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "RemoteSigned",
                "-File",
                str(root / "tools/run_gonggong_config_agent.ps1"),
                "-Workspace",
                str(root),
                "-Out",
                str(agent_result),
                "-Codex",
                str(fake_codex),
            ],
            env=agent_env,
            capture_output=True,
            timeout=180,
        )
        agent_value = json.loads(agent_result.read_text(encoding="utf-8-sig"))
        assert agent.returncode == 0 and agent_value["ok"], (agent.stderr.decode(errors="replace"), agent_value)
        assert agent_value["agent"]["independent_from_gonggong"] is False
        assert agent_value["agent"]["registered_framework_agent"] is False
        assert agent_value["agent"]["policy_hashes"]
        assert all(Path(agent_value[k]).is_file() for k in ["python", "node", "git", "gh"])
        assert agent_value["github"]["ok"] is False and agent_value["github"]["error"] == "gh_unauthenticated"
        cases += ["governed deterministic host selects and validates a complete runtime package"]
        assert not selector_marker.exists()
        assert agent_value["agent"]["provider_started"] is False
        foundation = root / "framework/FOUNDATION.md"
        original_policy = foundation.read_bytes()
        try:
            foundation.write_bytes(original_policy + b"\nchanged fixture policy")
            blocked = subprocess.run(agent.args, env=agent_env, capture_output=True, timeout=180)
            blocked_value = json.loads(agent_result.read_text(encoding="utf-8-sig"))
            assert blocked.returncode != 0 and not blocked_value["ok"]
            assert "Trusted host policy changed" in blocked_value["error"]
            assert blocked_value["agent"]["provider_started"] is False and not selector_marker.exists()
        finally:
            foundation.write_bytes(original_policy)
        cases += ["changed host policy blocks configuration before deployment"]
        core = root / "framework/upstream/yuanheng/core.md"
        moved_core = core.with_suffix(".fixture-backup")
        core.rename(moved_core)
        try:
            blocked = subprocess.run(agent.args, env=agent_env, capture_output=True, timeout=180)
            blocked_value = json.loads(agent_result.read_text(encoding="utf-8-sig"))
            assert blocked.returncode != 0 and not blocked_value["ok"]
            assert "Trusted host policy source is missing" in blocked_value["error"]
            assert blocked_value["agent"]["provider_started"] is False and not selector_marker.exists()
        finally:
            moved_core.rename(core)
        cases += ["missing host policy blocks configuration before deployment"]
        launcher = root / "tools/launch_gonggong_editor.ps1"
        shutil.copyfile(ROOT / "tools/launch_gonggong_editor.ps1", launcher)
        editor = root / "project/godot/bin/godot.windows.editor.x86_64.exe"
        editor.parent.mkdir(parents=True)
        editor.write_bytes(b"probe-only; never executed")
        shutil.copyfile(ROOT / "tools/installed_editor_workspace.ps1", root / "tools/installed_editor_workspace.ps1")
        console = editor.with_suffix(".console.exe")
        console.write_bytes(editor.read_bytes())
        (root / "samples/gonggong-workbench").mkdir(parents=True)
        inventory = {
            "default_editor": "bin/" + editor.name,
            "files": [
                {"path": "bin/" + path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                for path in (editor, console)
            ],
        }
        (editor.parents[1] / "installed.local.json").write_text(json.dumps(inventory))
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
