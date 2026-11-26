"""Cross-provider image collections; all inference and board rendering are faked."""

import base64
import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from contracts import validate
from extensions import NodeRegistry, canonical, validate_invocation, validate_outputs
from multi_image_provider import (
    MultiImageProvider,
    automatic_output_specifications,
    output_specifications,
    primary_prompt,
    register_images,
)


def asset(name, body):
    data = body.encode("utf-8")
    sha = hashlib.sha256(data).hexdigest()
    return dict(
        id=name,
        revision=sha,
        type="image",
        payload=dict(
            content_base64=base64.b64encode(data).decode(), content_sha256=sha, extension=".png", bytes=len(data)
        ),
    )


def reference(value):
    return {key: value[key] for key in ("id", "revision")}


class FakeImageProvider:
    def __init__(self, provider_id):
        self.provider_id = provider_id
        self.jobs = {}
        self.requests = []
        self.submissions = 0
        self.polls = 0

    def describe(self):
        return dict(
            id=self.provider_id,
            version="1",
            model="local deterministic test provider",
            model_version="fixture-v1",
            capabilities=["text_to_image", "image_to_image", "image_to_mesh", "text_to_mesh"],
            context_types=["text", "image"],
            available=True,
        )

    def read(self, key):
        if key not in self.jobs:
            raise ValueError("unknown local job")
        return copy.deepcopy(self.jobs[key])

    def submit(self, request, manifest, key):
        if key in self.jobs:
            return self.poll(key)
        registry = NodeRegistry()
        register_images(registry)
        validate_invocation(registry, request, manifest, self.describe())
        self.submissions += 1
        self.requests.append(copy.deepcopy(request))
        self.jobs[key] = dict(request=copy.deepcopy(request), manifest=copy.deepcopy(manifest), receipt=None)
        return dict(job_id=key, state="queued", outputs={}, error=None)

    def poll(self, key):
        job = self.jobs[key]
        if job["receipt"] is not None:
            return job["receipt"]
        self.polls += 1
        image = asset("generated-" + key, job["request"]["parameters"]["prompt"] + key)
        image["payload"]["provenance"] = dict(provider=self.provider_id)
        job["image"] = image
        ref = reference(image)
        job["receipt"] = dict(job_id=key, state="succeeded", outputs={"result": ref}, error=None)
        return job["receipt"]

    def lookup(self, key):
        return self.poll(key)

    def result_manifest(self, key):
        job = self.jobs[key]
        return dict(
            schema_version=1,
            artifacts=copy.deepcopy(job["manifest"]["artifacts"]) + [copy.deepcopy(job["image"])],
        )

    def cancel(self, key):
        self.jobs[key]["receipt"] = dict(job_id=key, state="cancelled", outputs={}, error=None)
        return self.jobs[key]["receipt"]


class MultiImageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="multi-image-test-")
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.sources = [asset("front", "front-pixels"), asset("side", "side-pixels")]
        self.manifest = dict(schema_version=1, artifacts=copy.deepcopy(self.sources))
        self.request = dict(
            node="image_to_image",
            version="3",
            inputs={"source": reference(self.sources[0])},
            parameters={"prompt": "same person", "output_count": 2, "output_labels": ["front", "three-quarter"]},
            context=[dict(artifact=reference(self.sources[1]), role="reference", scope="node", strength="reference")],
        )

    def adapter(self, inner):
        return MultiImageProvider(inner, self.root / "state")

    def board(self, sources, directory, config):
        result = asset("board", "|".join(source["asset"]["id"] + ":" + source["label"] for source in sources))
        result["payload"]["provenance"] = dict(
            adaptation="labelled_multi_source_reference_board",
            sources=[dict(source_sha256=source["asset"]["revision"], label=source["label"]) for source in sources],
            board_sha256=result["revision"],
        )
        return result

    def test_comfy_and_codex_receive_all_sources_as_one_labelled_board(self):
        for provider_id in ("comfy", "codex"):
            with self.subTest(provider=provider_id):
                inner = FakeImageProvider(provider_id)
                provider = self.adapter(inner)
                key = ("a" if provider_id == "comfy" else "1") * 64
                with patch("multi_image_provider.make_reference_board", side_effect=self.board) as board:
                    receipt = provider.submit(self.request, self.manifest, key)
                    receipt = provider.poll(receipt["job_id"])
                self.assertEqual(receipt["state"], "succeeded")
                self.assertEqual(inner.submissions, 2)
                self.assertEqual(board.call_count, 1)
                self.assertEqual([source["asset"]["id"] for source in board.call_args.args[0]], ["front", "side"])
                for request in inner.requests:
                    self.assertEqual(request["inputs"]["source"]["id"], "board")
                    self.assertFalse(any("artifact" in item for item in request["context"]))
                manifest = provider.result_manifest(receipt["job_id"])
                self.assertEqual(validate(manifest), [])
                collection = next(item for item in manifest["artifacts"] if item["type"] == "image_set")
                self.assertEqual([item["label"] for item in collection["payload"]["items"]], ["front", "three-quarter"])
                provenance = collection["payload"]["provenance"]
                self.assertEqual(provenance["adaptation"], "labelled_multi_source_reference_board")
                self.assertEqual(
                    [item["source_sha256"] for item in provenance["reference_board"]["sources"]],
                    [source["revision"] for source in self.sources],
                )
                self.assertEqual(provenance["ordered_sources"], provider.read(key)["sources"])
                self.assertEqual(set(receipt["outputs"]), {"image_set"})
                self.assertEqual(receipt["outputs"]["image_set"], reference(collection))
                registry = NodeRegistry()
                register_images(registry)
                validate_outputs(registry, "image_to_image", "3", receipt["outputs"], manifest)
                self.assertEqual(provider.submit(self.request, self.manifest, key)["state"], "succeeded")
                self.assertEqual(inner.submissions, 2)

    def test_native_receives_ordered_references_and_two_independent_prompts(self):
        inner = FakeImageProvider("kimi_work_image")
        provider = self.adapter(inner)
        receipt = provider.submit(self.request, self.manifest, "b" * 64)
        receipt = provider.poll(receipt["job_id"])
        self.assertEqual(receipt["state"], "succeeded")
        for request in inner.requests:
            self.assertEqual(request["inputs"]["source"], reference(self.sources[0]))
            references = [item["artifact"] for item in request["context"] if "artifact" in item]
            self.assertEqual(references, [reference(self.sources[1])])
            self.assertIn("exactly one independent image", request["parameters"]["prompt"])
        self.assertNotEqual(inner.requests[0]["parameters"]["prompt"], inner.requests[1]["parameters"]["prompt"])
        collection = next(
            item for item in provider.result_manifest(receipt["job_id"])["artifacts"] if item["type"] == "image_set"
        )
        self.assertEqual(collection["payload"]["provenance"]["adaptation"], "ordered_native_multi_reference")

    def test_text_to_image_explicit_count_and_missing_count_validation(self):
        inner = FakeImageProvider("comfy")
        provider = self.adapter(inner)
        request = copy.deepcopy(self.request)
        request.update(node="text_to_image", inputs={}, context=[], parameters={"prompt": "a prop", "output_count": 2})
        receipt = provider.poll(provider.submit(request, {"schema_version": 1, "artifacts": []}, "c" * 64)["job_id"])
        self.assertEqual(receipt["state"], "succeeded")
        self.assertEqual(inner.submissions, 2)
        with self.assertRaisesRegex(ValueError, "invalid_image_batch"):
            output_specifications({"output_count": 0})
        with self.assertRaisesRegex(ValueError, "invalid_image_batch"):
            output_specifications({"output_count": 2, "output_labels": ["same", "same"]})

    def test_partial_failure_keeps_receipts_and_never_resubmits(self):
        inner = FakeImageProvider("comfy")

        def fail_second(request, manifest, key):
            result = FakeImageProvider.submit(inner, request, manifest, key)
            if len(inner.requests) == 2:
                inner.jobs[key]["receipt"] = dict(job_id=key, state="failed", outputs={}, error="fixture failure")
                return inner.jobs[key]["receipt"]
            return result

        with (
            patch.object(inner, "submit", side_effect=fail_second),
            patch("multi_image_provider.make_reference_board", side_effect=self.board),
        ):
            provider = self.adapter(inner)
            receipt = provider.submit(self.request, self.manifest, "d" * 64)
        self.assertEqual(receipt["state"], "failed")
        children = provider.read("d" * 64)["children"]
        self.assertEqual(children[0]["receipt"]["state"], "succeeded")
        self.assertEqual(children[1]["receipt"]["state"], "failed")
        self.assertEqual(provider.poll("d" * 64)["state"], "failed")
        self.assertEqual(inner.submissions, 2)

    def test_restart_restores_child_receipts_without_new_submission(self):
        inner = FakeImageProvider("kimi_work_image")
        provider = self.adapter(inner)
        key = "e" * 64
        receipt = provider.poll(provider.submit(self.request, self.manifest, key)["job_id"])
        self.assertEqual(receipt["state"], "succeeded")
        restored = self.adapter(inner)
        self.assertEqual(restored.submit(self.request, self.manifest, key), receipt)
        self.assertEqual(restored.result_manifest(key), provider.result_manifest(key))
        self.assertEqual(inner.submissions, 2)

    def test_collection_source_expands_all_members(self):
        first = FakeImageProvider("kimi_work_image")
        provider = self.adapter(first)
        key = "f" * 64
        receipt = provider.poll(provider.submit(self.request, self.manifest, key)["job_id"])
        generated = provider.result_manifest(receipt["job_id"])
        collection = next(item for item in generated["artifacts"] if item["type"] == "image_set")
        second = FakeImageProvider("kimi_work_image")
        provider = self.adapter(second)
        request = copy.deepcopy(self.request)
        request["inputs"]["source"] = reference(collection)
        request["context"] = []
        request["parameters"].update(output_count=1, output_labels=[])
        receipt = provider.poll(provider.submit(request, generated, "0" * 64)["job_id"])
        self.assertEqual(receipt["state"], "succeeded")
        references = [second.requests[0]["inputs"]["source"]] + [
            item["artifact"] for item in second.requests[0]["context"] if "artifact" in item
        ]
        self.assertEqual(references, [item["artifact"] for item in collection["payload"]["items"]])

    def test_all_mesh_provider_routes_receive_the_multi_input_adapter(self):
        from generation_service import adapt_image_providers

        for name in ("kimi_native", "kimi_native_1", "api-modeling", "api-sculpt", "local_mesh", "comfy"):
            with self.subTest(name=name):
                inner = FakeImageProvider("kimi_native")
                providers = adapt_image_providers(
                    {name: inner}, self.root / "host.sqlite", {"enabled": True, "board_config": {}}
                )
                self.assertIsInstance(providers[name], MultiImageProvider)
                self.assertIs(providers[name].inner, inner)

    def test_mesh_accepts_single_image_and_expands_image_set_for_legacy_provider(self):
        collection = dict(
            id="mesh-input-set",
            revision="e" * 64,
            type="image_set",
            payload=dict(
                schema_version=1,
                count=2,
                items=[
                    dict(artifact=reference(self.sources[0]), label="front", index=0),
                    dict(artifact=reference(self.sources[1]), label="side", index=1),
                ],
            ),
        )
        for mode, source, manifest in (
            ("single", self.sources[0], self.manifest),
            ("list", collection, dict(schema_version=1, artifacts=self.sources + [collection])),
        ):
            with self.subTest(mode=mode):
                inner = FakeImageProvider("kimi_native")
                provider = self.adapter(inner)
                request = dict(
                    node="image_to_mesh",
                    version="2",
                    inputs={"source": reference(source)},
                    parameters={"prompt": "fit one character from every view"},
                    context=[],
                )
                key = ("3" if mode == "single" else "4") * 64
                receipt = provider.poll(provider.submit(request, manifest, key)["job_id"])
                self.assertEqual(receipt["state"], "succeeded")
                child = inner.requests[0]
                self.assertEqual(child["version"], "1")
                references = [child["inputs"]["source"]] + [
                    item["artifact"] for item in child["context"] if "artifact" in item
                ]
                expected = (
                    [reference(item) for item in self.sources] if mode == "list" else [reference(self.sources[0])]
                )
                self.assertEqual(references, expected)
                self.assertEqual(child["parameters"]["prompt"], "fit one character from every view")
                self.assertIsNone(provider._local(key))
                registry = NodeRegistry()
                register_images(registry)
                validate_invocation(registry, request, manifest, provider.describe())

        inner = FakeImageProvider("kimi_native")
        provider = self.adapter(inner)
        empty = dict(node="image_to_mesh", version="2", inputs={}, parameters={"prompt": "mesh"}, context=[])
        with self.assertRaisesRegex(ValueError, "invalid_image_batch"):
            provider.submit(empty, {"schema_version": 1, "artifacts": []}, "5" * 64)
        self.assertEqual(inner.submissions, 0)

    def test_generate_image_accepts_single_image_and_image_set(self):
        collection = dict(
            id="input-set",
            revision="f" * 64,
            type="image_set",
            payload=dict(
                schema_version=1,
                count=2,
                items=[
                    dict(artifact=reference(self.sources[0]), label="front", index=0),
                    dict(artifact=reference(self.sources[1]), label="side", index=1),
                ],
            ),
        )
        for mode, source, manifest in (
            ("single", self.sources[0], self.manifest),
            ("list", collection, dict(schema_version=1, artifacts=self.sources + [collection])),
        ):
            with self.subTest(mode=mode):
                inner = FakeImageProvider("kimi_work_image")
                provider = self.adapter(inner)
                request = dict(
                    node="generate_image",
                    version="1",
                    inputs={"source": reference(source)},
                    parameters={"prompt": "", "output_count": 1},
                    context=[],
                )
                key = ("7" if mode == "single" else "8") * 64
                receipt = provider.poll(provider.submit(request, manifest, key)["job_id"])
                self.assertEqual(receipt["state"], "succeeded")
                self.assertEqual(set(receipt["outputs"]), {"image_set"})
                child = inner.requests[0]
                self.assertEqual(child["node"], "image_to_image")
                references = [child["inputs"]["source"]] + [
                    item["artifact"] for item in child["context"] if "artifact" in item
                ]
                expected = (
                    [reference(item) for item in self.sources] if mode == "list" else [reference(self.sources[0])]
                )
                self.assertEqual(references, expected)
                self.assertIn("supplied ordered reference image(s)", child["parameters"]["prompt"])

    def test_single_image_sheet_is_interpreted_as_one_subject_before_generation(self):
        for index, supplemental_text in enumerate(("", "Keep the same character and choose one front pose")):
            with self.subTest(supplemental_text=supplemental_text):
                inner = FakeImageProvider("kimi_work_image")
                provider = self.adapter(inner)
                request = dict(
                    node="generate_image",
                    version="1",
                    inputs={"source": reference(self.sources[0])},
                    parameters={"prompt": supplemental_text, "output_count": 1},
                    context=[],
                )
                key = ("9" if index == 0 else "a") * 64
                receipt = provider.poll(provider.submit(request, self.manifest, key)["job_id"])
                self.assertEqual(receipt["state"], "succeeded")
                self.assertEqual(len(inner.requests), 1)
                child = inner.requests[0]
                self.assertEqual(child["inputs"]["source"], reference(self.sources[0]))
                prompt = child["parameters"]["prompt"]
                self.assertIn("including panels inside a single file", prompt)
                self.assertIn("turnaround/multiview sheet", prompt)
                self.assertIn("multiple poses or states of one subject", prompt)
                self.assertIn("ONE subject in ONE coherent view and pose", prompt)
                self.assertIn("never duplicate the subject", prompt)
                self.assertTrue(prompt.endswith("Perform this interpretation before generating the image."))
                if supplemental_text:
                    self.assertTrue(prompt.startswith(supplemental_text + "\n"))

    def test_unified_node_supports_text_images_and_combined_inputs(self):
        cases = (
            ("text", "text", "text_to_image"),
            ("images", "image", "image_to_image"),
            ("combined", "both", "image_to_image"),
        )
        for index, (mode, input_mode, child_kind) in enumerate(cases):
            with self.subTest(mode=mode):
                inner = FakeImageProvider("kimi_work_image")
                provider = self.adapter(inner)
                request = dict(
                    node="generate_image",
                    version="1",
                    inputs={},
                    parameters={"prompt": "", "output_count": 1, "output_labels": []},
                    context=[],
                )
                manifest = {"schema_version": 1, "artifacts": []}
                if input_mode in ("image", "both"):
                    request["inputs"] = {"source": reference(self.sources[0])}
                    manifest = copy.deepcopy(self.manifest)
                if input_mode in ("text", "both"):
                    request["parameters"]["prompt"] = "same sculpture"
                key = str(7 + index) * 64
                receipt = provider.poll(provider.submit(request, manifest, key)["job_id"])
                self.assertEqual(receipt["state"], "succeeded")
                self.assertEqual(set(receipt["outputs"]), {"image_set"})
                self.assertEqual(inner.requests[0]["node"], child_kind)
                if input_mode in ("image", "both"):
                    self.assertEqual(inner.requests[0]["inputs"]["source"], reference(self.sources[0]))
                    self.assertIn("including panels inside a single file", inner.requests[0]["parameters"]["prompt"])
                if mode == "images":
                    self.assertIn("supplied ordered reference", inner.requests[0]["parameters"]["prompt"])
                else:
                    self.assertIn("same sculpture", inner.requests[0]["parameters"]["prompt"])
                if mode == "combined":
                    self.assertTrue(inner.requests[0]["parameters"]["prompt"].startswith("same sculpture\n"))
                    self.assertIn("ONE subject", inner.requests[0]["parameters"]["prompt"])
                registry = NodeRegistry()
                register_images(registry)
                validate_invocation(registry, request, manifest, provider.describe())

        inner = FakeImageProvider("kimi_work_image")
        provider = self.adapter(inner)
        empty = dict(
            node="generate_image",
            version="1",
            inputs={},
            parameters={"prompt": "", "output_count": 1, "output_labels": []},
            context=[],
        )
        with self.assertRaisesRegex(ValueError, "invalid_image_batch"):
            provider.submit(empty, {"schema_version": 1, "artifacts": []}, "a" * 64)
        self.assertEqual(inner.submissions, 0)

    def test_automatic_requirements_infer_count_views_and_details(self):
        cases = [
            ("一个白底石雕", ["main"]),
            ("同一主体的正面、侧面和背面", ["正面", "侧面", "背面"]),
            ("同一角色多视角", ["正面", "右侧面", "背面", "左侧面"]),
            ("两张图：正面和面部细节", ["正面", "面部细节"]),
            ("角色三视图", ["正面", "侧面", "背面"]),
            ("角色前、后视角", ["正面", "背面"]),
            (
                "生成魔兽世界风格人类牧师图，用于生成人物模型，tpose，190身高，脸要我发你的图；"
                "要求前、后、左、右、俯视角，同时给出【多视角】脸部特写。",
                [
                    "正面",
                    "背面",
                    "左侧面",
                    "右侧面",
                    "俯视",
                    "面部正面特写",
                    "面部左侧特写",
                    "面部右侧特写",
                ],
            ),
        ]
        for prompt, expected in cases:
            with self.subTest(prompt=prompt):
                self.assertEqual(
                    [item["label"] for item in automatic_output_specifications(prompt)],
                    expected,
                )
        specifications = automatic_output_specifications("两张图：正面和面部细节")
        self.assertEqual([item["mode"] for item in specifications], ["view", "detail"])
        with self.assertRaisesRegex(ValueError, "invalid_image_batch"):
            automatic_output_specifications("生成九张图")
        cleaned = primary_prompt(
            "A small gray stone owl sculpture on a white background. Show a front view and a three-quarter view of the same sculpture."
        )
        self.assertIn("stone owl sculpture", cleaned)
        self.assertNotIn("front view", cleaned)
        self.assertNotIn("three-quarter view", cleaned)
        self.assertEqual(primary_prompt("同一石雕，正面和三分之四侧面"), "同一石雕")
        self.assertEqual(primary_prompt("生成同一石雕的正面和侧面"), "生成同一石雕的单张主图")

    def test_automatic_views_are_derived_from_the_same_primary_image(self):
        inner = FakeImageProvider("kimi_work_image")
        provider = self.adapter(inner)
        request = dict(
            node="text_to_image",
            version="4",
            inputs={},
            parameters={"prompt": "同一石雕，正面和三分之四侧面"},
            context=[],
        )
        key = "7" * 64
        receipt = provider.submit(request, {"schema_version": 1, "artifacts": []}, key)
        for _ in range(4):
            receipt = provider.poll(receipt["job_id"])
            if receipt["state"] == "succeeded":
                break
        self.assertEqual(receipt["state"], "succeeded")
        self.assertEqual(inner.submissions, 2)
        self.assertEqual(inner.requests[0]["node"], "text_to_image")
        self.assertEqual(inner.requests[0]["inputs"], {})
        self.assertNotIn("正面", inner.requests[0]["parameters"]["prompt"])
        self.assertNotIn("三分之四侧面", inner.requests[0]["parameters"]["prompt"])
        self.assertIn("exactly one single subject", inner.requests[0]["parameters"]["prompt"])
        children = provider.read(key)["children"]
        primary = inner.result_manifest(children[0]["key"])["artifacts"][-1]
        derived = inner.requests[1]
        self.assertEqual(derived["node"], "image_to_image")
        self.assertEqual(derived["inputs"]["source"], reference(primary))
        self.assertIn("authoritative depiction of the same generated subject", derived["parameters"]["prompt"])
        self.assertIn("do not design a new subject", derived["parameters"]["prompt"])
        result = provider.result_manifest(key)
        collection = next(item for item in result["artifacts"] if item["type"] == "image_set")
        self.assertEqual(collection["payload"]["provenance"]["derivation"], "primary_image_derived")
        second_image = next(
            item for item in result["artifacts"] if item["id"] == collection["payload"]["items"][1]["artifact"]["id"]
        )
        self.assertEqual(second_image["payload"]["provenance"]["derived_from"], reference(primary))
        self.assertIn(reference(primary), second_image["dependencies"])

    def test_t_pose_is_expanded_into_explicit_horizontal_arm_constraints(self):
        for index, pose in enumerate(("TPose", "T pose", "t-pose", "T_pose")):
            with self.subTest(pose=pose):
                inner = FakeImageProvider("kimi_work_image")
                provider = self.adapter(inner)
                request = dict(
                    node="generate_image",
                    version="2",
                    inputs={},
                    parameters={"prompt": "同一角色，" + pose + "，正面和背面"},
                    context=[],
                )
                receipt = provider.submit(request, {"schema_version": 1, "artifacts": []}, str(index + 1) * 64)
                for _ in range(4):
                    receipt = provider.poll(receipt["job_id"])
                    if receipt["state"] == "succeeded":
                        break
                self.assertEqual(receipt["state"], "succeeded")
                self.assertEqual(inner.submissions, 2)
                for child in inner.requests:
                    prompt = child["parameters"]["prompt"]
                    self.assertIn("Strict, symmetrical T-pose", prompt)
                    self.assertIn("both arms fully extended straight out to opposite sides", prompt)
                    self.assertIn("perfectly horizontal at shoulder height", prompt)
                    self.assertIn("straight elbows", prompt)
                    self.assertIn("two unbroken horizontal lines", prompt)
                    self.assertIn("Do not angle the arms downward", prompt)

    def test_standalone_garment_has_explicit_front_and_back_surface_constraints(self):
        cases = (
            "单独生成一件白色法袍，只要衣服，不要人体或模特，正面和背面",
            "生成一件白色法袍，不要人体或模特，正面和背面",
            "Generate a standalone white robe, front view and back view",
            "Generate a white robe with no person or mannequin, front view and back view",
        )
        for index, text in enumerate(cases):
            with self.subTest(prompt=text):
                inner = FakeImageProvider("kimi_work_image")
                provider = self.adapter(inner)
                request = dict(
                    node="generate_image",
                    version="2",
                    inputs={},
                    parameters={"prompt": text},
                    context=[],
                )
                receipt = provider.submit(request, {"schema_version": 1, "artifacts": []}, str(index + 5) * 64)
                for _ in range(4):
                    receipt = provider.poll(receipt["job_id"])
                    if receipt["state"] == "succeeded":
                        break
                self.assertEqual(receipt["state"], "succeeded")
                self.assertEqual(inner.submissions, 2)
                front, back = (child["parameters"]["prompt"] for child in inner.requests)
                self.assertIn("strict FRONT view of the ISOLATED garment itself", front)
                self.assertIn("exterior front surface", front)
                self.assertIn("front neckline", front)
                self.assertIn("without a person, body, face, mannequin or hanger", front)
                self.assertIn("wearer's left/right convention", front)
                self.assertNotIn("nose pointing toward the viewer", front)
                self.assertIn("identifies the SAME garment, but it is NOT the target view to reproduce", back)
                self.assertNotIn("authoritative depiction", back)
                self.assertIn("strict BACK view of the SAME ISOLATED garment", back)
                self.assertIn("rotate the garment itself exactly 180 degrees", back)
                self.assertIn("newly visible rear exterior", back)
                self.assertIn("back neckline, rear shoulder construction, rear sleeve attachments", back)
                self.assertIn("central front placket, front buttons and chest-only ornaments", back)
                self.assertIn("do not copy those front motifs onto the back", back)
                self.assertIn("no visible cuff opening, interior lining, turned-back cuff", back)
                self.assertIn("continuous closed pullover-style rear panel", back)
                self.assertIn("no rear vertical opening, placket, zipper, buttons", back)
                self.assertIn("rear waist and belt flat and smooth", back)
                self.assertIn("no front buckle, knot, clasp or large ornamental centerpiece", back)
                self.assertIn("broad flat fabric panels and clear horizontal elements", back)
                self.assertIn("horizontal shoulder yoke, horizontal waist band", back)
                self.assertIn("duplicated, mirrored or relabeled front", back)
                self.assertIn("object-turnaround reconstruction, not a flat retouch", back)
                self.assertIn("reconstruct its hidden surface", back)
                self.assertIn("if the result repeats the opposite-side view", back)
                self.assertNotIn("Change only the camera/view", back)
                self.assertIn("wearer's left/right convention", back)
                self.assertNotIn("face pointing away from the viewer", back)
                self.assertIn("straight-on, near-orthographic product view with no yaw", front)
                self.assertIn("Do not use a three-quarter, oblique or side view", front)

    def reviewed_adapter(self, inner):
        config = dict(endpoint="https://example.invalid/v1", model="kimi-k2.5", key_env="KIMI_API_KEY")
        return MultiImageProvider(inner, self.root / "reviewed-state", review_config=config)

    def reviewed_request(self):
        return dict(
            node="generate_image",
            version="2",
            inputs={},
            parameters={"prompt": "生成一件白色法袍，不要人体或模特，正面和背面"},
            context=[],
        )

    def finish(self, provider, receipt):
        for _ in range(4):
            receipt = provider.poll(receipt["job_id"])
            if receipt["state"] in ("succeeded", "failed", "cancelled"):
                break
        return receipt

    def review_document(self, passed):
        issues = [] if passed else ["front is oblique and back repeats the front"]
        return dict(
            passed=passed,
            same_garment=True,
            views=[
                dict(
                    label=label,
                    observed_view=("front", "back")[index] if passed else ("three_quarter_front", "front")[index],
                    matches_label=passed,
                    garment_only=True,
                    cuff_exterior_pass=passed,
                    closed_back_pass=passed,
                    flat_rear_belt_pass=passed,
                    horizontal_rear_layout_pass=passed,
                    evidence="actual generated pixels",
                    issues=issues,
                )
                for index, label in enumerate(("正面", "背面"))
            ],
            summary="garment view review",
            issues=issues,
            input_images=[dict(label="正面", sha256="a" * 64), dict(label="背面", sha256="b" * 64)],
        )

    def test_garment_view_review_rejects_wrong_angles_before_publication(self):
        inner = FakeImageProvider("kimi_work_image")
        provider = self.reviewed_adapter(inner)
        with patch.object(MultiImageProvider, "_review_garment_views", return_value=self.review_document(False)) as review:
            receipt = self.finish(provider, provider.submit(self.reviewed_request(), {"schema_version": 1, "artifacts": []}, "b" * 64))
        self.assertEqual(receipt["state"], "failed")
        self.assertIn("不是所要求的衣服正背面", receipt["error"])
        self.assertEqual(review.call_count, 1)
        self.assertEqual(inner.submissions, 2)
        self.assertNotIn("result", provider.read("b" * 64))
        with self.assertRaisesRegex(ValueError, "image_batch_result_invalid"):
            provider.result_manifest("b" * 64)

    def test_garment_view_review_pass_is_bound_to_result_provenance(self):
        inner = FakeImageProvider("kimi_work_image")
        provider = self.reviewed_adapter(inner)
        with patch.object(MultiImageProvider, "_review_garment_views", return_value=self.review_document(True)):
            receipt = self.finish(provider, provider.submit(self.reviewed_request(), {"schema_version": 1, "artifacts": []}, "c" * 64))
        self.assertEqual(receipt["state"], "succeeded")
        result = provider.result_manifest("c" * 64)
        collection = next(item for item in result["artifacts"] if item["type"] == "image_set")
        review = collection["payload"]["provenance"]["garment_view_review"]
        self.assertTrue(review["passed"])
        self.assertEqual([item["sha256"] for item in review["input_images"]], ["a" * 64, "b" * 64])

    def test_real_review_request_binds_the_actual_generated_image_hashes(self):
        inner = FakeImageProvider("kimi_work_image")
        provider = self.reviewed_adapter(inner)

        def complete_review(key, directory):
            directory = Path(directory)
            raw = (directory / "api-request.json").read_bytes()
            document = self.review_document(True)
            document.pop("input_images")
            (directory / "api-plan.json").write_text(canonical(document), encoding="utf-8")
            (directory / "api-receipt.json").write_text(
                canonical(
                    dict(
                        request_sha256=hashlib.sha256(raw).hexdigest(),
                        instructions_sha256=hashlib.sha256(canonical(document).encode("utf-8")).hexdigest(),
                    )
                ),
                encoding="utf-8",
            )
            return 0

        with patch.dict(os.environ, {"KIMI_API_KEY": "fixture"}), patch.object(
            MultiImageProvider, "_run_view_review", side_effect=complete_review
        ) as runner:
            receipt = self.finish(
                provider, provider.submit(self.reviewed_request(), {"schema_version": 1, "artifacts": []}, "e" * 64)
            )
        self.assertEqual(receipt["state"], "succeeded")
        self.assertEqual(runner.call_count, 1)
        result = provider.result_manifest("e" * 64)
        collection = next(item for item in result["artifacts"] if item["type"] == "image_set")
        review = collection["payload"]["provenance"]["garment_view_review"]
        expected = [item["artifact"]["revision"] for item in collection["payload"]["items"]]
        self.assertEqual([item["sha256"] for item in review["input_images"]], expected)

    def test_garment_view_review_unavailable_does_not_publish_unreviewed_images(self):
        inner = FakeImageProvider("kimi_work_image")
        provider = self.reviewed_adapter(inner)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("KIMI_API_KEY", None)
            receipt = self.finish(
                provider, provider.submit(self.reviewed_request(), {"schema_version": 1, "artifacts": []}, "d" * 64)
            )
        self.assertEqual(receipt["state"], "failed")
        self.assertIn("KIMI_API_KEY", receipt["error"])
        self.assertNotIn("result", provider.read("d" * 64))

    def test_only_kimi_image_adapter_receives_garment_review_config(self):
        from generation_service import adapt_image_providers

        config = dict(endpoint="https://example.invalid/v1", model="kimi-k2.5", key_env="KIMI_API_KEY")
        providers = adapt_image_providers(
            {"kimi_work_image": FakeImageProvider("kimi_work_image"), "kimi_native": FakeImageProvider("kimi_native")},
            self.root / "routing.sqlite",
            {"enabled": True, "board_config": {}, "review_config": config},
        )
        self.assertEqual(providers["kimi_work_image"].review_config, config)
        self.assertIsNone(providers["kimi_native"].review_config)

    def test_left_and_right_views_have_explicit_opposite_camera_directions(self):
        inner = FakeImageProvider("kimi_work_image")
        provider = self.adapter(inner)
        request = dict(
            node="text_to_image",
            version="4",
            inputs={},
            parameters={"prompt": "同一角色正面、左侧面、右侧面"},
            context=[],
        )
        key = "a" * 64
        receipt = provider.submit(request, {"schema_version": 1, "artifacts": []}, key)
        for _ in range(4):
            receipt = provider.poll(receipt["job_id"])
            if receipt["state"] == "succeeded":
                break
        self.assertEqual(receipt["state"], "succeeded")
        left, right = inner.requests[1:]
        self.assertIn("anatomical LEFT", left["parameters"]["prompt"])
        self.assertIn("nose toward the LEFT edge", left["parameters"]["prompt"])
        self.assertIn("anatomical RIGHT", right["parameters"]["prompt"])
        self.assertIn("nose toward the RIGHT edge", right["parameters"]["prompt"])
        self.assertEqual(left["inputs"]["source"], right["inputs"]["source"])

    def test_automatic_single_image_runs_only_once(self):
        inner = FakeImageProvider("kimi_work_image")
        provider = self.adapter(inner)
        request = dict(
            node="text_to_image",
            version="4",
            inputs={},
            parameters={"prompt": "白底上的一个石雕"},
            context=[],
        )
        key = "8" * 64
        receipt = provider.poll(provider.submit(request, {"schema_version": 1, "artifacts": []}, key)["job_id"])
        self.assertEqual(receipt["state"], "succeeded")
        self.assertEqual(inner.submissions, 1)
        self.assertEqual(provider.read(key)["derivation"], "automatic_single_image")

    def test_unified_version_two_uses_the_same_primary_derived_chain(self):
        inner = FakeImageProvider("kimi_work_image")
        provider = self.adapter(inner)
        request = dict(
            node="generate_image",
            version="2",
            inputs={},
            parameters={"prompt": "同一石雕，正面和三分之四侧面"},
            context=[],
        )
        key = "9" * 64
        receipt = provider.submit(request, {"schema_version": 1, "artifacts": []}, key)
        for _ in range(4):
            receipt = provider.poll(receipt["job_id"])
            if receipt["state"] == "succeeded":
                break
        self.assertEqual(receipt["state"], "succeeded")
        self.assertEqual(set(receipt["outputs"]), {"image_set"})
        self.assertEqual(inner.submissions, 2)
        children = provider.read(key)["children"]
        primary = inner.result_manifest(children[0]["key"])["artifacts"][-1]
        self.assertEqual(inner.requests[0]["node"], "text_to_image")
        self.assertEqual(inner.requests[1]["node"], "image_to_image")
        self.assertEqual(inner.requests[1]["inputs"]["source"], reference(primary))
        result = provider.result_manifest(key)
        collection = next(item for item in result["artifacts"] if item["type"] == "image_set")
        self.assertEqual(collection["payload"]["provenance"]["derivation"], "primary_image_derived")

    def test_version_two_keeps_primary_image_and_queue_outputs(self):
        inner = FakeImageProvider("kimi_work_image")
        provider = self.adapter(inner)
        request = copy.deepcopy(self.request)
        request["version"] = "2"
        receipt = provider.poll(provider.submit(request, self.manifest, "6" * 64)["job_id"])
        self.assertEqual(receipt["state"], "succeeded")
        self.assertEqual(set(receipt["outputs"]), {"result", "image_set"})
        collection = next(
            item for item in provider.result_manifest(receipt["job_id"])["artifacts"] if item["type"] == "image_set"
        )
        self.assertEqual(receipt["outputs"]["result"], collection["payload"]["items"][0]["artifact"])

    def test_version_one_keeps_original_provider_identity_and_lifecycle(self):
        inner = FakeImageProvider("comfy")
        provider = self.adapter(inner)
        request = copy.deepcopy(self.request)
        request["version"] = "1"
        request["parameters"] = {"prompt": "legacy single image"}
        key = "2" * 64
        provider.submit(request, self.manifest, key)
        self.assertEqual(provider.lookup(key)["state"], "succeeded")
        self.assertEqual(provider.poll(key)["state"], "succeeded")
        self.assertEqual(provider.result_manifest(key), inner.result_manifest(key))
        self.assertEqual(provider.cancel(key)["state"], "cancelled")
        self.assertEqual(inner.submissions, 1)
        self.assertIsNone(provider._local(key))

    def test_board_failure_and_unstarted_child_cancel_do_not_submit(self):
        for key in ("3" * 64, "4" * 64):
            inner = FakeImageProvider("comfy")
            provider = self.adapter(inner)
            with patch("multi_image_provider.make_reference_board", side_effect=ValueError("reference_board_failed")):
                receipt = provider.submit(self.request, self.manifest, key)
            self.assertEqual(receipt["state"], "failed")
            self.assertEqual(provider.poll(key)["state"], "failed")
            self.assertEqual(inner.submissions, 0)
            self.assertIsNone(inner.lookup(key) if key in inner.jobs else None)
        inner = FakeImageProvider("kimi_work_image")
        provider = self.adapter(inner)
        key = "5" * 64
        with patch.object(
            MultiImageProvider, "poll", return_value=dict(job_id=key, state="queued", outputs={}, error=None)
        ):
            provider.submit(self.request, self.manifest, key)
        self.assertEqual(provider.cancel(key)["state"], "cancelled")
        self.assertEqual(inner.submissions, 0)
        self.assertEqual(inner.jobs, {})


if __name__ == "__main__":
    unittest.main()
