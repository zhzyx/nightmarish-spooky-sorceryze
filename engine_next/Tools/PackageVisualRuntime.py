"""Package the audited visual executable and its exact offline shader outputs."""

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

SHADER_FILES = {
    "FixedMesh.vs.cso",
    "FixedMesh.ps.cso",
    "FixedMesh.cs.cso",
    "Deferred.vs.cso",
    "Deferred.ps.cso",
    "Lighting.vs.cso",
    "Lighting.ps.cso",
    "ToneMap.ps.cso",
    "Shadow.vs.cso",
    "Shadow.ps.cso",
    "Temporal.cs.cso",
    "Histogram.cs.cso",
    "Exposure.cs.cso",
    "BloomDown.cs.cso",
    "BloomUp.cs.cso",
    "ReflectionLighting.ps.cso",
    "ReflectionColor.cs.cso",
    "ReflectionTrace.cs.cso",
    "ReflectionComposite.cs.cso",
    "ReflectionRadiance.cs.cso",
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replace_directory(source, destination):
    # Windows scanners can briefly hold a newly copied executable without delete sharing.
    for attempt in range(20):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if os.name != "nt" or attempt == 19:
                raise
            time.sleep(0.1)


def create_package(repo, build_dir):
    repo = Path(repo).resolve()
    build_dir = Path(build_dir).resolve()
    build_dir.relative_to(repo / "build/engine_next")
    report = json.loads((build_dir / "VisualBuildReport.json").read_text(encoding="utf-8"))
    targets = [target for target in report["targets"] if target["name"] == "next_visual_client"]
    if len(targets) != 1:
        raise ValueError("Expected one audited visual executable")
    target = targets[0]
    if target["symbol_audit"]["forbidden"] or not target["contract"]["passed"]:
        raise ValueError("Visual target audits failed")
    sources = [target["artifact"], *report["shaders"]]
    expected = {"next_visual_client.exe", *SHADER_FILES}
    if len(sources) != len(expected) or {Path(item["path"]).name for item in sources} != expected:
        raise ValueError("Visual package requires exactly one executable and all declared shader stages")
    manifest_source = repo / target["manifest"]
    if digest(manifest_source) != target["manifest_sha256"]:
        raise ValueError("Visual link manifest differs from its build report")
    source_entries = []
    for item in sources:
        source = repo / item["path"]
        if source.is_symlink():
            raise ValueError("Linked visual output is not allowed")
        source = source.resolve()
        source.relative_to(build_dir)
        if source.is_symlink() or not source.is_file() or digest(source) != item["sha256"]:
            raise ValueError("Visual output differs from its build report: " + source.name)
        source_entries.append((source, item))
    output = build_dir / "Release"
    if output.exists():
        previous_path = output / "VisualPackage.json"
        if output.is_symlink() or not previous_path.is_file():
            raise ValueError("Existing visual package directory is unowned")
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
        previous_files = {item["path"] for item in previous.get("files", [])} | {"VisualPackage.json"}
        if {path.name for path in output.iterdir()} != previous_files or any(
            path.is_symlink() or not path.is_file() for path in output.iterdir()
        ):
            raise ValueError("Existing visual package contains unexpected files")
        for item in previous["files"]:
            if Path(item["path"]).name != item["path"] or digest(output / item["path"]) != item["sha256"]:
                raise ValueError("Existing visual package has modified files")
    staging = Path(tempfile.mkdtemp(prefix=".visual-package-", dir=build_dir))
    backup = staging.with_name(staging.name + "-previous")
    try:
        entries = []
        for source, item in source_entries:
            destination = staging / source.name
            shutil.copy2(source, destination)
            if digest(destination) != item["sha256"]:
                raise ValueError("Visual output changed during packaging: " + source.name)
            entries.append({"path": source.name, "sha256": digest(destination), "bytes": destination.stat().st_size})
        licenses = {
            "LICENSE.txt": "LICENSE.txt",
            "ENet-LICENSE.txt": "engine_next/thirdparty/enet/LICENSE",
            "zlib-LICENSE.txt": "engine_next/thirdparty/zlib/LICENSE",
            "libjpeg-turbo-LICENSE.md": "engine_next/thirdparty/libjpeg-turbo/LICENSE.md",
            "libjpeg-turbo-README.ijg": "engine_next/thirdparty/libjpeg-turbo/README.ijg",
        }
        for name, path in licenses.items():
            license_source = repo / path
            shutil.copy2(license_source, staging / name)
            entries.append({
                "path": name,
                "sha256": digest(staging / name),
                "bytes": license_source.stat().st_size,
            })
        manifest = {
            "schema_version": 1,
            "target": "EngineNextVisualPackage",
            "native_key": report["native_key"],
            "compiler": report["compiler"],
            "platform": report["platform"],
            "files": entries,
            "producer_manifest": target["manifest"],
            "producer_manifest_sha256": digest(manifest_source),
            "symbol_audit": target["symbol_audit"],
            "dynamic_dependencies": target["dynamic_dependencies"],
            "godot_runtime_dependencies": [],
        }
        (staging / "VisualPackage.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        if output.exists():
            replace_directory(output, backup)
        try:
            replace_directory(staging, output)
        except OSError:
            if backup.exists():
                replace_directory(backup, output)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return {
        "directory": output,
        "manifest": output / "VisualPackage.json",
        "files": sorted(path.name for path in output.iterdir()),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--build-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    directory = args.build_dir if args.build_dir.is_absolute() else args.repo / args.build_dir
    try:
        result = create_package(args.repo, directory)
        print(json.dumps({"passed": True, "manifest": str(result["manifest"]), "files": result["files"]}, indent=2))
        return 0
    except (OSError, ValueError) as error:
        print(json.dumps({"passed": False, "error": str(error)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
