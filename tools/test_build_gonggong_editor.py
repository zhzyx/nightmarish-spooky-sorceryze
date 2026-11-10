"""Exercise CLI checkout validation independently of an expensive native compile."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


class EditorCliTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.native = SimpleNamespace(build_or_reuse=self.reuse)
        spec = importlib.util.spec_from_file_location(
            "editor_cli", Path(__file__).with_name("build_gonggong_editor.py")
        )
        self.cli = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, editor_native_cache=self.native):
            spec.loader.exec_module(self.cli)
        (self.root / "bin").mkdir()
        (self.root / "bin/godot.windows.editor.x86_64.console.exe").write_bytes(b"console")
        self.head = "1" * 40
        self.source = "source"
        self.calls = []
        self.status = "built"

    def reuse(self, root, options, artifact, produce, *, env):
        self.assertEqual(root, self.root)
        self.assertEqual(artifact, root / "bin/godot.windows.editor.x86_64.exe")
        self.assertEqual(env["MSYSTEM"], "")
        self.options = options
        if self.status == "built":
            produce()
        return {"status": self.status, "artifact_sha256": "123"}

    def run_cli(self, *, fail=False):
        def external_run(cmd, cwd, check, env=None):
            self.calls.append(cmd)
            if "tools/package_tianshu_ui.py" in cmd:
                (cwd / "bin/tianshu-ui.json").write_text("current checkout")
            if "--test" in cmd and fail:
                raise subprocess.CalledProcessError(1, cmd)

        with (
            patch.object(self.cli.subprocess, "run", side_effect=external_run),
            patch.object(self.cli, "git_bytes", return_value=self.head.encode()),
            patch.object(self.cli, "source_snapshot", return_value={"source_digest": self.source}),
        ):
            return self.cli.build(self.root, 2, True, self.root.parent / "objects", 6)

    def test_compile_command_and_candidate_receipts_on_hit(self):
        first = self.run_cli()
        self.assertIn("use_mingw=yes", self.calls[0])
        self.assertIn("cache_limit=6", self.calls[0])
        self.assertIn("-j2", self.calls[0])
        self.assertTrue(all(f"{k}={v}" in self.calls[0] for k, v in self.options.items()))
        self.status = "hit"
        self.head = "2" * 40
        self.calls.clear()
        second = self.run_cli()
        self.assertEqual(first["native"]["artifact_sha256"], second["native"]["artifact_sha256"])
        self.assertNotEqual(first["revision"], second["revision"])
        self.assertEqual(len(self.calls), 2)
        self.assertIn("tools/package_tianshu_ui.py", self.calls[0])
        self.assertIn("--test-case=[AIChat]*", self.calls[1])
        receipts = [json.loads(p.read_text()) for p in (self.root / "bin/gonggong-build-receipts").glob("*.json")]
        self.assertCountEqual([r["revision"] for r in receipts], [first["revision"], second["revision"]])

    def test_failed_local_validation_never_publishes_success_receipt(self):
        self.status = "hit"
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_cli(fail=True)
        self.assertFalse((self.root / "bin/gonggong-build-receipts").exists())


if __name__ == "__main__":
    unittest.main()
