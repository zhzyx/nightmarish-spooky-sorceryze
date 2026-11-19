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
BOARD = "tianshu-board.json"
FILES = (GUI, CONSOLE, PACKAGE, BOARD)


def main_revision(workspace):
    remote = subprocess.check_output(
        ["git", "-C", workspace, "ls-remote", "--exit-code", "origin", "refs/heads/main"], text=True
    ).split()[0]
    head = subprocess.check_output(["git", "-C", workspace, "rev-parse", "HEAD"], text=True).strip()
    if remote != head:
        raise ValueError("Update the primary checkout to the current origin/main before installing")
    subprocess.run(
        [
            "git",
            "-C",
            workspace,
            "diff",
            "--quiet",
            head,
            "--",
            "tools/codex_cli",
            "tools/codebuddy_cli",
            "thirdparty/webview2/manifest.json",
        ],
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
            and receipt.get("tianshu_board_sha256") == hashes[BOARD]
        ):
            return
    raise ValueError("No matching clean main build receipt for the staged files")


def webview2_files(workspace, folder):
    manifest_path = workspace / "thirdparty/webview2/manifest.json"
    if not manifest_path.is_file():
        return []  # Older revisions predate the embedded browser.
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mapping = {
        "WebView2Loader.dll": "build/native/x64/WebView2Loader.dll",
        "WebView2-LICENSE.txt": "LICENSE.txt",
        "WebView2-NOTICE.txt": "NOTICE.txt",
    }
    for name, source in mapping.items():
        if not (folder / name).is_file() or digest(folder / name) != manifest["files"][source]:
            raise ValueError(f"Missing or unverified WebView2 distribution file: {name}")
    return list(mapping)


def stage(workspace, output, folder, run, archive=None):
    if archive is not None and not run:
        raise ValueError("An Actions archive requires its run ID")
    revision = main_revision(workspace)
    with tempfile.TemporaryDirectory(dir=output) as tmp:
        scratch = Path(tmp)
        if run:
            repo = json.loads((workspace / "work-items.json").read_text(encoding="utf-8"))["repository"]
            folder = scratch / "artifact"
            restore(run, repo, "main", None, folder, scratch, local_archive=archive)
            receipt = json.loads((folder / RECEIPT).read_text(encoding="utf-8"))
            if receipt["revision"] != revision:
                raise ValueError("Actions run does not match the current main revision")
        names = list(FILES) + webview2_files(workspace, folder)
        if run:
            if not (folder / CONSOLE).is_file():
                if "windows_subsystem=console" not in receipt["inputs"]["flags"]:
                    raise ValueError("Editor artifact lacks a console entry")
                names.remove(CONSOLE)
            names.extend(path.name for path in folder.glob("*.dll") if path.name not in names)
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
    parser.add_argument("--actions-archive", type=Path, help="Previously downloaded archive for the identified run")
    args = parser.parse_args()
    print(stage(args.workspace, args.stage, args.build_directory, args.actions_run, args.actions_archive))
