"""Synthetic Kimi Work 3D workers only; no network or Tripo API inference."""

import base64
import hashlib
import io
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

from kimi_provider import KimiNativeDirectProvider, check_model3d_tool
from test_kimi_provider import png_bytes, triangle_glb

KEY = "c" * 64


class Direct3DTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kimi-direct-3d-")
        self.root = Path(self.tmp.name)
        self.tool = self.root / "model3d_generation_tool.py"
        self.launcher = self.root / "model3d_generation_launch.py"
        self.watcher = self.root / "model3d_generation_watch.py"
        self.tool.write_text(
            "import sys\n"
            "if sys.argv[1] != 'image-to-url': raise SystemExit(2)\n"
            "path = sys.argv[sys.argv.index('--image-path') + 1]\n"
            "print('https://public.test/' + path.rsplit('/', 1)[-1])\n",
            encoding="utf-8",
        )
        self.launcher.write_text(
            "import json,sys\n"
            "from pathlib import Path\n"
            "args = sys.argv[1:]\n"
            "output = Path(args[args.index('--output') + 1])\n"
            "job = output.parent / 'runtime' / 'job'\n"
            "job.mkdir(parents=True, exist_ok=True)\n"
            "(job / 'worker.log').write_text('')\n"
            "(job / 'worker.pid').write_text('123')\n"
            "(job / 'args.json').write_text(json.dumps(args))\n"
            "print('Job log: ' + str(job / 'worker.log'))\n"
            "print('Job PID file: ' + str(job / 'worker.pid'))\n",
            encoding="utf-8",
        )
        glb = base64.b64encode(triangle_glb()).decode()
        preview = base64.b64encode(png_bytes()).decode()
        self.watcher.write_text(
            "import base64,json,sys\n"
            "from pathlib import Path\n"
            "args = sys.argv[1:]\n"
            "log = Path(args[args.index('--log-file') + 1])\n"
            "worker_args = json.loads((log.parent / 'args.json').read_text())\n"
            "output = Path(worker_args[worker_args.index('--output') + 1])\n"
            f"output.write_bytes(base64.b64decode('{glb}'))\n"
            f"output.with_suffix('.preview.png').write_bytes(base64.b64decode('{preview}'))\n"
            "log.write_text('upstream task_id: synthetic-task-1\\nSaved generated 3D model to: ' + str(output))\n"
            "print('done: ' + str(output))\n",
            encoding="utf-8",
        )
        self.config = dict(
            tool_path=str(self.tool),
            pythonw_path=sys.executable,
            storage=str(self.root / "state"),
            model="v3.1",
        )
        self.provider = KimiNativeDirectProvider(self.config)

    def tearDown(self):
        if (self.root / "state" / KEY).exists():
            try:
                self.provider.cancel(KEY)
            except (ValueError, TypeError):
                pass
        self.tmp.cleanup()

    def artifact(self, data, name="sheet"):
        return dict(
            id=name,
            revision=hashlib.sha256(data).hexdigest(),
            type="image",
            payload=dict(
                content_base64=base64.b64encode(data).decode(),
                content_sha256=hashlib.sha256(data).hexdigest(),
                bytes=len(data),
                extension=".png",
            ),
        )

    def model_artifact(self, task_id="source-task-1", name="source-model"):
        data = triangle_glb()
        return dict(
            id=name,
            revision=hashlib.sha256(data).hexdigest(),
            type="mesh",
            payload=dict(
                content_base64=base64.b64encode(data).decode(),
                content_sha256=hashlib.sha256(data).hexdigest(),
                bytes=len(data),
                extension=".glb",
                provenance={"service": "Tripo API", "operation": "generate_3d_model", "task_id": task_id},
            ),
        )

    def adjust_request(self, source, prompt="", guides=()):
        return dict(
            node="model_adjust",
            version="1",
            inputs={"source": {"id": source["id"], "revision": source["revision"]}},
            parameters={"prompt": prompt},
            context=[
                dict(
                    artifact={"id": guide["id"], "revision": guide["revision"]},
                    role="reference",
                    scope="node",
                    strength="reference",
                )
                for guide in guides
            ],
        )

    def adjust_arguments(self):
        return json.loads((self.root / "state" / KEY / "runtime" / "job" / "args.json").read_text())

    def wait(self):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            result = self.provider.poll(KEY)
            if result["state"] in ("succeeded", "failed", "cancelled"):
                return result
            time.sleep(0.05)
        self.fail("direct 3D worker did not finish")

    def run_job(self, request, manifest):
        self.provider.submit(request, manifest, KEY)
        result = self.wait()
        self.assertEqual(result["state"], "succeeded", self.provider.read(KEY))
        return self.provider.result_manifest(KEY)["artifacts"][0]

    def test_text_generation_uses_tripo_operation_and_real_glb_receipt(self):
        request = dict(
            node="text_to_mesh",
            version="1",
            inputs={},
            parameters={"prompt": "a detailed human priest in T pose"},
            context=[],
        )
        artifact = self.run_job(request, dict(schema_version=1, artifacts=[]))
        provenance = artifact["payload"]["provenance"]
        self.assertEqual(provenance["provider"], "kimi_native")
        self.assertEqual(provenance["service"], "Tripo API")
        self.assertEqual(provenance["operation"], "generate_3d_model")
        self.assertEqual(provenance["generation_model"], "v3.1")
        self.assertEqual(provenance["task_id"], "synthetic-task-1")
        self.assertEqual(provenance["geometry"]["triangles"], 1)
        self.assertFalse(provenance["blender_used"])
        self.assertFalse(provenance["fallback_used"])
        self.assertIsNotNone(provenance["preview_sha256"])
        arguments = json.loads((self.root / "state" / KEY / "runtime" / "job" / "args.json").read_text())
        self.assertIn("--description", arguments)
        self.assertNotIn("--multiview", arguments)

    def test_three_view_sheet_is_cropped_and_uploaded_in_front_right_back_order(self):
        from PIL import Image

        image = Image.new("RGB", (300, 100))
        image.paste((255, 0, 0), (0, 0, 100, 100))
        image.paste((0, 255, 0), (100, 0, 200, 100))
        image.paste((0, 0, 255), (200, 0, 300, 100))
        encoded = io.BytesIO()
        image.save(encoded, format="PNG")
        source = self.artifact(encoded.getvalue())
        request = dict(
            node="image_to_mesh",
            version="1",
            inputs={"source": {"id": "sheet", "revision": source["revision"]}},
            parameters={"prompt": "三视图"},
            context=[],
        )
        artifact = self.run_job(request, dict(schema_version=1, artifacts=[source]))
        provenance = artifact["payload"]["provenance"]
        self.assertEqual(provenance["input_mode"], "multiview_sheet")
        self.assertEqual(provenance["prompt_application"], "turnaround_selection_only")
        views = provenance["view_sources"]
        self.assertEqual([view["view"] for view in views], ["front", "right", "back"])
        self.assertEqual(
            [view["crop_box"] for view in views], [[0, 0, 100, 100], [100, 0, 200, 100], [200, 0, 300, 100]]
        )
        self.assertEqual(len({view["output_sha256"] for view in views}), 3)
        self.assertNotIn("public.test", json.dumps(provenance))
        arguments = json.loads((self.root / "state" / KEY / "runtime" / "job" / "args.json").read_text())
        self.assertIn("--multiview", arguments)
        self.assertIn("--front-url", arguments)
        self.assertIn("--right-url", arguments)
        self.assertIn("--back-url", arguments)
        self.assertNotIn("--left-url", arguments)
        self.assertNotIn("--description", arguments)

    def test_single_image_accepts_empty_prompt_and_rejects_extra_text_constraint(self):
        source = self.artifact(png_bytes(), "ordinary")
        request = dict(
            node="image_to_mesh",
            version="1",
            inputs={"source": {"id": "ordinary", "revision": source["revision"]}},
            parameters={"prompt": ""},
            context=[],
        )
        artifact = self.run_job(request, dict(schema_version=1, artifacts=[source]))
        self.assertEqual(artifact["payload"]["provenance"]["input_mode"], "image")
        arguments = json.loads((self.root / "state" / KEY / "runtime" / "job" / "args.json").read_text())
        self.assertIn("--image-url", arguments)
        self.assertNotIn("--multiview", arguments)

    def test_image_with_unsupported_text_fails_before_worker_launch(self):
        source = self.artifact(png_bytes(), "ordinary")
        request = dict(
            node="image_to_mesh",
            version="1",
            inputs={"source": {"id": "ordinary", "revision": source["revision"]}},
            parameters={"prompt": "also change the costume"},
            context=[],
        )
        result = self.provider.submit(request, dict(schema_version=1, artifacts=[source]), KEY)
        self.assertEqual(result["state"], "failed")
        self.assertEqual(result["error"], self.provider.MESSAGES["unsupported_image_text_constraints"])
        self.assertFalse((self.root / "state" / KEY / "runtime" / "job" / "args.json").exists())

    def test_tool_check_is_local_and_reports_missing_configuration(self):
        report = check_model3d_tool("", "")
        self.assertFalse(report["connected"])
        self.assertEqual(report["code"], "model3d_not_configured")
        ready = check_model3d_tool(str(self.tool), sys.executable)
        self.assertTrue(ready["connected"])
        self.assertEqual(ready["service"], "Tripo API")

    def test_adjust_uses_source_task_text_and_style_image_without_overwriting_original(self):
        source = self.model_artifact()
        guide = self.artifact(png_bytes(), "style")
        request = self.adjust_request(source, "Dim the gold decorations; preserve face, robe and T pose", [guide])
        artifact = self.run_job(request, dict(schema_version=1, artifacts=[source, guide]))
        arguments = self.adjust_arguments()
        self.assertEqual(arguments[0], "texture")
        self.assertEqual(arguments[arguments.index("--task-id") + 1], "source-task-1")
        self.assertEqual(arguments[arguments.index("--model") + 1], "v3.5")
        self.assertIn("--prompt", arguments)
        self.assertIn("--style-image-url", arguments)
        self.assertNotIn("--model-url", arguments)
        self.assertNotIn("--image-url", arguments)
        provenance = artifact["payload"]["provenance"]
        self.assertEqual(provenance["operation"], "texture_3d_model")
        self.assertEqual(provenance["source_task_id"], "source-task-1")
        self.assertEqual(provenance["guidance_mode"], "text_style_image")
        self.assertTrue(provenance["original_model_not_overwritten"])
        self.assertFalse(provenance["blender_used"])
        self.assertFalse(provenance["fallback_used"])
        state = self.root / "state" / KEY
        self.assertEqual(hashlib.sha256((state / "source-model.glb").read_bytes()).hexdigest(), source["revision"])
        self.assertTrue((state / "adjusted.glb").is_file())
        self.assertNotEqual(state / "source-model.glb", state / "adjusted.glb")

    def test_adjust_accepts_source_without_guidance(self):
        source = self.model_artifact(task_id="source-task-no-guidance")
        artifact = self.run_job(self.adjust_request(source), dict(schema_version=1, artifacts=[source]))
        arguments = self.adjust_arguments()
        self.assertIn("--task-id", arguments)
        for flag in ("--prompt", "--style-image-url", "--image-url", "--front-url"):
            self.assertNotIn(flag, arguments)
        self.assertEqual(artifact["payload"]["provenance"]["guidance_mode"], "none")

    def test_adjust_accepts_one_image_without_text(self):
        source = self.model_artifact(task_id="source-task-image")
        guide = self.artifact(png_bytes(), "appearance")
        artifact = self.run_job(
            self.adjust_request(source, guides=[guide]), dict(schema_version=1, artifacts=[source, guide])
        )
        arguments = self.adjust_arguments()
        self.assertIn("--image-url", arguments)
        self.assertNotIn("--prompt", arguments)
        self.assertNotIn("--style-image-url", arguments)
        self.assertEqual(artifact["payload"]["provenance"]["guidance_mode"], "image")

    def test_adjust_uploads_local_glb_when_no_upstream_task_is_available(self):
        source = self.model_artifact(task_id=None)
        artifact = self.run_job(
            self.adjust_request(source, "keep the shape"), dict(schema_version=1, artifacts=[source])
        )
        arguments = self.adjust_arguments()
        self.assertEqual(arguments[arguments.index("--model-url") + 1], "https://public.test/source-model.glb")
        self.assertNotIn("--task-id", arguments)
        self.assertTrue((self.root / "state" / KEY / "model-0.log").is_file())
        provenance = artifact["payload"]["provenance"]
        self.assertIsNone(provenance["source_task_id"])
        self.assertIsNotNone(provenance["source_model_url_sha256"])
        self.assertNotIn("public.test", json.dumps(provenance))

    def test_adjust_four_view_guidance_uses_all_ordered_views(self):
        source = self.model_artifact(task_id="source-task-four-view")
        guides = [self.artifact(png_bytes(), name) for name in ("front", "left", "back", "right")]
        artifact = self.run_job(
            self.adjust_request(source, guides=guides), dict(schema_version=1, artifacts=[source, *guides])
        )
        arguments = self.adjust_arguments()
        for view in ("front", "left", "back", "right"):
            flag = "--" + view + "-url"
            self.assertEqual(
                arguments[arguments.index(flag) + 1],
                "https://public.test/guide-" + str(("front", "left", "back", "right").index(view)) + ".png",
            )
        self.assertNotIn("--prompt", arguments)
        self.assertNotIn("--image-url", arguments)
        provenance = artifact["payload"]["provenance"]
        self.assertEqual(provenance["guidance_mode"], "four_images")
        self.assertEqual([view["view"] for view in provenance["view_sources"]], ["front", "left", "back", "right"])

    def test_adjust_rejects_missing_source_and_ambiguous_guidance_before_launch(self):
        source = self.model_artifact()
        two = [self.artifact(png_bytes(), name) for name in ("front", "left")]
        four = two + [self.artifact(png_bytes(), name) for name in ("back", "right")]
        cases = [
            (self.adjust_request(source, guides=two), [source, *two], "model_adjust_guidance_invalid"),
            (
                self.adjust_request(source, "text with four views", four),
                [source, *four],
                "model_adjust_guidance_invalid",
            ),
            (dict(self.adjust_request(source), inputs={}), [source], "model_adjust_source_missing"),
        ]
        for request, artifacts, error in cases:
            with self.subTest(error=error, images=len(request["context"])):
                with self.assertRaisesRegex(ValueError, error):
                    self.provider.plan(request, dict(schema_version=1, artifacts=artifacts))
        self.assertFalse((self.root / "state" / KEY / "runtime" / "job" / "args.json").exists())

    def test_executor_links_generated_mesh_into_adjustment_and_returns_new_artifact(self):
        from comfy_provider import register
        from editor_demo import factory
        from editor_host import compile_graph
        from executor import Executor

        model = {
            "nodes": [
                {
                    "id": "source",
                    "type": "text_to_mesh",
                    "provider": "kimi_native",
                    "source": "",
                    "parameters": {"prompt": "a synthetic generated mesh"},
                },
                {
                    "id": "adjust",
                    "type": "model_adjust",
                    "provider": "kimi_native",
                    "source": "",
                    "parameters": {"prompt": "preserve the source shape"},
                },
            ],
            "edges": [{"from": "source", "to": "adjust", "input": "source", "output": "result"}],
        }
        graph, manifest = compile_graph(model)
        registry, providers = factory()
        register(registry)
        providers["kimi_native"] = self.provider
        executor = Executor(self.root / "linked-executor.sqlite", registry, providers)
        try:
            run_id = executor.create(graph, manifest)
            for _ in range(400):
                status = executor.step(run_id)
                if status["state"] in ("succeeded", "failed", "cancelled"):
                    break
                time.sleep(0.05)
            self.assertEqual(status["state"], "succeeded", status)
            result = executor.export_node(run_id, "adjust")
            source_id = status["nodes"]["source"]["job"]["outputs"]["result"]["id"]
            adjusted_id = status["nodes"]["adjust"]["job"]["outputs"]["result"]["id"]
            self.assertNotEqual(adjusted_id, source_id)
            adjusted = next(artifact for artifact in result["manifest"]["artifacts"] if artifact["id"] == adjusted_id)
            provenance = adjusted["payload"]["provenance"]
            self.assertEqual(provenance["source_artifact_id"], source_id)
            self.assertEqual(provenance["source_task_id"], "synthetic-task-1")
            self.assertTrue(provenance["original_model_not_overwritten"])
            arguments_path = (
                self.root / "state" / status["nodes"]["adjust"]["job"]["job_id"] / "runtime" / "job" / "args.json"
            )
            self.assertIn("--task-id", json.loads(arguments_path.read_text()))
        finally:
            executor.close()


if __name__ == "__main__":
    unittest.main()
