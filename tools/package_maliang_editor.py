"""Build the offline Hunyuan image-to-mesh editor on Apple Silicon or Windows x64.

    python tools/package_maliang_editor.py --editor bin/Godot --output dist/Maliang.app
    py -3 tools/package_maliang_editor.py --editor bin --output dist/Maliang

Use --runtime with an already prepared python/ and ComfyUI-src/. Supply
--checkpoint and --license separately, or use the copies in a complete runtime.
Downloads take place on the build machine. The finished editor can be moved.
"""

import argparse
import ctypes
import errno
import hashlib
import http.client
import json
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile
from contextlib import contextmanager
from pathlib import Path

import editor_native_app
from package_tianshu_ui import installed_package

RECIPE = Path(__file__).resolve().with_name("maliang_hunyuan")
DISTRIBUTION = "maliang-hunyuan3d-2mini-v1"
BACKEND = "63e5bf594339f676b4b15e072529873e3448409e"
COMFY_URL = "https://codeload.github.com/Comfy-Org/ComfyUI/tar.gz/" + BACKEND
COMFY_SHA = "22ebca008dc6cbc8ab7cf2b456a3580a9195e3d81102f9d07d54c44b889f8257"
COMFY_TREE = "3540e0007b6c46875b3261426850a4466efee8e180d372b93a45fec8d865b71f"
# Unused upstream examples, CI, tests and writable work directories are outside the
# server source digest. The shipped first-party server/modules/assets are bound together.
COMFY_EXTRAS = {
    ".ci",
    ".github",
    "blueprints",
    "tests",
    "tests-unit",
    "script_examples",
    "input",
    "output",
    "temp",
    "user",
    "previews",
    "models",
    "custom_nodes",
}
MODEL_REVISION = "f90a0f7df7d5e6f71109cf333f6a95a0ae3194a6"
MODEL_BASE = "https://huggingface.co/tencent/Hunyuan3D-2mini/resolve/" + MODEL_REVISION + "/"
MODEL_URL = MODEL_BASE + "hunyuan3d-dit-v2-mini/model.fp16.safetensors"
MODEL_NAME = "hunyuan3d-mini.safetensors"
MODEL_PATH = Path("models/checkpoints") / MODEL_NAME
MODEL_SHA = "3cc66f3bea33e4062b7dbc875ffe1d70c4888914aec3e91b60f94e9bd01b522b"
MODEL_SIZE = 3819958234
LICENSE_SHA = "e5e6e2041e18326d82cd105a1b9404e36db55263dd9d42d4989f917c2501b67b"
NOTICE_SHA = "7b7ace3714c188b7a27e20edbcceaaac836540bbb63759a37039e5624c8f6bbc"
PYTHON_RELEASE = "20261026"
PYTHON_VERSION = "3.12.16"
PYTHONS = {
    "macos": ("aarch64-apple-darwin", "353d5f1b4fd2715e7053f12f068435d5bbad16b91e057006b5d01e0925709a7e"),
    "windows": ("x86_64-pc-windows-msvc", "1f2ab53880fc67ea323398c6388e05af28addc99a8e389209f08a51fdff4b149"),
}
CONFIG = {
    "distribution": DISTRIBUTION,
    "endpoint": "http://127.0.0.1:18788",
    "backend_revision": BACKEND,
    "checkpoints": {"mesh": {"name": MODEL_NAME, "sha256": MODEL_SHA}},
}
MODEL_PATHS = "maliang:\n  base_path: .\n  is_default: true\n  checkpoints: models/checkpoints\n"
TENCENT_ATTRIBUTION = (
    "Tencent Hunyuan 3D 2.0 is licensed under the Tencent Hunyuan 3D 2.0 Community License Agreement, "
    "Copyright © 2025 Tencent. All Rights Reserved. The trademark rights of “Tencent Hunyuan” "
    "are owned by Tencent or its affiliate."
)
digest = editor_native_app.digest


def platform_name():
    pair = (sys.platform, platform.machine().lower())
    if pair == ("darwin", "arm64"):
        return "macos"
    if pair[0] == "win32" and pair[1] in ("amd64", "x86_64"):
        return "windows"
    raise ValueError("Build on Apple Silicon macOS or x86-64 Windows for that platform.")


def python_path(runtime, target):
    return runtime / ("python/bin/python3.12" if target == "macos" else "python/python.exe")


def resource_path(editor, target):
    directory = editor / "Contents/Resources" if target == "macos" else editor
    return directory / "maliang-hunyuan"


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def require_hash(path, expected):
    if digest(path) != expected:
        raise ValueError(f"SHA-256 mismatch: {path.name}")


def download(url, destination, expected, size=None):
    """Stream fixed inputs, resuming only on a matching HTTP byte range."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        offset = destination.stat().st_size if destination.exists() else 0
        request = urllib.request.Request(url, headers={"Range": f"bytes={offset}-"} if offset else {})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                resumed = response.status == 206
                if resumed and not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
                    raise ValueError("Unexpected range from " + url)
                with destination.open("ab" if resumed else "wb") as out:
                    shutil.copyfileobj(response, out, 4 * 1024 * 1024)
                length = response.headers.get("Content-Length")
                end = (offset if resumed else 0) + int(length) if length else None
            total = destination.stat().st_size
            if (size and total < size) or (end and total < end):
                raise OSError(f"Short response at {total} bytes")
            if digest(destination) == expected:
                return
            destination.unlink()
            error = ValueError("SHA-256 mismatch from " + url)
        except (OSError, http.client.HTTPException) as exc:
            error = exc
        if attempt < 2:
            time.sleep(2**attempt)
    raise ValueError(f"Download failed: {url} ({error})")


def unpack_download(url, expected, top, destination, scratch):
    with tempfile.TemporaryDirectory(dir=scratch) as temp:
        directory = Path(temp)
        archive = directory / "source.tar.gz"
        download(url, archive, expected)
        with tarfile.open(archive, "r:gz") as source:
            # These exact official archives were digest-verified above. Python
            # 3.12+ additionally applies the stdlib data-only extraction policy.
            options = {"filter": "data"} if hasattr(tarfile, "data_filter") else {}
            source.extractall(directory, **options)
        (directory / top).rename(destination)


def copy_file(source, destination):
    """Clone APFS files, retaining xattrs, and copy normally across filesystems."""
    if sys.platform == "darwin":
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.clonefile(os.fsencode(source), os.fsencode(destination), 0) == 0:
            return destination
        code = ctypes.get_errno()
        if code not in (errno.EXDEV, errno.ENOTSUP, errno.EINVAL, errno.ENOSYS, errno.EPERM):
            raise OSError(code, os.strerror(code), str(destination))
    return shutil.copy2(source, destination)


def ignore_cache(directory, names):
    return [name for name in names if name in (".git", ".DS_Store", "__pycache__") or name.endswith((".pyc", ".pyo"))]


def copy_tree(source, destination, ignore=ignore_cache):
    shutil.copytree(source, destination, symlinks=True, copy_function=copy_file, ignore=ignore)


def copy_prepared_comfy(source, destination):
    # User images, generated meshes, extra models and custom nodes are private
    # runtime state. Only copy the server whose source identity we can verify.
    def ignore(directory, names):
        ignored = ignore_cache(directory, names)
        if Path(directory) == source:
            ignored.extend(name for name in names if name.startswith(".") or name in COMFY_EXTRAS)
        return ignored

    copy_tree(source, destination, ignore)
    for name in ("input", "output", "custom_nodes"):
        (destination / name).mkdir()


def validate_links(root):
    """All symlinks in supplied software must move with the copy."""
    for directory, dirs, files in os.walk(root):
        for name in dirs + files:
            item = Path(directory, name)
            if item.is_symlink():
                if os.path.isabs(os.readlink(item)) or not item.resolve(strict=True).is_relative_to(root):
                    raise ValueError(f"Link outside the distribution: {item.relative_to(root)}")
            elif getattr(os.path, "isjunction", lambda path: False)(item):
                raise ValueError(f"Nonportable directory junction: {item.relative_to(root)}")


def verify_comfy(root):
    entries = {}
    for directory, dirs, files in os.walk(root):
        here = Path(directory)
        dirs[:] = [
            name
            for name in dirs
            if not name.startswith(".") and name != "__pycache__" and (here != root or name not in COMFY_EXTRAS)
        ]
        for name in files:
            if name.startswith(".") or name.endswith((".pyc", ".pyo")):
                continue
            path = here / name
            entries[path.relative_to(root).as_posix()] = digest(path)
    value = hashlib.sha256()
    for name in sorted(entries):
        value.update((entries[name] + "  " + name + "\n").encode())
    if value.hexdigest() != COMFY_TREE:
        raise ValueError(f"ComfyUI server source does not match commit {BACKEND}.")


def prepare_python(runtime, target, scratch):
    triple, sha256 = PYTHONS[target]
    name = f"cpython-{PYTHON_VERSION}%2B{PYTHON_RELEASE}-{triple}-install_only_stripped.tar.gz"
    url = f"https://github.com/astral-sh/python-build-standalone/releases/download/{PYTHON_RELEASE}/{name}"
    unpack_download(url, sha256, "python", runtime / "python", scratch)
    lock = RECIPE / (target + "-cp312.txt")
    subprocess.run(
        [
            str(python_path(runtime, target)),
            "-I",
            "-B",
            "-m",
            "pip",
            "--isolated",
            "--disable-pip-version-check",
            "install",
            "--no-index",
            "--no-deps",
            "--no-compile",
            "--no-cache-dir",
            "--only-binary=:all:",
            "--require-hashes",
            "-r",
            str(lock),
        ],
        check=True,
    )
    return {"url": url, "sha256": sha256, "wheels_sha256": digest(lock)}


def install_windows_crt(runtime, scratch):
    # Python/Torch and the native editor use app-local CRT DLLs on clean Windows.
    # Carry Microsoft's x64 Release CRT and OpenMP files from the published VSIX.
    source = json.loads((RECIPE / "windows-crt.json").read_text(encoding="utf-8"))
    files = source["files"]
    python = runtime / "python"
    if not all((python / name).is_file() and digest(python / name) == sha for name, sha in files.items()):
        archive = scratch / "VC-Redist.vsix"
        download(source["url"], archive, source["sha256"])
        with zipfile.ZipFile(archive) as package:
            for name, sha in files.items():
                component = "OpenMP" if name == "vcomp140.dll" else "CRT"
                member = f"Contents/VC/Redist/MSVC/14.44.35112/x64/Microsoft.VC143.{component}/{name}"
                destination = python / name
                with package.open(member) as data, destination.open("wb") as out:
                    shutil.copyfileobj(data, out)
                require_hash(destination, sha)
        archive.unlink()
    for name in files:
        editor_dll = runtime.parent / name
        if not editor_dll.exists():
            copy_file(python / name, editor_dll)
    write_json(runtime / "licenses/Microsoft-VC-Redist-sources.json", source)
    return {"version": source["version"], "url": source["url"], "sha256": source["sha256"]}


def strip_build_launchers(python, target):
    # The editor invokes the bundled interpreter directly. Pip/uv's console
    # entry points contain absolute build-time interpreter paths.
    if target == "windows":
        scripts = python / "Scripts"
        if scripts.is_dir():
            for wrapper in scripts.glob("*.exe"):
                # distlib console launchers embed a shebang before their zip
                # payload. Keep independent executables installed by a wheel.
                with wrapper.open("rb") as stream:
                    launcher = re.search(rb"#![^\n]+\nPK\x03\x04", stream.read(512 * 1024))
                if launcher:
                    wrapper.unlink()
    else:
        for item in (python / "bin").iterdir():
            if item.is_file() and not item.is_symlink():
                with item.open("rb") as stream:
                    if stream.read(2) == b"#!":
                        item.unlink()
        for item in (python / "bin").iterdir():
            if item.is_symlink() and not item.exists():
                item.unlink()
    for record in python.rglob("direct_url.json"):
        if record.parent.suffix == ".dist-info":
            value = json.loads(record.read_text(encoding="utf-8"))
            if value.get("url", "").startswith("file:"):
                record.unlink()


def assemble(runtime, target, prepared, checkpoint, license_file, scratch):
    runtime.mkdir(parents=True)
    if prepared:
        for name in ("python", "ComfyUI-src"):
            source = prepared / name
            if not source.is_dir() or source.is_symlink():
                raise ValueError(f"Prepared runtime missing its own {name}/")
            if name == "ComfyUI-src":
                copy_prepared_comfy(source, runtime / name)
            else:
                copy_tree(source, runtime / name)
        python_source = {"input": "prepared"}
        if checkpoint is None:
            checkpoint = prepared / MODEL_PATH
        if license_file is None:
            license_file = prepared / "licenses/HUNYUAN-LICENSE"
    else:
        python_source = prepare_python(runtime, target, scratch)
        unpack_download(COMFY_URL, COMFY_SHA, "ComfyUI-" + BACKEND, runtime / "ComfyUI-src", scratch)

    validate_links(runtime)
    if (runtime / "python/pyvenv.cfg").exists():
        raise ValueError("Use a relocatable CPython distribution for this interpreter.")
    verify_comfy(runtime / "ComfyUI-src")
    strip_build_launchers(runtime / "python", target)
    validate_links(runtime / "python")
    model = runtime / MODEL_PATH
    model.parent.mkdir(parents=True)
    if checkpoint is None:
        download(MODEL_URL, model, MODEL_SHA, MODEL_SIZE)
    else:
        if checkpoint.stat().st_size != MODEL_SIZE:
            raise ValueError(f"Expected {MODEL_SIZE} bytes in {checkpoint.name}.")
        copy_file(checkpoint.resolve(strict=True), model)
    if model.stat().st_size != MODEL_SIZE:
        raise ValueError("Unexpected model byte length.")
    require_hash(model, MODEL_SHA)
    licenses = runtime / "licenses"
    licenses.mkdir()
    license_out = licenses / "HUNYUAN-LICENSE"
    if license_file is None:
        download(MODEL_BASE + "LICENSE", license_out, LICENSE_SHA)
    else:
        copy_file(license_file.resolve(strict=True), license_out)
        require_hash(license_out, LICENSE_SHA)
    notice = licenses / "HUNYUAN-NOTICE"
    copy_file(RECIPE / "HUNYUAN-NOTICE", notice)
    require_hash(notice, NOTICE_SHA)
    (licenses / "Notice.txt").write_text(TENCENT_ATTRIBUTION + "\n", encoding="utf-8")
    write_json(runtime / "config.json", CONFIG)
    (runtime / "model_paths.yaml").write_text(MODEL_PATHS, encoding="utf-8")
    return {
        "model": {"url": MODEL_URL, "sha256": MODEL_SHA, "bytes": MODEL_SIZE, "revision": MODEL_REVISION},
        "backend": {"url": COMFY_URL, "revision": BACKEND, "server_source_sha256": COMFY_TREE},
        "python": python_source,
        "notices": [
            "licenses/HUNYUAN-LICENSE",
            "licenses/HUNYUAN-NOTICE",
            "licenses/Notice.txt",
            "ComfyUI-src/LICENSE",
            "python/",
        ],
    }


def copy_editor(editor, staged, target):
    if target == "macos":
        app = editor.is_dir() and editor.suffix == ".app"
        if not app:
            editor_native_app.native_executable(editor)
        template = editor if app else Path(__file__).resolve().parents[1] / "misc/dist/macos_tools.app"
        editor_native_app.copy_app(template, staged)
        validate_links(staged)
        info_path = staged / "Contents/Info.plist"
        with info_path.open("rb") as stream:
            info = plistlib.load(stream)
        # The editor template predates the minimum OS of the ARM Torch wheels.
        minimum = info.get("LSMinimumSystemVersion", "0")
        info["LSMinimumSystemVersion"] = "14.0" if int(minimum.split(".")[0]) < 14 else minimum
        arch_minimum = info.setdefault("LSMinimumSystemVersionByArchitecture", {})
        if int(arch_minimum.get("arm64", "0").split(".")[0]) < 14:
            arch_minimum["arm64"] = info["LSMinimumSystemVersion"]
        with info_path.open("wb") as stream:
            plistlib.dump(info, stream)
        executable = info["CFBundleExecutable"]
        if not executable or Path(executable).name != executable or executable in (".", ".."):
            raise ValueError("Invalid CFBundleExecutable.")
        binary = staged / "Contents/MacOS" / executable
        if not app:
            binary.parent.mkdir(parents=True, exist_ok=True)
            binary.unlink(missing_ok=True)
            copy_file(editor, binary)
            package = installed_package(editor)
            if package.is_file():
                copy_file(package, installed_package(binary))
        editor_native_app.native_executable(binary)
        subprocess.run(["/usr/bin/lipo", str(binary), "-verify_arch", "arm64"], check=True)
        return binary
    directory = editor if editor.is_dir() else editor.parent
    if editor.is_dir():
        candidates = [p for p in directory.glob("*.exe") if not p.name.lower().endswith(".console.exe")]
        standard = directory / "godot.windows.editor.x86_64.exe"
        if standard.is_file():
            editor = standard
        elif len(candidates) == 1:
            editor = candidates[0]
        else:
            raise ValueError("Specify the editor .exe inside its Windows distribution directory.")
    with editor.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise ValueError("Missing Windows editor executable.")
        stream.seek(0x3C)
        stream.seek(int.from_bytes(stream.read(4), "little"))
        if stream.read(6) != b"PE\x00\x00\x64\x86":
            raise ValueError("An x86-64 Windows PE editor executable is required.")

    def ignore_native(folder, names):
        ignored = ignore_cache(folder, names)
        if Path(folder) == directory:
            ignored.append("maliang-hunyuan")
            if directory.name == "bin" and (directory.parent / "SConstruct").is_file():
                ignored.extend(("obj", "build_deps"))
        return ignored

    copy_tree(directory, staged, ignore_native)
    validate_links(staged)
    return staged / editor.name


def sign_app(app, identity, *, from_template):
    details = subprocess.run(["/usr/bin/codesign", "--display", "--verbose=4", str(app)], capture_output=True)
    lines = details.stderr.decode(errors="replace").splitlines()
    prior = next((line.partition("=")[2] for line in lines if line.startswith("Authority=")), None)
    if identity is None:
        if details.returncode == 0 and prior is None and "Signature=adhoc" not in lines:
            raise ValueError("An existing signing identity could not be determined. Supply --sign-identity.")
        identity = prior or "-"
    for attribute in ("com.apple.FinderInfo", "com.apple.ResourceFork"):
        subprocess.run(["/usr/bin/xattr", "-drs", attribute, str(app)], check=True)
    command = ["/usr/bin/codesign", "--force", "--sign", identity]
    if from_template:
        # Godot's stock bundle has auxiliary Info_*.plists under Contents.
        # They are nested code to codesign and have no seals in the raw template.
        command.append("--deep")
    if details.returncode == 0:
        command.append("--preserve-metadata=identifier,entitlements,flags,runtime")
    subprocess.run(command + [str(app)], check=True)
    subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)], check=True)


@contextmanager
def publication_lock(output):
    # Keep the lock inode stable across builders and process crashes.
    with output.with_name("." + output.name + ".maliang-lock").open("a+b") as lock:
        if os.name == "nt":
            import msvcrt

            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def is_distribution(path, target):
    config = resource_path(path, target) / "config.json"
    if path.is_symlink() or not config.is_file() or config.resolve() != config:
        return False
    return json.loads(config.read_text(encoding="utf-8")).get("distribution") == DISTRIBUTION


def publish(staged, output, target, verify=None):
    with publication_lock(output):
        backup = output.with_name("." + output.name + ".maliang-previous")
        if backup.exists():
            if not is_distribution(backup, target):
                raise ValueError(f"Previous-output recovery path is occupied: {backup}")
            if output.exists():
                shutil.rmtree(backup)
            else:
                backup.rename(output)
        if output.exists():
            if not is_distribution(output, target):
                raise ValueError(f"Output already exists and is not a Maliang distribution: {output}")
            output.rename(backup)
        try:
            staged.rename(output)
            if verify:
                verify(output)
        except BaseException:
            if not staged.exists() and output.exists():
                output.rename(staged)
            if backup.exists():
                backup.rename(output)
            raise
        if backup.exists():
            try:
                shutil.rmtree(backup)
            except OSError as error:
                # Publication already succeeded. A locked old Windows DLL can
                # be cleaned on a later run without undoing the verified output.
                print(f"Previous distribution cleanup pending at {backup}: {error}", file=sys.stderr)


def build(args):
    target = platform_name()
    editor = args.editor.resolve(strict=True)
    output = args.output.absolute()
    if output.is_symlink():
        raise ValueError("The output must be a new directory or a previous distribution.")
    output = output.resolve()
    if target == "macos" and output.suffix != ".app":
        raise ValueError("The macOS output must end in .app.")
    if target == "windows" and output.suffix.lower() == ".exe":
        raise ValueError("The Windows output is a directory.")
    if target != "macos" and args.sign_identity:
        raise ValueError("--sign-identity applies to macOS builds.")
    prepared = args.runtime.resolve(strict=True) if args.runtime else None
    inputs = [editor if target == "macos" or editor.is_dir() else editor.parent]
    inputs.extend(p.resolve(strict=True) for p in (prepared, args.checkpoint, args.license) if p)
    for source in inputs:
        if output.is_relative_to(source) or source.is_relative_to(output):
            raise ValueError("Keep build inputs and output in separate locations.")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage_parent = output.parent
    if target == "macos":
        # iCloud-managed Documents attaches Finder metadata while signing.
        # Stage in the local temporary directory when final rename is same-volume.
        local = Path(tempfile.gettempdir()).resolve()
        if local.stat().st_dev == output.parent.stat().st_dev:
            stage_parent = local
    with tempfile.TemporaryDirectory(dir=stage_parent, prefix=".maliang-build-") as stage:
        scratch = Path(stage)
        staged = scratch / "assembled" / output.name
        staged.parent.mkdir()
        copy_editor(editor, staged, target)
        runtime = resource_path(staged, target)
        if runtime.is_symlink() or runtime.parent.resolve() != runtime.parent:
            raise ValueError("Invalid runtime destination in the source editor.")
        if runtime.exists():
            shutil.rmtree(runtime)
        sources = assemble(runtime, target, prepared, args.checkpoint, args.license, scratch)
        if target == "windows":
            sources["microsoft_visual_cpp"] = install_windows_crt(runtime, scratch)
            sources["notices"].append("licenses/Microsoft-VC-Redist-sources.json")

        # Moving even a prebuilt copy before import catches build-time prefix dependencies.
        moved = scratch / "Relocated editor" / staged.name
        moved.parent.mkdir()
        staged.rename(moved)
        runtime = resource_path(moved, target)
        environment = dict(
            os.environ,
            HF_HUB_OFFLINE="1",
            TRANSFORMERS_OFFLINE="1",
            HF_HUB_DISABLE_TELEMETRY="1",
            PYTORCH_ENABLE_MPS_FALLBACK="1",
        )
        result = subprocess.run(
            [str(python_path(runtime, target)), "-I", "-B", str(RECIPE / "probe.py"), str(runtime), target],
            cwd=scratch,
            env=environment,
            check=True,
            stdout=subprocess.PIPE,
            encoding="utf-8",
        )
        sources["installed"] = json.loads(result.stdout)
        write_json(runtime / "sources.json", sources)
        if target == "macos":
            sign_app(moved, args.sign_identity, from_template=editor.is_file())
        verify = editor_native_app.verify_signature if target == "macos" else None
        publish(moved, output, target, verify)
    print(output, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--editor", type=Path, required=True, help="Mach-O, complete .app, Windows directory or its editor .exe"
    )
    parser.add_argument("--output", type=Path, required=True, help="Destination .app or Windows directory")
    parser.add_argument("--runtime", type=Path, help="Reuse a prepared runtime with python/ and ComfyUI-src/")
    parser.add_argument("--checkpoint", type=Path, help="Reuse the official fp16 mini checkpoint")
    parser.add_argument("--license", type=Path, help="Reuse the license from the pinned Tencent revision")
    parser.add_argument(
        "--sign-identity", help="macOS codesign identity (default: preserve source signer, else ad hoc)"
    )
    build(parser.parse_args())


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
