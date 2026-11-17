#!/usr/bin/env python3
"""Build/run the WebView2 hidden-HWND harness from an MSVC developer shell."""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from install_webview2 import install

ROOT = Path(__file__).resolve().parents[1]


class Fixture(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.requests.append(self.path)
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", self.server.external + "/redirected")
            self.end_headers()
            return
        if self.path == "/slow":
            time.sleep(2)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        try:
            marker = b""
            if self.server.is_external and self.path != "/execution-proof":
                marker = (
                    b"<script>parent.postMessage('external-page-executed','*');"
                    b"if(opener)opener.postMessage('external-page-executed','*');fetch('/execution-proof')</script>"
                )
            elif not self.server.is_external and self.path == "/allowed-frame":
                marker = b"<script>parent.postMessage('allowed-page-executed','*')</script>"
            self.wfile.write(
                b"<!doctype html><title>Fixture</title><h1>WebView2 fixture</h1><a href='/second'>Second</a>" + marker
            )
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def log_message(self, *_args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--arch", choices=("x86", "x64", "arm64"), default="x64")
    parser.add_argument("--package", type=Path)
    parser.add_argument("--compile-only", action="store_true")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("Windows is required; no simulated runtime pass is produced")
    sdk = install(args.package)
    build = args.build_dir.resolve()
    build.mkdir(parents=True, exist_ok=True)
    executable = build / "TestWebPlatformWindows.exe"
    command = [
        "cl",
        "/nologo",
        "/utf-8",
        "/std:c++17",
        "/Zc:__cplusplus",
        "/permissive-",
        "/MT",
        "/GR",
        "/O2",
        "/W4",
        "/WX",
        # Match Godot's MSVC warning policy and exception/header environment.
        *[
            "/wd" + warning
            for warning in ("4100", "4127", "4201", "4244", "4245", "4267", "4305", "4324", "4514", "4714", "4820")
        ],
        "/D_HAS_EXCEPTIONS=0",
        "/DWIN32",
        "/DWINDOWS_ENABLED",
        "/DWINVER=0x0A00",
        "/D_WIN32_WINNT=0x0A00",
        "/DNOMINMAX",
        "/DWEB_PLATFORM_WINDOWS_TESTS",
        "/DWEB_PLATFORM_WEBVIEW2_ENABLED",
        # Resolve windows.h through the actual engine wrapper, as SCons does.
        "/I" + str(ROOT / "platform/windows"),
        "/I" + str(ROOT),
        "/I" + str(sdk / "build/native/include"),
        str(ROOT / "editor/docks/WebPlatformNative.cpp"),
        str(ROOT / "editor/docks/WebPlatformWindows.cpp"),
        "/TP",
        str(ROOT / "tests/editor/TestWebPlatformWindows.cc"),
        "/Fe:" + str(executable),
        "/link",
        "user32.lib",
        "ole32.lib",
        "shell32.lib",
        "uuid.lib",
    ]
    subprocess.run(command, cwd=build, check=True)
    shutil.copyfile(sdk / "build/native" / args.arch / "WebView2Loader.dll", build / "WebView2Loader.dll")
    if args.compile_only:
        print("WEB_PLATFORM_WINDOWS_COMPILE_OK runtime=not-run")
        return
    servers = [ThreadingHTTPServer(("127.0.0.1", 0), Fixture) for _ in range(2)]
    origins = [f"http://127.0.0.1:{server.server_port}" for server in servers]
    for index, server in enumerate(servers):
        server.is_external = index == 1
        server.requests = []
        server.external = origins[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
    result = None
    try:
        with tempfile.TemporaryDirectory(prefix="godot-webview2-test-") as profile:
            environment = os.environ.copy()
            environment["GODOT_WEB_PLATFORM_TEST_DATA"] = profile
            # Isolate from user-specified WebView2 overrides during validation.
            for name in list(environment):
                if name.startswith("WEBVIEW2_"):
                    environment.pop(name)
            result = subprocess.run(
                [str(executable), *origins], env=environment, capture_output=True, text=True, timeout=180
            )
            print(result.stdout, end="")
            print(result.stderr, end="")
            # Runtime processes may release the isolated profile shortly after Close.
            for _ in range(50):
                try:
                    shutil.rmtree(profile)
                    break
                except PermissionError:
                    time.sleep(0.1)
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
    report = {
        "compile": "passed",
        "runtime": "passed" if result.returncode == 0 and "/execution-proof" not in servers[1].requests else "failed",
        "returncode": result.returncode,
        "hidden_hwnd": True,
        "external_requests": servers[1].requests,
        "navigation_policy_limit": "WebView2 may speculatively issue GET before cancellation; document/script rejection is checked, not network isolation.",
        "stdout": result.stdout,
        "stderr": result.stderr,
        "manual_not_run": ["real editor input and IME", "native upload/download dialogs", "visual DPI/modal layout"],
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    if report["runtime"] != "passed":
        raise SystemExit(f"WebView2 harness failed: {report}")


if __name__ == "__main__":
    main()
