"""Export only Engine Next build inputs into a physically Godot-free source tree."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

TOOL_FILES = [
    "tools/check_engine_next_contract.py",
    "tools/engine_next_contract.json",
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_files(repo):
    files = []
    for path in sorted((repo / "engine_next").rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise ValueError("Clean source export does not accept symlinks: " + str(path))
        files.append(path.relative_to(repo).as_posix())
    files.extend(TOOL_FILES)
    return sorted(files)


def export_clean_source(repo, output):
    repo = Path(repo).resolve()
    output = Path(output).resolve()
    output.relative_to(repo / "build/engine_next")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Clean source output must not exist or must be empty: " + str(output))
    inputs = source_files(repo)
    for relative in inputs:
        source = repo / relative
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    manifest = {
        "schema_version": 1,
        "source_root": output.name,
        "file_count": len(inputs),
        "files": [{"path": relative, "sha256": digest(repo / relative)} for relative in inputs],
        "godot_roots_present": [],
    }
    manifest_path = output.with_name(output.name + "Manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"root": output, "manifest": manifest_path, "file_count": len(inputs)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.output.is_absolute():
        args.output = args.repo / args.output
    try:
        result = export_clean_source(args.repo, args.output)
        print(json.dumps({
            "passed": True,
            "root": str(result["root"]),
            "manifest": str(result["manifest"]),
            "file_count": result["file_count"],
        }, indent=2))
    except (OSError, ValueError) as error:
        print(json.dumps({"passed": False, "error": str(error)}, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
