"""Run the native Save panel XCUITest on a dedicated macOS GUI test host."""

import argparse
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
FIXTURES = REPO / "samples/ainative-workbench/fixtures"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare(root, binary):
    app = root / "Godot.app"
    template = REPO / "misc/dist/macos_tools.app"
    shutil.copytree(template, app, ignore=shutil.ignore_patterns("Info_*.plist"))
    contents = app / "Contents"
    plist = plistlib.loads((template / "Contents/Info_arm64.plist").read_bytes())
    plist["CFBundleIdentifier"] = "org.godotengine.tests.maliang-save-panel.editor"
    (contents / "Info.plist").write_bytes(plistlib.dumps(plist))
    (contents / "MacOS").mkdir()
    exe = contents / "MacOS/Godot"
    shutil.copy2(binary, exe)
    for name in ("tianshu-board.json", "tianshu-ui.json"):
        shutil.copyfile(binary.with_name(name), contents / "Resources" / name)
    subprocess.run(["codesign", "--force", "--sign", "-", str(app)], check=True)
    (root / "_sc_").touch()
    (root / "exports").mkdir()
    home = root / "home"
    (home / "Library/Caches").mkdir(parents=True)
    project = root / "project"
    (project / "fixtures").mkdir(parents=True)
    for name in ("sample.png", "sample.glb"):
        shutil.copyfile(FIXTURES / name, project / "fixtures" / name)
    (project / "project.godot").write_text(
        'config_version=5\n[application]\nconfig/name="Maliang Save Panel Test"\n'
        '[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
    )
    environment = {
        "HOME": str(home),
        "CFFIXED_USER_HOME": str(home),
        "PATH": os.environ["PATH"],
        "SAVE_PANEL_ROOT": str(root),
        "AINATIVE_PYTHON": sys.executable,
        "PYTHONDONTWRITEBYTECODE": "1",
        "LANG": "en_US.UTF-8",
    }
    (root / "environment.json").write_text(json.dumps(environment))
    with (root / "import.log").open("w") as log:
        subprocess.run(
            [exe, "--headless", "--editor", "--path", project, "--import"],
            env=environment, cwd=root, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120,
        )
    shutil.copyfile(HERE / "probe.gd", project / "probe.gd")
    for name in ("project.yml", "SavePanelTests.swift"):
        shutil.copyfile(HERE / name, root / name)
    return exe


def verify(root):
    observations = json.loads((root / "callbacks.json").read_text())
    exports = root / "exports"
    names = sorted(path.name for path in exports.iterdir())
    expected = [("image", "chosen-image.png", "sample.png"), ("mesh", "chosen-mesh.glb", "sample.glb")]
    if [item["step"] for item in observations] != ["image", "mesh", "cancel"] or names != [row[1] for row in expected]:
        raise ValueError(f"Unexpected callbacks or export count: {observations}, files={names}")
    files = {}
    for item, (_, name, fixture) in zip(observations, expected):
        target = exports / name
        if [Path(path).resolve() for path in item["file_selected"]] != [target] or item["canceled"] != 0:
            raise ValueError(f"Unexpected destination or cancellation: {item}")
        source = Path(item["source"])
        if source.resolve() == target or not (target.read_bytes() == source.read_bytes() == (FIXTURES / fixture).read_bytes()):
            raise ValueError(f"Export differs from the preview or fixture: {name}")
        files[name] = {"bytes": target.stat().st_size, "sha256": digest(target)}
    if observations[-1]["canceled"] != 1 or observations[-1]["file_selected"]:
        raise ValueError(f"Unexpected cancel callback: {observations[-1]}")
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    binary = args.godot.resolve(strict=True)
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="maliang-save-ui-") as tmp:
        root = Path(tmp).resolve()
        report = {
            "source_commit": subprocess.check_output(["git", "-C", REPO, "rev-parse", "HEAD"], text=True).strip(),
            "binary_sha256": digest(binary),
            "passed": False,
        }
        try:
            editor = prepare(root, binary)
            report["signed_editor_sha256"] = digest(editor)
            subprocess.run(["xcodegen", "generate"], cwd=root, check=True)
            subprocess.run(
                [
                    "xcodebuild", "test", "-project", "SavePanel.xcodeproj", "-scheme", "SavePanel",
                    "-destination", "platform=macOS,arch=arm64", "-derivedDataPath", root / "build",
                    "-parallel-testing-enabled", "NO", "-resultBundlePath", out / "SavePanel.xcresult",
                ],
                cwd=root, timeout=600, check=True,
            )
            report["exports"] = verify(root)
            report["passed"] = True
        finally:
            for name in ("import.log", "editor.log", "callbacks.json", "failure.json"):
                if (root / name).is_file():
                    shutil.copy2(root / name, out / name)
            if (root / "exports").is_dir():
                shutil.copytree(root / "exports", out / "exports")
            (out / "result.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
