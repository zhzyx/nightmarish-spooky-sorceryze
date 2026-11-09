"""Pack the two reviewed desktop Tianshu presentation scripts for one editor launch."""

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "editor/docks/daqian"
SCRIPTS = ("graph_layout", "issue_graph")
ABI = "tianshu-graph/1"


def installed_package(executable):
    executable = Path(executable)
    if executable.parent.name == "MacOS" and executable.parent.parent.name == "Contents":
        return executable.parent.parent / "Resources/tianshu-ui.json"
    for slot in ("self_update_a", "self_update_b"):
        if slot in executable.name.split("."):
            return executable.with_name(f"tianshu-ui.{slot}.json")
    return executable.with_name("tianshu-ui.json")


def verify_candidate_package(manifest):
    # Legacy manifests predate desktop packages. New producer snapshots require the pin.
    expected = manifest.get("tianshu_ui_sha256")
    if expected is None and "tools/package_tianshu_ui.py" not in manifest.get("source_inputs", {}):
        return
    package = installed_package(manifest["executable"])
    if (
        package.is_symlink()
        or not package.is_file()
        or package.stat().st_size > 4 * 1024 * 1024
        or hashlib.sha256(package.read_bytes()).hexdigest() != expected
    ):
        raise ValueError("candidate_tianshu_ui_changed")


def pack(source, version, output):
    if not version.strip():
        raise ValueError("A package version is required")
    scripts = {name: (source / (name + ".gd")).read_text(encoding="utf-8") for name in SCRIPTS}
    payload = json.dumps({"abi": ABI, "version": version, **scripts}, ensure_ascii=False, sort_keys=True)
    checksum = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    envelope = json.dumps({"sha256": checksum, "payload": payload}, ensure_ascii=False)
    data = (envelope + "\n").encode("utf-8")
    if len(data) > 4 * 1024 * 1024:
        raise ValueError("Package exceeds the editor's 4 MiB limit")
    output.parent.mkdir(parents=True, exist_ok=True)
    stream = tempfile.NamedTemporaryFile(dir=output.parent, delete=False)
    temporary = Path(stream.name)
    try:
        with stream:
            stream.write(data)
        temporary.chmod(0o644)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return hashlib.sha256(data).hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--version", default="1")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(pack(args.source, args.version, args.output))
