"""Create and audit a minimal standalone Engine Next runtime package."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def create_package(repo, build_dir):
    repo = Path(repo).resolve()
    build_dir = Path(build_dir).resolve()
    build_dir.relative_to(repo / "build/engine_next")
    report = json.loads((build_dir / "RuntimeBuildReport.json").read_text(encoding="utf-8"))
    output = build_dir / "Release"
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    artifacts = []
    for target in report["targets"]:
        if target["name"] not in {"next_server", "next_client"}:
            continue
        artifact = target["artifact"]
        source = repo / artifact["path"]
        if digest(source) != artifact["sha256"]:
            raise ValueError("Runtime binary differs from its build report: " + str(source))
        destination = output / source.name
        shutil.copy2(source, destination)
        producer = repo / target["manifest"]
        artifacts.append({
            "path": destination.name,
            "sha256": digest(destination),
            "bytes": destination.stat().st_size,
            "producer_manifest": producer.relative_to(repo).as_posix(),
            "producer_manifest_sha256": digest(producer),
            "symbol_audit": target["symbol_audit"],
            "dynamic_dependencies": target["dynamic_dependencies"],
        })
    if len(artifacts) != 2:
        raise ValueError("Expected exactly one server and one client")
    shutil.copy2(repo / "engine_next/thirdparty/enet/LICENSE", output / "ENet-LICENSE.txt")
    manifest = {
        "schema_version": 1,
        "target": "EngineNextStandalonePackage",
        "compiler": report["compiler"],
        "platform": report["platform"],
        "sanitize": report["sanitize"],
        "native_key": report["native_key"],
        "artifacts": artifacts,
        "support_files": [{"path": "ENet-LICENSE.txt", "sha256": digest(output / "ENet-LICENSE.txt")}],
        "godot_free_package": True,
    }
    manifest_path = output / "RuntimePackage.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    forbidden_suffixes = {".pck", ".tscn", ".tres", ".gd", ".godot", ".cs", ".gdextension"}
    allowed_names = {item["path"] for item in artifacts} | {"ENet-LICENSE.txt", "RuntimePackage.json"}
    for path in output.iterdir():
        if (
            not path.is_file()
            or path.name not in allowed_names
            or path.suffix.lower() in forbidden_suffixes
            or "godot" in path.name.lower()
        ):
            raise ValueError("Unexpected or Godot-related package file: " + str(path))
    return {
        "manifest": manifest_path,
        "files": sorted(path.name for path in output.iterdir()),
        "directory": output,
        "godot_free_package": True,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--build-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.build_dir.is_absolute():
        args.build_dir = args.repo / args.build_dir
    try:
        result = create_package(args.repo, args.build_dir)
        print(
            json.dumps(
                {
                    "passed": True,
                    "manifest": str(result["manifest"]),
                    "files": result["files"],
                    "godot_free_package": result["godot_free_package"],
                },
                indent=2,
            )
        )
        return 0
    except (OSError, ValueError) as error:
        print(json.dumps({"passed": False, "error": str(error)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
