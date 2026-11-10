"""Kimi service routing with mocked discovery; no AI inference or other provider calls."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from generation_service import (
    ServiceError,
    check_service,
    prepare_provider,
    restore_provider,
    settings,
)
from kimi_provider import DEFAULT_ENDPOINT, DEFAULT_MODEL, KimiNativeProvider


class KimiServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kimi-service-fixture-")
        self.root = Path(self.tmp.name)
        self.godot = self.root / "godot-fixture"
        self.builder = self.root / "modeling_builder.gd"
        self.godot.write_bytes(b"fixture")
        self.builder.write_text("# fixture\n", encoding="utf-8")
        self.value = {
            "schema_version": 1,
            "mode": "kimi_native",
            "endpoint": DEFAULT_ENDPOINT,
            "image_model": "",
            "mesh_model": "",
            "kimi_model": DEFAULT_MODEL,
            "godot_path": str(self.godot),
            "builder_path": str(self.builder),
        }
        self.config = settings(self.value)
        self.discovery = {
            "connected": True,
            "code": "",
            "message": "synthetic discovery",
            "auth_mode": "environment_api_key",
            "available_models": [DEFAULT_MODEL],
        }

    def tearDown(self):
        self.tmp.cleanup()

    def model(self, kind="text_to_mesh"):
        return {
            "nodes": [
                {
                    "id": "generate",
                    "type": kind,
                    "provider": "local-copy",
                    "parameters": {"prompt": "a simple table"},
                }
            ],
            "edges": [],
        }

    def test_probe_has_only_kimi_mesh_capabilities_and_never_calls_legacy_backends(self):
        with (
            patch("kimi_provider.check_kimi", return_value=self.discovery) as kimi,
            patch("codex_provider.check_cli", side_effect=AssertionError("Codex probe called")),
            patch("modeling_provider.check_modeling_cli", side_effect=AssertionError("Modeling CLI probe called")),
            patch("generation_service.read_endpoint", side_effect=AssertionError("ComfyUI probe called")),
        ):
            report = check_service(self.value)
        kimi.assert_called_once_with({"endpoint": DEFAULT_ENDPOINT, "model": DEFAULT_MODEL})
        self.assertEqual(report["mode"], "kimi_native")
        self.assertTrue(report["connected"])
        self.assertTrue(report["capabilities"]["text_to_mesh"]["ready"])
        self.assertTrue(report["capabilities"]["image_to_mesh"]["ready"])
        self.assertFalse(report["capabilities"]["text_to_image"]["ready"])
        self.assertEqual(report["capabilities"]["image_to_image"]["code"], "node_unsupported")
        self.assertEqual(report["models"], {"image": [], "mesh": [DEFAULT_MODEL]})

    def test_prepare_and_restore_freeze_only_nonsecret_kimi_configuration(self):
        with (
            patch("kimi_provider.check_kimi", return_value=self.discovery),
            patch("codex_provider.check_cli", side_effect=AssertionError("Codex probe called")),
            patch("generation_service.read_endpoint", side_effect=AssertionError("ComfyUI probe called")),
        ):
            registry, providers, snapshot = prepare_provider(
                self.config, self.model(), self.root / "executor.sqlite", "a" * 32
            )
        self.assertEqual(snapshot["mode"], "kimi_native")
        self.assertEqual(set(snapshot), {"mode", "provider"})
        self.assertEqual(snapshot["provider"]["model"], DEFAULT_MODEL)
        self.assertNotIn("api_key", json.dumps(snapshot))
        self.assertNotIn("KIMI_API_KEY", json.dumps(snapshot))
        self.assertEqual(self.model()["nodes"][0]["provider"], "local-copy")
        self.assertIsInstance(providers["kimi_native"], KimiNativeProvider)
        self.assertIsNotNone(registry.get("image_to_mesh", "1"))
        with patch("codex_provider.CodexProvider", side_effect=AssertionError("Codex restore called")):
            restored_registry, restored = restore_provider(snapshot)
        self.assertIsInstance(restored["kimi_native"], KimiNativeProvider)
        self.assertIsNotNone(restored_registry.get("text_to_mesh", "1"))
        self.assertNotIn("codex", restored)
        self.assertNotIn("comfy", restored)

    def test_prepare_routes_nodes_and_rejects_images_before_network(self):
        model = self.model("text_to_mesh")
        with patch("kimi_provider.check_kimi", return_value=self.discovery):
            prepare_provider(self.config, model, self.root / "runs.sqlite", "b" * 32)
        self.assertEqual(model["nodes"][0]["provider"], "kimi_native")
        for kind in ("text_to_image", "image_to_image"):
            with self.subTest(kind=kind), patch("kimi_provider.check_kimi") as discovery:
                with self.assertRaises(ServiceError) as error:
                    prepare_provider(self.config, self.model(kind), self.root / (kind + ".sqlite"), "c" * 32)
                self.assertEqual(error.exception.code, "node_unsupported")
                discovery.assert_not_called()

    def test_auth_and_builder_failures_are_distinct_and_legacy_settings_remain_valid(self):
        with patch(
            "kimi_provider.check_kimi",
            return_value={**self.discovery, "connected": False, "code": "kimi_key_missing"},
        ):
            report = check_service(self.value)
        self.assertFalse(report["connected"])
        self.assertEqual(report["capabilities"]["text_to_mesh"]["code"], "kimi_key_missing")
        self.assertEqual(report["capabilities"]["image_to_mesh"]["code"], "kimi_key_missing")
        with patch("kimi_provider.check_kimi", return_value=self.discovery):
            report = check_service({**self.value, "builder_path": str(self.root / "missing.gd")})
        self.assertEqual(report["capabilities"]["text_to_mesh"]["code"], "modeling_runtime_missing")
        legacy = settings({"mode": "comfy", "endpoint": "http://127.0.0.1:8188"})
        self.assertEqual(legacy["mode"], "comfy")
        with self.assertRaises(ServiceError):
            settings({**self.value, "cli_path": "codex"})
        with self.assertRaises(ServiceError):
            settings({**self.value, "api_key": "forbidden"})
        with self.assertRaises(ServiceError):
            settings({**self.value, "endpoint": "https://example.com/coding/v1"})


if __name__ == "__main__":
    unittest.main()
