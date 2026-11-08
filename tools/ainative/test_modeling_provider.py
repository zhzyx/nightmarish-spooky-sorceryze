"""Synthetic CLI plans + real Godot builder; never calls an online model."""

import base64
import copy
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from comfy_provider import register
from executor import check_content
from extensions import NodeRegistry, validate_outputs
from modeling_provider import (
    _WORKERS,
    ModelingProvider,
    check_modeling_cli,
    modeling_schema,
    validate_mesh,
    validate_plan,
)

ROOT = Path(__file__).resolve().parents[2]
GODOT = (
    Path(os.environ["AINATIVE_TEST_GODOT"])
    if os.environ.get("AINATIVE_TEST_GODOT")
    else next(
        (
            candidate
            for candidate in (
                ROOT / "bin/godot.windows.editor.x86_64.exe",
                ROOT / "bin/godot.linuxbsd.editor.x86_64",
            )
            if candidate.is_file()
        ),
        Path(shutil.which("godot") or "__godot_unavailable__"),
    )
)
BUILDER = ROOT / "samples/ainative-workbench/addons/ainative/modeling_builder.gd"
KEY = "a" * 64
PLAN = {
    "version": 1,
    "name": "Table",
    "parts": [
        {
            "name": "Top",
            "primitive": "box",
            "position": [0, 1, 0],
            "rotation_degrees": [0, 0, 0],
            "size": [2, 0.1, 1],
            "color": [0.4, 0.2, 0.1, 1],
        }
    ],
}
FAKE_CS = r"""
using System;
using System.IO;
using System.Threading;
class ModelingCli {
  static int Main(string[] args) {
    Console.InputEncoding=System.Text.Encoding.UTF8;
    string dir=Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location);
    string mode=File.Exists(Path.Combine(dir,"mode"))?File.ReadAllText(Path.Combine(dir,"mode")).Trim():"ok";
    if(Array.IndexOf(args,"--version")>=0){Console.WriteLine("codex 0.166.0-alpha.6");return 0;}
    if(Array.IndexOf(args,"login")>=0){Console.WriteLine(mode=="no-login"?"Not logged in":"Logged in using ChatGPT");return mode=="no-login"?1:0;}
    File.AppendAllText(Path.Combine(dir,"runs"),"run\n");
    File.WriteAllText(Path.Combine(dir,"args"),String.Join("\n",args));
    File.WriteAllText(Path.Combine(dir,"prompt"),Console.In.ReadToEnd());
    File.WriteAllText(Path.Combine(dir,"started"),"yes");
    Console.WriteLine("{\"type\":\"thread.started\",\"thread_id\":\""+Guid.NewGuid().ToString()+"\"}");Console.Out.Flush();
    if(mode=="block")Thread.Sleep(30000);
    if(mode=="fail"){Console.WriteLine("{\"type\":\"turn.failed\"}");return 3;}
    int target=Array.IndexOf(args,"--output-last-message");
    if(mode!="no-output")File.Copy(Path.Combine(dir,"plan.json"),args[target+1],false);
    if(mode=="tool")Console.WriteLine("{\"type\":\"item.completed\",\"item\":{\"type\":\"command_execution\"}}");
    if(mode!="no-turn")Console.WriteLine("{\"type\":\"turn.completed\",\"usage\":{\"input_tokens\":15,\"output_tokens\":25,\"unknown\":123}}");
    return 0;
  }
}
"""


class PlanTests(unittest.TestCase):
    def test_accepts_primitives_and_returns_independent_data(self):
        plan = copy.deepcopy(PLAN)
        for primitive in ("box", "sphere", "cylinder", "capsule", "torus"):
            plan["parts"][0]["primitive"] = primitive
            self.assertEqual(validate_plan(plan), plan)
        validated = validate_plan(plan)
        validated["parts"].clear()
        self.assertEqual(len(plan["parts"]), 1)

    def test_rejects_executable_fields_unknown_primitive_and_invalid_shape(self):
        invalid = []
        for extra in ("script", "file", "code"):
            plan = copy.deepcopy(PLAN)
            plan[extra] = "print('not executed')"
            invalid.append(plan)
        for field, value in (
            ("primitive", "script"),
            ("position", [0, 0]),
            ("size", [0, 1, 1]),
            ("color", [1, 1, 1, 2]),
            ("rotation_degrees", [0, 0, 4000]),
        ):
            plan = copy.deepcopy(PLAN)
            plan["parts"][0][field] = value
            invalid.append(plan)
        for plan in invalid:
            with self.subTest(plan=plan), self.assertRaisesRegex(ValueError, "plan_invalid"):
                validate_plan(plan)

    def test_rejects_nonfinite_and_bool_numbers(self):
        for value in (True, False, float("nan"), float("inf"), -float("inf")):
            plan = copy.deepcopy(PLAN)
            plan["parts"][0]["position"][0] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "plan_invalid"):
                validate_plan(plan)

    def test_rejects_names_and_duplicate_or_unbounded_parts(self):
        for name in (
            "../x",
            "script.gd",
            "a/b",
            "a\\b",
            "a:b",
            "a@b",
            "a%b",
            'a"b',
            "a\x7fb",
            "a\nb",
            "  x",
            "",
            "x" * 81,
        ):
            plan = copy.deepcopy(PLAN)
            plan["parts"][0]["name"] = name
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "plan_invalid"):
                validate_plan(plan)
        for count in (0, 2, 65):
            plan = copy.deepcopy(PLAN)
            plan["parts"] *= count
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, "plan_invalid"):
                validate_plan(plan)

    def test_schema_is_closed_at_each_object_boundary(self):
        schema = modeling_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["properties"]["parts"]["items"]["additionalProperties"])
        self.assertEqual(schema["properties"]["parts"]["maxItems"], 64)

    def test_rejects_empty_glb_header_instead_of_reporting_mesh_success(self):
        import struct

        data = json.dumps({"asset": {"version": "2.0"}}).encode()
        data += b" " * ((-len(data)) % 4)
        glb = b"glTF" + struct.pack("<IIII", 2, 20 + len(data), len(data), 0x4E4F534A) + data
        with self.assertRaisesRegex(ValueError, "mesh_invalid"):
            validate_mesh(glb)


@unittest.skipUnless(os.name == "nt", "Synthetic CLI fixture is a Windows executable")
class ModelingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix="modeling-cli-fixture-")
        cls.exe = Path(cls.build.name) / "fake-modeling.exe"
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
        self.tmp = tempfile.TemporaryDirectory(prefix="modeling-provider-")
        self.directory = Path(self.tmp.name)
        self.fake = self.directory / "fake-modeling.exe"
        shutil.copy2(self.exe, self.fake)
        (self.directory / "plan.json").write_text(json.dumps(PLAN), encoding="utf-8")
        self.config = dict(
            cli_path=str(self.fake),
            storage=str(self.directory / "state"),
            godot_path=str(GODOT if GODOT.is_file() else self.fake),
            builder_path=str(BUILDER),
        )
        self.provider = ModelingProvider(self.config)
        self.request = dict(
            node="text_to_mesh", version="1", inputs={}, parameters={"prompt": "a simple table"}, context=[]
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

    def wait(self, key=KEY):
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            result = self.provider.poll(key)
            if result["state"] in ("succeeded", "failed", "cancelled"):
                return result
            time.sleep(0.05)
        self.fail("modeling worker did not finish")

    def wait_started(self):
        deadline = time.monotonic() + 10
        while not (self.directory / "started").exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue((self.directory / "started").is_file())

    def test_modeling_check_needs_login_not_imagegen(self):
        report = check_modeling_cli(str(self.fake))
        self.assertTrue(report["connected"])
        self.assertEqual(report["auth_mode"], "chatgpt")
        self.mode("no-login")
        self.assertEqual(check_modeling_cli(str(self.fake))["code"], "cli_login_required")

    @unittest.skipUnless(GODOT.is_file() and BUILDER.is_file(), "Real Godot and fixed builder required")
    def test_real_builder_end_to_end_manifest_recovery_and_idempotency(self):
        self.provider.submit(self.request, self.manifest, KEY)
        self.assertEqual(self.wait()["state"], "succeeded")
        result = self.provider.result_manifest(KEY)
        self.assertEqual(result["artifacts"][0]["type"], "mesh")
        registry = NodeRegistry()
        register(registry)
        validate_outputs(registry, "text_to_mesh", "1", self.provider.poll(KEY)["outputs"], result)
        check_content(result)
        payload = result["artifacts"][0]["payload"]
        geometry = validate_mesh(base64.b64decode(payload["content_base64"]))
        self.assertGreater(geometry["vertices"], 3)
        self.assertFalse(payload["provenance"]["generated_code_executed"])
        self.assertNotIn(str(self.directory), json.dumps(result))
        receipt = payload["provenance"]["instruction_receipt"]
        self.assertEqual(receipt["cli_turn_usage"], dict(input_tokens=15, output_tokens=25))
        reopened = ModelingProvider(self.config)
        self.assertEqual(reopened.submit(self.request, self.manifest, KEY)["state"], "succeeded")
        self.assertEqual((self.directory / "runs").read_text().count("run"), 1)
        self.assertEqual(reopened.cancel(KEY)["state"], "succeeded")
        self.assertEqual(reopened.result_manifest(KEY), result)
        arguments = (self.directory / "args").read_text()
        self.assertIn("--output-schema", arguments)
        self.assertIn("features.image_generation=false", arguments)
        self.assertIn("features.shell_tool=false", arguments)

    def test_changed_request_for_existing_intent_refuses_replay(self):
        self.mode("block")
        self.provider.submit(self.request, self.manifest, KEY)
        changed = copy.deepcopy(self.request)
        changed["parameters"]["prompt"] = "changed"
        with self.assertRaisesRegex(ValueError, "idempotency conflict"):
            self.provider.submit(changed, self.manifest, KEY)

    def test_cancellation_is_durable_and_stops_owned_worker(self):
        self.mode("block")
        self.provider.submit(self.request, self.manifest, KEY)
        self.wait_started()
        self.assertEqual(self.provider.cancel(KEY)["state"], "cancelled")
        self.assertEqual(self.wait()["state"], "cancelled")
        self.assertEqual(ModelingProvider(self.config).submit(self.request, self.manifest, KEY)["state"], "cancelled")
        with self.assertRaisesRegex(ValueError, "result not available"):
            self.provider.result_manifest(KEY)

    def test_stale_worker_intent_becomes_unknown_without_new_cli_execution(self):
        record = dict(
            request=self.request,
            manifest=self.manifest,
            fingerprint=self.provider.fingerprint,
            created=0,
            heartbeat=0,
            stage="cli",
        )
        with self.provider.db() as db:
            db.execute("INSERT INTO jobs VALUES(?,?)", (KEY, json.dumps(record)))
        result = self.provider.submit(self.request, self.manifest, KEY)
        self.assertEqual(result["state"], "failed")
        self.assertIn("回执不明", result["error"])
        self.assertFalse((self.directory / "runs").exists())

    def test_failure_or_incomplete_turn_never_publishes(self):
        for index, mode in enumerate(("fail", "no-output", "no-turn", "tool")):
            self.mode(mode)
            key = format(index + 1, "064x")
            self.provider.submit(self.request, self.manifest, key)
            self.assertEqual(self.wait(key)["state"], "failed", mode)
            with self.assertRaisesRegex(ValueError, "result not available"):
                self.provider.result_manifest(key)

    def test_invalid_model_generated_plan_never_reaches_builder(self):
        plan = copy.deepcopy(PLAN)
        plan["parts"][0]["script"] = "forbidden"
        (self.directory / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
        self.provider.submit(self.request, self.manifest, KEY)
        result = self.wait()
        self.assertEqual(result["state"], "failed")
        self.assertIn("建模指令", result["error"])
        self.assertFalse((self.directory / "state" / KEY / "builder.stdout").exists())

    def test_source_context_preserves_constraints_and_rejects_multiple_images(self):
        request = copy.deepcopy(self.request)
        request["context"] = [dict(role="instruction", scope="node", strength="constraint", text="four legs")]
        self.assertIn("four legs", self.provider.plan(request, self.manifest)["prompt"])
        request["context"].append(
            dict(role="reference", scope="node", strength="reference", artifact={"id": "a", "revision": "1"})
        )
        request["context"].append(
            dict(role="reference", scope="node", strength="reference", artifact={"id": "b", "revision": "2"})
        )
        with self.assertRaisesRegex(ValueError, "unsupported_multiple_image_constraints"):
            self.provider.plan(request, self.manifest)


if __name__ == "__main__":
    unittest.main()
