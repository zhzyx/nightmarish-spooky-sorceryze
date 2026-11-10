"""Exercise the commit-to-SCons route on a disposable checkout of the candidate."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "servers/rendering/instance_uniforms.cpp"
METAL = "drivers/metal/metal_objects_shared.cpp"
METAL_FX = "servers/rendering/renderer_rd/effects/metal_fx.cpp"
BMP = "modules/bmp/image_loader_bmp.cpp"


def git(root, *args):
    subprocess.run(
        ["git", "-c", "user.name=Scope test", "-c", "user.email=test@localhost", *args], cwd=root, check=True
    )


def verify(root, platform, flags, expected_sources):
    command = [
        sys.executable,
        "tools/build_engine_modules.py",
        "--base",
        "HEAD^",
        "--committed",
        "--ci-platform",
        platform,
        "--build",
        "--defer-full",
        "--",
        *flags,
    ]
    run = subprocess.run(
        command,
        cwd=root,
        env={**os.environ, "NO_COLOR": "1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    print(run.stdout, flush=True)
    run.check_returncode()
    log = run.stdout.replace("\\", "/")
    result = json.loads(run.stdout.splitlines()[-1])
    assert result["mode"] == ("modules" if expected_sources else "skip"), result
    assert result["sources"] == sorted(expected_sources), result
    if expected_sources:
        # Run in a cold tree and check the actual compiler actions, including platform-specific sources.
        for source in expected_sources:
            assert "Compiling " + source in log, source
        assert "Linking Program" not in log and "Linking Static Library bin/obj/servers/libservers" not in log
    else:
        assert "Building for platform" not in run.stdout


def main():
    platform, *flags = sys.argv[1:]
    if platform not in ("windows", "metal"):
        raise ValueError("expected a Windows or Metal CI worker")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        git(ROOT, "clone", "--quiet", "--shared", "--local", str(ROOT), str(root))
        with (root / "README.md").open("a", encoding="utf-8") as doc:
            doc.write("\nScope test.\n")
        git(root, "commit", "-qam", "Documentation only")
        verify(root, platform, flags, [])
        # Each worker sees the exact same cross-platform change set.
        for name in (SOURCE, BMP, METAL, METAL_FX):
            with (root / name).open("a", encoding="utf-8") as file:
                file.write("\n// Compile-scope test.\n")
        git(root, "commit", "-qam", "Render service, image module and Metal implementation")
        verify(root, platform, flags, [METAL, METAL_FX] if platform == "metal" else [SOURCE, BMP, METAL_FX])


if __name__ == "__main__":
    main()
