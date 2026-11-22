import argparse
import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from editor_host import compile_graph, dispatch
from executor import Executor
from garment_split import GarmentSource
from generation_service import check_inputs, prepare_provider, restore_provider, settings
from test_garment_split import item, make_glb


class GarmentSplitProviderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source.glb"
        self.raw = make_glb(self.source, embedded_image=True)
        self.geometry = GarmentSource(self.source)
        self.components = self.geometry.inspection()["components"]

    def tearDown(self):
        self.temporary.cleanup()

    def model(self, items):
        return {
            "nodes": [
                {
                    "id": "split",
                    "type": "garment_split",
                    "version": "1",
                    "provider": "garment-split",
                    "source": str(self.source),
                    "image_context": "",
                    "text": "",
                    "parameters": {"items": items},
                    "x": 0,
                    "y": 0,
                }
            ],
            "edges": [],
        }

    def execute(self, model):
        config = settings({"mode": "comfy", "endpoint": "http://127.0.0.1:8188"})
        database = self.root / "executor.sqlite"
        with patch("generation_service.read_endpoint", side_effect=AssertionError("remote service must not be probed")):
            registry, providers, snapshot = prepare_provider(config, model, database, "a" * 32)
        check_inputs(model)
        graph, manifest = compile_graph(model)
        host = Executor(str(database), registry, providers)
        try:
            run = host.create(graph, manifest)
            state = host.step(run)
            return host, run, state, providers, snapshot
        except Exception:
            host.close()
            raise

    def test_local_node_publishes_collection_and_each_garment(self):
        items = [
            item("cape", [self.components[0]["component_id"]]),
            item("armor", [self.components[2]["component_id"]], behavior="rigid", category="armor"),
        ]
        host, run, state, providers, snapshot = self.execute(self.model(items))
        try:
            self.assertEqual(state["state"], "succeeded", state)
            node = state["nodes"]["split"]
            self.assertIsNone(node["error"])
            exported = host.export(run)
            reference = exported["outputs"]["split"]["result"]
            artifacts = exported["manifest"]["artifacts"]
            primary = next(asset for asset in artifacts if asset["id"] == reference["id"])
            garments = [
                asset
                for asset in artifacts
                if asset["payload"].get("provenance", {}).get("artifact_role") == "garment"
            ]
            self.assertEqual(len(garments), 2)
            self.assertEqual(primary["payload"]["provenance"]["artifact_role"], "garment_collection")
            self.assertEqual(primary["payload"]["provenance"]["garment_count"], 2)
            self.assertEqual(
                [asset["payload"]["provenance"]["garment_id"] for asset in garments], ["cape", "armor"]
            )
            self.assertTrue(all(asset["payload"]["provenance"]["iteration_of"] == reference["id"] for asset in garments))
            data = base64.b64decode(primary["payload"]["content_base64"], validate=True)
            collection = self.root / "collection.glb"
            collection.write_bytes(data)
            geometry = GarmentSource(collection)
            self.assertEqual(sum(len(entry["faces"]) for entry in geometry.primitives.values()), 2)
            self.assertEqual(self.source.read_bytes(), self.raw)
            job_id = node["job"]["job_id"]
            provider = providers["garment-split"]
            self.assertEqual(provider.lookup(job_id)["state"], "succeeded")
            self.assertEqual(provider.result_manifest(job_id)["artifacts"], garments + [primary])
            restored_registry, restored = restore_provider(snapshot)
            self.assertIsNotNone(restored_registry.get("garment_split", "1"))
            self.assertEqual(restored["garment-split"].result_manifest(job_id), provider.result_manifest(job_id))
        finally:
            host.close()

    def test_invalid_items_fail_without_remote_or_partial_result(self):
        host, _run, state, _providers, _snapshot = self.execute(self.model([]))
        try:
            self.assertEqual(state["state"], "failed")
            node = state["nodes"]["split"]
            self.assertEqual(node["job"]["state"], "failed")
            self.assertEqual(node["result"], None)
            self.assertIn("衣服清单", node["public_error"])
            self.assertEqual(self.source.read_bytes(), self.raw)
        finally:
            host.close()

    def test_rigged_input_preserves_original_skin_and_weights(self):
        rigged = self.root / "rigged.glb"
        make_glb(rigged, skin=True)
        source = GarmentSource(rigged)
        component = source.inspection()["components"][0]["component_id"]
        model = self.model([item("cape", [component])])
        model["nodes"][0]["source"] = str(rigged)
        host, _run, state, _providers, _snapshot = self.execute(model)
        try:
            self.assertEqual(state["state"], "succeeded", state)
            primary = state["nodes"]["split"]["result"]
            provenance = primary["artifacts"][-1]["payload"]["provenance"]
            self.assertTrue(provenance["rigged"])
            self.assertTrue(provenance["skeleton_preserved"])
            self.assertTrue(provenance["skin_weights_preserved"])
            self.assertTrue(provenance["inverse_bind_matrices_preserved"])
        finally:
            host.close()

    def test_godot_integral_doubles_are_normalized_for_reviewed_triangles(self):
        reviewed = item("cape", [], review_state="confirmed")
        reviewed["selection"] = dict(
            mode="reviewed_triangles",
            primitives=[dict(node=0.0, primitive=0.0, triangles=[0.0])],
        )
        host, _run, state, _providers, _snapshot = self.execute(self.model([reviewed]))
        try:
            self.assertEqual(state["state"], "succeeded", state)
            self.assertEqual(
                state["nodes"]["split"]["resolved"]["parameters"]["items"][0]["selection"]["primitives"][0],
                {"node": 0, "primitive": 0, "triangles": [0]},
            )
        finally:
            host.close()

    def test_fresh_project_dispatch_uses_local_provider_without_service_file(self):
        model = self.model([item("cape", [self.components[0]["component_id"]])])
        args = argparse.Namespace(
            db=str(self.root / "fresh.sqlite"),
            factory="editor_demo:factory",
            service_config=None,
            command="create",
        )
        created = dispatch(args, {"model": model})
        args.command = "step"
        state = dispatch(args, {"run": created["run_id"]})
        self.assertEqual(state["state"], "succeeded", state)
        args.command = "preview"
        preview = dispatch(args, {"run": created["run_id"], "node": "split"})
        self.assertTrue(Path(preview["path"]).is_file())
        self.assertEqual(Path(preview["path"]).suffix, ".glb")
        self.assertGreater(Path(preview["path"]).stat().st_size, 28)
        self.assertEqual(self.source.read_bytes(), self.raw)


if __name__ == "__main__":
    unittest.main()
