"""Exercise Windows installation and launcher compatibility from a linked checkout."""

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import stage_installed_editor as stage
import package_workspace_release as release
import verify_release_bundle as verify


class ActionsStageTests(unittest.TestCase):
    def test_console_subsystem_and_dlls_come_from_same_immutable_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "work-items.json").write_text('{"repository":"fixture/repo"}')
            output = root / "staged"
            output.mkdir()
            revision = "1" * 40

            def restore(run, repo, branch, inputs, folder, scratch):
                folder.mkdir()
                for name in (stage.GUI, stage.PACKAGE, "D3D12Core.dll", "d3d12SDKLayers.dll"):
                    (folder / name).write_text(name)
                (folder / stage.RECEIPT).write_text(json.dumps({
                    "revision": revision, "inputs": {"flags": ["windows_subsystem=console"]},
                }))

            with patch.object(stage, "main_revision", return_value=revision), patch.object(stage, "restore", restore):
                self.assertEqual(stage.stage(root, output, None, "42"), revision)
            self.assertEqual({p.name for p in output.iterdir()}, {
                stage.GUI, stage.PACKAGE, "D3D12Core.dll", "d3d12SDKLayers.dll",
            })


@unittest.skipUnless(shutil.which("powershell.exe"), "Windows launcher required")
class InstalledEditorTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "primary checkout"
        self.root.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.email", "fixture@example.org")
        self.git("config", "user.name", "fixture")
        scripts = self.root / "tools"
        scripts.mkdir()
        for name in (
            "launch_gonggong_editor.ps1", "launch_latest_editor.ps1", "install_gonggong_editor.ps1",
            "stage_installed_editor.py", "installed_editor_workspace.ps1", "run_issue_gate.ps1",
            "initialize_downloaded_workspace.ps1",
        ):
            shutil.copyfile(Path(__file__).with_name(name), scripts / name)
        artifact = Path(__file__).resolve().parents[1] / ".github/scripts/windows_editor_artifact.py"
        (self.root / ".github/scripts").mkdir(parents=True)
        shutil.copyfile(artifact, self.root / ".github/scripts" / artifact.name)
        (self.root / ".gitignore").write_text("project/runtime/git/\n")
        self.git("add", ".")
        self.git("commit", "-m", "fixture")
        self.git("remote", "add", "origin", str(self.root))
        self.linked = self.root.parent / "linked checkout"
        self.git("worktree", "add", "--detach", str(self.linked))
        self.build = self.linked / "bin"
        self.build.mkdir()
        for name in stage.FILES:
            (self.build / name).write_text(name)
        receipts = self.build / "gonggong-build-receipts"
        receipts.mkdir()
        self.receipt = receipts / "build.json"
        self.receipt.write_text(json.dumps(dict(
            clean_source=True, revision=self.git("rev-parse", "HEAD").strip(), aichat="passed",
            native={"artifact_sha256": stage.digest(self.build / stage.GUI)},
            console_sha256=stage.digest(self.build / stage.CONSOLE),
            tianshu_sha256=stage.digest(self.build / stage.PACKAGE),
        )))
        (self.root / "samples/gonggong-workbench").mkdir(parents=True)

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True, stderr=subprocess.PIPE)

    def script(self, name, *args, success=True):
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             self.linked / "tools" / name, *args],
            cwd=self.linked, capture_output=True, text=True, errors="replace",
        )
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return re.sub(r"\n {15}", "", result.stdout)

    def test_package_verify_and_extract(self):
        inventory_bytes = b'{"files":[]}'
        runtime = self.root / "project/runtime"
        runtime.mkdir(parents=True)
        for name in ("installed.local.json", "cli-dependencies.json"):
            (runtime / name).write_bytes(inventory_bytes)
        anchors = {key: release.digest(inventory_bytes) for key in ("runtime_inventory_sha256", "cli_inventory_sha256")}
        (self.root / "distribution").mkdir()
        (self.root / "distribution/deliverables.json").write_text(json.dumps(anchors))
        self.git("add", "distribution")
        self.git("commit", "-m", "runtime anchors")
        receipt = json.loads(self.receipt.read_text())
        receipt["revision"] = self.git("rev-parse", "HEAD").strip()
        self.receipt.write_text(json.dumps(receipt))
        self.script("install_gonggong_editor.ps1", "-BuildDirectory", self.build, "-Python", sys.executable)
        archive = self.root.parent / "verified.zip"
        manifest = archive.with_suffix(".json")
        package_args = ["package", "--editor-stage", self.root / "project/godot", "--out", archive,
                        "--manifest", manifest, "--build-root", self.linked]
        with patch.object(release, "ROOT", self.root), patch.object(sys, "argv", list(map(str, package_args))):
            release.main()
        with zipfile.ZipFile(archive) as packed:
            self.assertFalse(any(name.startswith("project/godot/versions/") for name in packed.namelist()))
        extracted = self.root.parent / "extracted"
        with patch.object(sys, "argv", list(map(str, ["verify", "--archive", archive, "--sha256", stage.digest(archive),
                                       "--extract", extracted, "--report", self.root.parent / "verification.json"]))):
            verify.main()
        self.assertEqual((extracted / "project/godot/bin" / stage.GUI).read_text(), stage.GUI)
        git_root = Path(shutil.which("git")).resolve().parents[1]
        # Expose the host's portable Git at the same relative location as a full release.
        git_link = extracted / "project/runtime/git"
        subprocess.run(["cmd", "/c", "mklink", "/J", git_link, git_root], check=True, capture_output=True)
        try:
            for name, args in (("initialize_downloaded_workspace.ps1", []),
                               ("launch_gonggong_editor.ps1", ["-Probe", "-ProjectManager"])):
                subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                                "-File", extracted / "tools" / name, *args], check=True, capture_output=True)
        finally:
            git_link.rmdir()

    def test_install_probe_and_reject_stale(self):
        args = ("install_gonggong_editor.ps1", "-BuildDirectory", self.build, "-Python", sys.executable)
        self.script(*args)
        installed = self.root / "project/godot/bin"
        old_file = self.build / "godot.windows.editor.dev.self_update_a.exe"
        old_file.touch()
        for launcher in ("launch_latest_editor.ps1", "launch_gonggong_editor.ps1"):
            self.assertIn(str(installed / stage.GUI), self.script(launcher, "-Probe"))
            self.assertIn(str(installed / stage.CONSOLE), self.script(launcher, "-Console", "-Probe"))
        (self.build / stage.GUI).write_text("unverified")
        self.script(*args, success=False)
        self.assertEqual((installed / stage.GUI).read_text(), stage.GUI)
        (self.root / "notes.md").write_text("documentation")
        self.git("add", "notes.md")
        self.git("commit", "-m", "docs")
        self.script("launch_latest_editor.ps1", "-Probe")
        (self.root / "runtime.cpp").write_text("changed")
        self.git("add", "runtime.cpp")
        self.git("commit", "-m", "runtime")
        self.script("launch_latest_editor.ps1", "-Probe", success=False)
        self.script(*args, success=False)
