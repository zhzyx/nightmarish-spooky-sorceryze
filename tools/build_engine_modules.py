"""Plan or run an incremental Godot build from the project root."""

import argparse
import json
import os
import re
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
        if (
            modified
            and len(path.parts) >= 3
            and path.parts[0] == "modules"
            and re.fullmatch(r"[a-z0-9_]+", path.parts[1])
            and path.suffix in {".c", ".cc", ".cpp", ".cxx", ".m", ".mm"}
            and path.stem != "register_types"
            and "tests" not in path.parts
        ):
            sources.add(name)
        else:
            return "full", [], name
    return ("modules" if sources else "skip"), sorted(sources), ""


def build(sources, flags):
    scons = [sys.executable, "-m", "SCons"]
    with tempfile.TemporaryDirectory() as directory:
        inventory = Path(directory) / "inputs.json"
        try:
            subprocess.run([*scons, "-n", "-Q", *flags, f"module_build_inventory={inventory}"], check=True)
            inputs = json.loads(inventory.read_text(encoding="utf-8"))
        except (subprocess.CalledProcessError, OSError, ValueError) as error:
            return "full", f"SCons module inventory unavailable: {error}"
        if not isinstance(inputs, dict) or not all(isinstance(paths, list) for paths in inputs.values()):
            return "full", "invalid SCons module inventory"
    targets = set()
    for name in sources:
        module = PurePosixPath(name).parts[1]
        if name not in inputs.get(module, ()):
            return "full", name
        targets.add("module-" + module)
    subprocess.run([*scons, *flags, *sorted(targets)], check=True)
    return "modules", ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="Git revision to compare with the current checkout")
    parser.add_argument("--new-branch-base", help="default branch ref for a first push with an all-zero before SHA")
    parser.add_argument("--committed", action="store_true", help="compare the base to HEAD (CI clean checkout)")
    parser.add_argument("--build", action="store_true", help="run the selected build (default: print the plan)")
    parser.add_argument(
        "--defer-full", action="store_true", help="report full builds for the existing CI matrix to run"
    )
    parser.add_argument("flags", nargs="*", help="SCons configuration and options after --")
    args = parser.parse_args()
    os.chdir(Path(__file__).resolve().parents[1])
    revision = ""
    try:
        if args.base == "0" * 40 and args.new_branch_base:
            revision = git("merge-base", args.new_branch_base, "HEAD").decode().strip()
        elif args.base and args.base.strip("0"):
            revision = git("rev-parse", "--verify", "--end-of-options", args.base + "^{commit}").decode().strip()
        else:
            raise ValueError("missing base")
        mode, sources, reason = plan(changes(revision, args.committed))
    except (subprocess.CalledProcessError, ValueError):
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


if __name__ == "__main__":
    main()
