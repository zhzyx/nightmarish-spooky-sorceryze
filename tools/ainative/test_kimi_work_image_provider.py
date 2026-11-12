"""Kimi Work image task tests use local fake scripts, never real inference."""

import base64
import hashlib
import json
import os
import struct
import sys
import tempfile
import time
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from comfy_provider import digest
from kimi_work_image_provider import _WORKERS, KimiWorkImageProvider, _tool_fingerprint, check_image_tool

FAKE_TOOL = r"""
import argparse, hashlib, json, os, struct, sys, time, zlib
from pathlib import Path
parser = argparse.ArgumentParser()
sub = parser.add_subparsers(dest="command", required=True)
upload = sub.add_parser("image-to-url")
upload.add_argument("--image-path", required=True)
generate = sub.add_parser("generate")
for name in ("description", "size", "background", "output"):
    generate.add_argument("--" + name, required=True)
generate.add_argument("--reference-image", action="append")
args = parser.parse_args()
if args.command == "image-to-url":
    digest = hashlib.sha256(Path(args.image_path).read_bytes()).hexdigest()
    with (Path(__file__).parent / "uploads.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"content_sha256": digest}) + "\n")
    print("https://images.example.invalid/" + digest + ".png")
    raise SystemExit(0)
with (Path(__file__).parent / "calls.jsonl").open("a", encoding="utf-8") as stream:
    stream.write(json.dumps({"command": "generate", "references": args.reference_image or [], "description": args.description}) + "\n")
if os.environ.get("KIMI_WORK_FIXTURE_FAILURE") == "dependency":
    print("Missing dependency: fixture", file=sys.stderr)
    raise SystemExit(1)
if os.environ.get("KIMI_WORK_FIXTURE_FAILURE") == "service":
    print("Error generating image: synthetic service failure", file=sys.stderr)
    raise SystemExit(1)
if os.environ.get("KIMI_WORK_FIXTURE_FAILURE") == "unknown":
    raise SystemExit(3)
time.sleep(float(os.environ.get("KIMI_WORK_FIXTURE_DELAY", "0")))
width, height = [int(value) for value in args.size.split("x")]
rows = bytearray()
for y in range(height):
    rows.append(0)
    for x in range(width):
        rows.extend(((x + len(args.description)) % 251, (y + len(args.description)) % 251, (x + y) % 251))
def chunk(kind, body):
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xffffffff)
data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(bytes(rows))) + chunk(b"IEND", b"")
Path(args.output).write_bytes(data)
print("Saved generated image to: " + args.output, flush=True)
"""

FAKE_LAUNCH = r"""
import subprocess, sys, tempfile
from pathlib import Path
folder = Path(tempfile.mkdtemp(prefix="kimi-work-fake-job-"))
log = folder / "worker.log"
with log.open("wb") as stream:
    worker = subprocess.Popen([sys.executable, str(Path(__file__).with_name("image_generation_tool.py")), *sys.argv[1:]], stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
(folder / "worker.pid").write_text(str(worker.pid), encoding="utf-8")
print("Job log: " + str(log))
print("Job PID file: " + str(folder / "worker.pid"))
"""

FAKE_WATCH = r"""
import argparse, os, sys, time
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument("--log-file", required=True)
parser.add_argument("--pid-file", required=True)
parser.add_argument("--interval-seconds", default="5")
args = parser.parse_args()
if os.environ.get("KIMI_WORK_FIXTURE_FAILURE") == "unknown":
    time.sleep(0.5)
    print("failed: synthetic unknown worker result", file=sys.stderr)
    raise SystemExit(1)
deadline = time.monotonic() + 20
while time.monotonic() < deadline:
    text = Path(args.log_file).read_text(encoding="utf-8", errors="replace")
    saved = [line.removeprefix("Saved generated image to: ") for line in text.splitlines() if line.startswith("Saved generated image to: ")]
    if saved:
        print("done: " + saved[-1])
        raise SystemExit(0)
    failed = [line for line in text.splitlines() if line.startswith(("Error", "Missing dependency:"))]
    if failed:
        print("failed: " + failed[-1], file=sys.stderr)
        raise SystemExit(1)
    time.sleep(0.05)
print("failed: synthetic unknown worker result", file=sys.stderr)
raise SystemExit(1)
"""


def png(width=1024, height=1024):
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    rows = b"".join(b"\0" + bytes((y % 251, 70, 80)) * width for y in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


class KimiWorkImageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kimi-work-image-test-")
        self.root = Path(self.tmp.name)
        self.tools = self.root / "image_generation" / "scripts"
        self.tools.mkdir(parents=True)
        for name, source in (
            ("image_generation_tool.py", FAKE_TOOL),
            ("image_generation_launch.py", FAKE_LAUNCH),
            ("image_generation_watch.py", FAKE_WATCH),
        ):
            (self.tools / name).write_text(source, encoding="utf-8")
        self.config = dict(
            tool_path=str(self.tools / "image_generation_tool.py"),
            pythonw_path=sys.executable,
            storage=str(self.root / "state"),
        )
        patcher = patch(
            "kimi_work_image_provider.check_image_tool",
            return_value={
                "connected": True,
                "code": "",
                "tool_fingerprint": _tool_fingerprint(self.config["tool_path"]),
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.provider = KimiWorkImageProvider(self.config)

    def tearDown(self):
        self.tmp.cleanup()

    def request(self, kind="text_to_image", source=None):
        return dict(
            node=kind,
            version="1",
            inputs={"source": {k: source[k] for k in ("id", "revision")}} if source else {},
            parameters={"prompt": "an original floating city", "width": 1024, "height": 1024},
            context=[],
        )

    def source(self, suffix=""):
        data = png(1024, 1024 + len(suffix))
        sha = hashlib.sha256(data).hexdigest()
        return dict(
            id="fixture-input" + suffix,
            revision=sha,
            type="image",
            payload=dict(
                content_base64=base64.b64encode(data).decode(),
                content_sha256=sha,
                extension=".png",
                bytes=len(data),
            ),
        )

    def wait(self, key, provider=None):
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            snapshot = (provider or self.provider).lookup(key)
            if snapshot["state"] in ("succeeded", "failed", "cancelled"):
                # A terminal DB commit precedes process teardown by a few instructions.
                # Reap owned workers before TemporaryDirectory removes inherited logs.
                for process in _WORKERS:
                    process.wait(timeout=10)
                return snapshot
            time.sleep(0.05)
        self.fail("fake worker did not finish")

    def test_text_image_is_new_decoded_image_with_distinct_provenance(self):
        key = digest(["text-image"])
        snapshot = self.provider.submit(self.request(), {"schema_version": 1, "artifacts": []}, key)
        self.assertIn(snapshot["state"], ("queued", "running"))
        self.assertEqual(self.wait(key)["state"], "succeeded")
        artifact = self.provider.result_manifest(key)["artifacts"][0]
        payload = artifact["payload"]
        self.assertEqual(payload["extension"], ".png")
        self.assertEqual(payload["provenance"]["provider"], "kimi_work_image")
        self.assertEqual(payload["provenance"]["generation_version"], "v2")
        self.assertTrue(payload["provenance"]["distinct_from_mesh_model"])
        self.assertNotIn("reference_image_urls", json.dumps(payload["provenance"]))
        self.assertEqual(
            base64.b64decode(payload["content_base64"]), (self.provider.storage / key / "generated.png").read_bytes()
        )
        self.assertEqual(
            self.provider.submit(self.request(), {"schema_version": 1, "artifacts": []}, key)["state"], "succeeded"
        )
        self.assertEqual(len((self.tools / "calls.jsonl").read_text().splitlines()), 1)
        restored = KimiWorkImageProvider(self.config)
        self.assertEqual(restored.result_manifest(key), self.provider.result_manifest(key))

    def test_image_to_image_uploads_reference_and_does_not_copy_input(self):
        source = self.source()
        manifest = {"schema_version": 1, "artifacts": [source]}
        key = digest(["image-edit"])
        self.assertEqual(
            self.wait(self.provider.submit(self.request("image_to_image", source), manifest, key)["job_id"])["state"],
            "succeeded",
        )
        output = self.provider.result_manifest(key)["artifacts"][0]
        provenance = output["payload"]["provenance"]
        self.assertEqual(provenance["source_sha256"], source["revision"])
        self.assertNotEqual(provenance["output_sha256"], source["revision"])
        self.assertNotIn("https://", json.dumps(provenance))
        calls = [json.loads(line) for line in (self.tools / "calls.jsonl").read_text().splitlines()]
        self.assertEqual(len(calls[0]["references"]), 1)

    def test_invalid_size_and_mesh_do_not_start_generation(self):
        request = self.request()
        request["parameters"]["width"] = 512
        snapshot = self.provider.submit(request, {"schema_version": 1, "artifacts": []}, digest(["size"]))
        self.assertEqual(snapshot["state"], "failed")
        self.assertFalse((self.tools / "calls.jsonl").exists())
        request["parameters"]["width"] = 1024
        request["node"] = "text_to_mesh"
        with self.assertRaises(ValueError):
            self.provider.submit(request, {"schema_version": 1, "artifacts": []}, digest(["mesh"]))

    def test_cancel_is_terminal_and_restore_never_replays(self):
        key = digest(["cancel"])
        with patch.dict(os.environ, {"KIMI_WORK_FIXTURE_DELAY": "1.5"}):
            self.provider.submit(self.request(), {"schema_version": 1, "artifacts": []}, key)
            deadline = time.monotonic() + 5
            while not (self.tools / "calls.jsonl").exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue((self.tools / "calls.jsonl").is_file())
            self.assertEqual(self.provider.cancel(key)["state"], "cancelled")
            time.sleep(2)
        restored = KimiWorkImageProvider(self.config)
        self.assertEqual(restored.lookup(key)["state"], "cancelled")
        with self.assertRaises(ValueError):
            restored.result_manifest(key)
        self.assertEqual(len((self.tools / "calls.jsonl").read_text().splitlines()), 1)

    def test_dependency_service_and_unknown_failures_are_not_retried(self):
        for index, (failure, expected) in enumerate((
            ("dependency", "依赖"),
            ("service", "未返回成功"),
            ("unknown", "回执不明"),
        )):
            with self.subTest(failure=failure), patch.dict(os.environ, {"KIMI_WORK_FIXTURE_FAILURE": failure}):
                snapshot = self.wait(
                    self.provider.submit(self.request(), {"schema_version": 1, "artifacts": []}, digest([failure]))[
                        "job_id"
                    ]
                )
                self.assertEqual(snapshot["state"], "failed")
                self.assertIn(expected, snapshot["error"])
        self.assertEqual(len((self.tools / "calls.jsonl").read_text().splitlines()), 3)

    def test_local_check_does_not_execute_tool_or_read_credentials(self):
        report = check_image_tool("", "")
        self.assertFalse(report["connected"])
        self.assertEqual(report["code"], "image_not_configured")

    def test_adapter_sends_both_ordered_sources_to_each_independent_output(self):
        from multi_image_provider import MultiImageProvider

        sources = [self.source("-front"), self.source("-side")]
        manifest = dict(schema_version=1, artifacts=sources)
        request = dict(
            node="image_to_image",
            version="2",
            inputs={"source": {key: sources[0][key] for key in ("id", "revision")}},
            context=[dict(artifact={key: sources[1][key] for key in ("id", "revision")}, role="reference", scope="node", strength="reference")],
            parameters=dict(prompt="same sculpture", width=1024, height=1024, output_count=2, output_labels=["front", "three-quarter"]),
        )
        key = digest(["native-multi-image"])
        adapter = MultiImageProvider(self.provider, self.root / "adapter")
        self.assertEqual(self.wait(adapter.submit(request, manifest, key)["job_id"], adapter)["state"], "succeeded")
        restored = MultiImageProvider(KimiWorkImageProvider(self.config), self.root / "adapter")
        self.assertEqual(restored.lookup(key)["state"], "succeeded")
        calls = [json.loads(line) for line in (self.tools / "calls.jsonl").read_text().splitlines()]
        self.assertEqual(len(calls), 2)
        expected = ["https://images.example.invalid/" + source["revision"] + ".png" for source in sources]
        for call, label in zip(calls, ("front", "three-quarter")):
            self.assertEqual(call["references"], expected)
            self.assertIn("exactly one independent image", call["description"])
            self.assertIn(label, call["description"])
        # Independent workers can interleave the fixture's shared append-only
        # log. Verify each child's private, ordered upload receipts instead.
        for child in restored.read(key)["children"]:
            directory = self.provider.storage / child["key"]
            for index, url in enumerate(expected):
                receipt = (directory / ("upload-" + str(index) + ".log")).read_text().strip()
                self.assertEqual(receipt, url)
        artifacts = restored.result_manifest(key)["artifacts"]
        images = [asset for asset in artifacts if asset["type"] == "image" and asset["id"].startswith("kimi-work-image-")]
        self.assertEqual(len(images), 2)
        self.assertNotEqual(images[0]["revision"], images[1]["revision"])
        before = (self.tools / "calls.jsonl").read_bytes()
        self.assertEqual(restored.submit(request, manifest, key)["state"], "succeeded")
        self.assertEqual((self.tools / "calls.jsonl").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
