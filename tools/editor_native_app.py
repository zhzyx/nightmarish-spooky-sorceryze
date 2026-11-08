"""Package and verify the existing candidate as an immutable native macOS App.

The resource is a locator for the host's existing private candidate records. It
does not authorize a work order. Manifests and build snapshots stay beside the
App so recording the signed executable's digest never invalidates its seal.
"""

import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXECUTABLE_RELATIVE = "Contents/MacOS/Godot"
ORIGIN_RELATIVE = "Contents/Resources/gonggong_engine_origin.json"
MACH_O_MAGICS = {
    b"\xfe\xed\xfa\xce",
    b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
    b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe",
    b"\xbe\xba\xfe\xca",
    b"\xca\xfe\xba\xbf",
    b"\xbf\xba\xfe\xca",
}


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def manifest_path(app):
    return Path(str(app) + ".candidate.json")


def native_output_dir(root):
    """Derive the local artifact store without creating or trusting a path."""
    root = Path(root).resolve(strict=True)
    if sys.platform != "darwin":
        return root / "bin"
    import pwd

    source = str(root)
    home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    return (
        home
        / "Library/Application Support/gonggong/engine-artifacts"
        / hashlib.sha256(source.encode("utf-8")).hexdigest()
    )


def prepare_native_output_dir(root):
    output = native_output_dir(root)
    if not output.is_absolute() or output.resolve() != output:
        raise ValueError("candidate_native_app_path_invalid")
    missing = []
    for path in (output, *output.parents):
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise ValueError("candidate_native_app_path_invalid")
        if not path.exists():
            missing.append(path)
    for path in reversed(missing):
        path.mkdir(mode=0o700, exist_ok=True)
        if path.is_symlink() or not path.is_dir():
            raise ValueError("candidate_native_app_path_invalid")
    if output.resolve() != output:
        raise ValueError("candidate_native_app_path_invalid")
    return output


def app_for_executable(executable):
    executable = Path(executable)
    app = executable.parent.parent.parent
    return app if app.suffix == ".app" and executable == app / EXECUTABLE_RELATIVE else None


def native_executable(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink() or not os.access(path, os.X_OK):
        raise ValueError("candidate_native_executable_invalid")
    with path.open("rb") as stream:
        if stream.read(4) not in MACH_O_MAGICS:
            raise ValueError("candidate_native_executable_not_macho")


def verify_signature(app):
    result = subprocess.run(
        ["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)], capture_output=True, timeout=120
    )
    if result.returncode:
        raise ValueError(
            "candidate_native_signature_invalid: " + result.stderr.decode("utf-8", errors="replace").strip()[:2000]
        )


def clear_staged_signing_metadata(app):
    """Remove codesign-prohibited metadata only from the new staging copy."""
    for path in (Path(app), *Path(app).rglob("*")):
        result = subprocess.run(["/usr/bin/xattr", "-s", str(path)], capture_output=True, timeout=30)
        if result.returncode:
            raise ValueError("candidate_native_metadata_cleanup_failed")
        attributes = result.stdout.splitlines()
        for name in ("com.apple.FinderInfo", "com.apple.ResourceFork"):
            if name.encode("ascii") in attributes:
                result = subprocess.run(
                    ["/usr/bin/xattr", "-s", "-d", name, str(path)], capture_output=True, timeout=30
                )
                if result.returncode:
                    raise ValueError("candidate_native_metadata_cleanup_failed")


def copy_app(source, destination):
    """Preserve resource forks/extended signatures as well as ordinary bytes."""
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError("candidate_native_copy_target_occupied")
    # Python's copytree on macOS does not reliably preserve the extended
    # signatures codesign gives non-Mach-O nested components (e.g. alternate
    # template plists). ditto preserves those without re-signing anything.
    result = subprocess.run(
        ["/usr/bin/ditto", "--rsrc", "--extattr", str(source), str(destination)], capture_output=True, timeout=120
    )
    if result.returncode:
        raise ValueError("candidate_native_copy_failed")


def read_locator(executable):
    app = app_for_executable(executable)
    if app is None:
        return None
    resource = app / ORIGIN_RELATIVE
    if resource.is_symlink() or resource.stat().st_size > 64 * 1024:
        raise ValueError("candidate_native_origin_invalid")
    value = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("candidate_native_origin_invalid")
    return value


def origin_value(root, binding, project, app):
    root = Path(root).resolve()
    binding_path = Path(binding["binding_path"])
    if (
        binding.get("source_root") != str(root)
        or not binding_path.is_absolute()
        or binding_path.resolve() != binding_path
    ):
        raise ValueError("candidate_native_binding_invalid")
    if not project or not (Path(project).resolve() / "project.godot").is_file():
        raise ValueError("candidate_native_project_missing")
    return {
        "schema_version": 1,
        "source_root": str(root),
        "binding_path": binding["binding_path"],
        "candidate_manifest": str(manifest_path(app)),
        "project_root": str(Path(project).resolve()) if project else "",
    }


def descriptor(root, app):
    root, app = Path(root).resolve(strict=True), Path(app)
    if (
        not app.is_absolute()
        or (app.parent != root / "bin" and app.parent != native_output_dir(root))
        or app.suffix != ".app"
        or app.is_symlink()
        or app.resolve() != app
    ):
        raise ValueError("candidate_native_app_path_invalid")
    return {"bundle_path": str(app), "executable_relative": EXECUTABLE_RELATIVE, "origin_relative": ORIGIN_RELATIVE}


def verify_bundle(app, expected_origin, artifact_sha256=None, *, signature=True):
    app = Path(app)
    executable = app / EXECUTABLE_RELATIVE
    if app.is_symlink() or not app.is_dir() or app.resolve() != app:
        raise ValueError("candidate_native_app_path_invalid")
    # Reject linked Contents, MacOS, Resources, plist or locator as well as a
    # linked executable. A copied bundle must own its actual launch resources.
    for relative in ("Contents", "Contents/MacOS", "Contents/Resources", "Contents/Info.plist", ORIGIN_RELATIVE):
        path = app / relative
        if path.is_symlink() or path.resolve() != path:
            raise ValueError("candidate_native_app_path_invalid")
    native_executable(executable)
    with (app / "Contents/Info.plist").open("rb") as stream:
        info = plistlib.load(stream)
    if info.get("CFBundleExecutable") != "Godot" or "LSEnvironment" in info:
        raise ValueError("candidate_native_plist_invalid")
    if read_locator(executable) != expected_origin:
        raise ValueError("candidate_native_origin_invalid")
    if artifact_sha256 is not None and digest(executable) != artifact_sha256:
        raise ValueError("candidate_native_artifact_changed")
    if signature:
        verify_signature(app)
    return executable


def validate_native_app(root, manifest, manifest_file=None, *, signature=True):
    native = manifest.get("native_app")
    sha256 = manifest.get("artifact_sha256")
    if (
        manifest.get("schema_version") != 1
        or not isinstance(native, dict)
        or not isinstance(sha256, str)
        or len(sha256) != 64
        or any(c not in "0123456789abcdef" for c in sha256)
    ):
        raise ValueError("candidate_native_app_invalid")
    app = Path(native.get("bundle_path", ""))
    if native != descriptor(root, app) or manifest.get("executable") != str(app / EXECUTABLE_RELATIVE):
        raise ValueError("candidate_native_app_invalid")
    if manifest_file is not None and Path(manifest_file) != manifest_path(app):
        raise ValueError("candidate_native_manifest_path_invalid")
    expected = origin_value(root, manifest["binding"], manifest.get("project_root", ""), app)
    verify_bundle(app, expected, manifest.get("artifact_sha256"), signature=signature)
    return app


def package_app(root, artifact, binding, project, destination, template=None):
    root, artifact = Path(root).resolve(strict=True), Path(artifact).resolve(strict=True)
    destination = Path(destination)
    descriptor(root, destination)
    native_executable(artifact)
    template = Path(template) if template else root / "misc/dist/macos_tools.app"
    if template.is_symlink() or not template.is_dir():
        raise ValueError("candidate_native_template_invalid")
    if destination.parent != root / "bin":
        prepare_native_output_dir(root)
    # Stage entirely before replacing a previous inactive output slot. Every
    # byte in the final bundle, including the locator, precedes signing.
    with tempfile.TemporaryDirectory(prefix=".native-package-", dir=destination.parent) as temporary:
        staged = Path(temporary) / destination.name
        copy_app(template, staged)
        for relative in ("Contents", "Contents/MacOS", "Contents/Resources", "Contents/Info.plist", ORIGIN_RELATIVE):
            path = staged / relative
            if path.is_symlink() or path.resolve() != path:
                raise ValueError("candidate_native_template_invalid")
        signature = staged / "Contents/_CodeSignature"
        if signature.is_symlink():
            signature.unlink()
        elif signature.exists():
            shutil.rmtree(signature)
        executable = staged / EXECUTABLE_RELATIVE
        executable.parent.mkdir(parents=True, exist_ok=True)
        executable.unlink(missing_ok=True)
        shutil.copyfile(artifact, executable)
        shutil.copymode(artifact, executable)
        info_path = staged / "Contents/Info.plist"
        with info_path.open("rb") as stream:
            info = plistlib.load(stream)
        info["CFBundleExecutable"] = "Godot"
        info.pop("LSEnvironment", None)
        with info_path.open("wb") as stream:
            plistlib.dump(info, stream)
        locator = staged / ORIGIN_RELATIVE
        locator.parent.mkdir(parents=True, exist_ok=True)
        expected = origin_value(root, binding, project, destination)
        locator.write_text(json.dumps(expected, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        clear_staged_signing_metadata(staged)
        result = subprocess.run(
            ["/usr/bin/codesign", "--force", "--deep", "--sign", "-", str(staged)],
            capture_output=True,
            timeout=120,
        )
        if result.returncode:
            raise ValueError(
                "candidate_native_signing_failed: " + result.stderr.decode("utf-8", errors="replace").strip()[:2000]
            )
        verify_bundle(staged, expected)
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(staged, destination)
    verify_bundle(destination, expected)
    return destination
