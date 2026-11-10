import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from build_engine_modules import METAL_MARKERS, build, changes, conditional_consumers, plan, platform_plan


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

    def test_platforms_cover_mixed_commits(self):
        metal = "drivers/metal/metal_objects_shared.cpp"
        renderer = "servers/rendering/renderer_viewport.cpp"
        editor = "editor/editor_node.cpp"
        d3d = "drivers/d3d12/rendering_device_driver_d3d12.cpp"
        bmp = "modules/bmp/image_loader_bmp.cpp"
        files = [(name, True) for name in [metal, renderer, editor, d3d, bmp, "README.md"]]
        self.assertEqual(platform_plan(files, "windows")[:2], ("modules", sorted([renderer, editor, d3d, bmp])))
        self.assertEqual(platform_plan(files, "metal")[:2], ("modules", [metal]))
        self.assertEqual(platform_plan([(metal, True)], "windows")[0], "skip")
        self.assertEqual(platform_plan([(renderer, True)], "metal")[0], "skip")
        private = [("thirdparty/metal-cpp/metal_cpp.cpp", True)]
        self.assertEqual(platform_plan(private, "metal")[0], "modules")
        self.assertEqual(platform_plan(private, "windows")[0], "skip")
        self.assertEqual(platform_plan([("thirdparty/spirv-cross/spirv_msl.cpp", True)], "metal")[0], "full")
        for item in [(metal, False), ("servers/rendering/rendering_server.h", True)]:
            for worker in ("windows", "metal"):
                self.assertEqual(platform_plan([*files, item], worker)[0], "full")

    def test_removed_metal_guard_still_requires_apple(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = Path("servers/rendering/shared.cpp")
            (root / source.parent).mkdir(parents=True)
            (root / source).write_text("#ifdef METAL_ENABLED\n#endif\n")
            for args in (["init", "-q"], ["add", "."], ["commit", "-qm", "base"]):
                subprocess.run(
                    ["git", "-c", "user.name=test", "-c", "user.email=test@localhost", *args], cwd=root, check=True
                )
            (root / source).write_text("// shared\n")
            previous = Path.cwd()
            os.chdir(root)
            try:
                files = [(source.as_posix(), True)]
                consumers = conditional_consumers(files, "HEAD", False, METAL_MARKERS)
                self.assertEqual(consumers, {source.as_posix()})
                self.assertEqual(platform_plan(files, "windows", consumers)[:2], ("modules", [source.as_posix()]))
                self.assertEqual(platform_plan(files, "metal", consumers)[:2], ("modules", [source.as_posix()]))
            finally:
                os.chdir(previous)

    def test_configured_objects_and_archives_share_one_invocation(self):
        source = "servers/rendering/renderer_viewport.cpp"
        bmp = "modules/bmp/image_loader_bmp.cpp"
        targets = ["bin/obj/renderer.one.o", "bin/obj/renderer.two.o"]
        calls = []

        def configured(command, *, check):
            if "-n" in command:
                for flag in command:
                    if flag.startswith("module_build_inventory="):
                        Path(flag.split("=", 1)[1]).write_text(json.dumps({"bmp": [bmp]}))
                    if flag.startswith("engine_object_inventory="):
                        Path(flag.split("=", 1)[1]).write_text(json.dumps({source: targets}))
            else:
                calls.append(command)

        with patch("build_engine_modules.subprocess.run", side_effect=configured):
            self.assertEqual(build([source, bmp], [])[0], "modules")
            self.assertEqual(calls[0][3:], [*targets, "module-bmp"])
            self.assertEqual(build([source, "drivers/metal/missing.cpp"], [])[0], "full")
            self.assertEqual(len(calls), 1)

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
