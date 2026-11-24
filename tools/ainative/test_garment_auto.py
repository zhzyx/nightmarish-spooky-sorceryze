import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from garment_auto import COMPONENT_VIEWS, RENDER_VIEWS, recognize
from garment_split import GarmentSource
from test_garment_split import inventory, make_glb, png


class GarmentAutoRecognitionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source.glb"
        self.raw = make_glb(self.source, embedded_image=True)
        self.geometry = GarmentSource(self.source)
        self.components = self.geometry.inspection()["components"]
        self.image = self.root / "preview.png"
        self.image.write_bytes(png())
        self.planner = dict(endpoint="https://planner.example.com", model="vision-test", key_env="TEST_KEY")

    def tearDown(self):
        self.temporary.cleanup()

    def fake_render(self, source, candidates, directory, godot_path, render_script):
        self.assertEqual(Path(source).read_bytes(), self.raw)
        self.assertEqual(godot_path, "godot")
        self.assertEqual(render_script, "mesh_review.gd")
        images = [dict(path=self.image, label=view, component_id=None) for view in RENDER_VIEWS]
        for candidate in candidates:
            data = Path(candidate["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), candidate["sha256"])
            self.assertGreater(len(GarmentSource(candidate["path"]).primitives), 0)
            for view in COMPONENT_VIEWS:
                images.append(dict(path=self.image, label=view, component_id=candidate["component_id"]))
        return images

    def test_ai_selection_is_bound_to_rendered_components(self):
        selected = self.components[0]["component_id"]

        def fake_inventory(_config, inspection, images, directory):
            self.assertEqual(inspection["source_sha256"], self.geometry.sha256)
            attached = {entry["component_id"] for entry in images if entry["component_id"] is not None}
            self.assertIn(selected, attached)
            self.assertLessEqual(len(attached), 2)
            Path(directory).mkdir()
            return dict(
                schema_version=1,
                items=[inventory("cape", [selected])],
                non_garments=[],
                notes="",
            )

        with (
            patch("garment_auto._render", side_effect=self.fake_render),
            patch("garment_auto.request_inventory", side_effect=fake_inventory),
        ):
            result = recognize(
                self.source,
                self.root / "automatic",
                "godot",
                "mesh_review.gd",
                planner=self.planner,
                candidate_limit=2,
            )
        self.assertEqual(result["items"][0]["selection"]["component_ids"], [selected])
        self.assertEqual(result["items"][0]["review_state"], "automatic")
        self.assertEqual(result["receipt"]["candidate_count"], 2)
        self.assertFalse(result["receipt"]["visual_review_passed"])
        self.assertFalse(result["receipt"]["human_confirmed"])
        self.assertTrue((self.root / "automatic" / "auto-receipt.json").is_file())
        self.assertTrue((self.root / "automatic" / "selection.json").is_file())
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_semantic_item_without_component_evidence_does_not_split(self):
        document = dict(
            schema_version=1,
            items=[inventory("cape", [], needs_review=True)],
            non_garments=[],
            notes="",
        )
        with (
            patch("garment_auto._render", side_effect=self.fake_render),
            patch("garment_auto.request_inventory", return_value=document),
        ):
            with self.assertRaisesRegex(ValueError, "no_geometry"):
                recognize(
                    self.source,
                    self.root / "automatic",
                    "godot",
                    "mesh_review.gd",
                    planner=self.planner,
                    candidate_limit=1,
                )
        self.assertEqual(self.source.read_bytes(), self.raw)
        selection = json.loads((self.root / "automatic" / "selection.json").read_text())
        self.assertEqual(selection["items"], [])
        self.assertEqual(selection["unresolved_items"], ["cape"])


if __name__ == "__main__":
    unittest.main()
