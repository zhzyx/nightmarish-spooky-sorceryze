"""Check automatic Cocoa startup validation against a frozen desktop package manifest."""

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

PREFIX = "GongGong macOS startup validation"
PACKAGES = ("ui", "board")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def exercise(app, manifest, root, report):
    frozen = json.loads(manifest.read_bytes())["desktop_packages"]
    expected = {name: frozen[f"tianshu-{name}.json"]["sha256"] for name in PACKAGES}
    private = root / "Candidate.app"
    subprocess.run(["/usr/bin/ditto", app, private], check=True)
    subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", private], check=True)
    exe = private / "Contents/MacOS/Godot"
    resources = private / "Contents/Resources"
    paths = {name: resources / f"tianshu-{name}.json" for name in PACKAGES}
    if any(path.resolve(strict=True) != path for path in [exe, *paths.values()]):
        raise ValueError("Expected regular files inside the private bundle")
    original = {name: path.read_bytes() for name, path in paths.items()}
    if {name: digest(raw) for name, raw in original.items()} != expected:
        raise ValueError("Installed package bytes differ from the frozen manifest")
    report.update(
        editor_sha256=digest(exe.read_bytes()),
        manifest_sha256=digest(manifest.read_bytes()),
        installed_packages=expected,
    )
    (root / "_sc_").touch()
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text(
        'config_version=5\n[application]\nconfig/name="Startup validation"\n'
        '[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
    )
    home = root / "home"
    (home / "Library/Caches").mkdir(parents=True)
    temp = root / "temp"
    temp.mkdir()
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(home),
        "CFFIXED_USER_HOME": str(home),
        "TMPDIR": str(temp),
        "__GODOT_SHELL_ENV_SET": "1",
    }
    cache = root / "editor_data/cache"

    def receipts():
        return {p.name: p.read_bytes() for p in cache.glob("godot-silent-*.ok")}

    def launch(case, result, rejected="", diagnostic=""):
        before = receipts()
        run = subprocess.run(
            [exe, "--editor", "--display-driver", "macos", "--path", project, "--max-fps", "30", "--quit-after", "600"],
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=120,
        )
        log = run.stdout + run.stderr
        lines = log.splitlines()
        after = receipts()
        changed = sorted(after.keys() - before.keys())
        observations = [line.strip() for line in lines if PREFIX in line or "TIANSHU_" in line or "ERROR:" in line]
        report["cases"][case] = dict(exit_code=run.returncode, new_receipts=changed, observations=observations)
        if run.returncode or "SCRIPT ERROR" in log:
            raise RuntimeError(f"{case}: editor failed\n{log}")
        if any(after.get(key) != value for key, value in before.items()):
            raise RuntimeError(f"{case}: existing cache changed")
        if any(after[key].decode().strip() != key.removeprefix("godot-silent-").removesuffix(".ok") for key in changed):
            raise RuntimeError(f"{case}: invalid cache content")
        if result == "passed":
            if len(changed) != 1 or PREFIX + " passed" not in lines or PREFIX + " reused" in log:
                raise RuntimeError(f"{case}: cold probe did not create a success receipt\n{log}")
            for name, path in paths.items():
                if f"TIANSHU_{name.upper()}_LOADED {digest(path.read_bytes())}" not in lines:
                    raise RuntimeError(f"{case}: child did not confirm {name}\n{log}")
        elif result == "reused":
            if changed or PREFIX + " reused" not in lines or PREFIX + " passed" in log or "TIANSHU_UI_LOADED" in log:
                raise RuntimeError(f"{case}: expected cached success without a child probe\n{log}")
        else:
            reason = PREFIX + f": Tianshu {rejected} package was not loaded"
            if (
                changed
                or reason not in log
                or diagnostic not in log
                or PREFIX + " passed" in log
                or PREFIX + " reused" in log
            ):
                raise RuntimeError(f"{case}: expected explicit uncached failure\n{log}")
        if not rejected and ("Tianshu UI package missing" in log or "Tianshu board package missing" in log):
            raise RuntimeError(f"{case}: child reported missing resources\n{log}")

    launch("cold", "passed")
    launch("warm", "reused")
    for name, path in paths.items():
        label = "UI" if name == "ui" else "board"
        path.unlink()
        launch(f"missing_{name}", "rejected", name, f"Tianshu {label} package missing")
        envelope = json.loads(original[name])
        envelope["sha256"] = "0" * 64
        path.write_text(json.dumps(envelope), encoding="utf-8")
        launch(f"corrupt_{name}", "rejected", name, f"Tianshu {label} payload checksum mismatch")
        # Valid JSON with different outer bytes must invalidate this package's key.
        path.write_bytes(original[name] + b"\n")
        launch(f"changed_{name}", "passed")
        path.write_bytes(original[name])
        launch(f"restored_{name}", "reused")
    script = Path(__file__).with_name("macos_startup_validation.gd")
    (project / script.name).write_bytes(script.read_bytes())
    partial = subprocess.run(
        [exe, "--headless", "--editor", "--path", project, "--script", "res://" + script.name],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=180,
    )
    log = partial.stdout + partial.stderr
    diagnostics = [f"isolated Tianshu {name} package did not match the parent editor" for name in PACKAGES]
    if partial.returncode or "GONGGONG_VALIDATION_CLEANUP_OK" not in log or not all(msg in log for msg in diagnostics):
        raise RuntimeError("Partial child receipts or cleanup regression\n" + log)
    report["cases"]["partial_child_receipts"] = dict(exit_code=partial.returncode, observations=diagnostics)
    subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", app], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", required=True, type=Path, help="signed candidate .app")
    parser.add_argument("--manifest", required=True, type=Path, help="frozen common.json with desktop_packages")
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Cocoa acceptance requires macOS")
    report = dict(platform=platform.platform(), display="macos", state="failed", cases={})
    try:
        with tempfile.TemporaryDirectory(prefix="startup-validation-") as directory:
            exercise(args.app.resolve(strict=True), args.manifest, Path(directory).resolve(), report)
        report["state"] = "passed"
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
