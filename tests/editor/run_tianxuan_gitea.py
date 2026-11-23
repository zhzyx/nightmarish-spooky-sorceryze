"""Compiled native controls against isolated real Tianxuan and Gitea services.

Supply a verified Gitea binary. All accounts, credentials, repositories, settings
and server processes are disposable. No existing hosting deployment is contacted.
"""

import argparse
import base64
import getpass
import hashlib
import json
import os
import secrets
import socket
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import httpx
import uvicorn
from fastapi import Request
from fastapi.responses import JSONResponse
from run_tianxuan_controller import ROOT, NativeStore, Tianxuan, copy_editor, create_app, sanitized_environment


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@contextmanager
def lossy_hosting_proxy(origin):
    # Forward to the real service, then drop one acknowledged write response.
    drops = []
    control = {"reject_auth": False}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def forward(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            if control["reject_auth"]:
                denied = b'{"message":"invalid upstream token"}'
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(denied)))
                self.end_headers()
                self.wfile.write(denied)
                return
            headers = {
                key: value
                for key, value in self.headers.items()
                if key.lower() not in {"host", "connection", "content-length"}
            }
            with httpx.Client(trust_env=False, timeout=30) as transport:
                response = transport.request(self.command, origin + self.path, headers=headers, content=body)
            if (
                self.command == "POST"
                and self.path == "/api/v1/user/repos"
                and json.loads(body).get("name") == "native-unknown"
                and not drops
            ):
                assert response.status_code == 201
                drops.append(response.status_code)
                self.close_connection = True
                self.connection.shutdown(socket.SHUT_RDWR)
                return
            self.send_response(response.status_code)
            self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(response.content)))
            self.end_headers()
            self.wfile.write(response.content)

        do_GET = do_POST = do_PATCH = do_PUT = do_DELETE = forward

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:" + str(server.server_port), drops, control
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def exercise(directory, binary, gitea):
    host = directory / "hosting"
    host.mkdir()
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    password = secrets.token_urlsafe(36)
    config = host / "app.ini"
    config.write_text(
        f"""APP_NAME = Native Tianxuan isolated acceptance
RUN_USER = {getpass.getuser()}
RUN_MODE = prod
[server]
APP_DATA_PATH = {host / "data"}
HTTP_ADDR = 127.0.0.1
HTTP_PORT = {port}
DOMAIN = 127.0.0.1
ROOT_URL = {origin}/
DISABLE_SSH = true
OFFLINE_MODE = true
[database]
DB_TYPE = sqlite3
PATH = {host / "gitea.db"}
[repository]
ROOT = {host / "repos"}
[git]
HOME_PATH = {host / "git-home"}
[security]
INSTALL_LOCK = true
SECRET_KEY = {secrets.token_hex(32)}
[service]
DISABLE_REGISTRATION = true
REQUIRE_SIGNIN_VIEW = true
[log]
MODE = file
ROOT_PATH = {host / "log"}
LEVEL = Warn
[mailer]
ENABLED = false
""",
        encoding="utf-8",
    )
    config.chmod(0o600)
    environment = {
        key: value
        for key, value in sanitized_environment(directory).items()
        if not key.startswith(("GITEA_", "TIANXUAN_", "TX_"))
    }
    command = [str(gitea), "--work-path", str(host), "--config", str(config)]

    def cli(arguments):
        result = subprocess.run(
            [*command, *arguments],
            cwd=host,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        if result.returncode:
            raise RuntimeError(
                "Isolated Gitea CLI failed: " + (result.stdout + result.stderr)[-2500:].replace(password, "[redacted]")
            )
        return result.stdout

    cli(["migrate"])
    for username in ("native-author", "native-reviewer"):
        cli([
            "admin",
            "user",
            "create",
            "--username",
            username,
            "--email",
            username + "@example.invalid",
            "--password",
            password,
            "--must-change-password=false",
            *(["--admin"] if username == "native-author" else []),
        ])
    token = cli([
        "admin",
        "user",
        "generate-access-token",
        "--username",
        "native-author",
        "--token-name",
        "isolated-native-ui",
        "--scopes",
        "all",
        "--raw",
    ]).strip()
    if not token or any(character not in "0123456789abcdef" for character in token):
        raise AssertionError("Gitea did not return an isolated access token")
    with (host / "process.log").open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            [*command, "web"], cwd=host, env=environment, stdout=output, stderr=subprocess.STDOUT
        )
        try:
            with httpx.Client(
                base_url=origin + "/api/v1", headers={"Authorization": "token " + token}, timeout=15, trust_env=False
            ) as client:
                for _ in range(200):
                    if process.poll() is not None:
                        raise RuntimeError("Private Gitea server exited: " + (host / "process.log").read_text()[-2500:])
                    try:
                        if client.get("/version").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.1)
                else:
                    raise TimeoutError("Private Gitea startup timed out")

                def request(method, path, value=None):
                    response = client.request(method, path, json=value)
                    if response.is_error:
                        raise AssertionError(f"Gitea setup/readback {method} {path}: {response.status_code}")
                    return response.json() if response.content else None

                request(
                    "POST",
                    "/user/repos",
                    dict(name="shared-fixture", private=True, auto_init=True, default_branch="main"),
                )
                repo = "/repos/native-author/shared-fixture"
                request("PUT", repo + "/collaborators/native-reviewer", dict(permission="write"))
                request("POST", repo + "/branches", dict(new_branch_name="feature", old_branch_name="main"))
                request("POST", repo + "/branches", dict(new_branch_name="staging", old_branch_name="main"))
                content = b"Created for the native repository acceptance.\n"
                request(
                    "POST",
                    repo + "/contents/native.txt",
                    dict(branch="feature", message="Isolated feature", content=base64.b64encode(content).decode()),
                )
                before = request("GET", repo + "/branches/main")["commit"]["id"]
                advances = []

                def remote_change(action):
                    if action in {"auth_expired", "auth_restored"}:
                        proxy_control["reject_auth"] = action == "auth_expired"
                        return {"changed": True}
                    if action in {"retarget", "restore_target"}:
                        return request(
                            "PATCH", repo + "/pulls/1", dict(base="staging" if action == "retarget" else "main")
                        )
                    if action == "advance":
                        filename = f"race-{len(advances)}.txt"
                        request(
                            "POST",
                            repo + "/contents/" + filename,
                            dict(
                                branch="feature",
                                message="Concurrent revision",
                                content=base64.b64encode(b"concurrent\n").decode(),
                            ),
                        )
                        sha = request("GET", repo + "/branches/feature")["commit"]["id"]
                        for _ in range(100):
                            if request("GET", repo + "/pulls/1")["head"]["sha"] == sha:
                                break
                            time.sleep(0.05)
                        else:
                            raise AssertionError("Gitea did not advance the pull head")
                        advances.append(sha)
                        return {"head_sha": sha}
                    releases = request("GET", repo + "/releases")
                    return request(
                        "PATCH",
                        repo + "/releases/" + str(releases[0]["id"]),
                        dict(name="Collaborator title", body="Collaborator release notes"),
                    )

                with lossy_hosting_proxy(origin) as (proxy, drops, proxy_control):
                    report = native(directory, binary, proxy, token, password, remote_change)
                    assert drops == [201]
                assert len(advances) == 2
                pulls = request("GET", repo + "/pulls?state=closed")
                assert len(pulls) == 1 and pulls[0]["merged"] is True
                reviews = request("GET", repo + f"/pulls/{pulls[0]['number']}/reviews")
                assert any(
                    item["user"]["login"] == "native-reviewer" and item["state"] == "APPROVED" for item in reviews
                )
                after = request("GET", repo + "/branches/main")["commit"]["id"]
                assert after != before
                actual = request("GET", repo + "/contents/native.txt?ref=main")
                assert base64.b64decode(actual["content"]) == content
                releases = request("GET", repo + "/releases")
                assert len(releases) == 1 and releases[0]["tag_name"] == "v-native-1" and releases[0]["draft"] is False
                assert releases[0]["name"] == "原生正式发布"
                assert request("GET", "/repos/native-author/native-created")["private"] is True
                assert request("GET", "/repos/native-author/native-unknown")["private"] is True
                assert releases[0]["body"] == "Collaborator release notes"
                assert any(item["commit_id"] == advances[-1] and item["state"] == "APPROVED" for item in reviews)
                report["gitea_readback"] = dict(
                    passed=True,
                    version=request("GET", "/version")["version"],
                    binary_sha256=digest(gitea),
                    main_before=before,
                    main_after=after,
                    merge_content_verified=True,
                    independent_review_verified=True,
                    native_repository_created=True,
                    published_release_verified=True,
                    stale_head_rejected=True,
                    retargeted_pull_rejected=True,
                    upstream_auth_failure_preserves_session=True,
                    stale_release_rejected=True,
                    real_upstream_lost_ack_retained=True,
                )
                return report
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def native(directory, binary, origin, token, password, remote_change):
    store = Tianxuan(str(directory / "domain.sqlite"))
    owner = store.register("Hosting fixture", "first@example.invalid", password)
    reviewer = store.add_member(owner["user_id"], "reviewer@example.invalid", password, role="editor")
    store.link_identity(owner["user_id"], "gitea", "native-author", owner["user_id"])
    store.link_identity(owner["user_id"], "gitea", "native-reviewer", reviewer["user_id"])
    project = directory / "project"
    project.mkdir()
    (project / "project.godot").write_text(
        'config_version=5\n[application]\nconfig/name="Native hosting acceptance"\n', encoding="utf-8"
    )
    (project / "probe.gd").write_bytes(Path(__file__).with_name("tianxuan_gitea.gd").read_bytes())
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        editor = copy_editor(binary, directory / "engine")
    environment = {key: value for key, value in os.environ.items() if not key.startswith("TIANXUAN_")}
    environment.update(
        TIANXUAN_AUTH_MODE="accounts",
        TIANXUAN_REQUIRE_KEYS="0",
        TIANXUAN_GITEA_URL=origin,
        TIANXUAN_GITEA_TOKEN=token,
        TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
        TIANXUAN_TENANT_ID=owner["tenant_id"],
    )
    with patch.dict(os.environ, environment, clear=True), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        api = "http://127.0.0.1:" + str(sock.getsockname()[1])
        app = create_app(store, native_store=NativeStore(directory / "native.sqlite"), required_approvals=1)

        @app.post("/api/v1/native-test/hosting/{action}")
        def change_hosting(action: str):
            return remote_change(action)

        @app.middleware("http")
        async def legacy_unknown_status(request: Request, call_next):
            response = await call_next(request)
            # Older Tianxuan services collapse Gitea transport failures to 400.
            if request.method == "POST" and request.url.path == "/api/v1/repos" and response.status_code == 502:
                return JSONResponse({"detail": "upstream response lost"}, status_code=400)
            return response

        server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 20
            while not server.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise TimeoutError("Isolated Tianxuan service did not start")
                time.sleep(0.05)
            child_env = {
                key: value
                for key, value in sanitized_environment(directory).items()
                if not key.startswith(("TIANXUAN_", "TX_"))
            }
            child_env.update(TIANXUAN_API=api, TX_PASSWORD=password)
            result = subprocess.run(
                [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                cwd=directory,
                env=child_env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=180,
            )
            output = result.stdout + result.stderr
            if password in output or token in output:
                raise AssertionError("Fixture credential appeared in editor output")
            reports = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
            report = next((value for value in reports if value.get("passed") is True), None)
            if result.returncode or "SCRIPT ERROR" in output or report is None:
                raise AssertionError(output[-10000:])
            report.update(
                binary_sha256=digest(editor),
                process_diagnostics=[
                    line for line in result.stderr.splitlines() if line.startswith(("ERROR:", "WARNING:"))
                ],
            )
            return report
        finally:
            server.should_exit = True
            thread.join(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--gitea", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    files = [
        path
        for path in (ROOT / "editor/docks/tianxuan").iterdir()
        if path.is_file() and not path.name.endswith(".gen.h")
    ]
    files += [
        Path(__file__),
        Path(__file__).with_name("tianxuan_gitea.gd"),
        Path(__file__).with_name("run_tianxuan_controller.py"),
        ROOT / "customizations/components/tianxuan/server/api.py",
        ROOT / "customizations/components/tianxuan/server/schemas.py",
        ROOT / "customizations/components/tianxuan/duobao/gitea_client.py",
    ]
    hashes = {path.relative_to(ROOT).as_posix(): digest(path) for path in files}
    with tempfile.TemporaryDirectory(prefix="tianxuan-gitea-") as temporary:
        report = exercise(Path(temporary).resolve(), args.godot.resolve(strict=True), args.gitea.resolve(strict=True))
    if any(digest(ROOT / path) != value for path, value in hashes.items()):
        raise AssertionError("Candidate inputs changed during the hosting regression")
    report.update(
        input_sha256=hashes,
        evidence_level="compiled_native_controls_real_local_gitea_and_tianxuan",
        display_boundary="Headless controls with disposable real hosting; no production deployment, native display or Windows acceptance.",
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(passed=True, checks=len(report["checks"]), gitea=report["gitea_readback"]["version"])))


if __name__ == "__main__":
    main()
