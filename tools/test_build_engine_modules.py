import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from build_engine_modules import build, changes, plan


class BuildScopeTests(unittest.TestCase):
    def test_git_changes(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        previous = Path.cwd()
        self.addCleanup(os.chdir, previous)
        os.chdir(root)

        def git(*args):
            subprocess.run(["git", *args], check=True, capture_output=True)

        def mode(committed=False):
            return plan(changes("HEAD", committed))[:2]

        bmp = Path("modules/bmp/image_loader_bmp.cpp")
        tga = Path("modules/tga/image_loader_tga.cpp")
        for source in (bmp, tga):
            source.parent.mkdir(parents=True)
            source.write_text("old")
        git("init", "-q")
        git("add", ".")
        git("-c", "user.name=test", "-c", "user.email=test@localhost", "commit", "-qm", "base")
        Path("README.md").write_text("documentation")
        self.assertEqual(mode(), ("skip", []))
        bmp.write_text("changed")
        self.assertEqual(mode(), ("modules", [bmp.as_posix()]))
        tga.write_text("changed")
        git("add", str(tga))
        self.assertEqual(mode(), ("modules", [bmp.as_posix(), tga.as_posix()]))
        self.assertEqual(mode(committed=True), ("skip", []))
        (bmp.parent / "shared.h").write_text("header")
        self.assertEqual(mode()[0], "full")
        (bmp.parent / "shared.h").unlink()
        git("mv", str(bmp), "README-renamed.md")
        self.assertEqual(mode()[0], "full")
        git("add", ".")
        git("-c", "user.name=test", "-c", "user.email=test@localhost", "commit", "-qm", "candidate")
        self.assertEqual(plan(changes("HEAD^", True))[0], "full")

    def test_probe_failure_falls_back_but_compile_failure_propagates(self):
        source = "modules/bmp/image_loader_bmp.cpp"
        failure = subprocess.CalledProcessError(2, "SCons")
        with patch("build_engine_modules.subprocess.run", side_effect=failure):
            self.assertEqual(build([source], [])[0], "full")

        def probed(command, *, check):
            if "-n" in command:
                inventory = Path(command[-1].split("=", 1)[1])
                inventory.write_text('{"bmp": ["modules/bmp/image_loader_bmp.cpp"]}', encoding="utf-8")
            else:
                raise failure

        with patch("build_engine_modules.subprocess.run", side_effect=probed):
            with self.assertRaises(subprocess.CalledProcessError):
                build([source], [])

    def test_shared_and_generated_inputs(self):
        for path in (
            "modules/bmp/config.py",
            "modules/bmp/register_types.cpp",
            "modules/bmp/tests/example.cpp",
            "core/object/object.h",
            "editor/docks/daqian/graph_layout.gd",
            "tools/ainative/agent.py",
            "doc/classes/Image.xml",
            "thirdparty/library/example.cpp",
            "modules/SCsub",
        ):
            with self.subTest(path=path):
                self.assertEqual(plan([(path, True)])[0], "full")
        self.assertEqual(plan([("modules/bmp/new_file.cpp", False)])[0], "full")


if __name__ == "__main__":
    unittest.main()
