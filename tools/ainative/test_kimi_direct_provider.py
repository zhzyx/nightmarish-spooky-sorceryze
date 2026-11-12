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
            "import base64,sys\n"
            "from pathlib import Path\n"
            "args = sys.argv[1:]\n"
            "log = Path(args[args.index('--log-file') + 1])\n"
            "output = log.parent.parent.parent / 'generated.glb'\n"
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


if __name__ == "__main__":
    unittest.main()
