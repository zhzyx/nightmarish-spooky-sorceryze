"""Run three real Blender acceptance cases against a local API fixture.

The parent owns a Windows Job containing the worker and all its descendants.
Only fixture data is used; outbound firewall policy belongs to the CI workflow.
Output is audit evidence, including private temporary paths in diagnostic logs.
"""

import argparse
import hashlib
import json
import os
import platform
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = "4.5.11"
TIMEOUT = 900
TEST_NAMES = (
    "test_synthetic_api_real_rounded_loft_cups_reaches_strict_receipt_gate",
    "test_synthetic_api_real_blender_organic_mesh_receipt_and_recovery",
    "test_synthetic_api_real_character_retains_original_and_expanded_receipts",
)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_evidence():
    revision = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True, timeout=15
    ).stdout.strip()
    paths = sorted((ROOT / "tools/ainative").glob("*.py"))
    paths += [ROOT / "tools/editor_provenance_process.py", Path(__file__).resolve()]
    return dict(revision=revision, sha256={path.relative_to(ROOT).as_posix(): digest(path) for path in paths})


def preflight(blender):
    if sys.platform != "win32" or os.name != "nt" or platform.machine().lower() not in ("amd64", "x86_64"):
        raise RuntimeError("Real Windows x64 is required; this acceptance cannot be skipped")
    if not blender.is_absolute() or not blender.is_file() or blender.suffix.lower() != ".exe":
        raise RuntimeError("--blender must name an existing absolute Blender .exe")


def isolated_environment(directory, blender):
    # A whitelist avoids inheriting API tokens, host auth locations, Python hooks,
    # proxy settings, desktop tool channels, or a real model CLI on PATH.
    windows = os.environ.get("WINDIR", "C:/Windows")
    env = {
        "WINDIR": windows,
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", windows),
        "PATH": os.pathsep.join((str(Path(sys.executable).parent), str(Path(windows) / "System32"), windows)),
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "AINATIVE_TEST_BLENDER": str(blender),
    }
    for name, relative in {
        "HOME": "home",
        "USERPROFILE": "home",
        "APPDATA": "home/AppData/Roaming",
        "LOCALAPPDATA": "home/AppData/Local",
        "TEMP": "temp",
        "TMP": "temp",
        "TMPDIR": "temp",
        "BLENDER_USER_CONFIG": "blender/config",
        "BLENDER_USER_SCRIPTS": "blender/scripts",
        "BLENDER_USER_DATAFILES": "blender/datafiles",
    }.items():
        path = directory / relative
        path.mkdir(parents=True, exist_ok=True)
        env[name] = str(path)
    return env


def copy_evidence(source, destination):
    """Preserve fixture data and diagnostics, never a host profile or auth file."""
    if not source.is_dir():
        return
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise RuntimeError("Unexpected symlink in isolated fixture evidence")
        if not path.is_file():
            continue
        if path.suffix.lower() not in (
            ".json",
            ".glb",
            ".log",
            ".stdout",
            ".stderr",
            ".py",
            ".cs",
            ".png",
        ) and path.name not in ("args", "prompt", "runs", "started", "mode"):
            continue
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


class AcceptanceResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.names = []

    def startTest(self, test):
        self.names.append(test._testMethodName)
        super().startTest(test)

    def _exc_info_to_string(self, err, test):
        detail = super()._exc_info_to_string(err, test)
        # Include captured subprocess diagnostics when present.
        for name in ("stdout", "stderr"):
            value = getattr(err[1], name, None)
            if value:
                detail += (
                    "\n"
                    + name
                    + ":\n"
                    + (value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value)
                )
        return detail


def summarize(result):
    return dict(
        tests_run=result.testsRun,
        names=result.names,
        failures=[dict(test=str(test), traceback=detail) for test, detail in result.failures],
        errors=[dict(test=str(test), traceback=detail) for test, detail in result.errors],
        skipped=[dict(test=str(test), reason=reason) for test, reason in result.skipped],
        expected_failures=[str(test) for test, _ in result.expectedFailures],
        unexpected_successes=[str(test) for test in result.unexpectedSuccesses],
    )


def accepted(summary):
    return (
        summary.get("tests_run") == 3
        and summary.get("names") == list(TEST_NAMES)
        and all(
            summary.get(name) == []
            for name in ("failures", "errors", "skipped", "expected_failures", "unexpected_successes")
        )
    )


def worker(blender, output):
    report = dict(success=False, diagnostics=[])
    try:
        preflight(blender)
        report["runtime"] = dict(executable_sha256=digest(blender))
        # The parent Job also owns this version probe, including timeout cleanup.
        version = subprocess.run([str(blender), "--version"], capture_output=True, timeout=30, check=False)
        (output / "blender-version.stdout").write_bytes(version.stdout)
        (output / "blender-version.stderr").write_bytes(version.stderr)
        text = version.stdout.decode("utf-8", errors="replace")
        report["runtime"].update(version=text, version_returncode=version.returncode)
        if version.returncode != 0 or text.splitlines()[:1] != ["Blender " + VERSION + " LTS"]:
            raise RuntimeError("Expected the pinned official Blender " + VERSION + " runtime")
        sys.path.insert(0, str(ROOT / "tools/ainative"))
        import test_sculpt_provider as original

        class CapturingTests(original.SculptTests):
            def tearDown(self):
                try:
                    destination = output / "tests" / self._testMethodName
                    copy_evidence(self.directory, destination)
                    destination.mkdir(parents=True, exist_ok=True)
                    write_json(destination / "fixture.json", dict(planner="loopback_chat_completions"))
                    record = self.provider.read(original.KEY)
                    write_json(destination / "job-record.json", record)
                    if record.get("terminal", {}).get("state") == "succeeded":
                        manifest = self.provider.result_manifest(original.KEY)
                        original.check_content(manifest)
                        if str(self.directory) in json.dumps(manifest):
                            raise RuntimeError("Private fixture path in public manifest")
                        write_json(destination / "public-manifest.json", manifest)
                finally:
                    super().tearDown()

        suite = unittest.TestSuite(CapturingTests(name) for name in TEST_NAMES)
        with (output / "unittest.log").open("w", encoding="utf-8") as log:
            result = unittest.TextTestRunner(stream=log, verbosity=2, resultclass=AcceptanceResult).run(suite)
        report["tests"] = summarize(result)
        report["success"] = accepted(report["tests"])
    except BaseException as error:
        report["diagnostics"].append(traceback.format_exc())
        for name in ("stdout", "stderr"):
            value = getattr(error, name, None)
            if value:
                (output / ("failure." + name)).write_bytes(value if isinstance(value, bytes) else value.encode("utf-8"))
    finally:
        write_json(output / "worker-result.json", report)
    return 0 if report["success"] else 1


def run_owned_worker(blender, output, environment, report):
    sys.path.insert(0, str(ROOT / "tools"))
    from editor_provenance_process import WindowsJob

    job = WindowsJob(secrets.token_hex(16))
    child = None
    try:
        with (output / "worker.stdout").open("wb") as stdout, (output / "worker.stderr").open("wb") as stderr:
            child = job.spawn(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    str(Path(__file__).resolve()),
                    "--worker",
                    "--blender",
                    str(blender),
                    "--output",
                    str(output),
                ],
                cwd=str(ROOT),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                env=environment,
            )
            report["worker_returncode"] = child.wait(timeout=TIMEOUT)
    finally:
        try:
            forced = job.quiesce()
            report["cleanup"]["forced_process_termination"] = forced
            if forced:
                report["diagnostics"].append("Worker descendants remained active and required termination")
            if child is not None:
                child.wait(timeout=5)
            report["cleanup"]["processes_quiet"] = True
        finally:
            job.close()


def remove_temporary(directory):
    deadline = time.monotonic() + 10
    while True:
        try:
            shutil.rmtree(directory)
            return
        except OSError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.1)


def run(blender, output):
    report = dict(
        schema_version=1,
        success=False,
        platform=sys.platform,
        machine=platform.machine(),
        python=sys.version,
        expected_tests=list(TEST_NAMES),
        expected_blender_version=VERSION,
        diagnostics=[],
        cleanup=dict(processes_quiet=True, temporary_removed=True),
        scope="Fixed loopback API plans and real Blender geometry; no real model quality claim",
    )
    temporary = None
    try:
        if not output.is_absolute():
            raise RuntimeError("--output must be an absolute evidence directory")
        output.mkdir(parents=True, exist_ok=True)
        bootstrap = {"runtime-download.json", "execution-scope.json", "runner.log"}
        if any(path.name not in bootstrap for path in output.iterdir()):
            raise RuntimeError("--output contains stale acceptance evidence; only CI bootstrap files may preexist")
        report["source"] = source_evidence()
        preflight(blender)
        temporary = Path(tempfile.mkdtemp(prefix="blender-geometry-"))
        report["cleanup"] = dict(processes_quiet=False, temporary_removed=False)
        environment = isolated_environment(temporary, blender)
        run_owned_worker(blender, output, environment, report)
        result = json.loads((output / "worker-result.json").read_text(encoding="utf-8"))
        report["worker"] = result
        if report["worker_returncode"] != 0 or not result.get("success") or not accepted(result.get("tests", {})):
            raise RuntimeError("Three geometry tests must execute with zero failures, errors, or skips")
        if report["source"] != source_evidence():
            raise RuntimeError("Source inputs changed during acceptance")
        report["success"] = not report["diagnostics"]
    except BaseException:
        report["diagnostics"].append(traceback.format_exc())
    finally:
        if temporary is not None:
            try:
                if not report["success"]:
                    copy_evidence(temporary, output / "interrupted-fixtures")
            except BaseException:
                report["diagnostics"].append(traceback.format_exc())
            try:
                remove_temporary(temporary)
                report["cleanup"]["temporary_removed"] = True
            except BaseException:
                report["diagnostics"].append(traceback.format_exc())
                report["cleanup"]["retained_temporary_directory"] = str(temporary)
        report["success"] = bool(
            report["success"]
            and not report["diagnostics"]
            and all(report["cleanup"].get(key) is True for key in ("processes_quiet", "temporary_removed"))
        )
        try:
            output.mkdir(parents=True, exist_ok=True)
            report["artifacts"] = [
                dict(path=path.relative_to(output).as_posix(), bytes=path.stat().st_size, sha256=digest(path))
                for path in sorted(output.rglob("*"))
                if path.is_file() and path not in (output / "result.json", output / "runner.log")
            ]
            # The outer shell keeps this stream open beyond our final print.
            report["externally_finalized_artifacts"] = ["runner.log"] if (output / "runner.log").exists() else []
            write_json(output / "result.json", report)
        except BaseException:
            report["success"] = False
            traceback.print_exc()
    print(json.dumps(dict(success=report["success"], result=str(output / "result.json"))))
    return 0 if report["success"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    return worker(args.blender, args.output) if args.worker else run(args.blender, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
