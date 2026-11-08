"""Sculpt plans and durable CLI jobs; synthetic CLI with optional real Blender."""

import base64
import copy
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from anatomy_base import AGE_SOURCE_SHA256
from anatomy_base import SOURCE_SHA256 as ANATOMY_SOURCE_SHA256
from anatomy_body import BODY_SOURCE_SHA256
from character_detail import resolve_detail
from comfy_provider import digest, register
from executor import check_content
from extensions import NodeRegistry, validate_outputs
from organic_detail import expand_patterns
from sculpt_builder import (
    CHARACTER_AGE_WEIGHTS,
    LOFT_STEPS,
    MAX_TRIANGLES,
    MAX_VERTICES,
    RADIAL,
    _loft_sections,
    character_defaults,
    modeling_schema,
    resolve_age_blend,
    validate_plan,
)
from sculpt_provider import (
    _WORKERS,
    CALIBRATION_SCOPE,
    SculptProvider,
    frame_turnaround_panels,
    load_operator_calibration,
    modeling_quality_policy,
    selected_turnaround_panels,
    sheet_evidence,
)
from test_modeling_provider import FAKE_CS

ROOT = Path(__file__).resolve().parents[2]
BLENDER = Path(os.environ.get("AINATIVE_TEST_BLENDER") or shutil.which("blender") or "__blender_unavailable__")
BUILDER = ROOT / "tools/ainative/sculpt_builder.py"
KEY = "a" * 64
PLAN = {
    "version": 2,
    "name": "Organic",
    "materials": [{"name": "skin", "color": [0.4, 0.6, 0.8, 1], "roughness": 0.7}],
    "regions": [
        {
            "name": "body",
            "role": "body",
            "material": "skin",
            "surface": {
                "kind": "ellipsoid",
                "position": [0, 0.5, 0],
                "rotation_degrees": [0, 0, 0],
                "size": [1, 1, 1],
                "sections": [],
                "vertices": [],
                "faces": [],
            },
        }
    ],
    "finish": {"voxel_size": 0.06, "smooth_iterations": 1, "subdivision": 0},
    "completion": {"mode": "plausible", "inferred_regions": ["body"]},
}


def organic_receipt_fixture():
    plan = copy.deepcopy(PLAN)
    plan["regions"][0]["surface"].update(
        kind="loft",
        position=[0.1, 0.2, 0.3],
        rotation_degrees=[15, 30, 10],
        size=[1.1, 0.9, 1.2],
        sections=[dict(center=[0.1 * y, y, 0.15 * y], radius=[0.12] * 4, roll=17 * y) for y in (0.1, 0.55, 1.0)],
    )
    plan["repeat_patterns"] = [
        dict(
            name=name,
            source_region="body",
            material="skin",
            count=3,
            rows=1,
            start=0.1,
            end=0.8,
            side_degrees=angle,
            row_spread_degrees=0,
            radius=radius,
            radius_tip_scale=0.6,
            depth=0.5,
        )
        for name, angle, radius in (("small", 0, 0.004), ("large", 180, 0.06))
    ]
    plan["finish"].update(voxel_size=0.003, subdivision=0)
    plan["completion"]["inferred_regions"] = ["body", "small", "large"]
    validate_plan(plan)
    _, patterns = expand_patterns(plan, _loft_sections, MAX_TRIANGLES, MAX_VERTICES)
    receipt = dict(
        loft_sampling=dict(radial=RADIAL, samples_per_span=LOFT_STEPS, cap_latitude_rings=4),
        pre_voxel_loft_subdivision=1,
        pre_smoothed_loft_count=1,
        pre_smoothed_lofts=["body"],
        patterns=patterns,
        generated_cups=6,
        surface_seating=[],
        rounded_caps=[],
    )
    for pattern in patterns:
        for placement in pattern["placements"]:
            receipt["surface_seating"].append(
                dict(
                    name=placement["name"],
                    source_to_surface_distance=0,
                    distance_limit=max(0.009, 0.4 * placement["radius"] * max(placement["size"])),
                    seating_depth=min(0.001, 0.03 * placement["radius"] * min(placement["size"])),
                    normal_alignment=1,
                )
            )
    return plan, receipt


def image_artifact(name, rgb):
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    data = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress((b"\0" + rgb * 2) * 2))
        + chunk(b"IEND", b"")
    )
    sha = hashlib.sha256(data).hexdigest()
    return dict(
        id=name,
        revision=sha,
        type="image",
        payload=dict(
            content_base64=base64.b64encode(data).decode(), content_sha256=sha, bytes=len(data), extension=".png"
        ),
    )


def calibration_fixture(builder):
    image = image_artifact("internal-calibration", b"\x11\x33\x55")["payload"]
    value = dict(
        schema_version=1,
        png_base64=image["content_base64"],
        png_sha256=image["content_sha256"],
        width=2,
        height=2,
        baseline_builder_sha256=hashlib.sha256(builder.read_bytes()).hexdigest(),
        baseline_runtime_sha256={
            name + "_sha256": hashlib.sha256(builder.with_name(name + ".py").read_bytes()).hexdigest()
            for name in ("anatomy_base", "anatomy_body", "character_detail", "organic_detail", "period_groom")
        },
        panels=[
            dict(
                row=0,
                label="SYNTHETIC fixed adult fixture",
                age="adult",
                age_blend=None,
                plan_sha256="a" * 64,
                baseline_controls=dict(head_ratio=7.5, head_width=1.0),
            )
        ],
        scope=CALIBRATION_SCOPE,
    )
    builder.with_name("anatomy_calibration.py").write_text(
        "# Synthetic test asset only\nCALIBRATION = " + repr(value) + "\n", encoding="utf-8"
    )
    return value


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="sculpt-calibration-data-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.builder = self.directory / "sculpt_builder.py"
        self.builder.write_text("# fixed synthetic test builder\n", encoding="utf-8")
        for name in (
            "anatomy_base.py",
            "anatomy_body.py",
            "character_detail.py",
            "organic_detail.py",
            "period_groom.py",
        ):
            self.builder.with_name(name).write_text("# fixed synthetic data\n", encoding="utf-8")
        self.value = calibration_fixture(self.builder)

    def store(self, value):
        self.builder.with_name("anatomy_calibration.py").write_text(
            "CALIBRATION = " + repr(value) + "\n", encoding="utf-8"
        )

    def test_packaged_asset_matches_current_real_builder_and_anatomy_bytes(self):
        # A real-file integration gate must catch a stale committed atlas, rather
        # than merely compare constants within the generated asset.
        value = load_operator_calibration(BUILDER)
        self.assertEqual(value["metadata"]["baseline_builder_sha256"], hashlib.sha256(BUILDER.read_bytes()).hexdigest())
        self.assertTrue(value["png"])
        check_content(value["metadata"])

    def test_literal_asset_validates_and_public_metadata_is_not_inline_content(self):
        value = load_operator_calibration(self.builder)
        self.assertEqual(hashlib.sha256(value["png"]).hexdigest(), self.value["png_sha256"])
        self.assertEqual(value["metadata"]["role"], "internal_fixed_operator_calibration")
        self.assertFalse(value["metadata"]["user_reference"])
        self.assertNotIn("png_base64", value["metadata"])
        check_content(dict(operator_calibration=value["metadata"]))

    def test_executable_or_multiple_assignments_are_rejected_without_execution(self):
        sentinel = self.directory / "must-not-exist"
        for text in (
            "CALIBRATION = __import__('pathlib').Path(" + repr(str(sentinel)) + ").write_text('bad')\n",
            "CALIBRATION = " + repr(self.value) + "\nEXTRA = 1\n",
            "CALIBRATION = alias = " + repr(self.value) + "\n",
        ):
            self.builder.with_name("anatomy_calibration.py").write_text(text, encoding="utf-8")
            with self.subTest(), self.assertRaisesRegex(ValueError, "calibration_invalid"):
                load_operator_calibration(self.builder)
            self.assertFalse(sentinel.exists())

    def test_stale_sources_and_invalid_png_digest_dimensions_are_rejected(self):
        for name, invalid in (
            ("png_base64", self.value["png_base64"] + "a"),
            ("png_sha256", "f" * 64),
            ("width", 3),
            ("height", True),
            ("baseline_builder_sha256", "f" * 64),
            ("baseline_runtime_sha256", dict(anatomy_base_sha256="f" * 64, anatomy_body_sha256="e" * 64)),
        ):
            value = copy.deepcopy(self.value)
            value[name] = invalid
            self.store(value)
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "calibration_invalid"):
                load_operator_calibration(self.builder)

    def test_png_structure_is_validated_even_if_a_corrupt_image_hash_is_updated(self):
        value = copy.deepcopy(self.value)
        png = bytearray(base64.b64decode(value["png_base64"]))
        png[-1] ^= 1  # A wrong IEND CRC must not become trusted by changing only the SHA.
        value["png_base64"] = base64.b64encode(png).decode("ascii")
        value["png_sha256"] = hashlib.sha256(png).hexdigest()
        self.store(value)
        with self.assertRaisesRegex(ValueError, "calibration_invalid"):
            load_operator_calibration(self.builder)

    def test_invalid_or_changed_calibration_fails_before_cli_auth(self):
        config = dict(
            cli_path=sys.executable,
            blender_path=sys.executable,
            builder_path=str(self.builder),
            storage=str(self.directory / "state"),
        )
        self.builder.with_name("anatomy_calibration.py").write_text("CALIBRATION = {}\n", encoding="utf-8")
        provider = SculptProvider(config)
        request = dict(node="text_to_mesh", version="1", inputs={}, parameters=dict(prompt="human"), context=[])
        with patch("sculpt_provider.check_modeling_cli", side_effect=AssertionError("must fail before auth")):
            result = provider.submit(request, dict(schema_version=1, artifacts=[]), KEY)
        self.assertEqual(result["state"], "failed")
        self.assertIn("基线", result["error"])
        self.assertFalse((self.directory / "state" / KEY).exists())
        calibration_fixture(self.builder)
        changed = SculptProvider(dict(config, storage=str(self.directory / "changed-state")))
        value = copy.deepcopy(self.value)
        value["panels"][0]["label"] = "changed fixed fixture"
        self.store(value)
        with patch("sculpt_provider.check_modeling_cli", side_effect=AssertionError("must fail before auth")):
            result = changed.submit(request, dict(schema_version=1, artifacts=[]), KEY)
        self.assertEqual(result["state"], "failed")
        self.assertFalse((self.directory / "changed-state" / KEY).exists())

    def test_changed_detail_code_invalidates_calibration_before_model_use(self):
        for name in ("character_detail.py", "organic_detail.py", "period_groom.py"):
            path = self.builder.with_name(name)
            original = path.read_bytes()
            with self.subTest(dependency=name):
                path.write_bytes(original + b"# changed fixed operator\n")
                with self.assertRaisesRegex(ValueError, "calibration_invalid"):
                    load_operator_calibration(self.builder)
                path.write_bytes(original)


class SculptPlanTests(unittest.TestCase):
    def test_single_sheet_counts_distinct_named_views_and_requires_separate_panels(self):
        panels = [
            dict(view="front", box=[0, 0, 0.5, 0.5]),
            dict(view="back", box=[0.5, 0, 1, 0.5]),
            dict(view="front", box=[0, 0.5, 0.4, 1]),
            dict(view="profile_left_facing", box=[0.4, 0.5, 0.6, 1]),
            dict(view="back", box=[0.6, 0.5, 1, 1]),
        ]
        self.assertEqual(sheet_evidence(panels)["distinct_named_directions"], 3)
        uncertain = [dict(view="unknown", box=[0, 0, 1, 1])]
        self.assertEqual(sheet_evidence(uncertain)["distinct_named_directions"], 0)
        for invalid in ([], panels + [panels[0]], [dict(view="front", box=[0, 0, -1, 1])]):
            with self.assertRaisesRegex(ValueError, "reference_panels"):
                sheet_evidence(invalid)

    def test_registered_operator_picks_largest_observed_panel_per_required_direction(self):
        front = dict(view="front", box=[0, 0, 0.5, 0.5])
        back = dict(view="back", box=[0.5, 0, 1, 0.5])
        side = dict(view="profile_right_facing", box=[0.3, 0.5, 0.6, 1])
        smaller = dict(view="front", box=[0, 0.5, 0.25, 1])
        evidence = sheet_evidence([smaller, back, side, front])
        self.assertEqual(selected_turnaround_panels(evidence), [front, back, side])
        with self.assertRaisesRegex(ValueError, "turnaround_needs_three_views"):
            selected_turnaround_panels(sheet_evidence([front, back]))

    def test_panel_framing_preserves_observations_and_respects_other_figures(self):
        front = dict(view="front", box=[0.05, 0.03, 0.44, 0.45])
        back = dict(view="back", box=[0.53, 0.03, 0.98, 0.45])
        second_front = dict(view="front", box=[0.01, 0.54, 0.40, 0.96])
        side = dict(view="profile_left_facing", box=[0.44, 0.54, 0.56, 0.96])
        panels = [front, back, second_front, side]
        original = copy.deepcopy(panels)
        framed = frame_turnaround_panels(sheet_evidence(panels), [front, back, side])
        self.assertEqual(original, panels)
        self.assertLess(framed[2]["box"][0], 0.42)
        self.assertGreater(framed[2]["box"][0], second_front["box"][2])
        self.assertLessEqual(framed[0]["box"][2], framed[1]["box"][0])
        self.assertLessEqual(framed[1]["box"][3], framed[2]["box"][1])

    def test_diagonally_adjacent_subjects_stay_in_separate_frames(self):
        front = dict(view="front", box=[0.1, 0.1, 0.4, 0.4])
        back = dict(view="back", box=[0.42, 0.42, 0.72, 0.72])
        other_front = dict(view="front", box=[0.76, 0.76, 0.97, 0.98])
        framed = frame_turnaround_panels(sheet_evidence([front, back, other_front]), [front, back])
        self.assertTrue(any(framed[0]["box"][axis + 2] <= framed[1]["box"][axis] for axis in (0, 1)))
        self.assertTrue(any(framed[1]["box"][axis + 2] <= other_front["box"][axis] for axis in (0, 1)))

    def test_optional_face_receipt_is_bound_to_both_fixed_inputs(self):
        prior = dict(helper_sha256="1" * 64, body_sha256="2" * 64)
        config = dict(source_sha256="3" * 64, face_prior=prior)
        receipt = dict(
            builder_sha256="4" * 64,
            source_image_sha256=config["source_sha256"],
            registration_sha256=digest(config),
            observed_colors=True,
            exact_hidden_surface_recovery_claimed=False,
        )
        validate = SculptProvider._validate_registered_surface
        with self.assertRaisesRegex(ValueError, "builder_failed"):
            validate(receipt, config, receipt["builder_sha256"])
        receipt["sampling"] = dict(face_geometry=dict(prior, applied=False))
        validate(receipt, config, receipt["builder_sha256"])
        for name, invalid in (("body_sha256", "5" * 64), ("helper_sha256", None), ("applied", 1)):
            altered = copy.deepcopy(receipt)
            altered["sampling"]["face_geometry"][name] = invalid
            with self.assertRaisesRegex(ValueError, "builder_failed"):
                validate(altered, config, receipt["builder_sha256"])
        config.pop("face_prior")
        receipt["registration_sha256"] = digest(config)
        with self.assertRaisesRegex(ValueError, "builder_failed"):
            validate(receipt, config, receipt["builder_sha256"])

    def test_registered_export_checks_actual_color_and_index_values(self):
        position = struct.pack("<12f", 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1)
        colors = bytearray(struct.pack("<16f", *([0.2, 0.3, 0.4, 1.0] * 4)))
        indices = bytearray(struct.pack("<12H", 0, 2, 1, 0, 1, 3, 1, 2, 3, 2, 0, 3))
        primitive = dict(attributes={"POSITION": 0, "COLOR_0": 1}, indices=2)
        document = dict(
            asset=dict(version="2.0"),
            buffers=[dict(byteLength=136)],
            meshes=[dict(primitives=[primitive])],
            nodes=[dict(mesh=0)],
            scenes=[dict(nodes=[0])],
            scene=0,
            accessors=[
                dict(bufferView=0, type="VEC3", componentType=5126, count=4),
                dict(bufferView=1, type="VEC4", componentType=5126, count=4),
                dict(bufferView=2, type="SCALAR", componentType=5123, count=12),
            ],
            bufferViews=[
                dict(buffer=0, byteOffset=0, byteLength=48),
                dict(buffer=0, byteOffset=48, byteLength=64),
                dict(buffer=0, byteOffset=112, byteLength=24),
            ],
        )

        def blob():
            raw = json.dumps(document).encode()
            raw += b" " * (-len(raw) % 4)
            binary = position + colors + indices
            return (
                struct.pack("<4sII", b"glTF", 2, 28 + len(raw) + len(binary))
                + struct.pack("<I4s", len(raw), b"JSON")
                + raw
                + struct.pack("<I4s", len(binary), b"BIN\0")
                + binary
            )

        receipt = dict(vertices=4, triangles=4)
        SculptProvider._validate_registered_glb(blob(), receipt)
        for invalid in (float("nan"), float("inf"), 2.0, -0.2):
            struct.pack_into("<f", colors, 0, invalid)
            with self.subTest(color=invalid), self.assertRaisesRegex(ValueError, "mesh_invalid"):
                SculptProvider._validate_registered_glb(blob(), receipt)
        struct.pack_into("<f", colors, 0, 0.2)
        for index in (2, 99):
            struct.pack_into("<H", indices, 0, index)
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, "mesh_invalid"):
                SculptProvider._validate_registered_glb(blob(), receipt)
        struct.pack_into("<H", indices, 0, 0)
        for field, value in (("byteOffset", -1), ("byteStride", 3), ("byteLength", 48)):
            with self.subTest(field=field):
                original = document["bufferViews"][1].copy()
                document["bufferViews"][1][field] = value
                with self.assertRaisesRegex(ValueError, "mesh_invalid"):
                    SculptProvider._validate_registered_glb(blob(), receipt)
                document["bufferViews"][1] = original
        document["accessors"][1]["sparse"] = {}
        with self.assertRaisesRegex(ValueError, "mesh_invalid"):
            SculptProvider._validate_registered_glb(blob(), receipt)

    def test_trusted_anatomy_data_change_invalidates_runtime_fingerprint(self):
        with tempfile.TemporaryDirectory(prefix="sculpt-runtime-fingerprint-") as temporary:
            directory = Path(temporary)
            builder = directory / "sculpt_builder.py"
            builder.write_text("# fixed test interpreter\n", encoding="utf-8")
            anatomy = directory / "anatomy_base.py"
            anatomy.write_text("# first trusted data revision\n", encoding="utf-8")
            config = dict(
                cli_path=sys.executable,
                blender_path=sys.executable,
                builder_path=str(builder),
                storage=str(directory / "state"),
            )
            original = SculptProvider(config)
            original_inputs = copy.deepcopy(original.runtime_inputs)
            anatomy.write_text("# second trusted data revision\n", encoding="utf-8")
            changed = SculptProvider(config)
            self.assertNotEqual(original.fingerprint, changed.fingerprint)
            self.assertEqual(original.runtime_inputs, original_inputs)
            self.assertNotEqual(
                original.runtime_inputs["anatomy_base_sha256"], changed.runtime_inputs["anatomy_base_sha256"]
            )
            body = directory / "anatomy_body.py"
            body.write_text("# first body data revision\n", encoding="utf-8")
            with_body = SculptProvider(config)
            body.write_text("# second body data revision\n", encoding="utf-8")
            changed_body = SculptProvider(config)
            self.assertNotEqual(with_body.fingerprint, changed_body.fingerprint)
            self.assertNotEqual(
                with_body.runtime_inputs["anatomy_body_sha256"], changed_body.runtime_inputs["anatomy_body_sha256"]
            )
            calibration = directory / "anatomy_calibration.py"
            calibration.write_text("# first calibration revision\n", encoding="utf-8")
            with_calibration = SculptProvider(config)
            calibration.write_text("# second calibration revision\n", encoding="utf-8")
            self.assertNotEqual(with_calibration.fingerprint, SculptProvider(config).fingerprint)

    def test_character_contract_is_bounded_and_keeps_reserved_annotation(self):
        value = copy.deepcopy(PLAN)
        value.update(character=character_defaults(), regions=[], materials=[])
        value["completion"]["inferred_regions"] = ["character"]
        self.assertEqual(validate_plan(value), value)
        for field, invalid_value in (
            ("head_ratio", 20),
            ("neck_length", 4),
            ("age", "arbitrary code"),
            ("hem_height", 0.1),
            ("sleeve_length", 2),
            ("footwear", "load_mesh"),
        ):
            invalid = copy.deepcopy(value)
            invalid["character"][field] = invalid_value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_plan(invalid)

    def test_host_quality_policy_is_bounded_and_conditionally_anatomical(self):
        policy = modeling_quality_policy()
        self.assertLessEqual(len(policy.encode("utf-8")), 4096)
        self.assertIn("Only when the subject is human", policy)
        self.assertIn("For nonhuman organic subjects do not impose human", policy)
        self.assertIn("explicit user-supplied reference view labels", policy)
        self.assertIn("not recovered truth", policy)
        self.assertIn("ALL supplied USER views are the primary evidence", policy)
        self.assertIn("explicitly requested edit", policy)
        self.assertIn("honoring its supplied role and constraint strength", policy)
        self.assertIn("not a model weight control", policy)
        self.assertIn("physical skull and facial planes", policy)
        self.assertIn("natural garment thickness/drape", policy)
        self.assertIn("An elder label or a numeric age is not evidence of aging", policy)
        self.assertIn("Age alone does not imply emaciation", policy)

    def test_valid_plan_and_schema_version_are_distinct_from_v1(self):
        self.assertEqual(validate_plan(PLAN), PLAN)
        self.assertEqual(modeling_schema()["properties"]["version"]["const"], 2)
        for field, value in (("version", 1), ("code", "bpy.ops.object.delete()")):
            invalid = copy.deepcopy(PLAN)
            invalid[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_plan(invalid)

    def test_plan_budgets_and_nonfinite_geometry_are_rejected(self):
        invalid = []
        plan = copy.deepcopy(PLAN)
        plan["finish"]["voxel_size"] = 0.00001
        invalid.append(plan)
        plan = copy.deepcopy(PLAN)
        plan["regions"][0]["surface"]["position"][0] = float("nan")
        invalid.append(plan)
        plan = copy.deepcopy(PLAN)
        plan["regions"][0]["surface"]["size"][0] = True
        invalid.append(plan)
        plan = copy.deepcopy(PLAN)
        plan["regions"] *= 65
        invalid.append(plan)
        plan = copy.deepcopy(PLAN)
        plan["regions"][0]["surface"]["kind"] = "python"
        invalid.append(plan)
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_plan(value)

    def test_quality_receipt_cannot_use_model_claims_as_measurements(self):
        receipt = dict(
            ok=True,
            version=2,
            sha256="hash",
            source_plan_sha256="plan",
            body_components=1,
            body_manifold=True,
            body_volume=0.5,
            triangles=128,
            vertices=66,
        )
        SculptProvider._validate_quality_receipt(receipt, "hash", "plan")
        for key, value in (
            ("body_components", 2),
            ("body_manifold", False),
            ("body_volume", 0),
            ("body_volume", float("nan")),
            ("triangles", MAX_TRIANGLES + 1),
            ("vertices", MAX_VERTICES + 1),
            ("source_plan_sha256", "different"),
        ):
            invalid = dict(receipt)
            invalid[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                SculptProvider._validate_quality_receipt(invalid, "hash", "plan")

    def test_native_detail_receipt_is_bound_to_the_actual_requested_controls(self):
        character = character_defaults("stylized")
        character.update(hair="short_wavy", clothing="coverall", detail=dict(smile=0.6, cloth_ease=0.4))
        original = copy.deepcopy(character)
        receipt = dict(
            requested_detail=copy.deepcopy(character["detail"]),
            effective_detail=resolve_detail(character),
            garment_coverage="single_connected_coverall",
        )
        self.assertEqual(SculptProvider._detail_provenance(receipt, character), receipt)
        self.assertEqual(character, original)
        for field, value in (
            ("requested_detail", None),
            ("effective_detail", {}),
            ("garment_coverage", "exposed_midriff"),
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                SculptProvider._detail_provenance(dict(receipt, **{field: value}), character)

    def test_organic_receipt_cannot_claim_unrequested_cups_caps_or_presmoothing(self):
        receipt = dict(
            loft_sampling=dict(radial=RADIAL, samples_per_span=LOFT_STEPS, cap_latitude_rings=4),
            pre_voxel_loft_subdivision=0,
            pre_smoothed_loft_count=0,
            pre_smoothed_lofts=[],
            patterns=[],
            generated_cups=0,
            surface_seating=[],
            rounded_caps=[],
        )
        public = SculptProvider._organic_provenance(receipt, PLAN)
        self.assertEqual(public["generated_cups"], 0)
        check_content(public)
        for field, value in (
            ("generated_cups", 1),
            ("pre_voxel_loft_subdivision", 1),
            ("pre_smoothed_lofts", ["body"]),
            ("rounded_caps", [dict(name="body", end_caps={})]),
            ("surface_seating", [dict(name="fake")]),
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                SculptProvider._organic_provenance(dict(receipt, **{field: value}), PLAN)

    def test_organic_placements_match_requested_local_frame_radius_and_source_trs(self):
        plan, receipt = organic_receipt_fixture()
        original = copy.deepcopy((plan, receipt))
        self.assertEqual(SculptProvider._organic_provenance(receipt, plan)["generated_cups"], 6)
        mutations = {
            "missing_frame": lambda item: {"name": item["name"]},
            "wrong_center": lambda item: dict(item, center=[9, 9, 9]),
            "wrong_axis": lambda item: dict(item, axis=[0, 0, 0]),
            "wrong_radius": lambda item: dict(item, radius=0.06),
            "wrong_trs": lambda item: dict(item, rotation_degrees=[0, 0, 0], size=[1, 1, 1]),
            "nonfinite_frame": lambda item: dict(item, position=[float("nan"), 0, 0]),
            "boolean_vector": lambda item: dict(item, axis=[True, 0, 0]),
        }
        for name, mutate in mutations.items():
            invalid = copy.deepcopy(receipt)
            placement = invalid["patterns"][0]["placements"][0]
            invalid["patterns"][0]["placements"][0] = mutate(placement)
            with self.subTest(name=name), self.assertRaises(ValueError):
                SculptProvider._organic_provenance(invalid, plan)
        self.assertEqual((plan, receipt), original)

    def test_small_cup_cannot_borrow_large_pattern_distance_or_seating_depth(self):
        plan, receipt = organic_receipt_fixture()
        for changes in (
            dict(source_to_surface_distance=0.023, distance_limit=0.024),
            dict(distance_limit=0.024),
            dict(seating_depth=0.001),
        ):
            invalid = copy.deepcopy(receipt)
            invalid["surface_seating"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                SculptProvider._organic_provenance(invalid, plan)

    def test_organic_seating_names_and_fields_are_strict(self):
        plan, receipt = organic_receipt_fixture()
        for changes in (dict(name="unrequested"), dict(content_sha256="f" * 64), dict(normal_alignment=True)):
            invalid = copy.deepcopy(receipt)
            invalid["surface_seating"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                SculptProvider._organic_provenance(invalid, plan)
        invalid = copy.deepcopy(receipt)
        invalid["surface_seating"][1] = copy.deepcopy(invalid["surface_seating"][0])
        with self.assertRaises(ValueError):
            SculptProvider._organic_provenance(invalid, plan)

    def test_organic_receipt_rejects_unbounded_plan_before_fixed_expansion(self):
        plan, receipt = organic_receipt_fixture()
        plan["repeat_patterns"][0]["count"] = 1000000
        with patch("sculpt_provider.expand_patterns", side_effect=AssertionError("unbounded expansion")):
            with self.assertRaises(ValueError):
                SculptProvider._organic_provenance(receipt, plan)

    def test_age_provenance_requires_bounded_weight_and_source_hashes(self):
        expected = dict(
            anatomy_age_source_sha256=list(AGE_SOURCE_SHA256),
            anatomy_age_weight=CHARACTER_AGE_WEIGHTS["mature"],
            requested_age_blend=None,
            effective_age_blend=CHARACTER_AGE_WEIGHTS["mature"],
        )
        self.assertEqual(SculptProvider._age_provenance(expected, dict(age="mature")), expected)
        for name, value in (
            ("anatomy_age_weight", True),
            ("anatomy_age_weight", 1),
            ("anatomy_age_weight", float("nan")),
            ("anatomy_age_source_sha256", ["untrusted path", "f" * 64]),
            ("anatomy_age_source_sha256", ["f" * 64, "f" * 64]),
        ):
            invalid = dict(expected)
            invalid[name] = value
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                SculptProvider._age_provenance(invalid, dict(age="mature"))

    def test_requested_age_blend_matches_effective_weight_without_changing_old_plans(self):
        for blend in (None, 0.0, 0.8, 1.0):
            character = dict(age="elder", age_blend=blend)
            effective = resolve_age_blend(character)
            receipt = dict(
                anatomy_age_source_sha256=list(AGE_SOURCE_SHA256),
                anatomy_age_weight=effective,
                requested_age_blend=blend,
                effective_age_blend=effective,
            )
            self.assertEqual(SculptProvider._age_provenance(receipt, character), receipt)
            with self.assertRaises(ValueError):
                SculptProvider._age_provenance(dict(receipt, effective_age_blend=0.123), character)
        character = character_defaults()
        self.assertNotIn("age_blend", character)
        value = copy.deepcopy(PLAN)
        value.update(character=character, regions=[], materials=[])
        value["completion"]["inferred_regions"] = ["character"]
        self.assertEqual(validate_plan(value), value)

    def test_numerical_fill_is_recorded_instead_of_claiming_no_component_change(self):
        fill = dict(
            kind="certified_internal_negative_voxel_cavity", outer_skin_modified=False, signed_volume=-0.000000001
        )
        provenance = SculptProvider._numerical_provenance(dict(internal_voxel_fills=[fill]))
        self.assertEqual(provenance["internal_voxel_fill_count"], 1)
        self.assertRegex(provenance["internal_voxel_fill_certificates_sha256"], r"^[a-f0-9]{64}$")
        for key, value in (("outer_skin_modified", True), ("signed_volume", 0.1), ("kind", "drop_largest_component")):
            invalid = dict(fill)
            invalid[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                SculptProvider._numerical_provenance(dict(internal_voxel_fills=[invalid]))

    def test_character_provenance_distinguishes_fixed_body_data_from_neural_or_reference_mesh(self):
        operator = dict(
            kind="trusted_parametric_anatomy_v1",
            surface_implementation="continuous_cc0_body_v1",
            neural_weights_loaded=False,
            source_reference_mesh_imported=False,
            trusted_anatomy_base_used=False,
            trusted_anatomy_body_used=True,
            expanded_plan_sha256="f" * 64,
            anatomy_base_sha256=BODY_SOURCE_SHA256["base.obj"],
            anatomy_body_source_sha256=BODY_SOURCE_SHA256,
            anatomy_age_source_sha256=list(AGE_SOURCE_SHA256),
        )
        result = SculptProvider._character_provenance(operator)
        self.assertEqual(result["anatomy_body_source_sha256"], BODY_SOURCE_SHA256)
        self.assertNotIn("parameters", result)
        for name, value in (
            ("neural_weights_loaded", True),
            ("source_reference_mesh_imported", True),
            ("trusted_anatomy_base_used", True),
            ("surface_implementation", "primitive_skin_fusion"),
            ("anatomy_body_source_sha256", {"unsafe/source/path": "f" * 64}),
        ):
            invalid = dict(operator)
            invalid[name] = value
            with self.subTest(name=name), self.assertRaises(ValueError):
                SculptProvider._character_provenance(invalid)

    def test_continuous_surface_receipt_discloses_requested_and_effective_finish_controls(self):
        finish = dict(voxel_size=0.004, smooth_iterations=2, subdivision=0)
        operator = dict(
            requested_voxel_size=0.004,
            voxel_remesh_applied=False,
            effective_core_voxel_size=None,
            requested_smooth_iterations=2,
            effective_smooth_iterations=2,
            smoothing_factor=0.12,
            requested_subdivision=0,
            effective_body_subdivision=1,
            fixed_minimum_body_subdivision=1,
        )
        self.assertEqual(SculptProvider._surface_execution(operator, finish), operator)
        for name, value in (
            ("voxel_remesh_applied", True),
            ("effective_core_voxel_size", 0.004),
            ("effective_smooth_iterations", 1),
            ("requested_subdivision", False),
            ("effective_body_subdivision", 0),
        ):
            invalid = dict(operator)
            invalid[name] = value
            with self.subTest(name=name), self.assertRaises(ValueError):
                SculptProvider._surface_execution(invalid, finish)


@unittest.skipUnless(os.name == "nt", "Synthetic CLI fixture is a Windows executable")
class SculptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix="sculpt-cli-fixture-")
        cls.exe = Path(cls.build.name) / "fake-sculpt.exe"
        source = cls.exe.with_suffix(".cs")
        source.write_text(FAKE_CS, encoding="utf-8")
        compiler = Path(os.environ.get("WINDIR", "C:/Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
        if not compiler.is_file():
            raise unittest.SkipTest("C# fixture compiler unavailable")
        subprocess.run([str(compiler), "/nologo", "/out:" + str(cls.exe), str(source)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sculpt-provider-")
        self.directory = Path(self.tmp.name)
        self.fake = self.directory / "fake-sculpt.exe"
        shutil.copy2(self.exe, self.fake)
        (self.directory / "plan.json").write_text(json.dumps(PLAN), encoding="utf-8")
        self.config = dict(
            cli_path=str(self.fake),
            storage=str(self.directory / "state"),
            blender_path=str(BLENDER if BLENDER.is_file() else self.fake),
            builder_path=str(BUILDER),
        )
        self.provider = SculptProvider(self.config)
        self.request = dict(
            node="text_to_mesh", version="1", inputs={}, parameters={"prompt": "a rounded organic form"}, context=[]
        )
        self.manifest = dict(schema_version=1, artifacts=[])

    def tearDown(self):
        with self.provider.db() as db:
            keys = [row[0] for row in db.execute("SELECT key FROM jobs")]
        for key in keys:
            self.provider.cancel(key)
        deadline = time.monotonic() + 7
        while time.monotonic() < deadline and any(process.poll() is None for process in _WORKERS):
            time.sleep(0.05)
        for process in _WORKERS:
            process.poll()
        self.tmp.cleanup()

    def mode(self, value):
        (self.directory / "mode").write_text(value)

    def use_synthetic_calibration_runtime(self):
        runtime = self.directory / "synthetic-calibration-runtime"
        runtime.mkdir()
        for name in (
            "sculpt_builder.py",
            "anatomy_base.py",
            "anatomy_body.py",
            "character_detail.py",
            "organic_detail.py",
            "period_groom.py",
        ):
            shutil.copy2(BUILDER.with_name(name), runtime / name)
        calibration_fixture(runtime / "sculpt_builder.py")
        self.config = dict(self.config, builder_path=str(runtime / "sculpt_builder.py"))
        self.provider = SculptProvider(self.config)

    def wait(self, key=KEY):
        deadline = time.monotonic() + 330
        while time.monotonic() < deadline:
            result = self.provider.poll(key)
            if result["state"] in ("succeeded", "failed", "cancelled"):
                return result
            time.sleep(0.1)
        self.fail("sculpt worker did not complete")

    def wait_started(self):
        deadline = time.monotonic() + 10
        while not (self.directory / "started").exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue((self.directory / "started").is_file())

    @unittest.skipUnless(BLENDER.is_file(), "Explicit real Blender executable required")
    def test_synthetic_cli_real_rounded_loft_cups_reaches_strict_receipt_gate(self):
        self.use_synthetic_calibration_runtime()
        value = copy.deepcopy(PLAN)
        surface = value["regions"][0]["surface"]
        surface.update(
            kind="loft",
            position=[0, 0, 0],
            sections=[dict(center=[0, y, 0], radius=[0.12] * 4, roll=0) for y in (0.1, 1.0)],
            end_caps=dict(start="rounded", end="rounded", depth=0.6),
        )
        value["repeat_patterns"] = [
            dict(
                name="suckers",
                source_region="body",
                material="skin",
                count=3,
                rows=2,
                start=0.2,
                end=0.8,
                side_degrees=90,
                row_spread_degrees=60,
                radius=0.015,
                radius_tip_scale=0.7,
                depth=0.5,
            )
        ]
        value["finish"].update(voxel_size=0.025, subdivision=0)
        value["completion"]["inferred_regions"] = ["body", "suckers"]
        validate_plan(value)
        (self.directory / "plan.json").write_text(json.dumps(value), encoding="utf-8")
        self.provider.submit(self.request, self.manifest, KEY)
        result = self.wait()
        self.assertEqual(result["state"], "succeeded", self.provider.read(KEY).get("terminal"))
        manifest = self.provider.result_manifest(KEY)
        check_content(manifest)
        receipt = manifest["artifacts"][0]["payload"]["provenance"]["builder_receipt"]
        detail = receipt["quality"]["organic_detail"]
        self.assertEqual(detail["generated_cups"], 6)
        self.assertEqual(detail["surface_seating_count"], 6)
        self.assertEqual(detail["pre_smoothed_lofts"], ["body"])
        self.assertTrue(detail["patterns"][0]["hollow_closed_dishes"])
        self.assertEqual(receipt["quality"]["body_components"], 1)

    @unittest.skipUnless(BLENDER.is_file(), "Explicit real Blender executable required")
    def test_synthetic_cli_real_blender_organic_mesh_receipt_and_recovery(self):
        self.provider.submit(self.request, self.manifest, KEY)
        result = self.wait()
        self.assertEqual(result["state"], "succeeded", self.provider.read(KEY))
        manifest = self.provider.result_manifest(KEY)
        registry = NodeRegistry()
        register(registry)
        validate_outputs(registry, "text_to_mesh", "1", result["outputs"], manifest)
        check_content(manifest)
        provenance = manifest["artifacts"][0]["payload"]["provenance"]
        self.assertEqual(provenance["provider"], "codex-sculpt")
        self.assertFalse(provenance["exact_hidden_surface_recovery_claimed"])
        self.assertFalse(provenance["generated_code_executed"])
        self.assertEqual(provenance["hidden_surface_policy"], "generated_from_text_unobserved_geometry")
        self.assertEqual(provenance["builder_receipt"]["quality"]["body_components"], 1)
        self.assertTrue(provenance["builder_receipt"]["quality"]["body_manifold"])
        self.assertGreater(provenance["builder_receipt"]["geometry"]["vertices"], 100)
        self.assertNotIn(str(self.directory), json.dumps(manifest))
        reopened = SculptProvider(self.config)
        self.assertEqual(reopened.submit(self.request, self.manifest, KEY)["state"], "succeeded")
        self.assertEqual(reopened.cancel(KEY)["state"], "succeeded")
        self.assertEqual((self.directory / "runs").read_text().count("run"), 1)
        arguments = (self.directory / "args").read_text()
        self.assertIn("--output-schema", arguments)
        self.assertIn("features.image_generation=false", arguments)
        self.assertIn("features.shell_tool=false", arguments)

    @unittest.skipUnless(BLENDER.is_file(), "Explicit real Blender executable required")
    def test_synthetic_cli_real_character_retains_original_and_expanded_receipts(self):
        # These are synthetic controls, not a reference reconstruction or a paid GPT result.
        value = copy.deepcopy(PLAN)
        character = character_defaults()
        character.update(
            age="mature",
            clothing="robe_belt",
            hem_height=0.44,
            sleeve_length=0.75,
            trouser_width=1.3,
            footwear="sandals",
        )
        value.update(character=character, materials=[], regions=[])
        value["completion"]["inferred_regions"] = ["character"]
        (self.directory / "plan.json").write_text(json.dumps(value), encoding="utf-8")
        request = copy.deepcopy(self.request)
        request["parameters"]["prompt"] = "A synthetic full human character for fixed interpreter regression"
        self.provider.submit(request, self.manifest, KEY)
        result = self.wait()
        self.assertEqual(result["state"], "succeeded", self.provider.read(KEY))
        manifest = self.provider.result_manifest(KEY)
        check_content(manifest)
        provenance = manifest["artifacts"][0]["payload"]["provenance"]
        builder = provenance["builder_receipt"]
        self.assertEqual(builder["construction_operator"], "parametric_character")
        self.assertRegex(builder["native_receipt_sha256"], r"^[a-f0-9]{64}$")
        self.assertGreaterEqual(builder["numerical_surface_adjustments"]["internal_voxel_fill_count"], 0)
        self.assertEqual(
            builder["runtime_input_sha256"]["anatomy_base_sha256"],
            hashlib.sha256((ROOT / "tools/ainative/anatomy_base.py").read_bytes()).hexdigest(),
        )
        self.assertEqual(
            builder["runtime_input_sha256"]["anatomy_body_sha256"],
            hashlib.sha256((ROOT / "tools/ainative/anatomy_body.py").read_bytes()).hexdigest(),
        )
        operator = builder["quality"]["character_operator"]
        self.assertEqual(operator["anatomy_base_sha256"], ANATOMY_SOURCE_SHA256)
        self.assertFalse(operator["trusted_anatomy_base_used"])
        self.assertTrue(operator["trusted_anatomy_body_used"])
        self.assertEqual(operator["surface_implementation"], "continuous_cc0_body_v1")
        self.assertEqual(operator["anatomy_body_source_sha256"], BODY_SOURCE_SHA256)
        self.assertFalse(operator["neural_weights_loaded"])
        self.assertFalse(operator["source_reference_mesh_imported"])
        self.assertEqual(operator["anatomy_age_source_sha256"], list(AGE_SOURCE_SHA256))
        self.assertEqual(operator["anatomy_age_weight"], CHARACTER_AGE_WEIGHTS["mature"])
        self.assertFalse(operator["voxel_remesh_applied"])
        self.assertIsNone(operator["effective_core_voxel_size"])
        self.assertEqual(operator["requested_voxel_size"], value["finish"]["voxel_size"])
        self.assertEqual(operator["requested_subdivision"], value["finish"]["subdivision"])
        self.assertEqual(operator["effective_body_subdivision"], max(1, value["finish"]["subdivision"]))
        self.assertEqual(builder["numerical_surface_adjustments"]["internal_voxel_fill_count"], 0)
        canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        source_sha = hashlib.sha256(canonical.encode()).hexdigest()
        self.assertEqual(provenance["instructions_sha256"], source_sha)
        self.assertEqual(builder["quality"]["source_plan_sha256"], source_sha)
        self.assertNotEqual(operator["expanded_plan_sha256"], source_sha)
        self.assertEqual((self.directory / "runs").read_text().count("run"), 1)

    def test_two_ordered_images_preserve_role_strength_and_unique_evidence_count(self):
        self.use_synthetic_calibration_runtime()
        source = image_artifact("front", b"\x20\x40\x60")
        reference = image_artifact("side", b"\x80\x40\x60")
        manifest = dict(schema_version=1, artifacts=[source, reference])
        request = copy.deepcopy(self.request)
        request["node"] = "image_to_mesh"
        request["inputs"] = {"source": {key: source[key] for key in ("id", "revision")}}
        request["context"] = [
            dict(
                role="reference",
                scope="node",
                strength="reference",
                artifact={key: reference[key] for key in ("id", "revision")},
            )
        ]
        plan = self.provider.plan(request, manifest)
        self.assertEqual([image["role"] for image in plan["images"]], ["source", "reference"])
        self.assertEqual([image["strength"] for image in plan["images"]], ["reference", "reference"])
        self.assertEqual(plan["distinct_reference_images"], 2)
        self.assertIn("remain_ambiguous", plan["hidden_surface_policy"])
        request["context"][0]["artifact"] = request["inputs"]["source"]
        repeated = self.provider.plan(request, manifest)
        self.assertEqual(repeated["distinct_reference_images"], 1)
        self.assertIn("single_view", repeated["hidden_surface_policy"])

    def test_two_image_instruction_receipt_uses_reference_digests_not_inline_content(self):
        self.use_synthetic_calibration_runtime()
        source = image_artifact("front", b"\x20\x40\x60")
        reference = image_artifact("side", b"\x80\x40\x60")
        manifest = dict(schema_version=1, artifacts=[source, reference])
        request = copy.deepcopy(self.request)
        request["node"] = "image_to_mesh"
        request["inputs"] = {"source": {name: source[name] for name in ("id", "revision")}}
        request["context"] = [
            dict(
                role="reference",
                scope="node",
                strength="reference",
                artifact={name: reference[name] for name in ("id", "revision")},
            )
        ]
        value = copy.deepcopy(PLAN)
        value["completion"]["mode"] = "reference_constrained"
        (self.directory / "plan.json").write_text(json.dumps(value), encoding="utf-8")
        plan = self.provider.plan(request, manifest)
        record = dict(
            request=request,
            manifest=manifest,
            fingerprint=self.provider.fingerprint,
            heartbeat=time.time(),
            created=time.time(),
            stage="intent",
            plan=plan,
        )
        with self.provider.db() as db:
            db.execute("INSERT INTO jobs VALUES(?,?)", (KEY, json.dumps(record)))
            db.execute("INSERT INTO leases VALUES(?,?,0)", (KEY, time.time()))
        directory = self.directory / "state" / KEY
        directory.mkdir()
        _, receipt = self.provider._instructions(KEY, plan, directory)
        for evidence, artifact in zip(receipt["reference_images"], (source, reference)):
            self.assertEqual(evidence["reference_sha256"], artifact["payload"]["content_sha256"])
            self.assertNotIn("content_sha256", evidence)
            self.assertNotIn("content_base64", evidence)
        self.assertEqual([item["role"] for item in receipt["reference_images"]], ["source", "reference"])
        calibration = receipt["operator_calibration"]
        self.assertEqual(calibration["attachment_index"], 3)
        self.assertFalse(calibration["user_reference"])
        self.assertEqual(receipt["distinct_reference_images"], 2)
        self.assertIn("remain_ambiguous", receipt["hidden_surface_policy"])
        self.assertEqual((self.directory / "args").read_text().splitlines().count("--image"), 3)
        arguments = (self.directory / "args").read_text().splitlines()
        attachments = [Path(arguments[index + 1]) for index, value in enumerate(arguments) if value == "--image"]
        self.assertEqual(
            [path.name for path in attachments], ["reference-1.png", "reference-2.png", "operator-calibration.png"]
        )
        self.assertEqual(hashlib.sha256(attachments[-1].read_bytes()).hexdigest(), calibration["image_sha256"])
        check_content(dict(payload=dict(provenance=dict(instruction_receipt=receipt))))
        self.assertFalse((directory / "builder.stdout").exists())

    def test_single_image_turnaround_passes_to_builder_as_one_source_and_three_observed_directions(self):
        self.use_synthetic_calibration_runtime()
        # This test exercises model selection and its bound receipt only.
        builder = Path(self.config["builder_path"])
        builder.with_name("turnaround_surface.py").write_bytes(b"# synthetic fixed geometry helper\n")
        self.provider = SculptProvider(self.config)
        image = image_artifact("sheet", bytes((32, 64, 96)))
        request = dict(
            node="image_to_mesh",
            version="1",
            inputs={"source": {"id": image["id"], "revision": image["revision"]}},
            parameters={"prompt": "reconstruct turnaround"},
            context=[],
        )
        manifest = dict(schema_version=1, artifacts=[image])
        plan = self.provider.plan(request, manifest)
        response = copy.deepcopy(PLAN)
        response.update(
            character=character_defaults(), regions=[], materials=[], sheet_construction="registered_turnaround"
        )
        response["completion"] = dict(mode="reference_constrained", inferred_regions=["character"])
        response["reference_panels"] = [
            dict(view="front", box=[0, 0, 0.5, 0.5]),
            dict(view="back", box=[0.5, 0, 1, 0.5]),
            dict(view="profile_left_facing", box=[0, 0.5, 1, 1]),
        ]
        (self.directory / "plan.json").write_text(json.dumps(response), encoding="utf-8")
        record = dict(
            request=request,
            manifest=manifest,
            fingerprint=self.provider.fingerprint,
            created=time.time(),
            heartbeat=time.time(),
            stage="intent",
            plan=plan,
        )
        with self.provider.db() as db:
            db.execute("INSERT INTO jobs VALUES(?,?)", (KEY, json.dumps(record)))
            db.execute("INSERT INTO leases VALUES(?,?,0)", (KEY, time.time()))
        directory = self.directory / "state" / KEY
        directory.mkdir()
        instructions, receipt = self.provider._instructions(KEY, plan, directory)
        self.assertNotIn("reference_panels", instructions)
        self.assertNotIn("sheet_construction", instructions)
        self.assertEqual(receipt["sheet_construction"], "registered_turnaround")
        self.assertEqual(receipt["observed_selected_panels"], receipt["sheet_view_evidence"]["panels"])
        self.assertEqual(len(receipt["registered_panels"]), 3)
        self.assertEqual(receipt["distinct_reference_images"], 1)
        evidence = receipt["sheet_view_evidence"]
        self.assertEqual(evidence["source_sha256"], image["revision"])
        self.assertEqual(evidence["distinct_named_directions"], 3)
        self.assertEqual(receipt["operator_calibration"]["attachment_index"], 2)
        self.assertEqual(
            receipt["hidden_surface_policy"], "single_sheet_multiple_observed_views_hidden_surfaces_remain_ambiguous"
        )
        check_content(dict(instruction_receipt=receipt))

    def test_refuses_third_reference_or_global_context_instead_of_ignoring_it(self):
        artifact = image_artifact("front", b"\x20\x40\x60")
        manifest = dict(schema_version=1, artifacts=[artifact])
        request = copy.deepcopy(self.request)
        reference = dict(
            role="reference",
            scope="node",
            strength="reference",
            artifact={key: artifact[key] for key in ("id", "revision")},
        )
        request["context"] = [reference] * 3
        with self.assertRaisesRegex(ValueError, "unsupported_multiple_image_constraints"):
            self.provider.plan(request, manifest)
        request["context"] = [dict(reference, scope="workflow")]
        with self.assertRaisesRegex(ValueError, "unsupported_context_semantics"):
            self.provider.plan(request, manifest)

    def test_multi_image_cli_attachments_and_roles_are_not_dropped(self):
        self.use_synthetic_calibration_runtime()
        source = image_artifact("front", b"\x20\x40\x60")
        reference = image_artifact("side", b"\x80\x40\x60")
        request = copy.deepcopy(self.request)
        request["node"] = "image_to_mesh"
        request["inputs"] = {"source": {key: source[key] for key in ("id", "revision")}}
        request["context"] = [
            dict(
                role="reference",
                scope="node",
                strength="reference",
                artifact={key: reference[key] for key in ("id", "revision")},
            )
        ]
        plan = copy.deepcopy(PLAN)
        plan["completion"]["mode"] = "reference_constrained"
        (self.directory / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
        # Stop before native builder to test CLI attachments without costly geometry.
        self.mode("no-turn")
        self.provider.submit(request, dict(schema_version=1, artifacts=[source, reference]), KEY)
        self.assertEqual(self.wait()["state"], "failed")
        arguments = (self.directory / "args").read_text().splitlines()
        self.assertEqual(arguments.count("--image"), 3)
        prompt = (self.directory / "prompt").read_text(encoding="utf-8")
        self.assertIn("reference_constrained", prompt)
        self.assertIn('"role":"source"', prompt)
        self.assertIn('"role":"reference"', prompt)
        self.assertIn("ALL supplied USER views are the primary evidence", prompt)
        self.assertIn("not a generic 7.5-head default", prompt)
        self.assertIn("without replacing unrelated visible identity", prompt)
        self.assertIn("hem_height is the lowest garment Y divided by total character height", prompt)
        self.assertIn("preserve observed exposed forearms", prompt)
        self.assertIn("footwear=sandals", prompt)
        self.assertIn("Do not force differently colored trousers to inherit a shirt's color", prompt)
        self.assertIn("NOT a user target, reference view or reconstructed result", prompt)
        self.assertIn("nose_length increases FORWARD nose projection", prompt)
        self.assertIn("cheek_fullness increases forward cheek volume; it does not widen the skull", prompt)
        self.assertIn("Distinct USER target-image evidence count: 2", prompt)

    def test_quality_supplement_keeps_full_user_prompt_and_one_cli_request(self):
        request = copy.deepcopy(self.request)
        subject = "preserve-this-start " + ("organic detailed form " * 400) + " preserve-this-end"
        request["parameters"]["prompt"] = subject
        self.mode("no-turn")
        self.provider.submit(request, self.manifest, KEY)
        self.assertEqual(self.wait()["state"], "failed")
        prompt = (self.directory / "prompt").read_text(encoding="utf-8")
        self.assertIn(subject, prompt)
        self.assertIn(modeling_quality_policy(), prompt)
        self.assertIn("finish.voxel_size remains requested provenance", prompt)
        self.assertEqual((self.directory / "runs").read_text().count("run"), 1)
        self.assertNotIn("(bad anatomy:", prompt)

    def test_config_is_frozen_and_changed_request_cannot_replay_intent(self):
        self.mode("block")
        self.config["cli_path"] = "changed"
        self.assertEqual(self.provider.config["cli_path"], str(self.fake))
        self.provider.submit(self.request, self.manifest, KEY)
        changed = copy.deepcopy(self.request)
        changed["parameters"]["prompt"] = "different"
        with self.assertRaisesRegex(ValueError, "idempotency conflict"):
            self.provider.submit(changed, self.manifest, KEY)

    def test_missing_custom_builder_sibling_data_fails_before_cli(self):
        for missing in (
            "anatomy_base.py",
            "anatomy_body.py",
            "character_detail.py",
            "organic_detail.py",
            "period_groom.py",
            "anatomy_calibration.py",
        ):
            with self.subTest(missing=missing):
                custom = self.directory / ("custom-runtime-" + missing)
                custom.mkdir()
                script = custom / "sculpt_builder.py"
                script.write_bytes(BUILDER.read_bytes())
                for other in (
                    "anatomy_base.py",
                    "anatomy_body.py",
                    "character_detail.py",
                    "organic_detail.py",
                    "period_groom.py",
                    "anatomy_calibration.py",
                ):
                    if other != missing:
                        (custom / other).write_text("# fixed synthetic test data\n", encoding="utf-8")
                provider = SculptProvider(dict(self.config, builder_path=str(script), storage=str(custom / "state")))
                self.assertIsNone(provider.runtime_inputs[missing[:-3] + "_sha256"])
                result = provider.submit(self.request, self.manifest, KEY)
                self.assertEqual(result["state"], "failed")
                self.assertIn("固定解剖数据", result["error"])
                self.assertFalse((self.directory / "runs").exists())
                self.assertFalse((provider.storage / KEY).exists())

    def test_cancel_is_durable_and_leases_do_not_rewrite_image_manifests(self):
        self.mode("block")
        self.provider.submit(self.request, self.manifest, KEY)
        self.wait_started()
        with self.provider.db() as db:
            before = db.execute("SELECT body FROM jobs WHERE key=?", (KEY,)).fetchone()[0]
        self.provider._active(KEY)
        self.provider._active(KEY)
        with self.provider.db() as db:
            after = db.execute("SELECT body FROM jobs WHERE key=?", (KEY,)).fetchone()[0]
        self.assertEqual(before, after)
        self.assertEqual(self.provider.cancel(KEY)["state"], "cancelled")
        self.assertFalse(self.provider._active(KEY))
        self.assertEqual(SculptProvider(self.config).submit(self.request, self.manifest, KEY)["state"], "cancelled")
        with self.assertRaisesRegex(ValueError, "result not available"):
            self.provider.result_manifest(KEY)

    def test_unknown_worker_never_restarts_cli(self):
        record = dict(
            request=self.request,
            manifest=self.manifest,
            fingerprint=self.provider.fingerprint,
            created=0,
            heartbeat=0,
            stage="builder",
        )
        with self.provider.db() as db:
            db.execute("INSERT INTO jobs VALUES(?,?)", (KEY, json.dumps(record)))
        self.assertEqual(self.provider.submit(self.request, self.manifest, KEY)["state"], "failed")
        self.assertFalse((self.directory / "runs").exists())

    def test_invalid_plan_never_executes_blender(self):
        invalid = copy.deepcopy(PLAN)
        invalid["regions"][0]["surface"]["code"] = "forbidden"
        (self.directory / "plan.json").write_text(json.dumps(invalid), encoding="utf-8")
        self.provider.submit(self.request, self.manifest, KEY)
        result = self.wait()
        self.assertEqual(result["state"], "failed")
        self.assertIn("有机建模指令", result["error"])
        self.assertEqual(self.provider.read(KEY)["plan_validation_reason"], "surface_fields_invalid")
        self.assertFalse((self.directory / "state" / KEY / "builder.stdout").exists())

    def test_annotation_prose_is_actionable_plan_error_without_blender_or_normalization(self):
        invalid = copy.deepcopy(PLAN)
        invalid["completion"]["inferred_regions"] = ["All anatomy and facial structure"]
        (self.directory / "plan.json").write_text(json.dumps(invalid), encoding="utf-8")
        self.provider.submit(self.request, self.manifest, KEY)
        result = self.wait()
        self.assertEqual(result["state"], "failed")
        self.assertIn("真实且大小写一致的区域名称", result["error"])
        self.assertEqual(self.provider.read(KEY)["plan_validation_reason"], "completion_regions_invalid")
        directory = self.directory / "state" / KEY
        self.assertFalse((directory / "builder.stdout").exists())
        self.assertFalse((directory / "validated-plan.json").exists())
        self.assertEqual(json.loads((directory / "instructions.json").read_text())["completion"], invalid["completion"])
        record = self.provider.read(KEY)
        turn_receipt = record["cli_turn_receipt"]
        self.assertEqual(turn_receipt["cli_turn_usage"], dict(input_tokens=15, output_tokens=25))
        self.assertEqual(
            turn_receipt["raw_output_sha256"],
            hashlib.sha256((directory / "instructions.json").read_bytes()).hexdigest(),
        )
        self.assertEqual(turn_receipt["scope"], "completed_cli_turn_before_semantic_plan_validation")
        self.assertNotIn("instruction_receipt", record)
        terminal = record["terminal"]
        self.assertEqual(self.provider.submit(self.request, self.manifest, KEY), terminal)
        self.assertEqual((self.directory / "runs").read_text().count("run"), 1)

    def test_text_only_inference_requires_all_exact_region_names(self):
        invalid = copy.deepcopy(PLAN)
        invalid["completion"]["inferred_regions"] = []
        (self.directory / "plan.json").write_text(json.dumps(invalid), encoding="utf-8")
        self.provider.submit(self.request, self.manifest, KEY)
        result = self.wait()
        self.assertEqual(result["state"], "failed")
        self.assertIn("纯文字建模须列出全部区域", result["error"])
        self.assertFalse((self.directory / "state" / KEY / "builder.stdout").exists())

    def test_character_instruction_boundary_preserves_original_plan_and_reserved_name(self):
        self.use_synthetic_calibration_runtime()
        value = copy.deepcopy(PLAN)
        value.update(character=character_defaults(), materials=[], regions=[])
        value["completion"]["inferred_regions"] = ["character"]
        (self.directory / "plan.json").write_text(json.dumps(value), encoding="utf-8")
        plan = self.provider.plan(self.request, self.manifest)
        record = dict(
            request=self.request,
            manifest=self.manifest,
            fingerprint=self.provider.fingerprint,
            heartbeat=time.time(),
            created=time.time(),
            stage="intent",
            plan=plan,
        )
        with self.provider.db() as db:
            db.execute("INSERT INTO jobs VALUES(?,?)", (KEY, json.dumps(record)))
            db.execute("INSERT INTO leases VALUES(?,?,0)", (KEY, time.time()))
        directory = self.directory / "state" / KEY
        directory.mkdir()
        instructions, receipt = self.provider._instructions(KEY, plan, directory)
        self.assertEqual(instructions, value)
        self.assertEqual(instructions["completion"]["inferred_regions"], ["character"])
        canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        self.assertEqual(receipt["instructions_sha256"], hashlib.sha256(canonical.encode()).hexdigest())
        self.assertEqual(receipt["cli_turn_usage"], dict(input_tokens=15, output_tokens=25))
        self.assertEqual(receipt["reference_images"], [])
        self.assertEqual(receipt["distinct_reference_images"], 0)
        self.assertEqual(receipt["operator_calibration"]["attachment_index"], 1)
        self.assertEqual(receipt["hidden_surface_policy"], "generated_from_text_unobserved_geometry")
        prompt = (directory / "prompt.txt").read_text(encoding="utf-8")
        self.assertIn("NO USER reference images", prompt)
        self.assertIn("For realistic characters eye_size changes eyelid aperture, not globe size", prompt)
        self.assertIn("stylized characters also scale their globes consistently", prompt)
        self.assertIn("<=0.4*span/count", prompt)
        self.assertFalse((directory / "builder.stdout").exists())

    def test_failure_and_incomplete_receipts_do_not_publish(self):
        for index, mode in enumerate(("fail", "no-output", "no-turn", "tool")):
            self.mode(mode)
            key = format(index + 1, "064x")
            self.provider.submit(self.request, self.manifest, key)
            self.assertEqual(self.wait(key)["state"], "failed")
            with self.assertRaisesRegex(ValueError, "result not available"):
                self.provider.result_manifest(key)


if __name__ == "__main__":
    unittest.main()
