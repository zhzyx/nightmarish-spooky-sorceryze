"""Build a side-by-side editor, publishing progress for the running editor.

No editor is killed or overwritten. Restart is handled by the editor's normal
save/exit workflow, not by this worker. Only a checked artifact is marked ready.
"""

import argparse
import base64
import gzip
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def configuration_snapshot(current):
    """An App's build record is external; Godot itself has no slot in its name."""
    import editor_managed_native_entry as managed
    from editor_native_app import app_for_executable, read_locator, validate_native_app, verify_bundle

    app = app_for_executable(current)
    managed_path = app and (app.is_symlink() or managed.in_snapshot_store(app, ROOT))
    previous = Path(str(app if app else current) + ".build.json")
    if previous.is_file() and not managed_path:
        return json.loads(previous.read_text(encoding="utf-8"))
    if app:
        try:
            locator = read_locator(current)
        except FileNotFoundError:
            if managed_path:
                raise ValueError("build_managed_entry_unregistered") from None
            return {}
        manifest_path = Path(locator["candidate_manifest"])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validate_native_app(locator["source_root"], manifest, manifest_path)
        if managed_path:
            from editor_engine_candidate import identity

            initial = Path(manifest["binding"]["initial_launch_executable"])
            common, _, _ = identity(Path(locator["source_root"]))
            record = managed.registered_entry(initial, common, expected_manifest=manifest_path)
            if app not in (app_for_executable(initial), Path(record["canonical_payload"])):
                raise ValueError("build_managed_entry_changed")
        else:
            verify_bundle(app, read_locator(manifest["executable"]), manifest["artifact_sha256"])
        return manifest["build_options"]
    return {}


def write_status(path, **data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


# No plausible build runs this long, so an older lock cannot be trusted even when
# its recorded identifier happens to match a live, unrelated process.
LOCK_MAX_AGE = 12 * 3600


def process_is_running(pid):
    """Report whether a process is alive, without ever signaling it."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:  # Alive, but owned by somebody else.
            return True
        return True
    # On Windows os.kill() terminates the target even for signal 0, so the process
    # must be probed through a query-only handle instead.
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION.
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return True  # Assume the owner lives rather than stealing its lock.
        return code.value == 259  # STILL_ACTIVE.
    finally:
        kernel32.CloseHandle(handle)


def lock_owner(path):
    """Describe the recorded lock holder, tolerating truncated or legacy files."""
    try:
        owner = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return owner if isinstance(owner, dict) else {}


def lock_is_stale(path):
    """A lock is stale once its owner died or it outlived any plausible build."""
    owner = lock_owner(path)
    if not process_is_running(owner.get("pid")):
        return True
    started = owner.get("started")
    return not isinstance(started, (int, float)) or time.time() - started > LOCK_MAX_AGE


def acquire_lock(path):
    """Take the build lock, reclaiming one abandoned by a killed build.

    A bare exclusive file cannot distinguish a running build from a lock left
    behind when SCons was killed, which otherwise blocks every later build until
    somebody deletes the file by hand.
    """
    for reclaimed in (False, True):
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        except FileExistsError:
            if reclaimed or not lock_is_stale(path):
                return False
            try:
                path.unlink()
            except OSError:
                return False
            continue
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"pid": os.getpid(), "started": time.time()}, handle)
        return True
    return False


def build_options(current, extra, host_options=None):
    # Preserve the running editor's platform, architecture, dev and Mono flags.
    parts = current.name.split(".")
    if host_options is not None:
        fixed = {"platform", "target", "arch", "dev_build", "precision", "module_mono_enabled"}
        if (
            not isinstance(host_options, dict)
            or not fixed.issubset(host_options)
            or set(host_options) - fixed - {"use_volk", "accesskit", "vulkan", "metal", "opengl3"}
            or not all(isinstance(value, str) for value in host_options.values())
            or host_options["platform"] not in {"windows", "macos", "linuxbsd"}
            or host_options["target"] != "editor"
            or host_options["arch"] not in {"x86_64", "x86_32", "arm64", "arm32"}
            or host_options["precision"] not in {"single", "double"}
            or any(
                host_options[key] not in {"yes", "no"}
                for key in host_options
                if key not in {"platform", "target", "arch", "precision"}
            )
        ):
            raise ValueError("Invalid authoritative host build features")
        options = dict(host_options)
    else:
        if len(parts) < 4 or parts[0] != "godot" or parts[2] != "editor":
            raise ValueError(
                "The current executable must be a source-built Godot editor or provide authoritative host build features"
            )
        platform = parts[1]
        if platform not in {"windows", "macos", "linuxbsd"}:
            raise ValueError(f"Side-by-side self-update does not support the {platform} editor")
        arch = next((p for p in parts if p in {"x86_64", "x86_32", "arm64", "arm32"}), None)
        if not arch:
            raise ValueError("Cannot identify the current editor architecture")
        options = dict(
            platform=platform,
            target="editor",
            arch=arch,
            dev_build="yes" if "dev" in parts else "no",
            precision="double" if "double" in parts else "single",
            module_mono_enabled="yes" if "mono" in parts else "no",
        )
    saved = configuration_snapshot(current)
    if not isinstance(saved, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in saved.items()):
        raise ValueError("Invalid build configuration snapshot")
    if saved:
        protected = {
            "platform",
            "target",
            "arch",
            "dev_build",
            "precision",
            "module_mono_enabled",
            "extra_suffix",
            "ninja",
        }
        extra = [f"{k}={v}" for k, v in saved.items() if k not in protected] + extra
    for item in extra:
        key, separator, value = item.partition("=")
        if not separator or not re.fullmatch(r"[a-zA-Z_][a-zA-Z_0-9]*", key):
            raise ValueError("Additional SCons options must be key=value")
        if key in {
            "platform",
            "target",
            "arch",
            "dev_build",
            "precision",
            "module_mono_enabled",
            "extra_suffix",
            "ninja",
            "compiledb",
            "vsproj",
            "object_prefix",
        }:
            raise ValueError("Cannot override protected self-update option: " + key)
        options[key] = value
    # Two reusable output slots keep subsequent updates incremental. Neither slot
    # may overwrite the running editor. SCons itself reports other output locks.
    from editor_native_app import app_for_executable

    app = app_for_executable(current)
    slot_parts = (app.name if app else current.name).split(".")
    current_slot = saved.get("extra_suffix") if saved else None
    slot = "self_update_b" if current_slot == "self_update_a" or "self_update_a" in slot_parts else "self_update_a"
    options["extra_suffix"] = slot
    options["ninja"] = "no"
    return options


def write_resume_fixture(project, current, artifact, storage_case="legacy"):
    """Arm the startup check with a restart handoff the new editor must answer.

    A version check only proves the process starts. The AI dock is what has to
    keep working, because a broken dock cannot report its own breakage and would
    otherwise be promoted and then be unable to roll itself back.
    """
    token = secrets.token_hex(12)
    settings = project / ".godot/editor"
    settings.mkdir(parents=True, exist_ok=True)
    journal = {
        "version": 1,
        "agent": 0,
        "tool_rounds": 0,
        "tool_index": 0,
        "model": "",
        "cli_model": "",
        "backend": 0,
        # Acknowledge and stop: the check must not continue somebody's agent loop.
        "smoke_check": True,
        "messages": [],
        "tool_calls": [
            {"id": "startup_check", "type": "function", "function": {"name": "build_engine", "arguments": "{}"}}
        ],
        "restart": {
            "tool_call_id": "startup_check",
            "tool_name": "build_engine",
            "from_executable": str(current),
            "to_executable": str(artifact),
            "token": token,
            "attempt": 1,
        },
    }
    # Each case must earn a fresh acknowledgment, never reuse a previous one.
    (settings / "ai_chat_restart_ack.json").unlink(missing_ok=True)
    if storage_case != "legacy":
        # Exercise the real reader beyond the old 16 MiB cap, including UTF-8.
        journal["messages"] = [{"role": "user", "content": "snapshot 保留约束\n" * (1024 * 1024)}]
        raw = json.dumps(journal, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if not 16 * 1024 * 1024 < len(raw) <= 64 * 1024 * 1024:
            raise RuntimeError("Compressed resume fixture does not exercise the size boundary")
        journal = {
            "storage": "gzip-base64",
            "storage_version": 1,
            "uncompressed_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "payload": base64.b64encode(gzip.compress(raw, mtime=0)).decode("ascii"),
        }
        if storage_case == "oversized_declared":
            journal["uncompressed_bytes"] = 64 * 1024 * 1024 + 1
        elif storage_case == "corrupt_digest":
            journal["sha256"] = "0" * 64
        elif storage_case == "wrong_length":
            journal["uncompressed_bytes"] += 1
        elif storage_case != "compressed":
            raise ValueError("Unknown resume fixture storage case: " + storage_case)
    (settings / "ai_chat_resume.json").write_text(json.dumps(journal, ensure_ascii=False), encoding="utf-8")
    return token


def resume_ack_error(project, token, artifact):
    """Describe why the startup check is not acceptable, or nothing if it is."""
    ack = project / ".godot/editor/ai_chat_restart_ack.json"
    if not ack.is_file():
        return "The new editor started but its AI dock never acknowledged the restart handoff"
    try:
        value = json.loads(ack.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        return f"The new editor wrote an unreadable restart acknowledgment: {error}"
    if not isinstance(value, dict) or value.get("token") != token or value.get("dock_ready") is not True:
        return "The new editor wrote a restart acknowledgment for a different handoff"
    if Path(value.get("executable", "")).name != artifact.name:
        return "The restart acknowledgment names a different executable"
    if (project / ".godot/editor/ai_chat_resume.json").is_file():
        return "The new editor did not consume the restart journal, so it would replay on every start"
    return ""


def artifact_path(options):
    platform = options["platform"]
    name = f"godot.{platform}.editor"
    if options["dev_build"] == "yes":
        name += ".dev"
    if options["precision"] == "double":
        name += ".double"
    name += "." + options["arch"]
    if options.get("threads") == "no":
        name += ".nothreads"
    name += "." + options["extra_suffix"]
    if options["module_mono_enabled"] == "yes":
        name += ".mono"
    suffix = ".exe" if platform == "windows" else ""
    return ROOT / "bin" / (name + suffix)


def private_check_editor(artifact, directory):
    """Unpack the signed Mach-O before the isolation helper copies its bytes."""
    import importlib.util

    from editor_native_app import digest

    spec = importlib.util.spec_from_file_location(
        "editor_test_isolation", ROOT / "tests/editor/editor_test_isolation.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    unpacked = Path(directory) / "unpacked"
    unpacked.mkdir()
    bare = unpacked / artifact.name
    shutil.copyfile(artifact, bare)
    shutil.copymode(artifact, bare)
    expected = digest(artifact)
    # copy_editor intentionally consults the parent process environment.
    inherited = os.environ.pop("GONGGONG_WORKSPACE", None)
    try:
        private = module.copy_editor(bare, Path(directory) / "private_sc_editor")
    finally:
        if inherited is not None:
            os.environ["GONGGONG_WORKSPACE"] = inherited
    if digest(bare) != expected or digest(private) != expected:
        raise ValueError("candidate_isolated_artifact_changed")
    return private


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--status", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--cancel", type=Path, required=True)
    parser.add_argument("--scons-arg", action="append", default=[])
    parser.add_argument("--binding", type=Path)
    parser.add_argument("--project", default="")
    parser.add_argument("--host-build-options", type=json.loads)
    parser.add_argument("--artifact-layout", choices=("raw", "native_app"), default="raw")
    parser.add_argument("--maliang-release", type=Path, help="Signed Ma Liang .app for the first offline-model upgrade")
    args = parser.parse_args(argv)
    if args.maliang_release is not None and args.artifact_layout != "native_app":
        parser.error("--maliang-release requires --artifact-layout native_app")
    status = args.status.resolve()
    log_path = args.log.resolve()
    if not all(p.parent.is_dir() for p in (status, log_path, args.cancel)):
        parser.error("Status, log and cancel parent directories must already exist")
    # An exclusive lock prevents two agents/editors from building into the same slot.
    output_root = ROOT / "bin"
    if output_root.is_symlink() or (hasattr(output_root, "is_junction") and output_root.is_junction()):
        write_status(
            status, stage="failed", percent=0, error="Linked engine output directory is not allowed", exit_code=1
        )
        return 1
    output_root.mkdir(exist_ok=True)
    lock = output_root / "editor_self_build.lock"
    if not acquire_lock(lock):
        owner = lock_owner(lock).get("pid")
        held = f" (process {owner})" if isinstance(owner, int) else ""
        write_status(status, stage="failed", percent=0, error=f"Another self-build owns {lock}{held}", exit_code=1)
        return 1
    try:
        binding = None
        before = None
        if args.binding:
            import editor_engine_candidate as candidates
            from editor_source_manifest import source_snapshot

            binding = json.loads(args.binding.read_text(encoding="utf-8"))
            checked = candidates.prepare(
                ROOT, binding["issue"], binding["request_id"], binding["owner"], validate_only=True
            )
            if (
                Path(checked["source_root"]).resolve() != ROOT.resolve()
                or Path(checked["binding_path"]).resolve() != args.binding.resolve()
            ):
                raise ValueError("candidate_build_binding_mismatch")
            before = source_snapshot(ROOT)
        options = build_options(args.current, args.scons_arg, args.host_build_options)
        if args.artifact_layout == "native_app" and (not binding or options["platform"] != "macos"):
            raise ValueError("native_app_layout_requires_bound_macos_candidate")
        artifact = artifact_path(options)
        if artifact.resolve() == args.current.resolve():
            raise ValueError("Refusing to overwrite the running editor")
        env = os.environ.copy()
        # Empty MSYSTEM is required; merely unsetting it is not enough in Git Bash.
        env["MSYSTEM"] = ""
        env["PYTHONUNBUFFERED"] = "1"
        env["GODOT_BUILD_PROGRESS_FILE"] = str(status)
        dotnet = ROOT / ".dotnet"
        if dotnet.is_dir():
            env["DOTNET_ROOT"] = str(dotnet)
            env["DOTNET_ROOT_X64"] = str(dotnet)
            env["PATH"] = str(dotnet) + os.pathsep + env.get("PATH", "")
        command = [sys.executable, "-m", "SCons", *[f"{key}={value}" for key, value in options.items()]]
        write_status(status, stage="preparing", percent=0, log=str(log_path))
        # A monitor supplies cooperative cancellation without orphaning SCons.
        import threading

        cancelled = threading.Event()
        finished = threading.Event()

        def watch_cancel():
            while not finished.wait(0.25):
                if args.cancel.exists():
                    cancelled.set()
                    break

        threading.Thread(target=watch_cancel, daemon=True).start()

        # Popen polling below uses an Event, rather than blocking editor frames.
        def step(cmd, timeout=3600):
            log.write(("\nCOMMAND: " + subprocess.list2cmdline(cmd) + "\n").encode("utf-8"))
            log.flush()
            # Write directly to the log. Descendants may inherit stdout, so waiting
            # for pipe EOF would outlive the child and could block indefinitely.
            child = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + timeout
            try:
                while child.poll() is None:
                    if cancelled.wait(0.25):
                        raise InterruptedError("Build cancelled; current editor unchanged")
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Build/check timed out; current editor unchanged")
                return child.returncode
            finally:
                if child.poll() is None:
                    if os.name == "nt":
                        subprocess.run(
                            ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                            stdout=log,
                            stderr=subprocess.STDOUT,
                            check=False,
                        )
                    else:
                        child.kill()
                    child.wait()

        with log_path.open("wb", buffering=0) as log:
            try:
                env["GODOT_BUILD_COUNT_ONLY"] = "1"
                code = step([*command, "--dry-run"])
                if code:
                    raise RuntimeError(f"SCons preparation failed (exit {code}); see {log_path}")
                counted = json.loads(status.read_text(encoding="utf-8"))
                total = counted.get("total", 0)
                if counted.get("stage") != "counted" or total <= 0:
                    raise RuntimeError("SCons did not publish a build node count")
                env["GODOT_BUILD_COUNT_ONLY"] = "0"
                env["GODOT_BUILD_PROGRESS_TOTAL"] = str(total)
                write_status(status, stage="building", percent=0, total=total, estimated=True)
                code = step(command)
                if code:
                    raise RuntimeError(f"SCons build failed (exit {code}); see {log_path}")
                if not artifact.is_file():
                    raise RuntimeError("SCons exited successfully but the expected editor is missing")
                native_app = None
                # Older running hosts understand only raw executables and their
                # adjacent manifests. A native-aware caller explicitly opts in.
                if args.artifact_layout == "native_app":
                    from editor_native_app import (
                        EXECUTABLE_RELATIVE,
                        app_for_executable,
                        maliang_template,
                        native_output_dir,
                        package_app,
                    )

                    native_app = native_output_dir(ROOT) / (artifact.name + ".app")
                    running_app = app_for_executable(args.current.resolve())
                    if running_app == native_app:
                        raise ValueError("Refusing to overwrite the running editor App")
                    template = maliang_template(running_app, args.maliang_release)
                    package_app(ROOT, artifact, checked, args.project, native_app, template)
                    artifact = native_app / EXECUTABLE_RELATIVE
                snapshot = Path(str(native_app if native_app else artifact) + ".build.json")
                snapshot.write_text(json.dumps(options, ensure_ascii=False), encoding="utf-8")
                manifest = None
                write_status(status, stage="checking", percent=99, executable=str(artifact))
                # Exercise exactly the signed Mach-O bytes, copied to a private
                # self-contained editor outside any source/workspace ancestor.
                with tempfile.TemporaryDirectory(prefix="private_sc_self_update_") as directory:
                    private_artifact = private_check_editor(artifact, directory)
                    env = {key: value for key, value in env.items() if not key.startswith("GONGGONG_")}
                    env.pop("GODOT_BUILD_PROGRESS_FILE", None)
                    env["GONGGONG_RUNTIME_CONFIG"] = str(Path(directory) / "runtime-config.json")
                    code = step([str(private_artifact), "--headless", "--version"], timeout=60)
                    if code:
                        raise RuntimeError(f"New editor version check failed (exit {code})")
                    project = Path(directory) / "project"
                    project.mkdir()
                    (project / "project.godot").write_text(
                        'config_version=5\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
                        encoding="utf-8",
                    )
                    for storage_case in (
                        "legacy",
                        "compressed",
                        "oversized_declared",
                        "corrupt_digest",
                        "wrong_length",
                    ):
                        token = write_resume_fixture(project, args.current, private_artifact, storage_case)
                        # A first start in a fresh project pays for the initial scan.
                        code = step(
                            [
                                str(private_artifact),
                                "--headless",
                                "--editor",
                                "--path",
                                str(project),
                                "--quit-after",
                                "6",
                            ],
                            timeout=240,
                        )
                        if code:
                            raise RuntimeError(f"New editor startup failed for {storage_case} (exit {code})")
                        if storage_case in {"legacy", "compressed"}:
                            unacceptable = resume_ack_error(project, token, private_artifact)
                            if unacceptable:
                                raise RuntimeError(f"Resume check {storage_case}: {unacceptable}")
                        elif (project / ".godot/editor/ai_chat_restart_ack.json").exists() or (
                            project / ".godot/editor/ai_chat_resume.json"
                        ).exists():
                            raise RuntimeError(
                                f"Invalid resume check {storage_case} was acknowledged or retained for replay"
                            )
                        log.write(f"Resume startup check passed: {storage_case}\n".encode())
                if cancelled.is_set():
                    raise InterruptedError("Build cancelled; current editor unchanged")
                if binding:
                    # Publish only after startup succeeds: an older ready
                    # receipt may already point at this reusable output slot.
                    from editor_source_manifest import artifact_manifest, verify_source

                    manifest = artifact_manifest(ROOT, artifact, checked, args.project, options, before, native_app)
                    verify_source(ROOT, manifest)
                    recorded = json.loads(args.binding.read_text(encoding="utf-8"))
                    recorded["artifact_manifest"] = manifest
                    candidates.atomic_json(args.binding, recorded)
                write_status(
                    status,
                    stage="ready",
                    percent=100,
                    executable=str(artifact),
                    exit_code=0,
                    log=str(log_path),
                    configuration=options,
                    candidate_manifest=Path(manifest).as_posix() if manifest is not None else None,
                )
                return 0
            finally:
                finished.set()
    except Exception as error:
        write_status(
            status,
            stage="cancelled" if isinstance(error, InterruptedError) else "failed",
            percent=0,
            exit_code=1,
            error=str(error),
            log=str(log_path),
        )
        print(error, file=sys.stderr)
        return 1
    finally:
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
