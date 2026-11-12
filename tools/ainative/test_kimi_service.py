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
from kimi_work_image_provider import KimiWorkImageProvider


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

    def image_value(self):
        return {
            **self.value,
            "image_tool_path": str(self.root / "fixture" / "image_generation_tool.py"),
            "image_pythonw_path": str(self.root / "pythonw.exe"),
        }

    def image_discovery(self):
        return {
            "connected": True,
            "code": "",
            "message": "synthetic local image tool; no generation",
            "provider": "kimi_work_image",
            "generation_version": "v2",
            "tool_fingerprint": "fixture-image-tool-fingerprint",
        }

    def test_mesh_stays_ready_when_image_tool_is_absent_or_invalid(self):
        with (
            patch("kimi_provider.check_kimi", return_value=self.discovery) as kimi,
            patch("codex_provider.check_cli", side_effect=AssertionError("Codex probe called")),
            patch("modeling_provider.check_modeling_cli", side_effect=AssertionError("Modeling CLI probe called")),
            patch("generation_service.read_endpoint", side_effect=AssertionError("ComfyUI probe called")),
        ):
            for value in (self.value, self.image_value()):
                report = check_service(value)
                self.assertTrue(report["connected"])
                self.assertTrue(report["capabilities"]["text_to_mesh"]["ready"])
                self.assertTrue(report["capabilities"]["image_to_mesh"]["ready"])
                self.assertFalse(report["capabilities"]["text_to_image"]["ready"])
                self.assertIn(
                    report["capabilities"]["image_to_image"]["code"], ("image_not_configured", "image_tool_missing")
                )
                self.assertEqual(report["models"], {"image": [], "mesh": [DEFAULT_MODEL]})
        kimi.assert_called_with({"endpoint": DEFAULT_ENDPOINT, "model": DEFAULT_MODEL})

    def test_independent_image_discovery_does_not_call_legacy_backends(self):
        with (
            patch("kimi_provider.check_kimi", return_value=self.discovery),
            patch("kimi_work_image_provider.check_image_tool", return_value=self.image_discovery()) as image,
            patch("codex_provider.check_cli", side_effect=AssertionError("Codex probe called")),
            patch("generation_service.read_endpoint", side_effect=AssertionError("ComfyUI probe called")),
        ):
            report = check_service(self.image_value())
        image.assert_called_once_with(self.image_value()["image_tool_path"], self.image_value()["image_pythonw_path"])
        self.assertTrue(report["connected"])
        self.assertTrue(report["capabilities"]["text_to_image"]["ready"])
        self.assertTrue(report["capabilities"]["image_to_image"]["ready"])
        self.assertTrue(report["capabilities"]["text_to_mesh"]["ready"])
        self.assertEqual(report["kimi_work_image"]["provider"], "kimi_work_image")
        self.assertEqual(report["models"]["image"], ["Kimi Work agent-gw generate_image v2"])
        self.assertIn("独立 Kimi Work 图像服务", report["message"])

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
        self.assertNotIn("kimi_work_image", providers)
        self.assertIsNotNone(registry.get("image_to_mesh", "1"))
        with patch("codex_provider.CodexProvider", side_effect=AssertionError("Codex restore called")):
            restored_registry, restored = restore_provider(snapshot)
        self.assertIsInstance(restored["kimi_native"], KimiNativeProvider)
        self.assertIsNotNone(restored_registry.get("text_to_mesh", "1"))
        self.assertNotIn("codex", restored)
        self.assertNotIn("comfy", restored)

    def test_mixed_nodes_route_and_composite_snapshot_restores(self):
        model = {
            "nodes": [
                {"id": kind, "type": kind, "provider": "local-copy", "parameters": {"prompt": "fixture"}}
                for kind in ("text_to_mesh", "text_to_image", "image_to_image")
            ],
            "edges": [],
        }
        with (
            patch("kimi_provider.check_kimi", return_value=self.discovery),
            patch("kimi_work_image_provider.check_image_tool", return_value=self.image_discovery()),
            patch("codex_provider.check_cli", side_effect=AssertionError("Codex probe called")),
            patch("generation_service.read_endpoint", side_effect=AssertionError("ComfyUI probe called")),
        ):
            _, providers, snapshot = prepare_provider(
                settings(self.image_value()), model, self.root / "mixed.sqlite", "b" * 32
            )
        self.assertEqual(
            [node["provider"] for node in model["nodes"]], ["kimi_native", "kimi_work_image", "kimi_work_image"]
        )
        self.assertEqual(set(snapshot), {"mode", "provider", "image_provider"})
        self.assertIsInstance(providers["kimi_native"], KimiNativeProvider)
        self.assertIsInstance(providers["kimi_work_image"], KimiWorkImageProvider)
        self.assertNotIn("api_key", json.dumps(snapshot))
        self.assertNotIn("credential", json.dumps(snapshot).lower())
        with patch("codex_provider.CodexProvider", side_effect=AssertionError("Codex restore called")):
            _, restored = restore_provider(snapshot)
        self.assertIsInstance(restored["kimi_native"], KimiNativeProvider)
        self.assertIsInstance(restored["kimi_work_image"], KimiWorkImageProvider)
        self.assertNotIn("comfy", restored)

    def test_pure_images_do_not_require_mesh_provider_and_missing_tool_is_actionable(self):
        model = self.model("text_to_image")
        with (
            patch("kimi_provider.check_kimi", return_value=self.discovery),
            patch("kimi_work_image_provider.check_image_tool", return_value=self.image_discovery()),
        ):
            _, providers, snapshot = prepare_provider(
                settings(self.image_value()), model, self.root / "image.sqlite", "c" * 32
            )
        self.assertIsNone(snapshot["provider"])
        self.assertNotIn("kimi_native", providers)
        self.assertIsInstance(providers["kimi_work_image"], KimiWorkImageProvider)
        self.assertEqual(model["nodes"][0]["provider"], "kimi_work_image")
        _, restored = restore_provider(snapshot)
        self.assertEqual(set(restored) - {"local-copy"}, {"kimi_work_image"})
        with patch("kimi_provider.check_kimi", return_value=self.discovery):
            with self.assertRaises(ServiceError) as error:
                prepare_provider(self.config, self.model("image_to_image"), self.root / "missing.sqlite", "d" * 32)
            self.assertEqual(error.exception.code, "image_not_configured")
            prepare_provider(self.config, self.model(), self.root / "mesh-without-image.sqlite", "e" * 32)

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
