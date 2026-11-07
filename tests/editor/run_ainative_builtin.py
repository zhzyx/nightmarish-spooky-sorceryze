"""Exercise the native AINative editor in addon-free, isolated test projects."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from editor_test_isolation import copy_editor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--capture", nargs="?", const="auto", help="Optional real-renderer screenshot path (default: report.png)"
    )
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        parser.error("Python 3.11+ is required for the deployed AINative tools")
    binary = args.godot.resolve(strict=True)
    repository = Path(__file__).resolve().parents[2]
    script = Path(__file__).with_name("ainative_builtin.gd").resolve()
    capture = (
        None
        if args.capture is None
        else args.report.with_suffix(".png")
        if args.capture == "auto"
        else Path(args.capture)
    )
    if capture is not None:
        capture = capture.resolve()
        capture.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "state": "failed",
        "editor_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "scope": "Native AINative editor entry, bundled host, Mesh Copy preview/publication, synthetic rigging, isolated project state and relocated runtime scripts; no AI inference",
        "runs": [],
    }
    with tempfile.TemporaryDirectory(prefix="ainative-native-", ignore_cleanup_errors=os.name == "nt") as temporary:
        base = Path(temporary).resolve()
        engine = base / "engine"
        isolated_binary = copy_editor(binary, engine)
        projects = [base / "project-a", base / "project-b"]
        definition = 'config_version=5\n[application]\nconfig/name="AINative Native Acceptance"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
        for project in projects:
            project.mkdir()
            (project / "project.godot").write_text(definition, encoding="utf-8")
            for extension in ["png", "glb"]:
                shutil.copy2(
                    repository / "samples/ainative-workbench/fixtures" / ("sample." + extension),
                    project / ("fixture." + extension),
                )
        transfer = base / "portable-transfer"
        environment = os.environ.copy()
        environment["AINATIVE_PYTHON"] = sys.executable
        environment["AINATIVE_TEST_TRANSFER"] = str(transfer)
        # Provider selection is explicitly offline for this test, regardless of the user's environment.
        environment["AINATIVE_PROVIDER_FACTORY"] = "editor_demo:factory"

        def run(name, project, mode, editor=True, screenshot=None):
            receipt = base / (name + ".json")
            env = dict(environment, AINATIVE_TEST_MODE=mode, AINATIVE_TEST_RECEIPT=str(receipt))
            env.pop("AINATIVE_TEST_CAPTURE", None)
            command = [str(isolated_binary)]
            if screenshot is None:
                command += ["--headless"]
            else:
                # Render only this isolated test window; never drive the desktop.
                command += ["--position", "-20000,-20000", "--resolution", "1440x1000"]
                env["AINATIVE_TEST_CAPTURE"] = str(screenshot)
            if editor:
                command.append("--editor")
            command += ["--path", str(project), "--script", str(script)]
            try:
                process = subprocess.run(
                    command, env=env, capture_output=True, text=True, timeout=180, errors="replace"
                )
                log = process.stdout + process.stderr
                try:
                    value = json.loads(receipt.read_text(encoding="utf-8")) if receipt.is_file() else {}
                    if not isinstance(value, dict):
                        value = {}
                except (OSError, ValueError):
                    value = {}
                passed = process.returncode == 0 and value.get("ok") is True and "AINATIVE_BUILTIN_OK" in log
                # A script error can abort a helper while the main acceptance still reaches its end.
                passed = passed and "SCRIPT ERROR:" not in log
                entry = {"name": name, "passed": passed, "returncode": process.returncode, "receipt": value}
                if not passed:
                    entry["log_tail"] = log[-18000:]
                result["runs"].append(entry)
                if log:
                    print(log, end="" if log.endswith("\n") else "\n")
                return passed, value
            except subprocess.TimeoutExpired as error:
                pieces = [error.stdout or "", error.stderr or ""]
                log = "".join(
                    piece.decode("utf-8", errors="replace") if isinstance(piece, bytes) else piece for piece in pieces
                )
                result["runs"].append({"name": name, "passed": False, "error": "timeout", "log_tail": log[-18000:]})
                print(log)
                return False, {}

        first_ok, first = run("mesh-and-rig", projects[0], "full", screenshot=capture)
        second_ok, second = run("independent-project", projects[1], "entry") if first_ok else (False, {})
        if first_ok and second_ok:
            isolated = first["details"]["state_key"] != second["details"]["state_key"]
            result["project_state_isolated"] = isolated
            result["same_engine_bundle"] = first["details"]["host_sha256"] == second["details"]["host_sha256"]
            sample = base / "sample-addon-compatibility"
            sample.mkdir()
            (sample / "project.godot").write_text(
                definition + '[editor_plugins]\nenabled=PackedStringArray("res://addons/ainative/plugin.cfg")\n',
                encoding="utf-8",
            )
            shutil.copytree(repository / "samples/ainative-workbench/addons", sample / "addons")
            sample_ok, _ = run("sample-addon-compatibility", sample, "sample")
            shutil.copytree(transfer, projects[1] / "portable")
            # A runtime launch must not silently find scripts left in the editor's deployment.
            bundles = engine / "editor_data/ainative/bundles"
            if bundles.is_dir():
                bundles.rename(bundles.with_name("bundles-hidden-during-runtime-test"))
            runtime_ok, _ = run("relocated-runtime", projects[1], "runtime", editor=False)
            intact = all(
                (project / "project.godot").read_text(encoding="utf-8") == definition
                and not (project / "addons").exists()
                for project in projects
            )
            result["project_sources_unchanged"] = intact
            result["state"] = (
                "passed"
                if isolated and runtime_ok and sample_ok and intact and result["same_engine_bundle"]
                else "failed"
            )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"state": result["state"], "report": str(args.report)}, ensure_ascii=False))
    return 0 if result["state"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
