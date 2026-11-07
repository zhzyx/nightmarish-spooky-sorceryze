"""Real subprocess/HTTP regressions; no GPU, model inference or downloads.

All mutable fixtures live under runtime/comfy-integrated, never the user's
runtime. The fixture speaks the read-only Comfy discovery and queue protocol.
"""

import concurrent.futures
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import venv
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

import managed_comfy as managed

FIXTURE = r"""
import argparse, json, os, sys, threading, time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
parser=argparse.ArgumentParser()
parser.add_argument('--listen')
parser.add_argument('--port', type=int)
parser.add_argument('--base-directory')
parser.add_argument('--disable-auto-launch', action='store_true')
parser.add_argument('--disable-all-custom-nodes', action='store_true')
parser.add_argument('--offline', action='store_true')
parser.add_argument('--disable-partner-nodes', action='store_true')
parser.add_argument('--disable-api-nodes', action='store_true')
args=parser.parse_args()
root=Path(args.base_directory)
(root/'argv.json').write_text(json.dumps(sys.argv[1:]))
with open(root/'started', 'a') as stream: stream.write(str(os.getpid())+'\n')
if (root/'fail').exists(): raise SystemExit(17)
if (root/'delay').exists(): time.sleep(float((root/'delay').read_text()))
def monitor():
    while True:
        if (root/'crash').exists(): os._exit(23)
        time.sleep(.05)
threading.Thread(target=monitor, daemon=True).start()
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        routes={
          '/object_info': {
             'ImageOnlyCheckpointLoader': {'input': {'required': {'ckpt_name': [['mesh.safetensors']]}}}},
          '/system_stats': {'system': {'comfyui_version': 'fixture-local'}, 'devices': [{'name':'CPU fixture', 'type':'cpu'}]},
          '/queue': {'queue_running': [[1,'fixture']] if (root/'busy').exists() else [], 'queue_pending': []}}
        if self.path not in routes:
            self.send_error(404); return
        if (root/'unhealthy').exists():
            routes[self.path]={'protocol_not_ready': True}
        data=json.dumps(routes[self.path]).encode()
        self.send_response(200); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
ThreadingHTTPServer((args.listen,args.port), Handler).serve_forever()
"""


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class ManagedComfyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch = Path(__file__).resolve().parents[2] / "runtime/comfy-integrated"
        cls.scratch.mkdir(parents=True, exist_ok=True)
        cls.suite = tempfile.TemporaryDirectory(prefix="managed-tests-", dir=cls.scratch)
        cls.suite_path = Path(cls.suite.name)
        cls.python_home = cls.suite_path / "fixture-python"
        venv.EnvBuilder(with_pip=False).create(cls.python_home)
        cls.python = cls.python_home / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    @classmethod
    def tearDownClass(cls):
        # Supervisors retain terminal replies for two seconds, then close logs.
        time.sleep(2.5)
        cls.suite.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="case-", dir=self.suite_path)
        self.base = Path(self.directory.name)
        self.runtime = self.base / "runtime"
        self.runtime.mkdir()
        # A real venv, shared read-only by the fixture runtimes.
        if os.name == "nt":
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(self.runtime / "venv"), str(self.python_home)],
                check=True,
                capture_output=True,
            )
        else:
            (self.runtime / "venv").symlink_to(self.python_home, target_is_directory=True)
        (self.runtime / "ComfyUI-src").mkdir()
        (self.runtime / "ComfyUI-src/main.py").write_text(FIXTURE, encoding="utf-8")
        (self.runtime / "ComfyUI-src/comfy").mkdir()
        (self.runtime / "ComfyUI-src/comfy/cli_args.py").write_text(
            'parser.add_argument("--offline", action="store_true")\n'
            'parser.add_argument("--disable-partner-nodes", action="store_true")\n'
            'parser.add_argument("--disable-api-nodes", action="store_true")\n',
            encoding="utf-8",
        )
        (self.runtime / "models/checkpoints").mkdir(parents=True)
        (self.runtime / "models/checkpoints/mesh.safetensors").write_bytes(b"fixture only")
        self.port = free_port()
        self.config = dict(
            endpoint="http://127.0.0.1:" + str(self.port),
            checkpoints={"mesh": {"name": "mesh.safetensors"}},
            backend_revision="fixture",
        )
        self.config_path = self.runtime / "config.json"
        self.save_config()
        self.request = dict(
            runtime_root=str(self.runtime), state_dir=str(self.base / "state"), session_id="editor-a", timeout=10
        )
        self.external = []
        self.extra_servers = []

    def save_config(self):
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")

    def call(self, action, **kwargs):
        return managed.manage(dict(self.request, action=action, **kwargs))

    def wait_state(self, expected, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            reply = self.call("status", session_id="")
            if reply["state"] in expected:
                return reply
            time.sleep(0.1)
        self.fail(f"state did not reach {expected}: {reply!r}")

    def tearDown(self):
        (self.runtime / "busy").unlink(missing_ok=True)
        # Remove lease files without querying status/joining again.
        state = self.base / "state"
        if state.exists():
            for lease in state.glob("*/lease-*"):
                lease.unlink(missing_ok=True)
            deadline = time.monotonic() + 7
            while time.monotonic() < deadline:
                live = []
                for path in state.glob("*/instance.json"):
                    body = managed._read(path)
                    if body.get("state") not in managed.TERMINAL:
                        live.append(body)
                if not live:
                    break
                time.sleep(0.1)
        for child, stream in self.external:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=5)
            stream.close()
        for server in self.extra_servers:
            server.shutdown()
            server.server_close()
        # Windows supervisor logs may remain open for the terminal reply grace.
        time.sleep(2.2)
        self.directory.cleanup()

    def launch_external(self):
        stream = open(self.base / "external.log", "wb")
        child = subprocess.Popen(
            [
                str(self.python),
                str(self.runtime / "ComfyUI-src/main.py"),
                "--listen",
                "127.0.0.1",
                "--port",
                str(self.port),
                "--base-directory",
                str(self.runtime),
                "--disable-auto-launch",
            ],
            stdout=stream,
            stderr=stream,
            **managed._hidden(),
        )
        self.external.append((child, stream))
        deadline = time.monotonic() + 5
        config = managed._inspect(self.request)
        while time.monotonic() < deadline:
            if managed._probe(config)["connected"]:
                return child
            time.sleep(0.05)
        self.fail("external fixture failed")

    def test_inspect_and_private_override(self):
        before = hashlib.sha256(self.config_path.read_bytes()).hexdigest()
        receipt = self.call("inspect")
        self.assertTrue(receipt["ok"], receipt)
        self.assertFalse(receipt["connected"])
        self.assertEqual(receipt["mesh_model"], "mesh.safetensors")
        override = self.base / "isolated.json"
        override.write_text(json.dumps(dict(self.config, endpoint="http://127.0.0.1:" + str(free_port()))))
        other = self.call("inspect", config_path=str(override))
        self.assertTrue(other["ok"], other)
        self.assertNotEqual(other["endpoint"], receipt["endpoint"])
        self.assertEqual(before, hashlib.sha256(self.config_path.read_bytes()).hexdigest())

    def test_invalid_paths_models_addresses_and_deadline(self):
        self.assertEqual(self.call("inspect", runtime_root=str(self.base / "missing"))["code"], "runtime_invalid")
        for endpoint in (
            "https://127.0.0.1:8188",
            "http://example.com:8188",
            "http://0.0.0.0:8188",
            "http://127.0.0.1:8188/path",
            "http://127.0.0.1:8188?x=1",
            "http://u:p@127.0.0.1:8188",
            "http://127.0.0.1:99999",
        ):
            self.config["endpoint"] = endpoint
            self.save_config()
            self.assertEqual(self.call("inspect")["code"], "address_invalid", endpoint)
        self.config["endpoint"] = "http://127.0.0.1:" + str(self.port)
        self.config["checkpoints"]["mesh"]["name"] = "../private"
        self.save_config()
        self.assertEqual(self.call("inspect")["code"], "model_invalid")
        self.config["checkpoints"]["mesh"]["name"] = "missing.safetensors"
        self.save_config()
        self.assertEqual(self.call("start")["code"], "model_missing")

    def test_real_lifecycle_multiple_editors_and_release(self):
        receipt = self.call("start")
        self.assertTrue(receipt["ok"], receipt)
        self.assertEqual(receipt["state"], "running")
        self.assertTrue(receipt["owned"])
        argv = json.loads((self.runtime / "argv.json").read_text())
        self.assertIn("--disable-all-custom-nodes", argv)
        self.assertIn("--disable-auto-launch", argv)
        self.assertIn("--offline", argv)
        self.assertNotIn("--disable-api-nodes", argv)
        self.assertEqual(receipt["devices"][0]["type"], "cpu")
        lease_a = Path(receipt["lease_path"])
        self.assertTrue(lease_a.exists())
        second = self.call("start", session_id="editor-b")
        self.assertEqual(second["instance_id"], receipt["instance_id"])
        self.assertNotEqual(second["lease_path"], receipt["lease_path"])
        released = self.call("stop")
        self.assertEqual(released["state"], "shared")
        self.assertFalse(lease_a.exists())
        self.assertEqual(
            managed._listener_pid(receipt["endpoint"]), int((self.runtime / "started").read_text().strip())
        )
        self.call("release", session_id="editor-b")
        final = self.wait_state({"stopped"})
        self.assertFalse(final["connected"])
        # Windows may briefly complete a queued TCP handshake after the exact
        # listening process and its job have exited; no HTTP handler survives.
        deadline = time.monotonic() + 3
        while (
            managed._listener_pid(receipt["endpoint"]) is not None or managed._port_open(receipt["endpoint"])
        ) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertIsNone(managed._listener_pid(receipt["endpoint"]))
        self.assertFalse(managed._port_open(receipt["endpoint"]))

    def test_launch_command_offline_flag_compatibility(self):
        config = managed._inspect(self.request)
        cli = self.runtime / "ComfyUI-src/comfy/cli_args.py"
        for available, expected in (
            (["--offline", "--disable-partner-nodes", "--disable-api-nodes"], "--offline"),
            (["--disable-partner-nodes", "--disable-api-nodes"], "--disable-partner-nodes"),
            (["--disable-api-nodes"], "--disable-api-nodes"),
            ([], ""),
        ):
            with self.subTest(available=available):
                cli.write_text("\n".join('parser.add_argument("' + flag + '")' for flag in available), encoding="utf-8")
                command = managed._launch_command(config)
                self.assertIn("--disable-all-custom-nodes", command)
                self.assertIn("--disable-auto-launch", command)
                selected = [
                    flag for flag in ("--offline", "--disable-partner-nodes", "--disable-api-nodes") if flag in command
                ]
                self.assertEqual(selected, [expected] if expected else [])

    def test_concurrent_start_stop_has_one_process(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            replies = list(pool.map(lambda i: self.call("start", session_id="editor-" + str(i)), range(4)))
        self.assertTrue(all(reply["ok"] for reply in replies), replies)
        self.assertEqual(len({reply["instance_id"] for reply in replies}), 1)
        self.assertEqual(len((self.runtime / "started").read_text().splitlines()), 1)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda i: self.call("stop", session_id="editor-" + str(i)), range(4)))
        self.wait_state({"stopped"})

    def test_supervisor_lifetime_lock_survives_absent_callers(self):
        # Bypass caller operation.lock deliberately: two detached supervisors
        # race as though their original launching editors had already crashed.
        config = managed._inspect(self.request)
        folder = managed._private_state(self.request, config["endpoint"])
        processes = []
        for index in range(2):
            instance = str(index + 1) * 48
            launch_path = folder / ("race-" + str(index) + ".json")
            managed._write(
                launch_path,
                dict(
                    config=config,
                    session_id="lost-caller-" + str(index),
                    instance_id=instance,
                    token=str(index + 1) * 64,
                    folder=str(folder),
                    startup_timeout=8,
                ),
            )
            with open(folder / ("race-" + str(index) + ".log"), "ab") as stream:
                child = subprocess.Popen(
                    [sys.executable, str(Path(managed.__file__).resolve()), "--supervisor", str(launch_path)],
                    stdout=stream,
                    stderr=stream,
                    **managed._hidden(),
                )
            processes.append(child)
            managed._DETACHED_SUPERVISORS.append(child)
        receipt = self.wait_state({"running"})
        self.assertTrue(receipt["owned"], receipt)
        time.sleep(0.8)
        self.assertEqual(len((self.runtime / "started").read_text().splitlines()), 1)
        self.assertEqual(sum(child.poll() is None for child in processes), 1)
        reopened = self.call("start", session_id="reopened-editor")
        self.assertEqual(reopened["instance_id"], receipt["instance_id"])
        self.assertTrue(reopened["ok"], reopened)

    def test_recovered_starting_owner_keeps_full_startup_deadline(self):
        (self.runtime / "delay").write_text("4.5")
        config = managed._inspect(self.request)
        folder = managed._private_state(self.request, config["endpoint"])
        launch_path = folder / "recover-winner.json"
        managed._write(
            launch_path,
            dict(
                config=config,
                session_id="crashed-editor",
                instance_id="a" * 48,
                token="b" * 64,
                folder=str(folder),
                startup_timeout=10,
            ),
        )
        with open(folder / "recover-winner.log", "ab") as stream:
            child = subprocess.Popen(
                [sys.executable, str(Path(managed.__file__).resolve()), "--supervisor", str(launch_path)],
                stdout=stream,
                stderr=stream,
                **managed._hidden(),
            )
        managed._DETACHED_SUPERVISORS.append(child)
        deadline = time.monotonic() + 3
        while not (folder / "instance.json").is_file() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue((folder / "instance.json").is_file())
        original_read = managed._read
        skipped = False

        def simulate_unpublished_first_record(path):
            nonlocal skipped
            if Path(path).name == "instance.json" and not skipped:
                skipped = True
                raise FileNotFoundError("first caller died before initial publication")
            return original_read(path)

        with mock.patch.object(managed, "_read", side_effect=simulate_unpublished_first_record):
            receipt = self.call("start", session_id="reopened-editor")
        self.assertTrue(receipt["ok"], receipt)
        self.assertEqual(receipt["instance_id"], "a" * 48)
        self.assertEqual(len((self.runtime / "started").read_text().splitlines()), 1)

    def test_busy_queue_waits_and_never_interrupts(self):
        (self.runtime / "busy").touch()
        receipt = self.call("start")
        self.assertTrue(receipt["ok"], receipt)
        self.assertTrue(receipt["queue_busy"])
        self.assertEqual(self.call("release")["state"], "waiting_idle")
        time.sleep(0.8)
        current = self.call("status", session_id="")
        self.assertEqual(current["state"], "waiting_idle")
        self.assertTrue(current["owned"])
        (self.runtime / "busy").unlink()
        self.wait_state({"stopped"})

    def test_external_reuse_cannot_stop_external(self):
        child = self.launch_external()
        for action in ("start", "status", "stop", "release"):
            receipt = self.call(action)
            self.assertTrue(receipt["ok"], receipt)
            self.assertEqual(receipt["state"], "external")
            self.assertFalse(receipt["owned"])
            self.assertEqual(receipt["lease_path"], "")
            self.assertIsNone(child.poll())
        self.assertEqual(len((self.runtime / "started").read_text().splitlines()), 1)

    def test_unrelated_port_is_rejected(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"unrelated": true}')

        server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self.extra_servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        receipt = self.call("start")
        self.assertEqual(receipt["code"], "port_occupied", receipt)
        self.assertFalse((self.runtime / "started").exists())

    def test_slow_streamed_http_headers_obey_total_deadline(self):
        class SlowHandler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                try:
                    self.wfile.write(b"HTTP/1.1 200 OK\r\nX-Slow: ")
                    for _ in range(30):
                        self.wfile.write(b"x")
                        self.wfile.flush()
                        time.sleep(0.1)
                except OSError:
                    pass

            do_POST = do_GET

        server = ThreadingHTTPServer(("127.0.0.1", self.port), SlowHandler)
        self.extra_servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        before = time.monotonic()
        self.assertFalse(managed._probe(managed._inspect(self.request), timeout=0.3)["connected"])
        self.assertLess(time.monotonic() - before, 0.8)
        before = time.monotonic()
        receipt = self.call("start", timeout=1)
        self.assertFalse(receipt["ok"], receipt)
        self.assertEqual(receipt["code"], "port_occupied")
        self.assertLess(time.monotonic() - before, 1.5)
        folder = managed._private_state(self.request, self.config["endpoint"])
        managed._write(
            folder / "instance.json",
            dict(
                control_port=self.port,
                instance_id="slow-control",
                token="local-test",
                state="running",
                supervisor_pid=os.getpid(),
                supervisor_identity=managed._process_identity(os.getpid()),
            ),
        )
        before = time.monotonic()
        receipt = self.call("status", timeout=1)
        self.assertEqual(receipt["code"], "ownership_unknown", receipt)
        self.assertLess(time.monotonic() - before, 1.5)
        (folder / "instance.json").unlink()

    def test_listener_identity_matches_loopback_address(self):
        if not sys.platform.startswith(("win", "linux")):
            self.skipTest("native TCP table regression is exercised on Windows/Linux")
        with socket.socket() as first, socket.socket() as second:
            first.bind(("127.0.0.2", self.port))
            first.listen()
            self.assertIsNone(managed._listener_pid(self.config["endpoint"]))
            second.bind(("127.0.0.1", self.port))
            second.listen()
            self.assertEqual(managed._listener_pid(self.config["endpoint"]), os.getpid())

    def test_failure_and_unknown_exit_are_not_healthy(self):
        (self.runtime / "fail").touch()
        receipt = self.call("start")
        self.assertFalse(receipt["ok"], receipt)
        self.assertEqual(receipt["code"], "child_exited")
        self.assertFalse(receipt["connected"])
        (self.runtime / "fail").unlink()
        # Wait until terminal supervisor exits; next start must create a new owner.
        time.sleep(2.3)
        receipt = self.call("start")
        self.assertTrue(receipt["ok"], receipt)
        (self.runtime / "crash").touch()
        failed = self.wait_state({"failed"})
        self.assertEqual(failed["code"], "child_exited")
        self.assertFalse(failed["owned"])
        self.assertFalse(failed["connected"])

    def test_start_timeout_is_failure_and_reaps_exact_child(self):
        (self.runtime / "delay").write_text("8")
        started = time.monotonic()
        receipt = self.call("start", timeout=1)
        self.assertFalse(receipt["ok"], receipt)
        self.assertEqual(receipt["code"], "startup_timeout")
        self.assertLess(time.monotonic() - started, 5)
        self.wait_state({"failed", "stopped"})
        self.assertFalse(managed._port_open(self.config["endpoint"]))

    def test_bound_but_unhealthy_start_still_has_deadline(self):
        (self.runtime / "unhealthy").touch()
        receipt = self.call("start", timeout=1)
        self.assertFalse(receipt["ok"], receipt)
        self.assertEqual(receipt["code"], "startup_timeout")
        final = self.wait_state({"failed", "stopped"}, timeout=6)
        self.assertFalse(final["owned"])
        self.assertFalse(final["connected"])

    def test_health_loss_revokes_ready_and_can_recover(self):
        receipt = self.call("start")
        self.assertTrue(receipt["ok"], receipt)
        (self.runtime / "unhealthy").touch()
        lost = self.wait_state({"unknown"})
        self.assertFalse(lost["ok"])
        self.assertFalse(lost["connected"])
        self.assertTrue(lost["owned"])
        self.assertEqual(lost["code"], "service_unreachable")
        (self.runtime / "unhealthy").unlink()
        restored = self.wait_state({"running"})
        self.assertTrue(restored["ok"], restored)

    def test_unknown_supervisor_and_pid_reuse_never_kill(self):
        child = self.launch_external()
        folder = managed._private_state(self.request, self.config["endpoint"])
        record = dict(
            control_port=free_port(),
            instance_id="stale",
            token="stale",
            state="running",
            supervisor_pid=os.getpid(),
            supervisor_identity=managed._process_identity(os.getpid()),
            child_pid=child.pid,
        )
        managed._write(folder / "instance.json", record)
        receipt = self.call("stop")
        self.assertEqual(receipt["code"], "ownership_unknown", receipt)
        self.assertIsNone(child.poll())
        record["supervisor_identity"] = "reused-pid-has-different-creation-time"
        managed._write(folder / "instance.json", record)
        receipt = self.call("start")
        self.assertEqual(receipt["state"], "external", receipt)
        self.assertIsNone(child.poll())
        (folder / "instance.json").unlink()

    def test_same_port_different_config_does_not_join(self):
        receipt = self.call("start")
        self.assertTrue(receipt["ok"], receipt)
        override = self.base / "other-config.json"
        override.write_bytes(self.config_path.read_bytes())
        other = self.call("start", config_path=str(override), session_id="other-editor")
        self.assertEqual(other["code"], "instance_config_mismatch", other)
        self.assertFalse(other["ok"])
        self.assertEqual(self.call("status")["lease_count"], 1)

    def test_abandoned_editor_lease_expiry_reclaims_child(self):
        receipt = self.call("start")
        self.assertTrue(receipt["ok"], receipt)
        # Simulate an editor crash; never heartbeat or release this lease again.
        final = self.wait_state({"stopped"}, timeout=managed.LEASE_SECONDS + 5)
        self.assertFalse(final["owned"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
