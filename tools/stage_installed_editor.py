"""Stage the exact Windows main build for the primary checkout's installer."""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".github/scripts"))
from windows_editor_artifact import RECEIPT, digest, restore

GUI = "godot.windows.editor.x86_64.exe"
CONSOLE = "godot.windows.editor.x86_64.console.exe"
PACKAGE = "tianshu-ui.json"
FILES = (GUI, CONSOLE, PACKAGE)


def main_revision(workspace):
    remote = subprocess.check_output(
        ["git", "-C", workspace, "ls-remote", "--exit-code", "origin", "refs/heads/main"], text=True
    ).split()[0]
    head = subprocess.check_output(["git", "-C", workspace, "rev-parse", "HEAD"], text=True).strip()
    if remote != head:
        raise ValueError("Update the primary checkout to the current origin/main before installing")
    subprocess.run(
        ["git", "-C", workspace, "diff", "--quiet", head, "--", "tools/codex_cli", "tools/codebuddy_cli"],
        check=True,
    )
    return head


def local_receipt(folder, revision, hashes):
    for path in (folder / "gonggong-build-receipts").glob("*.json"):
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if (
            receipt.get("revision") == revision
            and receipt.get("clean_source") is True
            and receipt.get("aichat") == "passed"
            and receipt.get("native", {}).get("artifact_sha256") == hashes[GUI]
            and receipt.get("console_sha256") == hashes[CONSOLE]
            and receipt.get("tianshu_sha256") == hashes[PACKAGE]
        ):
            return
    raise ValueError("No matching clean main build receipt for the staged files")


def stage(workspace, output, folder, run):
    revision = main_revision(workspace)
    with tempfile.TemporaryDirectory(dir=output) as tmp:
        scratch = Path(tmp)
        if run:
            repo = json.loads((workspace / "work-items.json").read_text(encoding="utf-8"))["repository"]
            folder = scratch / "artifact"
            restore(run, repo, "main", None, folder, scratch)
            receipt = json.loads((folder / RECEIPT).read_text(encoding="utf-8"))
            if receipt["revision"] != revision:
                raise ValueError("Actions run does not match the current main revision")
        names = list(FILES)
        if run:
            if not (folder / CONSOLE).is_file():
                if "windows_subsystem=console" not in receipt["inputs"]["flags"]:
                    raise ValueError("Editor artifact lacks a console entry")
                names.remove(CONSOLE)
            names.extend(path.name for path in folder.glob("*.dll"))
        for name in names:
            shutil.copyfile(folder / name, output / name)
        if not run:
            local_receipt(folder, revision, {name: digest(output / name) for name in FILES})
    if main_revision(workspace) != revision:
        raise ValueError("Main changed during staging")
    return revision


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--stage", type=Path, required=True)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--build-directory", type=Path)
    inputs.add_argument("--actions-run")
    args = parser.parse_args()
    print(stage(args.workspace, args.stage, args.build_directory, args.actions_run))
