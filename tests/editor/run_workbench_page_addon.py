"""Verify that one installed editor loads, rejects and rolls back Project Brief packages."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from editor_test_isolation import copy_editor
from run_unified_settings_native import sanitized_environment

SOURCE = Path(__file__).resolve().parent


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def observe(editor, root):
    project = root / "project"
    shutil.copytree(SOURCE.parents[1] / "samples/gonggong-workbench", project)
    shutil.copyfile(SOURCE / "workbench_page_addon.gd", project / "observe.gd")
    binary = copy_editor(editor, root / "editor")
    engine = digest(binary)
    assert digest(editor) == engine
    addon = project / "addons/project_brief"
    script = addon / "plugin.gd"
    original = script.read_bytes()
    updated = original.replace(b'"Brief/Summary": "replace_text"', b'"Brief/Summary": "read"')
    assert original != updated
    results = {}
    for name, data, base, modes in (
        ("original", original, "EditorPlugin", ["replace_text"]),
        ("update", updated, "EditorPlugin", ["read"]),
        ("incompatible", b"@tool\nextends Node\n", "Node", []),
        ("rollback", original, "EditorPlugin", ["replace_text"]),
    ):
        script.write_bytes(data)
        process = subprocess.run(
            [binary, "--headless", "--editor", "--path", project, "--script", "res://observe.gd"],
            cwd=root,
            env=sanitized_environment(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
            check=True,
        )
        assert "SCRIPT ERROR" not in process.stderr, process.stderr
        (line,) = [line for line in process.stdout.splitlines() if line.startswith("ADDON_OBSERVATION ")]
        actual = json.loads(line.removeprefix("ADDON_OBSERVATION "))
        assert actual == dict(configured=True, enabled=bool(modes), script_base=base, summary_modes=modes), actual
        files = {file: digest(addon / file) for file in ("plugin.cfg", "plugin.gd")}
        package = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        results[name] = dict(files=files, package_sha256=package, loader=actual)
    assert results["rollback"] == results["original"] and digest(binary) == engine
    return dict(editor_sha256=engine, observations=results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    os.environ.pop("GONGGONG_WORKSPACE", None)
    with tempfile.TemporaryDirectory(prefix="workbench-page-addon-") as folder:
        result = observe(args.godot.resolve(strict=True), Path(folder))
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
