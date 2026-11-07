"""Private signed-App origin fixture and separate same-byte resume checks.

This is an offline locator fixture, not evidence that its tiny source tree built
the supplied engine. Final delivery still binds the frozen production sources.
No GUI, production binding, user settings, or installed user App is touched.
"""

import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import nullcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
native = importlib.import_module("editor_native_app")
worker = importlib.import_module("editor_self_build")
manifests = importlib.import_module("editor_source_manifest")

PROBE = r"""@tool
extends SceneTree
func _initialize():
    run.call_deferred()
func run():
    await create_timer(0.4).timeout
    var dock = root.find_child("AI Chat", true, false)
    var runtime: Dictionary = dock.call("get_runtime_configuration") if dock != null else {}
    var origin: Dictionary = runtime.get("engine_origin", {})
    var paths = EditorInterface.get_editor_paths()
    var expected_error := OS.get_environment("ORIGIN_EXPECTED_ERROR")
    var ok = origin.get("managed", false)
    if expected_error.is_empty():
        ok = ok and origin.get("ok", false)
        ok = ok and origin.get("source_root") == OS.get_environment("ORIGIN_SOURCE")
        ok = ok and origin.get("project_root") == OS.get_environment("ORIGIN_PROJECT")
    else:
        ok = ok and not origin.get("ok", false) and origin.get("error", "") == expected_error
        ok = ok and not origin.has("source_root") and not origin.has("project_root")
    ok = ok and paths.is_self_contained() and paths.get_config_dir() == OS.get_environment("ORIGIN_SETTINGS")
    FileAccess.open(OS.get_environment("ORIGIN_RESULT"), FileAccess.WRITE).store_string(JSON.stringify({
        "ok":ok, "origin":origin, "self_contained":paths.is_self_contained(),
        "config_dir":paths.get_config_dir(), "runtime_config":runtime.get("config_path", "")
    }))
    quit(0 if ok else 2)
"""


def git(root, *arguments):
    return subprocess.check_output(["git", "-C", str(root), *arguments], stderr=subprocess.STDOUT).decode().strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--keep-fixture", action="store_true", help="Keep only this system temporary diagnostic fixture"
    )
    parser.add_argument(
        "--origin-only", action="store_true", help="Run signed-bundle checks without repeating resume checks"
    )
    args = parser.parse_args()
    report = {"ok": False, "offline_origin_fixture": True, "zero_argument_launch_tested": False}
    try:
        lifetime = (
            nullcontext(tempfile.mkdtemp(prefix="private_sc_native_acceptance_"))
            if args.keep_fixture
            else tempfile.TemporaryDirectory(prefix="private_sc_native_acceptance_")
        )
        with lifetime as temporary:
            folder = Path(temporary).resolve()
            if args.keep_fixture:
                report["fixture_root"] = str(folder)
            source = folder / "source"
            source.mkdir()
            git(source, "init", "-b", "main")
            git(source, "config", "user.name", "Offline native fixture")
            git(source, "config", "user.email", "fixture@example.invalid")
            (source / "SConstruct").write_text("# Offline origin source identity fixture\n")
            git(source, "add", "SConstruct")
            git(source, "commit", "-m", "fixture")
            (source / "bin").mkdir()
            project = folder / "project"
            project.mkdir()
            (project / "project.godot").write_text(
                'config_version=5\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
            )
            (project / "probe.gd").write_text(PROBE)
            binding_path = source / ".git/gonggong-engine-candidates/offline-fixture.json"
            binding_path.parent.mkdir()
            binding = dict(
                state="prepared",
                source_root=str(source),
                common_dir=str(source / ".git"),
                repository="offline/fixture",
                issue=1,
                request_id="offline-native-fixture",
                owner="offline",
                branch="main",
                base_sha=git(source, "rev-parse", "HEAD"),
                initial_launch_executable=str(folder / "uninstalled-original"),
                binding_path=str(binding_path),
            )
            app = source / "bin/godot.self_update_a.app"
            before = manifests.source_snapshot(source)
            native.package_app(source, args.godot, binding, project, app, ROOT / "misc/dist/macos_tools.app")
            manifest_file = manifests.artifact_manifest(
                source,
                app / native.EXECUTABLE_RELATIVE,
                binding,
                project,
                {"extra_suffix": "self_update_a"},
                before,
                app,
            )
            binding_path.write_text(json.dumps(dict(binding, artifact_manifest=manifest_file)))
            manifest = json.loads(Path(manifest_file).read_text())
            report["signed_artifact_sha256"] = manifest["artifact_sha256"]
            installed = folder / "installed"
            installed.mkdir()
            installed_app = installed / app.name
            native.copy_app(app, installed_app)
            (installed / "_sc_").touch()
            native.verify_bundle(
                installed_app, native.read_locator(app / native.EXECUTABLE_RELATIVE), manifest["artifact_sha256"]
            )
            env = {key: value for key, value in os.environ.items() if not key.startswith("GONGGONG_")}
            env.update(
                ORIGIN_SOURCE=str(source),
                ORIGIN_PROJECT=str(project),
                ORIGIN_SETTINGS=str(installed / "editor_data"),
                ORIGIN_RESULT=str(folder / "origin-result.json"),
            )
            completed = subprocess.run(
                [
                    str(installed_app / native.EXECUTABLE_RELATIVE),
                    "--headless",
                    "--editor",
                    "--path",
                    str(project),
                    "--script",
                    "res://probe.gd",
                ],
                cwd=folder,
                env=env,
                capture_output=True,
                text=True,
                timeout=180,
            )
            report["bundle_stdout"] = completed.stdout[-3000:]
            report["bundle_stderr"] = completed.stderr[-3000:]
            origin = json.loads((folder / "origin-result.json").read_text())
            report["bundle_origin"] = origin
            bundle_ok = completed.returncode == 0 and origin["ok"]
            if not bundle_ok:
                report["error"] = "complete_signed_bundle_origin_failed"
            native.verify_signature(installed_app)
            report["bundle_signature_after_start"] = True
            if bundle_ok:
                report["bundle_rejections"] = []
                for target, data, expected_error in (
                    (source / "SConstruct", b"# changed after build\n", "engine_origin_source_changed"),
                    (
                        Path(manifest_file),
                        json.dumps(dict(manifest, artifact_sha256="0" * 64)).encode(),
                        "engine_origin_artifact_changed",
                    ),
                ):
                    original = target.read_bytes()
                    try:
                        target.write_bytes(data)
                        env["ORIGIN_EXPECTED_ERROR"] = expected_error
                        Path(env["ORIGIN_RESULT"]).unlink()
                        rejected = subprocess.run(
                            [
                                str(installed_app / native.EXECUTABLE_RELATIVE),
                                "--headless",
                                "--editor",
                                "--path",
                                str(project),
                                "--script",
                                "res://probe.gd",
                            ],
                            cwd=folder,
                            env=env,
                            capture_output=True,
                            text=True,
                            timeout=180,
                        )
                        observed = json.loads(Path(env["ORIGIN_RESULT"]).read_text())
                        if rejected.returncode or not observed["ok"]:
                            raise ValueError(
                                "native_origin_refusal_failed: " + expected_error + " " + json.dumps(observed)
                            )
                        report["bundle_rejections"].append(expected_error)
                    finally:
                        target.write_bytes(original)
                        env.pop("ORIGIN_EXPECTED_ERROR", None)
            if not args.origin_only:
                private = worker.private_check_editor(app / native.EXECUTABLE_RELATIVE, folder)
                if native.digest(private) != manifest["artifact_sha256"]:
                    raise ValueError("unpacked_signed_artifact_changed")
                report["unpacked_artifact_sha256"] = native.digest(private)
                resume_project = folder / "resume-project"
                resume_project.mkdir()
                shutil.copyfile(project / "project.godot", resume_project / "project.godot")
                env["GONGGONG_RUNTIME_CONFIG"] = str(folder / "resume-runtime.json")
                report["resume_cases"] = []
                for case in ("legacy", "compressed", "oversized_declared", "corrupt_digest", "wrong_length"):
                    token = worker.write_resume_fixture(resume_project, args.godot, private, case)
                    completed = subprocess.run(
                        [str(private), "--headless", "--editor", "--path", str(resume_project), "--quit-after", "6"],
                        cwd=folder,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=240,
                    )
                    if completed.returncode:
                        raise ValueError("resume_startup_failed: " + case + " " + completed.stderr[-2000:])
                    if case in {"legacy", "compressed"}:
                        error = worker.resume_ack_error(resume_project, token, private)
                        if error:
                            raise ValueError(case + ": " + error)
                    elif any(
                        (resume_project / ".godot/editor" / name).exists()
                        for name in ("ai_chat_restart_ack.json", "ai_chat_resume.json")
                    ):
                        raise ValueError("invalid_resume_was_acknowledged_or_retained: " + case)
                    report["resume_cases"].append(case)
            report["ok"] = bundle_ok
    except Exception as error:
        report["error"] = str(error)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {key: value for key, value in report.items() if key not in {"bundle_stdout", "bundle_stderr"}},
            ensure_ascii=False,
        )
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
