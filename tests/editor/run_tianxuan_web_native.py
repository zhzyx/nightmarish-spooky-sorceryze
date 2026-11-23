"""Real headless Chrome + compiled native editor + unchanged Web + isolated API.

The native transport proxy deliberately drops TCP connections during one phase.
The Web endpoint uses a disposable TLS certificate; no desktop or user profile is used.
"""

import argparse
import hashlib
import json
import os
import secrets
import select
import shutil
import signal
import socket
import socketserver
import ssl
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

import uvicorn
from run_tianxuan_controller import ROOT, NativeStore, Tianxuan, copy_editor, create_app, sanitized_environment


class Forward(socketserver.BaseRequestHandler):
    def handle(self):
        if self.server.offline.exists():
            return
        try:
            with socket.create_connection(self.server.destination, timeout=2) as upstream:
                streams = [self.request, upstream]
                while not self.server.offline.exists():
                    readable, _, _ = select.select(streams, [], [], 0.05)
                    for stream in readable:
                        block = stream.recv(65536)
                        if not block:
                            return
                        streams[1 - streams.index(stream)].sendall(block)
        except OSError:
            pass


class Proxy(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def stop(process):
    if process is None or process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def exercise(directory, args, web_files):
    environment = {
        key: value
        for key, value in sanitized_environment(directory).items()
        if not key.startswith(("TIANXUAN_", "TX_", "NEXT_PUBLIC_TIANXUAN_"))
    }
    environment["PATH"] = str(args.node.parent) + os.pathsep + environment.get("PATH", os.defpath)
    environment["GONGGONG_WORKSPACE"] = ""
    workspace = directory / "web"
    workspace.mkdir()
    for name in web_files:
        source = ROOT / name
        destination = workspace / source.relative_to(ROOT / "apps/tianxuan")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    (workspace / "node_modules").symlink_to(ROOT / "apps/tianxuan/node_modules", target_is_directory=True)
    certificate, private_key = directory / "cert.pem", directory / "key.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=127.0.0.1",
            "-keyout",
            str(private_key),
            "-out",
            str(certificate),
        ],
        check=True,
        capture_output=True,
    )
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        web_port = reservation.getsockname()[1]
    web_origin = f"https://127.0.0.1:{web_port}"
    password = secrets.token_urlsafe(32)
    store = Tianxuan(str(directory / "domain.sqlite"))
    owner = store.register("Native Web fixture", "first@example.invalid", password)
    store.add_member(owner["user_id"], "second@example.invalid", password, role="editor")
    native_store = NativeStore(directory / "native.sqlite")
    project = directory / "project"
    project.mkdir()
    (project / "project.godot").write_text(
        'config_version=5\n[application]\nconfig/name="Native Web collaboration fixture"\n'
    )
    (project / "probe.gd").write_bytes(Path(__file__).with_name("tianxuan_web_native.gd").read_bytes())
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        editor = copy_editor(args.godot, directory / "engine")
    modes = {key: value for key, value in environment.items() if not key.startswith("TIANXUAN_")}
    modes.update(
        TIANXUAN_AUTH_MODE="accounts",
        TIANXUAN_REQUIRE_KEYS="0",
        TIANXUAN_TENANT_ID=owner["tenant_id"],
        TIANXUAN_PUBLIC_ORIGIN=web_origin,
    )
    web_process = native_process = browser_process = None
    with (
        patch.dict(os.environ, modes, clear=True),
        socket.socket() as service_socket,
        Proxy(("127.0.0.1", 0), Forward) as proxy,
    ):
        service_socket.bind(("127.0.0.1", 0))
        destination = service_socket.getsockname()
        api_origin = f"http://127.0.0.1:{destination[1]}"
        proxy.destination = destination
        proxy.offline = directory / "network.offline"
        proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
        proxy_thread.start()
        server = uvicorn.Server(
            uvicorn.Config(create_app(store, native_store=native_store), log_level="error", access_log=False)
        )
        server_thread = threading.Thread(target=server.run, kwargs={"sockets": [service_socket]}, daemon=True)
        server_thread.start()
        logs = {name: (directory / (name + ".log")).open("w+") for name in ("web", "native", "browser")}
        try:
            deadline = time.monotonic() + 20
            while not server.started:
                if not server_thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("Isolated API did not start")
                time.sleep(0.05)
            web_environment = {
                **environment,
                "TIANXUAN_API_ORIGIN": api_origin,
                "TIANXUAN_INTERNAL_API_BASE": api_origin,
                "NEXT_PUBLIC_TIANXUAN_API_BASE": api_origin,
                "TIANXUAN_REQUIRE_KEYS": "1",
                "NEXT_TELEMETRY_DISABLED": "1",
            }
            web_process = subprocess.Popen(
                [
                    str(args.node),
                    str(workspace / "node_modules/next/dist/bin/next"),
                    "dev",
                    "-H",
                    "127.0.0.1",
                    "-p",
                    str(web_port),
                    "--experimental-https",
                    "--experimental-https-key",
                    str(private_key),
                    "--experimental-https-cert",
                    str(certificate),
                ],
                cwd=workspace,
                env=web_environment,
                stdout=logs["web"],
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            deadline = time.monotonic() + 120
            while True:
                if web_process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Isolated HTTPS Web server did not start")
                try:
                    with urlopen(
                        web_origin + "/login", context=ssl._create_unverified_context(), timeout=2
                    ) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.1)
            common = {
                **environment,
                "TX_PASSWORD": password,
                "TX_STATE": str(directory / "state.json"),
                "TX_COMMAND": str(directory / "command.json"),
                "TX_NETWORK_DOWN": str(proxy.offline),
            }
            native_environment = {**common, "TIANXUAN_API": f"http://127.0.0.1:{proxy.server_address[1]}"}
            native_process = subprocess.Popen(
                [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                cwd=directory,
                env=native_environment,
                stdout=logs["native"],
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            browser_environment = {
                **common,
                "TX_WEB": web_origin,
                "TX_CHROME": str(args.chrome),
                "TX_CHROME_PROFILE": str(directory / "chrome-profile"),
            }
            browser_process = subprocess.Popen(
                [str(args.node), str(Path(__file__).with_name("tianxuan_web_browser.mjs"))],
                cwd=directory,
                env=browser_environment,
                stdout=logs["browser"],
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            deadline = time.monotonic() + 240
            while native_process.poll() is None or browser_process.poll() is None:
                if native_process.poll() not in (None, 0) or browser_process.poll() not in (None, 0):
                    raise AssertionError("A cross-client probe failed")
                if time.monotonic() > deadline:
                    raise TimeoutError("Cross-client probes did not finish")
                time.sleep(0.1)
            outputs = {}
            for name in ("native", "browser"):
                logs[name].flush()
                raw = (directory / (name + ".log")).read_text()
                if password in raw:
                    raise AssertionError("A fixture credential appeared in diagnostics")
                if "SCRIPT ERROR" in raw:
                    raise AssertionError("Native script failed")
                receipts = [
                    value
                    for line in raw.splitlines()
                    if line.startswith("{") and (value := json.loads(line)).get("passed") is True
                ]
                if not receipts or receipts[-1].get("passed") is not True:
                    raise AssertionError(f"Missing {name} completion receipt")
                outputs[name] = receipts[-1]
                outputs[name]["diagnostics"] = [
                    line for line in raw.splitlines() if line.startswith(("WARNING:", "ERROR:"))
                ]
            return {
                "passed": True,
                "evidence_level": "compiled_native_headless_and_real_chrome_unchanged_web_real_isolated_service",
                "binary_sha256": digest(editor),
                "web_runtime": "Next.js development server from unchanged tracked inputs; production build is separate evidence",
                "fault_injection": "Native TCP proxy closes and refuses connections; Chrome network offline emulation for the Web phase",
                "tls_boundary": "Disposable local certificate trusted only by the isolated headless browser",
                **outputs,
            }
        except BaseException as error:
            for name, stream in logs.items():
                stream.flush()
                output = (directory / (name + ".log")).read_text().replace(password, "[REDACTED]")
                print(name + " diagnostics:\n" + output[-8000:])
            raise error
        finally:
            for process in (browser_process, native_process, web_process):
                stop(process)
            server.should_exit = True
            server_thread.join(timeout=10)
            proxy.shutdown()
            proxy_thread.join(timeout=3)
            for stream in logs.values():
                stream.close()
            store.db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("godot", "node", "chrome", "report"):
        parser.add_argument("--" + option, type=Path, required=True)
    args = parser.parse_args()
    for option in ("godot", "node", "chrome"):
        setattr(args, option, getattr(args, option).resolve(strict=True))
    web_files = subprocess.check_output(["git", "ls-files", "apps/tianxuan"], cwd=ROOT, text=True).splitlines()
    native_files = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "editor/docks/tianxuan").iterdir()
        if path.is_file() and not path.name.endswith(".gen.h")
    ]
    files = (
        web_files
        + native_files
        + [
            "tests/editor/" + name
            for name in (
                "run_tianxuan_web_native.py",
                "tianxuan_web_native.gd",
                "tianxuan_web_browser.mjs",
                "editor_test_isolation.py",
            )
        ]
    )
    fingerprints = {name: digest(ROOT / name) for name in files}
    with tempfile.TemporaryDirectory(prefix="tianxuan-web-native-") as temporary:
        receipt = exercise(Path(temporary).resolve(), args, web_files)
    assert fingerprints == {name: digest(ROOT / name) for name in files}, "Candidate inputs changed during validation"
    receipt["input_sha256"] = fingerprints
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps({
            "passed": True,
            "native_checks": len(receipt["native"]["checks"]),
            "browser_checks": len(receipt["browser"]["checks"]),
        })
    )


if __name__ == "__main__":
    main()
