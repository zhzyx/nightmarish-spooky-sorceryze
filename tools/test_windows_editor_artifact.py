import hashlib
import io
import json
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".github/scripts"))
import windows_editor_artifact as artifact


class WindowsSdkInstallTests(unittest.TestCase):
    def test_msvc_install_uses_only_published_sdk_bytes(self):
        script = Path(__file__).resolve().parents[1] / "misc/scripts/install_d3d12_sdk_windows.py"

        def download(url, destination):
            with ZipFile(destination, "w") as archive:
                archive.writestr("bin/x64/WinPixEventRuntime.lib", b"published import library")
                archive.writestr("bin/ARM64/WinPixEventRuntime.lib", b"published import library")

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, LOCALAPPDATA=tmp, MSYSTEM=""):
            for flags, calls in [([], 4), (["--msvc-only"], 0)]:
                with (
                    self.subTest(flags=flags),
                    patch.object(sys, "argv", [str(script), *flags]),
                    patch.object(sys, "path", list(sys.path)),
                    patch("urllib.request.urlretrieve", download),
                    patch("shutil.which", return_value="fixture-tool"),
                    patch("subprocess.run") as generate,
                    redirect_stdout(io.StringIO()),
                ):
                    runpy.run_path(str(script), run_name="__main__")
                    self.assertEqual(generate.call_count, calls)
                    pix = Path(tmp) / "Godot/build_deps/pix/bin/x64"
                    self.assertEqual((pix / "WinPixEventRuntime.lib").read_bytes(), b"published import library")


class WindowsEditorArtifactTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.repo = "team/repo"
        self.run = dict(
            repository=dict(full_name=self.repo),
            head_repository=dict(full_name=self.repo),
            head_branch="main",
            head_sha="1" * 40,
            event="push",
            conclusion="success",
            path=".github/workflows/runner.yml",
        )
        self.inputs = dict(source="shared-tree", image="image", sdk_sha256="libs", flags=["msvc"])
        self.exe = b"verified binary"
        self.source = self.root / "server.zip"
        self.pack()

    def pack(self, extra=None):
        with ZipFile(self.source, "w") as out:
            out.writestr("godot.windows.editor.x86_64.exe", self.exe)
            out.writestr(
                artifact.RECEIPT,
                json.dumps(
                    dict(
                        inputs=self.inputs,
                        revision=self.run["head_sha"],
                        binary_sha256=hashlib.sha256(self.exe).hexdigest(),
                    )
                ),
            )
            if extra:
                out.writestr(extra, b"injected")
        self.sha = "sha256:" + artifact.digest(self.source)

    def restore(self, expected=None):
        destination = self.root / "bin"
        responses = [
            self.run,
            {"status": "identical"},
            {"artifacts": [dict(name="windows-editor", id=42, expired=False, digest=self.sha)]},
        ]

        def download(cmd, stdout, check, timeout):
            self.assertEqual(cmd[0], "/selected host/gh")
            self.assertEqual(cmd[-1], "repos/team/repo/actions/artifacts/42/zip")
            stdout.write(self.source.read_bytes())

        with (
            patch.object(artifact, "api", side_effect=responses),
            patch.object(artifact.github_runtime, "resolve_gh", return_value="/selected host/gh"),
            patch.object(artifact.subprocess, "run", side_effect=download),
        ):
            return artifact.restore("100", self.repo, "main", expected or self.inputs, destination, self.root)

    def test_verified_main_artifact_restored_by_id(self):
        result = self.restore()
        self.assertEqual(result["archive_sha256"], self.sha)
        self.assertEqual((self.root / "bin/godot.windows.editor.x86_64.exe").read_bytes(), self.exe)

    @unittest.skipIf(os.name == "nt", "POSIX executable fixture")
    def test_explicit_cli_serves_json_and_binary_with_empty_path(self):
        executable = self.root / "selected host gh"
        responses = {
            "repos/team/repo/actions/runs/100": self.run,
            f"repos/team/repo/compare/{self.run['head_sha']}...main": {"status": "identical"},
            "repos/team/repo/actions/runs/100/artifacts?name=windows-editor": {
                "artifacts": [dict(name="windows-editor", id=42, expired=False, digest=self.sha)]
            },
        }
        executable.write_text(
            f"#!{sys.executable}\nimport sys,json\nfrom pathlib import Path\n"
            f"responses={responses!r}\n"
            "assert sys.argv[1]=='api'\n"
            f"if sys.argv[2].endswith('/zip'): sys.stdout.buffer.write(Path({str(self.source)!r}).read_bytes())\n"
            "else: print(json.dumps(responses[sys.argv[2]]))\n",
            encoding="utf-8",
        )
        executable.chmod(0o700)
        with patch.dict(os.environ, GONGGONG_GH=str(executable), PATH=""):
            result = artifact.restore("100", self.repo, "main", self.inputs, self.root / "bin", self.root)
        self.assertEqual(result["archive_sha256"], self.sha)
        self.assertEqual((self.root / "bin/godot.windows.editor.x86_64.exe").read_bytes(), self.exe)

    def test_invalid_explicit_cli_does_not_fall_back(self):
        with patch.dict(os.environ, GONGGONG_GH=str(self.root / "missing-gh")):
            with self.assertRaisesRegex(artifact.github_runtime.GitHubCommandError, "configured GONGGONG_GH"):
                artifact.api("repos/team/repo")

    def test_rejects_other_sources(self):
        for field, value in (
            ("path", "other.yml"),
            ("event", "pull_request"),
            ("head_branch", "feature"),
            ("head_repository", {"full_name": "fork/repo"}),
            ("conclusion", "failure"),
        ):
            with self.subTest(field=field):
                self.assertFalse(artifact.trusted(dict(self.run, **{field: value}), self.repo, "main"))

    def test_rejects_altered_archive_before_installing(self):
        self.sha = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.restore()
        self.assertFalse((self.root / "bin").exists())

    def test_rejects_mismatched_sdk_toolchain_and_options(self):
        for key in ("image", "sdk_sha256", "flags"):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "changed"):
                self.restore(dict(self.inputs, **{key: "different"}))
        self.assertFalse((self.root / "bin").exists())

    def test_source_identity_excludes_only_detached_inputs_outside_actual_graph(self):
        root = self.root / "checkout"
        root.mkdir()

        def git(*args):
            subprocess.run(["git", "-C", root, *args], check=True, capture_output=True)

        git("init")

        def commit(path, content):
            (root / path).write_text(content)
            git("add", ".")
            git("-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "snapshot")

        commit("native.cpp", "native")
        commit("layout.gd", "layout 1")
        graph = ["native.cpp"]
        module = SimpleNamespace(
            probe=lambda *args: {"native_sources": graph},
            CacheUnavailable=ValueError,
            is_external_data=lambda name, deps: name == "layout.gd" and name not in deps,
        )
        with patch.dict(sys.modules, editor_native_cache=module):
            before = artifact.source_identity(root, ["platform=windows"], {})
            commit("layout.gd", "layout 2")
            self.assertEqual(before, artifact.source_identity(root, ["platform=windows"], {}))
            graph.append("layout.gd")
            keyed = artifact.source_identity(root, ["platform=windows"], {})
            commit("layout.gd", "layout 3")
            self.assertNotEqual(keyed, artifact.source_identity(root, ["platform=windows"], {}))
            graph.clear()
            full = artifact.source_identity(root, ["platform=windows"], {})
            commit("layout.gd", "layout 4")
            self.assertNotEqual(full, artifact.source_identity(root, ["platform=windows"], {}))

    def test_rejects_unsafe_paths(self):
        self.pack("../replace.cpp")
        with self.assertRaisesRegex(ValueError, "Unexpected artifact path"):
            self.restore()
        self.assertFalse((self.root / "bin").exists())


if __name__ == "__main__":
    unittest.main()
