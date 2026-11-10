"""Package one committed source snapshot with verified local Windows deliverables."""

import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from verify_release_bundle import editor_files

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--editor-stage", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--build-root",
        type=Path,
        required=True,
        help="Actual original compiler source root, checked for accidental leakage",
    )
    args = parser.parse_args()
    if args.out.exists() or args.manifest.exists():
        raise ValueError("Output files must be new")
    ref = subprocess.check_output(["git", "rev-parse", args.ref + "^{commit}"], cwd=ROOT).decode().strip()
    tree = subprocess.check_output(["git", "rev-parse", ref + "^{tree}"], cwd=ROOT).decode().strip()
    anchors = json.loads(subprocess.check_output(["git", "show", ref + ":distribution/deliverables.json"], cwd=ROOT))
    files = {}
    forbidden = []
    for root in (ROOT, Path.home(), args.build_root.resolve()):
        for text in (str(root).replace("\\", "/"), str(root).replace("/", "\\")):
            forbidden += [text.lower().encode("utf-8"), text.lower().encode("utf-16-le")]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with (
        tempfile.TemporaryDirectory() as temporary,
        zipfile.ZipFile(args.out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive,
    ):
        source_zip = Path(temporary) / "source.zip"
        subprocess.run(["git", "archive", "--format=zip", "--output", str(source_zip), ref], cwd=ROOT, check=True)

        def add(name, data, origin, mode=0o100644):
            if name in files or name.startswith("/") or ".." in name.split("/"):
                raise ValueError("Duplicate or unsafe archive entry: " + name)
            if any(prefix in data.lower() for prefix in forbidden):
                raise ValueError("Machine-specific path in deliverable: " + name)
            entry = zipfile.ZipInfo(name, (2026, 11, 2, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            if mode not in (0o100644, 0o100755):
                raise ValueError("Unsupported source file mode: " + name)
            entry.external_attr = mode << 16
            archive.writestr(entry, data)
            files[name] = {"sha256": digest(data), "bytes": len(data), "origin": origin, "mode": oct(mode)}

        with zipfile.ZipFile(source_zip) as source:
            for entry in source.infolist():
                if not entry.is_dir():
                    mode = entry.external_attr >> 16
                    add(entry.filename, source.read(entry), "git:" + ref, mode or 0o100644)
        runtime_raw = (ROOT / "project/runtime/installed.local.json").read_bytes()
        if digest(runtime_raw) != anchors["runtime_inventory_sha256"]:
            raise ValueError("Runtime inventory differs from reviewed inventory")
        runtime_manifest = json.loads(runtime_raw)
        for item in runtime_manifest["files"]:
            data = (ROOT / "project/runtime" / item["path"]).read_bytes()
            if digest(data) != item["sha256"]:
                raise ValueError("Installed runtime changed: " + item["path"])
            add("project/runtime/" + item["path"], data, "verified_local_runtime")
        add(
            "project/runtime/installed.local.json",
            (ROOT / "project/runtime/installed.local.json").read_bytes(),
            "runtime_inventory",
        )
        cli_raw = (ROOT / "project/runtime/cli-dependencies.json").read_bytes()
        if digest(cli_raw) != anchors["cli_inventory_sha256"]:
            raise ValueError("CLI dependency inventory changed")
        for item in json.loads(cli_raw)["files"]:
            name = item["path"]
            if not name.startswith("tools/codebuddy_cli/node_modules/") or ".." in name.split("/"):
                raise ValueError("Unsafe CLI dependency path")
            data = (ROOT / name).read_bytes()
            if digest(data) != item["sha256"]:
                raise ValueError("CLI dependency changed: " + name)
            add(name, data, "fixed_cli_runtime_dependency")
        add("project/runtime/cli-dependencies.json", cli_raw, "cli_dependency_inventory")
        installed = json.loads((ROOT / "project/godot/installed.local.json").read_text(encoding="utf-8-sig"))
        for name, item in editor_files(installed, ref).items():
            installed_file = ROOT / "project/godot" / name
            data = (args.editor_stage / name).read_bytes()
            if digest(installed_file.read_bytes()) != item["sha256"] or digest(data) != item["sha256"]:
                raise ValueError("Release stage differs from verified main installation: " + name)
            add("project/godot/" + name, data, "verified_main_editor")
        add(
            "project/godot/installed.local.json",
            (json.dumps(installed, indent=2) + "\n").encode(),
            "release_installation_inventory",
        )
        manifest = {
            "schema_version": 2,
            "source_commit": ref,
            "source_tree": tree,
            "path_base": "extracted_workspace_root",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "model_validation": "simulated_only",
            "requires_valid_gonggong_source_binding": False,
            "framework_pointer": "CURRENT_FRAMEWORK.json",
            "source_history_included": False,
            "files": files,
        }
        raw_manifest = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
        archive.writestr("bundle-manifest.json", raw_manifest)
    manifest["archive"] = {
        "name": args.out.name,
        "bytes": args.out.stat().st_size,
        "sha256": digest(args.out.read_bytes()),
        "internal_manifest_sha256": digest(raw_manifest),
    }
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"source_commit": ref, "files": len(files), "archive": manifest["archive"]}))


if __name__ == "__main__":
    main()
