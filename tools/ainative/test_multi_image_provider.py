"""Cross-provider image collections; all inference and board rendering are faked."""
import base64
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from contracts import validate
from multi_image_provider import MultiImageProvider, output_specifications, register_images
from extensions import NodeRegistry, validate_invocation, validate_outputs


def asset(name, body):
    data = body.encode("utf-8")
    sha = hashlib.sha256(data).hexdigest()
    return dict(
        id=name,
        revision=sha,
        type="image",
        payload=dict(content_base64=base64.b64encode(data).decode(), content_sha256=sha, extension=".png", bytes=len(data)),
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
        return dict(schema_version=1, artifacts=[copy.deepcopy(self.jobs[key]["image"])])

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
            version="2",
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
                self.assertEqual(receipt["outputs"]["result"], collection["payload"]["items"][0]["artifact"])
                registry = NodeRegistry()
                register_images(registry)
                validate_outputs(registry, "image_to_image", "2", receipt["outputs"], manifest)
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
        collection = next(item for item in provider.result_manifest(receipt["job_id"])["artifacts"] if item["type"] == "image_set")
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

        with patch.object(inner, "submit", side_effect=fail_second), patch(
            "multi_image_provider.make_reference_board", side_effect=self.board
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
        references = [second.requests[0]["inputs"]["source"]] + [item["artifact"] for item in second.requests[0]["context"] if "artifact" in item]
        self.assertEqual(references, [item["artifact"] for item in collection["payload"]["items"]])

    def test_version_one_keeps_original_provider_identity_and_lifecycle(self):
        inner = FakeImageProvider("comfy")
        provider = self.adapter(inner)
        request = copy.deepcopy(self.request)
        request["version"] = "1"
        request["parameters"] = {"prompt": "legacy single image"}
        key = "2" * 64
        receipt = provider.submit(request, self.manifest, key)
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
        with patch.object(MultiImageProvider, "poll", return_value=dict(job_id=key, state="queued", outputs={}, error=None)):
            provider.submit(self.request, self.manifest, key)
        self.assertEqual(provider.cancel(key)["state"], "cancelled")
        self.assertEqual(inner.submissions, 0)
        self.assertEqual(inner.jobs, {})


if __name__ == "__main__":
    unittest.main()
