"""Real SCons consumer and hosted Git identity regressions (no editor compilation)."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / ".github/scripts"))
import editor_native_cache as cache  # noqa: E402
import windows_editor_artifact as artifact  # noqa: E402


class HostInputTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.name = "customizations/components/tianxuan/server/service.py"
        self.host = self.root / self.name
        self.host.parent.mkdir(parents=True)
        self.host.write_text("host v1")
        self.policy = self.root / "tools/native_host_inputs.json"
        self.policy.parent.mkdir()
        self.policy.write_text(json.dumps({"schema_version": 1, "inputs": [self.name]}))

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.PIPE)

    def commit(self):
        self.git("add", ".")
        self.git("-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture")

    def test_hosted_identity_uses_policy_and_actual_consumers_with_full_fallback(self):
        self.git("init", "-q")
        (self.root / "native.cpp").write_text("native")
        self.commit()
        graph = ["native.cpp"]
        with patch.object(cache, "probe", side_effect=lambda *args: {"native_sources": graph}):

            def identity():
                return artifact.source_identity(self.root, ["platform=windows"], {})

            first = identity()
            self.policy.write_text("uncommitted policy must not affect the hosted Git identity")
            self.assertEqual(first, identity())
            self.git("checkout", "--", "tools/native_host_inputs.json")
            self.host.write_text("host v2")
            self.commit()
            self.assertEqual(first, identity())
            graph.append(self.name)
            embedded = identity()
            self.assertNotEqual(first, embedded)
            self.host.write_text("host v3")
            self.commit()
            self.assertNotEqual(embedded, identity())
            graph.clear()
            fallback = identity()
            self.host.write_text("host v4")
            self.commit()
            self.assertNotEqual(fallback, identity())
            graph.append("native.cpp")
            self.policy.write_text("invalid json")
            self.commit()
            invalid_policy = identity()
            self.host.write_text("host v5")
            self.commit()
            self.assertNotEqual(invalid_policy, identity())

    @unittest.skipUnless(importlib.util.find_spec("SCons"), "SCons required for actual generator probe")
    def test_actual_generator_consumption_overrides_host_inventory(self):
        script = (
            "import sys\n"
            f"sys.path.insert(0, {str(ROOT / 'tools')!r})\n"
            "from editor_native_cache import write_probe\n"
            "env = Environment(tools=[])\n"
            "env.msvc = False\n"
            "env['library_type'] = 'executable'\n"
        )
        finish = "write_probe(env, ARGUMENTS['gonggong_native_probe'], {'git_hash': '', 'git_timestamp': 0})\n"
        source = self.root / "SConstruct"
        source.write_text(script + finish)
        independent = cache.probe(self.root, {}, dict(os.environ))["native_sources"]
        self.assertNotIn(self.name, independent)
        self.assertTrue(cache.is_external_data(self.name, independent, cache.host_inputs(self.root)))
        source.write_text(script + f"env.Command('native.gen', {self.name!r}, Copy('$TARGET', '$SOURCE'))\n" + finish)
        embedded = cache.probe(self.root, {}, dict(os.environ))["native_sources"]
        self.assertIn(self.name, embedded)
        self.assertFalse(cache.is_external_data(self.name, embedded, cache.host_inputs(self.root)))
        self.assertFalse((self.root / "native.gen").exists(), "probe must not build the target")

    @unittest.skipUnless(importlib.util.find_spec("SCons"), "SCons required for repository graph audit")
    def test_repository_host_inventory_has_zero_overlap_with_actual_scons_graph(self):
        configured = cache.host_inputs(ROOT)
        self.assertGreaterEqual(len(configured), 100)
        platform_name = "windows" if os.name == "nt" else "linuxbsd"
        options = {
            "platform": platform_name,
            "target": "editor",
            "dev_mode": "yes",
            "debug_symbols": "no",
            "accesskit": "no",
            "angle": "no",
        }
        if os.name == "nt":
            options["d3d12"] = "no"
        probed = set(cache.probe(ROOT, options, dict(os.environ))["native_sources"])
        self.assertGreater(len(probed), 5000)
        self.assertEqual(configured & probed, set())


if __name__ == "__main__":
    unittest.main()
