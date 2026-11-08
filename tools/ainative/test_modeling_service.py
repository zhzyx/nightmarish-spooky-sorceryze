"""Service routing for CLI modeling; no server or paid model calls."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from generation_service import ServiceError, check_service, prepare_provider, restore_provider, settings

CLI = dict(connected=True, code="", version="test", auth_mode="chatgpt", message="ready")
IMAGE = dict(CLI, image_generation=True)


class ModelingServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.godot = self.root / "godot.exe"
        self.builder = self.root / "modeling_builder.gd"
        self.godot.touch()
        self.builder.touch()
        self.config = settings(
            dict(mode="codex_modeling", cli_path="codex", godot_path=str(self.godot), builder_path=str(self.builder))
        )

    def test_discovery_never_contacts_mesh_server(self):
        with (
            patch("modeling_provider.check_modeling_cli", return_value=CLI),
            patch("codex_provider.check_cli", return_value=IMAGE),
            patch("generation_service.read_endpoint", side_effect=AssertionError("unexpected network")),
        ):
            report = check_service(self.config)
        self.assertTrue(all(item["ready"] for item in report["capabilities"].values()))
        self.assertEqual([], report["models"]["mesh"])

    def test_modeling_does_not_require_image_generation_feature(self):
        with (
            patch("modeling_provider.check_modeling_cli", return_value=CLI),
            patch(
                "codex_provider.check_cli",
                return_value=dict(connected=False, code="cli_image_unavailable", message="no imagegen"),
            ),
        ):
            report = check_service(self.config)
        self.assertTrue(report["capabilities"]["text_to_mesh"]["ready"])
        self.assertTrue(report["capabilities"]["image_to_mesh"]["ready"])
        self.assertFalse(report["capabilities"]["text_to_image"]["ready"])

    def test_missing_builder_is_not_advertised_as_ready(self):
        self.builder.unlink()
        with (
            patch("modeling_provider.check_modeling_cli", return_value=CLI),
            patch("codex_provider.check_cli", return_value=IMAGE),
        ):
            report = check_service(self.config)
        self.assertFalse(report["capabilities"]["text_to_mesh"]["ready"])
        self.assertEqual("modeling_runtime_missing", report["capabilities"]["text_to_mesh"]["code"])

    def test_mixed_graph_freezes_distinct_providers_and_restores(self):
        model = dict(nodes=[dict(id="image", type="text_to_image"), dict(id="mesh", type="text_to_mesh")], edges=[])
        with (
            patch("modeling_provider.check_modeling_cli", return_value=CLI),
            patch("codex_provider.check_cli", return_value=IMAGE),
        ):
            registry, providers, snapshot = prepare_provider(self.config, model, str(self.root / "jobs.db"), "run")
        self.assertEqual(["codex", "codex-modeling"], [n["provider"] for n in model["nodes"]])
        self.assertIsNone(snapshot["image_provider"]["mesh_config"])
        self.config["godot_path"] = "changed-after-create"
        restored_registry, restored = restore_provider(snapshot)
        self.assertEqual(str(self.godot), restored["codex-modeling"].config["godot_path"])
        self.assertEqual(providers["codex-modeling"].describe(), restored["codex-modeling"].describe())
        self.assertEqual(set(providers), set(restored))

    def test_machine_runtime_paths_are_only_valid_in_modeling_mode(self):
        for mode in ["offline", "comfy", "codex"]:
            with self.subTest(mode=mode), self.assertRaises(ServiceError):
                settings(dict(self.config, mode=mode))
        for field in ["godot_path", "builder_path"]:
            invalid = dict(self.config)
            invalid.pop(field)
            with self.subTest(field=field), self.assertRaises(ServiceError):
                settings(invalid)


if __name__ == "__main__":
    unittest.main()
