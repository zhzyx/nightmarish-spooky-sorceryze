import shlex
import tempfile
import unittest
from pathlib import Path

from BuildGameplay import (
    CORE_SOURCES,
    PUBLIC_HEADERS,
    TEST_SOURCES,
    artifact,
    parse_depfile,
    parse_msvc_includes,
    quoted_response,
    repository_name,
)


class BuildGameplayTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def write(self, name, content=""):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path

    def test_source_lists_are_unique_and_outside_godot_roots(self):
        sources = CORE_SOURCES + TEST_SOURCES
        self.assertEqual(len(sources), len(set(sources)))
        names = sources + ["engine_next/include/" + header for header in PUBLIC_HEADERS]
        for name in names:
            self.assertFalse(name.startswith(("core/", "modules/", "scene/", "servers/", "editor/")))
            self.assertTrue(name.startswith("engine_next/"))

    def test_depfile_accepts_only_declared_repository_inputs(self):
        self.write("engine_next/include/EngineNext/Gameplay/Vector3.h")
        self.write("engine_next/Tests/TestFramework.h")
        depfile = self.write(
            "build/engine_next/test.d",
            "test.o: engine_next/include/EngineNext/Gameplay/Vector3.h engine_next/Tests/TestFramework.h\n",
        )
        includes = parse_depfile(self.root, depfile)
        self.assertEqual(len(includes), 2)
        self.assertTrue(all(repository_name(self.root, name).startswith("engine_next/") for name in includes))

    def test_depfile_accepts_generated_header_probes(self):
        generated = self.write("build/engine_next/probe/PublicHeader0.cpp")
        depfile = self.write("build/engine_next/probe/PublicHeader0.d", "PublicHeader0.o: build/engine_next/probe/PublicHeader0.cpp\n")
        self.assertEqual(parse_depfile(self.root, depfile), [str(generated)])

    def test_godot_and_undeclared_includes_are_rejected(self):
        for name in ("core/object/object.h", "modules/gameplay/gameplay_prediction.h", "outside.h"):
            with self.subTest(name=name):
                depfile = self.write("build/engine_next/test.d", "test.o: " + name + "\n")
                with self.assertRaisesRegex(ValueError, "undeclared repository include"):
                    parse_depfile(self.root, depfile)

    def test_msvc_include_output_uses_the_same_boundary(self):
        rejected = self.root / "core/object/object.h"
        output = ("Note: including file: " + str(rejected) + "\r\n").encode()
        with self.assertRaisesRegex(ValueError, "undeclared repository include"):
            parse_msvc_includes(self.root, output)
        system_header = self.root.parent / "system-sdk-vector"
        accepted = ("Note: including file: " + str(system_header) + "\r\n").encode()
        self.assertEqual(parse_msvc_includes(self.root, accepted), [str(system_header.resolve())])

    def test_response_quoting_round_trips_spaces(self):
        values = [self.root / "directory with spaces/object.o", self.root / "library.a"]
        posix = quoted_response(values, windows=False)
        self.assertEqual([Path(value) for value in shlex.split(posix)], values)
        windows = quoted_response(values, windows=True)
        self.assertIn('"', windows)
        self.assertTrue(windows.endswith("\n"))

    def test_artifact_binds_repository_path_and_bytes(self):
        path = self.write("build/engine_next/object.o", b"object")
        record = artifact(self.root, path)
        self.assertEqual(record["path"], "build/engine_next/object.o")
        self.assertEqual(record["sha256"], "2958d416d08aa5a472d7b509036cb7eafd542add84527e66a145ea64cb4cdc75")


if __name__ == "__main__":
    unittest.main()
