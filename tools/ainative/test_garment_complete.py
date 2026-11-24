import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from extensions import canonical
from garment_auto import RENDER_VIEWS
from garment_complete import (
    _assign_triangles,
    _excluded_pixels,
    _fill_topology_pinholes,
    _GlbWriter,
    _validate_simple_polygon,
    _request_quality_review,
    _request_view_masks,
    _repair_quality_inventory,
    _position_weld,
    _solidify_primitive,
    _triangle_id_model,
    complete,
    validate_segmentation,
)
from garment_split import GarmentSource
from geometry_repair import load_glb
from test_garment_split import accessor_bytes, inventory, make_glb, png


def segmentation(coverage="complete_visible"):
    masks = [
        dict(
            view=view,
            polygons=[[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]],
        )
        for view in RENDER_VIEWS
    ]
    return dict(
        schema_version=2,
        items=[
            dict(
                id="cape",
                label="Complete cape",
                category="garment",
                slot="back",
                behavior="cloth",
                confidence=0.9,
                evidence="Full visible cape masks",
                needs_review=False,
                coverage=coverage,
                missing_regions=[] if coverage == "complete_visible" else ["back"],
                masks=masks,
            )
        ],
        non_garments=[],
        notes="",
    )


class GarmentCompleteTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source.glb"
        self.raw = make_glb(self.source, embedded_image=True)
        self.geometry = GarmentSource(self.source)

    def tearDown(self):
        self.temporary.cleanup()

    def test_single_triangle_becomes_closed_independent_shell(self):
        part = _solidify_primitive(
            self.geometry,
            (0, 0),
            np.asarray([0], dtype=np.int64),
            0.01,
            _position_weld(self.geometry.primitives[(0, 0)]["points"]),
        )[0]
        self.assertTrue(part["closed_position_welded"])
        self.assertEqual(part["source_triangles"], 1)
        self.assertEqual(part["boundary_edges_before"], 3)
        self.assertEqual(len(part["faces"]), 8)
        self.assertEqual(len(part["attributes"]["POSITION"]), 18)
        np.testing.assert_allclose(
            part["attributes"]["POSITION"][:3] - part["attributes"]["POSITION"][3:6],
            np.tile([0.0, 0.0, 0.01], (3, 1)),
        )

    def test_normal_seam_offsets_share_inner_positions(self):
        writer = _GlbWriter(self.geometry, "normal seam fixture")
        points = np.asarray(
            [[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
            dtype="<f4",
        )
        normals = np.asarray(
            [[0, 0, 1], [0, 0, 1], [0, 0, 1], [0.2, 0, 1], [0.2, 0, 1], [0.2, 0, 1]],
            dtype="<f4",
        )
        uv = np.zeros((6, 2), dtype="<f4")
        writer.add_part(
            "seamed-quad",
            dict(POSITION=points, NORMAL=normals, TEXCOORD_0=uv),
            np.asarray([[0, 1, 2], [3, 4, 5]], dtype="<u4"),
        )
        path = self.root / "seam.glb"
        path.write_bytes(writer.finish({}))
        source = GarmentSource(path)
        parts = _solidify_primitive(
            source,
            (0, 0),
            np.asarray([0, 1], dtype=np.int64),
            0.01,
            _position_weld(source.primitives[(0, 0)]["points"]),
        )
        self.assertEqual(len(parts), 2)
        self.assertTrue(all(part["closed_position_welded"] for part in parts))
        self.assertEqual([part["boundary_edges_before"] for part in parts], [3, 3])

    def test_triangle_id_model_and_masks_select_source_faces(self):
        primitive_map, id_sha = _triangle_id_model(self.geometry, self.root / "ids.glb")
        report = dict(model_sha256=self.geometry.sha256, triangle_id_model_sha256=id_sha, triangle_id_maps=[])
        renders = self.root / "renders"
        renders.mkdir()
        for index, view in enumerate(RENDER_VIEWS):
            path = renders / (view + ".png")
            high_path = renders / (view + ".high.png")
            Image.new("RGB", (2, 2), (65, 51, 51)).save(path)
            Image.new("RGB", (2, 2), (51, 51, 51)).save(high_path)
            report["triangle_id_maps"].append(
                dict(
                    view=view,
                    path=str(path),
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    high_path=str(high_path),
                    high_sha256=hashlib.sha256(high_path.read_bytes()).hexdigest(),
                )
            )
        assignments = _assign_triangles(self.geometry, segmentation(), primitive_map, report, renders)
        # The full mask and visible plane also support the other coplanar
        # triangles, even though the synthetic ID image sampled only triangle 1.
        self.assertEqual(assignments[0]["selected"][(0, 0)].tolist(), [0, 1])
        self.assertEqual(assignments[0]["evidence"]["selected_triangles"], 3)
        self.assertEqual(assignments[0]["evidence"]["subpixel_triangles"], 2)
        self.assertEqual(assignments[0]["evidence"]["conflicted_triangles"], 0)
        self.assertTrue((self.root / "ids.glb").is_file())

    def test_subpixel_triangle_on_same_visible_plane_is_recovered(self):
        writer = _GlbWriter(self.geometry, "dense surface fixture")
        points = np.asarray([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0.2, 0.2, 0], [0.3, 0.2, 0], [0.2, 0.3, 0]], dtype="<f4")
        normals = np.tile(np.asarray([[0, 0, 1]], dtype="<f4"), (6, 1))
        uv = np.zeros((6, 2), dtype="<f4")
        writer.add_part(
            "subpixel-surface",
            dict(POSITION=points, NORMAL=normals, TEXCOORD_0=uv),
            np.asarray([[0, 1, 2], [3, 4, 5]], dtype="<u4"),
        )
        path = self.root / "quad.glb"
        path.write_bytes(writer.finish({}))
        source = GarmentSource(path)
        primitive_map, _id_sha = _triangle_id_model(source, self.root / "quad-ids.glb")
        renders = self.root / "quad-renders"
        renders.mkdir()
        maps = []
        for view in RENDER_VIEWS:
            low_path = renders / (view + ".low.png")
            high_path = renders / (view + ".high.png")
            Image.new("RGB", (2, 2), (65, 51, 51)).save(low_path)
            Image.new("RGB", (2, 2), (51, 51, 51)).save(high_path)
            maps.append(
                dict(
                    view=view,
                    path=str(low_path),
                    sha256=hashlib.sha256(low_path.read_bytes()).hexdigest(),
                    high_path=str(high_path),
                    high_sha256=hashlib.sha256(high_path.read_bytes()).hexdigest(),
                )
            )
        report = dict(triangle_id_maps=maps)
        assignments = _assign_triangles(source, segmentation(), primitive_map, report, renders)
        self.assertEqual(assignments[0]["selected"][(0, 0)].tolist(), [0, 1])
        self.assertEqual(assignments[0]["evidence"]["subpixel_triangles"], 1)

    def test_subpixel_completion_rejects_occluded_body_behind_surface(self):
        writer = _GlbWriter(self.geometry, "occluded surface fixture")
        points = np.asarray([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0.2, 0.2, -1], [0.3, 0.2, -1], [0.2, 0.3, -1]], dtype="<f4")
        normals = np.tile(np.asarray([[0, 0, 1]], dtype="<f4"), (6, 1))
        uv = np.zeros((6, 2), dtype="<f4")
        writer.add_part(
            "surface-and-body",
            dict(POSITION=points, NORMAL=normals, TEXCOORD_0=uv),
            np.asarray([[0, 1, 2], [3, 4, 5]], dtype="<u4"),
        )
        path = self.root / "occluded.glb"
        path.write_bytes(writer.finish({}))
        source = GarmentSource(path)
        primitive_map, _id_sha = _triangle_id_model(source, self.root / "occluded-ids.glb")
        renders = self.root / "occluded-renders"
        renders.mkdir()
        maps = []
        for view in RENDER_VIEWS:
            low_path = renders / (view + ".low.png")
            high_path = renders / (view + ".high.png")
            Image.new("RGB", (2, 2), (65, 51, 51)).save(low_path)
            Image.new("RGB", (2, 2), (51, 51, 51)).save(high_path)
            maps.append(
                dict(
                    view=view,
                    path=str(low_path),
                    sha256=hashlib.sha256(low_path.read_bytes()).hexdigest(),
                    high_path=str(high_path),
                    high_sha256=hashlib.sha256(high_path.read_bytes()).hexdigest(),
                )
            )
        assignments = _assign_triangles(source, segmentation(), primitive_map, dict(triangle_id_maps=maps), renders)
        self.assertEqual(assignments[0]["selected"][(0, 0)].tolist(), [0])
        self.assertEqual(assignments[0]["evidence"]["subpixel_triangles"], 0)

    def test_complete_publishes_only_closed_wearable_shell(self):
        def fake_render(source, candidates, directory, godot_path, render_script, triangle_id_model=None, triangle_id_model_high=None):
            renders = directory / "renders"
            renders.mkdir(parents=True)
            maps = []
            for view in RENDER_VIEWS:
                path = renders / (view + ".triangles.png")
                high_path = renders / (view + ".triangles.high.png")
                Image.new("RGB", (2, 2), (65, 51, 51)).save(path)
                Image.new("RGB", (2, 2), (51, 51, 51)).save(high_path)
                maps.append(
                    dict(
                        view=view,
                        path=str(path),
                        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                        high_path=str(high_path),
                        high_sha256=hashlib.sha256(high_path.read_bytes()).hexdigest(),
                    )
                )
            report = dict(
                model_sha256=self.geometry.sha256,
                triangle_id_model_sha256=hashlib.sha256(Path(triangle_id_model).read_bytes()).hexdigest(),
                triangle_id_model_high_sha256=hashlib.sha256(Path(triangle_id_model_high).read_bytes()).hexdigest(),
                triangle_id_maps=maps,
            )
            (renders / "views.json").write_text(json.dumps(report), encoding="utf-8")
            return []

        with (
            patch("garment_complete._render", side_effect=fake_render),
            patch("garment_complete.request_segmentation", return_value=segmentation()),
        ):
            result = complete(
                self.source,
                self.root / "output",
                self.root / "evidence",
                "godot",
                "mesh_review.gd",
                planner=dict(endpoint="https://planner.example.com", model="vision", key_env="TEST"),
                quality_review=False,
            )
        self.assertEqual(result["status"], "wearable_shell")
        self.assertEqual(result["items"][0]["state"], "wearable_shell")
        self.assertTrue(result["items"][0]["closed_position_welded"])
        self.assertFalse(result["visual_review_passed"])
        self.assertFalse(result["fit_validated"])
        self.assertTrue((self.root / "output" / "cape.glb").is_file())
        self.assertTrue((self.root / "output" / "_garments.glb").is_file())
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_quality_gate_runs_one_generic_repair_and_records_history(self):
        def fake_render(source, candidates, directory, godot_path, render_script, triangle_id_model=None, triangle_id_model_high=None, camera_bounds=None):
            renders = directory / "renders"
            renders.mkdir(parents=True)
            maps = []
            for view in RENDER_VIEWS:
                path = renders / (view + ".triangles.png")
                high_path = renders / (view + ".triangles.high.png")
                Image.new("RGB", (2, 2), (65, 51, 51)).save(path)
                Image.new("RGB", (2, 2), (51, 51, 51)).save(high_path)
                maps.append(
                    dict(
                        view=view,
                        path=str(path),
                        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                        high_path=str(high_path),
                        high_sha256=hashlib.sha256(high_path.read_bytes()).hexdigest(),
                    )
                )
            report = dict(
                model_sha256=self.geometry.sha256,
                triangle_id_model_sha256=hashlib.sha256(Path(triangle_id_model).read_bytes()).hexdigest(),
                triangle_id_model_high_sha256=hashlib.sha256(Path(triangle_id_model_high).read_bytes()).hexdigest(),
                triangle_id_maps=maps,
                views=[dict(view=entry["view"], path=entry["path"], sha256=entry["sha256"]) for entry in maps],
            )
            (renders / "views.json").write_text(json.dumps(report), encoding="utf-8")
            return []

        repaired = segmentation()
        repaired["items"][0]["label"] = "Repaired cape"
        repair_record = dict(changed=True, items=[dict(id="cape", views=["back"])])

        with (
            patch("garment_complete._render", side_effect=fake_render),
            patch("garment_complete.request_segmentation", return_value=segmentation()),
            patch("garment_complete._request_exclusions", return_value=dict(views=[])),
            patch("garment_complete._repair_quality_inventory", return_value=(repaired, repair_record)) as repair,
            patch(
                "garment_complete._quality_gate",
                side_effect=[
                    dict(visual_review_passed=False, review=dict(items=[])),
                    dict(visual_review_passed=True, review=dict(items=[])),
                ],
            ) as gate,
        ):
            result = complete(
                self.source,
                self.root / "output",
                self.root / "evidence",
                "godot",
                "review",
                planner=dict(endpoint="https://planner.example.com", model="vision", key_env="TEST"),
            )
        self.assertEqual(gate.call_count, 2)
        self.assertEqual(repair.call_count, 1)
        self.assertEqual(result["quality_repair_attempt"], 1)
        self.assertEqual(result["quality_repair_history"], [repair_record])
        self.assertTrue(result["visual_review_passed"])
        self.assertTrue((self.root / "output" / "_garments.glb").is_file())
        self.assertTrue((self.root / "evidence" / "rejected-output-00" / "_garments.glb").is_file())

    def test_rigged_complete_preserves_skins_weights_and_inverse_binds(self):
        source = self.root / "rigged.glb"
        make_glb(source, skin=True, embedded_image=True)
        geometry = GarmentSource(source)

        def fake_render(source_path, candidates, directory, godot_path, render_script, triangle_id_model=None, triangle_id_model_high=None):
            renders = directory / "renders"
            renders.mkdir(parents=True)
            maps = []
            for view in RENDER_VIEWS:
                path = renders / (view + ".triangles.low.png")
                high_path = renders / (view + ".triangles.high.png")
                Image.new("RGB", (2, 2), (65, 51, 51)).save(path)
                Image.new("RGB", (2, 2), (51, 51, 51)).save(high_path)
                maps.append(
                    dict(
                        view=view,
                        path=str(path),
                        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                        high_path=str(high_path),
                        high_sha256=hashlib.sha256(high_path.read_bytes()).hexdigest(),
                    )
                )
            report = dict(
                model_sha256=geometry.sha256,
                triangle_id_model_sha256=hashlib.sha256(Path(triangle_id_model).read_bytes()).hexdigest(),
                triangle_id_model_high_sha256=hashlib.sha256(Path(triangle_id_model_high).read_bytes()).hexdigest(),
                triangle_id_maps=maps,
            )
            (renders / "views.json").write_text(json.dumps(report), encoding="utf-8")
            return []

        with (
            patch("garment_complete._render", side_effect=fake_render),
            patch("garment_complete.request_segmentation", return_value=segmentation()),
        ):
            result = complete(source, self.root / "rigged-output", self.root / "rigged-evidence", "godot", "review", quality_review=False)

        self.assertTrue(result["rigged"])
        self.assertTrue(result["skeleton_preserved"])
        self.assertTrue(result["skin_weights_preserved"])
        self.assertTrue(result["inverse_bind_matrices_preserved"])
        document, binary = load_glb(self.root / "rigged-output" / "cape.glb")
        self.assertEqual(document["skins"], geometry.document["skins"])
        self.assertEqual(document["nodes"][0]["skin"], 0)
        self.assertEqual(document["nodes"][1]["skin"], 0)
        primitive = document["meshes"][document["nodes"][0]["mesh"]]["primitives"][0]
        attributes = primitive["attributes"]
        self.assertIn("JOINTS_0", attributes)
        self.assertIn("WEIGHTS_0", attributes)
        self.assertEqual(
            document["accessors"][attributes["POSITION"]]["count"],
            document["accessors"][attributes["JOINTS_0"]]["count"],
        )
        self.assertEqual(
            accessor_bytes(document, binary, document["skins"][0]["inverseBindMatrices"], 64),
            accessor_bytes(geometry.document, geometry.binary, geometry.document["skins"][0]["inverseBindMatrices"], 64),
        )
        GarmentSource(self.root / "rigged-output" / "cape.glb")
        GarmentSource(self.root / "rigged-evidence" / "triangle-ids-low.glb")

    def test_partial_coverage_fails_closed_without_wearable_output(self):
        def fake_render(source, candidates, directory, godot_path, render_script, triangle_id_model=None, triangle_id_model_high=None):
            renders = directory / "renders"
            renders.mkdir(parents=True)
            (renders / "views.json").write_text("{}", encoding="utf-8")
            return []

        with (
            patch("garment_complete._triangle_id_model", return_value=([dict(node=0, primitive=0, start=0, count=2), dict(node=1, primitive=0, start=2, count=1)], "id")),
            patch("garment_complete._render", side_effect=fake_render),
            patch("garment_complete._validate_id_report"),
            patch("garment_complete.request_segmentation", return_value=segmentation("partial")),
            patch("garment_complete._assign_triangles") as assign,
        ):
            assign.return_value = [dict(item=segmentation("partial")["items"][0], selected={}, evidence=dict(conflict_ratio=0.0))]
            with self.assertRaisesRegex(ValueError, "no_wearable"):
                complete(self.source, self.root / "partial-output", self.root / "partial-evidence", "godot", "review", quality_review=False)
        self.assertFalse((self.root / "partial-output").exists())

    def test_view_request_creates_evidence_directory(self):
        document = dict(
            schema_version=2,
            view="front",
            items=[
                dict(
                    id="cape",
                    visible=True,
                    polygons=[[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]]],
                    complete_visible=True,
                    needs_review=False,
                    missing_regions=[],
                )
            ],
            notes="",
        )

        def fake_perform(config, directory):
            raw = (directory / "api-request.json").read_bytes()
            (directory / "api-receipt.json").write_text(
                canonical(
                    dict(
                        request_sha256=hashlib.sha256(raw).hexdigest(),
                        instructions_sha256=hashlib.sha256(canonical(document).encode("utf-8")).hexdigest(),
                    )
                ),
                encoding="utf-8",
            )
            (directory / "api-plan.json").write_text(canonical(document), encoding="utf-8")

        entry = dict(view="front", mime="image/png", data=png())
        with patch("garment_complete.perform", side_effect=fake_perform):
            result = _request_view_masks(
                dict(endpoint="https://planner.example.com", model="vision", key_env="TEST"),
                dict(items=[inventory("cape", [])]),
                entry,
                self.root / "nested" / "view-front",
            )
        self.assertEqual(result["view"], "front")
        self.assertTrue((self.root / "nested" / "view-front" / "prompt.txt").is_file())

    def test_quality_review_requires_all_views_and_rejects_extraneous_surface(self):
        document = dict(
            schema_version=1,
            passed=False,
            items=[
                dict(
                    id="cape",
                    passed=False,
                    defects=[
                        dict(view="back", kind="missing_surface", observation="Large hole in back cloth"),
                        dict(view="top", kind="extraneous_surface", observation="Boot sole included in garment"),
                    ],
                )
            ],
            notes="",
        )

        def fake_perform(config, directory):
            raw = (directory / "api-request.json").read_bytes()
            (directory / "api-receipt.json").write_text(
                canonical(
                    dict(
                        request_sha256=hashlib.sha256(raw).hexdigest(),
                        instructions_sha256=hashlib.sha256(canonical(document).encode("utf-8")).hexdigest(),
                    )
                ),
                encoding="utf-8",
            )
            (directory / "api-plan.json").write_text(canonical(document), encoding="utf-8")

        entries = [dict(view=view, mime="image/png", data=png()) for view in RENDER_VIEWS]
        with patch("garment_complete.perform", side_effect=fake_perform):
            result = _request_quality_review(
                dict(endpoint="https://planner.example.com", model="vision", key_env="TEST"),
                segmentation(),
                entries,
                entries,
                self.root / "quality",
            )
        self.assertFalse(result["passed"])
        self.assertEqual(result["items"][0]["defects"][1]["kind"], "extraneous_surface")
        request = json.loads((self.root / "quality" / "api-request.json").read_text())
        content = request["messages"][0]["content"]
        self.assertEqual(sum(part["type"] == "image_url" for part in content), 2 * len(RENDER_VIEWS))

    def test_complete_coverage_cannot_claim_missing_regions(self):
        value = segmentation()
        value["items"][0]["missing_regions"] = ["left sleeve"]
        with self.assertRaisesRegex(ValueError, "coverage_conflict"):
            validate_segmentation(value)

    def test_self_intersecting_mask_is_rejected(self):
        bowtie = [[0.0, 0.0], [1.0, 1.0], [0.0, 1.0], [1.0, 0.0]]
        with self.assertRaisesRegex(ValueError, "self_intersection"):
            _validate_simple_polygon(bowtie)
        _validate_simple_polygon([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])

    def test_non_garment_exclusion_applies_before_garment_selection(self):
        polygon = [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]]
        exclusions = dict(
            views=[
                dict(
                    view="front",
                    items=[
                        dict(id="hand_left", visible=True, polygons=polygon),
                        dict(id="footwear", visible=True, polygons=polygon),
                    ],
                )
            ]
        )
        robe = dict(slot="full_body")
        glove = dict(slot="hand_left")
        boot = dict(slot="foot_left")
        hands_only = dict(views=[dict(view="front", items=[exclusions["views"][0]["items"][0]])])
        footwear_only = dict(views=[dict(view="front", items=[exclusions["views"][0]["items"][1]])])
        self.assertTrue(_excluded_pixels(exclusions, "front", robe, (8, 8)).all())
        self.assertFalse(_excluded_pixels(hands_only, "front", glove, (8, 8)).all())
        self.assertFalse(_excluded_pixels(footwear_only, "front", boot, (8, 8)).all())

    def test_topology_pinhole_requires_two_selected_neighbours(self):
        writer = _GlbWriter(self.geometry, "pinhole fixture")
        points = np.asarray([[0, 0, 0], [1, 0, 0], [0, 1, 0], [-1, 0, 0]], dtype="<f4")
        normals = np.tile(np.asarray([[0, 0, 1]], dtype="<f4"), (4, 1))
        uv = np.zeros((4, 2), dtype="<f4")
        writer.add_part(
            "fan",
            dict(POSITION=points, NORMAL=normals, TEXCOORD_0=uv),
            np.asarray([[0, 1, 2], [0, 2, 3], [0, 3, 1]], dtype="<u4"),
        )
        path = self.root / "pinhole.glb"
        path.write_bytes(writer.finish({}))
        source = GarmentSource(path)
        primitive_map = [dict(node=0, primitive=0, start=0, count=3)]
        assignment = dict(selected={(0, 0): np.asarray([1, 2], dtype=np.int64)}, evidence={})
        winner = np.asarray([-1, 0, 0], dtype=np.int64)
        _fill_topology_pinholes(source, primitive_map, [assignment], winner)
        self.assertEqual(assignment["selected"][(0, 0)].tolist(), [0, 1, 2])
        self.assertEqual(assignment["evidence"]["topology_pinhole_triangles"], 1)

    def test_quality_repair_merges_missing_surface_but_replaces_extraneous_mask(self):
        source_image = self.root / "source.png"
        generated_image = self.root / "generated.png"
        source_image.write_bytes(png())
        generated_image.write_bytes(png())
        quality = dict(
            source_views=[dict(view="back", path=str(source_image))],
            generated_views=[dict(view="back", path=str(generated_image))],
            review=dict(items=[dict(id="cape", passed=False, defects=[dict(view="back", kind="missing_surface", observation="hole")])]),
        )
        response = dict(
            items=[
                dict(
                    id="cape",
                    visible=True,
                    polygons=[[[0.1, 0.1], [0.9, 0.1], [0.5, 0.9]]],
                    complete_visible=True,
                    needs_review=False,
                    missing_regions=[],
                )
            ]
        )
        with patch("garment_complete._request_view_masks", return_value=response):
            repaired, record = _repair_quality_inventory(dict(), segmentation(), quality, self.root / "repair")
        back = next(mask for mask in repaired["items"][0]["masks"] if mask["view"] == "back")
        self.assertEqual(len(back["polygons"]), 2)
        self.assertTrue(record["changed"])
        quality["review"]["items"][0]["defects"][0]["kind"] = "extraneous_surface"
        with patch("garment_complete._request_view_masks", return_value=response):
            replaced, _record = _repair_quality_inventory(dict(), segmentation(), quality, self.root / "replace")
        back = next(mask for mask in replaced["items"][0]["masks"] if mask["view"] == "back")
        self.assertEqual(len(back["polygons"]), 1)


if __name__ == "__main__":
    unittest.main()
