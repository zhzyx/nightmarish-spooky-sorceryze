"""Synthetic CLI/process + real localhost HTTP tests. These are not inference acceptance.

The Windows fake is a tiny compiled C# executable with no network/model calls.
It creates clearly synthetic 2x2 PNGs in a temporary CODEX_HOME, matching CLI's
documented on-disk thread layout. It is never installed as the real Codex CLI.
"""

import base64
import copy
import hashlib
import json
import os
import shutil
import struct
import subprocess
import tempfile
import threading
import time
import unittest
import zlib
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from codex_provider import _WORKERS, MESSAGES, CodexProvider, _environment, check_cli, validate_png
from comfy_provider import register
from editor_host import compile_graph
from executor import Executor, check_content
from extensions import NodeRegistry, validate_outputs

KEY = "a" * 64
PRIVATE = Path(__file__).resolve().parents[2] / "runtime" / "comfy-integrated"


def png(rgb=b"\x21\x42\x63"):
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress((b"\0" + rgb * 2) * 2))
        + chunk(b"IEND", b"")
    )


PNG = png()
GLB_JSON = json.dumps({"asset": {"version": "2.0"}}).encode()
GLB_JSON += b" " * ((-len(GLB_JSON)) % 4)
GLB = b"glTF" + struct.pack("<IIII", 2, 20 + len(GLB_JSON), len(GLB_JSON), 0x4E4F534A) + GLB_JSON


FAKE_CS = r"""
using System;
using System.IO;
using System.Threading;
class FakeCli {
  static int Main(string[] args) {
    Console.InputEncoding=System.Text.Encoding.UTF8;
    string home=Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location);
    string mode=File.Exists(Path.Combine(home,"mode"))?File.ReadAllText(Path.Combine(home,"mode")).Trim():"ok";
    if(Array.IndexOf(args,"--version")>=0) {Console.WriteLine("codex 0.166.0-alpha.6"); return 0;}
    if(Array.IndexOf(args,"login")>=0) {Console.WriteLine(mode=="no-login"?"Not logged in":"Logged in using ChatGPT"); return mode=="no-login"?1:0;}
    if(Array.IndexOf(args,"features")>=0) {Console.WriteLine("image_generation stable "+(mode=="no-image"?"false":"true")); return 0;}
    File.AppendAllText(Path.Combine(home,"runs"),"run\n");
    File.WriteAllText(Path.Combine(home,"args"),String.Join("\n",args));
    string prompt=Console.In.ReadToEnd();
    File.WriteAllText(Path.Combine(home,"prompt"),prompt);
    string thread=mode=="existing"?"00000000-0000-0000-0000-000000000000":Guid.NewGuid().ToString();
    Console.WriteLine("{\"type\":\"thread.started\",\"thread_id\":\""+thread+"\"}"); Console.Out.Flush();
    File.WriteAllText(Path.Combine(home,"started"),thread);
    if(mode=="block") Thread.Sleep(30000);
    if(mode=="fail") {Console.WriteLine("{\"type\":\"turn.failed\"}"); return 2;}
    if(mode!="no-output") {
      string root=Path.Combine(Environment.GetEnvironmentVariable("CODEX_HOME"),"generated_images",mode=="wrong-thread"?Guid.NewGuid().ToString():thread);
      Directory.CreateDirectory(root);
      byte[] data=Convert.FromBase64String("__PNG__");
      if(mode=="corrupt") data[data.Length-1]^=1;
      string output=Path.Combine(root,"exec-fixture.png");
      File.WriteAllBytes(output,data);
      if(mode=="old") File.SetLastWriteTimeUtc(output,DateTime.UtcNow.AddDays(-1));
      if(mode=="multiple") File.WriteAllBytes(Path.Combine(root,"exec-fixture-2.png"),data);
    }
    Console.WriteLine("{\"type\":\"item.completed\",\"item\":{\"type\":\"agent_message\",\"text\":\"fixture success text is not evidence\"}}");
    Console.WriteLine("{\"type\":\"turn.completed\",\"usage\":{\"input_tokens\":123,\"output_tokens\":7,\"unknown_field\":999}}"); return 0;
  }
}
"""


@unittest.skipUnless(os.name == "nt", "fixture executable targets Windows host")
class CodexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        PRIVATE.mkdir(parents=True, exist_ok=True)
        cls.build = tempfile.TemporaryDirectory(prefix="codex-fixture-build-", dir=PRIVATE)
        cls.exe = Path(cls.build.name) / "fake-codex.exe"
        source = cls.exe.with_suffix(".cs")
        source.write_text(FAKE_CS.replace("__PNG__", base64.b64encode(PNG).decode()), encoding="utf-8")
        compiler = Path(os.environ.get("WINDIR", "C:/Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
        if not compiler.is_file():
            raise unittest.SkipTest("Windows C# fixture compiler unavailable")
        subprocess.run([str(compiler), "/nologo", "/out:" + str(cls.exe), str(source)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="codex-provider-test-", dir=PRIVATE)
        self.directory = Path(self.tmp.name)
        self.fake = self.directory / "fake-codex.exe"
        shutil.copyfile(self.exe, self.fake)
        self.environment = patch.dict(os.environ, {"CODEX_HOME": str(self.directory / "cli-home")})
        self.environment.start()
        self.config = dict(cli_path=str(self.fake), storage=str(self.directory / "state"), mesh_config=None)
        self.p = CodexProvider(self.config)
        self.request = dict(
            node="text_to_image", version="1", inputs={}, parameters={"prompt": "a synthetic fixture"}, context=[]
        )
        self.manifest = dict(schema_version=1, artifacts=[])
        self.server = None

    def tearDown(self):
        # Cancel through durable state; the owned worker terminates only its child.
        with self.p.db() as db:
            keys = [row[0] for row in db.execute("SELECT key FROM jobs")]
        for key in keys:
            self.p.cancel(key)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and any(p.poll() is None for p in _WORKERS):
            time.sleep(0.1)
        for process in _WORKERS:
            process.poll()
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.http_thread.join()
        self.environment.stop()
        self.tmp.cleanup()

    def mode(self, value):
        (self.directory / "mode").write_text(value)

    def wait(self, key=KEY):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            result = self.p.poll(key)
            if result["state"] in ("succeeded", "failed", "cancelled"):
                return result
            time.sleep(0.05)
        self.fail("worker did not complete: " + str(self.p.read(key)))

    def wait_started(self):
        deadline = time.monotonic() + 10
        while not (self.directory / "started").exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue((self.directory / "started").exists())

    def image(self):
        data = png(b"\x11\x22\x33")
        sha = hashlib.sha256(data).hexdigest()
        return dict(
            id="input",
            revision=sha,
            type="image",
            payload=dict(content_base64=base64.b64encode(data).decode(), content_sha256=sha, extension=".png"),
        )

    def mesh_server(self):
        self.posts = []
        self.history = {}
        self.pending = []
        self.mesh_fail = False
        self.mesh_hold = False
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def send(self, value, raw=False):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(value if raw else json.dumps(value).encode())

            def do_GET(self):
                if self.path == "/queue":
                    self.send(dict(queue_pending=owner.pending, queue_running=[]))
                elif self.path.startswith("/history"):
                    self.send(owner.history)
                elif self.path.startswith("/view?"):
                    self.send(GLB, raw=True)

            def do_POST(self):
                data = self.rfile.read(int(self.headers["Content-Length"]))
                if self.path == "/upload/image":
                    import re

                    owner.uploaded = data
                    self.send(dict(name=re.search(b'filename="([^"]+)"', data)[1].decode(), subfolder=""))
                    return
                obj = json.loads(data)
                owner.posts.append((self.path, obj))
                if self.path == "/prompt":
                    graph = obj["prompt"]
                    receipt = [0, "remote", graph, obj["extra_data"], ["output"]]
                    owner.pending = [receipt]
                    owner.history = {
                        "remote": dict(
                            prompt=receipt,
                            status=dict(completed=True, status_str="success"),
                            outputs={
                                "output": {
                                    "mesh": [
                                        dict(
                                            filename=obj["extra_data"]["ainative_key"] + "_00001_.glb",
                                            subfolder="ainative",
                                            type="output",
                                        )
                                    ]
                                }
                            },
                        )
                    }
                    if owner.mesh_fail:
                        owner.history["remote"]["status"] = dict(completed=False, status_str="error")
                    if owner.mesh_hold:
                        owner.history = {}
                    self.send(dict(prompt_id="remote"))
                elif self.path == "/queue":
                    owner.pending = []
                    self.send({})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.http_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.http_thread.start()
        self.config["mesh_config"] = dict(
            endpoint="http://127.0.0.1:" + str(self.server.server_port),
            storage=str(self.directory / "mesh-state"),
            checkpoints={role: dict(name=role + ".safetensors", sha256="b" * 64) for role in ("image", "mesh")},
            backend_revision="synthetic-http-fixture",
        )
        self.p = CodexProvider(self.config)

    def test_check_is_read_only_and_fixed_safe_status(self):
        report = check_cli(str(self.fake))
        self.assertTrue(report["connected"])
        self.assertEqual(report["auth_mode"], "chatgpt")
        self.assertFalse((self.directory / "runs").exists())
        for mode, code in (("no-login", "cli_login_required"), ("no-image", "cli_image_unavailable")):
            self.mode(mode)
            self.assertEqual(check_cli(str(self.fake))["code"], code)
        self.assertEqual(check_cli(str(self.fake) + "missing")["code"], "cli_missing")

    def test_success_reopen_provenance_and_cli_restrictions(self):
        self.p.submit(self.request, self.manifest, KEY)
        result = self.wait()
        self.assertEqual(result["state"], "succeeded")
        reopened = CodexProvider(self.config)
        self.assertEqual(reopened.poll(KEY), result)
        manifest = reopened.result_manifest(KEY)
        registry = NodeRegistry()
        register(registry)
        validate_outputs(registry, "text_to_image", "1", result["outputs"], manifest)
        payload = manifest["artifacts"][0]["payload"]
        self.assertEqual(base64.b64decode(payload["content_base64"]), PNG)
        provenance = payload["provenance"]
        self.assertEqual(provenance["cli_turn_usage"], dict(input_tokens=123, output_tokens=7))
        self.assertIsNone(provenance["image_cost"])
        self.assertFalse(provenance["native_image_tool_event_available"])
        self.assertNotIn(str(self.directory), json.dumps(provenance))
        args = (self.directory / "args").read_text()
        for expected in (
            "--no-daemon",
            "--ignore-user-config",
            "read-only",
            "features.shell_tool=false",
            "features.plugins=false",
            'forced_login_method="chatgpt"',
            "features.code_mode_host=true",
        ):
            self.assertIn(expected, args)
        self.assertNotIn("features.code_mode_host=false", args)
        self.assertNotIn("model_providers.openai.supports_websockets", args)
        self.assertFalse(provenance["requested_cli_policy"]["actual_tool_catalog_verified"])
        self.p.submit(self.request, self.manifest, KEY)
        self.assertEqual((self.directory / "runs").read_text().count("run"), 1)

    def test_selected_model_is_an_explicit_optional_cli_argument(self):
        self.p.submit(self.request, self.manifest, KEY)
        self.assertEqual(self.wait()["state"], "succeeded")
        self.assertNotIn("--model", (self.directory / "args").read_text().splitlines())
        self.config["model"] = "fixture-codex-model"
        self.p = CodexProvider(self.config)
        key = "b" * 64
        self.p.submit(self.request, self.manifest, key)
        self.assertEqual(self.wait(key)["state"], "succeeded")
        arguments = (self.directory / "args").read_text().splitlines()
        self.assertEqual(arguments[arguments.index("--model") + 1], "fixture-codex-model")

    def test_refuses_bad_old_foreign_ambiguous_or_missing_png(self):
        for index, mode in enumerate(("old", "wrong-thread", "corrupt", "multiple", "no-output", "existing")):
            with self.subTest(mode=mode):
                self.mode(mode)
                if mode == "existing":
                    (self.directory / "cli-home/generated_images/00000000-0000-0000-0000-000000000000").mkdir(
                        parents=True
                    )
                key = hashlib.sha256(str(index).encode()).hexdigest()
                self.p.submit(self.request, self.manifest, key)
                result = self.wait(key)
                self.assertEqual(result["state"], "failed")
                self.assertEqual(result["error"], MESSAGES["cli_output_invalid"])
                with self.assertRaises(ValueError):
                    self.p.result_manifest(key)

    def test_failure_has_no_retry(self):
        self.mode("fail")
        self.p.submit(self.request, self.manifest, KEY)
        self.assertEqual(self.wait()["error"], MESSAGES["cli_execution_failed"])
        CodexProvider(self.config).submit(self.request, self.manifest, KEY)
        self.assertEqual((self.directory / "runs").read_text().count("run"), 1)

    def test_concurrent_intent_launches_one_cli(self):
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(lambda _: self.p.submit(self.request, self.manifest, KEY), range(5)))
        self.assertTrue(all(item["job_id"] == KEY for item in results))
        self.assertEqual(self.wait()["state"], "succeeded")
        self.assertEqual((self.directory / "runs").read_text().count("run"), 1)
        conflict = copy.deepcopy(self.request)
        conflict["parameters"]["prompt"] += " changed"
        with self.assertRaisesRegex(ValueError, "idempotency conflict"):
            self.p.submit(conflict, self.manifest, KEY)

    def test_cancel_after_reopen_stops_owned_process_and_late_write(self):
        self.mode("block")
        self.p.submit(self.request, self.manifest, KEY)
        self.wait_started()
        reopened = CodexProvider(self.config)
        cancelled = reopened.cancel(KEY)
        self.assertEqual(cancelled["state"], "cancelled")
        late = reopened.finish(KEY, "failed", "cli_execution_failed")
        self.assertEqual(late, cancelled)
        late_result = dict(schema_version=1, artifacts=[self.image()])
        self.assertEqual(reopened.finish(KEY, "succeeded", result=late_result), cancelled)
        for process in _WORKERS:
            process.wait(timeout=8)
        self.assertFalse(list((self.directory / "cli-home").rglob("*.png")))
        self.assertEqual(reopened.poll(KEY), cancelled)
        with self.assertRaises(ValueError):
            reopened.result_manifest(KEY)

    def test_abandoned_intent_is_unknown_never_replayed(self):
        record = dict(
            request=self.request,
            manifest=self.manifest,
            fingerprint=self.p.fingerprint,
            created=0,
            heartbeat=0,
            stage="intent",
        )
        with self.p.db() as db:
            db.execute("INSERT INTO jobs VALUES (?,?)", (KEY, json.dumps(record)))
        result = self.p.submit(self.request, self.manifest, KEY)
        self.assertEqual(result["error"], MESSAGES["cli_result_unknown"])
        self.assertFalse((self.directory / "runs").exists())

    def test_image_edit_consumes_snapshot_and_rejects_multiple_semantics(self):
        image = self.image()
        self.manifest["artifacts"] = [image]
        self.request.update(node="image_to_image", inputs={"source": {k: image[k] for k in ("id", "revision")}})
        self.p.submit(self.request, self.manifest, KEY)
        self.assertEqual(self.wait()["state"], "succeeded")
        snapshot = Path(self.config["storage"]) / KEY / "input.png"
        self.assertEqual(snapshot.read_bytes(), base64.b64decode(image["payload"]["content_base64"]))
        self.request["context"] = [
            dict(artifact=self.request["inputs"]["source"], role="reference", scope="node", strength="reference")
        ]
        self.assertEqual(
            self.p.submit(self.request, self.manifest, "b" * 64)["error"],
            MESSAGES["unsupported_multiple_image_constraints"],
        )
        self.request["context"] = [dict(text="instruction", role="instruction", scope="global", strength="constraint")]
        self.assertEqual(
            self.p.submit(self.request, self.manifest, "c" * 64)["error"], MESSAGES["unsupported_context_semantics"]
        )

    def test_gui_node_instruction_constraint_preserved_through_prompt(self):
        graph, manifest = compile_graph(
            dict(
                nodes=[
                    dict(
                        id="image",
                        type="text_to_image",
                        provider="codex",
                        parameters=dict(prompt="stone owl", seed=123, steps=7, denoise=0.4),
                        text="必须保留蓝色眼睛",
                    )
                ],
                edges=[],
            )
        )
        request = graph[0]["request"]
        expected = dict(text="必须保留蓝色眼睛", role="instruction", scope="node", strength="constraint")
        self.assertEqual(request["context"], [expected])
        plan = self.p.plan(request, manifest)
        self.assertEqual(plan["context"], [expected])
        self.p.submit(request, manifest, KEY)
        self.assertEqual(self.wait()["state"], "succeeded")
        prompt = (self.directory / "prompt").read_text(encoding="utf-8-sig")
        self.assertIn("natural-language constraints", prompt)
        data = json.loads(prompt.split("not permission to invoke other tools:\n", 1)[1])
        self.assertEqual(data["context"], [expected])
        provenance = self.p.result_manifest(KEY)["artifacts"][0]["payload"]["provenance"]
        self.assertEqual(provenance["context_semantics"], [{k: expected[k] for k in ("role", "scope", "strength")}])
        self.assertEqual(provenance["cli_controls_not_applied"], dict(seed=123, steps=7, denoise=0.4))
        self.assertEqual(provenance["unsupported_cli_controls"], ["seed", "steps", "denoise"])
        unsupported = copy.deepcopy(request)
        unsupported["context"][0]["scope"] = "global"
        with self.assertRaisesRegex(ValueError, "unsupported_context_semantics"):
            self.p.plan(unsupported, manifest)

    def test_mesh_is_local_only_and_missing_mesh_does_not_spend_cli(self):
        self.request["node"] = "text_to_mesh"
        self.assertEqual(self.p.submit(self.request, self.manifest, KEY)["error"], MESSAGES["mesh_service_missing"])
        self.assertFalse((self.directory / "runs").exists())
        self.mesh_server()
        bad = copy.deepcopy(self.config)
        bad["mesh_config"]["endpoint"] = "https://example.com"
        with self.assertRaisesRegex(ValueError, "loopback"):
            CodexProvider(bad)

    def test_text_to_mesh_keeps_both_stages_and_exact_bytes(self):
        self.mesh_server()
        self.request["node"] = "text_to_mesh"
        self.p.submit(self.request, self.manifest, KEY)
        result = self.wait()
        self.assertEqual(result["state"], "succeeded")
        artifacts = self.p.result_manifest(KEY)["artifacts"]
        self.assertEqual([a["type"] for a in artifacts], ["image", "mesh"])
        self.assertEqual(base64.b64decode(artifacts[0]["payload"]["content_base64"]), PNG)
        self.assertEqual(base64.b64decode(artifacts[1]["payload"]["content_base64"]), GLB)
        self.assertIn(PNG, self.uploaded)
        graph = next(obj["prompt"] for route, obj in self.posts if route == "/prompt")
        self.assertNotIn("image_model", graph)
        self.assertNotIn("positive", graph)
        self.assertEqual(graph["input"]["class_type"], "LoadImage")
        stages = artifacts[1]["payload"]["provenance"]["stages"]
        self.assertEqual([stage["stage"] for stage in stages], ["cli_image", "local_comfy_image_to_mesh"])
        self.assertEqual(
            [stage["artifact_sha256"] for stage in stages],
            [hashlib.sha256(PNG).hexdigest(), hashlib.sha256(GLB).hexdigest()],
        )
        check_content(self.p.result_manifest(KEY))

    def test_executor_consumes_direct_image_to_mesh_and_cli_to_mesh(self):
        self.mesh_server()
        registry = NodeRegistry()
        register(registry)
        for kind in ("image_to_mesh", "text_to_mesh"):
            with self.subTest(kind=kind):
                request = copy.deepcopy(self.request)
                request["node"] = kind
                manifest = dict(schema_version=1, artifacts=[])
                if kind == "image_to_mesh":
                    image = self.image()
                    manifest["artifacts"] = [image]
                    request["inputs"] = {"source": {k: image[k] for k in ("id", "revision")}}
                    request["parameters"] = {}
                host = Executor(self.directory / (kind + ".sqlite"), registry, {"codex": self.p})
                try:
                    rid = hashlib.md5(kind.encode(), usedforsecurity=False).hexdigest()
                    host.create([dict(id="mesh", provider="codex", request=request, links={})], manifest, rid)
                    deadline = time.monotonic() + 15
                    while time.monotonic() < deadline:
                        status = host.step(rid)
                        if status["nodes"]["mesh"]["state"] in ("succeeded", "failed"):
                            break
                        time.sleep(0.05)
                    self.assertEqual(status["nodes"]["mesh"]["state"], "succeeded", status)
                    run = host._read(rid)
                    output = run["nodes"]["mesh"]["result"]
                    check_content(output)
                    self.assertEqual(base64.b64decode(output["artifacts"][-1]["payload"]["content_base64"]), GLB)
                    self.assertGreater(host.db.execute("SELECT count(*) FROM assets").fetchone()[0], 0)
                    self.assertEqual(host.db.execute("SELECT count(*) FROM cache").fetchone()[0], 1)
                    self.assertIsNone(status["nodes"]["mesh"]["error"])
                finally:
                    host.close()

    def test_image_to_mesh_without_prompt_never_calls_cli(self):
        self.mesh_server()
        image = self.image()
        self.manifest["artifacts"] = [image]
        self.request.update(
            node="image_to_mesh", parameters={}, inputs={"source": {k: image[k] for k in ("id", "revision")}}
        )
        self.p.submit(self.request, self.manifest, KEY)
        self.assertEqual(self.wait()["state"], "succeeded")
        self.assertFalse((self.directory / "runs").exists())
        self.assertEqual([a["type"] for a in self.p.result_manifest(KEY)["artifacts"]], ["mesh"])

    def test_image_to_mesh_prompt_edits_before_local_mesh(self):
        self.mesh_server()
        image = self.image()
        self.manifest["artifacts"] = [image]
        self.request.update(node="image_to_mesh", inputs={"source": {k: image[k] for k in ("id", "revision")}})
        self.p.submit(self.request, self.manifest, KEY)
        self.assertEqual(self.wait()["state"], "succeeded")
        self.assertEqual((self.directory / "runs").read_text().count("run"), 1)
        self.assertIn(PNG, self.uploaded)
        self.assertNotIn(base64.b64decode(image["payload"]["content_base64"]), self.uploaded)
        self.assertEqual(
            self.p.result_manifest(KEY)["artifacts"][0]["payload"]["provenance"]["source_sha256"], image["revision"]
        )

    def test_mesh_failure_preserves_actual_image_stage(self):
        self.mesh_server()
        self.mesh_fail = True
        self.request["node"] = "text_to_mesh"
        self.p.submit(self.request, self.manifest, KEY)
        self.assertEqual(self.wait()["error"], MESSAGES["mesh_execution_failed"])
        private_image = self.p.read(KEY)["image_stage"]
        self.assertEqual(base64.b64decode(private_image["payload"]["content_base64"]), PNG)
        self.assertEqual(self.p.read(KEY)["stages"][0]["stage"], "cli_image")
        with self.assertRaises(ValueError):
            self.p.result_manifest(KEY)

    def test_cancel_mesh_only_deletes_owned_queue_never_interrupts(self):
        self.mesh_server()
        self.mesh_hold = True
        self.request["node"] = "text_to_mesh"
        self.p.submit(self.request, self.manifest, KEY)
        deadline = time.monotonic() + 10
        while not self.pending and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(self.pending)
        cancelled = CodexProvider(self.config).cancel(KEY)
        for worker in _WORKERS:
            worker.wait(timeout=8)
        self.assertEqual(self.p.poll(KEY), cancelled)
        self.assertEqual(self.posts[-1], ("/queue", {"delete": ["remote"]}))
        self.assertFalse(any(route == "/interrupt" for route, _ in self.posts))

    def test_unchanged_input_is_not_a_new_edit(self):
        sha = hashlib.sha256(PNG).hexdigest()
        image = dict(
            id="input",
            revision=sha,
            type="image",
            payload=dict(content_base64=base64.b64encode(PNG).decode(), content_sha256=sha, extension=".png"),
        )
        self.manifest["artifacts"] = [image]
        self.request.update(node="image_to_image", inputs={"source": {k: image[k] for k in ("id", "revision")}})
        self.p.submit(self.request, self.manifest, KEY)
        self.assertEqual(self.wait()["error"], MESSAGES["cli_output_invalid"])


class PngTests(unittest.TestCase):
    def test_environment_preserves_auth_location_without_parent_session_tools(self):
        with patch.dict(
            os.environ,
            {
                "CODEX_HOME": "existing-auth-home",
                "CODEX_MCP_NODE_PATH": "node-runtime",
                "CODEX_APP_TOOLS_PIPE_PATH": "parent-tools",
                "CODEX_THREAD_ID": "parent-thread",
                "CODEX_PERMISSION_PROFILE": "parent-permissions",
                "OPENAI_API_KEY": "fixture-key",
            },
        ):
            env = _environment()
        self.assertEqual(env["CODEX_HOME"], "existing-auth-home")
        self.assertEqual(env["CODEX_MCP_NODE_PATH"], "node-runtime")
        for name in ("CODEX_APP_TOOLS_PIPE_PATH", "CODEX_THREAD_ID", "CODEX_PERMISSION_PROFILE", "OPENAI_API_KEY"):
            self.assertNotIn(name, env)

    def test_decodes_png_and_rejects_signature_only_crc_or_trailing_data(self):
        self.assertEqual(validate_png(PNG), dict(width=2, height=2))
        for data in (b"\x89PNG\r\n\x1a\nfixture", PNG[:-1], PNG + b"trailing", PNG[:-1] + b"!"):
            with self.assertRaises(ValueError):
                validate_png(data)


if __name__ == "__main__":
    unittest.main()
