"""Deterministic vision-selection and review-loop tests; no network inference."""

import base64
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mesh_vision import (
    analysis_prompt,
    complete_review,
    corrected_review_yaw,
    get_review_plan,
    review,
    review_prompt,
    review_view_definitions,
    review_yaw_correction,
    select_generation_request,
    select_retry_adjust_request,
    validate_review,
)
from test_multi_image_provider import asset, reference


def analyzed(image_id, view, kind="full_subject"):
    return dict(
        image_id=image_id,
        view=view,
        content_kind=kind,
        detail_region="face" if kind == "detail" else "",
        same_subject=True,
        observation="synthetic observation",
    )


def analysis(entries):
    return dict(
        subject=dict(
            category="humanoid",
            description="one priest",
            structure="normal humanoid proportions",
            expected_details="face and vestments",
        ),
        images=entries,
        coherent=True,
        synthesis="one subject",
    )


def detail(region, views, source="detail", goal=None):
    return dict(
        region=region,
        views=views,
        source_image_ids=[source],
        goal=goal or "compare the requested " + region,
    )


def planned_analysis(entries, details, head_gate=False):
    document = analysis(entries)
    document["review_plan"] = dict(schema_version=1, details=details, head_gate=head_gate)
    return document


ACCEPTANCE = dict(
    top_view="approximate_allowed",
    face="recognizable_identity_normal_proportions",
    animation="geometry_readiness_only_rig_unverified",
)


def head_gate(**overrides):
    result = dict(
        applicable=True,
        complete_face=True,
        neck_join_pass=True,
        identity_pass=True,
        face_proportions_pass=True,
        animation_geometry_pass=True,
        observation="complete",
    )
    if overrides.get("applicable") is False:
        result.update(identity_pass=False, face_proportions_pass=False, animation_geometry_pass=False)
    result.update(overrides)
    return result


def reviewed_document(**values):
    values.setdefault("schema_version", 2)
    values.setdefault("acceptance", copy.deepcopy(ACCEPTANCE))
    values.setdefault("head_gate", head_gate())
    values.setdefault("rendered_front_view", "front")
    return values


class MeshVisionTests(unittest.TestCase):
    def request(self, sources):
        return dict(
            node="image_to_mesh",
            version="2",
            inputs={"source": reference(sources[0])},
            parameters={"prompt": "preserve the subject"},
            context=[
                dict(artifact=reference(source), role="reference", scope="node", strength="reference")
                for source in sources[1:]
            ],
        )

    def test_dynamic_weights_ignore_collection_order_and_details(self):
        sources = [asset(name, name) for name in ("detail", "top", "left", "back", "front", "right")]
        document = analysis([
            analyzed("detail", "detail", "detail"),
            analyzed("top", "top"),
            analyzed("left", "left"),
            analyzed("back", "back"),
            analyzed("front", "front"),
            analyzed("right", "right"),
        ])
        child, selected = select_generation_request(
            self.request(sources), [dict(asset=source, label=source["id"]) for source in sources], document
        )
        self.assertEqual([item["id"] for item in selected], ["front", "left", "right", "back"])
        self.assertEqual(
            [item["payload"]["provenance"]["analyzed_view"] for item in selected],
            ["front", "left", "right", "back"],
        )
        self.assertEqual(child["parameters"]["prompt"], "")
        self.assertEqual(len(child["context"]), 3)

    def test_no_front_uses_best_single_view_instead_of_inventing_front(self):
        sources = [asset("top", "top"), asset("side", "side"), asset("face", "face")]
        document = analysis([
            analyzed("top", "top"),
            analyzed("side", "right"),
            analyzed("face", "detail", "detail"),
        ])
        child, selected = select_generation_request(
            self.request(sources), [dict(asset=source, label=source["id"]) for source in sources], document
        )
        self.assertEqual([item["id"] for item in selected], ["side"])
        self.assertEqual(child["context"], [])

    def test_retry_uses_previous_model_for_appearance_adjustment(self):
        sources = [asset("front", "front")]
        document = analysis([analyzed("front", "front")])
        previous = dict(id="previous-model", revision="c" * 64, type="mesh")
        rejected = dict(
            subject_match=True,
            proportions_pass=True,
            head_gate=head_gate(applicable=True, complete_face=True, neck_join_pass=True),
            issues=["cloth is too glossy", "gold ornament is blurred", "hairstyle is too tall"],
        )
        child, selected = select_retry_adjust_request(self.request(sources), document, previous, rejected)
        self.assertEqual(child["node"], "model_adjust")
        self.assertEqual(child["inputs"], {"source": {"id": "previous-model", "revision": "c" * 64}})
        self.assertEqual(selected, [])
        self.assertIn("Preserve its geometry", child["parameters"]["prompt"])
        self.assertIn("cloth is too glossy", child["parameters"]["prompt"])
        self.assertIn("gold ornament is blurred", child["parameters"]["prompt"])
        self.assertNotIn("hairstyle is too tall", child["parameters"]["prompt"])
        self.assertLessEqual(len(child["parameters"]["prompt"]), 1000)
        document["subject"]["description"] = "detailed subject " * 100
        document["subject"]["expected_details"] = "fine ornament " * 100
        child, _ = select_retry_adjust_request(self.request(sources), document, previous, rejected)
        self.assertLessEqual(len(child["parameters"]["prompt"]), 1000)

    def test_facial_proportion_feedback_does_not_block_appearance_retry(self):
        sources = [asset("front", "front")]
        document = analysis([analyzed("front", "front")])
        previous = dict(id="previous-model", revision="c" * 64, type="mesh")
        rejected = dict(
            subject_match=True,
            proportions_pass=True,
            head_gate=head_gate(applicable=True, complete_face=True, neck_join_pass=True),
            issues=[
                "The face does not reproduce the reference's semi-realistic facial proportions and identity.",
                "cloth is too glossy",
            ],
        )
        child, selected = select_retry_adjust_request(self.request(sources), document, previous, rejected)
        self.assertEqual(child["node"], "model_adjust")
        self.assertEqual(selected, [])
        self.assertIn("facial proportions and identity", child["parameters"]["prompt"])
        self.assertIn("cloth is too glossy", child["parameters"]["prompt"])

    def test_camera_correction_uses_structured_front_view_once(self):
        with tempfile.TemporaryDirectory(prefix="mesh-review-yaw-") as temporary:
            directory = Path(temporary)
            views = directory / "views.json"
            rejected = reviewed_document(passed=False, rendered_front_view="left")
            views.write_text('{"yaw_degrees": 0.0}', encoding="utf-8")
            self.assertEqual(review_yaw_correction(rejected), -90.0)
            self.assertEqual(corrected_review_yaw(directory, rejected), -90.0)
            rejected["rendered_front_view"] = "back"
            views.write_text('{"yaw_degrees": 90.0}', encoding="utf-8")
            self.assertEqual(corrected_review_yaw(directory, rejected), -90.0)
            rejected["rendered_front_view"] = "front"
            self.assertIsNone(review_yaw_correction(rejected))
            accepted = reviewed_document(passed=True, rendered_front_view="right")
            self.assertIsNone(review_yaw_correction(accepted))

    def test_structural_failure_never_falls_back_to_full_regeneration(self):
        sources = [asset("front", "front")]
        document = analysis([analyzed("front", "front")])
        previous = dict(id="previous-model", revision="c" * 64, type="mesh")
        cases = [
            dict(
                subject_match=False,
                proportions_pass=True,
                head_gate=head_gate(applicable=True, complete_face=True, neck_join_pass=True),
                issues=[],
            ),
            dict(
                subject_match=True,
                proportions_pass=False,
                head_gate=head_gate(applicable=True, complete_face=True, neck_join_pass=True),
                issues=[],
            ),
            dict(
                subject_match=True,
                proportions_pass=True,
                head_gate=head_gate(applicable=True, complete_face=True, neck_join_pass=False),
                issues=[],
            ),
            dict(
                subject_match=True,
                proportions_pass=True,
                head_gate=head_gate(applicable=True, complete_face=True, neck_join_pass=True),
                issues=["both arms are missing"],
            ),
        ]
        for rejected in cases:
            with (
                self.subTest(rejected=rejected),
                self.assertRaisesRegex(ValueError, "model3d_geometry_edit_unsupported"),
            ):
                select_retry_adjust_request(self.request(sources), document, previous, rejected)

    def test_review_requires_every_dimension_and_every_rendered_view(self):
        generated = [
            dict(image_id="generated-" + view, label="generated " + view, path=Path(view + ".jpg"))
            for view in ("front", "head_front", "head_three_quarter", "head_side")
        ]
        original = [dict(image_id="source", label="source", path=Path("source.jpg"))]
        document = reviewed_document(
            passed=True,
            subject_match=True,
            proportions_pass=True,
            views=[
                dict(view="generated " + view, similar=True, observation="same")
                for view in ("front", "head_front", "head_three_quarter", "head_side")
            ]
            + [dict(view="actual rear comparison", similar=True, observation="supplemental evidence")],
            details_pass=True,
            head_gate=head_gate(
                applicable=True, complete_face=True, neck_join_pass=True, observation="complete head and neck"
            ),
            issues=[],
            retry_guidance="",
        )
        provider = object()
        with patch("mesh_vision._request_json", return_value=copy.deepcopy(document)):
            accepted = review(provider, "a" * 64, analysis([]), original, generated, [], Path("unused"))
        self.assertTrue(accepted["passed"])
        document["views"][0]["similar"] = False
        document["issues"] = ["right ear mismatch"]
        with patch("mesh_vision._request_json", return_value=copy.deepcopy(document)):
            rejected = review(provider, "a" * 64, analysis([]), original, generated, [], Path("unused"))
        self.assertFalse(rejected["passed"])

    def test_incomplete_face_or_missing_neck_is_a_hard_rejection(self):
        generated = [
            dict(image_id="generated-" + view, label="generated " + view, path=Path(view + ".jpg"))
            for view in ("head_front", "head_three_quarter", "head_side")
        ]
        document = reviewed_document(
            passed=True,
            subject_match=True,
            proportions_pass=True,
            views=[
                dict(view=view, similar=True, observation="visible")
                for view in ("head_front", "head_three_quarter", "head_side")
            ],
            details_pass=True,
            head_gate=head_gate(
                applicable=True, complete_face=False, neck_join_pass=True, observation="mouth and chin are cut"
            ),
            issues=[],
            retry_guidance="",
        )
        with patch("mesh_vision._request_json", return_value=copy.deepcopy(document)):
            rejected = review(object(), "a" * 64, analysis([]), [], generated, [], Path("unused"))
        self.assertFalse(rejected["passed"])
        document["head_gate"]["complete_face"] = True
        document["head_gate"]["neck_join_pass"] = False
        with patch("mesh_vision._request_json", return_value=copy.deepcopy(document)):
            rejected = review(object(), "a" * 64, analysis([]), [], generated, [], Path("unused"))
        self.assertFalse(rejected["passed"])

    def test_non_humanoid_does_not_need_head_views(self):
        generated = [dict(image_id="generated-front", label="generated front", path=Path("front.jpg"))]
        document = reviewed_document(
            passed=True,
            subject_match=True,
            proportions_pass=True,
            views=[dict(view="front", similar=True, observation="same vase")],
            details_pass=True,
            head_gate=head_gate(
                applicable=False, complete_face=False, neck_join_pass=False, observation="not a person"
            ),
            issues=[],
            retry_guidance="",
        )
        subject = analysis([])
        subject["subject"]["category"] = "ceramic vase"
        with patch("mesh_vision._request_json", return_value=copy.deepcopy(document)):
            accepted = review(object(), "a" * 64, subject, [], generated, [], Path("unused"))
        self.assertTrue(accepted["passed"])

    def test_comparison_suffixes_do_not_turn_a_valid_review_into_protocol_failure(self):
        generated = [
            dict(image_id="generated-front", label="generated front", path=Path("front.jpg")),
            dict(image_id="generated-right", label="generated right", path=Path("right.jpg")),
        ]
        document = reviewed_document(
            passed=True,
            subject_match=True,
            proportions_pass=True,
            views=[
                dict(view="generated-front compared with source side profiles", similar=True, observation="same"),
                dict(view="generated-right compared with source front", similar=True, observation="same"),
            ],
            details_pass=True,
            head_gate=head_gate(
                applicable=False, complete_face=False, neck_join_pass=False, observation="not applicable"
            ),
            issues=[],
            retry_guidance="",
        )
        result = validate_review(document, generated, False)
        self.assertTrue(result["passed"])
        self.assertEqual([item["view"] for item in result["views"]], ["front", "right"])
        incomplete = copy.deepcopy(document)
        incomplete["views"].pop()
        rejected = validate_review(incomplete, generated, False)
        self.assertFalse(rejected["passed"])
        self.assertTrue(rejected["review_incomplete"])
        self.assertIn("Missing required rendered view: right", rejected["issues"])

    def test_incomplete_report_rereviews_only_missing_views_on_the_same_model(self):
        generated = [
            dict(image_id="generated-" + view, label="generated " + view, path=Path(view + ".jpg"))
            for view in ("front", "head_front", "head_three_quarter", "head_side")
        ]
        missing = ["head_front", "head_three_quarter", "head_side"]
        first = reviewed_document(
            passed=False,
            review_incomplete=True,
            subject_match=True,
            proportions_pass=True,
            details_pass=True,
            views=[dict(view="front", similar=True, observation="front")],
            issues=["Missing required rendered view: " + view for view in missing],
            retry_guidance="",
        )
        second = reviewed_document(
            passed=True,
            subject_match=True,
            proportions_pass=True,
            details_pass=True,
            views=[dict(view=view, similar=True, observation="complete " + view) for view in missing],
            issues=[],
            retry_guidance="",
        )
        with patch("mesh_vision.review", side_effect=[first, second]) as review_call:
            result = complete_review(object(), "a" * 64, analysis([]), [], generated, [], Path("review-request"))
        self.assertTrue(result["passed"])
        self.assertEqual(review_call.call_count, 2)
        self.assertIs(review_call.call_args_list[0].args[4], generated)
        self.assertEqual(review_call.call_args_list[1].args[4], generated[1:])
        self.assertTrue(review_call.call_args_list[1].kwargs["partial"])
        for view in missing:
            self.assertIn("Missing required rendered view: " + view, review_call.call_args_list[1].args[5])
        self.assertEqual(review_call.call_args_list[1].args[6].name, "review-request-incomplete-retry")

    def test_complementary_reviews_complete_evidence_without_another_request(self):
        generated = [
            dict(image_id="generated-" + view, label="generated " + view, path=Path(view + ".png"))
            for view in ("front", "top", "head_front", "head_three_quarter", "head_side")
        ]
        first = reviewed_document(
            passed=False,
            review_incomplete=True,
            subject_match=True,
            proportions_pass=True,
            details_pass=True,
            views=[
                dict(view="front", similar=True, observation="front"),
                dict(view="top", similar=True, observation="approximate top"),
            ],
            issues=[
                "Missing required rendered view: head_front",
                "Missing required rendered view: head_three_quarter",
                "Missing required rendered view: head_side",
            ],
            retry_guidance="",
        )
        second = reviewed_document(
            passed=False,
            review_incomplete=True,
            subject_match=True,
            proportions_pass=True,
            details_pass=True,
            views=[
                dict(view=view, similar=True, observation=view)
                for view in ("head_front", "head_three_quarter", "head_side")
            ],
            issues=["Missing required rendered view: top"],
            retry_guidance="",
        )
        with patch("mesh_vision.review", side_effect=[first, second]) as review_call:
            result = complete_review(object(), "a" * 64, analysis([]), [], generated, [], Path("review-request"))
        self.assertTrue(result["passed"])
        self.assertEqual(result["evidence_recovery"], "merged_incomplete_reviews_same_model")
        self.assertEqual(review_call.call_count, 2)
        self.assertEqual([item["view"] for item in result["views"]], [item["image_id"][10:] for item in generated])
        from extensions import canonical

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def save(directory, document):
                directory.mkdir(parents=True)
                (directory / "api-plan.json").write_text(canonical(document), encoding="utf-8")
                (directory / "api-request.json").write_bytes(b"{}")
                receipt = dict(
                    request_sha256=hashlib.sha256(b"{}").hexdigest(),
                    instructions_sha256=hashlib.sha256(canonical(document).encode()).hexdigest(),
                )
                (directory / "api-receipt.json").write_text(canonical(receipt), encoding="utf-8")

            save(root / "review-request", first)
            save(root / "review-request-incomplete-retry", second)
            with patch("mesh_vision.review", side_effect=AssertionError("unexpected new API request")) as request:
                recovered = complete_review(
                    object(), "a" * 64, analysis([]), [], generated, [], root / "review-request"
                )
            self.assertTrue(recovered["passed"])
            self.assertEqual(request.call_count, 0)
        conflict = copy.deepcopy(second)
        conflict["views"].append(dict(view="top", similar=False, observation="contradictory top"))
        with patch("mesh_vision.review", side_effect=[first, conflict]):
            with self.assertRaisesRegex(ValueError, "vision_output_invalid"):
                complete_review(object(), "a" * 64, analysis([]), [], generated, [], Path("review-request"))

    def test_legacy_incomplete_retry_does_not_block_targeted_recovery(self):
        generated = [
            dict(image_id="generated-" + view, label="generated " + view, path=Path(view + ".png"))
            for view in ("front", "head_front", "head_three_quarter", "head_side")
        ]
        first = reviewed_document(
            passed=False,
            review_incomplete=True,
            subject_match=True,
            proportions_pass=True,
            details_pass=True,
            views=[dict(view="front", similar=True, observation="front")],
            issues=["Missing required rendered view: head_front"],
            retry_guidance="",
        )
        targeted = reviewed_document(
            passed=True,
            subject_match=True,
            proportions_pass=True,
            details_pass=True,
            views=[
                dict(view=view, similar=True, observation="complete " + view)
                for view in ("head_front", "head_three_quarter", "head_side")
            ],
            issues=[],
            retry_guidance="",
        )
        from extensions import canonical

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def save(directory, document):
                directory.mkdir(parents=True)
                (directory / "api-plan.json").write_text(canonical(document), encoding="utf-8")
                (directory / "api-request.json").write_bytes(b"{}")
                receipt = dict(
                    request_sha256=hashlib.sha256(b"{}").hexdigest(),
                    instructions_sha256=hashlib.sha256(canonical(document).encode()).hexdigest(),
                )
                (directory / "api-receipt.json").write_text(canonical(receipt), encoding="utf-8")

            save(root / "review-request", first)
            save(root / "review-request-incomplete-retry", first)
            with patch("mesh_vision.review", return_value=targeted) as request:
                result = complete_review(object(), "a" * 64, analysis([]), [], generated, [], root / "review-request")
            self.assertTrue(result["passed"])
            self.assertEqual(request.call_count, 1)
            self.assertEqual(request.call_args.args[4], generated[1:])
            self.assertTrue(request.call_args.kwargs["partial"])
            self.assertEqual(request.call_args.args[6].name, "review-request-incomplete-targeted-retry")

    def test_v2_allows_approximate_top_but_requires_face_and_animation_geometry(self):
        generated = [
            dict(image_id="generated-" + view, label="generated " + view, path=Path(view + ".png"))
            for view in ("front", "top", "head_front", "head_three_quarter", "head_side")
        ]
        document = reviewed_document(
            passed=True,
            subject_match=True,
            proportions_pass=True,
            views=[
                dict(view=view, similar=True, observation="same layout")
                for view in ("front", "head_front", "head_three_quarter", "head_side")
            ]
            + [dict(view="top", similar=True, observation="Similar layout; a slightly different elevation is allowed")],
            details_pass=True,
            issues=[],
            retry_guidance="",
        )
        accepted = validate_review(document, generated, True)
        self.assertTrue(accepted["passed"])
        for field in ("identity_pass", "face_proportions_pass", "animation_geometry_pass"):
            rejected = copy.deepcopy(accepted)
            rejected["head_gate"][field] = False
            with self.subTest(field=field):
                self.assertFalse(validate_review(rejected, generated, True)["passed"])
        legacy = copy.deepcopy(accepted)
        legacy.pop("schema_version")
        with patch("mesh_vision.review", return_value=accepted) as review_call:
            result = complete_review(
                object(), "a" * 64, analysis([]), [], generated, [], Path("new-review"), document=legacy
            )
        self.assertIs(result, accepted)
        self.assertIs(review_call.call_args.args[4], generated)
        prompt = review_prompt(analysis([]), [])
        self.assertIn("not a 1:1", prompt)
        self.assertIn("elevation angle differs moderately", prompt)
        self.assertIn("never claim that a skeleton", prompt)

    def test_hand_detail_plan_drives_render_and_review_without_head_views(self):
        document = planned_analysis(
            [analyzed("hand", "detail", "detail")],
            [
                detail("hand_left", ["front", "back"], "hand", "compare fingers and palm"),
                detail("hand_right", ["front"], "hand", "compare fingers and dorsal surface"),
            ],
        )
        plan = get_review_plan(document)
        definitions = review_view_definitions(plan)
        names = [item["view"] for item in definitions]
        self.assertEqual(names[:5], ["front", "right", "back", "left", "top"])
        self.assertEqual(names[5:], ["hand_left_front", "hand_left_back", "hand_right_front"])
        self.assertFalse(any(name.startswith("head_") for name in names))
        self.assertFalse(plan["head_gate"])
        generated = [
            dict(image_id="generated-" + name, label="generated " + name, path=Path(name + ".png")) for name in names
        ]
        accepted = reviewed_document(
            passed=True,
            subject_match=True,
            proportions_pass=True,
            details_pass=True,
            head_gate=head_gate(applicable=False, complete_face=False, neck_join_pass=False),
            views=[dict(view=name, similar=True, observation="matching hand evidence") for name in names],
            issues=[],
            retry_guidance="",
        )
        with patch("mesh_vision._request_json", return_value=copy.deepcopy(accepted)):
            result = review(object(), "a" * 64, document, [], generated, [], Path("unused"))
        self.assertTrue(result["passed"])
        prompt = review_prompt(document, [])
        self.assertIn("compare fingers and palm", prompt)
        self.assertIn("Never invent a missing reference view", prompt)

    def test_armor_and_object_plans_use_supported_regions_not_character_template(self):
        armor = planned_analysis(
            [analyzed("armor", "detail", "detail")],
            [detail("upper_body", ["front", "three_quarter"], "armor", "compare chest armor relief")],
        )
        names = [item["view"] for item in review_view_definitions(get_review_plan(armor))]
        self.assertEqual(names[5:], ["detail_upper_front", "detail_upper_three_quarter"])
        self.assertNotIn("head_front", names)
        vase = planned_analysis(
            [analyzed("vase", "detail", "detail")],
            [detail("object_detail", ["front", "side"], "vase", "compare engraved ornament")],
        )
        vase["subject"]["category"] = "ceramic vase"
        names = [item["view"] for item in review_view_definitions(get_review_plan(vase))]
        self.assertEqual(names[5:], ["object_detail_front", "object_detail_side"])
        self.assertFalse(get_review_plan(vase)["head_gate"])

    def test_head_gate_requires_the_complete_dynamic_head_capability(self):
        document = planned_analysis(
            [analyzed("face", "detail", "detail")],
            [detail("head", ["front"], "face")],
            head_gate=True,
        )
        with self.assertRaisesRegex(ValueError, "vision_output_invalid"):
            get_review_plan(document)
        document["review_plan"]["details"][0]["views"] = ["front", "three_quarter", "side"]
        self.assertTrue(get_review_plan(document)["head_gate"])
        document["review_plan"]["details"][0]["source_image_ids"] = ["unknown"]
        with self.assertRaisesRegex(ValueError, "vision_output_invalid"):
            get_review_plan(document)

    def test_analysis_goal_and_review_recovery_share_the_same_dynamic_contract(self):
        prompt = analysis_prompt(self.request([asset("hand", "hand")]), [dict(image_id="hand", label="source")])
        self.assertIn("review_plan", prompt)
        self.assertIn("hand_left or hand_right for hand goals", prompt)
        self.assertIn("Do not add head views", prompt)
        recovery = review_prompt(
            analysis([]),
            [],
            required_views=["hand_left_front"],
            recovery_context={"rendered_front_view": "front"},
        )
        self.assertIn('["hand_left_front"]', recovery)
        self.assertIn("targeted evidence recovery", recovery)
        self.assertIn("do not invent entries for unattached views", recovery)


class ReviewLoopTests(unittest.TestCase):
    def test_rejected_first_model_is_regenerated_before_success(self):
        from kimi_provider import KimiNativeDirectProvider

        with tempfile.TemporaryDirectory(prefix="mesh-review-loop-") as temporary:
            root = Path(temporary)
            tool = root / "model3d_generation_tool.py"
            tool.write_text("synthetic")
            godot = root / "godot"
            godot.write_text("synthetic")
            script = root / "mesh_review.gd"
            script.write_text("synthetic")
            provider = KimiNativeDirectProvider(
                dict(
                    tool_path=str(tool),
                    pythonw_path=str(Path(__file__)),
                    storage=str(root / "state"),
                    model="v3.1",
                    planner=dict(endpoint="https://api.kimi.com/coding/v1", model="k3.1-pro", key_env="KIMI_API_KEY"),
                    review_godot_path=str(godot),
                    review_script_path=str(script),
                )
            )
            key = "b" * 64
            source = asset("source", "source")
            request = dict(
                node="image_to_mesh",
                version="2",
                inputs={"source": reference(source)},
                parameters={"prompt": "one character"},
                context=[],
            )
            record = dict(
                request=request,
                manifest=dict(schema_version=1, artifacts=[source]),
                fingerprint=provider.fingerprint,
                created=1,
                heartbeat=1,
                stage="queued",
                reviewed=True,
            )
            from extensions import canonical

            with provider.db() as db:
                db.execute("INSERT INTO jobs VALUES (?,?)", (key, canonical(record)))
            document = analysis([analyzed("source", "front")])
            entries = [dict(image_id="source", label="source", path=root / "source.jpg")]
            selected = copy.deepcopy(source)
            selected["payload"]["provenance"] = dict(analyzed_view="front", generation_weight=100)
            child = dict(request, version="1", parameters={"prompt": ""})
            data = b"synthetic-glb"
            model = dict(
                id="model",
                revision=hashlib.sha256(data).hexdigest(),
                type="mesh",
                payload=dict(
                    content_base64=base64.b64encode(data).decode(),
                    content_sha256=hashlib.sha256(data).hexdigest(),
                    extension=".glb",
                    bytes=len(data),
                    provenance=dict(task_id="synthetic-task"),
                ),
            )
            rejected = dict(
                passed=False,
                subject_match=True,
                proportions_pass=True,
                views=[dict(view="front", similar=True, observation="same shape")],
                details_pass=False,
                head_gate=head_gate(applicable=True, complete_face=True, neck_join_pass=True, observation="complete"),
                issues=["cloth is too glossy"],
                retry_guidance="adjust the material",
            )
            accepted = dict(
                passed=True,
                subject_match=True,
                proportions_pass=True,
                views=[dict(view="front", similar=True, observation="match")],
                details_pass=True,
                head_gate=head_gate(applicable=True, complete_face=True, neck_join_pass=True, observation="complete"),
                issues=[],
                retry_guidance="",
            )
            with (
                patch("mesh_vision.analyze", return_value=dict(document=document, entries=entries)),
                patch("mesh_vision.select_generation_request", return_value=(child, [selected])),
                patch("mesh_vision.render_review_views", return_value=[]) as render_call,
                patch("mesh_vision.review", side_effect=[rejected, accepted]) as review_call,
                patch("mesh_vision.attach_head_review", side_effect=lambda model, _review, _analysis: model),
                patch.object(provider, "_cli", return_value=copy.deepcopy(model)) as cli,
                patch.object(
                    provider,
                    "plan",
                    side_effect=[dict(sources=[selected]), dict(sources=[selected], operation="texture_3d_model")],
                ),
            ):
                provider._work_reviewed(key)
            self.assertEqual(cli.call_count, 2)
            self.assertEqual(review_call.call_count, 2)
            self.assertEqual(render_call.call_args_list[0].args[2].name, "generated.glb")
            self.assertEqual(render_call.call_args_list[1].args[2].name, "adjusted.glb")
            terminal = provider.read(key)["terminal"]
            self.assertEqual(terminal["state"], "succeeded")
            self.assertEqual(len(provider.read(key)["review_attempts"]), 2)
            attempts = provider.read(key)["review_attempts"]
            self.assertEqual(attempts[0]["iteration_mode"], "initial_reference_generation")
            self.assertEqual(attempts[1]["iteration_mode"], "incremental_model_adjust")
            self.assertEqual(attempts[1]["parent_model_sha256"], model["revision"])
            provenance = provider.result_manifest(key)["artifacts"][-1]["payload"]["provenance"]
            self.assertEqual(provenance["review_policy"], "reference_driven_dynamic_review_plan_v1")
            self.assertEqual(provenance["visual_review_plan"], get_review_plan(document))

    def test_camera_mismatch_rereviews_same_model_without_model_adjust(self):
        from kimi_provider import KimiNativeDirectProvider

        with tempfile.TemporaryDirectory(prefix="mesh-review-orientation-loop-") as temporary:
            root = Path(temporary)
            tool = root / "model3d_generation_tool.py"
            tool.write_text("synthetic")
            godot = root / "godot"
            godot.write_text("synthetic")
            script = root / "mesh_review.gd"
            script.write_text("synthetic")
            provider = KimiNativeDirectProvider(
                dict(
                    tool_path=str(tool),
                    pythonw_path=str(Path(__file__)),
                    storage=str(root / "state"),
                    model="v3.1",
                    planner=dict(endpoint="https://api.kimi.com/coding/v1", model="k3.1-pro", key_env="KIMI_API_KEY"),
                    review_godot_path=str(godot),
                    review_script_path=str(script),
                )
            )
            key = "c" * 64
            source = asset("source", "source")
            request = dict(
                node="image_to_mesh",
                version="2",
                inputs={"source": reference(source)},
                parameters={"prompt": "one character"},
                context=[],
            )
            record = dict(
                request=request,
                manifest=dict(schema_version=1, artifacts=[source]),
                fingerprint=provider.fingerprint,
                created=1,
                heartbeat=1,
                stage="queued",
                reviewed=True,
            )
            from extensions import canonical

            with provider.db() as db:
                db.execute("INSERT INTO jobs VALUES (?,?)", (key, canonical(record)))
            document = analysis([analyzed("source", "front")])
            entries = [dict(image_id="source", label="source", path=root / "source.jpg")]
            selected = copy.deepcopy(source)
            selected["payload"]["provenance"] = dict(analyzed_view="front", generation_weight=100)
            child = dict(request, version="1", parameters={"prompt": ""})
            data = b"synthetic-glb"
            model = dict(
                id="model",
                revision=hashlib.sha256(data).hexdigest(),
                type="mesh",
                payload=dict(
                    content_base64=base64.b64encode(data).decode(),
                    content_sha256=hashlib.sha256(data).hexdigest(),
                    extension=".glb",
                    bytes=len(data),
                    provenance=dict(task_id="synthetic-task"),
                ),
            )
            rejected = reviewed_document(
                passed=False,
                subject_match=True,
                proportions_pass=True,
                views=[dict(view="front", similar=False, observation="front is a profile")],
                details_pass=False,
                head_gate=head_gate(
                    applicable=True,
                    complete_face=False,
                    identity_pass=False,
                    observation="head views show side and rear directions",
                ),
                issues=["The generated camera labels are rotated"],
                retry_guidance="correct the render cameras",
                rendered_front_view="left",
            )
            accepted = reviewed_document(
                passed=True,
                subject_match=True,
                proportions_pass=True,
                views=[dict(view="front", similar=True, observation="correct front")],
                details_pass=True,
                head_gate=head_gate(applicable=True, observation="complete"),
                issues=[],
                retry_guidance="",
                rendered_front_view="front",
            )

            def initial_render(_provider, _key, model_path, directory, **_kwargs):
                Path(model_path).write_bytes(data)
                directory.mkdir(parents=True)
                (directory / "views.json").write_text('{"yaw_degrees": 0.0}', encoding="utf-8")
                return ["original evidence"]

            with (
                patch("mesh_vision.analyze", return_value=dict(document=document, entries=entries)),
                patch("mesh_vision.select_generation_request", return_value=(child, [selected])),
                patch("mesh_vision.render_review_views", side_effect=initial_render),
                patch(
                    "mesh_vision.render_corrected_review_views", return_value=["corrected evidence"]
                ) as corrected_render,
                patch("mesh_vision.review", side_effect=[rejected, accepted]) as review_call,
                patch("mesh_vision.attach_head_review", side_effect=lambda model, _review, _analysis: model),
                patch.object(provider, "_cli", return_value=copy.deepcopy(model)) as cli,
                patch.object(provider, "plan", return_value=dict(sources=[selected])),
            ):
                provider._work_reviewed(key)
            self.assertEqual(cli.call_count, 1)
            self.assertEqual(review_call.call_count, 2)
            self.assertEqual(corrected_render.call_count, 1)
            self.assertEqual(corrected_render.call_args.args[2].name, "generated.glb")
            self.assertEqual(corrected_render.call_args.args[4], -90.0)
            self.assertEqual(review_call.call_args_list[1].args[4], ["corrected evidence"])
            terminal = provider.read(key)["terminal"]
            self.assertEqual(terminal["state"], "succeeded")
            attempts = provider.read(key)["review_attempts"]
            self.assertEqual(len(attempts), 1)
            self.assertEqual(attempts[0]["iteration_mode"], "initial_reference_generation")
            recovery = attempts[0]["review"]["orientation_recovery"]
            self.assertEqual(recovery["yaw_degrees"], -90.0)
            self.assertEqual(recovery["model_sha256"], model["revision"])
            self.assertFalse(recovery["geometry_changed"])

    def test_capability_boundary_delivers_last_model_without_passing_review(self):
        from kimi_provider import KimiNativeDirectProvider
        from test_kimi_provider import triangle_glb

        with tempfile.TemporaryDirectory(prefix="mesh-capability-delivery-") as temporary:
            root = Path(temporary)
            tool = root / "model3d_generation_tool.py"
            tool.write_text("synthetic")
            godot = root / "godot"
            godot.write_text("synthetic")
            script = root / "mesh_review.gd"
            script.write_text("synthetic")
            provider = KimiNativeDirectProvider(
                dict(
                    tool_path=str(tool),
                    pythonw_path=str(Path(__file__)),
                    storage=str(root / "state"),
                    model="v3.1",
                    planner=dict(endpoint="https://api.kimi.com/coding/v1", model="k3.1-pro", key_env="KIMI_API_KEY"),
                    review_godot_path=str(godot),
                    review_script_path=str(script),
                )
            )
            key = "d" * 64
            source = asset("source", "source")
            request = dict(
                node="image_to_mesh",
                version="2",
                inputs={"source": reference(source)},
                parameters={"prompt": "one character"},
                context=[],
            )
            record = dict(
                request=request,
                manifest=dict(schema_version=1, artifacts=[source]),
                fingerprint=provider.fingerprint,
                created=1,
                heartbeat=1,
                stage="queued",
                reviewed=True,
            )
            from extensions import canonical

            with provider.db() as db:
                db.execute("INSERT INTO jobs VALUES (?,?)", (key, canonical(record)))
            document = analysis([analyzed("source", "front")])
            entries = [dict(image_id="source", label="source", path=root / "source.jpg")]
            selected = copy.deepcopy(source)
            child = dict(request, version="1", parameters={"prompt": ""})
            data = triangle_glb()
            model = dict(
                id="model",
                revision=hashlib.sha256(data).hexdigest(),
                type="mesh",
                payload=dict(
                    content_base64=base64.b64encode(data).decode(),
                    content_sha256=hashlib.sha256(data).hexdigest(),
                    extension=".glb",
                    bytes=len(data),
                    provenance=dict(task_id="synthetic-task"),
                ),
            )
            rejected = reviewed_document(
                passed=False,
                subject_match=True,
                proportions_pass=False,
                views=[dict(view="front", similar=False, observation="wrong body proportions")],
                details_pass=False,
                head_gate=head_gate(applicable=True, observation="complete head"),
                issues=["Body proportions depart from the reference"],
                retry_guidance="geometry correction is unsupported",
                rendered_front_view="front",
            )

            def initial_render(_provider, _key, model_path, directory, **_kwargs):
                Path(model_path).write_bytes(data)
                directory.mkdir(parents=True)
                (directory / "views.json").write_text('{"yaw_degrees": 0.0}', encoding="utf-8")
                return ["original evidence"]

            with (
                patch("mesh_vision.analyze", return_value=dict(document=document, entries=entries)),
                patch("mesh_vision.select_generation_request", return_value=(child, [selected])),
                patch("mesh_vision.render_review_views", side_effect=initial_render),
                patch("mesh_vision.review", return_value=rejected) as review_call,
                patch.object(provider, "_cli", return_value=copy.deepcopy(model)) as cli,
                patch.object(provider, "plan", return_value=dict(sources=[selected])),
            ):
                provider._work_reviewed(key)
            self.assertEqual(cli.call_count, 1)
            self.assertEqual(review_call.call_count, 1)
            terminal = provider.read(key)["terminal"]
            self.assertEqual(terminal["state"], "succeeded")
            self.assertIsNone(terminal["error"])
            record = provider.read(key)
            self.assertFalse(record["review_attempts"][-1]["review"]["passed"])
            delivered = provider.result_manifest(key)["artifacts"][-1]
            provenance = delivered["payload"]["provenance"]
            self.assertTrue(provenance["capability_limited"])
            self.assertFalse(provenance["visual_review_passed"])
            self.assertEqual(provenance["geometry_sha256"], model["revision"])
            self.assertEqual(provenance["unresolved_issues"], rejected["issues"])
            self.assertNotEqual(delivered["revision"], model["revision"])


if __name__ == "__main__":
    unittest.main()
