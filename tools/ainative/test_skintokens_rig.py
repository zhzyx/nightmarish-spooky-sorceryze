"""Contract tests for the independent SkinTokens pipeline using a synthetic CLI.

These tests validate adapter behavior (immutability, validation, failure
handling). They are not evidence of real rigging quality or real inference.
"""

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

import skintokens_rig


def make_glb(path, with_skin=True):
    document = {"asset": {"version": "2.0"}, "meshes": [{"primitives": []}], "nodes": []}
    if with_skin:
        document["skins"] = [{"joints": [0, 1]}]
    payload = json.dumps(document).encode("utf-8")
    payload += b" " * (-len(payload) % 4)
    total = 12 + 8 + len(payload)
    path.write_bytes(
        b"glTF" + (2).to_bytes(4, "little") + total.to_bytes(4, "little")
        + len(payload).to_bytes(4, "little") + b"JSON" + payload
    )


SYNTHETIC_CLI = r'''#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
source, output = args[2], args[3]
name = source.rsplit("/", 1)[-1]
def write_glb(with_skin):
    doc = {"asset": {"version": "2.0"}, "meshes": [{"primitives": []}]}
    if with_skin:
        doc["skins"] = [{"joints": [0, 1, 2]}]
    payload = json.dumps(doc).encode()
    payload += b" " * (-len(payload) % 4)
    total = 12 + 8 + len(payload)
    with open(output, "wb") as stream:
        stream.write(b"glTF" + (2).to_bytes(4, "little") + total.to_bytes(4, "little")
                     + len(payload).to_bytes(4, "little") + b"JSON" + payload)
if "fail" in name:
    with open(output, "wb") as stream:
        stream.write(b"partial")
    print("synthetic failure", file=sys.stderr)
    sys.exit(3)
if "silent" in name:
    sys.exit(0)
write_glb("noskin" not in name)
'''


@unittest.skipIf(os.name == "nt", "synthetic executable uses a POSIX shebang")
class SkinTokensPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        cli = self.root / "synthetic-cli"
        cli.write_text(SYNTHETIC_CLI, encoding="utf-8")
        cli.chmod(cli.stat().st_mode | stat.S_IXUSR)
        self.model_dir = self.root / "weights"
        self.model_dir.mkdir()
        for name in skintokens_rig.WEIGHT_FILES:
            (self.model_dir / name).write_bytes(name.encode())
        self.config_path = self.root / "config.json"
        self.config_path.write_text(json.dumps({
            "cli": str(cli), "model_dir": str(self.model_dir), "device": "cpu",
        }), encoding="utf-8")
        self.source = self.root / "character.glb"
        make_glb(self.source)
        self.output = self.root / "rigged.glb"

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, source=None, output=None, report=None):
        argv = ["--config", str(self.config_path),
                "--source", str(source or self.source),
                "--output", str(output or self.output)]
        if report is not None:
            argv += ["--report", str(report)]
        return skintokens_rig.main(argv)

    def test_success_creates_new_output_and_provenance(self):
        report_path = self.root / "report.json"
        code = self.invoke(report=report_path)
        self.assertEqual(code, 0)
        self.assertTrue(self.output.is_file())
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["provider"], "skintokens_local")
        self.assertEqual(report["operation"], "skintokens_local_rig")
        self.assertEqual(report["source_sha256"], skintokens_rig._sha256(self.source))
        self.assertEqual(report["output_sha256"], skintokens_rig._sha256(self.output))
        self.assertEqual(report["rig"]["joint_count"], 3)
        self.assertFalse(report["blender_used"])
        self.assertFalse(report["cloud_used"])
        self.assertFalse(report["fallback_used"])
        self.assertEqual(len(report["weights"]), 3)
        self.assertEqual(report["quality"], "learned_auto_rig_not_reviewed")

    def test_existing_output_is_never_overwritten(self):
        self.output.write_bytes(b"precious")
        self.assertEqual(self.invoke(), 1)
        self.assertEqual(self.output.read_bytes(), b"precious")

    def test_existing_report_is_never_overwritten(self):
        report = self.root / "report.json"
        report.write_text("keep", encoding="utf-8")
        self.assertEqual(self.invoke(report=report), 1)
        self.assertEqual(report.read_text(encoding="utf-8"), "keep")
        self.assertFalse(self.output.exists())

    def test_cli_failure_removes_only_its_partial_output(self):
        source = self.root / "fail.glb"
        make_glb(source)
        original = source.read_bytes()
        self.assertEqual(self.invoke(source=source), 1)
        self.assertFalse(self.output.exists())
        self.assertEqual(source.read_bytes(), original)

    def test_missing_output_is_an_error(self):
        source = self.root / "silent.glb"
        make_glb(source)
        self.assertEqual(self.invoke(source=source), 1)
        self.assertFalse(self.output.exists())

    def test_output_without_skin_is_rejected_and_removed(self):
        source = self.root / "noskin.glb"
        make_glb(source, with_skin=False)
        self.assertEqual(self.invoke(source=source), 1)
        self.assertFalse(self.output.exists())

    def test_source_must_be_glb_with_mesh(self):
        bad = self.root / "bad.glb"
        bad.write_bytes(b"not a glb")
        self.assertEqual(self.invoke(source=bad), 1)
        self.assertFalse(self.output.exists())

    def test_missing_weights_fail_before_execution(self):
        (self.model_dir / "tokenrig.gguf").unlink()
        self.assertEqual(self.invoke(), 1)
        self.assertFalse(self.output.exists())

    def test_missing_config_is_explicit(self):
        with self.assertRaises(skintokens_rig.PipelineError):
            skintokens_rig.load_config(None)
        env = dict(os.environ)
        os.environ.pop("AINATIVE_SKINTOKENS_CONFIG", None)
        try:
            with self.assertRaises(skintokens_rig.PipelineError):
                skintokens_rig.load_config(None)
        finally:
            os.environ.clear()
            os.environ.update(env)


if __name__ == "__main__":
    unittest.main()
