"""Exercise deterministic GPU-package publication and validation through next_asset."""

import argparse
import filecmp
import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def snapshot(root):
    entries = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise RuntimeError("Acceptance fixtures must contain ordinary files and directories")
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            entries.append({"path": relative + "/", "kind": "directory"})
        elif path.is_file():
            entries.append({
                "path": relative,
                "kind": "file",
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            })
        else:
            raise RuntimeError("Acceptance fixtures contain an unsupported filesystem entry")
    return entries


def run(binary, arguments, operation, evidence, success=True, diagnostic=None):
    completed = subprocess.run(
        [str(binary), *map(str, arguments)], capture_output=True, text=True, encoding="utf-8", timeout=120
    )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"{operation} returned invalid JSON, exit {completed.returncode}") from error
    entry = {"operation": operation, "exit_code": completed.returncode, "result": result}
    evidence.append(entry)
    if success:
        if completed.returncode != 0 or result.get("valid") is not True:
            raise RuntimeError(f"{operation} failed")
    else:
        codes = {item["code"] for item in result.get("diagnostics", [])}
        if completed.returncode != 1 or result.get("valid") is not False or not codes:
            raise RuntimeError(f"{operation} did not reject the invalid package")
        if diagnostic is not None and diagnostic not in codes:
            raise RuntimeError(f"{operation} returned an unexpected diagnostic")
    return result


def run_usage(binary, arguments, operation, evidence):
    completed = subprocess.run(
        [str(binary), *map(str, arguments)], capture_output=True, text=True, encoding="utf-8", timeout=120
    )
    evidence.append({"operation": operation, "exit_code": completed.returncode})
    if completed.returncode != 2:
        raise RuntimeError(f"{operation} did not reject invalid CLI usage")


def replace_page(package, payload):
    manifest_path = package / "GpuManifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    page = package / "blobs" / manifest["page_sha256"]
    page.unlink()
    digest = hashlib.sha256(payload).hexdigest()
    (package / "blobs" / digest).write_bytes(payload)
    manifest["page_sha256"] = digest
    manifest["page_bytes"] = len(payload)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")), encoding="utf-8")


def validate(binary, package, source_digest, operation, evidence, success=True, diagnostic=None):
    return run(
        binary,
        ["gpu-validate", "--package", package, "--source-digest", source_digest],
        operation,
        evidence,
        success,
        diagnostic,
    )


def exercise_scene(binary, fixtures, workspace, name):
    directory = fixtures / name
    work = workspace / name
    work.mkdir()
    commands = []
    source = directory / "Scene.enpak"
    source_origin = "existing_fixture_package"
    if not source.exists():
        source = work / "Source.enpak"
        source_origin = "compiled_fixture_request"
        run(
            binary,
            ["compile", "--request", directory / "BuildRequest.json", "--source-root", directory, "--output", source],
            "compile_source",
            commands,
        )
    before = snapshot(source)
    inspected = run(binary, ["inspect", "--package", source], "inspect_source", commands)
    digest = inspected["package_digest"]
    expected_instances = 12 if name == "B" else 6
    results = []
    for label in ("First", "Second"):
        destination = work / f"{label}.engpu"
        if destination.exists():
            raise RuntimeError("GPU cook requires a fresh output directory")
        run(binary, ["gpu-cook", "--package", source, "--output", destination], f"cook_{label.lower()}", commands)
        result = validate(binary, destination, digest, f"validate_{label.lower()}", commands)
        if result["package_digest"] != digest or result["scene_id"] != f"m4.bench.{name.lower()}":
            raise RuntimeError("GPU package lost its source identity")
        if result["instance_count"] != expected_instances:
            raise RuntimeError("GPU package lost a fixture mesh instance")
        results.append(snapshot(destination))
    if results[0] != results[1]:
        raise RuntimeError("Independent GPU cooks produced different bytes")
    for entry in results[0]:
        if entry["kind"] == "file" and not filecmp.cmp(
            work / "First.engpu" / entry["path"], work / "Second.engpu" / entry["path"], shallow=False
        ):
            raise RuntimeError("Independent GPU cooks failed byte comparison")
    original = work / "First.engpu"
    run(binary, ["gpu-cook", "--package", source, "--output", original], "reconcile_existing", commands)
    if snapshot(original) != results[0]:
        raise RuntimeError("Idempotent publication changed an existing GPU package")
    usage_cases = (
        ("duplicate_package", ["gpu-cook", "--package", source, "--package", source, "--output", original]),
        ("unused_request", ["gpu-cook", "--package", source, "--output", original, "--request", "unused.json"]),
        ("missing_cook_package", ["gpu-cook", "--output", original]),
        ("missing_cook_output", ["gpu-cook", "--package", source]),
        (
            "duplicate_source_digest",
            ["gpu-validate", "--package", original, "--source-digest", digest, "--source-digest", digest],
        ),
        ("unused_output", ["gpu-validate", "--package", original, "--source-digest", digest, "--output", "unused"]),
        ("missing_validate_package", ["gpu-validate", "--source-digest", digest]),
        ("missing_validate_digest", ["gpu-validate", "--package", original]),
    )
    for label, arguments in usage_cases:
        run_usage(binary, arguments, f"reject_usage_{label}", commands)
    if snapshot(original) != results[0]:
        raise RuntimeError("Rejected CLI usage changed an existing GPU package")
    wrong_digest = ("0" if digest[0] != "0" else "1") + digest[1:]
    validate(binary, original, wrong_digest, "reject_wrong_source", commands, False, "gpu_manifest")
    manifest = json.loads((original / "GpuManifest.json").read_text(encoding="utf-8"))
    page_path = Path("blobs") / manifest["page_sha256"]
    original_page = (original / page_path).read_bytes()
    mutations = (
        ("changed_page", bytes([original_page[0] ^ 1]) + original_page[1:], False),
        ("truncated_page", original_page[:-1], False),
        ("rehashed_changed_page", bytes([original_page[0] ^ 1]) + original_page[1:], True),
        ("rehashed_truncated_page", original_page[:-1], True),
    )
    for label, payload, rehash in mutations:
        damaged = work / f"{label}.engpu"
        shutil.copytree(original, damaged)
        if rehash:
            replace_page(damaged, payload)
        else:
            (damaged / page_path).write_bytes(payload)
        validate(binary, damaged, digest, f"reject_{label}", commands, False, "gpu_page")
    unknown = work / "UnknownFile.engpu"
    shutil.copytree(original, unknown)
    (unknown / "Unexpected.txt").write_bytes(b"unlisted fixture file\n")
    validate(binary, unknown, digest, "reject_unknown_file", commands, False, "gpu_package_files")
    after = snapshot(source)
    if before != after:
        raise RuntimeError("GPU cook or validation changed the original enpak")
    return {
        "scene": name,
        "source_origin": source_origin,
        "source_package_digest": digest,
        "source_files_before": before,
        "source_files_after": after,
        "source_unchanged": True,
        "gpu_package_files": results[0],
        "deterministic": True,
        "byte_comparison_equal": True,
        "idempotent": True,
        "invalid_cli_usage_rejected": True,
        "instance_count": expected_instances,
        "commands": commands,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--next-asset", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    binary = args.next_asset.resolve(strict=True)
    fixtures = args.fixtures.resolve(strict=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": 1,
        "passed": False,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "tool_sha256": file_sha256(Path(__file__)),
        "executable": {"name": binary.name, "bytes": binary.stat().st_size, "sha256": file_sha256(binary)},
        "fixture_generator": json.loads((fixtures / "BenchmarkManifest.json").read_text(encoding="utf-8")),
        "scope": "CPU geometry-layout GPU package with source PNG/JPEG image bytes",
        "texture_mips_baked": False,
        "block_compression_baked": False,
        "clusters_baked": False,
        "scenes": [],
    }
    try:
        with tempfile.TemporaryDirectory(prefix="m42-assets-", dir=args.report.parent) as temporary:
            for name in ("B", "F"):
                report["scenes"].append(exercise_scene(binary, fixtures, Path(temporary), name))
        report["passed"] = True
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        report["error"] = str(error)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "report": str(args.report)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
