"""GUI configuration infrastructure with read-only HTTP fixtures; never model inference."""

import json
import os
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from generation_service import IMAGE_NODES, MESH_NODES


@unittest.skipUnless(os.environ.get("AINATIVE_GUI_TEST_GODOT"), "explicit Godot test binary required")
class ServiceGuiTests(unittest.TestCase):
    def test_settings_transport_and_offline_copy(self):
        with tempfile.TemporaryDirectory(prefix="maliang-service-gui-") as temporary:
            folder = Path(temporary)
            traffic_file = folder / "traffic.json"
            traffic_file.write_text("[]")
            traffic = []
            lock = threading.Lock()
            servers = []
            threads = []
            info = {key: {} for key in IMAGE_NODES | MESH_NODES | {"ImageScale", "VAEEncode"}}
            info["CheckpointLoaderSimple"] = {
                "input": {"required": {"ckpt_name": [["fixture-image.safetensors", "fixture-image-other.safetensors"]]}}
            }
            info["ImageOnlyCheckpointLoader"] = {
                "input": {"required": {"ckpt_name": [["fixture-mesh.safetensors", "fixture-mesh-other.safetensors"]]}}
            }

            def start(kind):
                object_calls = [0]

                class Handler(BaseHTTPRequestHandler):
                    def log_message(self, *args):
                        pass

                    def track(self, method):
                        with lock:
                            traffic.append(dict(method=method, path=self.path, fixture=kind))
                            pending = traffic_file.with_suffix(".tmp")
                            pending.write_text(json.dumps(traffic))
                            pending.replace(traffic_file)

                    def do_GET(self):
                        self.track("GET")
                        if self.path == "/object_info":
                            object_calls[0] += 1
                            if kind == "stops" and object_calls[0] > 2:
                                self.send_response(503)
                                self.end_headers()
                                self.wfile.write(b"{}")
                                return
                        if kind == "slow" and self.path == "/object_info":
                            time.sleep(0.4)
                        if self.path == "/system_stats":
                            value = {"system": {"comfyui_version": "read-only-ui-test-fixture"}}
                        elif kind == "protocol":
                            value = {"unrelated_fixture": True}
                        elif kind == "missing":
                            value = {key: {} for key in info}
                            value["CheckpointLoaderSimple"] = {"input": {"required": {"ckpt_name": [[]]}}}
                            value["ImageOnlyCheckpointLoader"] = {"input": {"required": {"ckpt_name": [[]]}}}
                        else:
                            value = info
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(json.dumps(value).encode())

                    def do_POST(self):
                        self.track("POST")
                        self.send_response(405)
                        self.end_headers()

                server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                servers.append(server)
                threads.append(thread)
                return "http://127.0.0.1:" + str(server.server_port)

            env = dict(os.environ)
            env.pop("AINATIVE_PROVIDER_FACTORY", None)
            env.pop("AINATIVE_COMFY_CONFIG", None)
            env["AINATIVE_SERVICE_TEST_ENDPOINT"] = start("valid")
            env["AINATIVE_SERVICE_TEST_SLOW_ENDPOINT"] = start("slow")
            env["AINATIVE_SERVICE_TEST_MISSING_ENDPOINT"] = start("missing")
            env["AINATIVE_SERVICE_TEST_PROTOCOL_ENDPOINT"] = start("protocol")
            env["AINATIVE_SERVICE_TEST_STOPS_ENDPOINT"] = start("stops")
            env["AINATIVE_SERVICE_TEST_TRAFFIC"] = str(traffic_file)
            receipt = Path(env.get("AINATIVE_SERVICE_GUI_REPORT", str(folder / "report.json")))
            env["AINATIVE_SERVICE_GUI_REPORT"] = str(receipt)
            root = Path(__file__).resolve().parents[2]
            try:
                result = subprocess.run(
                    [
                        env["AINATIVE_GUI_TEST_GODOT"],
                        "--headless",
                        "--path",
                        str(root / "samples/ainative-workbench"),
                        "--script",
                        "generation_service_acceptance.gd",
                    ],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                log = result.stdout + result.stderr
                if os.environ.get("AINATIVE_SERVICE_GUI_LOG"):
                    Path(os.environ["AINATIVE_SERVICE_GUI_LOG"]).write_text(log)
                self.assertEqual(result.returncode, 0, log[-16000:])
                self.assertNotIn("SCRIPT ERROR:", log)
                report = json.loads(receipt.read_text())
                self.assertTrue(report["ok"], log)
                self.assertGreaterEqual(len(report["checks"]), 40)
                self.assertTrue(traffic)
                self.assertTrue(all(call["method"] == "GET" for call in traffic), traffic)
                self.assertFalse(any(call["path"] in ("/prompt", "/upload/image") for call in traffic), traffic)
            finally:
                for server in servers:
                    server.shutdown()
                    server.server_close()
                for thread in threads:
                    thread.join()


if __name__ == "__main__":
    unittest.main()
