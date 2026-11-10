"""Plan or run an incremental Godot build from the project root."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath


def git(*args):
    return subprocess.check_output(["git", *args])


def changes(revision, committed):
    fields = git(
        "diff",
        "--raw",
        "--no-renames",
        "--ignore-submodules=none",
        "-z",
        revision,
        *(["HEAD"] if committed else []),
        "--",
    ).split(b"\0")
    for header, path in zip(fields[::2], fields[1::2]):
        old, new, _, _, status = header[1:].split()
        yield os.fsdecode(path), status == b"M" and old == new == b"100644"
    if not committed:
        for path in git("ls-files", "--others", "--exclude-standard", "-z").split(b"\0"):
            if path:
                yield os.fsdecode(path), False


# Only regular implementation edits may use a target from the configured graph.
# Headers, registration, generators, additions and removals retain integration coverage.
def implementation(path, modified):
    return (
        modified
        and (
            path.parts[0] in {"modules", "core", "scene", "servers", "editor", "drivers"}
            or path.parts[:2] == ("thirdparty", "metal-cpp")
        )
        and path.suffix in {".c", ".cc", ".cpp", ".cxx", ".m", ".mm"}
        and not path.stem.startswith("register_")
        and "tests" not in path.parts
    )


def plan(files):
    sources = set()
    for name, modified in files:
        path = PurePosixPath(name)
        if name in {"README.md", "AGENTS.md", "CONTRIBUTING.md"}:
            continue
        if path.parts[0] == "design-docs" and path.suffix == ".md":
            continue
        if path.parts[0] in {"data-collection", "gonggong-diting-data"} and path.suffix in {".json", ".jsonl", ".md"}:
            continue
        if implementation(path, modified):
            sources.add(name)
        else:
            return "full", [], name
    return ("modules" if sources else "skip"), sorted(sources), ""


# Metal's bundled libraries and include roots in drivers/metal/SCsub also need
# Apple verification. Shared third-party changes retain their Windows coverage.
METAL_PRIVATE = ("drivers/metal/", "thirdparty/metal-cpp/")
METAL_INPUTS = (
    *METAL_PRIVATE,
    "thirdparty/offset_allocator/",
    "thirdparty/spirv-cross/",
    "thirdparty/spirv-headers/",
)


METAL_MARKERS = ("METAL_ENABLED", '"drivers/metal/', "<MetalFX/")
D3D12_MARKERS = ("D3D12_ENABLED", '"drivers/d3d12/')


def conditional_consumers(files, revision, committed, markers):
    """Find backend-specific code on either side, including removed guards."""
    names = [
        name
        for name, _ in files
        if PurePosixPath(name).parts[0] in {"core", "scene", "servers", "drivers", "modules", "editor", "platform"}
        and PurePosixPath(name).suffix in {".cpp", ".c", ".cc", ".cxx", ".m", ".mm", ".h", ".hpp", ".inc", ".inl"}
    ]
    matches = set()
    for offset in range(0, len(names), 64):
        paths = names[offset : offset + 64]
        for tree in (revision, "HEAD" if committed else None):
            args = [
                "git",
                "--literal-pathspecs",
                "grep",
                "--full-name",
                "-IlzF",
                *(arg for marker in markers for arg in ("-e", marker)),
                *([tree] if tree else ["--untracked"]),
                "--",
                *paths,
            ]
            result = subprocess.run(args, stdout=subprocess.PIPE)
            if result.returncode not in (0, 1):  # 1 means there were no matches.
                raise subprocess.CalledProcessError(result.returncode, args)
            for entry in result.stdout.split(b"\0"):
                if entry:
                    path = os.fsdecode(entry)
                    matches.add(path.removeprefix(tree + ":") if tree else path)
    return matches


def platform_plan(files, platform, shared_metal=()):
    metal = [(name, modified) for name, modified in files if name.startswith(METAL_INPUTS) or name in shared_metal]
    if platform == "windows":
        return plan(
            (name, modified)
            for name, modified in files
            if not (name.startswith(METAL_PRIVATE) and implementation(PurePosixPath(name), modified))
        )
    if platform == "metal":
        if not metal:
            return "skip", [], ""
        mode, _, reason = plan(files)
        if mode == "full":
            return mode, [], reason
        return plan(metal)
    return plan(files)


def build(sources, flags):
    scons = [sys.executable, "-m", "SCons"]
    with tempfile.TemporaryDirectory() as directory:
        inventory = Path(directory) / "inputs.json"
        objects = Path(directory) / "objects.json"
        probe = [*scons, "-n", "-Q", *flags, f"module_build_inventory={inventory}"]
        need_objects = any(not name.startswith("modules/") for name in sources)
        if need_objects:
            probe.append(f"engine_object_inventory={objects}")
        try:
            subprocess.run(probe, check=True)
            inputs = json.loads(inventory.read_text(encoding="utf-8"))
            object_targets = json.loads(objects.read_text(encoding="utf-8")) if need_objects else {}
        except (subprocess.CalledProcessError, OSError, ValueError) as error:
            return "full", f"SCons module inventory unavailable: {error}"
        if not all(
            isinstance(mapping, dict)
            and all(
                isinstance(paths, list) and all(isinstance(path, str) for path in paths) for paths in mapping.values()
            )
            for mapping in (inputs, object_targets)
        ):
            return "full", "invalid SCons module inventory"
    targets = set()
    for name in sources:
        if name.startswith("modules/"):
            module = PurePosixPath(name).parts[1]
            if name not in inputs.get(module, ()):
                return "full", name
            targets.add("module-" + module)
        elif object_targets.get(name):
            targets.update(object_targets[name])
        else:
            return "full", name
    print("Selected SCons targets:", *sorted(targets), flush=True)
    subprocess.run([*scons, *flags, *sorted(targets)], check=True)
    return "modules", ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="Git revision to compare with the current checkout")
    parser.add_argument("--new-branch-base", help="default branch ref for a first push with an all-zero before SHA")
    parser.add_argument("--committed", action="store_true", help="compare the base to HEAD (CI clean checkout)")
    parser.add_argument("--ci-platform", choices=["windows", "metal"], help="limit the plan to this CI worker")
    parser.add_argument("--build", action="store_true", help="run the selected build (default: print the plan)")
    parser.add_argument(
        "--defer-full", action="store_true", help="report full builds for the existing CI matrix to run"
    )
    parser.add_argument("flags", nargs="*", help="SCons configuration and options after --")
    args = parser.parse_args()
    os.chdir(Path(__file__).resolve().parents[1])
    revision = ""
    files = []
    has_metal = False
    needs_d3d12 = False
    try:
        if args.base == "0" * 40 and args.new_branch_base:
            revision = git("merge-base", args.new_branch_base, "HEAD").decode().strip()
        elif args.base and args.base.strip("0"):
            revision = git("rev-parse", "--verify", "--end-of-options", args.base + "^{commit}").decode().strip()
        else:
            raise ValueError("missing base")
        files = list(changes(revision, args.committed))
        shared_metal = (
            conditional_consumers(files, revision, args.committed, METAL_MARKERS) if args.ci_platform else set()
        )
        has_metal = bool(shared_metal) or any(name.startswith(METAL_INPUTS) for name, _ in files)
        mode, sources, reason = platform_plan(files, args.ci_platform, shared_metal)
        if args.ci_platform == "windows" and mode == "modules":
            needs_d3d12 = any(source.startswith("drivers/d3d12/") for source in sources) or bool(
                conditional_consumers([(source, True) for source in sources], revision, args.committed, D3D12_MARKERS)
            )
    except (subprocess.CalledProcessError, ValueError):
        has_metal = True  # Neither platform can be excluded without a reliable comparison.
        mode, sources, reason = "full", [], "git comparison unavailable"
    if args.build and mode == "modules":
        mode, reason = build(sources, args.flags)
    if mode == "full" and args.build and not args.defer_full:
        subprocess.run([sys.executable, "-m", "SCons", *args.flags], check=True)
    print(json.dumps({"mode": mode, "sources": sources, "reason": reason}))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            print(f"build-mode={mode}", file=output)
            print(f"build-base={revision}", file=output)
            print(f"has-metal={str(has_metal).lower()}", file=output)
            print(f"needs-d3d12={str(needs_d3d12).lower()}", file=output)


if __name__ == "__main__":
    main()
