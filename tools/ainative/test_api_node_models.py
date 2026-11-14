"""API node choices, legacy migration and frozen providers; no remote inference."""

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from generation_service import (
    ServiceError,
    check_service,
    prepare_provider,
    restore_provider,
    run_service,
    save_run_service,
    settings,
)

ROOT = Path(__file__).resolve().parents[2]


class ApiNodeModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.database = self.folder / "runs.sqlite"

    def config(self, mode, **extra):
        runtime = "godot_path" if mode == "api_modeling" else "blender_path"
        return settings(
            dict(
                mode=mode,
                endpoint="https://example.test/v1",
                api_key_env="AINATIVE_NODE_FIXTURE_KEY",
                builder_path=str(ROOT / "tools/ainative/sculpt_builder.py"),
                **{runtime: sys.executable},
                **extra,
            )
        )

    def prepare(self, config, nodes):
        with patch("generation_service._probe_api", return_value={"connected": True}):
            return prepare_provider(config, {"nodes": nodes, "edges": []}, self.database, "a" * 32)

    def test_two_models_deduplicate_and_freeze_across_settings_and_node_edits(self):
        for mode in ("api_modeling", "api_sculpt"):
            with self.subTest(mode=mode):
                config = self.config(mode, api_model="unused-global")
                nodes = [
                    dict(id=str(i), type=kind, model=model)
                    for i, (kind, model) in enumerate([
                        ("text_to_mesh", "model-a"),
                        ("image_to_mesh", "model-b"),
                        ("text_to_mesh", "model-a"),
                    ])
                ]
                _, providers, snapshot = self.prepare(config, nodes)
                self.assertEqual(len(snapshot["providers"]), 2)
                self.assertEqual(nodes[0]["provider"], nodes[2]["provider"])
                self.assertNotEqual(nodes[0]["provider"], nodes[1]["provider"])
                expected = {n["provider"]: n["model"] for n in nodes}
                for key, model in expected.items():
                    self.assertEqual(providers[key].describe()["model"], model)
                frozen_nodes = copy.deepcopy(nodes)
                save_run_service(self.database, mode, snapshot)
                config.update(endpoint="https://changed.test/v1", api_key_env="CHANGED", api_model="changed")
                nodes[0]["model"] = "changed"
                _, restored = restore_provider(run_service(self.database, mode))
                for node in frozen_nodes:
                    provider = restored[node["provider"]]
                    self.assertEqual(provider.config["planner"]["model"], node["model"])
                    self.assertEqual(provider.config["planner"]["endpoint"], "https://example.test/v1")
                    self.assertEqual(provider.config["planner"]["key_env"], "AINATIVE_NODE_FIXTURE_KEY")
                    self.assertEqual(provider.fingerprint, providers[node["provider"]].fingerprint)

    def test_editor_create_persists_distinct_manifests_and_frozen_connection(self):
        from editor_host import dispatch

        for mode in ("api_modeling", "api_sculpt"):
            with self.subTest(mode=mode):
                config = self.config(mode)
                service_file = self.folder / "service.json"
                service_file.write_text(json.dumps(config))
                args = argparse.Namespace(
                    db=str(self.database),
                    factory="editor_demo:factory",
                    command="create",
                    service_config=str(service_file),
                )
                graph = dict(
                    nodes=[
                        dict(id=name, type="text_to_mesh", model=name, parameters={"prompt": "a stone owl"})
                        for name in ("model_a", "model_b")
                    ],
                    edges=[],
                )
                with patch("generation_service._probe_api", return_value={"connected": True}):
                    run = dispatch(args, {"model": graph})["run_id"]
                service_file.write_text(json.dumps({"mode": "offline"}))
                graph["nodes"][0]["model"] = "edited"
                args.command = "status"
                state = dispatch(args, {"run": run})
                _, providers = restore_provider(run_service(self.database, run))
                for name, node in state["nodes"].items():
                    self.assertEqual(node["provider_manifest"]["model"], name)
                    self.assertEqual(providers[node["provider"]].describe()["model"], name)
                    self.assertEqual(providers[node["provider"]].config["planner"]["endpoint"], config["endpoint"])

    def test_missing_field_migrates_once_and_old_single_snapshot_restores(self):
        for mode in ("api_modeling", "api_sculpt"):
            with self.subTest(mode=mode):
                config = self.config(mode, api_model="legacy-a")
                nodes = [dict(id="legacy", type="text_to_mesh")]
                _, _, snapshot = self.prepare(config, nodes)
                self.assertEqual(nodes[0]["model"], "legacy-a")
                config["api_model"] = "legacy-b"
                _, _, second = self.prepare(config, nodes)
                self.assertEqual(nodes[0]["model"], "legacy-a")
                self.assertEqual(second["provider"]["planner"]["model"], "legacy-a")
                _, restored = restore_provider(dict(mode=mode, provider=snapshot["provider"]))
                self.assertEqual(restored[nodes[0]["provider"]].config["planner"]["model"], "legacy-a")

    def test_explicit_invalid_never_falls_back_or_probes(self):
        for mode in ("api_modeling", "api_sculpt"):
            for model in ("", " ", None, 3, "a\nb", "a\x7fb", "x" * 257, " padded ", "gpt-4o", "openai/other"):
                with self.subTest(mode=mode, model=model), patch("generation_service._probe_api") as probe:
                    with self.assertRaises(ServiceError) as error:
                        prepare_provider(
                            self.config(mode, api_model="legacy-a"),
                            {"nodes": [dict(id="bad", type="text_to_mesh", model=model)]},
                            self.database,
                            "b" * 32,
                        )
                    self.assertEqual(error.exception.code, "node_api_model_invalid")
                    self.assertIn("节点检查器", str(error.exception))
                    probe.assert_not_called()

    def test_no_legacy_default_materializes_empty_and_requires_node_choice(self):
        for mode in ("api_modeling", "api_sculpt"):
            nodes = [dict(id="old", type="text_to_mesh")]
            with self.assertRaises(ServiceError):
                self.prepare(self.config(mode), nodes)
            self.assertEqual(nodes[0]["model"], "")
            with self.assertRaises(ServiceError):
                self.prepare(self.config(mode, api_model="later-default"), nodes)

    def test_connection_probe_without_model_and_ignores_stale_default(self):
        for mode in ("api_modeling", "api_sculpt"):
            for legacy in ({}, {"api_model": ""}, {"api_model": "gpt-4o"}):
                with (
                    self.subTest(mode=mode, legacy=legacy),
                    patch.dict(os.environ, {"AINATIVE_NODE_FIXTURE_KEY": "local-fixture"}, clear=True),
                ):
                    config = self.config(mode, **legacy)
                    report = check_service(config)
                    self.assertTrue(report["connected"], report)
                    self.assertTrue(report["capabilities"]["text_to_mesh"]["ready"])
                    self.assertFalse(report["capabilities"]["model_adjust"]["ready"])
                    nodes = [dict(id="explicit", type="text_to_mesh", model="model-a")]
                    _, _, snapshot = prepare_provider(config, {"nodes": nodes}, self.database, "d" * 32)
                    self.assertEqual(snapshot["provider"]["planner"]["model"], "model-a")

    def test_connection_safety_is_preserved(self):
        for mode in ("api_modeling", "api_sculpt"):
            for endpoint in (
                "https://api.openai.com/v1",
                "https://x.openai.azure.com/v1",
                "http://remote.test/v1",
                "https://u:p@example.test/v1",
            ):
                config = self.config(mode)
                config["endpoint"] = endpoint
                with self.assertRaises(ServiceError):
                    settings(config)

    @unittest.skipUnless(os.environ.get("AINATIVE_GUI_TEST_GODOT"), "explicit isolated Godot binary required")
    def test_native_node_controls_and_roundtrip(self):
        project = self.folder / "project"
        shutil.copytree(ROOT / "samples/ainative-workbench/addons", project / "addons")
        (project / "project.godot").write_text(
            '[application]\nconfig/name="API node isolated acceptance"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
        )
        shutil.copyfile(ROOT / "samples/ainative-workbench/api_node_models_acceptance.gd", project / "acceptance.gd")
        env = dict(
            os.environ,
            AINATIVE_PYTHON=sys.executable,
            AINATIVE_UI_TOOLS=str(ROOT / "tools/ainative"),
            AINATIVE_NODE_FIXTURE_KEY="local-configuration-only",
            AINATIVE_UI_STATE=str(self.folder / "state"),
            AINATIVE_API_NODE_REPORT=str(self.folder / "report.json"),
        )
        for key in ("AINATIVE_COMFY_CONFIG", "AINATIVE_PROVIDER_FACTORY"):
            env.pop(key, None)
        result = subprocess.run(
            [env["AINATIVE_GUI_TEST_GODOT"], "--headless", "--path", str(project), "--script", "acceptance.gd"],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        log = result.stdout + result.stderr
        if os.environ.get("AINATIVE_API_NODE_EVIDENCE"):
            evidence = Path(os.environ["AINATIVE_API_NODE_EVIDENCE"])
            (evidence / "native.log").write_text(log)
            if (self.folder / "report.json").is_file():
                shutil.copyfile(self.folder / "report.json", evidence / "native.json")
        self.assertEqual(result.returncode, 0, log)
        self.assertNotIn("SCRIPT ERROR", log)
        report = json.loads((self.folder / "report.json").read_text())
        self.assertTrue(report["ok"], report)


if __name__ == "__main__":
    unittest.main()
