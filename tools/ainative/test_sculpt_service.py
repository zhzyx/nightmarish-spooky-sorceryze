"""Routing and frozen snapshots for CLI/Blender sculpt service; no paid calls."""

import builtins
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from generation_service import (
    ServiceError,
    _blender_runtime,
    check_service,
    prepare_provider,
    restore_provider,
    settings,
)

CLI = dict(connected=True, code="", version="test", auth_mode="chatgpt", message="ready")
IMAGE = dict(CLI, image_generation=True)


class SculptServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.builder = self.root / "sculpt_builder.py"
        self.builder.touch()
        self.anatomy = self.builder.with_name("anatomy_base.py")
        self.anatomy.touch()
        self.body_anatomy = self.builder.with_name("anatomy_body.py")
        self.body_anatomy.touch()
        for name in ("character_detail.py", "organic_detail.py", "period_groom.py"):
            self.builder.with_name(name).touch()
        self.calibration = self.builder.with_name("anatomy_calibration.py")
        self.calibration.touch()
        self.config = settings(
            dict(
                mode="codex_sculpt",
                cli_path="codex",
                blender_path="blender",
                builder_path=str(self.builder),
                endpoint="",
            )
        )
        self.runtime = dict(executable="verified-blender.exe", version="Blender5.1")

    def test_discovery_has_no_comfy_or_neural_service_calls(self):
        with (
            patch("generation_service._blender_runtime", return_value=self.runtime),
            patch("modeling_provider.check_modeling_cli", return_value=CLI),
            patch("codex_provider.check_cli", return_value=IMAGE),
            patch("generation_service.read_endpoint", side_effect=AssertionError("unexpected server")),
        ):
            report = check_service(self.config)
        self.assertTrue(all(v["ready"] for v in report["capabilities"].values()))
        self.assertEqual([], report["models"]["mesh"])
        self.assertNotIn("已验收", report["capabilities"]["text_to_mesh"]["message"])

    def test_missing_blender_does_not_block_existing_image_mode(self):
        with (
            patch("generation_service._blender_runtime", return_value=None),
            patch("modeling_provider.check_modeling_cli", return_value=CLI),
            patch("codex_provider.check_cli", return_value=IMAGE),
        ):
            report = check_service(self.config)
            model = dict(nodes=[dict(id="image", type="text_to_image")], edges=[])
            _, providers, snapshot = prepare_provider(self.config, model, str(self.root / "jobs.db"), "run")
        self.assertFalse(report["capabilities"]["text_to_mesh"]["ready"])
        self.assertTrue(report["capabilities"]["text_to_image"]["ready"])
        self.assertEqual("codex", model["nodes"][0]["provider"])
        self.assertIsNone(snapshot["image_provider"]["mesh_config"])

    def test_missing_builder_sibling_data_blocks_mesh_before_blender_probe_only(self):
        for dependency in (
            self.anatomy,
            self.body_anatomy,
            self.calibration,
            self.builder.with_name("character_detail.py"),
            self.builder.with_name("organic_detail.py"),
            self.builder.with_name("period_groom.py"),
        ):
            with self.subTest(dependency=dependency.name):
                dependency.unlink()
                with (
                    patch("generation_service.shutil.which", return_value="verified-blender.exe"),
                    patch(
                        "generation_service.subprocess.run",
                        side_effect=AssertionError("missing data must fail before launch"),
                    ),
                    patch("modeling_provider.check_modeling_cli", return_value=CLI),
                    patch("codex_provider.check_cli", return_value=IMAGE),
                ):
                    self.assertIsNone(_blender_runtime(self.config))
                    report = check_service(self.config)
                    model = dict(nodes=[dict(id="image", type="text_to_image")], edges=[])
                    _, _, snapshot = prepare_provider(self.config, model, str(self.root / "jobs.db"), "image-only")
                self.assertFalse(report["capabilities"]["image_to_mesh"]["ready"])
                self.assertEqual("sculpt_runtime_missing", report["capabilities"]["image_to_mesh"]["code"])
                self.assertTrue(report["capabilities"]["image_to_image"]["ready"])
                self.assertEqual(model["nodes"][0]["provider"], "codex")
                self.assertIsNone(snapshot["image_provider"]["mesh_config"])
                dependency.touch()

    def test_invalid_calibration_blocks_only_mesh_before_blender_launch(self):
        with (
            patch("generation_service.shutil.which", return_value="verified-blender.exe"),
            patch("sculpt_provider.load_operator_calibration", side_effect=ValueError("calibration_invalid")),
            patch(
                "generation_service.subprocess.run", side_effect=AssertionError("invalid asset must fail before launch")
            ),
            patch("modeling_provider.check_modeling_cli", return_value=CLI),
            patch("codex_provider.check_cli", return_value=IMAGE),
        ):
            report = check_service(self.config)
        self.assertFalse(report["capabilities"]["image_to_mesh"]["ready"])
        self.assertTrue(report["capabilities"]["image_to_image"]["ready"])

    def test_image_only_prepare_and_reopen_do_not_import_missing_sculpt_stack(self):
        self.builder.with_name("character_detail.py").unlink()
        original_import = builtins.__import__
        sculpt_imports = []

        def isolated_import(name, *args, **kwargs):
            if name == "sculpt_provider":
                sculpt_imports.append(name)
                raise ImportError("isolated missing optional sculpt dependency")
            return original_import(name, *args, **kwargs)

        with (
            patch("builtins.__import__", side_effect=isolated_import),
            patch("generation_service.shutil.which", return_value="verified-blender.exe"),
            patch("generation_service.subprocess.run", side_effect=AssertionError("unexpected builder process")),
            patch("modeling_provider.check_modeling_cli", side_effect=AssertionError("unexpected sculpt auth")),
            patch("codex_provider.check_cli", return_value=IMAGE),
        ):
            report = check_service(self.config)
            self.assertTrue(report["capabilities"]["image_to_image"]["ready"])
            self.assertFalse(report["capabilities"]["image_to_mesh"]["ready"])
            model = dict(nodes=[dict(id="image", type="text_to_image")], edges=[])
            _, providers, snapshot = prepare_provider(self.config, model, str(self.root / "jobs.db"), "image-only")
            _, restored = restore_provider(snapshot)
            self.assertIsNone(snapshot["provider"])
            self.assertNotIn("codex-sculpt", providers)
            self.assertNotIn("codex-sculpt", restored)
            self.assertEqual(providers["codex"].describe(), restored["codex"].describe())
            with self.assertRaises(ServiceError) as failure:
                prepare_provider(
                    self.config,
                    dict(nodes=[dict(id="mesh", type="text_to_mesh")], edges=[]),
                    str(self.root / "jobs.db"),
                    "mesh",
                )
            self.assertEqual(failure.exception.code, "sculpt_runtime_missing")
        self.assertEqual(sculpt_imports, [])

    def test_unimportable_sculpt_module_is_structured_mesh_preflight_failure(self):
        original_import = builtins.__import__
        sculpt_imports = []

        def isolated_import(name, *args, **kwargs):
            if name == "sculpt_provider":
                sculpt_imports.append(name)
                raise ImportError("isolated corrupt optional sculpt dependency")
            return original_import(name, *args, **kwargs)

        with (
            patch("builtins.__import__", side_effect=isolated_import),
            patch("generation_service.shutil.which", return_value="verified-blender.exe"),
            patch("generation_service.subprocess.run", side_effect=AssertionError("unexpected builder process")),
            patch("modeling_provider.check_modeling_cli", side_effect=AssertionError("unexpected sculpt auth")),
            patch("codex_provider.check_cli", return_value=IMAGE),
        ):
            report = check_service(self.config)
            self.assertTrue(report["capabilities"]["text_to_image"]["ready"])
            self.assertEqual(report["capabilities"]["text_to_mesh"]["code"], "sculpt_runtime_missing")
            attempts = len(sculpt_imports)
            _, _, snapshot = prepare_provider(
                self.config,
                dict(nodes=[dict(id="image", type="text_to_image")], edges=[]),
                str(self.root / "jobs.db"),
                "image",
            )
            restore_provider(snapshot)
            self.assertEqual(len(sculpt_imports), attempts)
            with self.assertRaises(ServiceError) as failure:
                prepare_provider(
                    self.config,
                    dict(nodes=[dict(id="mesh", type="text_to_mesh")], edges=[]),
                    str(self.root / "jobs.db"),
                    "mesh",
                )
            self.assertEqual(failure.exception.code, "sculpt_runtime_missing")

    def test_sculpt_auth_does_not_require_image_generation_feature(self):
        with (
            patch("generation_service._blender_runtime", return_value=self.runtime),
            patch("modeling_provider.check_modeling_cli", return_value=CLI),
            patch(
                "codex_provider.check_cli",
                return_value=dict(connected=False, code="cli_image_unavailable", message="image feature unavailable"),
            ),
        ):
            report = check_service(self.config)
        self.assertTrue(report["capabilities"]["image_to_mesh"]["ready"])
        self.assertFalse(report["capabilities"]["text_to_image"]["ready"])

    def test_mixed_graph_restores_run_scoped_sculpt_snapshot(self):
        model = dict(nodes=[dict(id="image", type="text_to_image"), dict(id="mesh", type="text_to_mesh")], edges=[])
        with (
            patch("generation_service._blender_runtime", return_value=self.runtime),
            patch("modeling_provider.check_modeling_cli", return_value=CLI),
            patch("codex_provider.check_cli", return_value=IMAGE),
        ):
            _, providers, snapshot = prepare_provider(self.config, model, str(self.root / "jobs.db"), "run")
        self.assertEqual(["codex", "codex-sculpt"], [n["provider"] for n in model["nodes"]])
        self.config["blender_path"] = "changed-after-create"
        _, restored = restore_provider(snapshot)
        self.assertEqual("verified-blender.exe", restored["codex-sculpt"].config["blender_path"])
        self.assertEqual(providers["codex-sculpt"].describe(), restored["codex-sculpt"].describe())

    def test_engine_paths_cannot_be_confused_across_modes(self):
        for field in ["blender_path", "builder_path"]:
            bad = dict(self.config)
            bad.pop(field)
            with self.subTest(field=field), self.assertRaises(ServiceError):
                settings(bad)
        for mode in ["offline", "comfy", "codex", "codex_modeling"]:
            with self.subTest(mode=mode), self.assertRaises(ServiceError):
                settings(dict(self.config, mode=mode))
        with self.assertRaises(ServiceError):
            settings(dict(self.config, godot_path="wrong-executor.exe"))


if __name__ == "__main__":
    unittest.main()
