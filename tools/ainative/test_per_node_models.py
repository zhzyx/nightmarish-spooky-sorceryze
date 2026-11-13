"""Node-scoped model routing tests; no real generation requests are submitted."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from generation_service import (
    IMAGE_NODES,
    MESH_NODES,
    ServiceError,
    prepare_provider,
    restore_provider,
)


class PerNodeModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.info = {key: {} for key in IMAGE_NODES | MESH_NODES | {"ImageScale", "VAEEncode"}}
        self.info["CheckpointLoaderSimple"] = {"input": {"required": {"ckpt_name": [["image-a", "image-b"]]}}}
        self.info["ImageOnlyCheckpointLoader"] = {"input": {"required": {"ckpt_name": [["mesh-a", "mesh-b"]]}}}
        self.config = dict(
            schema_version=1,
            mode="comfy",
            endpoint="http://127.0.0.1:8188",
            image_model="image-a",
            mesh_model="mesh-a",
        )
        self.report = dict(
            connected=True,
            models={"image": ["image-a", "image-b"], "mesh": ["mesh-a", "mesh-b"]},
            backend_revision="fixture",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_comfy_nodes_use_and_restore_distinct_models(self):
        model = dict(
            nodes=[
                dict(id="a", type="text_to_image", model="image-a", parameters={"prompt": "a"}),
                dict(id="b", type="text_to_image", model="image-b", parameters={"prompt": "b"}),
            ],
            edges=[],
        )
        with patch("generation_service._probe_service", return_value=(self.report, self.info)):
            _, providers, snapshot = prepare_provider(self.config, model, self.root / "runs.sqlite", "a" * 32)
        self.assertNotEqual(model["nodes"][0]["provider"], model["nodes"][1]["provider"])
        checkpoints = [
            value.config["checkpoints"]["image"]["name"] for key, value in providers.items() if key.startswith("comfy")
        ]
        self.assertEqual(set(checkpoints), {"image-a", "image-b"})
        self.assertEqual(snapshot["providers"]["comfy"]["checkpoints"]["image"]["name"], "image-a")
        _, restored = restore_provider(snapshot)
        self.assertEqual(
            {
                key: value.config["checkpoints"]["image"]["name"]
                for key, value in restored.items()
                if key.startswith("comfy")
            },
            {"comfy": "image-a", "comfy_2": "image-b"},
        )
        model["nodes"][0]["model"] = "image-b"
        self.assertEqual(snapshot["providers"]["comfy"]["checkpoints"]["image"]["name"], "image-a")

    def test_legacy_defaults_and_explicit_missing_model(self):
        legacy = dict(nodes=[dict(id="a", type="text_to_image", parameters={"prompt": "a"})], edges=[])
        with patch("generation_service._probe_service", return_value=(self.report, self.info)):
            prepare_provider(self.config, legacy, self.root / "runs.sqlite", "b" * 32)
        self.assertEqual(legacy["nodes"][0]["model"], "image-a")
        missing = dict(nodes=[dict(id="a", type="text_to_image", model="", parameters={"prompt": "a"})], edges=[])
        with patch("generation_service._probe_service", return_value=(self.report, self.info)):
            with self.assertRaises(ServiceError) as context:
                prepare_provider(self.config, missing, self.root / "runs.sqlite", "c" * 32)
        self.assertEqual(context.exception.code, "image_model_missing")

    def test_old_single_provider_snapshot_still_restores(self):
        config = dict(
            endpoint="http://127.0.0.1:8188",
            storage=str(self.root / "legacy-state"),
            checkpoints={"image": {"name": "image-a", "sha256": None}, "mesh": {"name": "mesh-a", "sha256": None}},
            backend_revision="fixture|unverified-weights;run=" + "d" * 32,
        )
        _, providers = restore_provider({"mode": "comfy", "provider": config})
        self.assertEqual(providers["comfy"].config["checkpoints"]["image"]["name"], "image-a")

    def test_kimi_nodes_keep_independent_model_ids(self):
        from kimi_provider import DEFAULT_ENDPOINT, KimiNativeDirectProvider

        config = dict(
            schema_version=1,
            mode="kimi_native",
            endpoint=DEFAULT_ENDPOINT,
            image_model="",
            mesh_model="",
            model3d_tool_path=str(self.root / "model3d_generation_tool.py"),
            model3d_pythonw_path="fixture-python",
            model3d_model="v3.1",
            texture_model="v3.5",
        )
        report = dict(
            capabilities={"text_to_mesh": {"ready": True}},
            models={"mesh": ["v3.1", "v3.0"]},
        )
        model = dict(
            nodes=[
                dict(id="a", type="text_to_mesh", model="v3.1", parameters={"prompt": "a"}),
                dict(id="b", type="text_to_mesh", model="v3.0", parameters={"prompt": "b"}),
            ],
            edges=[],
        )
        with patch("generation_service._probe_kimi", return_value=report):
            _, providers, snapshot = prepare_provider(config, model, self.root / "runs.sqlite", "e" * 32)
        self.assertEqual(
            {value.config["model"] for key, value in providers.items() if key.startswith("kimi_native")},
            {"v3.1", "v3.0"},
        )
        self.assertTrue(
            all(
                isinstance(value, KimiNativeDirectProvider)
                for key, value in providers.items()
                if key.startswith("kimi_native")
            )
        )
        self.assertEqual(len(snapshot["providers"]), 2)
        _, restored = restore_provider(snapshot)
        self.assertEqual(
            {value.config["model"] for key, value in restored.items() if key.startswith("kimi_native")},
            {"v3.1", "v3.0"},
        )

    def test_codex_nodes_freeze_independent_image_and_mesh_models(self):
        config = dict(
            mode="codex",
            cli_path="fixture-cli",
            endpoint="http://127.0.0.1:8188",
            image_model="builtin",
            mesh_model="mesh-a",
        )
        report = dict(connected=True, models={"mesh": ["mesh-a", "mesh-b"]}, backend_revision="fixture")
        model = dict(
            nodes=[
                dict(id="a", type="text_to_image", model="image-cli-a", parameters={"prompt": "a"}),
                dict(id="b", type="text_to_image", model="image-cli-b", parameters={"prompt": "b"}),
                dict(
                    id="c", type="text_to_mesh", model="mesh-a", image_model="image-cli-a", parameters={"prompt": "c"}
                ),
                dict(id="d", type="text_to_mesh", model="mesh-b", image_model="builtin", parameters={"prompt": "d"}),
            ],
            edges=[],
        )
        with patch("generation_service._probe_codex", return_value=(report, {})):
            _, _, snapshot = prepare_provider(config, model, self.root / "runs.sqlite", "f" * 32)
        self.assertEqual(
            {value["model"] for value in snapshot["providers"].values()},
            {"image-cli-a", "image-cli-b", ""},
        )
        mesh_providers = [value for value in snapshot["providers"].values() if value["mesh_config"]]
        self.assertEqual(
            {value["mesh_config"]["checkpoints"]["mesh"]["name"] for value in mesh_providers},
            {"mesh-a", "mesh-b"},
        )
        self.assertEqual(model["nodes"][3]["provider"], "codex_4")

    def test_modeling_and_sculpt_nodes_keep_distinct_cli_models(self):
        for mode, probe, prefix in (
            ("codex_modeling", "_probe_modeling", "codex-modeling"),
            ("codex_sculpt", "_probe_sculpt", "codex-sculpt"),
        ):
            with self.subTest(mode=mode):
                config = dict(mode=mode, cli_path="fixture-cli", image_model="builtin", mesh_model="")
                if mode == "codex_modeling":
                    config.update(godot_path="fixture-godot", builder_path="fixture-builder")
                else:
                    config.update(
                        blender_path="fixture-blender", builder_path=str(Path(__file__).with_name("sculpt_builder.py"))
                    )
                report = dict(
                    capabilities={"text_to_mesh": {"ready": True}},
                    runtime={"executable": "fixture-blender"},
                )
                model = dict(
                    nodes=[
                        dict(id="a", type="text_to_mesh", model=mode + "-a", parameters={"prompt": "a"}),
                        dict(id="b", type="text_to_mesh", model=mode + "-b", parameters={"prompt": "b"}),
                    ],
                    edges=[],
                )
                with patch("generation_service." + probe, return_value=report):
                    _, providers, snapshot = prepare_provider(config, model, self.root / (mode + ".sqlite"), "1" * 32)
                selected = {value.config["model"] for key, value in providers.items() if key.startswith(prefix)}
                self.assertEqual(selected, {mode + "-a", mode + "-b"})
                self.assertEqual(set(snapshot["provider_types"].values()), {prefix})
                model["nodes"][0]["model"] = "changed-after-freeze"
                self.assertEqual(snapshot["providers"][prefix]["model"], mode + "-a")

    def test_model_adjust_migrates_as_mesh_not_as_cli_image(self):
        from generation_service import _migrate_node_models

        for mode, expected in (
            ("codex", "mesh-a"),
            ("codex_modeling", ""),
            ("codex_sculpt", ""),
            ("comfy", "mesh-a"),
            ("kimi_native", "v3.1"),
        ):
            with self.subTest(mode=mode):
                config = dict(self.config, mode=mode, model3d_model="v3.1")
                node = dict(id="adjust", type="model_adjust", parameters={})
                _migrate_node_models(node, config)
                self.assertEqual(node["model"], expected)


if __name__ == "__main__":
    unittest.main()
