"""Private self-contained editor copies; never fall back to the user's executable.

macos_editor leaves other platforms' existing runner behavior intact. copy_editor
also serves runners which already require a private executable on every platform.
A bare executable is supported; application bundles must be unpacked explicitly.
Each copy requires its full logical size plus 64 MiB free, even on cloneable APFS.
The caller owns the enclosing TemporaryDirectory and its cleanup/lifetime.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

RESERVE_BYTES = 64 * 1024 * 1024


def copy_editor(source, directory):
    source = Path(source).resolve(strict=True)
    directory = Path(directory).absolute()
    if not source.is_file() or not os.access(source, os.X_OK):
        raise ValueError("Editor source must be an executable file")
    if any(part.endswith(".app") for part in source.parts):
        raise ValueError("Application bundles are unsupported; supply a bare editor executable")
    if directory.exists() or directory.is_symlink():
        raise ValueError("Isolation directory must be new")
    parent = directory.parent.resolve(strict=True)
    if directory.parent.is_symlink() or not parent.is_dir():
        raise ValueError("Isolation parent must be an existing directory without symlinks")
    directory = parent / directory.name
    required = source.stat().st_size + RESERVE_BYTES
    if shutil.disk_usage(parent).free < required:
        raise OSError(f"Insufficient isolation capacity: need {required} free bytes (editor plus 64 MiB reserve)")
    directory.mkdir()
    target = directory / source.name
    try:
        cloned = False
        if sys.platform == "darwin":
            result = subprocess.run(["/bin/cp", "-c", str(source), str(target)], capture_output=True)
            cloned = result.returncode == 0
        if not cloned:
            target.unlink(missing_ok=True)
            shutil.copy2(source, target)
        if target.stat().st_size != source.stat().st_size or target.samefile(source):
            raise OSError("Editor copy is incomplete or aliases its source")
        (directory / "_sc_").touch(exist_ok=False)
        (directory / "editor_data").mkdir()
        return target
    except BaseException:
        shutil.rmtree(directory)
        raise


def macos_editor(source, directory):
    """Isolate macOS; preserve the original non-macOS launch path."""
    return copy_editor(source, directory) if sys.platform == "darwin" else Path(source).resolve(strict=True)
