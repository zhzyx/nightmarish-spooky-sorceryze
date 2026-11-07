"""Offline native Codex request lifetime checks; no provider or production Issue calls."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from editor_test_isolation import copy_editor
from run_requirements_intake import GH_FIXTURE

ROOT = Path(__file__).resolve().parents[2]
MOCK = r"""const fs = require('fs');
const path = require('path');
const root = process.env.GONGGONG_TEST_WORKSPACE;
const request = process.argv[4];
// Delay reading until the editor's _start_codex stack has returned.
setTimeout(() => {
  let value;
  try { value = JSON.parse(fs.readFileSync(request, 'utf8')); }
  catch (error) {
    fs.writeFileSync(path.join(root, 'wire', 'missing.json'), JSON.stringify({exists:false, code:error.code}));
    process.stdout.write(JSON.stringify({error:{code:'INVALID_REQUEST',message:'LIFETIME_REQUEST_MISSING'}}));
    process.exitCode = 1;
    return;
  }
  const name = value.messages.filter(m => m.role === 'user').at(-1).content;
  if (value.messages[0].content.includes('Requirements intake only')) {
    const request = JSON.parse(name).request;
    const answer = {decision:'continue',title:'Request lifetime fixture',category:'development',goal:request,scope:['isolated request lifetime'],acceptance:['request survives until terminal cleanup'],questions:[]};
    fs.writeFileSync(path.join(root, 'wire', 'intake-' + request + '.json'), '{}');
    setTimeout(() => process.stdout.write(JSON.stringify({choices:[{message:{role:'assistant',content:JSON.stringify(answer)},finish_reason:'stop'}]})), 300);
    return;
  }
  fs.writeFileSync(path.join(root, 'wire', name + '.json'), JSON.stringify({exists:true, request, pid:process.pid}));
  if (name === 'cancel') { setInterval(() => {}, 1000); return; }
  setTimeout(() => {
    if (name === 'failure') {
      process.stdout.write(JSON.stringify({error:{code:'PROCESS_EXIT',message:'LIFETIME_EXPECTED_FAILURE'}}));
      process.exitCode = 23;
    } else process.stdout.write(JSON.stringify({choices:[{message:{role:'assistant',content:'LIFETIME_SUCCESS'},finish_reason:'stop'}]}));
  }, 400);
}, 250);
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expect-missing", action="store_true")
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    errors = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            try:
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                assert "Requirements intake only" in request["messages"][0]["content"]
                value = json.loads(request["messages"][-1]["content"])
                answer = {
                    "decision": "continue",
                    "title": "Request lifetime fixture",
                    "category": "development",
                    "goal": value["request"],
                    "scope": ["isolated request lifetime"],
                    "acceptance": ["request survives until terminal cleanup"],
                    "questions": [],
                }
                body = json.dumps({
                    "choices": [
                        {"message": {"role": "assistant", "content": json.dumps(answer)}, "finish_reason": "stop"}
                    ]
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as error:
                errors.append(type(error).__name__)
                self.send_error(500)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="codex-lifetime-") as folder:
            root = Path(folder)
            binding = os.environ.pop("GONGGONG_WORKSPACE", None)
            try:
                isolated_editor = copy_editor(
                    args.godot.resolve().with_name(args.godot.name.replace(".console.exe", ".exe")), root / "bin"
                )
            finally:
                if binding is not None:
                    os.environ["GONGGONG_WORKSPACE"] = binding
            (root / "SConstruct").write_text("# Isolated engine root for native subprocess fixture.")
            for name in ["framework", "customizations", ".github"]:
                shutil.copytree(ROOT / name, root / name, ignore=shutil.ignore_patterns("__pycache__"))
            (root / "tools/codex_cli").mkdir(parents=True)
            for relative in ("tools/check_gonggong_distribution.py", "integrations/gonggong/frozen-distribution.json"):
                (root / relative).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, root / relative)
            shutil.copyfile(ROOT / "tools/gonggong_bridge.py", root / "tools/gonggong_bridge.py")
            (root / "tools/codex_cli/godot_bridge.js").write_text(MOCK, encoding="utf-8")
            shutil.copyfile(ROOT / "CURRENT_FRAMEWORK.json", root / "CURRENT_FRAMEWORK.json")
            (root / "framework/tools/agent-context.mjs").write_text(
                'process.stdout.write("ISOLATED_FRAMEWORK_CONTEXT_FIXTURE");', encoding="utf-8"
            )
            (root / ".gonggong-local.json").write_text("{}")
            (root / "work-items.json").write_text(
                json.dumps({"repository": "test/repo", "tenant_id": "gonggong-workspace"})
            )
            (root / "fake-issues.json").write_text(
                json.dumps([
                    {
                        "number": 6,
                        "state": "open",
                        "html_url": "https://github.com/test/repo/issues/6",
                        "body": "<!-- gonggong-request:isolated-gate -->",
                        "labels": [
                            {"name": n} for n in ["type:development", "status:in-progress", "workspace:gonggong"]
                        ],
                        "updated_at": "2026-01-01T00:00:00Z",
                    }
                ])
            )
            for command in [
                ["init", "--quiet"],
                ["remote", "add", "origin", "https://github.com/test/repo.git"],
                ["add", "framework", "customizations/platforms/data-collection/git-files/storage"],
                [
                    "-c",
                    "user.name=Isolated Test",
                    "-c",
                    "user.email=test@example.invalid",
                    "-c",
                    "commit.gpgsign=false",
                    "commit",
                    "--quiet",
                    "-m",
                    "Isolated fixture",
                ],
            ]:
                subprocess.run(["git", "-C", folder, *command], check=True, capture_output=True)
            subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(root / "customizations/platforms/data-collection/git-files/storage/diting_files.py"),
                    "init",
                    "--repo",
                    folder,
                ],
                check=True,
                capture_output=True,
            )
            project = root / "project"
            project.mkdir()
            for base in [root, project]:
                for name in ["auth", "api", "issue"]:
                    (base / name).write_text(GH_FIXTURE, encoding="utf-8")
            for name in ["wire", "temp", "appdata", "localappdata"]:
                (root / name).mkdir()
            (root / "not-executable.exe").write_text("Deliberately invalid executable for launch failure.")
            (root / "entry.js").write_text("// Native bridge replacement does not launch this entry.")
            (root / "entry.js").chmod(0o700)
            (root / "not-executable.exe").chmod(0o700)
            (root / "bin/editor_data/editor_settings-4.8.tres").write_text(
                '[gd_resource type="EditorSettings" format=3]\n\n[resource]\n'
                + '\nai_chat/backend = 0\nai_chat/endpoint = ""\n'
                + "ai_chat/cli_node = "
                + json.dumps(str(args.node.resolve()))
                + "\n"
                + "ai_chat/codex_entry = "
                + json.dumps(str(root / "entry.js"))
                + "\n"
                + "gonggong/python = "
                + json.dumps(sys.executable)
                + "\n"
                + "gonggong/workspace = "
                + json.dumps(str(root))
                + "\n"
                + "ai_chat/editor_control_bridge_enabled = false\n",
                encoding="utf-8",
            )
            (project / "project.godot").write_text(
                'config_version=5\n[application]\nconfig/name="Codex lifetime fixture"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
                encoding="utf-8",
            )
            shutil.copyfile(Path(__file__).with_name("codex_request_lifetime.gd"), project / "test.gd")
            env = {
                **{
                    key: value
                    for key, value in os.environ.items()
                    if not re.search(r"KEY|TOKEN|SECRET|CREDENTIAL|PASSWORD|AUTH", key, re.IGNORECASE)
                    and not key.upper().startswith(("GONGGONG_", "AINATIVE_", "OPENAI_", "ANTHROPIC_", "CODEX_"))
                },
                "APPDATA": str(root / "appdata"),
                "LOCALAPPDATA": str(root / "localappdata"),
                "TEMP": str(root / "temp"),
                "TMP": str(root / "temp"),
                "GODOT_AI_API_KEY": "",
                "GONGGONG_TEST_WORKSPACE": folder,
                "GONGGONG_WORKSPACE": folder,
                "GONGGONG_PYTHON": sys.executable,
                "GONGGONG_GH": sys.executable,
                "LIFETIME_NODE": str(args.node.resolve()),
                "LIFETIME_ENDPOINT": f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
                "LIFETIME_EXPECT_MISSING": "1" if args.expect_missing else "",
            }
            for name in ("HOME", "USERPROFILE", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
                private_path = root / "private-home" / name.lower()
                private_path.mkdir(parents=True, exist_ok=True)
                env[name] = str(private_path)
            env["PYTHONNOUSERSITE"] = "1"
            env.pop("NODE_OPTIONS", None)
            run = subprocess.run(
                [str(isolated_editor), "--headless", "--editor", "--path", str(project), "--script", "res://test.gd"],
                cwd=project,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.with_suffix(".log").write_text(run.stdout + run.stderr, encoding="utf-8")
            result = (
                json.loads((root / "result.json").read_text())
                if (root / "result.json").exists()
                else {"ok": False, "error": "driver_did_not_finish"}
            )
            result.update(
                fixture_sha256={
                    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in [Path(__file__), Path(__file__).with_name("codex_request_lifetime.gd")]
                },
                expected_missing=args.expect_missing,
                editor_sha256=hashlib.sha256(
                    args.godot.resolve().with_name(args.godot.name.replace(".console.exe", ".exe")).read_bytes()
                ).hexdigest(),
                process_exit=run.returncode,
                fixture_errors=errors,
                real_provider=False,
                request_files_after_exit=len(list((root / "temp").glob("godot_codex_request-*.json"))),
            )
            args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(result))
            assert run.returncode == 0 and result["ok"] and not errors, (
                "native request lifetime fixture failed; inspect local log"
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
