"""Windows-layout simulation: real PowerShell processes, host tools behind fixture PE launchers.

This does not install vendor runtimes or validate standalone packages, hardware,
all power-loss cutpoints, concurrent deployment, or interruption during rollback.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "d237ef78cc394a98db85b6eb1b39f0184217297d"
ENTRIES = {"python": "python/python.exe", "node": "node/node.exe", "git": "git/cmd/git.exe"}
LAUNCHER = r"""
using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading;
class FixtureLauncher {
    // Windows CRT argument quoting, including trailing backslashes and quotes.
    static string Quote(string value) {
        var result = new StringBuilder("\"");
        int slashes = 0;
        foreach (char c in value) {
            if (c == '\\') { slashes++; continue; }
            if (c == '"') { result.Append('\\', slashes * 2 + 1); result.Append(c); }
            else { result.Append('\\', slashes); result.Append(c); }
            slashes = 0;
        }
        result.Append('\\', slashes * 2); result.Append('"');
        return result.ToString();
    }
    static int Main(string[] args) {
        string marker = Environment.GetEnvironmentVariable("GONGGONG_SIMULATION_PAUSE");
        string here = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\', '/');
        if (NAME == "node" && marker != null && Path.GetFileName(here) == "node-staged") {
            File.WriteAllText(marker, "owned fixture node staged probe entered");
            Thread.Sleep(Timeout.Infinite);
        }
        var quoted = new StringBuilder();
        foreach (string arg in args) { if (quoted.Length > 0) quoted.Append(' '); quoted.Append(Quote(arg)); }
        var info = new ProcessStartInfo(TARGET, quoted.ToString());
        info.UseShellExecute = false;
        using (var child = Process.Start(info)) { child.WaitForExit(); return child.ExitCode; }
    }
}
"""


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run(command, *, env=None, timeout=240):
    return subprocess.run(command, env=env, capture_output=True, timeout=timeout, cwd=ROOT)


def clean_env():
    env = dict(os.environ)
    for name in list(env):
        if "KEY" in name.upper() or "TOKEN" in name.upper() or name.startswith("GONGGONG_"):
            env.pop(name)
    return env


def redact(text, paths):
    for index, path in enumerate(paths):
        value = str(path)
        text = text.replace(value, f"<fixture-path-{index}>")
        text = text.replace(value.replace("\\", "\\\\"), f"<fixture-path-{index}>")
    return text


def make_package(folder, tools):
    """Build executable Windows fixtures which delegate to preinstalled CI tools."""
    compiler = Path(os.environ["SystemRoot"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    if not compiler.is_file():
        compiler = Path(os.environ["SystemRoot"]) / "Microsoft.NET/Framework/v4.0.30319/csc.exe"
    assert compiler.is_file(), "Windows .NET Framework C# compiler required"
    records = []
    for name, relative in ENTRIES.items():
        binary = folder / relative
        binary.parent.mkdir(parents=True, exist_ok=True)
        source = folder.parent / f"fixture-{name}.cs"
        # JSON strings are also valid C# literals for these ordinary Windows paths.
        source.write_text(
            LAUNCHER.replace("NAME", json.dumps(name)).replace("TARGET", json.dumps(str(tools[name]))),
            encoding="utf-8",
        )
        result = run([str(compiler), "/nologo", "/target:exe", f"/out:{binary}", str(source)], timeout=60)
        assert result.returncode == 0, result.stdout.decode(errors="replace") + result.stderr.decode(errors="replace")
        assert binary.read_bytes()[:2] == b"MZ"
        records.append({"path": relative, "sha256": digest(binary)})
    (folder / "installed.local.json").write_text(
        json.dumps({"schema_version": 1, "path_base": "runtime_directory", "files": records}), encoding="utf-8"
    )
    return records


def ps_command(shell, script, root, result, *extra):
    return [
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
        *map(str, extra),
    ]


def interrupted_case(folder, shell, script, package, *, original, baseline=False):
    folder.mkdir()
    (folder / "CURRENT_FRAMEWORK.json").write_text("{}", encoding="utf-8")
    (folder / "tools").mkdir()
    (folder / "tools/gonggong_bridge.py").write_text("print('fixture doctor')\n", encoding="utf-8")
    runtime = folder / "project/runtime"
    original_bytes = b"original fixture runtime bytes; intentionally not executable\r\n"
    if original:
        (runtime / "python").mkdir(parents=True)
        (runtime / "python/python.exe").write_bytes(original_bytes)
        (runtime / "python/original.txt").write_bytes(original_bytes)
    marker = folder / "staged-node-entered"
    output = folder / "result.json"
    env = clean_env()
    env["GONGGONG_SIMULATION_PAUSE"] = str(marker)
    with (folder / "deploy.stdout.log").open("wb") as stdout, (folder / "deploy.stderr.log").open("wb") as stderr:
        process = subprocess.Popen(
            ps_command(shell, script, folder, output, "-SourceRuntime", package),
            env=env,
            stdout=stdout,
            stderr=stderr,
        )
        try:
            deadline = time.monotonic() + 60
            while not marker.exists():
                assert process.poll() is None, (folder / "deploy.stderr.log").read_text(errors="replace")
                assert time.monotonic() < deadline, "owned staged probe did not pause"
                time.sleep(0.05)
            receipts = list((runtime / ".gonggong-setup").glob("*/receipt.json"))
            assert len(receipts) == 1
            receipt = receipts[0]
            interrupted = read_json(receipt)
            assert interrupted["state"] == "deploying" and len(interrupted["changed"]) == 1, interrupted
            assert (runtime / "python/python.exe").read_bytes() == (package / "python/python.exe").read_bytes()
        finally:
            if process.poll() is None:
                # Only terminate the process tree created and owned by this case.
                killed = run(["taskkill.exe", "/PID", str(process.pid), "/T", "/F"], timeout=30)
                assert killed.returncode == 0, killed.stderr.decode(errors="replace")
            process.wait(timeout=30)
    command = ps_command(shell, script, folder, output, "-Rollback", receipt)
    rollback = run(command, env=clean_env(), timeout=60)
    value = read_json(output)
    assert value["global_environment_changed"] is False
    if baseline:
        assert rollback.returncode != 0 and value["ok"] is False
        assert "No matching active deployment" in value["error"], value
        assert read_json(receipt)["state"] == "deploying"
        assert (runtime / "python/python.exe").read_bytes() != original_bytes
    else:
        assert rollback.returncode == 0 and value["ok"] is True, value
        assert read_json(receipt)["state"] == "rolled_back"
        if original:
            assert (runtime / "python/python.exe").read_bytes() == original_bytes
            assert (runtime / "python/original.txt").read_bytes() == original_bytes
        else:
            assert not (runtime / "python").exists()
        retained = list(receipt.parent.glob("python-withdrawn-*"))
        assert len(retained) == 1
        assert (retained[0] / "python.exe").read_bytes() == (package / "python/python.exe").read_bytes()
        repeated = run(command, env=clean_env(), timeout=60)
        assert repeated.returncode != 0 and read_json(output)["ok"] is False
        assert "No matching active deployment" in read_json(output)["error"]
        assert read_json(receipt)["state"] == "rolled_back"
    return {
        "case": "baseline interrupted replacement"
        if baseline
        else "candidate interrupted replacement"
        if original
        else "candidate interrupted fresh install",
        "ok": True,
        "interruption": "owned PowerShell tree forcibly terminated at fixture staged-node probe after Python deployment",
        "receipt_at_interruption": interrupted,
        "deployment_exit_after_termination": process.returncode,
        "deployment_stdout": (folder / "deploy.stdout.log").read_text(errors="replace"),
        "deployment_stderr": (folder / "deploy.stderr.log").read_text(errors="replace"),
        "rollback_exit": rollback.returncode,
        "rollback_output": value,
        "rollback_stdout": rollback.stdout.decode(errors="replace"),
        "rollback_stderr": rollback.stderr.decode(errors="replace"),
        "original_bytes_restored": original and not baseline,
        "recovery_retained": not baseline,
        "repeated_rollback_rejected": not baseline,
    }


def journal_boundary_cases(folder, shell, script, package):
    """Explicit journal fixtures complement the real process-interruption cases."""
    cases = []
    for name in (
        "prepared-before-backup",
        "prepared-after-backup",
        "legacy-configured",
        "outside-target",
        "missing-backup",
    ):
        root = folder / name
        root.mkdir(parents=True)
        (root / "CURRENT_FRAMEWORK.json").write_text("{}", encoding="utf-8")
        transaction = root / "project/runtime/.gonggong-setup/fixture"
        transaction.mkdir(parents=True)
        target = root / "project/runtime/python"
        backup = transaction / "python-previous"
        original = b"unchanged original journal fixture"
        phase = "prepared"
        if name == "prepared-before-backup":
            target.mkdir()
            (target / "original.txt").write_bytes(original)
        elif name == "prepared-after-backup":
            backup.mkdir()
            (backup / "original.txt").write_bytes(original)
        elif name == "legacy-configured":
            target.mkdir()
            shutil.copyfile(package / "python/python.exe", target / "python.exe")
            backup.mkdir()
            (backup / "original.txt").write_bytes(original)
        elif name == "missing-backup":
            target.mkdir()
            (target / "original.txt").write_bytes(original)
            phase = "deployed"
        else:
            target = root / "outside-runtime"
            target.mkdir()
            (target / "original.txt").write_bytes(original)
            backup = None
        record = {"name": "python", "target": str(target), "backup": str(backup) if backup else ""}
        if name != "legacy-configured":
            record["phase"] = phase
        receipt = transaction / "receipt.json"
        receipt.write_text(
            json.dumps({
                "state": "configured" if name == "legacy-configured" else "deploying",
                "workspace": str(root),
                "changed": [record],
            }),
            encoding="utf-8",
        )
        output = root / "result.json"
        result = run(ps_command(shell, script, root, output, "-Rollback", receipt), env=clean_env(), timeout=60)
        value = read_json(output)
        assert (target / "original.txt").read_bytes() == original
        assert value["global_environment_changed"] is False
        if name in ("outside-target", "missing-backup"):
            assert result.returncode != 0 and value["ok"] is False
            assert read_json(receipt)["state"] == "deploying"
        else:
            assert result.returncode == 0 and value["ok"] is True, value
            assert read_json(receipt)["state"] == "rolled_back"
        cases.append({"case": name, "ok": True, "kind": "explicit journal fixture with real PowerShell rollback"})
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="Report directory")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("Windows-only: requires actual Windows PowerShell and fixture PE execution")
    assert args.godot.is_file(), "Built native Windows editor required"
    args.out.mkdir(parents=True, exist_ok=True)
    shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    tools = {
        "python": Path(sys.executable),
        "node": Path(shutil.which("node") or ""),
        "git": Path(shutil.which("git") or ""),
    }
    assert all(tool.is_file() for tool in tools.values()), "Preinstalled Python, Node, and Git required"
    report = {
        "ok": False,
        "scope": "Windows-layout simulation with actual PowerShell, host Python/Node/Git via compiled fixture PE launchers, native editor, loopback model and GitHub fixtures",
        "standalone_vendor_package_tested": False,
        "uncovered": [
            "all power-loss cutpoints",
            "concurrent deployment",
            "interruption during rollback",
            "real model/provider and GitHub publication",
            "hardware or Linux acceptance",
        ],
        "baseline_commit": BASELINE,
        "candidate_script_sha256": digest(ROOT / "tools/configure_gonggong_runtime.ps1"),
        "editor_sha256": digest(args.godot),
        "cases": [],
    }
    with tempfile.TemporaryDirectory(prefix="gonggong-windows-simulation-") as temporary:
        folder = Path(temporary)
        paths = [folder, ROOT, args.godot.resolve(), *tools.values(), Path.home(), Path(tempfile.gettempdir())]
        try:
            baseline_result = run(
                [str(tools["git"]), "show", f"{BASELINE}:tools/configure_gonggong_runtime.ps1"], timeout=30
            )
            assert baseline_result.returncode == 0, "Exact baseline git object required; fetch the recorded commit"
            baseline = folder / "baseline.ps1"
            baseline.write_bytes(baseline_result.stdout)
            report["baseline_script_sha256"] = digest(baseline)
            package = folder / "simulated-runtime"
            report["fixture_files"] = make_package(package, tools)
            versions = {}
            for name, tool in tools.items():
                version = run([str(tool), "--version"], env=clean_env(), timeout=30)
                assert version.returncode == 0
                versions[name] = (version.stdout + version.stderr).decode(errors="replace").strip()
            version = run([str(shell), "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"], timeout=30)
            assert version.returncode == 0
            versions["powershell"] = version.stdout.decode(errors="replace").strip()
            report["tool_versions"] = versions
            for name, script, original, old in [
                ("baseline", baseline, True, True),
                ("candidate-replacement-中文", ROOT / "tools/configure_gonggong_runtime.ps1", True, False),
                ("candidate-fresh", ROOT / "tools/configure_gonggong_runtime.ps1", False, False),
            ]:
                case = interrupted_case(folder / name, shell, script, package, original=original, baseline=old)
                report["cases"].append(case)
            report["journal_boundary_cases"] = journal_boundary_cases(
                folder / "journal-boundaries", shell, ROOT / "tools/configure_gonggong_runtime.ps1", package
            )
            for name, arguments, timeout in [
                ("runtime-setup", [str(ROOT / "tests/editor/run_runtime_setup.py"), "--source", str(package)], 600),
                (
                    "requirements-intake",
                    [
                        str(ROOT / "tests/editor/run_requirements_intake.py"),
                        "--godot",
                        str(args.godot.resolve()),
                        "--runtime-source",
                        str(package),
                    ],
                    600,
                ),
            ]:
                output = args.out / f"{name}.json"
                result = run(
                    [sys.executable, *arguments, "--out", str(output.resolve())], env=clean_env(), timeout=timeout
                )
                (args.out / f"{name}.process.log").write_text(
                    redact((result.stdout + result.stderr).decode(errors="replace"), paths), encoding="utf-8"
                )
                assert result.returncode == 0, f"{name} failed; see process log"
                value = read_json(output)
                assert value["ok"] is True
                if name == "runtime-setup":
                    assert len(value["cases"]) == 7
                else:
                    assert value["runtime_setup_and_resume"] is True
                report[name] = value
            report["ok"] = True
        except Exception as error:
            report["error"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            # Preserve actual case output even if an assertion interrupts the run.
            diagnostics = {
                str(path.relative_to(folder)): path.read_text(encoding="utf-8-sig", errors="replace")
                for pattern in ("*.log", "receipt.json", "result.json")
                for path in folder.rglob(pattern)
            }
            (args.out / "interruption-diagnostics.json").write_text(
                redact(json.dumps(diagnostics, ensure_ascii=False, indent=2), paths) + "\n", encoding="utf-8"
            )
            (args.out / "summary.json").write_text(
                redact(json.dumps(report, ensure_ascii=False, indent=2), paths) + "\n", encoding="utf-8"
            )
    print(json.dumps({"ok": report["ok"], "interruption_cases": len(report["cases"]), "scope": report["scope"]}))


if __name__ == "__main__":
    main()
